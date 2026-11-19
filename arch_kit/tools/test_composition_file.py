"""Tests for the composition file and the index check's prefixes (testdata/composition/). Every name is invented.

Each case copies the decision-index fixture to a temporary directory, swaps its foreign prefixes for a composition
file, runs the tool in a subprocess (the declaration is read once per process) and asserts the exit code and the line
that names the failure. No pin check is declared in any case: the commits come from the composition file.
"""
from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
INDEX = HERE / "testdata" / "decisions-index"
DATA = HERE / "testdata" / "composition"
BASH = shutil.which("bash")
C1 = "0123456789abcdef0123456789abcdef01234567"
C2 = "89abcdef0123456789abcdef0123456789abcdef"


def load(name):
    return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))


@unittest.skipUnless(BASH, "needs bash on the PATH")
class Composition(unittest.TestCase):
    def setUp(self):
        self.tree = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tree, True)
        shutil.copytree(INDEX / "decisions", self.tree / "decisions")

    def decl(self, edit=None, composition="full.yaml", foreign=False):
        c = yaml.safe_load((INDEX / "arch-kit.yaml").read_text(encoding="utf-8"))
        if not foreign:
            del c["decisions"]["index"]["foreign"]
        if composition is not None:
            c["files"] = {"composition": "composition.yaml"}
        if edit:
            edit(c)
        path = self.tree / "arch-kit.yaml"
        path.write_text(yaml.safe_dump(c), encoding="utf-8", newline="\n")
        return path

    def comp(self, data):
        (self.tree / "composition.yaml").write_text(yaml.safe_dump(data), encoding="utf-8", newline="\n")

    def run_tool(self, tool="check_decision_indexes", composition="full.yaml", edit=None, foreign=False, **env):
        if isinstance(composition, str):
            self.comp(load(composition))
        elif composition is not None:
            self.comp(composition)
        path = self.decl(edit, composition, foreign)
        e = dict(os.environ, ARCH_KIT_CONFIG=str(path), PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8")
        e.update(env)
        return subprocess.run([sys.executable, "-m", "arch_kit", tool], capture_output=True, text=True,
                              encoding="utf-8", env=e, cwd=self.tree)

    def refused(self, data, key, **kw):
        p = self.run_tool(composition=data, **kw)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual(p.stdout, "")
        self.assertTrue(p.stderr.startswith("arch-kit: "), p.stderr)
        self.assertIn("files.composition: " + key, p.stderr)
        return p.stderr

    def full(self, edit):
        c = load("full.yaml")
        edit(c)
        return c


class Accepted(Composition):
    def test_a_full_file(self):
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_components_only(self):
        p = self.run_tool(composition="components-only.yaml")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_a_declaration_path(self):
        p = self.run_tool(composition="declaration-path.yaml")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_the_accessor(self):
        self.comp(load("declaration-path.yaml"))
        path = self.decl()
        code = ("import declared; c = declared.composition('t'); print(c.names(), c.components[0].declaration, "
                "c.components[0].lists, c.consumers[0].declaration, c.consumers[0].commit[:7])")
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", cwd=HERE,
                           env=dict(os.environ, ARCH_KIT_CONFIG=str(path)))
        self.assertEqual(p.stdout.strip(), "('ferro', 'gild') docs/other/arch-kit.yaml "
                                           "Lists(relabel='ferro-relabel', barred='ferro-barred') "
                                           "docs/arch/arch-kit.yaml 89abcde", p.stderr)

    def test_no_files_composition_means_no_composition(self):
        code = "import declared; print(declared.composition('t'))"
        path = self.decl(composition=None, foreign=True)
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", cwd=HERE,
                           env=dict(os.environ, ARCH_KIT_CONFIG=str(path)))
        self.assertEqual(p.stdout.strip(), "None", p.stderr)


