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
    lines = stderr.strip().splitlines()
    last_line = lines[-1] if lines else ""

    for pattern, failure_type in _PATTERNS:
        m = pattern.search(stderr)
        if m:
            exc_class = m.group(0).split(":")[0].strip()
            msg_match = re.search(r"(\w+Error[^:\n]*): (.+)", last_line)
            message = msg_match.group(2) if msg_match else last_line
            line_match = re.search(r"line (\d+)", stderr)
            line_no = int(line_match.group(1)) if line_match else None
            return FailureInfo(
                type=failure_type,
                exception_class=exc_class,
                message=message,
                line_no=line_no,
            )

    if stderr.strip():
        exc_match = re.search(r"(\w+Error)[:\s]", stderr)
        exc_class = exc_match.group(1) if exc_match else "RuntimeError"
        return FailureInfo(
            type=FailureType.RUNTIME_ERROR,
            exception_class=exc_class,
            message=last_line,
            line_no=None,
        )

    return FailureInfo(
        type=FailureType.UNKNOWN,
        exception_class="",
        message="",
        line_no=None,
    )


def get_repair_prompt(info: FailureInfo) -> str:
    base = _REPAIR_PROMPTS[info.type]
    if info.message:
        base += f"\n错误信息：{info.message}"
    if info.line_no is not None:
        base += f"（第 {info.line_no} 行）"
    return base
