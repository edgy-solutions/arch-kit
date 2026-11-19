"""composed.py - the plumbing of a composed build: pinned trees, component declarations, fragments, relations.

A composing portal declares `files.composition`. Its build renders each group (its own records, then each
component) in a subprocess of its own, reading that group's declaration and loader at the pinned commit, and joins
the pieces into one page (render_html.assemble_composed). This module holds everything around that join:

- the `--checkout NAME=DIR` flags (one for every component and consumer the composition file lists) and their checks,
- each component's and consumer's declaration, read as data at its pin (`git show`), never imported,
- the temporary clone a component is rendered from, and its removal,
- the `--fragment` subprocess and the page ids it gets made unique with,
- the relations: "Consumed by" and "Consumes".

Errors about a component name its position (`components[1]`, `consumers[0]`), never its name, repository or lists.
Exit codes follow the tools': input errors exit 2 through project.die.
"""
from __future__ import annotations

import contextlib
import html
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

import yaml

import check_consumes
import declared
import project

DECISIONS_ONLY = "a composed portal is decisions-only for now"
RENDER = Path(__file__).resolve().parent / "render_html.py"


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def _bad(key, why):
    project.die(f"arch-kit: {project.PATH}: {key}: {why}")


def _die(tool, why):
    project.die(f"arch-kit: {tool}: {why}")


def own_name(tool: str) -> str:
    """The composing portal's own name: its `decisions.index.local_prefix`."""
    node = project.CONFIG.get("decisions")
    index = node.get("index") if isinstance(node, dict) else None
    local = index.get("local_prefix") if isinstance(index, dict) else None
    if not isinstance(local, str) or not re.fullmatch(declared.PREFIX_RE, local):
        _bad("decisions.index.local_prefix", "a composing portal is named by it, and it must be declared")
    return local


def require_decisions_mode(tool: str) -> None:
    if declared.portal_mode(tool) != "decisions":
        _bad("portal.mode", DECISIONS_ONLY)


def listed(comp) -> list:
    """(position key, entry) for every component, then every consumer, in file order."""
    return ([(f"components[{i}]", e) for i, e in enumerate(comp.components)]
            + [(f"consumers[{i}]", e) for i, e in enumerate(comp.consumers)])


# --- checkouts ----------------------------------------------------------------------------------------------------

def checkouts(tool: str, items: list[str], comp) -> dict:
    """Position key to the local clone's path, from the `--checkout NAME=DIR` flags. Exit 2 on any fault."""
    by_name = {e.name: (key, e) for key, e in listed(comp)}
    got: dict[str, Path] = {}
    for n, item in enumerate(items, 1):
        name, eq, rest = item.partition("=")
        if not eq or not name or not rest:
            _die(tool, f"--checkout argument {n} is not NAME=DIR")
        if name not in by_name:
            _die(tool, f"--checkout argument {n} names no component or consumer of the composition file")
        key = by_name[name][0]
        if key in got:
            _die(tool, f"{key}: --checkout is given twice")
        got[key] = Path(rest)
    for key, entry in listed(comp):
        if key not in got:
            _die(tool, f"{key}: --checkout is missing")
        code, _ = check_consumes._git(str(got[key]), "rev-parse", "--git-dir")
        if code != 0:
            _die(tool, f"{key}: its --checkout is not a git repository")
        code, _ = check_consumes._git(str(got[key]), "cat-file", "-e", entry.commit + "^{commit}")
        if code != 0:
            _die(tool, f"{key}: its pinned commit is not in its --checkout")
    return got


def add_checkout_flag(ap) -> None:
    ap.add_argument("--checkout", action="append", default=[], metavar="NAME=DIR",
                    help="a local clone of a component or consumer the composition file lists (one for each)")


def no_composition_checkouts(tool: str, items) -> None:
    if items:
        _die(tool, "--checkout needs files.composition: this declaration composes nothing")


# --- declarations at the pin --------------------------------------------------------------------------------------

