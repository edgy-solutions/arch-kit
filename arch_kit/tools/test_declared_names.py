"""Tests that the kit holds no first-consumer name and reads its names from the declaration.

Run from the kit root:
    python -m unittest discover -s arch_kit/tools -p "test_*.py"
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(HERE))
os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))
import data_exchange  # noqa: E402
import project  # noqa: E402

# The first consumer's name stem, assembled so this file does not hold it.
STEM = re.compile("d" + "dil", re.IGNORECASE)


def tracked_files(root: Path):
    """Tracked files by `git ls-files`; a walk that skips .git and node_modules when git is absent."""
    try:
        out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True,
                             encoding="utf-8", check=True).stdout.split("\n")
        return [root / f for f in out if f]
    except (OSError, subprocess.CalledProcessError):
        found = []
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
            found += [Path(dirpath) / f for f in files]
        return found


def scan(files, names=True):
    """(file, line number, line) for each match of the stem, in file contents and file names."""
    hits = []
    for f in files:
        if names and STEM.search(str(f.name)):
            hits.append((f, 0, f.name))
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for n, line in enumerate(text.split("\n"), 1):
            if STEM.search(line):
                hits.append((f, n, line[:120]))
    return hits


class NoConsumerName(unittest.TestCase):
    def test_kit_holds_no_first_consumer_name(self):
        files = tracked_files(KIT)
        self.assertTrue(files, "the scan saw no files")
        self.assertEqual(scan(files), [])

    def test_the_scan_covers_the_example_and_it_names_no_consumer_project(self):
        files = [f for f in tracked_files(KIT) if "examples" in f.relative_to(KIT).parts]
        self.assertTrue(any(f.name == "arch-kit.yaml" for f in files), "the scan did not see examples/")
        stems = re.compile("|".join(("d" + "dil", "i" + "agent", "invin" + "cible")), re.IGNORECASE)
        hits = []
        for f in files:
            if stems.search(f.name):
                hits.append((f.name, 0))
            for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
                if stems.search(line):
                    hits.append((f.name, n))
        self.assertEqual(hits, [])

    def test_the_scanner_reports_a_planted_name(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        planted = tmp / "plant.txt"
        planted.write_text("clean line\nbuilt on Open" + "DD" + "IL here\n", encoding="utf-8")
        hits = scan([planted])
        self.assertEqual([(h[0], h[1]) for h in hits], [(planted, 2)])
        named = tmp / ("x-open" + "dd" + "il.txt")
        named.write_text("clean\n", encoding="utf-8")
        self.assertEqual([h[1] for h in scan([named])], [0])


class MissingKey(unittest.TestCase):
    def test_tool_needing_model_file_exits_2_with_the_message(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        decl = tmp / "arch-kit.yaml"
        decl.write_text("kit: 1\npaths:\n  root: .\n  repo: .\n  decisions: .\n", encoding="utf-8")
        env = dict(os.environ, ARCH_KIT_CONFIG=str(decl), PYTHONPATH=str(KIT))
        p = subprocess.run([sys.executable, "-m", "arch_kit", "validate_sysml", "--jar", "j", "--library", "l"],
                           capture_output=True, text=True, encoding="utf-8", env=env, cwd=tmp)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(p.stderr.strip(),
                         f"arch-kit: {decl}: missing key 'model.file' (needed by validate_sysml)")


class ModelFileRoot(unittest.TestCase):
    def test_model_file_is_under_the_root_it_is_given(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        a, b = tmp / "A", tmp / "B"
        for d, text in ((a, "from A"), (b, "from B")):
            (d / "model").mkdir(parents=True)
            (d / "model" / "example.sysml").write_text(text, encoding="utf-8")
        with mock.patch.object(project, "ROOT", a):
            self.assertEqual(project.model_file("check_views"), a / "model" / "example.sysml")
            got = project.model_file("check_views", root=b)
        self.assertEqual(got, b / "model" / "example.sysml")
        self.assertEqual(got.read_text(encoding="utf-8"), "from B")


class DeclaredNamesAreUsed(unittest.TestCase):
    def test_data_exchange_reads_the_declared_annotations_from_the_fixture(self):
        text = (HERE / "testdata" / "rendered-basic.yaml").read_text(encoding="utf-8")
        docs = data_exchange.load_docs(text)
        ws = {w.name: w for w in (data_exchange.Workload(d, "demo") for d in docs
                                  if d.get("kind") in data_exchange.WORKLOAD_KINDS)}
        self.assertEqual(data_exchange.produces_key(), "example.org/produces-topics")
        self.assertEqual(ws["sensor-edge-atl"].produces, [("edge-atl", "raw")])
        self.assertEqual(ws["bridge-edge-atl"].groups, [("edge-atl", "bridge-atl")])
        self.assertEqual(ws["egress-gate-c2"].produces, [("hq", "egress-sink")])
        self.assertEqual(ws["egress-gate-c2"].groups, [("hq", "egress-gate-c2")])
        self.assertTrue(ws["sensor-edge-atl"].has_declaration)
        self.assertEqual(ws["lonely-edge-bdr"].groups, [("edge-bdr", "lonely-group-name-raw")])


if __name__ == "__main__":
    unittest.main()
