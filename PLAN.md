# Coding Agent Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Streamlit Web 应用，让用户粘贴有 bug 的 Python 代码后，Agent 自动多轮运行-报错-修复，直到代码无错执行或触发停机条件，同时提供护栏和 HITL 审批机制。

**Architecture:** 六个独立模块（models / lm / executor / classifier / guardrail / memory）加一个主循环（agent_loop）加 Streamlit UI，模块间通过 dataclass 接口通信，均无全局副作用以便单独测试。MockLM 替代真实 LM 支撑所有单元测试和 Demo，无需网络。

**Tech Stack:** Python 3.12, Streamlit, openai SDK, SQLite (stdlib), keyring, pytest, Docker

## Global Constraints

- Python 版本：3.12
- 禁止使用任何现成 agent 框架（LangChain / AutoGen 等）
- LM 默认模型：`gpt-4o-mini`
- 代码执行超时默认：10 秒
- stdout/stderr 截断阈值：8 KB
- Agent 最大轮次默认：8
- 卡死检测阈值：连续 3 轮相同 `FailureType`
- LM 响应解析失败最多重试：2 次
- 记忆注入取最近：5 次会话
- 凭据不硬编码，不进 Git，`.env` 加入 `.gitignore`
- Docker 单条 `docker run -p 8501:8501 --env-file .env coding-agent-harness` 可启动
- CI：`.gitlab-ci.yml`（GitLab CI）

---

## File Map

```
harness/
  __init__.py
  models.py          # 所有 dataclass / enum定义（Action, RunResult, FailureInfo, LoopResult 等）
  lm.py              # BaseLM, OpenAILM, MockLM, LMRateLimitError
  executor.py        # CodeExecutor.run()
  classifier.py      # FailureType enum, classify(), get_repair_prompt()
  guardrail.py       # GuardrailResult enum, check()
  memory.py          # MemoryStore: SQLite 两张表，start_session / append_round / finish_session / get_recent_sessions
  agent_loop.py      # run() → LoopResult
  cli.py             # setup / key-status / key-clear子命令
ui/
  __init__.py
  app.py             # Streamlit 单页应用
demo/
  demo_mechanisms.py # 三段 MockLM 演示，无需网络
tests/
  test_models.py
  test_lm.py
  test_executor.py
  test_classifier.py
  test_guardrail.py
  test_memory.py
  test_agent_loop.py
  test_ui_hitl.py
requirements.txt
Dockerfile
.gitlab-ci.yml
.gitignore
README.md
```

---

### Task 1: 数据模型（`harness/models.py`）

**Files:**
- Create `harness/__init__.py`
- Create: `harness/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `Action(type: Literal["run_code","write_file","shell","give_up"], payload: str)`
  - `RunResult(stdout: str, stderr: str, exit_code: int, elapsed: float, timed_out: bool)`
  - `FailureInfo(type: FailureType, exception_class: str, message: str, line_no: int | None)`
  - `LoopResult(status: Literal["success","failed","stall","hitl_pause","give_up"], final_code: str | None, rounds: int, session_id: str)`
  - `RoundRecord(round_no: int, failure_type: str, error_message: str, action_taken: str, guardrail_decision: str)`
  - `SessionSummary(session_id: str, created_at: str, success: bool, rounds: int, failure_types: list[str])`
  - `FailureType` enum（8 个值，见 Global Constraints）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_models.py
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
```

- [ ] **Step 2: 运行测试，确认失败**

```
pytest tests/test_models.py -v
```

预期：`ModuleNotFoundError: No module named 'harness'`

- [ ] **Step 3: 创建 `harness/__init__.py`（空文件）并实现 `harness/models.py`**

