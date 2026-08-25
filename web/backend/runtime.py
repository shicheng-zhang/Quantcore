"""Safe file-backed runtime state helpers."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


def read_json(path: str | Path, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default


def write_json_atomic(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as file:
        json.dump(value, file, indent=2)
        file.flush()
        os.fsync(file.fileno())
        temporary = file.name
    os.replace(temporary, target)
