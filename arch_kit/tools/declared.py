"""declared.py - the phases, statuses and views the consumer declares, checked against the kit's rule vocabulary.

The kit fixes a vocabulary of rules; the declaration (`phases`, `floor`, `statuses`, `views`, `export.browser`)
says which phases exist, in what order, and which rules put a capability in each. This module reads and
checks the declaration. It evaluates no rule: capability_phases.phase_of does, because the rules read a record.

Rules, each true when:
    measured          the record's `measured` list is non-empty
    built             the record's `built` list is non-empty
    {status: WORD}    a cited decision's status line starts with that declared status's `lead`
    still-open        the capability has a `still_open` citation
    pending           the capability has a `pending` entry
    rows              the record's `rows` list is non-empty

Badge keys are the palette keys the CSS already defines: m, b, a, p, r.

A bad declaration exits 2 through project.die with one line naming the declaration file and the key.
"""
from __future__ import annotations

import re
from typing import NamedTuple

import project

PLAIN_RULES = ("measured", "built", "still-open", "pending", "rows")
BADGES = ("m", "b", "a", "p", "r")
VIEW_KEYS = ("required", "required_dodaf", "homes", "capability_links")


class Phase(NamedTuple):
    name: str
    when: tuple
    badge: str


class Status(NamedTuple):
    word: str
    lead: str
    in_force: bool
    sources_check: bool


def _bad(key, why):
    project.die(f"arch-kit: {project.PATH}: {key}: {why}")


def _list(node, key):
    if not isinstance(node, list) or not node:
        _bad(key, "must be a non-empty list")
    return node


_CACHE: dict[str, object] = {}


def statuses(tool: str) -> list[Status]:
    """The declared decision statuses, in order."""
    if "statuses" not in _CACHE:
        out = []
        for i, item in enumerate(_list(project.need("statuses", tool), "statuses")):
            key = f"statuses[{i}]"
            if not isinstance(item, dict) or not isinstance(item.get("word"), str) or \
                    not isinstance(item.get("lead"), str) or not item["word"] or not item["lead"]:
                _bad(key, "needs a word and a lead, both non-empty strings")
            for k in item:
                if k not in ("word", "lead", "in_force", "sources_check"):
                    _bad(key, f"unknown key {k!r}")
            flags = [item.get(k, False) for k in ("in_force", "sources_check")]
            if not all(isinstance(f, bool) for f in flags):
                _bad(key, "in_force and sources_check must be true or false")
            if any(s.word == item["word"] or s.lead == item["lead"] for s in out):
                _bad(key, f"duplicate word or lead {item['word']!r}")
            out.append(Status(item["word"], item["lead"], *flags))
        _CACHE["statuses"] = out
    return _CACHE["statuses"]


def lead_of(lead: str | None, tool: str) -> Status | None:
    """The declared status a status line's lead (lowercased) starts with, or None."""
    return next((s for s in statuses(tool) if (lead or "").startswith(s.lead)), None)


def phases(tool: str) -> list[Phase]:
    """The declared phases, strongest first."""
    if "phases" not in _CACHE:
        out = []
        for i, item in enumerate(_list(project.need("phases", tool), "phases")):
            key = f"phases[{i}]"
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
                _bad(key, "needs a name")
            name = item["name"]
            for k in item:
                if k not in ("name", "when", "badge"):
                    _bad(key, f"unknown key {k!r}")
            if any(p.name == name for p in out):
                _bad(key, f"duplicate phase name {name!r}")
            if item.get("badge") not in BADGES:
                _bad(key, f"badge {item.get('badge')!r} is not one of {', '.join(BADGES)}")
            when = []
            for rule in _list(item.get("when"), key + ".when"):
                if isinstance(rule, dict) and set(rule) == {"status"}:
                    if rule["status"] not in [s.word for s in statuses(tool)]:
                        _bad(key + ".when", f"unknown status word {rule['status']!r}")
                    when.append(("status", rule["status"]))
                elif isinstance(rule, str) and rule in PLAIN_RULES:
                    when.append((rule, None))
                else:
                    _bad(key + ".when", f"unknown rule {rule!r}")
            out.append(Phase(name, tuple(when), item["badge"]))
        floor = project.need("floor", tool)
        if floor not in [p.name for p in out]:
            _bad("floor", f"{floor!r} is not a declared phase name")
        _CACHE["phases"] = out
        _CACHE["floor"] = floor
    return _CACHE["phases"]


def phase_names(tool: str) -> list[str]:
    return [p.name for p in phases(tool)]


def floor_phases(tool: str) -> tuple[str, ...]:
    """The floor phase and every phase above it: the phases that count as built."""
    names = phase_names(tool)
    return tuple(names[:names.index(_CACHE["floor"]) + 1])


def floor_name(tool: str) -> str:
    phases(tool)
    return _CACHE["floor"]


def slug(name: str) -> str:
    return name.replace(" ", "-")


