# arch-kit

arch-kit turns a project's architecture records into one published set of architecture views, and refuses to publish
anything they cannot back up.

A project writes:
- its views in Markdown;
- its model in SysML v2;
- its decisions as decision records;
- a capability record that says which decisions, deployment templates and measurements back each capability.

The kit checks these sources against each other, renders them as UAF views with DoDAF 2.02 and NAF 4 profiles, and
writes a single self-contained HTML file. It then checks that file as text and in a real browser.

The kit does not decide what is true. It checks that every claim points at something that exists, and that every
claim says how strong its evidence is. The [methodology](docs/METHODOLOGY.md) covers the writing that the checks
assume.

## Status

**Pre-release: `0.1.0.dev0`.** The kit is being extracted from the first project that used it. That project's export
is the acceptance test: after every step it must come out byte-identical, or each difference is listed and explained.

| Step | | State |
|---|---|---|
| 1 | Tools moved unchanged. Content paths are read from the project's declaration | done |
| 2 | No project names in the kit. Names, keys and file names are declared | done |
| 3 | A loader seam: each project reads its own files into a neutral record. Labels, phases, statuses and view kinds are declared | done |
| 4 | Relabelling and the leak scan run on the rendered HTML | planned |
| 5 | Each portal declares its hosting and its audience | planned |
| 6 | A CLI entry point, a reusable GitHub Action, the decision-index checks, a `v0.1.0` release, and a fictional example project | planned |
| 7 | The first project pins `v0.1.0`, with the golden comparison in its CI | planned |

