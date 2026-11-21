"""Self-test: component connections and the Protected by column.

The schema, the checks and the reports run through the same temporary project the component tests use
(test_components.Project). The data functions and the render are pure functions, tested on small inputs.
"""
from __future__ import annotations

import copy
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))

import components  # noqa: E402
from test_components import Project, good, message  # noqa: E402
from test_components_render import comp, none, page  # noqa: E402

SECTION = chr(167)
TOOL = "components_test: components.yaml: "


def cx(**over) -> dict:
    c = {"other": "CO-001", "direction": "calls", "protocol": "parcel topic over TLS", "sign_in": "locker token",
         "what_passes": "parcel events", "status": "built", "evidence": ["src/depot_sync.py:2"]}
    c.update(over)
    return c


def by(who="CO-003", **over) -> dict:
    p = {"by": who, "status": "built", "evidence": ["src/depot_sync.py:3"]}
    p.update(over)
    return p


def gap(why="no per-message signature", **over) -> dict:
    p = {"none": why, "status": "built", "evidence": ["src/depot_sync.py:3"]}
    p.update(over)
    return p


def with_connections(*connections):
    """A change to the good components: the connections go on the second component (CO-002, built)."""
    def apply(comps):
        comps[1]["connections"] = copy.deepcopy(list(connections))
        return comps
    return apply


class Runner(unittest.TestCase):
    def load(self, change):
        p = Project(self)
        p.put(change(good()))
        return p.render()

    def refused(self, change, text):
        r = self.load(change)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(text, message(r.stderr))

    def accepted(self, change):
        r = self.load(change)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r


NOT_PARTY = ("{} is not a component of this record, a component of a declared foreign member (<prefix>:CO-...), "
             "or an outside system (XE-...)")


class Schema(Runner):
    def test_a_bad_direction(self):
        self.refused(with_connections(cx(direction="sends")), "components.1.connections.0.direction:")

    def test_both_by_and_none(self):
        both = dict(by(), none="why")
        self.refused(with_connections(cx(protected_by=[both])),
                     "components.1.connections.0.protected_by.0: must have exactly one of by or none")

    def test_neither_by_nor_none(self):
        self.refused(with_connections(cx(protected_by=[{"status": "built", "evidence": ["src/depot_sync.py:3"]}])),
                     "components.1.connections.0.protected_by.0: must have exactly one of by or none")

    def test_an_empty_protected_by(self):
        self.refused(with_connections(cx(protected_by=[])),
                     "components.1.connections.0.protected_by: must list at least one protection")

    def test_an_empty_connections_list(self):
        self.refused(with_connections(), "components.1.connections: must list at least one connection")

    def test_an_extra_key_on_a_protection(self):
        self.refused(with_connections(cx(protected_by=[dict(by(), extra=1)])),
                     "components.1.connections.0.protected_by.0.extra: unknown key")

    def test_an_extra_key_on_a_connection(self):
        self.refused(with_connections(cx(extra=1)), "components.1.connections.0.extra: unknown key")

    def test_a_missing_key(self):
        c = cx()
        del c["protocol"]
        self.refused(with_connections(c), "components.1.connections.0.protocol: is required")

    def test_a_missing_protection_status(self):
        p = by()
        del p["status"]
        self.refused(with_connections(cx(protected_by=[p])),
                     "components.1.connections.0.protected_by.0.status: is required")

    def test_a_blank_protocol_and_a_two_line_none(self):
        self.refused(with_connections(cx(protocol=" ")),
                     f"components.1.connections.0.protocol: {components.LINE_WHY}")
        self.refused(with_connections(cx(protected_by=[gap("a\nb")])),
                     f"components.1.connections.0.protected_by.0.none: {components.LINE_WHY}")

    def test_a_record_without_connections_is_accepted(self):
        self.accepted(lambda comps: comps)


