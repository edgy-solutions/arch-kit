"""Tests that every file under a scripts/ directory is executable in git's index.

A declared script, such as a pin check, is run directly. A file committed as 100644 runs on Windows, which ignores
the bit, and fails on Linux with "Permission denied". So the mode is checked in the index, not on the disk.

Run from the kit root:
    python -m unittest discover -s arch_kit/tools -p "test_*.py"
"""
import subprocess
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]


def index_entries(root: Path):
    """(mode, path) for every tracked file, from `git ls-files -s`; None when this is not a git checkout."""
    try:
        out = subprocess.run(["git", "ls-files", "-s", "-z"], cwd=root, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    entries = []
    for record in out.stdout.decode("utf-8").split("\0"):
        if not record:
            continue
        meta, path = record.split("\t", 1)
        entries.append((meta.split(" ")[0], path))
    return entries


class ScriptsAreExecutable(unittest.TestCase):
    def test_every_file_under_a_scripts_directory_is_executable_in_the_index(self):
        entries = index_entries(KIT)
        if entries is None:
            self.skipTest("not a git checkout")
        scripts = [(mode, path) for mode, path in entries if "scripts" in path.split("/")[:-1]]
        self.assertTrue(scripts, "found no file under a scripts/ directory; the index listing went wrong")
        wrong = [f"{mode} {path}" for mode, path in scripts if mode != "100755"]
        self.assertEqual(wrong, [], "not executable in the index; fix with git update-index --chmod=+x PATH")


if __name__ == "__main__":
    unittest.main()
