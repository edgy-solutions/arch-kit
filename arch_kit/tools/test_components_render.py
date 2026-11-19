"""Self-test: components.render and components.nav, as pure functions (no project, no subprocess)."""
from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))

import components  # noqa: E402


def comp(n: int, **over) -> dict:
    c = {"id": f"CO-{n:03d}", "name": f"part-{n}", "purpose": "holds parcels", "plane": "edge", "wiring": "w",
         "sign_in": "s", "data_path": "d", "serves": ["pickup"], "status": "proposed", "evidence": ["ADR-0001"]}
    c.update(over)
    return c


def none(_item):
    return None


def page(items, planes=("edge", "hub"), href=none, **kw) -> str:
    return components.render(items, list(planes), href, **kw)[0][0]


class Render(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(components.render([], ["edge"], none), ([], []))
        self.assertEqual(components.nav([]), "")

    def test_count_wording(self):
        one = page([comp(1)])
        self.assertIn('<p class="component-count" data-component-count>1 component: 0 measured, 0 built, '
                      '0 accepted, 1 proposed.</p>', one)
        three = page([comp(1, status="measured"), comp(2, status="built"), comp(3, status="accepted")])
        self.assertIn("3 components: 1 measured, 1 built, 1 accepted, 0 proposed.", three)

    def test_plane_order_follows_planes_not_file_order(self):
        text = page([comp(1, plane="hub"), comp(2, plane="edge")])
        self.assertEqual(re.findall(r'<h2 data-plane="([^"]+)"', text), ["edge", "hub"])

    def test_a_plane_with_no_components_gets_no_heading(self):
        text = page([comp(1, plane="hub")])
        self.assertEqual(re.findall(r'<h2 data-plane="([^"]+)"', text), ["hub"])

    def test_an_undeclared_plane_comes_after_the_declared_ones(self):
        text = page([comp(1, plane="zed"), comp(2, plane="hub"), comp(3, plane="alt"), comp(4, plane="edge")])
        self.assertEqual(re.findall(r'<h2 data-plane="([^"]+)"', text), ["edge", "hub", "zed", "alt"])

    def test_file_order_is_kept_within_a_plane(self):
        text = page([comp(3), comp(1), comp(2)])
        self.assertEqual(re.findall(r'<article id="component-([^"]+)"', text), ["CO-003", "CO-001", "CO-002"])

    def test_each_status_gives_its_badge(self):
        for status, label in components.STATUS_LABEL.items():
            text = page([comp(1, status=status)])
            self.assertIn(f'data-status="{status}"', text)
            self.assertIn(f'<span class="badge component-{status}">{label}</span>', text)

    def test_evidence_with_an_href_is_a_link_and_without_is_code(self):
        text = page([comp(1, evidence=["ADR-0001", "src/a.py:2"])], href=lambda v: "#adr-0001" if v == "ADR-0001" else None)
        self.assertIn('<dt>Evidence</dt><dd><a href="#adr-0001">ADR-0001</a>, <code>src/a.py:2</code></dd>', text)

    def test_empty_serves_reads_none(self):
        self.assertIn("<dt>Serves</dt><dd>none</dd>", page([comp(1, serves=[])]))
        self.assertIn("<dt>Serves</dt><dd>a, b</dd>", page([comp(1, serves=["a", "b"])]))

    def test_values_and_hrefs_are_escaped(self):
        text = page([comp(1, purpose='a <b> & "c"', evidence=["x<y"])], href=lambda v: 'h"<&')
        self.assertIn("<dd>a &lt;b&gt; &amp; &quot;c&quot;</dd>", text)
        self.assertIn('<a href="h&quot;&lt;&amp;">x&lt;y</a>', text)
        self.assertNotIn("<b>", text)

    def test_pre_is_escaped_and_prov_is_not(self):
        text = page([comp(1)], pre="<i>&", prov='<div class="provenance">p</div>')
        self.assertIn("<h1>&lt;i&gt;&amp;Components</h1>", text)
        self.assertIn('<div class="provenance">p</div></section>', text)

    def test_the_page_shape_and_the_nav_item(self):
        sections, items = components.render([comp(1), comp(2)], ["edge"], none)
        self.assertEqual(len(sections), 1)
        self.assertTrue(sections[0].startswith('<section id="components" class="page components" data-components>'
                                               '<h1>Components</h1><p><a href="#front">Front page</a></p>'))
        self.assertEqual(items, ['<li><a href="#components">Components (2)</a></li>'])
        self.assertEqual(components.nav(items),
                         '<nav class="components"><h2>Components</h2><ul><li><a href="#components">Components (2)</a>'
                         '</li></ul></nav>')

    def test_no_whitespace_between_tags(self):
        self.assertNotRegex(page([comp(1), comp(2, plane="hub")]), r">\s+<")


if __name__ == "__main__":
    unittest.main()
