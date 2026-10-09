# Audit prompt

Paste the block below into a fresh session opened in this repository.

---

You are auditing this repository. Do not build, refactor, or edit anything. Read, run
the read-only tools, test on a scratch copy of the catalog if you need to, and
report. The repository's own rules apply to you: `CLAUDE.md`, then `MEMORY.md`.

## What to read first

The project, its goal in the owner's own words and where everything lives:
`README.md`. The operating rules, the hard rules and the command list:
`CLAUDE.md`. The accepted decisions: `docs/DATA-ARCHITECTURE.md` (layers,
archive, trees, trust boundaries), `docs/TERMS.md` and `docs/RULE.md` (the decision
model and the standing rule), `docs/HOUSEHOLDS.md`, `docs/PLAN-AND-SEARCH.md` (the search
ladder), `docs/LOOP.md` (the loop), indexed by `docs/RESEARCH-WORKFLOW.md`,
`docs/RESEARCH-CHECKLIST.md` (the checklist and the screen). Tables, invariants
and one line per tool: `schema/README.md`; each tool's docstring has the rest.
The source registry and its trust tiers (which classify source kinds and are
never scores): `data/data-sources.csv`, `data/DATA-SOURCES.md`. Deferred work:
`BACKLOG.md`. The tree's own state is in the catalog, read with
`python3 tools/tree.py overview`, `python3 tools/queue.py --all` and
`python3 tools/checklist.py --all`, never in a note.

## What to look for

Report findings, most serious first, each with the file and line, what the
flaw is, why it matters against the goal and the hard rules, and the smallest change that
fixes it. Use severity words, not numbers. Distinguish clearly between:

1. **Contradictions.** Anything in code, schema, tools, screen, or docs that
   contradicts an accepted decision or another doc. Include places where the
   docs say one thing and the code does another.
2. **Flaws that block the automated pipeline.** Look hard at the path from a
   planned step to an archived record to personas to a proposal to a review.
   Is the schema and tooling shaped so that adding automatic source connectors,
   the extractor and the matcher is straightforward, or will it force rework?
   Are the typed search steps actually executable by a program, or only
   readable by a person? Is `search_log` capturing what a program would need?
   Is the plan-per-checklist-row granularity (one research question per
   missing record) the right unit, or noise that will drown the real questions?
   Does anything assume Ancestry can be automated when it cannot?
3. **Violations of "plain over clever".** Anything that adds a concept, a
   table, a column, a state, a screen element or a rule that the vision does
   not need. Anything a user would find annoying. Anything that smells like a
   score or a hint feed.
4. **Trust leaks.** Any way an unreviewed or machine-produced value can become
   Accepted, be exported, feed a search as if accepted, or cross from one tree
   to another without a person deciding or the standing rule taking it on the
   owner's written terms; any way a person's decision can be undone without
   them.
5. **Hygiene.** Comments or docs that narrate history instead of describing
   current state, stray working notes, data files that could reach git, dated
   stamps, migration residue.

Also answer two direct questions at the end: is the loop as built honest
about what is automated and what is not, and what is the one change you
would make first before any more building.

Do not propose bells and whistles. Do not reopen accepted decisions unless you
believe one is actually wrong, and if so say why in one paragraph and mark it
as a challenge, not a finding.
