"""Self-test: the alignment record (docs/design/alignment.md): the schema, the checks, both routes.

Each case builds a project in a temporary directory from examples/decisions-only, adds `files.alignment` (or a loader
that defines `load_alignment`), puts one record in it and renders. An accepted record exits 0; a refused one exits 2
and its message names the path in the record.
"""
from __future__ import annotations

import copy
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))

import alignment  # noqa: E402
from test_example_decisions import KIT, copy_example, render  # noqa: E402

GOOD = yaml.safe_load((HERE / "testdata" / "alignment" / "good.yaml").read_text(encoding="utf-8"))
SEEDED = yaml.safe_load((HERE / "testdata" / "alignment" / "seeded.yaml").read_text(encoding="utf-8"))

LOADER_TAIL = '''

def load_alignment(root):
    import yaml
    out = yaml.safe_load((Path(root) / "records.yaml").read_text(encoding="utf-8"))
    return out
'''


def good() -> dict:
    return copy.deepcopy(GOOD)


def seeded() -> dict:
    return copy.deepcopy(SEEDED)


class Project:
    """A temporary project built from the decisions-only example, with alignment records by one route or the other."""

    def __init__(self, test: unittest.TestCase, route: str = "file"):
        self.tmp = Path(tempfile.mkdtemp())
        test.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = copy_example(self.tmp)
        self.route = route
        self.out = self.tmp / "export.html"
        decl = yaml.safe_load((self.root / "arch-kit.yaml").read_text(encoding="utf-8"))
        decl["decisions"]["index"]["foreign"] = [{"prefix": "other"}]
        if route == "file":
            decl["files"] = {"alignment": "alignment"}
        elif route == "loader":
            decl["loader"] = "alignment_loader.py"
            text = (self.root / "kit_loader.py").read_text(encoding="utf-8")
            (self.root / "alignment_loader.py").write_text(text + LOADER_TAIL, encoding="utf-8")
        self.decl = decl
        self.write_decl()

    def write_decl(self):
        (self.root / "arch-kit.yaml").write_text(yaml.safe_dump(self.decl, sort_keys=False), encoding="utf-8")

    def put(self, name: str, record) -> None:
        if self.route == "file":
            d = self.root / "alignment"
            d.mkdir(exist_ok=True)
            (d / f"{name}.yaml").write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
        else:
            (self.root / "records.yaml").write_text(yaml.safe_dump({name: record}, sort_keys=False), encoding="utf-8")

    def render(self):
        return render(self.root, self.out)


def body(stderr: str) -> str:
    """The message after the `<where>: ` part."""
    line = [ln for ln in stderr.splitlines() if ln.strip()][-1]
    return re.sub(r"^error: (alignment/[^:]*|alignment record [^:]*): ", "", line)


def mut(fn):
    def apply(rec):
        fn(rec)
        return rec
    return apply


def row(rec, element):
    return next(r for r in rec["rows"] if r["element"] == element)


def drop(d, *keys):
    for k in keys:
        d.pop(k, None)


