# tree

A family-tree application with AI in the core, built data-first: every fact must
trace to an archived copy of the record it came from, and a fresh tree must be
able to distrust every earlier conclusion.

| Where | What |
|---|---|
| `docs/DATA-ARCHITECTURE.md` | The design: four layers, content-addressed archive, trees/profiles, trust boundaries, aliases. Accepted decisions are recorded there. |
| `data/data-sources.csv` | Source registry and checklist (type, cost, URL, access, trust tier, status). `data/holders.csv` maps cited Ancestry collections to their free holders. `data/DATA-SOURCES.md` has the reasoning. |
| `schema/` | Portable DDL, seed taxonomy, manifest JSON Schema. `schema/README.md` maps tables to layers. |
| `tools/` | `initdb.py`, `tree.py`, `ingest_gedcom.py`, `resolve_places.py`, `backfill_aliases.py`, `checklist.py`, `footprint.py`, `plan.py`, `log_search.py`, `extract.py`, `match.py`. `tools/hooks/` holds the commit guard. |
| `trees/<slug>/` | Per-tree folder: README, `imports/` (named copies, ignored), `exports/` (snapshots, ignored). |
| `inbox/` | Drop zone for files to ingest. |
| `app/person/` | The person screen: stdlib server plus one page. |
| `CLAUDE.md` | Operating rules for an AI contributor. |
| `MEMORY.md` | Cross-cutting working patterns for any contributor; travels with the clone. |
| `BACKLOG.md` | Deferred work, self-governing. |

Not in git: `archive/` (content-addressed masters), `catalog/*.db`, `derivatives/`,
and everything under `trees/*/imports` and `trees/*/exports`. Those are backed up by
BagIt bags, not by git, and the commit hook refuses them: install it once with
`git config core.hooksPath tools/hooks`. Set `DATA_ROOT` to keep those directories
somewhere else, as a scratch run does.

```
python3 tools/initdb.py
python3 tools/tree.py create <slug> --name "..."
python3 tools/ingest_gedcom.py inbox/<file>.ged
python3 tools/resolve_places.py
python3 tools/backfill_aliases.py
python3 tools/checklist.py "Abram C Brant"      # per-person checklist and gaps
python3 app/person/server.py                    # the person screen, http://127.0.0.1:8765/
```
