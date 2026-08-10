"""
Tests for HITL state management logic (without Streamlit dependency).
Tests the agent_loop HITL pause/resume cycle directly.
"""
import tempfile
import json
from pathlib import Path

import pytest

from harness.agent_loop import run
from harness.lm import MockLM
from harness.memory import MemoryStore
from harness.models import Action


@pytest.fixture
def mem(tmp_path):
    return MemoryStore(db_path=tmp_path / "test.db")


def _hitl_response(payload: str = "os.remove('/tmp/f')") -> str:
    return json.dumps({"action": "run_code", "payload": payload})


def _good_response(code: str = "print('fixed')") -> str:
    return json.dumps({"action": "run_code", "payload": code})


def test_hitl_pause_status(mem):
    lm = MockLM([_hitl_response()])
    result = run("code", lm, memory=mem)
    assert result.status == "hitl_pause"


def test_hitl_pause_contains_pending_payload(mem):
    payload = "os.remove('/tmp/important.txt')"
    lm = MockLM([_hitl_response(payload)])
    result = run("code", lm, memory=mem)
    assert result.status == "hitl_pause"
    assert result.final_code == payload


def test_hitl_resume_approved_succeeds(mem):
    fixed_code = "print('safe_result')"
    pending_action = Action(type="run_code", payload=fixed_code)

    resume_state = {
        "session_id": mem.start_session("original"),
        "messages": [{"role": "user", "content": "Fix this code:\n\noriginal"}],
        "round_no": 1,
        "failure_history": [],
        "pending_action": pending_action,
        "approved": True,
    }

    lm = MockLM([])  # No more LM calls needed after approval
    result = run("original", lm, memory=mem, _resume_state=resume_state)
    assert result.status == "success"
    assert result.final_code == fixed_code


def test_hitl_resume_rejected_continues(mem):
    fixed_code = "print('safe')"
    pending_action = Action(type="run_code", payload="os.remove('/tmp/x')")

    session_id = mem.start_session("original")
    resume_state = {
        "session_id": session_id,
        "messages": [{"role": "user", "content": "Fix this code:\n\noriginal"}],
        "round_no": 1,
        "failure_history": [],
        "pending_action": pending_action,
        "approved": False,
    }

    lm = MockLM([_good_response(fixed_code)])
    result = run("original", lm, memory=mem, _resume_state=resume_state)
    assert result.status == "success"
    assert result.final_code == fixed_code


def test_hitl_session_recorded_in_memory(mem):
    lm = MockLM([_hitl_response()])
    result = run("code", lm, memory=mem)
    assert result.status == "hitl_pause"
    sessions = mem.get_recent_sessions()
    assert any(s.session_id == result.session_id for s in sessions)


def test_hitl_round_no_incremented(mem):
    lm = MockLM([_hitl_response()])
    result = run("code", lm, memory=mem)
    assert result.rounds == 1
