# The standard path: open sources, no Ancestry, no browser

You are the worker session. Read `CLAUDE.md`, `MEMORY.md`, `docs/AUDIT-PROMPT.md`, and `data/DATA-SOURCES.md` first. The source registry has an empty `Connector` column and no step ever runs as `auto`. This brief builds the runner and the first two connectors for sources that are free and have no login, so a search step can run without Ancestry and without a browser, archive what it finds, and feed the extractor and matcher. Ancestry stays assisted; this is the default path.

## Phase 1: the runner

1. `tools/run_step.py <step id>` executes a step whose mode is `auto`: build the query from the step's rendered fields, call the source's connector, archive every raw response as a JSON artifact with a manifest whose locator is the request URL and whose source is the registry row, archive any record image or OCR text the response points to, write one `search_log` row with the exact query, outcome `found` or `none`, and the artifact hashes, then run the extractor and matcher on what was archived. `--all` runs every planned auto step for the active tree, respecting each source's rate limit; `--dry-run` shows the requests without sending them.
2. A connector is one small module under `tools/connectors/` with a fixed contract: `search(fields) -> list of hits`, each hit carrying a request URL, the raw JSON, and optional record image or text URLs, plus a documented rate limit. Nothing else.

## Phase 2: two connectors

1. `loc_gov` for the Library of Congress newspaper collection (Chronicling America through the loc.gov JSON API, free, no key). Serves `obituary` steps: full-text search on the surname and given name near the death date and place. Archive the hit pages' OCR text. Set `Connector` to `loc_gov` on the H01 registry row.
2. `nara_1950` for the 1950 census on the National Archives site, which has a free name search over its own transcription and free page images. Serves `household` steps for census year 1950. Archive the page image and the transcription JSON. Set `Connector` on the registry row that covers it, adding a row if D01 is too broad.
3. An extractor variant for each connector's output: newspaper OCR text becomes one persona per matched name with a Residence or Death fact and the text region; the 1950 transcription becomes personas and facts like the Ancestry page does. Both under their own extractor tag.

## Phase 3: prove it on this tree

On a scratch copy, review one person enough to unlock searches, then run the 1950 household step for Frederick Michael Ahearn or Helen Sara Brant, and the obituary step for a person who died where Chronicling America has coverage. Report verbatim: the requests sent, the artifacts archived with their manifests, the search log rows, the extractions, and the matcher's proposals. If a source returns nothing for this tree, log the `none` and say so; that is a result, not a failure.

## Rules

Plain over clever: one runner, one connector contract, two connectors. Respect every source's stated rate limit and identify the tool in the user agent. No credentials anywhere. No Ancestry. No scores. Commit per phase with the data-file guard. If a source turns out to have no usable free endpoint, do the other and report why.

## Report

Same shape as before, plus the connector contract in one paragraph, so the next connectors can be written from the report alone.
