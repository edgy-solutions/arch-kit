# Design record: composed portals and the "consumer of" relation

**Status: proposed, with proposed answers to its questions, pending the project owner's ruling. Nothing is built.**

Proposes a decision: one portal can compose the records of other projects, and any project can declare that it
consumes a portal or part of one. Consumption is declared by the consumer only, is rendered on both sides, and every
link is pinned to a commit.

Phase 2 of the kit. It builds on Phase 1 (`v0.1.0`), where one project's records render as one portal from one
declaration (`arch-kit.yaml`) through a loader the project supplies. This record decides the shape of the relations,
the declaration, how a composed export keeps each component's own words, and how its names are checked. The build
steps at the end are a sketch, to be specified once this is ruled.

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
  commit, never at a branch. The kit's declaration check refuses a branch name, a tag or a short id (exit 2), as it
  refuses any other malformed key. The project's loader is not involved: it reads records, not the declaration.
- **Why not a tag.** A tag can be moved, and a record pin must not move. This is different from pinning the kit
  itself, where a release tag names a version of the tools, not a record.
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
  declaration;
- **list slots:** for each component, a named slot for its relabel list and one for its barred list (§8). The
  file names the slots, never the lists, which are passed by path when the build runs.

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

## 7. Each component keeps its own declaration

A composed portal is several projects' records in one export. It is not one merged project. Each component is read
and rendered as it is in its own standalone build:

- **Its own loader.** The composed build reads each component through the loader that component's `arch-kit.yaml`
  names, at the pinned commit. No component writes a second set of records for the composition, and the composing
  portal holds none of its components' formats.
- **Its own words.** Labels, phases with their earning rules, statuses, view kinds and the term dictionary come from
  the component's declaration. A component's pages show its phases and statuses in its own words, with its own badges.
- **Nothing is merged across components.** The kit does not map one component's phases or statuses onto another's,
  and does not rank capabilities across components. A page that lists every component, such as the composed front
  page, shows each row in that component's words, under the component's name.
- **The composing portal's own declaration** covers only what belongs to the composition: its name, its hosting and
  audience (§8), its composition file (§3), and any pages of its own.

**Whose code runs.** The composed build runs each component's loader, at the commit the composition file pins. The
composing portal trusts the components it lists, as it trusts the commits it pins. A consumer's declaration is read as
data only: the build reads its `consumes:` entries and never imports its loader. A consumer with `portal: none` has no
loader at all.

## 8. Names, lists and audience in a composed export

Phase 1's rule applies to the composed export as a whole: relabelling and the leak scan run on the rendered HTML,
and the export declares its hosting and audience.

- **Each component's lists apply to its pages.** A component's relabel list rewrites that component's pages, as in its
  standalone build. Its names are relabelled the same way wherever they appear.
- **The scan runs on the composed file with every list.** After the composed render, the leak scan runs on the whole
  file with the union of every component's relabel and barred lists, and the composing portal's own lists. A
  component's private name in another component's page, or in a "Consumed by" entry, is caught there. A leak writes no
  file, and the message names the list, the rule number and a count, never the value.
- **The lists are passed by path, as in Phase 1.** The composition file names each component's list *slots*, never
  their contents. Whoever runs the composed build passes a file for each slot. A component's private lists stay with
  that component's owner, and are never committed to the composing repository.
- **Public CI uses the sample lists by design.** A composed build in public CI runs with each component's sample lists.
  The relabel with real names runs only locally, where the private lists are, and a CI pass is never reported as a
  real-name check.
- **Audience.** The composed portal declares its own `portal.hosting` and `portal.audience`. A composed portal whose
  audience is `public` may compose only components whose own audience is `public`. Composing a `private` component into
  a `public` portal is an input error (exit 2), before any work. A `private` composed portal may compose either.
- **Consumers and audience.** A "Consumed by" entry shows the consumer's name, its `why` and a link. When the consumer's
  own portal is `private`, or it has `portal: none`, the entry links to its repository and shows nothing else from it.

