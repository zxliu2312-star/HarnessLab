from harness.models import (
    Action,
    RunResult,
    FailureInfo,
    FailureType,
    LoopResult,
    RoundRecord,
    SessionSummary,
)


def test_action_fields():
    a = Action(type="run_code", payload="print(1)")
    assert a.type == "run_code"
    assert a.payload == "print(1)"


def test_run_result_fields():
    r = RunResult(stdout="hi", stderr="", exit_code=0, elapsed=0.1, timed_out=False)
    assert r.exit_code == 0
    assert not r.timed_out


def test_failure_type_enum():
    assert FailureType.SYNTAX_ERROR.value == "SYNTAX_ERROR"
    assert len(list(FailureType)) == 8


def test_loop_result_fields():
    lr = LoopResult(status="success", final_code="print(1)", rounds=2, session_id="abc")
    assert lr.status == "success"
    assert lr.rounds == 2


def test_failure_info_line_no_optional():
    fi = FailureInfo(type=FailureType.UNKNOWN, exception_class="", message="", line_no=None)
    assert fi.line_no is None


def test_round_record_fields():
    rr = RoundRecord(
        round_no=1,
        failure_type="SYNTAX_ERROR",
        error_message="invalid syntax",
        action_taken="run_code",
        guardrail_decision="ALLOW",
    )
    assert rr.round_no == 1
    assert rr.failure_type == "SYNTAX_ERROR"


def test_session_summary_fields():
    ss = SessionSummary(
        session_id="uuid-1",
        created_at="2026-08-09T00:00:00",
        success=True,
        rounds=3,
        failure_types=["NAME_ERROR", "SYNTAX_ERROR"],
    )
    assert ss.success is True
    assert len(ss.failure_types) == 2


def test_all_failure_types_present():
    expected = {
        "SYNTAX_ERROR", "NAME_ERROR", "TYPE_ERROR", "IMPORT_ERROR",
        "RUNTIME_ERROR", "TIMEOUT", "ASSERTION_ERROR", "UNKNOWN",
    }
    actual = {ft.value for ft in FailureType}
    assert actual == expected
