# Design record: the alignment record

**Status: proposed, with proposed answers to its questions, pending the project owner's ruling. Nothing is built.**

Proposes a decision: the kit gets one general record type for comparing a project with external references, such as
a reference architecture, a standard or a framework. The comparison is made element by element, and each comparison
carries its evidence. A record can cite more than one reference. The export renders a coverage view for each
reference. Each reference's terms decide how much of it a portal may show.

## 1. What it records

A project already says, in prose and in standards tables, that it "aligns with" some external document. Those
claims have three weaknesses:

- They do not say which edition was read, where it came from, or whether it was read in full.
- They do not say which of the reference's elements the project covers, which it covers in part, and which it does
  not cover at all. So a gap is invisible: only the matches get written down.
- Their evidence is prose. Nothing checks that a cited decision record exists.

An alignment record fixes all three. It has two parts.

- **References.** Each reference is named, with its edition, where it was obtained, how much of it was read, and
  its terms. It also carries its element list.
- **Rows.** There is one row for each element of each reference: how closely the project corresponds to it, the
  evidence, and a one-line note.

## 2. The reference

```yaml
references:
  - key: ref-a                      # unique in the record; rows name it
    title: Example Reference Architecture
    edition: "Version 2, 2025"
    identifier: XX-0000              # optional: the publisher's own number
    obtained: "supplied by the project owner, 2026-11-18"   # or a URL
    read: full                       # full | partial | title-only
    read_note: "Appendices 4, 9 and 14 read in full; the rest skimmed"   # required unless read: full
    terms:
      status: public                 # public | unconfirmed | restricted
      basis: "public-disclosure notice on every page"
      cite: "names and paraphrase only; no passages, no figures"
    seed: example-ref-v2             # optional: take the element list from a kit seed (§4)
    elements:                        # optional: elements added here, or the whole list when there is no seed
      - id: ap9-pep
        name: Policy Enforcement Point
        where: "Appendix 9, para 3"
        group: "Appendix 9: roles"
```

- **`where`** cites by section and paragraph. A record never carries a figure or a quoted passage. The `name` is
  the reference's own name for the element. Anything descriptive is the record author's paraphrase, in the row's
  note.
- **`read: title-only`** means the reference is named and nothing more. It has no elements and no rows. That is the
  honest form for a document whose source or terms are not yet confirmed (§6).
- **`terms` is required.** A reference without its terms is refused, because the terms are what decide what may be
  shown (§6).

## 3. The row

```yaml
rows:
  - ref: ref-a
    element: ap9-pep
    correspondence: corresponds      # corresponds | partial | none | not-applicable
    evidence: [ADR-0007, ADR-0012]   # decision ids, repo:ADR-NNNN, or repository paths
    note: "One enforcement point per tier; each asks the decision point and applies the answer."
    owed: ADR-0020                   # optional: the decision that owes the missing part
```

- **Every element gets exactly one row.** A missing row is refused, and so is a second one. That makes the coverage
  complete by construction: a gap is a row that says `none`, not a row that is missing.
- **`evidence` is required** for `corresponds` and `partial`, and it must resolve. A decision id resolves through
  the decision index that the kit already checks. A `repo:ADR-NNNN` resolves through the declared foreign index. A
  path must exist at the checked commit. The rows for `none` and `not-applicable` may carry evidence, but they
  need a `note`.
- **`owed`** names the decision record that commits to closing the gap. It is allowed on `partial` and `none` only.
  It must resolve the same way as evidence.
- **The four values are the only values.** "Planned" is not a correspondence. A planned item is `none` with `owed`.

## 4. Seeds: element lists the kit carries

A seed is a reference's element list, written once in the kit, under `arch_kit/references/<seed>.yaml`, so that
every project comparing itself with that reference uses the same list. A seed holds only:

- each element's `id`, its `name` and its `where`, grouped;
- the reference's title, edition, identifier and terms.

It holds no descriptions, passages or figures.

A record can then name the seed. It can add elements of its own to the seed's list, but it cannot remove any. To
compare against only part of a reference, a record declares `groups: [...]` on the reference, and the rows cover
those groups only. The coverage view prints the groups that were left out, by name.

**The first seed: NATO Data Centric Reference Architecture, Version 2** (AC/322-D(2025)0056), publicly disclosed
under PDN(2025)0031. Its groups, as the project owner set them on 2026-11-18:

| Group | Elements | Where |
|---|---|---|
| Appendix 9: roles | Policy Enforcement Point; Policy Decision Point; Policy Information Point; Policy Administration Point | Appendix 9, para 3 |
| Appendix 4: data-product characteristics | Self-describing and reusable; Domain-centric; Metadata-driven; Interoperability and sharing; Machine-accessible; Lifecycle management; Automated governance; Consumer oriented | Appendix 4, para 12 |
| Appendix 14: planes | Infrastructure; Operational Data; Data Management; Analytical Data | Appendix 14, paras 1–10 |

