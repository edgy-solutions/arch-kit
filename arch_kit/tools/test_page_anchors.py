"""Tests the heading ids on declared pages and the links that reach them. All values are made up."""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))

import render_html  # noqa: E402
from markdown_it import MarkdownIt  # noqa: E402

PAGE_MD = "## Locker Rules\n\nText.\n\n### Pick-up & drop_off (v2)\n\n## Locker Rules\n\n#### Locker Rules\n\nEnd.\n"


def nodiagram(source, svg_id):
    return ""


class Anchors(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, True))
        self.file = (self.tmp / "rules.md").resolve()
        self.file.write_text("# Rules\n\n" + PAGE_MD, encoding="utf-8")
        md = MarkdownIt("commonmark", {"html": False}).enable("table")
        slugs = render_html.heading_slugs(md.parse(PAGE_MD, {}))
        self.pages = {self.file: {"id": "rules", "path": self.file, "text": PAGE_MD, "slugs": slugs}}

    def render(self, md: str, own: str | None = None) -> tuple[str, str]:
        page = render_html.Page("rules" if own else "v", {}, nodiagram, None, self.pages, own)
        page.base = self.tmp
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            return page.render(md), err.getvalue()

    def test_a_heading_gets_an_id_on_a_declared_page(self):
        out, _ = self.render(PAGE_MD, "rules")
        self.assertIn('<h2 id="page-rules--locker-rules">Locker Rules</h2>', out)
        self.assertIn('<h3 id="page-rules--pick-up--drop_off-v2">', out)

    def test_a_repeated_slug_takes_a_number(self):
        out, _ = self.render(PAGE_MD, "rules")
        self.assertIn('<h2 id="page-rules--locker-rules-1">', out)
        self.assertIn('<h4 id="page-rules--locker-rules-2">', out)

    def test_a_view_has_no_heading_ids(self):
        out, _ = self.render(PAGE_MD)
        self.assertNotIn(" id=", out)

    def test_a_view_links_to_a_heading_on_a_page(self):
        out, err = self.render("See [rules](rules.md#locker-rules-1).\n")
        self.assertIn('<a href="#page-rules--locker-rules-1">rules</a>', out)
        self.assertEqual(err, "")

    def test_a_view_links_to_a_page_with_no_fragment(self):
        out, err = self.render("See [rules](rules.md).\n")
        self.assertIn('<a href="#page-rules">rules</a>', out)
        self.assertEqual(err, "")

    def test_a_missing_fragment_links_the_page_and_warns(self):
        out, err = self.render("See [rules](rules.md#nowhere).\n")
        self.assertIn('<a href="#page-rules">rules</a>', out)
        self.assertEqual(err, "pages: rules: no heading for #nowhere\n")

    def test_a_page_fragment_that_is_found(self):
        out, err = self.render(PAGE_MD + "See [above](#locker-rules).\n", "rules")
        self.assertIn('<a href="#page-rules--locker-rules">above</a>', out)
        self.assertEqual(err, "")

    def test_a_page_fragment_that_is_not_found_stays_a_span(self):
        out, err = self.render("See [above](#nowhere).\n", "rules")
        self.assertIn('<span class="ref">above</span>', out)
        self.assertEqual(err, "pages: rules: no heading for #nowhere\n")

    def test_a_views_bare_fragment_stays_a_span(self):
        out, err = self.render("See [above](#locker-rules).\n")
        self.assertIn('<span class="ref">above</span>', out)
        self.assertEqual(err, "")

    def test_the_slug_is_githubs(self):
        self.assertEqual(render_html.github_slug("Pick-up & drop_off (v2)"), "pick-up--drop_off-v2")


if __name__ == "__main__":
    unittest.main()
