"""Generated views as markdown. Each emitter takes (ctx, view) and returns markdown, or "" when the records
give it nothing. Emitters read only the loaded records and the connection data derived from them, and name the
records they read through `ctx.use`."""
from __future__ import annotations

import posixpath
import re
from collections import Counter
from dataclasses import dataclass, field

from . import diagrams
from . import model
from .text import RECORDS_FROM_VIEW as VIEW_PREFIX
from .text import cell, fence, linked_paths, rec_link, rewrite_links, table

CORR_HEADER = ["#", "element", "what corresponds", "how closely", "status"]
CORR_HEADER_CAP = ["#", "element", "capability", "what corresponds", "how closely", "status"]
SECURITY_ROLES = "security roles"
SERVICE_ID = re.compile(r"^S\d+$")
DEPENDS = re.compile(r"\brows? (\d+)", re.I)
SOLID = ("measured", "built")
SECURITY_FLOWS = ("need-to-know", "source-to-use", "label-propagation")

# The sentence the browser check searches for; it opens the Resources Taxonomy view.
SEARCH_PHRASE = "One row per component record, with its claims counted by status"


@dataclass
class Ctx:
    members: list
    maps: dict  # member name -> {repo path: anchor}
    connections: object = None  # the Connections read from the connections and flow tables
    prefix: str = VIEW_PREFIX
    used: list = field(default_factory=list)  # (member, record) the running emitter read
    extra: list = field(default_factory=list)  # exception rows from connections and steps
    capabilities: dict = field(default_factory=dict)  # {capability id: title}, in the crosswalk's order
    cap_prefix: str = ""  # the prefix a Capability cell puts before an id: `<prefix>:<id>`
    cap_source: str = ""  # the title of the source the capabilities come from

    def start(self) -> None:
        self.used, self.extra = [], []

    def use(self, m, rec) -> None:
        if not any(r is rec for _m, r in self.used):
            self.used.append((m, rec))

    def member(self, name):
        return next(m for m in self.members if m.name == name)


GENERATORS: dict = {}


def generator(name):
    def deco(fn):
        GENERATORS[name] = fn
        return fn
    return deco


def clip(text: str, n: int = 160) -> str:
    return text if len(text) <= n else text[:n - 1] + "..."


def before_colon(text: str) -> str:
    return text.split(":", 1)[0].strip()


PLURALS = {"capability": "capabilities", "point of use": "points of use"}


def counted(n, noun) -> str:
    """`1 role`, `3 roles`: the noun takes its singular when the count is 1."""
    return f"{n} {noun if n == 1 else PLURALS.get(noun, noun + 's')}"


def pad(row, n):
    return (list(row) + [""] * n)[:max(n, len(row))]


def link(ctx, rec, label=None) -> str:
    return rec_link(rec, ctx.prefix, label)


def inl(ctx, text, rec, m) -> str:
    return cell(text, rec, ctx.maps[m.name], ctx.prefix)


# ---- alignment tables ------------------------------------------------------------------------

def capability_groups(ctx) -> list:
    """[(file name, [(member, record, rows)])]. Alignment records that share a file name form one group.
    Each row is [#, element, capability, what corresponds, how closely, status, ...]; the capability is None
    for a row from a table with no Capability column."""
    groups = {}
    for m in ctx.members:
        for r in m.records:
            if r.kind != "alignment":
                continue
            rows = []
            for t in r.tables:
                head = [h.casefold() for h in t.header]
                if head[:5] == CORR_HEADER:
                    rows += [row[:2] + [None] + row[2:] for row in (pad(x, 5) for x in t.rows)]
                elif head[:6] == CORR_HEADER_CAP:
                    rows += [pad(row, 6) for row in t.rows]
            if rows:
                groups.setdefault(posixpath.basename(r.rel), []).append((m, r, rows))
    return list(groups.items())


def alignment_groups(ctx) -> list:
    """[(file name, [(member, record, rows)])]. Alignment records that share a file name form one group.
    rows are the rows of the record's tables whose header starts with the correspondence header."""
    return [(name, [(m, r, [row[:2] + row[3:] for row in rows]) for m, r, rows in entries])
            for name, entries in capability_groups(ctx)]


def parse_capability(ctx, text) -> list:
    """[(kind, value)] for a Capability cell: known, none, unknown, or not written (the cell is None)."""
    if text is None:
        return [("not written", "")]
    out = []
    for part in model.plain(text).replace("`", "").split(","):
        part = part.strip()
        if not part:
            continue
        head, _, tail = part.partition(":")
        if part.casefold() == "none":
            out.append(("none", ""))
        elif ctx.cap_prefix and head == ctx.cap_prefix and tail in ctx.capabilities:
            out.append(("known", tail))
        else:
            out.append(("unknown", part))
    return out or [("not written", "")]


