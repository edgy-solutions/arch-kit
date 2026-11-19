"""alignment.py - the alignment record: loading, validating and merging seeds.

An alignment record compares a project with external references, element by element (docs/design/alignment.md).
The kit reads the records from `files.alignment` (every *.yaml in that directory is one record, named by its file
stem), or takes them from the loader's optional `load_alignment(root)`. Both routes meet in validate(), so one
record validates the same whichever way it arrives. The first error raises InputError, which the caller's handler
turns into exit 2. The message is `<where>: <path in the record>: <message>`.

A record is checked in this order: the schema (arch_kit/schema/alignment.schema.json), the seed merge, then the
checks in check().
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

import yaml

import declared
import project
from data_exchange import InputError

SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "alignment.schema.json"
SEEDS = Path(__file__).resolve().parents[1] / "references"
NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
TEXT_PATTERN = "\\S"

_SCHEMA_CACHE: dict = {}


def _schema() -> dict:
    if "schema" not in _SCHEMA_CACHE:
        _SCHEMA_CACHE["schema"] = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE["schema"]


def _dotted(path) -> str:
    return ".".join(str(p) for p in path) or "(record)"


def _fail(where: str, path, message: str):
    raise InputError(f"{where}: {_dotted(path) if not isinstance(path, str) else path}: {message}")


def _first_error(schema: dict, instance) -> tuple[list, str] | None:
    """The first schema error as (path, message), in path order, or None."""
    import jsonschema
    found = []
    for e in jsonschema.Draft202012Validator(schema).iter_errors(instance):
        path = list(e.absolute_path)
        if e.validator == "required":
            missing = [k for k in e.validator_value if k not in e.instance]
            path.append(missing[0])
            message = "is required"
        elif e.validator == "additionalProperties":
            extra = sorted(k for k in e.instance if k not in e.schema.get("properties", {}))
            path.append(extra[0])
            message = "unknown key"
        elif e.validator == "not" and e.validator_value == {}:
            message = "must be absent here"
        elif e.validator == "pattern" and e.validator_value == TEXT_PATTERN:
            message = "must be a non-empty string"
        elif e.validator == "pattern":
            message = "is not of the form [a-z0-9][a-z0-9-]*"
        else:
            message = e.message
        found.append((path, message))
    if not found:
        return None
    found.sort(key=lambda f: [(0, p, "") if isinstance(p, int) else (1, 0, p) for p in f[0]])
    return found[0]


# --- seeds ---------------------------------------------------------------------------------------------------------

def _seed_schema() -> dict:
    return {"$schema": _schema()["$schema"], "$defs": _schema()["$defs"], "$ref": "#/$defs/seed"}


def seed_names() -> list[str]:
    return sorted(f.stem for f in SEEDS.glob("*.yaml")) if SEEDS.is_dir() else []


def load_seed(name: str) -> dict | None:
    """The seed's text as a dict, validated as a seed; None when the kit has no seed of that name."""
    f = SEEDS / f"{name}.yaml"
    if not f.is_file():
        return None
    return validate_seed(f"references/{f.name}", yaml.safe_load(f.read_text(encoding="utf-8")))


def validate_seed(where: str, seed) -> dict:
    err = _first_error(_seed_schema(), seed)
    if err:
        _fail(where, err[0], err[1])
    ids = [e["id"] for e in seed["elements"]]
    dup = next((i for i in ids if ids.count(i) > 1), None)
    if dup:
        _fail(where, "elements", f"element id {dup} is not unique")
    return seed


def _group_order(elements: list[dict]) -> list[str]:
    out: list[str] = []
    for e in elements:
        if e["group"] not in out:
            out.append(e["group"])
    return out


CENSUS_KEY = re.compile(
    r"^(?:(?P<member>[a-z0-9]+(?:-[a-z0-9]+)*)(?::| ))?"
    r"(?:(?P<path>[^\s\u00a7:]*[./][^\s\u00a7:]*) )?"
    r"\u00a7(?P<section>[0-9][0-9a-z]*(?:-[0-9a-z]+)*)(?: \((?P<variant>[A-Za-z][A-Za-z0-9-]*)\))?"
    r"(?:\.(?P<bullet>[1-9][0-9]*))?$")


# --- the checks ----------------------------------------------------------------------------------------------------

