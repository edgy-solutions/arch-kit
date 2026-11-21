"""Tests for `chart: none`, `model: none` and `pages:`.

Each case copies examples/no-chart (or examples/minimal, for pages in a full-mode project) into a temporary git
repository, with the mermaid fence turned into a plain one so the cases need no Node or Chrome, except the
full-mode pages case, which skips with its reason when they are missing, as test_example does. A full-mode render
still asks for a mermaid-cli file, so the cases pass a stub that is never run.
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
sys.path.insert(0, str(HERE))

import test_example_decisions as td  # noqa: E402

KIT = td.KIT
EXAMPLE = KIT / "examples" / "no-chart"
SRC = "arch-views=" + "a" * 40
KC = "b" * 40
DATE = td.DATE


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = self.tmp / "proj"
        shutil.copytree(EXAMPLE, self.root, ignore=shutil.ignore_patterns("expected", "__pycache__"))
        for f in (self.root / "views").glob("*.md"):
            t = f.read_text(encoding="utf-8")
            if "```mermaid" in t:
                f.write_text(t.replace("```mermaid", "```text"), encoding="utf-8", newline="")
        self.out = self.tmp / "export.html"
        td.git(self.root, "init", "-q")
        self.recommit()

    def recommit(self):
        td.git(self.root, "add", ".")
        td.git(self.root, "commit", "-q", "-m", "example", "--allow-empty")

    def load(self) -> dict:
        return yaml.safe_load((self.root / "arch-kit.yaml").read_text(encoding="utf-8"))

    def save(self, d: dict):
        (self.root / "arch-kit.yaml").write_text(yaml.safe_dump(d, sort_keys=False), encoding="utf-8")
        self.recommit()

    def render(self, *extra, source=(SRC,), kit=KC):
        args = ["--out", str(self.out), "--barred", "barred.txt", "--relabel", "relabel.txt", "--date", DATE]
        for s in source:
            args += ["--source", s]
        if kit:
            args += ["--kit-commit", kit]
        stub = self.tmp / "mmdc-stub"
        stub.write_text("never run: the cases have no mermaid fence" + chr(10), encoding="utf-8")
        args += ["--mmdc", str(stub)]
        return td.tool(self.root, "render_html", *args, *extra)

    def check(self):
        return td.tool(self.root, "check_export", "--export", str(self.out), "--barred", "barred.txt",
                       "--relabel", "relabel.txt")

    def text(self):
        return self.out.read_text(encoding="utf-8")

    def refused(self, p, fragment):
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn(fragment, p.stderr)


class InputErrors(Base):
    def test_chart_values_release_are_not_taken(self):
        for flag, val in (("--chart", "chart"), ("--values", "v.yaml"), ("--release", "r")):
            with self.subTest(flag=flag):
                self.refused(self.render(flag, val), f"chart: none is declared; {flag} is not taken")

    def test_source_is_required(self):
        self.refused(self.render(source=()), "--source")

    def test_source_name_and_commit_are_checked(self):
        for bad in ("a b=" + "a" * 40, "arch-views=" + "A" * 40, "arch-views=" + "a" * 39, "arch-views",
                    "=" + "a" * 40):
            with self.subTest(bad=bad):
                self.refused(self.render(source=(bad,)), "--source")

    def test_kit_commit_is_checked(self):
        self.refused(self.render(kit="xyz"), "--kit-commit")

    def test_kit_commit_unavailable_names_the_flag(self):
        code = chr(10).join([
            "import subprocess, argparse",
            "def boom(*a, **k): raise OSError('no git')",
            "subprocess.run = boom",
            "import render_html",
            "try:",
            "    render_html.kit_commit(argparse.Namespace(kit_commit=None))",
            "except render_html.InputError as e:",
            "    print(e)",
        ])
        env = dict(os.environ, PYTHONPATH=str(KIT) + os.pathsep + str(HERE), PYTHONIOENCODING="utf-8",
                   ARCH_KIT_CONFIG=str(self.root / "arch-kit.yaml"))
        p = subprocess.run([sys.executable, "-c", code], cwd=self.root, env=env,
                           capture_output=True, text=True, encoding="utf-8")
        self.assertIn("--kit-commit", p.stdout + p.stderr)

    def test_model_none_without_chart_none_is_refused(self):
        d = self.load()
        del d["chart"]
        self.save(d)
        self.assertEqual(self.render().returncode, 2)

    def test_chart_none_without_model_none_is_refused(self):
        d = self.load()
        del d["model"]
        self.save(d)
        self.assertEqual(self.render().returncode, 2)

    def test_capability_links_must_be_empty_under_model_none(self):
        d = self.load()
        d["views"]["capability_links"] = ["Rs-Cn"]
        self.save(d)
        self.refused(self.render(), "capability_links")

    def test_a_model_needing_derived_home_is_refused(self):
        d = self.load()
        d["views"]["homes"]["taxonomy"] = "St-Tx"
        self.save(d)
        self.assertEqual(self.render().returncode, 2)


class Parts(Base):
    def test_provenance_parts_and_order(self):
        two = "second.repo=" + "c" * 40
        p = self.render(source=(SRC, two))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        t = self.text()
        block = t[t.index("data-provenance"):]
        want = [f'<p data-prov="source">Source: arch-views {"a" * 40}</p>',
                f'<p data-prov="source">Source: second.repo {"c" * 40}</p>',
                f'<p data-prov="kit">Kit: {KC}</p>']
        pos = [block.index(w) for w in want]
        self.assertEqual(pos, sorted(pos))
        self.assertIn('data-prov="date">Generated: ' + DATE, block)
        self.assertIn('data-prov="declared"', block)
        self.assertNotIn('data-prov="chart"', t)
        self.assertNotIn('data-prov="digest"', t)
        self.assertEqual(self.check().returncode, 0)

    def test_no_declarations_page_and_no_capabilities_nav(self):
        self.render()
        t = self.text()
        self.assertNotIn('id="declarations"', t)
        self.assertNotIn("For a deployment", t)
        self.assertNotIn('class="capabilities"', t)

    def mutated(self, fn) -> str:
        self.assertEqual(self.render().returncode, 0)
        self.out.write_text(fn(self.text()), encoding="utf-8")
        p = self.check()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        return p.stderr

    def test_check_export_refuses_a_missing_source_part(self):
        err = self.mutated(lambda t: re.sub(r'<p data-prov="source">.*?</p>', "", t, count=1))
        self.assertIn("source", err)

    def test_check_export_refuses_a_missing_kit_part(self):
        err = self.mutated(lambda t: re.sub(r'<p data-prov="kit">.*?</p>', "", t, count=1))
        self.assertIn("kit", err)

    def test_check_export_refuses_two_kit_parts(self):
        one = f'<p data-prov="kit">Kit: {KC}</p>'
        err = self.mutated(lambda t: t.replace(one, one + one, 1))
        self.assertIn("kit", err)

    def test_check_export_refuses_a_disagreeing_kit_part(self):
        err = self.mutated(lambda t: t.replace(f"Kit: {KC}", "Kit: " + "d" * 40, 1))
        self.assertIn("disagree", err)

    def test_check_export_refuses_a_disagreeing_source_part(self):
        err = self.mutated(lambda t: t.replace("Source: arch-views " + "a" * 40, "Source: arch-views " + "e" * 40, 1))
        self.assertIn("disagree", err)


class Pages(Base):
    def test_nav_and_sections(self):
        self.assertEqual(self.render().returncode, 0)
        t = self.text()
        pages = self.load()["pages"]
        self.assertTrue(pages)
        self.assertIn('<nav class="pages"><h2>More</h2><ul>', t)
        for p in pages:
            self.assertIn(f'<section id="page-{p["id"]}" class="page" data-page="{p["id"]}">', t)
            self.assertIn(f'href="#page-{p["id"]}"', t)
            self.assertIn(f"<h1>{p['title']}</h1>", t)
        self.assertIn('<a href="#front">Front page</a>', t)

    def test_a_page_file_that_is_missing_is_an_input_error(self):
        (self.root / self.load()["pages"][0]["file"]).unlink()
        self.assertEqual(self.render().returncode, 2)

    def test_duplicate_page_ids_are_refused(self):
        d = self.load()
        d["pages"] = d["pages"] + [d["pages"][0]]
        self.save(d)
        self.assertEqual(self.render().returncode, 2)

    def test_a_full_mode_project_takes_pages(self):
        import test_example
        reason = test_example.missing()
        if reason:
            self.skipTest(reason)
        root = self.tmp / "full"
        shutil.copytree(KIT / "examples" / "minimal", root, ignore=shutil.ignore_patterns("expected", "__pycache__"))
        (root / "pages").mkdir()
        (root / "pages" / "extra.md").write_text("# Extra\n\nA page in a full-mode project.\n", encoding="utf-8")
        d = yaml.safe_load((root / "arch-kit.yaml").read_text(encoding="utf-8"))
        d["pages"] = [{"id": "extra", "title": "Extra", "file": "pages/extra.md"}]
        (root / "arch-kit.yaml").write_text(yaml.safe_dump(d, sort_keys=False), encoding="utf-8")
        (root / "puppeteer.json").write_text('{"args": ["--no-sandbox"]}' + chr(10), encoding="utf-8")
        td.git(root, "init", "-q")
        td.git(root, "add", ".")
        td.git(root, "commit", "-q", "-m", "example")
        out = self.tmp / "full.html"
        p = td.tool(root, "render_html", "--out", str(out), "--chart", "chart", "--values", "values.yaml",
                    "--release", "larkspur", "--readiness", "READINESS.md", "--relabel", "relabel.txt",
                    "--barred", "barred.txt", "--date", DATE, "--puppeteer-config", str(root / "puppeteer.json"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        t = out.read_text(encoding="utf-8")
        self.assertIn('<section id="page-extra" class="page" data-page="extra">', t)
        self.assertIn('<nav class="pages"><h2>More</h2>', t)


if __name__ == "__main__":
    unittest.main()
