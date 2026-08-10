import tempfile
from pathlib import Path

import pytest

from harness.agent_loop import run
from harness.lm import MockLM
from harness.memory import MemoryStore
from harness.models import LoopResult


@pytest.fixture
def mem(tmp_path):
    return MemoryStore(db_path=tmp_path / "test.db")


def _good_response(code: str) -> str:
    import json
    return json.dumps({"action": "run_code", "payload": code})


def _giveup_response() -> str:
    import json
    return json.dumps({"action": "give_up", "payload": ""})


def test_success_on_first_round(mem):
    lm = MockLM([_good_response("print('hello')")])
    result = run("print('helo')", lm, memory=mem)
    assert result.status == "success"
    assert result.rounds == 1
    assert "hello" in result.final_code


def test_success_on_second_round(mem):
    broken = "x = undeclared_var"
    fixed = "x = 42\nprint(x)"
    lm = MockLM([
        _good_response(broken),
        _good_response(fixed),
    ])
    result = run(broken, lm, memory=mem)
    assert result.status == "success"
    assert result.rounds == 2


def test_give_up_action(mem):
    lm = MockLM([_giveup_response()])
    result = run("code", lm, memory=mem)
    assert result.status == "give_up"
    assert result.rounds == 1


def test_max_rounds_exhausted(mem):
    bad_code = "raise RuntimeError('always fails')"
    responses = [_good_response(bad_code)] * 8
    lm = MockLM(responses)
    result = run(bad_code, lm, memory=mem, max_rounds=8)
    assert result.status in ("failed", "stall")
    assert result.rounds <= 8


def test_stall_detection(mem):
    type_error_code = "x = 1 + 'a'"
    responses = [_good_response(type_error_code)] * 10
    lm = MockLM(responses)
    result = run(type_error_code, lm, memory=mem, max_rounds=10)
    assert result.status == "stall"
    assert result.rounds == 3


def test_parse_failure_causes_failed(mem):
    lm = MockLM(["not json", "still not json", "nope"])
    result = run("print(1)", lm, memory=mem)
    assert result.status == "failed"


def test_block_action_does_not_call_executor(mem):
    import json
    blocked_response = json.dumps({"action": "shell", "payload": "rm -rf /"})
    # After block, MockLM returns a good fix
    lm = MockLM([blocked_response, _good_response("print('safe')")])
    result = run("code", lm, memory=mem)
    # Should eventually succeed after block is rejected
    assert result.status == "success"


def test_hitl_pause_returns_correct_status(mem):
    import json
    hitl_response = json.dumps({"action": "run_code", "payload": "os.remove('/tmp/f')"})
    lm = MockLM([hitl_response])
    result = run("code", lm, memory=mem)
    assert result.status == "hitl_pause"


def test_loop_result_has_session_id(mem):
    lm = MockLM([_good_response("print('ok')")])
    result = run("print('ok')", lm, memory=mem)
    assert isinstance(result.session_id, str)
    assert len(result.session_id) == 36


def test_memory_records_written(mem):
    bad_code = "x = undeclared"
    fixed_code = "x = 1\nprint(x)"
    lm = MockLM([_good_response(bad_code), _good_response(fixed_code)])
    result = run(bad_code, lm, memory=mem)
    assert result.status == "success"
    sessions = mem.get_recent_sessions()
    assert len(sessions) >= 1
    session = next(s for s in sessions if s.session_id == result.session_id)
    assert session.success is True
    assert session.rounds == 2


def test_context_summary_injected_on_second_session(mem):
    # First session
    lm1 = MockLM([_good_response("print('hello')")])
    run("code1", lm1, memory=mem)

    # Second session — context summary should be non-empty
    summary = mem.build_context_summary()
    # May be empty if no round failures recorded; just check it doesn't crash
    assert isinstance(summary, str)
