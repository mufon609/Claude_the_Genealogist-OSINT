# Fetch cited records from free holders; verify the extractor on real pages

You are the worker session. Read `CLAUDE.md`, `MEMORY.md`, and `docs/AUDIT-PROMPT.md` first. Ancestry record images are behind a membership this account does not have, so the assisted fetch there is closed. This brief makes the fetch of a cited record work through free holders instead, verifies the extractor on a real free page, and records the rule that allows it.

## Phase 1: the rule and the registry

1. `docs/RESEARCH-WORKFLOW.md` §4: a cited record may be fetched from any holder of the same collection; the lookup uses the citation's own details (collection, year, place, district, sheet, the name as indexed), never the person's unreviewed facts, so it stays allowed before review. Ancestry is a citation source, not a fetch source.
2. `data/data-sources.csv`: set B02 Ancestry to status `blocked` with the note that record images require a membership this account lacks. Add a `Holders` column, or a small holders table in `data/`, mapping each cited Ancestry collection (by dbid) to its free holders: FamilySearch collection id for every US federal census year and for the Massachusetts, Kentucky, Tennessee, New Jersey, and Ohio vital collections the tree cites; Power Library for Pennsylvania death and birth certificates; the National Archives 1950 site for 1950; Find a Grave for its own index. Verify every FamilySearch collection id by opening the collection page in the browser; do not guess ids.
3. `tools/plan.py`: a fetch step for an Ancestry citation gets its locator re-targeted to the free holder from the mapping, with the citation's details carried on the step. A citation whose collection has no free holder yet stays a fetch step with mode `blocked` and the reason.

Commit Phase 1.

## Phase 2: verify the extractor on a real free page

1. Find a Grave memorial pages are free to view. Using the Claude in Chrome tools in the owner's browser, open one memorial the tree cites, for Abram C. Brant, capture the rendered page through the page's own DOM into `inbox/`, close the tab, open no other page. One record, at the owner's direction; never search or crawl.
2. On a scratch copy, archive it through the screen's attach path and write the Find a Grave parser into `tools/extract.py` under its own extractor tag: the memorial's name, dates, places, plot, inscription, and the family links as personas with relations. Compare field by field to the page. Run the matcher. Report the extraction and proposals verbatim.
3. Then the rest of the standing loop work: accepting a persona match, or the fact decision that follows it, closes every open question on that person the record answered, with `closed_reason` answered and `answered_by_proposal_id` set (`missing_parents` when a parent link is accepted; `unverified_claim` when the uncited event gains an accepted assertion; `missing_fact` when the fact now has a value with an accepted assertion; `conflict` only by a person), and regenerates the person's plan in the same request. New-person proposals become decidable: accepting creates the person in this tree, the persona link accepted, the same Undecided assertions as a match, and the family membership with an Undecided assertion when the persona's relation says child, parent or spouse of a person matched on the record; rejecting writes the proposal rejected and nothing else. Superseding an extraction marks its undecided proposals rejected with a note saying superseded.

Commit Phase 2.

## Phase 3: the FamilySearch fetch

The owner has a free FamilySearch account signed in on Chrome.

1. For Abram C. Brant's 1900 census fetch step, now re-targeted to FamilySearch, use the citation's details to locate the same record in the owner's browser: the collection page, then the record found through the collection's own search on the indexed name and place, then the record and its image. Capture the record page through the DOM and download the image through the site's own control into `inbox/`. One record. Close the tab.
2. On a scratch copy, archive both, write the FamilySearch record-page parser under its own extractor tag, compare field by field, match, and report verbatim.

Commit Phase 3.

## Rules

Plain over clever. One page at a time in the owner's own browser, never a crawl or an automated search at a closed source. Saved pages and images never enter git. No scores. Commit per phase with the data-file guard. Report in the usual shape, with one line per parser stating whether it was verified on a real page.
