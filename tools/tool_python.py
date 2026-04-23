from __future__ import annotations

import os
import pathlib
import sys


def resolve_idf_python() -> str | None:
    idf_python_env_path = os.environ.get("IDF_PYTHON_ENV_PATH")
    if not idf_python_env_path:
        return None

    root = pathlib.Path(idf_python_env_path)
    candidates = (
        root / "bin" / "python",
        root / "bin" / "python3",
        root / "Scripts" / "python.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def resolve_tool_python() -> str:
    return resolve_idf_python() or sys.executable
