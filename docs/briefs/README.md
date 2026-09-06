# Briefs

Task briefs for a worker session. Each is self-contained: paste it into a fresh
session after `CLAUDE.md`, `MEMORY.md` and `docs/AUDIT-PROMPT.md`. A brief stays
here after it is done, as the record of what was asked; the commits carry what
was built.

| Brief | State | Use |
|---|---|---|
| `free-holders-fetch.md` | done (Phases 1–2); Phase 3 moved to the foundations brief | Fetch cited records from free holders instead of Ancestry; verify the extractor on a real Find a Grave page. |
| `ancestry-assisted-fetch.md` | superseded | Ancestry record images need a paid membership this account lacks. Kept for a subscribed account. |
| `foundations-familysearch-fetch.md` | done | Scratch data root, parser detection, delete triggers and the 0.7.1 rebuild, the commit guard, the doc sweep; the FamilySearch fetch with its parser and holder search URLs; the loop on the real pages. |
| `open-source-connectors.md` | done | The runner and the first two free-source connectors (loc.gov newspapers, the 1950 census at the National Archives). |
| `owner-vouch.md` | current, first worker | The owner vouches for a fact on their own knowledge; the registry stays in step with the catalog; a held census page is held for every citation to the same page. |
| `no-browser-sources.md` | after `inbox-to-cards.md` | Survey the registry's free sources with documented endpoints against this family, build connectors for the ones that fill the most gaps, run them on scratch and report the results as decision cards. |
| `findagrave-fetch-method.md` | dedicated session | Fetch one cited memorial in the owner's browser by a method that costs one or two calls and no model transcription; measure it; test on scratch; commit nothing. |
| `inbox-to-cards.md` | next, after `owner-vouch.md` | One tool attaches every inbox file to the steps it fulfils by the record's own identity, extracts and matches after logging, and renders each Undecided proposal as the owner's decision card. |
| `findagrave-search.md` | Part A now (browser session); Part B after `inbox-to-cards.md` (worker) | A person with no memorial cited: search Find a Grave from the foundation, save the results page, audit every candidate against what we know, log the search, fetch only the memorials that fit. |
| `record-facts.md` | after `findagrave-search.md` Part B, before the survey | After a match: every fact the record supports is decidable, one decision accepts the record's facts, and the record's more exact value can become the tree's. |
