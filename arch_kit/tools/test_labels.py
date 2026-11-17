"""Tests that the labels the kit prints come from the declaration, not from the kit.

The kit's fixture declares made-up words. Each site that prints a declared word is rendered under the fixture, and
none of the first consumer's words may appear.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

HERE = Path(__file__).resolve().parent
KIT = HERE.parent.parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))

import capability_phases  # noqa: E402
import derived  # noqa: E402
import render_html  # noqa: E402

FIXTURE = HERE / "testdata"
SYSML = "occurrence def Alpha :> Top;\noccurrence def Beta :> Top;\n"
# The first consumer's words for these concepts; none may reach the fixture's output.
FORBIDDEN = ["Severed", "severed", "Lane", "lane-start", "Lab ", ", lab "]
# Each declared key, and a call that needs it.
KEYS = {
    "labels.degraded_mode.heading": "import derived; derived.degraded_mode_table({'capabilities': {}}, '')",
    "labels.degraded_mode.marker": "import derived; derived.degraded_marker()",
    "labels.degraded_mode.attribute": "import render_html, argparse; render_html.capability_pages("
                                      "argparse.Namespace(record=ARGS[0], chart='.', readiness=ARGS[1]), "
                                      "type('U', (), {'sysml': ARGS[2]}), {}, {}, render_html.Decisions(ARGS[3]), '')",
    "labels.degraded_mode.open_row_prefix":
        "import derived; derived.degraded_mode_table({'capabilities': {}}, '')",
    "labels.group.column": "import render_html; render_html.group_class()",
    "labels.environment.word": "import capability_phases; capability_phases.environment_sentence({'A': 'x'}, ['A'])",
}


def declaration_without(dotted: str, tmp: Path) -> Path:
    """The fixture's declaration with one dotted key removed (and an empty parent with it)."""
    config = yaml.safe_load((FIXTURE / "arch-kit.yaml").read_text(encoding="utf-8"))
    config["loader"] = str(FIXTURE / "loader.py")
    parts = dotted.split(".")
    node = config
    for part in parts[:-1]:
        node = node[part]
    del node[parts[-1]]
    path = tmp / "arch-kit.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


class MissingLabel(unittest.TestCase):
    def test_each_absent_label_key_exits_2_with_the_message(self):
        for dotted, code in KEYS.items():
            with self.subTest(key=dotted):
                tmp = Path(tempfile.mkdtemp())
                self.addCleanup(shutil.rmtree, tmp, True)
                decl = declaration_without(dotted, tmp)
                if "ARGS" in code:
                    code = "ARGS = " + repr(self.page_args(tmp)) + "\n" + code
                env = dict(os.environ, ARCH_KIT_CONFIG=str(decl), PYTHONPATH=str(HERE),
                           PYTHONIOENCODING="utf-8")
                p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                   encoding="utf-8", env=env, cwd=tmp)
                self.assertEqual(p.returncode, 2, p.stderr)
                tool = re.search(r"needed by (\w+)", p.stderr).group(1)
                self.assertEqual(p.stderr.strip(), f"arch-kit: {decl}: missing key '{dotted}' (needed by {tool})")

    @staticmethod
    def page_args(tmp: Path):
        return make_pages_tree(tmp)


def make_pages_tree(tmp: Path):
    """A decisions directory, a readiness doc and a record for capability_pages: (record, readiness, sysml, decisions)."""
    dec = tmp / "decisions"
    dec.mkdir()
    (dec / "ADR-0001-one.md").write_text("# ADR-0001 One\n\n## Status\n\naccepted\n\n## status\n\nText.\n",
                                         encoding="utf-8")
    (dec / "ROADMAP.md").write_text("| # | increment | what isolates | home | depends on |\n|---|---|---|---|---|\n",
                                    encoding="utf-8")
    ready = tmp / "readiness.md"
    ready.write_text("## RUN 2026-09-26 anchor one\nalpha ran\n", encoding="utf-8")
    record = yaml.safe_load((FIXTURE / "record.yaml").read_text(encoding="utf-8"))
    record["capabilities"]["Beta"] = {"description": "Beta is the second one.", "adrs": ["ADR-0001 §status"],
                                      "degraded_mode": "ADR-0001 §status"}
    path = tmp / "record.yaml"
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    return str(path), str(ready), SYSML, str(dec)


class FixtureRenderHoldsItsOwnWords(unittest.TestCase):
    def assert_clean(self, text: str):
        for word in FORBIDDEN:
            self.assertNotIn(word, text)

    def record(self):
        return yaml.safe_load((FIXTURE / "record.yaml").read_text(encoding="utf-8"))

    def test_the_derived_table_and_its_marker(self):
        out = derived.degraded_mode_table(self.record(), SYSML.split("\n")[0])
        self.assertIn("Isolated behaviour: 0 of 1 capabilities have it stated", out)
        self.assertIn("| Capability | Isolated behaviour | Row |", out)
        self.assertIn("| Alpha | not stated | IS-1 |", out)
        self.assertEqual(derived.degraded_marker(), "<!-- generated: isolated-behaviour -->")
        self.assertEqual(derived.homes()[derived.degraded_marker()], "St-Tx")
        self.assert_clean(out + derived.degraded_marker())

    def test_the_environment_sentence_and_the_evidence_cell(self):
        envs = {"A": "the first environment", "B": "the second"}
        text = capability_phases.environment_sentence(envs, ["A", "B"])
        self.assertEqual(text, "Site A is the first environment and site B the second.")
        record = self.record()
        cell = capability_phases.evidence_item(record, {"e1": (0, "2026-09-26", "run")}, {"entry": "e1"}, "alpha ran")
        self.assertEqual(cell, "2026-09-26, site A, run: alpha ran")
        self.assert_clean(text + cell)

    def test_the_group_column_and_the_rule_between_groups(self):
        table = ("<table><thead><tr><th>Capability</th><th>Team</th></tr></thead><tbody>"
                 "<tr><td>A</td><td>One</td></tr><tr><td>B</td><td>Two</td></tr></tbody></table>")
        out = render_html.style_table(table)
        self.assertEqual(out.count('class="team-start"'), 1)
        self.assertIn("tr.team-start>*{", render_html.CSS.replace("GROUPCLASS", render_html.group_class()))
        self.assert_clean(out + render_html.group_class())

    def test_the_capability_page(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        record, ready, sysml, decisions = make_pages_tree(tmp)
        args = argparse.Namespace(record=record, chart=str(tmp), readiness=ready)
        uaf = SimpleNamespace(sysml=sysml)
        sections, _ = render_html.capability_pages(args, uaf, {}, {}, render_html.Decisions(decisions), "")
        page = "".join(sections)
        self.assertIn("<h2>Isolated behaviour</h2><p data-isolated>Not stated by a decision record. Open row: IS-1", page)
        self.assertIn("<p data-isolated>Stated in ", page)
        self.assert_clean(page)


if __name__ == "__main__":
    unittest.main()
