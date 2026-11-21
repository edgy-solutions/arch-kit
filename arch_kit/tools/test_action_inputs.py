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


SHA = "0123456789abcdef0123456789abcdef01234567"


@unittest.skipIf(BASH is None, "bash is not on the PATH")
class ActionInputs(unittest.TestCase):
    def run_step(self, mode, chart, release, chart_ref=SHA, bundle_ref=SHA, action_dir=None):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            action = tmp / action_dir if action_dir else tmp
            action.mkdir(exist_ok=True)
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
                       IN_CONFIG="arch-kit.yaml", IN_CHART=chart, IN_RELEASE=release, IN_VALUES="", IN_CHART_REF=chart_ref,
                       IN_BUNDLE_REF=bundle_ref, IN_READINESS="",
                       IN_RELABEL="", IN_BARRED="", IN_OUT=(tmp / "out").as_posix(), IN_BROWSER="false",
                       IN_INDEX_CHECK="false", GITHUB_ACTION_PATH=action.as_posix(), PUPPETEER_EXECUTABLE_PATH="x")
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
        p, calls = self.run_step("decisions", "", "", "", "")
        self.assertTrue(calls, p.stdout + p.stderr)
        self.assertTrue(calls[0].startswith("render_html"), calls)
        self.assertNotIn("--chart", calls[0])
        self.assertNotIn("portal.mode is full", p.stdout)

    def test_full_with_both(self):
        p, calls = self.run_step("full", "c", "r1")
        self.assertTrue(calls, p.stdout + p.stderr)
        self.assertTrue(calls[0].startswith("check_views"), calls)

    def test_the_commits_are_passed_to_render_html(self):
        other = "f" * 40
        p, calls = self.run_step("full", "c", "r1", SHA, f"{SHA}\n{other}")
        render = [c for c in calls if c.startswith("render_html")]
        self.assertTrue(render, p.stdout + p.stderr)
        self.assertIn(f"--chart-commit {SHA} --bundle-commit {SHA} --bundle-commit {other}", render[0])
        self.assertNotIn("commit", [c for c in calls if c.startswith("check_views")][0])

    def test_chart_needs_both_refs(self):
        for chart_ref, bundle_ref in (("", SHA), (SHA, ""), ("", "")):
            p, calls = self.run_step("full", "c", "r1", chart_ref, bundle_ref)
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            self.assertIn("chart-ref and bundle-ref are required with chart: pass the 40-character commits the chart "
                          "and the values are checked out at", p.stdout)
            self.assertEqual(calls, [])

    def test_a_malformed_ref_is_refused_before_any_tool_runs(self):
        for chart_ref, bundle_ref, name in (("master", SHA, "chart-ref"), (SHA.upper(), SHA, "chart-ref"),
                                            (SHA, f"{SHA}\nmain", "bundle-ref"), (SHA, SHA[:39], "bundle-ref")):
            p, calls = self.run_step("full", "c", "r1", chart_ref, bundle_ref)
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            self.assertIn(f"the {name} input must hold 40 lowercase hex characters", p.stdout)
            self.assertEqual(calls, [])

    def test_the_kit_commit_is_the_pinned_action_directory(self):
        kit = "e" * 40
        p, calls = self.run_step("full", "c", "r1", action_dir=kit)
        render = [c for c in calls if c.startswith("render_html")]
        self.assertTrue(render, p.stdout + p.stderr)
        self.assertIn(f"--kit-commit {kit}", render[0])

    def test_no_kit_commit_warns_and_passes_none(self):
        p, calls = self.run_step("full", "c", "r1", action_dir="v1")
        render = [c for c in calls if c.startswith("render_html")]
        self.assertTrue(render, p.stdout + p.stderr)
        self.assertNotIn("--kit-commit", render[0])
        self.assertIn("the kit's commit cannot be read", p.stdout)

    def test_decisions_needs_no_refs(self):
        p, calls = self.run_step("decisions", "", "", "", "")
        self.assertTrue(calls, p.stdout + p.stderr)
        self.assertNotIn("commit", calls[0])


if __name__ == "__main__":
    unittest.main()