def group_slug(tool: str) -> str:
    """The declared group column, lowercased, with spaces as hyphens: the stem of the group-start CSS class."""
    return str(project.need("labels.group.column", tool)).lower().replace(" ", "-")


def views(tool: str) -> dict:
    """The declared view ids: required, required_dodaf, homes, capability_links."""
    if "views" not in _CACHE:
        node = project.need("views", tool)
        if not isinstance(node, dict):
            _bad("views", "must be a map")
        no_model = model_none(tool)
        for k in VIEW_KEYS:
            if k == "capability_links" and no_model and k not in node:
                continue
            project.need("views." + k, tool)
        for k in ("required", "required_dodaf", "capability_links"):
            if k not in node:
                continue
            value = node[k]
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                _bad("views." + k, "must be a list of view ids")
        homes = node["homes"]
        if not isinstance(homes, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in homes.items()):
            _bad("views.homes", "must map a generated-section name to a view id")
        if no_model and node.get("capability_links"):
            _bad("views.capability_links", "model: none is declared; there are no capability pages to link")
        if no_model:
            node = {**node, "capability_links": []}
        _CACHE["views"] = node
    return _CACHE["views"]


def home(name: str, tool: str) -> str:
    """The view that holds the generated section `name` (views.homes)."""
    return views(tool)["homes"].get(name) or project.need("views.homes." + name, tool)


HOSTINGS = ("ci-artifact", "static-site", "none")
AUDIENCES = ("public", "private")
MODES = ("full", "decisions")


def _none_pairing(tool: str) -> None:
    """`chart: none` and `model: none` are declared together. Either alone exits 2 and says so."""
    if "none_pairing" in _CACHE:
        return
    chart_value, model_value = project.CONFIG.get("chart"), project.CONFIG.get("model")
    if chart_value is not None and chart_value != "none":
        _bad("chart", f"{chart_value!r} is not allowed; the only value is none")
    if model_value is not None and model_value != "none" and not isinstance(model_value, dict):
        _bad("model", "must be a map, or none")
    if chart_value == "none" and model_value != "none":
        _bad("chart", "chart: none is declared without model: none; the two go together in this version")
    if model_value == "none" and chart_value != "none":
        _bad("model", "model: none is declared without chart: none; the two go together in this version")
    _CACHE["none_pairing"] = True


def chart_none(tool: str) -> bool:
    """True when `chart: none` is declared: a full-mode project with no chart, values or release."""
    _none_pairing(tool)
    return project.CONFIG.get("chart") == "none"


def model_none(tool: str) -> bool:
    """True when `model: none` is declared: a full-mode project with no SysML model."""
    _none_pairing(tool)
    return project.CONFIG.get("model") == "none"


PAGE_ID = re.compile(r"[a-z0-9][a-z0-9-]*")


def pages(tool: str) -> list[dict]:
    """The extra pages (`pages:`): a list of {id, title, file}, in order. Empty when absent. Exits 2 naming the key."""
    if "pages" not in _CACHE:
        node = project.CONFIG.get("pages")
        out: list[dict] = []
        if node is not None:
            if not isinstance(node, list) or not node:
                _bad("pages", "must be a non-empty list")
            seen: set = set()
            for i, item in enumerate(node):
                key = f"pages[{i}]"
                if not isinstance(item, dict) or set(item) != {"id", "title", "file"}:
                    _bad(key, "must be a map of id, title and file")
                pid, title = item["id"], item["title"]
                if not isinstance(pid, str) or not PAGE_ID.fullmatch(pid):
                    _bad(key + ".id", "must be a slug of lowercase letters, digits and hyphens")
                if pid in seen:
                    _bad(key + ".id", f"{pid} is used twice")
                if pid in ("front", "declarations") or pid.startswith(("view-", "cap-", "decision-")):
                    _bad(key + ".id", f"{pid} collides with a page the kit writes")
                seen.add(pid)
                if not isinstance(title, str) or not title.strip() or title != title.strip() or "\n" in title:
                    _bad(key + ".title", "must be one line of text")
                out.append({"id": pid, "title": title, "file": _relative(item["file"], key + ".file")})
        _CACHE["pages"] = out
    return _CACHE["pages"]


def portal_none(tool: str) -> bool:
    """True when the declaration's `portal` is the scalar `none`: a project with no portal of its own, which still
    declares what it consumes. Distinct from the map form's `portal.hosting: none`."""
    return project.CONFIG.get("portal") == "none"


def _portal(field: str, allowed: tuple, tool: str) -> str:
    if portal_none(tool):
        if field == "hosting":
            return "none"
        project.die(f"arch-kit: {project.PATH}: portal: portal: none has no audience")
    key = "portal." + field
    if not isinstance(project.need("portal", tool), dict):
        _bad("portal", "must be a map")
    value = project.need(key, tool)
    if value not in allowed:
        _bad(key, f"{value!r} is not one of {', '.join(allowed)}")
    return value


