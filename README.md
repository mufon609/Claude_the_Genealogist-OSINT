# tree

A family-tree application with AI in the core, built data-first: every fact must
trace to an archived copy of the record it came from, and a fresh tree must be
able to distrust every earlier conclusion.

The goal, in the owner's words: "Humans should be working off of defined logical
rules, so there is no reason why we cannot implement these policies in code.
Automation should be the goal as long as it is built off an accurate and trusted
foundation of documents." and "The human should only be used if there are
serious doubts." The work is a loop: the next person at the edge of the
confirmed tree, the records that should exist for them, fetched, read and
decided by the owner's written rules, then the next person; where a source
forbids automation, that person waits on the owner's browser and the loop goes
on to the next.

| Where | What |
|---|---|
| `docs/DATA-ARCHITECTURE.md` | The design: four layers, content-addressed archive, trees/profiles, trust boundaries, aliases. Accepted decisions are recorded there. |
| `data/data-sources.csv` | Source registry and checklist (type, cost, URL, access, trust tier, status, the collections other holders serve its records under). `data/holders.csv` maps cited Ancestry collections to their free holders; `data/jurisdictions.csv` says which records exist where and who holds them, `data/countries.csv` the world's countries, `data/evidence-classes.csv` the proof standard's classes. `data/evidence-classes.csv` classifies each record kind's fields for the proof standard; `data/life-limits.csv` holds the limits of one life a link or a statement is tested against. `data/DATA-SOURCES.md` has the reasoning. |
| `schema/` | Portable DDL, seed taxonomy, manifest JSON Schema. `schema/README.md` maps tables to layers. |
| `tools/` | `initdb.py`, `tree.py`, `ingest_gedcom.py`, `resolve_places.py`, `backfill_aliases.py`, `checklist.py`, `footprint.py`, `plan.py`, `log_search.py`, `attach_inbox.py`, `fetches.py`, `cards.py`, `proof.py`, `extract.py`, `match.py`, `conclude.py`, `run_step.py`, `run_task.py`, `cite.py`, `queue.py`, `turn.py`, `turns.py`, `tombstone.py`, `backup.py`, `check.py`; shared modules `treelib.py`, `forms.py`, `catalog.py`, the readers and the matcher (`readers.py`, `matcher.py`), `households.py`, `attach.py`, `fetch_list.py`, the decision code by job (`rule.py`, `conflicts.py`, `decisions.py`, `copies.py`, `merges.py`, `reconsider.py`, `arrival.py`), `facts.py`, `overview.py`, in layers `schema/README.md` states; `save_page.js` and `save_image.js`, the page-saves-itself and image-saves-itself scripts the owner's browser runs; `tools/connectors/` one module per free source with an endpoint; `tools/tasks/` the one text of each kind of task a model runs (`run_task.py`). `tools/hooks/` holds the commit guard. `tests/checks/` holds the harness (`parsers.py`, `scenario.py`, `loop.py`, `imports.py`, `cut_gedcom.py`) and `tests/fixtures/` its saved pages, their `.expect.json` sidecars, the scenarios and the harness tree. |
| `trees/<slug>/` | Per-tree folder: README, `imports/` (named copies, ignored), `exports/` (snapshots, ignored). |
| `inbox/` | Drop zone for files to ingest, made by the first tool that uses it. |
| `downloads/` | Where the browser saves the pages a turn waits on: the owner sets it as the browser's download location once; `tools/fetches.py collect` moves them into `inbox/`. No tool reads the owner's own download folder. |
| `app/person/` | The person screen: stdlib server plus one page, and `read_record.md`, what a reader of a record image writes. |
| `CLAUDE.md` | Operating rules for an AI contributor. |
| `.claude/` | What Claude Code reads of the project: `agents/tree-fetch.md` and `skills/tree-fetch/SKILL.md`, written by `tools/run_task.py write` from `tools/tasks/` and held to it by the check. A session the owner is at uses the skill to have a model save one page of the fetch list. |
| `MEMORY.md` | Cross-cutting working patterns for any contributor; travels with the clone. |
| `BACKLOG.md` | Deferred work, self-governing. |

Not in git: `archive/` (content-addressed masters), `catalog/*.db`, `derivatives/`,
`inbox/`, what `downloads/` holds, and everything under `trees/*/imports` and `trees/*/exports`. Those are backed up by
BagIt bags, not by git, and the commit hook refuses them: install it once with
`git config core.hooksPath tools/hooks`. Set `DATA_ROOT` to keep those directories,
the catalog among them, somewhere else, as a scratch run does: a tool given no `--db`
opens the catalog under `DATA_ROOT`, and a `--db` outside `DATA_ROOT` is refused.

```
python3 tools/initdb.py
python3 tools/tree.py create <slug> --name "..."
python3 tools/ingest_gedcom.py inbox/<file>.ged   # any GEDCOM; labelled with the exporter its header names
python3 tools/tree.py home "<person>"           # the home person: the queue and the loop refuse to run without one
python3 tools/resolve_places.py
python3 tools/backfill_aliases.py
python3 tools/checklist.py "Abram C Brant"      # per-person checklist and gaps
python3 tools/queue.py && python3 tools/turn.py "<person>"   # the loop: the next person at the tree's edge, their plan run end to end
python3 tools/turns.py --turns 2                             # the loop run without a hand on it: what was saved in the browser taken in, then turn after turn from the queue; a person whose pages wait for the browser waits, the loop goes on
python3 app/person/server.py                    # the person screen, http://127.0.0.1:8765/
```
