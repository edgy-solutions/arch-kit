"""adr_sections.headings reads the headings the page renderer produces, including those inside block quotes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
EXAMPLE = KIT / "examples" / "decisions-only"

SCRIPT = (
    "import json, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import adr_sections\n"
    "print(json.dumps([[h.level, h.text, h.slug] for h in adr_sections.headings(sys.stdin.read())]))\n"
)


def read(text: str) -> list:
    env = dict(os.environ, PYTHONPATH=str(KIT), ARCH_KIT_CONFIG=str(EXAMPLE / "arch-kit.yaml"), PYTHONUTF8="1")
    p = subprocess.run([sys.executable, "-c", SCRIPT, str(HERE)], input=text, cwd=EXAMPLE, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise AssertionError(p.stderr)
    return json.loads(p.stdout)


class Headings(unittest.TestCase):
    def test_plain_headings(self):
        got = read("# Title\n\n## Context\n\ntext\n\n### Detail\n")
        self.assertEqual([h[:2] for h in got], [[2, "Context"], [3, "Detail"]])

    def test_a_heading_in_a_block_quote_counts(self):
        got = read("## Context\n\n> ## Note\n> body\n\n> ### Condition\n")
        self.assertEqual([h[1] for h in got], ["Context", "Note", "Condition"])

    def test_a_heading_in_a_nested_block_quote_counts(self):
        got = read("> > ### Deep\n>> ## Deeper\n")
        self.assertEqual([h[:2] for h in got], [[3, "Deep"], [2, "Deeper"]])

    def test_a_fence_in_a_block_quote_hides_its_contents(self):
        got = read("> ```\n> ## not a heading\n> ```\n> ## real\n")
        self.assertEqual([h[1] for h in got], ["real"])

    def test_a_fence_in_a_block_quote_ends_with_the_quote(self):
        got = read("> ```\n> code\n\n## after the quote\n")
        self.assertEqual([h[1] for h in got], ["after the quote"])

    def test_a_fence_outside_a_quote_still_hides_quoted_looking_lines(self):
        got = read("```\n> ## inside\n```\n## after\n")
        self.assertEqual([h[1] for h in got], ["after"])

    def test_a_quoted_fence_line_inside_a_plain_fence_does_not_close_it(self):
        got = read("```\n> ```\n## inside\n```\n## after\n")
        self.assertEqual([h[1] for h in got], ["after"])

    def test_a_deeper_quoted_fence_line_does_not_close_a_quoted_fence(self):
        got = read("> ```\n> > ```\n> ## inside\n> ```\n> ## after\n")
        self.assertEqual([h[1] for h in got], ["after"])

    def test_duplicate_slugs_are_numbered_across_quotes(self):
        got = read("## Same\n> ## Same\n")
        self.assertEqual([h[2] for h in got], ["same", "same-1"])


if __name__ == "__main__":
    unittest.main()