def read_declaration(key: str, directory: Path, entry) -> dict:
    """The entry's declaration at its pin, parsed as data. Exit 2 when it is missing or invalid."""
    code, text = check_consumes._git(str(directory), "show", f"{entry.commit}:{entry.declaration}")
    if code != 0:
        _bad(key, "its declaration is not at the pin")
    try:
        config = yaml.safe_load(text)
    except yaml.YAMLError:
        _bad(key, "its declaration at the pin is not valid YAML")
    if not isinstance(config, dict) or config.get("kit") != 1:
        _bad(key, "its declaration at the pin is not a declaration (key 'kit' must be 1)")
    return config


def portal_of(config: dict) -> dict | None:
    """The portal map of a declaration, or None for `portal: none` (or no map)."""
    node = config.get("portal")
    return node if isinstance(node, dict) else None


def audience_of(config: dict) -> str | None:
    node = portal_of(config)
    return node.get("audience") if node else None


def refuse_component(key: str, config: dict) -> None:
    if config.get("portal") == "none":
        _bad(key, "portal: none: a project with no portal is a consumer, not a component")
    node = portal_of(config)
    if (node.get("mode", "full") if node else "full") != "decisions":
        _bad(key, "portal.mode: a full-mode component is not composed yet")
    files = config.get("files")
    if isinstance(files, dict) and declared.COMPOSITION_KEY in files:
        _bad(key, "files.composition: composition does not nest")


def refuse_consumer(key: str, config: dict) -> None:
    node = config.get("consumes")
    if not isinstance(node, list) or not node:
        _bad(key, "consumes: a consumer must declare consumes:")


def foreign_consumes(key: str, config: dict) -> list:
    """The `consumes:` entries of a declaration read as data, as declared.Consumes tuples (not validated further)."""
    node = config.get("consumes")
    if node is None:
        return []
    if not isinstance(node, list):
        _bad(key, "consumes: must be a list")
    out = []
    for j, item in enumerate(node):
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item.get(k)
                                                  for k in ("portal", "repo", "commit", "why")):
            _bad(key, f"consumes[{j}]: needs portal, repo, commit and why")
        records = item.get("records")
        if records is not None and (not isinstance(records, list) or not all(isinstance(r, str) for r in records)):
            _bad(key, f"consumes[{j}].records: must be a list of strings")
        out.append(declared.Consumes(item["portal"], item["repo"], item["commit"],
                                     tuple(records) if records else None, item["why"], item.get("drift", "warn")))
    return out


# --- the pinned tree ----------------------------------------------------------------------------------------------

