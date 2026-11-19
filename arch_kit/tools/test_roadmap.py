"""Self-test: the roadmap record: the schema, the checks, both routes, and the roadmap note.

Each case builds a project in a temporary directory from examples/decisions-only, adds `files.roadmap` (or a loader
that defines `load_roadmap`), puts increments in the file and loads them in a subprocess (the declaration is read once
per process). An accepted list exits 0; a refused one exits 2 and its message names the increment and the key. The
example declares `registers.roadmap` as a note that does not exist; a case that creates the note is refused.
"""
from __future__ import annotations

import copy
import datetime
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

from test_example_decisions import copy_example  # noqa: E402

LOADER_TAIL = '''

def load_roadmap(root):
    import yaml
    return yaml.safe_load((Path(root) / "records.yaml").read_text(encoding="utf-8"))["roadmap"]
'''


def inc(n: int, **over) -> dict:
    r = {"id": f"RM-{n:03d}", "increment": f"step-{n}", "isolates": "whether a locker works offline",
         "home": "ADR-0001", "depends_on": [], "status": "proposed"}
    r.update(over)
    return r


GOOD = [
    inc(1, status="measured", home="ADR-0001"),
    inc(2, status="built", home="ADR-0002", depends_on=["RM-001"]),
    inc(3, status="accepted", home="other:ADR-0007", depends_on=["RM-001", "RM-002"]),
    {"id": "RM-004", "increment": "step-4", "isolates": "whether returns reach the depot", "depends_on": ["RM-003"],
     "status": "proposed"},
]


def good() -> list:
    return copy.deepcopy(GOOD)


class Project:
    """A temporary project built from the decisions-only example, with the roadmap by one route or the other."""

    def __init__(self, test: unittest.TestCase, route: str = "file", declare: bool = True):
        self.tmp = Path(tempfile.mkdtemp())
        test.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = copy_example(self.tmp)
        self.route = route
        decl = yaml.safe_load((self.root / "arch-kit.yaml").read_text(encoding="utf-8"))
        decl["decisions"]["index"]["foreign"] = [{"prefix": "other"}]
        if declare and route == "file":
            decl["files"] = {"roadmap": "roadmap.yaml"}
        elif declare:
            decl["loader"] = "roadmap_loader.py"
            text = (self.root / "kit_loader.py").read_text(encoding="utf-8")
            (self.root / "roadmap_loader.py").write_text(text + LOADER_TAIL, encoding="utf-8")
        self.decl = decl
        self.write_decl()

    def write_decl(self):
        (self.root / "arch-kit.yaml").write_text(yaml.safe_dump(self.decl, sort_keys=False), encoding="utf-8")

    def put(self, items) -> None:
        name = "roadmap.yaml" if self.route == "file" else "records.yaml"
        (self.root / name).write_text(yaml.safe_dump({"roadmap": items}, sort_keys=False), encoding="utf-8")

    def note(self, name: str = "ROADMAP.md") -> None:
        (self.root / "decisions" / name).write_text("# Roadmap\n", encoding="utf-8")

    def render(self):
        return load_in(self.root, "arch-kit.yaml")


LOAD = '''
import sys
sys.path.insert(0, {tools!r})
import roadmap
from data_exchange import InputError
try:
    print({show})
except InputError as e:
    print(f"error: {{e}}", file=sys.stderr)
    sys.exit(2)
'''
COUNT = 'len(roadmap.load("roadmap_test", ["ADR-0001", "ADR-0002", "ADR-0003"]))'
IDS = '",".join(r["id"] for r in roadmap.load("roadmap_test", ["ADR-0001", "ADR-0002", "ADR-0003"]))'


def load_in(root: Path, decl: str, show: str = COUNT) -> subprocess.CompletedProcess:
    env = dict(os.environ, ARCH_KIT_CONFIG=str(root / decl), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-c", LOAD.format(tools=str(HERE), show=show)], cwd=root, env=env,
                          capture_output=True, text=True, encoding="utf-8")


def message(stderr: str) -> str:
    return [ln for ln in stderr.splitlines() if ln.strip()][-1]


def mut(fn):
    def apply(items):
        fn(items)
        return items
    return apply


