# Fixtures

Saved real pages, one per parser, read by `tools/check.py` (through `tests/checks/parsers.py`) on a scratch catalog. They are the owner's own family documents
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
| `familysearch-census-1940-KQT1-2MF.html` | FamilySearch record ark:/61903/1:1:KQT1-2MF, United States Census 1940, the Robert Davidson household of Hempstead, Nassau County, New York; the head's own Birth Date field is a bare year (1914), the census index's own estimate from his age, not a birth as written | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-census-1920-MXBF-NHK.html` | FamilySearch record ark:/61903/1:1:MXBF-NHK, United States Census 1920, the James J Ahearn household of Northampton, Hampshire County, Massachusetts; the mother's and two sons' rows carry a blank relationship cell, testing that sex, age and birthplace still land in their own columns rather than shifting into it | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-ohio-death-index-VKBL-4FN.html` | FamilySearch record ark:/61903/1:1:VKBL-4FN, Ohio, Death Index, Robert Edgar Davidson; the page's own Event Date field carries his time of death ("09:50 PM"), not a date | `rule:familysearch-record` | public record; FamilySearch terms |
| `nara-1950-schedule-3947385.json` | The 1950 census site's answer for schedule 3947385, enumeration district 30-392, Nassau County, New York, as the connector archived it | `rule:nara-1950-schedule` | public record, National Archives |
| `aad-search-davidson-robert-15.html` | The National Archives' AAD enlistment search, DAVIDSON ROBERT born '15, saved in the browser | `rule:aad-search` | public record, National Archives |
| `familysearch-massachusetts-birth-records-1907-FXJ3-Z7X.html` | FamilySearch record ark:/61903/1:1:FXJ3-Z7X, Massachusetts State Vital Records, the birth of Frederick Michael Ahearn at Northampton, 22 May 1907, indexed as "Ahearu" with parents "James J. Ahearu" and "Annie E. Scauusl"; the page's heading says Death, its fields say Birth | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-washington-petitions-for-naturalization-1967-6ZR5-N8ML.html` | FamilySearch record ark:/61903/1:1:6ZR5-N8ML, Washington, Naturalization Records, 1850-1994, Noi Davidson's petition, Tacoma, 11 Dec 1967 | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-social-security-numident-1956-6KML-FS23.html` | FamilySearch record ark:/61903/1:1:6KML-FS23, United States, Social Security Numerical Identification Files (NUMIDENT), 1936-2007, Raymond Earl Davidson, whose own Parents and Siblings table names Robert Davidson and Ruth Peters with no role word | `rule:familysearch-record` | public record; FamilySearch terms |
| `familysearch-search-census-1950-ahearn-frederick-micheal.html` | FamilySearch record search results, the 1950 census collection for Frederick Micheal Ahearn born 1930–1934 in Pennsylvania, 142 results, page 1 of 8, saved from the step's prefilled link | `rule:familysearch-search` | FamilySearch terms |
| `familysearch-search-kentucky-deaths-bell-lena-howard.html` | FamilySearch record search results, the Kentucky Deaths 1911-1967 collection for Lena Howard Bell, 529 results, page 1 of 27, saved in the browser as the search a cited Kentucky death record (no ark of the holder's in the citation) was looked for by hand; the first row names her as a mother on another's record with no dates of her own | `rule:familysearch-search` | FamilySearch terms |
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
`value` as written when it matters). A fact pattern: `type`, and any of `value`, `value_starts`, `date`, `place` (matched
as a prefix of the place string as written). A `why` on any pattern is printed with the failure and says what the page
taught. `tools/check.py --show` prints what each reading wrote, for writing a sidecar.

## The harness tree

`harness.ged` is cut from the owner's own export by `tests/checks/cut_gedcom.py`, never written by hand: the header and the
submitter record verbatim, the INDI and FAM records of the people the scenarios need, verbatim, and every SOUR record they
cite. The one edit the cut makes is dropping a line whose value points at a record outside the cut (a family, a person, a
media object), with the lines under it; so a person whose families all fall outside the cut stands in the file with no
link, as the file itself would hold a stranger. It holds the home person, their parents and grandparents on both sides,
two great-grandparents' households as two census pages name them (the 1940 and 1920 pages above), the great-grandmother's
parents (the memorial's subject and his wife), a great-great-grandfather's parents and his two entries in the file (the
file's own duplicate, for the merge), and the 1900 household of a great-great-grandmother's parents. It is the only `.ged`
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
| `steps` | the list of steps; each is one action key with its arguments, `as` (a label to bind the result under), `say` (what the step is about), and `expect` (a list of expectations) |

A value `"$label"` reads what a step bound; `"$label.key.0.key"` reads into it. A person is an entry id, `{"name": …}` or
`{"created": …}` (a person the rule made, by display name), or `"$label"`. A record is the label of the step that
archived it. A card is `{"record": label, "person": ref}` or `{"record": label, "persona": name as written[, "role": …]}`,
with `extraction` and `latest` to pick a reading; a step of the plan is `{"person": ref, "step_key": …}`, `step_key_like`,
`row_key`, `kind`, `status`, or `locator: {kind, value}`.

Actions: `plan` (`"all"` or people), `attach` (`fixture` into the inbox and `tools/attach_inbox.py`, `about` for the
owner's word), `archive` (a `fixture`, or a stand-in: `stand_in: "image"`, or a page with only a `saved_from` line,
`suffix` to make other bytes of the same page; `source`, `collection`, `locator`, or a `manifest`; `extract`, `match`
(people, `null` for the record's own), `rule` to run the standing rule too), `seed` (the same, for a page the harness only
reads by a typed reading), `reread`, `match`, `decide` (`card`, `status`, `note`, `by`, `choice`), `withdraw`,
`reconsider` (`dry`), `fact` (`tools/conclude.py fact` on `field` or `fields`), `assertion` (one statement decided through
`tools/conclude.py assertion`: by `record` and `event_type`, or a `membership` of the file), `link_on_word`, `living`,
`transcribe` (a reading typed into the person screen's form: `record`, `form`, `relations` to bound personas, `about`,
`by`), `view`, `save` (a stand-in written under the fetch list's own name for `holder` and `person`, into a `folder`),
`collect`, `log`, `reopen`, `step` (a plan step written by hand), `place_card` (a place answer's card with the geocoder's
`candidates` planted in the cache), `older_matcher`, `merge`, `cite`.

Expectations: `last` (the action's result against a pattern), `bound`, `cards` (the cards on a record: `people`,
`kind`, `count`, `personas`), `card` (`status`, `kind`, `decided_by`, `note`, `rationale`), `rule` (`taken`, `why`),
`facts` (key facts by status), `alias`, `linked`, `memberships`, `persons` (`count`, or `named` with `given` and
`surname`), `event` (`strings` by status, `shown`, `canonical_date`, `basis`, `events`), `disagreements`, `question`,
`assertions_on`, `links` (a person's link statuses on a record's personas), `is_subject`, `citations_held`,
`checklist_row`, `baseline`, `step`, `step_count`, `fetch_entries`, `search_log`, `named_for`, `audit`, `hints`,
`living`, `mode` (`planned` for the plan's own), `foundation`, `results_page`, `place_string`, `artifact`,
`artifact_where`, `extractor`, `person_persona`, `reach`, `trusted`, `plan_idempotent`, `no_repeats`, `whole`, `file`,
`count`, `proposal_status`, `proposals_of`, `person_merged`, `find_person`, `listed`, `assertion_subject`. A `why` beside
an expectation is printed with its failure.

Patterns: a dict matches the keys given, a list its length and each element, a string or number equals; `{">=": n}`,
`{"<=": n}`, `{"has": x}` (a substring, or every substring of a list, or an element), `{"lacks": x}`, `{"starts": s}`,
`{"ends": s}`, `{"first": p}`, `{"len": n}`, `{"some": p}`, `{"none": p}`, `{"every": p}`, `{"not": p}`, `{"in": [..]}`,
`{"is": null}`, `{"any": true}`.

The loop's scenarios (`scenarios/loop/`) add, through `tests/checks/loop.py`, the actions `turn` (`tools/turn.py` on a
person, `run_step.run` standing in with the outcomes the data gives: `fake_run: {first, then, error}`), `resume` (pages
into the inbox, then `--resume`), `clear_state`, `run` (one step through `tools/run_step.py`, its download a body the
data gives, `fetch: {header, rows}` or `{body}`, or no network at all), `run_all` (`--all` with a run that regenerates
the plan or raises, as the data says), `run_connector` (a connector standing in, answering none for a request carrying
`none_when`), `resolve` (`tools/resolve_places.py --only` each string named, the geocoder's `cache` and Wikidata's
answers planted), `place_string`, `apply_places`, `step_query`; and the expectations `queue` (`first`, `named`,
`not_named`, `passed`, `not_passed`, `reasons`), `runnable`, `turn_state`, `locator_known`, `steps_by_kind`,
`fetched_rows`, `place`, `place_card`, `event_place`. The fakes are code because they exercise the connectors' contract;
what they are asked with and answer with is in the scenario. `connectors.json` holds the same for the offline connector
checks in `tools/check.py`: the names, titles and bodies they are run against.

Two stand-ins carry no fact of anyone: the smallest of JPEG files stands for a gravestone photograph the harness never
parses, and a page of nothing but its saved-from line stands for an obituary the file cites at a holder with no parser,
read only by a reading typed from the file's own claims.
