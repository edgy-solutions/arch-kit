"""Self-test: the prose page record: the schema, the checks, both routes and the citation scan.

Each case builds a project in a temporary directory from examples/pages, replaces its pages with the case's (a
directory of *.md files, or a loader that defines `load_pages`) and loads them in a subprocess (the declaration is
read once per process). An accepted list exits 0; a refused one exits 2 and its message names the page and the key,
or the line of a citation. The example declares components, a roadmap, flows and an alignment record, so every kind of
citation resolves; a case that drops one of them gets the "declares no" message.
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
sys.path.insert(0, str(HERE))
os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))

from test_example_pages import copy_example  # noqa: E402

import pages  # noqa: E402

LOADER_TAIL = '''

def load_pages(root):
    import yaml
    return yaml.safe_load((Path(root) / "records.yaml").read_text(encoding="utf-8"))["pages"]
'''

LOAD = '''
import sys
sys.path.insert(0, {tools!r})
import pages
from data_exchange import InputError
try:
    print({show})
except InputError as e:
    print(f"error: {{e}}", file=sys.stderr)
    sys.exit(2)
'''
LOCAL = '["ADR-0001", "ADR-0002", "ADR-0003"]'
COUNT = f'len(pages.load("pages_test", {LOCAL}))'
IDS = f'",".join(p["id"] for p in pages.load("pages_test", {LOCAL}))'


def page(pid: str, kind: str = "walkthrough", body: str = "A line.\n", **over) -> dict:
    p = {"id": pid, "title": f"Title {pid}", "kind": kind, "body": body}
    p.update(over)
    return p


GOOD = [
    page("ov", "overview", "See [[ADR-0001]] and [[CO-001|built]].\n"),
    page("w1", order=1, body="Step [[RM-002|accepted]] on [[FL-001|built]], also [[other:ADR-0007]].\n"),
    page("w2", order=2, body="Compare [[alignment:coverage]] and [[RM-003]] and [[FL-002]].\n"),
]


def good() -> list:
    return copy.deepcopy(GOOD)


class Project:
    """A temporary project built from the pages example, with the pages by one route or the other."""

    def __init__(self, test: unittest.TestCase, route: str = "dir", declare: bool = True):
        self.tmp = Path(tempfile.mkdtemp())
        test.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = copy_example(self.tmp)
        shutil.rmtree(self.root / "pages")
        self.route = route
        self.decl = yaml.safe_load((self.root / "arch-kit.yaml").read_text(encoding="utf-8"))
        del self.decl["files"]["pages"]
        if declare and route == "dir":
            self.decl["files"]["pages"] = "pages"
        elif declare:
            self.decl["loader"] = "pages_loader.py"
            text = (self.root / "kit_loader.py").read_text(encoding="utf-8")
            (self.root / "pages_loader.py").write_text(text + LOADER_TAIL, encoding="utf-8")
        self.write_decl()

    def write_decl(self):
        (self.root / "arch-kit.yaml").write_text(yaml.safe_dump(self.decl, sort_keys=False), encoding="utf-8")

    def put(self, items) -> None:
        if self.route == "dir":
            (self.root / "pages").mkdir(exist_ok=True)
            for p in items:
                front = {k: v for k, v in p.items() if k not in ("id", "body")}
                text = "---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n" + p.get("body", "")
                (self.root / "pages" / f"{p['id']}.md").write_text(text, encoding="utf-8", newline="\n")
        else:
            (self.root / "records.yaml").write_text(yaml.safe_dump({"pages": items}, sort_keys=False), encoding="utf-8")

    def raw(self, name: str, text: bytes | str) -> None:
        (self.root / "pages").mkdir(exist_ok=True)
        data = text.encode("utf-8") if isinstance(text, str) else text
        (self.root / "pages" / name).write_bytes(data)

    def render(self, show: str = COUNT):
        return load_in(self.root, "arch-kit.yaml", show)


def load_in(root: Path, decl: str, show: str = COUNT) -> subprocess.CompletedProcess:
    env = dict(os.environ, ARCH_KIT_CONFIG=str(root / decl), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-c", LOAD.format(tools=str(HERE), show=show)], cwd=root, env=env,
                          capture_output=True, text=True, encoding="utf-8")


def message(stderr: str) -> str:
    return [ln for ln in stderr.splitlines() if ln.strip()][-1]


def mut(fn):
    def apply(items):
        fn(items)
        return items
    return apply


def where(route: str, items: list, i: int, key: str) -> str:
    """The location the message gives for item i's key."""
    return f"pages/{items[i]['id']}.md: {key}" if route == "dir" else f"load_pages: pages[{i}].{key}"


