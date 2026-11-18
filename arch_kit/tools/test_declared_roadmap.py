"""Tests for the declared roadmap table headers (`derived.roadmap`). Every name is invented.

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

NOTE = """# Order

| step | slice | isolates | where | after |
| --- | --- | --- | --- | --- |
| 1 | first | a | h1 | none |

| no | piece | lands in | reason |
| --- | --- | --- | --- |
| a | p | 1 | because |
"""
HEADERS = {"increments": ["step", "slice", "isolates", "where", "after"],
           "fold_ins": ["no", "piece", "lands in", "reason"]}
SHOW = ("import sys; sys.path.insert(0, %r); import declared; "
        "print(declared.roadmap_headers('t'), sep='|')" % str(HERE))
TABLES = ("import sys; sys.path.insert(0, %r); import derived; text = open('note.md', encoding='utf-8').read(); "
          "inc, fold = derived.declared.roadmap_headers('t'); "
          "print(len(derived.table_with(text, inc, 'increment')), len(derived.table_with(text, fold, 'fold-in')))"
          % str(HERE))


class Roadmap(unittest.TestCase):
    def setUp(self):
        self.tree = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tree, True)
        (self.tree / "note.md").write_text(NOTE, encoding="utf-8")

    def run_snippet(self, code, roadmap=None):
        c = yaml.safe_load((HERE / "testdata" / "arch-kit.yaml").read_text(encoding="utf-8"))
        c["paths"] = {"root": ".", "repo": ".", "decisions": "decisions"}
        if roadmap is not None:
            c["derived"]["roadmap"] = roadmap
        path = self.tree / "arch-kit.yaml"
        path.write_text(yaml.safe_dump(c), encoding="utf-8")
        env = dict(os.environ, ARCH_KIT_CONFIG=str(path), PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                              env=env, cwd=self.tree)

    def refused(self, roadmap, key):
        p = self.run_snippet(SHOW, roadmap)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn(key, p.stderr)

    def test_defaults_are_the_original_headers(self):
        p = self.run_snippet(SHOW)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), str((["#", "increment", "what isolates", "home", "depends on"],
                                                ["row", "slice", "folds into", "why it costs the increment nothing"])))

    def test_one_key_alone_keeps_the_other_default(self):
        p = self.run_snippet(SHOW, {"fold_ins": HEADERS["fold_ins"]})
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("'#', 'increment'", p.stdout)
        self.assertIn("'no', 'piece'", p.stdout)

    def test_renamed_headers_find_the_tables_only_when_declared(self):
        p = self.run_snippet(TABLES, HEADERS)
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "1 1"), p.stderr)
        p = self.run_snippet(TABLES)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("the roadmap note has 0 increment tables, expected one", p.stderr + p.stdout)

    def test_bad_values_are_refused_by_key(self):
        for key in HEADERS:
            for bad in ("x", [], [""], [3, "a", "b", "c", "d"], ["a", "a", "b", "c", "d"], ["a", "b"]):
                with self.subTest(key=key, bad=bad):
                    self.refused({key: bad}, "derived.roadmap." + key)

    def test_unknown_key_and_non_map(self):
        self.refused({"rows": ["a"]}, "derived.roadmap")
        self.refused(["a"], "derived.roadmap")


if __name__ == "__main__":
    unittest.main()
