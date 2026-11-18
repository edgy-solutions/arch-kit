"""The CV-3 text names the record in use: the default as a link, a passed --record as plain words.

The view is the declared phases home. A view that lost the link is a check error. Runs on a copy of examples/minimal.
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


class RenderProfile(Tool):
    def phases_text(self, *extra):
        out = self.tmp / "o"
        rc, _, err = self.run_tool("render_profile", "--profile", "uaf", "--out", out, *extra)
        self.assertEqual(rc, 0, err)
        return (out / "St-Rm-P.md").read_text(encoding="utf-8")

    def test_the_view_has_the_link_the_name_is_built_from(self):
        self.assertIn(LINK, (EXAMPLE / "views" / "St-Rm-P.md").read_text(encoding="utf-8"))

    def test_the_default_record_is_named_as_a_link(self):
        text = self.phases_text()
        self.assertIn("[capability-record.yaml](", text)
        self.assertNotIn("the deployment's own", text)

    def test_a_passed_record_is_named_as_the_deployments_own(self):
        text = self.phases_text("--record", self.own)
        self.assertEqual(text.count(OWN), 2)
        self.assertNotIn("](", text.split("| The table", 1)[1].split(NL, 1)[0])

    def test_a_phases_view_without_the_link_fails_the_render(self):
        view = self.root / "views" / "St-Rm-P.md"
        view.write_text(view.read_text(encoding="utf-8").replace(LINK, "the record"), encoding="utf-8", newline=NL)
        out = self.tmp / "o"
        rc, _, err = self.run_tool("render_profile", "--profile", "uaf", "--out", out, "--record", self.own)
        self.assertEqual(rc, 1, err)
        self.assertIn("St-Rm-P: the link", err)


class NameRecord(unittest.TestCase):
    def test_default_record_is_unchanged(self):
        d = EXAMPLE / "capability-record.yaml"
        self.assertEqual(capability_phases.name_record(f"a {LINK} b", d, d), f"a {LINK} b")

    def test_other_record_replaces_every_link(self):
        out = capability_phases.name_record(f"{LINK} and {LINK}", Path("other.yaml"), EXAMPLE / "capability-record.yaml")
        self.assertEqual(out.count(OWN), 2)
        self.assertNotIn("](", out)

    def test_other_record_without_the_link_is_a_check_error(self):
        with self.assertRaises(capability_phases.CheckError):
            capability_phases.name_record("reworded", Path("other.yaml"), EXAMPLE / "capability-record.yaml")


if __name__ == "__main__":
    unittest.main()