Question 3 proposes a fourth group from the same appendix: Appendix 9's services. They are cryptographic protection
(para 4), and the four identity, credential and access management services (paras 7–10).

## 5. The coverage view

The export renders one page for each alignment record. For each reference, the page shows:

1. **The reference block:** title, edition, identifier, where it was obtained, read status, and terms.
2. **The coverage table:** one line per group, with the counts of `corresponds`, `partial`, `none` and
   `not-applicable`. It ends with a total line. The score is (`corresponds` + `partial`) out of all the elements,
   less the `not-applicable` ones. The table prints the counts, not a percentage.
3. **The gaps:** each `none` row and each `partial` row, with its note and its `owed` decision when there is one.
4. **The rows:** every row, grouped as the reference groups them. Each evidence id links to its decision page.

A reference with `read: title-only` renders its reference block and one line, "Cited by title only; not compared".
It has no table.

## 6. Terms decide what is shown

The portal's audience (`portal.audience`, already declared) meets each reference's `terms.status`:

| `terms.status` | `private` portal | `public` portal |
|---|---|---|
| `public` | everything | everything |
| `unconfirmed` | everything | **title only.** Elements and rows must be absent from the record, or the build fails, naming the reference |
| `restricted` | everything | **refused.** The build fails, naming the reference |

- **The public rule fails rather than hides.** A public portal fails on an `unconfirmed` reference that has
  elements. It does not quietly drop them. So the record that ships is the record that was written.
- **Where the names live meanwhile.** A project that needs the element names before the terms are confirmed keeps
  them in a private file, outside the repository the portal renders from.
- **Seeds are public by rule.** The kit carries a seed only for a reference whose terms are `public`.

## 7. How the kit reads it

The alignment record is new, and no project has its own format for it. The kit therefore reads it directly, without
going through the loader:

```yaml
files:
  alignment: alignment/              # under paths.root; every *.yaml in it is one record
```

- Validation is by `arch_kit/schema/alignment.schema.json`, with the same validator as the capability record. A
  record that fails is refused at its first error, and the exit code is 2.
- A project that declares no `files.alignment` renders as it does today, byte for byte.

## 8. What this does not decide

- **A crosswalk between two references,** that is, element to element, with no project in between. That is a
  different record (reference against reference). It can come later on the same reference block.
- **Moving a project's existing standards tables onto this type.** Each project proposes that separately, once the
  type is built.
- **Machine-readable exports of the record** (for example, as RDF). Not now.

## 9. Build steps, once ruled (sketch)

| Step | What | Proves |
|---|---|---|
| AL-1 | `alignment.schema.json`, the `files.alignment` key, and the checks in §2–3: terms required, one row per element, evidence and `owed` resolve, `groups` | Fixture records, accepted and refused, one for each rule |
| AL-2 | The first seed (§4), and seed loading with added elements | A fixture record over the seed |
| AL-3 | The coverage page (§5) | A golden page for the fixture; a project without `files.alignment` stays byte-identical |
| AL-4 | The audience rule (§6) | An `unconfirmed` reference with elements, refused by a public portal; a title-only reference, accepted |

## Questions for the ruling

Each question names the alternative.

1. **Does the kit read the record directly** (§7)? The alternative is to read it through the loader, like the
   capability record, at the cost of a loader change in every adopting project.
2. **Is "exactly one row per element" a hard rule** (§3)? The alternative is to allow missing rows and print them
   as "not assessed". That is easier to start with, but it makes a gap invisible again.
3. **Does the first seed include Appendix 9's services,** as well as its roles (§4)? The alternative is roles only,
   as the project owner listed them. Then a project's identity and cryptography evidence has no element to attach
   to unless the project adds its own.
4. **What happens to a second reference whose title contains a word the kit's own name lists bar?** It cannot be
   seeded, or even named, in the kit. The proposed form: the project's own record declares it inline. The
   alternative is to change the kit's lists.
5. **Does a public portal fail on an `unconfirmed` reference that has elements** (§6)? The alternative is to drop
   them with a warning.

## Proposed answers, pending the ruling

These are recommendations, not the ruling.

1. **Directly.** The record has no prior format to adapt, so a loader would only rename the kit's own keys.
2. **Hard.** The point of the type is that gaps are written down.
3. **Include the services, as their own group.** A project that wants roles only declares `groups:`.
4. **Inline in the project's record, with `read: title-only` until its source is confirmed.** The kit's lists stay
   as they are.
5. **Fail.** It is the same fail-closed rule as a private component in a public composed portal.
