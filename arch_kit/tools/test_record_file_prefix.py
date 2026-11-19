"""Tests for `decisions.records.file_prefix`: record file names with and without the prefix. Every name is invented.

Each case runs a small snippet in a subprocess, because the declaration is read once per process.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent


def snippet(code: str) -> str:
    return "import sys; sys.path.insert(0, %r); import declared; %s" % (str(HERE), code)


PATTERNS = snippet("print(*declared.record_file_patterns('t'), sep='|')")


def ids(*names: str) -> str:
    return snippet("print(*[declared.record_id_of_file('t', n) for n in %r], sep='|')" % (names,))


class FilePrefix(unittest.TestCase):
    def setUp(self):
        self.tree = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tree, True)

    def run_snippet(self, code, records=None, cwd=None):
        c = yaml.safe_load((HERE / "testdata" / "arch-kit.yaml").read_text(encoding="utf-8"))
        c["paths"] = {"root": ".", "repo": ".", "decisions": "decisions"}
        if records is not None:
            c["decisions"] = {"records": records}
        path = self.tree / "arch-kit.yaml"
        path.write_text(yaml.safe_dump(c), encoding="utf-8")
        env = dict(os.environ, ARCH_KIT_CONFIG=str(path), PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                              env=env, cwd=cwd or self.tree)

    def test_default_is_prefixed(self):
        p = self.run_snippet(PATTERNS)
        self.assertEqual(p.stdout.strip(), "ADR-(?P<n>" + chr(92) + "d{4})-.+" + chr(92) + ".md|ADR-*.md", p.stderr)
        p = self.run_snippet(ids("ADR-0007-x.md", "0007-x.md", "ADR-0007-x.txt"))
        self.assertEqual(p.stdout.strip(), "ADR-0007|None|None", p.stderr)

    def test_unprefixed(self):
        p = self.run_snippet(PATTERNS, {"file_prefix": False})
        self.assertEqual(p.stdout.strip().split("|")[1], "[0-9][0-9][0-9][0-9]-*.md", p.stderr)
        p = self.run_snippet(ids("0007-x.md", "ADR-0007-x.md"), {"file_prefix": False})
        self.assertEqual(p.stdout.strip(), "ADR-0007|None", p.stderr)

    def test_declared_prefix_and_digits(self):
        p = self.run_snippet(ids("012-x.md"), {"prefix": "DR", "digits": 3, "file_prefix": False})
        self.assertEqual(p.stdout.strip(), "DR-012", p.stderr)

    def test_non_bool_is_refused(self):
        for bad in ("no", 0, 1, None, "false"):
            with self.subTest(bad=bad):
                p = self.run_snippet(PATTERNS, {"file_prefix": bad})
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIn("decisions.records.file_prefix", p.stderr)

    def test_render_and_check_export_on_unprefixed_files(self):
        dec = self.tree / "decisions"
        dec.mkdir()
        (dec / "ROADMAP.md").write_text("# Roadmap\n\nNothing yet.\n", encoding="utf-8")
        for n, slug in ((1, "first-choice"), (2, "second-choice")):
            (dec / f"{n:04d}-{slug}.md").write_text(
                f"# ADR-{n:04d}: A choice\n\n## Status\n\nAccepted\n\n## Decision\n\nWe chose.\n", encoding="utf-8")
        for cmd in (["init", "-q"], ["add", "."], ["-c", "user.name=t", "-c", "user.email=t@example.org",
                                                  "commit", "-q", "-m", "records"]):
            subprocess.run(["git", "-C", str(self.tree), *cmd], check=True, capture_output=True)
        code = snippet(
            "import render_html, check_export, project, re; "
            "dec = render_html.Decisions(project.DECISIONS); "
            "sections, nav = render_html.decision_pages({}, dec, ''); raw = ''.join(sections); "
            "print(*[i for i, _ in check_export.PAGE_RE.findall(raw)]); "
            "print(*re.findall(r'decisions/[^<]*', raw), sep=' '); "
            "print(check_export.check_decisions(raw, None)); "
            "print(check_export.check_decisions(raw.replace('id=\"adr-0002\"', 'id=\"x\"'), None) != [])")
        p = self.run_snippet(code, {"file_prefix": False}, cwd=self.tree)
        self.assertEqual(p.returncode, 0, p.stderr)
        lines = p.stdout.strip().splitlines()
        self.assertEqual(lines[0], "adr-0001 adr-0002 decision-roadmap")
        self.assertIn("decisions/0001-first-choice.md", lines[1])
        self.assertIn("decisions/0002-second-choice.md", lines[1])
        self.assertEqual(lines[2:], ["[]", "True"])


if __name__ == "__main__":
    unittest.main()
