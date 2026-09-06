# The owner vouches for a fact; the registry stays in step; a held page is held for the whole household

You are the worker session. Read `CLAUDE.md`, `MEMORY.md`, and `docs/AUDIT-PROMPT.md` first. The owner has approved themselves, their parents and their grandparents as the accepted baseline, in conversation with the director, who records decisions through the screen's own API on the owner's instruction. The owner does no research and opens no screen. Three things stand in the way of recording that baseline and working outward from it.

Every test runs under a scratch `DATA_ROOT` with a scratch `--db`. The live catalog now holds Accepted rows; do not touch it.

## Phase 1: the owner vouches for a fact

Today `decide_fact` in `app/person/server.py` accepts only assertions whose evidence the person can see: the file's uncited claims and citations whose record is held. A key fact backed only by citations to unfetched records, or a name and sex backed only by person-level citations, cannot be accepted at all, so the owner's own knowledge of their parents' names and births has nowhere to go.

1. When the owner accepts a key fact and no assertion behind it has held evidence, write one new assertion, status `accepted`, `asserted_by` the owner, on the same subject, with `persona_id` the tree file's persona for that person and `artifact_sha256` the file, `citation_text` "Tree owner's own knowledge", and a note JSON `{"vouched": true}`. The cited assertions stay Undecided until their record is fetched; a later fetch and match adds held evidence beside the vouch. When held evidence exists, behave as now. Reject and Undecided are unchanged.
2. Name and sex share the person-level citations, so one vouch on the person covers both, as one decision does today.
3. `docs/RESEARCH-CHECKLIST.md` §6b, `docs/RESEARCH-WORKFLOW.md` §1 and the decision model in `docs/DATA-ARCHITECTURE.md` §1a say it in one sentence each: a person may accept a fact on their own knowledge; the fact then traces to the tree file as the archived claim and the acceptance is the person's; a vouched fact is Accepted like any other and the record fetch still runs.
4. Test on scratch on Noi Davidson (name, sex, birth, death all cited, nothing held): the vouch rows, the fact status, the plan regenerated, then a fetch attached for one of her cited records and the match accepted, showing the vouch and the held evidence side by side. Integrity and foreign keys.

Commit Phase 1.

## Phase 2: the registry stays in step with the catalog

Accepting a link on Raymond Earl Davidson failed on the live catalog with a bare foreign-key error, because `data/holders.csv` named the 1950 holder D05 before the live catalog's `source` table had it; the plan regeneration inside the decision wrote a step against a missing row. The director ran `initdb --sync-sources` to clear it. The tools must not let that happen again.

1. `tools/plan.py` checks, before writing anything, that every holder in `data/holders.csv` and every source id the checklist emits exists in the catalog's `source` table, and stops with one line naming the missing ids and the sync command. The screen returns that line as the error of the decision that triggered the regeneration, not the SQL error.
2. `tools/initdb.py --sync-sources` is named in `CLAUDE.md` under "Working the repo" as the step after any change to `data/data-sources.csv`, and `schema/README.md` says the same in the registry line.
3. Test on scratch: remove D05 from a scratch catalog's `source` table, run `plan.py` and a fact decision through the screen, show both messages; then sync and show both succeed.

Commit Phase 2.

## Phase 3: a held page is held for the whole household

Backlog: a held census page counts as held only under the citation id it was archived by, because Ancestry cites each household member under their own record id. The 1900 page archived under Charlotte D Lukens's id does not count as held for Milton Reager Lukens, so his checklist still says cited and his review cannot proceed. The footprint already groups census citations by year as one page; held must follow the same rule.

1. An archived record is held for every citation to the same page: same collection, same year, same census place, same enumeration district and sheet, as the citation's own details give them, not only the id it was archived under. The plan marks every such fetch step done with the artifact, the checklist reads held, and the matcher's candidates include every person whose citation the page fulfils.
2. Test on scratch with the 1900 Lukens page: Milton's and Charlotte's rows read held, the matcher proposes Milton without a second attach, and a person with a citation to a different page of the same collection stays cited.
3. Remove the backlog entry.

Commit Phase 3.

## Rules

Plain over clever. No scores. Nothing Accepted without a person; the vouch is the person's decision recorded as such. Commit per phase with the guard installed. Report in the shape `docs/DIRECTOR-HANDOVER.md` gives, with verbatim rows for every test. When this is accepted the director records the owner's remaining approvals through the vouch and the loop starts outward from the grandparents.
