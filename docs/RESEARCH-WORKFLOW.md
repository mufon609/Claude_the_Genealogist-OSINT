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
accepted and nothing disagrees, and everything the document states comes with
it. It may do so only for document kinds that identify a person fully, from
sources nobody can edit at will (registry tiers T1–T3: certificates, census,
obituaries, published works), and only counting accepted facts that themselves
rest on such a source or on the owner's own word. A page anyone can edit (T4:
Find a Grave, member trees) is a lead and a card, never a ground the rule
stands on, and a person whose accepted facts rest on T4 alone is marked so on
their card until a trusted record about them is accepted. Every other kind is
a hint until a person reads it. The starting list, to be refined as records
are met:

| Document | What it gives | Standing |
|---|---|---|
| Federal or state census 1850 on | full names and ages; relationships from 1880 | automated |
| Federal census 1790–1840 | the head's name, the rest counted | hint |
| Find a Grave memorial | full name, dates, cemetery, linked family | a card, always: anyone can edit the page |
| Death, birth, marriage certificate or index | full name, dates, parents or spouse | automated |
| Social Security index, draft cards, veterans' files | full name, exact birth date | automated |
| Church register entry | names and dates when the register keeps them | automated when dated and the parents are named; hint otherwise |
| Obituary, newspaper hit | free text | hint until the text is read; then the named survivors decide |
| Will, probate, land, tax, directory | names, no ages | hint |
| Compiled genealogy, family Bible | lineage, no proof | hint, never proof |
| A row on a search results page | name, years, place | hint; its own record is the document |

## 1. Baseline: what we know and have approved

An imported tree is a set of **claims**, not knowledge. The Ahearn import has 232
facts with no citation at all and 1,122 citations that point at records we do
not hold. None of that is a baseline yet.

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

42 of the 117 people in the imported file are dead ends. Ranking: home person's direct line
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
citation whose collection has no free holder is a fetch step with mode
`blocked` and the reason in its rationale. A **search**
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

## 4. Search: execute and log every step, including failures

| Mode | Sources | Behaviour |
|---|---|---|
| auto | Chronicling America (loc.gov), the 1950 census site; FamilySearch after Innovator approval, WikiTree, NARA catalog, Open Archives, Wikidata, the held archive when their connectors exist | the system runs the query, archives raw responses, extracts personas |
| assisted | Find a Grave, FamilySearch record search (free account), Newspapers.com, Fold3, Archion | the system builds the exact search URL and tells the user what to look for; the user saves the result to `inbox/`, or a session drives the owner's own logged-in browser to save one cited record at a time by the page-saves-itself method below; the system takes it from there |

**The page saves itself.** A cited page at an assisted source is saved from
the owner's own browser in one call and never read through the model: open
the citation's URL in a new tab, wait for the page to load, run one script
in the page that clones the document, removes `iframe`, `script`, `style`,
`link` and `noscript` elements, and hands the result to the browser as a
download named after the record's own id; the script returns the byte count
and whether the parser's marker and the family markup are present, and all
three must hold before the tab is closed. Move the file from the download
folder to `inbox/` and log the step as found with it. Measured on a Find a
Grave memorial: one call, about half a minute from navigation to file, the
saved page a quarter of the rendered size, nothing transcribed. If the
browser is set to ask where to save each download, turn that off first or
answer the dialog by hand; a dialog left open blocks every later browser
call. Chrome lets a page start one download without a hand on it: a second
page saved in the same tab lands nowhere, so each page gets its own tab,
closed after the file arrives. `tools/memorials.py list` prints every memorial
a planned fetch step points at, once, leads from held records first, with the
people waiting on it; a browser session works down that list one tab per page;
`tools/memorials.py collect` then moves every saved page from the download
folder into `inbox/` and attaches each by its own identity. Never encode a page and read it out through the model in slices.
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
place with nothing disagreeing. A row that fits nobody gets no proposal; it
stays a candidate on the page, and the candidate card lists every row with
its fields as agrees, disagrees or absent and its memorial URL. No fit at all
sets the run to `none`. Nothing is fetched by the audit: a candidate the owner
accepts is fetched by the one-call method and attached like any memorial. A
second page of results is a second run of the step, never automatic.

