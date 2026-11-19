#!/usr/bin/env bash
# Index-drift checks for a decisions directory.
#
# ONE COPY, run by both CI and humans. The register index points here rather
# than repeating the commands, because a documented copy and a CI copy are two
# things to keep in sync — which is the exact drift these checks exist to
# catch. Do not inline them into the workflow.
#
#   python -m arch_kit check_decision_indexes
#
# This script is run by check_decision_indexes.py, which reads the names below
# from the declaration (`decisions.index`), exports them, and runs the script
# from the declared decisions directory. It is not meant to be called directly.
#
#   IDX_DIRNAME   the decisions directory's own name, for messages
#   IDX_REGISTER  the register index file: one row per register id
#   IDX_README    the document index: every indexed document is named in it
#   IDX_HOMES     globs, space-separated: where register ids are declared, and
#                 their status tokens
#   IDX_INDEXED   globs, space-separated: each document matching one must be
#                 named in IDX_README
#   IDX_LOCAL     the local prefix: `PREFIX:<record id>` must resolve here
#   IDX_FOREIGN   one line per foreign prefix, in order: the prefix, a tab,
#                 then the pin check's path relative to the decisions
#                 directory (empty for none)
#   IDX_ROOT      the repository root, relative to the decisions directory
#   IDX_RECORD_PREFIX, IDX_RECORD_DIGITS   a decision record id is PREFIX-<digits>
#                 and its file PREFIX-<digits>-<slug>.md (default ADR, 4)
#   IDX_RECORD_FILE_PREFIX   0 when a record file is <digits>-<slug>.md, with no prefix (default 1)
#   IDX_ID_LETTERS, IDX_ID_MIN, IDX_ID_MAX   a register id is that many capital
#                 letters, a hyphen, then MIN to MAX digits (default 2, 1, 2)
#
# Exit 0 = clean. Exit 1 = drift, with the specifics printed.
#
# WHAT THESE PROVE, AND WHAT THEY DO NOT
#   check 1  every register ID has an index row, and every row is a real ID
#   check 2  every indexed document is referenced by the document index
#   check 3  every row's status equals its home's declared token, exactly
#   check 4  every row's home HAS a token (so check 3 cannot be skipped by
#            absence — absence answering as agreement is the disease this
#            tooling exists to fight)
#
#   NOT checked: whether a status is TRUE. Check 3 proves the index AGREES
#   with the home; both can be wrong together. Only a human reading the home
#   document establishes truth, and the clean-run output says so out loud.
#
#   Status is compared, not inferred. It used to be prose, and every attempt
#   to pattern-match it produced both false positives and false negatives —
#   register blocks vary in length, so no context window is correct. A check
#   tuned until it passes is a check whose green means nothing. The fix was
#   to declare the property, not to write a better regex.
#   The status-token design is recorded in the project's own decision corpus.
set -uo pipefail

: "${IDX_DIRNAME:?}" "${IDX_REGISTER:?}" "${IDX_README:?}" "${IDX_HOMES:?}" "${IDX_INDEXED:?}"
: "${IDX_LOCAL:?}" "${IDX_ROOT:?}"
IDX_FOREIGN="${IDX_FOREIGN:-}"
# The grammar of the ids, from the declaration; the defaults are the original fixed forms.
rp="${IDX_RECORD_PREFIX:-ADR}"
rd="${IDX_RECORD_DIGITS:-4}"
# A record file is PREFIX-<digits>-<slug>.md, or <digits>-<slug>.md when IDX_RECORD_FILE_PREFIX is 0.
rfp="$rp-"; [ "${IDX_RECORD_FILE_PREFIX:-1}" = 0 ] && rfp=""
idlet="[A-Z]{${IDX_ID_LETTERS:-2}}"
idnum="[0-9]{${IDX_ID_MIN:-1},${IDX_ID_MAX:-2}}"
recform="$rp-$(printf '%*s' "$rd" '' | tr ' ' N)"
fail=0

