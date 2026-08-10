from __future__ import annotations

import json
import re
from typing import Optional

from harness.classifier import classify, get_repair_prompt
from harness.executor import CodeExecutor
from harness.guardrail import GuardrailResult, check
from harness.lm import BaseLM
from harness.memory import MemoryStore
from harness.models import Action, FailureType, LoopResult, RoundRecord

_DEFAULT_MAX_ROUNDS = 8
_STALL_THRESHOLD = 3
_PARSE_RETRY_LIMIT = 2

_SYSTEM_PROMPT = """You are a Python debugging assistant. Your job is to fix broken Python code.

For each message, respond with a JSON object (and nothing else) in one of these formats:

Run code:
{"action": "run_code", "payload": "<full python code here>"}

Write a file:
{"action": "write_file", "payload": "<file content>"}

Shell command:
{"action": "shell", "payload": "<shell command>"}

Give up:
{"action": "give_up", "payload": ""}

Rules:
- Always output valid JSON and nothing else.
- Always include the full corrected code in payload when using run_code.
- Do not delete assert statements; fix the logic instead.
{memory_context}"""

_FORMAT_ERROR_MSG = (
    'Your previous response was not valid JSON in the expected format. '
    'Respond ONLY with a JSON object like: {"action": "run_code", "payload": "..."}'
)


def _parse_action(response: str) -> Optional[Action]:
    text = response.strip()
    # Try to extract JSON even if wrapped in markdown code fences
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        action_type = data.get("action")
        payload = data.get("payload", "")
        if action_type not in ("run_code", "write_file", "shell", "give_up"):
            return None
        return Action(type=action_type, payload=str(payload))
    except (json.JSONDecodeError, KeyError):
        return None


def run(
    code: str,
    lm: BaseLM,
    memory: Optional[MemoryStore] = None,
    max_rounds: int = _DEFAULT_MAX_ROUNDS,
    executor: Optional[CodeExecutor] = None,
    _resume_state: Optional[dict] = None,
) -> LoopResult:
    if executor is None:
        executor = CodeExecutor()

    if _resume_state:
        session_id = _resume_state["session_id"]
        messages = _resume_state["messages"]
        round_no = _resume_state["round_no"]
        failure_history: list[FailureType] = _resume_state["failure_history"]
        pending_action: Action = _resume_state["pending_action"]
        approved: bool = _resume_state["approved"]
    else:
        if memory is None:
            memory = MemoryStore()

        session_id = memory.start_session(code)
        context = memory.build_context_summary()
        system_content = _SYSTEM_PROMPT.replace("{memory_context}", context)

        messages: list[dict] = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": f"Fix this Python code:\n\n```python\n{code}\n```",
            },
        ]
        round_no = 0
        failure_history: list[FailureType] = []
        pending_action = None
        approved = False

    # Handle HITL resume: either execute or inject rejection
    if pending_action is not None:
        if approved:
            run_result = executor.run(pending_action)
        else:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "[GUARDRAIL] Action was rejected by user. "
                        "Please provide an alternative solution that does not require "
                        "dangerous operations."
                    ),
                }
            )
            pending_action = None

    while round_no < max_rounds:
        # If we just handled a HITL-approved action, skip LM call this iteration
        if pending_action is not None and approved:
            action = pending_action
            pending_action = None
            approved = False
        else:
            # LM call with parse-retry loop
            parse_failures = 0
            action = None
            while parse_failures <= _PARSE_RETRY_LIMIT:
                lm_response = lm.complete(messages)
                messages.append({"role": "assistant", "content": lm_response})
                action = _parse_action(lm_response)
                if action is not None:
                    break
                parse_failures += 1
                if parse_failures <= _PARSE_RETRY_LIMIT:
                    messages.append({"role": "user", "content": _FORMAT_ERROR_MSG})

            if action is None:
                if memory:
                    memory.finish_session(session_id, None, False, round_no)
                return LoopResult(
                    status="failed",
                    final_code=None,
                    rounds=round_no,
                    session_id=session_id,
                )

        round_no += 1

        if action.type == "give_up":
            if memory:
                memory.finish_session(session_id, None, False, round_no)
            return LoopResult(
                status="give_up",
                final_code=None,
                rounds=round_no,
                session_id=session_id,
            )

        # Guardrail check
        guardrail = check(action)

        if guardrail == GuardrailResult.BLOCK:
            reject_msg = (
                f"[GUARDRAIL] BLOCKED: Action '{action.type}' with payload matched a "
                "high-risk pattern and was rejected. Please provide a safe alternative."
            )
            messages.append({"role": "user", "content": reject_msg})
            if memory:
                memory.append_round(
                    session_id,
                    RoundRecord(
                        round_no=round_no,
                        failure_type="BLOCK",
                        error_message=reject_msg,
                        action_taken=action.type,
                        guardrail_decision="BLOCK",
                    ),
                )
            continue

        if guardrail == GuardrailResult.HITL_REQUIRED:
            if memory:
                memory.append_round(
                    session_id,
                    RoundRecord(
                        round_no=round_no,
                        failure_type="HITL_REQUIRED",
                        error_message="Awaiting human approval",
                        action_taken=action.type,
                        guardrail_decision="HITL_REQUIRED",
                    ),
                )
            return LoopResult(
                status="hitl_pause",
                final_code=action.payload,
                rounds=round_no,
                session_id=session_id,
            )

        # Execute
        run_result = executor.run(action)
        failure_info = classify(run_result)

        if memory:
            memory.append_round(
                session_id,
                RoundRecord(
                    round_no=round_no,
                    failure_type=failure_info.type.value,
                    error_message=failure_info.message,
                    action_taken=action.type,
                    guardrail_decision="ALLOW",
                ),
            )

        if run_result.exit_code == 0:
            if memory:
                memory.finish_session(session_id, action.payload, True, round_no)
            return LoopResult(
                status="success",
                final_code=action.payload,
                rounds=round_no,
                session_id=session_id,
            )

        # Stall detection
        failure_history.append(failure_info.type)
        if (
            len(failure_history) >= _STALL_THRESHOLD
            and len(set(failure_history[-_STALL_THRESHOLD:])) == 1
        ):
            if memory:
                memory.finish_session(session_id, None, False, round_no)
            return LoopResult(
                status="stall",
                final_code=None,
                rounds=round_no,
                session_id=session_id,
            )

        repair_prompt = get_repair_prompt(failure_info)
        feedback = (
            f"Execution failed (round {round_no}).\n"
            f"Exit code: {run_result.exit_code}\n"
            f"stderr:\n{run_result.stderr}\n\n"
            f"{repair_prompt}"
        )
        messages.append({"role": "user", "content": feedback})

    if memory:
        memory.finish_session(session_id, None, False, round_no)
    return LoopResult(
        status="failed",
        final_code=None,
        rounds=round_no,
        session_id=session_id,
    )
