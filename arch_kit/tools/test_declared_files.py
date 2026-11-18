"""Tests for the declared content file names (`files.*`). Every name is invented.

Each case runs a small snippet in a subprocess, because the declaration is read once per process.
The end-to-end case renames every content file of examples/minimal, declares the new names, and shows the tools
that need no chart-rendering stack give the same result as on the original.
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

DEFAULTS = {
    "profiles": "profiles.yaml", "slots": "slots.yaml", "appendix": "APPENDIX-A.md", "inventory": "INVENTORY.md",
    "readme": "README.md", "record": "capability-record.yaml", "adr_exemptions": "adr-exemptions.yaml",
    "annotation_exceptions": "annotation-exceptions.yaml",
}
SNIPPET = ("import sys; sys.path.insert(0, %r); import declared; "
           "print(*[declared.content_file(k, 't') for k in %r], sep='|')" % (str(HERE), list(DEFAULTS)))
README_SNIPPET = ("import sys; sys.path.insert(0, %r); import declared; "
                  "print(declared.decisions_readme('t'))" % str(HERE))


class ContentFiles(unittest.TestCase):
    def setUp(self):
        self.tree = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tree, True)

    def run_snippet(self, snippet, edit=None):
        c = yaml.safe_load((HERE / "testdata" / "arch-kit.yaml").read_text(encoding="utf-8"))
        c["paths"] = {"root": ".", "repo": ".", "decisions": "decisions"}
        if edit:
            edit(c)
        path = self.tree / "arch-kit.yaml"
        path.write_text(yaml.safe_dump(c), encoding="utf-8")
        env = dict(os.environ, ARCH_KIT_CONFIG=str(path), PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "-c", snippet], capture_output=True, text=True, encoding="utf-8",
                              env=env, cwd=self.tree)

    def refused(self, edit, key, snippet=SNIPPET):
        p = self.run_snippet(snippet, edit)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn(key, p.stderr)

    def test_defaults_are_todays_names(self):
        c = yaml.safe_load((HERE / "testdata" / "arch-kit.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("files", c)
        p = self.run_snippet(SNIPPET)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip().split("|"), list(DEFAULTS.values()))

    def test_each_key_is_accepted(self):
        for key in DEFAULTS:
            with self.subTest(key):
                p = self.run_snippet(SNIPPET, lambda c: c.update(files={key: "other/" + key + ".txt"}))
                self.assertEqual(p.returncode, 0, p.stderr)
                want = [("other/" + k + ".txt") if k == key else v for k, v in DEFAULTS.items()]
                self.assertEqual(p.stdout.strip().split("|"), want)

    def test_an_unknown_key_is_refused_by_name(self):
        self.refused(lambda c: c.update(files={"glossary": "g.md"}), "files.glossary")

    def test_files_must_be_a_map(self):
        self.refused(lambda c: c.update(files=["a"]), "files")

    def test_a_bad_value_is_refused_by_key(self):
        for bad in ("../x.md", "/x.md", "\\x.md", "C:x.md", "a/../x.md", "", " x.md", 3, ["x"]):
            with self.subTest(bad):
                self.refused(lambda c: c.update(files={"readme": bad}), "files.readme")

    def test_decisions_readme_defaults_and_does_not_need_the_other_index_keys(self):
        p = self.run_snippet(README_SNIPPET, lambda c: c.pop("decisions", None))
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "README.md"), p.stderr)
        p = self.run_snippet(README_SNIPPET, lambda c: c.update(decisions={"index": {"readme": "INDEX.md"}}))
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "INDEX.md"), p.stderr)

    def test_decisions_readme_is_validated(self):
        self.refused(lambda c: c.update(decisions={"index": {"readme": "a b.md"}}), "decisions.index.readme",
                     README_SNIPPET)


RENAMES = {
    "profiles.yaml": "view-list.yaml",
    "slots.yaml": "slot-list.yaml",
    "APPENDIX-A.md": "MAPPING.md",
    "INVENTORY.md": "CONTENTS.md",
    "README.md": "INDEX.md",
    "capability-record.yaml": "record.yaml",
    "adr-exemptions.yaml": "exempt.yaml",
}
KEYS = {"profiles.yaml": "profiles", "slots.yaml": "slots", "APPENDIX-A.md": "appendix", "INVENTORY.md": "inventory",
        "README.md": "readme", "capability-record.yaml": "record", "adr-exemptions.yaml": "adr_exemptions"}


def copy_example(dest: Path, rename: bool) -> Path:
    shutil.copytree(EXAMPLE, dest, ignore=shutil.ignore_patterns("expected", "__pycache__"))
    if rename:
        for old, new in RENAMES.items():
            (dest / old).rename(dest / new)
        for p in [*dest.glob("*.md"), *(dest / "views").glob("*.md")]:
            text = p.read_text(encoding="utf-8")
            for old, new in RENAMES.items():
                text = text.replace(old, new)
            p.write_text(text, encoding="utf-8", newline="")
        with open(dest / "arch-kit.yaml", "a", encoding="utf-8", newline="\n") as f:
            f.write("files:\n" + "".join(f"  {KEYS[o]}: {n}\n" for o, n in RENAMES.items()))
    return dest


def run_tool(root: Path, name: str, *args: str):
    env = dict(os.environ, PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    cmd = [sys.executable, "-m", "arch_kit", "--config", "arch-kit.yaml", name, *args]
    return subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, encoding="utf-8")


def unmap(text: str, tmp: Path) -> str:
    for old, new in RENAMES.items():
        text = text.replace(new, old)
    return text.replace(str(tmp), "TMP").replace("\\", "/")


class RenamedExample(unittest.TestCase):
    def test_the_example_with_every_content_file_renamed_gives_the_same_results(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        a = copy_example(tmp / "a", False)
        b = copy_example(tmp / "b", True)
        checks = [
            ("check_views", "--chart", "chart", "--values", "values.yaml", "--release", "larkspur",
             "--readiness", "READINESS.md", "--barred", "barred.txt"),
            ("check_views", "--allow-partial", "no chart in this test", "--barred", "barred.txt"),
            ("browser_facts", "--root", ".", "--out", "facts.json"),
            ("check_decision_indexes",),
        ]
        for name, *args in checks:
            with self.subTest(name, args=args[:1]):
                got = [run_tool(root, name, *args) for root in (a, b)]
                self.assertEqual(got[0].returncode, got[1].returncode, got[1].stdout + got[1].stderr)
                self.assertEqual(unmap(got[0].stdout, a), unmap(got[1].stdout, b))
                self.assertEqual(unmap(got[0].stderr, a), unmap(got[1].stderr, b))
        self.assertEqual((a / "facts.json").read_bytes(), (b / "facts.json").read_bytes())

    def test_a_renamed_file_that_is_not_declared_is_not_found(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        b = copy_example(tmp / "b", True)
        text = (b / "arch-kit.yaml").read_text(encoding="utf-8").replace("  slots: slot-list.yaml\n", "")
        (b / "arch-kit.yaml").write_text(text, encoding="utf-8", newline="\n")
        p = run_tool(b, "check_views", "--allow-partial", "no chart in this test", "--barred", "barred.txt")
        self.assertNotEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main()