# --- scope, derived rather than listed --------------------------------------
# REGISTER HOMES are enumerated from the directory. An earlier version named
# four decision records literally, so a register introduced in a later record
# was invisible to checks 3 and 4 — the third instance of scope-as-literal-list
# in that project. Same fix each time: ASK THE DIRECTORY, not the author's
# memory of it.
homes_files=$(ls $IDX_HOMES 2>/dev/null)

# REGISTER PREFIXES are derived from declaration sites in those homes — both
# shapes: a bolded heading (`**UD-7 — …`) and a table row (`| **GD-01** |`).
#
# Deliberately NOT a generic [A-Z]{2}-[0-9]+ scan over prose. In this domain
# that pattern also matches platform designations — UH-60, CH-47, AH-64, MQ-9 —
# and a check that demands an index row for "AH-64" is a false-positive
# generator whose failures teach people to ignore it. None appear in the
# corpus today; the point is that they legitimately could.
#
# Also deliberately not scanned from plans or the document index: a plan that
# describes the status-token design contains an EXAMPLE row, and an example is
# not a declaration.
prefixes=$( { grep -ohE "^\*\*${idlet}-${idnum} —" $homes_files
              grep -ohE "^\| \*\*${idlet}-${idnum}\*\* \|" $homes_files
            } 2>/dev/null | grep -oE "$idlet" | sort -u | paste -sd'|' -)
if [ -z "$prefixes" ]; then
  echo "FAIL: no register prefixes found — the derivation is broken, not the corpus"
  exit 1
fi

# --- check 1: IDs <-> index rows -------------------------------------------
# The exclusion of the register index is LOAD-BEARING, not tidiness. Scanning *.md
# would include the index in its own corpus, so every row would vouch for
# itself and the phantom-row direction could never fail. A verification that
# includes its own subject in its evidence is not a verification.
corpus=$(grep -ohE "\b($prefixes)-${idnum}\b" \
           $(ls *.md | grep -vxF "$IDX_REGISTER") | sort -u)
rows=$(grep -ohE "^\| ($prefixes)-${idnum} " "$IDX_REGISTER" \
         | tr -d '| ' | sort -u)

missing=$(comm -23 <(echo "$corpus") <(echo "$rows"))
phantom=$(comm -13 <(echo "$corpus") <(echo "$rows"))

if [ -n "$missing" ]; then
  echo "FAIL: register IDs with no row in $IDX_REGISTER:"
  echo "$missing" | sed 's/^/    /'
  fail=1
fi
if [ -n "$phantom" ]; then
  echo "FAIL: rows in $IDX_REGISTER whose ID exists nowhere else:"
  echo "$phantom" | sed 's/^/    /'
  echo "    (a renamed or deleted ID, or a typo in the row)"
  fail=1
fi

# --- check 2: every document is indexed ------------------------------------
# Blind spot of check 1: a whole document can go unlisted without affecting
# any ID. First run of this found ELEVEN, including the two most-cited files
# in the corpus.
unindexed=""
for f in $IDX_INDEXED; do
  [ -e "$f" ] || continue
  grep -q "$f" "$IDX_README" || unindexed="${unindexed}    ${f}"$'\n'
done
if [ -n "$unindexed" ]; then
  echo "FAIL: documents not referenced by $IDX_DIRNAME/$IDX_README:"
  printf '%s' "$unindexed"
  fail=1
fi

