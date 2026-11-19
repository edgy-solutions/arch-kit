"""The decisions-only example's loader: the decision functions and nothing else.

A portal in `decisions` mode reads no capability record, so there is no `load_record`, `model_capabilities`,
`resolve_entries`, `quote_of`, `measured_line` or `resolve_quotes`, and no KEY_NAMES. The record files are named
NNNN-<slug>.md; the mapping from a name to a record id is the kit's (`decisions.records.file_prefix`).
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
    m = re.search(rf"\[{re.escape(adr)}:[^\n]*\*\*(accepted|proposed)", index_text, re.I)
    return m.group(1).lower() if m else None
