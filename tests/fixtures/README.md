# Fixtures

Saved real pages, one per parser, read by `tools/check.py` on a scratch catalog. They are the owner's own family documents
in the owner's repository; every page is public at its holder except where the rights column says otherwise. A fixture is
the bytes as the archive holds them (or as the browser saved them), never edited: the parser is checked against the page
as it is.

| File | Holder and page | Parser | Rights |
|---|---|---|---|
| `findagrave-memorial-78019650.html` | Find a Grave memorial 78019650, Abram C Brant (1880–1961), saved by the page-saves-itself method | `rule:findagrave-memorial` | user-contributed page, Find a Grave terms |
| `findagrave-search-davidson-robert-1915-2004.html` | Find a Grave memorial search, Robert Davidson 1915–2004, Ohio, saved by the owner | `rule:findagrave-search` | Find a Grave terms |
| `familysearch-census-1940-KQX1-VT9.html` | FamilySearch record ark:/61903/1:1:KQX1-VT9, United States Census 1940, the Ahearn household of Caln Township, Chester County, Pennsylvania | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1900-M9HX-SWP.html` | FamilySearch record ark:/61903/1:1:M9HX-SWP, United States Census 1900, the Davidson household of Adairville, Logan County, Kentucky | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1950-6X5P-KT7T.html` | FamilySearch record ark:/61903/1:1:6X5P-KT7T, United States Census 1950, the Hahnle household of Lindenhurst, Suffolk County, New York | `rule:familysearch-record` | public record; FamilySearch terms |
| `nara-1950-schedule-3947385.json` | The 1950 census site's answer for schedule 3947385, enumeration district 30-392, Nassau County, New York, as the connector archived it | `rule:nara-1950-schedule` | public record, National Archives |
| `aad-search-davidson-robert-15.html` | The National Archives' AAD enlistment search, DAVIDSON ROBERT born '15, saved in the browser | `rule:aad-search` | public record, National Archives |
| `familysearch-massachusetts-birth-records-1907-FXJ3-Z7X.html` | FamilySearch record ark:/61903/1:1:FXJ3-Z7X, Massachusetts State Vital Records, the birth of Frederick Michael Ahearn at Northampton, 22 May 1907, indexed as "Ahearu" with parents "James J. Ahearu" and "Annie E. Scauusl"; the page's heading says Death, its fields say Birth | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-search-census-1950-ahearn-frederick-micheal.html` | FamilySearch record search results, the 1950 census collection for Frederick Micheal Ahearn born 1930–1934 in Pennsylvania, 142 results, page 1 of 8, saved from the step's prefilled link | `rule:familysearch-search` | FamilySearch terms |
| `aad-enlistment-247275.html` | The AAD enlistment record 247275, Robert C Davidson, saved in the browser | `rule:aad-enlistment` | public record, National Archives |
| `va-gravesite-search-davidson-raymond-2007.html` | The VA Nationwide Gravesite Locator's results page for Davidson, Raymond, died 2007, as the connector's posted search received it: two decedents, the second Raymond E Davidson (1939–2007) | `rule:va-gravesite` | public record, Department of Veterans Affairs |
| `va-gravesite-search-davidson-raymond-page1.html` | The same locator's first page for Davidson, Raymond with no year: ten of 22 decedents and the links to the next pages, as the connector received it on a scratch run | `rule:va-gravesite` | public record, Department of Veterans Affairs |

## From connector runs

| File | Where it came from | Parser |
|---|---|---|
| `wikitree-profile-Hubner-223.json` + `.manifest.json` | WikiTree's getProfile for Hubner-223 (David Hübner/Heebner, 1696–1784) with parents, spouses, children and siblings, fetched by the WikiTree connector on a scratch data root on 7 September 2026, not the live catalog; the manifest is its provenance | `rule:wikitree-profile` |
| `ia-search-inside-genealogicalreco01krie-heebner.json` + `.manifest.json` | The Internet Archive's search inside the item genealogicalreco01krie (Genealogical record of the descendants of the Schwenkfelders, 1879) for Heebner, with the pages the connector chose in the manifest's notes, from the same scratch run | `rule:ia-search-inside` |
| `ia-advancedsearch-title-schwenkfelder-families.json` | The Archive's advanced search for texts titled "The Genealogical Record of the Schwenkfelder Families", as the books connector asks it: three copies of the 1923 book. Read by the connector's offline check, not by an extractor: a search response is the query's evidence, not a record | none |
| `locgov-ocr-sn89058321-1918-05-10-p2.json` + `.manifest.json` | loc.gov's page text for image 2 of The Commercial (Union City, Tennessee), 10 May 1918, a hit of Ollie Duke Davidson's obituary step run live on the catalog on 7 September 2026; the harness adds the step's kind (obituary), which the runner now writes on every response and did not then | `rule:loc-gov-ocr` |

A connector's response is read with the notes its manifest carries (the item, the pages chosen, what was searched for, the
step's kind), as the extractor reads it on arrival.

Not here: an Ancestry index page. The owner's account reaches Ancestry's record pages only through a membership offer
("Join Ancestry"), so no page could be saved and the parser stays unverified; the two pages archived under Ancestry record
ids are FamilySearch record pages.

## The harness tree

`harness.ged` is a small GEDCOM in Ancestry's shape, written by hand for `tools/check.py`: the Ahearn household of the
1940 census of Caln Township (Frederick Michael Ahearn, Helen Sara Brant, Frederick Micheal Ahearn Jr, Alicia Ahern),
Helen's parents Abram C Brant and Charlotte D Lukens, and Frederick's father James Joseph Ahearn, each with the citations
the owner's file carries for the two pages above (the 1940 record ids, Abram's memorial; James also cites the SAR
applications, whose free holder has no parser), and Raymond Earl Davidson
(1939–2007) on his own, with no citation, for the gravesite locator's page. Ingested into a scratch catalog,
it is what the matcher, the standing rule and the decision writers are run against: the four cards the 1940 page makes,
the rule refusing each (no accepted fact, a disagreement), the son accepted with his facts and no link, the mother's
accept asserting the mother-son link, the father's the couple and his side of the link (mother, son and the couple then linked on the record for the matcher), the sister placed beside her
brother undecided and then with her parents on the owner's word (a vouch, no link for the matcher), the memorial taken by the rule as Abram's identity on a page anyone can edit (the name, both dates to
the day, the burial place and the relatives it lists agreeing with the tree's claims), its facts written undecided and none
accepted, his wife and daughter refused with the reason and the new people the memorial links coming up once he is
accepted, a rejection writing nothing else, a new person created with her marked maiden name as her birth surname and
Abram placed as her child from the page with the membership created but its assertion undecided like the page's other
facts, reconsider keeping the identity and refusing the listed relatives, a decision
taken back taken again as a card, the owner's own accept of it an identity too, the page re-read carrying two decided
links and no fact accepted, the photograph the page types Grave as a fetch step saved under the list's name and archived
under the gravestone row unparsed, a reading of it by the model one card for Abram the rule leaves to the owner, the
gravesite page's one card for Raymond among its namesakes (the near ones hints) and the rule taking it once his dates are
his own word, the SAR page listed once for James and once for his son's footprint step, each name ending in its person's six characters,
saved under James's name and reaching his step alone, unparsed, the son's still waiting, James's step then reopened so the
record names nobody it was fetched for while the found row stays, a
found run at a row-source connector leaving a fetch step planned, a planted step nothing generates dropped and named in the
run's audit row, and the plan regenerating unchanged. It is the only `.ged` the commit guard allows.
