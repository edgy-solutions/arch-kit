"""Tests for the commits the page names: the chart's, each bundle repository's and the kit's.

Each case builds a chart repository and one or two values repositories with `git init` in temporary directories, and
renders a decisions-only portal (examples/decisions-only) with --chart and --values, so no Node or Chrome is needed.
The render reads the HEAD of each repository, checks the flags against it, and refuses a chart or a values file that
differs from its commit.
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import test_example_decisions as td  # noqa: E402

GIT = shutil.which("git")
GITENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.org", GIT_COMMITTER_NAME="t",
              GIT_COMMITTER_EMAIL="t@example.org", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
NL = chr(10)
CHART_YAML = "apiVersion: v2" + NL + "name: demo" + NL + "version: 0.1.0" + NL
NOWHERE = "none (not in a git repository)"


def git(cwd, *args):
    p = subprocess.run([GIT, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=GITENV)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def make_repo(path: Path, files: dict[str, str]) -> str:
    """A repository of its own with one commit; returns its HEAD."""
    path.mkdir(parents=True)
    git(path, "init", "-q")
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text, encoding="utf-8", newline="")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "fixture")
    return git(path, "rev-parse", "HEAD")


def parts(text: str, name: str) -> list[str]:
    """The text of each provenance part of that name on the front page, in order."""
    front = text[text.index('<section id="front"'):]
    front = front[:front.index("</section>")]
    return re.findall(rf'<p data-prov="{name}">(.*?)</p>', front, re.S)


@unittest.skipUnless(GIT, "needs git on the PATH")
class InputCommits(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="input-commits-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = td.copy_example(self.tmp)
        self.out = self.tmp / "export.html"
        self.chart = self.tmp / "chartrepo" / "chart"
        self.chart_head = make_repo(self.tmp / "chartrepo", {"chart/Chart.yaml": CHART_YAML})
        self.values1 = self.tmp / "valuesrepo1" / "values.yaml"
        self.head1 = make_repo(self.tmp / "valuesrepo1", {"values.yaml": "a: 1" + NL})
        self.values2 = self.tmp / "valuesrepo2" / "extra.yaml"
        self.head2 = make_repo(self.tmp / "valuesrepo2", {"extra.yaml": "b: 2" + NL})

    def render(self, *flags, chart=None, values=None, out=None):
        chart = chart or self.chart
        values = values or [self.values1]
        (out or self.out).unlink(missing_ok=True)
        args = ["--out", str(out or self.out), "--chart", str(chart), "--release", "demo", "--barred", "barred.txt",
                "--date", td.DATE]
        for v in values:
            args += ["--values", str(v)]
        return td.tool(self.root, "render_html", *args, *flags)

    def text(self):
        return self.out.read_text(encoding="utf-8")

    def refused(self, p, fragment):
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn(fragment, p.stderr)
        self.assertFalse(self.out.exists())

    def test_no_flags_the_parts_name_both_heads(self):
        p = self.render()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        t = self.text()
        self.assertEqual(parts(t, "chart-commit"), [f"Chart commit: {self.chart_head}"])
        self.assertEqual(parts(t, "bundle-commit"), [f"Bundle commit: {self.head1}"])
        self.assertTrue(re.fullmatch(r"Kit: [0-9a-f]{40}", parts(t, "kit")[0]))
        self.assertLess(t.index('data-prov="digest"'), t.index('data-prov="chart-commit"'))
        self.assertLess(t.index('data-prov="kit"'), t.index('data-prov="date"'))

    def test_flags_equal_to_the_heads_pass(self):
        p = self.render("--chart-commit", self.chart_head, "--bundle-commit", self.head1)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(parts(self.text(), "chart-commit"), [f"Chart commit: {self.chart_head}"])

    def test_a_kit_commit_is_taken_with_a_chart_and_named_on_the_page(self):
        # The Action passes --kit-commit with a chart; the flag was once taken only with chart: none.
        kit = "0123456789abcdef0123456789abcdef01234567"
        p = self.render("--kit-commit", kit)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(parts(self.text(), "kit"), [f"Kit: {kit}"])

    def test_a_malformed_kit_commit_refuses(self):
        self.refused(self.render("--kit-commit", "main"), "--kit-commit")

    def test_a_wrong_chart_commit_refuses(self):
        wrong = "0" * 40
        p = self.render("--chart-commit", wrong)
        self.refused(p, f"--chart-commit {wrong} is not the commit the chart is checked out at ({self.chart_head})")
        p = self.render("--chart-commit", "master")
        self.refused(p, "--chart-commit must be 40 lowercase hex characters")

    def test_a_missing_and_an_extra_bundle_commit_refuse(self):
        extra = "1" * 40
        p = self.render("--bundle-commit", self.head1, "--bundle-commit", extra, values=[self.values1, self.values2])
        self.refused(p, f"; missing {self.head2}")
        self.assertIn(f"; extra {extra}", p.stderr)
        p = self.render("--bundle-commit", self.head1, "--bundle-commit", self.head2, "--bundle-commit", extra,
                        values=[self.values1, self.values2])
        self.refused(p, f"; extra {extra}")
        self.assertNotIn("missing", p.stderr)
        p = self.render("--bundle-commit", extra)
        self.refused(p, f"--bundle-commit {extra} is not the commit the bundle is checked out at ({self.head1})")

    def test_a_modified_tracked_file_in_the_chart_refuses(self):
        (self.chart / "Chart.yaml").write_text(CHART_YAML + "description: edited" + NL, encoding="utf-8")
        self.refused(self.render(), f"the chart at {self.chart} differs from its commit; commit it, or build from a clean checkout")

    def test_a_modified_values_file_refuses(self):
        self.values1.write_text("a: 2" + NL, encoding="utf-8")
        self.refused(self.render(), f"the values file at {self.values1} differs from its commit; commit it, or build from a clean checkout")

    def test_an_untracked_file_in_the_chart_directory_refuses(self):
        (self.chart / "templates").mkdir()
        (self.chart / "templates" / "new.yaml").write_text("x: 1" + NL, encoding="utf-8")
        p = self.render()
        self.refused(p, "differs from its commit")
        self.assertNotIn("new.yaml", p.stderr)

    def test_an_ignored_file_does_not_refuse(self):
        (self.tmp / "chartrepo" / ".gitignore").write_text("*.tmp" + NL, encoding="utf-8")
        git(self.tmp / "chartrepo", "add", ".gitignore")
        git(self.tmp / "chartrepo", "commit", "-q", "-m", "ignore")
        (self.chart / "scratch.tmp").write_text("x", encoding="utf-8")
        p = self.render()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_values_in_two_repositories_give_two_parts_in_order(self):
        p = self.render(values=[self.values2, self.values1])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(parts(self.text(), "bundle-commit"), [f"Bundle commit: {self.head2}", f"Bundle commit: {self.head1}"])
        p = self.render("--bundle-commit", self.head1, "--bundle-commit", self.head2, values=[self.values1, self.values2])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_two_values_files_in_one_repository_give_one_part(self):
        (self.values1.parent / "more.yaml").write_text("c: 3" + NL, encoding="utf-8")
        git(self.values1.parent, "add", "more.yaml")
        git(self.values1.parent, "commit", "-q", "-m", "more")
        head = git(self.values1.parent, "rev-parse", "HEAD")
        p = self.render(values=[self.values1, self.values1.parent / "more.yaml"])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(parts(self.text(), "bundle-commit"), [f"Bundle commit: {head}"])

    def test_a_chart_outside_any_repository(self):
        plain = self.tmp / "plain" / "chart"
        plain.mkdir(parents=True)
        (plain / "Chart.yaml").write_text(CHART_YAML, encoding="utf-8")
        loose = self.tmp / "plain" / "values.yaml"
        loose.write_text("a: 1" + NL, encoding="utf-8")
        p = self.render(chart=plain, values=[loose])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        t = self.text()
        self.assertEqual(parts(t, "chart-commit"), [f"Chart commit: {NOWHERE}"])
        self.assertEqual(parts(t, "bundle-commit"), [f"Bundle commit: {NOWHERE}"])
        self.assertIn("not in a git repository", p.stderr)
        self.assertEqual(td.tool(self.root, "check_export", "--export", str(self.out), "--barred", "barred.txt").returncode, 0)
        p = self.render("--chart-commit", self.chart_head, chart=plain, values=[loose])
        self.refused(p, "--chart-commit is given but the chart")
        p = self.render("--bundle-commit", self.head1, chart=plain, values=[loose])
        self.refused(p, "--bundle-commit is given but a values file")

    def test_check_export_accepts_the_block_and_fails_a_page_that_differs(self):
        p = self.render()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        c = td.tool(self.root, "check_export", "--export", str(self.out), "--barred", "barred.txt")
        self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
        raw = self.text()
        pages = list(re.finditer(r'<section id="[^"]+" class="page', raw))
        self.assertGreater(len(pages), 1)
        # change the chart-commit part on the last page only
        start = pages[-1].start()
        tail = raw[start:].replace(f"Chart commit: {self.chart_head}", "Chart commit: " + "9" * 40, 1)
        self.assertNotEqual(tail, raw[start:])
        self.out.write_text(raw[:start] + tail, encoding="utf-8", newline="")
        c = td.tool(self.root, "check_export", "--export", str(self.out), "--barred", "barred.txt")
        self.assertEqual(c.returncode, 1, c.stdout + c.stderr)
        self.assertIn("pages disagree on the chart-commit part", c.stdout + c.stderr)

    def test_check_export_fails_a_malformed_or_missing_part(self):
        self.assertEqual(self.render().returncode, 0)
        raw = self.text()
        for old, new, want in (
                (f"Chart commit: {self.chart_head}", "Chart commit: abc", "malformed chart-commit"),
                (f"Bundle commit: {self.head1}", "Bundle commit: abc", "malformed bundle-commit")):
            self.out.write_text(raw.replace(old, new), encoding="utf-8", newline="")
            c = td.tool(self.root, "check_export", "--export", str(self.out), "--barred", "barred.txt")
            self.assertEqual(c.returncode, 1, c.stdout + c.stderr)
            self.assertIn(want, c.stdout + c.stderr)
        # In decisions mode the commit parts are optional, as the chart and digest parts are.
        stripped = re.sub(r'<p data-prov="(chart-commit|bundle-commit|kit)">.*?</p>', "", raw)
        self.out.write_text(stripped, encoding="utf-8", newline="")
        c = td.tool(self.root, "check_export", "--export", str(self.out), "--barred", "barred.txt")
        self.assertEqual(c.returncode, 0, c.stdout + c.stderr)

if __name__ == "__main__":
    unittest.main()
