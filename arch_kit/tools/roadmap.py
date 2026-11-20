"""roadmap.py - the roadmap record: loading and validating.

A roadmap is an ordered list of increments. Each names what it isolates, where its decision lives, which earlier
increments it depends on, and how far along it is. There is no date key and no date in the text: the order and
`depends_on` are the schedule. The kit reads the increments from `files.roadmap` (one YAML file whose only key is
`roadmap`), or takes them from the loader's optional `load_roadmap(root)`. Both routes meet in validate(), so a list
validates the same whichever way it arrives. The first error raises InputError, which the caller's handler turns into
exit 2. The message is `<where>: <path>: <message>`: the schema's path is dotted (`roadmap.0.id`), a later check's is
`roadmap[i].<key>`.

A list is checked in this order: the schema (arch_kit/schema/roadmap.schema.json), then the checks in check().
`depends_on` names only increments that come earlier in the list, so there is no cycle to find and no separate cycle
check.

The record and the roadmap note are two routes to one roadmap. When a route is declared and `registers.roadmap` names a
file that exists under the decisions directory, load() refuses; a declared note that does not exist is not an error.

render() makes the Roadmap page and the front page's nav items, and nav() wraps the items; render_html wires
them in, passing render_html's roadmap page id as `page_id` so the existing links to the roadmap page keep working.
CSS goes to the page style. This module must not import render_html.
"""
from __future__ import annotations

import datetime
import html
import json
import re
from pathlib import Path
from typing import Callable

import yaml

import alignment
import declared
import project
from data_exchange import InputError

SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "roadmap.schema.json"
KEYS = ("id", "increment", "isolates", "home", "depends_on", "status")
STATUSES = ("measured", "built", "accepted", "proposed")
ID_WHY = "must be RM- then capitals, digits and hyphens"
LINE_WHY = "must be one non-empty line"
DATE_WHY = "is a date; a roadmap carries no dates"
NO_DATES = "a roadmap carries no dates"
DATE_IN_TEXT = re.compile(r"\b[0-9]{4}-[0-9]{2}(-[0-9]{2})?\b")

_SCHEMA_CACHE: dict = {}


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _schema() -> dict:
    if "schema" not in _SCHEMA_CACHE:
        _SCHEMA_CACHE["schema"] = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE["schema"]


def _fail(where: str, path: str, message: str):
    raise InputError(f"{where}: {path}: {message}")


def _first_error(instance) -> tuple[str, str] | None:
    """The first schema error as (dotted path, message), in path order, or None."""
    import jsonschema
    found = []
    for e in jsonschema.Draft202012Validator(_schema()).iter_errors(instance):
        path = list(e.absolute_path)
        if e.validator == "required":
            path.append([k for k in e.validator_value if k not in e.instance][0])
            message = "is required"
        elif e.validator == "additionalProperties":
            path.append(sorted(k for k in e.instance if k not in e.schema.get("properties", {}))[0])
            message = "unknown key"
        elif e.validator == "type" and isinstance(e.instance, datetime.date):
            message = DATE_WHY
        elif e.validator in ("pattern", "not") and path and path[-1] == "id":
            message = ID_WHY
        elif e.validator in ("pattern", "not") and len(path) > 1 and path[-2] == "depends_on":
            message = ID_WHY
        elif e.validator in ("pattern", "not") and path and path[-1] in ("increment", "isolates", "home"):
            message = LINE_WHY
        elif e.validator == "minItems" and path == ["roadmap"]:
            message = "must list at least one increment"
        else:
            message = e.message
        found.append((path, message))
    if not found:
        return None
    found.sort(key=lambda f: [(0, p, "") if isinstance(p, int) else (1, 0, p) for p in f[0]])
    path, message = found[0]
    return ".".join(str(p) for p in path) or "(record)", message


def check(where: str, items: list[dict], tool: str, ctx: alignment.Context) -> None:
    """The checks after the schema. Each names the first offending increment; the first failure raises."""
    def bad(i: int, key: str, why: str):
        _fail(where, f"roadmap[{i}].{key}", why)

    for key, label in (("id", "increment id"), ("increment", "increment")):
        seen: set = set()
        for i, r in enumerate(items):
            if r[key] in seen:
                bad(i, key, f"{label} {r[key]} is not unique")
            seen.add(r[key])
    for key in ("increment", "isolates"):
        for i, r in enumerate(items):
            if DATE_IN_TEXT.search(r[key]):
                bad(i, key, NO_DATES)
    for i, r in enumerate(items):
        dup = next((d for d in r["depends_on"] if r["depends_on"].count(d) > 1), None)
        if dup is not None:
            bad(i, "depends_on", f"{dup} is listed twice")
    ids = [r["id"] for r in items]
    for i, r in enumerate(items):
        for k, dep in enumerate(r["depends_on"]):
            if dep == r["id"]:
                bad(i, f"depends_on[{k}]", "an increment cannot depend on itself")
            if dep in ids[i + 1:]:
                bad(i, f"depends_on[{k}]", f"{dep} comes later; an increment depends only on earlier ones")
            if dep not in ids[:i]:
                bad(i, f"depends_on[{k}]", f"{dep} is not an increment id")
    for i, r in enumerate(items):
        home = r.get("home")
        if home is None:
            if r["status"] != "proposed":
                bad(i, "home", "is required unless the status is proposed")
        elif not ctx.decision_id(home):
            problem = ctx.census_problem(home)
            if problem is not None:
                bad(i, "home", problem)
            if not ctx.census_key(home):
                bad(i, "home", f"{home} does not resolve to a decision record")


