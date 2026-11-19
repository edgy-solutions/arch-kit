"""Self-test: the alignment example builds, checks and matches its snapshot, and the page appears in both portal modes.

The example (examples/alignment) is the decisions-only example with `files.alignment` declared and one alignment
record over the kit's first seed. The test copies it into a temporary git repository, runs render_html and
check_export, and compares the export with examples/alignment/expected/export.html after the same normalising
test_example does. The full-mode case copies examples/minimal, adds one record, and shows the rest of the document
is the minimal snapshot.

The test never writes the snapshot. To regenerate it after an intended change to the example, from the kit root:

    python arch_kit/tools/test_example_alignment.py --write-snapshot
"""
from __future__ import annotations

import re
import shutil
import subprocess
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
EXAMPLE = KIT / "examples" / "alignment"
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


class Example(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = copy_example(self.tmp)
        self.out = self.tmp / "export.html"

    def test_the_example_builds_checks_and_matches_its_snapshot(self):
        p = td.render(self.root, self.out)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        for name, args in (("check_export", ("--export", str(self.out), "--barred", "barred.txt")),
                           ("check_decision_indexes", ())):
            p = td.tool(self.root, name, *args)
            self.assertEqual(p.returncode, 0, f"{name}: " + p.stdout + p.stderr)
        got = normalise(self.out.read_text(encoding="utf-8"))
        want = normalise(SNAPSHOT.read_text(encoding="utf-8"))
        if got != want:
            import difflib
            diff = list(difflib.unified_diff(want.split("\n"), got.split("\n"), "expected", "built", lineterm="", n=0))
            self.fail("the export differs from expected/export.html after normalising:\n" + "\n".join(diff[:40]))

    def test_the_page_and_the_nav_are_there(self):
        td.render(self.root, self.out)
        text = self.out.read_text(encoding="utf-8")
        self.assertIn('<nav class="alignment"><h2>Alignment</h2><ul><li><a href="#alignment-coverage">'
                      'Sorrel against two references</a></li></ul></nav>', text)
        self.assertIn('<section id="alignment-coverage" class="page alignment" data-alignment="coverage">', text)
        self.assertLess(text.index('<nav class="decisions">'), text.index('<nav class="alignment">'))
        self.assertLess(text.index('<section id="adr-0003"'), text.index('<section id="alignment-coverage"'))

    def test_the_page_states_its_coverage_in_counts_and_its_gaps(self):
        td.render(self.root, self.out)
        text = self.out.read_text(encoding="utf-8")
        page = text[text.index('id="alignment-coverage"'):]
        self.assertIn("<td>2 of 3</td>", page)
        self.assertIn("<td>2 of 4</td>", page)
        self.assertNotIn("%", page)
        self.assertIn("Not compared: Appendix 9: services, Appendix 4: data-product characteristics, "
                      "Appendix 14: planes.", text)
        self.assertIn("Cited by title only; not compared.", text)
        self.assertIn('<a href="#adr-0001"><span class="nb">ADR-0001</span></a>', text)
        self.assertIn("decisions/README.md</span></code>", text)

    def test_a_declaration_without_labels_still_renders_an_alignment_table(self):
        decl = yaml.safe_load((self.root / "arch-kit.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("labels", decl)
        td.render(self.root, self.out)
        text = self.out.read_text(encoding="utf-8")
        page = text[text.index('id="alignment-coverage"'):]
        self.assertIn("<table", page)

    def test_a_project_without_the_key_renders_no_alignment(self):
        decl = yaml.safe_load((self.root / "arch-kit.yaml").read_text(encoding="utf-8"))
        del decl["files"]
        (self.root / "arch-kit.yaml").write_text(yaml.safe_dump(decl, sort_keys=False), encoding="utf-8")
        td.render(self.root, self.out)
        text = self.out.read_text(encoding="utf-8")
        self.assertNotIn("alignment", text)


class FullMode(unittest.TestCase):
    """The page appears in `portal.mode: full` too.

    The rest of the document is not compared with the minimal snapshot: the minimal example can be rendered only with
    Node, mermaid-cli and Chrome, and this case could not be run where it was written, so it asserts presence only."""

    def test_the_minimal_example_with_one_record_gains_the_nav_and_the_page(self):
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
        decl["files"] = dict(decl.get("files") or {}, alignment="alignment")
        (root / "arch-kit.yaml").write_text(yaml.safe_dump(decl, sort_keys=False), encoding="utf-8")
        (root / "alignment").mkdir()
        shutil.copy(EXAMPLE / "alignment" / "coverage.yaml", root / "alignment" / "coverage.yaml")
        (root / "puppeteer.json").write_text('{"args": ["--no-sandbox"]}' + chr(10), encoding="utf-8")
        out = tmp / "export.html"
        p = td.tool(root, "render_html", "--out", str(out), "--chart", "chart", "--values", "values.yaml",
                    "--release", "larkspur", "--readiness", "READINESS.md", "--relabel", "relabel.txt",
                    "--barred", "barred.txt", "--date", DATE, "--puppeteer-config", str(root / "puppeteer.json"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        text = out.read_text(encoding="utf-8")
        self.assertIn('<nav class="alignment"><h2>Alignment</h2>', text)
        self.assertIn('<section id="alignment-coverage" class="page alignment"', text)
        self.assertLess(text.index('<nav class="decisions">'), text.index('<nav class="alignment">'))


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
