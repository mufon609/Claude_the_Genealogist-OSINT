# Research workflow

The app does not start from records and it does not start from hints. It starts
from what the family already knows and has approved, turns the gaps into
questions about people, and works each question down a ladder of searches that
does not need a name until a name has been found.

```
 ┌──────────┐   ┌───────────┐   ┌──────┐   ┌────────┐   ┌─────────┐   ┌───────┐   ┌────────┐
 │ BASELINE │ → │ QUESTIONS │ → │ PLAN │ → │ SEARCH │ → │ EXTRACT │ → │ MATCH │ → │ REVIEW │ ─┐
 └──────────┘   └───────────┘   └──────┘   └────────┘   └─────────┘   └───────┘   └────────┘  │
      ▲            (auto)        (AI, approved)  (auto/assisted,  (layer 3)   (proposals    (person-      │
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
  and is labelled as such in every query.
- Review is person-centred: one person, their claims, the records behind each,
  verdict per fact. This is the first screen.

## 2. Questions: generated from gaps in the baseline

Questions are always about a person. They are generated, not typed:

| Kind | Trigger | Example from this tree |
|---|---|---|
| `missing_parents` | no parents in tree | Thomas Ahearn (1846–1902): 0 citations, no parents |
| `identity_incomplete` | no surname, or given name only | "Dorothy", "Minerva E", "Carol Evers" |
| `missing_spouse` / `missing_children` | family with one partner / none | John Brant, Elizabeth Bean |
| `missing_fact` | no birth/death/marriage date or place | John Cassel: death 1802, no birth |
| `unverified_claim` | fact with no record behind it | every uncited fact |
| `conflict` | competing values | 5 marriage dates for David Heebner & Maria Kriebel |
| `unlinked_relative` | a person in the tree who may be the answer | James Ahearn (1810–1899) vs Thomas Ahearn: same surname, same town, no link |

42 of the 117 people are dead ends today. Ranking: home person's direct line
first, then tractability (era and place with good record coverage in the
registry), then how many other questions an answer would unlock. A question is
**blocked** until its subject is baseline-complete.

## 3. Plan: the search ladder (AI proposes, human approves)

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

| Missing-link person | Own records | Relatives' records | Records holding 2+ family members | First thing to fetch |
|---|---|---|---|---|
| Thomas Ahearn (1846–1902), no parents | 0 | 4 | 0 | 1880 census cited twice on wife Alice McGee and son Patrick |
| Minerva E, no surname | 2 | 11 | 2 | two Kentucky death records on her children (mother's maiden name), 1850 census ×2 |
| Dorothy, no surname | 1 | 2 | 2 | the family history and Find a Grave memorial on Evan and Elizabeth Williams |
| Elizabeth Bean / John Brant, no parents | 1 | 9 | 1 | 1880 census and the church-and-town record on the Brant family |
| Mary Bridget Walsh, no parents | 2 | 6 | 2 | PA death certificates ×2 on the Boltons |

And the records that already hold the most family members: a compiled family
history holding 14 Cassels, a Pennsylvania will holding 7 Cassels, a family
history book holding 6 Lukens/Berkheimer/Rubican relatives, a 1930 census page
holding all 4 Peters. Those are where a missing Cassel, Lukens or Peters is found.

A plan is an ordered list of steps: layer, source (registry ID), a **typed
query** (`footprint_record`, `footprint_collection`, `subject_record`,
`household`, `name`, `surname_locality`), execution mode, what a hit would look
like, and the stop condition. The user approves the plan. Layer 0 steps are
fetches of records we already cite, so they are cheap, decisive, and usually
assisted (Ancestry) or automatic (FamilySearch, once approved).

Record type → era → place → source (layer 2) is a lookup, not a guess. The
registry's coverage column drives it (MA deaths 1841–1915 are free and indexed;
Irish civil registration starts 1864, so an 1810 birth means parish registers).

## 4. Search: execute and log every step, including failures

| Mode | Sources | Behaviour |
|---|---|---|
| auto | FamilySearch (after Innovator approval), WikiTree, loc.gov newspapers, NARA catalog, Open Archives, Wikidata, held archive | the system runs the query, archives raw responses, extracts personas |
| assisted | Ancestry, Find a Grave, Newspapers.com, Fold3, Archion | the system builds the exact search URL and tells the user what to look for; the user saves the result to `inbox/`; the system takes it from there |
| manual | county courthouses, Schwenkfelder Library, parish archives | the system produces a request letter or visit checklist |

Every execution is a **research log** row: query as actually run, source, date,
outcome (`found`, `none`, `blocked`, `error`), artifacts produced. "Searched the
1880 census of Worcester Township for Brant, none found" is evidence and stays.

## 5–7. Extract, match, review

Fetched records go through the existing evidence layer (extraction → personas).
Matching compares personas to the tree and produces proposals, but every
proposal now **answers a question**: "Is the James Ahearn in this 1870 household
Thomas's father?" Review happens on the person's screen, in the language of the
question. Accepting grows the baseline, which generates new questions.

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
## Schema additions this needs

```
review            (id, tree_id, entity_kind, entity_id, fact_ref, status, reviewed_by, reviewed_at, note)   -- status: undecided|accepted|rejected
research_question (id, tree_id, subject_person_id, kind, detail_json, status, priority, tractability, created_at, answered_by_proposal_id)
search_plan       (id, question_id, seq, layer, source_id, query_type, query_json, mode, expected, status, rationale)
                   query_type: footprint_record | footprint_collection | subject_record | household | name | surname_locality
search_log        (id, plan_step_id, executed_at, executed_by, query_json, source_id, outcome, artifacts_json, notes)
proposal.question_id
```

## What changes from today

- There is no hint queue. The 272 record citations and 49 media references that
  came with the Ancestry export are kept as data (in the import's extraction
  JSON and on the assertions) and surface only as Layer 0 footprint steps under
  the questions of the people they support.
- The footprint is computed from resolved data (accepted family links and
  citations), so it improves every time a review accepts something.
- Nothing is searched for a person until that person's baseline is reviewed.
- The first screen is the person: claims, evidence, verdicts, then their
  questions and the plan for each.
- Applying to the FamilySearch Innovator Program is the single step that turns
  most Layer 1–2 searches from assisted into automatic.
