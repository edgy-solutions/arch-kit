"""Tests for the portal declaration (hosting, audience) and the public-audience rule. All values are made up.

Each case runs a tool in a subprocess under its own declaration, as test_declared.py does, because the declaration
is read once per process. The rule is checked before any work, so no chart or export is needed.
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
FIXTURE = HERE / "testdata"


def config(**portal):
    """The fixture's declaration with its portal replaced; a value of None drops that key, portal=None drops the map."""
    c = yaml.safe_load((FIXTURE / "arch-kit.yaml").read_text(encoding="utf-8"))
    c["loader"] = str(FIXTURE / "loader.py")
    if portal.get("portal", 0) is None:
        del c["portal"]
        return c
    c["portal"] = {"hosting": "ci-artifact", "audience": "public"}
    for k, v in portal.items():
        if v is None:
            del c["portal"][k]
        else:
            c["portal"][k] = v
    return c


class Portal(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "rules.txt").write_text("zebra-host-9\tthe lab\n", encoding="utf-8", newline="\n")
        (self.tmp / "barred.txt").write_text("quux-secret-77\n", encoding="utf-8", newline="\n")

    def run_tool(self, cfg, tool, *args):
        decl = self.tmp / "arch-kit.yaml"
        decl.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        env = dict(os.environ, ARCH_KIT_CONFIG=str(decl), PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "-m", "arch_kit", tool, *args], capture_output=True, text=True,
                              encoding="utf-8", env=env, cwd=self.tmp)

    def export(self, cfg, *extra):
        return self.run_tool(cfg, "check_export", "--export", str(self.tmp / "none.html"), *extra)

    def render(self, cfg, *extra):
        out = self.tmp / "out.html"
        p = self.run_tool(cfg, "render_html", "--out", str(out), "--chart", ".", "--values", "v.yaml",
                          "--release", "r", *extra)
        return p, out

    def test_each_missing_key_exits_2_naming_it(self):
        for cfg, key in ((config(portal=None), "portal"), (config(audience=None), "portal.audience"),
                         (config(hosting=None), "portal.hosting")):
            p = self.export(cfg, "--barred", str(self.tmp / "barred.txt"))
            self.assertEqual(p.returncode, 2, key)
            self.assertIn(f"missing key '{key}'", p.stderr)

    def test_each_bad_value_exits_2_listing_the_allowed_values(self):
        for cfg, key, allowed in ((config(audience="open"), "portal.audience", "public, private"),
                                  (config(hosting="s3"), "portal.hosting", "ci-artifact, static-site, none")):
            p = self.render(cfg)[0]
            self.assertEqual(p.returncode, 2, key)
            self.assertIn(key, p.stderr)
            self.assertIn(allowed, p.stderr)

    def test_public_check_export_without_relabel_exits_2(self):
        p = self.export(config(), "--barred", str(self.tmp / "barred.txt"))
        self.assertEqual(p.returncode, 2)
        self.assertIn("the portal's audience is public: check_export needs a relabel list (--relabel)", p.stderr)

    def test_public_render_without_relabel_or_without_barred_exits_2_and_writes_nothing(self):
        p, out = self.render(config(), "--barred", str(self.tmp / "barred.txt"))
        self.assertEqual(p.returncode, 2)
        self.assertIn("the portal's audience is public: render_html needs a relabel list (--relabel)", p.stderr)
        self.assertFalse(out.exists())
        p, out = self.render(config(), "--relabel", str(self.tmp / "rules.txt"))
        self.assertEqual(p.returncode, 2)
        self.assertIn("the portal's audience is public: render_html needs a barred list (--barred)", p.stderr)
        self.assertFalse(out.exists())

    def test_private_does_not_ask_for_the_lists(self):
        p = self.export(config(audience="private"), "--barred", str(self.tmp / "barred.txt"))
        self.assertNotIn("audience is public", p.stderr)
        p, _ = self.render(config(audience="private"))
        self.assertNotIn("audience is public", p.stderr)

    def test_none_hosting_is_accepted(self):
        p = self.export(config(hosting="none", audience="private"), "--barred", str(self.tmp / "barred.txt"))
        self.assertNotIn("portal.hosting", p.stderr)


if __name__ == "__main__":
    unittest.main()
