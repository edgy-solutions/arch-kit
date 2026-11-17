"""Tests for check_decision_indexes on a made-up corpus (testdata/decisions-index/). Every name is invented.

Each case copies the fixture to a temp directory, breaks it once, runs the tool in a subprocess (the declaration is
read once per process) and asserts the exit code and the line that names the failure.
"""
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
FIXTURE = HERE / "testdata" / "decisions-index"
BASH = shutil.which("bash")


@unittest.skipUnless(BASH, "needs bash on the PATH")
class IndexCheck(unittest.TestCase):
    def setUp(self):
        self.tree = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tree, True)
        shutil.copytree(FIXTURE, self.tree, dirs_exist_ok=True)
        self.dec = self.tree / "decisions"

    def append(self, name, text):
        with open(self.dec / name, "a", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def replace(self, name, old, new):
        path = self.dec / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    def decl(self, edit=None):
        c = yaml.safe_load((FIXTURE / "arch-kit.yaml").read_text(encoding="utf-8"))
        if edit:
            edit(c)
        path = self.tree / "arch-kit.yaml"
        path.write_text(yaml.safe_dump(c), encoding="utf-8")
        return path

    def run_tool(self, edit=None, **env):
        e = dict(os.environ, ARCH_KIT_CONFIG=str(self.decl(edit)), PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8")
        e.update(env)
        return subprocess.run([sys.executable, "-m", "arch_kit", "check_decision_indexes"], capture_output=True,
                              text=True, encoding="utf-8", env=e, cwd=self.tree)

    def drift(self, p, stream, line):
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn(line, (p.stdout if stream == "out" else p.stderr).splitlines())

    def test_clean(self):
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stderr)
        out = p.stdout.splitlines()
        self.assertEqual(out[0], "decision indexes clean: 3 IDs, all documents indexed, all statuses agree")
        self.assertIn("note: 'agree' means the index matches the home, NOT that either is true.", out)
        self.assertIn("  all loam:-prefixed ones resolve here.", out)
        self.assertIn("  1 ferro:-prefixed reference(s); 1 Cites line(s), each", out)
        self.assertIn("  pinned at 0123456. That each cited file exists", out)
        self.assertEqual(p.stderr, "")

    def test_a_register_id_with_no_row(self):
        self.append("ADR-0002-beta.md", "\nAlso XY-3.\n")
        p = self.run_tool()
        self.drift(p, "out", "FAIL: register IDs with no row in REGISTER.md:")
        self.assertIn("    XY-3", p.stdout.splitlines())

    def test_a_phantom_row(self):
        self.append("REGISTER.md", "| XY-9 | a ghost | open |\n")
        p = self.run_tool()
        self.drift(p, "out", "FAIL: rows in REGISTER.md whose ID exists nowhere else:")
        self.assertIn("    XY-9", p.stdout.splitlines())

    def test_an_unindexed_document(self):
        (self.dec / "PLAN-extra.md").write_text("# Extra\n", encoding="utf-8")
        p = self.run_tool()
        self.drift(p, "out", "FAIL: documents not referenced by decisions/README.md:")
        self.assertIn("    PLAN-extra.md", p.stdout.splitlines())

    def test_a_status_mismatch(self):
        self.replace("REGISTER.md", "| XY-2 | the second item | closed |", "| XY-2 | the second item | open |")
        p = self.run_tool()
        self.drift(p, "out", "FAIL: XY-2 status disagrees — home says 'closed', index says 'open' "
                             "(the home is authoritative; fix the index)")

    def test_a_home_with_no_token(self):
        self.append("ADR-0002-beta.md", "\n**XY-4 — an item with no status line**\n")
        self.append("REGISTER.md", "| XY-4 | an item with no status line | open |\n")
        p = self.run_tool()
        self.drift(p, "out", "FAIL: XY-4 has no declared Status token in its home document")

    def test_an_unknown_citation_prefix(self):
        self.append("PLAN-build.md", "\nSee zz:ADR-0001.\n")
        p = self.run_tool()
        self.drift(p, "err", "FAIL: cross-repo citations with an unrecognised prefix:")
        self.assertIn("    zz:ADR-0001", p.stderr.splitlines())
        self.assertIn("      Known repos: loam, ferro. An unqualified ADR-NNNN means", p.stderr.splitlines())

    def test_an_unresolved_local_citation(self):
        self.append("PLAN-build.md", "\nSee loam:ADR-0099.\n")
        p = self.run_tool()
        self.drift(p, "err", "FAIL: loam:-prefixed citations with no matching document here:")
        self.assertIn("    loam:ADR-0099", p.stderr.splitlines())

    def test_a_failed_pin_check(self):
        stub = self.tree / "scripts" / "pin-stub.sh"
        stub.write_text("#!/usr/bin/env bash\necho 'error: the pin moved' >&2\nexit 1\n", encoding="utf-8",
                        newline="\n")
        p = self.run_tool()
        self.drift(p, "err", "FAIL: an ferro citation is not pinned (errors above)")
        self.assertIn("error: the pin moved", p.stderr.splitlines())

    def test_no_prefixes_found(self):
        self.replace("ADR-0001-alpha.md", "**XY-1 — the first item**", "the first item")
        self.replace("ADR-0001-alpha.md", "**XY-2 — the second item**", "the second item")
        self.replace("DEBT.md", "| **QZ-01** |", "| QZ-01 |")
        p = self.run_tool()
        self.drift(p, "out", "FAIL: no register prefixes found — the derivation is broken, not the corpus")

    def test_pins_out_receives_the_pin_list(self):
        out = self.tree / "pins.txt"
        p = self.run_tool(PINS_OUT=str(out))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(out.read_text(encoding="utf-8").splitlines(),
                         ["ADR-0001-alpha.md ferro 0123456789abcdef0123456789abcdef01234567 docs/adr/ADR-0007-x.md"])

    def test_a_foreign_prefix_with_no_pin_check_and_a_second_one(self):
        def edit(c):
            c["decisions"]["index"]["foreign"].append({"prefix": "gild"})

        self.append("PLAN-build.md", "\nSee gild:ADR-0003 and zz:ADR-0001.\n")
        p = self.run_tool(edit)
        self.drift(p, "err", "      Known repos: loam, ferro, gild. An unqualified ADR-NNNN means")
        self.append("PLAN-build.md", "\n")
        self.replace("PLAN-build.md", "zz:ADR-0001", "ferro:ADR-0007")
        p = self.run_tool(edit)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = p.stdout.splitlines()
        self.assertIn("  1 ferro:-prefixed reference(s); 1 Cites line(s), each", out)
        self.assertIn("  1 gild:-prefixed reference(s); no pin check is declared for this prefix.", out)
        self.assertLess(out.index("  1 ferro:-prefixed reference(s); 1 Cites line(s), each"),
                        out.index("  1 gild:-prefixed reference(s); no pin check is declared for this prefix."))

    def test_missing_and_bad_declaration_keys_exit_2_naming_the_key(self):
        def drop(*path):
            def edit(c):
                node = c
                for k in path[:-1]:
                    node = node[k]
                del node[path[-1]]
            return edit

        def put(*path, value):
            def edit(c):
                node = c
                for k in path[:-1]:
                    node = node[k]
                node[path[-1]] = value
            return edit

        cases = [(drop("decisions"), "decisions.index"), (drop("decisions", "index"), "decisions.index"),
                 *[(drop("decisions", "index", k), "decisions.index." + k)
                   for k in ("register", "readme", "register_homes", "indexed", "local_prefix")],
                 (put("decisions", "index", "local_prefix", value="Loam"), "decisions.index.local_prefix"),
                 (put("decisions", "index", "register_homes", value=[]), "decisions.index.register_homes"),
                 (put("decisions", "index", "indexed", value=["a b.md"]), "decisions.index.indexed[0]"),
                 (put("decisions", "index", "foreign", value=[{"pin_check": "x"}]), "decisions.index.foreign[0]"),
                 (put("decisions", "index", "foreign", value=[{"prefix": "loam"}]),
                  "decisions.index.foreign[0].prefix"),
                 (put("decisions", "index", "foreign", value=[{"prefix": "ferro", "pin_check": "scripts/none.sh"}]),
                  "decisions.index.foreign[0].pin_check")]
        for edit, key in cases:
            p = self.run_tool(edit)
            self.assertEqual(p.returncode, 2, key)
            self.assertIn(key, p.stderr)
            self.assertEqual(p.stdout, "", key)

    def test_foreign_is_optional(self):
        def edit(c):
            del c["decisions"]["index"]["foreign"]

        self.replace("ADR-0001-alpha.md", " and cites ferro:ADR-0007", "")
        p = self.run_tool(edit)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
