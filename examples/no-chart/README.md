# Marigold architecture

The architecture views of the example project: a parcel-locker network, invented for the kit. This example declares
`chart: none` and `model: none`: the export is the full shell (the three grids, a page per view, the views list and the
provenance footer) for a project with no chart and no model. Its two `pages:` are plain markdown files.

Run the tools from this directory with `python -m arch_kit --config arch-kit.yaml TOOL`. The render takes
`--source NAME=COMMIT` (a source the views were written from, with its 40-hex commit) in place of `--chart`,
`--values` and `--release`; `--kit-commit` overrides the kit's own commit, which is otherwise read from its checkout.

`expected/export.html` is the snapshot the self-test compares with. The test never writes it; regenerate it from the kit
root with `python arch_kit/tools/test_example_no_chart.py --write-snapshot` and review the diff.
