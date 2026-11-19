"""pages.py - the prose page: loading, validating and rendering.

A page is a project's overview or one walkthrough, written as prose. Every record it cites is checked to exist, and a
status it claims is checked against the record, so prose cannot claim more than the records do. The kit reads the pages
from `files.pages` (a directory of *.md files, directly in it, in sorted order), or takes them from the loader's
optional `load_pages(root)`. Both routes meet in the same checks, so a page checks the same whichever way it arrives.
The first error raises InputError, which the caller's handler turns into exit 2.

A page file opens with YAML front matter between a first line `---` and the next line that is exactly `---`. The front
matter is a map whose only keys are `title`, `kind` (overview or walkthrough) and `order`; the body is everything after
the closing line, and the id is the file stem. A loader's page is `{id, title, kind, body}` and an optional `order`.

A list is checked in this order: the schema (arch_kit/schema/pages.schema.json), then the checks in check(): ids are
unique, at most one page is the overview, and every citation resolves. The message is `<file>: <key>: <why>` on the
directory route and `load_pages: pages[i].<key>: <why>` on the loader route. A citation error reads `<where>: line N:
<why>`: N is the 1-based line in the file (front matter counted) on the directory route, and the line in `body` on the
loader route.

A citation is `[[ident]]` or `[[ident|status]]`. The ident is a component (CO-), an increment (RM-), a flow (FL-),
`alignment:<name>`, or else a decision id (local or foreign). A status is one of measured, built, accepted, proposed,
and is checked against the record.

render() makes one page per file and the front page's nav items, and nav() wraps the items; render_html
wires them in. CSS goes to the page style. This module must not import render_html.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Callable

import yaml

import alignment
import components
import declared
import flows
import project
import roadmap
from data_exchange import InputError

SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "pages.schema.json"
KEYS = ("id", "title", "kind", "order", "body")
FRONT_KEYS = ("title", "kind", "order")
KINDS = ("overview", "walkthrough")
STATUSES = ("measured", "built", "accepted", "proposed")
ID_WHY = "must be lowercase letters, digits and hyphens"
TITLE_WHY = "must be one non-empty line"
BODY_WHY = "must not be empty"
FRONT_WHY = "must open with front matter between --- lines"
CITATION = re.compile(r"\[\[([^\[\]|\s]+)(?:\|([^\[\]\s]+))?\]\]")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
COMPONENT_ID = re.compile(r"CO-[A-Z0-9]+(-[A-Z0-9]+)*")
INCREMENT_ID = re.compile(r"RM-[A-Z0-9]+(-[A-Z0-9]+)*")
FLOW_ID = re.compile(r"FL-[A-Z0-9]+(-[A-Z0-9]+)*")
ALIGNMENT = "alignment:"
PLACEHOLDER = re.compile("\ue000([0-9]+)\ue001")

_SCHEMA_CACHE: dict = {}


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _schema() -> dict:
    if "schema" not in _SCHEMA_CACHE:
        _SCHEMA_CACHE["schema"] = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE["schema"]


def _first_error(instance) -> tuple[list, str] | None:
    """The first schema error as (path, message), in path order, or None."""
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
        elif e.validator in ("pattern", "not") and path and path[-1] == "id":
            message = ID_WHY
        elif e.validator in ("pattern", "not") and path and path[-1] == "title":
            message = TITLE_WHY
        elif e.validator == "pattern" and path and path[-1] == "body":
            message = BODY_WHY
        elif e.validator == "minItems" and path == ["pages"]:
            message = "must list at least one page"
        else:
            message = e.message
        found.append((path, message))
    if not found:
        return None
    found.sort(key=lambda f: [(0, p, "") if isinstance(p, int) else (1, 0, p) for p in f[0]])
    return found[0]


# --- citations -----------------------------------------------------------------------------------------------------

def _blank_code_spans(line: str) -> str:
    """The line with each inline code span (backticks included) replaced by spaces, so positions are kept."""
    return CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)


def _citations(body: str) -> list[tuple[int, int, int, str, str | None]]:
    """Every citation in a page body as (line_no, start, end, ident, status_or_None), in order. line_no is the
    1-based line in `body`; start and end are the columns of the whole `[[...]]` in that line. The check and the
    render both use this, so they agree on what counts. A citation inside a fenced code block (a line starting, after
    up to three spaces, with ``` or ~~~ opens a fence; the same marker, at least as long, closes it) or inside an
    inline code span is not one. Indented code blocks are not special-cased: a citation in one counts."""
    out = []
    fence: str | None = None
    for n, line in enumerate(body.split("\n"), 1):
        m = FENCE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)
                continue
        else:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) \
                    and not line.lstrip(" ")[len(m.group(1)):].strip():
                fence = None
            continue
        for c in CITATION.finditer(_blank_code_spans(line)):
            out.append((n, c.start(), c.end(), c.group(1), c.group(2)))
    return out


class _Records:
    """The record sets a citation may name, each loaded at most once and only when a citation needs it."""

    def __init__(self, tool: str, local_ids):
        self.tool = tool
        self.local_ids = local_ids
        self.ctx = alignment.Context(tool, local_ids)
        self._sets: dict = {}

    def _get(self, key: str, fn: Callable):
        if key not in self._sets:
            self._sets[key] = fn()
        return self._sets[key]

    def resolve(self, ident: str) -> tuple[str, dict | None, str | None]:
        """(kind, record, nothing): the kind the resolver used, the record (None when it does not resolve), and, when
        the project declares no record of that kind, what it declares none of."""
        t, ids = self.tool, self.local_ids
        if COMPONENT_ID.fullmatch(ident):
            found = self._get("component", lambda: {c["id"]: c for c in components.load(t, ids)})
            return "component", found.get(ident), None if found else "components"
        if INCREMENT_ID.fullmatch(ident):
            found = self._get("increment", lambda: {r["id"]: r for r in roadmap.load(t, ids)})
            return "increment", found.get(ident), None if found else "increments"
        if FLOW_ID.fullmatch(ident):
            found = self._get("flow", lambda: {f["id"]: f for f in flows.load(t, ids)})
            return "flow", found.get(ident), None if found else "flows"
        if ident.startswith(ALIGNMENT):
            found = self._get("alignment", lambda: alignment.load(t, ids, audience=declared.portal_audience(t)))
            return "alignment", found.get(ident[len(ALIGNMENT):]), None if found else "alignment records"
        return "decision", ({} if self.ctx.decision_id(ident) else None), None


def _citation_problem(records: _Records, ident: str, status: str | None) -> str | None:
    """Why a citation is refused, or None."""
    kind, record, nothing = records.resolve(ident)
    if record is None:
        return f"[[{ident}]] does not resolve" + (f": the project declares no {nothing}" if nothing else "")
    if status is None:
        return None
    cite = f"[[{ident}|{status}]]"
    if status not in STATUSES:
        return f"{cite}: {status} is not a status ({', '.join(STATUSES)})"
    if kind == "flow":
        if status != "built":
            return f"{cite}: a flow is built or not; only |built applies"
        if not record["built"]:
            return f"{cite} says built; {ident} is not built"
        return None
    if kind in ("decision", "alignment"):
        return f"{cite}: only components, increments and flows carry a status"
    if record["status"] != status:
        return f"{cite} says {status}; {ident} is {record['status']}"
    return None


# --- checking ------------------------------------------------------------------------------------------------------

class _Where:
    """How an error names its place: the page file on the directory route, load_pages on the loader route."""

    def __init__(self, files: list[str] | None):
        self.files = files

    def key(self, i: int, key: str) -> str:
        return f"{self.files[i]}: {key}" if self.files else f"load_pages: pages[{i}].{key}"

    def line(self, i: int) -> str:
        return self.files[i] if self.files else f"load_pages: pages[{i}].body"


def check(where: _Where, pages: list[dict], offsets: list[int], tool: str, local_ids) -> None:
    """The checks after the schema, in order; the first failure raises. `offsets[i]` is the number of file lines
    before page i's body (0 on the loader route), so a citation's line is the line in the file."""
    def bad(i: int, key: str, why: str):
        raise InputError(f"{where.key(i, key)}: {why}")

    seen: set = set()
    for i, p in enumerate(pages):
        if p["id"] in seen:
            bad(i, "id", f"page id {p['id']} is not unique")
        seen.add(p["id"])
    first = None
    for i, p in enumerate(pages):
        if p["kind"] == "overview":
            if first is not None:
                bad(i, "kind", f"only one page may be the overview; {pages[first]['id']} already is")
            first = i
    records = _Records(tool, local_ids)
    for i, p in enumerate(pages):
        for line, _start, _end, ident, status in _citations(p["body"]):
            why = _citation_problem(records, ident, status)
            if why:
                raise InputError(f"{where.line(i)}: line {line + offsets[i]}: {why}")


def _read_page(directory: str, f: Path) -> tuple[dict, int]:
    """One page file as (page, lines before the body). Front matter problems raise."""
    where = f"{directory}/{f.name}"
    try:
        text = f.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise InputError(f"{where}: (record): cannot be read") from None
    lines = text.split("\n")
    close = next((k for k in range(1, len(lines)) if lines[k].rstrip("\r") == "---"), None)
    if lines[0].rstrip("\r") != "---" or close is None:
        raise InputError(f"{where}: (record): {FRONT_WHY}")
    try:
        front = yaml.safe_load("\n".join(lines[1:close]))
    except yaml.YAMLError:
        raise InputError(f"{where}: (record): not valid YAML") from None
    if not isinstance(front, dict):
        raise InputError(f"{where}: (record): front matter must be a map")
    extra = sorted(str(k) for k in front if k not in FRONT_KEYS)
    if extra:
        raise InputError(f"{where}: {extra[0]}: unknown key")
    page = {"id": f.stem, **front, "body": "\n".join(lines[close + 1:])}
    return page, close + 1


def _loader_function(tool: str) -> Callable | None:
    if "loader" not in project.CONFIG:
        return None
    return getattr(project.loader(tool), "load_pages", None)


def declared_route(tool: str) -> bool:
    """True when the project declares `files.pages` or a loader `load_pages`."""
    return declared.pages_dir(tool) is not None or _loader_function(tool) is not None


def _dotted(path: list, files: list[str] | None) -> str:
    """The schema's path as a key: `title` on a file, `pages[i].title` in a loader's list."""
    rest = [str(p) for p in path[2:]]
    if files is not None:
        return ".".join(rest) or "(record)"
    head = f"pages[{path[1]}]" if len(path) > 1 else "pages"
    return ".".join([head, *rest])


def load(tool: str, local_ids) -> tuple[dict, ...]:
    """The pages in file (sorted) or list order, validated. Empty when the project declares neither `files.pages`
    nor a loader `load_pages`."""
    directory = declared.pages_dir(tool)
    fn = _loader_function(tool)
    if directory is not None and fn is not None:
        declared._bad("files.pages", "is declared, and the loader also defines load_pages; use one route")
    if directory is None and fn is None:
        return ()
    pages: list[dict] = []
    offsets: list[int] = []
    files: list[str] | None = None
    if directory is not None:
        base = project.ROOT / directory
        if not base.is_dir():
            raise InputError(f"{directory}: (record): is not a directory")
        files = []
        for f in sorted(f for f in base.glob("*.md") if f.is_file()):
            page, offset = _read_page(directory, f)
            err = _first_error({"pages": [page]})
            if err:
                raise InputError(f"{directory}/{f.name}: {_dotted(err[0], files)}: {err[1]}")
            pages.append(page)
            offsets.append(offset)
            files.append(f"{directory}/{f.name}")
        if not pages:
            raise InputError(f"{directory}: (record): must list at least one page")
    else:
        pages = fn(project.ROOT)
        if not isinstance(pages, list):
            raise InputError("load_pages must return a list of pages")
        err = _first_error({"pages": pages})
        if err:
            raise InputError(f"load_pages: {_dotted(err[0], None)}: {err[1]}")
        offsets = [0] * len(pages)
    check(_Where(files), pages, offsets, tool, local_ids)
    return tuple(pages)


# --- rendering -----------------------------------------------------------------------------------------------------

STATUS_LABEL = {"measured": "Measured", "built": "Built", "accepted": "Accepted", "proposed": "Proposed"}
CSS = """
.cite{white-space:nowrap}
.prose-measured{background:var(--m-bg);color:var(--m-fg)}
.prose-built{background:var(--b-bg);color:var(--b-fg)}
.prose-accepted{background:var(--a-bg);color:var(--a-fg)}
.prose-proposed{background:var(--p-bg);color:var(--p-fg)}
nav.prose ul{padding-left:1.2em}
""".strip()


def _markdown():
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        raise InputError("markdown-it-py is not installed: pip install markdown-it-py==4.0.0") from None
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    md.renderer.rules["table_open"] = lambda t, i, o, e: '<div class="scroll"><table>\n'
    md.renderer.rules["table_close"] = lambda t, i, o, e: "</table></div>\n"
    return md


def _kind_of(ident: str) -> str:
    """The kind the resolver uses for an ident, and the name `href` receives for it."""
    if COMPONENT_ID.fullmatch(ident):
        return "component"
    if INCREMENT_ID.fullmatch(ident):
        return "increment"
    if FLOW_ID.fullmatch(ident):
        return "flow"
    return "alignment" if ident.startswith(ALIGNMENT) else "decision"


def _body_html(md, body: str, href) -> str:
    """The body as HTML. Each citation becomes a private-use placeholder before markdown and a link (or code) after,
    so it survives emphasis and table cells and a `|` in it cannot split a cell."""
    found = _citations(body)
    lines = body.split("\n")
    for k, (n, start, end, _ident, _status) in reversed(list(enumerate(found))):
        lines[n - 1] = f"{lines[n - 1][:start]}\ue000{k}\ue001{lines[n - 1][end:]}"
    out = md.render("\n".join(lines))

    def cite(m):
        k = int(m.group(1))
        if k >= len(found):
            return m.group(0)
        ident, status = found[k][3], found[k][4]
        kind = _kind_of(ident)
        target = href(kind, ident[len(ALIGNMENT):] if kind == "alignment" else ident)
        if target is not None:
            text = f'<a class="cite" href="{_esc(target)}" data-cite="{_esc(ident)}">{_esc(ident)}</a>'
        else:
            text = f'<code class="cite" data-cite="{_esc(ident)}">{_esc(ident)}</code>'
        if status in STATUS_LABEL:
            text += f' <span class="badge prose-{status}">{STATUS_LABEL[status]}</span>'
        return text

    return PLACEHOLDER.sub(cite, out)


def _ordered(pages) -> list[dict]:
    """The overview first, then the walkthroughs by (order, id); a missing order sorts after every number."""
    def key(p):
        return (p["kind"] != "overview", p.get("order") is None, p.get("order") or 0, p["id"])
    return sorted(pages, key=key)


def render(pages, href, prov: str = "", pre: str = "") -> tuple[list[str], list[str]]:
    """One section per page and the front page's nav items, in page order; both empty when there are no pages.
    `href(kind, ident)` returns the href of a cited record, or None; kind is decision, component, increment, flow or
    alignment, and ident is the cited id (the record name, without `alignment:`, for an alignment record). render_html
    wires it in. Render does not re-check resolution: load() did."""
    if not pages:
        return [], []
    md = _markdown()
    sections, items = [], []
    for p in _ordered(pages):
        pid, title = _esc(p["id"]), _esc(p["title"])
        sections.append(f'<section id="page-{pid}" class="page prose" data-page="{pid}" data-kind="{_esc(p["kind"])}">'
                        f'<h1>{_esc(pre)}{title}</h1><p><a href="#front">Front page</a></p>'
                        f'<div class="body">{_body_html(md, p["body"], href)}</div>{prov}</section>')
        items.append(f'<li><a href="#page-{pid}">{title}</a></li>')
    return sections, items


def nav(items: list[str]) -> str:
    if not items:
        return ""
    return f'<nav class="prose"><h2>Overview and walkthroughs</h2><ul>{"".join(items)}</ul></nav>'
