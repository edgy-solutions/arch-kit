import unittest

from arch_kit.generators import catalogue

GROUPS = [{"key": "g", "title": "G"}]


def view(**kw):
    return {"key": "v", "title": "V", "group": "g", "status": "none", **kw}


class PackagedTests(unittest.TestCase):
    def test_the_packaged_catalogue_loads_and_checks(self):
        cat = catalogue.load()
        self.assertTrue(cat["groups"] and cat["views"])

    def test_the_dictionary_view_needs_a_dictionary_of_the_projects_terms(self):
        am = next(v for v in catalogue.load()["views"] if v["key"] == "Am-If")
        self.assertEqual(am["needs"], "a dictionary of the project's terms")


class MergeTests(unittest.TestCase):
    CAT = {"groups": GROUPS, "views": [view(), view(key="w", title="W")]}

    def test_an_override_sets_a_field_by_key_and_leaves_the_rest(self):
        out = catalogue.merge(self.CAT, {"w": {"title": "Other"}})
        self.assertEqual([v["title"] for v in out["views"]], ["V", "Other"])
        self.assertEqual(self.CAT["views"][1]["title"], "W")

    def test_none_is_no_overrides(self):
        self.assertEqual(catalogue.merge(self.CAT, None)["views"], self.CAT["views"])

    def test_an_unknown_key_is_refused(self):
        with self.assertRaisesRegex(catalogue.CatalogueError, "x: overrides.nope: names a view not in the catalogue"):
            catalogue.merge(self.CAT, {"nope": {}}, "x")

    def test_overrides_must_be_a_map_of_maps(self):
        for bad in ([], {"v": "x"}):
            with self.assertRaisesRegex(catalogue.CatalogueError, "overrides must be a map"):
                catalogue.merge(self.CAT, bad)


class CheckTests(unittest.TestCase):
    def bad(self, groups, views, text):
        with self.assertRaisesRegex(catalogue.CatalogueError, text):
            catalogue.check(groups, views, "c")

    def test_a_good_catalogue_passes(self):
        catalogue.check(GROUPS, [view(), view(key="w", status="feeds", generator="overview")])

    def test_malformed_groups(self):
        self.bad([{"key": "g"}], [], "groups must be a list")

    def test_views_not_a_list(self):
        self.bad(GROUPS, {}, "views must be a list")

    def test_a_view_needs_a_key_and_a_title(self):
        self.bad(GROUPS, [view(key="")], "a view needs a key")
        self.bad(GROUPS, [view(title="")], "v needs a title")

    def test_duplicate_keys(self):
        self.bad(GROUPS, [view(), view()], "duplicate view key v")

    def test_unknown_group(self):
        self.bad(GROUPS, [view(group="z")], "names a group not in groups")

    def test_status(self):
        self.bad(GROUPS, [view(status="maybe")], "must be feeds, fields or none")

    def test_generator(self):
        self.bad(GROUPS, [view(generator="nope")], "names an unknown generator")
        self.bad(GROUPS, [view(status="feeds")], "is feeds and has no generator")


if __name__ == "__main__":
    unittest.main()