ID_WHY = "must be lowercase letters, digits and hyphens"
TITLE_WHY = "must be one non-empty line"
BODY_WHY = "must not be empty"

# (name, change to the good pages, index, key, text the why holds)
SCHEMA_REFUSED = [
    ("bad kind", mut(lambda c: c[1].update(kind="essay")), 1, "kind", "is not one of"),
    ("order zero", mut(lambda c: c[1].update(order=0)), 1, "order", "minimum"),
    ("order a string", mut(lambda c: c[1].update(order="1")), 1, "order", "is not of type 'integer'"),
    ("order a fraction", mut(lambda c: c[1].update(order=1.5)), 1, "order", "is not of type 'integer'"),
    ("bad id, capitals", mut(lambda c: c[0].update(id="Ov")), 0, "id", ID_WHY),
    ("bad id, underscore", mut(lambda c: c[0].update(id="a_b")), 0, "id", ID_WHY),
    ("bad id, double hyphen", mut(lambda c: c[0].update(id="a--b")), 0, "id", ID_WHY),
    ("bad id, trailing hyphen", mut(lambda c: c[0].update(id="a-")), 0, "id", ID_WHY),
    ("two lines in title", mut(lambda c: c[1].update(title="a\nb")), 1, "title", TITLE_WHY),
    ("blank title", mut(lambda c: c[1].update(title="  ")), 1, "title", TITLE_WHY),
    ("empty title", mut(lambda c: c[1].update(title="")), 1, "title", TITLE_WHY),
    ("blank body", mut(lambda c: c[1].update(body=" \n\n")), 1, "body", BODY_WHY),
    ("empty body", mut(lambda c: c[1].update(body="")), 1, "body", BODY_WHY),
    ("no title", mut(lambda c: c[2].pop("title")), 2, "title", "is required"),
    ("no kind", mut(lambda c: c[2].pop("kind")), 2, "kind", "is required"),
]

# Route B only: the loader's dict can carry what a file cannot.
LOADER_REFUSED = [
    ("unknown key", mut(lambda c: c[1].update(extra=1)), 1, "extra", "unknown key"),
    ("no id", mut(lambda c: c[2].pop("id")), 2, "id", "is required"),
    ("no body", mut(lambda c: c[2].pop("body")), 2, "body", "is required"),
]


class Routes(unittest.TestCase):
    def test_the_directory_route_is_accepted(self):
        p = Project(self)
        p.put(good())
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "3"), r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")

    def test_the_loader_route_is_accepted(self):
        p = Project(self, "loader")
        p.put(good())
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "3"), r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")

    def test_both_declared_is_refused(self):
        p = Project(self)
        p.put(good())
        text = (p.root / "kit_loader.py").read_text(encoding="utf-8")
        (p.root / "pages_loader.py").write_text(text + LOADER_TAIL, encoding="utf-8")
        p.decl["loader"] = "pages_loader.py"
        p.write_decl()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("files.pages: is declared, and the loader also defines load_pages; use one route", r.stderr)

    def test_neither_declared_gives_nothing(self):
        p = Project(self, declare=False)
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "0"), r.stdout + r.stderr)

    def test_a_loader_without_load_pages_and_no_directory_gives_nothing(self):
        p = Project(self, declare=False)
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "0"), r.stdout + r.stderr)

    def test_files_are_read_in_sorted_order_and_the_stem_is_the_id(self):
        p = Project(self)
        p.put([page("zz"), page("aa"), page("mm", "overview")])
        r = p.render(IDS)
        self.assertEqual(r.stdout.strip(), "aa,mm,zz", r.stdout + r.stderr)

    def test_list_order_is_kept_on_the_loader_route(self):
        p = Project(self, "loader")
        p.put([page("zz"), page("aa")])
        r = p.render(IDS)
        self.assertEqual(r.stdout.strip(), "zz,aa", r.stdout + r.stderr)

    def test_only_md_files_directly_in_the_directory_are_read(self):
        p = Project(self)
        p.put(good())
        p.raw("notes.txt", "no front matter")
        (p.root / "pages" / "sub").mkdir()
        p.raw("sub/deep.md", "no front matter")
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "3"), r.stdout + r.stderr)

    def test_the_load_result_has_the_page_keys(self):
        p = Project(self)
        p.put(good())
        r = p.render('sorted(pages.load("pages_test", %s)[1])' % LOCAL)
        self.assertEqual(r.stdout.strip(), "['body', 'id', 'kind', 'order', 'title']", r.stdout + r.stderr)

    def test_a_missing_directory_is_refused(self):
        p = Project(self)
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(message(r.stderr), "error: pages: (record): is not a directory")

    def test_an_empty_directory_is_refused(self):
        p = Project(self)
        (p.root / "pages").mkdir()
        r = p.render()
        self.assertEqual(message(r.stderr), "error: pages: (record): must list at least one page")

    def test_an_empty_loader_list_is_refused(self):
        p = Project(self, "loader")
        p.put([])
        r = p.render()
        self.assertEqual(message(r.stderr), "error: load_pages: pages: must list at least one page")

    def test_a_loader_that_returns_a_map_is_refused(self):
        p = Project(self, "loader")
        (p.root / "records.yaml").write_text(yaml.safe_dump({"pages": {"a": 1}}), encoding="utf-8")
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("load_pages must return a list of pages", r.stderr)

    def test_a_loader_item_that_is_not_a_map_is_refused(self):
        p = Project(self, "loader")
        p.put(["text"])
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertRegex(message(r.stderr), r"^error: load_pages: pages\[0\]: ")