A source is `auto` only when its registry row names a built connector (the
`Connector` column of `data/data-sources.csv`): `loc_gov` on H01 (Chronicling
America through the loc.gov JSON API) and `nara_1950` on D05 (the 1950 census
site's own name search). `tools/run_step.py` runs an auto step: the connector
turns the step's rendered fields into requests, every response is archived as
it came with the request URL as locator, each hit's own transcription or text
and image are archived too, one `search_log` row holds the exact query, the
outcome and every hash, and the extractor and matcher run on each hit's record.
It runs a fetch step the same way when the citation's free holder has a
connector: the 1950 site takes the citation's surname within its enumeration
district and answers with the household's schedule, whose every row becomes a
persona and whose image is archived beside it; the page is logged found on
every household member's step that cites the same year, district, place and
page. A schedule row that fits nobody stays on the page. Every other search
step is `assisted` or `awaiting_approval`.

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
extractor `rule:findagrave-memorial@0.2.0` (the memorial's name, dates,
places, plot, inscription as written and memorial id on one persona, one
persona per family member in the page's own label word with a relation to the
memorial's subject; verified on a real memorial), a Find a Grave search
results page to `rule:findagrave-search@0.1.0` (one persona per row, the
memorial id and URL as its identity), a FamilySearch record page to
`rule:familysearch-record@0.1.0` (one persona per person the page names, in
the page's own role word, one fact per field as written, one relation per
stated relationship, the relatives its fields name as personas; verified on
real pages), an Ancestry index page to `rule:ancestry-index@0.1.0` (built to
Ancestry's page structure, not yet verified on a real page), a 1950 census
site response to `rule:nara-1950-schedule@0.1.0` and a loc.gov OCR response
to `rule:loc-gov-ocr@0.1.0`; a page no parser claims gets a failed extraction
by `rule:extract@0.1.0` and is reported. The raw parsed page is in
`extraction.structured_json`. Re-running an
extractor, at any version, supersedes its earlier extraction and rejects that
extraction's undecided proposals with the note `superseded`; a persona the
earlier extraction had decided carries its decision to the new persona of the
same name and role on the same page (the decision was about the record, whose
bytes have not changed), an accepted one asserting the new facts the record
gives and nothing it already asserted, and the matcher proposes the rest
again. A record image gets no
automatic extraction: it is read one person per row, by the person acting
through the screen's transcription form (extractor `human:<user>`) or by the
model reading the image (extractor `llm:<model>`, layer 3 like any extraction,
`docs/DATA-ARCHITECTURE.md` §1), each persona in the record's own role word
with its facts as written, a birth calculated from an age and the record's year
(qualifier `calculated`, so the matcher allows two years), and its relation to
the head. What the reading proposes is decided like any record. That is the
path for every image until an OCR or HTR extractor exists.

`tools/match.py` runs on every extraction as it is written. For each person
whose step the record fulfils, every persona is compared with that person and
their relatives as the catalog knows them, and with two more kinds of
candidate the record itself points at: a person already accepted under the
memorial the persona links (the same page is the same identity), and a person
of the tree with the persona's surname and a birth within three years of the
persona's, who may stand in the tree with no family link yet. The comparison
is on name, sex, birth and death dates, burial and death place and the
relationships the record states; a census index's estimated birth year and a
household member's age become a calculated birth year the matcher allows two
years on. A given name agrees through its common short forms (Willie for
William, Charley for Charles) and across a one-letter slip in a longer name; a
wife written under her husband's surname is not a surname disagreement. A
persona of the same name as a candidate that disagrees on something else is
still proposed as that candidate, with the disagreement in its rationale, so
the owner sees the likely identity and the difference together; the rule never
takes such a proposal. One proposal per persona: `persona_match`
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
stated on the record gives no membership. Where the record's date or place
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
records; an obituary collection, a land or public records index is a hint) and
its source is one nobody can edit at will (T1–T3), the given name and surname
agree with the accepted name, at least two accepted facts agree (birth date,
death date, a death or burial place, a stated relationship to a person the
record names who fits a relative the tree already links; a date agreeing to
the day on a trusted statement of the day, and a relationship the tree holds
on trusted evidence, each count double) and each rests, on the very event or
link compared, on a trusted source or on the owner's own word, and nothing
compared disagrees. Claims never count, and a fact that
rests only on a page anyone can edit does not count either. The proposal records the rule as the decider with its
reason in words, the audit row says the same, and the card shows "accepted by
rule" with a Reject control: rejecting turns the link and every assertion the
rule wrote rejected. A proposal the rule does not take is a card for the owner
with the reason it was not taken. The rule never creates a person. The rule
can take a decision back: `tools/conclude.py reconsider` examines every
decision it made, oldest first, as the rule stands now and on the ground that
stood before it (its own assertions and those of later rule decisions do not
count), withdraws one it would no longer take, and the record is a card for
the owner again with the reason; accepting that card makes everything the
decision had written stand again. Run it after any change to the rule or to a
source's tier.

Every accept, of a match, a new person or a fact,
regenerates the person's plan in the same request, and an open question of
kind `missing_parents`, `unverified_claim` or `missing_fact` that the
regeneration closes is closed as `answered` with the proposal that brought the
evidence; a `conflict` closes only when a person dismisses it. Accepting grows
the baseline, which generates new questions.

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
unless they were run, and closes a question whose gap has gone; a question a
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
