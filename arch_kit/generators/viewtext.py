"""The text around a generated view: its title, sources line and exceptions table, and its profile entry."""
from __future__ import annotations

import re

from . import model, text, views

PROFILE_LABELS = {"uaf": "UAF 1.3", "dodaf202": "DoDAF 2.02", "naf4": "NAF v4.1"}


NO_DODAF = "UAF 1.3 Table 2-1 gives no DoDAF view"


NO_NAF = "NAF v4.1 section not yet read"


def uaf_id(v):
    return v["uaf"] if "uaf" in v else v["key"]


def ordered_views(cw) -> list:
    """Views in navigation order: by declared group, then declaration order."""
    out = []
    for g in cw["groups"]:
        out += [v for v in cw["views"] if v["group"] == g["key"]]
    return out


def sources_line(used) -> str:
    by = {}
    for m, rec in used:
        by.setdefault(m.name, []).append(f"`{rec.path}`")
    return "Sources: " + "; ".join(f"{name} ({', '.join(paths)})" for name, paths in by.items()) + "."


def exceptions(ctx) -> str:
    rows = []
    for _m, rec in ctx.used:
        for heading, _row, status_cell, cells in rec.claims:
            status = model.claim_status(status_cell)
            if status not in views.SOLID:
                claim = cells[0] if cells else heading
                rows.append([text.cell(rec.display_id), text.cell(claim[:100]), text.cell(status)])
    rows += ctx.extra
    if not rows:
        rows = [["none", "", ""]]
    return "## Exceptions\n\n" + text.table(["Record", "Claim", "Status"], rows)


def view_text(v, ctx, body) -> str:
    return f"# {v['title']}\n\n{sources_line(ctx.used)}\n\n{body.rstrip(chr(10))}\n\n{exceptions(ctx)}"


def view_name(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")


def profile_entry(v) -> dict:
    vid = uaf_id(v)
    entry = {"name": view_name(v["title"]), "file": f"views/{vid}.md", "exports": {}}
    no_target = {}
    if v.get("dodaf"):
        entry["exports"]["dodaf202"] = list(v["dodaf"])
    else:
        no_target["dodaf202"] = NO_DODAF
    naf = v.get("naf")
    if naf and naf.get("read"):
        entry["exports"]["naf4"] = [naf["id"]]
    else:
        no_target["naf4"] = NO_NAF
    if no_target:
        entry["no_target"] = no_target
    return entry