class FrontMatter(unittest.TestCase):
    def refused(self, text, why, name="x.md"):
        p = Project(self)
        p.raw(name, text)
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(message(r.stderr), f"error: pages/{name}: {why}")

    OPEN = "(record): must open with front matter between --- lines"

    def test_no_front_matter(self):
        self.refused("Just prose.\n", self.OPEN)

    def test_an_empty_file(self):
        self.refused("", self.OPEN)

    def test_front_matter_not_on_the_first_line(self):
        self.refused("\n---\ntitle: x\n---\nbody\n", self.OPEN)

    def test_front_matter_never_closed(self):
        self.refused("---\ntitle: x\nkind: overview\nbody text\n", self.OPEN)

    def test_a_closing_line_must_be_exactly_three_hyphens(self):
        self.refused("---\ntitle: x\nkind: overview\n----\nbody\n", self.OPEN)

    def test_bad_yaml(self):
        self.refused("---\ntitle: [a: b: c\n---\nbody\n", "(record): not valid YAML")

    def test_front_matter_that_is_not_a_map(self):
        self.refused("---\n- a\n- b\n---\nbody\n", "(record): front matter must be a map")

    def test_empty_front_matter_is_not_a_map(self):
        self.refused("---\n---\nbody\n", "(record): front matter must be a map")

    def test_an_unreadable_file(self):
        p = Project(self)
        p.raw("x.md", b"---\ntitle: \xff\xfe\n---\nbody\n")
        r = p.render()
        self.assertEqual(message(r.stderr), "error: pages/x.md: (record): cannot be read")

    def test_an_unknown_front_matter_key(self):
        for key in ("id", "body", "extra", "date"):
            with self.subTest(key=key):
                self.refused(f"---\ntitle: x\nkind: overview\n{key}: y\n---\nbody\n", f"{key}: unknown key")

    def test_a_missing_key_in_the_front_matter(self):
        self.refused("---\ntitle: x\n---\nbody\n", "kind: is required")

    def test_a_bad_file_name_is_a_bad_id(self):
        self.refused("---\ntitle: x\nkind: overview\n---\nbody\n", f"id: {ID_WHY}", name="Bad_Name.md")

    def test_the_first_bad_file_in_sorted_order_is_named(self):
        p = Project(self)
        p.raw("a.md", "no front matter")
        p.raw("b.md", "---\n- x\n---\n")
        r = p.render()
        self.assertEqual(message(r.stderr), f"error: pages/a.md: {self.OPEN}")

    def test_the_body_is_everything_after_the_closing_line(self):
        p = Project(self)
        p.raw("x.md", "---\ntitle: x\nkind: overview\n---\nfirst\n---\nsecond\n")
        r = p.render('repr(pages.load("pages_test", %s)[0]["body"])' % LOCAL)
        self.assertEqual(r.stdout.strip(), "'first\\n---\\nsecond\\n'", r.stdout + r.stderr)


