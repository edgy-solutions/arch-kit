"""components.py - the component record: loading and validating.

A component is one part of a system: what it is for, how it is wired, how it signs in, where its data goes, which
plane it sits on, what it serves, how far along it is, and the evidence. The kit reads the components from
`files.components` (one YAML file whose only key is `components`), or takes them from the loader's optional
`load_components(root)`. Both routes meet in validate(), so a list validates the same whichever way it arrives. The
planes and the results paths come from the top-level `components:` map of the declaration. The first error raises
InputError, which the caller's handler turns into exit 2. The message is `<where>: <path>: <message>`: the schema's
path is dotted (`components.0.id`), a later check's is `components[i].<key>`.

A list is checked in this order: the schema (arch_kit/schema/components.schema.json), then the checks in check().
One check does not refuse: a `measured` component with no evidence under `components.results` is reported on stderr.

render() makes the Components page and the front page's nav items, and nav() wraps the items; lane 02's render_html
wires them in. CSS goes to the page style. This module must not import render_html.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Callable

import yaml

import alignment
import declared
import project
from data_exchange import InputError

SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "components.schema.json"
KEYS = ("id", "name", "purpose", "plane", "wiring", "sign_in", "data_path", "serves", "status", "evidence")
STATUSES = ("measured", "built", "accepted", "proposed")
PART_WHY = "must be a part name: a letter or digit, then letters, digits, dots, underscores or hyphens"
LINE_WHY = "must be one non-empty line"
PATTERN_WHY = {
    "id": "must be CO- then capitals, digits and hyphens",
    "name": PART_WHY,
    "plane": PART_WHY,
    "purpose": LINE_WHY,
    "wiring": LINE_WHY,
    "sign_in": LINE_WHY,
    "data_path": LINE_WHY,
}
FILE_LINE = re.compile(r"^(.+):([1-9][0-9]*)$")

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
        elif e.validator in ("pattern", "not") and path and path[-1] in PATTERN_WHY:
            message = PATTERN_WHY[path[-1]]
        elif e.validator in ("pattern", "not") and len(path) > 1 and path[-2] == "serves":
            message = LINE_WHY
        elif e.validator == "minItems" and path == ["components"]:
            message = "must list at least one component"
        elif e.validator == "minItems" and path and path[-1] == "evidence":
            message = "must name at least one piece of evidence"
        else:
            message = e.message
        found.append((path, message))
    if not found:
        return None
    found.sort(key=lambda f: [(0, p, "") if isinstance(p, int) else (1, 0, p) for p in f[0]])
    path, message = found[0]
    return ".".join(str(p) for p in path) or "(record)", message


def _file_line(ctx: alignment.Context, item: str) -> bool:
    """Form (c): `path:N`, a file under the repo (path_exists's safety rules) with at least N lines."""
    m = FILE_LINE.match(item)
    if not m or not ctx.path_exists(m.group(1)):
        return False
    target = ctx.repo / m.group(1)
    if not target.is_file():
        return False
    try:
        lines = len(target.read_bytes().decode("utf-8", errors="replace").splitlines())
    except OSError:
        return False
    return int(m.group(2)) <= lines


def _evidence_path(item: str) -> str:
    m = FILE_LINE.match(item)
    return (m.group(1) if m else item).replace("\\", "/")


def _under(path: str, results: tuple[str, ...]) -> bool:
    for r in results:
        r = r.replace("\\", "/").rstrip("/")
        if path == r or path.startswith(r + "/"):
            return True
    return False


def census_only_built(components: list[dict], ctx: alignment.Context) -> tuple[str, ...]:
    """The ids, in record order, of the `built` components whose evidence has no `path:N` and at least one census key."""
    return tuple(c["id"] for c in components
                 if c["status"] == "built" and not any(_file_line(ctx, e) for e in c["evidence"])
                 and any(ctx.census_key(e) for e in c["evidence"]))


def check(where: str, components: list[dict], tool: str, ctx: alignment.Context) -> list[str]:
    """The checks after the schema. Each names the first offending component. Returns the reports (not refusals)."""
    def bad(i: int, key: str, why: str):
        _fail(where, f"components[{i}].{key}", why)

    for key, label in (("id", "component id"), ("name", "component name")):
        seen: set = set()
        for i, c in enumerate(components):
            if c[key] in seen:
                bad(i, key, f"{label} {c[key]} is not unique")
            seen.add(c[key])
    planes, results = declared.components_declaration(tool)
    for i, c in enumerate(components):
        if c["plane"] not in planes:
            bad(i, "plane", f"{c['plane']} is not a declared plane (components.planes)")
    for key in ("serves", "evidence"):
        for i, c in enumerate(components):
            dup = next((d for d in c[key] if c[key].count(d) > 1), None)
            if dup is not None:
                bad(i, key, f"{dup} is listed twice")
    for i, c in enumerate(components):
        for k, item in enumerate(c["evidence"]):
            if ctx.decision_id(item) or ctx.path_exists(item) or _file_line(ctx, item):
                continue
            problem = ctx.census_problem(item)
            if problem is not None:
                bad(i, f"evidence[{k}]", problem)
            if not ctx.census_key(item):
                bad(i, f"evidence[{k}]", f"{item} does not resolve to a decision record or a repository path")
    for i, c in enumerate(components):
        if (c["status"] == "built" and not any(_file_line(ctx, e) for e in c["evidence"])
                and not any(ctx.census_key(e) for e in c["evidence"])):
            bad(i, "evidence", "built needs a file and line (path:N) in evidence")
        if c["status"] == "accepted" and not any(ctx.decision_id(e) or ctx.census_key(e) for e in c["evidence"]):
            bad(i, "evidence", "accepted needs a decision record in evidence")
    reports = []
    census_only = set(census_only_built(components, ctx))
    for i, c in enumerate(components):
        if c["id"] in census_only:
            reports.append(f"{where}: components[{i}].evidence: built, but the only evidence is a census key (no path:N)")
        if c["status"] == "measured" and not any(_under(_evidence_path(e), results) for e in c["evidence"]):
            reports.append(f"{where}: components[{i}].evidence: measured, but no evidence is under components.results")
    return reports


def validate(where: str, record, tool: str, local_ids) -> tuple[dict, ...]:
    """The one validation both routes call: schema (on a map whose only key is `components`), then checks. The
    reports from check() go to stderr; the components come back in file order."""
    err = _first_error(record)
    if err:
        _fail(where, err[0], err[1])
    for report in check(where, record["components"], tool, alignment.Context(tool, local_ids)):
        print(f"{tool}: {report}", file=sys.stderr)
    return tuple(record["components"])


def _loader_function(tool: str) -> Callable | None:
    if "loader" not in project.CONFIG:
        return None
    return getattr(project.loader(tool), "load_components", None)


def declared_route(tool: str) -> bool:
    """True when the project declares `files.components` or a loader `load_components`."""
    return declared.components_file(tool) is not None or _loader_function(tool) is not None


def load(tool: str, local_ids) -> tuple[dict, ...]:
    """The components in file order, validated. Empty when the project declares neither `files.components` nor a
    loader `load_components`."""
    name = declared.components_file(tool)
    fn = _loader_function(tool)
    if name is not None and fn is not None:
        declared._bad("files.components", "is declared, and the loader also defines load_components; use one route")
    if name is None and fn is None:
        return ()
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
        raise InputError("load_components must return a list of components")
    return validate("load_components", {"components": records}, tool, local_ids)


STATUS_LABEL = {"measured": "Measured", "built": "Built", "accepted": "Accepted", "proposed": "Proposed"}
FIELDS = (("purpose", "Purpose"), ("wiring", "Wiring"), ("sign_in", "Sign-in"), ("data_path", "Data path"))
CSS = """
.component-count{color:var(--muted)}
.component{border-top:1px solid var(--line);padding:.5rem 0}
.component h3{font-size:1rem;margin:.5rem 0}
.component dl{display:grid;grid-template-columns:max-content 1fr;gap:2px 12px;margin:0;font-size:14px}
.component dt{color:var(--muted)}
.component dd{margin:0;min-width:0;overflow-wrap:anywhere}
.component-measured{background:var(--m-bg);color:var(--m-fg)}
.component-built{background:var(--b-bg);color:var(--b-fg)}
.component-accepted{background:var(--a-bg);color:var(--a-fg)}
.component-proposed{background:var(--p-bg);color:var(--p-fg)}
nav.components ul{padding-left:1.2em}
""".strip()


def _evidence(item: str, decision_href) -> str:
    href = decision_href(item)
    if href:
        return f'<a href="{_esc(href)}">{_esc(item)}</a>'
    return f"<code>{_esc(item)}</code>"


def _component(c: dict, decision_href) -> str:
    rows = "".join(f"<dt>{label}</dt><dd>{_esc(c[key])}</dd>" for key, label in FIELDS)
    serves = ", ".join(_esc(s) for s in c["serves"]) or "none"
    evidence = ", ".join(_evidence(e, decision_href) for e in c["evidence"])
    status = _esc(c["status"])
    return (f'<article id="component-{_esc(c["id"])}" class="component" data-component="{_esc(c["id"])}" '
            f'data-status="{status}">'
            f'<h3>{_esc(c["id"])} {_esc(c["name"])} <span class="badge component-{status}">'
            f'{_esc(STATUS_LABEL[c["status"]])}</span></h3>'
            f"<dl>{rows}<dt>Serves</dt><dd>{serves}</dd><dt>Evidence</dt><dd>{evidence}</dd></dl></article>")


def render(components, planes, decision_href, prov: str = "", pre: str = "") -> tuple[list[str], list[str]]:
    """The Components page and the front page's nav items; both empty when there are no components.
    `decision_href(item)` returns the href of a local decision record's page, or None. render_html wires it in."""
    if not components:
        return [], []
    n = len(components)
    per = {s: sum(1 for c in components if c["status"] == s) for s in STATUSES}
    count = (f'<p class="component-count" data-component-count>{n} {"component" if n == 1 else "components"}: '
             f'{per["measured"]} measured, {per["built"]} built, {per["accepted"]} accepted, '
             f'{per["proposed"]} proposed.</p>')
    order = list(planes) + [p for p in dict.fromkeys(c["plane"] for c in components) if p not in planes]
    groups = ""
    for plane in order:
        members = [c for c in components if c["plane"] == plane]
        if members:
            groups += f'<h2 data-plane="{_esc(plane)}">{_esc(plane)}</h2>'
            groups += "".join(_component(c, decision_href) for c in members)
    page = (f'<section id="components" class="page components" data-components><h1>{_esc(pre)}Components</h1>'
            f'<p><a href="#front">Front page</a></p>{count}{groups}{prov}</section>')
    return [page], [f'<li><a href="#components">Components ({n})</a></li>']


def nav(items: list[str]) -> str:
    if not items:
        return ""
    return f'<nav class="components"><h2>Components</h2><ul>{"".join(items)}</ul></nav>'
