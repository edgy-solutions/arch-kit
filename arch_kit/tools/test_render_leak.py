"""Tests that the render relabels the finished HTML and refuses to write a file that still leaks. All values are made up.

The document is a small fixed string handed to render_html.main in place of a full assembly (which needs a chart and
a diagram renderer); the final pass, the scan, the exit code and the write are the real ones.
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))

import relabel  # noqa: E402
import render_html  # noqa: E402

NAME = "zebra-host-9"
BARRED = "quux-secret-77"


class Render(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.rules = self.tmp / "rules.txt"
        self.rules.write_text(f"{NAME}\tthe lab\n", encoding="utf-8", newline="\n")
        self.barred = self.tmp / "barred.txt"
        self.barred.write_text(f"{BARRED}\n", encoding="utf-8", newline="\n")
        self.out = self.tmp / "out" / "export.html"

    def run_main(self, doc, *extra):
        argv = ["--out", str(self.out), "--chart", ".", "--values", "v.yaml", "--release", "r", *extra]
        err = io.StringIO()
        rules = relabel.load([self.rules])
        with mock.patch.object(render_html, "assemble", return_value=(doc, rules)), \
                mock.patch.object(render_html, "make_mmdc", return_value=None), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            rc = render_html.main(argv)
        return rc, err.getvalue()

    def test_a_name_in_text_and_attribute_is_relabelled_and_written(self):
        rc, _ = self.run_main(f'<p>on {NAME} now</p><a title="{NAME}">k</a>', "--relabel", str(self.rules))
        self.assertEqual(rc, 0)
        text = self.out.read_text(encoding="utf-8")
        self.assertNotIn(NAME, text)
        self.assertIn("<p>on the lab now</p>", text)

    def test_a_name_in_an_id_refuses_and_writes_nothing(self):
        rc, err = self.run_main(f'<section id="view-{NAME}"><p>ok</p></section>')
        self.assertEqual(rc, 1)
        self.assertFalse(self.out.exists())
        self.assertIn("relabel rule 1 survives 1 time(s)", err)
        self.assertNotIn(NAME, err)
        self.assertNotIn("the lab", err)

    def test_a_barred_value_in_a_capability_page_refuses_with_barred(self):
        doc = f'<section id="cap-x" class="page"><p>holds {BARRED} here</p></section>'
        rc, err = self.run_main(doc, "--barred", str(self.barred))
        self.assertEqual(rc, 1)
        self.assertFalse(self.out.exists())
        self.assertIn("barred value(s)", err)
        self.assertNotIn(BARRED, err)

    def test_the_barred_value_alone_does_not_refuse_without_barred(self):
        doc = f'<section id="cap-x" class="page"><p>holds {BARRED} here</p></section>'
        rc, _ = self.run_main(doc)
        self.assertEqual(rc, 0)
        self.assertTrue(self.out.exists())

    def test_a_bad_barred_list_is_an_input_error(self):
        rc, _ = self.run_main("<p>x</p>", "--barred", str(self.tmp / "missing.txt"))
        self.assertEqual(rc, 2)
        self.assertFalse(self.out.exists())


class RecordPass(unittest.TestCase):
    def test_a_decision_heading_that_relabelling_changes_keeps_an_anchor_with_no_name(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "ADR-0001-x.md").write_text(f"# ADR-0001: x\n\nStatus: Accepted\n\n## Hosting on {NAME}\n\nText.\n",
                                           encoding="utf-8", newline="\n")
        (tmp / "ROADMAP.md").write_text("# roadmap\n", encoding="utf-8", newline="\n")
        rules = [relabel.Rule(__import__("re").compile(NAME, __import__("re").I), "the lab", "r.txt", 1)]
        with mock.patch.object(render_html.capability_phases, "roadmap_file", return_value="ROADMAP.md"):
            dec = render_html.Decisions(tmp, rules)
        self.assertNotIn(NAME, dec.texts["ADR-0001"])
        self.assertEqual(dec.replaced, 1)
        anchors = [dec.anchor("ADR-0001", h) for h in dec.heads["ADR-0001"]]
        self.assertTrue(anchors)
        self.assertNotIn("zebra", "".join(anchors))
        self.assertIn("lab", "".join(anchors))

if __name__ == "__main__":
    unittest.main()