class Checks(Runner):
    def test_each_form_of_other_is_accepted(self):
        for other in ("CO-001", "other:CO-007", "XE-PARCEL-API"):
            with self.subTest(other=other):
                self.accepted(with_connections(cx(other=other)))

    def test_an_undeclared_prefix(self):
        self.refused(with_connections(cx(other="nowhere:CO-007")),
                     "components[1].connections[0].other: " + NOT_PARTY.format("nowhere:CO-007"))

    def test_an_unknown_component(self):
        self.refused(with_connections(cx(other="CO-099")),
                     "components[1].connections[0].other: " + NOT_PARTY.format("CO-099"))

    def test_a_foreign_prefix_with_a_bad_rest(self):
        self.refused(with_connections(cx(other="other:ADR-0007")),
                     "components[1].connections[0].other: " + NOT_PARTY.format("other:ADR-0007"))

    def test_a_bad_outside_system_form(self):
        self.refused(with_connections(cx(other="XE-")),
                     "components[1].connections[0].other: " + NOT_PARTY.format("XE-"))

    def test_self_reference(self):
        self.refused(with_connections(cx(other="CO-002")),
                     "components[1].connections[0].other: a component cannot connect to itself")

    def test_the_same_other_and_direction_twice(self):
        self.refused(with_connections(cx(), cx(protocol="other")),
                     "components[1].connections[1].other: CO-001 calls is listed twice")

    def test_the_same_other_in_two_directions_is_accepted(self):
        self.accepted(with_connections(cx(), cx(direction="reads")))

    def test_a_repeated_evidence_item_on_a_connection(self):
        self.refused(with_connections(cx(evidence=["src/depot_sync.py:2", "src/depot_sync.py:2"])),
                     "components[1].connections[0].evidence: src/depot_sync.py:2 is listed twice")

    def test_a_repeated_evidence_item_on_a_protection(self):
        self.refused(with_connections(cx(protected_by=[by(evidence=["ADR-0001", "ADR-0001"])])),
                     "components[1].connections[0].protected_by[0].evidence: ADR-0001 is listed twice")

    def test_each_form_of_by_is_accepted(self):
        for who in ("CO-003", "CO-002", "other:CO-007", "XE-GATE"):
            with self.subTest(by=who):
                self.accepted(with_connections(cx(protected_by=[by(who)])))

    def test_a_bad_protector(self):
        self.refused(with_connections(cx(protected_by=[by("CO-099")])),
                     "components[1].connections[0].protected_by[0].by: " + NOT_PARTY.format("CO-099"))

    def test_the_same_protector_twice(self):
        self.refused(with_connections(cx(protected_by=[by("CO-003"), by("CO-003")])),
                     "components[1].connections[0].protected_by[1].by: CO-003 is listed twice")

    def test_two_none_entries(self):
        self.refused(with_connections(cx(protected_by=[gap("a"), gap("b")])),
                     "components[1].connections[0].protected_by[1].none: more than one none entry")

    def test_an_unresolved_evidence_item_in_a_protection(self):
        self.refused(with_connections(cx(protected_by=[by(evidence=["src/nothing.py"])])),
                     "components[1].connections[0].protected_by[0].evidence[0]: src/nothing.py does not resolve to a "
                     "decision record or a repository path")

    def test_an_unresolved_evidence_item_on_a_connection(self):
        self.refused(with_connections(cx(evidence=["ADR-0099"])),
                     "components[1].connections[0].evidence[0]: ADR-0099 does not resolve")

    def test_built_without_a_line_on_a_connection(self):
        self.refused(with_connections(cx(evidence=["ADR-0001"])),
                     "components[1].connections[0].evidence: built needs a file and line (path:N) in evidence")

    def test_accepted_without_a_decision_on_a_protection(self):
        self.refused(with_connections(cx(protected_by=[by(status="accepted")])),
                     "components[1].connections[0].protected_by[0].evidence: accepted needs a decision record in "
                     "evidence")

    def test_existing_messages_come_first(self):
        def change(comps):
            comps[0]["plane"] = "cloud"
            return with_connections(cx(other="CO-099"))(comps)
        self.refused(change, "components[0].plane: cloud is not a declared plane")


class Reports(Runner):
    def test_the_gap_line(self):
        r = self.accepted(with_connections(cx(protected_by=[by(), gap()])))
        lines = [ln for ln in r.stderr.splitlines() if ln.strip()]
        self.assertEqual(lines, [TOOL + "components[1].connections[0].protected_by[1]: gap: "
                                 "none: no per-message signature"])

    def test_a_connection_without_protected_by_gives_no_report(self):
        r = self.accepted(with_connections(cx()))
        self.assertEqual(r.stderr, "")

    def test_census_only_built_on_a_connection(self):
        p = Project(self)
        p.decl["census"] = "GUIDE.md"
        p.write_decl()
        (p.root / "GUIDE.md").write_text("# Guide\n", encoding="utf-8")
        p.put(with_connections(cx(evidence=[SECTION + "4.1"]))(good()))
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(TOOL + "components[1].connections[0].evidence: built, but the only "
                      "evidence is a census key (no path:N)", r.stderr)

    def test_measured_not_under_results_on_a_protection(self):
        r = self.accepted(with_connections(cx(protected_by=[by(status="measured", evidence=["src/depot_sync.py"])])))
        self.assertIn(TOOL + "components[1].connections[0].protected_by[0].evidence: measured, "
                      "but no evidence is under components.results", r.stderr)

    def test_measured_under_results_gives_no_report(self):
        r = self.accepted(with_connections(cx(protected_by=[by(status="measured",
                                                               evidence=["results/locker-wake.txt"])])))
        self.assertEqual(r.stderr, "")

    def test_reports_follow_the_component_reports(self):
        def change(comps):
            comps[3]["evidence"] = ["src"]
            return with_connections(cx(protected_by=[gap()]))(comps)
        r = self.accepted(change)
        lines = [ln for ln in r.stderr.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 2, r.stderr)
        self.assertIn("components[3].evidence: measured", lines[0])
        self.assertIn("gap: none:", lines[1])


CELL_BY = ('CO-003 <span class="badge component-accepted">Accepted</span> (<a href="#adr-0001">ADR-0001</a>, '
           '<code>src/a.py:2</code>)')
