"""A decisions-only loader for the composed fixtures: the decision functions and nothing else.

The status of a record is the body of its `## Status` section. Every name in the fixtures is invented.
"""
from __future__ import annotations

import re
from pathlib import Path

import declared


def read_text(path: Path) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return None


def adr_file(decisions_dir: Path, adr: str) -> Path | None:
    found = sorted(f for f in Path(decisions_dir).glob(declared.record_file_patterns("loader")[1])
                   if declared.record_id_of_file("loader", f.name) == adr)
    return found[0] if len(found) == 1 else None


def adr_status(text: str) -> str | None:
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Status\s*$", line):
            body = []
            for nxt in lines[i + 1:]:
                if nxt.startswith("#"):
                    break
                body.append(nxt)
            return "\n".join(body).strip() or None
    return None


def adr_lead(decisions_dir: Path, adr: str) -> str | None:
    path = adr_file(decisions_dir, adr)
    text = read_text(path) if path else None
    status = adr_status(text) if text is not None else None
    return status.lstrip("* ").lower() if status else None


def index_status(index_text: str, adr: str) -> str | None:
    return None
