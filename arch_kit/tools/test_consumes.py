"""Tests for `consumes:`, `portal: none` and check_consumes (testdata/consumes/). Every name is invented.

Each case writes a declaration to a temporary directory and runs a tool in a subprocess (the declaration is read once
per process). check_consumes is checked against a fixture git repository built in setUpClass; nothing is fetched.
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
sys.path.insert(0, str(HERE))
KIT = HERE.parents[1]
DATA = HERE / "testdata" / "consumes"
C1 = "0123456789abcdef0123456789abcdef01234567"
GOOD = {"portal": "example-platform", "repo": "https://example.org/example-platform.git", "commit": C1,
        "why": "Labels its outbound records with the platform's label model."}


def load(name):
    return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.org",
                           "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_tool(self, config, tool="check_consumes", *args, **env):
        path = self.tmp / "arch-kit.yaml"
        path.write_text(yaml.safe_dump(config), encoding="utf-8", newline="\n")
        e = dict(os.environ, ARCH_KIT_CONFIG=str(path), PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8")
        e.update(env)
        return subprocess.run([sys.executable, "-m", "arch_kit", tool, *args], capture_output=True, text=True,
                              encoding="utf-8", env=e, cwd=self.tmp)

    def consumer(self, **entry):
        c = load("full.yaml")
        c["consumes"] = [dict(copy.deepcopy(GOOD), **entry)]
        return c

    def refused(self, config, key, tool="check_consumes", *args):
        p = self.run_tool(config, tool, *args)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual(p.stdout, "")
        self.assertIn(key, p.stderr)
        self.assertTrue(p.stderr.startswith("arch-kit: "), p.stderr)
        return p.stderr


class Accepted(Base):
    def test_a_full_entry(self):
        p = self.run_tool(load("full.yaml"))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("consumes[0]: example-platform: not checked: no checkout given", p.stdout)
        self.assertIn("check_consumes: 2 entries: 0 checked, 2 not checked, 0 failed", p.stdout)

    def test_a_minimal_entry(self):
        p = self.run_tool(load("minimal.yaml"))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("check_consumes: 1 entries: 0 checked, 1 not checked, 0 failed", p.stdout)

    def test_a_64_hex_commit(self):
        p = self.run_tool(self.consumer(commit="ab" * 32))
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_portal_none_with_no_paths(self):
        p = self.run_tool(load("none.yaml"))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("1 not checked", p.stdout)

    def test_no_consumes_says_so(self):
        c = load("full.yaml")
        del c["consumes"]
        p = self.run_tool(c)
        self.assertEqual((p.returncode, p.stdout), (0, "check_consumes: no consumes: declared\n"))

    def test_the_accessor_returns_named_fields(self):
        sys.path.insert(0, str(HERE))
        code = ("import declared; e = declared.consumes('t'); print(len(e), e[0].portal, e[0].drift, e[0].records, "
                "e[1].records, e[1].drift)")
        path = self.tmp / "arch-kit.yaml"
        path.write_text(yaml.safe_dump(load("full.yaml")), encoding="utf-8")
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", cwd=HERE,
                           env=dict(os.environ, ARCH_KIT_CONFIG=str(path)))
        self.assertEqual(p.stdout.strip(), "2 example-platform fail ('ADR-0012', 'capability:LabelledRecords') None warn",
                         p.stderr)


class Refused(Base):
    def test_consumes_is_not_a_list_of_maps(self):
        for bad in ("x", [], ["x"], {"portal": "a"}):
            with self.subTest(bad=bad):
                c = load("full.yaml")
                c["consumes"] = bad
                self.refused(c, "consumes: must be a non-empty list of maps")

    def test_an_unknown_key(self):
        self.refused(self.consumer(branch="main"), "consumes[0]: unknown key 'branch'")

    def test_a_missing_required_key(self):
        for key in ("portal", "repo", "commit", "why"):
            with self.subTest(key=key):
                c = self.consumer()
                del c["consumes"][0][key]
                self.refused(c, f"consumes[0].{key}: missing key")

    def test_portal_is_not_a_project_name(self):
        for bad in ("Example", "1abc", "a b", "", 3):
            with self.subTest(bad=bad):
                self.refused(self.consumer(portal=bad), "consumes[0].portal")

    def test_repo_is_empty_or_has_whitespace(self):
        for bad in ("", "https://example.org/a b.git", " x", None):
            with self.subTest(bad=bad):
                self.refused(self.consumer(repo=bad), "consumes[0].repo")

    def test_commit_must_be_a_full_commit(self):
        for bad in ("main", "v1.0.0", C1[:7], C1[:39], C1.upper(), C1 + "0", "g" * 40, None):
            with self.subTest(bad=bad):
                err = self.refused(self.consumer(commit=bad), "consumes[0].commit")
                self.assertIn("must be a full commit id (40 or 64 hex characters), not a branch, tag or short id", err)

    def test_why_is_empty_or_has_a_newline(self):
        for bad in ("", "  ", "one\ntwo", None):
            with self.subTest(bad=bad):
                self.refused(self.consumer(why=bad), "consumes[0].why")

    def test_drift_is_not_warn_or_fail(self):
        self.refused(self.consumer(drift="ignore"), "consumes[0].drift")

    def test_two_entries_with_the_same_portal(self):
        c = self.consumer()
        c["consumes"].append(dict(GOOD, commit="ab" * 20))
        self.refused(c, "consumes[1].portal")

    def test_records_shape(self):
        for bad in ("ADR-0001", [], [3], ["capability:"], ["capability:a b"],
                    ["ADR-0001", "ADR-0001"], ["capability:x", "capability:x"]):
            with self.subTest(bad=bad):
                self.refused(self.consumer(records=bad), "consumes[0].records")

    def test_any_prefix_and_digit_count_is_accepted(self):
        p = self.run_tool(self.consumer(records=["DR-002", "ADR-0012", "X1-7"]))
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_a_malformed_record_id(self):
        for bad in ("dr-2", "DR-", "DR 002", "DR-0a", "-002"):
            with self.subTest(bad=bad):
                self.refused(self.consumer(records=[bad]), "consumes[0].records[0]")

    def test_render_html_and_check_export_refuse_a_malformed_consumes(self):
        for tool in ("render_html", "check_export"):
            with self.subTest(tool=tool):
                self.refused(self.consumer(commit="main"), "consumes[0].commit", tool)

    def test_portal_none_without_consumes(self):
        c = load("none.yaml")
        del c["consumes"]
        self.refused(c, "portal: none needs consumes:")


class PortalNone(Base):
    def test_render_html_writes_no_file_and_exits_0(self):
        out = self.tmp / "export.html"
        p = self.run_tool(load("none.yaml"), "render_html", "--out", str(out))
        self.assertEqual((p.returncode, p.stdout), (0, "portal: none: nothing to render\n"), p.stderr)
        self.assertFalse(out.exists())

    def test_check_views_exits_2(self):
        p = self.run_tool(load("none.yaml"), "check_views")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual(p.stderr.strip(), f"arch-kit: {self.tmp / 'arch-kit.yaml'}: portal: none: check_views has "
                                           f"no portal to check")

    def test_every_other_tool_with_a_main_exits_2(self):
        tools = ("adr_sections", "browser_facts", "check_annotations", "check_decision_indexes", "check_export",
                 "check_views", "check_views_canary", "data_exchange", "portal", "render_profile", "validate_sysml")
        for tool in tools:
            with self.subTest(tool=tool):
                p = self.run_tool(load("none.yaml"), tool)
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertTrue(p.stderr.strip().endswith(f"portal: none: {tool} has no portal to check"), p.stderr)

    def test_paths_when_present_are_read_as_today(self):
        c = load("none.yaml")
        c["paths"] = {"root": "."}
        self.refused(c, "missing key 'paths.repo'")

    def test_other_declarations_still_need_paths(self):
        c = load("full.yaml")
        del c["paths"]
        self.refused(c, "missing key 'paths'")


class CheckConsumes(Base):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(tempfile.mkdtemp())
        git(cls.repo, "init", "-q")
        (cls.repo / "docs" / "arch").mkdir(parents=True)
        (cls.repo / "decisions").mkdir()
        decl = cls.repo / "docs" / "arch" / "arch-kit.yaml"
        base = {"kit": 1, "paths": {"root": ".", "repo": "../..", "decisions": "../../decisions"}}
        decl.write_text(yaml.safe_dump(base), encoding="utf-8", newline="\n")
        (cls.repo / "decisions" / "ADR-0001-first.md").write_text("# ADR-0001\n", encoding="utf-8", newline="\n")
        git(cls.repo, "add", "docs/arch/arch-kit.yaml", "decisions/ADR-0001-first.md")
        git(cls.repo, "commit", "-q", "-m", "first")
        cls.c1 = git(cls.repo, "rev-parse", "HEAD")
        # The second commit moves the project to its own record grammar, DR with three digits. Only its declaration says so.
        base["decisions"] = {"records": {"prefix": "DR", "digits": 3}}
        decl.write_text(yaml.safe_dump(base), encoding="utf-8", newline="\n")
        git(cls.repo, "mv", "decisions/ADR-0001-first.md", "decisions/DR-001-first.md")
        (cls.repo / "decisions" / "DR-002-second.md").write_text("# DR-002\n", encoding="utf-8", newline="\n")
        git(cls.repo, "add", "docs/arch/arch-kit.yaml", "decisions/DR-002-second.md")
        git(cls.repo, "commit", "-q", "-m", "second")
        cls.c2 = git(cls.repo, "rev-parse", "HEAD")

    @classmethod
    def tearDownClass(cls):
        def clear(func, path, _):
            os.chmod(path, 0o700)
            func(path)
        shutil.rmtree(cls.repo, onerror=clear)

    def check(self, commit, records, *extra, name="example-platform", checkout=True):
        args = ["--checkout", f"{name}={self.repo}", *extra] if checkout else list(extra)
        return self.run_tool(self.consumer(commit=commit, records=records), "check_consumes", *args)

    def test_pin_found_and_all_ids_present(self):
        p = self.check(self.c2, ["DR-001", "DR-002"])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("check_consumes: 1 entries: 1 checked, 0 not checked, 0 failed", p.stdout)

    def test_a_consumer_on_the_default_grammar_finds_a_dr_record(self):
        # The consumer stays on ADR/4; the consumed declaration at the pin says DR/3.
        self.assertEqual(self.check(self.c2, ["DR-002"]).returncode, 0)
        p = self.check(self.c1, ["DR-002"])
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn(f"consumes[0]: example-platform: DR-002 not found at {self.c1[:7]}", p.stdout)

    def test_an_id_in_the_consumers_own_grammar_is_not_found_in_the_dr_project(self):
        p = self.check(self.c2, ["ADR-0012"])
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn(f"consumes[0]: example-platform: ADR-0012 not found at {self.c2[:7]}", p.stdout)

    def test_an_explicit_declaration_path(self):
        p = self.check(self.c2, ["DR-002"], name="example-platform")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = self.run_tool(self.consumer(commit=self.c2, records=["DR-002"]), "check_consumes", "--checkout",
                          f"example-platform={self.repo}:docs/arch/arch-kit.yaml")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = self.run_tool(self.consumer(commit=self.c2, records=["DR-002"]), "check_consumes", "--checkout",
                          f"example-platform={self.repo}:docs/arch/missing.yaml")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("declaration docs/arch/missing.yaml not found at " + self.c2[:7], p.stdout)

    def test_pin_not_found(self):
        p = self.check("f" * 40, ["DR-001"])
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("consumes[0]: example-platform: pin not found: fffffff", p.stdout)
        self.assertIn("0 checked, 0 not checked, 1 failed", p.stdout)

    def test_an_id_present_only_at_the_later_commit(self):
        p = self.check(self.c1, ["ADR-0001", "DR-002"])
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn(f"consumes[0]: example-platform: DR-002 not found at {self.c1[:7]}", p.stdout)
        self.assertNotIn("ADR-0001 not found", p.stdout)

    def test_no_checkout_is_not_a_pass(self):
        p = self.check(self.c2, ["DR-001"], checkout=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("consumes[0]: example-platform: not checked: no checkout given", p.stdout)
        self.assertIn("1 entries: 0 checked, 1 not checked, 0 failed", p.stdout)

    def test_a_capability_is_left_to_the_composed_build(self):
        p = self.check(self.c2, ["capability:LabelledRecords", "DR-001"])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("consumes[0]: example-platform: capability:LabelledRecords: checked when composed", p.stdout)

    def test_a_whole_portal_entry_checks_only_the_pin(self):
        c = load("minimal.yaml")
        c["consumes"][0]["commit"] = self.c1
        p = self.run_tool(c, "check_consumes", "--checkout", f"example-platform={self.repo}")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("1 checked", p.stdout)

    def test_a_checkout_for_an_unknown_name(self):
        p = self.check(self.c2, ["DR-001"], name="example-other")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("--checkout example-other", p.stderr)

    def test_a_malformed_checkout(self):
        p = self.run_tool(self.consumer(), "check_consumes", "--checkout", "example-platform")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)


class ByteIdentical(Base):
    """A valid `consumes:` changes nothing a render prints or writes."""

    def test_decisions_only_example(self):
        import test_example_decisions as ed
        proj = ed.copy_example(self.tmp)
        decl = proj / "arch-kit.yaml"
        c = yaml.safe_load(decl.read_text(encoding="utf-8"))
        c["consumes"] = load("full.yaml")["consumes"]
        decl.write_text(yaml.safe_dump(c), encoding="utf-8", newline="\n")
        out = self.tmp / "export.html"
        p = ed.render(proj, out)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        got = ed.normalise(out.read_text(encoding="utf-8"))
        self.assertEqual(got, ed.normalise(ed.SNAPSHOT.read_text(encoding="utf-8")))
        p = ed.check(proj, out)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_minimal_example(self):
        import test_example as ex
        why = ex.missing()
        if why:
            self.skipTest(why)
        proj = self.tmp / "proj"
        shutil.copytree(ex.EXAMPLE, proj, ignore=shutil.ignore_patterns("expected", "__pycache__"))
        for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "example")):
            git(proj, *args)
        decl = proj / "arch-kit.yaml"
        decl.write_text(decl.read_text(encoding="utf-8") + yaml.safe_dump({"consumes": load("full.yaml")["consumes"]}),
                        encoding="utf-8", newline="\n")
        (self.tmp / "puppeteer.json").write_text('{"args": ["--no-sandbox"]}\n', encoding="utf-8")
        out = self.tmp / "export.html"
        env = dict(os.environ, PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable, "-m", "arch_kit", "--config", "arch-kit.yaml", "render_html", "--out",
                            str(out), "--chart", "chart", "--values", "values.yaml", "--release", "larkspur",
                            "--readiness", "READINESS.md", "--relabel", "relabel.txt", "--barred", "barred.txt",
                            "--date", ex.DATE, "--puppeteer-config", str(self.tmp / "puppeteer.json")],
                           cwd=proj, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(ex.normalise(out.read_text(encoding="utf-8")),
                         ex.normalise(ex.SNAPSHOT.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
