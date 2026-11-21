"""Self-test: the flows example builds, checks and matches its snapshot, and the page and its lists appear.

The example (examples/flows) is the decisions-only example with `files.flows` declared: three decision records and four
flows, one built and one that no decision record covers. The test copies it into a temporary git repository, runs
render_html and check_export, and compares the export with examples/flows/expected/export.html after the same
normalising test_example does. The full-mode case copies examples/minimal and adds flows that name capabilities.

The test never writes the snapshot. To regenerate it after an intended change to the example, from the kit root:

    python arch_kit/tools/test_example_flows.py --write-snapshot
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import test_example_decisions as td  # noqa: E402
from test_example import normalise  # noqa: E402

KIT = td.KIT
EXAMPLE = KIT / "examples" / "flows"
SNAPSHOT = EXAMPLE / "expected" / "export.html"
MINIMAL = KIT / "examples" / "minimal"
DATE = td.DATE


def copy_example(tmp: Path) -> Path:
    root = tmp / "proj"
    shutil.copytree(EXAMPLE, root, ignore=shutil.ignore_patterns("expected", "__pycache__"))
    td.git(root, "init", "-q")
    td.git(root, "add", ".")
    td.git(root, "commit", "-q", "-m", "example")
    return root


def edit_flows(root: Path, change) -> None:
    f = root / "flows.yaml"
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    change(data["flows"])
    f.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def page(text: str, pid: str) -> str:
    start = text.index(f'<section id="{pid}"')
    return text[start:text.index("</section>", start)]


class Example(td.BrowserCase, unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = copy_example(self.tmp)
        self.out = self.tmp / "export.html"

    def build(self) -> str:
        p = td.render(self.root, self.out)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return self.out.read_text(encoding="utf-8")

    def test_the_example_builds_checks_and_matches_its_snapshot(self):
        self.build()
        for name, args in (("check_export", ("--export", str(self.out), "--barred", "barred.txt")),
                           ("check_decision_indexes", ())):
            p = td.tool(self.root, name, *args)
            self.assertEqual(p.returncode, 0, f"{name}: " + p.stdout + p.stderr)
            if name == "check_export":
                self.assertIn("4 flows; ", p.stdout)
        got = normalise(self.out.read_text(encoding="utf-8"))
        want = normalise(SNAPSHOT.read_text(encoding="utf-8"))
        if got != want:
            import difflib
            diff = list(difflib.unified_diff(want.split("\n"), got.split("\n"), "expected", "built", lineterm="", n=0))
            self.fail("the export differs from expected/export.html after normalising:\n" + "\n".join(diff[:40]))

    def test_the_page_the_rows_and_the_nav(self):
        text = self.build()
        self.assertIn('<section id="flows" class="page flows" data-flows><h1>Teasel: Flows</h1>', text)
        self.assertEqual(re.findall(r'<tr data-flow="([^"]+)"', text), ["FL-001", "FL-002", "FL-003", "FL-004"])
        self.assertIn('<nav class="flows"><h2>Flows</h2><ul><li><a href="#flows">Flows (4)</a></li></ul></nav>', text)
        self.assertLess(text.index('<nav class="decisions">'), text.index('<nav class="flows">'))
        self.assertLess(text.index('<section id="adr-0003"'), text.index('<section id="flows"'))
        flows = page(text, "flows")
        self.assertIn('<a href="#adr-0002"><span class="nb">ADR-0002</span></a>', flows)
        self.assertIn("Not built", flows)
        self.assertIn(">Built<", flows)
        self.assertNotIn("%", flows)

    def test_the_count_line(self):
        text = self.build()
        self.assertIn('<p class="flow-count" data-flow-count>4 flows: 1 built, 3 not built; '
                      '1 with no decision record.</p>', text)

    def test_the_gap_list_is_there_and_is_gone_when_every_flow_has_a_decision(self):
        text = self.build()
        flows = page(text, "flows")
        self.assertIn("<h2>Flows no decision record covers</h2><ul><li>FL-004: ledger → intake</li></ul>", flows)
        edit_flows(self.root, lambda f: f[3].update(decided_by=["ADR-0001"]))
        text = self.build()
        self.assertNotIn("Flows no decision record covers", text)
        self.assertIn("4 flows: 1 built, 3 not built; 0 with no decision record.", text)

    def test_the_list_is_on_exactly_the_records_that_decide_a_flow(self):
        text = self.build()
        for pid, ids in (("adr-0001", ["FL-001"]), ("adr-0002", ["FL-002", "FL-003"]), ("adr-0003", ["FL-002"])):
            block = re.findall(r'<div class="flows-decided" data-flows-decided>(.*?)</div>', page(text, pid), re.S)
            self.assertEqual(len(block), 1, pid)
            self.assertIn("<h2>Flows this record decides</h2>", block[0])
            self.assertEqual(re.findall(r'<a href="#flows">(FL-[A-Z0-9-]+):', block[0]), ids, pid)
            body = page(text, pid)
            self.assertLess(body.index("data-flows-decided"), body.index('<div class="provenance"'))
        self.assertIn('<a href="#flows">FL-002: depot → ledger (receipt.v1)</a>', page(text, "adr-0003"))
        edit_flows(self.root, lambda f: f[1].update(decided_by=["ADR-0002"]))
        text = self.build()
        self.assertNotIn("data-flows-decided", page(text, "adr-0003"))
        self.assertIn("data-flows-decided", page(text, "adr-0002"))

    def test_a_foreign_decision_id_is_plain_text(self):
        decl = yaml.safe_load((self.root / "arch-kit.yaml").read_text(encoding="utf-8"))
        decl["decisions"]["index"]["foreign"] = [{"prefix": "other"}]
        (self.root / "arch-kit.yaml").write_text(yaml.safe_dump(decl, sort_keys=False), encoding="utf-8")
        edit_flows(self.root, lambda f: f[3].update(decided_by=["other:ADR-0007"]))
        text = self.build()
        self.assertIn("other:ADR-0007", page(text, "flows"))
        self.assertNotIn('href="#other', text)
        self.assertIn("0 with no decision record.", text)

    def test_a_project_without_the_key_renders_no_flows(self):
        decl = yaml.safe_load((self.root / "arch-kit.yaml").read_text(encoding="utf-8"))
        del decl["files"]
        (self.root / "arch-kit.yaml").write_text(yaml.safe_dump(decl, sort_keys=False), encoding="utf-8")
        text = self.build()
        for needle in ("data-flows", "data-flow", 'class="flows"', "flow-count", "flows-decided", "nav.flows"):
            self.assertNotIn(needle, text)


class Check(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = copy_example(self.tmp)
        self.out = self.tmp / "export.html"
        p = td.render(self.root, self.out)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.text = self.out.read_text(encoding="utf-8")

    def check(self, text: str):
        self.out.write_text(text, encoding="utf-8", newline="\n")
        return td.check(self.root, self.out)

    def test_a_passing_export(self):
        p = self.check(self.text)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("; 4 flows; ", p.stdout)

    def test_a_missing_row_fails(self):
        text = re.sub(r'<tr data-flow="FL-003">.*?</tr>', "", self.text, count=1, flags=re.S)
        p = self.check(text)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("FAIL: flows: the page has 3 data-flow rows, the record 4; missing FL-003", p.stderr)

    def test_rows_in_another_order_fail(self):
        text = self.text.replace('data-flow="FL-001"', 'data-flow="FL-00x"').replace('data-flow="FL-002"', 'data-flow="FL-001"')
        text = text.replace('data-flow="FL-00x"', 'data-flow="FL-002"')
        p = self.check(text)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("same ids, different order", p.stderr)

    def test_a_wrong_count_line_fails(self):
        p = self.check(self.text.replace("1 built, 3 not built", "2 built, 2 not built"))
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("FAIL: flows: the count line says 4, 2, 2, 1", p.stderr)

    def test_a_second_flows_page_fails(self):
        start = self.text.index('<section id="flows"')
        end = self.text.index("</section>", start) + len("</section>")
        text = self.text[:end] + "\n" + self.text[start:end].replace('id="flows"', 'id="flows2"') + self.text[end:]
        p = self.check(text)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("FAIL: flows: the export has 2 flows pages, expected one", p.stderr)

    def test_no_flows_page_fails(self):
        start = self.text.index('<section id="flows"')
        end = self.text.index("</section>", start) + len("</section>")
        text = self.text[:start] + self.text[end:]
        p = self.check(text.replace('<a href="#flows">Flows (4)</a>', "Flows (4)"))
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("FAIL: flows: the export has 0 flows pages", p.stderr)


class FullMode(unittest.TestCase):
    """Flows that name capabilities, in `portal.mode: full`. It needs the diagram tools, as test_example does."""

    def test_a_capability_page_lists_its_flows_and_the_row_links_to_it(self):
        import test_example
        reason = test_example.missing()
        if reason:
            self.skipTest(reason)
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        root = tmp / "proj"
        shutil.copytree(MINIMAL, root, ignore=shutil.ignore_patterns("expected", "__pycache__"))
        td.git(root, "init", "-q")
        td.git(root, "add", ".")
        td.git(root, "commit", "-q", "-m", "example")
        decl = yaml.safe_load((root / "arch-kit.yaml").read_text(encoding="utf-8"))
        decl["files"] = dict(decl.get("files") or {}, flows="flows.yaml")
        (root / "arch-kit.yaml").write_text(yaml.safe_dump(decl, sort_keys=False), encoding="utf-8")
        flows = [{"id": "FL-001", "from": "capability:ParcelIntake", "to": "depot", "carries": "parcel.v1",
                  "via": "broker/parcels", "decided_by": ["ADR-0001"], "built": True},
                 {"id": "FL-002", "from": "depot", "to": "capability:ParcelRouting", "carries": "route.v1",
                  "via": "queue/routes", "decided_by": [], "built": False}]
        (root / "flows.yaml").write_text(yaml.safe_dump({"flows": flows}, sort_keys=False), encoding="utf-8")
        (root / "puppeteer.json").write_text('{"args": ["--no-sandbox"]}' + chr(10), encoding="utf-8")
        out = tmp / "export.html"
        p = td.tool(root, "render_html", "--out", str(out), "--chart", "chart", "--values", "values.yaml",
                    "--release", "larkspur", "--readiness", "READINESS.md", "--relabel", "relabel.txt",
                    "--barred", "barred.txt", "--date", DATE, "--puppeteer-config", str(root / "puppeteer.json"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        text = out.read_text(encoding="utf-8")
        intake = page(text, "cap-ParcelIntake")
        self.assertIn('<div class="flows-capability" data-flows-capability><h2>Flows</h2>', intake)
        self.assertIn('<a href="#flows">FL-001: capability:ParcelIntake → depot (parcel.v1)</a>', intake)
        self.assertNotIn("FL-002", intake)
        self.assertIn("FL-002", page(text, "cap-ParcelRouting"))
        table = page(text, "flows")
        self.assertIn('<a href="#cap-ParcelIntake">', table)
        self.assertIn('<a href="#cap-ParcelRouting">', table)
        self.assertIn('<nav class="flows">', text)
        p = td.tool(root, "check_export", "--export", str(out), "--barred", "barred.txt", "--relabel", "relabel.txt")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("2 flows; ", p.stdout)


def write_snapshot() -> int:
    with tempfile.TemporaryDirectory() as t:
        root = copy_example(Path(t))
        out = Path(t) / "export.html"
        for p in (td.render(root, out), td.check(root, out)):
            if p.returncode:
                print(p.stdout + p.stderr, file=sys.stderr)
                return 1
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(normalise(out.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    print(f"wrote {SNAPSHOT}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-snapshot"]:
        sys.exit(write_snapshot())
    unittest.main()