class Schema(unittest.TestCase):
    def test_each_schema_refusal(self):
        for name, change, i, key, text in SCHEMA_REFUSED + LOADER_REFUSED:
            for route in ("dir", "loader"):
                if route == "dir" and (name, change, i, key, text) in LOADER_REFUSED:
                    continue
                with self.subTest(name, route=route):
                    p = Project(self, route)
                    items = change(good())
                    p.put(items)
                    r = p.render()
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    want = f"error: {where(route, items, i, key)}: "
                    self.assertTrue(message(r.stderr).startswith(want), message(r.stderr))
                    self.assertIn(text, message(r.stderr))

    def test_the_wider_ids_are_accepted(self):
        for pid in ("a", "a1", "1", "walk-through", "a-b-c", "0-1"):
            with self.subTest(id=pid):
                p = Project(self)
                p.put([page(pid)])
                r = p.render()
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Checks(unittest.TestCase):
    def test_two_overviews(self):
        for route in ("dir", "loader"):
            with self.subTest(route=route):
                p = Project(self, route)
                items = [page("one", "overview"), page("mid"), page("two", "overview")]
                p.put(items)
                r = p.render()
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                key = "pages/two.md: kind" if route == "dir" else "load_pages: pages[2].kind"
                self.assertEqual(message(r.stderr), f"error: {key}: only one page may be the overview; one already is")

    def test_no_overview_is_accepted(self):
        p = Project(self)
        p.put([page("w1")])
        self.assertEqual(p.render().returncode, 0)

    def test_a_duplicate_id_on_the_loader_route(self):
        p = Project(self, "loader")
        p.put([page("w1"), page("w2"), page("w1")])
        r = p.render()
        self.assertEqual(message(r.stderr), "error: load_pages: pages[2].id: page id w1 is not unique")

    def test_a_duplicate_id_comes_before_two_overviews(self):
        p = Project(self, "loader")
        p.put([page("a", "overview"), page("b", "overview"), page("a")])
        r = p.render()
        self.assertEqual(message(r.stderr), "error: load_pages: pages[2].id: page id a is not unique")

    def test_two_overviews_come_before_a_bad_citation(self):
        p = Project(self)
        p.put([page("a", "overview", "[[ADR-0099]]\n"), page("b", "overview")])
        r = p.render()
        self.assertIn("pages/b.md: kind: only one page may be the overview; a already is", r.stderr)

    def test_a_schema_error_comes_before_the_checks(self):
        p = Project(self, "loader")
        p.put([page("a", "overview"), page("b", "overview"), page("c", title="")])
        r = p.render()
        self.assertEqual(message(r.stderr), f"error: load_pages: pages[2].title: {TITLE_WHY}")


def body_at_line_3(cite: str) -> str:
    return f"First line.\n\nSee {cite} here.\n"


# (name, citation, text of the refusal)
CITATIONS = [
    ("an unknown decision", "[[ADR-0099]]", "[[ADR-0099]] does not resolve"),
    ("an undeclared foreign prefix", "[[nowhere:ADR-0001]]", "[[nowhere:ADR-0001]] does not resolve"),
    ("a foreign prefix with a bad id", "[[other:nope]]", "[[other:nope]] does not resolve"),
    ("an unknown component", "[[CO-099]]", "[[CO-099]] does not resolve"),
    ("an unknown increment", "[[RM-099]]", "[[RM-099]] does not resolve"),
    ("an unknown flow", "[[FL-099]]", "[[FL-099]] does not resolve"),
    ("an unknown alignment record", "[[alignment:nope]]", "[[alignment:nope]] does not resolve"),
    ("an unknown ident with a status", "[[CO-099|built]]", "[[CO-099]] does not resolve"),
    ("a lower case component id is a decision id", "[[co-001]]", "[[co-001]] does not resolve"),
    ("a status that is not one", "[[CO-001|done]]",
     "[[CO-001|done]]: done is not a status (measured, built, accepted, proposed)"),
    ("a status that is not one, on an increment", "[[RM-001|Built]]",
     "[[RM-001|Built]]: Built is not a status (measured, built, accepted, proposed)"),
    ("a status that is not one, on a flow", "[[FL-001|done]]",
     "[[FL-001|done]]: done is not a status (measured, built, accepted, proposed)"),
    ("a status that is not one, on a decision", "[[ADR-0001|done]]",
     "[[ADR-0001|done]]: done is not a status (measured, built, accepted, proposed)"),
    ("another status on a flow", "[[FL-001|accepted]]", "[[FL-001|accepted]]: a flow is built or not; only |built applies"),
    ("measured on a flow", "[[FL-002|measured]]", "[[FL-002|measured]]: a flow is built or not; only |built applies"),
    ("built on a flow that is not built", "[[FL-002|built]]", "[[FL-002|built]] says built; FL-002 is not built"),
    ("a status on a local decision", "[[ADR-0001|accepted]]",
     "[[ADR-0001|accepted]]: only components, increments and flows carry a status"),
    ("a status on a foreign decision", "[[other:ADR-0007|accepted]]",
     "[[other:ADR-0007|accepted]]: only components, increments and flows carry a status"),
    ("a status on an alignment record", "[[alignment:coverage|built]]",
     "[[alignment:coverage|built]]: only components, increments and flows carry a status"),
    ("a component whose status differs", "[[CO-001|accepted]]", "[[CO-001|accepted]] says accepted; CO-001 is built"),
    ("a proposed component called built", "[[CO-003|built]]", "[[CO-003|built]] says built; CO-003 is proposed"),
    ("an increment whose status differs", "[[RM-003|accepted]]", "[[RM-003|accepted]] says accepted; RM-003 is proposed"),
    ("an accepted increment called measured", "[[RM-002|measured]]",
     "[[RM-002|measured]] says measured; RM-002 is accepted"),
]

