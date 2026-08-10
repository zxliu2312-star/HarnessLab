import pytest
from harness.executor import CodeExecutor
from harness.models import Action, RunResult


def test_run_success():
    ex = CodeExecutor()
    action = Action(type="run_code", payload="print('hello')")
    result = ex.run(action)
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert result.timed_out is False


def test_run_syntax_error():
    ex = CodeExecutor()
    action = Action(type="run_code", payload="def f(:\n  pass")
    result = ex.run(action)
    assert result.exit_code != 0
    assert "SyntaxError" in result.stderr


def test_run_timeout():
    ex = CodeExecutor()
    action = Action(type="run_code", payload="import time; time.sleep(60)")
    result = ex.run(action, timeout=1)
    assert result.timed_out is True
    assert result.exit_code != 0


def test_stdout_truncated_at_8kb():
    ex = CodeExecutor()
    # Generate ~10KB output
    action = Action(type="run_code", payload="print('x' * 10240)")
    result = ex.run(action)
    assert len(result.stdout) <= 8192 + 50


def test_elapsed_is_positive():
    ex = CodeExecutor()
    action = Action(type="run_code", payload="pass")
    result = ex.run(action)
    assert result.elapsed >= 0


def test_run_returns_run_result():
    ex = CodeExecutor()
    action = Action(type="run_code", payload="x = 1")
    result = ex.run(action)
    assert isinstance(result, RunResult)


def test_stderr_captured():
    ex = CodeExecutor()
    action = Action(type="run_code", payload="import sys; sys.stderr.write('err_msg')")
    result = ex.run(action)
    assert "err_msg" in result.stderr


def test_exit_code_nonzero_on_exception():
    ex = CodeExecutor()
    action = Action(type="run_code", payload="raise ValueError('boom')")
    result = ex.run(action)
    assert result.exit_code != 0
    assert "ValueError" in result.stderr
