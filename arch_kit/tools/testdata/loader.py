"""The kit fixture's loader: the smallest that lets the kit's own tests pass.

It reads the fixture's own made-up formats, with the neutral keys written as they are (no mapping):
a record YAML, decision records named ADR-NNNN-*.md whose status is a `## Status` section or a
`Status:` line, and pipe tables for registers and the roadmap. It imports nothing from a consumer.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from data_exchange import InputError

KEY_NAMES = {"groups": "groups", "environments": "environments", "environment": "environment",
             "degraded_mode": "degraded_mode"}


def load_record(path) -> dict:
    try:
        record = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise InputError(f"cannot read {path}: {e}")
    if not isinstance(record, dict):
        raise InputError(f"{path}: expected a map")
    return record


def model_capabilities(sysml_text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in re.finditer(r"occurrence def (\w+) :> (\w+);", sysml_text)}


def read_text(path: Path) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return None


def adr_file(decisions_dir: Path, adr: str) -> Path | None:
    found = sorted(Path(decisions_dir).glob(f"{adr}-*.md"))
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
    for line in lines:
        m = re.match(r"^\**Status\**\s*[:\-]?\s*\**\s*(.+)$", line)
        if m:
            return m.group(1).strip()
    return None


def adr_lead(decisions_dir: Path, adr: str) -> str | None:
    path = adr_file(decisions_dir, adr)
    text = read_text(path) if path else None
    status = adr_status(text) if text is not None else None
    return status.lstrip("* ").lower() if status else None


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def register_subjects(text: str) -> dict[str, tuple[str, str]]:
    """Rows of any `| ID | Subject | Status |` table: id to (subject, status)."""
    out: dict[str, tuple[str, str]] = {}
    for line in text.split("\n"):
        cells = _cells(line) if line.lstrip().startswith("|") else []
        if len(cells) >= 3 and re.match(r"^[A-Z]+-\d+$", cells[0]):
            out.setdefault(cells[0], (cells[1], cells[-1]))
    return out


def register_rows(text: str) -> dict[str, str]:
    return {k: v[1] for k, v in register_subjects(text).items()}


def roadmap_rows(text: str) -> list[list[str]]:
    return [_cells(ln) for ln in text.split("\n") if ln.lstrip().startswith("|")]


def index_status(index_text: str, adr: str) -> str | None:
    m = re.search(rf"\[{re.escape(adr)}:[^\n]*\*\*(accepted|proposed)", index_text, re.I)
    return m.group(1).lower() if m else None


def resolve_entries(record: dict, readiness_lines: list[str]) -> tuple[dict, list[str]]:
    """Entry name to (anchor line, date, section): the date is any YYYY-MM-DD on the anchor line."""
    found, fails = {}, []
    for key, entry in record["entries"].items():
        hits = [i for i, ln in enumerate(readiness_lines) if (entry or {}).get("anchor", "\0") in ln]
        date = re.search(r"\d{4}-\d{2}-\d{2}", readiness_lines[hits[0]]) if len(hits) == 1 else None
        if not date:
            fails.append(f"entry {key}: anchor is not on exactly one dated line")
            continue
        found[key] = (hits[0], date.group(0), "readiness")
    return found, fails


def quote_of(lines: list[str], at: int) -> str:
    return lines[at].strip()


def measured_line(readiness_lines: list[str], at: int, text: str) -> list[int]:
    return [i for i in range(at, len(readiness_lines)) if text in readiness_lines[i]]


def resolve_quotes(record: dict, readiness: list[str], entries: dict | None = None) -> tuple[dict, list[str]]:
    fails: list[str] = []
    if entries is None:
        entries, fails = resolve_entries(record, readiness)
    quotes = {}
    for name, cap in record["capabilities"].items():
        for k, m in enumerate((cap or {}).get("measured") or []):
            if m.get("entry") in entries:
                hits = measured_line(readiness, entries[m["entry"]][0], m.get("line", ""))
                if len(hits) == 1:
                    quotes[(name, k)] = quote_of(readiness, hits[0])
                else:
                    fails.append(f"{name}: line is on {len(hits)} readiness lines, expected one")
    return quotes, fails
