"""Tests for the composed build (testdata/composed/). Every name is invented.

Each case builds real git repositories in a temporary directory (git init, no network), writes the composition file
with the real commits, and runs render_html and check_export in subprocesses (the declaration is read once per
process). Assertions are on the exit code, the document, and that the source repositories are left as they were.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
DATA = HERE / "testdata" / "composed"
RENDER = HERE / "render_html.py"
CHECK = HERE / "check_export.py"
DATE = "2026-01-02"
GIT = shutil.which("git")
GITENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.org", GIT_COMMITTER_NAME="t",
              GIT_COMMITTER_EMAIL="t@example.org", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
DECL = "docs/arch/arch-kit.yaml"
GROUPS = ("example-portal", "example-platform", "example-second")


def git(cwd, *args):
    p = subprocess.run([GIT, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=GITENV)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def tick(path, mutate=None):
    """Commit the whole repository as it stands (a fixture repository of its own)."""
    if mutate:
        mutate()
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "fixture")
    return git(path, "rev-parse", "HEAD")


@unittest.skipUnless(GIT, "needs git on the PATH")
class Composed(unittest.TestCase):
    audience = {}      # project name -> edit of its declaration, before its first commit

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="composed-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = {}
        self.head = {}
        for name in (*GROUPS, "example-app", "example-hidden"):
            d = self.tmp / name
            shutil.copytree(DATA / name, d)
            self.repo[name] = d
        for name in GROUPS:
            src, dst = ("second_loader.py",) * 2 if name == "example-second" else ("loader_adr.py", "kit_loader.py")
            shutil.copy(DATA / src, self.repo[name] / "docs" / "arch" / dst)
        for name in self.repo:
            git(self.repo[name], "init", "-q")
        for name in ("example-platform", "example-second"):
            self.head[name] = tick(self.repo[name])
        self.platform_url = "https://example.org/example-platform.git"
        self.second_url = "https://example.org/example-second.git"

    # --- the consumer and composition files ---------------------------------------------------------------------

    def entry(self, portal, commit, why, records=None, drift=None):
        e = {"portal": portal, "repo": f"https://example.org/{portal}.git", "commit": commit, "why": why}
        if records:
            e["records"] = records
        if drift:
            e["drift"] = drift
        return e

    def commit_consumer(self, name, entries, edit=None):
        decl = self.repo[name] / DECL
        c = yaml.safe_load(decl.read_text(encoding="utf-8"))
        c["consumes"] = entries
        if edit:
            edit(c)
        decl.write_text(yaml.safe_dump(c), encoding="utf-8", newline="\n")
        self.head[name] = tick(self.repo[name])

    def commit_portal(self, members=None, consumers=None, edit=None, lists=None):
        comp = {"composition": 1,
                "members": [{"name": n, "repo": f"https://example.org/{n}.git", "commit": self.head[n],
                                "lists": {"relabel": n + "-relabel", "barred": n + "-barred"}}
                               for n in (members or ("example-platform", "example-second"))]}
        if consumers is None:
            consumers = ("example-app",)
        if consumers:
            comp["consumers"] = [{"name": n, "repo": f"https://example.org/{n}.git", "commit": self.head[n]}
                                 for n in consumers]
        if edit:
            edit(comp)
        (self.repo["example-portal"] / "docs" / "arch" / "composition.yaml").write_text(
            yaml.safe_dump(comp), encoding="utf-8", newline="\n")
        decl = self.repo["example-portal"] / DECL
        c = yaml.safe_load(decl.read_text(encoding="utf-8"))
        c["files"] = {"composition": "composition.yaml"}
        decl.write_text(yaml.safe_dump(c), encoding="utf-8", newline="\n")
        self.head["example-portal"] = tick(self.repo["example-portal"])
        return comp

    def standard(self):
        """The platform consumed by example-app (one record) and by the hidden consumer; the second by the app."""
        self.commit_consumer("example-app", [
            self.entry("example-platform", self.head["example-platform"], "Keeps its labels on the platform model.",
                       records=["ADR-0002"]),
            self.entry("example-unrelated", "0" * 40, "Something outside this composition.")])
        self.commit_consumer("example-hidden", [
            self.entry("example-platform", self.head["example-platform"], "Secret reason for using the platform.",
                       records=["ADR-0001"])])
        self.commit_consumer("example-second", [
            self.entry("example-platform", self.head["example-platform"], "Uses the commit pins of the platform.",
                       records=["ADR-0002"])])
        return self.commit_portal(consumers=("example-app", "example-hidden"))

    # --- running ------------------------------------------------------------------------------------------------

    def checkouts(self, names=None):
        names = names or ("example-platform", "example-second", "example-app", "example-hidden")
        out = []
        for n in names:
            out += ["--checkout", f"{n}={self.repo[n]}"]
        return out

    def run_tool(self, script, args, config=None):
        repo = self.repo["example-portal"]
        env = dict(os.environ, ARCH_KIT_CONFIG=str(config or repo / DECL), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, str(script), *args], cwd=repo, capture_output=True, text=True,
                              encoding="utf-8", env=env)

    def render(self, names=None, extra=()):
        out = self.tmp / "out.html"
        p = self.run_tool(RENDER, ["--out", str(out), "--date", DATE, *self.checkouts(names), *extra])
        return p, (out.read_text(encoding="utf-8") if out.exists() else "")

    def check(self, names=None, extra=()):
        out = self.tmp / "out.html"
        return self.run_tool(CHECK, ["--export", str(out), "--barred", str(DATA / "barred.txt"),
                                     *self.checkouts(names), *extra])

    def states(self):
        return {n: (git(self.repo[n], "rev-parse", "HEAD"), git(self.repo[n], "status", "--porcelain"))
                for n in self.repo}


class Build(Composed):
    def setUp(self):
        super().setUp()
        self.standard()

    def test_the_build_and_the_check(self):
        before = self.states()
        p, doc = self.render()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        c = self.check()
        self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
        self.assertIn("composed: 3 groups", c.stdout)
        self.assertEqual(self.states(), before)
        self.assertFalse(list(Path(tempfile.gettempdir()).glob("arch-kit-fragment-*")))

    def test_one_front_block_per_group_in_order(self):
        _, doc = self.render()
        found = re.findall(r'<div class="member" data-member="([^"]+)"', doc)
        self.assertEqual(found, list(GROUPS))

    def test_the_second_member_shows_its_own_words(self):
        _, doc = self.render()
        self.assertIn("Work is handed over through a queue", doc)
        self.assertIn("Every outbound record carries a label", doc)
        self.assertIn("The portal renders the records of its members", doc)
        self.assertIn("DR-001", doc)

    def test_colliding_ids_become_distinct_pages_and_links_resolve(self):
        _, doc = self.render()
        ids = re.findall(r'\bid="([^"]+)"', doc)
        self.assertEqual(len(ids), len(set(ids)))
        for g in ("example-portal", "example-platform"):
            self.assertIn(f'id="{g}--adr-0001"', doc)
        targets = set(re.findall(r'href="#([^"]+)"', doc)) - {"front"}
        self.assertFalse(targets - set(ids), sorted(targets - set(ids))[:5])
        self.assertNotRegex(doc, r'href="(?!#)')

    def test_consumed_by_blocks(self):
        _, doc = self.render()
        self.assertIn("Consumed by", doc)
        self.assertNotIn("Keeps its labels on the platform model.", doc)   # a consumer with no portal: no why
        self.assertIn("example-app", doc)
        self.assertIn("Uses the commit pins of the platform.", doc)

    def test_a_private_consumer_shows_no_why(self):
        _, doc = self.render()
        self.assertNotIn("Secret reason", doc)
        self.assertIn("example-hidden", doc)

    def test_consumes_block_for_a_member_that_consumes(self):
        _, doc = self.render()
        self.assertIn("Consumes", doc)

    def test_an_entry_for_a_name_that_is_not_a_group_is_ignored(self):
        _, doc = self.render()
        self.assertNotIn("example-unrelated", doc)
        self.assertNotIn("Something outside this composition", doc)

    def test_the_composed_in_sentence(self):
        decl = self.repo["example-platform"] / DECL
        c = yaml.safe_load(decl.read_text(encoding="utf-8"))
        c["portal"]["composed_in"] = "example-portal"
        decl.write_text(yaml.safe_dump(c), encoding="utf-8", newline="\n")
        self.head["example-platform"] = tick(self.repo["example-platform"])
        self.commit_portal()
        out = self.tmp / "standalone.html"
        rules = self.tmp / "rules.tsv"
        rules.write_text("no-such-value-here" + chr(9) + "other" + chr(10), encoding="utf-8", newline=chr(10))
        env = dict(os.environ, ARCH_KIT_CONFIG=str(decl), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run([sys.executable, str(RENDER), "--out", str(out), "--date", DATE, "--relabel", str(rules),
                            "--barred", str(DATA / "barred.txt")],
                           cwd=self.repo["example-platform"], capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("example-portal", out.read_text(encoding="utf-8"))


class Flows(Composed):
    """Two members that declare flows (both with an FL-001) and the composing portal, which declares none."""

    FLOWS = {"example-platform": ("ADR-0001", "labels", "store"), "example-second": ("DR-001", "queue", "worker")}

    def setUp(self):
        super().setUp()
        for name, (decided, a, b) in self.FLOWS.items():
            d = self.repo[name] / DECL
            c = yaml.safe_load(d.read_text(encoding="utf-8"))
            c["files"] = dict(c.get("files") or {}, flows="flows.yaml")
            d.write_text(yaml.safe_dump(c), encoding="utf-8", newline="\n")
            (self.repo[name] / "docs" / "arch" / "flows.yaml").write_text(yaml.safe_dump({"flows": [
                {"id": "FL-001", "from": a, "to": b, "carries": f"{a}.v1", "via": f"{a}/{b}",
                 "decided_by": [decided], "built": name == "example-second"}]}), encoding="utf-8", newline="\n")
            self.head[name] = tick(self.repo[name])
        self.standard()

    def test_each_group_with_flows_has_its_own_page_and_link(self):
        p, doc = self.render()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        ids = re.findall(r'\bid="([^"]+)"', doc)
        self.assertEqual(len(ids), len(set(ids)))
        for g in ("example-platform", "example-second"):
            self.assertEqual(doc.count(f'<section id="{g}--flows" class="page flows" data-flows>'), 1, g)
            self.assertEqual(doc.count(f'<li><a href="#{g}--flows">Flows (1)</a></li>'), 1, g)
        self.assertNotIn("example-portal--flows", doc)
        self.assertEqual(doc.count('data-flow="FL-001"'), 2)
        self.assertEqual(len(re.findall(r'<nav class="flows"><h3>Flows</h3>', doc)), 2)
        targets = set(re.findall(r'href="#([^"]+)"', doc)) - {"front"}
        self.assertFalse(targets - set(ids), sorted(targets - set(ids))[:5])
        self.assertIn("nav.flows ul", doc)

    def test_the_decision_page_lists_point_at_their_own_flows_page(self):
        _, doc = self.render()
        start = doc.index('<section id="example-second--dr-001"')
        block = doc[start:doc.index("</section>", start)]
        self.assertIn('<a href="#example-second--flows">FL-001: queue', block)

    def test_the_check_passes_and_a_missing_page_or_link_fails(self):
        p, doc = self.render()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        c = self.check()
        self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
        out = self.tmp / "out.html"
        out.write_text(doc.replace('<li><a href="#example-second--flows">Flows (1)</a></li>', ""),
                       encoding="utf-8", newline="\n")
        c = self.check()
        self.assertEqual(c.returncode, 1, c.stdout + c.stderr)
        self.assertIn("example-second", c.stderr)
        self.assertIn("front-page links to its flows page", c.stderr)

    def test_no_flows_anywhere_adds_nothing(self):
        # the base fixtures declare no flows: the document carries no trace
        base = Build("test_the_build_and_the_check")
        base.setUp()
        try:
            _, doc = base.render()
        finally:
            base.doCleanups()
        for needle in ("data-flows", "data-flow", 'class="flows"', "nav.flows"):
            self.assertNotIn(needle, doc)


class Refused(Composed):
    def setUp(self):
        super().setUp()
        self.standard()

    def refused(self, names=None, extra=(), key=None):
        p, _ = self.render(names, extra)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertTrue(p.stderr.startswith("arch-kit: ") or "arch-kit" in p.stderr, p.stderr)
        if key:
            self.assertIn(key, p.stderr)
        return p.stderr

    def test_missing_checkout(self):
        self.refused(("example-platform", "example-second", "example-app"), key="consumers[1]")

    def test_a_name_the_file_does_not_list(self):
        self.refused(extra=["--checkout", f"example-nowhere={self.repo['example-app']}"])

    def test_a_name_given_twice(self):
        self.refused(extra=["--checkout", f"example-app={self.repo['example-app']}"])

    def test_not_a_git_repository(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        p, _ = self.render(("example-platform", "example-second", "example-app"),
                           ["--checkout", f"example-hidden={plain}"])
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn("consumers[1]", p.stderr)

    def test_a_commit_not_in_the_checkout(self):
        def edit(c):
            c["members"][0]["commit"] = "f" * 40
        self.commit_portal(consumers=("example-app", "example-hidden"), edit=edit)
        self.assertIn("members[0]", self.refused())

    def test_a_full_mode_composing_portal(self):
        decl = self.repo["example-portal"] / DECL
        c = yaml.safe_load(decl.read_text(encoding="utf-8"))
        c["portal"]["mode"] = "full"
        decl.write_text(yaml.safe_dump(c), encoding="utf-8", newline="\n")
        self.refused()

    def _member_edit(self, name, edit):
        decl = self.repo[name] / DECL
        c = yaml.safe_load(decl.read_text(encoding="utf-8"))
        edit(c)
        decl.write_text(yaml.safe_dump(c), encoding="utf-8", newline="\n")
        self.head[name] = tick(self.repo[name])
        self.commit_portal(consumers=("example-app", "example-hidden"))

    def test_a_member_with_no_portal(self):
        self._member_edit("example-second", lambda c: c.update(portal="none"))
        self.assertIn("members[1]", self.refused())

    def test_a_full_mode_member(self):
        self._member_edit("example-second", lambda c: c["portal"].update(mode="full"))
        self.assertIn("members[1]", self.refused())

    def test_a_member_that_composes(self):
        self._member_edit("example-second", lambda c: c.update(files={"composition": "composition.yaml"}))
        self.assertIn("members[1]", self.refused())

    def test_a_consumer_without_a_consumes_list(self):
        decl = self.repo["example-hidden"] / DECL
        c = yaml.safe_load(decl.read_text(encoding="utf-8"))
        del c["consumes"]
        decl.write_text(yaml.safe_dump(c), encoding="utf-8", newline="\n")
        self.head["example-hidden"] = tick(self.repo["example-hidden"])
        self.commit_portal(consumers=("example-app", "example-hidden"))
        self.assertIn("consumers[1]", self.refused())
        self.assertFalse(list(Path(tempfile.gettempdir()).glob("arch-kit-fragment-*")))


if __name__ == "__main__":
    unittest.main()
