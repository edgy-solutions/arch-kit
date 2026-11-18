"""The kit installs as the `arch-kit` command.

Installs the kit into a temporary virtual environment and runs the command with no arguments: exit 2, and the
usage text lists the tools. Skipped, with the reason, when the environment cannot be created. pip needs the
package index for the three dependencies.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]


class Command(unittest.TestCase):
    def test_installed_command_prints_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_dir = Path(tmp) / "venv"
            try:
                venv.create(env_dir, with_pip=True)
            except Exception as e:  # noqa: BLE001
                self.skipTest(f"cannot create a virtual environment: {e}")
            bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
            py = bindir / ("python.exe" if sys.platform == "win32" else "python")
            if not py.exists():
                self.skipTest(f"no interpreter at {py}")
            # Build from a copy, so pip leaves no build/ or egg-info in the checkout.
            src = Path(tmp) / "src"
            shutil.copytree(KIT, src, ignore=shutil.ignore_patterns(
                ".git", "node_modules", "__pycache__", "build", "*.egg-info", "examples"))
            pip = subprocess.run([str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                                  str(src)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(pip.returncode, 0, pip.stderr[-2000:])
            exe = bindir / ("arch-kit.exe" if sys.platform == "win32" else "arch-kit")
            self.assertTrue(exe.exists(), f"{exe} was not installed")
            run = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8", cwd=tmp)
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertIn("usage: arch-kit [--config FILE] TOOL [ARGS...]", run.stderr)
            for name in ("check_views", "render_html", "check_export", "check_decision_indexes"):
                self.assertIn(name, run.stderr)


if __name__ == "__main__":
    unittest.main()
