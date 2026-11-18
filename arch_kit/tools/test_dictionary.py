"""Tests for the declared term dictionary (`derived.dictionary`). Every name is invented.

Each case writes a small project to a temp directory and builds the dictionary table in a subprocess, because the
declaration is read once per process.
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

SNIPPET = ("import sys; sys.path.insert(0, %r); from pathlib import Path; import derived; "
           "print(derived.build(derived.DICTIONARY_MARKER, Path('.'), None, '', ''))" % str(HERE))


class Dictionary(unittest.TestCase):
    def setUp(self):
        self.tree = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tree, True)
        (self.tree / "decisions").mkdir()
        self.dir = self.tree / "lexicon"
        self.dir.mkdir()
        (self.dir / "gadgets.yaml").write_text("gadgets:\n  - {name: a, size: 1}\n  - {name: b, size: 2}\n",
                                               encoding="utf-8")

    def run_tool(self, edit=None):
        c = yaml.safe_load((HERE / "testdata" / "arch-kit.yaml").read_text(encoding="utf-8"))
        c["paths"] = {"root": ".", "repo": ".", "decisions": "decisions"}
        c["derived"] = {"dictionary": {"dir": "lexicon", "terms": [{"file": "gadgets.yaml", "path": "gadgets"}]}}
        if edit:
            edit(c)
        path = self.tree / "arch-kit.yaml"
        path.write_text(yaml.safe_dump(c), encoding="utf-8")
        env = dict(os.environ, ARCH_KIT_CONFIG=str(path), PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "-c", SNIPPET], capture_output=True, text=True, encoding="utf-8",
                              env=env, cwd=self.tree)

    def refused(self, edit, key):
        p = self.run_tool(edit)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn(key, p.stderr)

    def test_a_declared_dir_under_another_name_builds_the_table(self):
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("| gadgets.yaml | gadgets | records | 2 | name, size |", p.stdout)

    def test_the_key_is_required(self):
        self.refused(lambda c: c.pop("derived"), "derived.dictionary")

    def test_dir_is_required(self):
        self.refused(lambda c: c["derived"]["dictionary"].pop("dir"), "derived.dictionary.dir")

    def test_dir_with_dotdot_is_refused(self):
        self.refused(lambda c: c["derived"]["dictionary"].update(dir="../lexicon"), "derived.dictionary.dir")

    def test_empty_terms_are_refused(self):
        self.refused(lambda c: c["derived"]["dictionary"].update(terms=[]), "derived.dictionary.terms")

    def test_a_file_that_is_not_a_bare_yaml_name_is_refused(self):
        for bad in ("sub/gadgets.yaml", "gadgets.json", "gadgets"):
            with self.subTest(bad):
                self.refused(lambda c: c["derived"]["dictionary"]["terms"][0].update(file=bad),
                             "derived.dictionary.terms[0].file")

    def test_a_declared_file_that_is_absent_fails(self):
        (self.dir / "gadgets.yaml").rename(self.dir / "other.yaml")
        p = self.run_tool()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("derived: the dictionary names lexicon/gadgets.yaml, which does not exist", p.stderr)

    def test_a_present_file_that_is_not_declared_fails(self):
        (self.dir / "extra.yaml").write_text("x: 1\n", encoding="utf-8")
        p = self.run_tool()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("derived: lexicon/extra.yaml has no dictionary row", p.stderr)


if __name__ == "__main__":
    unittest.main()