# (name, citation, files key to drop, text)
UNDECLARED = [
    ("components", "[[CO-001]]", "components", "[[CO-001]] does not resolve: the project declares no components"),
    ("increments", "[[RM-001]]", "roadmap", "[[RM-001]] does not resolve: the project declares no increments"),
    ("flows", "[[FL-001]]", "flows", "[[FL-001]] does not resolve: the project declares no flows"),
    ("alignment records", "[[alignment:coverage]]", "alignment",
     "[[alignment:coverage]] does not resolve: the project declares no alignment records"),
    ("components, with a status", "[[CO-001|built]]", "components",
     "[[CO-001]] does not resolve: the project declares no components"),
]


class Citations(unittest.TestCase):
    def line(self, route: str, items: list, i: int, n: int) -> str:
        """Where a citation on body line n of page i is named, and the line number the message gives."""
        offset = len(items[i]) if route == "dir" else 0
        place = f"pages/{items[i]['id']}.md" if route == "dir" else f"load_pages: pages[{i}].body"
        return f"error: {place}: line {n + offset}: "

    def test_each_citation_refusal(self):
        for name, cite, text in CITATIONS:
            for route in ("dir", "loader"):
                with self.subTest(name, route=route):
                    p = Project(self, route)
                    items = good()
                    items[1]["body"] = body_at_line_3(cite)
                    p.put(items)
                    r = p.render()
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertEqual(message(r.stderr), self.line(route, items, 1, 3) + text)

    def test_the_line_counts_the_front_matter_on_the_directory_route(self):
        p = Project(self)
        p.raw("x.md", "---\ntitle: x\nkind: overview\norder: 1\n---\n[[ADR-0001]]\n[[ADR-0099]]\n")
        r = p.render()
        self.assertEqual(message(r.stderr), "error: pages/x.md: line 7: [[ADR-0099]] does not resolve")

    def test_the_line_is_the_body_line_on_the_loader_route(self):
        p = Project(self, "loader")
        p.put([page("x", "overview", "[[ADR-0001]]\n[[ADR-0099]]\n")])
        r = p.render()
        self.assertEqual(message(r.stderr), "error: load_pages: pages[0].body: line 2: [[ADR-0099]] does not resolve")

    def test_the_first_bad_citation_is_named(self):
        p = Project(self)
        p.put([page("a", "overview", "ok [[ADR-0001]]\n[[CO-099]] [[ADR-0099]]\n"), page("b", body="[[RM-099]]\n")])
        r = p.render()
        self.assertEqual(message(r.stderr), "error: pages/a.md: line 6: [[CO-099]] does not resolve")

    def test_each_undeclared_record_set(self):
        for name, cite, key, text in UNDECLARED:
            for route in ("dir", "loader"):
                with self.subTest(name, route=route):
                    p = Project(self, route)
                    del p.decl["files"][key]
                    p.write_decl()
                    items = [page("a", "overview", body_at_line_3(cite))]
                    p.put(items)
                    r = p.render()
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertEqual(message(r.stderr), self.line(route, items, 0, 3) + text)

    def test_a_decision_has_no_declares_no_variant(self):
        p = Project(self)
        p.put([page("a", "overview", "[[ADR-0099]]\n")])
        r = p.render()
        self.assertNotIn("declares no", r.stderr)

    def test_a_record_set_is_loaded_only_when_a_citation_needs_it(self):
        p = Project(self)
        p.put([page("a", "overview", "[[ADR-0001]] [[other:ADR-0007]]\n")])
        (p.root / "components.yaml").write_text("not: [valid", encoding="utf-8")
        (p.root / "roadmap.yaml").write_text("not: [valid", encoding="utf-8")
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "1"), r.stdout + r.stderr)
        p.put([page("a", "overview", "[[CO-001]]\n")])
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("components.yaml: (record): not valid YAML", r.stderr)

    def test_a_record_set_is_loaded_once(self):
        p = Project(self)
        p.put([page("a", "overview", "[[CO-001]] [[CO-002]]\n"), page("b", body="[[CO-003]]\n")])
        code = ("import components\norig = components.load\ncalls = []\n"
                "components.load = lambda *a: calls.append(1) or orig(*a)\n"
                f"pages.load('pages_test', {LOCAL})\nprint(len(calls))")
        env = dict(os.environ, ARCH_KIT_CONFIG=str(p.root / "arch-kit.yaml"), PYTHONDONTWRITEBYTECODE="1")
        script = f"import sys\nsys.path.insert(0, {str(HERE)!r})\nimport pages\n" + code
        out = subprocess.run([sys.executable, "-c", script], cwd=p.root, env=env, capture_output=True, text=True)
        self.assertEqual((out.returncode, out.stdout.strip()), (0, "1"), out.stdout + out.stderr)

    def test_every_status_on_a_matching_record_is_accepted(self):
        p = Project(self)
        p.put([page("a", "overview", "[[CO-001|built]] [[CO-002|accepted]] [[CO-003|proposed]] [[RM-001|built]] "
                                     "[[RM-002|accepted]] [[RM-003|proposed]] [[FL-001|built]] [[FL-002]]\n")])
        r = p.render()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "1"), r.stdout + r.stderr)

    def test_citations_in_code_are_ignored_by_the_check(self):
        body = ("Inline `[[ADR-0099]]` and ``[[CO-099|x]]`` and `a` [[ADR-0001]].\n\n"
                "```\n[[RM-099]]\n```\n\n~~~python\n[[FL-099]]\n~~~~\n\n   ```\n[[alignment:nope]]\n   ```\n")
        for route in ("dir", "loader"):
            with self.subTest(route=route):
                p = Project(self, route)
                p.put([page("a", "overview", body)])
                r = p.render()
                self.assertEqual((r.returncode, r.stdout.strip()), (0, "1"), r.stdout + r.stderr)

    def test_a_citation_after_a_fence_closes_is_checked(self):
        p = Project(self, "loader")
        p.put([page("a", "overview", "```\n[[ADR-0099]]\n```\n[[RM-099]]\n")])
        r = p.render()
        self.assertEqual(message(r.stderr), "error: load_pages: pages[0].body: line 4: [[RM-099]] does not resolve")

    def test_a_citation_after_an_inline_span_on_the_same_line_is_checked(self):
        p = Project(self, "loader")
        p.put([page("a", "overview", "`[[ADR-0001]]` then [[ADR-0099]]\n")])
        r = p.render()
        self.assertEqual(message(r.stderr), "error: load_pages: pages[0].body: line 1: [[ADR-0099]] does not resolve")