def portal_hosting(tool: str) -> str:
    """Where the portal is served: ci-artifact, static-site or none. Declared and validated only; the Action reads it."""
    return _portal("hosting", HOSTINGS, tool)


def portal_audience(tool: str) -> str:
    """Who may read the portal: public or private. A public audience makes check_export and render_html require lists."""
    return _portal("audience", AUDIENCES, tool)


def portal_mode(tool: str) -> str:
    """What the portal holds: `full` (the default when `portal.mode` is absent) or `decisions`, the decision records,
    their index and the roadmap only. Unlike hosting and audience the key is optional."""
    node = project.CONFIG.get("portal")
    if node is None or portal_none(tool):
        return "full"
    if not isinstance(node, dict):
        _bad("portal", "must be a map")
    mode = node.get("mode", "full")
    if mode not in MODES:
        _bad("portal.mode", f"{mode!r} is not one of {', '.join(MODES)}")
    return mode


def composed_in(tool: str) -> str | None:
    """`portal.composed_in`: the name of the portal this project is composed into, or None. Optional.

    A standalone decisions-mode front page names it. The value is a project name (PREFIX_RE)."""
    node = project.CONFIG.get("portal")
    if node is None:
        return None
    if portal_none(tool):
        _bad("portal.composed_in", "portal: none has no portal to be composed")
    if not isinstance(node, dict) or "composed_in" not in node:
        return None
    return _prefix(node["composed_in"], "portal.composed_in")


def require_public_lists(tool: str, **given: bool) -> None:
    """Exit 2 when the audience is public and a list the tool needs is not given. `given` maps a flag to whether it was."""
    portal_hosting(tool)
    if portal_audience(tool) != "public":
        return
    names = {"relabel": "a relabel list (--relabel)", "barred": "a barred list (--barred)"}
    for flag, present in given.items():
        if not present:
            project.die(f"error: the portal's audience is public: {tool} needs {names[flag]}")


INDEX_KEYS = ("register", "readme", "register_homes", "indexed", "local_prefix", "foreign", "register_id")
INDEX_OPTIONAL = ("foreign", "register_id")
PREFIX_RE = r"[a-z][a-z0-9-]*"


class Foreign(NamedTuple):
    prefix: str
    pin_check: str | None
    commit: str | None = None   # set when the prefix comes from the composition file: the full commit it pins


class DecisionIndex(NamedTuple):
    register: str | None     # None when `decisions.index.register` is `none`
    readme: str
    register_homes: tuple
    indexed: tuple
    local_prefix: str
    foreign: tuple


FILE_DEFAULTS = {
    "profiles": "profiles.yaml",
    "slots": "slots.yaml",
    "appendix": "APPENDIX-A.md",
    "inventory": "INVENTORY.md",
    "readme": "README.md",
    "record": "capability-record.yaml",
    "adr_exemptions": "adr-exemptions.yaml",
    "annotation_exceptions": "annotation-exceptions.yaml",
}


ALIGNMENT_KEY = "alignment"  # a `files` key with no default: a directory of alignment records, absent unless declared
COMPOSITION_KEY = "composition"  # a `files` key with no default: the composition file, relative to the declaration
FLOWS_KEY = "flows"  # a `files` key with no default: one YAML file of flow records, absent unless declared
COMPONENTS_KEY = "components"  # a `files` key with no default: one YAML file of component records, absent unless declared
ROADMAP_KEY = "roadmap"  # a `files` key with no default: one YAML file of roadmap increments, absent unless declared
OPTIONAL_FILE_KEYS = (ALIGNMENT_KEY, COMPOSITION_KEY, FLOWS_KEY, COMPONENTS_KEY, ROADMAP_KEY)


def _relative(value, key):
    """Exit 2 unless value is a plain relative path with no '..', no leading slash and no drive letter."""
    import re
    if not isinstance(value, str) or not value.strip() or value != value.strip() or value.startswith(("/", "\\")) \
            or re.match(r"^[A-Za-z]:", value) or ".." in re.split(r"[/\\]", value):
        _bad(key, "must be a plain relative path with no '..'")
    return value


def content_file(key: str, tool: str) -> str:
    """The declared name of a content file under paths.root (`files.<key>`), or its default.

    Every key is optional; the default is the name the kit has always used. An unknown key, or a value that is
    not a plain relative path, exits 2 naming the key."""
    if "files" not in _CACHE:
        node = project.CONFIG.get("files")
        out = dict(FILE_DEFAULTS)
        if node is not None:
            if not isinstance(node, dict):
                _bad("files", "must be a map")
            for k, v in node.items():
                if k not in FILE_DEFAULTS and k not in OPTIONAL_FILE_KEYS:
                    _bad(f"files.{k}", f"unknown key; the keys are {', '.join((*FILE_DEFAULTS, *OPTIONAL_FILE_KEYS))}")
                out[k] = _relative(v, f"files.{k}")
        _CACHE["files"] = out
    if key not in FILE_DEFAULTS:
        raise KeyError(key)
    return _CACHE["files"][key]