class Context:
    """What the evidence checks need from the project."""

    def __init__(self, tool: str, local_ids, repo: Path | None = None,
                 audience: str | None = None):
        self.tool = tool
        self.local_ids = set(local_ids)
        self.repo = Path(repo) if repo is not None else project.REPO
        self.audience = audience
        self._foreign: set | None = None

    def foreign(self) -> set:
        if self._foreign is None:
            self._foreign = {f.prefix for f in declared.decisions_index(self.tool).foreign}
        return self._foreign

    def decision_id(self, value: str) -> bool:
        """A local decision id, or `<prefix>:<id>` with a declared foreign prefix and an id of the decision-id form."""
        if value in self.local_ids:
            return True
        prefix, sep, rest = value.partition(":")
        if sep and re.fullmatch(declared.record_patterns(self.tool)[0], rest):
            return prefix in self.foreign()
        return False

    def census_problem(self, value: str) -> str | None:
        """None when `value` lacks the census form (see CENSUS_KEY) or has it and is acceptable; otherwise why not.
        A member-qualified key is not checked here: the mesh loader resolves it. A path in a key is accepted by form:
        the census document and the directory of resolvable records differ, so the loader resolves the key.
        The declared census may be a file or a directory."""
        m = CENSUS_KEY.match(value)
        if m is None or m["member"]:
            return None
        census = declared.census_file(self.tool)
        if census is None:
            return f"{value} is a census key, and the project declares no census (census:)"
        if not (self.repo / census).exists():
            return f"{value} cites the census {census}, which does not exist"
        return None

    def census_key(self, value: str) -> bool:
        return CENSUS_KEY.match(value) is not None and self.census_problem(value) is None

    def path_exists(self, value: str) -> bool:
        if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value) or ".." in re.split(r"[/\\]", value):
            return False
        try:
            return (self.repo / value).exists()
        except (OSError, ValueError):
            return False


def merge(where: str, record: dict) -> dict:
    """The record with each reference's seed merged in: the reference's own title, edition, identifier and terms
    win; the compared elements are the seed's (filtered by `groups`), then the inline ones. Adds, to each
    reference, `compared` (the elements, in order) and `left_out` (the seed's groups `groups` leaves out)."""
    out = dict(record)
    out["references"] = []
    for i, ref in enumerate(record["references"]):
        ref = dict(ref)
        seed = None
        if "seed" in ref:
            seed = load_seed(ref["seed"])
            if seed is None:
                _fail(where, f"references.{i}.seed", f"seed {ref['seed']} not found; the kit's seeds are "
                                                     f"{', '.join(seed_names()) or '(none)'}")
            for k in ("title", "edition", "identifier", "terms"):
                if k not in ref and k in seed:
                    ref[k] = seed[k]
            seed_ids = {e["id"] for e in seed["elements"]}
            for k, e in enumerate(ref.get("elements", [])):
                if e["id"] in seed_ids:
                    _fail(where, f"references.{i}.elements.{k}.id", f"{e['id']} is an element of seed {ref['seed']}")
        ref["_seed_elements"] = list(seed["elements"]) if seed else []
        out["references"].append(ref)
    return out


def _compared(where: str, i: int, ref: dict) -> tuple[list[dict], list[str]]:
    """(compared elements, seed groups left out) of one merged reference. Checks `groups`."""
    seed_elements = ref["_seed_elements"]
    inline = list(ref.get("elements", []))
    if "groups" in ref:
        if "seed" not in ref:
            _fail(where, f"references.{i}.groups", "groups needs a seed")
        have = _group_order(seed_elements)
        seen: list[str] = []
        for k, g in enumerate(ref["groups"]):
            if g not in have:
                _fail(where, f"references.{i}.groups.{k}", f"{g} is not a group of seed {ref['seed']}")
            if g in seen:
                _fail(where, f"references.{i}.groups.{k}", f"{g} is listed twice")
            seen.append(g)
        kept = [e for e in seed_elements if e["group"] in seen]
        left_out = [g for g in have if g not in seen]
    else:
        kept, left_out = seed_elements, []
    return kept + inline, left_out