```python
# harness/models.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class FailureType(Enum):
    SYNTAX_ERROR = "SYNTAX_ERROR"
    NAME_ERROR = "NAME_ERROR"
    TYPE_ERROR = "TYPE_ERROR"
    IMPORT_ERROR = "IMPORT_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIMEOUT = "TIMEOUT"
    ASSERTION_ERROR = "ASSERTION_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass
class Action:
    type: Literal["run_code", "write_file", "shell", "give_up"]
    payload: str


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    elapsed: float
    timed_out: bool


@dataclass
class FailureInfo:
    type: FailureType
    exception_class: str
    message: str
    line_no: int | None


@dataclass
class LoopResult:
    status: Literal["success", "failed", "stall", "hitl_pause", "give_up"]
    final_code: str | None
    rounds: int
    session_id: str


@dataclass
class RoundRecord:
    round_no: int
    failure_type: str
    error_message: str
    action_taken: str
    guardrail_decision: str


@dataclass
class SessionSummary:
    session_id: str
    created_at: str
    success: bool
    rounds: int
    failure_types: list[str]
```

- [ ] **Step 4: 运行测试，确认通过**

```
pytest tests/test_models.py -v
```

预期：5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add harness/__init__.py harness/models.py tests/test_models.py
git commit -m "feat: add data models (Action, RunResult, FailureInfo, LoopResult, enums)"
```

---

### Task 2: LM 抽象层（`harness/lm.py`）

**Files:**
- Create: `harness/lm.py`
- Create: `tests/test_lm.py`

**Interfaces:**
- Consumes:无（独立模块）
- Produces:
  - `BaseLM` 抽象基类，方法 `complete(messages: list[dict]) -> str`
  - `OpenAILM(api_key: str, model: str = "gpt-4o-mini", base_url: str | None = None)`
  - `MockLM(responses: list[str])`
  - `LMRateLimitError(message: str)`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_lm.py
import pytest
from harness.lm import MockLM, LMRateLimitError, BaseLM, OpenAILM

def test_mock_lm_returns_in_order():
    lm = MockLM(["resp1", "resp2"])
    assert lm.complete([]) == "resp1"
    assert lm.complete([]) == "resp2"

def test_mock_lm_exhausted_raises():
    lm = MockLM(["only_one"])
    lm.complete([])
    with pytest.raises(RuntimeError, match="MockLM response queue exhausted"):
        lm.complete([])

def test_base_lm_is_abstract():
    with pytest.raises(TypeError):
        BaseLM()

def test_openailm_is_subclass():
    assert issubclass(OpenAILM, BaseLM)

def test_lm_rate_limit_error_is_exception():
    err = LMRateLimitError("too many requests")
    assert isinstance(err, Exception)
    assert "too many requests" in str(err)
```

- [ ] **Step 2: 运行测试，确认失败**

```
pytest tests/test_lm.py -v
```

预期：`ImportError: cannot import name 'MockLM' from 'harness.lm'`

- [ ] **Step 3: 实现 `harness/lm.py`**

```python
# harness/lm.py
from __future__ import annotations
from abc import ABC, abstractmethod


class LMRateLimitError(Exception):
    pass


class BaseLM(ABC):
    @abstractmethod
    def complete(self, messages: list[dict]) -> str:
        ...


class MockLM(BaseLM):
    def __init__(self, responses: list[str]) -> None:
        self._queue = list(responses)

    def complete(self, messages: list[dict]) -> str:
        if not self._queue:
            raise RuntimeError("MockLM response queue exhausted")
        return self._queue.pop(0)


class OpenAILM(BaseLM):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ) -> None:
        from openai import OpenAI
        self._model = model
        kwargs: dict = {"api_key": api_key}
        if base_url is not None:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)

    def complete(self, messages: list[dict]) -> str:
        from openai import RateLimitError
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
            return resp.choices[0].message.content or ""
        except RateLimitError as e:
            raise LMRateLimitError(str(e)) from e
```

- [ ] **Step 4: 运行测试，确认通过**

```
pytest tests/test_lm.py -v
```

