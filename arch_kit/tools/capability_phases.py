#!/usr/bin/env python3
"""capability_phases.py - the phase and evidence of every St-Tx capability, from the record.

Reads docs/arch/capability-record.yaml, which says for each capability in the
model's CapabilityTaxonomy what it cites: decision records, chart templates,
register rows, readiness entries. Nothing in the record states a phase or
evidence; both are computed here, and every citation has to resolve against
the file it names or the render fails.

Phases, highest first:
    measured          cites a readiness entry under `measured`
    built unmeasured  cites a chart template under `built`, and no readiness entry
    accepted design   cites an ADR whose Status begins with accepted
    proposed          cites an ADR whose Status begins with proposed, or a
                      `still_open` citation, or a `pending` entry
    row               cites only rows in a register
A capability that cites none of these has no phase, and that is a failure.

Evidence comes from the readiness doc only: an entry is an anchor line that
holds a date, and a quote is the cited line. A decision record's wording is
never read for evidence, only its Status line. A message names the record's
own text (capability, entry, anchor, line); it never echoes a readiness line.

Two keys say how a capability's page reads:
    description   two or three plain sentences, written from the decisions below
    derived_from  citations the description was written from; when absent, from `adrs`
    severed       (kit key degraded_mode) required for every capability: the exact string `not stated`, or one
                  citation `ADR-NNNN §LABEL` of the record that says how the capability
                  behaves when its link is severed. `not stated` needs an `SV-` id in
                  `rows`; a citation needs none.
    pending       optional list of non-empty strings naming the sources a decision waits
                  on. A capability with it is at least `proposed`, and needs no
                  `derived_from` or `adrs`.
A decision is cited by section: `ADR-0038 §1`, in `adrs`, `derived_from` and
`still_open[].adr`. The label is the number a heading starts with, or the
GitHub slug of a heading with none (adr_sections.py lists them). A bare
`ADR-0038` cites no section, and a section that does not resolve fails.

Used by render_profile.py (the St-Rm-P marker) and check_views.py (the
`phases` rule). This module writes no file. Stdlib and PyYAML only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import adr_sections
import project
from data_exchange import InputError

PHASES = ["measured", "built unmeasured", "accepted design", "proposed", "row"]
NOT_MEASURED = "not measured"
SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "record.schema.json"


def follow_ups_file():
    return project.need("registers.follow_ups", "capability_phases")


def debt_file():
    return project.need("registers.debt", "capability_phases")


def roadmap_file():
    return project.need("registers.roadmap", "capability_phases")


OUTPUT_FIELDS = ("phase", "evidence")
NOT_STATED = "not stated"
SECTIONS = ("groups", "environments", "entries", "capabilities")
CAP_KEYS = ("description", "derived_from", "adrs", "built", "measured", "rows", "still_open", "increment",
            "degraded_mode", "pending")
ADR_ID_RE = re.compile(r"ADR-\d{4}")


class CheckError(Exception):
    """A citation did not resolve: exit 1. Carries stderr to pass through."""


# --- record and model ---------------------------------------------------------

def key_names(tool: str) -> dict[str, str]:
    """The neutral record keys to the consumer's own, for messages (the loader's KEY_NAMES)."""
    return project.loader(tool).KEY_NAMES


def _validate(path, record: dict) -> None:
    """Raise InputError for the first place the loader's record breaks the neutral schema."""
    import jsonschema
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(record),
                    key=lambda e: [str(p) for p in e.absolute_path])
    if not errors:
        return
    first = errors[0]
    where = ".".join(str(p) for p in first.absolute_path) or "(record)"
    text = f"{where}: {first.message}"
    for neutral, own in key_names("load_record").items():  # the consumer's words, as in every other message
        text = re.sub(rf"\b{neutral}\b", own, text)
    raise InputError(f"{path}: {text}")


def load_record(path) -> dict:
    record = project.loader("capability_phases").load_record(path)
    _validate(path, record)
    return record


def model_capabilities(sysml_text: str) -> dict[str, str]:
    return project.loader("capability_phases").model_capabilities(sysml_text)


# --- reading the decisions ----------------------------------------------------

def read_text(path: Path) -> str | None:
    return project.loader("capability_phases").read_text(path)


def adr_file(decisions_dir: Path, adr: str) -> Path | None:
    return project.loader("capability_phases").adr_file(decisions_dir, adr)


