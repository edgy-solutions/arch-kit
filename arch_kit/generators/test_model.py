import unittest

from arch_kit.generators import model


def ref(key):
    return model.Ref("rec", key, key[-1])


def row(rec_name, a, b, status, n=1):
    r = model.Record(member="m", path=f"{rec_name}.md", rel=f"{rec_name}.md", kind="components", title=rec_name,
                     rid=rec_name)
    return model.ConnRow("m", r, n, str(n), ref(a), ref(b), "out", ref(a), ref(b), status=status), r


class ClaimStatusTests(unittest.TestCase):
    def test_one_status(self):
        self.assertEqual(model.claim_status("`built` and prose"), "built")

    def test_not_built_is_one_token(self):
        self.assertEqual(model.claim_statuses("`not built`"), ["not built"])

    def test_two_and_none(self):
        self.assertEqual(model.claim_status("`built` `proposed`"), model.TWO)
        self.assertEqual(model.claim_status("nothing"), model.NONE)
        self.assertEqual(model.claim_status("`maybe`"), model.NONE)


class RecordTests(unittest.TestCase):
    def test_display_id_and_ref(self):
        r = model.Record("m", "a/b.md", "b.md", "other", "T", None)
        self.assertEqual((r.ref, r.display_id), ("b.md", "m:b.md"))

    def test_decision_status_is_the_first_line_of_the_status_section(self):
        r = model.Record("m", "a.md", "a.md", "decisions", "T", "D-1",
                         sections=[("Context", ["x"]), ("Status", ["", "Accepted", "more"])])
        self.assertEqual(model.decision_status(r), "Accepted")

    def test_vocabulary_section(self):
        r = model.Record("m", "a.md", "a.md", "readme", "T", None, sections=[("Status vocabulary", ["a", "b"])])
        self.assertEqual(model.vocabulary_section(r), "## Status vocabulary\na\nb")
        self.assertIsNone(model.vocabulary_section(model.Record("m", "a.md", "a.md", "readme", "T", None)))


class BuildEdgesTests(unittest.TestCase):
    def test_two_rows_from_the_two_ends_merge_into_one_edge(self):
        a, b = ("rec", "m", "A"), ("rec", "m", "B")
        r1, ra = row("A", a, b, "built")
        r2, rb = row("B", a, b, "built")
        r1.start = r1.this = ref(a)
        r1.start.rec, r1.end.rec = ra, rb
        r2.start.rec, r2.end.rec = ra, rb
        out = []
        edges = model.build_edges([r1, r2], out)
        self.assertEqual(len(edges), 1)
        self.assertTrue(edges[0].merged)
        self.assertEqual(out, [])

    def disagreeing(self):
        a, b = ("rec", "m", "A"), ("rec", "m", "B")
        r1, ra = row("A", a, b, "built")
        r2, rb = row("B", a, b, "proposed")
        for r in (r1, r2):
            r.start.rec, r.end.rec = ra, rb
        return [r1, r2]

    def test_merged_rows_that_disagree_raise_the_default_kind(self):
        out = []
        model.build_edges(self.disagreeing(), out)
        self.assertEqual([f.kind for f in out], ["connections-disagree"])

    def test_a_caller_names_its_own_kind(self):
        out = []
        model.build_edges(self.disagreeing(), out, {"disagree": "own-disagree"})
        self.assertEqual([f.kind for f in out], ["own-disagree"])

    def test_a_row_alone_is_its_own_edge_and_edges_are_numbered(self):
        r1, _ = row("A", ("rec", "m", "A"), ("rec", "m", "B"), "built")
        r2, _ = row("C", ("rec", "m", "C"), ("rec", "m", "D"), "built")
        edges = model.build_edges([r1, r2], [])
        self.assertEqual([e.n for e in edges], [1, 2])
        self.assertTrue(all(e.solid and not e.merged for e in edges))


class HelperTests(unittest.TestCase):
    def test_plain_collapses_space_and_drops_ticks(self):
        self.assertEqual(model.plain(" `a`\n b "), "a b")

    def test_ident_prefers_front_matter(self):
        r = model.Record("m", "a.md", "a.md", "components", "T", "CO-A", front={"id": "CO-B"})
        self.assertEqual(model.ident(r), "CO-B")
        r.front = {}
        self.assertEqual(model.ident(r), "CO-A")

    def test_id_pattern(self):
        self.assertEqual(model.ID.fullmatch("m:CO-DEPOT").groups(), ("m", "CO-DEPOT"))


if __name__ == "__main__":
    unittest.main()
