from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional


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
    line_no: Optional[int]


@dataclass
class LoopResult:
    status: Literal["success", "failed", "stall", "hitl_pause", "give_up"]
    final_code: Optional[str]
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
    failure_types: list = field(default_factory=list)