## 9. What this does not decide

- How a `static-site` portal is published. The Phase 1 Action uploads a CI artifact only, and publishing a site is a
  later step for single and composed portals alike.
- Whether a consumer's project-supplied reader is needed for the generated data-exchange section. That is a separate
  Phase 2 item, decided by what a second project's adoption shows.
- A software development kit or any runtime dependency between projects. This record covers architecture records
  only.

## 10. Build steps, once ruled (sketch)

| Step | What | Proves |
|---|---|---|
| P2-1 | `consumes:` in the declaration, the kit's declaration checks (full sha, known names, `records` that exist at the pin), and `portal: none` | Fixture declarations, accepted and refused |
| P2-2 | The composition file, and the decision index check reading its prefixes from it | The index check's output unchanged for a project with no composition |
| P2-3 | The composed build: each component through its own loader and declaration, under its name, with the "Consumed by" and "Consumes" lists | The example project, composed with a second fictional project whose phases and statuses differ, and one fictional consumer |
| P2-4 | Lists and audience in the composed build (§8): list slots, the union scan, the public-audience refusal | A leak planted in each component, caught in the composed file; a private component refused by a public portal |
| P2-5 | Pin states (§5) and `drift: fail` | One fixture per state |

Each step keeps Phase 1's golden comparison for a project that declares no composition: its export stays
byte-identical.

**A pin already exists.** The kit's first consumer pins its citations of a peer repository's records to a commit, and
its decision index check runs that pin check. Phase 1 step S6a carries it over as a declared script
(`decisions.index.foreign[].pin_check`). P2-1's `commit` is the same pin, declared rather than scripted. P2-2 should
replace the script with that declaration, not run beside it, so a project has one pin for each peer, not two.

## Questions for the ruling

Each question names the alternative.

1. Is "consumes" declared only by the consumer, with the composition file listing only where to look (§3)? The
   alternative is a registry of consumers in the composition file itself, which moves the declaration to the consumed
   side.
2. Is `portal: none` the right form for a project with records still to come (§2)? The alternative is a separate,
   smaller file for consumption only.
3. Is a warning by default, with `drift: fail` on request, the right default for the consumer's own check (§5)? The
   alternative is failing by default, with `drift: warn` on request.
4. Is five accepted decision records the threshold for an application's own portal (§6)? The alternative is no fixed
   number: the application's owner decides.
5. Does the composed build re-render each component from its sources, through its own loader (§7)? The alternative is
   to stitch together each component's already-checked export. That runs no component code, but it cannot add the
   "Consumed by" lists or relabel across pages, and the composed file would hold several page shells.
6. Does the leak scan run on the composed file with the union of every component's lists, passed by path into
   declared slots (§8)? The alternative is to trust each component's own scan and run only the composing portal's
   lists. That misses a name that crosses from one component's pages into another's.
7. Is a `private` component in a `public` composed portal refused outright (§8)? The alternative is to leave it out,
   with a warning.

## Proposed answers, pending the ruling

These are recommendations, not the ruling. Question 4 is left to the project owner.

1. **Yes, the consumer declares.** The project owner has already ruled this, on 2026-11-16.
2. **Yes, `portal: none`.** It is an explicit value, so a missing portal is always declared and never assumed.
3. **Yes, a warning by default.** Drift never fails the consumed side's build. A consumer can declare itself strict
   with `drift: fail`, and then its own build fails on its own stale pin.
4. **The project owner's question.** The recommendation is that five accepted decision records be guidance, not a
   rule the kit enforces.
5. **Re-render each component from its sources.** One kit version then renders everything, and every check runs on
   the whole export. Stitching finished exports would mix kit versions, and would trust each component's own build.
   The cost is that the composed build needs read access to every component's repository.
6. **Yes, every component's lists combined.** A name barred in one component is barred across the whole portal.
7. **Yes, refused outright.** It fails closed, and that includes the component's name: no part of a private
   component, not even its name, appears in a public portal.