def validate(where: str, record, tool: str, local_ids) -> tuple[dict, ...]:
    """The one validation both routes call: schema (on a map whose only key is `roadmap`), then checks. The
    increments come back in file order."""
    err = _first_error(record)
    if err:
        _fail(where, err[0], err[1])
    check(where, record["roadmap"], tool, alignment.Context(tool, local_ids))
    return tuple(record["roadmap"])


def _loader_function(tool: str) -> Callable | None:
    if "loader" not in project.CONFIG:
        return None
    return getattr(project.loader(tool), "load_roadmap", None)


def declared_route(tool: str) -> bool:
    """True when the project declares `files.roadmap` or a loader `load_roadmap`."""
    return declared.roadmap_file(tool) is not None or _loader_function(tool) is not None


def _refuse_note() -> None:
    """Exit 2 when `registers.roadmap` names a note that exists: the record and the note are one roadmap, not two.
    An undeclared register means no note, and a declared one that names no file is not an error."""
    registers = project.CONFIG.get("registers")
    name = registers.get("roadmap") if isinstance(registers, dict) else None
    if isinstance(name, str) and name and (project.DECISIONS / name).is_file():
        declared._bad("files.roadmap", f"is declared, and the roadmap note decisions/{name} exists; use one")


def load(tool: str, local_ids) -> tuple[dict, ...]:
    """The increments in file order, validated. Empty when the project declares neither `files.roadmap` nor a loader
    `load_roadmap`."""
    name = declared.roadmap_file(tool)
    fn = _loader_function(tool)
    if name is not None and fn is not None:
        declared._bad("files.roadmap", "is declared, and the loader also defines load_roadmap; use one route")
    if name is None and fn is None:
        return ()
    _refuse_note()
    if name is not None:
        path = project.ROOT / name
        try:
            record = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            raise InputError(f"{name}: (record): cannot be read") from None
        except yaml.YAMLError:
            raise InputError(f"{name}: (record): not valid YAML") from None
        return validate(name, record, tool, local_ids)
    records = fn(project.ROOT)
    if not isinstance(records, list):
        raise InputError("load_roadmap must return a list of increments")
    return validate("load_roadmap", {"roadmap": records}, tool, local_ids)


STATUS_LABEL = {"measured": "Measured", "built": "Built", "accepted": "Accepted", "proposed": "Proposed"}
CSS = """
.roadmap-count{color:var(--muted)}
.roadmap-measured{background:var(--m-bg);color:var(--m-fg)}
.roadmap-built{background:var(--b-bg);color:var(--b-fg)}
.roadmap-accepted{background:var(--a-bg);color:var(--a-fg)}
.roadmap-proposed{background:var(--p-bg);color:var(--p-fg)}
nav.roadmap ul{padding-left:1.2em}
""".strip()


def _home(home, decision_href) -> str:
    if home is None:
        return "none"
    href = decision_href(home)
    if href:
        return f'<a href="{_esc(href)}">{_esc(home)}</a>'
    return f"<code>{_esc(home)}</code>"


def _row(n: int, r: dict, decision_href, page_id: str) -> str:
    deps = ", ".join(f'<a href="#{_esc(page_id)}-{_esc(d)}">{_esc(d)}</a>' for d in r["depends_on"]) or "none"
    status = _esc(r["status"])
    return (f'<tr id="{_esc(page_id)}-{_esc(r["id"])}" data-increment="{_esc(r["id"])}" data-status="{status}">'
            f'<td>{n}</td><td>{_esc(r["id"])}</td><td>{_esc(r["increment"])}</td><td>{_esc(r["isolates"])}</td>'
            f'<td>{_home(r.get("home"), decision_href)}</td><td>{deps}</td>'
            f'<td><span class="badge roadmap-{status}">{_esc(STATUS_LABEL[r["status"]])}</span></td></tr>')


def render(items, decision_href, prov: str = "", pre: str = "", page_id: str = "roadmap") -> tuple[list[str], list[str]]:
    """The Roadmap page and the front page's nav items; both empty when there are no increments.
    `decision_href(item)` returns the href of a local decision record's page, or None. render_html wires it in and
    passes its own roadmap page id as `page_id`, so the existing links to the roadmap page keep working."""
    if not items:
        return [], []
    n = len(items)
    per = {s: sum(1 for r in items if r["status"] == s) for s in STATUSES}
    count = (f'<p class="roadmap-count" data-roadmap-count>{n} {"increment" if n == 1 else "increments"}: '
             f'{per["measured"]} measured, {per["built"]} built, {per["accepted"]} accepted, '
             f'{per["proposed"]} proposed.</p>')
    rows = "".join(_row(i, r, decision_href, page_id) for i, r in enumerate(items, 1))
    table = ('<div class="scroll"><table><thead><tr><th>#</th><th>Id</th><th>Increment</th><th>What isolates</th>'
             f'<th>Home</th><th>Depends on</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>')
    pid = _esc(page_id)
    page = (f'<section id="{pid}" class="page roadmap" data-roadmap><h1>{_esc(pre)}Roadmap</h1>'
            f'<p><a href="#front">Front page</a></p>{count}{table}{prov}</section>')
    return [page], [f'<li><a href="#{pid}">Roadmap ({n})</a></li>']


def nav(items: list[str]) -> str:
    if not items:
        return ""
    return f'<nav class="roadmap"><h2>Roadmap</h2><ul>{"".join(items)}</ul></nav>'