def check(where: str, record: dict, ctx: Context) -> dict:
    """The checks after the schema and the seed merge. Returns the record with `compared` and `left_out` on each
    reference (and without the private seed list)."""
    refs = record["references"]
    # 1. keys
    keys: list[str] = []
    for i, ref in enumerate(refs):
        if ref["key"] in keys:
            _fail(where, f"references.{i}.key", f"reference key {ref['key']} is not unique")
        keys.append(ref["key"])
        ids: list[str] = [e["id"] for e in ref["_seed_elements"]]
        for k, e in enumerate(ref.get("elements", [])):
            if e["id"] in ids:
                _fail(where, f"references.{i}.elements.{k}.id", f"element id {e['id']} is not unique in reference "
                                                                f"{ref['key']}")
            ids.append(e["id"])
    # 2. read: title-only
    for i, ref in enumerate(refs):
        if ref["read"] != "title-only":
            continue
        for field in ("seed", "groups", "elements"):
            if field in ref:
                _fail(where, f"references.{i}.{field}", f"reference {ref['key']} is read title-only, so it has no {field}")
    for j, row in enumerate(record["rows"]):
        ref = next((r for r in refs if r["key"] == row["ref"]), None)
        if ref is not None and ref["read"] == "title-only":
            _fail(where, f"rows.{j}.ref", f"reference {ref['key']} is read title-only, so no row may name it")
    # 3. groups, and the compared elements
    compared: dict[str, list[dict]] = {}
    for i, ref in enumerate(refs):
        els, left_out = _compared(where, i, ref)
        if ref["read"] != "title-only" and not els:
            _fail(where, f"references.{i}.elements", f"reference {ref['key']} has no compared element")
        ref["compared"], ref["left_out"] = els, left_out
        compared[ref["key"]] = els
    # 4. rows: exactly one per compared element
    seen: set = set()
    for j, row in enumerate(record["rows"]):
        if row["ref"] not in compared:
            _fail(where, f"rows.{j}.ref", f"{row['ref']} is not a reference key")
        if row["element"] not in {e["id"] for e in compared[row["ref"]]}:
            _fail(where, f"rows.{j}.element", f"{row['element']} is not a compared element of reference {row['ref']}")
        if (row["ref"], row["element"]) in seen:
            _fail(where, f"rows.{j}", f"a second row for ref {row['ref']} element {row['element']}")
        seen.add((row["ref"], row["element"]))
    for ref in refs:
        for e in ref["compared"]:
            if (ref["key"], e["id"]) not in seen:
                _fail(where, "rows", f"no row for ref {ref['key']} element {e['id']}")
    # 5. evidence, 6. owed
    for j, row in enumerate(record["rows"]):
        for k, value in enumerate(row.get("evidence", [])):
            if ctx.decision_id(value) or ctx.path_exists(value):
                continue
            problem = ctx.census_problem(value)
            if problem is not None:
                _fail(where, f"rows.{j}.evidence.{k}", problem)
            if not ctx.census_key(value):
                _fail(where, f"rows.{j}.evidence.{k}", f"{value} does not resolve")
    for j, row in enumerate(record["rows"]):
        if "owed" in row and not ctx.decision_id(row["owed"]):
            _fail(where, f"rows.{j}.owed", f"{row['owed']} does not resolve")
    for ref in refs:
        del ref["_seed_elements"]
    return record


def validate(where: str, record, ctx: Context) -> dict:
    """The one validation both routes call: schema, seed merge, checks. Returns the merged record."""
    err = _first_error(_schema(), record)
    if err:
        _fail(where, err[0], err[1])
    return check(where, merge(where, record), ctx)


# --- loading -------------------------------------------------------------------------------------------------------

def _loader_function(tool: str) -> Callable | None:
    if "loader" not in project.CONFIG:
        return None
    return getattr(project.loader(tool), "load_alignment", None)


def load(tool: str, local_ids, audience: str | None = None) -> dict[str, dict]:
    """Every alignment record by name, validated and merged, in name order. Empty when the project declares
    neither `files.alignment` nor a loader `load_alignment`."""
    directory = declared.alignment_dir(tool)
    fn = _loader_function(tool)
    if directory is not None and fn is not None:
        declared._bad("files.alignment", "is declared, and the loader also defines load_alignment; use one route")
    if directory is None and fn is None:
        return {}
    ctx = Context(tool, local_ids, audience=audience)
    out: dict[str, dict] = {}
    if directory is not None:
        base = project.ROOT / directory
        if not base.is_dir():
            declared._bad("files.alignment", f"{directory} is not a directory under paths.root")
        files = sorted(f for f in base.glob("*.yaml") if f.is_file())
        if not files:
            declared._bad("files.alignment", f"{directory} holds no *.yaml record")
        for f in files:
            where = f"{directory}/{f.name}"
            if not NAME_RE.fullmatch(f.stem):
                raise InputError(f"{where}: (record): the file name must match [a-z0-9][a-z0-9-]*")
            try:
                record = yaml.safe_load(f.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                raise InputError(f"{where}: (record): cannot be read") from None
            except yaml.YAMLError:
                raise InputError(f"{where}: (record): not valid YAML") from None
            out[f.stem] = _finish(where, record, ctx)
    else:
        records = fn(project.ROOT)
        if not isinstance(records, dict) or not all(isinstance(k, str) and isinstance(v, dict)
                                                    for k, v in records.items()):
            raise InputError("load_alignment must return a dict of record name to record")
        for name, record in sorted(records.items()):
            if not NAME_RE.fullmatch(name):
                raise InputError(f"alignment record {name}: (record): the name must match [a-z0-9][a-z0-9-]*")
            out[name] = _finish(f"alignment record {name}", record, ctx)
    return out


def check_audience(where: str, record: dict, audience: str | None) -> None:
    """A public portal shows a reference with unconfirmed terms by title only and never shows one with restricted
    terms. A private portal, or no audience given, shows everything."""
    if audience != "public":
        return
    for i, ref in enumerate(record["references"]):
        status = ref["terms"]["status"]
        if status == "restricted":
            _fail(where, f"references.{i}", f"reference {ref['key']} has restricted terms; a public portal may "
                                            f"not show it")
        if status == "unconfirmed" and ref["read"] != "title-only":
            _fail(where, f"references.{i}", f"reference {ref['key']} has unconfirmed terms; a public portal shows "
                                            f"it by title only, so it may carry no elements")


def _finish(where: str, record, ctx: Context) -> dict:
    merged = validate(where, record, ctx)
    check_audience(where, merged, ctx.audience)
    return merged
