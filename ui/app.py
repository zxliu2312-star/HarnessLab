from __future__ import annotations

import os

import streamlit as st

from harness import agent_loop
from harness.lm import LMRateLimitError, OpenAILM
from harness.memory import MemoryStore

st.set_page_config(page_title="Coding Agent Harness", layout="centered")

_MEMORY = MemoryStore()


def _get_lm():
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL") or None
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    if not api_key:
        try:
            import keyring
            api_key = keyring.get_password("coding-agent-harness", "openai_api_key") or ""
        except Exception:
            pass
    if not api_key:
        return None
    return OpenAILM(api_key=api_key, model=model, base_url=base_url)


def _render_api_banner():
    lm = _get_lm()
    if lm is None:
        st.warning(
            "No API key found. Set `OPENAI_API_KEY` in your environment or `.env` file, "
            "or run `python -m harness.cli setup` to store it in your system keychain.",
            icon="⚠️",
        )
    return lm


def _render_history():
    sessions = _MEMORY.get_recent_sessions(limit=10)
    if not sessions:
        st.info("No sessions yet.")
        return
    for s in sessions:
        status_icon = "✅" if s.success else "❌"
        label = f"{status_icon} {s.created_at[:19]}  —  {s.rounds} round(s)"
        with st.expander(label):
            if s.failure_types:
                st.write("**Error types encountered:**", ", ".join(s.failure_types))
            else:
                st.write("No errors recorded.")


def main():
    st.title("Coding Agent Harness")
    st.caption("Paste broken Python code and let the agent fix it automatically.")

    lm = _render_api_banner()

    code_input = st.text_area(
        "Python code to fix",
        height=200,
        placeholder="Paste your buggy Python code here...",
        key="code_input",
    )

    run_clicked = st.button("Run Agent", disabled=(lm is None), type="primary")

    # Output area
    output_placeholder = st.empty()

    # HITL approval area
    if st.session_state.get("hitl_pending"):
        pending = st.session_state["hitl_state"]
        st.warning("The agent wants to perform a potentially dangerous operation.")
        st.code(pending["pending_action_payload"], language="python")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Approve", type="primary"):
                _resume_hitl(approved=True, lm=lm, output_placeholder=output_placeholder)
        with col2:
            if st.button("Reject"):
                _resume_hitl(approved=False, lm=lm, output_placeholder=output_placeholder)

    if run_clicked and code_input.strip():
        st.session_state["hitl_pending"] = False
        _run_agent(code_input, lm, output_placeholder)

    # History
    st.divider()
    st.subheader("Session History")
    _render_history()


def _run_agent(code: str, lm, output_placeholder):
    status_box = output_placeholder.container()
    progress_msgs = []

    def render_progress(msg: str):
        progress_msgs.append(msg)
        with status_box:
            for m in progress_msgs:
                st.write(m)

    render_progress("Starting agent...")

    with st.spinner("Agent is running..."):
        try:
            result = agent_loop.run(code, lm, memory=_MEMORY)
        except LMRateLimitError as e:
            output_placeholder.error(f"Rate limit error: {e}. Please wait and try again.")
            return
        except Exception as e:
            output_placeholder.error(f"Unexpected error: {e}")
            return

    _handle_result(result, code, lm, output_placeholder)


def _handle_result(result, code, lm, output_placeholder):
    if result.status == "hitl_pause":
        st.session_state["hitl_pending"] = True
        st.session_state["hitl_state"] = {
            "pending_action_payload": result.final_code or "",
            "original_code": code,
        }
        st.rerun()
        return

    with output_placeholder.container():
        if result.status == "success":
            st.success(f"Fixed in {result.rounds} round(s)!")
            st.code(result.final_code or "", language="python")
        elif result.status == "stall":
            st.error(
                f"Agent stalled after {result.rounds} round(s) — "
                "same error repeated 3 times."
            )
        elif result.status == "give_up":
            st.warning(f"Agent gave up after {result.rounds} round(s).")
        elif result.status == "hitl_pause":
            pass  # handled above
        else:
            st.error(f"Agent failed after {result.rounds} round(s).")


def _resume_hitl(approved: bool, lm, output_placeholder):
    hitl_state = st.session_state.get("hitl_state", {})
    st.session_state["hitl_pending"] = False

    from harness.models import Action

    payload = hitl_state.get("pending_action_payload", "")
    original_code = hitl_state.get("original_code", "")

    pending_action = Action(type="run_code", payload=payload)

    resume_state = {
        "session_id": hitl_state.get("session_id", ""),
        "messages": hitl_state.get("messages", [
            {"role": "user", "content": f"Fix this code:\n\n{original_code}"}
        ]),
        "round_no": hitl_state.get("round_no", 1),
        "failure_history": hitl_state.get("failure_history", []),
        "pending_action": pending_action,
        "approved": approved,
    }

    with st.spinner("Resuming agent..."):
        try:
            result = agent_loop.run(
                original_code, lm, memory=_MEMORY, _resume_state=resume_state
            )
        except LMRateLimitError as e:
            output_placeholder.error(f"Rate limit error: {e}")
            return

    _handle_result(result, original_code, lm, output_placeholder)


if __name__ == "__main__":
    main()
