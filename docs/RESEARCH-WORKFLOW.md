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

## 1. Baseline: what we know and have approved

An imported tree is a set of **claims**, not knowledge. The Ahearn import has 232
facts with no citation at all and 1,122 citations that point at records we do
not hold. None of that is a baseline yet.

- A human reviews each person and sets each key fact to **Accepted**,
  **Rejected**, or leaves it **Undecided**. Key facts: name, sex, birth, death,
  parents, spouses, children. A person is *baseline-complete* when no key fact
  is Undecided.
- Only Accepted facts feed searches. An Undecided fact can be used as a lead
  and is labelled as such in every query: every query field is `{value, basis}`
  with basis `accepted` or `lead`. A Rejected fact is left out, and a relative
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
| `missing_record` | a checklist row that is missing or cited-but-not-held (`docs/RESEARCH-CHECKLIST.md` §3) | Abram C. Brant: 1900 census household |

42 of the 117 people are dead ends today. Ranking: home person's direct line
first, then tractability (era and place with good record coverage in the
registry), then how many other questions an answer would unlock. Until its subject is
baseline-complete (no key fact Undecided) a question gets no search steps and
no footprint, duplicate or unlinked leads; only fetch steps for records the
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
spouse or parents), unlinked same-surname persons as leads with a generation
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
they serve. Running a step (Go, Search, the log buttons) is the approval;
there is no approval state. Fetches are cheap and decisive, and open before the
baseline is reviewed because the review needs them.

Record type → era → place → source (layer 2) is a lookup, not a guess. The
registry's coverage column drives it (MA deaths 1841–1915 are free and indexed;
Irish civil registration starts 1864, so an 1810 birth means parish registers).

## 4. Search: execute and log every step, including failures

| Mode | Sources | Behaviour |
|---|---|---|
| auto | FamilySearch (after Innovator approval), WikiTree, loc.gov newspapers, NARA catalog, Open Archives, Wikidata, held archive | the system runs the query, archives raw responses, extracts personas |
| assisted | Find a Grave, FamilySearch record search (free account), Newspapers.com, Fold3, Archion | the system builds the exact search URL and tells the user what to look for; the user saves the result to `inbox/`, or a session drives the owner's own logged-in browser to save one cited record at a time; the system takes it from there |
| manual | county courthouses, Schwenkfelder Library, parish archives | the system produces a request letter or visit checklist |

A source is `auto` only when its registry row names a built connector (the
`Connector` column of `data/data-sources.csv`); none does yet, so today every
search step is `assisted` or `awaiting_approval`.

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
claim, so it closes as answered the moment an accepted persona match supplies
the claim with its Undecided assertion. Whether the claim stands is the
baseline review of that fact, tracked on the assertion, not on the question.

## 5–7. Extract, match, review

Fetched records go through the evidence layer (extraction → personas). A
record page saved as HTML is parsed on arrival by `tools/extract.py`, which
reads the page's kind from the page itself: a Find a Grave memorial goes to
extractor `rule:findagrave-memorial@0.1.0` (the memorial's name, dates,
places, plot, inscription and memorial id on one persona, one persona per
family member in the page's own label word with a relation to the memorial's
subject; verified on a real memorial), anything else to
`rule:ancestry-index@0.1.0` (one persona per person the page names, in the
page's own role word, one fact per field as written, one relation per stated
relationship; built to Ancestry's page structure, not yet verified on a real
page). The raw parsed page is in `extraction.structured_json`. Re-running an
extractor supersedes its earlier extraction and rejects that extraction's
undecided proposals with the note `superseded`. A record image gets no
automatic extraction: the person screen offers a transcription form on a held
record with no persona, one persona at a time, written as an extraction by
extractor `human:<user>`. That is the fallback for every image until an OCR or
HTR extractor exists.

`tools/match.py` runs on every extraction as it is written. For each person
whose step the record fulfils, every persona is compared with that person and
their relatives as the catalog knows them, on name, sex, birth year and the
relationships the record states. One proposal per persona: `persona_match`
with the candidate that fits, or `new_person` when nobody does. The rationale
is plain words, which fields agree, which disagree, which are absent; no score
is stored or shown. A proposal carries the step's question when the step has
one, so it **answers a question**: "Is the James Ahearn in this 1870 household
Thomas's father?" Review happens on the person's screen, on the held record.
Accepting a match writes the persona link Accepted and an Undecided assertion
from each of the person's events to the matching persona fact, creating the
event from the fact's date when the person has none of that type; Name and
Sex facts assert the person. Rejecting writes the link Rejected. Nothing
becomes Accepted at the fact level here: the fact decision does that, and it
now has held evidence to accept. A `new_person` proposal is decided the same
way: accepting creates the person in this tree with the name as written (a
maiden name the record marks becomes the birth surname), the persona link
Accepted, the same Undecided assertions, and a family membership with an
Undecided assertion on the artifact where the record says the persona is the
child, parent or spouse of a person matched on the same record; a sibling
stated on the record gives no membership. Rejecting writes the proposal
rejected and nothing else. Every accept, of a match, a new person or a fact,
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

- There is no hint queue. The record citations and media references that came
  with the Ancestry export are data (in the import's extraction JSON and on the
  assertions) and surface only as Layer 0 footprint steps under the questions
  of the people they support.
- The footprint is computed from accepted family links and citations, so it
  improves every time a review accepts something.
- Nothing is searched for a person until that person's baseline is reviewed.
  Fetching a record the tree already cites is allowed before review, because
  the review needs the record.
- The first screen is the person: claims, evidence, verdicts, then their
  questions and the plan for each.
- FamilySearch Innovator Program approval is what turns most Layer 1–2
  searches from assisted into automatic.
