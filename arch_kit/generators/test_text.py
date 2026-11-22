import unittest

from arch_kit.generators import model, text


def rec(**kw):
    return model.Record(member="m", path="decisions/ADR-0001-x.md", rel="ADR-0001-x.md", kind="decisions",
                        title="X", rid="ADR-0001", **kw)


class RecLinkTests(unittest.TestCase):
    def test_anchor_links_to_the_records_page(self):
        self.assertEqual(text.rec_link(rec(anchor="m-adr-0001"), "../pages/records.md"),
                         "[m:ADR-0001](../pages/records.md#m-adr-0001)")

    def test_no_anchor_is_text(self):
        self.assertEqual(text.rec_link(rec(), "../pages/records.md"), "m:ADR-0001")

    def test_href_replaces_the_page_link(self):
        r = rec(anchor="m-adr-0001", href="../docs/adr/ADR-0001-x.md")
        self.assertEqual(text.rec_link(r, "../pages/records.md", "ADR-0001"), "[ADR-0001](../docs/adr/ADR-0001-x.md)")

    def test_brackets_in_the_label_become_parentheses(self):
        self.assertEqual(text.rec_link(rec(), "p.md", "a [b]"), "a (b)")


class CellTests(unittest.TestCase):
    def test_cell_escapes_pipes_and_joins_lines(self):
        self.assertEqual(text.cell("a | b\nc"), r"a \| b c")

    def test_an_escaped_pipe_is_not_escaped_twice(self):
        self.assertEqual(text.cell(r"a \| b"), r"a \| b")

    def test_none_is_empty(self):
        self.assertEqual(text.cell(None), "")

    def test_a_link_to_a_known_path_goes_to_the_records_page(self):
        r = rec()
        out = text.cell("see [x](ADR-0002-y.md)", r, {"decisions/ADR-0002-y.md": "m-adr-0002"}, "records.md")
        self.assertEqual(out, "see [x](records.md#m-adr-0002)")

    def test_table_and_fence(self):
        self.assertEqual(text.table(["A", "B"], [["1", "2"]]), "| A | B |\n|---|---|\n| 1 | 2 |\n")
        self.assertEqual(text.fence("txt", "x\n\n"), "```txt\nx\n```\n")


class LinkPathTests(unittest.TestCase):
    def test_relative_link_is_normalised_against_the_base(self):
        self.assertEqual(text.link_path("../a/b.md#h", "docs/x"), "docs/a/b.md")

    def test_absolute_fragment_and_empty_links_have_no_path(self):
        for href in ("https://x.example.invalid/a", "#h", "", "//host/p", "<>"):
            self.assertIsNone(text.link_path(href, "docs"))

    def test_linked_paths_skips_fenced_code_and_images(self):
        r = rec(text="[a](one.md) ![i](img.png)\n```\n[b](two.md)\n```\n`[c](three.md)` [d](four.md)\n")
        self.assertEqual(text.linked_paths(r), {"decisions/one.md", "decisions/four.md"})


if __name__ == "__main__":
    unittest.main()
