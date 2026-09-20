# Research workflow

The app does not start from records and it does not start from hints. It starts
from what the family already knows and has approved, turns the gaps into
questions about people, and works each question down a ladder of searches that
does not need a name until a name has been found.

```
 ┌──────────┐   ┌───────────┐   ┌──────┐   ┌────────┐   ┌─────────┐   ┌───────┐   ┌────────┐
 │ BASELINE │ → │ QUESTIONS │ → │ PLAN │ → │ SEARCH │ → │ EXTRACT │ → │ MATCH │ → │ REVIEW │ ─┐
 └──────────┘   └───────────┘   └──────┘   └────────┘   └─────────┘   └───────┘   └────────┘  │
      ▲            (auto)        (generated)     (auto/assisted,  (layer 3)   (proposals    (person-      │
      │                                           logged)                     answer a Q)    centred)     │
      └────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 0. Terms

**Claim.** What the imported file or a searcher says without a record behind it.
An Undecided fact in a query carries basis `claim`; an Accepted one carries
`accepted`; a citation's own detail carries `citation`, a checklist row's value
`row`, what a held record itself says (the name as written, the record it
links) `record`, and the search as it was run on a saved results page `run`.
Nothing is searched on claims alone.

**Lead.** A piece of follow-up work about one person that the evidence produced
and the loop can act on: a record to fetch because a held record names it
(the parent's memorial linked from Raymond Earl Davidson's), a search to run
because an accepted fact makes it possible (the 1950 household at the address
the 1940 census gives), a person named on an accepted record who is not yet in
the tree. A lead has a person, what to do, where to do it, and what produced it
(the record, fact or citation). Leads are the queue of work; every lead is a
plan step with its log, so what was tried and what it gave is never lost. A
lead closes when it is run, found or none, or when its gap has gone. Accepting
a document produces leads; running them consumes leads. The file's citations
are leads whose origin is the file.

**Hint.** A document, or a row on a search page, that overlaps the person on
some of what identifies them but not on enough for the matcher to propose it or
the rule to accept it: the surname, the place and the period agree, but there
is no age, no full name, no stated relationship. A census before 1850 that
names the head and counts the rest; a tax list; a directory line; a search row
with a bare year; a newspaper hit before its text is read. Hints are kept on
the person with what agrees and what is missing, for research when the leads
run dry. A document already accepted as the person's can also stay a hint
while it still has work in it (the pre-1850 household accepted as the family's,
the children not yet identified). A hint never becomes a fact on its own;
research turns it into a lead or a match. Hints are shown only on a person
whose baseline is reviewed, never as a feed.

**Which documents the rule may accept on its own.** The standing rule (§5–7)
accepts a document as the person's when it agrees with what the person already
accepted, and everything the document states comes with it; a disagreement
with a value that rests on no accepted assertion is not a veto — the record
is still taken on its points, and the difference becomes a conflict question,
never a silent overwrite. It may do so only for document kinds that identify
a person fully, from sources nobody can edit at will (registry tiers T1–T3:
certificates, census, obituaries, published works), and only counting
accepted facts that themselves rest on such a source or on the owner's own
word. A page anyone can edit (T4:
Find a Grave, member trees) identifies a person but never builds their facts:
accepting it, by the owner or by the rule, writes the persona link, and the
family memberships the page states are created where the tree lacks them
with an undecided assertion each, the way a sibling placement already is;
every fact the page types is written as an undecided assertion too, what the
page says, never accepted and never a ground the rule stands on; the rule
takes such an identity when the name agrees and at
least three of birth date to the day, death date to the day, burial place, and
a stated parent or spouse who is that relative in the tree agree with the
tree, claimed or accepted. A person whose accepted facts rest on T4 alone is
marked so on their card until a trusted record about them is accepted. A
memorial's gravestone photographs are primary sources (T1): each is a fetch
step, saved in the owner's browser one at a time and read by the transcription
path into a card like any other image. Every other kind is a hint until a
person reads it. The starting list, to be refined as records are met:

| Document | What it gives | Standing |
|---|---|---|
| Federal or state census 1850 on | full names and ages; relationships from 1880 | automated |
| Federal census 1790–1840 | the head's name, the rest counted | hint |
| Find a Grave memorial | full name, dates, cemetery, linked family, gravestone photographs | the identity by the rule when the name and three of birth day, death day, burial place, a stated parent or spouse agree; the family memberships it states created where the tree lacks them, undecided like its facts; each gravestone photograph a fetch step |
| Death, birth, marriage certificate or index | full name, dates, parents or spouse | automated |
| Social Security index, draft cards, veterans' files | full name, exact birth date | automated |
| Naturalization petition, declaration or index | full name, birth date and place, residence, spouse | automated |
| Church register entry | names and dates when the register keeps them | automated when dated and the parents are named; hint otherwise |
| Obituary, newspaper hit | free text | hint until the text is read (by hand or by the model); then the named survivors decide: automated for the person it names once a stated relative it names is a relative the tree already links on trusted evidence, never on dates or places alone |
| Will, probate, land, tax, directory | names, no ages | hint |
| Compiled genealogy, family Bible | lineage, no proof | hint, never proof |
| A row on a search results page | name, years, place | hint; its own record is the document |

## 1. Baseline: what we know and have approved

An imported tree is a set of **claims**, not knowledge. The Ahearn import, as
imported on 5 September 2026, had 232 facts with no citation at all and 1,122
citations that point at records we did not hold. None of that is a baseline;
the live checklist says where the review stands now.

- A person accepts documents, not facts: the decision on a held record is
  whether it is about this person, and every fact the record states comes with
  it (§5–7). Key facts: name, sex, birth, death, parents, spouses, children;
  each is **Accepted**, **Rejected** or **Undecided** according to the documents
  behind it. A person is *baseline-complete* when no key fact is Undecided. A
  person may accept a fact on their own knowledge (a vouch): the fact then
  traces to the tree file as the archived claim, the acceptance is the
  person's, it is Accepted like any other, and the record fetch still runs. The
  standing rule (§0, §5–7) accepts on the person's behalf a document that
  agrees with what they already accepted.
- Only Accepted facts feed searches. An Undecided fact is a claim and is
  labelled as such in every query: every query field is `{value, basis}` with
  basis `accepted` or `claim`. A Rejected fact is left out, and a relative
  whose family link is Rejected is not a relative to the footprint or the
  checklist.
- Review is person-centred: one person, their claims, the records behind each,
  verdict per fact. This is the first screen.

## 2. Questions: generated from gaps in the baseline

Questions are always about a person. They are generated, not typed:

| Kind | Trigger | Example from this tree |
|---|---|---|
| `missing_parents` | no parents in tree | Thomas Ahearn (1846–1902): 0 citations, no parents |
| `identity_incomplete` | no surname, or given name only | "Dorothy", "Minerva E", "Carol Evers" |
| `missing_spouse` | a person of marriageable age with no partner | John Brant, Elizabeth Bean |
| `missing_fact` | no birth/death/marriage date or place | John Cassel: death 1802, no birth |
| `unverified_claim` | fact with no record behind it | every uncited fact |
| `conflict` | competing values | 5 marriage dates for David Heebner & Maria Kriebel |
| `duplicate_person` | two persons with the same name and the same key fact | the two Thomas Ahearns, both born 2 Oct 1846 |
| `unlinked_relative` | a person in the tree who may be the answer | a same-surname person in the same town with no link |

42 of the 117 people in the file as imported are dead ends. Ranking: home person's direct line
first, then tractability (era and place with good record coverage in the
registry), then how many other questions an answer would unlock. Until its subject is
baseline-complete (no key fact Undecided) a question gets no search steps and
no footprint, duplicate or unlinked persons; only fetch steps for records the
tree already cites exist, because the review needs those records.

## 3. Plan: the search ladder

The first rung is not a record type and not a name. It is **the family's own
record footprint**: the records already attached to the missing person's
relatives. A father, wife and children who all appear in the same census page,
family history, will, or church register were recorded together; the missing
member is very likely on the same page, or in the same collection one entry
away. The catalog already knows this footprint, so it is computed, not guessed.

| Layer | What is searched | Needs a name for the unknown? | What it yields |
|---|---|---|---|
| 0 Family footprint | records already cited or archived for **any relative** (spouse, children, parents, siblings), ranked by how many family members share the same record | no | the 1880 census page cited on Thomas Ahearn's wife and son almost certainly lists Thomas and his birthplace; the two Kentucky death certificates cited on Minerva E's children name their mother's maiden name |
| 1 Same collections | the collections in the footprint, searched for the family's surname, place and era | no | the family is in the 1900 census: search the 1880 and 1910 censuses of the same township for the same household |
| 2 Relationship records | records *about the known relatives* that state relationships, chosen by record type × era × place | no | death cert (parents), marriage (parents, maiden name), SS-5, baptism, obituary (survivors), probate (heirs), naturalization |
| 3 Household | the subject as child/spouse/boarder in census years not yet in the footprint | no | candidate parents from co-residence |
| 4 Named candidate | once a candidate name exists, search for that person directly | yes | the candidate's own birth, marriage, death, parents |
| 5 Locality-surname | all persons of the surname in the county in the era | no | the FAN cluster; Schwenkfelder Genealogical Record for Brant/Heebner/Cassel |

Measured on the imported tree before any new record has been fetched:

| Missing-link person | Own records | Records on relatives, not yet on the person | Of which one page holds 2+ family members | First thing to fetch (`tools/footprint.py`) |
|---|---|---|---|---|
| Thomas Ahearn (1846–1902), no parents | 0 | 3 | 1 | 1880 census on Alice McGee and Patrick Ahearn |
| Minerva E, no surname | 2 | 8 | 0 | Kentucky Death Records, 1852-1965 on Ellen E McCrary |
| Dorothy, no surname | 1 | 1 | 0 | U.S., Find a Grave® Index, 1600s-Current on Elizabeth Williams |
| Elizabeth Bean, no parents | 1 | 9 | 0 | Philadelphia, Pennsylvania Death Certificates Index, 1803-1915 on Abraham B Brant |
| Mary Bridget Walsh, no parents | 2 | 4 | 0 | Pennsylvania Death Certificates, 1906-1973 on Anna Marie Bolton |

And the records that already hold the most family members: a compiled family
history holding 14 Cassels, a Pennsylvania will holding 7 Cassels, a family
history book holding 6 Lukens/Berkheimer/Rubican relatives, a 1930 census page
holding all 4 Peters. Those are where a missing Cassel, Lukens or Peters is found.

`tools/footprint.py "<person>"` computes Layer 0 from the catalog, read-only:
the duplicate check first (same name and birth year, or same name and the same
spouse or parents), unlinked same-surname persons as hints with a generation
label, then every record cited or held on a spouse, child, parent or sibling
that is not already on the person, ranked by how many family members share it
and by what it would settle, with the collections to search next. Ancestry
cites each person on a census page under a different record id, so census
citations are grouped by year as one page. `tools/checklist.py` shows the top
of this list under FOOTPRINT, ahead of the Group A rows.

A plan is a list of executable steps for a person. Each step belongs to a
checklist row and is one of two kinds. A **fetch** is a record the tree already
cites, on the person or on a relative: it carries the citation's locator (an
Ancestry APID, the record's identity), the collection, the relatives it sits
on, the registry row the record is fetched from (the free holder of the
collection, `data/holders.csv`), and the citation's own details as its fields
(collection, the name the citation sits on, the page text's parts such as
year, census place, enumeration district, sheet, the memorial URL), each with
basis `citation`; every citation on a row is one fetch step, in one shape. A
citation whose collection has no free holder, or whose holder is an
archive.org collection of scanned index pages with no page-locating step
built yet (`data/holders.csv`'s `scanned_index` kind), is a fetch step with
mode `blocked` and the reason in its rationale; a reviewed person whose row is cited
only through blocked fetches also gets the row's search step at the free
sources, as for a missing row. A **search**
is a typed query (`subject_record`, `household`, `couple`, `name`,
`surname_locality`, `obituary`, `probate`) for a missing row, built from the
foundation fields with each field's basis, with its registry sources, one mode
(`auto`, `assisted`, `awaiting_approval`), and what a hit would look like.
A fetch step's fields carry basis `citation`.
Footprint records on relatives are fetch steps under the fact-level question
they serve. A held record that names a person and links their own record makes
a fetch step for that record on that person, once the persona is accepted as
them: a memorial lists each family member with their own memorial, so the
accepted parent's memorial is a lead under the parent's cemetery row, with the
linked record's own identity (`memorial_id`) as the locator and the page's
words as its fields (basis `record`); nothing is generated for a persona only
proposed. Running a step (Go, Search, the log buttons) is the approval;
there is no approval state. Fetches are cheap and decisive, and open before the
baseline is reviewed because the review needs them.

Record type → era → place → source (layer 2) is a lookup, not a guess. The
registry's coverage column drives it (MA deaths 1841–1915 are free and indexed;
Irish civil registration starts 1864, so an 1810 birth means parish registers).

A search step's place field carries every accurate description of the place
it stands for, not the tree's canonical name alone: the names valid at the
record's own date and the as-written strings first, every other name only
once those return nothing, because a collection is found under the place's
modern name and the record inside it under the name its own day used. A
revision tries the most likely combinations first and widens to every
combination only once those are not getting hits.

## 4. Search: execute and log every step, including failures

| Mode | Sources | Behaviour |
|---|---|---|
| auto | Chronicling America (loc.gov), the 1950 census site, the Internet Archive's full-text and title search, WikiTree, the VA gravesite locator, the New Jersey death index; FamilySearch after Innovator approval, NARA catalog, Open Archives, Wikidata, the held archive when their connectors exist | the system runs the query, archives raw responses, extracts personas |
| assisted | Find a Grave, the WWII Army enlistment file at the National Archives (AAD), FamilySearch record search (free account), Newspapers.com, Fold3, Archion | the system builds the exact search URL and tells the user what to look for; the user saves the result to `inbox/`, or a session drives the owner's own logged-in browser to save one cited record at a time by the page-saves-itself method below; the system takes it from there |

**Adjusting a prefilled search.** A person at the keyboard may change the
fields of a prefilled search before running it (a wider year, a middle name,
a place spelt as the site wants it); the run's log carries the fields as run,
so the change is a logged act. A link that is wrong for the citation itself
(a suffix taken as a surname) is a defect: report it, do not work around it.

**The enlistment file.** The WWII Army enlistment step for a man born 1895
to 1927 carries the National Archives' own fielded search prefilled (the name
as the file writes it, the year of birth as two digits); the site answers a
browser only, so the results page is saved there, comes in through `inbox/`
and becomes the candidate card on the step, every row (name, birth year,
residence county and state, enlistment year) audited against the person; the
full record of a row that fits is saved the same way and read as a record:
the birth year and nativity, the residence at enlistment, the enlistment as a
military service event, education and marital status as written.

**The page saves itself.** A cited page at an assisted source is saved from
the owner's own browser in one call and never read through the model: open
the citation's URL in a new tab, wait for the page to load, run one script
in the page that clones the document, removes `iframe`, `script`, `style`,
`link` and `noscript` elements, and hands the result to the browser as a
download named after the record's own id (`tools/save_page.js`, run in the
page with the file name filled in); the script returns the byte count
and whether the parser's marker and the family markup are present, and all
three must hold before the tab is closed. Move the file from the download
folder to `inbox/` and log the step as found with it. Measured on a Find a
Grave memorial: one call, about half a minute from navigation to file, the
saved page a quarter of the rendered size, nothing transcribed. If the
browser is set to ask where to save each download, turn that off first or
answer the dialog by hand; a dialog left open blocks every later browser
call. Chrome lets a page start one download without a hand on it: a second
page saved in the same tab lands nowhere, so each page gets its own tab,
closed after the file arrives. `tools/fetches.py list` prints every page a
planned fetch step points at, at every holder without a connector, once, leads
from held records first, with the link to open, the people waiting on it and
the file name to save under; a browser session works down that list one tab per
page; `tools/fetches.py collect` then moves every saved page from the download
folder (or `--folder`) into `inbox/` and attaches each by its own identity,
read from the saved-from line the browser wrote (`tools/save_page.js`) when
that line is a FamilySearch record or search URL, a Find a Grave memorial or
search, or an AAD record or search — whatever the file is named, since Chrome
may have sanitized or de-duplicated the name the list printed. A FamilySearch
link that is the collection's own search (no ark yet known) is listed to save
under `familysearch-<collection words>-search-<given>-<surname>.html`, the
given name and surname the search's own, so the several people's steps one
search serves share one name; a link that is a record page is listed under
`familysearch-<collection words>-<year>-<ark id>.html`, the ark id read off
the page once saved. For a page from a holder whose pages carry no identity
the attach reads (an SAR patriot page, a Legacy.com obituary), by the name
the list printed, whole: such a page is listed once per citation and person
waiting on it, under a name that carries the citation's own record locator
(the step's key when it has none) and ends in that person's six characters,
so one person's several pages of one collection are told apart as two
people's are, and no name waits on a year the citation may not carry; the
saved file goes to that person's steps on that citation alone, archived under
that holder with the page's own URL as locator, logged found, unparsed until
a parser claims it. A file with neither a recognised saved-from line nor a
listed name is left in the folder. Never encode a page and read it out through the model in slices.

**When the site blocks the fetch.** When a source answers a page save or a
search in the owner's browser with a challenge or a sign-in, the session
notifies the owner and waits; once the owner has passed it by hand, the session
continues. The session never passes a challenge itself, and a challenge does
not by itself make the source assisted-only.

**The image saves itself.** A gravestone photograph on a memorial accepted as
a person's own (by the owner or by the rule) is a fetch step of its own under
the cemetery row, one per photograph the page types Grave, with the image's
URL as its locator and the page's words (the memorial, the photograph's id,
its caption and type) as its fields; `tools/fetches.py list` prints it with
the file name to save under and says it is an image. Open the image's own URL
in a new tab and run `tools/save_image.js` in it with the name filled in: the
tab fetches its own bytes and hands them to the browser as a download;
`collect` moves it to `inbox/` and attaches it to its step by that name (an
image carries no identity in its bytes), archived under the gravestone row
(E05, tier 1) with the image's URL as locator, logged found, never parsed. It
is read one person at a time by the transcription path, the screen's form or
the model, into a card like any other image.
`tools/attach_inbox.py` then takes every file in `inbox/`: it reads the
record's own identity from the file (the memorial id, the ark), archives it
once, logs a found run on every fetch step whose citation carries that
identity, and runs the extractor and matcher once; the screen's own attach
does the same for the step the person chose plus every other step the record
fulfils. A file whose identity matches no step stays in the inbox.

**A link on the owner's word.** When a record stops short of naming both
parties in full (a marriage index that gives the spouse's surname by four
letters), the owner can place a person in a family on their own word about
that record (`conclude.link_on_word`): the membership carries one Accepted
assertion on the artifact, vouched, with the owner's reason, and a marriage
the record dates becomes the couple's Marriage event on the same evidence. A
divorce is a `Divorce` event on the couple's family (`conclude.divorce`), dated
as the records allow, with an Accepted assertion per piece of evidence the
owner names; the couple stays a family so the children keep both parents, and
the screen shows the pair with a broken heart and the date between them.
A record the owner cites on their own word, with nothing in the file and
nothing archived yet (a census schedule they have seen: the place, the
enumeration district, the sheet), is a fetch step on the person's plan
carrying those details as the owner gives them (`tools/cite.py`,
`attach.cite_on_word`), each field on the owner's word and the holder as
its locator: the runner asks the holder's connector for it exactly as for
a record the file cites, what comes back is fetched for that person and
read by the extractor, the matcher and the standing rule like any other
record, and the planner never drops the step.

**A family-held original.** A photograph or scan of something the family
holds (an heirloom's label, a letter, a Bible page) has no record identity and
no step. It is archived under the family-held source (M05, tier T3: a family
statement) on the owner's word about whom it concerns, filed under the tree,
and read one persona at a time by the owner or the model; the matcher puts the
reading before the owner as a card for the person named. Nothing on it is taken
by the rule.

**A search at an assisted source.** For a missing cemetery row the step
carries the Find a Grave search URL built from the foundation fields (first
given name, surname, birth and death years each with the site's year filter
at 3, the birth surname included for a woman, the first spouse as the linked
name; no location, which filters on the cemetery's place rather than the
death place). The owner's browser opens it once and saves the results page
into `inbox/`. The results page's identity is the search's own fields, so
`tools/attach_inbox.py` attaches it to the cemetery search step whose fields
they are: the page is archived with the search URL as locator, the log row
carries the query as run and the number of results and pages, and the
extractor makes one persona per row. The audit is the matcher: every row
against the person and their relatives, dates compared as dates (a different
day in the same year disagrees; a bare year against a full date agrees on the
year only and says so), and a `persona_match` proposal only for a row that
agrees on the surname and on at least one of birth date, death date or burial
place; a disagreement beside such an agreement stands in the rationale, the
likely identity and the difference together. A row that agrees on the name
alone, or fits nobody, gets no proposal; it
stays a candidate on the page, and the candidate card lists every row with
its fields as agrees, disagrees or absent and its memorial URL. No fit at all
sets the run to `none`. Nothing is fetched by the audit: a candidate the owner
accepts is fetched by the one-call method and attached like any memorial. A
second page of results is a second run of the step, never automatic.

A FamilySearch search step (a missing row at a collection FamilySearch holds:
a census year, a state's vital records) carries the site's record search
prefilled the same way (`catalog.familysearch_search_url`), and its results
page, saved in the browser, comes in the same way: its identity is the
search's own fields read from the saved page's URL (`q.givenName`, `q.surname`,
the birth range, the collection), `tools/attach_inbox.py` attaches it to the
search step whose fields they are (the surname, the first given name, a birth
year inside the page's range, the census year of the collection searched), the
extractor makes one persona per row with the record's own ark as its identity,
the row's events (a census as a residence on its date and place) and the
relatives it names, and the matcher audits every row as it audits a memorial
search; the record page of a row that fits is saved by the same method. When
a step's sources include a holder with a connector as well (the 1950 site),
the page saved by hand and the connector's own answer are runs of the same
step, whichever came first.

A source is `auto` only when its registry row names a built connector (the
`Connector` column of `data/data-sources.csv`): `loc_gov` on H01 (Chronicling
America through the loc.gov JSON API), `nara_1950` on D05 (the 1950 census
site's own name search), and on the Internet Archive's full-text search
`ia_newspapers` on H07 (the newspaperarchive collection, an obituary step
keeping the death year and the next), `ia_directories` on K01 (items with
directory in the title, the person's adult years) and `ia_books` on L02
(genealogies and histories by title, hints; a fetch step whose citation names
a book asks the Archive's advanced search for the title and reads the copies
found, the search inside each for the citation's surname), `wikitree` on B04 (the
shared tree's search by name and birth or death year, each profile fetched
with its parents, spouses, children and siblings; a page anyone can edit, so
always a card), `va_graves` on E03 (the Nationwide Gravesite Locator's
own search, posted by surname and first given name with the step's death
year; the results page is the record: each veteran's name, dates of birth and
death, rank, branch, war period, cemetery, section and site), and
`nj_death_index` on C09 (the New Jersey death index 2001-2017 as Reclaim The
Records' CSV files on the Internet Archive, fetched whole and read locally;
the death record row alone, since C09 sits on the birth and marriage rows
too; the surname's own rows out of the whole file are the record, a none run
when none fits anyone).
`tools/run_step.py` runs an auto step at every
connector its sources have, one log row per source, and a fetch step at its
holder's connector and at those of its row's sources too (an obituary cited at
a closed source runs at the Archive's newspapers and at loc.gov with the
citation's paper and date; the page saved by hand and a connector's answer are
runs of the same step): the connector turns the
step's rendered fields into requests, every response is archived as it came
with the request URL as locator, each hit's own transcription or text and
image are archived too (a hit may lead on: an Archive item's metadata names
the server, the search inside it names the page, the reader gives the page
image; the search inside is asked once per spelling of the surname the alias
table holds for the person, Ahearn then Ahern, the pages merged; a book the
Archive only lends stops at its metadata and the run is `none` with the
reason), one `search_log` row holds the exact query, the outcome and every
hash, and the extractor and matcher run on each hit's record.
It runs a fetch step the same way when the citation's free holder has a
connector: the 1950 site takes the citation's surname within its enumeration
district and answers with the household's schedule, whose every row becomes a
persona and whose image is archived beside it; the page is logged found on
every household member's step that cites the same year, district, place and
page. A schedule row that fits nobody stays on the page. A household record
that arrives any other way (a page saved by hand, a search's result) holds a
member's own row the moment its persona is accepted onto them: their step for
that census year is logged found with the record, so no runner searches that
census again for a household the tree has read. The Archive takes a
cited book's title and the gravesite locator the citation's name; a citation
that names no book gives the Archive nothing to ask, and that step is logged
`none` there, the note naming the field wanted, and left for a hand on the
person's screen, not the fetch list. A source's years, from the registry's coverage column, gate its
steps: an obituary step for a death after Chronicling America's last year is
logged `none` at loc.gov without a request, the note saying so. A connector
with nothing to ask on the step's fields (WikiTree without a birth or death
year, the Archive's books without a state, a cited book without a title) is
logged `none` the same way, without a request, the note naming the field it
wanted, so the step is asked again once the plan writes that field. Each
source's runs on a step are read on their own: a step whose row has two
connectors is asked at the ones whose source has no found or none run on its
current fields, so one connector's none does not close the step at the other,
and a source that did not answer (a run logged `error`) is asked again on the
next turn while the rest are not. A connector's request may post a form, name the identity its
response is archived under, and say the response is itself the record. Every
other search step is `assisted` or `awaiting_approval`.

Open sources with connectors are the standard path and Ancestry is the
exception: a step runs automatically wherever a free source with a documented
endpoint holds the record kind, and the browser-driven fetch exists only for
records the tree already cites at a closed source. Never crawl or search a
closed source.

**A cited record may be fetched from any holder of the same collection.**
Ancestry is a citation source, not a fetch source: its record pages and
images need a membership this account lacks. The record a citation points at
is the same census sheet, certificate or memorial wherever it is held, so the
fetch step is re-targeted to the free holder of the collection
(`data/holders.csv`: FamilySearch for the federal censuses and the
Massachusetts, Kentucky, Tennessee, New Jersey and Ohio vital collections, the
National Archives site for 1950, Find a Grave for its own index). The lookup at
the holder uses the citation's own details only: the collection, the year,
the census place, the enumeration district and sheet, the certificate range,
the memorial URL, and the name the citation sits on (the tree's name of that
person, the only name the export carries for the record). It never uses the
person's unreviewed facts, so a fetch stays allowed before the baseline is
reviewed. One record at a time, found through the holder's own collection
search on those details, in the owner's own browser when the holder has no
endpoint. A collection with no free holder yet leaves its steps `blocked`.

Every execution is a **research log** row: query as actually run, source, date,
outcome (`found`, `none`, `blocked`, `error`), artifacts produced. "Searched the
1880 census of Worcester Township for Brant, none found" is evidence and stays.

A `missing_fact` or `unverified_claim` question is about the absence of a
claim, so it closes as answered the moment an accepted document supplies the
claim; the document's assertion is Accepted with the document, and a value that
differs from the tree's is a `conflict` question, not a silent change.

## 5–7. Extract, match, review

Fetched records go through the evidence layer (extraction → personas). A
record page saved as HTML is parsed on arrival by `tools/extract.py`, which
reads the page's kind from the page itself: a Find a Grave memorial goes to
extractor `rule:findagrave-memorial@0.3.0` (the memorial's name, dates,
places, plot, inscription and biography as written and memorial id on one
persona, one persona per family member in the page's own label word with a relation to the
memorial's subject, and in the parsed page every photograph with the type the
page gives it; verified on a real memorial), a Find a Grave search
results page to `rule:findagrave-search@0.1.0` (one persona per row, the
memorial id and URL as its identity), a FamilySearch record page to
`rule:familysearch-record@0.1.0` (one persona per person the page names, in
the page's own role word, one fact per field as written, one relation per
stated relationship, the relatives its fields name as personas; verified on
real pages), an Ancestry index page to `rule:ancestry-index@0.1.0` (built to
Ancestry's page structure, not yet verified on a real page), a FamilySearch search results page to
`rule:familysearch-search@0.1.0` (one persona per row with the record's ark as
its identity), an AAD enlistment results page to `rule:aad-search@0.1.0` and a
full enlistment record to `rule:aad-enlistment@0.1.0`, a 1950 census
site response to `rule:nara-1950-schedule@0.1.0`, a loc.gov OCR response
to `rule:loc-gov-ocr@0.1.0`, the Archive's search inside an item to
`rule:ia-search-inside@0.1.0` and a WikiTree profile with its relatives to
`rule:wikitree-profile@0.1.0`; a page no parser claims gets a failed extraction
by `rule:extract@0.1.0` and is reported. The raw parsed page is in
`extraction.structured_json`. Re-running an
extractor, at any version, supersedes its earlier extraction and rejects that
extraction's undecided proposals with the note `superseded`; a persona the
earlier extraction had decided carries its decision to the new persona of the
same name and role on the same page (the decision was about the record, whose
bytes have not changed), an accepted one asserting the new facts the record
gives and nothing it already asserted, and the matcher proposes the rest
again. The matcher is versioned the same way (`rule:matcher@0.2.0`, raised
with any change to what fits): `tools/conclude.py reconsider` runs it again on
every current extraction whose undecided proposals an older matcher wrote,
rejecting those with the note `superseded` and proposing the personas again as
the matcher stands. A record image gets no
automatic extraction: it is read one person per row through the screen's
transcription path. The model reads it by default (extractor `llm:<model>`,
layer 3 like any extraction, `docs/DATA-ARCHITECTURE.md` §1), each persona in
the record's own role word with its facts as written, a birth calculated from
an age and the record's year (qualifier `calculated`, so the matcher allows
two years), and its relation to the head; a person reads it (extractor
`human:<user>`) only on serious doubt, stated as the reason. An index page
whose own name is a slip — an indexer's transposition or misreading, not a
fresh fact — goes through the same path to the same default. What the
reading proposes is decided like any record, the rule taking it exactly as
it takes a parsed record, never by who did the reading. That is the
path for every image until an OCR or HTR extractor exists.

`tools/match.py` runs on every extraction as it is written, one person at a
time. For each person whose step the record fulfils, every persona is
compared with that person and their relatives as the catalog knows them, but
a proposal may name only the person the record was fetched for, a person
attached to them by a record already accepted (a vouched link is a claim the
owner stands behind, not a document, so a vouched relative waits too), or a
person already accepted under the memorial the persona links (the same page
is the same identity); every other persona waits, shown on the card as
waiting on this decision. Accepting the document as that person's runs the
matcher again: the record's other personas are then proposed against the
accepted person's relatives, claims included, and against a person of the
tree with the persona's surname and a birth within three years who stands in
the tree with no family link yet; a persona the record relates to the accepted
person and that fits nobody is proposed as a new person then, never before. So
a household or a profile is decided one person after another, each on the
record's own words about the last. The comparison
is on name, sex, birth and death dates, birth, burial and death place, the
residence the record gives against every place the tree knows the person at,
and the relationships the record states; a persona fits only on more than a
name and a year (a place, a death, a full date or a stated relationship); a census index's estimated birth year and a
household member's age become a calculated birth year the matcher allows two
years on. As a bare year against a full date agrees on the year only and says so (§4), a place agrees on the part it
states even when it is coarser than the tree's own: a record place that names the tree's own place, or an ancestor of it
in the resolved hierarchy (the county, or the state alone, spelled out or as its two-letter US code), agrees on the level
it names and the rationale says which place that is; and a record place inside the tree's own — the tree's place with a finer
part named ahead of it (the town when the tree holds only the state) — agrees on the level the tree states, the finer part is
not compared, and the rationale says the record is finer and names it; a place that is neither the tree's place, nor an
ancestor of it, nor inside it still disagrees — save a record place naming a county alone, which takes the state its own
collection is registered under (a bare county otherwise names no state at all to compare) and the rationale says so; the
place string itself stays as written. A surname agrees as written or as a spelling variant, the same
Soundex code within two edits (Ahearn and Ahern, Brant and Brandt), said so
in the rationale. A given name agrees through its common short forms (Willie for
William, Charley for Charles) and across a one-letter slip in a longer name; a
wife written under her husband's surname is not a surname disagreement, nor is
any woman's the record otherwise shows married: a daughter or sister carrying
another surname beside a son-in-law or brother-in-law of that surname on the
same record, or written "Mrs." A
persona of the same name as a candidate that disagrees on something else is
still proposed as that candidate, with the disagreement in its rationale, so
the owner sees the likely identity and the difference together; the rule never
takes such a proposal, and when another persona on the same page fits that
candidate, or is already accepted as them, the near one is not proposed at
all: one decision is put once, and the near persona stays a hint on the page.
A persona of the same name that disagrees on both its dates is not a likely
identity either: it stays a hint on the page, never a card.
A row of a results page, a schedule row or a name in running text that agrees
on the name alone is a hint on the page too, never a card: its own record is
the document. One proposal per persona: `persona_match`
with the candidate that fits, or `new_person` when nobody does. The rationale
is plain words, which fields agree, which disagree, which are absent; no score
is stored or shown. A proposal carries the step's question when the step has
one, so it **answers a question**: "Is the James Ahearn in this 1870 household
Thomas's father?" Review happens on the person's screen, on the held record.
The decision is about the document: is this record's persona this person.
Accepting writes the persona link Accepted and an Accepted assertion from each
fact the record states to the person: Name and Sex assert the person; an event
fact asserts the person's event of that type and year, created from the
record's date when the person has none of that type; an attribute the record
states (an occupation, an inscription) asserts the person's attribute of that
type, created with the record's value when the person has none; a fact about
the record or the page (its id, an age at death) asserts nothing. Where the
record says the persona is the child, parent or spouse of a persona already
accepted as a person on the same record, the family link between the two
carries an Accepted assertion on the artifact too, created in a family of the
right shape when the tree lacks the link: a parent-child relation is evidence
on the child's membership, a spouse relation on both partners'; a sibling
stated on the record places the person as a child of the other's accepted
parents with an Undecided assertion (the record states the sibling, not the
parents), and only when the other is an accepted child of one family;
otherwise a sibling gives no membership. On a page anyone can edit (T4) the
decision is an identity: the persona link is Accepted, and the family
memberships the page states are created where the tree lacks them, each with
an Undecided assertion, the way a sibling placement already is; every fact
the page types is written as an Undecided assertion too, what the page says,
never accepted by the decision and never ground for the rule. Where the
record's date or place
disagrees with the event's own value, the record's statement is still accepted
as what that record says, the event keeps its value, and the difference is a
`conflict` question on the person, generated from the catalog
(`Catalog.disagreements`) and shown in the plan. Nothing a person did not
approve as a document becomes Accepted: the per-fact decision remains for the
file's own claims (the vouch) and for undoing a single claim. Rejecting writes
the link Rejected. A `new_person` proposal is decided the same way: accepting
creates the person in this tree with the name as written (a maiden name the
record marks becomes the birth surname), the persona link Accepted, the same
assertions and the same family links. Rejecting writes the proposal rejected
and nothing else.

**The standing rule.** After the matcher writes its proposals, the rule takes a
`persona_match` on the owner's behalf when the record's collection is of a kind
that identifies a person fully (§0's list: a census from 1850, a 1950 schedule,
a certificate or index of birth, death or marriage, Social Security, service
records, a veteran's gravesite; a land or public records index is a hint), read
by hand or by the model exactly as one a rule parsed — the rule judges the
record's own kind, tier and agreeing facts, never who did the reading. A
persona whose stated relationship (child, parent, spouse, sibling) is to a
persona accepted on the same record as a person the tree links to a
candidate by that relation, claimed or accepted, is taken the same way when
the persona's given name and surname agree with the candidate's name,
claimed or accepted, and a birth year agrees where both have one; the
record's own name fact then documents the name. A persona stated as a sibling
of a person accepted on the record fits a candidate who is a child of that
person's parents in the tree, claimed or accepted, or who has no parents in
the tree at all and whose surname agrees (nothing holds the sibling, nothing
contradicts it), and is taken the same way; accepting places the candidate as
a child of those parents with an undecided assertion, as a sibling placement
is. A sibling the tree holds counts as a relationship point like a parent or
a spouse, on the evidence of the child membership beside the other's. A persona such a trusted
record (T1–T2, or an obituary once read) names in a stated relationship to a
person accepted on it, who fits nobody in the tree after the fitting check,
is created by the rule as a person with the record's facts and the family
link accepted, and enters the queue. The fitting check, run before any
creation: a person of the tree with the same surname or birth surname and a
birth year within the matcher's window, or the same stated relationship to
the same accepted person, fits and is proposed instead of a new one. An
obituary or newspaper text is such a kind only once read (a bare citation is
still a hint) and only on its own ground: one of its two points must be a
stated relative who is that relative in the tree, on trusted evidence — no
number of agreeing dates or places substitutes, because the named survivors
are what identifies the person here (§0). Its source is one nobody can edit at
will (T1–T3), the given name and surname agree with the accepted name (a wife
under her married surname agrees too — that is how her own obituary can name
her at all), at least two accepted facts agree (birth date,
death date, a death or burial place, a stated relationship to a person the
record names who fits a relative the tree already links, the relative's own
persona on that same record being already accepted as them counting as such
a fit (accepted by the owner); a date agreeing to the day on a trusted
statement of the day, and a relationship the tree holds on trusted evidence,
each count double) and each rests, on the very event or link compared, on a
trusted source or on the owner's own word, and nothing among them disagrees;
a disagreement with a value that rests on no accepted assertion is not a
veto here either, and becomes the same conflict question. A
surname agreeing only one letter apart is a card, never the rule's. Claims never count, and a fact that
rests only on a page anyone can edit does not count either. The one exception, on the owner's word: a stated
relationship to a relative the tree links by a claim alone counts one point, never double, when that relative's own
persona on the record fits them on more than a name (a name and an age, a name and a place), so a confirmed child in
the claimed parents' census household is taken on name, birth year and the stated parent, and the parents then
follow through the claimed route above; an obituary's named survivor is still one the tree holds on trusted
evidence. On a page anyone can edit that identifies a person (a
memorial, a profile) the rule takes the identity alone, when the name agrees and at least three of birth date to the
day, death date to the day, burial place, and a stated parent or spouse who is that relative in the tree agree with
the tree, claimed or accepted; a relative the page lists by name and years alone has at most the stated relation and
is a card for the owner. The proposal records the rule as the decider with its
reason in words, the audit row says the same, and the card shows "accepted by
rule" with a Reject control: rejecting turns the link and every assertion the
rule wrote rejected. A proposal the rule does not take is a card for the owner
with the reason it was not taken. The rule creates a person only as above,
through the fitting check; every other `new_person` proposal is a card for
the owner. The rule
can take a decision back: `tools/conclude.py reconsider` examines every
decision it made, oldest first, as the rule stands now and on the ground that
stood before it (its own assertions and those of later rule decisions do not
count), withdraws one it would no longer take, and the record is a card for
the owner again with the reason; accepting that card makes everything the
decision had written stand again. It then proposes again the cards an older
matcher wrote, and examines every card still undecided
the same way and takes one it would now take, recorded as the rule; a decision
can open another card, so it passes again until nothing new is taken. Run it
after any change to the rule, to the matcher or to a source's tier.

Every accept, of a match, a new person or a fact,
regenerates the person's plan in the same request, and an open question of
kind `missing_parents`, `unverified_claim` or `missing_fact` that the
regeneration closes is closed as `answered` with the proposal that brought the
evidence; a `conflict` closes only when a person dismisses it. Accepting grows
the baseline, which generates new questions.

## 8. The loop

A turn is one person's plan run end to end: the cited fetches at holders with
connectors, the assisted saves made through the owner's own browser session,
the auto searches, the standing rule's decisions on what comes back, the
people it creates, and the plan regenerated at the end. The queue a turn
draws from is the edge of the confirmed tree, in the overview's own order
(`tools/tree.py overview`): the home person's line first, then everyone a
record names after. The living default (`docs/DATA-ARCHITECTURE.md` §7)
stands unchanged inside a turn. A challenge at a holder pauses the turn for
the owner's hand and resumes once they have passed it (§4); it does not stop
the turn, and it does not by itself make the source assisted-only. What a
turn leaves for the owner are the conflict questions it raised and the cards
the rule did not take.

`tools/queue.py` names the next person. It walks the overview's own order,
the home person's line first, generation by generation, and at each confirmed
card takes a parent or spouse the file names whose link is not yet accepted
before the card's own person, then that person when a document waits, a
conflict is open or a key fact is undecided and a turn can still act on them:
a step a connector can run with no run since the plan last wrote its fields,
or a page the fetch list can name. A person whose open question is now the
owner's alone (a card to decide, a conflict, an assisted search with no link
to open) is passed over with the reason; `--all` lists everyone.

`tools/turn.py "<person>"` runs the turn: `tools/plan.py` first, then every
step a connector can run on this person's plan, one commit each as
`tools/run_step.py --all` does, the standing rule deciding what comes back and
creating the people a record names; then this person's own pages at holders
without a connector (`tools/fetches.py list`, narrowed to their unrun steps)
are printed with the file name to save under, and the turn pauses for the
owner's browser session, its state kept beside the catalog.
`tools/turn.py --resume` picks the paused turn up: `tools/fetches.py collect`,
`tools/attach_inbox.py` on whatever collect's naming left behind,
`tools/conclude.py reconsider`, and the plan regenerated; a turn with nothing
to fetch runs the same tail in the same call. The turn writes nothing of its
own: every catalog write is one of those tools' under its own name. Its
report says what was held, what the rule decided, who was created and what is
left for the owner, in words. A record the owner cites on their own word
(`tools/cite.py`) is a fetch step on the plan a turn runs like any other.
`tools/turns.py` is the loop run without a hand on it: it asks the queue for
the next person, runs their turn with `tools/turn.py`'s own code, prints the
turn's report and asks the queue again, until the queue names nobody a turn
can act on, a turn pauses on pages to save (the runner stops with that list
printed and the turn's state kept; the session at the owner's browser saves
them and calls `tools/turns.py --resume`, which resumes the paused turn and
goes on to the next person), or `--turns N` turns are done. A person the
queue names again whose last turn held nothing new for them is passed over
for the rest of the run with that reason. Its own state (the turns run, each
person's held count before and after, the passed-over) lives beside the
turn's state file on the same pattern; it writes nothing of its own to the
catalog. A connector's challenge is an error run, the source did not answer,
and the turn goes on; a challenge in the browser is the session's pause,
outside the runner. Its summary says, in words, the turns run, the people
passed over and why, and what is left for the owner.

## Worked example: Thomas Ahearn (1846–1902)

1. Baseline: birth 2 Oct 1846, death 21 Aug 1902, wife Alice McGee, son Patrick,
   no parents, **zero citations on Thomas himself**. Every fact is `unverified_claim`.
   Blocked until reviewed.
2. After review, questions: `missing_parents`; `unverified_claim` × n;
   `duplicate_person`: a second "Thomas Ahearn" with the **identical birth date
   2 Oct 1846** exists in the tree as a child of James Ahearn (1810–1899) and
   Johanna Barry. The dead end is a duplicate entry; the parents are already in
   the tree. The question is answered by resolved data before any search runs.
3. Plan for `missing_parents`:
   - L0 footprint: the 1880 census record cited on Alice and Patrick (Thomas
     should be head of household: age, birthplace, parents' birthplaces);
     the Massachusetts marriage record cited on Alice (names Thomas's parents);
     Patrick's Massachusetts birth record (names both parents, mother's maiden name).
     Three fetches, all records we already cite, before any search.
   - L0 via the duplicate: merging the two Thomas entries closes the question.
     The 1870 census (`1,7163::26817907`) cited on James Ahearn's family is the
     record that proves it (Thomas, 23, in James's household).
   - L1: same collections (MA marriages, MA births, 1870/1880 census) for Ahearn
     in Northampton / Hampshire County.
   - L2: Thomas's own MA death record 1902 (free, T1, names parents); obituary
     in Northampton papers 1902 (loc.gov); naturalization.
   - L4: only if the footprint fails to name the parents.

## Schema

```
research_question (id, tree_id, subject_person_id, kind, q_key, detail_json, status open|closed, closed_reason answered|dismissed|gap_gone, answered_by_proposal_id, created_at, closed_at)
                   kind: missing_parents | identity_incomplete | missing_spouse | missing_fact | unverified_claim | conflict | duplicate_person | unlinked_relative
