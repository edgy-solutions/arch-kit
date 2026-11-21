#!/usr/bin/env python3
"""browser_facts.py - the numbers and ids the browser check expects, computed from the declaration and the sources.

Usage:
    python -m arch_kit browser_facts --out FILE

Writes JSON. Nothing is read from the rendered HTML: a fact computed from the page it checks would only say
the page agrees with itself. The fields:

    views               the number of views in the profiles file (files.profiles)
    base_pages          the front page, the views and the declarations page (render_html.build)
    capability_pages    one per capability in the model file (render_html.capability_pages)
    decision_pages      one per decisions/ADR-*.md plus the roadmap note (render_html.Decisions)
    phase_badges        body cells under the declared phase column, in every table of the phases-home view's
                        source. The generated capability-phases table is counted by its rows: one per
                        model capability that has a record entry. The tables are parsed with render_html.table_grid
    badge_kinds         the distinct badge keys of the declared phases
    phase_names         the declared phase names, strongest first
    phase_column        labels.phase.column
    group_starts        rows of the capability table, in order, whose group cell differs from the row above
    group_slug          labels.group.column as a CSS slug; a row that starts a group carries `<slug>-start`
    phases_home         the view that holds the capability-phases table (`views.homes`)
    wide_table_columns  the largest column count of any table in the export.browser.views.table view's source;
                        when the data-exchange home is that view, also the kit's fixed Exchanges table
                        (data_exchange.exchange_header)
    expect_wide_table   the optional export.browser.expect_wide_table, false when absent
    roles, search, capability_link, min_pages, min_tables, min_tokens   the declaration's export.browser.* and
                        the first of views.capability_links

In `portal.mode: decisions` the facts are these, from facts_decisions; nothing of the views, profiles, record or
model is read:

    mode                "decisions"
    page_ids            every page's section id but the front's, in document order: the decision pages, the
                        alignment pages, then the Flows page when there are flows
    decision_pages      how many of page_ids are decision pages, the roadmap note included
    alignment_pages     how many are alignment pages
    flows_pages         1 when there is a Flows page, else 0
    search              {phrase, finds}: export.browser.search.phrase, and the page id of the decision named by
                        export.browser.search.finds (a decision id such as ADR-0002). When export.browser.search
                        is absent: the first decision record's id as the phrase, and that record's page
    min_pages           export.browser.min_pages; when absent, one printed page for each page of the portal,
                        the front page included (every page starts a new printed page)
    defaulted           the keys of search and min_pages that were not declared and took their defaults, so the
                        browser check's lines can say which values were derived

Both keys are optional in this mode. A declared search needs both phrase and finds.

A missing declared key exits 2 through project.need. Stdlib, PyYAML and markdown-it-py only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import capability_phases
import check_views
import data_exchange
import declared
import project
import render_html
import render_profile

EXIT_OK, EXIT_INPUT = 0, 2
TOOL = "browser_facts"
ROLES = ("table", "diagram", "profile_only")


def source_tables(markdown: str) -> list:
    """Each table of a markdown text as render_html.table_grid parses it."""
    if render_html.MarkdownIt is None:
        raise check_views.InputError("markdown-it-py is not installed: pip install markdown-it-py==4.0.0")
    md = render_html.MarkdownIt("commonmark", {"html": False}).enable("table")
    out = []
    for m in render_html.TABLE_RE.finditer(md.render(markdown)):
        parsed = render_html.table_grid(m.group(0))
        if parsed is not None:
            out.append(parsed)
    return out


def expect_wide_table() -> bool:
    """Whether the declaration says its table view holds a table wider than its container at 1280: the optional
    `export.browser.expect_wide_table`. The kit's examples say so; a project that does not skips that check."""
    return bool((project.CONFIG.get("export", {}).get("browser") or {}).get("expect_wide_table", False))


