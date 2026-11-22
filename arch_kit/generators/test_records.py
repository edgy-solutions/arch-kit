import unittest

from arch_kit.generators import records


def rec(rid, body="body\n"):
    return f"# Locker ({rid})\n\n{body}"


class ParseTests(unittest.TestCase):
    def test_id_and_title(self):
        r = records.parse("a", "docs/arch/components/x.md", "components/x.md", "# Locker (CO-LOCKER)\n")
        self.assertEqual(r.rid, "CO-LOCKER")
        self.assertEqual(r.title, "Locker (CO-LOCKER)")
        r = records.parse("a", "p", "decisions/ADR-0007-foo.md", "# Title\n")
        self.assertEqual(r.rid, "ADR-0007")
        r = records.parse("a", "p", "components/y.md", "# No id here\n")
        self.assertIsNone(r.rid)

    def test_classify(self):
        self.assertEqual(records.classify("README.md"), "readme")
        self.assertEqual(records.classify("roadmap.md"), "roadmap")
        self.assertEqual(records.classify("notes.md"), "other")
        self.assertEqual(records.classify("flows/f.md"), "flows")
        self.assertEqual(records.classify("misc/f.md"), "other")

    def test_split_cells_keeps_escaped_bar(self):
        self.assertEqual(records.split_cells("| a | b \\| c | d |"), ["a", "b \\| c", "d"])

    def test_separator_row(self):
        self.assertTrue(records._is_sep("|---|:--:|"))
        self.assertFalse(records._is_sep("| a | b |"))

    def test_claims_gaps_and_not_established(self):
        text = rec("CO-LOCKER", "## Claims\n\n| Claim | Status |\n|---|---|\n| door | `built` |\n\n"
                   "## Gaps\n\n- first gap\n  continued\n- second gap\n\n"
                   "## Not established\n\n| Fact | Who could establish it |\n|---|---|\n| a fact | the depot |\n")
        r = records.parse("a", "p", "components/c.md", text)
        self.assertEqual([c[2] for c in r.claims], ["`built`"])
        self.assertEqual(r.gaps, ["first gap continued", "second gap"])
        self.assertEqual(r.not_established, [{"fact": "a fact", "who": "the depot"}])

    def test_fenced_heading_is_not_a_heading(self):
        r = records.parse("a", "p", "components/c.md", "# T (CO-A)\n\n```\n# not a title\n## Gaps\n```\n")
        self.assertEqual(r.title, "T (CO-A)")
        self.assertEqual([s[0] for s in r.sections], [""])

    def test_exposure_outside_gaps_is_noted(self):
        r = records.parse("a", "p", "components/c.md", "# T (CO-A)\n\nPresent exposure here.\n")
        self.assertEqual(r.exposure_misplaced, [3])


class FrontMatterTests(unittest.TestCase):
    def test_stripped_and_body_parses(self):
        plain = rec("CO-LOCKER", "text\n")
        r0 = records.parse("alpha", "p.md", "components/c.md", plain)
        r1 = records.parse("alpha", "p.md", "components/c.md", "---\nid: CO-LOCKER\nplane: x\n---\n" + plain)
        self.assertEqual(r1.front, {"id": "CO-LOCKER", "plane": "x"})
        self.assertEqual(r0.front, {})
        self.assertEqual(r1.text, r0.text)
        self.assertEqual((r1.title, r1.rid, r1.claims, r1.tables), (r0.title, r0.rid, r0.claims, r0.tables))

    def test_unterminated_is_not_front_matter(self):
        r = records.parse("alpha", "p.md", "components/c.md", "---\n# T (CO-A)\n")
        self.assertEqual((r.front, r.front_error), ({}, ""))
        self.assertEqual(r.rid, "CO-A")

    def test_bad_yaml_sets_error(self):
        r = records.parse("alpha", "p.md", "components/c.md", "---\nid: [unclosed\n---\n" + rec("CO-A"))
        self.assertEqual((r.front, r.front_error), ({}, "does not parse"))

    def test_not_a_mapping_sets_error(self):
        r = records.parse("alpha", "p.md", "components/c.md", "---\n- a\n- b\n---\n" + rec("CO-A"))
        self.assertEqual(r.front_error, "is not a mapping")


if __name__ == "__main__":
    unittest.main()
