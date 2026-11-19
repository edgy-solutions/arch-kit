"""Self-test: the flow record (docs/design/flows.md): the schema, the checks, both routes.

Each case builds a project in a temporary directory from examples/decisions-only, adds `files.flows` (or a loader that
defines `load_flows`), puts flows in it and loads them in a subprocess (the declaration is read once per process). An
accepted list exits 0; a refused one exits 2 and its message names the flow and the key. The full-mode capability
cases copy examples/minimal the same way, and need no diagram tool. The page is tested in test_flows_export.py.
"""
from __future__ import annotations

import copy
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_example_decisions import KIT, copy_example  # noqa: E402

LOADER_TAIL = '''

def load_flows(root):
    import yaml
    return yaml.safe_load((Path(root) / "records.yaml").read_text(encoding="utf-8"))["flows"]
'''

GOOD = [
    {"id": "FL-001", "from": "intake", "to": "depot", "carries": "parcel.v1", "via": "broker/parcels",
     "decided_by": ["ADR-0001"], "built": False},
    {"id": "FL-002", "from": "depot", "to": "ledger", "carries": "receipt.v1", "via": "/api/receipts",
     "decided_by": ["ADR-0002", "other:ADR-0007"], "built": True},
    {"id": "FL-003", "from": "ledger", "to": "intake", "carries": "ack.v1", "via": "queue/acks",
     "decided_by": [], "built": False},
]


def good() -> list:
    return copy.deepcopy(GOOD)


class Project:
    """A temporary project built from the decisions-only example, with flows by one route or the other."""

    def __init__(self, test: unittest.TestCase, route: str = "file"):
        self.tmp = Path(tempfile.mkdtemp())
        test.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = copy_example(self.tmp)
        self.route = route
        self.out = self.tmp / "export.html"
        decl = yaml.safe_load((self.root / "arch-kit.yaml").read_text(encoding="utf-8"))
        decl["decisions"]["index"]["foreign"] = [{"prefix": "other"}]
        if route == "file":
            decl["files"] = {"flows": "flows.yaml"}
        else:
            decl["loader"] = "flows_loader.py"
            text = (self.root / "kit_loader.py").read_text(encoding="utf-8")
            (self.root / "flows_loader.py").write_text(text + LOADER_TAIL, encoding="utf-8")
        self.decl = decl
        self.write_decl()

    def write_decl(self):
        (self.root / "arch-kit.yaml").write_text(yaml.safe_dump(self.decl, sort_keys=False), encoding="utf-8")

    def put(self, flows) -> None:
        name = "flows.yaml" if self.route == "file" else "records.yaml"
        (self.root / name).write_text(yaml.safe_dump({"flows": flows}, sort_keys=False), encoding="utf-8")

    def render(self):
        return load_in(self.root, "arch-kit.yaml")


LOAD = '''
import sys
sys.path.insert(0, {tools!r})
import flows
from data_exchange import InputError
try:
    print(len(flows.load("flows_test", ["ADR-0001", "ADR-0002", "ADR-0003"])))
except InputError as e:
    print(f"error: {{e}}", file=sys.stderr)
    sys.exit(2)
'''


def load_in(root: Path, decl: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, ARCH_KIT_CONFIG=str(root / decl), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-c", LOAD.format(tools=str(HERE))], cwd=root, env=env,
                          capture_output=True, text=True, encoding="utf-8")


def message(stderr: str) -> str:
    return [ln for ln in stderr.splitlines() if ln.strip()][-1]


def mut(fn):
    def apply(flows):
        fn(flows)
        return flows
    return apply


def dup_decided(flows):
    flows[0]["decided_by"] = ["ADR-0001", "ADR-0001"]


# (name, change to the good flows, text the message holds)
REFUSED = [
    ("duplicate id", mut(lambda f: f[1].update(id="FL-001")), "flows[1].id: flow id FL-001 is not unique"),
    ("from equals to", mut(lambda f: f[0].update(to="intake")), "flows[0].to: must differ from from"),
    ("duplicate flow", mut(lambda f: f[1].update(**{"from": "intake", "to": "depot", "carries": "parcel.v1",
                                                    "via": "broker/parcels"})),
     "flows[1].id: FL-002 repeats an earlier flow"),
    ("duplicate decided_by", mut(dup_decided), "flows[0].decided_by: ADR-0001 is listed twice"),
    ("unresolved decision", mut(lambda f: f[0].update(decided_by=["ADR-0099"])),
     "flows[0].decided_by[0]: ADR-0099 does not resolve"),
    ("undeclared foreign prefix", mut(lambda f: f[0].update(decided_by=["nowhere:ADR-0007"])),
     "flows[0].decided_by[0]: nowhere:ADR-0007 does not resolve"),
    ("capability in decisions mode", mut(lambda f: f[0].update(**{"from": "capability:ParcelIntake"})),
     "flows[0].from: capability: references need the capability record; this portal is decisions-only"),
    # the schema
    ("empty list", mut(lambda f: f.clear()), "flows: must list at least one flow"),
    ("unknown key", mut(lambda f: f[1].update(extra=1)), "flows.1.extra: unknown key"),
    ("bad id", mut(lambda f: f[0].update(id="FL-trace")), "flows.0.id: must be FL- then capitals, digits and hyphens"),
    ("id without a body", mut(lambda f: f[0].update(id="FL-")), "flows.0.id: must be FL- then capitals, digits and hyphens"),
    ("lower case id", mut(lambda f: f[0].update(id="fl-001")), "flows.0.id: must be FL- then capitals, digits and hyphens"),
    ("double hyphen in id", mut(lambda f: f[0].update(id="FL--A")), "flows.0.id: must be FL- then capitals, digits and hyphens"),
    ("trailing hyphen in id", mut(lambda f: f[0].update(id="FL-A-")), "flows.0.id: must be FL- then capitals, digits and hyphens"),
    ("underscore in id", mut(lambda f: f[0].update(id="FL-A_B")), "flows.0.id: must be FL- then capitals, digits and hyphens"),
    ("bad from", mut(lambda f: f[0].update(**{"from": "a b"})), "flows.0.from: must be a part name"),
    ("bad to", mut(lambda f: f[0].update(to="-x")), "flows.0.to: must be a part name"),
    ("space in carries", mut(lambda f: f[0].update(carries="a b")), "flows.0.carries: must be a non-empty string"),
    ("two lines in via", mut(lambda f: f[0].update(via="a\nb")), "flows.0.via: must be one non-empty line"),
    ("blank via", mut(lambda f: f[0].update(via=" ")), "flows.0.via: must be one non-empty line"),
    ("decided_by not a list", mut(lambda f: f[0].update(decided_by="ADR-0001")), "flows.0.decided_by:"),
    ("built not a boolean", mut(lambda f: f[0].update(built="yes")), "flows.0.built:"),
] + [(f"no {k}", mut(lambda f, k=k: f[2].pop(k)), f"flows.2.{k}: is required")
     for k in ("id", "from", "to", "carries", "via", "decided_by", "built")]