search_plan       (id, person_id, row_key, question_id?, seq, step_key, kind fetch|search, query_type, query_json {field: {value, basis}},
                   locator_source_id, locator_kind, locator_value, collection_id, on_json, sources_json, mode fetch|blocked|auto|assisted|awaiting_approval,
                   expected, status planned|done|skipped, rationale, revisions_json, created_at)
                   row_key: "<record>:<instance>" of the checklist row, or "footprint:<locator>" for a record on a relative
search_log        (id, tree_id, plan_step_id, question_id, executed_at, executed_by, source_id, query_json, outcome found|none|blocked|error, artifacts_json, notes)
proposal.question_id
source.connector
```

A question is fact-level; a missing checklist row is a unit of work, a step,
not a question, and a step carries a question id only when it answers one.
There is no separate review table: the baseline review is the status on the
assertions behind each key fact. Questions and steps are keyed so
`tools/plan.py` regenerates them idempotently, drops steps no longer generated
(a done one stays; one that was run but is not done is kept for its log as
`skipped`, and is planned again if it is generated again), and closes a
question whose gap has gone; a question a
person dismissed stays closed. `tools/log_search.py` (and the person screen)
record every run with the fields as rendered after include and revise; a
`found` run marks the step done, a `none` run leaves it planned and visible as
tried. A found run that archived a file records the artifact on the log; the
row is then held, and the assertion comes from extraction and review.

## Rules that hold throughout

- There is no hint feed on an unreviewed person. The record citations and
  media references that came with the Ancestry export are data (in the import's
  extraction JSON and on the assertions) and surface only as fetch steps, and
  as Layer 0 footprint steps under the questions of the people they support.
  Hints (§0) live on a reviewed person's screen.
- The footprint is computed from accepted family links and citations, so it
  improves every time a review accepts something.
- Nothing is searched for a person until that person's baseline is reviewed.
  Fetching a record the tree already cites is allowed before review, because
  the review needs the record.
- The first screen is the person: claims, evidence, verdicts, then their
  questions and the plan for each.
- FamilySearch Innovator Program approval is what turns most Layer 1–2
  searches from assisted into automatic.
