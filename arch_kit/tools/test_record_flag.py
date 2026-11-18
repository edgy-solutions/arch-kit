"""check_views --record: a deployment's own capability record, read in place of <root>/capability-record.yaml.

Runs on a copy of examples/minimal, with its own declaration.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
EXAMPLE = KIT / "examples" / "minimal"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("ARCH_KIT_CONFIG", str(EXAMPLE / "arch-kit.yaml"))

import capability_phases  # noqa: E402

LINK = "[capability-record.yaml](../capability-record.yaml)"
OWN = "`capability-record.yaml`, the deployment's own"
NL = chr(10)


class Tool(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = self.tmp / "ex"
        shutil.copytree(EXAMPLE, self.root, ignore=shutil.ignore_patterns("__pycache__", "expected"))
        self.own = self.tmp / "own-record.yaml"
        shutil.copyfile(EXAMPLE / "capability-record.yaml", self.own)

    def run_tool(self, name, *args):
        env = dict(os.environ, PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        env.pop("ARCH_KIT_CONFIG", None)
        p = subprocess.run([sys.executable, "-m", "arch_kit", "--config", "arch-kit.yaml", name, *map(str, args)],
                           cwd=self.root, env=env, capture_output=True, text=True, encoding="utf-8")
        return p.returncode, p.stdout, p.stderr


class CheckViews(Tool):
    def test_a_copy_outside_the_tree_passes(self):
        rc, out, err = self.run_tool("check_views", "--record", self.own, "--allow-partial", "test")
        self.assertEqual(rc, 0, err)

    def test_the_flag_is_read_not_the_root_copy(self):
        text = self.own.read_text(encoding="utf-8")
        self.assertIn("adrs: [ADR-0001", text)
        self.own.write_text(text.replace("adrs: [ADR-0001", "adrs: [ADR-9999", 1), encoding="utf-8", newline=NL)
        rc, out, err = self.run_tool("check_views", "--record", self.own, "--allow-partial", "test")
        self.assertEqual(rc, 1, err)
        self.assertTrue(any(l.startswith("FAIL: phases:") for l in err.splitlines()), err)
        rc, out, err = self.run_tool("check_views", "--allow-partial", "test")
        self.assertEqual(rc, 0, err)

    def test_a_missing_record_is_bad_input_and_names_the_path(self):
        gone = self.tmp / "nowhere.yaml"
        rc, out, err = self.run_tool("check_views", "--record", gone, "--allow-partial", "test")
        self.assertEqual(rc, 2, err)
        self.assertIn(str(gone), err)
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
