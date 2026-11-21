"""Front matter in decision records: the heading reader and the rendered page both skip it."""
from __future__ import annotations

import ast
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import test_example_decisions as ex  # noqa: E402

FM = "---\nstatus: Accepted\ndate: 2026-01-02\n---\n"


def strip_front_matter():
    """The helper from adr_sections.py, taken from its source: importing the module reads a declaration."""
    src = (HERE / "adr_sections.py").read_text(encoding="utf-8")
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "strip_front_matter")
    ns: dict = {}
    exec(compile(ast.Module([node], []), "adr_sections.py", "exec"), ns)
    return ns["strip_front_matter"]


class FrontMatter(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = ex.copy_example(self.tmp)
        self.record = next((self.root / "decisions").glob("0002-*.md"))

    def headings(self):
        p = ex.tool(self.root, "adr_sections", "ADR-0002")
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.splitlines()

    def add_front_matter(self, block=FM):
        self.record.write_text(block + self.record.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        ex.git(self.root, "add", ".")
        ex.git(self.root, "commit", "-q", "-m", "front matter")

    def test_heading_count_is_the_same_with_front_matter(self):
        before = self.headings()
        self.add_front_matter()
        self.assertEqual(self.headings(), before)

    def test_the_page_renders_with_no_extra_h2(self):
        out = self.tmp / "before.html"
        self.assertEqual(ex.render(self.root, out).returncode, 0)
        self.add_front_matter()
        after = self.tmp / "after.html"
        p = ex.render(self.root, after)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        count = lambda f: len(re.findall(r"<h2\b", f.read_text(encoding="utf-8")))
        self.assertEqual(count(after), count(out))
        self.assertNotIn("status: Accepted", after.read_text(encoding="utf-8"))

    def test_an_unclosed_block_is_left_alone(self):
        strip = strip_front_matter()
        text = "---\nstatus: Accepted\n\n## Context\n"
        self.assertEqual(strip(text), text)

    def test_line_numbers_are_unchanged(self):
        strip = strip_front_matter()
        for end in ("---", "..."):
            text = f"---\nstatus: x\n{end}\n## Context\nbody\n"
            out = strip(text)
            self.assertEqual(len(out.split("\n")), len(text.split("\n")))
            self.assertEqual(out.split("\n")[3:], text.split("\n")[3:])
            self.assertEqual(out.split("\n")[:3], ["", "", ""])

    def test_text_without_front_matter_is_unchanged(self):
        strip = strip_front_matter()
        text = "# Title\n\n---\n\n## Context\n"
        self.assertEqual(strip(text), text)


if __name__ == "__main__":
    unittest.main()
