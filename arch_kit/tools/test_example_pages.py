"""Self-test: the pages example loads and renders to expected/pages.html, byte for byte; and render()'s pure rules.

The example (examples/pages) is the decisions-only example with components, a roadmap, flows, an alignment record and
`files.pages` declared. The test copies it to a temporary directory, loads and renders the pages in a subprocess at
that root (the declaration is read once per process) and compares the printed result with the expected file. To
regenerate the expected file after an intended change, from the kit root:

    python arch_kit/tools/test_example_pages.py --write-expected
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
EXAMPLE = KIT / "examples" / "pages"
EXPECTED = EXAMPLE / "expected" / "pages.html"
LOCAL_IDS = ["ADR-0001", "ADR-0002", "ADR-0003"]

RENDER = '''
import sys
sys.path.insert(0, {tools!r})
import pages
local_ids = {ids!r}
items = pages.load("pages_example", local_ids)
def href(kind, ident):
    if kind == "decision":
        return f"#{{ident.lower()}}" if ident in local_ids else None
    return {{"component": f"#component-{{ident}}", "increment": f"#roadmap-{{ident}}", "flow": "#flows",
            "alignment": f"#alignment-{{ident}}"}}[kind]
sections, nav = pages.render(items, href, prov="", pre="")
sys.stdout.buffer.write((chr(10).join(sections) + chr(10) + pages.nav(nav) + chr(10)).encode("utf-8"))
'''


os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))
sys.path.insert(0, str(HERE))

import pages  # noqa: E402
from data_exchange import InputError  # noqa: E402


def pg(pid: str, kind: str = "walkthrough", body: str = "text", **over) -> dict:
    p = {"id": pid, "title": f"Title {pid}", "kind": kind, "body": body}
    p.update(over)
    return p


def none(_kind, _ident):
    return None


def build(items, href=none, **kw) -> str:
    return "\n".join(pages.render(items, href, **kw)[0])


def ids_of(sections) -> list[str]:
    return [re.search(r'data-page="([^"]+)"', s).group(1) for s in sections]


class Render(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(pages.render([], none), ([], []))
        self.assertEqual(pages.nav([]), "")

    def test_order_overview_first_then_order_then_id(self):
        items = [pg("w-b", order=2), pg("w-a", order=2), pg("w-z"), pg("w-y"), pg("w-c", order=1),
                 pg("zz-overview", "overview")]
        sections, nav = pages.render(items, none)
        self.assertEqual(ids_of(sections), ["zz-overview", "w-c", "w-a", "w-b", "w-y", "w-z"])
        self.assertEqual(re.findall(r'href="#page-([^"]+)"', "".join(nav)), ids_of(sections))

    def test_a_missing_order_sorts_after_every_number(self):
        sections, _ = pages.render([pg("a"), pg("b", order=99999)], none)
        self.assertEqual(ids_of(sections), ["b", "a"])

    def test_the_page_markup(self):
        text = build([pg("one", "overview", "hello")], pre="Woad: ", prov="<p>made</p>")
        self.assertEqual(text, '<section id="page-one" class="page prose" data-page="one" data-kind="overview">'
                               '<h1>Woad: Title one</h1><p><a href="#front">Front page</a></p>'
                               '<div class="body"><p>hello</p>\n</div><p>made</p></section>')

    def test_placeholder_round_trip_in_emphasis_and_a_table_cell(self):
        body = ("Some *emphasis with [[ADR-0001]] in it* and **[[CO-001|built]]**.\n\n"
                "| a | b |\n| - | - |\n| [[RM-001|proposed]] | x |\n")
        text = build([pg("p", body=body)], lambda k, i: f"#{k}-{i}")
        self.assertIn('<em>emphasis with <a class="cite" href="#decision-ADR-0001" data-cite="ADR-0001">ADR-0001</a>'
                      ' in it</em>', text)
        self.assertIn('<strong><a class="cite" href="#component-CO-001" data-cite="CO-001">CO-001</a> '
                      '<span class="badge prose-built">Built</span></strong>', text)
        self.assertIn('<div class="scroll"><table>', text)
        self.assertIn('<td><a class="cite" href="#increment-RM-001" data-cite="RM-001">RM-001</a> '
                      '<span class="badge prose-proposed">Proposed</span></td>', text)
        self.assertNotIn("", text)

    def test_code_is_left_alone(self):
        body = "Inline `[[ADR-0001]]` here.\n\n```\n[[ADR-0002]]\n```\n"
        text = build([pg("p", body=body)], lambda k, i: "#x")
        self.assertIn("<code>[[ADR-0001]]</code>", text)
        self.assertIn("[[ADR-0002]]", text)
        self.assertNotIn("data-cite", text)

    def test_href_none_gives_code(self):
        text = build([pg("p", body="[[other:ADR-0007]]")])
        self.assertIn('<code class="cite" data-cite="other:ADR-0007">other:ADR-0007</code>', text)
        self.assertNotIn("<a class=", text)

    def test_the_kind_passed_to_href(self):
        seen = []
        build([pg("p", body="[[CO-1]] [[RM-1]] [[FL-1]] [[alignment:cov]] [[ADR-0001]] [[other:ADR-0007]]")],
              lambda k, i: seen.append((k, i)))
        self.assertEqual(seen, [("component", "CO-1"), ("increment", "RM-1"), ("flow", "FL-1"),
                                ("alignment", "cov"), ("decision", "ADR-0001"), ("decision", "other:ADR-0007")])

    def test_each_status_gives_its_badge(self):
        for s, label in (("measured", "Measured"), ("built", "Built"), ("accepted", "Accepted"),
                         ("proposed", "Proposed")):
            with self.subTest(status=s):
                text = build([pg("p", body=f"[[CO-001|{s}]]")])
                self.assertIn(f' <span class="badge prose-{s}">{label}</span>', text)
        self.assertNotIn("badge", build([pg("p", body="[[CO-001]]")]))

    def test_a_flow_built_uses_the_built_badge(self):
        self.assertIn('<span class="badge prose-built">Built</span>', build([pg("p", body="[[FL-001|built]]")]))

    def test_escaping(self):
        text = build([pg("p", title="<b>x</b> & y", body="[[a&b]]")], lambda k, i: '"><x', pre="<p>")
        self.assertIn("<h1>&lt;p&gt;&lt;b&gt;x&lt;/b&gt; &amp; y</h1>", text)
        self.assertIn('href="&quot;&gt;&lt;x" data-cite="a&amp;b">a&amp;b</a>', text)
        self.assertNotIn("<b>", text)

    def test_raw_html_in_a_body_is_not_passed(self):
        self.assertIn("&lt;script&gt;", build([pg("p", body="<script>x</script>")]))

    def test_pre_is_escaped_and_prov_is_not(self):
        text = build([pg("p")], pre="A&B: ", prov="<i>p</i>")
        self.assertIn("<h1>A&amp;B: Title p</h1>", text)
        self.assertTrue(text.endswith("</div><i>p</i></section>"))

    def test_nav(self):
        _, items = pages.render([pg("a", "overview"), pg("b", order=1, title="B & b")], none)
        self.assertEqual(items, ['<li><a href="#page-a">Title a</a></li>', '<li><a href="#page-b">B &amp; b</a></li>'])
        self.assertEqual(pages.nav(items), '<nav class="prose"><h2>Overview and walkthroughs</h2><ul>'
                                           + "".join(items) + "</ul></nav>")

    def test_css(self):
        self.assertIn(".cite{white-space:nowrap}", pages.CSS)
        for s in pages.STATUSES:
            self.assertIn(f".prose-{s}{{", pages.CSS)
        self.assertIn("nav.prose ul{padding-left:1.2em}", pages.CSS)

    def test_markdown_missing_raises(self):
        saved = sys.modules.get("markdown_it")
        sys.modules["markdown_it"] = None
        try:
            with self.assertRaises(InputError) as c:
                pages.render([pg("p")], none)
        finally:
            if saved is not None:
                sys.modules["markdown_it"] = saved
            else:
                del sys.modules["markdown_it"]
        self.assertEqual(str(c.exception), "markdown-it-py is not installed: pip install markdown-it-py==4.0.0")


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
            self.fail("the output differs from expected/pages.html:\n" + "\n".join(diff[:40]))

    def test_the_walkthroughs_render_in_order_not_file_order(self):
        text = EXPECTED.read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'<section id="page-([^"]+)"', text), ["overview", "b-return", "a-offline"])

    def test_the_example_cites_what_the_spec_names(self):
        text = EXPECTED.read_text(encoding="utf-8")
        for want in ('href="#adr-0001"', 'data-cite="other:ADR-0007"', 'href="#component-CO-001"',
                     'href="#roadmap-RM-002"', 'href="#flows"', 'href="#alignment-coverage"',
                     "<code>[[ADR-0001]]</code>", "[[ADR-0099]]", '<div class="scroll"><table>'):
            self.assertIn(want, text)


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
