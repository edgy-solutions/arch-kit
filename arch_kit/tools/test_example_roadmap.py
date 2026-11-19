"""Self-test: the roadmap example loads and renders to expected/roadmap.html, byte for byte.

The example (examples/roadmap) is the decisions-only example with `files.roadmap` declared. The test copies it
to a temporary directory, loads and renders the roadmap in a subprocess at that root (the declaration is read once
per process) and compares the printed result with the expected file. To regenerate the expected file after an
intended change, from the kit root:

    python arch_kit/tools/test_example_roadmap.py --write-expected
"""
from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
EXAMPLE = KIT / "examples" / "roadmap"
EXPECTED = EXAMPLE / "expected" / "roadmap.html"
LOCAL_IDS = ["ADR-0001", "ADR-0002", "ADR-0003"]

RENDER = '''
import sys
sys.path.insert(0, {tools!r})
import roadmap
local_ids = {ids!r}
items = roadmap.load("roadmap_example", local_ids)
sections, nav = roadmap.render(items, lambda v: f"#{{v.lower()}}" if v in local_ids else None, prov="", pre="", page_id="roadmap")
sys.stdout.buffer.write((chr(10).join(sections) + chr(10) + roadmap.nav(nav) + chr(10)).encode("utf-8"))
'''


os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))
sys.path.insert(0, str(HERE))

import roadmap  # noqa: E402


def inc(n: int, **over) -> dict:
    r = {"id": f"RM-{n:03d}", "increment": f"step-{n}", "isolates": "one thing", "home": "ADR-0001",
         "depends_on": [], "status": "proposed"}
    r.update(over)
    return r


def none(_item):
    return None


def page(items, href=none, **kw) -> str:
    return roadmap.render(items, href, **kw)[0][0]


