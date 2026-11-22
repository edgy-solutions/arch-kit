import unittest
from types import SimpleNamespace

from arch_kit.generators import catalogue, model, views, viewtext


class ParseCapabilityTests(unittest.TestCase):
    CTX = views.Ctx([], {}, capabilities={"A6": "Six", "A7": "Seven", "A9": "Data-Centric Security"},
                    cap_prefix="dcra")

    def parse(self, text):
        return views.parse_capability(self.CTX, text)

    def test_one_id(self):
        self.assertEqual(self.parse("dcra:A9"), [("known", "A9")])

    def test_two_ids(self):
        self.assertEqual(self.parse("dcra:A6, dcra:A7"), [("known", "A6"), ("known", "A7")])

    def test_backticks_are_dropped(self):
        self.assertEqual(self.parse("`dcra:A9`"), [("known", "A9")])

    def test_none(self):
        self.assertEqual(self.parse("none"), [("none", "")])

    def test_not_written(self):
        self.assertEqual(self.parse(None), [("not written", "")])

    def test_an_unknown_id(self):
        self.assertEqual(self.parse("dcra:A99"), [("unknown", "dcra:A99")])

    def test_a_word(self):
        self.assertEqual(self.parse("foo"), [("unknown", "foo")])

    def test_the_label(self):
        self.assertEqual(views.capability_label(self.CTX, "A9"), "A9 Data-Centric Security")

    def test_a_count_of_one_is_singular(self):
        self.assertEqual([views.counted(n, "role") for n in (1, 2)], ["1 role", "2 roles"])
        self.assertEqual(views.counted(1, "capability"), "1 capability")
        self.assertEqual(views.counted(3, "capability"), "3 capabilities")


class ProtectionSentenceTests(unittest.TestCase):
    def test_stated_protection_is_counted_apart_and_only_when_present(self):
        P = model.Protection
        end = SimpleNamespace(key=("rec", "m", "CO-B"))

        def edge(entry):
            return SimpleNamespace(end=end, rows=[SimpleNamespace(protected=[entry])])
        both = [edge(P("stated", None, "a gate as written")), edge(P("none", None, "x"))]
        self.assertEqual(views.connection_protection_sentence(both),
                         "Protected by: 2 connections are points of use: 0 enforced by another component, 0 by the "
                         "target itself, 1 with a written none, 1 stated, not classified, 0 not written.")
        self.assertNotIn("stated", views.connection_protection_sentence(both[1:]))


class RegistryTests(unittest.TestCase):
    def test_every_catalogue_generator_is_registered(self):
        for name in catalogue.GENERATORS:
            self.assertIn(name, views.GENERATORS)

    def test_every_feeding_view_of_the_packaged_catalogue_has_a_generator(self):
        for v in catalogue.load()["views"]:
            if v["status"] == "feeds":
                self.assertIn(v["generator"], views.GENERATORS)


class ViewTextTests(unittest.TestCase):
    def test_view_name(self):
        self.assertEqual(viewtext.view_name("Information: Dictionary"), "Information-Dictionary")

    def test_sources_line_groups_paths_by_member(self):
        m = SimpleNamespace(name="m")
        r1, r2 = SimpleNamespace(path="a.md"), SimpleNamespace(path="b.md")
        self.assertEqual(viewtext.sources_line([(m, r1), (m, r2)]), "Sources: m (`a.md`, `b.md`).")

    def test_exceptions_lists_unsolid_claims_and_says_none_otherwise(self):
        rec = model.Record("m", "a.md", "a.md", "components", "T", "CO-A",
                           claims=[("H", 1, "`built`", ["ok"]), ("H", 2, "`proposed`", ["later"])])
        ctx = views.Ctx([], {}, used=[(SimpleNamespace(name="m"), rec)])
        out = viewtext.exceptions(ctx)
        self.assertIn("| m:CO-A | later | proposed |", out)
        self.assertNotIn("| ok |", out)
        self.assertIn("| none |  |  |", viewtext.exceptions(views.Ctx([], {})))

    def test_ordered_views_follow_the_groups(self):
        cw = {"groups": [{"key": "g2", "title": "Two"}, {"key": "g1", "title": "One"}],
              "views": [{"key": "a", "group": "g1"}, {"key": "b", "group": "g2"}, {"key": "c", "group": "g1"}]}
        self.assertEqual([v["key"] for v in viewtext.ordered_views(cw)], ["b", "a", "c"])

    def test_profile_entry_names_the_missing_targets(self):
        e = viewtext.profile_entry({"key": "K", "title": "A B"})
        self.assertEqual(e["file"], "views/K.md")
        self.assertEqual(set(e["no_target"]), {"dodaf202", "naf4"})
        e = viewtext.profile_entry({"key": "K", "title": "A B", "uaf": "U", "dodaf": ["X"],
                                    "naf": {"read": True, "id": "N"}})
        self.assertEqual((e["file"], e["exports"]), ("views/U.md", {"dodaf202": ["X"], "naf4": ["N"]}))
        self.assertNotIn("no_target", e)


if __name__ == "__main__":
    unittest.main()
