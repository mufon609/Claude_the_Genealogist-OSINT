# Data Sources — Investigation Notes

Companion to `data-sources.csv`. The CSV is the checklist; this file holds the
reasoning that does not fit in a cell.

## 1. What the seed file told us

`source/meta/Ahearn Family Tree.ged` — Ancestry export, GEDCOM 5.5.1, 2025.08 exporter,
dated 5 Sep 2026.

| Metric | Value |
|---|---|
| Individuals / Families | 117 / 43 |
| Source records / citations (_APID) | 85 / 1,225 |
| Media objects (OBJE) | 49 — **zero have FILE paths** (images stayed on Ancestry) |
| Events: BIRT / DEAT / BURI / MARR / RESI / PROB / Arrival | 105 / 80 / 55 / 51 / 123 / 3 / 4 |
| Date span | 1640 – 2025 |
| Places (PLAC strings) | 506 |

**Geography (drives source priority):** Pennsylvania (Montgomery, Chester, Philadelphia,
Lancaster) ≫ Massachusetts > Kentucky (Simpson Co.) > New York (Nassau/Hempstead) >
Tennessee > New Jersey. European origins: Sachsen (Berthelsdorf/Freiberg), Silesia
(Harpersdorf, Langneundorf), Nordrhein-Westfalen (Mülheim/Köln), Netherlands
(Apeldoorn, Leiden, Leeuwarden), Ireland (Cork).

**Ethnic/religious clusters:** Schwenkfelder (Silesia → Berthelsdorf → PA 1734),
Mennonite (Lancaster), Presbyterian. These have records that national databases do not index.

**Surnames:** Cassel, Ahearn, Davidson, Rittenhouse, Heebner, Brant, Bell, McCrary,
Peters, Redden, Lukens, Dewees, Sevier, Wiegner.

### Data-quality defects found (the "untrusted data" problem in miniature)

1. **`Lehi, UT, USA` / `Provo, UT, USA` appear 84 times, but only as the
   publication place of Ancestry's own source records (PUBL/PLAC), never as an
   event place.** The ingest rejects them if they ever appear on an event.
2. **Four spellings of one country:** `USA`, `United States of America`,
   `United States`, and bare state names. Same for `Germany` / `Allemagne` / `Schlesien`.
3. **Malformed place:** `Langneundorf, Silesa, , Germany` (typo + empty jurisdiction).
4. **Modern-vs-historical jurisdiction mix:** `Nieder, Harperdorf, Silesia, Poland`
   uses a German village name under a modern country; needs GOV/Kartenmeister mapping.
5. **Citations are Ancestry-relative.** `_APID 1,62910::3230778` = dbid 62910, record
   3230778. Meaningless outside Ancestry unless we keep a dbid → collection-name map.
6. **Media orphaned.** 49 OBJE records carry `_OID`/`_PID`/`_ENCR` handles only.
7. **Living people present** with voter-registration citations. Privacy policy needed
   before anything is shared or fed to a model.

## 2. Taxonomy (CSV `Category` column)

| Code | Category | Why it matters |
|---|---|---|
| A | Tree Format | Ingest/export. GEDCOM 5.5.1 in, GEDCOM 7 (+GEDZIP) canonical, GEDCOM X for the evidence graph. |
| B | Hosted Tree | Other people's conclusions. Useful for hints, never for proof. |
| C | Vital | Birth/marriage/death. Primary or official-index evidence. |
| D | Census | Household snapshots every 10 years, 1790–1950. |
| E | Burial | Death date/place + family clustering; Find a Grave is user-contributed. |
| F | Military | Draft cards give exact birth date/place + physical description. |
| G | Immigration | Arrival, origin village, naturalization. |
| H | Newspaper | Obituaries and marriage notices — LLM extraction targets. |
| I | Church | Pre-civil-registration vitals; the Schwenkfelder/Mennonite/Dutch/Irish records. |
| J | Land/Probate/Tax | Wills are the best pre-1850 relationship proof. |
| K | Residence | City directories fill gaps between censuses. |
| L | Books | Published genealogies (secondary; often wrong but citeable). |
| M | Media | Photos and document images; Ancestry-hosted media is the immediate gap. |
| N | Place | Gazetteers and boundary history for normalization and "did this place exist then?" checks. |
| O | Name | Variant/phonetic matching. |
| P | DNA | Raw data is manual-download only everywhere; high privacy sensitivity. |
| Q | Reference | Notable-person link-outs (Sevier, Rittenhouse, Dewees). |
| R | AI Enablement | HTR/OCR, linkage training data, date parsing, proof-standard rubric. |
| S | Governance | Privacy and citation-portability policy. |