ID_WHY = "must be RM- then capitals, digits and hyphens"
LINE_WHY = "must be one non-empty line"
DATE_WHY = "is a date; a roadmap carries no dates"
NO_DATES = "a roadmap carries no dates"
REQUIRED = ("id", "increment", "isolates", "depends_on", "status")
DAY = datetime.date(2026, 11, 19)

# (name, change to the good increments, text the message holds)
REFUSED = [
    # the schema
    ("empty list", mut(lambda c: c.clear()), "roadmap: must list at least one increment"),
    ("unknown key", mut(lambda c: c[1].update(extra=1)), "roadmap.1.extra: unknown key"),
    ("a date key", mut(lambda c: c[1].update(date=DAY)), "roadmap.1.date: unknown key"),
    ("a due key", mut(lambda c: c[1].update(due="soon")), "roadmap.1.due: unknown key"),
    ("bad id", mut(lambda c: c[0].update(id="RM-trace")), f"roadmap.0.id: {ID_WHY}"),
    ("id without a body", mut(lambda c: c[0].update(id="RM-")), f"roadmap.0.id: {ID_WHY}"),
    ("lower case id", mut(lambda c: c[0].update(id="rm-001")), f"roadmap.0.id: {ID_WHY}"),
    ("double hyphen in id", mut(lambda c: c[0].update(id="RM--A")), f"roadmap.0.id: {ID_WHY}"),
    ("trailing hyphen in id", mut(lambda c: c[0].update(id="RM-A-")), f"roadmap.0.id: {ID_WHY}"),
    ("underscore in id", mut(lambda c: c[0].update(id="RM-A_B")), f"roadmap.0.id: {ID_WHY}"),
    ("id with a newline", mut(lambda c: c[0].update(id="RM-A\nB")), f"roadmap.0.id: {ID_WHY}"),
    ("id with a trailing newline", mut(lambda c: c[0].update(id="RM-A\n")), f"roadmap.0.id: {ID_WHY}"),
    ("two lines in increment", mut(lambda c: c[0].update(increment="a\nb")), f"roadmap.0.increment: {LINE_WHY}"),
    ("blank increment", mut(lambda c: c[0].update(increment=" ")), f"roadmap.0.increment: {LINE_WHY}"),
    ("empty increment", mut(lambda c: c[0].update(increment="")), f"roadmap.0.increment: {LINE_WHY}"),
    ("two lines in isolates", mut(lambda c: c[0].update(isolates="a\r\nb")), f"roadmap.0.isolates: {LINE_WHY}"),
    ("blank isolates", mut(lambda c: c[0].update(isolates="  ")), f"roadmap.0.isolates: {LINE_WHY}"),
    ("empty isolates", mut(lambda c: c[0].update(isolates="")), f"roadmap.0.isolates: {LINE_WHY}"),
    ("two lines in home", mut(lambda c: c[0].update(home="ADR-0001\nx")), f"roadmap.0.home: {LINE_WHY}"),
    ("blank home", mut(lambda c: c[0].update(home=" ")), f"roadmap.0.home: {LINE_WHY}"),
    ("depends_on not a list", mut(lambda c: c[1].update(depends_on="RM-001")), "roadmap.1.depends_on:"),
    ("bad id in depends_on", mut(lambda c: c[1].update(depends_on=["rm-001"])), f"roadmap.1.depends_on.0: {ID_WHY}"),
    ("second depends_on item bad", mut(lambda c: c[2].update(depends_on=["RM-001", "x"])),
     f"roadmap.2.depends_on.1: {ID_WHY}"),
    ("depends_on item with a newline", mut(lambda c: c[1].update(depends_on=["RM-001\nx"])),
     f"roadmap.1.depends_on.0: {ID_WHY}"),
    ("status outside the enum", mut(lambda c: c[0].update(status="done")), "roadmap.0.status:"),
    # a YAML date where a string is expected
    ("date as id", mut(lambda c: c[0].update(id=DAY)), f"roadmap.0.id: {DATE_WHY}"),
    ("date as increment", mut(lambda c: c[0].update(increment=DAY)), f"roadmap.0.increment: {DATE_WHY}"),
    ("date as isolates", mut(lambda c: c[0].update(isolates=DAY)), f"roadmap.0.isolates: {DATE_WHY}"),
    ("date as home", mut(lambda c: c[0].update(home=DAY)), f"roadmap.0.home: {DATE_WHY}"),
    ("date in depends_on", mut(lambda c: c[1].update(depends_on=[DAY])), f"roadmap.1.depends_on.0: {DATE_WHY}"),
] + [(f"no {k}", mut(lambda c, k=k: c[2].pop(k)), f"roadmap.2.{k}: is required") for k in REQUIRED] + [
    # the checks
    ("duplicate id", mut(lambda c: c[1].update(id="RM-001")), "roadmap[1].id: increment id RM-001 is not unique"),
    ("duplicate increment", mut(lambda c: c[1].update(increment="step-1")),
     "roadmap[1].increment: increment step-1 is not unique"),
    ("year-month in increment", mut(lambda c: c[0].update(increment="Ship 2026-11")),
     f"roadmap[0].increment: {NO_DATES}"),
    ("date in increment", mut(lambda c: c[0].update(increment="Ship 2026-11-19 or so")),
     f"roadmap[0].increment: {NO_DATES}"),
    ("date in isolates", mut(lambda c: c[1].update(isolates="by 2027-01-05")), f"roadmap[1].isolates: {NO_DATES}"),
    ("year-month in isolates", mut(lambda c: c[2].update(isolates="(2026-12)")), f"roadmap[2].isolates: {NO_DATES}"),
    ("duplicate depends_on", mut(lambda c: c[2].update(depends_on=["RM-001", "RM-001"])),
     "roadmap[2].depends_on: RM-001 is listed twice"),
    ("depends on itself", mut(lambda c: c[1].update(depends_on=["RM-002"])),
     "roadmap[1].depends_on[0]: an increment cannot depend on itself"),
    ("depends on itself, second item", mut(lambda c: c[2].update(depends_on=["RM-001", "RM-003"])),
     "roadmap[2].depends_on[1]: an increment cannot depend on itself"),
    ("depends on a later one", mut(lambda c: c[0].update(depends_on=["RM-002"])),
     "roadmap[0].depends_on[0]: RM-002 comes later; an increment depends only on earlier ones"),
    ("depends on the last one", mut(lambda c: c[1].update(depends_on=["RM-001", "RM-004"])),
     "roadmap[1].depends_on[1]: RM-004 comes later; an increment depends only on earlier ones"),
    ("depends on nothing in the list", mut(lambda c: c[1].update(depends_on=["RM-009"])),
     "roadmap[1].depends_on[0]: RM-009 is not an increment id"),
    ("a two-step cycle", mut(lambda c: (c[0].update(depends_on=["RM-002"]), c[1].update(depends_on=["RM-001"]))),
     "roadmap[0].depends_on[0]: RM-002 comes later; an increment depends only on earlier ones"),
    ("measured without a home", mut(lambda c: c[0].pop("home")),
     "roadmap[0].home: is required unless the status is proposed"),
    ("built without a home", mut(lambda c: c[1].pop("home")),
     "roadmap[1].home: is required unless the status is proposed"),
    ("accepted without a home", mut(lambda c: c[2].pop("home")),
     "roadmap[2].home: is required unless the status is proposed"),
    ("unresolved home", mut(lambda c: c[0].update(home="ADR-0099")),
     "roadmap[0].home: ADR-0099 does not resolve to a decision record"),
    ("undeclared foreign prefix", mut(lambda c: c[0].update(home="nowhere:ADR-0007")),
     "roadmap[0].home: nowhere:ADR-0007 does not resolve to a decision record"),
    ("a path is not a decision record", mut(lambda c: c[0].update(home="decisions")),
     "roadmap[0].home: decisions does not resolve to a decision record"),
    ("a proposed increment with an unresolved home", mut(lambda c: c[3].update(home="ADR-0099")),
     "roadmap[3].home: ADR-0099 does not resolve to a decision record"),
    # each check runs over every increment before the next starts
    ("a repeated id comes before a missing home", mut(lambda c: (c[0].pop("home"), c[3].update(id="RM-001"))),
     "roadmap[3].id: increment id RM-001 is not unique"),
    ("a date in text comes before a repeated depends_on",
     mut(lambda c: (c[1].update(depends_on=["RM-001", "RM-001"]), c[3].update(isolates="2026-11"))),
     f"roadmap[3].isolates: {NO_DATES}"),
    ("a repeated depends_on comes before an unknown one",
     mut(lambda c: (c[1].update(depends_on=["RM-009"]), c[3].update(depends_on=["RM-003", "RM-003"]))),
     "roadmap[3].depends_on: RM-003 is listed twice"),
    ("an unknown dependency comes before a missing home", mut(lambda c: (c[0].pop("home"), c[3].update(depends_on=["RM-009"]))),
     "roadmap[3].depends_on[0]: RM-009 is not an increment id"),
]


