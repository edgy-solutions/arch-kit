"""Unit tests: browser_facts in `portal.mode: decisions`, and the full-mode facts left as they were.

The facts of a decisions-mode portal come from the declaration and the sources (browser_facts.facts_decisions). The
tests run the tool on copies of the examples. A decisions-mode project has no views, profiles, record or model, and
the tool must not ask for them.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import test_example_decisions as td  # noqa: E402

KIT = td.KIT
EXAMPLES = KIT / "examples"

MINIMAL_FACTS = {
    "badge_kinds": 5, "base_pages": 12, "capability_link": "St-Tx", "capability_pages": 2, "decision_pages": 4,
    "exchange": False, "expect_wide_table": True, "extra_pages": 0, "group_slug": "team", "group_starts": 1,
    "id_max": 47, "min_pages": 5, "min_tables": 5, "min_tokens": 100, "phase_badges": 7, "phase_column": "Stage",
    "phase_names": ["measured", "built", "accepted design", "proposed", "row"], "phases_home": "St-Rm-P",
    "roles": {"diagram": "Op-Pr", "profile_only": "Am-Tr", "table": "Rs-Cn"},
    "search": {"finds": "Rs-Cn", "phrase": "Which resource talks to which"}, "views": 10, "wide_table_columns": 9,
}


class Facts(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def copy(self, name: str) -> Path:
        root = self.tmp / name
        shutil.copytree(EXAMPLES / name, root, ignore=shutil.ignore_patterns("expected", "__pycache__"))
        return root

    def run_facts(self, root: Path, config: str = "arch-kit.yaml"):
        out = self.tmp / "facts.json"
        p = td.tool(root, "browser_facts", "--root", ".", "--out", str(out), config=config)
        return p, (json.loads(out.read_text(encoding="utf-8")) if p.returncode == 0 else None)

    def edit(self, root: Path, change) -> None:
        f = root / "arch-kit.yaml"
        decl = yaml.safe_load(f.read_text(encoding="utf-8"))
        change(decl)
        f.write_text(yaml.safe_dump(decl, sort_keys=False), encoding="utf-8")

    def test_the_flows_example_lists_its_pages_in_document_order(self):
        p, facts = self.run_facts(self.copy("flows"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(facts, {
            "mode": "decisions",
            "page_ids": ["adr-0001", "adr-0002", "adr-0003", "flows"],
            "decision_pages": 3, "alignment_pages": 0, "flows_pages": 1,
            "search": {"phrase": "cargo van", "finds": "adr-0002"},
            "min_pages": 5,
        })

    def test_the_alignment_example_lists_its_alignment_page_after_the_decisions(self):
        p, facts = self.run_facts(self.copy("alignment"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(facts["page_ids"], ["adr-0001", "adr-0002", "adr-0003", "alignment-coverage"])
        self.assertEqual((facts["decision_pages"], facts["alignment_pages"], facts["flows_pages"]), (3, 1, 0))

    def test_the_decisions_only_example_has_no_alignment_or_flows_page(self):
        p, facts = self.run_facts(self.copy("decisions-only"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(facts["page_ids"], ["adr-0001", "adr-0002", "adr-0003"])
        self.assertEqual((facts["alignment_pages"], facts["flows_pages"]), (0, 0))

    def test_with_no_export_browser_both_settings_take_their_defaults(self):
        p, facts = self.run_facts(self.copy("decisions-only"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(facts["search"], {"phrase": "ADR-0001", "finds": "adr-0001"})
        self.assertEqual(facts["min_pages"], 4)

    def test_a_missing_min_pages_is_one_per_page_with_the_front(self):
        root = self.copy("flows")
        self.edit(root, lambda d: d["export"]["browser"].pop("min_pages"))
        p, facts = self.run_facts(root)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(facts["min_pages"], 1 + len(facts["page_ids"]))
        self.assertEqual(facts["search"], {"phrase": "cargo van", "finds": "adr-0002"})

    def test_a_missing_search_takes_the_first_record(self):
        root = self.copy("flows")
        self.edit(root, lambda d: d["export"]["browser"].pop("search"))
        p, facts = self.run_facts(root)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(facts["search"], {"phrase": "ADR-0001", "finds": "adr-0001"})
        self.assertEqual(facts["min_pages"], 5)

    def test_a_declared_search_without_its_phrase_exits_2(self):
        root = self.copy("flows")
        self.edit(root, lambda d: d["export"]["browser"]["search"].pop("phrase"))
        p, _ = self.run_facts(root)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("export.browser.search.phrase", p.stderr)

    def test_a_finds_id_that_is_not_a_decision_exits_2(self):
        root = self.copy("flows")
        self.edit(root, lambda d: d["export"]["browser"]["search"].update(finds="ADR-0099"))
        p, _ = self.run_facts(root)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("ADR-0099", p.stderr)
        self.assertIn("not a decision record id", p.stderr)

    def test_the_full_mode_facts_are_unchanged(self):
        root = self.tmp / "minimal"
        shutil.copytree(EXAMPLES / "minimal", root, ignore=shutil.ignore_patterns("expected", "__pycache__"))
        p, facts = self.run_facts(root)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(facts, MINIMAL_FACTS)


if __name__ == "__main__":
    unittest.main()