## 3. Trust tiers (CSV `TrustTier` column)

The AI core should weight evidence by tier, not treat every citation as equal.

| Tier | Meaning | Examples |
|---|---|---|
| T1 | Image of an original record | Death certificate, census page, parish register, will |
| T2 | Official or archival index/transcription | SSDI, state death index, NARA AAD, IPUMS |
| T3 | Curated secondary | Find a Grave memorial, obituary, published family history, DAR/SAR application |
| T4 | User-contributed tree | Ancestry member trees, FamilySearch Tree, Geni, WikiTree (WikiTree is better sourced, call it T3/T4) |
| T5 | AI-inferred (our own) | Suggested match, extracted fact from OCR — must always cite the T1–T3 it came from |
| ref | Reference data, not evidence | Gazetteers, name dictionaries, cM tables |

## 4. Access reality (verified Sep 2026)

| Source | Programmatic access | Verdict |
|---|---|---|
| FamilySearch | REST, OAuth2, free, **closed to public** — Innovator Program application required | Apply early; it is the single largest free index. Sandbox on approval. |
| Ancestry | **None.** Internal API rewritten early 2026, partners only. ToS bans scraping. | User-exported GEDCOM is the only lawful path. |
| Find a Grave | **None.** Ancestry-owned; ToS bans automation. | Store memorial IDs; user-initiated fetch only. |
| MyHeritage Family Graph | REST JSON, free, app-key approval | Read-only. Docs are old; confirm keys still issued. |
| WikiTree | REST JSON, free, no auth for public profiles | Use now. |
| Geni | REST JSON, OAuth, sandbox | Use later. |
| Chronicling America | loc.gov JSON/YAML API (legacy API retired 2025) | Use now; bulk OCR available. |
| NARA Catalog | REST v2, key by email to Catalog_API@nara.gov | Use now. |
| IPUMS full count | API for harmonized data; names need restricted-access application | Apply if we want linkage training data. |
| Open Archives (NL) | REST JSON, free | Use now for Dutch branch. |
| Gramps Web API | Self-hosted REST, AGPL-3.0 | Candidate backend; license decision needed. |
| DNA vendors | Manual raw-data download only, everywhere | Never automate; user uploads file. |

## 5. Suggested order of work (P0 rows)

1. Parse the 5.5.1 file, keep every `_APID`, build the dbid → collection map (S02).
2. Define the living-person rule and redact before any model sees the data (S01).
3. Place normalization: GeoNames + Wikidata + Newberry boundaries; flag the Lehi/Provo artifacts (N01–N03).
4. Apply to FamilySearch Innovator Program (B01) and email NARA for an API key.
5. Recover the 49 media files from Ancestry manually (M01).
6. Wire loc.gov newspaper search and WikiTree lookups as the first two live enrichment sources (H01, B04).
7. Encode the Genealogical Proof Standard as the AI's evidence rubric (R06) using the tiers above.

## 6. Status vocabulary

`todo` · `investigating` · `verified` (facts checked against the source) · `in-use`
(wired into a tool) · `blocked` (no lawful programmatic path) · `blocked-apply` (needs
an application) · `flag` (policy decision required) · `n/a` (not a data source, or a
decision recorded in `docs/`; tracked for completeness)
