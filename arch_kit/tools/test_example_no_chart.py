"""Self-test: the no-chart example (`chart: none`, `model: none`, two pages) builds, checks and matches its snapshot.

Runs render_html (with --source and --kit-commit, no chart flags), check_export, browser_facts and
check_export_browser.mjs on examples/no-chart and asserts each exits 0, then compares the export with
examples/no-chart/expected/export.html after the normalising test_example does. check_views is not run: its
command line still reads the chart, the readiness file and the inventory, which this project does not have.

Skipped, with the reason, on the same conditions as test_example. To regenerate the snapshot, from the kit root:

    python arch_kit/tools/test_example_no_chart.py --write-snapshot
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_example as te  # noqa: E402

KIT = te.KIT
EXAMPLE = KIT / "examples" / "no-chart"
SNAPSHOT = EXAMPLE / "expected" / "export.html"
TOOLS = te.TOOLS
SOURCE = "arch-views=" + "a" * 40
KIT_COMMIT = "b" * 40


def missing() -> str | None:
    if not EXAMPLE.is_dir():
        return f"{EXAMPLE} does not exist"
    te.EXAMPLE = EXAMPLE
    return te.missing()


def build(out: Path) -> dict[str, int]:
    (out / "puppeteer.json").write_text('{"args": ["--no-sandbox"]}\n', encoding="utf-8")
    pcfg = str(out / "puppeteer.json")
    env = dict(os.environ, PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8")
    export = out / "export.html"

    def tool(name: str, *args: str) -> int:
        cmd = [sys.executable, "-m", "arch_kit", "--config", "arch-kit.yaml", name, *args]
        p = subprocess.run(cmd, cwd=EXAMPLE, env=env, capture_output=True, text=True, encoding="utf-8")
        (out / f"{name}.log").write_text(p.stdout + p.stderr, encoding="utf-8")
        return p.returncode

    rcs: dict[str, int] = {}
    rcs["render_html"] = tool("render_html", "--out", str(export), "--relabel", "relabel.txt", "--barred",
                              "barred.txt", "--date", te.DATE, "--source", SOURCE, "--kit-commit", KIT_COMMIT,
                              "--puppeteer-config", pcfg)
    rcs["check_export"] = tool("check_export", "--export", str(export), "--barred", "barred.txt",
                               "--relabel", "relabel.txt")
    rcs["browser_facts"] = tool("browser_facts", "--root", ".", "--out", str(out / "facts.json"))
    p = subprocess.run(["node", "check_export_browser.mjs", str(export), "--shots", str(out / "shots"),
                        "--facts", str(out / "facts.json"), "--puppeteer-config", pcfg],
                       cwd=TOOLS / "export", env=env, capture_output=True, text=True, encoding="utf-8")
    (out / "browser.log").write_text(p.stdout + p.stderr, encoding="utf-8")
    rcs["check_export_browser"] = p.returncode
    rcs["check_decision_indexes"] = tool("check_decision_indexes")
    return rcs


class NoChartExample(unittest.TestCase):
    def test_the_example_builds_checks_and_matches_its_snapshot(self):
        why = missing()
        if why:
            self.skipTest(why)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rcs = build(out)
            for name, rc in rcs.items():
                log = out / ("browser.log" if name == "check_export_browser" else f"{name}.log")
                tail = log.read_text(encoding="utf-8")[-1500:] if log.is_file() else ""
                self.assertEqual(rc, 0, f"{name} exited {rc}; rcs {rcs}\n{tail}")
            got = (out / "export.html").read_text(encoding="utf-8")
        self.assertEqual(got.count("<svg"), 1, "the example has one diagram")
        want = te.normalise(SNAPSHOT.read_text(encoding="utf-8"))
        have = te.normalise(got)
        if have != want:
            import difflib
            diff = list(difflib.unified_diff(want.split("\n"), have.split("\n"), "expected", "built", lineterm="", n=0))
            self.fail("the export differs from expected/export.html after normalising:\n" + "\n".join(diff[:40]))


def write_snapshot() -> int:
    why = missing()
    if why:
        print(f"cannot build: {why}", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        rcs = build(Path(tmp))
        if any(rcs.values()):
            print(f"the chain failed: {rcs}", file=sys.stderr)
            return 1
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(te.normalise((Path(tmp) / "export.html").read_text(encoding="utf-8")),
                            encoding="utf-8", newline="\n")
    print(f"wrote {SNAPSHOT}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-snapshot"]:
        sys.exit(write_snapshot())
    unittest.main()
