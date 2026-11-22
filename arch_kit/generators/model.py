"""The neutral records a view generator reads, and the connections and flow steps derived from them.

A consuming project's loader builds `Record`s (one per markdown record) and a `Connections` (the connection rows,
edges and flow steps read from the records' tables), then calls the generators in `views`. Nothing here reads a file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---- records ----------------------------------------------------------------------------------

@dataclass
class Table:
    heading: str
    section: str
    header: list
    rows: list


@dataclass
class Record:
    member: str
    path: str  # repo-relative
    rel: str  # relative to the records directory
    kind: str  # components flows alignment decisions readme roadmap other
    title: str
    rid: object  # str or None
    anchor: str = ""
    text: str = ""
    sections: list = field(default_factory=list)
    tables: list = field(default_factory=list)
    claims: list = field(default_factory=list)  # (heading, row, status cell, cells)
    gaps: list = field(default_factory=list)
    not_established: list = field(default_factory=list)
    exposure_misplaced: list = field(default_factory=list)  # line numbers
    front: dict = field(default_factory=dict)  # YAML front matter, {} when none or unusable
    front_error: str = ""  # why the front matter was unusable, "" when fine or absent
    href: str = ""  # a link target that replaces `<page>#<anchor>`; a consuming loader sets it

    @property
    def ref(self) -> str:
        return self.rid or self.rel

    @property
    def display_id(self) -> str:
        return f"{self.member}:{self.ref}"


def decision_status(rec: Record) -> str:
    for h, body in rec.sections:
        if h.casefold().startswith("status"):
            for ln in body:
                if ln.strip():
                    return ln.strip()
    return ""


def vocabulary_section(rec: Record):
    for key in ("status vocabulary", "vocabulary"):
        for h, body in rec.sections:
            if key in h.casefold():
                return f"## {h}\n" + "\n".join(body)
    return None


# ---- statuses, findings, members ---------------------------------------------------------------

STATUSES = ("measured", "built", "accepted", "proposed", "not built")


TICK = re.compile(r"`([^`]*)`")


TWO = "two statuses given"


NONE = "no status given"


@dataclass
class Finding:
    kind: str  # rule1 rule2 rule3 no-id path-refused front-matter diagram, or a caller's own code
    member: str
    ref: str
    detail: str


@dataclass
class Member:
    name: str
    commit: object  # 40-hex pin, or None for a member with no records yet
    records_path: object  # relative path, or None for a member with no records yet
    repo: str = ""
    cites: list = field(default_factory=list)  # names of members whose ids this member's records may cite bare
    census: object = None  # repo path of the member's census of decisions, or None
    checkout: object = None
    records: list = field(default_factory=list)
    refused: int = 0
    claims: list = field(default_factory=list)  # (record, heading, row, status | TWO | NONE)
    findings: list = field(default_factory=list)


    @property
    def has_records(self) -> bool:
        return self.commit is not None


def claim_statuses(cell: str) -> list:
    """Distinct status tokens in the cell, in order of appearance. A backticked `not built`
    is one token; it is never also counted as `built`."""
    out = []
    for t in TICK.findall(cell):
        t = t.strip().lower()
        if t in STATUSES and t not in out:
            out.append(t)
    return out


def claim_status(cell: str):
    """The one status, TWO when the cell gives several, NONE when it gives none."""
    hits = claim_statuses(cell)
    return hits[0] if len(hits) == 1 else (TWO if hits else NONE)


# ---- connections ------------------------------------------------------------------------------

# The finding kinds `build_edges` can raise. A caller that wants its own codes passes a map with the same keys.
DEFAULT_KINDS = {"no-status": "connections-no-status", "status": "connections-status",
                 "disagree": "connections-disagree", "direction": "connections-direction",
                 "outside": "connections-outside", "id": "connections-id", "columns": "connections-columns"}

# An id as the members write it: `CO-PT-LAKE`, optionally `member:` in front.
ID = re.compile(r"(?:([a-z0-9][a-z0-9-]*):)?([A-Z]{2,}(?:-[A-Z0-9]+)+)")


NO_STATUS = "no status given"


SOLID = ("built", "measured")


@dataclass
class Ref:
    kind: str  # rec | element | role | outside | unresolved
    key: tuple
    label: str
    rec: object = None  # the record, for kind rec
    member: str = ""  # the member the node belongs to, "" for a node that is no member's


@dataclass
class ConnRow:
    member: str
    rec: object  # the component record that writes the row
    row: int  # 1-based row in its table
    n: str  # the `#` cell, or the row number when the table has no `#`
    this: Ref
    other: Ref
    direction: str  # as written
    start: Ref
    end: Ref
    protocol: str = ""
    signin: str = ""
    passes: str = ""
    status: str = NO_STATUS
    evidence: str = ""
    has_status_column: bool = False
    protected: list | None = None  # Protections; None when the table has no Protected by column


@dataclass
class Edge:
    start: Ref
    end: Ref
    rows: list  # one ConnRow, or the two that merged
    n: int = 0  # the edge's number in the system views

    @property
    def merged(self) -> bool:
        return len(self.rows) == 2

    @property
    def solid(self) -> bool:
        return all(r.status in SOLID for r in self.rows)


@dataclass
class Protection:
    """One entry of a step's Protected by cell."""
    kind: str  # "id", "none", "not a point of use", "not written", "stated" (text as written, not classified)
    ref: object  # the resolved Ref for an id entry, else None
    text: str  # the id as written, or the condition after `none:`
    status: str = NO_STATUS


