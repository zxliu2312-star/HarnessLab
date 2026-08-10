import tempfile
from pathlib import Path

import pytest

from harness.memory import MemoryStore
from harness.models import RoundRecord, SessionSummary


@pytest.fixture
def store(tmp_path):
    return MemoryStore(db_path=tmp_path / "test.db")


def test_start_session_returns_uuid(store):
    sid = store.start_session("print('hello')")
    assert isinstance(sid, str)
    assert len(sid) == 36  # UUID format


def test_start_session_creates_record(store):
    sid = store.start_session("x = 1")
    sessions = store.get_recent_sessions()
    assert any(s.session_id == sid for s in sessions)


def test_append_round_stores_data(store):
    sid = store.start_session("code")
    rr = RoundRecord(
        round_no=1,
        failure_type="NAME_ERROR",
        error_message="name 'x' is not defined",
        action_taken="run_code",
        guardrail_decision="ALLOW",
    )
    store.append_round(sid, rr)
    sessions = store.get_recent_sessions()
    match = next(s for s in sessions if s.session_id == sid)
    assert "NAME_ERROR" in match.failure_types


def test_finish_session_updates_record(store):
    sid = store.start_session("code")
    store.finish_session(sid, final_code="print('fixed')", success=True, rounds=2)
    sessions = store.get_recent_sessions()
    match = next(s for s in sessions if s.session_id == sid)
    assert match.success is True
    assert match.rounds == 2


def test_finish_session_failed(store):
    sid = store.start_session("bad code")
    store.finish_session(sid, final_code=None, success=False, rounds=8)
    sessions = store.get_recent_sessions()
    match = next(s for s in sessions if s.session_id == sid)
    assert match.success is False


def test_get_recent_sessions_limit(store):
    for i in range(7):
        sid = store.start_session(f"code {i}")
        store.finish_session(sid, None, False, 1)
    sessions = store.get_recent_sessions(limit=5)
    assert len(sessions) == 5


def test_get_recent_sessions_ordered_desc(store):
    for i in range(3):
        sid = store.start_session(f"code {i}")
        store.finish_session(sid, None, False, 1)
    sessions = store.get_recent_sessions()
    created_ats = [s.created_at for s in sessions]
    assert created_ats == sorted(created_ats, reverse=True)


def test_build_context_summary_empty(store):
    summary = store.build_context_summary()
    assert summary == ""


def test_build_context_summary_with_data(store):
    sid = store.start_session("code")
    for ft in ["NAME_ERROR", "NAME_ERROR", "SYNTAX_ERROR"]:
        store.append_round(
            sid,
            RoundRecord(
                round_no=1,
                failure_type=ft,
                error_message="err",
                action_taken="run_code",
                guardrail_decision="ALLOW",
            ),
        )
    store.finish_session(sid, None, False, 3)
    summary = store.build_context_summary()
    assert "NAME_ERROR" in summary
    assert "2" in summary


def test_multiple_rounds_recorded(store):
    sid = store.start_session("code")
    for i, ft in enumerate(["SYNTAX_ERROR", "NAME_ERROR", "TYPE_ERROR"], start=1):
        store.append_round(
            sid,
            RoundRecord(
                round_no=i,
                failure_type=ft,
                error_message="err",
                action_taken="run_code",
                guardrail_decision="ALLOW",
            ),
        )
    store.finish_session(sid, "fixed", True, 3)
    sessions = store.get_recent_sessions()
    match = next(s for s in sessions if s.session_id == sid)
    assert len(match.failure_types) == 3
    assert match.failure_types[0] == "SYNTAX_ERROR"