class Refused(Composition):
    def test_composition_is_not_1(self):
        for bad in (2, "1", True, None):
            with self.subTest(bad=bad):
                self.refused(self.full(lambda c: c.__setitem__("composition", bad)), "composition:")

    def test_components_is_missing_or_empty(self):
        for bad in ("missing", [], "x"):
            with self.subTest(bad=bad):
                def edit(c):
                    if bad == "missing":
                        del c["components"]
                    else:
                        c["components"] = bad
                self.refused(self.full(edit), "components:")

    def test_an_unknown_key(self):
        self.refused(self.full(lambda c: c.__setitem__("extra", 1)), "extra: unknown key")
        self.refused(self.full(lambda c: c["components"][0].__setitem__("branch", "x")), "components[0].branch")
        self.refused(self.full(lambda c: c["consumers"][0].__setitem__("lists", {})), "consumers[0].lists")

    def test_a_missing_required_key(self):
        for key in ("name", "repo", "commit", "lists"):
            with self.subTest(key=key):
                self.refused(self.full(lambda c: c["components"][0].pop(key)), f"components[0].{key}: missing key")
        for key in ("name", "repo", "commit"):
            with self.subTest(key=key):
                self.refused(self.full(lambda c: c["consumers"][0].pop(key)), f"consumers[0].{key}: missing key")

    def test_a_name_that_is_not_a_project_name(self):
        for bad in ("Ferro", "1x", "a b", "", 5):
            with self.subTest(bad=bad):
                self.refused(self.full(lambda c: c["components"][0].__setitem__("name", bad)), "components[0].name")
                self.refused(self.full(lambda c: c["consumers"][0].__setitem__("name", bad)), "consumers[0].name")

    def test_a_duplicate_name_across_components_and_consumers(self):
        self.refused(self.full(lambda c: c["consumers"][0].__setitem__("name", "ferro")), "consumers[0].name")

    def test_a_name_equal_to_the_local_prefix(self):
        self.refused(self.full(lambda c: c["components"][0].__setitem__("name", "loam")), "components[0].name")

    def test_repo_and_commit(self):
        for bad in ("", "https://example.org/a b.git", None):
            with self.subTest(repo=bad):
                self.refused(self.full(lambda c: c["components"][0].__setitem__("repo", bad)), "components[0].repo")
                self.refused(self.full(lambda c: c["consumers"][0].__setitem__("repo", bad)), "consumers[0].repo")
        for bad in ("main", C1[:7], C1.upper(), "v1", None):
            with self.subTest(commit=bad):
                err = self.refused(self.full(lambda c: c["components"][0].__setitem__("commit", bad)),
                                   "components[0].commit")
                self.assertIn("must be a full commit id (40 or 64 hex characters), not a branch, tag or short id", err)
                self.refused(self.full(lambda c: c["consumers"][0].__setitem__("commit", bad)), "consumers[0].commit")

    def test_declaration_is_not_a_relative_path(self):
        for bad in ("/abs/x.yaml", "../x.yaml", "a/../x.yaml", "C:/x.yaml", "", 3):
            with self.subTest(bad=bad):
                self.refused(self.full(lambda c: c["components"][0].__setitem__("declaration", bad)),
                             "components[0].declaration")
                self.refused(self.full(lambda c: c["consumers"][0].__setitem__("declaration", bad)),
                             "consumers[0].declaration")

    def test_lists_is_not_a_map_with_exactly_relabel_and_barred(self):
        for bad in ("x", {}, {"relabel": "a"}, {"relabel": "a", "barred": "b", "extra": "c"}, {"relabel": "a", "other": "b"}):
            with self.subTest(bad=bad):
                self.refused(self.full(lambda c: c["components"][0].__setitem__("lists", bad)), "components[0].lists")

    def test_a_slot_name_that_does_not_match(self):
        for bad in ("Ferro", "-x", "a_b", "", 3, None):
            with self.subTest(bad=bad):
                self.refused(self.full(lambda c: c["components"][0]["lists"].__setitem__("relabel", bad)),
                             "components[0].lists.relabel")

    def test_a_slot_name_used_twice(self):
        def across(c):
            c["components"].append(dict(c["components"][0], name="third"))
        err = self.refused(self.full(across), "components[1].lists.relabel")
        self.assertIn("used twice", err)
        self.refused(self.full(lambda c: c["components"][0]["lists"].__setitem__("barred", "ferro-relabel")),
                     "components[0].lists.barred")

    def test_a_slot_value_that_is_a_path(self):
        for bad in ("lists/ferro.txt", "..\\ferro.txt", "/etc/x"):
            with self.subTest(bad=bad):
                err = self.refused(self.full(lambda c: c["components"][0]["lists"].__setitem__("barred", bad)),
                                   "components[0].lists.barred")
                self.assertIn("a slot names a slot, never a path", err)

    def test_a_missing_file(self):
        path = self.decl()
        e = dict(os.environ, ARCH_KIT_CONFIG=str(path), PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable, "-m", "arch_kit", "check_decision_indexes"], capture_output=True,
                           text=True, encoding="utf-8", env=e, cwd=self.tree)
        self.assertEqual(p.returncode, 2)
        self.assertIn("files.composition", p.stderr)

    def test_portal_none_with_a_composition(self):
        def edit(c):
            for k in ("paths", "decisions", "files"):
                c.pop(k, None)
            c.update({"portal": "none", "files": {"composition": "composition.yaml"},
                      "consumes": [{"portal": "ferro", "repo": "https://example.org/ferro.git", "commit": C1,
                                    "why": "Uses it."}]})
        p = self.run_tool(tool="check_consumes", edit=edit)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("files.composition: a project with no portal composes nothing", p.stderr)

    def test_declaring_both_sources(self):
        p = self.run_tool(foreign=True)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual(p.stderr.strip().split(": ", 2)[2],
                         "decisions.index.foreign: a project with files.composition takes its foreign prefixes from "
                         "it; declare one, not both")


