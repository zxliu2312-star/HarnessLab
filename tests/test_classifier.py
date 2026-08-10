from harness.classifier import classify, get_repair_prompt
from harness.models import RunResult, FailureType


def _make_result(stderr: str, exit_code: int = 1, timed_out: bool = False) -> RunResult:
    return RunResult(stdout="", stderr=stderr, exit_code=exit_code, elapsed=0.1, timed_out=timed_out)


def test_classify_syntax_error():
    r = _make_result('  File "s.py", line 1\nSyntaxError: invalid syntax')
    fi = classify(r)
    assert fi.type == FailureType.SYNTAX_ERROR
    assert fi.exception_class == "SyntaxError"


def test_classify_name_error():
    fi = classify(_make_result("NameError: name 'x' is not defined"))
    assert fi.type == FailureType.NAME_ERROR


def test_classify_attribute_error_maps_to_name_error():
    fi = classify(_make_result("AttributeError: 'NoneType' object has no attribute 'foo'"))
    assert fi.type == FailureType.NAME_ERROR


def test_classify_type_error():
    fi = classify(_make_result("TypeError: unsupported operand type"))
    assert fi.type == FailureType.TYPE_ERROR


def test_classify_import_error():
    fi = classify(_make_result("ImportError: No module named 'foo'"))
    assert fi.type == FailureType.IMPORT_ERROR


def test_classify_module_not_found():
    fi = classify(_make_result("ModuleNotFoundError: No module named 'bar'"))
    assert fi.type == FailureType.IMPORT_ERROR


def test_classify_assertion_error():
    fi = classify(_make_result("AssertionError"))
    assert fi.type == FailureType.ASSERTION_ERROR


def test_classify_timeout():
    r = RunResult(stdout="", stderr="", exit_code=-1, elapsed=10.5, timed_out=True)
    fi = classify(r)
    assert fi.type == FailureType.TIMEOUT


def test_classify_runtime_error():
    fi = classify(_make_result("ZeroDivisionError: division by zero"))
    assert fi.type == FailureType.RUNTIME_ERROR


def test_classify_unknown():
    fi = classify(_make_result(""))
    assert fi.type == FailureType.UNKNOWN


def test_get_repair_prompts_all_unique():
    stubs = {
        FailureType.SYNTAX_ERROR: "SyntaxError: invalid syntax",
        FailureType.NAME_ERROR: "NameError: name 'x' is not defined",
        FailureType.TYPE_ERROR: "TypeError: unsupported operand type",
        FailureType.IMPORT_ERROR: "ImportError: No module named 'foo'",
        FailureType.ASSERTION_ERROR: "AssertionError",
        FailureType.RUNTIME_ERROR: "ZeroDivisionError: division by zero",
        FailureType.UNKNOWN: "",
    }
    prompts = []
    for ft, stderr in stubs.items():
        fi = classify(_make_result(stderr))
        prompts.append(get_repair_prompt(fi))

    timeout_fi = classify(RunResult(stdout="", stderr="", exit_code=-1, elapsed=11.0, timed_out=True))
    prompts.append(get_repair_prompt(timeout_fi))

    assert len(set(prompts)) == 8


def test_import_error_prompt_mentions_module():
    fi = classify(_make_result("ImportError: No module named 'requests'"))
    prompt = get_repair_prompt(fi)
    assert "模块" in prompt or "module" in prompt.lower() or "import" in prompt.lower()


def test_assertion_error_prompt_no_delete_assert():
    fi = classify(_make_result("AssertionError"))
    prompt = get_repair_prompt(fi)
    assert "断言" in prompt or "assert" in prompt.lower()
    # Prompt must say do NOT delete ("不要删除"), not instruct deletion
    assert "不要删除" in prompt or "do not remove" in prompt.lower()


def test_classify_captures_line_no():
    stderr = '  File "script.py", line 5\n    x = y\nNameError: name y is not defined'
    fi = classify(_make_result(stderr))
    assert fi.line_no == 5


def test_classify_success_returns_unknown():
    r = RunResult(stdout="ok", stderr="", exit_code=0, elapsed=0.1, timed_out=False)
    fi = classify(r)
    assert fi.type == FailureType.UNKNOWN
