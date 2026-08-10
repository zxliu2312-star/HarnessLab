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

        # Start from the full current environment so Windows system vars
        # (SYSTEMROOT, USERPROFILE, TEMP, etc.) are present — Python's runtime
        # needs them on Windows even for trivial scripts.
        env = os.environ.copy()
        env["PYTHONPATH"] = os.environ.get("PYTHONPATH", "")

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