# --- checks 3 & 4: declared status tokens ----------------------------------
# Status used to be prose, and every attempt to infer it by pattern produced
# both false positives and false negatives — no context window is correct
# because register blocks vary in length. So it is DECLARED now, and this is
# an exact string comparison with no window and no heuristic.
#
# Two homes, one grammar:
#   table  — the Status COLUMN of a register's table (a `| **GD-01** |` row)
#         is the token. A second token there would be two truths.
#   others — a `Status: …` line immediately above the row's **ID — heading.
home_status() {
  # table-shaped rows: | **GD-01** | … | … | open |
  sed -nE "s/^\| \*\*(($prefixes)-${idnum})\*\* \|.*\| ([^|]*) \|\$/\1\t\3/p" $homes_files \
    | sed -E 's/[[:space:]]+$//'
  # prose rows: a `Status: …` line, then the **ID — heading it labels.
  # `prefixes` is passed in with -v; awk is single-quoted, so a shell variable
  # written inline here would silently be the literal string '$prefixes' and
  # match nothing — a scope bug that would look exactly like "no rows found".
  awk -v pre="$prefixes" '
    /^`Status: / { s=$0; sub(/^`Status: /,"",s); sub(/`$/,"",s); pending=s; next }
    $0 ~ "^\\*\\*(" pre ")-[0-9]+ —" {
      if (pending != "") {
        match($0, "(" pre ")-[0-9]+")
        print substr($0,RSTART,RLENGTH) "\t" pending
        pending=""
      }
    }
  ' $homes_files
}

index_status() {
  sed -nE "s/^\| (($prefixes)-${idnum}) \|.*\| ([^|]*) \|\$/\1\t\3/p" "$IDX_REGISTER" \
    | sed -E 's/[[:space:]]+$//'
}

home_status | sort > /tmp/.dec_homes.$$
index_status | sort > /tmp/.dec_idx.$$
trap 'rm -f /tmp/.dec_homes.$$ /tmp/.dec_idx.$$' EXIT

# Both checks in one awk pass, exact field comparison — no regex against
# prose, no window, nothing to tune.
#
# check 4 runs first in effect: a row whose home carries NO token would
# otherwise drop out of the comparison silently — absence answering as
# agreement, which is the exact disease this tooling exists to fight.
status_report=$(awk -F'\t' '
  NR==FNR { home[$1]=$2; next }
  { idx[$1]=$2 }
  END {
    for (id in idx) {
      if (!(id in home))
        print "FAIL: " id " has no declared Status token in its home document"
      else if (home[id] != idx[id])
        print "FAIL: " id " status disagrees — home says \x27" home[id] "\x27, index says \x27" idx[id] "\x27 (the home is authoritative; fix the index)"
    }
  }
' /tmp/.dec_homes.$$ /tmp/.dec_idx.$$ | sort)

if [ -n "$status_report" ]; then
  printf '%s\n' "$status_report"
  fail=1
fi


# ---------------------------------------------------------------------------
# CROSS-REPO CITATIONS — ADR numbers can name two different documents
# ---------------------------------------------------------------------------
# `LOCAL:ADR-0029` and `FOREIGN:ADR-0029` are different decisions (ADR is the
# declared record prefix, and 4 its digits). An unqualified number is therefore already ambiguous, and a convergence of
# corpora will only add more of them.
#
# THE CONVENTION IS LOCALITY: an unqualified `ADR-NNNN` means THIS repo, which
# is what the existing references already mean and why they are not being
# rewritten. A reference to another corpus MUST carry its prefix, because
# that is the one case the reader cannot infer.
#
# WHAT THIS CAN AND CANNOT CHECK, stated rather than implied:
#   * an unknown prefix          -> a finding; the vocabulary is closed
#   * `LOCAL:ADR-NNNN`           -> must resolve to a document HERE
#   * `FOREIGN:ADR-NNNN`         -> form checked, and, where the declaration
#                                   names a pin check for that prefix, PINNED:
#                                   the citing ADR carries a Cites line at a
#                                   sha that is a prefix of the sha the
#                                   project pins that repository at
#
# This script still cannot see the other repo. A checker that reported a
# foreign citation as "verified" here would be asserting something it has
# no access to -- the same shape as a check that cannot fail. So the pin is
# checked here, and that each cited file EXISTS at the pin is checked by a CI
# fetch, which needs the network.
# Set PINS_OUT to a file to receive the pin list that the fetch reads.
foreign_prefixes=$(printf '%s\n' "$IDX_FOREIGN" | cut -f1 | grep -v '^$')
KNOWN_REPOS="$IDX_LOCAL"
known_list="$IDX_LOCAL"
for fp in $foreign_prefixes; do
  KNOWN_REPOS="$KNOWN_REPOS|$fp"
  known_list="$known_list, $fp"
done

# NO word-boundary escape IN THIS PATTERN, deliberately. An earlier version
# carried one and a layer of quoting turned it into a literal BACKSPACE byte,
# so the search matched nothing and the summary reported "0 prefixed, all
# prefixes known" -- a clean pass over a query that could not match, in a
# checker whose whole job is catching that shape. The unanchored pattern is
# equivalent here (verified against the corpus: same two hits) and has nothing
# to mis-transcribe.
xrefs=$(grep -ohE "[a-z][a-z0-9-]*:$rp-[0-9]{$rd}" *.md 2>/dev/null | sort -u)

bad_prefix=$(printf '%s\n' "$xrefs" | grep -vE "^($KNOWN_REPOS):" | grep -v '^$')
if [ -n "$bad_prefix" ]; then
  echo "FAIL: cross-repo citations with an unrecognised prefix:" >&2
  printf '%s\n' "$bad_prefix" | sed 's/^/    /' >&2
  echo "      Known repos: $known_list. An unqualified $recform means" >&2
  echo "      THIS repo by locality and needs no prefix." >&2
  fail=1
fi

missing_local=""
for ref in $(printf '%s\n' "$xrefs" | grep -E "^$IDX_LOCAL:$rp-[0-9]{$rd}$"); do
  num="${ref#$IDX_LOCAL:$rp-}"
  ls ${rfp}${num}-*.md >/dev/null 2>&1 || missing_local="${missing_local}    ${ref}"$'\n'
done
if [ -n "$missing_local" ]; then
  echo "FAIL: $IDX_LOCAL:-prefixed citations with no matching document here:" >&2
  printf '%s' "$missing_local" >&2
  fail=1
fi

# --- cross-seam pins, one entry per foreign prefix ---------------------------
# `foreign_summary` collects each entry's clean-run lines; they are printed
# only when every check passed, as before.
foreign_summary=""
pins_all=""
while IFS=$'\t' read -r fp fpin; do
  [ -n "$fp" ] || continue
  foreign=$(printf '%s\n' "$xrefs" | grep -cE "^$fp:$rp-" || true)
  if [ -z "$fpin" ]; then
    foreign_summary="${foreign_summary}  ${foreign:-0} ${fp}:-prefixed reference(s); no pin check is declared for this prefix."$'\n'
    continue
  fi
  if ! pins=$("$fpin" "$IDX_ROOT"); then
    echo "FAIL: an $fp citation is not pinned (errors above)" >&2
    fail=1
  fi
  pins_all="${pins_all:+$pins_all$'\n'}$pins"
  foreign_summary="${foreign_summary}  ${foreign:-0} ${fp}:-prefixed reference(s); $(printf '%s\n' "$pins" | grep -c .) Cites line(s), each"$'\n'
  foreign_summary="${foreign_summary}  pinned at $(printf '%s\n' "$pins" | awk 'NR==1{print substr($3,1,7)}'). That each cited file exists"$'\n'
  foreign_summary="${foreign_summary}  at the pin is checked by the workflow's fetch, not here: this repo"$'\n'
  foreign_summary="${foreign_summary}  cannot see that corpus."$'\n'
done <<EOF
$IDX_FOREIGN
EOF
if [ -n "${PINS_OUT:-}" ]; then printf '%s\n' "$pins_all" > "$PINS_OUT"; fi

if [ "$fail" -eq 0 ]; then
  echo "decision indexes clean: $(echo "$corpus" | wc -l | tr -d ' ') IDs, all documents indexed, all statuses agree"
  echo "note: 'agree' means the index matches the home, NOT that either is true."
  echo "cross-repo citations: $(printf '%s\n' "$xrefs" | grep -c . || true) prefixed, all prefixes known,"
  echo "  all $IDX_LOCAL:-prefixed ones resolve here."
  printf '%s' "$foreign_summary"
fi
exit "$fail"
