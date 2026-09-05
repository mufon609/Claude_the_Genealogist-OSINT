# tree

A family-tree application with AI in the core, built data-first: every fact must
trace to an archived copy of the record it came from, and a fresh tree must be
able to distrust every earlier conclusion.

| Where | What |
|---|---|
| `docs/DATA-ARCHITECTURE.md` | The design: four layers, content-addressed archive, trees/profiles, trust boundaries, aliases. Accepted decisions are recorded there. |
| `data/data-sources.csv` | Source registry and checklist (type, cost, URL, access, trust tier, status). `data/DATA-SOURCES.md` has the reasoning. |
| `schema/` | Portable DDL, migrations, seed taxonomy, manifest JSON Schema. `schema/README.md` maps tables to layers. |
| `tools/` | `initdb.py`, `tree.py`, `ingest_gedcom.py`, `resolve_places.py`, `backfill_aliases.py`, `migrate.py`. |
| `trees/<slug>/` | Per-tree folder: README, `imports/` (named copies, ignored), `exports/`. |
| `inbox/` | Drop zone for files to ingest. |

Not in git: `archive/` (content-addressed masters), `catalog/*.db`, `derivatives/`,
and everything under `trees/*/imports`. Those are backed up by BagIt bags, not by git.

```
python3 tools/initdb.py
python3 tools/tree.py create <slug> --name "..."
python3 tools/ingest_gedcom.py inbox/<file>.ged
python3 tools/resolve_places.py
python3 tools/backfill_aliases.py
```