预期：5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add harness/lm.py tests/test_lm.py
git commit -m "feat: add LM abstraction (BaseLM, OpenAILM, MockLM, LMRateLimitError)"
```

---

### Task 3: 代码执行器（`harness/executor.py`）

**Files:**
- Create: `harness/executor.py`
- Create: `tests/test_executor.py`

**Interfaces:**
- Consumes: `Action` from `harness.models`
- Produces: `CodeExecutor.run(action: Action, timeout: int = 10) -> RunResult`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_executor.py
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
    # 生成 10KB 输出
    action = Action(type="run_code", payload="print('x' * 10240)")
    result = ex.run(action)
    assert len(result.stdout) <= 8192 + 100  # 允许换行符和截断提示

def test_elapsed_is_positive():
    ex = CodeExecutor()
    action = Action(type="run_code", payload="pass")
    result = ex.run(action)
    assert result.elapsed >= 0
```

- [ ] **Step 2: 运行测试，确认失败**

```
pytest tests/test_executor.py -v
```

预期：`ImportError: cannot import name 'CodeExecutor' from 'harness.executor'`

- [ ] **Step 3: 实现 `harness/executor.py`**

```python
# harness/executor.py
from __future__ import annotations
import os
import subprocess
import tempfile
import time

from harness.models import Action, RunResult

_MAX_OUTPUT = 8 * 1024  # 8 KB


class CodeExecutor:
    def run(self, action: Action, timeout: int = 10) -> RunResult:
        tmpdir = tempfile.mkdtemp()
        script = os.path.join(tmpdir, "script.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write(action.payload)

        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        }

        start = time.monotonic()
        timed_out = False
        try:
            proc = subprocess.run(
                ["python", script],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = -1
            stdout = ""
            stderr = f"TimeoutExpired: execution exceeded {timeout}s"

        elapsed = time.monotonic() - start

        if len(stdout) > _MAX_OUTPUT:
            stdout = stdout[:_MAX_OUTPUT] + "\n[truncated]"
        if len(stderr) > _MAX_OUTPUT:
            stderr = stderr[:_MAX_OUTPUT] + "\n[truncated]"

        return RunResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            elapsed=elapsed,
            timed_out=timed_out,
        )
```

- [ ] **Step 4: 运行测试，确认通过**

```
pytest tests/test_executor.py -v
```

预期：5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add harness/executor.py tests/test_executor.py
git commit -m "feat: add CodeExecutor with timeout, truncation, minimal env"
```

---

### Task 4: 失败分类器（`harness/classifier.py`）

**Files:**
- Create: `harness/classifier.py`
- Create: `tests/test_classifier.py`

**Interfaces:**
- Consumes: `RunResult`, `FailureType`, `FailureInfo` from `harness.models`
- Produces:
  - `classify(result: RunResult) -> FailureInfo`
  - `get_repair_prompt(info: FailureInfo) -> str`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_classifier.py
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

def test_get_repair_prompt_unique_per_type():
    prompts = {get_repair_prompt(classify(_make_result(f"{t.value}: x"))) for t in FailureType if t != FailureType.TIMEOUT and t != FailureType.UNKNOWN}
    timeout_prompt = get_repair_prompt(classify(RunResult(",",−1,11.0,True)))
    # 至少 7 种不同提示
    all_prompts = prompts | {timeout_prompt}
    assert len(all_prompts) >= 7

def test_import_error_promptmentions_module():
    fi = classify(_make_result("ImportError: No module named 'requests'"))
    prompt = get_repair_prompt(fi)
    assert "模块" in prompt or "module" in prompt.lower() or "import" in prompt.lower()

def test_assertion_error_prompt_no_deleteassert():
    fi = classify(_make_result("AssertionError"))
    prompt = get_repair_prompt(fi)
    assert "断言" in prompt or "assert" in prompt.lower()
    assert "删除" not in prompt and "remove" not in prompt.lower()
```