CELL_NONE = ('<span class="badge connection-gap">Gap</span> none: no &lt;signature&gt; '
             '<span class="badge component-built">Built</span> (<code>src/a.py:2</code>)')


def href(item):
    return "#adr-0001" if item == "ADR-0001" else None


class Cell(unittest.TestCase):
    BY = {"by": "CO-003", "status": "accepted", "evidence": ["ADR-0001", "src/a.py:2"]}
    NONE = {"none": "no <signature>", "status": "built", "evidence": ["src/a.py:2"]}

    def test_a_by_entry(self):
        self.assertEqual(components.protected_by_cell([self.BY], href), CELL_BY)

    def test_a_none_entry(self):
        self.assertEqual(components.protected_by_cell([self.NONE], href), CELL_NONE)

    def test_a_mixed_list(self):
        self.assertEqual(components.protected_by_cell([self.BY, self.NONE], href), CELL_BY + "; " + CELL_NONE)

    def test_none_is_not_written(self):
        self.assertEqual(components.protected_by_cell(None, href), '<span class="not-written">not written</span>')

    def test_the_protector_is_escaped(self):
        cell = components.protected_by_cell([dict(self.BY, by="a<b")], none)
        self.assertTrue(cell.startswith("a&lt;b <span"))


class Table(unittest.TestCase):
    HEAD = ("<tr><th>Other party</th><th>Direction</th><th>Protocol</th><th>Sign-in</th><th>Protected by</th>"
            "<th>What passes</th><th>Evidence</th><th>Status</th></tr>")

    def test_a_component_with_connections(self):
        c = comp(1, connections=[cx(other="XE-API", protected_by=None, evidence=["src/a.py:2"])])
        del c["connections"][0]["protected_by"]
        text = page([c])
        want = ('</dl><h4>Connections</h4><div class="scroll"><table class="connections">' + self.HEAD
                + '<tr data-connection="XE-API"><td>XE-API</td><td>calls</td><td>parcel topic over TLS</td>'
                '<td>locker token</td><td><span class="not-written">not written</span></td>'
                '<td>parcel events</td><td><code>src/a.py:2</code></td>'
                '<td><span class="badge component-built">Built</span></td></tr></table></div></article>')
        self.assertIn(want, text)

    def test_a_protected_row_uses_the_cell(self):
        c = comp(1, connections=[cx(protected_by=[by("CO-003", status="accepted", evidence=["ADR-0001"])])])
        text = page([c], href=href)
        cell = components.protected_by_cell(c["connections"][0]["protected_by"], href)
        self.assertIn(f"<td>{cell}</td>", text)

    def test_a_component_without_connections_is_unchanged(self):
        want = ('<article id="component-CO-001" class="component" data-component="CO-001" data-status="proposed">'
                '<h3>CO-001 part-1 <span class="badge component-proposed">Proposed</span></h3><dl>'
                '<dt>Purpose</dt><dd>holds parcels</dd><dt>Wiring</dt><dd>w</dd><dt>Sign-in</dt><dd>s</dd>'
                '<dt>Data path</dt><dd>d</dd><dt>Serves</dt><dd>pickup</dd><dt>Evidence</dt><dd>'
                '<a href="#adr-0001">ADR-0001</a></dd></dl></article>')
        self.assertIn(want, page([comp(1)], href=href))
        self.assertNotIn("Connections", page([comp(1)]))


class Rows(unittest.TestCase):
    def record(self):
        return [
            comp(1),
            comp(2, connections=[
                cx(protected_by=[by("CO-001"), gap("open")]),
                cx(other="XE-API", direction="reads"),
            ]),
            comp(3, connections=[cx(other="CO-002", protected_by=[gap("shared", status="proposed")])]),
        ]

    def test_connection_rows(self):
        rows = components.connection_rows(self.record())
        self.assertEqual([(r["component"], r["other"], r["direction"]) for r in rows],
                         [("CO-002", "CO-001", "calls"), ("CO-002", "XE-API", "reads"), ("CO-003", "CO-002", "calls")])
        self.assertEqual(set(rows[0]), {"component", "other", "direction", "protocol", "sign_in", "what_passes",
                                        "status", "evidence", "protected_by"})
        self.assertEqual(len(rows[0]["protected_by"]), 2)
        self.assertIsNone(rows[1]["protected_by"])

    def test_gaps(self):
        self.assertEqual(components.gaps(self.record()), [
            {"component": "CO-002", "other": "CO-001", "direction": "calls", "why": "open", "status": "built",
             "evidence": ["src/depot_sync.py:3"]},
            {"component": "CO-003", "other": "CO-002", "direction": "calls", "why": "shared", "status": "proposed",
             "evidence": ["src/depot_sync.py:3"]},
        ])

    def test_no_connections_gives_nothing(self):
        self.assertEqual(components.connection_rows([comp(1)]), [])
        self.assertEqual(components.gaps([comp(1)]), [])


if __name__ == "__main__":
    unittest.main()
