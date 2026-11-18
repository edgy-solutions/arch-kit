"""arch-kit [--config FILE] TOOL [ARGS...]   (python -m arch_kit is the same)"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent / "tools"
NAMES = (
    "adr_sections", "browser_facts", "capability_floor", "capability_phases", "check_annotations",
    "check_decision_indexes", "check_export",
    "check_views", "check_views_canary", "data_exchange", "derived", "marks", "portal", "relabel",
    "render_html", "render_profile", "validate_sysml",
)


def main(argv):
    config = None
    if argv[:1] == ["--config"]:
        if len(argv) < 2:
            raise SystemExit("usage: arch-kit [--config FILE] TOOL [ARGS...]   (python -m arch_kit is the same)")
        config = argv[1]
        argv = argv[2:]
    if not argv or argv[0] not in NAMES:
        print("usage: arch-kit [--config FILE] TOOL [ARGS...]   (python -m arch_kit is the same)\ntools: " + ", ".join(NAMES),
              file=sys.stderr)
        return 2
    if config is not None:
        os.environ["ARCH_KIT_CONFIG"] = str(Path(config).resolve())
    sys.path.insert(0, str(TOOLS))
    sys.argv = [argv[0] + ".py", *argv[1:]]
    runpy.run_path(str(TOOLS / (argv[0] + ".py")), run_name="__main__")
    return 0


def cli():
    """The `arch-kit` console script."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
