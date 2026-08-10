from __future__ import annotations

import re
from enum import Enum

from harness.models import Action


class GuardrailResult(Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    HITL_REQUIRED = "HITL_REQUIRED"


_BLOCK_PATTERNS: list[re.Pattern] = [
    re.compile(r"rm\s+-rf\s+/"),
    re.compile(r"rm\s+-rf\s+~"),
    re.compile(r":\(\)\{\s*:\|:&\s*\};:"),
    re.compile(r"\bdd\b.*\bof="),
    re.compile(r"\bmkfs\b"),
    re.compile(r"['\"/]/(etc)/"),
    re.compile(r"['\"/]/(sys)/"),
    re.compile(r"['\"/]/(proc)/"),
    re.compile(r">[\s]*/etc/"),
]

_HITL_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bos\.remove\s*\("),
    re.compile(r"\bshutil\.rmtree\s*\("),
    re.compile(r"\bsubprocess\.run\s*\("),
    re.compile(r"\bsubprocess\.call\s*\("),
    re.compile(r"\bsubprocess\.Popen\s*\("),
    re.compile(r"\bos\.system\s*\("),
    re.compile(r"\beval\s*\("),
    re.compile(r"\bexec\s*\("),
    re.compile(r"\.connect\s*\("),
    re.compile(r"\burllib\.request\.urlopen\s*\("),
    re.compile(r"\burllib\.urlopen\s*\("),
    re.compile(r"\brequests\.get\s*\("),
    re.compile(r"\brequests\.post\s*\("),
    re.compile(r"\brequests\.put\s*\("),
    re.compile(r"\brequests\.delete\s*\("),
    re.compile(r"\brequests\.request\s*\("),
]


def check(action: Action) -> GuardrailResult:
    payload = action.payload

    for pattern in _BLOCK_PATTERNS:
        if pattern.search(payload):
            return GuardrailResult.BLOCK

    for pattern in _HITL_PATTERNS:
        if pattern.search(payload):
            return GuardrailResult.HITL_REQUIRED

    return GuardrailResult.ALLOW
