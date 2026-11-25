"""Tests for `decisions.accounted_for`: every decision record of the named statuses is cited or listed as untraced.

Each case copies examples/minimal into a temporary directory, rewrites its records and declaration, and runs
check_views with --allow-partial, as a consumer would.
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
KIT = HERE.parents[1]
EXAMPLE = KIT / "examples" / "minimal"
OK_ABSENT = "ok: 15 rules, 10 views; not run: quotes, floor (x)"


def entry(record="ADR-0004", decided_by="ADR-0001", capability="none, by decision", reason="a test rule"):
    return {"record": record, "capability": capability, "decided_by": decided_by, "reason": reason}


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = self.tmp / "proj"
        shutil.copytree(EXAMPLE, self.root, ignore=shutil.ignore_patterns("expected", "__pycache__"))
        self.decisions = self.root / "decisions"

    def index(self, n, word):
        """The README line for ADR-000<n>, with the status word it shows (replacing any earlier line)."""
        p = self.decisions / "README.md"
        lines = [l for l in p.read_text(encoding="utf-8").split(chr(10)) if not l.startswith(f"- [ADR-000{n}:")]
        at = max(i for i, l in enumerate(lines) if l.startswith("- [ADR-"))
        lines.insert(at + 1, f"- [ADR-000{n}: A record](ADR-000{n}-a-record.md) **{word}**")
        p.write_text(chr(10).join(lines), encoding="utf-8", newline="")

    def add_record(self, n, word):
        nl = chr(10)
        text = f"# ADR-000{n} A record{nl}{nl}## Status{nl}{nl}{word.capitalize()}.{nl}{nl}## 1. Decision{nl}{nl}Test data.{nl}"
        (self.decisions / f"ADR-000{n}-a-record.md").write_text(text, encoding="utf-8", newline="")
        self.index(n, word)

    def declare(self, block):
        p = self.root / "arch-kit.yaml"
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        d["decisions"]["accounted_for"] = block
        p.write_text(yaml.safe_dump(d, sort_keys=False), encoding="utf-8", newline="")

    def record(self, edit):
        p = self.root / "capability-record.yaml"
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        edit(d["capabilities"])
        p.write_text(yaml.safe_dump(d, sort_keys=False), encoding="utf-8", newline="")

    def run_check(self):
        env = dict(os.environ, PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        env.pop("MSYS_NO_PATHCONV", None)
        return subprocess.run([sys.executable, "-m", "arch_kit", "--config", "arch-kit.yaml", "check_views",
                               "--allow-partial", "x"], cwd=self.root, env=env, capture_output=True,
                              text=True, encoding="utf-8")

    def three(self, untraced=None):
        """ADR-0001 cited by adrs, ADR-0005 only by derived_from, ADR-0004 untraced; ADR-0002 is proposed and
        ADR-0003 superseded. The two new records are exempted from the derived rule, which reads views."""
        self.add_record(4, "accepted")
        self.add_record(5, "accepted")
        (self.root / "adr-exemptions.yaml").write_text(
            yaml.safe_dump({"exempt": {i: {"category": "rule", "reason": "a test record"}
                                       for i in ("ADR-0004", "ADR-0005")}}), encoding="utf-8", newline="")
        self.record(lambda caps: caps["ParcelRouting"].update(derived_from=["ADR-0005 §1"]))
        self.declare({"statuses": ["Accepted"], "untraced": [entry()] if untraced is None else untraced})

    def refused(self, fragment):
        p = self.run_check()
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn(fragment, p.stderr)

    def fails(self, fragment):
        p = self.run_check()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("FAIL: accounted-for: " + fragment, p.stderr)


class AccountedFor(Case):
    def test_absent_key_changes_nothing(self):
        p = self.run_check()
        self.assertEqual((p.returncode, p.stdout.strip(), p.stderr), (0, OK_ABSENT, ""))

    def test_three_records(self):
        self.three()
        p = self.run_check()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(p.stdout.strip().endswith(
            "; accounted for: 3 decision records (2 cited, 1 untraced by decision)"), p.stdout)

    def test_unaccounted_record_fails(self):
        self.three(untraced=[])
        self.fails("ADR-0004 (accepted) is cited by no capability and is not listed in "
                   "decisions.accounted_for.untraced")

    def test_cited_and_listed_fails(self):
        self.three(untraced=[entry(), entry(record="ADR-0001")])
        self.fails("ADR-0001 is cited by ParcelIntake and also listed as untraced by decision")

    def test_other_statuses_are_not_required_or_counted(self):
        self.three()
        self.add_record(5, "proposed")
        p = self.run_check()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(p.stdout.strip().endswith(
            "; accounted for: 2 decision records (1 cited, 1 untraced by decision)"), p.stdout)

    def test_stale_entry_for_superseded_record_fails(self):
        self.three(untraced=[entry(), entry(record="ADR-0003")])
        self.fails("untraced entry ADR-0003: its status is superseded, which the rule doesn't apply to")

    def test_missing_record_file_fails(self):
        self.three(untraced=[entry(), entry(record="ADR-0009")])
        self.fails("untraced entry ADR-0009: no decision record file")

    def test_decided_by_without_file_fails(self):
        self.three(untraced=[entry(decided_by="ADR-0009")])
        self.fails("untraced entry ADR-0004: decided_by ADR-0009 has no decision record file")


class Refusals(Case):
    def setUp(self):
        super().setUp()
        self.three()

    def test_built_is_refused(self):
        self.declare({"statuses": ["Accepted"], "untraced": [entry(capability="built")]})
        self.refused("built is for things that exist")

    def test_none_is_refused(self):
        self.declare({"statuses": ["Accepted"], "untraced": [entry(capability="none")]})
        self.refused("none, by decision")

    def test_two_line_reason_is_refused(self):
        self.declare({"statuses": ["Accepted"], "untraced": [entry(reason="one" + chr(10) + "two")]})
        self.refused("untraced[0].reason")

    def test_long_reason_is_refused(self):
        self.declare({"statuses": ["Accepted"], "untraced": [entry(reason="x" * 161)]})
        self.refused("untraced[0].reason")

    def test_unknown_status_word_is_refused(self):
        self.declare({"statuses": ["Ratified"]})
        self.refused("decisions.accounted_for.statuses")

    def test_empty_statuses_are_refused(self):
        self.declare({"statuses": []})
        self.refused("decisions.accounted_for.statuses")

    def test_unknown_key_is_refused(self):
        self.declare({"statuses": ["Accepted"], "extra": 1})
        self.refused("decisions.accounted_for")

    def test_bad_record_id_is_refused(self):
        self.declare({"statuses": ["Accepted"], "untraced": [entry(record="4")]})
        self.refused("untraced[0].record")

    def test_duplicate_record_is_refused(self):
        self.declare({"statuses": ["Accepted"], "untraced": [entry(), entry()]})
        self.refused("listed twice")

    def test_entry_with_extra_key_is_refused(self):
        e = entry()
        e["note"] = "x"
        self.declare({"statuses": ["Accepted"], "untraced": [e]})
        self.refused("untraced[0]")


if __name__ == "__main__":
    unittest.main()
