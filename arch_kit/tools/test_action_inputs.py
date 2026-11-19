"""Tests the input guard of the Action's "Check and render" step.

The step's `run:` text is loaded from action.yml and run with bash against a stub `arch-kit` that logs every call
except `portal --mode`. A full-mode project with no chart or no release must fail at once, with exit 2, before any
step runs; a decisions-mode project needs neither input.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ACTION = Path(__file__).resolve().parents[2] / "action.yml"
BASH = shutil.which("bash")


def step_script() -> str:
    action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    for step in action["runs"]["steps"]:
        if step.get("name") == "Check and render":
            return step["run"]
    raise AssertionError("no step named 'Check and render' in action.yml")


@unittest.skipIf(BASH is None, "bash is not on the PATH")
class ActionInputs(unittest.TestCase):
    def run_step(self, mode, chart, release):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            log = tmp / "calls.log"
            bin_dir = tmp / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "arch-kit"
            stub.write_text(
                "#!/usr/bin/env bash\n"
                'shift 2\n'   # --config FILE
                f'if [ "$1" = portal ] && [ "$2" = --mode ]; then echo {mode}; exit 0; fi\n'
                f'echo "$@" >> "{log.as_posix()}"\n'
                "exit 0\n", encoding="utf-8", newline="\n")
            stub.chmod(0o755)
            script = tmp / "step.sh"
            script.write_text(step_script(), encoding="utf-8", newline="\n")
            env = dict(os.environ, PATH=bin_dir.as_posix() + os.pathsep + os.environ["PATH"],
                       IN_CONFIG="arch-kit.yaml", IN_CHART=chart, IN_RELEASE=release, IN_VALUES="", IN_READINESS="",
                       IN_RELABEL="", IN_BARRED="", IN_OUT=(tmp / "out").as_posix(), IN_BROWSER="false",
                       IN_INDEX_CHECK="false", GITHUB_ACTION_PATH=tmp.as_posix(), PUPPETEER_EXECUTABLE_PATH="x")
            p = subprocess.run([BASH, str(script)], env=env, capture_output=True, text=True, encoding="utf-8")
            calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
            return p, calls

    def test_full_without_chart(self):
        p, calls = self.run_step("full", "", "r1")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("the chart input is required", p.stdout)
        self.assertNotIn("release", p.stdout)
        self.assertEqual(calls, [])

    def test_full_without_release(self):
        p, calls = self.run_step("full", "c", "")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("the release input is required", p.stdout)
        self.assertNotIn("chart", p.stdout)
        self.assertEqual(calls, [])

    def test_full_without_either(self):
        p, calls = self.run_step("full", "", "")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("the chart and release inputs are required", p.stdout)
        self.assertEqual(calls, [])

    def test_decisions_needs_neither(self):
        p, calls = self.run_step("decisions", "", "")
        self.assertTrue(calls, p.stdout + p.stderr)
        self.assertTrue(calls[0].startswith("render_html"), calls)
        self.assertNotIn("--chart", calls[0])
        self.assertNotIn("portal.mode is full", p.stdout)

    def test_full_with_both(self):
        p, calls = self.run_step("full", "c", "r1")
        self.assertTrue(calls, p.stdout + p.stderr)
        self.assertTrue(calls[0].startswith("check_views"), calls)


if __name__ == "__main__":
    unittest.main()
