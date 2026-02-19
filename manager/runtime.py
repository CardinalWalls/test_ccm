from __future__ import annotations

import datetime as dt
import fcntl
import json
import subprocess
from pathlib import Path
from typing import Any, Callable, TypeVar


T = TypeVar("T")


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def run_cmd(
    command: list[str],
    cwd: Path,
    *,
    timeout: int = 300,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
    )
    if check and cp.returncode != 0:
        raise RuntimeError(
            "Command failed: "
            + " ".join(command)
            + f"\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
        )
    return cp


def locked_json_update(path: Path, lock_path: Path, fn: Callable[[Any], T]) -> T:
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                data = []
            result = fn(data)
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            return result
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