class Render(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(roadmap.render([], none), ([], []))
        self.assertEqual(roadmap.nav([]), "")

    def test_count_wording(self):
        self.assertIn('<p class="roadmap-count" data-roadmap-count>1 increment: 0 measured, 0 built, 0 accepted, '
                      '1 proposed.</p>', page([inc(1)]))
        three = page([inc(1, status="measured"), inc(2, status="built"), inc(3, status="accepted")])
        self.assertIn("3 increments: 1 measured, 1 built, 1 accepted, 0 proposed.", three)

    def test_the_page_and_the_table_markup(self):
        text = page([inc(1)], pre="Yarrow: ")
        self.assertTrue(text.startswith('<section id="roadmap" class="page roadmap" data-roadmap>'
                                        '<h1>Yarrow: Roadmap</h1><p><a href="#front">Front page</a></p>'))
        self.assertIn('<div class="scroll"><table><thead><tr><th>#</th><th>Id</th><th>Increment</th>'
                      '<th>What isolates</th><th>Home</th><th>Depends on</th><th>Status</th></tr></thead><tbody>', text)
        self.assertTrue(text.endswith("</tbody></table></div></section>"))
        self.assertNotRegex(text, r">\s+<")

    def test_prov_is_not_escaped(self):
        self.assertTrue(page([inc(1)], prov="<p>made</p>").endswith("</table></div><p>made</p></section>"))

    def test_rows_in_file_order_with_anchors_and_positions(self):
        text = page([inc(3), inc(1, depends_on=["RM-003"]), inc(2)])
        self.assertEqual(re.findall(r'<tr id="roadmap-([^"]+)" data-increment="([^"]+)"', text),
                         [("RM-003", "RM-003"), ("RM-001", "RM-001"), ("RM-002", "RM-002")])
        self.assertEqual(re.findall(r"<tr [^>]*><td>(\d+)</td>", text), ["1", "2", "3"])

    def test_depends_on_links_or_none(self):
        text = page([inc(1), inc(2, depends_on=["RM-001"]), inc(3, depends_on=["RM-001", "RM-002"])])
        self.assertIn('<td>none</td><td><span class="badge', text)
        self.assertIn('<td><a href="#roadmap-RM-001">RM-001</a></td>', text)
        self.assertIn('<td><a href="#roadmap-RM-001">RM-001</a>, <a href="#roadmap-RM-002">RM-002</a></td>', text)

    def test_home_is_a_link_code_or_none(self):
        href = lambda v: "#adr-0001" if v == "ADR-0001" else None  # noqa: E731
        text = page([inc(1), inc(2, home="other:ADR-0007"), inc(3, home=None)], href)
        self.assertIn('<td><a href="#adr-0001">ADR-0001</a></td>', text)
        self.assertIn("<td><code>other:ADR-0007</code></td>", text)
        rows = text.split("<tr ")[3]
        self.assertIn("<td>none</td><td>none</td>", rows)

    def test_each_status_gives_its_badge_and_data_status(self):
        for s, label in (("measured", "Measured"), ("built", "Built"), ("accepted", "Accepted"),
                         ("proposed", "Proposed")):
            with self.subTest(status=s):
                text = page([inc(1, status=s)])
                self.assertIn(f'data-status="{s}"', text)
                self.assertIn(f'<span class="badge roadmap-{s}">{label}</span>', text)

    def test_escaping(self):
        text = page([inc(1, increment="<b>x</b> & y", isolates='"q" <i>', home="<h>")], pre="<p>")
        self.assertIn("&lt;b&gt;x&lt;/b&gt; &amp; y", text)
        self.assertIn("&quot;q&quot; &lt;i&gt;", text)
        self.assertIn("<code>&lt;h&gt;</code>", text)
        self.assertIn("<h1>&lt;p&gt;Roadmap</h1>", text)
        self.assertNotIn("<b>", text)

    def test_page_id_is_used_throughout(self):
        sections, items = roadmap.render([inc(1), inc(2, depends_on=["RM-001"])], none, page_id="plan&1")
        text = sections[0]
        self.assertIn('<section id="plan&amp;1" class="page roadmap"', text)
        self.assertIn('<tr id="plan&amp;1-RM-001"', text)
        self.assertIn('<a href="#plan&amp;1-RM-001">RM-001</a>', text)
        self.assertEqual(items, ['<li><a href="#plan&amp;1">Roadmap (2)</a></li>'])
        self.assertNotIn('"#roadmap', text)

    def test_nav(self):
        _, items = roadmap.render([inc(1)], none)
        self.assertEqual(items, ['<li><a href="#roadmap">Roadmap (1)</a></li>'])
        self.assertEqual(roadmap.nav(items), '<nav class="roadmap"><h2>Roadmap</h2><ul>'
                                             '<li><a href="#roadmap">Roadmap (1)</a></li></ul></nav>')

    def test_css_names_every_status(self):
        for s in roadmap.STATUSES:
            self.assertIn(f".roadmap-{s}{{", roadmap.CSS)


def run_in(root: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, ARCH_KIT_CONFIG=str(root / "arch-kit.yaml"), PYTHONDONTWRITEBYTECODE="1")
    code = RENDER.format(tools=str(HERE), ids=LOCAL_IDS)
    return subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True)


def copy_example(tmp: Path) -> Path:
    root = tmp / "proj"
    shutil.copytree(EXAMPLE, root, ignore=shutil.ignore_patterns("expected", "__pycache__"))
    return root


class Example(unittest.TestCase):
    def test_the_example_renders_to_its_expected_file(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        p = run_in(copy_example(tmp))
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace"))
        self.assertEqual(p.stderr, b"")
        want = EXPECTED.read_bytes()
        if p.stdout != want:
            diff = list(difflib.unified_diff(want.decode("utf-8").split("\n"), p.stdout.decode("utf-8").split("\n"),
                                             "expected", "built", lineterm="", n=0))
            self.fail("the output differs from expected/roadmap.html:\n" + "\n".join(diff[:40]))


def write_expected() -> int:
    with tempfile.TemporaryDirectory() as t:
        p = run_in(copy_example(Path(t)))
        if p.returncode or p.stderr:
            print(p.stderr.decode("utf-8", "replace"), file=sys.stderr)
            return 1
    EXPECTED.parent.mkdir(exist_ok=True)
    EXPECTED.write_bytes(p.stdout)
    print(f"wrote {EXPECTED}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-expected"]:
        sys.exit(write_expected())
    unittest.main()
