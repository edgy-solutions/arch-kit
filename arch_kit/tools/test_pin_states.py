"""Tests for the pin states of the composed build and the consumer's own drift check. Every name is invented.

The platform is committed at C0, then one record is edited (changed) and another is marked superseded; the composition
pins the platform at that later commit. Entries pinned at C0 therefore see each state.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest

from test_composed import DECL, GIT, HERE, Composed, tick

KIT = HERE.parents[1]
ZERO = "0" * 40


def section(doc: str, page: str) -> str:
    m = re.search(rf'<section id="{re.escape(page)}".*?</section>', doc, re.S)
    assert m, page
    return m.group(0)


def pins(text: str) -> list[str]:
    return re.findall(r'data-pin="([^"]+)"', text)


@unittest.skipUnless(GIT, "needs git on the PATH")
class States(Composed):
    def setUp(self):
        super().setUp()
        self.c0 = self.head["example-platform"]
        d = self.repo["example-platform"] / "decisions"
        one = next(d.glob("ADR-0001-*.md"))
        one.write_text(one.read_text(encoding="utf-8").replace("a label", "a label and a version"),
                       encoding="utf-8", newline="\n")
        two = next(d.glob("ADR-0002-*.md"))
        two.write_text(two.read_text(encoding="utf-8").replace("Accepted.", "Superseded."),
                       encoding="utf-8", newline="\n")
        self.head["example-platform"] = tick(self.repo["example-platform"])
        self.d = self.head["example-platform"]

    def build(self, by_consumer):
        """One `consumes:` entry on the platform for each consumer named: (commit, records)."""
        for name in ("example-second", "example-app", "example-hidden"):
            if name in by_consumer:
                c, r = by_consumer[name]
                self.commit_consumer(name, [self.entry("example-platform", c, "Reason " + name, records=r)])
            else:
                self.commit_consumer(name, [self.entry("example-second" if name != "example-second" else
                                                       "example-unrelated", self.c0, "Elsewhere")])
        self.commit_portal(consumers=("example-app", "example-hidden"))
        p, doc = self.render()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return doc

    def test_each_state_on_the_record_it_names(self):
        doc = self.build({"example-second": (self.c0, ["ADR-0001", "ADR-0002", "ADR-0003", "ADR-0009"]),
                          "example-app": (ZERO, ["ADR-0003"])})
        self.assertEqual(pins(section(doc, "example-platform--adr-0001")), ["changed"])
        self.assertEqual(pins(section(doc, "example-platform--adr-0002")), ["superseded"])
        self.assertEqual(sorted(pins(section(doc, "example-platform--adr-0003"))), ["current", "pin-not-found"])
        front = doc[doc.index('data-member="example-platform"'):doc.index('data-member="example-second"')]
        self.assertIn("record-not-found", pins(front))
        second = doc[doc.index('data-member="example-second"'):]
        self.assertEqual(pins(second[:second.index("</div></div>") + 1]).count("record-not-found"), 1)

    def test_whole_portal_entries(self):
        doc = self.build({"example-second": (self.d, None), "example-app": (self.c0, None),
                          "example-hidden": (ZERO, None)})
        front = doc[doc.index('data-member="example-platform"'):doc.index('data-member="example-second"')]
        self.assertEqual(sorted(pins(front)), ["changed", "current", "pin-not-found"])

    def test_the_text_of_a_state(self):
        doc = self.build({"example-second": (self.c0, ["ADR-0001"])})
        self.assertIn('<span class="pin" data-pin="changed">changed since</span>', doc)

    def test_the_exit_code_is_zero_in_every_state(self):
        self.build({"example-second": (self.c0, ["ADR-0001", "ADR-0009"]), "example-app": (ZERO, ["ADR-0002"])})


class Drift(Composed):
    def setUp(self):
        super().setUp()
        self.c0 = self.head["example-platform"]
        d = self.repo["example-platform"] / "decisions"
        one = next(d.glob("ADR-0001-*.md"))
        one.write_text(one.read_text(encoding="utf-8").replace("a label", "a label and a version"),
                       encoding="utf-8", newline="\n")
        self.head["example-platform"] = tick(self.repo["example-platform"])

    def run_check(self, entries):
        self.commit_consumer("example-app", entries)
        env = dict(os.environ, ARCH_KIT_CONFIG=str(self.repo["example-app"] / DECL), PYTHONPATH=str(KIT),
                   PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, "-m", "arch_kit", "check_consumes", "--checkout",
                               f"example-platform={self.repo['example-platform']}"],
                              cwd=self.repo["example-app"], capture_output=True, text=True, encoding="utf-8", env=env)

    def test_warn_is_the_default_and_exits_zero(self):
        p = self.run_check([self.entry("example-platform", self.c0, "Reason", records=["ADR-0001"])])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("warn: consumes[0]: changed since the pin: ADR-0001", p.stdout)
        self.assertIn("superseded is shown only where composed", p.stdout)

    def test_fail_exits_one(self):
        p = self.run_check([self.entry("example-platform", self.c0, "Reason", records=["ADR-0001"], drift="fail")])
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("FAIL: consumes[0]: changed since the pin: ADR-0001", p.stdout)

    def test_an_unchanged_record_is_quiet(self):
        p = self.run_check([self.entry("example-platform", self.c0, "Reason", records=["ADR-0003"], drift="fail")])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn("changed since", p.stdout)

    def test_a_whole_portal_entry(self):
        p = self.run_check([self.entry("example-platform", self.c0, "Reason", drift="fail")])
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("FAIL: consumes[0]: changed since the pin: the decisions directory", p.stdout)

    def test_pin_not_found_is_still_a_failure(self):
        p = self.run_check([self.entry("example-platform", ZERO, "Reason")])
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("pin not found", p.stdout)


if __name__ == "__main__":
    unittest.main()
