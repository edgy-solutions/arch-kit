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
| `name` | The framework or system's display name. It is the default attribution line ("built on NAME") and is shortened to "the framework" in decision titles | `data_exchange`, `derived` |
| `model.file` | The SysML v2 model, relative to `paths.root` (or to `--root` where a tool takes one) | `check_views`, `render_profile`, `validate_sysml` |
| `model.package` | The model's top-level package name, which the reference parser must report | `validate_sysml` |
| `exchange.annotations.produces` | The workload annotation that lists the topics a workload produces | `data_exchange` |
| `exchange.annotations.groups` | The workload annotation that lists its consumer groups | `data_exchange` |
| `exchange.schema_key` | The JSON Schema extension key that declares a payload's key, label and owning tier | `data_exchange` |
| `registers.follow_ups` | The follow-ups register, a file under `paths.decisions` | `capability_phases` |
| `registers.debt` | The generalisation-debt register, under `paths.decisions` | `capability_phases` |
| `registers.roadmap` | The roadmap file whose table rows name the increments, under `paths.decisions` | `capability_phases` |
| `readiness.default` | The default readiness document, relative to the chart directory, used when `--readiness` is not given | `render_html`, `render_profile` |

## A complete example

The kit's own tests use this declaration. Every value is made up.

```yaml
kit: 1
paths:
  root: .
  repo: .
  decisions: .
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
```

## What is not declared yet

Some things are still fixed in the kit. They become declared in the next steps (see the README's status section):

- the content file names under `paths.root` (`profiles.yaml`, `slots.yaml`, `APPENDIX-A.md`, `INVENTORY.md`,
  `README.md`, `capability-record.yaml`, `adr-exemptions.yaml`, `annotation-exceptions.yaml`, `ontology/*.yaml`), and
  the decision index and record names under `paths.decisions` (`README.md`, `ADR-NNNN-<slug>.md`);
- the phases and their order, and the decision status words;
- the required views, and the views that hold each generated section;
- the column labels on the capability pages.

Until they are declared, a project has to follow the first consumer's conventions for them.