def capability_label(ctx, cid) -> str:
    return f"{cid} {ctx.capabilities[cid]}"


def keyed(entries) -> tuple:
    """Row ids in first-appearance order, and per entry index {id: row}."""
    order, per = [], []
    for _m, _r, rows in entries:
        d = {}
        for row in rows:
            rid = row[0].strip()
            d.setdefault(rid, row)
            if rid not in order:
                order.append(rid)
        per.append(d)
    return order, per


def group_title(entries) -> str:
    return " / ".join(f"{r.title or r.rel} ({m.name})" for m, r, _ in entries)


@generator("overview")
def overview(ctx, v) -> str:
    out = []
    for m in ctx.members:
        recs = [r for r in m.records if r.rel.casefold() == "overview.md"]
        recs += [r for r in m.records if r.rel.startswith("walkthroughs/")]
        if not recs:
            continue
        for r in recs:
            ctx.use(m, r)
        items = "".join(f"- {link(ctx, r, r.title or r.rel)}\n" for r in recs)
        out.append(f"### {m.name}\n\n{items}")
    return "\n".join(out)


@generator("traceability")
def traceability(ctx, v) -> str:
    decisions = [(m, r) for m in ctx.members for r in m.records if r.kind == "decisions" and r.rid]
    if not decisions:
        return ""
    cited = {(m.name, r.path): [] for m, r in decisions}
    for m in ctx.members:
        for r in m.records:
            for p in linked_paths(r):
                if (m.name, p) in cited:
                    cited[(m.name, p)].append((m, r))
    n_cited = sum(1 for lst in cited.values() if lst)
    rows = []
    for m, r in decisions:
        ctx.use(m, r)
        by = cited[(m.name, r.path)]
        for bm, br in by:
            ctx.use(bm, br)
        text = ", ".join(link(ctx, x) for _m, x in by) if by else "cited by no record"
        rows.append([cell(r.display_id), cell(r.title), cell(m.name), inl(ctx, model.decision_status(r), r, m), text])
    top = (f"{len(decisions)} decisions: {n_cited} cited by at least one record, "
           f"{len(decisions) - n_cited} cited by no record.\n\n")
    return top + table(["Id", "Title", "Member", "Status", "Cited by"], rows)


@generator("correspondence")
def correspondence(ctx, v) -> str:
    out = []
    for _name, entries in capability_groups(ctx):
        for m, r, _ in entries:
            ctx.use(m, r)
        order, per = keyed(entries)
        if len(entries) == 1:
            m, r, _rows = entries[0]
            rows = [[cell(i), inl(ctx, before_colon(per[0][i][1]), r, m),
                     inl(ctx, capability_text(ctx, per[0][i][2]), r, m), inl(ctx, clip(per[0][i][3]), r, m),
                     inl(ctx, per[0][i][4], r, m), inl(ctx, per[0][i][5], r, m)] for i in order]
            out.append(f"### {group_title(entries)}\n\n"
                       + table(["Id", "Element", "Capability", "What corresponds", "How closely", "Status"], rows))
            continue
        head = ["Id", "Element", "Capability"]
        for m, _r, _ in entries:
            head += [f"{m.name}: What corresponds", f"{m.name}: How closely", f"{m.name}: Status"]
        rows = []
        for i in order:
            first = next((k for k, d in enumerate(per) if i in d), 0)
            fm, fr, _ = entries[first]
            caps = [capability_text(ctx, d[i][2]) for d in per if i in d]
            cells = [cell(i), inl(ctx, before_colon(per[first][i][1]), fr, fm),
                     inl(ctx, " / ".join(dict.fromkeys(c for c in caps if c)), fr, fm)]
            for (m, r, _rows), d in zip(entries, per):
                row = d.get(i)
                cells += ([inl(ctx, clip(row[3]), r, m), inl(ctx, row[4], r, m), inl(ctx, row[5], r, m)]
                          if row else ["", "", ""])
            rows.append(cells)
        out.append(f"### {group_title(entries)}\n\n" + table(head, rows))
    return "\n".join(out)


