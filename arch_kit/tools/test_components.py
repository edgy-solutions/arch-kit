"""Self-test: the component record: the schema, the checks, both routes, the `components:` declaration.

Each case builds a project in a temporary directory from examples/decisions-only, adds `files.components` (or a loader
that defines `load_components`) and a `components:` map, copies the fixtures in testdata/components into it, puts
components in the file and loads them in a subprocess (the declaration is read once per process). An accepted list
exits 0; a refused one exits 2 and its message names the component and the key. A measured component with no evidence
under `components.results` is not refused: the report goes to stderr.
"""
from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))

from test_example_decisions import copy_example  # noqa: E402

FIXTURES = HERE / "testdata" / "components"

LOADER_TAIL = '''

def load_components(root):
    import yaml
    return yaml.safe_load((Path(root) / "records.yaml").read_text(encoding="utf-8"))["components"]
'''

DECLARATION = {"planes": ["edge", "hub"], "results": ["results"]}


def component(n: int, **over) -> dict:
    c = {"id": f"CO-{n:03d}", "name": f"part-{n}", "purpose": "holds parcels for pickup", "plane": "edge",
         "wiring": "talks to the depot over the parcel topic", "sign_in": "locker token", "data_path": "locker to depot",
         "serves": ["pickup"], "status": "proposed", "evidence": ["ADR-0001"]}
    c.update(over)
    return c


GOOD = [
    component(1, name="locker-agent", status="proposed", evidence=["ADR-0001"]),
    component(2, name="depot-sync", plane="hub", status="built", evidence=["src/depot_sync.py:2"]),
    component(3, name="ledger", plane="hub", status="accepted", evidence=["ADR-0002", "other:ADR-0007"], serves=[]),
    component(4, name="wake-probe", status="measured", evidence=["results/locker-wake.txt"]),
]


def good() -> list:
    return copy.deepcopy(GOOD)


class Project:
    """A temporary project built from the decisions-only example, with components by one route or the other."""

    def __init__(self, test: unittest.TestCase, route: str = "file", declaration=DECLARATION):
        self.tmp = Path(tempfile.mkdtemp())
        test.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = copy_example(self.tmp)
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        self.route = route
        decl = yaml.safe_load((self.root / "arch-kit.yaml").read_text(encoding="utf-8"))
        decl["decisions"]["index"]["foreign"] = [{"prefix": "other"}]
        if declaration is not None:
            decl["components"] = copy.deepcopy(declaration)
        if route == "file":
            decl["files"] = {"components": "components.yaml"}
        else:
            decl["loader"] = "components_loader.py"
            text = (self.root / "kit_loader.py").read_text(encoding="utf-8")
            (self.root / "components_loader.py").write_text(text + LOADER_TAIL, encoding="utf-8")
        self.decl = decl
        self.write_decl()

    def write_decl(self):
        (self.root / "arch-kit.yaml").write_text(yaml.safe_dump(self.decl, sort_keys=False), encoding="utf-8")

    def put(self, components) -> None:
        name = "components.yaml" if self.route == "file" else "records.yaml"
        (self.root / name).write_text(yaml.safe_dump({"components": components}, sort_keys=False), encoding="utf-8")

    def render(self):
        return load_in(self.root, "arch-kit.yaml")


LOAD = '''
import sys
sys.path.insert(0, {tools!r})
import components
from data_exchange import InputError
try:
    print(len(components.load("components_test", ["ADR-0001", "ADR-0002", "ADR-0003"])))
except InputError as e:
    print(f"error: {{e}}", file=sys.stderr)
    sys.exit(2)
'''


def load_in(root: Path, decl: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, ARCH_KIT_CONFIG=str(root / decl), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-c", LOAD.format(tools=str(HERE))], cwd=root, env=env,
                          capture_output=True, text=True, encoding="utf-8")


def message(stderr: str) -> str:
    return [ln for ln in stderr.splitlines() if ln.strip()][-1]


def mut(fn):
    def apply(components):
        fn(components)
        return components
    return apply


ID_WHY = "must be CO- then capitals, digits and hyphens"
PART_WHY = "must be a part name: a letter or digit, then letters, digits, dots, underscores or hyphens"
LINE_WHY = "must be one non-empty line"
KEYS = ("id", "name", "purpose", "plane", "wiring", "sign_in", "data_path", "serves", "status", "evidence")