class OutsideElements(unittest.TestCase):
    def test_an_outside_system_resolves_by_form_and_loads_nothing(self):
        for route in ("dir", "loader"):
            with self.subTest(route=route):
                p = Project(self, route)
                for key in ("components", "roadmap", "flows", "alignment"):
                    del p.decl["files"][key]
                p.write_decl()
                p.put([page("a", "overview", "See [[XE-LEDGER]] and [[XE-LEDGER-API]].\n")])
                for name in ("components.yaml", "roadmap.yaml", "flows.yaml"):
                    (p.root / name).write_text("not: [valid", encoding="utf-8")
                r = p.render()
                self.assertEqual((r.returncode, r.stdout.strip()), (0, "1"), r.stdout + r.stderr)

    def test_a_status_on_an_outside_system_is_refused(self):
        p = Project(self)
        p.put([page("a", "overview", body_at_line_3("[[XE-LEDGER|built]]"))])
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(message(r.stderr), "error: pages/a.md: line 7: [[XE-LEDGER|built]]: "
                         "only components, increments and flows carry a status")

    def test_a_malformed_outside_id_does_not_resolve(self):
        for cite in ("[[XE-ledger]]", "[[XE-LEDGER-]]"):
            with self.subTest(cite):
                p = Project(self)
                p.put([page("a", "overview", body_at_line_3(cite))])
                r = p.render()
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertTrue(message(r.stderr).endswith(f"{cite} does not resolve"), r.stderr)

    def test_href_receives_the_element_kind_and_a_link_is_made(self):
        seen = []

        def href(kind, ident):
            seen.append((kind, ident))
            return "#ledger"
        sections, _ = pages.render([page("a", "overview", "See [[XE-LEDGER]].\n")], href)
        self.assertEqual(seen, [("element", "XE-LEDGER")])
        self.assertIn('<a class="cite" href="#ledger" data-cite="XE-LEDGER">XE-LEDGER</a>', sections[0])

    def test_no_href_gives_code(self):
        sections, _ = pages.render([page("a", "overview", "See [[XE-LEDGER]].\n")], lambda kind, ident: None)
        self.assertIn('<code class="cite" data-cite="XE-LEDGER">XE-LEDGER</code>', sections[0])


