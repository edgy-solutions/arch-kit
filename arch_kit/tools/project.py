"""The consumer's declared paths: where its architecture content, repository and decisions live.

The declaration is a YAML file named by env ARCH_KIT_CONFIG, or docs/arch/arch-kit.yaml under the
current directory. Paths in it are relative to the declaration file's own directory:

    kit: 1
    paths:
      root: .
      repo: ../..
      decisions: ../../decisions

ROOT, REPO and DECISIONS are the resolved paths; CONFIG is the parsed map. A missing file, a kit
version other than 1, or a missing path key exits 2 with a one-line message.

The other keys (name, model.file, model.package, exchange.annotations.produces and .groups,
exchange.schema_key, registers.follow_ups, .debt and .roadmap, readiness.default) are optional at
load. need("model.file", "validate_sysml") returns the value when a tool uses it, and exits 2 with
`arch-kit: <decl path>: missing key 'model.file' (needed by validate_sysml)` when it is absent.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

KEYS = ("root", "repo", "decisions")


def _die(message):
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _load():
    env = os.environ.get("ARCH_KIT_CONFIG")
    path = Path(env) if env else Path.cwd() / "docs" / "arch" / "arch-kit.yaml"
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError:
        _die(f"arch-kit: {path}: declaration file not found or unreadable")
    except yaml.YAMLError:
        _die(f"arch-kit: {path}: not valid YAML")
    if not isinstance(config, dict) or config.get("kit") != 1:
        _die(f"arch-kit: {path}: key 'kit' must be 1")
    paths = config.get("paths")
    if not isinstance(paths, dict):
        _die(f"arch-kit: {path}: missing key 'paths'")
    for key in KEYS:
        if key not in paths:
            _die(f"arch-kit: {path}: missing key 'paths.{key}'")
    base = path.resolve().parent
    return config, {key: (base / str(paths[key])).resolve() for key in KEYS}, path


CONFIG, _PATHS, PATH = _load()
ROOT = _PATHS["root"]
REPO = _PATHS["repo"]
DECISIONS = _PATHS["decisions"]


def need(dotted, tool):
    """The declared value at a dotted key, or exit 2 naming the key and the tool that needs it."""
    value = CONFIG
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            _die(f"arch-kit: {PATH}: missing key '{dotted}' (needed by {tool})")
        value = value[part]
    return value


def model_file(tool):
    """The declared model file, resolved against paths.root."""
    return ROOT / str(need("model.file", tool))


def readiness_default(chart_dir, tool):
    """The declared default readiness doc, relative to the chart directory."""
    return Path(os.path.normpath(Path(chart_dir) / str(need("readiness.default", tool))))
