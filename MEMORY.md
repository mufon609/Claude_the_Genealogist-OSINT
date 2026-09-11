---
id: meta/memory
type: meta
---

# Contributor memory

Durable behavioral patterns and working knowledge that span sessions and
contributors (human or AI) but don't fit a more specific surface. Kept in
the repo so it travels with a clone. Keep short. Promote entries to a more
specific home when one emerges.

---

## What goes here

- Cross-cutting working patterns that affect how a contributor approaches
  the repo, not what the repo contains.
- Behavioral discipline around session conduct, review shape, and
  recovery from failure modes that don't map cleanly to a single owner doc.
- Pointers to patterns that already live in repo files, when the pointer
  itself is the load-bearing thing a contributor needs to carry between
  sessions.

## What does NOT go here

- What the project is and where things are → `README.md`.
- Project-specific operating rules for an AI contributor → `CLAUDE.md`.
- Accepted design decisions and their rationale → `docs/DATA-ARCHITECTURE.md`,
  `docs/RESEARCH-WORKFLOW.md`, `docs/RESEARCH-CHECKLIST.md`.
- Schema-level field semantics → comments in `schema/catalog.sql`.
- Per-tool behavior → that tool's docstring.
- Deferred work → `BACKLOG.md`.
- Past-work narrative, dated incidents, BACKLOG IDs, commit hashes → git
  log only.

## How to add an entry

One H3 per pattern. Lead with the rule. Add a short `Why` paragraph only
when the rationale is non-obvious from the rule. Skip dates, commit hashes,
and incident references — those belong in git log. When a more specific
home for an entry emerges, promote the entry there and delete the H3 from
this file.

---

## Entries

### Multi-issue reviews split into phases

When a review surfaces 3+ issues on a single artifact, work them in phases.
Address each phase in order; pause for confirmation between phases.

- **Phase 1 — factual correctness.** Wrong values, misspellings,
  mis-linked paths, mis-attributed sources. Self-contained errors; can ship
  independently.
- **Phase 2 — completeness.** Missing items, gaps, under-attribution. The
  artifact works but is thinner than the sources support.
- **Phase 3 — convention.** Schema changes, layout changes, taxonomy
  redefinitions. Can't be fixed at the artifact level; needs consensus and
  typically becomes a BACKLOG entry rather than an in-session change.

Within a phase, log out-of-phase observations rather than mixing fixes
across phases — bundling a Phase 2 item into a Phase 1 commit produces long
diffs that mix self-evident corrections with contested taste calls.

Pre-existing defects discovered during a review get fixed in the same pass
and reported transparently in the summary — not silently left because they
pre-date the session. The "surface as observation, don't fix" reflex is
reserved for convention-level questions and larger architectural items, not
for mechanical issues already in scope.

After each phase, do a verification pass — re-run the tools, re-run checks,
re-read the relevant sections. Treat this as systematic re-review rather
than rubber-stamp confirmation; expect 1–2 items to surface on a legitimate
re-read.

**Why:** Multi-issue reviews that try to address every surfaced item in one
pass produce long diffs mixing clear factual corrections with contested
convention changes. Phasing makes each piece independently reviewable and
lets the contributor halt after Phase 1 if Phase 2 or 3 need more
discussion.

### Lean over bespoke tooling

Before proposing a new script or system, check whether existing
infrastructure — git, the standard library, the schema, an existing tool or
view — already covers the need, and prefer the smaller change. If a proposal
is heavier than the problem, say so and offer the lean alternative.

### NO BANDAIDS, in practice

Any issue found during a review either gets fixed immediately (preferred
for mechanical issues, missing checks, hygiene gaps) or filed in
`BACKLOG.md` for later (design questions, convention-level changes, items
needing consensus). A comment parking the issue (`# known issue: X never
fires under condition Y`) is not a third option. The day-to-day reflexes:

- **Fix the cause, not a backstop.** Fix a failure at its source rather
  than adding a compensating downstream verify/inspect step. And don't add
  — or keep — a check whose only job is to re-confirm an issue already fixed
  at the source; a review may call it "coverage," but it is dead weight.
- **Defer real work to BACKLOG, never verbally.** When a fix is too big for
  the session, add it to `BACKLOG.md` immediately and say you filed it — a
  chat-only "I'm skipping this" loses the work. Describe the work, not an ID
  (BACKLOG IDs recycle).
- **Question whether a derived artifact should exist before patching it.**
  Heavy fix-up on a generated artifact (a derivative, an extract, a
  scaffold) is a smell it is wrong-by-construction. Judge from the
  consumer's seat — a researcher — not the checker's: machinery that
  satisfies a check but adds no consumer value is overhead to drop. Prefer
  remove/regenerate over patch.

### Prefer removing a fact to leaving it half-finished

When a piece of content's value or sourcing is uncertain, leave it out —
the git diff is the recovery record — rather than ship incorrect or
half-finished work; record genuinely load-bearing removals in BACKLOG. An
agent with no more context defaults to hedging, and an unsourced hedge
degrades the repo.

### Check the governing docs before treating an "inconsistency" as open

The governing surfaces usually already settle what looks like an open
design question: `README.md` for what the project is, `CLAUDE.md` for the
operating rules, `docs/` for accepted decisions, `schema/catalog.sql` for
field and structure semantics, and the tools' docstrings for what is
mechanically enforced. Grep them for the governing rule first; if a
standard exists, bring the data into compliance rather than inventing
tooling or a parallel scheme. A check often *silently skips* a
non-compliant form, so a violation can read green and look like "no
standard exists."

### A schema or check mechanism applies to every instance of its type

