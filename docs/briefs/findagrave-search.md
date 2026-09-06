# Find a Grave search: candidates, an audit against what we know, then only the memorials that fit

Two parts. Part A is for the dedicated browser session that solved the memorial fetch; Part B is for the worker, after `docs/briefs/inbox-to-cards.md`. Both read `CLAUDE.md`, `MEMORY.md`, `docs/AUDIT-PROMPT.md` and `docs/DIRECTOR-HANDOVER.md` first.

## The problem

Fetching a memorial the file already cites is solved: one call, thirty seconds. The research case is the other one: a person with no memorial cited, for whom the cemetery row is missing. That takes a search, and a search returns candidates who may or may not be the person. The process must produce the candidates as evidence, audit each against the person's foundation in the same agrees, disagrees, absent words the cards use, log the search whether or not anything fits, and fetch only the memorials that fit, each by the one-call method. Find a Grave forbids automation, so every page is opened in the owner's own browser, one at a time, user-initiated, at low volume: one search page and at most three memorials per person per run.

The test person has a known answer, so the search can be judged: Robert Edgar Davidson (19 February 1915, Woodburn, Logan County, Kentucky, to 5 April 2004, Tiro, Crawford County, Ohio; wife Ruth M Peters). His memorial is cited in the file and its page is already in the inbox. The session and the audit get only the foundation fields, never the memorial id, and must pick him from the results on their own; the director holds the answer and compares. A first run that picks the wrong row or no row is a finding about the audit, not a failure of the process.

## Part A: the search page, saved (browser session)

1. Open the site's own memorial search form in a new tab. Fill it by hand from the person's foundation only: last name Davidson, first name Robert, birth year 1915, death year 2004, with the site's own year tolerance if it offers one, and a location if the form takes one. Submit once. Record the resulting URL verbatim; that is the search URL shape the worker builds from the foundation fields in Part B.
2. Save the results page by the page-saves-itself method in `docs/RESEARCH-WORKFLOW.md` §4, named `findagrave-search-davidson-robert-1915-2004.html`, into `inbox/`. Report what the results page carries per row in its own markup: name, years, cemetery, place, memorial id and URL, and the marker the parser can claim the page by. Report the number of results and, if the site paginated, whether page two exists; open no further page.
3. From the saved results only, without opening any memorial, list every row with name, years, cemetery and place, say which row is the person and why in the agrees, disagrees, absent words, and give its memorial id; or say that no row fits. The director checks the pick against the known memorial.
4. Open no memorial. Close the tabs. Report as before: procedure, calls, minutes, bytes, gates.

## Part B: parser, audit, card (worker)

1. `rule:findagrave-search@0.1.0` in `tools/extract.py`, claiming a results page by its own marker: one persona per result row with name as written, birth and death years, cemetery and place as facts, and the memorial id and URL as the persona's own identity. The search page is archived as an artifact whose locator is the search URL; the search step's log row carries the query as run and the number of results.
2. The cemetery search step for a missing row builds the Find a Grave search URL from the foundation fields with basis, in the URL shape Part A observed, as the FamilySearch steps do. It stays `assisted`.
3. The audit: the matcher compares every result persona with the person and their relatives, as it does for a memorial, and writes one `persona_match` proposal per candidate that agrees on the surname and at least one of birth year, death year or place with no disagreement, and one card listing every candidate, fitting or not, with the fields as agrees, disagrees or absent and the memorial URL. No candidate fitting is logged as `none` with the candidates kept on the artifact. Nothing is fetched by the audit.
4. The fetch that follows: a candidate the owner accepts on the card (or, later, the standing rule) becomes a fetch step for that memorial URL, run by the one-call method through the browser session, and goes through `tools/attach_inbox.py` like any other memorial.
5. Test on scratch with Part A's file: the personas, the proposals, the candidate card, the log row; the audit must rank the known memorial as the fit, and the report says whether it did. The memorial itself is already held, so no fetch follows in the test.

Commit per phase with the guard installed; report in the usual shape, with the candidate card verbatim.