def adr_lead(decisions_dir: Path, adr: str) -> str | None:
    return project.loader("capability_phases").adr_lead(decisions_dir, adr)


def adr_id(citation) -> str:
    """The ADR id a citation starts with; the text itself when it starts with none."""
    m = ADR_ID_RE.match(str(citation).strip())
    return m.group(0) if m else str(citation)


def parsed(items) -> list[tuple[str, str]]:
    """(id, label) of each item that is a citation; an item that is not one is left out."""
    out = []
    for item in items or []:
        try:
            out.append(adr_sections.parse_citation(item))
        except ValueError:
            pass
    return out


def record_adrs(cap: dict) -> list[str]:
    """The ADR ids `adrs` cites, de-duplicated in order."""
    return list(dict.fromkeys(adr_id(c) for c in cap.get("adrs") or []))


def record_citations(cap: dict) -> list[tuple[str, str]]:
    return parsed(cap.get("adrs"))


def derived_citations(cap: dict) -> list[tuple[str, str]]:
    return parsed(cap.get("derived_from"))


def open_citations(cap: dict) -> list[tuple[str, str]]:
    return parsed((s or {}).get("adr") for s in cap.get("still_open") or [] if isinstance(s, dict))


def still_open(cap: dict) -> list[dict]:
    return list(cap.get("still_open") or [])


def statuses_of(record: dict, decisions_dir) -> dict[str, str | None]:
    """ADR id to the file's lead status, for every ADR the record cites."""
    ids = set()
    for cap in record["capabilities"].values():
        cap = cap or {}
        ids.update(record_adrs(cap))
        ids.update(adr_id(s.get("adr")) for s in still_open(cap) if isinstance(s, dict) and s.get("adr"))
    return {i: adr_lead(Path(decisions_dir), i) for i in sorted(i for i in ids if i)}


