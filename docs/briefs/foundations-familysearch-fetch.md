# Foundations, then the FamilySearch fetch, then the loop on a real page

You are the worker session. Read `CLAUDE.md`, `MEMORY.md`, and `docs/AUDIT-PROMPT.md` first. This brief replaces the resume brief for the FamilySearch fetch: that work becomes Phase 2 here, after the foundations in Phase 1. If you have uncommitted FamilySearch work, keep it on disk and report it under deviations; do not commit it before Phase 1.

What you do not do: swap catalog files, restart the local screen, or remove the archive object for the Find a Grave memorial that no catalog row references. The director swaps a rebuilt catalog in after integrity and foreign-key checks; the orphan waits for the owner's word; the memorial page in `inbox/` is attached by the owner, not by you. Every test runs on a scratch catalog under a scratch data root, never on `catalog/tree.db` or the repository's `archive/`.

## Phase 1: foundations

1. **Scratch data root.** `tools/treelib.py` resolves every data directory (`archive/`, `derivatives/`, `inbox/`, `trees/<slug>/imports`, `trees/<slug>/exports`) under one root given by the environment variable `DATA_ROOT`, default the repository. Only treelib changes; every tool and the screen already go through it. A scratch run is then `--db <scratch>/tree.db` with `DATA_ROOT=<scratch>`, and a scratch attach moves a copy of the inbox file, never the owner's. Add the one-line recipe to `CLAUDE.md` under "Working the repo".
2. **A parser claims a page or the extraction fails.** In `tools/extract.py` each parser claims a page by its own marker: the Find a Grave memorial by `<body id="memorial-summary">` as now, the Ancestry index page by a marker taken from the selectors that parser already relies on. A page no parser claims writes one extraction with status `failed`, no personas, no `structured_json` beyond the reason, and the matcher is not run; the screen's attach reports it as unparsed. The Ancestry marker is as unverified as the parser; say so in the report.
3. **Delete triggers.** `schema/sqlite_extras.sql` aborts DELETE on `persona` and `persona_fact`, as `schema/README.md` already claims. Bump the schema to 0.7.1 in `schema/catalog.sql` and `tools/initdb.py`. Rebuild on a side path, not the live file: `initdb --db catalog/tree.rebuilt.db`, the same tree slug and name as `tools/tree.py show` reports, `ingest_gedcom trees/ahearn/imports/2026-09-05_Ahearn-Family-Tree.ged --keep`, `resolve_places` (cached), `backfill_aliases`, `plan --all`. Report a table of row counts per table beside the live catalog's; the only differences allowed are ids and timestamps. The director swaps it in.
4. **A commit guard the repo installs.** `tools/hooks/pre-commit`, installed once by `git config core.hooksPath tools/hooks`, refuses a commit whose staged paths fall under `archive/`, `catalog/` databases, `derivatives/`, `inbox/` (except `.gitkeep`), `trees/*/imports`, `trees/*/exports`, or end in `.ged`, `.db`, `.db-wal`, `.db-shm`. Rule 7 in `CLAUDE.md` names the install command; `README.md` gets the same line. Install it before the Phase 1 commit and show it refusing a staged `.ged` on a throwaway file.
5. **Describe-current-state sweep.** `docs/AUDIT-PROMPT.md`: schema 0.7.1; the counts as the catalog has them (persons, Undecided assertions, open questions, fetch steps, re-targeted and blocked); the extractor and matcher listed as built, with one line per parser saying whether it is verified on a real page; not built: connectors and the runner, the FamilySearch parser until Phase 2, exporters, backups. `docs/SOURCE-PROFILE.md`: the agent table names Ancestry as a citation source only and the fetcher as working free holders. `README.md`: the tools list gains `extract.py` and `match.py`. `docs/RESEARCH-WORKFLOW.md` §4: drop the `manual` mode row; nothing produces it and the schema does not allow it. Every change describes current state; no history.

Commit Phase 1. The commit includes this brief, its row in `docs/briefs/README.md`, and the backlog entries the director added.

## Phase 2: the FamilySearch fetch

The owner's free FamilySearch account is signed in on Chrome. One record, in the owner's own browser, found only through the citation's own details. Stop and report at any gate: a login prompt, a terms interstitial, a rate limit, a page that will not render.

1. Abram C. Brant's 1900 census fetch step (id `01M1T5HCGM25KEJKYRJB98EMX3`, locator `1,7602::47389682`, holder FamilySearch collection 1325221) carries: Year 1900, Census Place Norristown, Montgomery, Pennsylvania, Roll 1444, Page 2, ED 0240, indexed name Charlotte D Lukens. Open the collection page, use the collection's own search on the indexed name and place, open the record page and its image. Capture the record page through the DOM into `inbox/` and download the image through the site's own control into `inbox/`. Close the tab; open no other page. DOM capture through the Chrome extension: script output is capped near 1.5 KB and rejects text that looks like a query string or a hash, so clone the page in-page, marker-encode it into a `<pre>`, read it out in 25,000-character slices, decode, and verify each chunk and the whole by SHA-256.
2. On a scratch catalog under a scratch data root, with a copy of both files in the scratch inbox: attach through the screen's attach path (a second server on another port and the scratch `--db`). Write the FamilySearch record-page parser in `tools/extract.py` under `rule:familysearch-record@0.1.0` with its own marker: the record's fields as labelled, one persona per household member in the page's own role word, one relation per stated relationship. Record the page's ark on the artifact as a second locator in `artifact_locator`; the step's locator stays the citation's apid. Compare field by field to the page in a table. Run the matcher. Report the extraction and the proposals verbatim.
3. **Holder search URL on re-targeted steps.** The person screen's link for a FamilySearch-held step becomes the collection's own search prefilled from the step's fields, in the exact URL shape observed during the fetch, and for a National Archives 1950 step the site's name search likewise; Find a Grave keeps the memorial URL. Built from the citation's details only, never from the person's facts. Say in the report which parameters the URL carries.

Commit Phase 2. The fetched page and image never enter git.

## Phase 3: the loop on the real pages, on scratch

On the scratch catalog from Phase 2, with the memorial page also attached from the scratch inbox, report each of these verbatim with the rows it wrote:

1. Accept the persona match for Allen Brant or Ida Brant on the memorial (each has an open `missing_fact: death date` question): the Undecided death assertion, the question closed as `answered` with `answered_by_proposal_id`, the plan regenerated in the same request.
2. Accept one `new_person` proposal whose relation on the record is child, parent or spouse of a matched person (the census household, or the memorial if it gives one): the person, the accepted link, the Undecided assertions, the family membership with its Undecided assertion. A sibling gives no membership; show that too on one of the memorial's siblings.
3. Reject one proposal: the proposal rejected and nothing else.
4. Re-run the extractor on one of the pages: the earlier extraction superseded, its undecided proposals rejected with note `superseded`.
5. `plan.py --all` twice, unchanged the second time. `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, and the `v_unsupported_*` counts.

Commit Phase 3 if any code changed; otherwise say so.

## Rules

Plain over clever. One page at a time in the owner's own browser, never a crawl or an automated search at any source. No scores. Nothing Accepted without a person. Commit per phase with the guard installed. Report in the shape `docs/DIRECTOR-HANDOVER.md` gives: per item what changed with file and line, test outcomes verbatim, deviations and why, findings outside the brief, commit hashes, one paragraph on what next, and one line per parser stating whether it was verified on a real page.
