"""Self-test: the components example loads and renders to expected/components.html, byte for byte.

The example (examples/components) is the decisions-only example with `files.components` declared. The test copies it
to a temporary directory, loads and renders the components in a subprocess at that root (the declaration is read once
per process) and compares the printed result with the expected file. To regenerate the expected file after an
intended change, from the kit root:

    python arch_kit/tools/test_example_components.py --write-expected
"""
from __future__ import annotations

import difflib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
EXAMPLE = KIT / "examples" / "components"
EXPECTED = EXAMPLE / "expected" / "components.html"
LOCAL_IDS = ["ADR-0001", "ADR-0002", "ADR-0003"]
GAP = (b"components_example: components.yaml: components[2].connections[0].protected_by[0]: gap: none: "
       b"the start log is readable by every local account\n")

RENDER = '''
import sys
sys.path.insert(0, {tools!r})
import components, declared
local_ids = {ids!r}
items = components.load("components_example", local_ids)
planes, _ = declared.components_declaration("components_example")
sections, nav = components.render(items, planes, lambda v: f"#{{v.lower()}}" if v in local_ids else None, prov="", pre="")
sys.stdout.buffer.write((chr(10).join(sections) + chr(10) + components.nav(nav) + chr(10)).encode("utf-8"))
'''


def run_in(root: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, ARCH_KIT_CONFIG=str(root / "arch-kit.yaml"), PYTHONDONTWRITEBYTECODE="1")
    code = RENDER.format(tools=str(HERE), ids=LOCAL_IDS)
    return subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True)


def copy_example(tmp: Path) -> Path:
    root = tmp / "proj"
    shutil.copytree(EXAMPLE, root, ignore=shutil.ignore_patterns("expected", "__pycache__"))
    return root


class Example(unittest.TestCase):
    def test_the_example_renders_to_its_expected_file(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        p = run_in(copy_example(tmp))
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace"))
        self.assertEqual(p.stderr.replace(b"\r\n", b"\n"), GAP)
        want = EXPECTED.read_bytes()
        if p.stdout != want:
            diff = list(difflib.unified_diff(want.decode("utf-8").split("\n"), p.stdout.decode("utf-8").split("\n"),
                                             "expected", "built", lineterm="", n=0))
            self.fail("the output differs from expected/components.html:\n" + "\n".join(diff[:40]))


def write_expected() -> int:
    with tempfile.TemporaryDirectory() as t:
        p = run_in(copy_example(Path(t)))
        if p.returncode or p.stderr.replace(b"\r\n", b"\n") != GAP:
            print(p.stderr.decode("utf-8", "replace"), file=sys.stderr)
            return 1
    EXPECTED.parent.mkdir(exist_ok=True)
    EXPECTED.write_bytes(p.stdout)
    print(f"wrote {EXPECTED}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-expected"]:
        sys.exit(write_expected())
    unittest.main()
