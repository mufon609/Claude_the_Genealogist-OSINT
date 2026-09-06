# CLAUDE.md

Operating rules for an AI contributor in this repo. Read `MEMORY.md` next;
it holds the cross-cutting working patterns. `README.md` says what the
project is and where things are.

## What this is

A family-tree application with AI in the core, built data-first. Every
fact must trace to an archived copy of the record it came from. A fresh
tree must be able to distrust every earlier conclusion. The user researches
people; everything else exists to serve that.

## Where decisions live

| Question | Read |
|---|---|
| Layers, archive, trees, trust boundaries, aliases, decision model | `docs/DATA-ARCHITECTURE.md` |
| Baseline → questions → search ladder → review | `docs/RESEARCH-WORKFLOW.md` |
| Per-person checklist, gaps, search foundation, the screen | `docs/RESEARCH-CHECKLIST.md` |
| What the imported tree holds; agent duties | `docs/SOURCE-PROFILE.md` |
| Source registry, free holders of cited collections, the reasoning | `data/data-sources.csv`, `data/holders.csv`, `data/DATA-SOURCES.md` |
| Tables, invariants, tools | `schema/README.md`, `schema/catalog.sql` |
| Deferred work | `BACKLOG.md` |

Anything marked accepted in those docs stands. Do not reopen it in code.

## Hard rules

1. **Three states.** Every human decision is `undecided | accepted |
   rejected`. No numeric confidence, no scores, no percentages, anywhere a
   person decides. Machine scores stay inside notes/JSON.
2. **Evidence is immutable.** `artifact`, `persona`, `persona_fact` are
   insert-only. Corrections are new rows; removals are tombstones. Errors in
   records are never corrected in evidence; they become aliases.
3. **Nothing is Accepted without a person saying so.** Imports and AI output
   arrive Undecided. Conclusions need an Accepted assertion.
4. **Trees are isolated.** No automatic reuse of evidence across trees.
5. **One person per screen.** Foundation → checklist → tasks → results →
   review. No queue screens, no navigation by data type, no hint feeds on
   unreviewed people. Define the screen's goal in one sentence and confirm
   it before building.
6. **Plain over clever.** No bells and whistles. If a feature is not in the
   design docs, ask before building it.
7. **Data never enters git.** `archive/`, `catalog/*.db`, `derivatives/`,
   `inbox/`, `trees/*/imports` are ignored, and the commit hook refuses them:
   install it once with `git config core.hooksPath tools/hooks`.
8. **No bandaids.** Fix the cause or file it in `BACKLOG.md`. No parking
   comments, no compensating checks. Comments describe current code, never
   history (see `MEMORY.md`).
9. **Commit only when asked**, directly to `main`, with the tools green.
10. **Working notes are a report**, returned to the user, never committed.

## Working the repo

```
python3 tools/initdb.py --force              # fresh catalog (schema is rebuilt, not migrated)
python3 tools/tree.py create <slug> --name "…"
python3 tools/ingest_gedcom.py inbox/<file>.ged
python3 tools/resolve_places.py             # Nominatim, cached; --reset undoes AI resolutions only
python3 tools/backfill_aliases.py
python3 tools/checklist.py "<person>"       # read-only checklist + gaps (footprint on top); --json, --all
python3 tools/footprint.py "<person>"       # read-only Layer 0 on its own
python3 tools/plan.py --all                 # materialize questions + steps (idempotent)
python3 tools/log_search.py --list "<person>"   # the steps with outcomes; --step/--outcome to log a run; --dismiss <question>
python3 tools/extract.py <sha256>            # personas + facts from an archived record page (Find a Grave memorial or Ancestry index, HTML)
python3 tools/match.py <extraction id>       # proposals: persona match or new person, rationale in words
python3 tools/tree.py show
python3 app/person/server.py --by user:<you>  # person screen on http://127.0.0.1:8765/
DATA_ROOT=<scratch> python3 tools/<tool>.py --db <scratch>/tree.db   # scratch run: its own archive/, inbox/, derivatives/, trees/*/imports
```

- Stdlib Python only, so far. Portable SQL (SQLite now, Postgres later).
- Verify after every change: `PRAGMA integrity_check`, `foreign_key_check`,
  and the `v_unsupported_*` views. Test decisions on a scratch copy of the
  catalog, never on the real one.
- Place resolution auto-accepts only unique full matches; everything else
  stays Undecided. Never widen that.
- External services: Nominatim public endpoint at 1 req/s with cache;
  Ancestry and Find a Grave have no API and forbid scraping — assisted
  fetch only.
