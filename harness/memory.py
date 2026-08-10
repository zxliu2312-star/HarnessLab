from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from harness.models import RoundRecord, SessionSummary

_DEFAULT_DB = Path(__file__).parent.parent / "harness_memory.db"

_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    original_code TEXT NOT NULL,
    final_code  TEXT,
    success     INTEGER NOT NULL DEFAULT 0,
    rounds      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rounds (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL REFERENCES sessions(id),
    round_no          INTEGER NOT NULL,
    failure_type      TEXT NOT NULL,
    error_message     TEXT NOT NULL,
    action_taken      TEXT NOT NULL,
    guardrail_decision TEXT NOT NULL
);
"""


class MemoryStore:
    def __init__(self, db_path: str | Path = _DEFAULT_DB) -> None:
        self._db = Path(db_path)
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_DDL)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def start_session(self, original_code: str) -> str:
        session_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, created_at, original_code) VALUES (?, ?, ?)",
                (session_id, created_at, original_code),
            )
        return session_id

    def append_round(self, session_id: str, round_: RoundRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO rounds
                   (session_id, round_no, failure_type, error_message, action_taken, guardrail_decision)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    round_.round_no,
                    round_.failure_type,
                    round_.error_message,
                    round_.action_taken,
                    round_.guardrail_decision,
                ),
            )

    def finish_session(
        self, session_id: str, final_code: str | None, success: bool, rounds: int
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET final_code=?, success=?, rounds=? WHERE id=?",
                (final_code, int(success), rounds, session_id),
            )

    def get_recent_sessions(self, limit: int = 5) -> list[SessionSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, created_at, success, rounds FROM sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

            summaries = []
            for row in rows:
                failure_types = [
                    r["failure_type"]
                    for r in conn.execute(
                        "SELECT failure_type FROM rounds WHERE session_id=? ORDER BY round_no",
                        (row["id"],),
                    ).fetchall()
                ]
                summaries.append(
                    SessionSummary(
                        session_id=row["id"],
                        created_at=row["created_at"],
                        success=bool(row["success"]),
                        rounds=row["rounds"],
                        failure_types=failure_types,
                    )
                )
        return summaries

    def build_context_summary(self, limit: int = 5) -> str:
        sessions = self.get_recent_sessions(limit)
        if not sessions:
            return ""
        counts: dict[str, int] = {}
        for s in sessions:
            for ft in s.failure_types:
                counts[ft] = counts.get(ft, 0) + 1
        lines = [f"过去 {len(sessions)} 次会话错误类型统计："]
        for ft, n in sorted(counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {ft}: {n} 次")
        return "\n".join(lines)
