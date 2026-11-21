"""Self-test: `render_html` without --date dates the build from the committer date of HEAD, in UTC.

The decisions-only example draws no diagram, so the test needs neither Node nor Chrome. It copies the example into a
temporary git repository, commits it with a fixed committer date, and renders:
  - with no --date: the page carries the UTC day of that commit;
  - with --date: the page carries the given day;
  - with a root that is not in a git repository: the page carries today (UTC) and stderr says so.
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

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_example_decisions import EXAMPLE, KIT, tool  # noqa: E402

COMMITTED = "2026-01-02T23:30:00-05:00"   # 2026-01-03 04:30 UTC
DATE_RE = re.compile(r"Generated: (\d{4}-\d{2}-\d{2})")


def commit(root: Path, when: str) -> None:
    env = dict(os.environ, GIT_COMMITTER_DATE=when, GIT_AUTHOR_DATE=when)
    for args in (["init", "-q"], ["add", "."], ["commit", "-q", "-m", "example"]):
        subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
                       check=True, capture_output=True, env=env)


def copy(tmp: Path, name: str) -> Path:
    root = tmp / name
    shutil.copytree(EXAMPLE, root, ignore=shutil.ignore_patterns("expected", "__pycache__"))
    return root


def date_of(out: Path) -> str:
    return DATE_RE.search(out.read_text(encoding="utf-8")).group(1)


class BuildDate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = copy(self.tmp, "repo")
        commit(self.root, COMMITTED)
        self.out = self.tmp / "export.html"

    def render(self, root: Path, *extra: str, config: str = "arch-kit.yaml") -> subprocess.CompletedProcess:
        return tool(root, "render_html", "--out", str(self.out), "--barred", "barred.txt", *extra, config=config)

    def test_default_is_the_committer_date_in_utc(self):
        p = self.render(self.root)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(date_of(self.out), "2026-01-03")
        self.assertNotIn("no commit to date the build from", p.stderr)

    def test_date_flag_overrides(self):
        p = self.render(self.root, "--date", "2026-02-03")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(date_of(self.out), "2026-02-03")

    def test_a_dirty_tree_keeps_the_head_date(self):
        with (self.root / "decisions" / "0001-lockers-accept-parcels-offline.md").open("a", encoding="utf-8") as f:
            f.write("\n")
        p = self.render(self.root)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(date_of(self.out), "2026-01-03")

    def test_a_root_outside_git_uses_today_and_says_so(self):
        # The records are stamped from a git repository (paths.repo); the root, which dates the build, is not in one.
        nogit = copy(self.tmp, "nogit")
        decl = yaml.safe_load((nogit / "arch-kit.yaml").read_text(encoding="utf-8"))
        decl["paths"]["repo"] = "../repo"
        decl["paths"]["decisions"] = "../repo/decisions"
        (nogit / "arch-kit.yaml").write_text(yaml.safe_dump(decl), encoding="utf-8")
        before = datetime.datetime.now(datetime.timezone.utc).date()
        p = self.render(nogit)
        after = datetime.datetime.now(datetime.timezone.utc).date()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        got = date_of(self.out)
        self.assertIn(got, {before.isoformat(), after.isoformat()})
        self.assertIn(f"render_html: no commit to date the build from; using today ({got})", p.stderr)


if __name__ == "__main__":
    unittest.main()