@generator("services")
def services(ctx, v) -> str:
    out = []
    for _name, entries in alignment_groups(ctx):
        order, per = keyed(entries)
        ids = [i for i in order if SERVICE_ID.match(i)]
        if not ids:
            continue
        for m, r, _ in entries:
            ctx.use(m, r)
        items = []
        for i in ids:
            first = next(k for k, d in enumerate(per) if i in d)
            fm, fr, _ = entries[first]
            name = inl(ctx, before_colon(per[first][i][1]), fr, fm)
            who = []
            for (m, r, _rows), d in zip(entries, per):
                row = d.get(i)
                if row:
                    who.append(f"{m.name}: {inl(ctx, row[3], r, m)}, {inl(ctx, row[4], r, m)}")
            items.append(f"- **{i}** {name} ({'; '.join(who)})\n")
        out.append(f"### {group_title(entries)}\n\n{''.join(items)}")
    return "\n".join(out)


def capability_text(ctx, text, blank="") -> str:
    """The labels a Capability cell names, joined with `; `. `blank` stands for a cell that was not written."""
    out = []
    for kind, value in parse_capability(ctx, text):
        out.append(capability_label(ctx, value) if kind == "known" else "none" if kind == "none"
                   else f"{value} (unknown)" if kind == "unknown" else blank)
    return "; ".join(dict.fromkeys(out))


def by_entry(items) -> str:
    """`<member> <file>: <ids>` for each member and file in `items` [(member, file, id)], joined with `; `."""
    found = {}
    for member, name, rid in items:
        found.setdefault((member, name), []).append(rid)
    return "; ".join(f"{member} {name}: {', '.join(ids)}" for (member, name), ids in found.items())


@generator("strategic-taxonomy")
def strategic_taxonomy(ctx, v) -> str:
    groups = capability_groups(ctx)
    if not ctx.capabilities or not any(
            row[2] is not None for _n, es in groups for _m, _r, rows in es for row in rows):
        return ""
    named = {c: [] for c in ctx.capabilities}
    none, unwritten, unknown = [], [], []
    for name, entries in groups:
        for m, r, rows in entries:
            ctx.use(m, r)
            for row in rows:
                rid = row[0].strip()
                for kind, value in dict.fromkeys(parse_capability(ctx, row[2])):
                    if kind == "known":
                        named[value].append((m.name, name, rid))
                    elif kind == "none":
                        none.append((m.name, name, rid))
                    elif kind == "not written":
                        unwritten.append((m.name, name, rid))
                    else:
                        unknown.append((value, m.name, name, rid))
    rows = []
    for cid, title in ctx.capabilities.items():
        items = named[cid]
        rows.append([cell(cid), cell(title), str(len(items)),
                     cell(by_entry(items)) if items else "named by no row",
                     cell(", ".join(dict.fromkeys(i[0] for i in items)))])
    out = [f"The {counted(len(ctx.capabilities), 'capability')} of {ctx.cap_source}, with the alignment rows "
           "that name each.\n\n" + table(["Capability", "Title", "Rows", "Named by", "Members"], rows)]
    bullets = []
    if none:
        bullets.append(f"- **none**: {counted(len(none), 'row')} ({by_entry(none)})")
    if unwritten:
        where = "; ".join(f"{m} {n}" for m, n in dict.fromkeys((i[0], i[1]) for i in unwritten))
        bullets.append(f"- **not written**: {counted(len(unwritten), 'row')} in tables with no Capability column "
                       f"({where})")
    bullets += [f"- **unknown**: {value} in {m} {n} row {rid}" for value, m, n, rid in unknown]
    if bullets:
        out.append("#### Not placed\n\n" + "\n".join(bullets) + "\n")
    return "\n".join(out)


@generator("services-traceability")
def services_traceability(ctx, v) -> str:
    rows, kinds, by_cap = [], [], {c: [] for c in ctx.capabilities}
    for _name, entries in capability_groups(ctx):
        order, per = keyed(entries)
        for i in (i for i in order if SERVICE_ID.match(i)):
            seen = set()
            for (m, r, _rows), d in zip(entries, per):
                row = d.get(i)
                if not row:
                    continue
                ctx.use(m, r)
                found = parse_capability(ctx, row[2])
                seen |= {k for k, _ in found}
                for kind, value in found:
                    if kind == "known" and i not in by_cap[value]:
                        by_cap[value].append(i)
                rows.append([cell(i), inl(ctx, before_colon(row[1]), r, m),
                             inl(ctx, capability_text(ctx, row[2], "not written"), r, m), cell(m.name),
                             inl(ctx, row[4], r, m), inl(ctx, row[5], r, m)])
            kinds.append("named" if seen & {"known", "unknown"} else "none" if "none" in seen else "unwritten")
    if not rows:
        return ""
    head = (f"{counted(len(kinds), 'service')}: {kinds.count('named')} name a capability, "
            f"{kinds.count('none')} name none, {kinds.count('unwritten')} have no Capability column.")
    bullets = [f"- **{capability_label(ctx, c)}**: {', '.join(ids)}" for c, ids in by_cap.items() if ids]
    return (head + "\n\n"
            + table(["Service", "Name", "Capabilities", "Member", "How closely", "Status"], rows)
            + ("\n#### By capability\n\n" + "\n".join(bullets) + "\n" if bullets else ""))


