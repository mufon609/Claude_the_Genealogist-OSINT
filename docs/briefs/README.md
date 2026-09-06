# Briefs

Reusable task briefs for a worker session. Each is self-contained: paste it into
a fresh session after `CLAUDE.md`, `MEMORY.md` and `docs/AUDIT-PROMPT.md`.

| Brief | Use |
|---|---|
| `free-holders-fetch.md` | Fetch cited records from free holders (Find a Grave, FamilySearch, NARA, Power Library) instead of Ancestry, verify the extractor on real pages, finish the loop. |
| `ancestry-assisted-fetch.md` | Superseded by the brief above: Ancestry record images need a paid membership this account lacks. Kept for a subscribed account. |
| `open-source-connectors.md` | The standard path: a runner and the first two free-source connectors so steps run without Ancestry and without a browser. |
| `foundations-familysearch-fetch.md` | Current: scratch data root, parser detection, delete triggers and a 0.7.1 rebuild, the commit guard, the doc sweep; then the FamilySearch fetch with its parser and holder search URLs; then the loop on the real pages. Replaces Phase 3 of `free-holders-fetch.md`. |