@dataclass
class StepRow:
    member: str
    rec: object
    row: int
    n: str
    actors: list  # Refs; "one of" when there are several
    targets: list  # Refs; empty when the target is `—`
    action: str
    passes: str = ""
    check: str = ""
    by: str = ""
    status: str = NO_STATUS
    evidence: str = ""
    has_status_column: bool = False
    protected: list | None = None  # Protections; None when the table has no Protected by column

    @property
    def solid(self) -> bool:
        return self.status in SOLID


@dataclass
class Flow:
    member: str
    rec: object
    steps: list

    @property
    def has_role(self) -> bool:
        return any(r.kind == "role" for s in self.steps for r in s.actors + s.targets)


@dataclass
class Connections:
    """The connection rows, edges and flows read from the records' tables, with the findings that reading raised."""
    rows: list = field(default_factory=list)  # ConnRow, in record and row order
    edges: list = field(default_factory=list)
    flows: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    resolver: object = None  # an object with link_ids(member, text, prefix), or None


def ident(rec):
    """A component's id: its front matter id when it has one, else the id in its title."""
    fid = rec.front.get("id")
    return fid if isinstance(fid, str) and fid else rec.rid


def plain(cell: str) -> str:
    return " ".join(cell.replace("`", "").split())


def build_edges(rows, out, kinds=None) -> list:
    """One edge per row, except that two rows merge when they come from the two records at the ends, start at the
    same part, end at the same part, and each side writes exactly one such row. Two merged rows that give different
    statuses raise a finding of kind `kinds["disagree"]`; `kinds` maps keys of `DEFAULT_KINDS` to a caller's own codes,
    and a key it leaves out keeps the default."""
    kind = {**DEFAULT_KINDS, **(kinds or {})}["disagree"]
    groups = {}
    for r in rows:
        groups.setdefault((r.start.key, r.end.key), []).append(r)
    edges, done = [], set()
    for r in rows:
        if id(r) in done:
            continue
        group = groups[(r.start.key, r.end.key)]
        mate = None
        if len(group) == 2 and r.start.rec is not None and r.end.rec is not None and r.start.rec is not r.end.rec:
            a, b = group
            if {id(a.rec), id(b.rec)} == {id(r.start.rec), id(r.end.rec)}:
                mate = b if a is r else a
        if mate is None:
            edges.append(Edge(r.start, r.end, [r]))
            done.add(id(r))
            continue
        pair = sorted((r, mate), key=lambda x: x.rec is not r.start.rec)  # the start side's row first
        edges.append(Edge(r.start, r.end, pair))
        done.update((id(r), id(mate)))
        if pair[0].status != pair[1].status:
            out.append(Finding(kind, pair[0].member, pair[0].rec.ref,
                                     f"merged connection: row {pair[0].row} and {pair[1].rec.ref} row {pair[1].row} "
                                     "give different statuses"))
    for n, e in enumerate(edges, 1):
        e.n = n
    return edges
