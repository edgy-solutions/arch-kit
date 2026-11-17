# Design record: composed portals and the "consumer of" relation

**Status: draft, proposed. Nothing in it is ruled, and nothing is built.**

Proposes a decision: one portal can compose the records of other projects, and any project can declare that it
consumes a portal or part of one. Consumption is declared by the consumer only, is rendered on both sides, and every
link is pinned to a commit.

Phase 2 of the kit. It builds on Phase 1, where one project's records render as one portal from one declaration
(`arch-kit.yaml`). This record decides the shape of the relations and the declaration. The build steps at the end are
a sketch, to be specified once this is ruled.

## 1. Three relations, one vocabulary

A project can relate to another project's records in three ways. They are different relations, they are declared in
different places, and the export renders each one differently.

| Relation | Meaning | Declared by | Rendered |
|---|---|---|---|
| **composes** | Portal P renders project Q's records as part of P. Q is a *component* of P. | P, in its composition file (§3) | Q's pages appear inside P, under Q's name |
| **consumes** | Project X depends on portal Y, or on named records in it, and does not render them. | X, in its own `arch-kit.yaml` (§2) | A link on both sides: in X's portal, and in Y's pages wherever Y is rendered by a composition (§4) |
| **cites** | One decision record names another, in its text. | The record's author, in the text (`ADR-NNNN`, or `repo:ADR-NNNN` across repositories) | As written. The decision index check already resolves the names |

- **A citation is not a consumption.** A record can cite another project's decision without the project depending on
  that portal. A consumption is usually backed by citations, but the kit does not infer one from the other.
- **An application is a consumer, not a component.** A project that uses a composed portal, but whose own records are
  not part of it, is listed by the composed portal as a consumer, with a link. It is not composed into it.
- **The repository prefixes are the shared key.** The prefix a `repo:ADR-NNNN` citation uses, the name a
  composition file gives a component, and the name a `consumes` entry gives a portal are the same declared name for
  the same project. One table of known projects serves all three (§3).

## 2. The consumer's declaration

The consumer declares what it consumes in its own `arch-kit.yaml`:

```yaml
consumes:
  - portal: example-platform          # the consumed portal's declared name
    repo: https://example.org/example-platform.git
    commit: 0123456789abcdef0123456789abcdef01234567   # full sha; a branch or a short sha is refused
    records: [ADR-0012, capability:LabelledRecords]      # optional; omitted means the whole portal
    why: "Labels its outbound records with the platform's label model."
```

- **`commit` is required, and must be a full commit id.** A link always points at the record as it was at that
  commit, never at a branch. The loader refuses a branch name, a tag or a short id.
- **`records`** names decision records by id and capabilities by `capability:<name>`. Omitted, the consumption is of
  the portal as a whole.
- **`why`** is one sentence. It is shown on both sides.
- **The consumed side declares nothing.** It does not need to know its consumers in advance, and gains none of their
  names in its own repository.

**A project with no portal of its own** still declares its consumption. Its `arch-kit.yaml` can hold only the
project's name and `consumes:`, with `portal: none`. The kit then reads and checks the declaration and renders
nothing. This is how an application is listed before it has records of its own.

## 3. The composition file

A composing portal declares, in a composition file beside its `arch-kit.yaml`:

- **components:** each composed project, by name, repository and full commit;
- **consumers:** each project it lists as a consumer, by name, repository and full commit of that project's
  declaration.

The composition file says *where to look*. What a consumer consumes still comes only from that consumer's own
declaration, read at the listed commit. The composing portal does not restate it, so the two cannot disagree.

The names in the composition file are the table of known projects in §1. The decision index check reads its
repository prefixes from the same table, instead of from a list of its own.

## 4. Rendering both sides

At composition time, the build:

1. checks out each component and each listed consumer at its pinned commit;
2. reads every `consumes` entry whose `portal` is the composing portal or one of its components;
3. renders, on each consumed page, a **"Consumed by"** list: the consumer's name, its `why`, and a link to the
   consumer's portal (or its repository, when it has `portal: none`), pinned to the consumer's listed commit;
4. renders, in each consumer's portal that the composition also builds, a **"Consumes"** list: the consumed portal
   and records, each linked at the commit the consumer pinned.

A component's own standalone build does not check out its consumers, so it shows no "Consumed by" list. Its front
page says that its consumers are listed where it is composed, and names that portal when its declaration says one.

## 5. Pins that have moved on

A consumer pins commit C of a record. The composed portal shows the record at a later commit D. At composition time,
the build compares the record at C with the record at D and shows one of:

- **current:** the record is unchanged between C and D;
- **changed since:** the record changed, but its status did not;
- **superseded since:** the record's status at D is Superseded, Withdrawn, Deprecated or Rejected (the declared
  statuses that are not in force);
- **pin not found:** commit C is not in the repository.

Each is shown beside the "Consumed by" entry and beside the consumer's own "Consumes" entry.

- **The consumed side's build never fails on a pin.** It did not write the pin.
- **The consumer's own check reports drift as a warning.** A consumer may declare `drift: fail` on an entry to make
  its own check fail instead. The consumed side is never affected by that setting.

## 6. When an application gets its own portal

An application is listed as a consumer until it has enough records of its own to need a portal. The proposed
threshold: **its fifth accepted decision record**. At that point the application gets its own `arch-kit.yaml` with a
portal. It is then either composed as a component, if its records belong in the composed portal, or stays a consumer
with a portal of its own.

The number is a proposal for the project owner to rule.

## 7. What this does not decide

- How a composed portal is hosted, and who may read it. Phase 1 step 5 declares `portal.hosting` and
  `portal.audience` per portal. A composed portal declares its own, and the strictest audience among its components
  is a lower bound.
- Relabelling and the leak scan across components. Each component's lists apply to its own pages. Whether a
  composing portal adds a list of its own is left open.
- A software development kit or any runtime dependency between projects. This record covers architecture records
  only.

## 8. Build steps, once ruled (sketch)

| Step | What | Proves |
|---|---|---|
| P2-1 | `consumes:` in the declaration, the loader's checks (full sha, known names, `records` that exist at the pin), and `portal: none` | Fixture declarations, accepted and refused |
| P2-2 | The composition file, and the decision index check reading its prefixes from it | The index check's output unchanged for a project with no composition |
| P2-3 | The composed build: components rendered under their names, with the "Consumed by" and "Consumes" lists | The example project, composed with a second fictional project and one fictional consumer |
| P2-4 | Pin states (§5) and `drift: fail` | One fixture per state |

Each step keeps Phase 1's golden comparison for a project that declares no composition: its export stays
byte-identical.

**A pin already exists.** The kit's first consumer pins its citations of a peer repository's records to a commit, and
its decision index check runs that pin check. Phase 1 step S6a carries it over as a declared script
(`decisions.index.foreign[].pin_check`). P2-1's `commit` is the same pin, declared rather than scripted. P2-2 should
replace the script with that declaration, not run beside it, so a project has one pin for each peer, not two.

## Questions for the ruling

1. Is "consumes" declared only by the consumer, with the composition file listing only where to look (§3)? The
   alternative is a registry of consumers in the composition file itself, which moves the declaration to the consumed
   side.
2. Is `portal: none` the right form for a project with records still to come (§2)?
3. Is a warning by default, with `drift: fail` on request, the right default for the consumer's own check (§5)?
4. The threshold for an application's own portal: five accepted decision records (§6)?
