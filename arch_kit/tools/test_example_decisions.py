"""Self-test: the decisions-only example builds, checks and matches its snapshot, and `portal.mode` is validated.

The example (examples/decisions-only) declares `portal.mode: decisions` and `decisions.records.file_prefix: false`.
Its loader has only the decision functions. The test copies it into a temporary git repository (the render stamps
each record from git, so it needs history), runs render_html, check_export and check_decision_indexes, and compares the
export with examples/decisions-only/expected/export.html after the same normalising test_example does. The example draws
no diagram, so those tests need neither Node nor Chrome. The browser tests (here and in test_example_flows and
test_example_alignment) run browser_facts and check_export_browser.mjs on the export, and are skipped, with the
reason, when Node, the export node_modules or Chrome (PUPPETEER_EXECUTABLE_PATH) is missing. CI installs all three,
and a skipped test fails the job.

The test never writes the snapshot. To regenerate it after an intended change to the example, from the kit root:

    python arch_kit/tools/test_example_decisions.py --write-snapshot
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_example import normalise  # noqa: E402

import seam  # noqa: E402

KIT = HERE.parents[1]
EXAMPLE = KIT / "examples" / "decisions-only"
SNAPSHOT = EXAMPLE / "expected" / "export.html"
DATE = "2026-01-01"


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
                   check=True, capture_output=True)


def copy_example(tmp: Path) -> Path:
    root = tmp / "proj"
    shutil.copytree(EXAMPLE, root, ignore=shutil.ignore_patterns("expected", "__pycache__"))
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "example")
    return root


def browser_missing() -> str | None:
    """Why the browser check cannot run here, or None. It needs Node, puppeteer in export/node_modules and Chrome."""
    if shutil.which("node") is None:
        return "node is not installed"
    if not (HERE / "export" / "node_modules" / "puppeteer").is_dir():
        return f"puppeteer is not installed: run `npm ci` in {HERE / 'export'}"
    chrome = os.environ.get("PUPPETEER_EXECUTABLE_PATH")
    if not chrome or not Path(chrome).is_file():
        return "PUPPETEER_EXECUTABLE_PATH does not name a Chrome binary"
    return None


def browser_check(root: Path, export: Path, out: Path) -> tuple[int, int, str]:
    """browser_facts then the browser check on EXPORT, with their logs in OUT; (facts rc, check rc, browser log)."""
    (out / "puppeteer.json").write_text('{"args": ["--no-sandbox"]}\n', encoding="utf-8")
    p = tool(root, "browser_facts", "--root", ".", "--out", str(out / "facts.json"))
    (out / "browser_facts.log").write_text(p.stdout + p.stderr, encoding="utf-8")
    if p.returncode:
        return p.returncode, -1, p.stdout + p.stderr
    env = dict(os.environ, PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8")
    q = subprocess.run(["node", "check_export_browser.mjs", str(export), "--shots", str(out / "shots"),
                        "--facts", str(out / "facts.json"), "--puppeteer-config", str(out / "puppeteer.json")],
                       cwd=HERE / "export", env=env, capture_output=True, text=True, encoding="utf-8")
    log = q.stdout + q.stderr
    (out / "browser.log").write_text(log, encoding="utf-8")
    return 0, q.returncode, log


class BrowserCase:
    """The browser test every decisions-mode example has: set `root`, `out` and `tmp` in setUp. `defaults` is True
    for an example that declares no export.browser, so its search and page-floor lines must say they were derived."""

    defaults = False

    def test_the_browser_check_passes_on_the_export(self):
        why = browser_missing()
        if why:
            self.skipTest(why)
        p = render(self.root, self.out)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        facts_rc, check_rc, log = browser_check(self.root, self.out, self.tmp)
        self.assertEqual(facts_rc, 0, "browser_facts failed")
        self.assertEqual(check_rc, 0, "check_export_browser failed:\n" + log[-1500:])
        self.assertEqual([ln for ln in log.splitlines() if ln.startswith("FAIL")], [])
        self.assertIn(" passed, 0 failed", log)
        if self.defaults:
            how = ("the default phrase (the first decision record's id)", "(the default floor (one page per portal page))")
        else:
            how = ("the declared phrase", "(min_pages, declared)")
        for words in how:
            self.assertIn(words, log)


def tool(root: Path, name: str, *args: str, config: str = "arch-kit.yaml") -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "arch_kit", "--config", config, name, *args], cwd=root, env=env,
                          capture_output=True, text=True, encoding="utf-8")


def render(root: Path, out: Path, config: str = "arch-kit.yaml") -> subprocess.CompletedProcess:
    return tool(root, "render_html", "--out", str(out), "--barred", "barred.txt", "--date", DATE, config=config)


def check(root: Path, out: Path) -> subprocess.CompletedProcess:
    return tool(root, "check_export", "--export", str(out), "--barred", "barred.txt")


class Example(BrowserCase, unittest.TestCase):
    defaults = True  # the decisions-only example declares no export.browser

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = copy_example(self.tmp)
        self.out = self.tmp / "export.html"

    def test_the_example_builds_checks_and_matches_its_snapshot(self):
        p = render(self.root, self.out)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        for name, args in (("check_export", ("--export", str(self.out), "--barred", "barred.txt")),
                           ("check_decision_indexes", ())):
            p = tool(self.root, name, *args)
            self.assertEqual(p.returncode, 0, f"{name}: " + p.stdout + p.stderr)
        got = normalise(self.out.read_text(encoding="utf-8"))
        want = normalise(SNAPSHOT.read_text(encoding="utf-8"))
        if got != want:
            import difflib
            diff = list(difflib.unified_diff(want.split("\n"), got.split("\n"), "expected", "built", lineterm="", n=0))
            self.fail("the export differs from expected/export.html after normalising:\n" + "\n".join(diff[:40]))

    def test_a_dangling_internal_link_fails_only_the_internal_links_check(self):
        why = browser_missing()
        if why:
            self.skipTest(why)
        render(self.root, self.out)
        text = self.out.read_text(encoding="utf-8")
        link = '<a href="#adr-0003">'
        self.assertIn(link, text)
        self.out.write_text(text.replace(link, '<a href="#adr-9999">', 1), encoding="utf-8")
        facts_rc, check_rc, log = browser_check(self.root, self.out, self.tmp)
        self.assertEqual(facts_rc, 0)
        self.assertEqual(check_rc, 1, log[-1500:])
        fails = [ln for ln in log.splitlines() if ln.startswith("FAIL")]
        self.assertEqual(len(fails), 1, fails)
        self.assertIn("internal links", fails[0])
        self.assertIn("#adr-9999", fails[0])

    def test_the_export_holds_the_records_and_no_capability_or_roadmap_page(self):
        render(self.root, self.out)
        text = self.out.read_text(encoding="utf-8")
        for pid in ("adr-0001", "adr-0002", "adr-0003"):
            self.assertIn(f'<section id="{pid}"', text)
        self.assertNotIn('id="decision-roadmap"', text)
        self.assertNotIn('id="cap-', text)
        self.assertNotIn("<h2>Capabilities</h2>", text)
        self.assertIn("decisions/0001-lockers-accept-parcels-offline.md", text)

    def test_the_loader_has_no_capability_functions_and_meets_the_decision_names(self):
        text = (EXAMPLE / "kit_loader.py").read_text(encoding="utf-8")
        self.assertNotIn("def load_record", text)
        names = set(seam.names_for("decisions"))
        self.assertTrue({"read_text", "adr_file", "adr_lead", "adr_status", "index_status"} <= names)
        self.assertFalse(names & {"load_record", "model_capabilities", "resolve_entries", "quote_of",
                                  "measured_line", "resolve_quotes", "KEY_NAMES"})
        self.assertEqual(seam.names_for("full"), seam.NAMES)

    def test_check_export_fails_when_a_record_page_is_missing(self):
        render(self.root, self.out)
        text = self.out.read_text(encoding="utf-8")
        start = text.index('<section id="adr-0002"')
        end = text.index("</section>", start) + len("</section>")
        self.out.write_text(text[:start] + text[end:], encoding="utf-8")
        p = check(self.root, self.out)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("missing adr-0002", p.stderr)

    def test_the_mode_key_is_validated(self):
        decl = yaml.safe_load((self.root / "arch-kit.yaml").read_text(encoding="utf-8"))
        decl["portal"]["mode"] = "bogus"
        (self.root / "bad.yaml").write_text(yaml.safe_dump(decl), encoding="utf-8")
        for name in ("portal", "render_html"):
            p = tool(self.root, name, "--mode", config="bad.yaml") if name == "portal" else \
                render(self.root, self.out, "bad.yaml")
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            self.assertIn("portal.mode", p.stderr)

    def test_no_chart_means_no_chart_provenance_line_and_check_export_passes(self):
        p = render(self.root, self.out)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        text = self.out.read_text(encoding="utf-8")
        self.assertNotIn('data-prov="chart"', text)
        self.assertNotIn('data-prov="digest"', text)
        self.assertIn('data-prov="date"', text)
        p = check(self.root, self.out)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_a_chart_given_in_decisions_mode_is_still_recorded(self):
        chart = self.root / "chart"
        chart.mkdir()
        (chart / "Chart.yaml").write_text("apiVersion: v2" + chr(10) + "name: demo" + chr(10) + "version: 0.1.0" + chr(10), encoding="utf-8")
        (self.root / "values.yaml").write_text("a: 1" + chr(10), encoding="utf-8")
        git(self.root, "add", "chart", "values.yaml")   # the render refuses a chart or values that differ from their commit
        git(self.root, "commit", "-q", "-m", "chart and values")
        p = tool(self.root, "render_html", "--out", str(self.out), "--chart", "chart", "--values", "values.yaml",
                 "--release", "demo", "--barred", "barred.txt", "--date", DATE)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("Chart: demo 0.1.0", self.out.read_text(encoding="utf-8"))
        self.assertEqual(check(self.root, self.out).returncode, 0)

    def test_full_mode_still_requires_the_chart_flags(self):
        minimal = KIT / "examples" / "minimal"
        env = dict(os.environ, PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable, "-m", "arch_kit", "--config", "arch-kit.yaml", "render_html", "--out",
                            str(self.out), "--barred", "barred.txt"], cwd=minimal, env=env, capture_output=True,
                           text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("the following arguments are required: --chart, --values, --release", p.stderr)

    def test_portal_prints_the_mode_and_full_when_absent(self):
        p = tool(self.root, "portal", "--mode")
        self.assertEqual(p.stdout.strip(), "decisions", p.stderr)
        p = tool(self.root, "portal")
        self.assertEqual(p.stdout.strip(), "none private", p.stderr)
        minimal = KIT / "examples" / "minimal"
        env = dict(os.environ, PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable, "-m", "arch_kit", "--config", "arch-kit.yaml", "portal", "--mode"],
                           cwd=minimal, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.stdout.strip(), "full", p.stderr)


def write_snapshot() -> int:
    with tempfile.TemporaryDirectory() as t:
        root = copy_example(Path(t))
        out = Path(t) / "export.html"
        for p in (render(root, out), check(root, out)):
            if p.returncode:
                print(p.stdout + p.stderr, file=sys.stderr)
                return 1
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(normalise(out.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    print(f"wrote {SNAPSHOT}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-snapshot"]:
        sys.exit(write_snapshot())
    unittest.main()