@generator("standards")
def standards(ctx, v) -> str:
    rows = []
    for m in ctx.members:
        for r in m.records:
            if r.kind == "alignment" and r.tables:
                for row in r.tables[0].rows:
                    if row and row[0].strip().casefold() in ("name", "edition"):
                        rest = "; ".join(c for c in row[1:] if c.strip())
                        ctx.use(m, r)
                        rows.append([cell(m.name), link(ctx, r, r.title or r.rel), cell(row[0].strip()),
                                     inl(ctx, rest, r, m)])
    out = []
    if rows:
        out.append("### Standards the alignment records name\n\n" + table(["Member", "Record", "Field", "Value"], rows))
    rows_ = list(ctx.connections.rows) if ctx.connections else []
    used = Counter(" ".join(x.protocol.replace("`", "").split()) for x in rows_ if x.protocol.strip())
    for x in rows_:
        if x.protocol.strip():
            ctx.use(ctx.member(x.member), x.rec)
    out.append("### Protocols used\n\n")
    if used:
        out.append(table(["Protocol", "Uses"], [[cell(p), str(n)] for p, n in sorted(used.items())]))
    else:
        out.append("none written yet\n")
    return "\n".join(out)


# ---- roadmap ---------------------------------------------------------------------------------

def roadmap_data(rec):
    """(table, row ids, edges, depend-on matches) for the record's first `# | increment` table, or None.
    An edge (a, b) runs from the depended-on row a to the row b that depends on it."""
    for t in rec.tables:
        if len(t.header) >= 2 and t.header[0].strip() == "#" and t.header[1].strip().casefold().startswith("increment"):
            rows = [pad(r, len(t.header)) for r in t.rows]
            ids = [r[0].strip() for r in rows]
            col = next((k for k, h in enumerate(t.header) if h.strip().casefold().startswith("depends")), None)
            edges, matches = [], 0
            if col is not None:
                for r in rows:
                    for mt in DEPENDS.finditer(r[col]):
                        matches += 1
                        if mt.group(1) in ids:
                            e = (mt.group(1), r[0].strip())
                            if e not in edges:
                                edges.append(e)
            return t, rows, ids, edges, matches
    return None


@generator("roadmap")
def roadmap(ctx, v) -> str:
    out = []
    for m in ctx.members:
        for r in m.records:
            if r.kind != "roadmap":
                continue
            data = roadmap_data(r)
            if data is None:
                continue
            t, rows, ids, edges, matches = data
            ctx.use(m, r)
            body = table([cell(h) for h in t.header], [[inl(ctx, c, r, m) for c in row] for row in rows])
            out.append(f"### {r.display_id} {r.title}\n\n{len(edges)} of {matches} depend-ons resolve to a row\n\n"
                       + body + "\n" + fence("mermaid", diagrams.roadmap_source(rows, ids, edges)))
    return "\n".join(out)


# ---- resources -------------------------------------------------------------------------------

@generator("resources")
def resources(ctx, v) -> str:
    cols = list(model.STATUSES) + [model.TWO, model.NONE]
    out = []
    for m in ctx.members:
        recs = [r for r in m.records if r.kind == "components"]
        if not recs:
            continue
        rows = []
        for r in recs:
            ctx.use(m, r)
            c = Counter(st for rec, _h, _row, st in m.claims if rec is r)
            rows.append([cell(model.ident(r) or r.rel), cell(r.title)] + [str(c[s]) for s in cols]
                        + [link(ctx, r, "record")])
        out.append(f"### {m.name}\n\n" + table(["Id", "Title"] + cols + ["Record"], rows))
    if not out:
        return ""
    return SEARCH_PHRASE + ".\n\n" + "\n".join(out)


# ---- connection diagrams ---------------------------------------------------------------------------

NOT_GROUPED = "Not grouped by plane: no record declares a plane yet."
NO_STEP_TARGET = "—"


def edges_of(ctx) -> list:
    return ctx.connections.edges if ctx.connections else []


