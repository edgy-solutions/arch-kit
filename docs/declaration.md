# The project declaration (`arch-kit.yaml`)

The kit holds no project's names, paths or file names. A project declares them once, in a YAML file, and every tool
reads them from there.

## Where the tools look for it

1. `--config FILE` on the command line: `python -m arch_kit --config FILE TOOL ...`;
2. otherwise the environment variable `ARCH_KIT_CONFIG`;
3. otherwise `docs/arch/arch-kit.yaml` under the current directory.

Paths inside the file are relative to the file's own directory, not to the current directory.

## Required keys

```yaml
kit: 1                    # the declaration format version; anything else is refused
paths:
  root: .                 # the architecture content: views/, model/, profiles.yaml, ...
  repo: ../..             # the repository root, where git stamps are read
  decisions: ../../decisions   # the decision records and their registers
```

If the file is missing, `kit` is not 1, or one of the three paths is missing, the tool exits 2. It prints one line
naming the file and the key.

## Keys a tool needs when it uses them

These keys are optional when the declaration loads. A tool that needs an absent key exits 2 with:

```
arch-kit: <declaration path>: missing key '<dotted.key>' (needed by <tool>)
```

So a project that never runs the data-exchange generator does not need to declare its annotation keys.

| Key | What it names | Needed by |
|---|---|---|
| `loader` | The project's loader module, relative to the declaration file (see [the loader](#the-loader)) | every tool that reads the capability record, a decision record or a register: `capability_phases` and `marks`, and through them `check_views`, `render_html`, `render_profile`, `derived`, `capability_floor`, `check_export` and `check_views_canary` |
| `name` | The framework or system's display name. It is the default attribution line ("built on NAME") and is shortened to "the framework" in decision titles | `data_exchange`, `derived` |
| `model.file` | The SysML v2 model, relative to `paths.root` (or to `--root` where a tool takes one) | `check_views`, `render_profile`, `validate_sysml` |
| `model.package` | The model's top-level package name, which the reference parser must report | `validate_sysml` |
| `exchange.annotations.produces` | The workload annotation that lists the topics a workload produces | `data_exchange` |
| `exchange.annotations.groups` | The workload annotation that lists its consumer groups | `data_exchange` |
| `exchange.schema_key` | The JSON Schema extension key that declares a payload's key, label and owning tier | `data_exchange` |
| `registers.follow_ups` | The follow-ups register, a file under `paths.decisions` | `capability_phases` |
| `registers.debt` | The generalisation-debt register, under `paths.decisions` | `capability_phases` |
| `registers.roadmap` | The roadmap file whose table rows name the increments, under `paths.decisions` | `capability_phases` |
| `labels.degraded_mode.heading` | The degraded-mode section's page heading, its table column and the derived table's lead sentence | `render_html`, `derived` |
| `labels.degraded_mode.marker` | The generated-section marker, `<!-- generated: MARKER -->` | `derived`, and through it `check_views` and `render_profile` |
| `labels.degraded_mode.attribute` | The HTML attribute on the capability page's degraded-mode paragraph | `render_html` |
| `labels.degraded_mode.open_row_prefix` | A record row id with this prefix is the open row for "not stated" | `capability_phases`, `derived`, `render_html` |
| `labels.group.column` | The capability-phases table column that holds the group, which `render_html` styles | `capability_phases`, `render_html` |
| `labels.environment.word` | The word for an environment, in the phases document's sentence ("<Word> X is ...") and the evidence cell ("<date>, <word> X, ...") | `capability_phases` |
| `readiness.default` | The default readiness document, relative to the chart directory, used when `--readiness` is not given | `render_html`, `render_profile` |

## A complete example

The kit's own tests use this declaration. Every value is made up.

```yaml
kit: 1
paths:
  root: .
  repo: .
  decisions: .
loader: loader.py
name: Example
model:
  file: model/example.sysml
  package: Example
exchange:
  annotations:
    produces: example.org/produces-topics
    groups: example.org/consumer-groups
  schema_key: x-example
registers:
  follow_ups: FOLLOW-UPS.md
  debt: DEBT.md
  roadmap: ROADMAP.md
readiness:
  default: ../scripts/READINESS.md
labels:
  degraded_mode:
    heading: Isolated behaviour
    marker: isolated-behaviour
    attribute: data-isolated
    open_row_prefix: IS-
  group:
    column: Team
  environment:
    word: site
```

The labels are the words the kit prints for three concepts. The kit holds none of them. Two identifiers follow from
them: the CSS class that marks the first row of a new group is the group column, lowercased, with spaces as hyphens,
then `-start` (`team-start` here), and the environment word starts a sentence with its first letter in upper case
("Site X is ...").

## The loader

The kit holds the rules and the rendering, but not the project's file formats. Reading the project's files is the
loader's job. The loader is a Python module that the project writes, and `loader:` declares it. The kit imports it
once, by path.

The loader provides the names in `arch_kit/tools/seam.py`, where they are written as a `typing.Protocol` with one line
each:
- `load_record`: the capability record;
- `model_capabilities`: the capabilities in the model;
- the decision records: `read_text`, `adr_file`, `adr_lead`, `adr_status` and `index_status`;
- the registers and the roadmap: `register_rows`, `register_subjects` and `roadmap_rows`;
- the readiness document: `resolve_entries`, `quote_of`, `measured_line` and `resolve_quotes`;
- `KEY_NAMES`, a map from each neutral key to the project's own name for it.

The kit's tests check that every name exists on the kit's own fixture loader, `arch_kit/tools/testdata/loader.py`.
That file is a minimal working loader for a made-up format, and a starting point for writing one.

### The neutral record

`load_record` returns the record with these keys, whatever the project calls them on disk:

| Neutral key | What it holds |
|---|---|
| `groups` | for each parent capability in the model, the group it belongs to, shown beside its capabilities |
| `environments` | the environments a measurement can run in. Every entry must name one of them |
| `entries.<key>.environment` | the environment that entry's measurement ran in |
| `capabilities.<name>.degraded_mode` | what the capability does when it is cut off |

All other keys keep the names that `arch_kit/schema/record.schema.json` gives them. The loader maps the keys after it
parses the file. It should refuse a file that already uses a neutral key, so that two names never mean the same thing.

The kit validates the returned record against `arch_kit/schema/record.schema.json` (JSON Schema draft 2020-12), with
`jsonschema==4.26.0`. Messages print the project's own key names through `KEY_NAMES`, including schema errors, so
the output reads in the project's own words.

### When it fails

All of these exit 2:

| Failure | Message |
|---|---|
| No `loader` key | `arch-kit: <declaration>: missing key 'loader' (needed by <tool>)` |
| The file does not exist | `arch-kit: <declaration>: loader file <path> not found` |
| The record breaks the schema | `<record>: <where>: <what>`, for the first place it breaks |

## What is not declared yet

Some things are still fixed in the kit. Some become declared in step 3 (S3b: the labels, now declared; S3c: the phases, statuses and view kinds), and the file names are not yet scheduled (see the README's status section):

- the content file names under `paths.root` (`profiles.yaml`, `slots.yaml`, `APPENDIX-A.md`, `INVENTORY.md`,
  `README.md`, `capability-record.yaml`, `adr-exemptions.yaml`, `annotation-exceptions.yaml`, `ontology/*.yaml`), and
  the decision index and record names under `paths.decisions` (`README.md`, `ADR-NNNN-<slug>.md`);
- the phases and their order, and the decision status words;
- the required views, and the views that hold each generated section.

Until they are declared, a project has to follow the first consumer's conventions for them.
