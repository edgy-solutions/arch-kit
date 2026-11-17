# Larkspur architecture

The architecture views of the example project: a parcel-locker network, invented for the kit. A view's source is in
[views/](views/). Each ends with a Sources table that says where its claims come from.

How to read a Sources table:

| Decision | Meaning |
|---|---|
| Accepted | The record says accepted. |
| Proposed | The record says proposed. |
| Decision pending | No decision record decides it yet. |
| Generated | Computed when the view is rendered, not written in it. |

| Evidence | Meaning |
|---|---|
| Built | The record says done. |
| Declared | Read from a chart render. Nothing was observed running. |
| Pending | The record says the work is pending. |
| Not stated | The record does not say. |
| Generated | Computed when the view is rendered. |
| Status line | In the view's source only: read from the cited record's status line when the view is rendered. |

## About this example

This directory is the kit's example project, and the kit's self-test builds it. Every name in it is invented. Run its
tools from this directory with `python -m arch_kit --config arch-kit.yaml TOOL` (see the kit's README for the full
chain), or run `python -m unittest arch_kit.tools.test_example` from the kit root.

It declares no data exchange, so no exchange section is generated and Helm is never run. The kit's reader for the
exchange (`helm-annotations`) is covered by its own unit tests, not by this example.

The chart in `chart/` is a stub, and it is not rendered. Three things still read it: the provenance block (`Chart.yaml`
and the values files), the check that a built claim's template exists (`chart/templates/`), and the readiness document
(`READINESS.md`) that the evidence quotes come from.

`validate_sysml` is not part of the chain: it needs Java and a reference parser.

The roadmap note (`decisions/ROADMAP.md`) copies the kit's format. Its two table headers (the increment table and the
fold-in table) and its `Status:` line are the kit's, not a choice this project made. See the kit's METHODOLOGY.

`expected/export.html` is the snapshot the self-test compares with. Diagrams, the build date and decision stamps are
normalised first. After an intended change to the example, regenerate it from the kit root with

    python arch_kit/tools/test_example.py --write-snapshot

and review the diff before committing. The test never writes it.