# (name, change to the good record, the path the message names, text it holds)
REFUSED = [
    # the schema
    ("no title", mut(lambda r: drop(r, "title")), "title", "is required"),
    ("unknown top key", mut(lambda r: r.update(bogus=1)), "bogus", "unknown key"),
    ("empty title", mut(lambda r: r.update(title=" ")), "title", "non-empty"),
    ("no references", mut(lambda r: r.update(references=[])), "references", ""),
    ("no rows key", mut(lambda r: drop(r, "rows")), "rows", "is required"),
    ("unknown reference key", mut(lambda r: r["references"][0].update(bogus=1)), "references.0.bogus", "unknown key"),
    ("bad reference key", mut(lambda r: r["references"][0].update(key="Ref A")), "references.0.key", "[a-z0-9]"),
    ("no reference key", mut(lambda r: drop(r["references"][0], "key")), "references.0.key", "is required"),
    ("bad read value", mut(lambda r: r["references"][0].update(read="all")), "references.0.read", ""),
    ("partial without read_note", mut(lambda r: drop(r["references"][0], "read_note")),
     "references.0.read_note", "is required"),
    ("title-only without read_note", mut(lambda r: drop(r["references"][1], "read_note")),
     "references.1.read_note", "is required"),
    ("no reference title", mut(lambda r: drop(r["references"][0], "title")), "references.0.title", "is required"),
    ("no edition", mut(lambda r: drop(r["references"][0], "edition")), "references.0.edition", "is required"),
    ("no terms", mut(lambda r: drop(r["references"][0], "terms")), "references.0.terms", "is required"),
    ("bad terms status", mut(lambda r: r["references"][0]["terms"].update(status="open")),
     "references.0.terms.status", ""),
    ("no terms basis", mut(lambda r: drop(r["references"][0]["terms"], "basis")), "references.0.terms.basis",
     "is required"),
    ("no terms cite", mut(lambda r: drop(r["references"][0]["terms"], "cite")), "references.0.terms.cite",
     "is required"),
    ("unknown terms key", mut(lambda r: r["references"][0]["terms"].update(x=1)), "references.0.terms.x",
     "unknown key"),
    ("element without where", mut(lambda r: drop(r["references"][0]["elements"][1], "where")),
     "references.0.elements.1.where", "is required"),
    ("element id pattern", mut(lambda r: r["references"][0]["elements"][1].update(id="E 2")),
     "references.0.elements.1.id", "[a-z0-9]"),
    ("element unknown key", mut(lambda r: r["references"][0]["elements"][0].update(x=1)),
     "references.0.elements.0.x", "unknown key"),
    ("row without ref", mut(lambda r: drop(r["rows"][0], "ref")), "rows.0.ref", "is required"),
    ("row without element", mut(lambda r: drop(r["rows"][0], "element")), "rows.0.element", "is required"),
    ("row without correspondence", mut(lambda r: drop(r["rows"][0], "correspondence")), "rows.0.correspondence",
     "is required"),
    ("row with a sixth value", mut(lambda r: r["rows"][0].update(correspondence="planned")),
     "rows.0.correspondence", ""),
    ("row unknown key", mut(lambda r: r["rows"][0].update(x=1)), "rows.0.x", "unknown key"),
    ("corresponds without counterpart", mut(lambda r: drop(r["rows"][0], "counterpart")), "rows.0.counterpart",
     "is required"),
    ("partial without counterpart", mut(lambda r: drop(r["rows"][1], "counterpart")), "rows.1.counterpart",
     "is required"),
    ("corresponds without evidence", mut(lambda r: drop(r["rows"][0], "evidence")), "rows.0.evidence",
     "is required"),
    ("partial without evidence", mut(lambda r: drop(r["rows"][1], "evidence")), "rows.1.evidence", "is required"),
    ("empty evidence", mut(lambda r: r["rows"][0].update(evidence=[])), "rows.0.evidence", ""),
    ("none with a counterpart", mut(lambda r: r["rows"][2].update(counterpart="x")), "rows.2.counterpart",
     "must be absent"),
    ("not-applicable with a counterpart", mut(lambda r: r["rows"][3].update(counterpart="x")),
     "rows.3.counterpart", "must be absent"),
    ("not_assessed with a counterpart", mut(lambda r: r["rows"][4].update(counterpart="x")),
     "rows.4.counterpart", "must be absent"),
    ("not_assessed with evidence", mut(lambda r: r["rows"][4].update(evidence=["ADR-0001"])), "rows.4.evidence",
     "must be absent"),
    ("none without a note", mut(lambda r: drop(r["rows"][2], "note")), "rows.2.note", "is required"),
    ("not-applicable without a note", mut(lambda r: drop(r["rows"][3], "note")), "rows.3.note", "is required"),
    ("owed on corresponds", mut(lambda r: r["rows"][0].update(owed="ADR-0002")), "rows.0.owed", "must be absent"),
    ("owed on not-applicable", mut(lambda r: r["rows"][3].update(owed="ADR-0002")), "rows.3.owed",
     "must be absent"),
    ("owed on not_assessed", mut(lambda r: r["rows"][4].update(owed="ADR-0002")), "rows.4.owed", "must be absent"),
    # the checks
    ("duplicate reference key", mut(lambda r: r["references"][1].update(key="ref-a")), "references.1.key",
     "not unique"),
    ("duplicate element id", mut(lambda r: r["references"][0]["elements"][1].update(id="e1")),
     "references.0.elements.1.id", "not unique"),
    ("title-only with elements", mut(lambda r: r["references"][1].update(elements=[
        {"id": "x1", "name": "X", "where": "w", "group": "g"}])), "references.1.elements", "title-only"),
    ("title-only with groups", mut(lambda r: r["references"][1].update(groups=["g"])), "references.1.groups",
     "title-only"),
    ("title-only with a row", mut(lambda r: r["rows"].append(
        {"ref": "ref-b", "element": "x1", "correspondence": "not_assessed"})), "rows.5.ref", "title-only"),
    ("a compared reference with no elements", mut(lambda r: drop(r["references"][0], "elements")),
     "references.0.elements", "no compared element"),
    ("groups without a seed", mut(lambda r: r["references"][0].update(groups=["Part 1: roles"])),
     "references.0.groups", "needs a seed"),
    ("row for an unknown reference", mut(lambda r: r["rows"][0].update(ref="ref-z")), "rows.0.ref",
     "not a reference key"),
    ("row for an unknown element", mut(lambda r: r["rows"][0].update(element="e9")), "rows.0.element",
     "not a compared element"),
    ("second row for an element", mut(lambda r: r["rows"].append(
        {"ref": "ref-a", "element": "e5", "correspondence": "not_assessed"})), "rows.5", "second row"),
    ("missing row", mut(lambda r: r["rows"].pop(2)), "rows", "no row for ref ref-a element e3"),
    ("evidence: unknown decision", mut(lambda r: r["rows"][0].update(evidence=["ADR-0099"])), "rows.0.evidence.0",
     "does not resolve"),
    ("evidence: second entry unknown", mut(lambda r: r["rows"][0].update(evidence=["ADR-0001", "ADR-0099"])),
     "rows.0.evidence.1", "does not resolve"),
    ("evidence: undeclared prefix", mut(lambda r: r["rows"][0].update(evidence=["nope:ADR-0001"])),
     "rows.0.evidence.0", "does not resolve"),
    ("evidence: foreign id of the wrong form", mut(lambda r: r["rows"][0].update(evidence=["other:7"])),
     "rows.0.evidence.0", "does not resolve"),
    ("evidence: path that does not exist", mut(lambda r: r["rows"][0].update(evidence=["decisions/none.md"])),
     "rows.0.evidence.0", "does not resolve"),
    ("evidence: path with ..", mut(lambda r: r["rows"][0].update(evidence=["decisions/../arch-kit.yaml"])),
     "rows.0.evidence.0", "does not resolve"),
    ("evidence: absolute path", mut(lambda r: r["rows"][0].update(evidence=["/arch-kit.yaml"])),
     "rows.0.evidence.0", "does not resolve"),
    ("owed: unknown decision", mut(lambda r: r["rows"][1].update(owed="ADR-0099")), "rows.1.owed",
     "does not resolve"),
    ("owed: a path", mut(lambda r: r["rows"][1].update(owed="decisions/README.md")), "rows.1.owed",
     "does not resolve"),
    ("owed: undeclared prefix", mut(lambda r: r["rows"][2].update(owed="nope:ADR-0008")), "rows.2.owed",
     "does not resolve"),
]


