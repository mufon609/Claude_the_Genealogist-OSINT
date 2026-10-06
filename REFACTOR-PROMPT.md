# Refactor prompt: the decision code split by job

Paste this into a fresh Claude Code session opened in this repository, or tell
it: "read REFACTOR-PROMPT.md and do it".

**Model and effort:** Opus 5.5 at high (xhigh if it is offered). The work
changes no behaviour but moves the code the standing rule lives in; a slip in
a move breaks decisions on the owner's live tree, so it wants the strongest
model and a careful pace, not speed.

---

You are splitting this repository's decision code by job, with behaviour
unchanged. Name yourself for the audit trail (`--by "agent:<name> for
user:neural"`) with a name not already in
`sqlite3 -readonly catalog/tree.db "select distinct actor from audit_log"`,
and say it in your reports. Check what this file asks for against the code
and the docs yourself before acting; where you find otherwise, say so.

## Read first

1. `CLAUDE.md` (the hard rules, the commands), then `MEMORY.md` (no bandaids;
   comments describe current code, never history; one home for each rule).
2. `BACKLOG.md` section A, entry **A4**. It is the work's terms of reference
   and says what is left. If A4 is gone from the backlog, the work is done:
   say so and stop.
3. `schema/README.md`'s table of tools, and `tests/checks/unresolved_names.py`
   (the check that every name a tool reads resolves, which guards every move).

## Before you start

- `git status`, `git log -10`, `git worktree list`: nothing else is in flight
  (only `main`, a clean tree). If a worktree or another session is working,
  stop and tell the owner.
- `python3 tools/check.py` green, run with `TMPDIR` set to a folder of your
  own (never delete `/tmp/tree-check-*` by glob: another run may own them).
- Read `git log` for commits that already did part of A4 (a module already
  split out of `tools/conclude.py`) and continue from where they stopped.

## The work, in A4's order

1. **The decision code by job.** Read `tools/conclude.py` and group its
   functions by the job each does (A4 names the jobs). Measure the groups
   with `ast` rather than by eye, including which group calls which. Then
   move one group into its own module under `tools/` per commit. Every file
   that imports a moved name imports it from the module that now owns it. Add
   no re-export layer and no compatibility shim. `tools/conclude.py` stays the
   command every doc names. Break the import cycle between `conclude.py` and
   `facts.py`. Keep each function's text as it is: a move, not a rewrite.
2. **The rule's text by part**, as A4 says: `docs/RESEARCH-WORKFLOW.md` split
   into one file per part, `CLAUDE.md`'s table naming each, every link to a
   moved section updated (grep the repository), each of the rule's functions
   naming in its docstring the paragraph it implements, and a check that fails
   where a named paragraph is gone.
3. **The backlog triaged**, as A4 says: overlapping entries merged, nothing
   that is still true dropped.

A defect you find while moving code is filed in `BACKLOG.md` with what you
saw, not fixed in the move, unless it stops the proof below. Other open
backlog entries are not part of this work.

## The proof for every commit of part 1

Each commit lands only when all of these hold:

- **The moved text is the text.** Every moved function's `ast.dump` equals
  the original's, compared against the parent commit.
- **The checks.** `python3 tools/check.py` is green, and the unresolved-names
  check in it is clean.
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
  pushed commit. Then update A4 in `BACKLOG.md` with what is done and what is
  left, commit and push that, and tell the owner. The next session starts
  from this file again.
- **Finishing:** update `README.md`, `CLAUDE.md` and `schema/README.md`
  wherever they name where a function or rule lives. Delete A4 from
  `BACKLOG.md` and delete this file in the closing commit. Report to the
  owner, in words and without scores:
  - each new module and its job;
  - what each proof showed;
  - every defect you filed.

You may do the moves yourself or brief subagent workers in their own
worktrees. Every module touches `conclude.py`, so run them one at a time.
Review each yourself with the proof above before it lands.