If a field or validator mechanism is right for a type, declare it for the
whole type and migrate all instances (empty lists render nothing) — never
carve out one "optional exception" to dodge a corpus-wide sweep. Content
scope (which instances get *populated*) must not leak into the
schema-mechanism decision (which instances *declare* the field).

### Verify a BACKLOG item against current state before executing it

A `BACKLOG.md` item may already be mostly done by a prior session whose
bookkeeping lagged. Before executing one, reconcile each sub-bullet against
current artifacts and `git log`; strike what's done, drop what's redundant
or unattested. Most "fix the BACKLOG" work is triage, not building.

### Commit directly to main

In this repo, commit straight to `main` — do not branch first. Standard
discipline still holds: the tools and checks must be green to commit, and
data files (archive, catalog, imports, derivatives) never enter git. Commit
each finished piece of code or doc work without waiting to be asked; a
research decision is never a commit.

### Commit before auditing, in multi-agent batches

When cleaner subagents edit artifacts and auditor subagents verify, commit
the cleaner edits before dispatching the auditors. An auditor's
advisory-scoped shell can run `git restore` and silently revert an
uncommitted batch; a committed change is immune. A regression caught after
the commit is a cheap follow-up — far cheaper than lost work.

### Two sessions on one working tree

When a director session tasks a worker session on the same clone, only the
worker edits and commits while it works; the director reads, tasks and
audits. Never `git add -A` on the shared tree: it stages the other session's
half-written files (it happened, and broke the screen until the next
commit). The worker records its catalog writes as
`--by "agent:<session> for user:<owner>"`, stops and reports on any defect
instead of working around it, and the director audits the commits and the
catalog read-only at the end. A plan is put to the worker for critique before
it becomes a task; the critique has been right every time.

### No speculative estimates — name the work, not its size

Work plans, BACKLOG entries, and status reports state what needs to get
done, not how much of it there is or how long it will take. Do not invent:
per-task percentage gains, accuracy projections, hour estimates, session
counts, line-count estimates, or probability claims about whether something
will succeed. Algorithm- or library-level facts (a published benchmark
number, a documented distance metric, a measured throughput) are properties
of the tool itself and belong in artifacts. The line: anything specific to
THIS project's outcome where there is no measurement is speculation.

Where uncertainty matters, state directional shape only ("this should help
format X more than format Y, magnitudes unknown") and prefer naming what
would resolve the uncertainty (run a real test) over inventing the number.

**Why:** Speculative percentages and hours read as precision but contain no
information — the reader cannot tell what was measured from what was
guessed, and the artifact decays as more sessions accumulate fake-precise
predictions that nothing tests.

### Working notes are a report, not a residue

An agent's — or contributor's — analysis, intermediate reasoning, and
findings are a **deliverable**: handed to the user, or returned up a
pipeline as a handoff. They are never persisted into the repository's
durable surfaces. The repo records *what the sources say* and *what the
code does*, not the working process that produced either.

Three durable surfaces, three places working notes must not land:

- **Generated artifacts** — derivatives, extractions, exports: regenerated
  from their inputs, never hand-annotated.
- **Code comments** — what the code does and the non-obvious why, not who
  changed it or what a review found (see "Comments describe code, not
  refactor history" below).
- **Stray files** — no scratch notes, status logs, or "summary of this
  session" files committed to the tree.

The record lives in **git history** (commit messages, PR descriptions).

### Comments describe code, not refactor history

Code comments describe what a function or script does and any non-obvious
why — invariants, layering rules, surprising behavior — not refactor
history. Forbidden in comments: BACKLOG identifiers (`per BACKLOG C21`),
commit hashes (`migrated at af5f789`), dated audit notes (`2026-05-05 audit
surfaced …`), phase/cluster markers, `Origin:` / `Migration:` / `Anchor
pattern:` blocks, "previously X, now Z" reframings, and "mirror X exactly"
sync reminders for code since centralized. The commit message carries *why
we changed it*; the comment carries *why it is the way it is*, and only
when non-obvious. This describe-current-state rule extends to every
governance file — retiring a check, removing a schema field, deleting a
template: the file describes current state and pending work, not past
evolution. Git log carries the evolution.

**What TO keep:** functional descriptions, plus non-obvious why notes
anchored on still-live concepts — a durable governance anchor (a
`schema/catalog.sql` table or column, a `docs/` decision, a `CLAUDE.md`
rule), a BACKLOG mention when scoping a "not yet implemented" path, or a
layering invariant (e.g. "artifact rows are insert-only; corrections are new
rows"). Anchor on durable concepts, never transient ones (specific commits,
dated audits, phase markers).

### Define the user's goal before building a screen

Write the goal of a screen in one sentence from the user's point of view
and get it confirmed before building. Organize screens around a person (or
a research question about a person); surface pipeline items — unresolved
places, uncited facts, records to fetch — only as questions about that
person. Never ship a screen whose primary navigation is a data type.

**Why:** A screen that mirrors internal queues (places, names, records)
makes sense to the pipeline and to nobody else; the user is researching
people.

### Plain over clever

Fewer, plainer features that work end to end. Every human decision is
Accepted / Rejected / Undecided; a record row is held / cited / missing /
n/a. No numeric confidence, no percentages, no score badges, no hint queues.
Ask before adding anything not already in the design docs.

### Trees are isolated; evidence is never auto-reused across them

A fresh tree must be able to distrust everything an earlier tree concluded.
Each import gets its own extraction and personas even for identical bytes;
cross-tree sharing is never automatic. Owner doc: `docs/DATA-ARCHITECTURE.md`,
trust boundaries.

### Accepted decisions are not reopened

Architecture and workflow decisions marked accepted in `docs/` stand. Build
to them; propose a change as a BACKLOG entry with the reason, not by
building around them.
