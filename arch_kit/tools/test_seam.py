"""Tests for the seam: the loader declaration, the interface, and the neutral record's schema."""
from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
KIT = HERE.parent.parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))

import capability_phases  # noqa: E402
import project  # noqa: E402
import seam  # noqa: E402
from data_exchange import InputError  # noqa: E402

FIXTURE_RECORD = HERE / "testdata" / "record.yaml"


def run_loader(decl_text):
    """Ask project.loader for the loader under a declaration with the given text; return the process."""
    tmp = Path(tempfile.mkdtemp())
    decl = tmp / "arch-kit.yaml"
    decl.write_text("kit: 1\npaths:\n  root: .\n  repo: .\n  decisions: .\n" + decl_text, encoding="utf-8")
    env = dict(os.environ, ARCH_KIT_CONFIG=str(decl), PYTHONPATH=str(HERE))
    p = subprocess.run([sys.executable, "-c", "import project; project.loader('check_views')"],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=tmp)
    shutil.rmtree(tmp, True)
    return p, decl


class LoaderDeclaration(unittest.TestCase):
    def test_no_loader_key_exits_2_with_the_message(self):
        p, decl = run_loader("")
        self.assertEqual(p.returncode, 2)
        self.assertEqual(p.stderr.strip(), f"arch-kit: {decl}: missing key 'loader' (needed by check_views)")

    def test_missing_loader_file_exits_2_naming_the_path(self):
        p, decl = run_loader("loader: nowhere.py\n")
        self.assertEqual(p.returncode, 2)
        self.assertEqual(len(p.stderr.strip().splitlines()), 1)
        self.assertIn(str(decl.parent / "nowhere.py"), p.stderr)

    def test_the_declared_loader_is_the_one_returned(self):
        mod = project.loader("test_seam")
        self.assertEqual(Path(mod.__file__).name, "loader.py")
        self.assertIs(project.loader("test_seam"), mod)


class Interface(unittest.TestCase):
    def test_every_name_in_the_protocol_is_on_the_fixture_loader(self):
        mod = project.loader("test_seam")
        missing = [n for n in seam.NAMES if not hasattr(mod, n)]
        self.assertEqual(missing, [])

    def test_the_protocol_lists_the_spec_names(self):
        self.assertEqual(len(seam.NAMES), 15)


class RecordSchema(unittest.TestCase):
    def write(self, record):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        p = tmp / "record.yaml"
        p.write_text(yaml.safe_dump(record), encoding="utf-8")
        return p

    def test_the_fixture_record_validates(self):
        record = capability_phases.load_record(FIXTURE_RECORD)
        self.assertIn("Alpha", record["capabilities"])

    def test_a_capability_without_degraded_mode_fails_naming_the_path(self):
        record = yaml.safe_load(FIXTURE_RECORD.read_text(encoding="utf-8"))
        broken = copy.deepcopy(record)
        del broken["capabilities"]["Alpha"]["degraded_mode"]
        with self.assertRaises(InputError) as cm:
            capability_phases.load_record(self.write(broken))
        self.assertIn("capabilities.Alpha: 'degraded_mode' is a required property", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