def use_edges(ctx) -> None:
    for e in edges_of(ctx):
        for r in e.rows:
            ctx.use(ctx.member(r.member), r.rec)
        if not e.solid:
            st = " / ".join(dict.fromkeys(r.status for r in e.rows))
            ctx.extra.append([cell(e.rows[0].rec.display_id), cell(f"connection {e.n} to {e.end.label}"), cell(st)])


def ref_cell(ctx, ref) -> str:
    """An end as a table cell: a part links to its record on the records page."""
    if ref.kind == "rec":
        return rec_link(ref.rec, ctx.prefix, ref.label)
    return cell(ref.label)


def ends_cell(ctx, refs) -> str:
    return "; ".join(ref_cell(ctx, r) for r in refs) if refs else NO_STEP_TARGET


def tcell(ctx, text, rec) -> str:
    """A table cell of a record's text: its links to other records rewritten, and each bare id that resolves to a
    record linked. Links, code spans and the pipes of the cell are left as they are."""
    text = " ".join(str(text or "").split())
    base = posixpath.dirname(rec.path)
    text = rewrite_links(text, base, ctx.maps.get(rec.member, {}), ctx.prefix)
    res = ctx.connections.resolver if ctx.connections else None
    if res is not None:
        text = res.link_ids(rec.member, text, ctx.prefix)
    return re.sub(r"(?<!\\)\|", r"\\|", text)


def joined_cell(ctx, rows, field) -> str:
    """The distinct values of one field over the rows of an edge, joined with ` / `."""
    out = {}
    for r in rows:
        v = " ".join(str(getattr(r, field)).split())
        if v and v not in out:
            out[v] = r
    return " / ".join(tcell(ctx, v, r.rec) for v, r in out.items())


def records_of(ctx, rows) -> str:
    out = []
    for r in rows:
        link_ = rec_link(r.rec, ctx.prefix)
        if link_ not in out:
            out.append(link_)
    return "; ".join(out)


@generator("structure")
def structure(ctx, v) -> str:
    edges = edges_of(ctx)
    if not edges:
        return ""
    use_edges(ctx)
    seen, rows = set(), []
    for e in edges:
        for ref in (e.start, e.end):
            if ref.key in seen:
                continue
            seen.add(ref.key)
            kind = {"rec": "part", "role": "role", "element": "outside element", "outside": "outside system",
                    "unresolved": "id found in no record"}[ref.kind]
            rows.append([ref_cell(ctx, ref), cell(ref.member), kind, rec_link(ref.rec, ctx.prefix) if ref.rec else ""])
    return (NOT_GROUPED + "\n\n" + fence("mermaid", diagrams.graph_source(edges, False)) + "\n"
            + table(["Part", "Member", "Kind", "Record"], rows))


@generator("connectivity")
def connectivity(ctx, v) -> str:
    edges = edges_of(ctx)
    if not edges:
        return ""
    use_edges(ctx)
    rows = []
    for e in edges:
        rs = e.rows
        rows.append([str(e.n), ref_cell(ctx, e.start), ref_cell(ctx, e.end), joined_cell(ctx, rs, "direction"),
                     joined_cell(ctx, rs, "protocol"), joined_cell(ctx, rs, "signin"), joined_cell(ctx, rs, "passes"),
                     cell(" / ".join(dict.fromkeys(r.status for r in rs))), joined_cell(ctx, rs, "evidence"),
                     records_of(ctx, rs)])
    return (fence("mermaid", diagrams.graph_source(edges, True)) + "\n"
            + table(["n", "From", "To", "Direction", "Protocol", "Sign-in", "What passes", "Status", "Evidence",
                     "Record"], rows))


def flow_section(ctx, flow) -> str:
    ctx.use(ctx.member(flow.member), flow.rec)
    rows = []
    for s in flow.steps:
        if not s.solid:
            ctx.extra.append([cell(flow.rec.display_id), cell(f"step {s.n}"), cell(s.status)])
        rows.append([cell(s.n), ends_cell(ctx, s.actors), tcell(ctx, s.action, flow.rec), ends_cell(ctx, s.targets),
                     tcell(ctx, s.passes, flow.rec), tcell(ctx, s.check, flow.rec), tcell(ctx, s.by, flow.rec),
                     cell(s.status), tcell(ctx, s.evidence, flow.rec)])
    return (f"### {flow.rec.display_id} {flow.rec.title}\n\n"
            + fence("mermaid", diagrams.sequence_source(flow)) + "\n"
            + table(["n", "Actor", "Action", "Target", "What passes", "Check or decision", "Decided by",
                     "Status", "Evidence"], rows))


def sequences(ctx, v, roles) -> str:
    out = []
    for flow in ctx.connections.flows if ctx.connections else []:
        if flow.has_role != roles:
            continue
        out.append(flow_section(ctx, flow))
    return "\n".join(out)