def alignment_dir(tool: str) -> str | None:
    """The declared directory of alignment records under paths.root (`files.alignment`), or None. It has no default."""
    content_file("profiles", tool)  # reads and checks the whole `files` map
    return _CACHE["files"].get(ALIGNMENT_KEY)


def flows_file(tool: str) -> str | None:
    """The declared file of flow records under paths.root (`files.flows`), or None. It has no default."""
    content_file("profiles", tool)  # reads and checks the whole `files` map
    return _CACHE["files"].get(FLOWS_KEY)


def components_file(tool: str) -> str | None:
    """The declared file of component records under paths.root (`files.components`), or None. It has no default."""
    content_file("profiles", tool)  # reads and checks the whole `files` map
    return _CACHE["files"].get(COMPONENTS_KEY)


def roadmap_file(tool: str) -> str | None:
    """The declared file of roadmap increments under paths.root (`files.roadmap`), or None. It has no default."""
    content_file("profiles", tool)  # reads and checks the whole `files` map
    return _CACHE["files"].get(ROADMAP_KEY)


def components_declaration(tool: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(planes, results) from the top-level `components:` map: the plane names a component may sit on, and the
    repository paths (files or directories) whose contents count as measured results. `planes` is required;
    `results` is optional and absent means (). Call it only when components are loaded."""
    import re
    if "components" not in _CACHE:
        node = project.CONFIG.get("components")
        if node is None:
            _bad("components.planes", "is required when components are declared")
        if not isinstance(node, dict):
            _bad("components", "must be a map")
        for k in node:
            if k not in ("planes", "results"):
                _bad("components", f"unknown key {k!r}")
        if "planes" not in node:
            _bad("components.planes", "is required when components are declared")
        planes = _list(node["planes"], "components.planes")
        for i, v in enumerate(planes):
            if not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", v):
                _bad(f"components.planes[{i}]", "must be a part name: a letter or digit, then letters, digits, dots, "
                                                 "underscores or hyphens")
            if planes.index(v) != i:
                _bad(f"components.planes[{i}]", f"{v} is listed twice")
        results = node.get("results", [])
        if not isinstance(results, list):
            _bad("components.results", "must be a list")
        for i, v in enumerate(results):
            _relative(v, f"components.results[{i}]")
            if results.index(v) != i:
                _bad(f"components.results[{i}]", f"{v} is listed twice")
        _CACHE["components"] = (tuple(planes), tuple(results))
    return _CACHE["components"]


def decisions_readme(tool: str) -> str:
    """The decision document index file name: `decisions.index.readme` when declared, else README.md.

    Unlike decisions_index() it needs none of the other `decisions.index` keys."""
    node = project.CONFIG.get("decisions")
    index = node.get("index") if isinstance(node, dict) else None
    if isinstance(index, dict) and "readme" in index:
        return _name(index["readme"], "decisions.index.readme")
    return "README.md"


def _name(value, key):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or any(c.isspace() for c in value):
        _bad(key, "must be a non-empty string with no spaces")
    return value


def _prefix(value, key):
    import re
    if not isinstance(value, str) or not re.fullmatch(PREFIX_RE, value):
        _bad(key, f"{value!r} is not a prefix: lowercase letters, digits and hyphens, starting with a letter")
    return value


RECORD_KEYS = ("prefix", "digits", "file_prefix")
REGISTER_ID_KEYS = ("letters", "digits")


def _int(value, key, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        _bad(key, f"must be an integer from {low} to {high}")
    return value


def record_grammar(config: dict, bad=None) -> tuple:
    """(prefix, digits, file_prefix) of a decision record id, from a declaration's parsed map (`decisions.records`).

    Pure: it reads only `config`. `bad(key, why)` is called on a malformed value and must not return; the default
    exits 2 through the project's own declaration. The defaults are ADR, 4 and true."""
    import re
    bad = bad or _bad
    decisions = config.get("decisions")
    node = decisions.get("records") if isinstance(decisions, dict) else None
    prefix, digits, file_prefix = "ADR", 4, True
    if node is not None:
        if not isinstance(node, dict):
            bad("decisions.records", "must be a map")
        for k in node:
            if k not in RECORD_KEYS:
                bad("decisions.records", f"unknown key {k!r}")
        if "prefix" in node:
            prefix = node["prefix"]
            if not isinstance(prefix, str) or not re.fullmatch(r"[A-Z][A-Z0-9]*", prefix):
                bad("decisions.records.prefix", f"{prefix!r} is not a prefix: uppercase letters and digits, "
                                                f"starting with a letter")
        if "digits" in node:
            d = node["digits"]
            if isinstance(d, bool) or not isinstance(d, int) or not 1 <= d <= 8:
                bad("decisions.records.digits", "must be an integer from 1 to 8")
            digits = d
        if "file_prefix" in node:
            file_prefix = node["file_prefix"]
            if not isinstance(file_prefix, bool):
                bad("decisions.records.file_prefix", f"{file_prefix!r} must be true or false")
    return prefix, digits, file_prefix


def record_file_regex(prefix: str, digits: int, file_prefix: bool) -> tuple:
    """(regex text, file glob) for a record file NAME under a grammar. Pure; record_file_patterns calls it."""
    d = chr(92) + "d"
    if file_prefix:
        return f"{prefix}-(?P<n>{d}{{{digits}}})-.+" + chr(92) + ".md", f"{prefix}-*.md"
    return f"(?P<n>{d}{{{digits}}})-.+" + chr(92) + ".md", "[0-9]" * digits + "-*.md"


def record_id(tool: str) -> tuple:
    """(prefix, digits) of a decision record id (`decisions.records`); a record id is PREFIX-<digits> and its
    file PREFIX-<digits>-<slug>.md. The default is ADR and 4."""
    if "record_id" not in _CACHE:
        prefix, digits, file_prefix = record_grammar(project.CONFIG)
        _CACHE["record_id"] = (prefix, digits)
        _CACHE["record_file_prefix"] = file_prefix
    return _CACHE["record_id"]


def record_patterns(tool: str) -> tuple:
    """(regex text, glob) for a decision record id: `PREFIX-\d{N}` and `PREFIX-*.md`. For file names see
    record_file_patterns and record_id_of_file."""
    prefix, digits = record_id(tool)
    return f"{prefix}-" + chr(92) + f"d{{{digits}}}", f"{prefix}-*.md"


def record_file_patterns(tool: str) -> tuple:
    """(regex text, file glob) for a decision record's file NAME. The regex matches the whole name and captures the
    digits as `n`. With `decisions.records.file_prefix` true (the default) a name is PREFIX-<digits>-<slug>.md;
    with false it is <digits>-<slug>.md. The record id is PREFIX-<digits> either way."""
    prefix, digits = record_id(tool)
    return record_file_regex(prefix, digits, _CACHE["record_file_prefix"])


def record_id_of_file(tool: str, name: str):
    """The record id (PREFIX-<digits>) a record file name carries, or None when the name is not a record file."""
    import re
    m = re.fullmatch(record_file_patterns(tool)[0], name)
    return f"{record_id(tool)[0]}-{m.group('n')}" if m else None


def record_file_prefixed(tool: str) -> bool:
    """Whether record file names carry the prefix (`decisions.records.file_prefix`, default true)."""
    record_id(tool)
    return _CACHE["record_file_prefix"]


def record_form(tool: str) -> str:
    """The form a message shows for a record id: the prefix, a hyphen and one N per digit (ADR-NNNN by default)."""
    prefix, digits = record_id(tool)
    return f"{prefix}-" + "N" * digits


def register_id(tool: str) -> tuple:
    """(letters, min digits, max digits) of a register id (`decisions.index.register_id`): that many capital
    letters, a hyphen, then min to max digits. The default is 2, 1 and 2."""
    if "register_id" not in _CACHE:
        decisions = project.CONFIG.get("decisions")
        index = decisions.get("index") if isinstance(decisions, dict) else None
        node = index.get("register_id") if isinstance(index, dict) else None
        letters, low, high = 2, 1, 2
        base = "decisions.index.register_id"
        if node is not None:
            if not isinstance(node, dict):
                _bad(base, "must be a map")
            for k in node:
                if k not in REGISTER_ID_KEYS:
                    _bad(base, f"unknown key {k!r}")
            if "letters" in node:
                letters = _int(node["letters"], base + ".letters", 1, 6)
            if "digits" in node:
                pair = node["digits"]
                if not isinstance(pair, list) or len(pair) != 2:
                    _bad(base + ".digits", "must be a list of two integers, [min, max]")
                low = _int(pair[0], base + ".digits", 1, 6)
                high = _int(pair[1], base + ".digits", 1, 6)
                if low > high:
                    _bad(base + ".digits", "min must not exceed max")
        _CACHE["register_id"] = (letters, low, high)
    return _CACHE["register_id"]


def decisions_index(tool: str) -> DecisionIndex:
    """The declared decision-index names (`decisions.index`): the files, globs and repository prefixes."""
    if "decisions_index" not in _CACHE:
        node = project.need("decisions.index", tool)
        if not isinstance(node, dict):
            _bad("decisions.index", "must be a map")
        for k in node:
            if k not in INDEX_KEYS:
                _bad("decisions.index", f"unknown key {k!r}")
        base = "decisions.index."
        # `register: none` (the string) declares that there is no register; a missing key never does.
        no_register = node.get("register") == "none"
        if no_register:
            if portal_mode(tool) != "decisions":
                _bad(base + "register", "`none` needs `portal.mode: decisions`")
            for k in ("register_homes", "register_id"):
                if k in node:
                    _bad(base + k, "must be absent when `decisions.index.register` is `none`")
        for k in INDEX_KEYS:
            if k not in INDEX_OPTIONAL and not (no_register and k == "register_homes"):
                project.need("decisions.index." + k, tool)
        lists = {"register_homes": ()}
        for k in ("register_homes", "indexed"):
            if no_register and k == "register_homes":
                continue
            lists[k] = tuple(_name(v, f"{base}{k}[{i}]") for i, v in enumerate(_list(node[k], base + k)))
        local = _prefix(node["local_prefix"], base + "local_prefix")
        foreign = []
        items = node.get("foreign", [])
        if not isinstance(items, list):
            _bad(base + "foreign", "must be a list")
        comp = composition(tool)
        if comp is not None:
            if "foreign" in node:
                _bad(base + "foreign", "a project with files.composition takes its foreign prefixes from it; "
                                       "declare one, not both")
            items = []
            foreign = [Foreign(e.name, None, e.commit) for e in (*comp.members, *comp.consumers)]
        for i, item in enumerate(items):
            key = f"{base}foreign[{i}]"
            if not isinstance(item, dict) or "prefix" not in item:
                _bad(key, "needs a prefix")
            for k in item:
                if k not in ("prefix", "pin_check"):
                    _bad(key, f"unknown key {k!r}")
            prefix = _prefix(item["prefix"], key + ".prefix")
            if prefix == local or any(f.prefix == prefix for f in foreign):
                _bad(key + ".prefix", f"duplicate prefix {prefix!r}")
            pin = item.get("pin_check")
            if pin is not None:
                _name(pin, key + ".pin_check")
            foreign.append(Foreign(prefix, pin))
        _CACHE["decisions_index"] = DecisionIndex(
            None if no_register else _name(node["register"], base + "register"), _name(node["readme"], base + "readme"),
            lists["register_homes"], lists["indexed"], local, tuple(foreign))
    return _CACHE["decisions_index"]


class Term(NamedTuple):
    file: str
    path: str


class Dictionary(NamedTuple):
    dir: str
    terms: tuple


def dictionary(tool: str) -> Dictionary:
    """The declared term dictionary (`derived.dictionary`): a directory under the repository root, and the
    (file, path) pairs the Am-If table shows, in order."""
    import re
    if "dictionary" not in _CACHE:
        base = "derived.dictionary."
        node = project.need("derived.dictionary", tool)
        if not isinstance(node, dict):
            _bad("derived.dictionary", "must be a map")
        for k in node:
            if k not in ("dir", "terms"):
                _bad("derived.dictionary", f"unknown key {k!r}")
        d = project.need(base + "dir", tool)
        terms = project.need(base + "terms", tool)
        _relative(d, base + "dir")
        out = []
        for i, item in enumerate(_list(terms, base + "terms")):
            key = f"{base}terms[{i}]"
            if not isinstance(item, dict) or set(item) != {"file", "path"}:
                _bad(key, "needs exactly a file and a path")
            f, path = item["file"], item["path"]
            if not isinstance(f, str) or not re.fullmatch(r"[^/\\\s]+\.yaml", f):
                _bad(key + ".file", f"{f!r} is not a bare .yaml file name")
            if not isinstance(path, str) or not path.strip():
                _bad(key + ".path", "must be a non-empty string")
            out.append(Term(f, path))
        _CACHE["dictionary"] = Dictionary(d, tuple(out))
    return _CACHE["dictionary"]


ROADMAP_DEFAULTS = {
    "increments": ("#", "increment", "what isolates", "home", "depends on"),
    "fold_ins": ("row", "slice", "folds into", "why it costs the increment nothing"),
}


def roadmap_headers(tool: str) -> tuple:
    """The header cells of the roadmap note's two tables (`derived.roadmap.increments`, `.fold_ins`), as lists.

    Both keys are optional; the defaults are the original fixed headers. The columns are still read by position,
    so a declared header needs at least as many cells as the default."""
    if "roadmap" not in _CACHE:
        node = project.CONFIG.get("derived")
        node = node.get("roadmap") if isinstance(node, dict) else None
        if node is None:
            node = {}
        if not isinstance(node, dict):
            _bad("derived.roadmap", "must be a map")
        for k in node:
            if k not in ROADMAP_DEFAULTS:
                _bad("derived.roadmap", f"unknown key {k!r}")
        out = []
        for k, default in ROADMAP_DEFAULTS.items():
            key = "derived.roadmap." + k
            cells = node.get(k, list(default))
            _list(cells, key)
            if not all(isinstance(c, str) and c.strip() for c in cells):
                _bad(key, "every header cell must be a non-empty string")
            if len(set(cells)) != len(cells):
                _bad(key, "header cells must be distinct")
            if len(cells) < len(default):
                _bad(key, f"needs at least {len(default)} columns, the tool reads them by position")
            out.append(list(cells))
        _CACHE["roadmap"] = tuple(out)
    return tuple(list(h) for h in _CACHE["roadmap"])


READERS = ("helm-annotations",)


def exchange_reader(tool: str) -> str | None:
    """The declared data-exchange reader (`exchange.reader`), or None when the project declares no exchange.

    The only reader the kit has is `helm-annotations` (data_exchange.py). Any other value exits 2 and lists the
    allowed ones."""
    if "exchange_reader" not in _CACHE:
        node = project.CONFIG.get("exchange")
        reader = None
        if node is not None:
            if not isinstance(node, dict):
                _bad("exchange", "must be a map")
            if "reader" in node:
                reader = node["reader"]
                if reader not in READERS:
                    _bad("exchange.reader", f"{reader!r} is not one of: {', '.join(READERS)}")
        _CACHE["exchange_reader"] = reader
    return _CACHE["exchange_reader"]


def exchange_home(profiles: dict, tool: str) -> str | None:
    """The view that holds the data-exchange section (profiles.yaml `data_exchange.home`), or None with no exchange.

    With no reader declared there is nothing to put in a home: a `data_exchange.home` given anyway exits 2."""
    node = (profiles or {}).get("data_exchange")
    home = node.get("home") if isinstance(node, dict) else None
    if exchange_reader(tool) is None:
        if home is not None:
            project.die(f"arch-kit: profiles.yaml: data_exchange.home is {home!r}, but the declaration "
                        f"has no exchange.reader: a home with nothing to put in it")
        return None
    return home


# --- consumes: and the composition file --------------------------------------------------------------------------

COMMIT_RE = r"[0-9a-f]{40}|[0-9a-f]{64}"
COMMIT_WHY = "must be a full commit id (40 or 64 hex characters), not a branch, tag or short id"
DRIFTS = ("warn", "fail")
CONSUMES_KEYS = ("portal", "repo", "commit", "records", "why", "drift")
CONSUMES_REQUIRED = ("portal", "repo", "commit", "why")
DEFAULT_DECLARATION = "docs/arch/arch-kit.yaml"


class Consumes(NamedTuple):
    portal: str
    repo: str
    commit: str
    records: tuple | None     # None when omitted: the whole portal
    why: str
    drift: str


def _repo(value, key):
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        _bad(key, "must be a non-empty string with no whitespace")
    return value


def _commit(value, key):
    import re
    if not isinstance(value, str) or not re.fullmatch(COMMIT_RE, value):
        _bad(key, COMMIT_WHY)
    return value


def consumes(tool: str) -> tuple:
    """The declared `consumes:` entries, or () when there are none. Validated only; nothing renders from it."""
    import re
    if "consumes" not in _CACHE:
        node = project.CONFIG.get("consumes")
        out = []
        if node is not None:
            if not isinstance(node, list) or not node or not all(isinstance(i, dict) for i in node):
                _bad("consumes", "must be a non-empty list of maps")
            for i, item in enumerate(node):
                key = f"consumes[{i}]"
                for k in item:
                    if k not in CONSUMES_KEYS:
                        _bad(key, f"unknown key {k!r}")
                for k in CONSUMES_REQUIRED:
                    if k not in item:
                        _bad(f"{key}.{k}", "missing key")
                portal = _prefix(item["portal"], key + ".portal")
                if any(c.portal == portal for c in out):
                    _bad(key + ".portal", f"duplicate portal {portal!r}")
                repo = _repo(item["repo"], key + ".repo")
                commit = _commit(item["commit"], key + ".commit")
                why = item["why"]
                if not isinstance(why, str) or not why.strip() or "\n" in why or "\r" in why:
                    _bad(key + ".why", "must be a non-empty one-line string")
                drift = item.get("drift", "warn")
                if drift not in DRIFTS:
                    _bad(key + ".drift", f"{drift!r} is not one of {', '.join(DRIFTS)}")
                records = None
                if "records" in item:
                    shape = r"[A-Z][A-Z0-9]*-[0-9]+"
                    rkey = key + ".records"
                    refs = item["records"]
                    if not isinstance(refs, list) or not refs:
                        _bad(rkey, "must be a non-empty list of strings")
                    for j, ref in enumerate(refs):
                        if not isinstance(ref, str):
                            _bad(f"{rkey}[{j}]", "must be a string")
                        if ref.startswith("capability:"):
                            name = ref[len("capability:"):]
                            if not name or any(c.isspace() for c in name):
                                _bad(f"{rkey}[{j}]", f"{ref!r}: capability:<name> needs a name with no whitespace")
                        elif not re.fullmatch(shape, ref):
                            _bad(f"{rkey}[{j}]", f"{ref!r} is neither a record id (PREFIX-<digits>, such as ADR-0012) nor capability:<name>")
                        if refs.index(ref) != j:
                            _bad(f"{rkey}[{j}]", f"duplicate record {ref!r}")
                    records = tuple(refs)
                out.append(Consumes(portal, repo, commit, records, why, drift))
        _CACHE["consumes"] = tuple(out)
    return _CACHE["consumes"]


SLOT_RE = r"[a-z0-9][a-z0-9-]*"
COMPOSITION_ENTRY_KEYS = ("name", "repo", "commit", "declaration")


class Lists(NamedTuple):
    relabel: str     # a slot name, never a path
    barred: str


class Member(NamedTuple):
    name: str
    repo: str
    commit: str
    declaration: str
    lists: Lists


class Consumer(NamedTuple):
    name: str
    repo: str
    commit: str
    declaration: str


class Composition(NamedTuple):
    members: tuple
    consumers: tuple

    def names(self) -> tuple:
        """Every name in file order: the members, then the consumers."""
        return tuple(e.name for e in (*self.members, *self.consumers))


def _cbad(key, why):
    _bad("files.composition", f"{key}: {why}")


def composition(tool: str) -> Composition | None:
    """The composition file (`files.composition`, relative to the declaration), checked, or None when not declared."""
    import re
    import yaml
    if "composition" not in _CACHE:
        content_file("profiles", tool)  # reads and checks the whole `files` map
        value = _CACHE["files"].get(COMPOSITION_KEY)
        result = None
        if value is not None:
            if portal_none(tool):
                _bad("files.composition", "a project with no portal composes nothing")
            path = project.PATH.resolve().parent / value
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            except OSError:
                _bad("files.composition", f"{path} not found or unreadable")
            except yaml.YAMLError:
                _bad("files.composition", f"{path} is not valid YAML")
            if not isinstance(data, dict):
                _cbad("composition", "the file must be a map")
            if data.get("composition") != 1 or isinstance(data.get("composition"), bool):
                _cbad("composition", "must be 1")
            for k in data:
                if k not in ("composition", "members", "consumers"):
                    _cbad(k, "unknown key")
            comps = data.get("members")
            if not isinstance(comps, list) or not comps:
                _cbad("members", "must be a non-empty list")
            decl = project.CONFIG.get("decisions")
            index = decl.get("index") if isinstance(decl, dict) else None
            local = index.get("local_prefix") if isinstance(index, dict) else None
            seen, slots = [], []

            def entry(item, key, allowed):
                if not isinstance(item, dict):
                    _cbad(key, "must be a map")
                for k in item:
                    if k not in allowed:
                        _cbad(f"{key}.{k}", "unknown key")
                for k in allowed:
                    if k not in item and k != "declaration":
                        _cbad(f"{key}.{k}", "missing key")
                name = item["name"]
                if not isinstance(name, str) or not re.fullmatch(PREFIX_RE, name):
                    _cbad(f"{key}.name", f"{name!r} is not a project name: lowercase letters, digits and hyphens, "
                                         f"starting with a letter")
                if name in seen:
                    _cbad(f"{key}.name", f"duplicate name {name!r}")
                if name == local:
                    _cbad(f"{key}.name", f"{name!r} is this project's own decisions.index.local_prefix")
                seen.append(name)
                repo, commit = item["repo"], item["commit"]
                if not isinstance(repo, str) or not repo or any(c.isspace() for c in repo):
                    _cbad(f"{key}.repo", "must be a non-empty string with no whitespace")
                if not isinstance(commit, str) or not re.fullmatch(COMMIT_RE, commit):
                    _cbad(f"{key}.commit", COMMIT_WHY)
                d = item.get("declaration", DEFAULT_DECLARATION)
                if not isinstance(d, str) or not d.strip() or d != d.strip() or d.startswith(("/", "\\")) \
                        or re.match(r"^[A-Za-z]:", d) or ".." in re.split(r"[/\\]", d):
                    _cbad(f"{key}.declaration", "must be a plain relative path with no '..'")
                return name, repo, commit, d

            built = []
            for i, item in enumerate(comps):
                key = f"members[{i}]"
                name, repo, commit, d = entry(item, key, (*COMPOSITION_ENTRY_KEYS, "lists"))
                lists = item["lists"]
                if not isinstance(lists, dict) or set(lists) != {"relabel", "barred"}:
                    _cbad(key + ".lists", "must be a map with exactly the keys relabel and barred")
                for k in ("relabel", "barred"):
                    slot = lists[k]
                    if not isinstance(slot, str) or not re.fullmatch(SLOT_RE, slot):
                        what = "a slot names a slot, never a path" if isinstance(slot, str) and \
                            ("/" in slot or chr(92) in slot) else f"must match {SLOT_RE}"
                        _cbad(f"{key}.lists.{k}", f"{slot!r}: {what}")
                    if slot in slots:
                        _cbad(f"{key}.lists.{k}", f"slot {slot!r} is used twice")
                    slots.append(slot)
                built.append(Member(name, repo, commit, d, Lists(lists["relabel"], lists["barred"])))
            cons = data.get("consumers", [])
            if not isinstance(cons, list):
                _cbad("consumers", "must be a list")
            built_c = []
            for i, item in enumerate(cons):
                name, repo, commit, d = entry(item, f"consumers[{i}]", COMPOSITION_ENTRY_KEYS)
                built_c.append(Consumer(name, repo, commit, d))
            result = Composition(tuple(built), tuple(built_c))
        _CACHE["composition"] = result
    return _CACHE["composition"]