Until `v0.1.0`, pin a commit, not a branch. Some conventions are still fixed rather than declared. The
[declaration reference](docs/declaration.md#what-is-not-declared-yet) lists them.

## How it works

```
 views/*.md ─┐
 model ──────┤                ┌─ render_profile ─> Markdown per profile (uaf, dodaf202, naf4)
 decisions ──┼─> check_views ─┤
 record ─────┤   (17 rules)   └─ render_html ────> export.html ─> check_export ─> browser check
 chart ──────┘
```

- **`check_views`** checks the sources against each other: links, citations, the model, the capability record, and
  what the deployment actually renders.
- **`render_profile`** and **`render_html`** fill the generated sections from declared sources, never from text
  written for them:
  - the data-exchange tables from a Helm render;
  - the capability phases from the record;
  - the derived tables from the model and the record.
- **`check_export`** and the **browser check** test the file people will read.

Every page ends with a provenance block. It gives the chart and its version, a digest of the values files read, the
date, and the line "Declared, not measured": the export reads the views, the model and a chart render, and no running
system. A table built from a render carries the same stamp. A number counts as "measured" only when a readiness entry
records the run that produced it.

## Quick start

### Requirements

- Python 3.10 or later (CI uses 3.12), with `pyyaml`, `markdown-it-py==4.0.0` and `jsonschema==4.26.0`.
- For diagrams and the browser check: Node.js 22 or later, and Chrome. Run `npm ci` in `arch_kit/tools/export`, and set
  `PUPPETEER_EXECUTABLE_PATH` to Chrome.
- For the deployment-backed checks and the data-exchange tables: `helm`, and the project's chart.
- For `validate_sysml`: Java 21 and the SysML v2 reference parser.

### 1. Get the kit

```sh
git clone https://github.com/edgy-solutions/arch-kit
cd arch-kit && git checkout <commit>
export PYTHONPATH="$PWD"
```

### 2. Declare your project

Put `docs/arch/arch-kit.yaml` in your repository:

```yaml
kit: 1
paths:
  root: .                      # this directory: views/, model/, profiles.yaml, ...
  repo: ../..                  # the repository root
  decisions: ../../decisions   # the decision records
loader: kit_loader.py          # your module that reads your files for the kit
name: Example
model:
  file: model/example.sysml
  package: Example
```

The loader is a Python module you own. It reads your capability record, your decision records and your registers,
and hands the kit the record in a neutral shape. The kit checks that shape against a JSON Schema when the record
loads. The [declaration reference](docs/declaration.md) lists every key and the tool that needs it, and describes
[the loader](docs/declaration.md#the-loader).

### 3. Run it

From your repository root:

```sh
python -m arch_kit check_views --chart CHART --values VALUES.yaml --release NAME \
    --readiness READINESS.md --barred BARRED.txt

python -m arch_kit render_html --out export.html --chart CHART --values VALUES.yaml \
    --release NAME --relabel RELABEL.txt

python -m arch_kit check_export --export export.html --barred BARRED.txt --relabel RELABEL.txt

python -m arch_kit browser_facts --out facts.json

node "$PYTHONPATH/arch_kit/tools/export/check_export_browser.mjs" export.html --shots shots/ --facts facts.json
```

`python -m arch_kit [--config FILE] TOOL [ARGS...]` runs any tool. Run it with no tool to list them. `--config`
points at a declaration somewhere else.

## Content layout

The tools read these files under `paths.root` and `paths.decisions`. The file names are fixed for now.

```
<paths.root>/
  README.md                  the vocabulary of the Sources table's Decision and Evidence columns
  INVENTORY.md               the slot table
  APPENDIX-A.md              the UAF view → DoDAF 2.02 / NAF 4 / DNDAF mapping (the only copy)
  profiles.yaml              the views, their ids and files
  slots.yaml                 the registered slots
  capability-record.yaml     each capability: its description, citations, built templates, evidence
  views/*.md                 one file per view; the first line is "# Name (ID)"
  <model.file>               the SysML v2 model
  ontology/*.yaml            input to the data-dictionary table
  adr-exemptions.yaml        decisions exempt from the derived tables
  annotation-exceptions.yaml workloads exempt from the annotation check

<paths.decisions>/
  README.md                  the decision index, with each record's status
  ADR-NNNN-<slug>.md         one decision record each, with a status line
  <registers.*>              the follow-ups and debt registers, and the roadmap (declared)
```

A view cites a decision by section: `[ADR-0007 §PLACEMENT](...)`. The label must resolve to exactly one heading in
that record. Generated sections are marked in the view with an HTML comment, `<!-- generated: NAME -->`, and are
filled at render time.

## The tools

| Tool | What it does |
|---|---|
| `check_views` | Checks the sources: [17 rules](docs/rules.md) |
| `check_views_canary` | Breaks a copy of the tree, and proves `quotes` and `floor` fail |
| `render_profile` | Renders the views as one profile: `uaf`, `dodaf202` or `naf4` |
| `render_html` | Renders all three profiles as one self-contained HTML file, with diagrams drawn at build time |
| `check_export` | Checks the HTML file: views, provenance, links, diagrams, size, barred and relabelled names |
| `export/check_export_browser.mjs` | Opens the file in headless Chrome, and checks buttons, pages and diagrams. It needs `--facts` from `browser_facts` |
| `browser_facts` | Writes the counts and view ids the browser check expects, computed from the declaration and the sources |
| `data_exchange` | Generates the data-exchange view (producers, consumers, routes per tier) from a Helm render |
| `check_annotations` | Checks that each workload in a render declares the topics it produces and the groups it consumes |
| `capability_phases` | Computes each capability's phase and evidence from the record |
| `capability_floor` | Uses the render as a floor: everything deployed must be claimed by a capability that is at least built |
| `derived` | Builds the tables a view takes from a declared artefact instead of writing them |
| `marks` | Fills a Sources row's Evidence from the cited record's status line |
| `adr_sections` | Reads a decision record's sections, and resolves `ADR-NNNN §LABEL` citations |
| `relabel` | Replaces internal names in decision records as they are exported. The sources are not changed |
| `validate_sysml` | Parses the model with the reference parser, and proves the parser rejects two broken copies |

The checks exit 0 when everything passes, 1 when a check fails, and 2 when an input is missing or bad. A check that
cannot run is never reported as passing.

## Documentation

- [The declaration](docs/declaration.md): `arch-kit.yaml`, key by key.
- [The checks](docs/rules.md): what each rule fails on, the export checks, and the relabel and barred lists.
- [Methodology](docs/METHODOLOGY.md): how to write records the checks can hold to (records or proposes, findings
  first, read status per source, every claim cited, misses recorded).

## Names that must not be published

A project's relabel list and barred list belong to that project. Keep them out of this repository, and out of any
public one. The kit ships only made-up samples. A green run with the samples is not evidence that a project's private
scan ran. See [the checks](docs/rules.md#names-in-the-published-file).

## Development

```sh
pip install pyyaml markdown-it-py==4.0.0 jsonschema==4.26.0
python -m unittest discover -s arch_kit/tools -p 'test_*.py'
```

CI (`.github/workflows/tests.yml`) runs the suite on every push and pull request to `main`, and any skipped test fails
the job. A separate step first runs the check that no tracked file names a consuming project. The kit's own test
fixtures use made-up names only.

Changes reach `main` through pull requests, and merge on green CI after review.

## Licence

MIT. See [LICENSE](LICENSE).