- [ ] **Step 2: 运行测试，确认失败**

```
pytest tests/test_classifier.py -v
```

预期：全部失败，`ImportError`

- [ ] **Step 3: 实现 `harness/classifier.py`**

```python
# harness/classifier.py
from __future__ import annotations
import re

from harness.models import FailureInfo, FailureType, RunResult

_PATTERNS: list[tuple[re.Pattern, FailureType]] = [
    (re.compile(r"SyntaxError"), FailureType.SYNTAX_ERROR),
    (re.compile(r"NameError|AttributeError"), FailureType.NAME_ERROR),
    (re.compile(r"TypeError"), FailureType.TYPE_ERROR),
    (re.compile(r"ImportError|ModuleNotFoundError"), FailureType.IMPORT_ERROR),
    (re.compile(r"AssertionError"), FailureType.ASSERTION_ERROR),
]

_REPAIR_PROMPTS: dict[FailureType, str] = {
    FailureType.SYNTAX_ERROR: (
        "代码存在语法错误（SyntaxError）。请仔细检查括号匹配、冒号、缩进，"
        "修正语法后重新输出完整代码。"
    ),
    FailureType.NAME_ERROR: (
        "代码存在未定义的变量或属性（NameError/AttributeError）。"
        "请补充缺失的变量定义或修正属性引用，输出完整修正后的代码。"
    ),
    FailureType.TYPE_ERROR: (
        "代码存在类型错误（TypeError）。请检查函数参数类型、操作数类型，"
        "进行必要的类型转换后输出完整代码。"
    ),
    FailureType.IMPORT_ERROR: (
        "代码存在导入错误（ImportError/ModuleNotFoundError）。"
        "请识别缺失的模块名，优先使用 Python 标准库替代，"
        "或改写为不依赖该外部模块的实现。不要修改业务逻辑，输出完整代码。"
    ),
    FailureType.ASSERTION_ERROR: (
        "代码触发了断言失败（AssertionError）。断言是正确性契约，"
        "请修正代码逻辑使其满足断言条件，不要删除断言，输出完整修正后的代码。"
    ),
    FailureType.RUNTIME_ERROR: (
        "代码在运行时抛出异常。请根据错误信息定位问题根源，"
        "修正后输出完整代码。"
    ),
    FailureType.TIMEOUT: (
        "代码执行超时（超过 10 秒）。请检查是否存在死循环或低效算法，"
        "优化后输出完整代码。"
    ),
    FailureType.UNKNOWN: (
        "代码执行失败，无法确定具体错误类型。请审查完整输出，"
        "尝试修正潜在问题后输出完整代码。"
    ),
}


def classify(result: RunResult) -> FailureInfo:
    if result.timed_out:
        return FailureInfo(
            type=FailureType.TIMEOUT,
            exception_class="TimeoutExpired",
            message="execution timed out",
            line_no=None,
        )

    stderr = result.stderr
    last_line = stderr.strip().splitlines()[-1] if stderr.strip() else ""

    for pattern, failure_type in _PATTERNS:
        m = pattern.search(stderr)
        if m:
            exc_class = m.group(0).split(":")[0].strip()
            msg_match = re.search(r"(\w+Error[^:]*): (.+)", last_line)
            message = msg_match.group(2) if msg_match else last_line
            line_match = re.search(r"line (\d+)", stderr)
            line_no = int(line_match.group(1)) if line_match else None
            return FailureInfo(type=failure_type, exception_class=exc_class, message=message, line_no=line_no)

    if stderr.strip():
        exc_match = re.search(r"(\w+Error)[:\s]", stderr)
        exc_class = exc_match.group(1) if exc_match else "RuntimeError"
        return FailureInfo(type=FailureType.RUNTIME_ERROR, exception_class=exc_class, message=last_line, line_no=None)

    return FailureInfo(type=FailureType.UNKNOWN, exception_class="", message="", line_no=None)


def get_repair_prompt(info: FailureInfo) -> str:
    base = _REPAIR_PROMPTS[info.type]
    if info.message:
        base += f"\n错误信息：{info.message}"
    if info.line_no is not None:
        base += f"（第 {info.line_no} 行）"
    return base
```

