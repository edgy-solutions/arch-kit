"""Self-test: the minimal example project builds, checks and matches its snapshot.

Runs the tool chain on examples/minimal and asserts every tool exits 0:
render_html, check_export, check_views, browser_facts, check_export_browser.mjs (Node and Chrome),
check_decision_indexes (bash). Then it compares the export with examples/minimal/expected/export.html after
normalising what changes between machines and commits:
  - each inline <svg> (a diagram's drawing differs by renderer) becomes <svg/>;
  - the build date becomes DATE;
  - the chart, bundle and kit commits (`Chart commit: <sha>`, `Bundle commit: <sha>`, `Kit: <sha>`) become SHA;
  - a decision stamp, `Commit abc1234, 2026-01-01`, becomes `Commit SHA, DATE`, and the note that the working
    tree differs from the commit is dropped.
The example declares no data exchange, so this test does not cover the data-exchange reader; the unit tests of
the reader and of the optional exchange do.

Skipped, with the reason, when Node, the mermaid-cli install (`npm ci` in arch_kit/tools/export) or Chrome
(PUPPETEER_EXECUTABLE_PATH) is missing. CI installs all three, and a skipped test fails the job. The render reads
decision stamps from git, so the checkout needs full history.

The test never writes the snapshot. To regenerate it after an intended change to the example, from the kit root:

    python arch_kit/tools/test_example.py --write-snapshot

and review the diff of examples/minimal/expected/export.html before committing it.
"""
from __future__ import annotations

import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bytes_diff import same_bytes_message  # noqa: E402

KIT = Path(__file__).resolve().parents[2]
EXAMPLE = KIT / "examples" / "minimal"
SNAPSHOT = EXAMPLE / "expected" / "export.html"
TOOLS = KIT / "arch_kit" / "tools"
DATE = "2026-01-01"

SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S)
STAMP_RE = re.compile(r"Commit [0-9a-f]{7,40}, \d{4}-\d{2}-\d{2}")
DIRTY_RE = re.compile(r" \(working tree differs from this commit\)")
DATE_RE = re.compile(r"Generated: \d{4}-\d{2}-\d{2}")
COMMIT_RE = re.compile(r"(Chart commit|Bundle commit|Kit): [0-9a-f]{40}")


def normalise(html: str) -> str:
    html = html.replace("\r\n", "\n")
    html = SVG_RE.sub("<svg/>", html)
    html = STAMP_RE.sub("Commit SHA, DATE", html)
    html = DIRTY_RE.sub("", html)
    html = COMMIT_RE.sub(lambda m: m.group(1) + ": SHA", html)
    return DATE_RE.sub("Generated: DATE", html)


def mmdc() -> Path:
    name = "mmdc.cmd" if sys.platform == "win32" else "mmdc"
    return TOOLS / "export" / "node_modules" / ".bin" / name


def missing() -> str | None:
    if not EXAMPLE.is_dir():
        return f"{EXAMPLE} does not exist"
    if shutil.which("node") is None:
        return "node is not installed"
    if not mmdc().is_file():
        return f"mermaid-cli is not installed at {mmdc()}: run `npm ci` in {TOOLS / 'export'}"
    chrome = os.environ.get("PUPPETEER_EXECUTABLE_PATH")
    if not chrome or not Path(chrome).is_file():
        return "PUPPETEER_EXECUTABLE_PATH does not name a Chrome binary"
    return None


def tool_env() -> dict[str, str]:
    return dict(os.environ, PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8")


def tool(out: Path, name: str, *args: str) -> int:
    cmd = [sys.executable, "-m", "arch_kit", "--config", "arch-kit.yaml", name, *args]
    p = subprocess.run(cmd, cwd=EXAMPLE, env=tool_env(), capture_output=True, text=True, encoding="utf-8")
    (out / f"{name}.log").write_text(p.stdout + p.stderr, encoding="utf-8")
    return p.returncode


def render(out: Path, date: str | None) -> int:
    """Run render_html into out/export.html; `date=None` leaves out --date, so the commit date is used."""
    (out / "puppeteer.json").write_text('{"args": ["--no-sandbox"]}\n', encoding="utf-8")
    return tool(out, "render_html", "--out", str(out / "export.html"), "--chart", "chart", "--values", "values.yaml",
                "--release", "larkspur", "--readiness", "READINESS.md", "--relabel", "relabel.txt",
                "--barred", "barred.txt", *(["--date", date] if date else []),
                "--puppeteer-config", str(out / "puppeteer.json"))


def build(out: Path) -> dict[str, int]:
    """Run the chain into `out`; return each tool's exit code, in order."""
    rcs: dict[str, int] = {"render_html": render(out, DATE)}
    pcfg = str(out / "puppeteer.json")
    env = tool_env()
    export = out / "export.html"
    rcs["check_export"] = tool(out, "check_export", "--export", str(export), "--barred", "barred.txt",
                               "--relabel", "relabel.txt")
    rcs["check_views"] = tool(out, "check_views", "--chart", "chart", "--values", "values.yaml", "--release", "larkspur",
                              "--readiness", "READINESS.md", "--barred", "barred.txt")
    rcs["browser_facts"] = tool(out, "browser_facts", "--root", ".", "--out", str(out / "facts.json"))
    p = subprocess.run(["node", "check_export_browser.mjs", str(export), "--shots", str(out / "shots"),
                        "--facts", str(out / "facts.json"), "--puppeteer-config", pcfg],
                       cwd=TOOLS / "export", env=env, capture_output=True, text=True, encoding="utf-8")
    (out / "browser.log").write_text(p.stdout + p.stderr, encoding="utf-8")
    rcs["check_export_browser"] = p.returncode
    rcs["check_decision_indexes"] = tool(out, "check_decision_indexes")
    return rcs


class Example(unittest.TestCase):
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
        want = normalise(SNAPSHOT.read_text(encoding="utf-8"))
        have = normalise(got)
        if have != want:
            import difflib
            diff = list(difflib.unified_diff(want.split("\n"), have.split("\n"), "expected", "built", lineterm="", n=0))
            self.fail("the export differs from expected/export.html after normalising:\n" + "\n".join(diff[:40]))

    def test_two_builds_without_a_date_write_the_same_bytes(self):
        why = missing()
        if why:
            self.skipTest(why)
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            a, b = Path(t1), Path(t2)
            for d in (a, b):
                rc = render(d, None)
                log = (d / "render_html.log").read_text(encoding="utf-8")[-1500:]
                self.assertEqual(rc, 0, f"render_html exited {rc}\n{log}")
            msg = same_bytes_message(a / "export.html", b / "export.html")
            if msg:
                self.fail(msg)
            page = (a / "export.html").read_text(encoding="utf-8")
        m = DATE_RE.search(page)
        self.assertTrue(m, "the page has no Generated: date")
        iso = subprocess.run(["git", "-C", str(EXAMPLE), "log", "-1", "--format=%cI", "HEAD"], capture_output=True,
                             text=True, encoding="utf-8", check=True).stdout.strip()
        want = datetime.datetime.fromisoformat(iso).astimezone(datetime.timezone.utc).date().isoformat()
        self.assertEqual(m.group(0), f"Generated: {want}")


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
        SNAPSHOT.write_text(normalise((Path(tmp) / "export.html").read_text(encoding="utf-8")), encoding="utf-8",
                            newline="\n")
    print(f"wrote {SNAPSHOT}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-snapshot"]:
        sys.exit(write_snapshot())
    unittest.main()
