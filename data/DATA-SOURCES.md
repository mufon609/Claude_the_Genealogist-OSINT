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
| T1 | Image of an original record | Death certificate, census page, parish register, will, a gravestone photograph (E05) |
| T2 | Official or archival index/transcription | SSDI, state death index, NARA AAD, IPUMS |
| T3 | Published secondary: printed or curated, not editable by its readers | Obituary, published family history, DAR/SAR application, cemetery transcription |
| T4 | Anyone can edit it | Ancestry member trees, FamilySearch Tree, Geni, WikiTree, Find a Grave, BillionGraves. A T4 page identifies a person but never builds their facts: accepting it writes the persona link, and the family memberships it states are created where the tree lacks them, undecided like its facts, never accepted and never the rule's ground; the rule may take the identity when the name and three of birth day, death day, burial place, a stated parent or spouse agree with the tree; a person whose accepted facts rest on T4 alone is marked so |
| T5 | AI-inferred (our own) | Suggested match, extracted fact from OCR — must always cite the T1–T3 it came from |
| ref | Reference data, not evidence | Gazetteers, name dictionaries, cM tables |

**A record's tier.** A record takes the tier of its holder, the registry row it came from: an ark is FamilySearch's
(D03), a memorial id Find a Grave's (E01), anything else the row it was archived under. Where a holder serves another
row's records under a collection of its own, that row's `ServedAs` column names the holder and words the collection's
name carries (`D03:Find a Grave` on E01, for FamilySearch's own index of the memorials), several separated by `;`, and
such a collection takes that row's tier: a memorial indexed at FamilySearch is still a page anyone can edit (T4), and
FamilySearch's Social Security collections carry C01's and C02's own. `tools/initdb.py --sync-sources` writes every
collection's tier from the column (`collection.trust_tier`, cleared where the column names none), and the tier read for a
record (`catalog.tier_sql`) is its collection's where its holder's own collection carries one, the holder's otherwise. A
collection first met when a record arrives (`tools/attach.py`, `tools/run_step.py`) takes its tier from the column the
same way when it is created.

**A tree file's row.** A GEDCOM is labelled with the exporter its own header names (`HEAD.SOUR`, with its `NAME` and
`CORP`), never assumed to be one vendor's. The ingest takes the Hosted Tree row whose name opens one of the names the
header gives ("Ancestry.com" opens "Ancestry.com Family Trees"), and writes that row's terms and cost on the artifact:
Ancestry's member-tree export is B02. A file whose header names no exporter with a row here is A05, a family tree file
of unknown origin: T4 like every compiled tree (someone's conclusions, which anyone could have edited, so it identifies
people and never builds their facts), with no terms assumed. A row for another exporter is added when a file from it
arrives, named so that its first words open the name its header gives.

### Evidence classes (`evidence-classes.csv`)