def split_row(line: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def register_rows(text: str) -> dict[str, str]:
    return project.loader("capability_phases").register_rows(text)


def register_subjects(text: str) -> dict[str, tuple[str, str]]:
    return project.loader("capability_phases").register_subjects(text)


def roadmap_rows(text: str) -> list[list[str]]:
    return project.loader("capability_phases").roadmap_rows(text)


def roadmap_row(rows: list[list[str]], increment: str) -> list[str] | None:
    exact = [r for r in rows if len(r) > 1 and r[1] == increment]
    return (exact or [r for r in rows if any(increment in c for c in r)] or [None])[0]


def increment_label(cap: dict, road_rows: list[list[str]]) -> str | None:
    """`number: text` for the capability's CV-3 increment, or None when it names none."""
    if not cap.get("increment"):
        return None
    first = roadmap_row(road_rows, cap["increment"])[0]
    number = "done" if first.startswith("done") else first
    return f"{number}: {cap['increment'].replace('**', '')}"


def index_status(index_text: str, adr: str) -> str | None:
    return project.loader("capability_phases").index_status(index_text, adr)


def sentences(text: str) -> int:
    """How many sentences the text has: the . ? and ! that end one, not those of e.g. and i.e."""
    text = re.sub(r"\b(e\.g|i\.e)\.", "", text, flags=re.I)
    return len(re.findall(r"[.?!][\"')\]]*(?=\s|$)", text))


def check_description(name: str, description) -> list[str]:
    if not isinstance(description, str) or not description.strip():
        return [f"{name} has no description"]
    n = sentences(description)
    if not 2 <= n <= 4:
        return [f"{name}: the description has {n} sentence{'s' if n != 1 else ''}, expected two or three"]
    return []


def check_section(name: str, item, decisions_dir: Path) -> list[str]:
    """A citation must be `ADR-NNNN §LABEL` and the label must name one heading of the record."""
    try:
        adr, label = adr_sections.parse_citation(item)
    except ValueError:
        return [f"{name}: {item!r} cites no section"]
    path = adr_file(decisions_dir, adr)
    text = read_text(path) if path else None
    if text is None:
        return []  # no file: check_adr says so
    try:
        adr_sections.resolve(text, label)
    except LookupError as e:
        return [f"{name}: {adr} §{label}: {e.args[0]}"]
    return []


# --- the record against the decisions -----------------------------------------

def check_record(record: dict, capabilities: dict[str, str], decisions_dir) -> list[str]:
    """Every failure, one line each. Needs no chart and no readiness doc."""
    decisions_dir = Path(decisions_dir)
    names = key_names("check_record")
    fails: list[str] = []
    caps = {k: (v or {}) for k, v in record["capabilities"].items()}
    for name in capabilities:
        if name not in caps:
            fails.append(f"{name} is a capability in the model and has no entry in the record")
    for name in caps:
        if name not in capabilities:
            fails.append(f"{name} is in the record and is not a capability in the model")
    for parent in dict.fromkeys(capabilities.values()):
        if parent not in record["groups"]:
            fails.append(f"{parent} has no {names['groups']} entry in the record")
    for key, entry in record["entries"].items():
        entry = entry or {}
        if entry.get("environment") not in record["environments"]:
            fails.append(f"entry {key} names {names['environment']} {entry.get('environment')}, "
                         f"which {names['environments']} does not declare")
        for f in OUTPUT_FIELDS:
            if f in entry:
                fails.append(f"entry {key} has a field '{f}': phase and evidence are computed, not recorded")

    index_text = read_text(decisions_dir / "README.md")
    follow = read_text(decisions_dir / follow_ups_file())
    debt = read_text(decisions_dir / debt_file())
    road = read_text(decisions_dir / roadmap_file())
    registers = register_rows(follow) if follow is not None else {}
    road_rows = roadmap_rows(road) if road is not None else []
    for label, text in ((f"decisions/{follow_ups_file()}", follow), (f"decisions/{debt_file()}", debt),
                        (f"decisions/{roadmap_file()}", road), ("decisions/README.md", index_text)):
        if text is None:
            fails.append(f"{label} cannot be read")

    seen_adrs: set[str] = set()

    def check_adr(name: str, adr: str) -> str | None:
        path = adr_file(decisions_dir, adr)
        if path is None:
            if adr not in seen_adrs:
                fails.append(f"{name}: {adr} is not exactly one file in decisions/")
            seen_adrs.add(adr)
            return None
        lead = adr_lead(decisions_dir, adr)
        if adr not in seen_adrs:
            if index_text is not None and f"[{adr}:" not in index_text:
                fails.append(f"{name}: {adr} is not in decisions/README.md")
            if not lead or not lead.startswith(("accepted", "proposed")):
                fails.append(f"{name}: {adr} has no readable ## Status line beginning accepted or proposed")
        seen_adrs.add(adr)
        return lead

    for name, cap in caps.items():
        for f in OUTPUT_FIELDS:
            if f in cap:
                fails.append(f"{name} has a field '{f}': phase and evidence are computed, not recorded")
        if not any(cap.get(k) for k in ("adrs", "built", "measured", "still_open", "rows", "pending")):
            fails.append(f"{name} has no phase")
        for key in cap:
            if key not in CAP_KEYS and key not in OUTPUT_FIELDS:
                fails.append(f"{name} has a key '{key}' that the record does not accept")
        fails += check_description(name, cap.get("description"))
        pend = cap.get("pending")
        if pend is not None and (not isinstance(pend, list) or not pend
                                 or not all(isinstance(p, str) and p.strip() for p in pend)):
            fails.append(f"{name}: pending must be a list of non-empty strings")
        if not cap.get("adrs") and not cap.get("derived_from") and not pend:
            fails.append(f"{name}: its description is derived from no decision")
        cited = list(cap.get("adrs") or []) + list(cap.get("derived_from") or []) + [
            (s or {}).get("adr") for s in still_open(cap) if isinstance(s, dict) and (s or {}).get("adr")]
        for item in cited:
            fails += check_section(name, item, decisions_dir)
        for adr in dict.fromkeys(adr_id(c) for c in list(cap.get("adrs") or []) + list(cap.get("derived_from") or [])):
            check_adr(name, adr)
        for item in still_open(cap):
            adr, says = (item or {}).get("adr"), (item or {}).get("says")
            if not adr or not says:
                fails.append(f"{name}: a still_open citation needs adr and says")
                continue
            adr = adr_id(adr)
            check_adr(name, adr)
            path = adr_file(decisions_dir, adr)
            text = read_text(path) if path else None
            if text is not None and says not in text:
                fails.append(f"{name}: {adr} does not contain {says!r}")
        sv_rows = [r for r in cap.get("rows") or [] if str(r).startswith("SV-")]
        degraded = cap.get("degraded_mode")
        dm = names["degraded_mode"]
        if not degraded:
            fails.append(f"{name} has no {dm} entry")
        elif degraded == NOT_STATED:
            if not sv_rows:
                fails.append(f"{name}: {dm} is not stated and rows names no SV- row")
        else:
            try:
                adr_sections.parse_citation(degraded)
            except ValueError:
                fails.append(f"{name}: {dm} {degraded!r} is neither '{NOT_STATED}' nor a citation ADR-NNNN §LABEL")
            else:
                fails += check_section(name, degraded, decisions_dir)
                check_adr(name, adr_id(degraded))
                if sv_rows:
                    fails.append(f"{name}: {dm} is stated in {degraded} and rows still names {sv_rows[0]}")
        for row in cap.get("rows") or []:
            status = registers.get(row)
            if follow is not None and status is None:
                fails.append(f"{name}: row {row} is not in a | ID | Subject | Status | register in decisions/{follow_ups_file()}")
            elif status is not None and status.lstrip("* ").lower().startswith("fixed"):
                fails.append(f"{name}: row {row} is {status}, not open")
            if row.startswith("GD-") and debt is not None and not re.search(
                    rf"(?<![\w-]){re.escape(row)}(?![\w-])", debt):
                fails.append(f"{name}: row {row} is not in decisions/{debt_file()}")
        increment = cap.get("increment")
        if increment and road is not None and roadmap_row(road_rows, increment) is None:
            fails.append(f"{name}: increment {increment} is not on a table row of decisions/{roadmap_file()}")
        for m in cap.get("measured") or []:
            if (m or {}).get("entry") not in record["entries"]:
                fails.append(f"{name}: measured names entry {(m or {}).get('entry')}, which entries does not declare")
    return fails


def phase_of(cap: dict, statuses: dict[str, str | None]) -> str | None:
    """The highest phase the capability's citations give. `statuses` is from statuses_of."""
    cap = cap or {}
    leads = [(statuses.get(a) or "") for a in record_adrs(cap)]
    if cap.get("measured"):
        return "measured"
    if cap.get("built"):
        return "built unmeasured"
    if any(s.startswith("accepted") for s in leads):
        return "accepted design"
    if any(s.startswith("proposed") for s in leads) or still_open(cap) or cap.get("pending"):
        return "proposed"
    if cap.get("rows"):
        return "row"
    return None


# --- the document -------------------------------------------------------------

def quote_of(lines: list[str], at: int) -> str:
    return project.loader("capability_phases").quote_of(lines, at)


def resolve_entries(record: dict, readiness_lines: list[str]) -> tuple[dict, list[str]]:
    return project.loader("capability_phases").resolve_entries(record, readiness_lines)


def measured_line(readiness_lines: list[str], at: int, text: str) -> list[int]:
    return project.loader("capability_phases").measured_line(readiness_lines, at, text)


def lab_sentence(labs: dict, used: list[str]) -> str:
    parts = [f"{'Lab' if i == 0 else 'lab'} {k}{' is' if i == 0 else ''} {labs[k]}"
             for i, k in enumerate(used)]
    if len(parts) > 1:
        parts = [", ".join(parts[:-1]) + " and " + parts[-1]] if len(parts) > 2 else [" and ".join(parts)]
    return parts[0] + "." if parts else ""


def resolve_quotes(record: dict, readiness: list[str], entries: dict | None = None) -> tuple[dict, list[str]]:
    return project.loader("capability_phases").resolve_quotes(record, readiness, entries=entries)


def evidence_item(record: dict, entries: dict, measured: dict, quote: str) -> str:
    """One piece of evidence, as the Evidence column prints it."""
    _, date, section = entries[measured["entry"]]
    return f"{date}, lab {record['entries'][measured['entry']]['environment']}, {section}: {quote}"


def evidence_cells(record: dict, readiness_text: str) -> dict[str, list[str]]:
    """Capability to the evidence strings render_table prints for it, joined by '; '. Raises CheckError."""
    readiness = readiness_text.replace("\r\n", "\n").split("\n")
    entries, fails = resolve_entries(record, readiness)
    quotes, quote_fails = resolve_quotes(record, readiness, entries)
    fails += quote_fails
    if fails:
        raise CheckError("".join(f"phases: {f}\n" for f in fails))
    return {name: [evidence_item(record, entries, m, quotes[(name, k)]) for k, m in enumerate(cap["measured"])]
            for name, cap in ((n, c or {}) for n, c in record["capabilities"].items())
            if cap.get("measured")}


def render_table(record: dict, capabilities: dict[str, str], decisions_dir, templates_dir,
                 readiness_text: str) -> str:
    """The phases document text. Raises CheckError listing every failure."""
    decisions_dir, templates_dir = Path(decisions_dir), Path(templates_dir)
    fails = check_record(record, capabilities, decisions_dir)
    readiness = readiness_text.replace("\r\n", "\n").split("\n")
    entries, entry_fails = resolve_entries(record, readiness)
    fails += entry_fails
    caps = {k: (v or {}) for k, v in record["capabilities"].items()}

    for name, cap in caps.items():
        for b in cap.get("built") or []:
            tpl, contains = (b or {}).get("template"), (b or {}).get("contains")
            text = read_text(templates_dir / tpl) if tpl else None
            if text is None:
                fails.append(f"{name}: template {tpl} is not in the chart's templates")
            elif not contains or contains not in text:
                fails.append(f"{name}: template {tpl} does not contain {contains!r}")
    quotes, quote_fails = resolve_quotes(record, readiness, entries)
    fails += quote_fails
    if fails:
        raise CheckError("".join(f"phases: {f}\n" for f in fails))

    statuses = statuses_of(record, decisions_dir)
    index_text = read_text(decisions_dir / "README.md") or ""
    road_rows = roadmap_rows(read_text(decisions_dir / roadmap_file()) or "")
    rows, counts, used = [], dict.fromkeys(PHASES, 0), set()
    for name, parent in capabilities.items():
        cap = caps[name]
        phase = phase_of(cap, statuses)
        counts[phase] += 1
        lane = str(record["groups"][parent])
        label = increment_label(cap, road_rows)
        if label:
            lane += f", {label}"
        evidence = NOT_MEASURED
        if phase == "measured":
            used.update(record["entries"][m["entry"]]["environment"] for m in cap["measured"])
            evidence = "; ".join(evidence_item(record, entries, m, quotes[(name, k)])
                                 for k, m in enumerate(cap["measured"]))
        built = list(dict.fromkeys(f"templates/{b['template']}" for b in cap.get("built") or []))
        decisions, noted = [], set()
        for adr, label in record_citations(cap):
            note = ""
            if adr not in noted:
                theirs = index_status(index_text, adr)
                mine = "accepted" if statuses[adr].startswith("accepted") else "proposed"
                note = f" (record: {mine}; index: {theirs})" if theirs and mine != theirs else ""
                noted.add(adr)
            decisions.append(f"{adr} §{label}{note}")
        decisions += [f"{adr} §{label} (names it still open)" for adr, label in open_citations(cap)]
        if cap.get("pending"):
            decisions.append("decision pending")
        rows.append(f"| {name} | {lane} | {phase} | {evidence} | {', '.join(built) or '-'} | "
                    f"{', '.join(decisions) or '-'} | {', '.join(cap.get('rows') or []) or '-'} |")

    out = ["Phases: " + ", ".join(f"{counts[p]} {p}" for p in PHASES) + ".", "",
           "| Capability | Lane | Phase | Evidence | Built | Decisions | Rows |",
           "|---|---|---|---|---|---|---|", *rows, ""]
    if used:
        out += [lab_sentence(record["environments"], sorted(used)), ""]
    out += ['An entry is the last time the readiness doc records that check. It ran against the chart of that '
            'date, which can be older than the chart this document was rendered from. "Not measured" means '
            'the readiness doc has no entry for the capability, and says nothing about measurements recorded '
            'elsewhere.']
    return "\n".join(out)


# --- the barred list ----------------------------------------------------------

def load_barred(paths) -> list[re.Pattern]:
    """Compile the barred list: a pattern per line, `#` comments, an optional `|reason` tail."""
    patterns: list[re.Pattern] = []
    for path in paths:
        name = Path(path).name
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError:
            raise CheckError(f"barred list {name} cannot be read") from None
        for n, line in enumerate(text.splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            if "|" in line:
                line = line.rsplit("|", 1)[0]
            try:
                patterns.append(re.compile(line, re.IGNORECASE))
            except re.error:
                raise CheckError(f"barred list {name} line {n} does not compile") from None
    if not patterns:
        raise CheckError("the barred list is empty")
    return patterns


def scan_barred(texts: dict[str, list[str]], barred) -> list[str]:
    """One failure per name that carries a barred value. It never says which, or what matched."""
    fails = []
    for name, strings in texts.items():
        n = sum(len(p.findall(s)) for s in strings for p in barred)
        if n:
            fails.append(f"quotes: {name}: carries {n} barred value(s)")
    return fails