class Accepted(unittest.TestCase):
    def test_the_good_record_is_accepted_by_the_file_route(self):
        p = Project(self)
        p.put("coverage", good())
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_good_record_is_accepted_by_the_loader_route(self):
        p = Project(self, "loader")
        p.put("coverage", good())
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_route_means_no_alignment_and_exit_0(self):
        p = Project(self, "none")
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_good_fixture_uses_every_value(self):
        self.assertEqual({r["correspondence"] for r in GOOD["rows"]},
                         {"corresponds", "partial", "none", "not-applicable", "not_assessed"})
        fields = {k for r in GOOD["references"] for k in r}
        self.assertTrue({"key", "title", "edition", "identifier", "obtained", "read", "read_note", "terms",
                         "elements"} <= fields)
        self.assertTrue({"counterpart", "evidence", "note", "owed"} <= {k for r in GOOD["rows"] for k in r})
        self.assertTrue({"status", "context"} <= set(GOOD))


class Refused(unittest.TestCase):
    def test_every_rule_refuses_its_record_and_names_the_path(self):
        p = Project(self)
        for name, change, path, text in REFUSED:
            with self.subTest(name):
                p.put("coverage", change(good()))
                r = p.render()
                self.assertEqual(r.returncode, 2, name + "\n" + r.stdout + r.stderr)
                self.assertIn(f"alignment/coverage.yaml: {path}: ", r.stderr, name)
                self.assertIn(text, r.stderr, name)

    def test_the_loader_route_gives_the_same_message_body(self):
        files, loader = Project(self), Project(self, "loader")
        for name, change, path, text in REFUSED[::7]:
            with self.subTest(name):
                files.put("coverage", change(good()))
                loader.put("coverage", change(good()))
                a, b = files.render(), loader.render()
                self.assertEqual((a.returncode, b.returncode), (2, 2), name)
                self.assertIn("alignment record coverage: ", b.stderr)
                self.assertEqual(body(a.stderr), body(b.stderr), name)

    def test_the_first_error_wins(self):
        p = Project(self)
        rec = good()
        rec["rows"][0]["evidence"] = ["ADR-0099"]
        rec["rows"][1]["evidence"] = ["ADR-0098"]
        p.put("coverage", rec)
        r = p.render()
        self.assertIn("rows.0.evidence.0", r.stderr)
        self.assertNotIn("rows.1.evidence", r.stderr)

    def test_the_schema_runs_before_the_checks(self):
        p = Project(self)
        rec = good()
        rec["rows"][0]["evidence"] = ["ADR-0099"]
        rec["rows"][4]["evidence"] = ["ADR-0001"]  # not_assessed: a schema error
        p.put("coverage", rec)
        r = p.render()
        self.assertIn("rows.4.evidence: must be absent", r.stderr)


