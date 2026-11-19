"""Tests the break opportunities (<wbr>) that Page adds to long tokens inside table cells. All values are made up."""
from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))

import render_html  # noqa: E402

PATH = "parcels/lockers/north-wing/bay-07/intake/manifests/slots.yml"
assert len(PATH) == 60
HEX = "0123456789abcdef0123456789abcdef01234567"


def render(md: str) -> str:
    return render_html.Page("t", {}, lambda source, svg_id: "").render(md)


def cell(body: str) -> str:
    return render(f"| a | b |\n|---|---|\n| x | {body} |\n")


def text_of(html_text: str) -> str:
    return re.sub(r"<[^>]*>", "", html_text)


class LongTokens(unittest.TestCase):
    def test_a_path_gets_a_break_after_each_slash_and_keeps_its_text(self):
        out = cell(PATH)
        self.assertIn("parcels/<wbr>lockers/<wbr>north-<wbr>wing/<wbr>", out)
        self.assertIn(f"<td>{PATH}</td>", out.replace("<wbr>", ""))
        self.assertIn(PATH, text_of(out))

    def test_a_hex_id_breaks_every_twenty_characters(self):
        out = cell(HEX)
        self.assertIn(f"{HEX[:20]}<wbr>{HEX[20:40]}", out)
        self.assertEqual(out.count("<wbr>"), 1)

    def test_a_short_token_gets_none(self):
        self.assertNotIn("<wbr>", cell("a/b/c/d/e/f/g/h/i/j/k/l"[:23]))

    def test_a_paragraph_outside_a_table_gets_none(self):
        self.assertNotIn("<wbr>", render(PATH + "\n"))

    def test_an_inline_code_path_in_a_cell_gets_breaks(self):
        out = cell(f"`{PATH}`")
        self.assertIn("<code>parcels/<wbr>lockers/", out)
        self.assertNotIn("<wbr>", render(f"`{PATH}`\n"))
        self.assertIn(f"<code>{PATH}</code>", render(f"`{PATH}`" + chr(10)))
        self.assertIn("<code>a&lt;b</code></td>", cell("`a<b`"))

    def test_an_ampersand_stays_one_entity(self):
        out = cell("https://example.test/locker?bay=7&slot=12&owner=north-wing")
        self.assertIn("bay=<wbr>7&amp;<wbr>slot=", out)
        self.assertNotIn("&amp;amp;", out)
        self.assertNotRegex(out, r"&[a-z#0-9]*<wbr>")

    def test_a_header_cell_gets_breaks(self):
        out = render(f"| {PATH} | b |\n|---|---|\n| x | y |\n")
        self.assertIn("<th>parcels/<wbr>lockers/", out)


if __name__ == "__main__":
    unittest.main()
