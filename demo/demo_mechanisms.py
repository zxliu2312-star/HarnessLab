"""
demo_mechanisms.py — Three mechanism demonstrations using MockLM (no network needed).

Demo 1: Guardrail BLOCK — high-risk shell command is blocked before execution.
Demo 2: Feedback loop — NameError detected, repaired, agent succeeds in round 2.
Demo 3: Stall detection — same TypeError repeated 3 times triggers stall halt.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Allow running from project root without installing
sys.path.insert(0, str(Path(__file__).parent.parent))

from harness.agent_loop import run
from harness.executor import CodeExecutor
from harness.guardrail import GuardrailResult, check
from harness.lm import MockLM
from harness.memory import MemoryStore
from harness.models import Action


def _resp(action: str, payload: str) -> str:
    return json.dumps({"action": action, "payload": payload})


def _sep(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Demo 1: Guardrail BLOCK
# ---------------------------------------------------------------------------
def demo_guardrail_block() -> None:
    _sep("Demo 1: Guardrail BLOCK")

    dangerous_action = Action(type="shell", payload="rm -rf /tmp && rm -rf /")
    decision = check(dangerous_action)

    print(f"  Action  : {dangerous_action.type!r}  payload={dangerous_action.payload!r}")
    print(f"  Decision: {decision.value}")

    assert decision == GuardrailResult.BLOCK, "Expected BLOCK"

    # Verify via the full loop: MockLM first returns a blocked shell command,
    # then the agent gets the rejection feedback and returns safe code.
    mem = MemoryStore(db_path=Path(tempfile.mkdtemp()) / "demo1.db")
    lm = MockLM([
        _resp("shell", "rm -rf /tmp && rm -rf /"),
        _resp("run_code", "print('safe hello')"),
    ])
    result = run("print('helo')", lm, memory=mem)

    print(f"  Loop result status : {result.status}")
    print(f"  Rounds             : {result.rounds}")
    assert result.status == "success", f"Expected success, got {result.status}"
    print("  [PASS] executor was NOT called with dangerous payload; loop recovered.")


# ---------------------------------------------------------------------------
# Demo 2: Feedback loop — NameError detected → repaired
# ---------------------------------------------------------------------------
def demo_feedback_loop() -> None:
    _sep("Demo 2: Feedback Loop (NameError → repair → success)")

    broken_code = "print(x)"
    fixed_code = "x = 42\nprint(x)"

    mem = MemoryStore(db_path=Path(tempfile.mkdtemp()) / "demo2.db")
    lm = MockLM([
        _resp("run_code", broken_code),   # round 1: still broken
        _resp("run_code", fixed_code),    # round 2: fixed
    ])

    result = run(broken_code, lm, memory=mem)

    print(f"  Input code         : {broken_code!r}")
    print(f"  Loop result status : {result.status}")
    print(f"  Rounds used        : {result.rounds}")
    print(f"  Final code         : {result.final_code!r}")

    assert result.status == "success", f"Expected success, got {result.status}"
    assert result.rounds == 2, f"Expected 2 rounds, got {result.rounds}"
    print("  [PASS] Feedback loop repaired NameError in 2 rounds.")


# ---------------------------------------------------------------------------
# Demo 3: Stall detection — same TypeError 3 times
# ---------------------------------------------------------------------------
def demo_stall_detection() -> None:
    _sep("Demo 3: Stall Detection (TypeError × 3)")

    type_error_code = "result = 1 + 'two'"

    mem = MemoryStore(db_path=Path(tempfile.mkdtemp()) / "demo3.db")
    lm = MockLM([
        _resp("run_code", type_error_code),
        _resp("run_code", type_error_code),
        _resp("run_code", type_error_code),
        _resp("run_code", type_error_code),  # should never be reached
    ])

    result = run(type_error_code, lm, memory=mem, max_rounds=10)

    print(f"  Input code         : {type_error_code!r}")
    print(f"  Loop result status : {result.status}")
    print(f"  Rounds until stall : {result.rounds}")

    assert result.status == "stall", f"Expected stall, got {result.status}"
    assert result.rounds == 3, f"Expected stall at round 3, got {result.rounds}"
    print("  [PASS] Stall detected after TYPE_ERROR × 3, loop halted at round 3.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\nCoding Agent Harness — Mechanism Demonstrations")
    print("(All demos use MockLM — no network required)\n")

    try:
        demo_guardrail_block()
        demo_feedback_loop()
        demo_stall_detection()
        print()
        print("=" * 60)
        print("  All 3 demos passed.")
        print("=" * 60)
        print()
    except AssertionError as e:
        print(f"\n[FAIL] {e}", file=sys.stderr)
        sys.exit(1)