class Scan(unittest.TestCase):
    """_citations(): what counts as a citation, and where."""

    def test_positions_and_parts(self):
        self.assertEqual(pages._citations("ab [[ADR-0001]] c\n[[CO-001|built]]"),
                         [(1, 3, 15, "ADR-0001", None), (2, 0, 16, "CO-001", "built")])

    def test_not_a_citation(self):
        for text in ("[[ ADR-0001]]", "[[]]", "[ADR-0001]", "[[a b]]", "[[a|]]", "[[a[b]]"):
            with self.subTest(text=text):
                self.assertEqual(pages._citations(text), [])

    def test_code_spans_keep_positions(self):
        self.assertEqual(pages._citations("`[[X]]` [[Y]]"), [(1, 8, 13, "Y", None)])
        self.assertEqual(pages._citations("``a ` [[X]]`` [[Y]]"), [(1, 14, 19, "Y", None)])

    def test_an_unclosed_span_is_not_code(self):
        self.assertEqual(pages._citations("`[[X]]"), [(1, 1, 6, "X", None)])

    def test_fences(self):
        self.assertEqual(pages._citations("```\n[[X]]\n```\n[[Y]]"), [(4, 0, 5, "Y", None)])
        self.assertEqual(pages._citations("~~~\n[[X]]\n```\n[[Z]]\n~~~\n[[Y]]"), [(6, 0, 5, "Y", None)])
        self.assertEqual(pages._citations("```\n[[X]]\n~~~\n[[Z]]"), [])
        self.assertEqual(pages._citations("````\n[[X]]\n```\n[[Z]]\n````\n[[Y]]"), [(6, 0, 5, "Y", None)])
        self.assertEqual(pages._citations("```\n[[X]]"), [])

    def test_four_spaces_do_not_open_a_fence(self):
        self.assertEqual(pages._citations("    ```\n[[X]]"), [(2, 0, 5, "X", None)])

    def test_an_indented_code_block_is_not_special(self):
        self.assertEqual(pages._citations("para\n\n    [[X]]\n"), [(3, 4, 9, "X", None)])


class Declaration(unittest.TestCase):
    def test_an_unknown_files_key_still_lists_pages(self):
        p = Project(self)
        p.decl["files"]["nonsense"] = "x"
        p.write_decl()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("pages", r.stderr)

    def test_an_absolute_pages_path_is_refused(self):
        p = Project(self)
        p.decl["files"]["pages"] = "/pages"
        p.write_decl()
        r = p.render()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("files.pages: must be a plain relative path with no '..'", r.stderr)

    def test_a_pages_path_with_dotdot_is_refused(self):
        p = Project(self)
        p.decl["files"]["pages"] = "../pages"
        p.write_decl()
        r = p.render()
        self.assertIn("files.pages: must be a plain relative path with no '..'", r.stderr)

    def test_load_pages_is_an_optional_seam_name(self):
        import seam
        self.assertIn("load_pages", seam.OPTIONAL_NAMES)
        self.assertNotIn("load_pages", seam.NAMES)


if __name__ == "__main__":
    unittest.main()