class Routes(unittest.TestCase):
    def test_the_file_route_is_accepted(self):
        p = Project(self)
        p.put(good())
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "4"), r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")

    def test_the_loader_route_is_accepted(self):
        p = Project(self, "loader")
        p.put(good())
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "4"), r.stdout + r.stderr)

    def test_both_declared_is_refused(self):
        p = Project(self)
        p.put(good())
        text = (p.root / "kit_loader.py").read_text(encoding="utf-8")
        (p.root / "roadmap_loader.py").write_text(text + LOADER_TAIL, encoding="utf-8")
        p.decl["loader"] = "roadmap_loader.py"
        p.write_decl()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("files.roadmap: is declared, and the loader also defines load_roadmap; use one route", r.stderr)

    def test_neither_declared_gives_nothing(self):
        p = Project(self, declare=False)
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "0"), r.stdout + r.stderr)

    def test_a_loader_without_load_roadmap_and_no_file_gives_nothing(self):
        p = Project(self, declare=False)
        p.decl["loader"] = "kit_loader.py"
        p.write_decl()
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "0"), r.stdout + r.stderr)

    def test_file_order_is_kept(self):
        for route in ("file", "loader"):
            with self.subTest(route=route):
                p = Project(self, route)
                items = good()
                for r in items:
                    r["depends_on"] = []
                items.reverse()
                p.put(items)
                r = load_in(p.root, "arch-kit.yaml", IDS)
                self.assertEqual(r.stdout.strip(), "RM-004,RM-003,RM-002,RM-001", r.stdout + r.stderr)

    def test_wider_ids_are_accepted(self):
        for rid in ("RM-001", "RM-1", "RM-TRACE", "RM-PT-PUBLISH"):
            with self.subTest(id=rid):
                p = Project(self)
                items = good()
                items[0]["id"] = rid
                items[1]["depends_on"] = [rid]
                items[2]["depends_on"] = [rid, "RM-002"]
                p.put(items)
                r = p.render()
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_single_increment_with_no_dependencies_is_accepted(self):
        p = Project(self)
        p.put([inc(1)])
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "1"), r.stdout + r.stderr)

    def test_a_file_that_is_not_a_map_with_roadmap_is_refused(self):
        p = Project(self)
        (p.root / "roadmap.yaml").write_text(yaml.safe_dump(good()), encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_a_top_level_unknown_key_is_refused(self):
        p = Project(self)
        (p.root / "roadmap.yaml").write_text(yaml.safe_dump({"roadmap": good(), "more": 1}), encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("more: unknown key", r.stderr)

    def test_a_loader_that_returns_a_map_is_refused(self):
        p = Project(self, "loader")
        (p.root / "records.yaml").write_text(yaml.safe_dump({"roadmap": {"a": 1}}), encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("load_roadmap must return a list of increments", r.stderr)

    def test_an_unreadable_file_is_refused(self):
        p = Project(self)
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("roadmap.yaml: (record): cannot be read", r.stderr)

    def test_bad_yaml_is_refused(self):
        p = Project(self)
        (p.root / "roadmap.yaml").write_text("roadmap: [a: b: c\n", encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("roadmap.yaml: (record): not valid YAML", r.stderr)

    def test_the_error_names_the_file(self):
        p = Project(self)
        items = good()
        items[0]["id"] = "x"
        p.put(items)
        r = p.render()
        self.assertRegex(message(r.stderr), r"^error: roadmap\.yaml: roadmap\.0\.id: ")

    def test_an_unquoted_date_in_the_file_is_refused(self):
        p = Project(self)
        (p.root / "roadmap.yaml").write_text(
            "roadmap:\n  - id: RM-001\n    increment: 2026-11-19\n    isolates: x\n    home: ADR-0001\n"
            "    depends_on: []\n    status: built\n", encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(f"roadmap.yaml: roadmap.0.increment: {DATE_WHY}", message(r.stderr))


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
                        self.assertRegex(message(r.stderr), r"^error: load_roadmap: ")


class Home(unittest.TestCase):
    def accepted(self, **over):
        p = Project(self)
        items = good()
        items[0].update(over)
        p.put(items)
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_local_decision_is_accepted(self):
        self.accepted(home="ADR-0003")

    def test_a_foreign_decision_is_accepted(self):
        self.accepted(home="other:ADR-0007")

    def test_absent_is_accepted_when_proposed(self):
        p = Project(self)
        items = good()
        items[0].pop("home")
        items[0]["status"] = "proposed"
        p.put(items)
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_absent_is_refused_for_each_other_status(self):
        for status in ("measured", "built", "accepted"):
            with self.subTest(status=status):
                p = Project(self)
                items = good()
                items[3]["status"] = status
                p.put(items)
                r = p.render()
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("roadmap[3].home: is required unless the status is proposed", message(r.stderr))


class Note(unittest.TestCase):
    """The record and the roadmap note are one roadmap, not two."""

    WHY = "files.roadmap: is declared, and the roadmap note decisions/ROADMAP.md exists; use one"

    def test_the_file_route_with_the_note_is_refused(self):
        p = Project(self)
        p.put(good())
        p.note()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(self.WHY, r.stderr)

    def test_the_loader_route_with_the_note_is_refused(self):
        p = Project(self, "loader")
        p.put(good())
        p.note()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(self.WHY, r.stderr)

    def test_the_note_is_refused_before_the_record_is_read(self):
        p = Project(self)
        p.note()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(self.WHY, r.stderr)
        self.assertNotIn("cannot be read", r.stderr)

    def test_the_message_names_the_declared_note(self):
        p = Project(self)
        p.decl["registers"]["roadmap"] = "PLAN.md"
        p.write_decl()
        p.put(good())
        p.note("PLAN.md")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("files.roadmap: is declared, and the roadmap note decisions/PLAN.md exists; use one", r.stderr)

    def test_a_declared_note_that_does_not_exist_is_accepted(self):
        for route in ("file", "loader"):
            with self.subTest(route=route):
                p = Project(self, route)
                self.assertEqual(p.decl["registers"]["roadmap"], "ROADMAP.md")
                self.assertFalse((p.root / "decisions" / "ROADMAP.md").exists())
                p.put(good())
                r = p.render()
                self.assertEqual((r.returncode, r.stdout.strip()), (0, "4"), r.stdout + r.stderr)

    def test_an_undeclared_register_means_no_note(self):
        p = Project(self)
        del p.decl["registers"]["roadmap"]
        p.write_decl()
        p.put(good())
        p.note()
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "4"), r.stdout + r.stderr)

    def test_no_route_with_the_note_is_unchanged(self):
        p = Project(self, declare=False)
        p.note()
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "0"), r.stdout + r.stderr)

    def test_a_note_named_by_the_other_register_is_not_the_roadmap_note(self):
        p = Project(self)
        p.put(good())
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((p.root / "decisions" / "FOLLOW-UPS.md").is_file())


class Declaration(unittest.TestCase):
    def test_an_unknown_files_key_still_lists_roadmap(self):
        p = Project(self)
        p.decl["files"] = {"nonsense": "x.yaml"}
        p.write_decl()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("roadmap", r.stderr)

    def test_an_absolute_roadmap_path_is_refused(self):
        p = Project(self)
        p.decl["files"] = {"roadmap": "/roadmap.yaml"}
        p.write_decl()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("files.roadmap: must be a plain relative path with no '..'", r.stderr)


if __name__ == "__main__":
    unittest.main()
