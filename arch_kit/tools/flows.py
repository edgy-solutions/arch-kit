"""flows.py - the flow record: loading and validating (docs/design/flows.md).

A flow says that one part of a project sends one kind of record to another part, over one channel, and which decision
records decided it. The kit reads the flows from `files.flows` (one YAML file whose only key is `flows`), or takes them
from the loader's optional `load_flows(root)`. Both routes meet in validate(), so a list validates the same whichever
way it arrives. The first error raises InputError, which the caller's handler turns into exit 2. The message is
`<where>: <path>: <message>`: the schema's path is dotted (`flows.0.id`), a later check's is `flows[i].<key>`.

A list is checked in this order: the schema (arch_kit/schema/flows.schema.json), then the checks in check().
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import yaml

import alignment
import capability_phases
import declared
import project
from data_exchange import InputError

SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "flows.schema.json"
CAPABILITY = "capability:"
KEYS = ("id", "from", "to", "carries", "via", "decided_by", "built")
PATTERN_WHY = {
    "id": "must be FL- and at least three digits",
    "from": "must be a part name or capability:<name>",
    "to": "must be a part name or capability:<name>",
    "carries": "must be a non-empty string with no whitespace",
    "via": "must be one non-empty line",
}

_SCHEMA_CACHE: dict = {}


def _schema() -> dict:
    if "schema" not in _SCHEMA_CACHE:
        _SCHEMA_CACHE["schema"] = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE["schema"]


def _fail(where: str, path: str, message: str):
    raise InputError(f"{where}: {path}: {message}")


def _first_error(instance) -> tuple[str, str] | None:
    """The first schema error as (dotted path, message), in path order, or None."""
    import jsonschema
    found = []
    for e in jsonschema.Draft202012Validator(_schema()).iter_errors(instance):
        path = list(e.absolute_path)
        if e.validator == "required":
            path.append([k for k in e.validator_value if k not in e.instance][0])
            message = "is required"
        elif e.validator == "additionalProperties":
            path.append(sorted(k for k in e.instance if k not in e.schema.get("properties", {}))[0])
            message = "unknown key"
        elif e.validator in ("pattern", "not") and path and path[-1] in PATTERN_WHY:
            message = PATTERN_WHY[path[-1]]
        elif e.validator == "minItems" and path == ["flows"]:
            message = "must list at least one flow"
        else:
            message = e.message
        found.append((path, message))
    if not found:
        return None
    found.sort(key=lambda f: [(0, p, "") if isinstance(p, int) else (1, 0, p) for p in f[0]])
    path, message = found[0]
    return ".".join(str(p) for p in path) or "(record)", message


def _capabilities(tool: str) -> set[str]:
    """The capability names of a full-mode project's capability record (what the model declares)."""
    path = project.model_file(tool)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise InputError(f"cannot read the model {path}: {e.strerror or e}") from None
    return set(capability_phases.model_capabilities(text))


def check(where: str, flows: list[dict], tool: str, ctx: alignment.Context) -> None:
    """The checks after the schema. Each names the first offending flow."""
    def bad(i: int, key: str, why: str):
        _fail(where, f"flows[{i}].{key}", why)

    seen: set = set()
    for i, f in enumerate(flows):
        if f["id"] in seen:
            bad(i, "id", f"flow id {f['id']} is not unique")
        seen.add(f["id"])
    for i, f in enumerate(flows):
        if f["from"] == f["to"]:
            bad(i, "to", "must differ from from")
    seen = set()
    for i, f in enumerate(flows):
        key = (f["from"], f["to"], f["carries"], f["via"])
        if key in seen:
            bad(i, "id", f"{f['id']} repeats an earlier flow's from, to, carries and via")
        seen.add(key)
    for i, f in enumerate(flows):
        dup = next((d for d in f["decided_by"] if f["decided_by"].count(d) > 1), None)
        if dup is not None:
            bad(i, "decided_by", f"{dup} is listed twice")
    for i, f in enumerate(flows):
        for k, value in enumerate(f["decided_by"]):
            if not ctx.decision_id(value):
                bad(i, f"decided_by[{k}]", f"{value} does not resolve to a decision record")
    names: set[str] | None = None
    decisions_only = declared.portal_mode(tool) == "decisions"
    for i, f in enumerate(flows):
        for key in ("from", "to"):
            value = f[key]
            if not value.startswith(CAPABILITY):
                continue
            if decisions_only:
                bad(i, key, "capability: references need the capability record; this portal is decisions-only")
            if names is None:
                names = _capabilities(tool)
            if value[len(CAPABILITY):] not in names:
                bad(i, key, f"{value[len(CAPABILITY):]} is not a capability in the capability record")


def validate(where: str, record, tool: str, local_ids) -> tuple[dict, ...]:
    """The one validation both routes call: schema (on a map whose only key is `flows`), then checks."""
    err = _first_error(record)
    if err:
        _fail(where, err[0], err[1])
    check(where, record["flows"], tool, alignment.Context(tool, local_ids))
    return tuple(record["flows"])


def _loader_function(tool: str) -> Callable | None:
    if "loader" not in project.CONFIG:
        return None
    return getattr(project.loader(tool), "load_flows", None)


def declared_route(tool: str) -> bool:
    """True when the project declares `files.flows` or a loader `load_flows`."""
    return declared.flows_file(tool) is not None or _loader_function(tool) is not None


def load(tool: str, local_ids) -> tuple[dict, ...]:
    """The flows in file order, validated. Empty when the project declares neither `files.flows` nor a loader
    `load_flows`."""
    name = declared.flows_file(tool)
    fn = _loader_function(tool)
    if name is not None and fn is not None:
        declared._bad("files.flows", "is declared, and the loader also defines load_flows; use one route")
    if name is None and fn is None:
        return ()
    if name is not None:
        path = project.ROOT / name
        try:
            record = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            raise InputError(f"{name}: (record): cannot be read") from None
        except yaml.YAMLError:
            raise InputError(f"{name}: (record): not valid YAML") from None
        return validate(name, record, tool, local_ids)
    records = fn(project.ROOT)
    if not isinstance(records, list):
        raise InputError("load_flows must return a list of flows")
    return validate("load_flows", {"flows": records}, tool, local_ids)