# (name, change to the good components, text the message holds)
REFUSED = [
    # the schema
    ("empty list", mut(lambda c: c.clear()), "components: must list at least one component"),
    ("unknown key", mut(lambda c: c[1].update(extra=1)), "components.1.extra: unknown key"),
    ("bad id", mut(lambda c: c[0].update(id="CO-trace")), f"components.0.id: {ID_WHY}"),
    ("id without a body", mut(lambda c: c[0].update(id="CO-")), f"components.0.id: {ID_WHY}"),
    ("lower case id", mut(lambda c: c[0].update(id="co-001")), f"components.0.id: {ID_WHY}"),
    ("double hyphen in id", mut(lambda c: c[0].update(id="CO--A")), f"components.0.id: {ID_WHY}"),
    ("trailing hyphen in id", mut(lambda c: c[0].update(id="CO-A-")), f"components.0.id: {ID_WHY}"),
    ("underscore in id", mut(lambda c: c[0].update(id="CO-A_B")), f"components.0.id: {ID_WHY}"),
    ("id with a newline", mut(lambda c: c[0].update(id="CO-A\nB")), f"components.0.id: {ID_WHY}"),
    ("name with a space", mut(lambda c: c[0].update(name="a b")), f"components.0.name: {PART_WHY}"),
    ("name with a leading hyphen", mut(lambda c: c[0].update(name="-x")), f"components.0.name: {PART_WHY}"),
    ("name with a capability prefix", mut(lambda c: c[0].update(name="capability:x")),
     f"components.0.name: {PART_WHY}"),
    ("plane with a space", mut(lambda c: c[0].update(plane="a b")), f"components.0.plane: {PART_WHY}"),
    ("two lines in purpose", mut(lambda c: c[0].update(purpose="a\nb")), f"components.0.purpose: {LINE_WHY}"),
    ("blank purpose", mut(lambda c: c[0].update(purpose=" ")), f"components.0.purpose: {LINE_WHY}"),
    ("empty wiring", mut(lambda c: c[0].update(wiring="")), f"components.0.wiring: {LINE_WHY}"),
    ("two lines in wiring", mut(lambda c: c[0].update(wiring="a\r\nb")), f"components.0.wiring: {LINE_WHY}"),
    ("blank sign_in", mut(lambda c: c[0].update(sign_in="  ")), f"components.0.sign_in: {LINE_WHY}"),
    ("two lines in sign_in", mut(lambda c: c[0].update(sign_in="a\nb")), f"components.0.sign_in: {LINE_WHY}"),
    ("blank data_path", mut(lambda c: c[0].update(data_path="")), f"components.0.data_path: {LINE_WHY}"),
    ("two lines in data_path", mut(lambda c: c[0].update(data_path="a\nb")), f"components.0.data_path: {LINE_WHY}"),
    ("serves not a list", mut(lambda c: c[0].update(serves="pickup")), "components.0.serves:"),
    ("blank serves item", mut(lambda c: c[0].update(serves=["pickup", " "])), f"components.0.serves.1: {LINE_WHY}"),
    ("two lines in a serves item", mut(lambda c: c[0].update(serves=["a\nb"])), f"components.0.serves.0: {LINE_WHY}"),
    ("status outside the enum", mut(lambda c: c[0].update(status="done")), "components.0.status:"),
    ("evidence not a list", mut(lambda c: c[0].update(evidence="ADR-0001")), "components.0.evidence:"),
    ("empty evidence", mut(lambda c: c[0].update(evidence=[])),
     "components.0.evidence: must name at least one piece of evidence"),
    ("evidence item not a string", mut(lambda c: c[0].update(evidence=[1])), "components.0.evidence.0:"),
] + [(f"no {k}", mut(lambda c, k=k: c[2].pop(k)), f"components.2.{k}: is required") for k in KEYS] + [
    # the checks
    ("duplicate id", mut(lambda c: c[1].update(id="CO-001")), "components[1].id: component id CO-001 is not unique"),
    ("duplicate name", mut(lambda c: c[1].update(name="locker-agent")),
     "components[1].name: component name locker-agent is not unique"),
    ("undeclared plane", mut(lambda c: c[0].update(plane="cloud")),
     "components[0].plane: cloud is not a declared plane (components.planes)"),
    ("duplicate serves", mut(lambda c: c[0].update(serves=["pickup", "pickup"])),
     "components[0].serves: pickup is listed twice"),
    ("duplicate evidence", mut(lambda c: c[0].update(evidence=["ADR-0001", "ADR-0001"])),
     "components[0].evidence: ADR-0001 is listed twice"),
    ("unresolved decision", mut(lambda c: c[0].update(evidence=["ADR-0099"])),
     "components[0].evidence[0]: ADR-0099 does not resolve to a decision record or a repository path"),
    ("undeclared foreign prefix", mut(lambda c: c[0].update(evidence=["nowhere:ADR-0007"])),
     "components[0].evidence[0]: nowhere:ADR-0007 does not resolve to a decision record or a repository path"),
    ("second item unresolved", mut(lambda c: c[0].update(evidence=["ADR-0001", "src/nothing.py"])),
     "components[0].evidence[1]: src/nothing.py does not resolve to a decision record or a repository path"),
    ("line zero", mut(lambda c: c[1].update(evidence=["src/depot_sync.py:0"])),
     "components[1].evidence[0]: src/depot_sync.py:0 does not resolve"),
    ("line past the end", mut(lambda c: c[1].update(evidence=["src/depot_sync.py:4"])),
     "components[1].evidence[0]: src/depot_sync.py:4 does not resolve"),
    ("leading zero line", mut(lambda c: c[1].update(evidence=["src/depot_sync.py:02"])),
     "components[1].evidence[0]: src/depot_sync.py:02 does not resolve"),
    ("directory with a line", mut(lambda c: c[1].update(evidence=["src:1"])),
     "components[1].evidence[0]: src:1 does not resolve"),
    ("missing file with a line", mut(lambda c: c[1].update(evidence=["src/nothing.py:1"])),
     "components[1].evidence[0]: src/nothing.py:1 does not resolve"),
    ("parent path", mut(lambda c: c[1].update(evidence=["../outside.txt"])),
     "components[1].evidence[0]: ../outside.txt does not resolve"),
    ("parent path with a line", mut(lambda c: c[1].update(evidence=["src/../src/depot_sync.py:1"])),
     "components[1].evidence[0]: src/../src/depot_sync.py:1 does not resolve"),
    ("absolute path", mut(lambda c: c[1].update(evidence=["/etc/hostname"])),
     "components[1].evidence[0]: /etc/hostname does not resolve"),
    ("absolute path with a line", mut(lambda c: c[1].update(evidence=["/etc/hostname:1"])),
     "components[1].evidence[0]: /etc/hostname:1 does not resolve"),
    ("drive path", mut(lambda c: c[1].update(evidence=["C:/Windows/win.ini"])),
     "components[1].evidence[0]: C:/Windows/win.ini does not resolve"),
    ("built with a decision only", mut(lambda c: c[1].update(evidence=["ADR-0001"])),
     "components[1].evidence: built needs a file and line (path:N) in evidence"),
    ("built with a bare path only", mut(lambda c: c[1].update(evidence=["src/depot_sync.py"])),
     "components[1].evidence: built needs a file and line (path:N) in evidence"),
    ("accepted with a path only", mut(lambda c: c[2].update(evidence=["src/depot_sync.py:1"])),
     "components[2].evidence: accepted needs a decision record in evidence"),
    ("accepted with a bare path only", mut(lambda c: c[2].update(evidence=["src"])),
     "components[2].evidence: accepted needs a decision record in evidence"),
]