@generator("sequences-parts")
def sequences_parts(ctx, v) -> str:
    return sequences(ctx, v, False)


@generator("sequences-roles")
def sequences_roles(ctx, v) -> str:
    return sequences(ctx, v, True)


# ---- security views --------------------------------------------------------------------------

SIGNIN_CLASSES = ("no sign-in", "not established", "not written", "stated")
IN_PROCESS_PROTOCOLS = ("in-process", "in process", "environment variable", "python logging")
IN_PROCESS_CLASS = "inside one process"


def in_process(rows) -> bool:
    """True when every row's protocol names a call inside one process; an empty protocol makes it false."""
    for r in rows:
        v = " ".join(model.plain(r.protocol).casefold().split())
        if not v or not any(w in v for w in IN_PROCESS_PROTOCOLS):
            return False
    return True


def signin_class(rows) -> str:
    found = []
    for r in rows:
        v = model.plain(r.signin).casefold()
        if v == "not established":
            found.append("not established")
        elif v == "none" or re.match(r"none(?![a-z])", v):
            found.append("no sign-in")
        elif not v:
            found.append("not written")
        else:
            found.append("stated")
    return min(found, key=SIGNIN_CLASSES.index)


@generator("security-connectivity")
def security_connectivity(ctx, v) -> str:
    edges = edges_of(ctx)
    if not edges:
        return ""
    use_edges(ctx)
    classes = [IN_PROCESS_CLASS if in_process(e.rows) else signin_class(e.rows) for e in edges]
    n = Counter(classes)
    n_in = n[IN_PROCESS_CLASS]
    carried = any(r.protected is not None for e in edges for r in e.rows)
    tail = (f"{n['no sign-in']} with no sign-in, {n['not established']} with sign-in "
            f"not established, {n['not written']} with sign-in not written, {n['stated']} with a sign-in stated.")
    if n_in:
        head = (f"{counted(len(edges), 'connection')}: {n_in} inside one process, where a sign-in does not apply; "
                f"of the other {len(edges) - n_in}, " + tail)
    else:
        head = f"{counted(len(edges), 'connection')}: " + tail
    gaps = [f"- **{c}**: connection {e.n}, {ref_cell(ctx, e.start)} to {ref_cell(ctx, e.end)}"
            for c in SIGNIN_CLASSES[:3] for e, k in zip(edges, classes) if k == c]
    if carried:
        head += " " + connection_protection_sentence(edges)
        for e in edges:
            for r in e.rows:
                for en in r.protected or []:
                    if en.kind == "none":
                        gaps.append(f"- **unprotected**: connection {e.n}, {ref_cell(ctx, e.start)} to "
                                    f"{ref_cell(ctx, e.end)}: none: {en.text} (`{en.status}`)")
        gaps += [f"- **Protected by not written**: connection {e.n}, {ref_cell(ctx, e.start)} to "
                 f"{ref_cell(ctx, e.end)}" for e in edges if connection_not_written(e)]
    rows = []
    for e, k in zip(edges, classes):
        rs = e.rows
        signin = joined_cell(ctx, rs, "signin")
        if k not in ("stated", IN_PROCESS_CLASS):
            signin = f"**gap:** {k}" + (f" {signin}" if signin else "")
        prot = [" / ".join(connection_protection_cell(ctx, r) for r in rs)] if carried else []
        rows.append([str(e.n), ref_cell(ctx, e.start), ref_cell(ctx, e.end), joined_cell(ctx, rs, "direction"),
                     joined_cell(ctx, rs, "protocol"), signin, *prot, joined_cell(ctx, rs, "passes"),
                     cell(" / ".join(dict.fromkeys(r.status for r in rs))), joined_cell(ctx, rs, "evidence"),
                     records_of(ctx, rs)])
    inside = ""
    if n_in:
        nums = ", ".join(str(e.n) for e, c in sorted(zip(edges, classes), key=lambda p: p[0].n)
                         if c == IN_PROCESS_CLASS)
        inside = (f"#### Inside one process\n\nConnections {nums}: the caller and the callee share a process, so the "
                  "table shows their sign-in as written and marks no gap.\n\n")
    return (head + "\n\n#### Gaps\n\n"
            + ("\n".join(gaps) + "\n" if gaps else "No connection is without a stated sign-in.\n") + "\n"
            + inside
            + table(["n", "From", "To", "Direction", "Protocol", "Sign-in", *(["Protected by"] if carried else []),
                     "What passes", "Status", "Evidence", "Record"], rows))