class Declaration(unittest.TestCase):
    def test_both_routes_declared_exits_2_naming_both(self):
        p = Project(self, "loader")
        p.decl["files"] = {"alignment": "alignment"}
        p.write_decl()
        p.put("coverage", good())
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("files.alignment", r.stderr)
        self.assertIn("load_alignment", r.stderr)

    def test_a_declared_directory_that_does_not_exist_exits_2(self):
        p = Project(self)
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("files.alignment", r.stderr)

    def test_a_declared_directory_with_no_record_exits_2(self):
        p = Project(self)
        (p.root / "alignment").mkdir()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("files.alignment", r.stderr)

    def test_the_key_must_be_a_plain_relative_path(self):
        p = Project(self)
        p.decl["files"] = {"alignment": "../elsewhere"}
        p.write_decl()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("files.alignment", r.stderr)

    def test_an_unknown_files_key_still_exits_2_and_lists_alignment(self):
        p = Project(self)
        p.decl["files"] = {"bogus": "x"}
        p.write_decl()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("files.bogus", r.stderr)
        self.assertIn("alignment", r.stderr)

    def test_a_file_name_that_is_not_a_record_name_exits_2(self):
        p = Project(self)
        p.put("Bad Name", good())
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Bad Name.yaml", r.stderr)

    def test_a_file_that_is_not_yaml_or_not_a_mapping_exits_2(self):
        p = Project(self)
        p.put("coverage", ["a", "list"])
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("alignment/coverage.yaml: (record): ", r.stderr)
        (p.root / "alignment" / "coverage.yaml").write_text("a: [", encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("not valid YAML", r.stderr)

    def test_the_loader_returning_anything_but_a_dict_of_dicts_exits_2(self):
        p = Project(self, "loader")
        for value in ([good()], {"coverage": [1]}, {"coverage": None}):
            (p.root / "records.yaml").write_text(yaml.safe_dump(value), encoding="utf-8")
            r = p.render()
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("load_alignment", r.stderr)

    def test_the_loader_function_is_optional_and_not_in_the_seam_names(self):
        import seam
        self.assertNotIn("load_alignment", seam.NAMES)
        self.assertTrue(hasattr(seam.Loader, "load_alignment"))

    def test_the_records_are_read_in_sorted_order(self):
        p = Project(self)
        p.put("b-second", good())
        bad = good()
        bad.pop("title")
        p.put("a-first", bad)
        r = p.render()
        self.assertIn("alignment/a-first.yaml: title: is required", r.stderr)


class Seeds(unittest.TestCase):
    def files(self):
        found = sorted((KIT / "arch_kit" / "references").glob("*.yaml"))
        self.assertTrue(found)
        return found

    def test_every_seed_validates_as_a_seed(self):
        for f in self.files():
            with self.subTest(f.name):
                alignment.validate_seed(f.name, yaml.safe_load(f.read_text(encoding="utf-8")))

    def test_every_seed_is_public(self):
        for f in self.files():
            with self.subTest(f.name):
                self.assertEqual(yaml.safe_load(f.read_text(encoding="utf-8"))["terms"]["status"], "public")

    def test_every_seed_has_unique_ids_and_four_fields_per_element(self):
        for f in self.files():
            with self.subTest(f.name):
                els = yaml.safe_load(f.read_text(encoding="utf-8"))["elements"]
                self.assertEqual(len({e["id"] for e in els}), len(els))
                for e in els:
                    self.assertEqual(set(e), {"id", "name", "where", "group"})
                    self.assertTrue(all(isinstance(v, str) and v.strip() for v in e.values()))

    def test_the_first_seed_has_the_groups_in_the_ruled_order(self):
        seed = alignment.load_seed("nato-dcra-v2")
        self.assertEqual(alignment._group_order(seed["elements"]),
                         ["Appendix 9: roles", "Appendix 9: services", "Appendix 4: data-product characteristics",
                          "Appendix 14: planes"])
        self.assertEqual(len(seed["elements"]), 21)

    def test_a_seed_that_breaks_the_seed_schema_is_refused(self):
        seed = yaml.safe_load((KIT / "arch_kit" / "references" / "nato-dcra-v2.yaml").read_text(encoding="utf-8"))
        del seed["elements"][0]["where"]
        with self.assertRaises(alignment.InputError):
            alignment.validate_seed("x", seed)
        seed["elements"][0]["where"] = "w"
        seed["elements"][1]["id"] = seed["elements"][0]["id"]
        with self.assertRaises(alignment.InputError):
            alignment.validate_seed("x", seed)


# (name, change to the seeded record, the path the message names, text it holds)
SEED_REFUSED = [
    ("an unknown seed", mut(lambda r: r["references"][0].update(seed="no-such-seed")), "references.0.seed",
     "no-such-seed"),
    ("a seed name that is not a name", mut(lambda r: r["references"][0].update(seed="../x")),
     "references.0.seed", ""),
    ("a group the seed does not have", mut(lambda r: r["references"][0].update(groups=["Appendix 99: nothing"])),
     "references.0.groups.0", "not a group of seed nato-dcra-v2"),
    ("a group listed twice", mut(lambda r: r["references"][0].update(
        groups=["Appendix 9: roles", "Appendix 9: roles"])), "references.0.groups.1", "listed twice"),
    ("an inline id that is a seed id", mut(lambda r: r["references"][0]["elements"][0].update(id="ap9-pep")),
     "references.0.elements.0.id", "ap9-pep"),
    ("an inline id that is an id of a group the seed filtered out",
     mut(lambda r: r["references"][0]["elements"][0].update(id="ap4-lifecycle")),
     "references.0.elements.0.id", "ap4-lifecycle"),
    ("a row for an element groups filtered out", mut(lambda r: r["rows"].append(
        {"ref": "dcra", "element": "ap4-lifecycle", "correspondence": "not_assessed"})), "rows.11.element",
     "not a compared element"),
    ("a missing row for a seed element", mut(lambda r: r["rows"].pop(4)), "rows",
     "no row for ref dcra element ap9-crypto"),
    ("a seed with title-only", mut(lambda r: r["references"][0].update(read="title-only")),
     "references.0.seed", "title-only"),
    ("groups without a seed", mut(lambda r: (drop(r["references"][0], "seed"), r["references"][0].update(
        title="T", edition="E", terms={"status": "public", "basis": "b", "cite": "c"}))),
     "references.0.groups", "needs a seed"),
]


class Seeded(unittest.TestCase):
    def ctx(self):
        return alignment.Context("render_html", ["ADR-0001", "ADR-0002", "ADR-0003"], KIT / "examples" / "decisions-only")

    def test_the_fixture_over_the_seed_is_accepted_by_both_routes(self):
        self.assertEqual(len(SEEDED["rows"]), 11)
        for route in ("file", "loader"):
            with self.subTest(route):
                p = Project(self, route)
                p.put("coverage", seeded())
                r = p.render()
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_seed_supplies_title_edition_identifier_and_terms_and_the_record_wins(self):
        rec = seeded()
        ref = alignment.merge("x", rec)["references"][0]
        self.assertEqual(ref["title"], "Data Centric Reference Architecture for the Alliance")
        self.assertEqual(ref["identifier"], "AC/322-D(2025)0056")
        self.assertEqual(ref["terms"]["status"], "public")
        rec["references"][0]["title"] = "Our title"
        rec["references"][0]["terms"] = {"status": "unconfirmed", "basis": "b", "cite": "c"}
        ref = alignment.merge("x", rec)["references"][0]
        self.assertEqual((ref["title"], ref["terms"]["status"], ref["edition"]),
                         ("Our title", "unconfirmed", "Version 2, 2025"))

    def test_the_compared_elements_are_the_seeds_in_order_then_the_inline_ones(self):
        ref = alignment.validate("x", seeded(), self.ctx())["references"][0]
        self.assertEqual([e["id"] for e in ref["compared"]],
                         ["ap9-pep", "ap9-pdp", "ap9-pip", "ap9-pap", "ap9-crypto", "ap9-authz", "ap9-authn",
                          "ap9-certs", "ap9-identity", "local-audit", "local-export"])
        self.assertEqual(ref["left_out"], ["Appendix 4: data-product characteristics", "Appendix 14: planes"])

    def test_a_seed_with_no_groups_compares_every_element_and_leaves_none_out(self):
        rec = seeded()
        del rec["references"][0]["groups"]
        ref = alignment.merge("x", rec)["references"][0]
        els, left = alignment._compared("x", 0, ref)
        self.assertEqual((len(els), left), (23, []))

    def test_every_refusal_names_the_path(self):
        p = Project(self)
        for name, change, path, text in SEED_REFUSED:
            with self.subTest(name):
                p.put("coverage", change(seeded()))
                r = p.render()
                self.assertEqual(r.returncode, 2, name + "\n" + r.stdout + r.stderr)
                self.assertIn(f"alignment/coverage.yaml: {path}: ", r.stderr, name)
                self.assertIn(text, r.stderr, name)


class Audience(unittest.TestCase):
    """AL-4: a public portal shows unconfirmed terms by title only and never shows restricted terms."""

    def finish(self, rec, audience):
        ctx = alignment.Context("render_html", ["ADR-0001", "ADR-0002", "ADR-0003"], KIT / "examples" / "decisions-only",
                                audience=audience)
        ctx._foreign = {"other"}
        return alignment._finish("alignment/coverage.yaml", rec, ctx)

    def with_status(self, key: str, status: str):
        rec = good()
        next(r for r in rec["references"] if r["key"] == key)["terms"]["status"] = status
        return rec

    def test_public_refuses_an_unconfirmed_reference_that_has_elements(self):
        with self.assertRaises(alignment.InputError) as c:
            self.finish(self.with_status("ref-a", "unconfirmed"), "public")
        self.assertEqual(str(c.exception), "alignment/coverage.yaml: references.0: reference ref-a has unconfirmed "
                         "terms; a public portal shows it by title only, so it may carry no elements")

    def test_public_accepts_an_unconfirmed_title_only_reference(self):
        self.finish(good(), "public")

    def test_public_refuses_restricted_whether_or_not_title_only(self):
        for key, i in (("ref-a", 0), ("ref-b", 1)):
            with self.subTest(key):
                with self.assertRaises(alignment.InputError) as c:
                    self.finish(self.with_status(key, "restricted"), "public")
                self.assertEqual(str(c.exception), f"alignment/coverage.yaml: references.{i}: reference {key} has "
                                 "restricted terms; a public portal may not show it")

    def test_private_shows_all_three(self):
        rec = good()
        rec["references"][0]["terms"]["status"] = "restricted"
        rec["references"][1]["terms"]["status"] = "restricted"
        self.finish(rec, "private")
        self.finish(self.with_status("ref-a", "unconfirmed"), "private")


if __name__ == "__main__":
    unittest.main()
