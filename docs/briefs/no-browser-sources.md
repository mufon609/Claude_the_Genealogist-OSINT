# Sources that need no browser: survey, then connectors, then real runs

You are the worker session. Read `CLAUDE.md`, `MEMORY.md`, `docs/AUDIT-PROMPT.md`, `docs/DIRECTOR-HANDOVER.md` and `data/DATA-SOURCES.md` first. The owner decides in conversation; the director records decisions. The owner has skipped the FamilySearch API application for now and wants the tree's gaps filled from free sources with documented endpoints, so that no fetch needs a browser. The runner, the connector contract in `tools/connectors/`, and the two connectors already built (`loc_gov`, `nara_1950`) are the pattern; write the report so the next connector can be written from it alone.

Every test runs under a scratch `DATA_ROOT` with a scratch `--db`. The live catalog holds the owner's Accepted rows; do not touch it. Identify the tool in every user agent as the existing connectors do; honour every stated rate limit; no credentials in the repo, and a free API key, where one is needed, comes from an environment variable named in the connector's docstring and reported as such.

## Phase 1: survey, one real request each

For each candidate below, send one documented request with this family's own names and places (the owner's grandparents' lines: Ahearn, Davidson, Brant, Lukens, Cassel, Heebner; Pennsylvania, Massachusetts, Kentucky, Tennessee, New York, New Jersey; the Netherlands and Silesia for the origins). Record in the report, per source: the exact request, the response shape (a trimmed real sample), the rate limit and terms as the source states them, the free key requirement if any, which checklist rows it can fill (`docs/RESEARCH-CHECKLIST.md` §2), and one line saying whether it is worth a connector for this tree. Set each registry row's `Status` from what came back, with the endpoint in `Access` and the limit in `Notes`. A source that answers nothing useful for this family is marked so and left; that is a result.

Candidates, from `data/data-sources.csv`: K01 Internet Archive city directories; L01 HathiTrust full-text and data API; C08 Reclaim the Records bulk indexes for New York; C09 New Jersey bulk vital files; F01 NARA Access to Archival Databases; B04 WikiTree API; I07 Open Archives (Netherlands); M02 Digital Public Library of America; I09 the Polish state archives for the Silesian villages; D02 IPUMS full count. Add a candidate you find with a documented free endpoint that serves a row this tree is missing, and say where you found it.

Commit Phase 1: registry rows and the survey's lines in `data/DATA-SOURCES.md`, nothing else.

## Phase 2: connectors for the sources that fill the most gaps

In this order unless the survey says otherwise, and say so if it does: city directories (K01), HathiTrust (L01), the New York and New Jersey bulk indexes (C08, C09), the enlistment data (F01). Each is one module under `tools/connectors/` on the existing contract, with an extractor variant under its own versioned tag that claims its own output by marker or fails, and the registry row's `Connector` set. A bulk file is archived once as an artifact and searched locally; the search log records the file's hash and the exact query. Directory and book hits archive the page text and, where the source serves one, the page image. Stop after the connectors the survey justified; two good connectors beat five thin ones.

Commit Phase 2.

## Phase 3: real runs on scratch, results as cards

On a scratch catalog: the owner's grandparents and their parents are the subjects. Vouch the baseline through the screen where the owner has already approved it (the seven), run every auto step the new connectors serve, and report verbatim: requests sent, artifacts with manifests, search log rows, extractions, proposals. For each proposal, one card in the shape `docs/DIRECTOR-HANDOVER.md` describes under the owner's decisions: a one-line highlight and the links it makes, the file's claim, the record with holder, collection, identity and tier, the link to the primary document, the fields as agrees, disagrees or absent, the relationships stated, what accepting closes, anything odd. The director puts those cards to the owner.

Commit Phase 3 if code changed.

## Report

The usual shape, plus one line per source from the survey, one line per connector (endpoint, limit, user agent), one line per extractor variant saying whether it was verified on a real response, and the connector contract paragraph updated if anything in it changed.