def connection_is_point_of_use(edge) -> bool:
    return any(r.protected is not None and [e.kind for e in r.protected] != ["not a point of use"]
               for r in edge.rows)


def connection_not_written(edge) -> bool:
    return any(r.protected and r.protected[0].kind == "not written" for r in edge.rows)


def connection_protection_sentence(edges) -> str:
    uses = [e for e in edges if connection_is_point_of_use(e)]
    kinds = [{edge_protection_kind(e, en) for r in e.rows for en in r.protected or [] if en.kind in ("id", "none")}
             for e in uses]
    a, b, c = (sum(1 for k in kinds if w in k) for w in ("component", "own", "none"))
    d = sum(1 for e in uses if connection_not_written(e))
    s = sum(1 for e in uses if any(en.kind == "stated" for r in e.rows for en in r.protected or []))
    stated = f"{s} stated, not classified, " if s else ""
    one = len(uses) == 1
    return (f"Protected by: {len(uses)} {'connection is a point' if one else 'connections are points'} of use: "
            f"{a} enforced by another component, {b} by the target itself, {c} with a written none, "
            f"{stated}{d} not written.")


def connection_protection_cell(ctx, row) -> str:
    if row.protected is None:
        return ""
    if [e.kind for e in row.protected] == ["not a point of use"]:
        return "—"
    return "; ".join(entry_cell(ctx, e) for e in row.protected)


def security_role_tables(ctx) -> list:
    """[(member, record, table)] for the tables under a security roles heading in an alignment record."""
    out = []
    for m in ctx.members:
        for r in m.records:
            if r.kind != "alignment":
                continue
            for t in r.tables:
                head = [h.casefold() for h in t.header]
                if SECURITY_ROLES in (t.heading or "").casefold() and (
                        head[:5] == CORR_HEADER or head[:6] == CORR_HEADER_CAP):
                    out.append((m, r, t))
    return out


def first_word(text) -> str:
    found = re.search(r"`([^`]*)`", text)
    return " ".join((found.group(1) if found else model.plain(text).split(" ")[0]).split()).casefold()


def security_flows(ctx) -> list:
    return [f for f in (ctx.connections.flows if ctx.connections else [])
            if posixpath.basename(f.rec.rel).removesuffix(".md") in SECURITY_FLOWS]


def protection_kind(step, entry) -> str:
    """`none`, `own` (the id is one of the step's targets: the target itself enforces access; a tool's own
    role-based access is the common case) or `component`."""
    if entry.kind == "none":
        return "none"
    if entry.ref is not None and any(entry.ref.key == t.key for t in step.targets):
        return "own"
    return "component"


def edge_protection_kind(edge, entry) -> str:
    """The same three kinds for a connection: the end of an edge is the party called or read, so an id that is
    that party is `own`."""
    if entry.kind == "none":
        return "none"
    if entry.ref is not None and entry.ref.key == edge.end.key:
        return "own"
    return "component"


def entry_cell(ctx, entry) -> str:
    status = f" `{entry.status}`"
    if entry.kind == "none":
        return f"**gap:** none: {cell(entry.text)}{status}"
    if entry.kind == "not written":
        return "**not written**"
    return (ref_cell(ctx, entry.ref) if entry.ref is not None else cell(entry.text)) + status


def protection_cell(ctx, step) -> str:
    return "; ".join(entry_cell(ctx, e) for e in step.protected or [])


def is_point_of_use(step) -> bool:
    return step.protected is not None and [e.kind for e in step.protected] != ["not a point of use"]


@generator("security-structure")
def security_structure(ctx, v) -> str:
    out = []
    for m, r, t in security_role_tables(ctx):
        ctx.use(m, r)
        cap = [h.casefold() for h in t.header][:6] == CORR_HEADER_CAP
        rows = []
        for row in t.rows:
            row = pad(row, 7 if cap else 6)
            if not cap:
                row = row[:2] + [""] + row[2:]
            rows.append(row)
        words = [first_word(row[4]) for row in rows]
        counts = Counter(words)
        names = [w for w in ("close", "partial", "different", "none") if counts[w]]
        names += [w for w in counts if w not in names]
        sentence = f"{counted(len(rows), 'role')}: " + ", ".join(f"{counts[w]} {w}" for w in names) + "."
        gaps = []
        for row, w in zip(rows, words):
            status = model.plain(row[5]).casefold()
            if w == "none" or status not in SOLID:
                gaps.append(f"- **{row[0].strip()}** {before_colon(row[1])}: how closely {w}; status {status}")
        body = [[cell(row[0]), inl(ctx, before_colon(row[1]), r, m), inl(ctx, row[2], r, m),
                 inl(ctx, clip(row[3]), r, m), inl(ctx, row[4], r, m), inl(ctx, row[5], r, m),
                 inl(ctx, row[6], r, m)] for row in rows]
        out.append(f"### {r.title or r.rel} ({m.name})\n\n{sentence}\n\n#### Gaps\n\n"
                   + ("\n".join(gaps) + "\n" if gaps else "No role is unmet.\n") + "\n"
                   + table(["Id", "Role", "Capability", "What corresponds", "How closely", "Status", "Evidence"], body))
    use = protection_section(ctx)
    if use:
        out.append(use)
    return "\n".join(out)


