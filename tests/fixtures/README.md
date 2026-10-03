# Fixtures

Saved real pages, one per parser, read by `tools/check.py` (through `tests/checks/parsers.py`) on a scratch catalog. They are the owner's own family documents
in the owner's repository; every page is public at its holder except where the rights column says otherwise. A fixture is
the bytes as the archive holds them (or as the browser saved them), never edited: the parser is checked against the page
as it is. The same holds for everything else the harness reads, the scenarios' answers included: every response body, row,
page and record is real, archived or captured from its holder, but for two stand-in files no code looks inside; what is
simulated, and those two stand-ins, are named in "What is simulated" at the end.

| File | Holder and page | Parser | Rights |
|---|---|---|---|
| `findagrave-memorial-78019650.html` | Find a Grave memorial 78019650, Abram C Brant (1880–1961), saved by the page-saves-itself method | `rule:findagrave-memorial` | user-contributed page, Find a Grave terms |
| `findagrave-memorial-143847338.html` | Find a Grave memorial 143847338, John Davidson (1822–1877) of Franklin, Kentucky, a Union veteran, the page's veteran badge (a "V" and a hidden "Veteran") beside his name, as the archive holds it | `rule:findagrave-memorial` | user-contributed page, Find a Grave terms |
| `findagrave-memorial-130509402.html` | Find a Grave memorial 130509402, John Georgi Young Davidson (1876–1946), whom the file writes John Y, with the parents, wife, siblings and children it lists, as the archive holds it | `rule:findagrave-memorial` | user-contributed page, Find a Grave terms |
| `findagrave-search-davidson-robert-1915-2004.html` | Find a Grave memorial search, Robert Davidson 1915–2004, Ohio, saved by the owner | `rule:findagrave-search` | Find a Grave terms |
| `familysearch-census-1940-KQX1-VT9.html` | FamilySearch record ark:/61903/1:1:KQX1-VT9, United States Census 1940, the Ahearn household of Caln Township, Chester County, Pennsylvania | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1900-M9HX-SWP.html` | FamilySearch record ark:/61903/1:1:M9HX-SWP, United States Census 1900, the Davidson household of Adairville, Logan County, Kentucky | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1950-6X5P-KT7T.html` | FamilySearch record ark:/61903/1:1:6X5P-KT7T, United States Census 1950, the Hahnle household of Lindenhurst, Suffolk County, New York | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1950-6XYS-NQ16.html` | FamilySearch record ark:/61903/1:1:6XYS-NQ16, United States Census 1950, the Fred M Ahern household of Pennsylvania, saved from a search's results rather than a citation, as the archive holds it under its file name with no record id; the household record the loop's scenarios accept member by member; the son's and the father's Name fields keep another name each collapsed beneath the one shown | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1900-M3QL-XYW.html` | FamilySearch record ark:/61903/1:1:M3QL-XYW, United States Census 1900, the Milton Lukens household of Montgomery County, Pennsylvania, focused on his daughter Charlotte A Lukens, every member's own details table open; each Event Place shows Norriton Township and keeps Norristown collapsed beneath it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1940-KQT1-2MF.html` | FamilySearch record ark:/61903/1:1:KQT1-2MF, United States Census 1940, the Robert Davidson household of Hempstead, Nassau County, New York; the head's own Birth Date field is a bare year (1914), the census index's own estimate from his age, not a birth as written | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1920-MXBF-NHK.html` | FamilySearch record ark:/61903/1:1:MXBF-NHK, United States Census 1920, the James J Ahearn household of Northampton, Hampshire County, Massachusetts; the mother's and two sons' rows carry a blank relationship cell, testing that sex, age and birthplace still land in their own columns rather than shifting into it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-ohio-death-index-VKBL-4FN.html` | FamilySearch record ark:/61903/1:1:VKBL-4FN, Ohio, Death Index, Robert Edgar Davidson; the page's own Event Date field shows his time of death ("09:50 PM") and keeps the date, 5 Apr 2004, collapsed beneath it; his parents given by one surname each, Davidson and Bell, and an Other People row reading UNKNOWN | `rule:familysearch-record` | public record; FamilySearch terms |
| `nara-1950-schedule-3947385.json` | The 1950 census site's answer for schedule 3947385, enumeration district 30-392, Nassau County, New York, as the connector archived it | `rule:nara-1950-schedule` | public record, National Archives |
| `aad-search-davidson-robert-15.html` | The National Archives' AAD enlistment search, DAVIDSON ROBERT born '15, saved in the browser | `rule:aad-search` | public record, National Archives |
| `familysearch-pennsylvania-and-new-jersey-church-and-t-1909-HHGB-BQ3Z.html` | FamilySearch record ark:/61903/1:1:HHGB-BQ3Z, Pennsylvania, Births and Christenings, 1709-1950 (the free holder of Ancestry's Pennsylvania and New Jersey Church and Town Records, cited under the church register row), the birth of Helen Sarah Brandt at Philadelphia, 11 Jul 1909, with her parents Abram C Brandt and Charlotte D. Lukens Brandt, saved by the page-saves-itself method as the archive holds it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-massachusetts-birth-records-1907-FXJ3-Z7X.html` | FamilySearch record ark:/61903/1:1:FXJ3-Z7X, Massachusetts State Vital Records, the birth of Frederick Michael Ahearn at Northampton, 22 May 1907, indexed as "Ahearu" with parents "James J. Ahearu" and "Annie E. Scauusl"; the page's heading says Death, its fields say Birth | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-kentucky-death-records-1911-1967-1_1-NSGC-PXX-ollie-duke-davidson.html` | FamilySearch record ark:/61903/1:1:NSGC-PXX, Kentucky, Deaths, 1911-1967, Lena Howard Bell as her son Ollie Duke Davidson's death record names her, under the page's leading "Mentioned in the Record of" banner; an Other People row reads ", [1918]", a year and no name | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-washington-petitions-for-naturalization-1967-6ZR5-N8ML.html` | FamilySearch record ark:/61903/1:1:6ZR5-N8ML, Washington, Naturalization Records, 1850-1994, Noi Davidson's petition, Tacoma, 11 Dec 1967 | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-social-security-numident-1956-6KML-FS23.html` | FamilySearch record ark:/61903/1:1:6KML-FS23, United States, Social Security Numerical Identification Files (NUMIDENT), 1936-2007, Raymond Earl Davidson, whose own Parents and Siblings table names Robert Davidson and Ruth Peters with no role word | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-search-census-1950-ahearn-frederick-micheal.html` | FamilySearch record search results, the 1950 census collection for Frederick Micheal Ahearn born 1930–1934 in Pennsylvania, 142 results, page 1 of 8, saved from the step's prefilled link | `rule:familysearch-search` | FamilySearch terms |
| `familysearch-search-kentucky-deaths-bell-lena-howard.html` | FamilySearch record search results, the Kentucky Deaths 1911-1967 collection for Lena Howard Bell, 529 results, page 1 of 27, saved in the browser as the search a cited Kentucky death record (no ark of the holder's in the citation) was looked for by hand; the first row names her as a mother on another's record with no dates of her own | `rule:familysearch-search` | FamilySearch terms |
| `familysearch-massachusetts-marriage-search-no-results-annie-e-scannell.html` | FamilySearch record search results, the Massachusetts, State Vital Records collection for Annie E Scannell, saved in the browser as the search her cited marriage index citation (no ark of the holder's) was looked for by hand; the site answered "No Results", saved from the search's own URL as any results page is, 19 Sept 2026 | `rule:familysearch-search` | FamilySearch terms |
| `aad-enlistment-247275.html` | The AAD enlistment record 247275, Robert C Davidson, saved in the browser | `rule:aad-enlistment` | public record, National Archives |
| `familysearch-kentucky-death-index-1946-QKC9-LBLM.html` | FamilySearch record ark:/61903/1:1:QKC9-LBLM, Kentucky, Vital Record Indexes, the death of John Y Davidson in Simpson County on 11 Jun 1946 (the file and his memorial say the 10th), his birth calculated from his age, as the archive holds it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-kentucky-vital-record-indexes-1915-QKH2-XT3L.html` | FamilySearch record ark:/61903/1:1:QKH2-XT3L, Kentucky, Vital Record Indexes, Robert E Davidson's birth, 19 Feb 1915 in Logan County, his mother Lena Bell; saved as a file, archived under its file name as the archive holds it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-massachusetts-marriage-index-1901-N445-429.html` | FamilySearch record ark:/61903/1:1:N445-429, Massachusetts, State Vital Records, the marriage of James J. Ahern and Annie E. Scannell at Amherst, 26 Jun 1901 (the file says Northampton, citing this record), the groom's page: his parents Thomas, given by one name, and Alice McGee, and the bride's parents Dennis, given by one name, and Mary Castello, filed in his Extended Family as Father-in-law and Mother-in-law, as the archive holds it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-obituary-collection-2004-QL71-6HG3.html` | FamilySearch record ark:/61903/1:1:QL71-6HG3, U.S., Obituary Collection, Robert Edgar Davidson's obituary in the Bucyrus Telegraph Forum, 2004: born 19 Feb 1915 at Woodburn, Kentucky, his parents, his brothers and sisters, his children and their families by name alone; archived under the file's own citation (Ancestry's 1,7545::2520318), as the archive holds it | `rule:familysearch-record` | FamilySearch terms |
| `familysearch-tennessee-marriage-index-1895-VNXD-RXW.html` | FamilySearch record ark:/61903/1:1:VNXD-RXW, Tennessee, State Marriage Index, John Davidson and Lena Bell, 25 Dec 1895, Robertson County: two names, the date and the county, nothing else, as the archive holds it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-social-security-claims-index-6K99-MWLL.html` | FamilySearch record ark:/61903/1:1:6K99-MWLL, United States, Social Security Applications and Claims Index, Robert Edgar Davidson, born 19 February 1915 at Auburn, Kentucky, his parents John Y Davidson and Lena Bell, as the archive holds it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-search-kentucky-birth-index-robert-edgar-davidson.html` | FamilySearch record search results, the Kentucky Birth Index 1911-1999 for Robert Edgar Davidson, a hundred rows of Davidsons born from 1911 to 1999, as the archive holds it | `rule:familysearch-search` | FamilySearch terms |
| `va-gravesite-search-davidson-raymond-2007.html` | The VA Nationwide Gravesite Locator's results page for Davidson, Raymond, died 2007, as the connector's posted search received it: two decedents, the second Raymond E Davidson (1939–2007) | `rule:va-gravesite` | public record, Department of Veterans Affairs |
| `va-gravesite-search-davidson-raymond-page1.html` | The same locator's first page for Davidson, Raymond with no year: ten of 22 decedents and the links to the next pages, as the connector received it on a scratch run | `rule:va-gravesite` | public record, Department of Veterans Affairs |
| `va-gravesite-search-davidson-raymond-e.html` | The same locator's page for Davidson, Raymond E, as the archive holds it: five decedents, two of them written Raymond E Davidson, the first (1939–2007) the harness's Raymond Earl Davidson and the second (1930–2021) another man | `rule:va-gravesite` | public record, Department of Veterans Affairs |

## Pages no parser reads

A real page the archive holds from a holder whose pages no parser claims, saved by the page-saves-itself method under the
fetch list's name and archived by `collect`: read by no `<stem>.expect.json` (the extractor fails it, which is what the
scenario that uses it is about), its `.manifest.json` the archive's own, byte for byte, so `sha256sum` against `archive/objects/sha256/…`
shows the page is the archived one.

| File | Holder and page | Rights |
|---|---|---|
| `mansfield-news-journal-obituary-193623-page-not-found.html` + `.manifest.json` | The archive's object `040d0989…` (18 September 2026, H05): the Mansfield News Journal's own answer when the link a cited obituary names (`mansfieldnewsjournal.com/news/stories/20040408/obituaries/193623.html`) was opened in the browser: its "Page Not Found (404)" page, which holds no obituary and no record of anyone, the paper's navigation and trending headlines of that day | the paper's page, its terms |

## From connector runs

| File | Where it came from | Parser |
|---|---|---|
| `wikitree-profile-Hubner-223.json` + `.manifest.json` | WikiTree's getProfile for Hubner-223 (David Hübner/Heebner, 1696–1784) with parents, spouses, children and siblings, fetched by the WikiTree connector on a scratch data root on 7 September 2026, not the live catalog; the manifest is its provenance | `rule:wikitree-profile` |
| `ia-search-inside-genealogicalreco01krie-heebner.json` + `.manifest.json` | The Internet Archive's search inside the item genealogicalreco01krie (Genealogical record of the descendants of the Schwenkfelders, 1879) for Heebner, with the pages the connector chose in the manifest's notes, from the same scratch run | `rule:ia-search-inside` |
| `locgov-ocr-sn89058321-1918-05-10-p2.json` + `.manifest.json` | loc.gov's page text for image 2 of The Commercial (Union City, Tennessee), 10 May 1918, a hit of Ollie Duke Davidson's obituary step run live on the catalog on 7 September 2026; the harness adds the step's kind (obituary), which the runner now writes on every response and did not then | `rule:loc-gov-ocr` |
| `ky-death-index-1946-davidson.txt` + `.manifest.json` | Five lines of Reclaim The Records' Kentucky death index file for 1946 on the Internet Archive, DAVIDSON JIMMIE to DAVIDSON L, John Y Davidson's (Simpson County, 11 Jun 1946, certificate 14205) among them: the bytes exactly as one byte-range request returned them, each line's carriage-control byte kept; the manifest gives the range, the whole file's URL, size and sha256. The shape of the derivative the Kentucky connector keeps, and its offline check's year file | `rule:ky-death-index` |
| `ky-birth-index-1915-davidson.txt` + `.manifest.json` | Four lines of the same release's Kentucky birth index file for 1915, DAVIDSON PRYCE to DAVIDSON RONALD, Robert Edgar Davidson's (Logan County, 19 Feb 1915, mother Lena H Bell) among them, fetched and kept the same way | `rule:ky-birth-index` |

A connector's response is read with the notes its manifest carries (the item, the pages chosen, what was searched for, the
step's kind), as the extractor reads it on arrival.

## Saved responses the connector checks and the runner's scenarios are answered with

Read by `tools/check.py`'s offline connector checks (`connectors.json` names them) and played back by the loop's `run`
action as a holder's answer, never parsed as a page of their own. Each is a real response with its manifest beside it:
where the archive holds the response, the manifest is the archive's own and the sha256 in it is the file's, so
`sha256sum` against `archive/objects/sha256/…` shows the bytes are the archived ones; the one response captured for the
harness has its own manifest saying so.

| File | Where it came from |
|---|---|
| `nj-death-index-2006-2017-excerpt.csv` + `.manifest.json` | Reclaim The Records' New Jersey death index 2006–2017 (a 69 MB CSV on the Internet Archive; the archive holds it as sha256 `c94cb11b…`, fetched 15 September 2026): the file's header line, every line under the surname Ahearn (31) or Evers (42), and the line of state file number 20150061197 (Noi Davidson, born 15 Jan 1929 at Morioka, died 12 Nov 2015), each exactly as the file holds it, in the file's order, line feed ends; the manifest names every line number. Frederick Ahearn (M), born 6 Nov 1932 at Coatesville, died 3 Apr 2016, is the Ahearn row that fits Frederick Micheal Ahearn Jr; no Evers row is Carol's |
| `ia-advancedsearch-title-schwenkfelder-families.json` + `.manifest.json` | The archive's own object (sha256 `986aaa76…`, 11 September 2026): the Archive's advanced search for texts titled "The Genealogical Record of the Schwenkfelder Families", as the books connector asks it; the three copies of the 1923 book |
| `ia-metadata-genealogicalreco0000samu.json` + `.manifest.json` | The archive's object `ccf44554…` (11 September 2026): the Archive's metadata for the copy genealogicalreco0000samu, which names the server and directory its search inside and page images are read from |
| `ia-search-inside-genealogicalreco0000samu-brant.json` + `.manifest.json` | The archive's object `90297f84…` (11 September 2026): the search inside that copy for Brant, three matches on two pages (182, 743) |
| `ia-search-inside-genealogicalreco0000samu-brandt.json` + `.manifest.json` | **Captured for the harness**, one request on 2 October 2026 23:47 UTC with the project's User-Agent, at `https://ia801406.us.archive.org/fulltext/inside.php?item_id=genealogicalreco0000samu&doc=genealogicalreco0000samu&path=%2F28%2Fitems%2Fgenealogicalreco0000samu&q=Brandt`: the same search inside the same copy for Brandt, the spelling the book's own index gives for Brant ("Brand, Brandt — see Brant"); six matches on five pages (159, 209, 257, 743, 763) |
| `ia-fts-newspapers-helen-brant.json` + `.manifest.json` | The archive's object `84cace00…` (12 September 2026): the Archive's full-text search of its newspapers for "Helen Brant", 119 issues of which the first 40 are the answer; three of them (St Joseph Herald Press 11 Feb 1967 and 8 Apr 1972, Corsicana Semi Weekly Light 28 Jan 1938) carry no year of their own, only the day in their title |
| `ia-fts-books-raymond-davidson-new-york.json` + `.manifest.json` | The archive's object `660fbefc…` (13 September 2026): the Archive's full-text search of its books for "Raymond Davidson" with New York and a genealogy title; its third hit is spinneyfamilygen00phil, a book the Archive lends |
| `ia-metadata-spinneyfamilygen00phil.json` + `.manifest.json` | The archive's object `ba021857…` (13 September 2026): the Archive's metadata for that lent book (`access-restricted-item` true) |
| `ia-fts-directories-raymond-davidson-new-jersey-towns.json` + `.manifest.json` | The archive's object `c5219b32…` (18 September 2026): the Archive's full-text search of its city directories for "Raymond Davidson" in directories titled for the towns Raymond Earl Davidson's events name, as the directories connector asks it; its one hit is martindalehubbel0003unse_r8g1, a book the Archive lends |
| `ia-metadata-martindalehubbel0003unse_r8g1.json` + `.manifest.json` | The archive's object `378d47ed…` (18 September 2026): the Archive's metadata for that lent book, the Martindale-Hubbell Law Directory 2014 (`access-restricted-item` true): the only hit of a run, so a none run whose every hit is lent |
| `ia-fts-newspapers-alicia-ahearn-empty.json` + `.manifest.json` | The archive's object `d6c20ff8…` (20 September 2026): the Archive's full-text search of its newspapers for "Alicia Ahearn", which holds nothing: the Archive's empty answer |
| `wikitree-search-davidson-noi-1929-empty.json` + `.manifest.json` | The archive's object `eb0a659a…` (13 September 2026): WikiTree's searchPerson for Noi Davidson born 1929, which holds nothing: WikiTree's empty answer |
| `ny-marriage-index-1959-page-970.jpg` + `.manifest.json` | The archive's object `c3dd7c98…` (7 September 2026): page 970 of Reclaim The Records' New York State marriage index for 1959 on the Internet Archive, as its reader serves the scan (3054 × 3530, 1.2 MB), the groom's row HAHNLE CHRIS M, license issued at HUNTING, 8/14, certificate 32801 among them: the image a scenario's reading is typed from. Never parsed by the harness |
| `va-gravesite-search-davidson-raymond-e.html` + `.manifest.json` | The archive's object `e6db8c20…` (14 September 2026): the VA Nationwide Gravesite Locator's results page for Davidson, Raymond, middle name beginning E, as the connector's posted search received it: five decedents, Raymond E Davidson (1939–2007) the first |
| `va-gravesite-search-davidson-noi.html` + `.manifest.json` | The archive's object `17c08be7…` (14 September 2026): the same locator's page for Davidson, Noi: one decedent, Noi Davidson (1929–2015) |
| `nara-1950-search-davidson-nassau-ed-30-392.json` + `.manifest.json` | The archive's object `9fda2c90…` (7 September 2026): the 1950 census site's own search for Davidson in Nassau County, New York, enumeration district 30-392: the one schedule (`nara-1950-schedule-3947385.json`, read as a page above) |
| `nara-1950-search-davidson-nassau-ed-30-393-empty.json` + `.manifest.json` | **Captured for the harness**, one request on 3 October 2026 00:06 UTC (2 October local) with the project's User-Agent, at `https://1950census.archives.gov/api/search?name=Davidson&state=NY&county=Nassau&ed=30-393&page=1`: the same search within the district beside it, which the site answers with nothing (`{"total":0,"size":25,"page":1,"results":[]}`): the census site's empty answer |

## Gazetteer answers

The place resolver's answers from GOV and Wikidata, fetched on a scratch copy of the live catalog on 2 October 2026 with the
project's User-Agent, planted by the `resolve` action of the loop's scenarios so no request goes out. GOV's data is CC BY-SA
(genealogy.net), Wikidata's CC0.

| File | What it holds |
|---|---|
| `gov-answers-langneundorf-berthelsdorf.json` | GOV's SOAP answers as the resolver caches them: `searchByName` for Langneundorf, Dłużec and Berthelsdorf, and `searchRelatedByName` for Dłużec within Schlesien and Berthelsdorf within Sachsen, Freiberg, Germany, Deutschland and Deutsches Reich |
| `wikidata-answers-ballyquirk.json` | Wikidata's API answers as the resolver caches them: the search for Ballyquirk, the four townlands' items, the units they lie in followed up P131, and the labels of them all |
| `wikidata-Q5321228-dluzec.json` | Wikidata's item for Dłużec (Lwówek Śląski), with its GOV id (P2503) and SIMC, as Special:EntityData serves it |
| `wikidata-Q104305769-ballyquirk.json` | Wikidata's item for the townland Ballyquirk in Killeagh, County Cork |
| `wikidata-Q502553-berthelsdorf-herrnhut.json`, `wikidata-Q27479092-berthelsdorf-weissenborn.json`, `wikidata-Q827807-berthelsdorf-liebstadt.json`, `wikidata-Q65183687-berthelsdorf-hainichen.json` | Wikidata's items for four Saxon Berthelsdorfs the geocoder answers with, read for their GOV ids (P2503); only the Weißenborn one carries one |

| `gov-answers-harperdorf.json` | GOV's SOAP answers for "Nieder, Harperdorf, Silesia, Poland" as the resolver caches them, fetched on a scratch data root on 3 October 2026 07:32–07:33 UTC with the project's User-Agent: `searchByName` for Nieder Harperdorf and Twardocice, and `searchRelatedByName` for Twardocice within Schlesien, Polen and Poland |
| `wikidata-Q7857426-twardocice.json` | Wikidata's item for Twardocice (Nieder Harpersdorf), as Special:EntityData serves it, fetched by the same scratch run on 3 October 2026 |
| `wikidata-Q200077-morioka.json`, `wikidata-Q11643491-tonan.json` | Wikidata's items for Morioka and for Tonan, its former name (P1365 with its dates): the live resolver's own cache files (`derivatives/geocode/wikidata/`, fetched 18 September 2026), copied byte for byte |

## Geocoder answers

`geocoder/nominatim-<place>.json`: the geocoder's (Nominatim's) answers to the queries the resolver asks, each a cache record
exactly as the live resolver kept it under `derivatives/geocode/nominatim/` (`{query, fetched_at, results}`, results as
Nominatim served them), copied byte for byte; the scenarios' `place_card` and `resolve` actions plant them in the scratch
resolver's cache under the file name it looks them up by (`geocoder: [...]`), so no request goes out. Data © OpenStreetMap
contributors, ODbL. Fetched by the live resolver on 5 September 2026 unless said otherwise. The United Kingdom's answers (`nominatim-united-kingdom.json`, 13 September; `nominatim-aberdeen-united-kingdom.json`, 3 October) are the live cache's; `nominatim-scotland-united-kingdom.json` and `nominatim-aberdeen-scotland-united-kingdom.json` were fetched on a scratch data root on 3 October 2026 07:39 UTC with the project's User-Agent.

| Files (`geocoder/nominatim-…`) | The query and what the geocoder answered |
|---|---|
| `new-egypt-ocean-county-new-jersey`, `new-jersey`, `auburn-kentucky` (7 September), `logan-county-kentucky`, `woodburn-kentucky`, `northampton-hampshire-massachusetts` | the place the query names, one answer each; New Egypt's two (the township's village and a postcode node) |
| `coatesville-chester-pennsylvania`, `pennsylvania`, `philadelphia-philadelphia-pennsylvania` | one answer each; the last the city alone |
| `philadelphia-pennsylvania` | two: the city and the county that is coterminous with it |
| `hempstead-nassau-new-york` | two: the Town of Hempstead and the Village of Hempstead in it |
| `morioka-japan` (15 September) | three: Morioka, Iwate Prefecture, and two streets named for it |
| `misawa-aomori-japan` | two: the city of Misawa and a quarter of it, under Aomori Prefecture (the first-level-unit import scenario) |
| `ogau-tonan-iwate-shiwa-japan`, `ogau-tonan-japan` | no answer: the geocoder knows no such place (a former name's words) |
| `langneundorf-lower-silesia`, `berthelsdorf-sachsen-germany` (six), `berthelsdorf-herrnhut-sachsen-germany`, `berthelsdorf-freiberg-sachsen-germany`, `ballyquirk-ireland` (four) | the answers the gazetteer scenario's resolver run reads |
| `nieder-harperdorf-lower-silesia-poland` (none), `nieder-lower-silesia-poland` (six, none of them Harpersdorf), `twardocice-pielgrzymka-lower-silesia-poland` (one) | the answers the resolver reads for "Nieder, Harperdorf, Silesia, Poland" before asking GOV |
| `united-kingdom`, `aberdeen-united-kingdom` | one answer each: the country, and Aberdeen City asked without Scotland |
| `scotland-united-kingdom`, `aberdeen-scotland-united-kingdom` | one answer each: Scotland, and Aberdeen City within it |
| `ballyquirk-cork-ireland` | **Captured for the harness**, one request on 2 October 2026 23:56 UTC through the resolver's own `nominatim()` with the project's User-Agent (the live cache holds no answer to this query): one answer, the Killeagh townland |
| `new-jersey-united-states`, `pennsylvania-united-states`, `massachusetts-united-states`, `michigan-united-states` (5 and 13 September) | one state boundary each (the state-abbreviation scenario) |
| `worcester-montgomery-county-pennsylvania-united-states`, `worcester-montgomery-pennsylvania-united-states`, `worcester-pennsylvania-united-states` | the same two places each, the village and the township (one card for one set of places) |
| `norristown-montgomery-pennsylvania-united-states`, `pottstown-montgomery-pennsylvania-united-states`, `warwick-bucks-pennsylvania-united-states`, `philadelphia-pennsylvania-united-states`, `northampton-hampshire-massachusetts-united-states` | one boundary each, Philadelphia the city and the county coterminous with it (the turn reading its places) |
| `cadillac-memorial-gardens-west-westland-wayne-county-michigan-united-states` (7 September) | one answer: Cadillac Memorial Gardens West Cemetery, which the string names without its last word (a part that is the start of a name) |
| `worchester-montgomery-pennsylvania-united-states`, `worchester-montgomery-county-pennsylvania-united-states` | no answer: the geocoder knows no such place, the spelling being Worcester's misspelt |
| `worchester-pennsylvania-united-states`, `worcester-township-montgomery-county-pennsylvania-united-states` | one answer each: a street of Nescopeck, and the owner's override's own query, Worcester Township (a part a spelling near the name) |
| `hemp-nassau-new-york-united-states`, `hempstead-nassau-county-new-york-united-states` | one answer, a lane named Hemp, and two, the Town of Hempstead and the Village of Hempstead in it, the override's own query (a part that is a truncation) |
| `mt-holly-burlington-new-jersey-united-states` (15 September), `mount-holly-burlington-county-new-jersey-united-states` | two each: Mount Holly Township and a peak of the same name in it, the string written Mt. and written out |
| `caln-township-chester-pennsylvania-united-states` | one boundary, Caln Township |

Not here: an Ancestry index page. The owner's account reaches Ancestry's record pages only through a membership offer
("Join Ancestry"), so no page could be saved and the parser stays unverified; the two pages archived under Ancestry record
ids are FamilySearch record pages.

## What each page must yield

Beside every fixture a parser reads sits `<stem>.expect.json` (the fixture's own name with its extension replaced, the way
`<stem>.manifest.json` sits beside a connector's response): the expectations `tests/checks/parsers.py` compares the reading
with, one reader for every page, so a page of another family needs a page and a sidecar and nothing else. A sidecar holds:

| Key | Meaning |
|---|---|
| `archive` | how the page is archived: `mime`, `source` (the registry id) and `locator` (`kind`, `value`), as the attach would archive it. Absent for a fixture with a manifest: the manifest is its provenance. |
| `notes` | what the run's log knew that the manifest does not (the step's kind), merged over the manifest's notes. |
| `extractor` | the parser that must claim the page, by the name of its extractor row. |
| `personas` | how many personas the reading writes: a number, exact, or `{"min": n}`. |
| `sequence` | `{"<n>": persona pattern}`: the persona at that sequence must match the pattern. |
| `every` | a persona pattern every persona must match. |
| `some` | a list of persona patterns; at least one persona matches each, or exactly `count` of them when the pattern says so. |
| `toward` | `{"<n>": {kind: count, …}}`: how many relations of each kind point at persona n from the others; `"only": true` forbids any other kind. |
| `none` | `place`: no fact anywhere carries that place as written; `name_ends`: no name ends with that text. |
| `parsed` | a pattern over the parsed page (`extraction.structured_json`): a dict matches the keys given, a list its length and each element in turn, a string equals, `null` is nothing, `{"$starts": s}` a prefix. |

A persona pattern: `name` (as written, exact), `name_has` (words the name contains, any case), `role` (the page's own word,
`""` for none), `sex`, `region` (texts the persona's `region_json` contains), `facts` (fact patterns each of which some fact
of the persona matches), `no_facts` (fact patterns none may match), `relations` (`kind`, `to` the sequence it points at,
`value` as written when it matters, `computed`: true when its `region_json` marks it the site's own inference, false when
the record states it). A fact pattern: `type`, and any of `value`, `value_starts`, `date`, `place` (matched
as a prefix of the place string as written), `alternate` (true: the fact holds a value the page keeps collapsed beneath the
one it shows, as its `region_json` marks it; false: it does not). A `why` on any pattern is printed with the failure and says what the page
taught. `tools/check.py --show` prints what each reading wrote, for writing a sidecar.

## The harness tree

`harness.ged` is cut from the owner's own export by `tests/checks/cut_gedcom.py`, never written by hand: the header and the
submitter record verbatim, the INDI and FAM records of the people the scenarios need, verbatim, and every SOUR record they
cite. The one edit the cut makes is dropping a line whose value points at a record outside the cut (a family, a person, a
media object), with the lines under it; so a person whose families all fall outside the cut stands in the file with no
link, as the file itself would hold a stranger. It holds the home person, their parents and grandparents on both sides,
two great-grandparents' households as two census pages name them (the 1940 and 1920 pages above), the great-grandmother's
parents (the memorial's subject and his wife), a great-great-grandfather's parents and his two entries in the file (the
file's own duplicate, for the merge), the 1900 household of a great-great-grandmother's parents, and one person apart from
them all, whose one citation is an application of the Sons of the American Revolution (the holder whose link prefills
nothing, for the loop's scenario of an assisted search). It is the only `.ged`
the commit guard allows. To cut it again from a fresh export, or from another family's:

```
python3 tests/checks/cut_gedcom.py <export.ged> tests/fixtures/harness.ged <INDI xref> ... --fam <FAM xref> ...
```

## The scenarios

`scenarios/<module>/<nn>-<name>.json` are what `tests/checks/scenario.py` walks, one scratch catalog each: the tree
ingested, then steps in order, each doing one thing and checking what it wrote or refused. Nothing in the walker names a
person: people are the harness file's own entry ids (`I…`, as `external_id` keeps them), records the label a step bound
them under, and expectations name the words a reason must carry. A scenario file:

| Key | Meaning |
|---|---|
| `title`, `line` | the check's name, and the ok line printed when it passes |
| `tree` | `file` (the GEDCOM under `tests/fixtures/`), `home` (the home person's entry id), `plan` (every person planned first) |
| `steps` | the list of steps; each is one action key with its arguments, `as` (a label to bind the result under), `say` (what the step is about), `at` (a timestamp the clock every tool reads stands at while the action runs, for a check that depends on writes sharing a second), and `expect` (a list of expectations) |

A value `"$label"` reads what a step bound; `"$label.key.0.key"` reads into it. A person is an entry id, `{"name": …}` or
`{"created": …}` (a person the rule made, by display name), or `"$label"`. A record is the label of the step that
archived it. A card is `{"record": label, "person": ref}` or `{"record": label, "persona": name as written[, "role": …]}`,
with `extraction` and `latest` to pick a reading; a step of the plan is `{"person": ref, "step_key": …}`, `step_key_like`,
`row_key`, `kind`, `status`, or `locator: {kind, value}`.

Actions: `plan` (`"all"` or people), `migrate` (`tools/initdb.py --migrate` on the scratch catalog itself, its printed
line; `{"reset_to": version}` first forgets every later version's own row, since a scratch catalog is born with every
migration already recorded applied, so a correction is met the way an older catalog upgraded through it would;
`"refused": true` when the correction refusing is the outcome expected, what it printed coming back as `refused`),
`sync_sources` (`tools/initdb.py --sync-sources` on the scratch catalog itself: the registry's rows and every
collection's tier, its printed line), `proof` (`tools/proof.py`'s summary of a `person`, one `fact` when named: its
whole, each fact also under `fact.<name>`, and its `text`), `dismiss` (a person's one open conflict question whose
detail carries `detail_has`, closed by the owner through `tools/log_search.py --dismiss` with a `note`), `attach`
(`fixture` into the inbox and `tools/attach_inbox.py`, `about` for the
owner's word), `archive` (a `fixture`, or a stand-in: `stand_in: "image"`, or a page with only a `saved_from` line,
`suffix` to make other bytes of the same page; `source`, `collection`, `locator`, or a `manifest`; `extract`, `match`
(people, `null` for the record's own), `rule` to run the standing rule too), `seed` (the same, for a page the harness only
reads by a typed reading), `reread`, `match`, `decide` (`card`, `status`, `note`, `by`, `choice`; `screen` through the person screen's own route, its answer in words as `summary`), `withdraw` (a `card`, or with `record` every decision the rule made on it),
`reconsider` (`dry`; its `rows`, and `wrote`, the audit rows the run wrote), `fact` (`tools/conclude.py fact` on `field` or `fields`), `assertion` (one statement decided through
`tools/conclude.py assertion`: by `record` and `event_type`, or a `membership` of the file), `place` (a persona fact
placed onto an event through `tools/conclude.py place`: `record`, `person`, `fact_type` find the fact; `event` is a
literal id or `{person, type, index}`, that person's nth event of the type in the person screen's own order),
`link_on_word`, `living`,
`transcribe` (a reading typed into the person screen's form: `record`, `form` with the persona's `line` or `bbox` and
`image_is`, `relations` to bound personas, `about`, `by` the reader, `llm:<model id>` or `user:<name>`), `view`, `save` (a stand-in written under the fetch list's own name for `holder` and `person` (the entry whose link has `url_has`, when the person has several there), into a `folder`;
`name` overrides that with the file's own name, to save a page under a browser's sanitized shape rather than the list's; `key` writes the
key under the page's own saved-from line as `tools/save_page.js` does when the list's call gave it one: `true` for the entry's own steps, or a
list of plan steps, a string that is no step's id written as given: a key naming a step the plan lacks), `collect` (its `lines` are each result as the tool prints it, its `sha` the record when one page came in), `log`, `reopen`, `step` (a plan step written by hand), `event` (a second event of a type a person already
carries, written by the harness itself for a path only a planted event exercises), `file_family` (a family of the
owner's own export that the cut leaves out, because another scenario reads its people without it, written as the
import writes it: `xref` the family's own id in the export, `partners` and `children`, each membership the file's
uncited claim, undecided), `divorce` (the owner's word ending a marriage through `tools/conclude.py divorce`: `a`, `b`,
`date`, each `evidence` a record's fact by `record`, `persona` as written and `fact_type`, with `citation`, and `note`),
`resolve_conflict` (a conflict question closed through `tools/conclude.py resolve`: the
`person`'s one open conflict whose detail has `detail_has`, or with `over_rule` the one the rule resolved, `keep` a bound
assertion id or `{record, event_type}` for that record's statement on the person's event of the type, `note`; a refusal
comes back as its `error`), `reopen_conflict` (a conflict the rule resolved, taken back by the owner through
`tools/conclude.py reopen`: the `person`'s one such question whose detail has `detail_has`, `note`), `place_card` (a place answer's card, its candidates the results of the
geocoder's real answers named under `geocoder`, planted in the cache), `older_matcher`, `legacy_card` (a card an older matcher wrote for the row at sequence `row`
of a results page `record`, put to `person`, planted undecided as that matcher's `version`: the matcher writes none now, so only
an older one can stand for reconsider to meet), `persona_link` (a person's link to a record's persona of a `role`, and
`persona` name and `sequence` row, set to `status`, the state a card an older matcher put up for a memorial's listed relative leaves once
decided; with `card`, the link that card's decision wrote on another row of the same name before a decision reached only its own
entry of the page, the shape the 0.7.5 migration corrects), `merge`, `cite`, `question` (a research_question row patched by
hand into a shape nothing today writes, found by `kind` and `detail_has` among the person's own and set from `set`, for
a regeneration to be checked against a prior state, such as a legacy truncated key).

Expectations: `last` (the action's result against a pattern), `bound`, `cards` (the cards on a record: `people`,
`kind`, `count`, `personas`), `card` (`status`, `kind`, `decided_by`, `decided_at`, `note`, `rationale`), `rule` (`taken`, `why`),
`facts` (key facts by status), `alias`, `linked`, `memberships`, `persons` (`count`, or `named` with `given` and
`surname`), `event` (`strings` by status, `shown`, `canonical_date`, `basis`, `events`), `family_event` (the events of a `type` on the family `a` and `b` are partners in: `events`, each one's date as written in date order, `dates`, how many statements each carries, `per_event`, in the same order, and with `record` its `statements` on them by status and `per_event` that record's alone), `disagreements`, `question`,
`assertions_on`, `links` (a person's link statuses on a record's personas, by `persona` name, `role` and `sequence` row), `is_subject`, `citations_held`,
`checklist_row`, `baseline`, `waiting`, `step`, `step_count`, `fetch_entries`, `fetch_call` (the call the list gives the save script for the page serving a `step`: its `call` text and the steps it `serves`), `search_log`, `named_for`, `audit`, `hints`,
`living`, `mode` (`planned` for the plan's own), `foundation`, `results_page`, `place_string`, `artifact` (its row,
`tier` as `catalog.tier_sql` reads it and `collection_tier` its collection's own), `artifact_where`, `classes` (a
record's statements on a person's events of an `event_type`, or on a family `link`, read by
`catalog.evidence_classes`: some statement's `source`, `information`, `evidence`, `relationship`, `original`),
`statement` (which reading a record's statements on a person's events of an `event_type` are read through,
`catalog.statement_of`: `current` or `earlier` each), `conflict_rule` (the rule's test on a conflict, `conclude.classes_decide`, on a person's event of a `type` and its `axis`,
date or place: `taken` and the reason, `why`), `extractor` (a reading's extractor row, `kind`, `name`, `model_id`, `version`,
`prompt_is_instruction` for the sha256 of `app/person/read_record.md`, and what the extraction kept: `image_is`, `year`,
`regions` of its personas), `person_persona`, `reach`, `trusted` (a `membership`, or a person's `event` of a type, on
trusted ground for the rule; `stating` a date or a place), `plan_idempotent`, `no_repeats`, `one_event` (no record fact
stated on two events of its type that a person or a family holds), `whole`, `file`,
`count`, `proposal_status`, `proposals_of`, `person_merged`, `find_person`, `listed`, `assertion_subject`. A `why` beside
an expectation is printed with its failure.

Patterns: a dict matches the keys given, a list its length and each element, a string or number equals; `{">=": n}`,
`{"<=": n}`, `{"has": x}` (a substring, or every substring of a list, or an element), `{"lacks": x}`, `{"starts": s}`,
`{"ends": s}`, `{"first": p}`, `{"len": n}`, `{"some": p}`, `{"none": p}`, `{"every": p}`, `{"not": p}`, `{"in": [..]}`,
`{"is": null}`, `{"any": true}`.

The loop's scenarios (`scenarios/loop/`) add, through `tests/checks/loop.py`, the actions `turn` (`tools/turn.py` on a
person, `run_step.run` standing in with the outcomes the data gives: `fake_run: {first, then, error}`), `turns` (`tools/turns.py` the same way: `turns` for --turns,
`resume` with `inbox` for --resume; its summary, its state as the run ended, what is saved, a refusal's text), `resume` (pages
into the inbox, then `--resume`; its report, and with a turn's printed report `reopens`, the question ids the report names for `tools/conclude.py reopen`), `clear_state`, `run` (one step through `tools/run_step.py` and its real connectors, only the network call
replaced: one answer per request as `fetch: {answers: [{url_has, fixture, content_type | error}]}`, each answer for the first request
carrying its `url_has` that no earlier request took: a saved real response, or the harness's stand-in for a holder that did not
answer; a request nothing answers fails the run; no `fetch` for no network at all; `dry` for a dry run, `again` for a run by the
step's id at every connector; the result's `records` are the sha256 of every record the runner archived and read), `run_all` (`--all` with a run that regenerates
the plan or raises, as the data says), `run_connector` (`run_step.run_connector` with the real `connector` named, answered like `run`: the
place names the step carries tried one at a time; the answers are taken in the order the requests come, one for each request the
runner sends, and a name that makes a request already made on the run sends none, so it takes no answer; the result adds the
`logged_note`, the note the run logged),
`decide_place` (the owner's choice on a place card found by its `raw` string: the candidate carrying the `gazetteer` id, or the geocoder's own answer `osm`, type/id), `resolve` (`tools/resolve_places.py --only` each string named, the geocoder's real answers under `geocoder`, Wikidata's items under `wikidata`
and the gazetteers' answers under `gazetteer` planted: each `gazetteer` fixture a list of the resolver's own cache records,
written where the resolver reads them), `place_string`, `apply_places`, `step_query`; and the expectations `queue` (`first`, `named`,
`not_named`, `passed`, `not_passed`, `reasons`), `runnable`, `turn_state`, `turns_run` (the runner's turns in
order, each `person`, `paused`, `nothing_new`, and its `passed` / `not_passed`), `locator_known`, `steps_by_collection`,
`fetched_rows` (`held` for a one-person row's value, `present` for a household row's key), `place` (`place_type`,
`wikidata_id`, `gov_id`, a `dated_name` and its `dated` span, the `chain` of names up to the country), `place_card`, `event_place`. The fakes are code because they exercise the connectors' and the runner's contract; what they are asked with
and answer with is in the scenario. `connectors.json` holds the same for the offline connector checks in `tools/check.py`: the
names and titles they are asked with and the saved real responses they are read against.

The import scenarios (`scenarios/imports/`) add, through `tests/checks/imports.py`, how a file is read as itself. The file
is always a fixture, the harness tree, written as another exporter would write it: the action `ingest` (`tools/ingest_gedcom.py`
into the scenario's tree, a refusal not an error: the result is its `code`, what it `said`, the `imports` and `artifacts` the
catalog holds afterwards) takes `file` and `written`: `char` (the header's CHAR value), `codec` (the encoding the bytes are written in, utf-8 by default) with `bom` (its
byte order mark first), `without_exporter` (the header's SOUR block dropped, a file that names no exporter) and `header_only`
(everything from the first person on dropped); a character the codec cannot write becomes `?`, as an exporter for that
character set writes it. `run_tool` runs one of the tools on the scenario's catalog (`tool`, `args`; `--db` goes first) and
returns its `code` and what it `said`. The expectations are `checklist_records` (the record kinds of a person's checklist
rows: `has`, `lacks`), `stored` (text the import stored: a `citation`, `collection` name, `note` body, `place` string or
person `name` holding the words given, `absent` for words no row holds, `clean` for no replacement character anywhere) and
`xref_systems` (the external id systems of the tree's persons). A scenario with no `tree.file` starts with an empty tree.
The geocoder's answer for the place the first-level-unit scenario resolves is the owner's own cache entry, fetched on
5 September 2026.

## What is simulated

Every response body, row, page and record the harness reads is real, but for the two stand-ins at the end: a page or response the live archive holds (a connector's
response with the archive's own manifest beside it, and the check that the bytes are the archive's own), the owner's own export
cut down (`harness.ged`), the geocoder's and the gazetteers' answers as the live resolver kept them, or one captured from its
holder for the harness and named so above (three: the Archive's search inside the Schwenkfelder record for Brandt on 2 October 2026,
Nominatim's answer for "Ballyquirk, Cork, Ireland" on 2 October, the 1950 census site's empty answer for Davidson in district 30-393 on
3 October UTC); a few were captured by a connector or the resolver on a scratch data root and say so in their rows. A holder's
request is asked of a real connector; only the network call is replaced.

What is simulated is a holder that does not answer, which is a control signal and no record:

- `run` and `run_connector` answers carrying an `error`: the connection raises `URLError` whose message begins "the harness's
  stand-in for no answer" (a timeout, a challenge, a refusal): the census page image in the loop scenarios
  `21-the-record-a-connector-archived`, `94-place-names-different-requests` and `100-a-hit-on-an-early-name-is-the-same-fields`, WikiTree in `22-a-steps-two-connectors`.
- `turn` and `turns` with `fake_run`: `run_step.run` replaced by a function that logs the outcome the data gives, only `none` (the
  holder answered nothing) or `error` (it did not answer), with no request, response or record, its note saying "harness: faked,
  no network"; in `10-turn`, `15-turns` (the error is the same stand-in), `60-unnamed-fetch` and `61-browse-only-holder`, to see
  what the turn does after such a run.
- `run_all`: `run_step.run` replaced by a function that regenerates the plan or raises `SystemExit`, no request; which steps are
  runnable is the real connectors' say (`25-runner-all`).
- The parent sha256 `check.py` hands the New Jersey and Kentucky connectors as the file's own (a placeholder string, only
  compared back).

Two stand-ins are not real, and no connector, parser or reading looks inside either; they carry no fact of anyone. The smallest of
JPEG files, written by `scenario.py`, stands for the Find a Grave gravestone photograph the fetch list names
(`decisions/50-memorial`: the archive holds no photograph of that memorial) and for the two family-held photographs the owner drops
into the inbox (`decisions/95-cited-on-the-owners-word`: the only family-held photographs the archive has are marked private and
never redistributed). A page of nothing but its saved-from line stands for the Newspapers.com obituary page the file cites
(`decisions/70-obituary-read-by-the-model`, `decisions/97-proof-summary`, `loop/70-held-is-the-subject`: the archive does not hold
the page, the holder forbidding a save); the obituary's readings are typed from the file's own claims onto it, as `transcribe`
types a reading, each persona's line the order the claims are typed in, since the page has nothing to point at. The 1959
marriage index's readings are typed from the real image above, each persona's line counted on it and its row's `bbox` in the
image's own pixels.
