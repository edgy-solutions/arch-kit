"""Mermaid sources for the diagram views. The emitters write them as ```mermaid fences; the kit renders them."""
from __future__ import annotations

import re


ESCAPES = {"#": "#35;", '"': "#quot;", "<": "#lt;", ">": "#gt;", ";": "#59;"}
SOLID = ("built", "measured")
CUT = 60


def mlabel(s) -> str:
    """A mermaid label: one pass, so the entity codes it writes are not themselves escaped."""
    return re.sub(r'[#"<>;]', lambda m: ESCAPES[m.group(0)], " ".join(str(s).split()))


# ---- sources ---------------------------------------------------------------------------------

def roadmap_source(rows, ids, edges) -> str:
    node = {}
    lines = ["flowchart LR"]
    for k, row in enumerate(rows, 1):
        node.setdefault(ids[k - 1], f"n{k}")
        label = f"{ids[k - 1]}. {row[1]}"[:60]
        lines.append(f'  n{k}["{mlabel(label)}"]')
    for a, b in edges:
        lines.append(f"  {node[a]} --> {node[b]}")
    return "\n".join(lines)


def clip(text, n=CUT) -> str:
    text = " ".join(str(text).replace("`", "").split())
    return text if len(text) <= n else text[:n - 1] + "…"


def joined(values) -> str:
    """The distinct non-empty values, in order, joined with ` / `."""
    out = []
    for v in values:
        v = " ".join(str(v).split())
        if v and v not in out:
            out.append(v)
    return " / ".join(out)


def edge_protocol(edge) -> str:
    return joined(r.protocol for r in edge.rows)


def graph_source(edges, labelled) -> str:
    """The structure graph: a subgraph per member for the parts that have a record, the other ends outside them.
    With `labelled`, each edge carries `#n` and its Protocol cell; a solid edge is built or measured."""
    nodes = {}  # key -> [id, label, member or None]

    def add(ref):
        if ref.key not in nodes:
            nodes[ref.key] = [f"n{len(nodes) + 1}", mlabel(ref.label), ref.member if ref.kind == "rec" else None]
        return nodes[ref.key][0]

    lines = []
    for e in edges:
        a, b = add(e.start), add(e.end)
        label = ""
        if labelled:
            label = '|"' + mlabel(f"#{e.n} {clip(edge_protocol(e))}".strip()) + '"|'
        lines.append(f"  {a} {'-->' if e.solid else '-.->'}{label} {b}")
    out = ["flowchart LR"]
    members = []
    for n in nodes.values():
        if n[2] is not None and n[2] not in members:
            members.append(n[2])
    for i, m in enumerate(members, 1):
        out.append(f'  subgraph m{i}["{mlabel(m)}"]')
        out += [f'    {n[0]}["{n[1]}"]' for n in nodes.values() if n[2] == m]
        out.append("  end")
    out += [f'  {n[0]}["{n[1]}"]' for n in nodes.values() if n[2] is None]
    return "\n".join(out + lines)


def sequence_source(flow) -> str:
    """One sequenceDiagram for the flow. A step with several ends is drawn once per end, `(one of)`; a step with
    no target is a note on its actor; a step that is not built or measured has a dashed arrow."""
    ids = {}
    lines = ["sequenceDiagram"]

    def part(ref):
        if ref.key not in ids:
            ids[ref.key] = f"p{len(ids) + 1}"
            lines.append(f"  participant {ids[ref.key]} as {mlabel(ref.label)}")
        return ids[ref.key]

    msgs = []
    for s in flow.steps:
        base = f"{s.n}. {s.action}"
        many = len(s.actors) > 1 or len(s.targets) > 1
        text = mlabel(clip(base) + (" (one of)" if many else ""))
        arrow = "->>" if s.solid else "-->>"
        if not s.targets:
            for a in s.actors:
                msgs.append(f"  Note over {part(a)}: {text}")
            continue
        for a in s.actors:
            for t in s.targets:
                msgs.append(f"  {part(a)}{arrow}{part(t)}: {text}")
    return "\n".join(lines + msgs)