def protection_section(ctx) -> str:
    """Protection at each point of use, across the selected flows of every member."""
    uses = []  # (flow, step)
    flows = set()
    for flow in security_flows(ctx):
        for st in flow.steps:
            if is_point_of_use(st):
                uses.append((flow, st))
                flows.add(id(flow))
    if not uses:
        return ""
    for flow in security_flows(ctx):
        if id(flow) in flows:
            ctx.use(ctx.member(flow.member), flow.rec)
    kinds = [{protection_kind(st, e) for e in st.protected if e.kind in ("id", "none")} for _f, st in uses]
    a, b, c = (sum(1 for k in kinds if w in k) for w in ("component", "own", "none"))
    sentence = (f"{counted(len(uses), 'point of use')} in {counted(len(flows), 'flow')}: {a} enforced by another component, "
                f"{b} by the target itself, {c} with a written none.")
    ends = lambda refs: "; ".join(r.label for r in refs) if refs else NO_STEP_TARGET  # noqa: E731
    gaps = []
    for flow, st in uses:
        for e in st.protected:
            if e.kind == "none":
                gaps.append(f"- **{flow.rec.display_id} step {st.n}**, {ends(st.actors)} to {ends(st.targets)}: "
                            f"none: {e.text}")
    for flow, st in uses:
        if st.protected[0].kind == "not written":
            gaps.append(f"- **{flow.rec.display_id} step {st.n}**, {ends(st.actors)} to {ends(st.targets)}: "
                        "not written")
    rows = []
    for (flow, st), _k in zip(uses, kinds):
        cells = {"component": [], "own": [], "none": []}
        for e in st.protected:
            if e.kind == "not written":
                cells["none"].append("**not written**")
            else:
                cells[protection_kind(st, e)].append(entry_cell(ctx, e))
        rows.append([cell(flow.rec.display_id), cell(st.n), ends_cell(ctx, st.actors), ends_cell(ctx, st.targets),
                     "; ".join(cells["component"]), "; ".join(cells["own"]), "; ".join(cells["none"])])
    return ("### Protection at each point of use\n\n" + sentence + "\n\n#### Gaps\n\n"
            + ("\n".join(gaps) + "\n" if gaps else "Every point of use names what protects it.\n") + "\n"
            + table(["Flow", "Step", "From", "To", "Another component", "The target itself", "None"], rows))


@generator("security-processes")
def security_processes(ctx, v) -> str:
    out = []
    for flow in security_flows(ctx):
        has_col = any(st.protected is not None for st in flow.steps)
        gaps = []
        for st in flow.steps:
            for e in st.protected or []:
                if e.kind == "none":
                    others = [x for x in st.protected if x is not e]
                    also = ""
                    if others:
                        also = "; also " + "; ".join(entry_cell(ctx, x) for x in others)
                    gaps.append(f"- **step {st.n}, unprotected**: none: {e.text} (`{e.status}`){also}")
        for st in flow.steps:
            if st.protected and st.protected[0].kind == "not written":
                gaps.append(f"- **step {st.n}**: Protected by not written")
        gaps += [f"- **step {st.n}**: {st.status}" for st in flow.steps if not st.solid]
        text = "#### Gaps\n\n" + ("\n".join(gaps) + "\n" if gaps else "Every step is built or measured.\n") + "\n"
        if has_col:
            uses = [st for st in flow.steps if is_point_of_use(st)]
            text += "#### Points of use\n\n"
            if uses:
                text += table(["Step", "From", "To", "Protected by"],
                              [[cell(st.n), ends_cell(ctx, st.actors), ends_cell(ctx, st.targets),
                                protection_cell(ctx, st)] for st in uses])
            else:
                text += "No step is a point of use.\n"
        else:
            text += "#### Points of use\n\nThis flow's steps have no Protected by column.\n"
        out.append(text + "\n" + flow_section(ctx, flow))
    return "\n".join(out)
