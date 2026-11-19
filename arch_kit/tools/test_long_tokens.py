"""Tests the break opportunities (<wbr>) that Page adds to long tokens inside table cells. All values are made up."""
from __future__ import annotations

import html
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
URL = "https://example.test/parcels/lockers/north-wing/bay-07/intake?owner=north-wing&slot=12&token=abc"
assert len(URL) >= 80
PATH47 = PATH[:47]
PATH48 = PATH[:48]
assert len(PATH47) == 47 and len(PATH48) == 48
HEX = "0123456789abcdef0123456789abcdef01234567"
HEAD = "| a | b | c | d |\n|---|---|---|---|\n"


def render(md: str) -> str:
    return render_html.Page("t", {}, lambda source, svg_id: "").render(md)


def row(*cells: str) -> str:
    return "| " + " | ".join(cells) + " |\n"


def cell(body: str) -> str:
    """A four-column table with `body` in column 4."""
    return render(HEAD + row("w", "x", "y", body))


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
        out = render(row("a", "b", "c", PATH) + "|---|---|---|---|\n" + row("w", "x", "y", "z"))
        self.assertIn("<th>parcels/<wbr>lockers/", out)

    def test_a_47_character_path_in_columns_one_to_three_gets_none(self):
        for col in range(3):
            cells = ["w", "x", "y", "z"]
            cells[col] = PATH47
            out = render(HEAD + row(*cells))
            self.assertNotIn("<wbr>", out)
            self.assertIn(f"<td>{PATH47}</td>", out)

    def test_a_60_character_path_in_column_two_gets_breaks_and_keeps_its_text(self):
        out = render(HEAD + row("w", PATH, "y", "z"))
        self.assertIn("<td>parcels/<wbr>lockers/", out)
        self.assertIn(f"<td>{PATH}</td>", out.replace("<wbr>", ""))
        self.assertIn(PATH, text_of(out))

    def test_a_48_character_path_in_column_one_gets_breaks(self):
        out = render(HEAD + row(PATH48, "x", "y", "z"))
        self.assertIn("<td>parcels/<wbr>lockers/", out)
        self.assertIn(f"<td>{PATH48}</td>", out.replace("<wbr>", ""))

    def test_a_24_character_run_in_column_four_still_gets_breaks(self):
        self.assertIn("<wbr>", cell("a" * 24))
        self.assertNotIn("<wbr>", render(HEAD + row("a" * 24, "x", "y", "z")))

    def test_a_header_cell_in_column_two_gets_none(self):
        out = render(row("a", PATH47, "c", "d") + "|---|---|---|---|\n" + row("w", "x", "y", "z"))
        self.assertNotIn("<wbr>", out)
        self.assertIn(f"<th>{PATH47}</th>", out)

    def test_a_printed_link_target_breaks_in_column_four_but_not_its_href(self):
        out = cell(f"[short]({URL})")
        self.assertIn("<wbr>", out)
        self.assertNotIn("href=", out)  # an external link prints its target; it has no href attribute
        self.assertNotRegex(out, r'href="[^"]*<wbr>')
        self.assertIn(f"short ({URL})", html.unescape(text_of(out)))

    def test_a_link_in_column_two_prints_its_long_target_with_breaks(self):
        out = render(HEAD + row("w", f"[short]({URL})", "y", "z"))
        self.assertIn("<wbr>", out)
        self.assertNotIn("href=", out)
        self.assertIn(f"short ({URL})", html.unescape(text_of(out)))

    def test_a_link_in_column_two_with_a_short_target_gets_none(self):
        out = render(HEAD + row("w", "[short](https://example.test/parcels/lockers)", "y", "z"))
        self.assertNotIn("<wbr>", out)

    def test_the_column_count_resets_per_row(self):
        out = render(HEAD + row("w", "x", "y", "z") + row(PATH47, "x", "y", PATH))
        second = out.split("<tr>")[-1]
        self.assertIn(f"<td>{PATH47}</td>", second)
        self.assertIn("<td>parcels/<wbr>lockers/", second)

    def test_a_header_min_width_counts_a_break_hint_as_a_break(self):
        out = render_html.style_tables(render(HEAD + row("w", PATH, "y", "z")))
        self.assertIn("<wbr>", out)
        piece = max(len(w) for w in PATH.replace("/", "/ ").replace("-", "- ").split())
        width = int(re.search(r'<th[^>]*min-width:(\d+)ch[^>]*>b</th>', out).group(1))
        self.assertLessEqual(width, max(piece, render_html.PROSE_MIN_CH))
        self.assertLess(width, len(PATH))

    def test_a_header_min_width_for_an_unbroken_token_is_its_length(self):
        token = "0123456789" * 4
        out = render_html.style_tables(render(HEAD + row("w", token, "y", "z")))
        self.assertNotIn("<wbr>", out)
        self.assertRegex(out, r'<th[^>]*min-width:40ch[^>]*>b</th>')


if __name__ == "__main__":
    unittest.main()
