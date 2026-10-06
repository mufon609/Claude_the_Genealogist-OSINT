# Fixtures

Saved real pages, one per parser, read by `tools/check.py` (through `tests/checks/parsers.py`) on a scratch catalog. They are the owner's own family documents
in the owner's repository; every page is public at its holder except where the rights column says otherwise. A fixture is
the bytes as the archive holds them (or as the browser saved them), never edited: the parser is checked against the page
as it is. The same holds for everything else the harness reads, the scenarios' answers included: every response body, row,
page and record is real, archived or captured from its holder, but for one stand-in file no code looks inside, which only
the owner can replace; what is simulated, and that stand-in, are named in "What is simulated" at the end.

| File | Holder and page | Parser | Rights |
|---|---|---|---|
| `findagrave-memorial-78019650.html` | Find a Grave memorial 78019650, Abram C Brant (1880–1961), saved by the page-saves-itself method | `rule:findagrave-memorial` | user-contributed page, Find a Grave terms |
| `findagrave-memorial-142698059.html` | Find a Grave memorial 142698059, Helen Sara Brant Ahearn (1909–1986), with her parents, her husband and five photographs, three of them typed Grave (two family photographs on the farm and, uncaptioned, the stone), as the archive holds it (the archive's object `868192df…`, the owner's save of 6 September 2026) | `rule:findagrave-memorial` | user-contributed page, Find a Grave terms |
| `findagrave-memorial-143847338.html` | Find a Grave memorial 143847338, John Davidson (1822–1877) of Franklin, Kentucky, a Union veteran, the page's veteran badge (a "V" and a hidden "Veteran") beside his name, as the archive holds it | `rule:findagrave-memorial` | user-contributed page, Find a Grave terms |
| `findagrave-memorial-130509402.html` | Find a Grave memorial 130509402, John Georgi Young Davidson (1876–1946), whom the file writes John Y, with the parents, wife, siblings and children it lists, as the archive holds it | `rule:findagrave-memorial` | user-contributed page, Find a Grave terms |
| `findagrave-search-davidson-robert-1915-2004.html` | Find a Grave memorial search, Robert Davidson 1915–2004, Ohio, saved by the owner | `rule:findagrave-search` | Find a Grave terms |
| `familysearch-census-1940-KQX1-VT9.html` | FamilySearch record ark:/61903/1:1:KQX1-VT9, United States Census 1940, the Ahearn household of Caln Township, Chester County, Pennsylvania | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1900-M9HX-SWP.html` | FamilySearch record ark:/61903/1:1:M9HX-SWP, United States Census 1900, the Davidson household of Adairville, Logan County, Kentucky | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1950-6X5P-KT7T.html` | FamilySearch record ark:/61903/1:1:6X5P-KT7T, United States Census 1950, the Hahnle household of Lindenhurst, Suffolk County, New York | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1950-6XYS-NQ16.html` | FamilySearch record ark:/61903/1:1:6XYS-NQ16, United States Census 1950, the Fred M Ahern household of Pennsylvania, saved from a search's results rather than a citation, as the archive holds it under its file name with no record id; the household record the loop's scenarios accept member by member; the son's and the father's Name fields keep another name each collapsed beneath the one shown | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1900-M3QL-XYW.html` | FamilySearch record ark:/61903/1:1:M3QL-XYW, United States Census 1900, the Milton Lukens household of Montgomery County, Pennsylvania, focused on his daughter Charlotte A Lukens, every member's own details table open; each Event Place shows Norriton Township and keeps Norristown collapsed beneath it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1925-KS4R-RTQ.html` | FamilySearch record ark:/61903/1:1:KS4R-RTQ, New York, State Census, 1925, Ruth Peters, page 19, line 25, saved with Document Information and the household closed, as the archive holds it (the archive's object `e9e889aa…`): its Event Place keeps beneath the place it shows two others, Hempstead, Hempstead, and the place restated with its districts, Hempstead, A.D. 01, E.D. 06, Nassau, New York, United States | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1925-KS4R-RTM.html` | FamilySearch record ark:/61903/1:1:KS4R-RTM, New York, State Census, 1925, Mary Peters, Wife, page 19, line 23 of the same districts as Ruth's page, saved with Document Information and the household closed, as the archive holds it (the archive's object `83876e39…`, its saved-from line and the key of the fetch list entry it was saved for above the page): its Event Place shows Hempstead, Hempstead and keeps Hempstead, Nassau and the place restated with its districts beneath it. Read with Ruth's page in decisions `99zzj`, one household under a head not held | `rule:familysearch-record` | public record; FamilySearch terms |
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
| `familysearch-search-nj-marriages-davidson-reiko-diane.html` | FamilySearch record search results, the New Jersey Marriages 1670-1980 collection for Reiko Diane Davidson, five rows of Davidsons and Davisons married from 1885 to 1900, as the archive holds it (the archive's object `24a52f8d…`, the owner's save of 18 September 2026 at 16:31) | `rule:familysearch-search` | FamilySearch terms |
| `familysearch-search-nj-marriages-davidson-reiko-diane-saved-again.html` | The same search saved again in the browser at 19:02 the same day, as the archive holds it (the archive's object `fbc2a73f…`): other bytes, six more than the first, and the same five rows; the scenarios' second save of one page | `rule:familysearch-search` | FamilySearch terms |
| `familysearch-massachusetts-marriage-search-no-results-annie-e-scannell.html` | FamilySearch record search results, the Massachusetts, State Vital Records collection for Annie E Scannell, saved in the browser as the search her cited marriage index citation (no ark of the holder's) was looked for by hand; the site answered "No Results", saved from the search's own URL as any results page is, 19 Sept 2026 | `rule:familysearch-search` | FamilySearch terms |
| `aad-enlistment-247275.html` | The AAD enlistment record 247275, Robert C Davidson, saved in the browser | `rule:aad-enlistment` | public record, National Archives |
| `familysearch-kentucky-death-index-1946-QKC9-LBLM.html` | FamilySearch record ark:/61903/1:1:QKC9-LBLM, Kentucky, Vital Record Indexes, the death of John Y Davidson in Simpson County on 11 Jun 1946 (the file and his memorial say the 10th), his birth calculated from his age, as the archive holds it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-kentucky-deaths-1946-N983-M2R.html` | FamilySearch record ark:/61903/1:1:N983-M2R, Kentucky, Deaths, 1911-1967, the death certificate of John Young Davidson at Franklin, Simpson County, its date the year alone (1946), his mother Ellen McCreary, his father Y J Davidson and his wife Lena Howard Davidson; archived under the file's death index citation (`1,3077::604036`) on the owner's word, as the archive holds it (the archive's object `630cfb36…`, 15 September 2026) | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-kentucky-vital-record-indexes-1915-QKH2-XT3L.html` | FamilySearch record ark:/61903/1:1:QKH2-XT3L, Kentucky, Vital Record Indexes, Robert E Davidson's birth, 19 Feb 1915 in Logan County, his mother Lena Bell; saved as a file, archived under its file name as the archive holds it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-massachusetts-marriage-index-1901-N445-429.html` | FamilySearch record ark:/61903/1:1:N445-429, Massachusetts, State Vital Records, the marriage of James J. Ahern and Annie E. Scannell at Amherst, 26 Jun 1901 (the file says Northampton, citing this record), the groom's page: his parents Thomas, given by one name, and Alice McGee, and the bride's parents Dennis, given by one name, and Mary Castello, filed in his Extended Family as Father-in-law and Mother-in-law, as the archive holds it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-obituary-collection-2004-QL71-6HG3.html` | FamilySearch record ark:/61903/1:1:QL71-6HG3, U.S., Obituary Collection, Robert Edgar Davidson's obituary in the Bucyrus Telegraph Forum, 2004: born 19 Feb 1915 at Woodburn, Kentucky, his parents, his brothers and sisters, his children and their families by name alone; archived under the file's own citation (Ancestry's 1,7545::2520318), as the archive holds it | `rule:familysearch-record` | FamilySearch terms |
| `familysearch-tennessee-marriage-index-1895-VNXD-RXW.html` | FamilySearch record ark:/61903/1:1:VNXD-RXW, Tennessee, State Marriage Index, John Davidson and Lena Bell, 25 Dec 1895, Robertson County: two names, the date and the county, nothing else, as the archive holds it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-social-security-claims-index-6K99-MWLL.html` | FamilySearch record ark:/61903/1:1:6K99-MWLL, United States, Social Security Applications and Claims Index, Robert Edgar Davidson, born 19 February 1915 at Auburn, Kentucky, his parents John Y Davidson and Lena Bell, as the archive holds it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-search-kentucky-birth-index-robert-edgar-davidson.html` | FamilySearch record search results, the Kentucky Birth Index 1911-1999 for Robert Edgar Davidson, a hundred rows of Davidsons born from 1911 to 1999, as the archive holds it | `rule:familysearch-search` | FamilySearch terms |
| `familysearch-search-census-1925-peters.html` + `.manifest.json` | FamilySearch record search results, the New York, State Census, 1925 collection (1937489) searched for the surname Peters at Hempstead, Nassau, in 1925 with no given name, the Peters household's own search: 120 matching records, page 1 of 6, twenty rows, Ruth Peters's (KS4R-RTQ) the eleventh and a row the index gives the surname alone, born about 1887 (KS4B-K6V), the fourth; as the archive holds it (the archive's object `f1fb1f2c…`, saved in the owner's browser on 5 October 2026 with the key of the live catalog's fetch list entry under its saved-from line), the manifest the archive's own. Read in decisions `99zzl`, the household's search answered by hand | `rule:familysearch-search` | FamilySearch terms |
| `familysearch-search-census-1925-peters-mary.html` + `.manifest.json` | FamilySearch record search results, the same collection for Mary Peters at Hempstead, Nassau, in 1925, the search Mary Peters's own citation made: nine rows, Mary Peters (KS4R-RTM, born about 1887) the second, a Mary K Peters of Oyster Bay the third; as the archive holds it (the archive's object `04801822…`, 20 September 2026), the manifest the archive's own. Read in decisions `99zzl`, an earlier search of the household's collection, surname and place | `rule:familysearch-search` | FamilySearch terms |
| `familysearch-united-states-world-war-i-draft-registra-1873-4X3T-LGW2.html` | FamilySearch record ark:/61903/1:1:4X3T-LGW2, United States, World War I Draft Registration Cards, 1917-1918, James Joseph Ahearn, born 25 May 1873, registered at Northampton, Massachusetts: the first page a model saved (the `tree-fetch` agent in the owner's browser, 5 October 2026 UTC), as the archive holds it (the archive's object `f3f439c2…`), its saved-from line and the key of the live plan's step under it as the save script wrote them | `rule:familysearch-record` | public record; FamilySearch terms |
| `va-gravesite-search-davidson-raymond-2007.html` | The VA Nationwide Gravesite Locator's results page for Davidson, Raymond, died 2007, as the connector's posted search received it: two decedents, the second Raymond E Davidson (1939–2007) | `rule:va-gravesite` | public record, Department of Veterans Affairs |
| `va-gravesite-search-davidson-raymond-page1.html` | The same locator's first page for Davidson, Raymond with no year: ten of 22 decedents and the links to the next pages, as the connector received it on a scratch run | `rule:va-gravesite` | public record, Department of Veterans Affairs |
| `va-gravesite-search-davidson-raymond-e.html` | The same locator's page for Davidson, Raymond E, as the archive holds it: five decedents, two of them written Raymond E Davidson, the first (1939–2007) the harness's Raymond Earl Davidson and the second (1930–2021) another man | `rule:va-gravesite` | public record, Department of Veterans Affairs |
| `va-gravesite-search-davidson-noi.html` | The same locator's page for Davidson, Noi, as the archive holds it: one decedent, Noi Davidson (1929–2015), a dependent's row, which names the veteran she is buried with ("Relationships: WIFE OF DAVIDSON, RAYMOND E") and carries the veteran's rank and branch (MSGT US AIR FORCE): the veteran a persona of the row, the rank and branch the veteran's | `rule:va-gravesite` | public record, Department of Veterans Affairs |

## Pages no parser reads

A real page or image the archive holds from a holder whose pages no parser claims, saved in the browser under the fetch
list's name: read by no `<stem>.expect.json` (the extractor fails it, which is what the scenario that uses it is about, or the
scenario reads it only by a reading it types from the page's own words), its `.manifest.json` the archive's own, byte for
byte, so `sha256sum` against `archive/objects/sha256/…` shows the page is the archived one.

| File | Holder and page | Rights |
|---|---|---|
| `mansfield-news-journal-obituary-193623-page-not-found.html` + `.manifest.json` | The archive's object `040d0989…` (18 September 2026, H05): the Mansfield News Journal's own answer when the link a cited obituary names (`mansfieldnewsjournal.com/news/stories/20040408/obituaries/193623.html`) was opened in the browser: its "Page Not Found (404)" page, which holds no obituary and no record of anyone, the paper's navigation and trending headlines of that day | the paper's page, its terms |
| `legacy-obituary-noi-davidson-17624767.html` + `.manifest.json` | The archive's object `0ee95c3d…` (13 September 2026, H05): the Trentonian's notice of Noi (nee Segawa) Davidson on Legacy.com, the page the file's U.S., Obituary Collection citation points at: age 86, of New Egypt, died Thursday, November 12 at Mt. Holly, born in Morioka, Japan, "predeceased by her husband, Raymond E. Davidson", her children, grandson, brothers and sister, published 15 to 17 November 2015. Read in the obituary scenarios by readings typed from its words | Legacy.com's terms |
| `findagrave-photo-142698059-117088371.jpg` + `.manifest.json` | The archive's object `7b2dd95d…` (12 September 2026, E05): photograph 117088371 of memorial 142698059, the Ahearn stone (AHEARN; FREDERICK M, MAY 22, 1907, FEB. 19, 2001; HELEN BRANT, JULY 11 1909, JAN 24, 1986), 3264 × 2448, saved under the fetch list's name. Read in the memorial scenario by a reading typed from its words | the contributor's photograph, Find a Grave terms |
| `familysearch-census-1900-image-S3HY-6WS7-8BK.jpg` + `.manifest.json` | The archive's object `c7cebd8b…` (6 September 2026, D03): image S3HY-6WS7-8BK, sheet 2A of enumeration district 240, Norristown borough, Ward Sixth, Montgomery County, Pennsylvania, the 1900 census, 3690 × 3725, from FamilySearch's viewer's own download control, archived under the file's citation of the Lukens household (`1,7602::47389682`): the head Milton Lukens on line 4, his dwelling and family numbers 22 and 22 written over a struck 35 and 35, his daughter Charlotte A on line 7. Read in decisions `99zzi` and `99zzk` by a reading typed from its words, `99zzk` grouping its two lines with the record page's household | FamilySearch terms |
| `familysearch-kentucky-death-records-1946-N983-M2R.jpg` + `.manifest.json` | The archive's object `940de305…` (15 September 2026, D03): the image of that certificate behind ark:/61903/1:1:N983-M2R, 1852 × 1756, state file 14205, John Young Davidson, died the 11th day of June 1946 at Franklin, Simpson County, aged 71, archived under the same citation. Read in decisions `99ze` by a reading typed from its words, one copy of the record with the page, the index entry and the state index's line | FamilySearch terms |

## From connector runs

| File | Where it came from | Parser |
|---|---|---|
| `wikitree-profile-Hubner-223.json` + `.manifest.json` | WikiTree's getProfile for Hubner-223 (David Hübner/Heebner, 1696–1784) with parents, spouses, children and siblings, fetched by the WikiTree connector on a scratch data root on 7 September 2026, not the live catalog; the manifest is its provenance | `rule:wikitree-profile` |
| `wikitree-profile-Davidson-349.json` + `.manifest.json` | The archive's object `d22f883f…` (20 September 2026, B04): WikiTree's getProfile for Davidson-349, John William Davidson, born December 1876 at Bishop Auckland, County Durham, England, with his parents and siblings, which the WikiTree connector fetched live on a name search for John Y Davidson (born 24 April 1876 in Kentucky); the manifest is the archive's own, byte for byte. Read in decisions `99zzd` for a month a record gives against a day of another month in the same year | `rule:wikitree-profile` |
| `ia-search-inside-genealogicalreco01krie-heebner.json` + `.manifest.json` | The Internet Archive's search inside the item genealogicalreco01krie (Genealogical record of the descendants of the Schwenkfelders, 1879) for Heebner, with the pages the connector chose in the manifest's notes, from the same scratch run | `rule:ia-search-inside` |
| `locgov-ocr-sn89058321-1918-05-10-p2.json` + `.manifest.json` | loc.gov's page text for image 2 of The Commercial (Union City, Tennessee), 10 May 1918, a hit of Ollie Duke Davidson's obituary step run live on the catalog on 7 September 2026; the harness adds the step's kind (obituary), which the runner now writes on every response and did not then | `rule:loc-gov-ocr` |
| `ky-death-index-1946-davidson.txt` + `.manifest.json` | Five lines of Reclaim The Records' Kentucky death index file for 1946 on the Internet Archive, DAVIDSON JIMMIE to DAVIDSON L, John Y Davidson's (Simpson County, 11 Jun 1946, certificate 14205) among them: the bytes exactly as one byte-range request returned them, each line's carriage-control byte kept; the manifest gives the range, the whole file's URL, size and sha256. The shape of the derivative the Kentucky connector keeps, and its offline check's year file | `rule:ky-death-index` |
| `ky-death-index-1946-page-153-top.txt` + `.manifest.json` | **Captured for the harness**: bytes 686455–687382 of the same 1946 file, cut at a line's start from one byte-range request of bytes 678713–687382 on 3 October 2026 08:08 UTC with the project's User-Agent (the file's ETag unchanged, so its sha256 stands): the line that ends page 152, page 153's heading (the department's line, DEATH INDEX FOR YEAR 1946 PAGE NO 153, the column titles) and the five Davidson lines above, carriage-control bytes kept. The year file with its headings, which the reader refuses as no one surname's derivative | none: `rule:ky-death-index` refuses it |
| `ky-birth-index-1915-davidson.txt` + `.manifest.json` | Four lines of the same release's Kentucky birth index file for 1915, DAVIDSON PRYCE to DAVIDSON RONALD, Robert Edgar Davidson's (Logan County, 19 Feb 1915, mother Lena H Bell) among them, fetched and kept the same way | `rule:ky-birth-index` |

A connector's response is read with the notes its manifest carries (the item, the pages chosen, what was searched for, the
step's kind), as the extractor reads it on arrival.

## Saved responses the connector checks and the runner's scenarios are answered with

Read by `tools/check.py`'s offline connector checks (`connectors.json` names them) and played back by the loop's `run`
action as a holder's answer, never parsed as a page of their own. Each is a real response with its manifest beside it:
where the archive holds the response, the manifest is the archive's own and the sha256 in it is the file's, so
`sha256sum` against `archive/objects/sha256/…` shows the bytes are the archived ones; a response captured for the
harness has its own manifest saying so. A saved response answers only the request it was asked at: the loop's `run` refuses
one whose manifest (or sidecar) names another URL.

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
| `ia-fts-directories-noi-davidson-towns-empty.json` + `.manifest.json` | The archive's object `6145a559…` (13 September 2026): the Archive's full-text search of its city directories for "Noi Davidson" in directories titled for New Egypt, Tacoma, Arneytown, Ogau Tonan or Mount Holly Township, the towns her events name, as the directories connector asks it, which holds nothing: the Archive's empty answer |
| `wikitree-search-davidson-noi-1929-empty.json` + `.manifest.json` | The archive's object `eb0a659a…` (13 September 2026): WikiTree's searchPerson for Noi Davidson born 1929, which holds nothing: WikiTree's empty answer |
| `ny-marriage-index-1959-page-970.jpg` + `.manifest.json` | The archive's object `c3dd7c98…` (7 September 2026): page 970 of Reclaim The Records' New York State marriage index for 1959 on the Internet Archive, as its reader serves the scan (3054 × 3530, 1.2 MB), the groom's row HAHNLE CHRIS M, license issued at HUNTING, 8/14, certificate 32801 among them: the image a scenario's reading is typed from. Never parsed: the scenario that puts it to the parsers by hand gets the failed extraction back, no parser claiming an image |
| `va-gravesite-search-davidson-raymond-e.html` + `.manifest.json` | The archive's object `e6db8c20…` (14 September 2026): the VA Nationwide Gravesite Locator's results page for Davidson, Raymond, middle name beginning E, as the connector's posted search received it: five decedents, Raymond E Davidson (1939–2007) the first |
| `va-gravesite-search-davidson-noi.html` + `.manifest.json` | The archive's object `17c08be7…` (14 September 2026): the same locator's page for Davidson, Noi: one decedent, Noi Davidson (1929–2015), a dependent's row naming the veteran she is buried with, read as a page above |
| `nara-1950-search-davidson-nassau-ed-30-392.json` + `.manifest.json` | The archive's object `9fda2c90…` (7 September 2026): the 1950 census site's own search for Davidson in Nassau County, New York, enumeration district 30-392: the one schedule (`nara-1950-schedule-3947385.json`, read as a page above) |
| `nara-1950-search-davidson-queens-ed-30-392.json` + `.manifest.json` | **Captured for the harness**, one request on 3 October 2026 07:44 UTC with the project's User-Agent, at `https://1950census.archives.gov/api/search?name=Davidson&state=NY&county=Queens&ed=30-392&page=1`: the same search in Queens County, the county the town sat in before Nassau County was cut from it in 1899, which the site answers with nothing (`{"total":0,"size":25,"page":1,"results":[]}`): the census site's empty answer |
| `nara-1950-search-raymond-davidson-nassau.json` + `.manifest.json` | **Captured for the harness**, one request on 3 October 2026 07:57 UTC with the project's User-Agent, at `https://1950census.archives.gov/api/search?name=Raymond%20Davidson&state=NY&county=Nassau&page=1`: the site's search for Raymond Davidson in Nassau County with no district, 1251 schedules of which the first page (25) is the answer and none has a highlighted name carrying both his given name and his surname |

## A launcher's output

What `claude -p --output-format json` printed for one launch, as it came, played back by the loop's `task` action in the
launcher's place (`tools/run_task.py capture` writes one).

| File | Where it came from |
|---|---|
| `task-launcher-answer-not-saved.json` | **Captured for the harness** on 4 October 2026: one launch on the smallest model (`haiku`, effort low) with the fetch task's own flags (the answer schema, no built-in tool, `--chrome`, a spending limit, input closed), asked by a probe's prompt and not a rendered task to answer `not_saved` with the line `probe`, no browser tool called: the launcher's result with its measures (2 turns, 1829 ms, $0.02528, the model's usage) and a valid answer. The scenarios read its measures and its `not_saved`; nothing in it is about a page |
| `task-launcher-answer-denied.json` | **Captured for the harness** on 4 October 2026: one launch on the smallest model (`haiku`, effort low) of a rendered fetch task (`tools/run_task.py capture`, the live list's first page) with a browser connected: the launcher's result as it came, the launcher having refused the model the browser action that opens a tab (`permission_denials`: a headless launch has nobody to approve a browser action), the model answering `not_saved`; no page was saved. The scenario reads its measures, its refusal and its `not_saved`; nothing in it is about a page |

## A session's report

What a session reported of the subagent it spawned on a handed task, as `tools/run_task.py done --out` wrote it when the run
was reported: the subagent's last message as it came (`answer`), the tokens, tool uses and time the session was given for it, the
model it was spawned on, the agent file's effort and the task as handed out. Played back by the loop's `task` action with `session`.

| File | Where it came from |
|---|---|
| `task-session-report-saved-elsewhere.json` | **Captured for the harness** on 4 October 2026 on the live catalog, the owner present: the first fetch task a model ran in the owner's browser, the agent `tree-fetch` spawned on `haiku` (effort low) with the rendered task of the live list's first page, James Joseph Ahearn's record in United States, World War I Draft Registration Cards (ark:/61903/1:1:4X3T-LGW2). The subagent answered `saved` with the script's line `ok fs-record 137015B`; the session was given 12799 tokens, 9 tool uses and 63068 ms. The browser's download location was the home's download folder and not the data root's `downloads/`, so no page came in and the run's row on the live catalog is `nothing`, marked as differing. Loop `129` plays it back on the same step with nothing in the folder: the run as it happened |
| `task-session-report-saved.json` | **Captured for the harness** on 5 October 2026 UTC on the live catalog, the owner present: the same page's task run again once the browser saved into the data root's `downloads/`, the save script by then one awaited call. The subagent answered `saved` with the script's line `ok fs-record 128020B`; the session was given 8895 tokens, 5 tool uses and 26788 ms. One file came in, the page below (`familysearch-united-states-world-war-i-draft-registra-1873-4X3T-LGW2.html`, 128020 bytes); collect took it by its own identity and the run's row on the live catalog is `card`, the report and the finding agreeing. Loop `125` plays the report back on the same step with that page coming in |

## Gazetteer answers

The place resolver's answers from GOV and Wikidata, fetched on a scratch copy of the live catalog on 2 October 2026 with the
project's User-Agent, planted by the `resolve` action of the loop's scenarios (and Wikidata's items by `turn`, `resume` and
`turns` too, under `wikidata`) so no request goes out. GOV's data is CC BY-SA (genealogy.net), Wikidata's CC0.

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
| `wikidata-Q1010236-norristown.json`, `wikidata-Q1345-philadelphia.json`, `wikidata-Q1185890-pottstown.json`, `wikidata-Q1895826-warwick-township.json`, `wikidata-Q49186-northampton.json` | Wikidata's items the resolver reads for the geocoder's candidates in the turn that reads a person's places (loop `12`): the live resolver's own cache files (`derivatives/geocode/wikidata/`, fetched 18 September 2026), copied byte for byte |
| `wikidata-Q936639-mount-holly.json`, `wikidata-Q1893417-caln-township.json` (and Northampton's above) | the same, for the strings a part must name in full (loop `93`) |
| `wikidata-Q678018-bandon.json` | Wikidata's item for the town of Bandon, County Cork, the one place the geocoder's six-candidate answer for "Bandon, Ireland" verifies (loop `118`): the live resolver's own cache file (`derivatives/geocode/wikidata/`, fetched 3 October 2026), copied byte for byte |
| `wikidata-Q36405-aberdeen.json` | **Captured for the harness**, one request on 3 October 2026 23:09 UTC with the project's User-Agent, at `https://www.wikidata.org/wiki/Special:EntityData/Q36405.json`, through the resolver's own `wikidata_entity` (the cache file it wrote, byte for byte): Wikidata's item for Aberdeen, the city the geocoder's answer for "Aberdeen, Scotland" names (loop `104`) |
| `wikidata-Q1133193-coatesville.json`, `wikidata-Q1205932-takizawa.json`, `wikidata-Q1348478-shizukuishi.json`, `wikidata-Q2391361-tamayama.json`, `wikidata-Q11367618-nakano.json`, `wikidata-Q11410107-kuriyagawa.json`, `wikidata-Q11444312-ota.json`, `wikidata-Q11520132-motomiya.json`, `wikidata-Q11557079-asagishi.json`, `wikidata-Q11603862-yanagawa.json`, `wikidata-Q11604013-yonai.json` (and Philadelphia's above) | the same, for the resolver's own line (loop `90`) |

## Geocoder answers

`geocoder/nominatim-<place>.json`: the geocoder's (Nominatim's) answers to the queries the resolver asks, each a cache record
exactly as the live resolver kept it under `derivatives/geocode/nominatim/` (`{query, fetched_at, results}`, results as
Nominatim served them, every one asked for the first page's six candidates; a record asked at another limit carries it as
`limit`), copied byte for byte; the scenarios' `place_card` and `resolve` actions plant them in the scratch
resolver's cache under the file name it looks them up by at that limit (`geocoder: [...]`), so no request goes out. Data © OpenStreetMap
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
| `bandon-ireland` (3 October) | six, as many as the resolver asks for first: the town of Bandon, County Cork, and five stretches of the River Bandon (a page that may be cut, loop `118`); the live cache's |

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
`""` for none), `sex`, `region` (texts the persona's `region_json` contains), `page_place` (the entry's place on its page as
the region keeps it: `form`, the record form's id or `null`; `locators`, each locator given with that value as written;
`no_locators`, true when the region keeps none), `facts` (fact patterns each of which some fact
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
| `awaits`, `capture` | a fixture the scenario reads that only the owner's browser can produce, and the command that captures it: while the file is absent the scenario is not run, `tools/check.py` prints a `wait` line naming both and counts it neither ok nor failed |
| `steps` | the list of steps; each is one action key with its arguments, `as` (a label to bind the result under), `say` (what the step is about), `at` (a timestamp the clock every tool reads stands at while the action runs, for a check that depends on writes sharing a second), and `expect` (a list of expectations) |

No scenario sends a request. `tools/check.py` starts every check under a guard (`tests/checks/offline.py`, put on every Python
process a check starts through the interpreter's startup hook in `tests/checks/offline_site/`) that refuses a connection to any host
but this machine's own and writes the refusal down: the scenario whose process asked fails with the host named, whether the code
under check swallowed the failure or not. What answers a holder is data planted before the run: the geocoder's and the
gazetteers' answers in the resolver's cache, Wikidata's items, a `fetch` answer for the runner's own network call. `tools/check.py
--scenario NAME` walks only the scenarios whose file name has NAME in it (`104`, `a-constituent-country`).

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
collection's tier, its printed line), `backfill` (`tools/backfill_aliases.py` on the scenario's tree as the harness session,
its printed lines), `proof` (`tools/proof.py`'s summary of a `person`, one `fact` when named: its
whole, each fact also under `fact.<name>`, and its `text`), `dismiss` (a person's one open question of `kind`, a conflict when none is
named, whose detail carries `detail_has`, closed by the owner through `tools/log_search.py --dismiss` with a `note`; a refusal comes back
as `error`), `post` (a POST handed to the person screen's own handler with no socket, or a GET when `method` says so: `path`, its parts joined, a part a string or
`{"question": ref}` / `{"step": ref}` for that row's id; `body`; `headers` that differ from the ones the page sends, null for one left out;
the result is the response's `code` and JSON `body`, and the `ids` the path's row parts named), `attach`
(`fixture` into the inbox and `tools/attach_inbox.py`, or `stand_in: "image"` under `as_file`, `about` for the
owner's word; its `filed` the path the original is filed under, its `line` the result as the tool prints it), `archive` (a `fixture`; `source`, `collection`, `locator`, or a
`manifest`; `extract`, `match` (people, `null` for the record's own), `rule` to run the standing rule too), `seed` (the same,
for a page no parser reads, which the harness reads only by a typed reading), `reread`, `match`, `decide` (`card`, `status`, `note`, `by`, `choice`; its result `conclude.decide`'s, `rematched` the cards of the people it changed matched again; `screen` through the person screen's own route, its answer in words as `summary`), `withdraw` (a `card`, or with `record` every decision the rule made on it, recorded as the rule acting for the harness unless `by` names who),
`reconsider` (`dry`; its `rows`, and `wrote`, the audit rows the run wrote), `fact` (`tools/conclude.py fact` on `field` or `fields`), `assertion` (one statement decided through
`tools/conclude.py assertion`: by `record` and `event_type`, or a `membership`, its first statement, the `record`'s own when one is given), `place` (a persona fact
placed onto an event through `tools/conclude.py place`: `record`, `person`, `fact_type` find the fact, `alternate` true for
the one the page keeps beneath the value it shows (false for one it shows); `event` is a
literal id or `{person, type, index}`, that person's nth event of the type in the person screen's own order),
`link_on_word`, `living`,
`transcribe` (a reading typed into the person screen's form: `record`, `form` with the persona's `line` or `bbox` and
`image_is`, `relations` to bound personas, `about`, `by` the reader, `llm:<model id>` or `user:<name>`: the harness types every reading,
so its reader names the harness, `llm:harness` in a model's place and `user:harness` (or `human:harness`, the default) in a person's), `view`,
`copies` (the owner's word on two archived copies through `tools/conclude.py`'s `copies_on_word`: `a` and `b` bound records, a
listing's row as `{record, number}`, `same` false for two records, `note`; the `rows` it carried or gave back),
`save` (a `fixture` written under the fetch list's own name for `holder` and `person` (the entry whose link has `url_has`, when the person has several there), into a `folder`;
`name` overrides that with the file's own name, to save a page under a browser's sanitized shape rather than the list's; `key` writes the
key under the page's own saved-from line as `tools/save_page.js` does when the list's call gave it one: `true` for the entry's own steps, or a
list of plan steps, a string that is no step's id written as given: a key naming a step the plan lacks), `collect` (its `lines` are each result as the tool prints it, its `sha` the record when one page came in), `attach_inbox` (`tools/attach_inbox.py` over every file in the inbox, one file per transaction: its `results` and `lines`), `block_filing` (the filing of a `file`'s original under the tree refused, so its attach fails after writing its rows; `clear` lifts it, and the scenario's end does), `log`, `reopen`, `step` (a plan step written by hand, with `revisions` the include and revise an earlier screen stored on it), `event` (a second event of a type a person already
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
of a `record`, put to `person`, planted undecided as that matcher's `version`: a results page's row, or another row of a record put
to a person the current matcher would not put it to; the matcher writes none of them now, so only an older one can stand for
reconsider or a decision to meet), `older_reading` (a record's reading as an older reader left it in the owner's
catalog and no reader writes now: the `extractor` and each persona with its facts copied from the catalog's own rows, a date
read from its `date_text`, a `place` as its words, and its `relations` to the reading's other personas by their `sequence`
under `to`; it stands as the record's current reading), `persona_link` (a person's link to a record's persona of a `role`, and
`persona` name and `sequence` row, set to `status`, the state a card an older matcher put up for a memorial's listed relative leaves once
decided; with `card`, the link that card's decision wrote on another row of the same name before a decision reached only its own
entry of the page, the shape the 0.7.5 migration corrects), `merge` (a `duplicate` merged into the person it duplicates, `kept`, with a `note`; `older` for the merge as an older tool left it, every proposal it re-pointed naming the duplicate again, every membership it folded back on the duplicate's row with the statements it moved, every persona link it folded back there as it was (the kept person's own row as it was too), every name alias it moved or folded the duplicate's again and every question it closed open again, the shape the merge run again on the pair completes), `cite`, `question` (a research_question row patched by
hand into a shape nothing today writes, found by `kind` and `detail_has` among the person's own and set from `set`, for
a regeneration to be checked against a prior state, such as a legacy truncated key), `households` (the households grouped
again and stored where they changed, `tools/households.py` regroup, as the plan groups them: `kept`, `written`, `superseded`,
`ungrouped`, every row the table holds as `rows`, and the current `households`).

Expectations: `last` (the action's result against a pattern), `bound`, `cards` (the cards on a record: `people`,
`kind`, `count`, `personas`), `card` (`status`, `kind`, `decided_by`, `decided_at`, `note`, `rationale`), `rule` (`taken`, `why`),
`compare` (a `card`'s persona against its person as the matcher compares them: `agree`, `disagree`, `absent`, the
`vetoes` the rule reads among the disagreements, and the card's `fields`, each field's verdict), `facts` (key facts by status), `alias`, `linked`, `parents` (a person's parents as the tree holds them, by display name in name order), `memberships`, `persons` (`count`, or `named` with `given` and
`surname`), `event` (`strings` by status, `shown`, `canonical_date`, `basis`, `events`), `family_event` (the events of a `type` on the family `a` and `b` are partners in: `events`, each one's date as written in date order, `dates`, how many statements each carries, `per_event`, in the same order, and with `record` its `statements` on them by status and `per_event` that record's alone), `disagreements`, `question` (a person's questions by `kind`, `status` and `closed_reason`, `detail_has` in the detail: whether any is there, or their `count`),
`assertions_on`, `links` (a person's link statuses on a record's personas, by `persona` name, `role` and `sequence` row), `is_subject`, `citations_held`,
`checklist_row`, `baseline`, `waiting`, `step`, `step_count`, `fetch_entries`, `fetch_call` (the call the list gives the save script for the page serving a `step`: its `call` text and the steps it `serves`), `search_log`, `named_for`, `audit`, `hints`,
`living`, `mode` (`planned` for the plan's own), `foundation`, `results_page`, `place_string`, `artifact` (its row,
`tier` as `catalog.tier_sql` reads it and `collection_tier` its collection's own), `artifact_where`, `classes` (a
record's statements on a person's events of an `event_type`, or on a family `link`, read by
`catalog.evidence_classes`: some statement's `source`, `information`, `evidence`, `relationship`, `original`),
`statement` (which reading a record's statements on a person's events of an `event_type` are read through,
`catalog.statement_of`: `current` or `earlier` each), `states` (a record's statements on a `person`, on their events of an
`event_type`, on the person themselves with `kind` person, or on their own family links with `kind` family_member, in the
order written: each one's `status`, who set it, `by`, and `person_decided`, whether that was a person's own decision on it), `conflict_rule` (the rule's test on a conflict, `conclude.classes_decide`, on a person's event of a `type` and its `axis`,
date or place: `taken` and the reason, `why`), `extractor` (a reading's extractor row, `kind`, `name`, `model_id`, `version`,
`prompt_is_instruction` for the sha256 of `app/person/read_record.md`, and what the extraction kept: `image_is`, `year`,
`regions` of its personas), `person_persona`, `reach`, `trusted` (a `membership`, or a person's `event` of a type, on
trusted ground for the rule; `stating` a date or a place), `plan_idempotent`, `no_repeats`, `one_event` (no record fact
stated on two events of its type that a person or a family holds), `whole`, `file` (`name` in the inbox or a `folder`, or a bound
`path`, there or with `exists` false not; with `fixture`, holding that fixture's bytes),
`count`, `proposal_status`, `proposals_of`, `person_merged`, `find_person`, `listed`, `assertion_subject`, `origins` (`overview.origins`: the `people` by what brought them in, `file` or
`record`, and the accepted `documents` by what fetched them, `citation`, `lead`, `search` or `hand`), `overview` (a `person`'s card on the
tree overview, confirmed or at the edge, matching `is`: its `parents`, `claimed_parents`, `spouses`, `claimed_spouses`), `households` (the current
stored households, those of a `form` when it is named, matching `is`: each one's `form`, `page`, `complete`, `missing`, `ground`,
`grouped_by` and `members` in line order, a member's `name` as written, `relationship` as stated, `head`, `line`, `entry` and the
`record`, the label of the first step bound to its file), `household_leads` (what each household not wholly held that the tree
ties to a `person` leads to, `tools/households.py` candidates, one entry per household matching `is`: its `answer`, the pages of its
own search `held`, `count`, `total`, `next` and `next_url`; the candidates in `order` and the ones `open`, each `name`, `ark`, `born`,
`for` (the missing entries it could be) and `why`; those `left_out`, each `name`, `ark` and `why`; and those `tried`, each `name`,
`ark` and `where` its page placed it). An entry of `expect` is one
expectation, its name the key and its pattern the value, and a `why`, printed with its failure; any other key beside the name (a
`status` meant for the pattern) is a failure, as an action no step knows is, so a claim written in the wrong place cannot pass.

Patterns: a dict matches the keys given, a list its length and each element, a string or number equals; `{">=": n}`,
`{"<=": n}`, `{"has": x}` (a substring, or every substring of a list, or an element), `{"lacks": x}`, `{"starts": s}`,
`{"ends": s}`, `{"first": p}`, `{"len": n}`, `{"some": p}`, `{"none": p}`, `{"every": p}`, `{"not": p}`, `{"in": [..]}`,
`{"is": null}`, `{"any": true}`.

The loop's scenarios (`scenarios/loop/`) add, through `tests/checks/loop.py`, the actions `turn_by_hand` (`tools/turn.py "<name>"` as the owner runs it, `turn.main`, on a `person` the same stand-ins answering as a turn's (`fake_run`, `fails`); what it printed, `exit` the status it ended with, `None` when it ran to its end), `turn` (`tools/turn.py` on a
person, `run_step.run` standing in with the outcomes the data gives: `fake_run: {first, then, error}`, `raise` an outcome for a run
that raises the data's `error`, or with `fetch` the real runner
and connectors answered as `run` is; the geocoder's real answers
under `geocoder` and Wikidata's items under `wikidata` planted for the turn's resolver, as `resolve` plants them; `fails` for the
harness's stand-ins for the runner's or the turn's own work failing: `reading` every record's reading raising, `requests` the connector
named unable to build its requests, `reconsider` the tail's reconsider raising; what it printed, `left` the report from its
`left:` on, and `state`, the entries of the people who wait as the file beside the database holds them), `task` (`tools/run_task.py`'s run of one fetch task, on the fetch list's entry serving a `step`, at a `model` and `effort`: the launcher's process alone replaced, by `silent` (`timeout`, or `exit` with its status) or by `captured`, a fixture holding a launcher's own output; `saves` a real page that comes into the data root's `downloads/` while the launcher runs, or a list of them, a `fixture` under the entry's name (or `name`), with the entry's key when `key`; the result is the run as the tool returns it, `printed` as it prints it and `command`, what the launcher was started with; with `session` the task goes through the session's launcher and no process is started: handed out, the page under `saves` coming in while it is out, then reported done with `{"captured": fixture}`, a session's own report as `tools/run_task.py done --out` wrote it, or `"silent"`, a subagent that ended with no message; the result adds the `handout` the session was handed, the `state` written beside the database, and `out_twice` and `done_twice`, the refusals of a second task while one is out and of a second report), `turns` (`tools/turns.py` the same way: `turns` for --turns,
`inbox` the pages dropped into the inbox first, `arrives` a page saved as `save` saves one once the run's opening resume is over,
as the owner's browser saves a page while the runner goes on; what it printed, its summary, the run's count as it ended, `turn_state`
the entries of the people who wait, a refusal's text), `next_person` (`tools/turns.py`'s choice of the next person on a run's count
the data gives, `turns` each with its `person` and the held count `held_before` and `held_after`: the person `named` and those
`passed` over, by name, with the `reasons`), `resume` (pages
into the inbox and the answers planted as a turn's, then `--resume`; its report, `finished` the people who waited whose turns it finished, and with a turn's printed report `reopens`, the question ids the report names for `tools/conclude.py reopen`), `clear_state`, `old_turn_state` (the
state beside the database written in the one-turn shape, a turn on `person` paused at `at`, its keys as the owner's own state file holds
them), `run` (one step through `tools/run_step.py` and its real connectors, only the network call
replaced: one answer per request as `fetch: {answers: [{url_has, fixture, content_type | error | challenge}]}`, each answer for the first request
carrying its `url_has` that no earlier request took (with `every`, for every such request): a saved real response, refused for any request but the one its manifest or
sidecar says it was asked at, or the harness's stand-in for a holder that did not
answer (`error`) or served a challenge page in place of its answer (`challenge`); a request nothing answers fails the step, whatever the runner made of the refusal; no `fetch` for no network at all; `dry` for a dry run, `again` for a run by the
step's id at every connector, `fails` as a turn's; each connector's result names `failed`, the failure of a run that failed; the result's `records` are the sha256 of every record the runner archived and read, `archived` of every response), `run_all` (`--all` with a run that regenerates
the plan or raises, as the data says), `run_connector` (`run_step.run_connector` with the real `connector` named, answered like `run`: the
place names the step carries tried one at a time; the answers are taken in the order the requests come, one for each request the
runner sends, and a name that makes a request already made on the run sends none, so it takes no answer; the result adds the
`logged_note`, the note the run logged),
`decide_place` (the owner's choice on a place card found by its `raw` string: the candidate carrying the `gazetteer` id, or the geocoder's own answer `osm`, type/id), `resolve` (`tools/resolve_places.py --only` each string named, the geocoder's real answers under `geocoder`, Wikidata's items under `wikidata`
and the gazetteers' answers under `gazetteer` planted: each `gazetteer` fixture a list of the resolver's own cache records,
written where the resolver reads them; with `geocoder_silent`, run in the harness's process under the stand-in for a geocoder
that does not answer, named in "What is simulated"), `place_string`, `apply_places`, `step_query`, `save_names` (`fetches.distinct_names` on the `entries` given, each a `url` and the
`save_as` built for it: the `names` the fetch list then prints), `browser_script` (a script the owner's browser runs, `file`
under `tools/`: `awaited`, whether its code is one awaited call of an async function, and the placeholder `call` it ends in);
and the expectations `queue` (`first`, `named`,
`not_named`, `passed`, `not_passed`, `reasons`: by person, or a list of `[person, pattern]` pairs for a person the rule created; the
people who wait read as the tool reads them), `runnable`, `turn_state` (the entries of the people who wait: with `person` that person's,
matching `is`, or none with `is` null; without, `is` null for nobody waiting), `task_run` (the `task_run` rows in the order written, matching `is`: each with its `launcher`, `steps`, `task`, `usage` and `answer` read from their JSON, `text_is_current` saying its hash is the task text's own, and `log`, the `search_log` row it names as its step's key and outcome), `kept_places` (the words of the place strings the geocoder left unanswered, kept beside the database for the tree, matching
`is`), `turns_run` (the runner's turns in
order, each `person`, `nothing_new` (no more records held after the turn than before), `failed`, `waits` (whether the person waits on pages now), its `passed` / `not_passed`, and
`finished`, the people who waited whose turns the run finished), `locator_known`, `steps_by_collection`,
`fetched_rows` (`held` for a one-person row's value, `present` for a household row's key), `place` (`place_type`,
`wikidata_id`, `gov_id`, a `dated_name` and its `dated` span, the `chain` of names up to the country), `place_card`, `event_place`. The fakes are code because they exercise the connectors' and the runner's contract; what they are asked with
and answer with is in the scenario. `connectors.json` holds the same for the offline connector checks in `tools/check.py`: the
names and titles they are asked with and the saved real responses they are read against; its `district` place is a residence as the
owner's catalog holds it, read off FamilySearch's 1950 census row for Dorothy J Peters, a place in the District of Columbia.

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

## The guards

`rules.json` holds plain-value cases for the pure rules `tools/check.py` runs on their own. Its `web_url` cases are the web
addresses a file's citation may carry and the link each becomes (`href`: the escaped address, or nothing for an address that is
not http or https: `javascript:`, `data:`, any case of a scheme, whitespace inside one): `catalog.web_url` is checked on them, and
`tests/checks/housekeeping.py` runs the person screen's own `web` helper (`app/person/index.html`) on the same cases under node, so
the Python reader of a file's address and the screen cannot differ. `housekeeping.py` holds the checks of the small guards around
the catalog that no scenario reaches, each run on what it guards under a temporary directory: the commit hook runs in a throwaway
git repository on names it must refuse (a letter beyond ASCII, a quote, a newline) and names it must pass; a catalog from before
the `same_record` and `task_run` tables (the scratch catalog with both dropped and their versions forgotten: nothing in the harness is an
older catalog, and the owner's backups never enter git) is migrated by `tools/initdb.py --migrate` to the code's version, and one whose
person vitals view is another definition gets the schema's own; a bag `tools/backup.py` writes under the scratch data root while a turn
commits a record (after the objects are copied, and in the middle of the dump) holds an object for every artifact its dump has a row
for, and no row of the dump names an artifact the dump has no row for; `tools/tree.py use` writes `catalog/.active-tree` whole (a run of the
tool whose write stops leaves the file as it was). Its `tree_home` action (`housekeeping.py`) runs `tools/tree.py home` on a scenario's tree: the
`person` named as `form` says (`bracketed`, the default, `id` or `name`), the result its `code`, what it `said` and the `home` person's entry id.

## What is simulated

Every response body, row, page and record the harness reads is real, but for the one stand-in at the end: a page or response
the live archive holds (with the archive's own manifest beside it, or a sidecar saying how the archive holds it), the owner's own
export cut down (`harness.ged`), the geocoder's and the gazetteers' answers and Wikidata's items as the live resolver kept them,
or one captured from its holder for the harness and named so above (five: the Archive's search inside the Schwenkfelder record
for Brandt on 2 October 2026, Nominatim's answer for "Ballyquirk, Cork, Ireland" on 2 October, and on 3 October UTC the 1950
census site's answers for Davidson in Queens within district 30-392 and for Raymond Davidson in Nassau, and the top of page 153
of the 1946 Kentucky death index); a few were captured by a connector or the resolver on a scratch data root and say so in
their rows. A holder's request is asked of a real connector; only the network call is replaced, and a saved response answers
only the request its manifest or sidecar says it was asked at. One response is cut down as `harness.ged` is: the New Jersey
death index's whole file, which its connector asks for in loop `20`, `21`, `24` and `102`, is answered by its excerpt (the
header, every line under Ahearn and Evers, and Noi Davidson's line, each as the file holds it).

A holder that does not answer is simulated, a control signal and no record:

- `run` and `run_connector` answers carrying an `error`: the connection raises `URLError` whose message begins "the harness's
  stand-in for no answer" (a timeout, a challenge, a refusal): the census page image in loop `21`, `94` (its second run), `96`
  and `100`; the census site's search in Nassau County in `94`'s first run, so that its second and third names are tried and the
  first and third, whose request it was, are logged unanswered;
  WikiTree in `22`; the 1950 schedule's transcription and its image, then the image alone, and an Archive book's metadata in
  `114`, whose searches are the holders' real answers.
- `turn` answers carrying `challenge`: the connection answers with status 200 and `loop.py`'s `CHALLENGE`, a few bytes of HTML
  titled "Just a moment..." saying it is the harness's stand-in for a holder's challenge page, served in place of the answer a JSON
  connector reads: every request of loop `106`'s turns.
- The geocoder in a turn (`turn`, `turns`, `resume`) or a `resolve` whose step says `geocoder_silent`: `loop.py` answers it from the resolver's cache
  alone, and a query the cache lacks at the limit it is asked at fails as an endpoint that does not answer, so no request is made: loop `12` and `117` (their first step,
  the geocoder silent on purpose), `118` (the wider request a full page calls for, which no answer in the harness serves), `10`, `13`, `15`, `61`, `106`, `108`, `109`, `110` and `111`, whose turns read
  place strings no answer is planted for. A step that does not say it has the geocoder's answers it plants and no others, and a query
  they lack is a request, which fails the scenario.

- `task` with `silent`: the launcher's process (`run_task.spawn`) raises the timeout it would raise (`timeout`, loop `120`,
  `124`) or exits with a status and prints nothing (`exit`, loop `121`): a launcher that does not answer, no result invented.
  With `captured` the process prints a launcher's real output; the page under `saves` is a real saved page, written into
  `downloads/` as the browser would leave it (loop `123`, `124`). With `session: "silent"` the session reports its subagent
  done with no message and no measures (loop `128`): the same silence at the other launcher. With `session: {"captured": …}`
  nothing is simulated: the report is a session's own (loop `125`, `129`), and the step it is played back on is written by
  hand as the owner's catalog holds it.

The runner's runs are simulated where a scenario is about what happens after one, not about a holder's answer:

- `turn` and `turns` with `fake_run` (`{"first": "none"}` when the step gives none): `run_step.run` replaced by a function that
  logs the outcome the data gives, `none` or `error`, with no request, response or record, its note saying "harness: faked, no
  network": loop `10` (an error, the same stand-in, then none), `12`, `13`, `15`, `60`, `61`, `63`, `108`, `109` and `110` (none). A `none` here
  stands for an answer of nothing that no holder gave. With `raise`, the function raises the data's error instead, the
  harness's stand-in for a turn that fails outside its runs' own reading and requests (loop `111`).
- `fails`: a code path replaced by one that raises, saying it is the harness's stand-in: the extractor the runner calls
  (`reading`), a connector's `requests` (`requests`), the tail's `reconsider` (`reconsider`), for a run or a turn whose own work
  fails (loop `110`). No page, response or record is touched; the response the failed reading was given is a real one.
- `turns` with `arrives`: a real page saved into the download folder after the run's opening resume, the moment a browser save
  happens while the runner goes on being the only thing simulated (loop `115`); `next_person`: a run's count of turns and held
  counts given as data, the runner's own state in the run and no record of anyone (loop `115`).
- `old_turn_state`: the state beside the database written in the one-turn shape, its keys as the owner's own file holds them and
  its people the harness's own (loop `109`); no page or record of anyone.
- `log`: a run written by hand, as a connector or a saved page would leave it, its outcome and its artifacts (real pages the
  scenario archived) as the step gives them: decisions `60`, `90`, `99zd` (a search step's run finding the christening record); loop `10`, `31`, `32`, `46`, `50`, `63`, `70`, `72`, `101`.
- `run_all`: `run_step.run` replaced by a function that regenerates the plan or raises `SystemExit`, no request; which steps are
  runnable is the real connectors' say (loop `25`).
- The parent sha256 `check.py` hands the New Jersey and Kentucky connectors as the file's own (a placeholder string, only
  compared back).

The owner's own hand, and the model's, are played by the harness on real pages:

- Readings (`transcribe`): every reading is typed by the harness from the page's or the image's own words, and its reader names
  the harness, `llm:harness` in the model's place (decisions `50`, the Ahearn stone; `70` and `97`, Noi Davidson's obituary;
  `71`, the 1959 marriage index; `99ze` and `99zn`, John Y Davidson's death certificate; loop `70`, the obituary) and `user:harness` in a
  person's (decisions `71`, `99f`, the marriage index). On the marriage index each persona's line is counted on the image and
  its row's `bbox` is in the image's own pixels; on the stone the `bbox` is the inscription's panel; on the certificate the
  `bbox` is the full name's line; on the obituary each persona's line is the order the notice names them.
- `merge` of two children of one family (decisions `99zt`, `99zu`, `99zzn`, `99zzo`): the owner's file enters no child twice
  under the same parents, so the harness merges the 1940 household's daughter into its son, or the 1920 household's Anna R into
  her sister Alicia M, both the file's own children of that family, to walk the merge of two members of one family; in `99zzn`
  and `99zzo` the harness's own decision (`persona_link`) puts the 1920 census's Alicia M to Anna as well, as one child entered
  twice would carry the same entry, so the merge meets a persona both link; no person, page or record is invented.
- `save`: a real page or image written into the inbox or a download folder as the owner's browser leaves it, under the fetch
  list's name or the one given; with `key`, the save script's key comment written under the page's own saved-from line, as
  `tools/save_page.js` writes it (loop `41`, `42`, `43`, `108`). `tools/check.py`'s test of that script writes the script's own head over
  the Lena Howard Bell search page's document.
- `block_filing`: the move that files a saved page's original under the tree refused, so the attach fails after its rows are
  written, the stand-in for a file whose transaction fails (loop `107`); no page or record is touched.
- Catalog state a path needs and no record or run would leave in a short scenario is written by hand: plan
  steps (`step`, `step_query`, and with `revisions` a revision the screen stored before it refused a year that is no year, loop `116`), events (`event`), a research question's shape (`question`), cards and links an older matcher
  left (`legacy_card`, `older_matcher`, `persona_link`), a reading an older reader left (`older_reading`, its rows copied from
  the owner's catalog), a merge an older tool left unfinished (`merge` with `older`), a place card on the geocoder's real answers (`place_card`) and place
  strings of the owner's records (`place_string`). None of them is a page or a response, and none is a record of anyone but
  as the owner's catalog already holds it.

One stand-in is not real, and no connector, parser or reading looks inside it; it carries no fact of anyone. The smallest of
JPEG files, written by `scenario.py`, stands for the two family-held photographs the owner drops into the inbox
(`decisions/95-cited-on-the-owners-word`): the only family-held photographs the archive has are marked private and never
redistributed, and whether one may sit in `tests/` is the owner's choice (CLAUDE.md, hard rule 7).
