"""Tests for `decisions.index.register: none` on a copy of the decisions-only example.

The copy declares no register: `register: none`, no `register_homes`, and no FOLLOW-UPS.md. The example itself keeps
its register, so its snapshot is untouched. Each case runs the tool in a subprocess.
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
KIT = HERE.parents[1]
EXAMPLE = KIT / "examples" / "decisions-only"
BASH = shutil.which("bash")
NOT_RUN = "checks 1, 3 and 4: not run: decisions.index.register is none"


@unittest.skipUnless(BASH, "needs bash on the PATH")
class NoRegister(unittest.TestCase):
    def setUp(self):
        self.tree = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tree, True)
        self.root = self.tree / "proj"
        shutil.copytree(EXAMPLE, self.root, ignore=shutil.ignore_patterns("expected", "__pycache__"))
        dec = self.root / "decisions"
        (dec / "FOLLOW-UPS.md").unlink()
        readme = dec / "README.md"
        readme.write_text("".join(l for l in readme.read_text(encoding="utf-8").splitlines(True)
                                  if "FOLLOW-UPS" not in l), encoding="utf-8")
        self.edit(lambda c: (c["decisions"]["index"].update(register="none", indexed=["[0-9]*.md"]),
                             c["decisions"]["index"].pop("register_homes")))

    def edit(self, fn):
        path = self.root / "arch-kit.yaml"
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        fn(config)
        path.write_text(yaml.safe_dump(config), encoding="utf-8")

    def run_check(self):
        env = dict(os.environ, PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        return subprocess.run([sys.executable, "-m", "arch_kit", "--config", "arch-kit.yaml", "check_decision_indexes"],
                              cwd=self.root, env=env, capture_output=True, text=True, encoding="utf-8")

    def test_clean_run_says_which_checks_did_not_run(self):
        p = self.run_check()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn(NOT_RUN, p.stdout)

    def test_check_2_still_runs(self):
        (self.root / "decisions" / "0004-unlisted-record.md").write_text("# ADR-0004: Unlisted\n", encoding="utf-8")
        p = self.run_check()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("0004-unlisted-record.md", p.stdout)
        self.assertIn(NOT_RUN, p.stdout)

    def test_none_in_full_mode(self):
        self.edit(lambda c: c["portal"].pop("mode"))
        p = self.run_check()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn(NOT_RUN, p.stdout)

    def test_a_missing_register_key_still_exits_2(self):
        self.edit(lambda c: c["decisions"]["index"].pop("register"))
        p = self.run_check()
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("decisions.index.register", p.stderr)

    def test_none_with_register_homes_exits_2(self):
        self.edit(lambda c: c["decisions"]["index"].update(register_homes=["[0-9]*.md"]))
        p = self.run_check()
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("decisions.index.register_homes", p.stderr)

    def test_none_with_register_id_exits_2(self):
        self.edit(lambda c: c["decisions"]["index"].update(register_id={"letters": 2}))
        p = self.run_check()
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("decisions.index.register_id", p.stderr)

    def test_the_script_fails_on_an_empty_register_without_the_flag(self):
        env = dict(os.environ, IDX_DIRNAME="d", IDX_REGISTER="", IDX_README="README.md", IDX_HOMES="x.md",
                   IDX_INDEXED="x.md", IDX_LOCAL="p", IDX_ROOT=".")
        p = subprocess.run([BASH, str(HERE / "check_decision_indexes.sh")], cwd=self.root / "decisions", env=env,
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("IDX_REGISTER", p.stderr)


if __name__ == "__main__":
    unittest.main()