class Routes(unittest.TestCase):
    def test_the_file_route_is_accepted(self):
        p = Project(self)
        p.put(good())
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "4"), r.stdout + r.stderr)
        self.assertNotIn("measured, but", r.stderr)

    def test_the_loader_route_is_accepted(self):
        p = Project(self, "loader")
        p.put(good())
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "4"), r.stdout + r.stderr)

    def test_both_declared_is_refused(self):
        p = Project(self)
        p.put(good())
        text = (p.root / "kit_loader.py").read_text(encoding="utf-8")
        (p.root / "components_loader.py").write_text(text + LOADER_TAIL, encoding="utf-8")
        p.decl["loader"] = "components_loader.py"
        p.write_decl()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("files.components: is declared, and the loader also defines load_components; use one route",
                      r.stderr)

    def test_neither_declared_gives_nothing(self):
        p = Project(self, declaration=None)
        del p.decl["files"]
        p.write_decl()
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "0"), r.stdout + r.stderr)

    def test_a_loader_without_load_components_and_no_file_gives_nothing(self):
        p = Project(self, declaration=None)
        del p.decl["files"]
        p.decl["loader"] = "kit_loader.py"
        p.write_decl()
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "0"), r.stdout + r.stderr)

    def test_file_order_is_kept(self):
        p = Project(self)
        comps = good()
        comps.reverse()
        p.put(comps)
        script = LOAD.replace('print(len(components.load("components_test", ["ADR-0001", "ADR-0002", "ADR-0003"])))',
                              'print(",".join(c["id"] for c in '
                              'components.load("components_test", ["ADR-0001", "ADR-0002", "ADR-0003"])))')
        env = dict(os.environ, ARCH_KIT_CONFIG=str(p.root / "arch-kit.yaml"), PYTHONIOENCODING="utf-8",
                   PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([sys.executable, "-c", script.format(tools=str(HERE))], cwd=p.root, env=env,
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.stdout.strip(), "CO-004,CO-003,CO-002,CO-001", r.stdout + r.stderr)

    def test_wider_ids_are_accepted(self):
        for cid in ("CO-001", "CO-1", "CO-TRACE", "CO-PT-PUBLISH"):
            with self.subTest(id=cid):
                p = Project(self)
                comps = good()
                comps[0]["id"] = cid
                p.put(comps)
                r = p.render()
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_an_empty_serves_is_accepted(self):
        p = Project(self)
        comps = good()
        for c in comps:
            c["serves"] = []
        p.put(comps)
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_file_that_is_not_a_map_with_components_is_refused(self):
        p = Project(self)
        (p.root / "components.yaml").write_text(yaml.safe_dump(good()), encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_a_top_level_unknown_key_is_refused(self):
        p = Project(self)
        (p.root / "components.yaml").write_text(yaml.safe_dump({"components": good(), "more": 1}), encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("more: unknown key", r.stderr)

    def test_a_loader_that_returns_a_map_is_refused(self):
        p = Project(self, "loader")
        (p.root / "records.yaml").write_text(yaml.safe_dump({"components": {"a": 1}}), encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("load_components must return a list of components", r.stderr)

    def test_an_unreadable_file_is_refused(self):
        p = Project(self)
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("components.yaml: (record): cannot be read", r.stderr)

    def test_bad_yaml_is_refused(self):
        p = Project(self)
        (p.root / "components.yaml").write_text("components: [a: b: c\n", encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("components.yaml: (record): not valid YAML", r.stderr)

    def test_the_error_names_the_file(self):
        p = Project(self)
        comps = good()
        comps[0]["id"] = "x"
        p.put(comps)
        r = p.render()
        self.assertRegex(message(r.stderr), r"^error: components\.yaml: components\.0\.id: ")


class Refusals(unittest.TestCase):
    def test_each_refusal(self):
        for name, change, text in REFUSED:
            for route in ("file", "loader"):
                with self.subTest(name, route=route):
                    p = Project(self, route)
                    p.put(change(good()))
                    r = p.render()
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertIn(text, message(r.stderr))
                    if route == "loader":
                        self.assertRegex(message(r.stderr), r"^error: load_components: ")


class Evidence(unittest.TestCase):
    """Forms (a), (b) and (c), and what each status needs."""

    def accepted(self, **over):
        p = Project(self)
        comps = good()
        comps[0].update(over)
        p.put(comps)
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def test_a_local_decision_is_accepted(self):
        self.accepted(evidence=["ADR-0003"])

    def test_a_foreign_decision_is_accepted(self):
        self.accepted(evidence=["other:ADR-0007"])

    def test_a_file_is_accepted(self):
        self.accepted(evidence=["src/depot_sync.py"])

    def test_a_directory_is_accepted(self):
        self.accepted(evidence=["src"])

    def test_a_file_and_line_is_accepted(self):
        self.accepted(evidence=["src/depot_sync.py:1"])

    def test_the_last_line_is_accepted(self):
        self.accepted(evidence=["src/depot_sync.py:3"])

    def test_the_forms_mix(self):
        self.accepted(evidence=["ADR-0001", "src", "src/depot_sync.py:2"])

    def test_proposed_needs_nothing_more(self):
        self.accepted(status="proposed", evidence=["src"])

    def test_built_with_a_line_among_others_is_accepted(self):
        self.accepted(status="built", evidence=["ADR-0001", "src/depot_sync.py:2"])

    def test_accepted_with_a_decision_among_others_is_accepted(self):
        self.accepted(status="accepted", evidence=["src/depot_sync.py:2", "ADR-0002"])


class Measured(unittest.TestCase):
    """`measured` without evidence under components.results is reported, not refused."""

    REPORT = "components_test: components.yaml: components[{i}].evidence: measured, but no evidence is under " \
             "components.results"

    def run_with(self, comps, route="file"):
        p = Project(self, route)
        p.put(comps)
        return p.render()

    def test_a_report_is_printed_and_the_load_succeeds(self):
        comps = good()
        comps[3]["evidence"] = ["src/depot_sync.py"]
        r = self.run_with(comps)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "4"), r.stdout + r.stderr)
        self.assertIn(self.REPORT.format(i=3), r.stderr)

    def test_the_loader_route_names_load_components(self):
        comps = good()
        comps[3]["evidence"] = ["ADR-0001"]
        r = self.run_with(comps, "loader")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("components_test: load_components: components[3].evidence: measured, but no evidence is under "
                      "components.results", r.stderr)

    def test_reports_are_in_file_order(self):
        comps = good()
        comps[0].update(status="measured", evidence=["ADR-0001"])
        comps[3]["evidence"] = ["src"]
        r = self.run_with(comps)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = [ln for ln in r.stderr.splitlines() if "measured, but" in ln]
        self.assertEqual(lines, [self.REPORT.format(i=0), self.REPORT.format(i=3)])

    def test_no_report_for_evidence_under_results(self):
        for item in ("results", "results/", "results/locker-wake.txt", "results/locker-wake.txt:1",
                     "results/depot/run-01.txt", "results/depot"):
            with self.subTest(item=item):
                comps = good()
                comps[3]["evidence"] = [item]
                r = self.run_with(comps)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertNotIn("measured, but", r.stderr)

    def test_one_item_under_results_is_enough(self):
        comps = good()
        comps[3]["evidence"] = ["ADR-0001", "src", "results/depot/run-01.txt"]
        r = self.run_with(comps)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("measured, but", r.stderr)

    def test_a_sibling_of_results_is_not_under_it(self):
        p = Project(self, declaration={"planes": ["edge", "hub"], "results": ["results/depot"]})
        comps = good()
        comps[3]["evidence"] = ["results/locker-wake.txt"]
        p.put(comps)
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(self.REPORT.format(i=3), r.stderr)

    def test_no_results_declared_reports_every_measured(self):
        p = Project(self, declaration={"planes": ["edge", "hub"]})
        p.put(good())
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(self.REPORT.format(i=3), r.stderr)

    def test_other_statuses_are_never_reported(self):
        p = Project(self)
        p.put(good()[:3])
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("measured, but", r.stderr)


class Declaration(unittest.TestCase):
    """The top-level `components:` map."""

    def refused(self, declaration, text):
        p = Project(self, declaration=declaration)
        p.put(good())
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(text, r.stderr)

    def test_no_map_is_refused(self):
        self.refused(None, "components.planes: is required when components are declared")

    def test_no_planes_is_refused(self):
        self.refused({"results": ["results"]}, "components.planes: is required when components are declared")

    def test_an_empty_planes_is_refused(self):
        self.refused({"planes": []}, "components.planes: must be a non-empty list")

    def test_planes_not_a_list_is_refused(self):
        self.refused({"planes": "edge"}, "components.planes: must be a non-empty list")

    def test_a_repeated_plane_is_refused(self):
        self.refused({"planes": ["edge", "hub", "edge"]}, "components.planes[2]: edge is listed twice")

    def test_a_bad_plane_name_is_refused(self):
        self.refused({"planes": ["edge", "a b"]}, "components.planes[1]: must be a part name")

    def test_a_plane_that_is_not_a_string_is_refused(self):
        self.refused({"planes": [3]}, "components.planes[0]: must be a part name")

    def test_an_unknown_key_is_refused(self):
        self.refused({"planes": ["edge"], "extra": 1}, "components: unknown key 'extra'")

    def test_a_map_that_is_not_a_map_is_refused(self):
        self.refused(["edge"], "components: must be a map")

    def test_results_not_a_list_is_refused(self):
        self.refused({"planes": ["edge"], "results": "results"}, "components.results: must be a list")

    def test_an_absolute_result_is_refused(self):
        self.refused({"planes": ["edge"], "results": ["/results"]},
                     "components.results[0]: must be a plain relative path with no '..'")

    def test_a_drive_result_is_refused(self):
        self.refused({"planes": ["edge"], "results": ["C:/results"]},
                     "components.results[0]: must be a plain relative path with no '..'")

    def test_a_parent_result_is_refused(self):
        self.refused({"planes": ["edge"], "results": ["results", "../results"]},
                     "components.results[1]: must be a plain relative path with no '..'")

    def test_a_repeated_result_is_refused(self):
        self.refused({"planes": ["edge"], "results": ["results", "results"]},
                     "components.results[1]: results is listed twice")

    def test_results_may_be_left_out(self):
        p = Project(self, declaration={"planes": ["edge", "hub"]})
        p.put(good())
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_declaration_is_not_read_without_a_route(self):
        p = Project(self, declaration={"bogus": 1})
        del p.decl["files"]
        p.write_decl()
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "0"), r.stdout + r.stderr)

    def test_an_unknown_files_key_still_lists_components(self):
        p = Project(self)
        p.decl["files"] = {"nonsense": "x.yaml"}
        p.write_decl()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("components", r.stderr)


class CensusEvidence(unittest.TestCase):
    """A census key as the fourth evidence form."""

    S = "\u00a7"

    def render(self, status, evidence, census="GUIDE.md"):
        p = Project(self)
        if census is not None:
            p.decl["census"] = census
            p.write_decl()
            (p.root / census).write_text("# Guide\n", encoding="utf-8")
        comps = good()
        comps[0].update(status=status, evidence=evidence)
        p.put(comps)
        return p.render()

    def test_a_census_key_is_accepted(self):
        r = self.render("proposed", [f"{self.S}4p.3"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_accepted_is_satisfied_by_a_census_key_alone(self):
        r = self.render("accepted", [f"{self.S}4p.3"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_built_with_only_a_census_key_is_reported_not_refused(self):
        r = self.render("built", [f"{self.S}4p.3"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("components_test: components.yaml: components[0].evidence: built, but the only evidence is a "
                      "census key (no path:N)", r.stderr)

    def test_built_with_neither_form_still_refuses(self):
        r = self.render("built", ["ADR-0001"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("built needs a file and line", r.stderr)

    def test_built_with_a_line_and_a_census_key_is_neither_refused_nor_reported(self):
        r = self.render("built", ["src/depot_sync.py:2", f"{self.S}4p.3"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("built, but", r.stderr)

    def test_census_only_built_returns_the_ids(self):
        import alignment
        import components
        from unittest import mock
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
        comps = [
            {"id": "CO-001", "status": "built", "evidence": [f"{self.S}4.1"]},
            {"id": "CO-002", "status": "built", "evidence": ["src/depot_sync.py:2", f"{self.S}4.1"]},
            {"id": "CO-003", "status": "built", "evidence": ["ADR-0001"]},
            {"id": "CO-004", "status": "accepted", "evidence": [f"{self.S}4.1"]},
            {"id": "CO-005", "status": "built", "evidence": ["ADR-0001", f"other-member {self.S}2"]},
        ]
        with mock.patch.object(alignment.declared, "census_file", return_value="GUIDE.md"):
            (tmp / "GUIDE.md").write_text("# Guide\n", encoding="utf-8")
            ctx = alignment.Context("components_test", ["ADR-0001"], tmp)
            self.assertEqual(components.census_only_built(comps, ctx), ("CO-001", "CO-005"))

    def test_a_path_other_than_the_census_is_accepted(self):
        r = self.render("proposed", [f"OTHER.md {self.S}4.1"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_census_is_refused_at_the_evidence(self):
        r = self.render("proposed", [f"{self.S}4.1"], census=None)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("components[0].evidence[0]: ", r.stderr)
        self.assertIn("declares no census (census:)", r.stderr)


if __name__ == "__main__":
    unittest.main()
