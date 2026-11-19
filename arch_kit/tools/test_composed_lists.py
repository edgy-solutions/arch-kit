"""Tests for the lists and audience of the composed build (testdata/composed/). Every name is invented.

Same fixtures as test_composed.py. A finding names its list and rule number, never the value that matched.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from test_composed import DATA, DECL, Composed, tick

TAB = chr(9)
NL = chr(10)


class Lists(Composed):
    def setUp(self):
        super().setUp()
        self.public = False

    def write(self, name, text):
        p = self.tmp / name
        p.write_text(text, encoding="utf-8", newline=NL)
        return p

    def edit(self, name, fn):
        decl = self.repo[name] / DECL
        c = yaml.safe_load(decl.read_text(encoding="utf-8"))
        fn(c)
        decl.write_text(yaml.safe_dump(c), encoding="utf-8", newline=NL)
        if name != "example-portal":
            self.head[name] = tick(self.repo[name])

    def lists(self, **given):
        out = []
        for slot, path in given.items():
            out += ["--list", f"{slot.replace('_', '-')}={path}"]
        return out

    def empty_slots(self):
        return {s: self.write(s + ".txt", "# none" + NL) for s in
                ("example-platform-relabel", "example-second-relabel")}

    def slot_files(self, **barred):
        files = {}
        for n in ("example-platform", "example-second"):
            files[n + "-relabel"] = self.write(n + "-relabel.tsv", "unused-pattern-a" + TAB + "x" + NL)
            files[n + "-barred"] = self.write(n + "-barred.txt", barred.get(n.replace("-", "_"),
                                                                              "unused-pattern-b") + NL)
        return files

    def args(self, files):
        out = []
        for slot, path in files.items():
            out += ["--list", f"{slot}={path}"]
        return out


class Scan(Lists):
    def setUp(self):
        super().setUp()
        self.standard()

    def test_no_slots_on_a_private_portal_names_the_empty_ones(self):
        p, _ = self.render()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("example-platform-relabel", p.stderr)
        self.assertIn("example-second-barred", p.stderr)
        self.assertIn("ran empty", p.stderr)

    def test_a_leak_in_each_member_is_caught_by_its_slot(self):
        for who, phrase in (("example-platform", "Every outbound record carries"),
                            ("example-second", "handed over through a queue")):
            files = self.slot_files(**{who.replace("-", "_"): phrase})
            p, doc = self.render(extra=self.args(files))
            self.assertEqual(p.returncode, 1, p.stderr)
            self.assertEqual(doc, "")
            self.assertFalse((self.tmp / "out.html").exists())
            self.assertIn(f"barred list {who}-barred rule 1", p.stderr)
            self.assertNotIn(phrase.split()[0] + " " + phrase.split()[1], p.stderr)

    def test_a_leak_in_a_consumed_by_entry_is_caught(self):
        own = self.write("own-barred.txt", "commit pins of the platform" + NL)
        p, _ = self.render(extra=["--barred", str(DATA / "barred.txt"), "--barred", str(own)])
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("barred list --barred 2 rule 1", p.stderr)
        self.assertNotIn("commit pins", p.stderr)
        self.assertFalse((self.tmp / "out.html").exists())

    def test_a_conflicting_rule_pair_is_refused(self):
        own = self.write("own.tsv", "same-pattern" + TAB + "one" + NL)
        slot = self.write("slot.tsv", "x" + TAB + "y" + NL + "same-pattern" + TAB + "two" + NL)
        p, _ = self.render(extra=["--relabel", str(own), "--list", f"example-second-relabel={slot}"])
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn("--relabel 1 rule 1", p.stderr)
        self.assertIn("example-second-relabel rule 2", p.stderr)
        self.assertNotIn("same-pattern", p.stderr)

    def test_a_slot_relabel_is_applied_and_the_check_passes(self):
        slot = self.write("slot.tsv", "queue" + TAB + "line" + NL)
        extra = ["--list", f"example-second-relabel={slot}"]
        p, doc = self.render(extra=extra)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn("queue", doc.lower().replace("data-", ""))
        c = self.check(extra=extra)
        self.assertEqual(c.returncode, 0, c.stdout + c.stderr)

    def test_check_export_names_the_list_and_never_the_value(self):
        p, _ = self.render()
        self.assertEqual(p.returncode, 0, p.stderr)
        slot = self.write("late.txt", "queue" + NL)
        c = self.check(extra=["--list", f"example-second-barred={slot}"])
        self.assertEqual(c.returncode, 1, c.stdout + c.stderr)
        self.assertIn("barred list example-second-barred rule 1", c.stderr)
        self.assertNotIn("queue", c.stderr)

    def test_list_flag_faults(self):
        for bad in (["--list", "example-nowhere=" + str(DATA / "barred.txt")],
                    ["--list", "example-platform-barred"],
                    ["--list", f"example-platform-barred={DATA / 'barred.txt'}"] * 2,
                    ["--list", f"example-platform-barred={self.tmp / 'missing.txt'}"]):
            p, _ = self.render(extra=bad)
            self.assertEqual(p.returncode, 2, p.stderr)


class Audience(Lists):
    def make_public(self):
        self.edit("example-portal", lambda c: c["portal"].update(audience="public"))

    def test_a_private_member_under_a_public_portal_is_refused(self):
        self.edit("example-platform", lambda c: c["portal"].update(audience="private"))
        self.make_public()
        self.standard()
        files = self.slot_files()
        p, _ = self.render(extra=[*self.args(files), "--relabel", str(files["example-platform-relabel"]),
                                  "--barred", str(DATA / "barred.txt")])
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn("members[0]: its audience is private", p.stderr)
        self.assertNotIn("example-platform", p.stderr)

    def test_a_missing_slot_on_a_public_portal_is_refused(self):
        self.make_public()
        self.standard()
        files = self.slot_files()
        del files["example-second-barred"]
        p, _ = self.render(extra=[*self.args(files), "--relabel", str(files["example-platform-relabel"]),
                                  "--barred", str(DATA / "barred.txt")])
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn("example-second-barred", p.stderr)

    def test_a_public_portal_with_every_list_builds_and_checks(self):
        self.edit("example-second", lambda c: c["portal"].update(audience="public"))
        self.make_public()
        self.standard()
        files = self.slot_files()
        extra = [*self.args(files), "--relabel", str(files["example-platform-relabel"])]
        p, _ = self.render(extra=[*extra, "--barred", str(DATA / "barred.txt")])
        self.assertEqual(p.returncode, 0, p.stderr)
        c = self.check(extra=extra)
        self.assertEqual(c.returncode, 0, c.stdout + c.stderr)


if __name__ == "__main__":
    unittest.main()
