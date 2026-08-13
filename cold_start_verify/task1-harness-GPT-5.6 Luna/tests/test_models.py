from harness.models import Action, RunResult, FailureInfo, FailureType, LoopResult, RoundRecord, SessionSummary


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