def facts(root: Path) -> dict:
    if declared.portal_mode(TOOL) == "decisions":
        return facts_decisions(root)
    tree = check_views.Tree(root)
    if declared.model_none(TOOL):
        return facts_no_model(root, tree)
    try:
        record = capability_phases.load_record(root / declared.content_file("record", "browser_facts"))
    except capability_phases.InputError as e:
        raise check_views.InputError(str(e))
    capabilities = capability_phases.model_capabilities(tree.sysml)
    road_rows = capability_phases.roadmap_rows(
        capability_phases.read_text(project.DECISIONS / capability_phases.roadmap_file()) or "")
    rows = {name: parent for name, parent in capabilities.items() if name in record["capabilities"]}
    groups = [capability_phases.group_of(record, record["capabilities"][name] or {}, parent, road_rows)
              for name, parent in rows.items()]
    phases = declared.phases(TOOL)
    group_column = str(project.need("labels.group.column", TOOL))
    phase_column = str(project.need("labels.phase.column", TOOL))
    home = declared.home("capability-phases", TOOL)
    browser = {key: project.need("export.browser." + key, TOOL)
               for key in ("views", "search", "min_pages", "min_tables", "min_tokens")}
    roles = {r: str(project.need("export.browser.views." + r, TOOL)) for r in ROLES}
    search = {k: str(project.need("export.browser.search." + k, TOOL)) for k in ("phrase", "finds")}

    # the phases-home view: its source tables, with the generated table standing as one row per capability row
    text = tree.view_text.get(home, "")
    stand_in = "\n".join([f"| Capability | {group_column} | {phase_column} |", "|---|---|---|"] +
                         ["| x | x | x |"] * len(rows)) + "\n"
    tables = source_tables(text.replace(render_profile.PHASES_MARKER, stand_in))
    badges = 0
    for _, head_starts, grid in tables:
        heads = [render_html.plain(c[2]) for c in grid[0]]
        if phase_column in heads:
            col = heads.index(phase_column)
            badges += sum(1 for r in grid[1:] if col < len(r))

    # the widest table in the table view's source, and the kit's fixed Exchanges table when that view is its home
    wide = max([max(len(r) for r in grid) for _, _, grid in source_tables(tree.view_text.get(roles["table"], ""))] or [0])
    dx_home = (tree.profiles.get("data_exchange") or {}).get("home")
    if dx_home == roles["table"]:
        wide = max(wide, len(data_exchange.exchange_header({"topic": "", "writer": "", "consumers": ""})))

    return {
        "views": len(tree.views),
        "exchange": declared.exchange_reader(TOOL) is not None,
        "base_pages": 1 + len(tree.views) + (0 if declared.chart_none(TOOL) else 1),
        "extra_pages": len(declared.pages(TOOL)),
        "capability_pages": len(capabilities),
        "decision_pages": len(render_html.Decisions(project.DECISIONS).keys()),
        "phase_badges": badges,
        "badge_kinds": len({p.badge for p in phases}),
        "phase_names": [p.name for p in phases],
        "phase_column": phase_column,
        "group_starts": sum(1 for a, b in zip(groups, groups[1:]) if a != b),
        "group_slug": declared.group_slug(TOOL),
        "phases_home": home,
        "wide_table_columns": wide,
        "roles": roles,
        "search": search,
        "capability_link": declared.views(TOOL)["capability_links"][0],
        "min_pages": browser["min_pages"],
        "min_tables": browser["min_tables"],
        "min_tokens": browser["min_tokens"],
        "id_max": render_html.ID_MAX,
        "expect_wide_table": expect_wide_table(),
    }


def facts_decisions(root: Path) -> dict:
    """The facts of a `portal.mode: decisions` portal, from the declaration and the sources (render_html's own
    readers, called as `decisions_parts` calls them with no relabel rules). No views, profiles, record or model."""
    browser = (project.CONFIG.get("export") or {}).get("browser") or {}
    dec = render_html.Decisions(project.DECISIONS)
    keys = dec.keys()
    records_only = [k for k in keys if k != render_html.ROADMAP_KEY]
    defaulted = [k for k in ("search", "min_pages") if k not in browser]
    if "search" in browser:
        search = {k: str(project.need("export.browser.search." + k, TOOL)) for k in ("phrase", "finds")}
    elif records_only:
        search = {"phrase": records_only[0], "finds": records_only[0]}
    else:
        raise check_views.InputError("there is no decision record to search for: declare export.browser.search")
    if search["finds"] not in keys or search["finds"] == render_html.ROADMAP_KEY:
        raise check_views.InputError(f"export.browser.search.finds {search['finds']!r} is not a decision record id "
                                     f"(the records are {', '.join(k for k in keys if k != render_html.ROADMAP_KEY)})")
    records = render_html.alignment_records(dec)
    flow_list = render_html.flows_records(dec)
    decision_ids = [dec.page_id(k) for k in keys]
    alignment_ids = [f"alignment-{name}" for name in sorted(records)]
    flows_ids = ["flows"] if flow_list else []
    page_ids = decision_ids + alignment_ids + flows_ids
    min_pages = browser["min_pages"] if "min_pages" in browser else 1 + len(page_ids)
    return {
        "mode": "decisions",
        "page_ids": page_ids,
        "decision_pages": len(decision_ids),
        "alignment_pages": len(alignment_ids),
        "flows_pages": len(flows_ids),
        "search": {"phrase": search["phrase"], "finds": dec.page_id(search["finds"])},
        "min_pages": min_pages,
        "defaulted": defaulted,
    }


def facts_no_model(root: Path, tree: check_views.Tree) -> dict:
    """The facts of a project with model: none: no capability pages and none of the phase facts."""
    browser = {key: project.need("export.browser." + key, TOOL)
               for key in ("views", "search", "min_pages", "min_tables", "min_tokens")}
    roles = {r: str(project.need("export.browser.views." + r, TOOL)) for r in ROLES}
    search = {k: str(project.need("export.browser.search." + k, TOOL)) for k in ("phrase", "finds")}
    wide = max([max(len(r) for r in grid) for _, _, grid in source_tables(tree.view_text.get(roles["table"], ""))] or [0])
    return {
        "views": len(tree.views),
        "exchange": False,
        "model": False,
        "base_pages": 1 + len(tree.views) + (0 if declared.chart_none(TOOL) else 1),
        "extra_pages": len(declared.pages(TOOL)),
        "capability_pages": 0,
        "decision_pages": len(render_html.Decisions(project.DECISIONS).keys()),
        "wide_table_columns": wide,
        "roles": roles,
        "search": search,
        "min_pages": browser["min_pages"],
        "min_tables": browser["min_tables"],
        "min_tokens": browser["min_tokens"],
        "id_max": render_html.ID_MAX,
        "expect_wide_table": expect_wide_table(),
    }


def main(argv: list[str] | None = None) -> int:
    project.require_portal("browser_facts")
    ap = argparse.ArgumentParser(description="Write the facts the browser check reads, from the declaration.")
    ap.add_argument("--root", default=str(project.ROOT))
    ap.add_argument("--out", required=True, help="the JSON file to write")
    a = ap.parse_args(argv)
    try:
        out = facts(Path(a.root))
    except (check_views.InputError, data_exchange.InputError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_INPUT
    Path(a.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
