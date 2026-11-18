"""Tests for the declared decision-record id and register id grammar, and the roadmap headers. Every name is invented.

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


RECORD = snippet("print(*declared.record_id('t'), *declared.record_patterns('t'), declared.record_form('t'), sep='|')")
REGISTER = snippet("print(declared.register_id('t'))")
INDEX = snippet("print(declared.decisions_index('t').local_prefix)")


class Grammar(unittest.TestCase):
    def setUp(self):
        self.tree = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tree, True)

    def run_snippet(self, code, edit=None):
        c = yaml.safe_load((HERE / "testdata" / "arch-kit.yaml").read_text(encoding="utf-8"))
        c["paths"] = {"root": ".", "repo": ".", "decisions": "decisions"}
        if edit:
            edit(c)
        path = self.tree / "arch-kit.yaml"
        path.write_text(yaml.safe_dump(c), encoding="utf-8")
        env = dict(os.environ, ARCH_KIT_CONFIG=str(path), PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                              env=env, cwd=self.tree)

    def refused(self, code, edit, key):
        p = self.run_snippet(code, edit)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn(key, p.stderr)

    @staticmethod
    def put(**decisions):
        def edit(c):
            c["decisions"] = decisions
        return edit

    def test_defaults(self):
        p = self.run_snippet(RECORD, lambda c: c.pop("decisions", None))
        self.assertEqual(p.stdout.strip(), "ADR|4|ADR-" + chr(92) + "d{4}|ADR-*.md|ADR-NNNN", p.stderr)
        p = self.run_snippet(REGISTER, lambda c: c.pop("decisions", None))
        self.assertEqual(p.stdout.strip(), "(2, 1, 2)", p.stderr)

    def test_declared_values(self):
        p = self.run_snippet(RECORD, self.put(records={"prefix": "DR2", "digits": 3}))
        self.assertEqual(p.stdout.strip(), "DR2|3|DR2-" + chr(92) + "d{3}|DR2-*.md|DR2-NNN", p.stderr)
        p = self.run_snippet(REGISTER, self.put(index={"register_id": {"letters": 3, "digits": [1, 3]}}))
        self.assertEqual(p.stdout.strip(), "(3, 1, 3)", p.stderr)
        p = self.run_snippet(REGISTER, self.put(index={"register_id": {"letters": 4}}))
        self.assertEqual(p.stdout.strip(), "(4, 1, 2)", p.stderr)

    def test_records_without_index_is_accepted_and_index_unknown_keys_still_refused(self):
        p = self.run_snippet(RECORD, self.put(records={"prefix": "DR"}))
        self.assertEqual(p.returncode, 0, p.stderr)
        base = {"register": "R.md", "readme": "README.md", "register_homes": ["a.md"], "indexed": ["a.md"],
                "local_prefix": "loam"}
        p = self.run_snippet(INDEX, self.put(records={"prefix": "DR"}, index=dict(base)))
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "loam"), p.stderr)
        p = self.run_snippet(INDEX, self.put(index=dict(base, register_id={"letters": 3})))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.refused(INDEX, self.put(index=dict(base, extra=1)), "decisions.index")

    def test_bad_record_values(self):
        for key, bad in (("prefix", "adr"), ("prefix", "1AB"), ("prefix", ""), ("prefix", 3), ("prefix", "A-B"),
                         ("digits", 0), ("digits", 9), ("digits", "4"), ("digits", True), ("digits", 2.5)):
            with self.subTest(key=key, bad=bad):
                self.refused(RECORD, self.put(records={key: bad}), "decisions.records." + key)
        self.refused(RECORD, self.put(records={"width": 4}), "decisions.records")
        self.refused(RECORD, self.put(records=["ADR"]), "decisions.records")

    def test_bad_register_id_values(self):
        for key, bad in (("letters", 0), ("letters", 7), ("letters", "2"), ("letters", True),
                         ("digits", [0, 2]), ("digits", [1, 7]), ("digits", [3, 2]), ("digits", [1]),
                         ("digits", 2), ("digits", ["1", 2]), ("digits", [1, 2, 3])):
            with self.subTest(key=key, bad=bad):
                self.refused(REGISTER, self.put(index={"register_id": {key: bad}}),
                             "decisions.index.register_id." + key)
        self.refused(REGISTER, self.put(index={"register_id": {"width": 2}}), "decisions.index.register_id")
        self.refused(REGISTER, self.put(index={"register_id": 2}), "decisions.index.register_id")


if __name__ == "__main__":
    unittest.main()
