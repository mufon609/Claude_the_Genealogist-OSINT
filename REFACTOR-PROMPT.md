# Refactor prompt: the decision code split by job, the tools in layers

Paste this into a fresh Claude Code session opened in this repository, or tell
it: "read REFACTOR-PROMPT.md and do it".

**Model and effort:** Opus 5.5 at high (xhigh if it is offered). The work
changes no behaviour but moves the code the standing rule lives in; a slip in
a move breaks decisions on the owner's live tree, so it wants the strongest
model and a careful pace, not speed.

---

You are splitting this repository's decision code by job and putting its tools
in layers, with behaviour unchanged. Name yourself for the audit trail (`--by "agent:<name> for
user:neural"`) with a name not already in
`sqlite3 -readonly catalog/tree.db "select distinct actor from audit_log"`,
and say it in your reports. Check what this file asks for against the code
and the docs yourself before acting; where you find otherwise, say so.

## Read first

1. `CLAUDE.md` (the hard rules, the commands), then `MEMORY.md` (no bandaids;
   comments describe current code, never history; one home for each rule).
2. `BACKLOG.md` section A, entries **A4** and **A5**. They are the work's
   terms of reference and say what is left. If both are gone from the
   backlog, the work is done: say so and stop.
3. `schema/README.md`'s table of tools, `tests/checks/unresolved_names.py`
   (the check that every name a tool reads resolves, which guards every move)
   and `tests/checks/import_cycles.py` (the layers below, measured).

## The target: the tools in layers

Each module imports from its own layer or the layers below it, never from a
layer above, and no import closes a cycle. Inside a layer the modules may
import one another (the decisions read the rule; `turn` runs `run_step`),
so within a layer the cycle check is the guard. The table is data at the
top of `tests/checks/import_cycles.py`, where layer 4 names the split's
modules `rule`, `decisions`, `copies`, `merges`, `reconsider` and
`conflicts`; a module added to `tools/`, or named otherwise by the split,
takes its row there in the commit that adds it.

