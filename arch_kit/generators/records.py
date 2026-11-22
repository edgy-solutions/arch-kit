"""Read a markdown record into a `Record`: title, id, sections, claims, gaps, not-established lists."""
from __future__ import annotations

import posixpath
import re

import yaml

from .model import Record, Table

ID_RE = re.compile(r"\(([A-Z]{2,}(?:-[A-Z0-9]+)+)\)")
BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
KINDS = ("components", "flows", "alignment", "decisions")


def classify(rel: str) -> str:
    parts = rel.split("/")
    if len(parts) == 1:
        low = parts[0].lower()
        if low == "readme.md":
            return "readme"
        if low == "roadmap.md":
            return "roadmap"
        return "other"
    return parts[0] if parts[0] in KINDS else "other"


def split_cells(line: str) -> list:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def _is_sep(line: str) -> bool:
    s = line.strip()
    if "-" not in s or "|" not in s:
        return False
    return not s.replace("|", "").replace(":", "").replace("-", "").replace(" ", "")


def _fences(lines: list) -> list:
    flags, inside = [], False
    for ln in lines:
        t = ln.lstrip()
        if t.startswith("```") or t.startswith("~~~"):
            inside = not inside
            flags.append(True)
        else:
            flags.append(inside)
    return flags


def split_front(text: str) -> tuple:
    """(front dict, error, body). A text whose first line is `---` has front matter up to the next
    `---` line. An unterminated opener is not front matter. Never raises."""
    lines = text.split("\n")
    if lines[0].rstrip() != "---":
        return {}, "", text
    for k in range(1, len(lines)):
        if lines[k].rstrip() == "---":
            body = "\n".join(lines[k + 1:])
            try:
                data = yaml.safe_load("\n".join(lines[1:k]))
            except Exception:  # noqa: BLE001 - any YAML failure is a finding, never a raise
                return {}, "does not parse", body
            if not isinstance(data, dict):
                return {}, "is not a mapping", body
            return data, "", body
    return {}, "", text


def parse(member: str, path: str, rel: str, text: str) -> Record:
    kind = classify(rel)
    front, front_error, text = split_front(text)
    lines = text.split("\n")
    fence = _fences(lines)
    title = ""
    for k, ln in enumerate(lines):
        if not fence[k] and ln.startswith("# "):
            title = ln[2:].strip()
            break
    rid = None
    stem = posixpath.basename(rel)[:-3]
    if kind == "decisions":
        m = re.search(r"ADR-(\d+)", stem, re.I) or re.match(r"(\d+)", stem)
        if m:
            rid = f"ADR-{m.group(1)}"
    else:
        found = ID_RE.findall(title)
        if found:
            rid = found[-1]
    rec = Record(member, path, rel, kind, title, rid, text=text, front=front, front_error=front_error)

    sections = [("", [])]
    for k, ln in enumerate(lines):
        if not fence[k] and ln.startswith("## "):
            sections.append((ln[3:].strip(), []))
        else:
            sections[-1][1].append(ln)
    rec.sections = sections

    heading = ""
    section = ""
    gap_lines = set()
    cur_gap = None
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        if fence[i]:
            i += 1
            continue
        if re.match(r"^#{1,6}\s", ln):
            heading = ln.lstrip("#").strip()
            if ln.startswith("## "):
                section = ln[3:].strip()
            cur_gap = None
            i += 1
            continue
        low_sec = section.casefold()
        if ln.strip().startswith("|") and i + 1 < n and _is_sep(lines[i + 1]) and not fence[i + 1]:
            header = split_cells(ln)
            rows = []
            j = i + 2
            while j < n and lines[j].strip().startswith("|") and not fence[j]:
                rows.append(split_cells(lines[j]))
                j += 1
            rec.tables.append(Table(heading, section, header, rows))
            low = [h.casefold() for h in header]
            vocab = "status vocabulary" in (heading.casefold(), section.casefold())
            if "status" in low and not vocab:
                idx = low.index("status")
                for k, row in enumerate(rows, 1):
                    row = row + [""] * (len(header) - len(row))
                    rec.claims.append((heading, k, row[idx], row))
            if low_sec.startswith("not established"):
                fi = low.index("fact") if "fact" in low else 0
                wi = next((x for x, h in enumerate(low) if h.startswith("who")), None)
                for row in rows:
                    row = row + [""] * (len(header) - len(row))
                    rec.not_established.append(
                        {"fact": row[fi], "who": row[wi] if wi is not None else ""}
                    )
            i = j
            continue
        if low_sec == "gaps" or low_sec.startswith("not established"):
            m = BULLET.match(ln)
            if m:
                if low_sec == "gaps":
                    rec.gaps.append(m.group(2).strip())
                    cur_gap = len(rec.gaps) - 1
                    gap_lines.add(i)
                else:
                    rec.not_established.append({"fact": m.group(2).strip(), "who": ""})
            elif ln.strip() and ln[:1] in (" ", "\t") and cur_gap is not None and low_sec == "gaps":
                rec.gaps[cur_gap] += " " + ln.strip()
                gap_lines.add(i)
            elif ln.strip():
                cur_gap = None
        i += 1
    for k, ln in enumerate(lines):
        if not fence[k] and "present exposure" in ln.casefold() and k not in gap_lines:
            rec.exposure_misplaced.append(k + 1)
    return rec


