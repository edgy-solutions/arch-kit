"""Tests for the optional data exchange (`exchange.reader`). Every name is invented.

Each case writes a small project to a temp directory and runs the tool in a subprocess, because the declaration is
read once per process. Declared: the existing tests, which use the fixture declaration with the reader, cover it.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_declared as td  # noqa: E402

RULES = ("import sys, check_views as c; from pathlib import Path; t = c.Tree(Path('.')); "
         "f = c.rule_outputs(t) + c.rule_generated(t) + c.rule_floor(t, None); print('FAILS', f)")
RENDER = ("import sys, argparse, render_profile as r; from pathlib import Path; "
          "r.generate_document = lambda *x: sys.exit('the generator ran'); "
          "r.Renderer.phases_content = lambda self: ''; r.derived.build = lambda *x: ''; "
          "a = argparse.Namespace(profile='uaf', out=None, slots=None, chart='chart', values=[], release='x', "
          "allow_no_kinds=None, record='capability-record.yaml', readiness='READINESS.md'); "
          "R = r.Renderer(a, Path('views')); print('EXCHANGE', R.exchange, repr(R.dx_content()), R.home, R.dx_id)")


def config(exchange="absent"):
    c = td.fixture_config()
    if exchange == "absent":
        c.pop("exchange", None)
    else:
        c["exchange"] = exchange
    return c


class OptionalExchange(unittest.TestCase):
    def tree(self, home=False, marker=False):
        tmp = td.tmpdir(self)
        td.build_tree(tmp)
        prof = yaml.safe_load((tmp / "profiles.yaml").read_text(encoding="utf-8"))
        prof.pop("data_exchange")
        prof["profiles"] = {p: {"label": p} for p in ("uaf", "dodaf202", "naf4")}
        if home:
            prof["data_exchange"] = {"home": "Aa-One"}
        (tmp / "profiles.yaml").write_text(yaml.safe_dump(prof), encoding="utf-8")
        if marker:
            with (tmp / "views" / "Aa-One.md").open("a", encoding="utf-8") as f:
                f.write("\n<!-- generated: data-exchange -->\n")
        return tmp

    def test_no_exchange_skips_the_exchange_rules(self):
        tmp = self.tree()
        p, _ = td.run_py(RULES, tmp, config())
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn("exchange", p.stdout)
        self.assertNotIn("data_exchange", p.stdout)

    def test_no_exchange_refuses_a_marker(self):
        tmp = self.tree(marker=True)
        p, _ = td.run_py(RULES, tmp, config())
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("no exchange.reader", p.stdout)

    def test_a_home_with_no_exchange_exits_2_naming_the_key(self):
        tmp = self.tree(home=True)
        p, _ = td.run_py(RULES, tmp, config())
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("data_exchange.home", p.stderr)

    def test_a_bad_reader_exits_2_and_lists_the_allowed_values(self):
        tmp = self.tree()
        p, _ = td.run_py(RULES, tmp, config({"reader": "nope"}))
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("exchange.reader", p.stderr)
        self.assertIn("helm-annotations", p.stderr)

    def test_an_exchange_that_is_not_a_map_exits_2(self):
        p, _ = td.run_py(RULES, self.tree(), config("helm-annotations"))
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("exchange", p.stderr)

    def test_render_with_a_chart_and_no_exchange_runs_no_generator(self):
        tmp = self.tree()
        (tmp / "chart" / "templates").mkdir(parents=True)
        (tmp / "chart" / "Chart.yaml").write_text("name: c\nversion: 1\n", encoding="utf-8")
        (tmp / "READINESS.md").write_text("x\n", encoding="utf-8")
        c = config()
        c["readiness"] = {"default": "READINESS.md"}
        p, _ = td.run_py(RENDER, tmp, c)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("EXCHANGE False '' None None", p.stdout)
    def facts(self, cfg, home):
        tmp = self.tree(home=home)
        out = tmp / "facts.json"
        code = f"import sys, browser_facts; sys.exit(browser_facts.main(['--root', '.', '--out', r'{out}']))"
        p, _ = td.run_py(code, tmp, cfg)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return json.loads(out.read_text(encoding="utf-8"))

    def test_the_browser_facts_say_whether_there_is_an_exchange(self):
        self.assertIs(self.facts(config(), False)["exchange"], False)
        self.assertIs(self.facts(td.fixture_config(), True)["exchange"], True)


if __name__ == "__main__":
    unittest.main()