- [ ] **Step 4: 运行测试，确认通过**

```
pytest tests/test_classifier.py -v
```

预期：全部 PASSED（至少 11 tests）

- [ ] **Step 5: Commit**

```bash
git add harness/classifier.py tests/test_classifier.py
git commit -m "feat: add failure classifier and repair prompt router (8 FailureTypes)"
```

---

### Task 5: 治理护栏（`harness/guardrail.py`）

**Files:**
- Create: `harness/guardrail.py`
- Create: `tests/test_guardrail.py`

**Interfaces:**
- Consumes: `Action` from `harness.models`
- Produces:
  - `GuardrailResult` enum：`ALLOW`, `BLOCK`, `HITL_REQUIRED`
  - `check(action: Action) -> GuardrailResult`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_guardrail.py
import pytest
from harness.guardrail import check, GuardrailResult
from harness.models import Action

def _act(payload: str, type_: str = "shell") -> Action:
    return Action(type=type_, payload=payload)

# BLOCK 测试
def test_block_rm_rf_root():
    assert check(_act("rm -rf /")) == GuardrailResult.BLOCK

def test_block_rm_rf_home():
    assert check(_act("rm -rf ~")) == GuardrailResult.BLOCK

def test_block_fork_bomb():
    assert check(_act(":(){ :|:& };:")) == GuardrailResult.BLOCK

def test_block_dd():
    assert check(_act("dd if=/dev/zero of=/dev/sda")) == GuardrailResult.BLOCK

def test_block_mkfs():
    assert check(_act("mkfs.ext4 /dev/sdb")) == GuardrailResult.BLOCK

def test_block_write_etc():
    assert check(_act("echo x > /etc/passwd"), "run_code") == GuardrailResult.BLOCK

def test_block_write_sys():
    assert check(_act("with open('/sys/foo','w') as f: f.write('x')"), "run_code") == GuardrailResult.BLOCK

def test_block_write_proc():
    assert check(_act("open('/proc/1/mem','w')"), "run_code") == GuardrailResult.BLOCK

# HITL 测试
def test_hitl_os_remove():
    assert check(_act("os.remove('/tmp/f')", "run_code")) == GuardrailResult.HITL_REQUIRED

def test_hitl_shutil_rmtree():
    assert check(_act("shutil.rmtree('/home/user/data')", "run_code")) == GuardrailResult.HITL_REQUIRED

def test_hitl_subprocess_run():
    assert check(_act("subprocess.run(['ls'])", "run_code")) == GuardrailResult.HITL_REQUIRED

def test_hitl_os_system():
    assert check(_act("os.system('ls')", "run_code")) == GuardrailResult.HITL_REQUIRED

def test_hitl_eval():
    assert check(_act("eval('1+1')", "run_code")) == GuardrailResult.HITL_REQUIRED

def test_hitl_exec():
    assert check(_act("exec('pass')", "run_code")) == GuardrailResult.HITL_REQUIRED

def test_hitl_socket_connect():
    assert check(_act("s.connect('8.8.8.8', 53))", "run_code")) == GuardrailResult.HITL_REQUIRED

def test_hitl_urllib_urlopen():
    assert check(_act("urllib.request.urlopen('http://x.com')", "run_code")) == GuardrailResult.HITL_REQUIRED

def test_hitl_requests_get():
    assert check(_act("requests.get('http://x.com')", "run_code")) == GuardrailResult.HITL_REQUIRED

def test_hitl_requests_post():
    assert check(_act("requests.post('http://x.com', data={})", "run_code")) == GuardrailResult.HITL_