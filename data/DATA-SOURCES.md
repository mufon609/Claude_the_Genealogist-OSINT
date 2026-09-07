# Data Sources — Investigation Notes

Companion to `data-sources.csv`. The CSV is the checklist; this file holds the
reasoning that does not fit in a cell.

## 1. What the seed file told us

`trees/ahearn/imports/2026-09-05_Ahearn-Family-Tree.ged` (named copy; the archive
holds the hashed master) — Ancestry export, GEDCOM 5.5.1, 2025.08 exporter, dated
5 Sep 2026.

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
   3230778. The ingest keeps the dbid → collection map in the `collection` table so
   they mean something outside Ancestry.
6. **Media orphaned.** 49 OBJE records carry `_OID`/`_PID`/`_ENCR` handles only.
7. **Living people present** with voter-registration citations. The living-person
   policy in `docs/DATA-ARCHITECTURE.md` §7 governs what is shared or fed to a model.

## 2. Taxonomy (CSV `Category` column)

| Code | Category | Why it matters |
|---|---|---|
| A | Tree Format | Ingest/export. GEDCOM 5.5.1 in, GEDCOM 7 (+GEDZIP) canonical, GEDCOM X for the evidence graph. |
| B | Hosted Tree | Other people's conclusions. Useful as leads, never as proof. |
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

The tier says what *kind* of source a record is. It is shown next to every
source and never turned into a score; the decision on a fact stays three-state.

| Tier | Meaning | Examples |
|---|---|---|
| T1 | Image of an original record | Death certificate, census page, parish register, will |
| T2 | Official or archival index/transcription | SSDI, state death index, NARA AAD, IPUMS |
| T3 | Published secondary: printed or curated, not editable by its readers | Obituary, published family history, DAR/SAR application, cemetery transcription |
| T4 | Anyone can edit it | Ancestry member trees, FamilySearch Tree, Geni, WikiTree, Find a Grave, BillionGraves. A T4 record is a lead and a card, never a source the rule trusts on its own, and a person whose accepted facts rest on T4 alone is marked so |
| T5 | AI-inferred (our own) | Suggested match, extracted fact from OCR — must always cite the T1–T3 it came from |
| ref | Reference data, not evidence | Gazetteers, name dictionaries, cM tables |

## 4. Access reality (verified Sep 2026)

| Source | Programmatic access | Verdict |
|---|---|---|
| FamilySearch | REST, OAuth2, free, **closed to public** — Innovator Program application required | Apply early; it is the single largest free index. Sandbox on approval. |
| Ancestry | **None.** Internal API rewritten early 2026, partners only. ToS bans scraping. Record pages and images need a membership this account lacks. | User-exported GEDCOM is the only lawful path in; cited records are fetched from free holders (`holders.csv`). |
| Find a Grave | **None.** Ancestry-owned; ToS bans automation. | Store memorial IDs; user-initiated fetch only. |
| MyHeritage Family Graph | REST JSON, free, app-key approval | Read-only. Docs are old; confirm keys still issued. |
| WikiTree | REST JSON, free, no auth for public profiles, an appId on every request | Connector `wikitree` (B04) runs the compiled-genealogy step: searchPerson by name with the birth or death year and a two-year spread, each match's profile fetched with its relatives; T4, so every match is a card and never the rule's ground. |
| HathiTrust | full-text search behind a browser challenge; the data API wants a key | The compiled-genealogy step carries the full-text search prefilled (L01); the results are read in the browser. |
| Geni | REST JSON, OAuth, sandbox | Use later. |
| Chronicling America | loc.gov JSON/YAML API; 20 JSON requests a minute, 150 text-service requests a minute | Connector `loc_gov` (H01) runs obituary steps: collection search on surname and given name, the year, the state; each hit's OCR text archived. |
| 1950 census site | `1950census.archives.gov/api/search` (name, state, county; `scheduleId` for one schedule), IIIF page images; no stated rate limit | Connector `nara_1950` (D05) runs 1950 household steps at one request a second; a hit is a schedule whose matched row carries both names; its transcription and image archived. |
| Internet Archive | full-text search at `be-api.us.archive.org/fts/v1/search` (query-string syntax, `collection:` and `title:` filters, a hit names the item and its page), item metadata at `archive.org/metadata/<id>` (server, directory, files), the reader's search inside at `<server>/fulltext/inside.php` (matches with page numbers), page images from `BookReaderImages.php`; no stated rate limit | Connectors `ia_newspapers` (H07: obituary steps within the newspaperarchive collection, the death year and the next), `ia_directories` (K01: items with directory in the title, the person's adult years) and `ia_books` (L02: everything else, hints). Each hit: the item's metadata, the search inside it, up to three page images; the words around the match are the record's text. The New York marriage index items are here too, but their OCR does not carry names (the backlog's page-locating step). |
| NARA AAD, the WWII Army enlistment file | a fielded search form (`display-partial-records.jsp`, dt=893) that answers a browser only: a declared tool gets 403 | Assisted: the step carries the search prefilled, the results page and a full record are saved in the browser and come in through `inbox/`; parsers `aad-search` and `aad-enlistment`. |
| NARA Catalog | REST v2, key by email to Catalog_API@nara.gov | Use now. |
| IPUMS full count | API for harmonized data; names need restricted-access application | Apply if we want linkage training data. |
| Open Archives (NL) | REST JSON, free | Use now for Dutch branch. |
| Gramps Web API | Self-hosted REST, AGPL-3.0 | Not the backend (`docs/DATA-ARCHITECTURE.md` §7); export to Gramps XML instead. |
| DNA vendors | Manual raw-data download only, everywhere | Never automate; user uploads file. |

## 5. Free holders of cited collections

`holders.csv` maps each Ancestry collection the tree cites (by dbid) to the
free holders of the same record set: the holder's registry row, the kind and
key of its collection (a FamilySearch collection id, a site, a memorial URL
from the citation itself), the collection page, and what the holder covers.
Every FamilySearch id was checked by opening the collection page. Rows for the
same dbid are in order of preference. A cited collection with no row here has
no free holder yet and its fetch steps are `blocked`; the Pennsylvania death
and birth certificates are the notable case, viewable only through Ancestry
(free with a Pennsylvania address) since the State Archives collections left
Power Library.

## 6. Deferred work

Lives in `BACKLOG.md`. Rows whose `Status` is `blocked-apply` or `todo` with a
P0 priority are the registry's view of the same items.

## 7. Status vocabulary

`todo` · `investigating` · `verified` (facts checked against the source) · `in-use`
(wired into a tool) · `blocked` (no lawful programmatic path) · `blocked-apply` (needs
an application) · `flag` (policy decision required) · `n/a` (not a data source, or a
decision recorded in `docs/`; tracked for completeness)