class Routes(unittest.TestCase):
    def test_the_file_route_is_accepted(self):
        p = Project(self)
        p.put(good())
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "3"), r.stdout + r.stderr)

    def test_the_loader_route_is_accepted(self):
        p = Project(self, "loader")
        p.put(good())
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_wider_ids_are_accepted(self):
        for fid in ("FL-001", "FL-1", "FL-TRACE", "FL-PT-PUBLISH"):
            with self.subTest(id=fid):
                p = Project(self)
                flows = good()
                flows[0]["id"] = fid
                p.put(flows)
                r = p.render()
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_both_declared_is_refused(self):
        p = Project(self)
        p.put(good())
        text = (p.root / "kit_loader.py").read_text(encoding="utf-8")
        (p.root / "flows_loader.py").write_text(text + LOADER_TAIL, encoding="utf-8")
        p.decl["loader"] = "flows_loader.py"
        p.write_decl()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("files.flows: is declared, and the loader also defines load_flows; use one route", r.stderr)

    def test_an_empty_decided_by_is_accepted(self):
        p = Project(self)
        flows = good()
        for f in flows:
            f["decided_by"] = []
        p.put(flows)
        r = p.render()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_file_that_is_not_a_map_with_flows_is_refused(self):
        p = Project(self)
        (p.root / "flows.yaml").write_text(yaml.safe_dump(good()), encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_a_top_level_unknown_key_is_refused(self):
        p = Project(self)
        (p.root / "flows.yaml").write_text(yaml.safe_dump({"flows": good(), "more": 1}), encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("more: unknown key", r.stderr)

    def test_a_loader_that_returns_a_map_is_refused(self):
        p = Project(self, "loader")
        (p.root / "records.yaml").write_text(yaml.safe_dump({"flows": {"a": 1}}), encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("load_flows must return a list", r.stderr)

    def test_the_error_names_the_file(self):
        p = Project(self)
        flows = good()
        flows[0]["id"] = "x"
        p.put(flows)
        r = p.render()
        self.assertRegex(message(r.stderr), r"^error: flows\.yaml: flows\.0\.id: ")


class Refusals(unittest.TestCase):
    def test_each_refusal(self):
        for name, change, text in REFUSED:
            for route in ("file", "loader"):
                with self.subTest(name, route=route):
                    p = Project(self, route)
                    p.put(change(good()))
                    r = p.render()
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertIn(text, message(r.stderr))
                    if route == "loader":
                        self.assertRegex(message(r.stderr), r"^error: load_flows: ")




class FullMode(unittest.TestCase):
    """A capability reference in a full-mode project (examples/minimal), loaded without a diagram tool."""

    def load(self, flows):
        flows[1]["decided_by"] = ["ADR-0002"]   # the minimal example declares no foreign prefix
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        root = tmp / "proj"
        shutil.copytree(KIT / "examples" / "minimal", root, ignore=shutil.ignore_patterns("expected", "__pycache__"))
        decl = yaml.safe_load((root / "arch-kit.yaml").read_text(encoding="utf-8"))
        decl["files"] = dict(decl.get("files") or {}, flows="flows.yaml")
        (root / "arch-kit.yaml").write_text(yaml.safe_dump(decl, sort_keys=False), encoding="utf-8")
        (root / "flows.yaml").write_text(yaml.safe_dump({"flows": flows}, sort_keys=False), encoding="utf-8")
        return load_in(root, "arch-kit.yaml")

    def test_a_capability_in_the_record_is_accepted(self):
        flows = good()
        flows[0]["from"] = "capability:ParcelIntake"
        flows[1]["to"] = "capability:ParcelRouting"
        r = self.load(flows)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "3")

    def test_a_capability_not_in_the_record_is_refused(self):
        flows = good()
        flows[1]["to"] = "capability:Nothing"
        r = self.load(flows)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("flows[1].to: Nothing is not a capability in the capability record", r.stderr)


if __name__ == "__main__":
    unittest.main()
