"""Tests that phases, statuses, views and the browser facts come from the declaration.

The kit's fixture (testdata/arch-kit.yaml) declares a phase order, status words, view ids and homes that differ from
the first consumer's. Tests that need a changed declaration or a tree of files run in a subprocess, as test_labels.py
does, because the declaration is read once per process.
"""
from __future__ import annotations

import copy
import json
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
os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))

import capability_phases as cp  # noqa: E402
import declared  # noqa: E402
import derived  # noqa: E402
import render_html  # noqa: E402

FIXTURE = HERE / "testdata"
SCRIPT = HERE / "export" / "check_export_browser.mjs"
SYSML = "occurrence def Alpha :> Top;\noccurrence def Beta :> Other;\n"


def fixture_config() -> dict:
    config = yaml.safe_load((FIXTURE / "arch-kit.yaml").read_text(encoding="utf-8"))
    config["loader"] = str(FIXTURE / "loader.py")
    return config


def run_py(code: str, tmp: Path, config: dict | None = None):
    """Run `code` in a subprocess whose declaration is `config` (default: the fixture's), written into `tmp`."""
    path = tmp / "arch-kit.yaml"
    path.write_text(yaml.safe_dump(config or fixture_config()), encoding="utf-8")
    env = dict(os.environ, ARCH_KIT_CONFIG=str(path), PYTHONPATH=str(HERE), PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", env=env, cwd=tmp)
    return p, path


def tmpdir(case: unittest.TestCase) -> Path:
    tmp = Path(tempfile.mkdtemp())
    case.addCleanup(shutil.rmtree, tmp, True)
    return tmp


class PhasesFollowTheDeclaration(unittest.TestCase):
    def phase(self, cap, leads=()):
        return cp.phase_of(cap, dict(leads))

    def test_the_fixture_declares_a_different_order_from_the_consumers(self):
        self.assertEqual(declared.phase_names("t"), ["verified", "shipped", "draft", "agreed", "listed"])
        self.assertEqual(declared.floor_phases("t"), ("verified", "shipped"))
        self.assertEqual(declared.floor_name("t"), "shipped")

    def test_each_capability_lands_in_the_declared_phase(self):
        self.assertEqual(self.phase({"measured": [{"entry": "e"}], "built": [{"template": "t"}]}), "verified")
        self.assertEqual(self.phase({"built": [{"template": "t"}]}), "shipped")
        self.assertEqual(self.phase({"adrs": ["ADR-0001 §s"]}, [("ADR-0001", "accepted")]), "agreed")
        self.assertEqual(self.phase({"adrs": ["ADR-0001 §s"]}, [("ADR-0001", "proposed")]), "draft")
        self.assertEqual(self.phase({"pending": ["x"]}), "draft")
        self.assertEqual(self.phase({"rows": ["IS-1"]}), "listed")
        self.assertIsNone(self.phase({}))

    def test_the_first_matching_phase_wins(self):
        cap = {"adrs": ["ADR-0001 §s", "ADR-0002 §s"]}
        self.assertEqual(self.phase(cap, [("ADR-0001", "accepted"), ("ADR-0002", "proposed")]), "draft")


class StatusesFollowTheDeclaration(unittest.TestCase):
    def test_status_word_is_the_declared_word(self):
        self.assertEqual(render_html.status_word("accepted (2026)"), "Accepted")
        self.assertEqual(render_html.status_word("withdrawn"), "Withdrawn")
        self.assertEqual(render_html.status_word("odd one"), "Odd")
        self.assertEqual(render_html.status_word(None), "no status")

    def test_derived_classes_by_declared_lead_and_in_force_is_a_flag(self):
        self.assertEqual(derived.adr_class("ADR-0001", "# T\n\n## Status\n\nProposed\n"), "Proposed")
        self.assertEqual(derived.adr_class("ADR-0001", "# T\n\n## Status\n\nSuperseded by 2\n"), "Superseded")
        in_force = {s.word for s in declared.statuses("t") if s.in_force}
        self.assertEqual(in_force, {"Accepted", "Proposed"})
        with self.assertRaises(cp.CheckError) as e:
            derived.adr_class("ADR-0001", "# T\n\n## Status\n\nweird\n")
        self.assertIn("no status beginning accepted, proposed, superseded, rejected, deprecated or withdrawn",
                      e.exception.args[0])

    def test_check_record_refuses_a_record_whose_status_is_not_in_force(self):
        tmp = tmpdir(self)
        (tmp / "ADR-0001-one.md").write_text(
            "# ADR-0001 One\n\n## Status\n\nsuperseded by ADR-0002\n\n## status\n\nText.\n", encoding="utf-8")
        (tmp / "README.md").write_text("[ADR-0001: One](ADR-0001-one.md)\n", encoding="utf-8")
        (tmp / "ROADMAP.md").write_text(
            "| # | increment | what isolates | home | depends on |\n|---|---|---|---|---|\n", encoding="utf-8")
        record = yaml.safe_load((FIXTURE / "record.yaml").read_text(encoding="utf-8"))
        record["capabilities"]["Alpha"]["adrs"] = ["ADR-0001 §status"]
        fails = cp.check_record(record, {"Alpha": "Top"}, tmp)
        self.assertTrue(any("ADR-0001 has no readable ## Status line beginning accepted or proposed" in f
                            for f in fails), fails)


class BadDeclarationsExit2(unittest.TestCase):
    CASES = {
        "unknown rule": (lambda c: c["phases"][0].update(when=["frobnicated"]), "frobnicated"),
        "unknown status": (lambda c: c["phases"][2].update(when=[{"status": "Nonesuch"}]), "Nonesuch"),
        "duplicate name": (lambda c: c["phases"][1].update(name="verified"), "duplicate"),
        "bad floor": (lambda c: c.update(floor="nowhere"), "floor"),
        "bad badge": (lambda c: c["phases"][0].update(badge="z"), "badge"),
    }

    def test_each_exits_2_and_names_the_declaration(self):
        for label, (change, word) in self.CASES.items():
            with self.subTest(label):
                tmp = tmpdir(self)
                config = copy.deepcopy(fixture_config())
                change(config)
                p, path = run_py("import declared; declared.phases('t'); declared.floor_phases('t')", tmp, config)
                self.assertEqual(p.returncode, 2, p.stderr)
                self.assertIn(word, p.stderr)
                self.assertIn(str(path), p.stderr)


def build_tree(tmp: Path, dx_home: str = "Aa-One") -> None:
    """A tree the fixture declaration can be read against: four views, two capabilities, two decision records."""
    (tmp / "views").mkdir()
    (tmp / "model").mkdir()
    files = {"Aa-One": "Aa-One.md", "Bb-Two": "Bb-Two.md", "Cc-Cap": "Cc-Cap.md", "Pp-Home": "Pp-Home.md"}
    prof = {"views": {v: {"name": v, "file": f"views/{f}"} for v, f in files.items()},
            "data_exchange": {"home": dx_home}}
    (tmp / "profiles.yaml").write_text(yaml.safe_dump(prof), encoding="utf-8")
    (tmp / "slots.yaml").write_text("{}\n", encoding="utf-8")
    (tmp / "README.md").write_text("x\n", encoding="utf-8")
    (tmp / "model" / "example.sysml").write_text(SYSML, encoding="utf-8")
    wide = "| a | b | c | d | e |\n|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 |\n"
    narrow = "| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 |\n"
    (tmp / "views" / "Aa-One.md").write_text("# Aa\n\n" + narrow + "\n" + wide, encoding="utf-8")
    (tmp / "views" / "Bb-Two.md").write_text("# Bb\n\n" + narrow, encoding="utf-8")
    (tmp / "views" / "Cc-Cap.md").write_text("# Cc\n\n" + narrow, encoding="utf-8")
    # Pp-Home: a legend of 3 rows, the generated table (one row per capability, 2), a second Stage table
    # of 2 rows, and a table with no Stage column.
    (tmp / "views" / "Pp-Home.md").write_text(
        "# Pp\n\n| Stage | Meaning |\n|---|---|\n| verified | a |\n| shipped | b |\n| listed | c |\n\n"
        "<!-- generated: capability-phases -->\n\n"
        "| Thing | Stage | Note |\n|---|---|---|\n| x | draft | y |\n| z | agreed | w |\n\n"
        "| Thing | Note |\n|---|---|\n| x | y |\n", encoding="utf-8")
    record = yaml.safe_load((FIXTURE / "record.yaml").read_text(encoding="utf-8"))
    record["groups"]["Other"] = "The other group"
    record["capabilities"]["Beta"] = {"description": "Beta is the second one.", "adrs": ["ADR-0001 §status"],
                                      "degraded_mode": "ADR-0001 §status"}
    (tmp / "capability-record.yaml").write_text(yaml.safe_dump(record), encoding="utf-8")
    (tmp / "ADR-0001-one.md").write_text("# ADR-0001 One\n\n## Status\n\naccepted\n\n## status\n\nText.\n",
                                         encoding="utf-8")
    (tmp / "ADR-0002-two.md").write_text("# ADR-0002 Two\n\n## Status\n\nproposed\n", encoding="utf-8")
    (tmp / "ROADMAP.md").write_text(
        "| # | increment | what isolates | home | depends on |\n|---|---|---|---|---|\n", encoding="utf-8")


def browser_facts(case: unittest.TestCase, dx_home: str = "Aa-One") -> dict:
    tmp = tmpdir(case)
    build_tree(tmp, dx_home)
    out = tmp / "facts.json"
    code = f"import sys, browser_facts; sys.exit(browser_facts.main(['--root', '.', '--out', r'{out}']))"
    p, _ = run_py(code, tmp)
    case.assertEqual(p.returncode, 0, p.stderr)
    return json.loads(out.read_text(encoding="utf-8"))


class BrowserFacts(unittest.TestCase):
    def test_every_field_against_hand_counted_values(self):
        f = browser_facts(self)
        self.assertEqual(f["views"], 4)
        self.assertEqual(f["base_pages"], 6)              # the front page, 4 views, the declarations page
        self.assertEqual(f["capability_pages"], 2)        # Alpha, Beta
        self.assertEqual(f["decision_pages"], 3)          # ADR-0001, ADR-0002, the roadmap note
        self.assertEqual(f["phase_badges"], 7)            # legend 3 + generated table 2 + second Stage table 2
        self.assertEqual(f["badge_kinds"], 5)
        self.assertEqual(f["phase_names"], ["verified", "shipped", "draft", "agreed", "listed"])
        self.assertEqual(f["phase_column"], "Stage")
        self.assertEqual(f["group_starts"], 1)            # Alpha is in Top, Beta in Other
        self.assertEqual(f["group_slug"], "team")
        self.assertEqual(f["phases_home"], "Pp-Home")
        self.assertEqual(f["wide_table_columns"], 9)      # Aa-One is the data-exchange home: the kit's Exchanges table
        self.assertEqual(f["roles"], {"table": "Aa-One", "diagram": "Bb-Two", "profile_only": "Cc-Cap"})
        self.assertEqual(f["search"], {"phrase": "which gadget feeds which", "finds": "Aa-One"})
        self.assertEqual(f["capability_link"], "Cc-Cap")
        self.assertEqual((f["min_pages"], f["min_tables"], f["min_tokens"]), (3, 2, 10))
        import render_html
        self.assertEqual(f["id_max"], render_html.ID_MAX)

    def test_without_the_data_exchange_home_the_width_is_the_sources_widest_table(self):
        self.assertEqual(browser_facts(self, dx_home="Bb-Two")["wide_table_columns"], 5)


class ViewsFollowTheDeclaration(unittest.TestCase):
    def test_check_views_enforces_the_declared_home_and_required_views(self):
        tmp = tmpdir(self)
        build_tree(tmp)
        (tmp / "views" / "Bb-Two.md").write_text("# Bb\n\n<!-- generated: capability-phases -->\n", encoding="utf-8")
        code = ("import check_views, project\n"
                "t = check_views.Tree(project.ROOT)\n"
                "print('\\n'.join(check_views.rule_phases(t)))\n"
                "print('\\n'.join(check_views.rule_outputs(t)))\n")
        p, _ = run_py(code, tmp)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("phases: the capability-phases marker is in Bb-Two, not in Pp-Home", p.stdout)
        self.assertIn("outputs: no view exports XV-1 under dodaf202", p.stdout)
        self.assertNotIn("is missing", p.stdout)    # the declared required views Aa-One and Bb-Two exist
        self.assertNotIn("Op-Cn", p.stdout)         # the first consumer's required views are not asked for


class BrowserScript(unittest.TestCase):
    def test_without_facts_it_exits_2(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not installed")
        p = subprocess.run([node, str(SCRIPT), "x.html", "--shots", tempfile.gettempdir()],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn("--facts", p.stderr)


if __name__ == "__main__":
    unittest.main()