A tier classifies the source; a class classifies each piece of information a record gives. The Genealogical Proof
Standard reads every statement by three classes (`docs/RULE.md`, "The proof standard"), all words,
never numbers: the **source** (original: the record made at the event, or its image; derivative: an index, abstract or
transcript; authored: a compiled genealogy, a memorial page, a family tree), the **information** of that one field
(primary: from someone with first-hand knowledge, the record's own event; secondary: the rest; indeterminable), and the
**evidence** (direct: the field states the fact; indirect: it is worked out from something else). A family link's
statement is also **stated** by the record or **computed** by its indexer, and a derivative names the **original** it was
copied from: the words a record is named by in a proof. Which files are copies of one record is `same_record`'s
(`docs/DATA-ARCHITECTURE.md` §7 decision 15), never the original's words alone, which two people's records share; the rule
counts once a record of the same original about the same person's same event. A T2 index can hold primary information (a birth
register's own birth) and a T1 image secondary (the age on a census page): the two scales answer different questions.

One row per record kind and field: `kind`, `field`, `reads_as`, `standing`, the five classes, and `notes`. A record reads
as several kinds, most specific first (`catalog.record_kinds`): a FamilySearch record page as its own collection, its
Event Type and its collection's kind word (`FamilySearch: <words>`), then `familysearch-record`; a record read by the
model or a person as what its reader says the image is (`reading of an index`, or `reading` for the record made at the
event), the collection it is filed under, its registry row, the checklist rows of the steps it was fetched for
(`census household`, `death record`, the checklist's own words), then `reading`; any other page as its parser. A kind's
`reads_as` adds the kind it is a case of (`FamilySearch: Death` reads as `death record`). A collection's row gives a
reading filed under it its kind (an obituary index reads as `obituary`), and a source class only where everything filed
under it is of that class: the image filed under an index's citation is often the record the index points to (a
certificate, a newspaper page), which a reader that does not say what it read leaves original. The field is the fact type as `persona_fact.fact_type` stores it,
`<type> [<label>]` for one field label of its `region_json`, `relation` or `relation:<kind>` for a family link, and
`relation [<heading>]` for a relationship whose label ends with that heading (FamilySearch's relatives tables). Each
class is read from the most specific row that gives it, kind before field, then the rows every record shares (`*`),
then the default row of the source class, so a field nothing names reads indeterminable (`catalog.evidence_classes`).
`{year}` in an original's name is the record's own year. Two readings are the reading's own, not the table's: a date
worked out or bounded from another field (qualifier calculated, estimated, before or after: an age, a newspaper's own
date) is indirect evidence, and a relationship the reading marks computed is computed and indirect, one it marks stated
stated and direct (the record names the relationship itself). Both come from the record's
current reading: a statement written from an earlier reading is read through the same person on the page in the current
one (`catalog.statement_of`), so a page read again by a better parser reads by what that parser found.

**Standing.** A kind's `*` row may carry the standing the rule gives a record of that kind (`docs/TERMS.md`
§0's table): `automated`, the rule may take it; `identity`, a page anyone can edit that identifies a person, the rule
taking the identity and never a fact; `hint`, the owner decides. A record takes the standing of the most specific of its
kinds that gives one (`catalog.record_standing`), so a parser that serves many collections (`familysearch-record`, a
reading) gives none and its collection's kind decides; a record no kind gives a standing is a hint. Three limits stay rules
on the kinds: a `census household` is ground only on a form `data/record-forms.csv` says names every member (one it holds no form of is a person's to read), an `obituary` is ground only through the
relatives it names, and a `church register` entry is automated only when it is dated and names the parents.

Where a genealogist could contest a row, the table reads the class that leaves the decision to a person
(`docs/DATA-ARCHITECTURE.md` §7 decision 9): the Social Security application's birth date and parents read as secondary
(the applicant's own word), an obituary and its indexes as secondary, FamilySearch's relatives tables as computed save
what the page shows the record stating (the reader marks those stated: the roles a record of one event names, an
obituary's brothers and sisters, a marriage's spouse's parents, a relative's page's own record subject, the rows with a word on a census head's own page), and the Pennsylvania births and christenings index
as indeterminable (it does not name each entry's original). The NUMIDENT's parents read as stated, because the
application's own fields name them, and as secondary information like the rest of the application.

## 4. Access reality (verified Sep 2026)

| Source | Programmatic access | Verdict |
|---|---|---|
| FamilySearch | REST, OAuth2, closed to the public (Innovator Program) | **Not used**, the owner's decision. Its record and search pages are saved in the owner's browser by the page-saves-itself method and read by the `familysearch-record` and `familysearch-search` parsers; the decisions on them are automated from the saved page. |
| Ancestry | **Skipped.** No API, ToS bans scraping, record pages need a membership. The project's point is the records Ancestry charges for, found free. | User-exported GEDCOM is the only path in; cited records are fetched from free holders (`holders.csv`). |
| Find a Grave | **None.** Ancestry-owned; ToS bans automation. | Store memorial IDs; user-initiated fetch only. |
| Find a Grave photographs | None; each image saved in the owner's browser one at a time (`tools/save_image.js`) | Registry row E05 (T1): a memorial's photographs typed Grave by the page are fetch steps under the cemetery row of the person accepted as its subject, read by the transcription path into a card. |
| MyHeritage Family Graph | REST JSON, free, app-key approval | Read-only. Docs are old; confirm keys still issued. |
| WikiTree | REST JSON, free, no auth for public profiles, an appId on every request | Connector `wikitree` (B04) runs the compiled-genealogy step: searchPerson by name with the birth or death year and a two-year spread, each match's profile fetched with its relatives; T4, so every match is a card and never the rule's ground. |
| HathiTrust | full-text search behind a browser challenge; the data API wants a key | The compiled-genealogy step carries the full-text search prefilled (L01); the results are read in the browser. |
| Geni | REST JSON, OAuth, sandbox | Use later. |
| Chronicling America | loc.gov JSON/YAML API; 20 JSON requests a minute, 150 text-service requests a minute | Connector `loc_gov` (H01) runs obituary steps: collection search on surname and given name, the year, the state; each hit's OCR text archived. |
| 1950 census site | `1950census.archives.gov/api/search` (name, state, county; `scheduleId` for one schedule), IIIF page images; no stated rate limit | Connector `nara_1950` (D05) runs 1950 household steps at one request a second; a hit is a schedule whose matched row carries both names; its transcription and image archived. |
| Internet Archive | full-text search at `be-api.us.archive.org/fts/v1/search` (query-string syntax, `collection:` and `title:` filters, a hit names the item and its page), the advanced search at `archive.org/advancedsearch.php` (`title:("…")` as a phrase, JSON, the items with title, year and collections), item metadata at `archive.org/metadata/<id>` (server, directory, files), the reader's search inside at `<server>/fulltext/inside.php` (matches with page numbers), page images from `BookReaderImages.php`; no stated rate limit | Connectors `ia_newspapers` (H07: obituary steps within the newspaperarchive collection, the death year and the next), `ia_directories` (K01: items with directory in the title, the person's adult years) and `ia_books` (L02: everything else, hints; a fetch step naming a book asks the advanced search for its title and keeps the copies whose title carries it, up to three). Each hit: the item's metadata, the search inside it, up to three page images; the words around the match are the record's text. The New York marriage index items are here too, but their OCR does not carry names (the backlog's page-locating step). |
| VA Nationwide Gravesite Locator | a form that posts to `gravelocator.cem.va.gov/ngl/result` (name parts each with an exact / begins with / contains option, birth and death month and year, a cemetery or all); answers a declared tool with the results page; no robots.txt, no stated rate limit | Connector `va_graves` (E03): the cemetery row's search and the citations to the veterans' gravesites and BIRLS collections, by surname and first given name exact with the step's death year; the results page is the record, one persona per decedent (name, rank and branch, war period, dates of birth and death, cemetery, section and site), and on a dependent's row the veteran it names (Relationships: WIFE OF …) a persona related as written, the row's rank and branch the veteran's; T2, a kind the rule may take. |
| New Jersey death and marriage indexes (Reclaim The Records, on the Internet Archive) | the death index 2001-2017 as two plain CSV files (collection `njdeathindex`: name, birth date and place, death date), fetched whole and read locally; the marriage index 1901-2016 (collection `njmarriageindex`) as scanned index pages, one item per year, bride or groom index and surname range, a Text PDF with a poor OCR layer; both answer a declared tool | Connector `nj_death_index` (C09) runs the death record row alone: a connector declares the checklist rows it answers, and C09 sits on the birth and marriage rows too, so a marriage search at C09 is assisted and never answered with death rows. The surname's own rows out of the whole file are the record, a none run when none fits anyone. The marriage index is the holder of dbid 61253 in `holders.csv`, ahead of FamilySearch's collection (to 1980); no connector reads inside a scanned PDF, so its fetch steps are logged blocked pending the page-locating step the backlog describes for the New York marriage index. |
| Kentucky death and birth indexes (Reclaim The Records, on the Internet Archive) | one plain-text file per year, 1911-1989, in two items (`reclaim-the-records-kentucky-death-index-01911-1989`, 3-5 MB a year; `reclaim-the-records-kentucky-birth-index-01911-1989`, 7-11 MB a year), the file names read off `archive.org/metadata/<item>`; the state's own printout, every line opening with a carriage-control byte, a heading and a HIPAA notice on each page, fixed-width rows sorted by surname and given name: a death row the name, age, county of death as a five-letter code, county of residence, date, certificate volume, number and filing year; a birth row the name, date, birth number, county code, mother's maiden name, sex, date filed. Byte ranges are served (HTTP 206), and the files answer a declared tool; Public Domain Mark. The later death items are not read: 1990-2004 and 2011-2022 are scanned pages, 2005-2010 text files of another layout | Connector `ky_vital_index` (C06) runs the death and birth record rows for a Kentucky event (a search step's year equal to its birth year is the birth row's), and a fetch step whose citation of either index names its year; a year's file is fetched whole, since the runner sends no byte range, and the surname's rows (the given name's first letter kept, a married woman's other surnames asked on the death row) are the record, a none run when none fits anyone; a county code is read as "<County> County, Kentucky". The file's own citations of these indexes (dbids 3077 and 8788) name no year, so in `holders.csv` FamilySearch stays first and C06, the row's own source, is asked on those steps and logs none with the year wanted. |
| Alabama Department of Archives and History | CONTENTdm's JSON API: a collection search at `/digital/api/search/collection/<alias>/searchterm/<term>/…`, an item's fields and IIIF image at `/digital/api/collections/<alias>/items/<id>/false`, the collection list at `dmwebservices … dmGetCollectionList/json`; answers a declared tool | No connector: the surname files (Ancestry dbid 61266) are not among the 68 digital collections the API lists; the collection once taken for them (p17217coll3) is the World War I service records, another record set. |
| SAR Patriot Research System | the search form posts; `robots.txt` disallows `/patriot/search` to every agent | Assisted only: the step carries the search page, run in the owner's browser. |
| FamilySearch Digital Library | the book search answers a declared tool with a challenge script | Assisted only: the title search opens in the browser. |
| Pennsylvania Newspaper Archive | Open ONI's JSON page search (`/search/pages/results/?searchType=advanced&proxtext=…&date1=YYYY-MM-DD&date2=…&dateFilterType=range&format=json`), a page's OCR at `<page id>ocr.txt`, titles at `/newspapers/`; answers a declared tool; no stated rate limit | Titles 1789–2013, few after the 1920s. No connector yet: no reviewed person's obituary step is in Pennsylvania (the backlog names the work). |
| NARA AAD, the WWII Army enlistment file | a fielded search form (`display-partial-records.jsp`, dt=893) that answers a browser only: a declared tool gets 403 | Assisted: the step carries the search prefilled, the results page and a full record are saved in the browser and come in through `inbox/`; parsers `aad-search` and `aad-enlistment`. |
| NARA Catalog | REST v2, key by email to Catalog_API@nara.gov | Use now. |
| IPUMS full count | API for harmonized data; names need restricted-access application | Apply if we want linkage training data. |
| Open Archives (NL) | REST JSON, free, no key: `api.openarch.nl/1.0/records/search.json?name=&eventplace=&number_show=`, one record in A2A shape at `show.json?archive=&identifier=`; answers a declared tool (70 records for Sijtske Lieuwes in Friesland, 1721–1782) | The church row for a Netherlands-born person. No connector yet: none of them is reviewed (the backlog names the work). |
| Gramps Web API | Self-hosted REST, AGPL-3.0 | Not the backend (`docs/DATA-ARCHITECTURE.md` §7); export to Gramps XML instead. |
| DNA vendors | Manual raw-data download only, everywhere | Never automate; user uploads file. |
| Google News Archive | No API; a title's issues browsed at `news.google.com/newspapers`, one date found by Google Books' own site search restricted to `books.google.com` and a date (`tbm=bks`, `tbs=cdr:1,cd_min:…,cd_max:…`); the issue read and searched by page (its own "Search in this book") in the `books.google.com/books` viewer, whose plain Next/Previous paging can skip a page its own search still finds; each page's own image, fetched once at a person's pace from `books.google.com/books/content` (`id`, `pg`, `img=1`, the highest zoom the endpoint serves), unauthenticated and low-resolution (~575×462px for a two-page spread) | Registry row H08, holder for dbid 61843 ahead of Legacy.com; no connector, browser-paced only. Fetching the page itself, once, drew no challenge; a burst of requests probing zoom/img parameters drew a Google reCAPTCHA once. Per the owner (11 Sept 2026, `MEMORY.md`, `challenge-is-a-pause-not-a-stop`): a challenge at a download is a pause for the owner's hand, not a reason to treat the source as forever assisted — notify, wait, continue, never solve it in-session. Verified on the Boca Raton News, 27 Jan 1986 (Helen Sara Brant's obituary). |

## 5. Free holders of cited collections

`holders.csv` maps each Ancestry collection the tree cites (by dbid) to the
free holders of the same record set: the holder's registry row, the kind and
key of its collection, the collection page, and what the holder covers. Five
kinds: `fs_collection`, a FamilySearch indexed collection whose id is the key
and whose own search is prefilled from the citation; `fs_images`, a
FamilySearch images-only collection, browsed film by film with no search or
record page for a browser to save, so a step at such a holder stays on the
plan, fetchable, with the reason in its rationale, but never reaches
`tools/fetches.py`'s list; `url`, any other holder, the key
a search template filled from the citation's details ({given}, {surname},
{name}, {title}, {year}, {date}, {mdy} the publication date as Google Books'
own `cd_min`/`cd_max` take it ("27 Jan 1986" → "1/27/1986"), {place}, {city},
or {url} for the citation's own page), the holder's page opening when a
detail is missing; `memorial`, the
citation's own Find a Grave URL; `scanned_index`, an archive.org collection of
scanned index pages, one item per year, readable only through the
page-locating step BACKLOG.md describes for the New York State marriage
index — until that step exists, a citation at such a holder is a fetch step
with mode `blocked`. Every FamilySearch id was read off the site's
collection list with its record count (indexed) or "Browse Images"; the other
holders' search shapes were tried in the browser. Rows for the same dbid are in
order of preference: the Archive first for a cited book, then FamilySearch's
Digital Library, then HathiTrust. A cited collection with no row here has no
free holder yet and its fetch steps are `blocked`, and its registry row's notes
say so: the Pennsylvania death and birth certificates and veterans' burial
cards (the State Archives' records are on Ancestry Pennsylvania alone), the
Lancaster Mennonite and Presbyterian church records, the Korean and Civil War
draft records, the Alabama surname files (not among the state archives'
digital collections), and the Colorado voter file, which is living-person
data and is never fetched. A county probate collection is held film by film:
the row for the Massachusetts wills and probate points at the Franklin County
films the tree cites, browsed through the catalog's digitized index.

**New Jersey death index (dbid 61260) past 1929.** The FamilySearch row (D03)
covers only 1901-1903 and 1916-1929 (`New Jersey, Death Index, 1901-1903;
1916-1929`, FamilySearch 2843410). Reclaim The Records' release, on
archive.org (collection `njdeathindex`), was checked 13 Sep 2026: 2001-2017 is
served as two plain-text CSV files, one row per decedent (name, birth date and
place, death date) — `newjerseydeathindex_2001-2006_data_csv` and
`newjerseydeathindex_2006-2017_data_csv`; 1949-2000 and 1901-1903/1920-1929
(partial) are served as scanned index pages, one item per year and surname
range, the same shape as the New York marriage index (the backlog's page-locating entry); the NJ
Department of Health did not locate an index for 1904-1919 or 1930-1948, and
neither year range is on this holder. The two years this tree currently cites
under dbid 61260 (2015, 2016) are both in the 2006-2017 CSV, so the row added
to `holders.csv` points at that file directly and is placed ahead of the
FamilySearch row: `catalog.holders()` takes the first row for a dbid, with no
year-aware routing, and no citation in this tree falls in the FamilySearch
row's own 1901-1903/1916-1929 range. A citation in that range, or in the
1949-2000 scanned-page range, would need the same page-locating step the
backlog describes for the New York marriage index; none exists in this
tree yet.

## 5a. Where records exist (`jurisdictions.csv`)

The checklist builds a person's rows from reference data, never from one
family's places: `data/jurisdictions.csv` says, by US state or country (lower
case; `*` for anywhere), which records exist from when and which registry rows
hold them. Kinds: `vital_birth`, `vital_death`, `vital_marriage` (the year
statewide registration begins, the holder), `state_census` (its years, the
holder), `church` (the holders of church registers there), `civil` (a
country's civil registration from that year, parish registers before),
`land` (land warrants and deeds), `passenger` (the lists for a person born in
the year window, `from`/`to`). A place with no row of a kind gets that row
with no source, and the row says the data is missing: the fix for a new
family's places is a row here (with a registry row in `data-sources.csv` for
a new holder), never code. The table holds the places this tree's research
has needed so far. A record whose state is unknown is searched at every
state's holder of its kind the table knows.

`data/countries.csv` lists every country's name and the words records write
for it (Deutschland and Allemagne for Germany, USA for the United States); the
place resolver and the checklist read a country from a place string's last
part only, since a country's name earlier in a string is a town or county of
that name (Lebanon, Pennsylvania; Poland, Ohio). A country's name that is also
a US state (Georgia) is read as the state. Its `units` column lists the
first-level units a record writes where the country's name would stand
(England, Scotland, Wales and Northern Ireland, each with its own registration
and records): read as the country, and kept by the resolver as the place's
first-level unit, asked and verified like any other part of the string.

## 5b. The limits of one life (`life-limits.csv`)

Identity is tested, not assumed (`docs/DATA-ARCHITECTURE.md` §7 decision 12): a
family link or an accepted statement that a single life could not hold is a
question for the owner (`research_question` kind `identity`), and the standing
rule refuses a record that would add one. The bounds are data, one row each,
`limit`, `value` and the `reason` in words:

- **A parent's age at a child's birth.** A mother from 12 to 55, a father from
  13 to 80. The bounds are set where a genealogist calls a link impossible or
  nearly so, not where it is merely unusual: a mother of 45 or a father of 70
  is recorded often enough to pass. A hit asks, it never decides, so a bound
  may sit at the very edge of the possible. A parent whose sex the tree does
  not give is held to the wider of the two.
- **A child born after a parent's death.** Never after the mother's (0 months),
  up to ten months after the father's: about nine months of pregnancy and a
  month for a date known only to the month.
- **What a life holds after its end** (`after_death_types`): the death, a burial
  or a cremation, a will and its probate. Any other statement dated after the
  death is another person's or a wrong date; a statement before the birth is
  tested the same way, the birth itself excepted.

A date is compared over every day it can stand for (`catalog.date_span`): a
bare year spans the year, a month the month, a date marked about, estimated or
calculated two years more on either side, before and after leave a side open.
Only a limit broken over the whole of both spans counts, so an imprecise date
never raises a question a finer date of it might settle. One person in two
places in one census year has no bound to set and stays a rule of the code
(`Catalog.beyond_life`).

## 5c. Record forms (`record-forms.csv`)

A record is read by its form (`docs/DATA-ARCHITECTURE.md` §7 decision 21): the file holds one row for each shape a kind of
record took, read by `tools/forms.py`. Today its rows are the census: every federal schedule from 1790 to 1950 and every
state census `jurisdictions.csv` names (New York 1855 to 1925, Massachusetts 1855 and 1865). Years share a row only where
the form is the same (the 1800 and 1810 schedules of inquiries were identical); any change in what the form asks or how its
pages are laid out is a row of its own, so 1830 and 1840, or 1915 and 1925, are two rows. The grouping decision 21 speaks of
(the head alone 1790 to 1840, every member and no relationship 1850 to 1870, a relationship to the head 1880 to 1950) is
read from the rows' `names` and `relationship` columns, not from how rows are cut.

The columns, one form per row:

- `id` (`us-1900`, `ny-1925`, `us-1800-1810`), `kind` (the record kind as `evidence-classes.csv` names it, `census
  household`), `jurisdiction` (`united states`, or a state as `jurisdictions.csv` writes it) and `years` (`;`-separated).
- `lost`: what the sources say was lost of the form's schedules, empty where they say nothing. The 1890 population schedules
  survive only in fragments, so the checklist's 1890 row is not applicable, as before.
- `names`: `head` (the head of the family named, the rest counted) or `every member`.
- `relationship`, `birth`, `parents_birthplace`: the form's own words for each person's relationship to the head, for what it
  states of a birth (an age, a month of birth within the year, the month and year of 1900) and for the birthplace of each
  person's father and mother; empty where the form has no such column. The 1870 schedule's Father of foreign birth and Mother
  of foreign birth are marks, not places, so its `parents_birthplace` is empty; the 1940 and 1950 schedules ask the parents'
  birthplaces only of the persons on their sample lines, and the words say so.
- `states`: every column of the form in its own words, `;`-separated, grouped as the form groups them.
- `locators`: what places an entry on the form, in these terms: `state`, `county`, `minor_division` (the township, town,
  city, borough or precinct the heading names), `ward`, `block`, `supervisor_district`, `enumeration_district`,
  `assembly_district`, `election_district`, `page`, `sheet` and `sheet_letter` (the A or B side), `line`, `dwelling` and
  `family` (the numbers in order of visitation: the 1940 schedule's number of household in order of visitation is its
  `family`, the 1950 serial number of dwelling unit its `dwelling`), and `image`, the page's image. Only what the row's
  sources document is listed: no page or line numbering is listed for the New York censuses before 1925 or for
  Massachusetts, whose sources give the questions alone.
- `page`: the locators that together make one page (the state, the districts and the sheet with its side from 1900 to
  1940), or `image` where the sources do not document how pages are numbered, so that only the page's image tells two pages
  apart.
- `household`: how a household is bounded on a page, `;`-separated: `one line` (a form that names the head alone: the line
  is the household), `family number` (a run of lines opened by the line carrying the family's number in order of
  visitation), `opened by the head` (the head's line opens the run: the enumerators' instructions from 1850 put the head, or
  the father, mother or other ostensible head, first), `over a page break` (lines are filled and pages numbered in the order
  visited, so a run continues from the last line of one page to the first of the next), `one schedule` (1890, one schedule
  per family) or `unbounded` (New York 1892: no relationship and no family number).
- `lines`: where a household is a run of lines (`family number` or `opened by the head`), the locators the household script
  (`tools/households.py`) reads as an entry's line on the form, in order, and empty where it is not: `image_line`, a
  reading's own line counted down its image, on every such form, and `line`, the copy's own Line Number, on the 1925 New York
  form alone, whose index gives one person to a page. FamilySearch's line is not read on the federal schedules: on the 1900
  Lukens record page every member, the page's own person too, carries line 10, while the sheet's image has the head on line 4
  and his daughter on line 7. A form whose household is one line, one schedule or unbounded has none. Whether a copy's line
  is the form's own is what a form's calibration finds; the column is what the script reads until then, and calibration
  changes it.
- `source`: the addresses the row rests on, `;`-separated, each opened when the row was written; `notes`: what the sources
  say of the heading, the numbering of pages and lines and the order of names, in words.

A reader keeps every locator an entry carries as the entry's place on its page, in its persona's `region_json` as
`{"form": <id>, "locators": {<locator>: <value as written>}}` (`tools/extract.py` `page_place`; the screen's transcription
path, `app/person/server.py` `form_place`): the form's own and those its copy adds, which no form prints (FamilySearch's
household identifier, its microfilm, digital folder and image numbers and the NARA publication and roll, the 1950 census
site's schedule id, a reading's line counted from the top of its image, `image_line`). A locator is no fact about the
person, so it is never a `persona_fact`, and the region is written once with the persona, as the evidence is insert-only:
a better reading writes new personas with their own regions. Whether a copy's line or household identifier is the form's
own is what a form's calibration finds (decision 21), never assumed here. The household script groups an entry by its form's
`page`, `household` and `lines` (`docs/HOUSEHOLDS.md`): a page is the form's page locators all held
alike, the county a copy's locators lack read off the entry's census residence (the 1925 New York index writes the county
only in its event place).

Sources. The federal rows rest on the Census Bureau's own: *Measuring America: The Decennial Censuses From 1790 to 2000*
(2002), whose pages reproduce each schedule and its instructions (cited by the PDF's page), the questionnaire pages of
census.gov for 1790 to 1860 (their index of questions) and the enumerators' instructions for 1850 to 1950, as census.gov
serves them (the 1950 manual is a scan without a text layer, read from its images); the 1890 row also on the
National Archives' *Prologue* account of the schedules' loss. The New York rows rest on the New York State Library's list
of the questions of each state census and, for 1915 and 1925, the State Archives' finding aids for the schedules (series
A0275 and A0276), which describe each page's heading. The Massachusetts rows rest on a genealogist's published list of the
1855 and 1865 columns: the Massachusetts Archives' and the FamilySearch Research Wiki's pages on these censuses answered a
script with a browser challenge when they were opened (5 October 2026), and are a better source to cite once read.

## 6. Deferred work

Lives in `BACKLOG.md`. Rows whose `Status` is `blocked-apply` or `todo` with a
P0 priority are the registry's view of the same items.

## 7. Status vocabulary

`todo` · `investigating` · `verified` (facts checked against the source) · `in-use`
(wired into a tool) · `blocked` (no lawful programmatic path) · `blocked-apply` (needs
an application) · `flag` (policy decision required) · `n/a` (not a data source, or a
decision recorded in `docs/`; tracked for completeness)