def _force(func, path, _exc):
    """shutil.rmtree's onerror: git's object files are read-only on Windows."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


@contextlib.contextmanager
def pinned(key: str, directory: Path, commit: str):
    """A temporary local clone of `directory` at `commit`, removed on exit even after an error. DIR is never changed."""
    tmp = tempfile.mkdtemp(prefix="arch-kit-pin-")
    try:
        tree = Path(tmp) / "tree"
        for args in (["git", "clone", "--quiet", "--shared", "--no-checkout", str(directory), str(tree)],
                     ["git", "-C", str(tree), "checkout", "--quiet", "--detach", commit]):
            p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
            if p.returncode != 0:
                _bad(key, "cannot make a clone of its checkout at the pin")
        yield tree
    finally:
        shutil.rmtree(tmp, onerror=_force)


# --- one group, in its own process --------------------------------------------------------------------------------

class Group(NamedTuple):
    name: str
    key: str            # "portal", or the position key
    fragment: dict
    git_dir: str        # a repository holding the group's history
    commit: str         # the pin, or HEAD for the composing portal's own group
    decl: str           # the group's declaration, relative to the repository's top
    decisions: str      # the group's decisions directory, relative to the repository's top
    config: dict


def run_fragment(key: str, decl: Path, date: str, relabels=(), cwd=None) -> dict:
    """Render one group's pieces with the kit's own render_html in a new process. Its failure stops the build."""
    with tempfile.TemporaryDirectory(prefix="arch-kit-fragment-") as tmp:
        out = Path(tmp) / "fragment.json"
        cmd = [sys.executable, str(RENDER), "--fragment", str(out), "--date", date]
        for r in relabels:
            cmd += ["--relabel", str(r)]
        env = dict(os.environ, ARCH_KIT_CONFIG=str(Path(decl).resolve()), PYTHONIOENCODING="utf-8")
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, cwd=cwd)
        if p.returncode != 0:
            where = "portal: " if key == "portal" else f"{key}: "
            for line in p.stderr.splitlines():
                sys.stderr.write(where + line + "\n")
            raise SystemExit(p.returncode)
        return json.loads(out.read_text(encoding="utf-8"))


def prefixed(text: str, name: str) -> str:
    """Every id and every in-page href of a group's pieces made unique with the group's name. `#front` stays."""
    p = name + "--"
    text = re.sub(r'(?<![\w-])id="([^"]*)"', lambda m: f'id="{p}{m.group(1)}"', text)
    return re.sub(r'href="#([^"]*)"', lambda m: m.group(0) if m.group(1) == "front" else f'href="#{p}{m.group(1)}"',
                  text)


def top_relative(git_dir: str, path: Path) -> str:
    """`path` relative to the top of the repository at git_dir, with forward slashes."""
    code, top = check_consumes._git(git_dir, "rev-parse", "--show-toplevel")
    if code != 0:
        _bad("paths.repo", "is not a git repository")
    return Path(os.path.realpath(path)).relative_to(Path(os.path.realpath(top.strip()))).as_posix()


def decisions_rel(decl_rel: str, config: dict) -> str:
    import posixpath
    paths = config.get("paths")
    d = paths.get("decisions") if isinstance(paths, dict) else None
    if not isinstance(d, str):
        return "."
    return posixpath.normpath(posixpath.join(posixpath.dirname(decl_rel), d.replace("\\", "/")))


# --- relations ----------------------------------------------------------------------------------------------------

class Use(NamedTuple):
    """One `consumes:` entry, with the project that declared it."""
    who: str            # the declaring project's name
    key: str            # "portal", components[i] or consumers[i]
    open: bool          # its own portal is public: its why may be shown
    repo: str           # the declaring project's repository, from the composition file ("" for the portal itself)
    commit: str         # the declaring project's pin in the composition file
    entry: object       # declared.Consumes


class Collected(NamedTuple):
    own: str
    groups: list
    uses: list          # every Use that names the composing portal or a component, in order
    own_uses: dict      # group name to the Use list of that group's own consumes:
    notes: list


def collect(tool: str, items: list[str], date: str, relabels=()) -> Collected:
    """Check the composition, render every group in its own process, and gather the relations.

    Everything that can be refused is refused before any clone is made."""
    comp = declared.composition(tool)
    require_decisions_mode(tool)
    own = own_name(tool)
    dirs = checkouts(tool, items, comp)
    configs = {}
    for key, entry in listed(comp):
        configs[key] = read_declaration(key, dirs[key], entry)
        (refuse_component if key.startswith("components") else refuse_consumer)(key, configs[key])
    notes: list[str] = []
    groups: list[Group] = []
    with contextlib.ExitStack() as stack:
        # The composing portal's own group: its own declaration and working tree, no clone.
        repo = str(project.REPO)
        decl_rel = top_relative(repo, project.PATH)
        groups.append(Group(own, "portal", run_fragment("portal", project.PATH, date, relabels), repo, "HEAD",
                            decl_rel, top_relative(repo, project.DECISIONS), project.CONFIG))
        for i, entry in enumerate(comp.components):
            key = f"components[{i}]"
            tree = stack.enter_context(pinned(key, dirs[key], entry.commit))
            decl = tree / entry.declaration
            groups.append(Group(entry.name, key, run_fragment(key, decl, date, cwd=str(tree)), str(tree),
                                entry.commit, entry.declaration, decisions_rel(entry.declaration, configs[key]),
                                configs[key]))
        uses, own_uses = [], {}
        sources = [("portal", own, True, "", "", list(declared.consumes(tool)))]
        for key, entry in listed(comp):
            cfg = configs[key]
            sources.append((key, entry.name, audience_of(cfg) == "public", entry.repo, entry.commit,
                            foreign_consumes(key, cfg)))
        names = {g.name for g in groups}
        for key, name, public, repo, commit, entries in sources:
            mine = [Use(name, key, public, repo, commit, e) for e in entries]
            if name in names:
                own_uses[name] = mine
            if key != "portal":
                uses += [u for u in mine if u.entry.portal in names]
            for u in mine:
                if u.entry.records and any(r.startswith("capability:") for r in u.entry.records):
                    note = f"{key}: capability references are not composed yet"
                    if note not in notes:
                        notes.append(note)
    return Collected(own, groups, uses, own_uses, notes)


# --- blocks -------------------------------------------------------------------------------------------------------

def component_id(name: str) -> str:
    return f"{name}--component"


def _who(use: Use, groups: set) -> str:
    name = esc(use.who)
    return f'<a href="#{esc(component_id(use.who))}">{name}</a>' if use.who in groups else name


def consumed_by_li(use: Use, groups: set, only=None, state: str = "") -> str:
    """One entry of a "Consumed by" list. A consumer whose portal is private, or that has none, shows its name,
    repository and commit as text, and nothing else of it."""
    where = f' <span class="repo">{esc(use.repo)} at {esc(use.commit[:7])}</span>' if use.repo else ""
    why = f": {esc(use.entry.why)}" if use.open else ""
    extra = ""
    if only:
        extra = " (" + ", ".join(esc(r) for r in only) + ")"
    return f"<li>{_who(use, groups)}{why}{where}{extra}{state}</li>"


def consumed_by_block(lis: list[str]) -> str:
    if not lis:
        return ""
    return f'<div class="consumed-by" data-consumed-by><h2>Consumed by</h2><ul>{"".join(lis)}</ul></div>'


def consumes_li(use: Use, group_pages: dict, state: str = "") -> str:
    """One entry of a "Consumes" list: the consumed portal, the why, each record, and the pin."""
    e = use.entry
    name = esc(e.portal)
    if e.portal in group_pages:
        name = f'<a href="#{esc(component_id(e.portal))}">{name}</a>'
    refs = ""
    if e.records:
        shown = []
        for r in e.records:
            page = group_pages.get(e.portal, {}).get(r)
            shown.append(f'<a href="#{esc(page)}">{esc(r)}</a>' if page else esc(r))
        refs = " (" + ", ".join(shown) + ")"
    return f'<li>{name}{refs}: {esc(e.why)} <span class="repo">at {esc(e.commit[:7])}</span>{state}</li>'


def consumes_block(lis: list[str]) -> str:
    if not lis:
        return ""
    return f'<div class="consumes" data-consumes><h3>Consumes</h3><ul>{"".join(lis)}</ul></div>'


COMPOSED_CSS = """
.component{margin:1.5rem 0;padding-bottom:8px;border-top:2px solid var(--head)}
.component h2{margin-top:1rem}
.consumed-by,.consumes{margin:1rem 0;font-size:14px}
.consumed-by h2,.consumes h3{font-size:1rem;margin:.5rem 0}
.consumed-by .repo,.consumes .repo{color:var(--muted)}
.pin{display:inline-block;margin-left:6px;padding:0 8px;border:1px solid currentColor;border-radius:10px;font-size:12px;font-weight:600;white-space:nowrap}
.pin[data-pin="current"]{color:var(--m-fg)}
.pin[data-pin="changed"]{color:var(--a-fg)}
.pin[data-pin="superseded"],.pin[data-pin="pin-not-found"],.pin[data-pin="record-not-found"]{color:var(--p-fg)}
""".strip()