class IndexCheck(Composition):
    def test_the_summary_names_each_prefix_and_its_commit(self):
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        out = p.stdout.splitlines()
        self.assertIn("  1 ferro:-prefixed reference(s); pinned at 0123456 by the composition file. That each cited "
                      "record", out)
        self.assertIn("  0 gild:-prefixed reference(s); pinned at 89abcde by the composition file. That each cited "
                      "record", out)
        self.assertEqual(out.count("  exists at the pin is checked when composed, not here."), 2)

    def test_no_pin_check_runs(self):
        # The fixture's pin-check stub is not copied here and none is declared; a pin check run would exit 2 or 1.
        self.assertFalse((self.tree / "scripts").exists())
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn("Cites line", p.stdout)
        self.assertNotIn("no pin check is declared", p.stdout)

    def test_pins_out_has_the_lines(self):
        out = self.tree / "pins.txt"
        p = self.run_tool(PINS_OUT=str(out))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(out.read_text(encoding="utf-8").splitlines(), [f"- ferro {C1} -", f"- gild {C2} -"])

    def test_the_prefixes_are_the_known_repos(self):
        (self.tree / "decisions" / "PLAN-build.md").write_text(
            (self.tree / "decisions" / "PLAN-build.md").read_text(encoding="utf-8") + "\nSee zz:ADR-0001.\n",
            encoding="utf-8", newline="\n")
        p = self.run_tool()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("      Known repos: loam, ferro, gild. An unqualified ADR-NNNN means", p.stderr.splitlines())


class EveryRender(unittest.TestCase):
    def test_a_malformed_composition_file_fails_render_html_and_check_export(self):
        sys.path.insert(0, str(HERE))
        import test_example_decisions as ed
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        proj = ed.copy_example(tmp)
        decl = proj / "arch-kit.yaml"
        c = yaml.safe_load(decl.read_text(encoding="utf-8"))
        c["files"] = {"composition": "composition.yaml"}
        decl.write_text(yaml.safe_dump(c), encoding="utf-8", newline="\n")
        (proj / "composition.yaml").write_text("composition: 2\n", encoding="utf-8", newline="\n")
        out = tmp / "export.html"
        p = ed.render(proj, out)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("files.composition: composition: must be 1", p.stderr)
        self.assertFalse(out.exists())
        p = ed.check(proj, out)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