| Layer | Modules |
|---|---|
| 0 | `treelib`, `forms` |
| 1 | `catalog` (read-only reads; the name and place rules) |
| 2 | `extract`, `match`, `households`, `resolve_places`, `footprint`, `checklist`, `connectors` (readers and comparers) |
| 3 | `log_search`, `plan`, `attach`, `fetches` |
| 4 | the modules split from `conclude.py`: the rule (points, identity, the evidence classes), decisions (`decide`, `link_family`, `assert_facts`, aliases, `place`, the commands on the owner's word), copies (`carry`, `join_copies`, `copies_on_word`), merges, reconsider (`rematch`, `withdraw`, `reconsider`), conflicts (`rule_conflicts`, `resolve`, `reopen`, `classes_decide`); and `facts`, `proof`, `cards`, `overview` |
| 5 | entry points: the `conclude.py` command line, `turn`, `turns`, `queue`, `run_step`, `run_task`, `tree`, `ingest_gedcom`, `initdb`, `backup`, `tombstone`, `cite`, `backfill_aliases`, `attach_inbox`, `check`, `app/person/server.py` |

Three modules the owner's list leaves out are placed by what they import and
what imports them: the `tools/connectors/` package (it imports `treelib` and
`catalog` alone) in layer 2, `attach_inbox` and `check` (commands) in layer 5.

**The measurement**, `python3 tests/checks/import_cycles.py`, on 9 Oct 2026:
409 elementary cycles, every one through an import deferred inside a
function (with the module-level imports alone the graph has none), all
inside one strongly connected set of fifteen modules: `attach`,
`backfill_aliases`, `catalog`, `checklist`, `conclude`, `connectors`,
`extract`, `facts`, `footprint`, `households`, `log_search`, `match`, `plan`,
`proof`, `resolve_places`. The shortest are `attach`/`extract`,
`attach`/`match`, `catalog`/`match`, `conclude`/`facts`, `conclude`/`proof`.
Ten pairs of modules import upward, and with those ten imports gone no cycle
is left. Imports deferred inside functions: `check` 39, `conclude` 24,
`extract` 8, `connectors` 7, `initdb` 7, `match` 5, `attach` 3, `households`
3, `plan` 3, `proof` 3, `log_search` 2, `run_step` 2, `catalog` 1, `overview`
1, `tree` 1. Every report of A4 and A5 prints the script's output as it
stands after the commit: the cycles, the upward imports and the deferred
imports.

**What A4's split closes.** Four of the upward imports are names that leave
`conclude.py` for a layer-4 module: `facts` (`MARKS`, `answer_questions`,
`settle_people`, `statement_people`, in `evidence_rows` and `decide_fact`),
`cards` (`rule_accepts`, `sibling_home`), `overview` (`trusted_evidence`) and
`proof` (`CONFLICT_AXIS`, `classes_decide`, `conflict_lines`). Two cycles need
more than the split:

- `conclude`/`facts`: only `conclude.main` imports `facts` (`decide_fact`,
  `evidence_rows`, `KEY_FACTS`, `claimed_parts`, `fact_status`). It is broken
  when the command line is all that imports `facts` and no layer-4 module
  `facts` imports from imports it back.
- `conclude`/`proof`, which the split turns into conflicts and `proof`
  importing each other inside layer 4: `classes_decide` imports `proof`'s
  `axis_value`, `order`, `record_info`, `same_value`, `sides`, `specificity`,
  `subject_statements` and `words`, and `kept_agrees` its `same_value`. The
  move: those helpers, the comparison of a conflict's sides, go to the
  conflicts module, and `proof` imports them from there.

**The moves the layering requires** (A5), each a module the graph puts in two
layers, with the function that causes it:

1. `catalog` (1) imports `match` (2): `Catalog.disagreements` reads
   `match.middle_differs`. The middle-name rule moves to `catalog`, with the
   name rules, and `match` imports it from there.
2. `match` (2) imports `log_search` (3): `match.persons_for` reads
   `log_search.REOPENED`, the note prefix of a reopen's log row. The log's
   note prefixes (`REOPENED`, and `HOUSEHOLD` and `ON_WORD` beside it, which
   `overview` reads) move to `catalog`, which reads the log for every layer.
3. `extract` (2) imports `conclude` at its top level: `extract.extract`
   carries the decisions on a page's earlier reading to the new one
   (`join_copies`, `carry`, `settle_carried`), and `extract.carry_links`
   writes them (`assert_facts`, `link_family`, `link_people`). A reader
   writes decisions. The carry moves to the copies module, which reads the
   page through `extract.extract` and then carries; every caller that reads a
   page for a tree (`run_step`, `attach`, the screen, the harness) calls it
   there.
4. `extract` (2) imports `conclude` and `attach` in `extract.read`, and `match`
   (2) imports `attach` in `match.main`: the command lines of
   `tools/extract.py` and `tools/match.py` (the owner's word through
   `attach.on_word`, the rule through `match_record`) are entry points in a
   reader's file. Each moves as `conclude.py`'s does: the command keeps its
   file and the name the docs give it, the reader's functions move to a
   module of their own that takes the reader's row in the table, and every
   importer imports from that module.
5. `attach` (3) imports `conclude`: `attach.attach` ends by running
   `match_record`, the matcher and the rule, on the reading it made. The
   arrival (`attach.attach`, `attach_each`, `attach_inbox`, which archive a
   file, read it and decide) moves to layer 4 beside `match_record`, with
   `fetches.collect`, which runs it for a browser session's saves; `attach`
   keeps what places a file (`identity`, `steps_for`, `on_word`,
   `cite_on_word`, `saved_steps`, `line`, `inbox_files`, `failed`).
6. The decisions import `backfill_aliases` (5): `write_name_alias`,
   `decide_place`, `same_personas` and `write_resolution` read its
   `classify`, `clean` and `key`. The alias rule moves to `catalog`, with the
   name rules, and `backfill_aliases` and `check` import it from there.

A move moves a function's text unchanged; where a move changes a call site
(3, 5), the side-by-side proof below is what shows the behaviour unchanged.

## Before you start

- `git status`, `git log -10`, `git worktree list`: nothing else is in flight
  (only `main`, a clean tree). If a worktree or another session is working,
  stop and tell the owner.
- `python3 tools/check.py` green, run with `TMPDIR` set to a folder of your
  own (never delete `/tmp/tree-check-*` by glob: another run may own them).
- `python3 tests/checks/import_cycles.py`: its output is where your work
  starts, and your first report prints it.
- Read `git log` for commits that already did part of A4 or A5 (a module
  already split out of `tools/conclude.py`, a helper already moved down) and
  continue from where they stopped.

## The work, in A4's order, then A5

1. **The decision code by job.** Read `tools/conclude.py` and group its
   functions by the job each does (A4 names the jobs). Measure the groups
   with `ast` rather than by eye, including which group calls which. Then
   move one group into its own module under `tools/` per commit. Every file
   that imports a moved name imports it from the module that now owns it. Add
   no re-export layer and no compatibility shim. `tools/conclude.py` stays the
   command every doc names. Break the import cycles between `conclude.py` and
   `facts.py` and between `conclude.py` and `proof.py`, as the target above
   says. Keep each function's text as it is: a move, not a rewrite.
2. **The rule's text by part, with stable identifiers**, as A4 says:
   `docs/RESEARCH-WORKFLOW.md` split into one file per part, `CLAUDE.md`'s
   table naming each, every link to a moved section updated (grep the
   repository). Every clause of the rule that code implements opens with a
   stable identifier in bold brackets, `**[rule.points.2]**`: a dotted name of
   the part and a serial within it, never renumbered (a clause removed leaves
   its number unused; a clause added takes the next). A function that
   implements a clause cites its identifier in its docstring. The check
   `tests/checks/rule_ids.py`, written with this part and run by
   `tools/check.py`, fails where a docstring cites an identifier no doc holds,
   and lists under `--verbose` the identifiers no docstring cites.
3. **The tools in layers**, as A5 says: each move above, one module a commit,
   with the same proof. The cycle check (`tests/checks/import_cycles.py`)
   joins `tools/check.py` in A5's closing commit, once it passes: never
   before, and never with an allowlist.

A defect you find while moving code is filed in `BACKLOG.md` with what you
saw, not fixed in the move, unless it stops the proof below. Other open
backlog entries are not part of this work.

## The proof for every commit of A4 part 1 and of A5

Each commit lands only when all of these hold:

- **The moved text is the text.** Every moved function's `ast.dump` equals
  the original's, compared against the parent commit.
- **The checks.** `python3 tools/check.py` is green, and the unresolved-names
  check in it is clean. `python3 tests/checks/import_cycles.py` names no cycle
  or upward import the commit's parent did not.
- **Old and new code side by side.**
  - Make two identical scratch copies of the live catalog:
    `sqlite3 -readonly catalog/tree.db ".backup '<scratch>/catalog/tree.db'"`
    for each, plus `catalog/.active-tree` and a copy of `derivatives/geocode`
    in each. Link `archive/` only when nothing you run writes it; copy it
    otherwise.
  - Run the parent commit's code against one and yours against the other,
    with `DATA_ROOT=<scratch>`:
    - `tools/cards.py --all`
    - the whole `tools/conclude.py reconsider --dry-run`
    - `tools/queue.py --all`
    - `tools/proof.py` for the home person and four people of their line
  - The outputs must be byte for byte identical.
- **Clean up.** Delete the scratch copies when done: they hold a family's
  data.

The refactor changes no data. Never write the live catalog.

## Committing, stopping, finishing

- **Committing:** commit each finished piece directly to `main`, staged by
  explicit path, the message saying what the code now does (match
  `git log -15`'s style). Push it at once (`CLAUDE.md` rule 9), so a session
  that stops leaves `main` whole.
- **Stopping:** if your usage or context runs low, stop only after a green,
  pushed commit. Then update A4 or A5 in `BACKLOG.md` with what is done and
  what is left, commit and push that, and tell the owner. The next session starts
  from this file again.
- **Finishing:** update `README.md`, `CLAUDE.md` and `schema/README.md`
  wherever they name where a function or rule lives. Delete A4 from
  `BACKLOG.md` when its parts are done; in A5's closing commit wire
  `tests/checks/import_cycles.py` into `tools/check.py`, delete A5 and delete
  this file. Report to the owner, in words and without scores:
  - each new module and its job;
  - what each proof showed;
  - the output of `tests/checks/import_cycles.py` after each commit;
  - every defect you filed.

You may do the moves yourself or brief subagent workers in their own
worktrees. Every module touches `conclude.py`, so run them one at a time.
Review each yourself with the proof above before it lands.
