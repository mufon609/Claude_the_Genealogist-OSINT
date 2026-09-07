# Per-person research checklist and the auto-search that comes from it

Opening a person's profile answers three questions in order, on one screen:

1. **What do we know and have Accepted?** (the search foundation)
2. **Which records should exist for this person, and which do we hold?** (the checklist)
3. **What is missing, and what search fills it?** (the gaps, pre-filled, ready to run)

## 1. The fact checklist (what a finished profile has)

| Fact | Detail we want | Typical multi-person record that gives it |
|---|---|---|
| Name | given, surname, variants, maiden name | census, marriage, church register |
| Sex | | any |
| Birth | date, place | census (year/state), church baptism, family Bible |
| Parents | father, mother with maiden name | census as child, marriage record, baptism, will of parent |
| Siblings | | census as child, parent's will, obituary |
| Marriage(s) | date, place, spouse, spouse's parents | marriage record, church register |
| Children | | census, church baptisms, will, obituary |
| Residence trail | one entry per census year alive | census, directories, tax lists |
| Occupation | | census, directories, draft cards |
| Migration | origin, arrival, naturalization | passenger list (family group), naturalization |
| Military | service, draft | draft card (individual), pension file (family) |
| Death | date, place, cause | death record, obituary, gravestone |
| Burial | cemetery, plot | cemetery record, Find a Grave (family plot) |
| Probate | will, heirs | probate file |

## 2. The record checklist: multi-person records first

**Group A: records that hold several family members.** One fetch fills facts for
the whole household and proves relationships. These are worked first.

| Record | Who is on it | What it settles | Windows (this tree's places) | Registry |
|---|---|---|---|---|
| Federal census household | everyone in the house | ages, birthplaces, relationships (1880+), immigration year, occupation | 1790–1950 every 10 years; 1890 lost; **before 1850 only the head is named** | D01, D03 |
| State census | household | same, off-decade | NY 1855–1925, MA 1855/1865 | C08 |
| Marriage record | bride, groom, both sets of parents, witnesses | parents, maiden name, ages, birthplaces | MA 1841+, PA county 1885+/state 1906+, KY/TN county books | C03, C05–C09 |
| Church register (baptism, marriage, burial) | child + parents + sponsors; family registers | parents, dates, religion, godparents (often kin) | Schwenkfelder 1734+, Mennonite, Presbyterian, Catholic (Ireland, Cologne), Dutch Reformed | I01–I09 |
| Will / probate | testator + every heir | children, spouse, sometimes grandchildren; pre-1850 the best relationship proof | PA 1683+, MA 1635+ | J03 |
| Obituary | deceased + survivors + predeceased | children, siblings, married names of daughters | 1800s–, dense after 1900 | H01–H06 |
| Cemetery / family plot | the plot | spouse, children, in-laws buried together | any | E01–E04 |
| Passenger list / emigration list | the travelling family | origin, ages, who came together | NY 1820–1957; Schwenkfelder ships 1734 | G01, G04 |
| Pension file | veteran, widow, children | marriage date/place, children's births | Rev War, Civil War | F03, F04 |
| Land deed | grantor, spouse (dower), heirs | spouse, heirs | PA 1682+ | J01, J02 |
| City directory / tax list | adults of a household | residence, occupation, adult sons | 1822–1995 | K01, J04 |
| Family Bible / compiled genealogy | whole lineage | hints for everything; **never proof** | | L01–L03, I01 |

**Group B: records about one person.** Filled in after Group A, to complete
that person's own facts. Many still *name* relatives (B1); some do not (B2).

| Record | Names relatives? | Settles | Windows | Registry |
|---|---|---|---|---|
| Death certificate | B1: parents, informant, spouse | death date/place/cause, birth date/place, burial | PA 1906+, MA 1841+, KY 1911+, TN 1908+, NJ 1848+ | C03, C05–C10 |
| Birth certificate | B1: parents | birth date/place | PA 1906+, MA 1841+ | C03, C05 |
| Social Security application (SS-5) | B1: parents | birth, parents | 1936+ | C02 |
| Naturalization | B1: spouse/children sometimes | birthplace, arrival, origin | 1798+ | G02 |
| Draft card | B1: next of kin | exact birth date/place, residence, employer | WWI (men b. 1872–1900), WWII (men b. 1877–1927) | F02 |
| Military service record | B2 | service | only when a military event is already known | F01–F03 |

Gravestones are covered by the Group A cemetery row (the same source names the
family plot). Directory entries are the Group A directory row. Voter
registration (C11) is living-person data and is never a checklist row.

Every row is **gated by era, place and sex**, taken from the person's Accepted
facts and the registry's coverage column. A man born 1880 gets the WWI and
WWII draft-card rows; a woman born 1815 does not. A person born 1696 in Silesia
gets no US census rows and instead gets the 1734 ship list, the Berthelsdorf
and Harpersdorf registers, and Philadelphia County probate (Montgomery County
did not exist until 1784). A pre-1850 census row is still a household record,
but the expectation is "counted under the head", not "named".

## 3. From checklist to gaps to search tasks (automatic on opening a profile)

For each checklist row: **held** (archived), **cited but not held** (the old
tree pointed at it), **missing**, or **not applicable**. A census page is held
for every household member cited on it: the citation's own details (collection,
year, census place, enumeration district, sheet) name the page, whichever
member's record id it was archived under. Everything that is not held is a gap,
and every gap has a pre-built search step:

| Gap | Pre-built search |
|---|---|
| census year missing | household query: surname + Accepted residence place + ±2 years on Accepted birth; expect spouse/children names on the page |
| marriage record missing | couple query: both names, Accepted birth years, marriage place = residence at first child's birth if no better; hit names both sets of parents |
| obituary missing | name + death date ±1 week + death place; newspaper sources for that place |
| will/probate missing | name + death place county + death year..+5 |
| cited but not held | fetch step: the citation's locator (APID) and its own details, re-targeted to the free holder of the collection; `blocked` when the collection has none |
| death/birth record missing | individual query gated by the jurisdiction's window |
| parents unknown (dead end) | footprint first (records already on relatives), then Group A rows for the person as a child |

Ranking inside the task list: Group A before Group B; cited-not-held before
missing (it is a fetch, not a search); records that would answer the most open
facts first. The list is the person's research task. It appears when the profile
opens, and it is empty when the person is done.

## 4. The search foundation and the user's controls

The foundation is the set of Accepted facts, shown as fields with checkboxes:

```
Search foundation (Accepted)                       Task list
 Given   Abram C.        variants: Abram, Abraham        ▶ Go (run all checked)
 Surname Brant           variants: Brandt                  A  [ ] 1900 census household        Search
 Birth   1880 ±2         Worcester Twp, Montgomery PA       A  [ ] 1880 census household        Search
 Death   1961            Pottstown PA                       A  [ ] marriage record, Lukens      Search
 Spouse  Charlotte Lukens                                   A  [ ] obituary 1961                 Search
 Parents Abraham B. Brant / Sarah Cassel                    A  [ ] will / probate 1961           Search
                                                            B  [ ] WWI draft card               Search
                                                            B  [ ] WWII draft card              Search
 Selected step: 1900 census household
 [x] given Abram C   [x] surname Brant   [x] birth 1880 ±2   [ ] death 1961   revise: surname → Brandt
```

- **Go** runs every checked task with its fields as rendered.
- **Uncheck a field** on a step to keep a doubtful fact out of that query (the
  fact stays Undecided/Accepted in the tree; this only affects the search).
- **Revise** a field on a step for the search only: alternate spelling, wider
  year range, neighbouring county. Include and revise are saved on the step
  (`search_plan.revisions_json`), never as facts; useful revisions become aliases.
- **Click one gap → Search** runs that single task, seeded with the same
  foundation. One fact, not ten.
- Results come back as proposals tied to that gap ("this 1900 census page
  answers *1900 census household*"). The checklist row reads held once its
  record is in the archive: a done fetch step for that row with an archived
  record in its log, or an archived page that a citation on the row names; the
  fact behind it is still decided by a person.

Every run, including "nothing found", is written to the research log with the
fields exactly as rendered after include and revise, so the same search is not
repeated blindly and negative results count.

## 5. Real examples (computed from the catalog, before any review)

**Abram C. Brant (1880–1961)** — foundation: both parents, spouse, birth and
death from certificates. Group A gaps: 1880, 1900, 1930, 1940, 1950 census
households; marriage record (dated in the tree, no record); obituary; probate.
Group B gaps: WWI and WWII draft cards, Social Security. Held or cited: 1910
and 1920 census, birth and death certificates, Find a Grave, church record.
Five of seven censuses are missing on a well-sourced man.

**Minerva E (1815–aft 1900), no surname, no parents** — foundation is thin:
1850 and 1870 households of Robert Powell McCrary, birth Feb 1815 Tennessee.
Every other Group A row is a gap: 1860, 1880, 1900 census; marriage record
(the one that gives her surname); obituary; probate; cemetery. Search order:
footprint first (the Kentucky death certificates already cited on her children
name their mother), then the marriage record for Robert Powell McCrary in
Tennessee/Kentucky about 1835–1845, then the 1880/1900 households.

**Thomas Ahearn (1846–1902)** — gaps: 1850 and 1860 households (as a child in
James Ahearn's house: this is where his parents are proved), 1900 census,
marriage record, obituary, cemetery, birth record, Civil War draft 1863.

**David St Johns Heebner (1696–1784)** — no US census applies. His rows are
the 1734 Schwenkfelder ship list, Berthelsdorf/Görlitz registers 1726–1734,
Harpersdorf (Silesia) baptisms, Philadelphia County probate 1784, PA land
warrants, and the Schwenkfelder Genealogical Record. Migration and church
agents, not census.

## 6. The workflow on screen, and what the clean UIs do right

Prior art worth naming: **GenSmarts** and **Legacy's Research Guidance** did
exactly this in the 2000s: compare a person's facts to record availability by
place and time, and produce a to-do list. **Ancestry's search form** is
pre-filled from the profile with per-field "exact" toggles and ±year ranges;
that is the foundation panel. **FamilySearch's Research Help** panel puts
record hints, data problems and research suggestions in one place per person.
**RootsMagic's research log** records every search and its result.

What those UIs got wrong: they show the queue instead of the person, and they
show hints before the baseline is trusted. Neither happens here.

The flow is linear and stays on one person:

```
 open person ─► FOUNDATION (Accepted facts)
             ─► CHECKLIST  (Group A rows, then Group B; held / cited / missing)
             ─► TASKS      (one per gap; include/revise its fields on the step; Go, or Search one)
             ─► RESULTS    (proposals under the gap they answer)
             ─► REVIEW     (Accept / Reject / Undecided) ─► foundation grows ─► repeat
```

Layout rules that keep it clean:
- One person per screen. Family members are links, not panels; a spouse link
  carries the marriage year and, for a divorced couple, a broken heart with
  the divorce date, so the pair reads as linked whatever the surnames say.
- Three regions only: foundation (top), checklist with tasks (middle), results
  for the task you clicked (bottom or side). No tabs on the first screen.
- Group A rows are visually first and marked as household records; Group B is
  collapsed until Group A is done or the user opens it.
- Every row shows one of four words: held, cited, missing, n/a. No percentages.
- The search form is never blank: a step's fields are always the foundation,
  and every field is one click to exclude on that step.
- Anything the AI produced is Undecided and lives under the gap it answers.

## 6a. The generator

`tools/checklist.py "<person>"` produces everything above for one person from
the catalog, read-only: the foundation with each field marked `accepted` or
`claim`, the generated questions, the Group A and Group B rows with
held / cited / missing / n/a, the relative a citation sits on when it is not on
the person, and the pre-built search step per gap with its execution mode per
source (`auto`, `assisted`, `awaiting approval`, or `fetch` for a cited record,
`blocked` for one with no free holder).
`--json` gives the machine form; `--all` gives one line per person. A real
citation always beats an era rule; the row is then marked with the rule it
falls outside of. Every query field is `{value, basis}`: basis `accepted` or
`claim` for a fact about the person, `row` for a value the checklist row sets
(a census year), `citation` for a detail the citation itself carries (a fetch
step's fields); a Rejected fact is left out. Before the baseline is reviewed
the generator emits only fetch steps for cited records: no search steps, no
footprint, no duplicate or unlinked persons.

## 6b. The screen as built

`app/person/server.py` serves it at http://127.0.0.1:8765/ (stdlib only,
localhost only). The entry page is the tree overview, whose goal in one
sentence: the overview shows the family as people cards; a badge on a card
says how many documents wait for a decision and what can run next; opening a
card is the person screen, where the waiting documents are decided first and
everything else follows from them. The cards are laid out from the home person
(`tools/tree.py home`) upward, one row per generation of ancestors, a card's
parents above it, following a parents link only where the owner accepted it:
the tree ends at the last accepted link, a card at the edge names the parents
the file claims as a claim, and a link resting on an editable source alone
says so. The rest of the file's people are a count, with those that have a
document waiting folded away; nobody enters the tree until a document the
owner accepts places them, and if a link falls, everything beyond it leaves
the page. A badge is a plain count of what waits:
documents to decide, steps that run on their own, steps that need a hand,
conflicts, and "rests on sources anyone can edit" when every accepted fact of
the person comes from a T4 source; a person with every key fact accepted and
nothing waiting says so.
The
person page puts the documents first: every record waiting for a decision
about this person as its card (the highlight, the record with holder,
collection, identity and tier, the tree's claim, each field as agrees,
disagrees or absent, the relationships stated, what adding it closes), with
Add and Ignore; then what is known (key facts with the documents they rest
on, then every other fact, the per-fact buttons kept for the owner's own
knowledge and for undoing a claim); then what the plan does next (questions,
the footprint, Group A, Group B collapsed) with a selected panel showing the
step or the citations behind the row clicked, each with a link to the free holder the
record is fetched from (the memorial page itself for Find a Grave; for a
FamilySearch step the collection's own search prefilled from the citation's
details, for a National Archives 1950 step the site's name search, the
collection page for a citation without a step) or to Ancestry when the
collection has no free holder and the step is blocked. Every fact of the
person is decidable under the same three states: the seven key facts first,
then every other event or attribute the person has (burial, residences,
occupation, an inscription), each with its evidence; a fact a held record
states that the tree had no event for appears once a match is accepted, created
from the record's fact with its Accepted assertion. Deciding a fact sets every assertion that supports it and writes an
audit row. Accept sets Accepted only on the assertions whose evidence is
visible: the tree owner's uncited claim and citations whose record is held;
a citation to a record not yet fetched stays Undecided until the fetch. When
no evidence behind a fact is visible, Accept is the person's own knowledge: a
vouch, one Accepted assertion by the person on the tree file's persona, so
the fact traces to the file as the archived claim and the acceptance to the
person, the cited records still get fetched, and held evidence later sits
beside the vouch. A
"Generate plan" button materializes the questions and steps into the catalog;
every checklist row and footprint record then shows its step, its log, and
three ways to log a run: nothing found, blocked, or found with a file picked
from `inbox/`, which archives the file (bytes already in the archive are
linked, not copied), files a copy under the tree, and records it on the step's
log and on every other step the record's own identity fulfils (the memorial id
or ark read from the file), then parses and matches the page; the same path
`tools/attach_inbox.py` runs over the whole inbox. No assertion is written by
the attach; that comes from extraction and review. A fact-level question has one Dismiss control, and a dismissed
question stays closed when the plan is refreshed. Name and sex share the
person-level citations from the import, so deciding one decides the other,
and accepting a person's children accepts the same link seen from the child's
side as parents. Include and revise live on the step: a search step lists its
fields with a checkbox and a revise box, saved on the step, and every logged
run records the fields as rendered, each with its basis. Until the baseline
is reviewed the page says in one line what review unlocks (searches, the
family footprint, unlinked persons) and that fetching cited records is open. A held row's
panel also shows each record its steps archived: the file, its extractions
with personas, facts and relations, and, when the record has no persona yet,
a form to transcribe one person at a time (name, role, sex, age, birth, death,
residence, a relation to a persona already on the record); the model reads an
image the same way, as extractor `llm:<model>`. Under each
persona sit the matcher's proposals on the record (a record cited on several
relatives is fetched for all of them, and each proposal names the person it
concerns), each as the decision card, with Add / Ignore on a persona match or a
new person, Ignore asking why so the reason is kept on the decision and shown
on the card afterwards; a decision answers in one line with what it made and closed
(the link, the questions answered, the rows this record fulfils) and what the
plan does next (the facts now carrying held evidence to accept, the proposals
still open on the record, the steps still planned). A held row
opens its record through the citation's archived artifact as well as through
a step. Accepting a persona
on a held record as this person accepts everything the record states about
them (`docs/RESEARCH-WORKFLOW.md` §5–7); the decision's answer lists what came
in and any conflict it raised. A proposal the standing rule accepted shows
"accepted by rule" with the reason and a Reject control; one the rule took
back (`tools/conclude.py reconsider`) is a card again with the rule's reason. An assisted search step whose source's search the tool can build
(Find a Grave) shows that link, built from the foundation fields; the results
page saved into `inbox/` comes back as the candidate card on the step's
record, every row with its fields as agrees, disagrees or absent
(`docs/RESEARCH-WORKFLOW.md` §4). An auto step runs through its connector
from `tools/run_step.py`; the screen has no run control. Assisted sources are
worked by opening the link, searching with the step's fields, and logging the
result.

**The decision card.** Every proposal put to the owner, on the screen and from
`tools/cards.py`, is one card with the same parts in the same order: a one-line
highlight of what the record is and the links it makes; the person and the
fact or link, with the file's claim; the record with its holder, collection,
own identity and trust tier; the primary document, as the archived copy and the
holder's page; what the record says field by field against the claim, each
field agrees, disagrees or absent (a date and a place are two fields); the
relationships it states and how each persona on the record stands (accepted
as, proposed as, a new person, no proposal); what accepting closes, from the
step's question when it has one and from the checklist row otherwise; anything
odd. The same card, with the same parts, when the owner decides on a source.
No scores, and no count dressed as one.

## 7. What this maps to in the schema

- a checklist row = `search_plan.row_key` (`"<record>:<instance>"`); a row is
  a unit of work, not a question, so `research_question` holds only the
  fact-level kinds and a step carries `question_id` only when it answers one
  (a footprint record under missing parents);
- a cited row = one `fetch` step per citation with `locator_source_id` (the
  free holder, or B02 when there is none and the mode is `blocked`),
  `locator_kind`, `locator_value`, `collection_id`, `on_json` (the relatives
  it sits on) and `query_json` holding the citation's own details with basis
  `citation`; a missing row = one `search` step with `query_json` holding the
  foundation fields as `{value, basis}` and one `mode`;
- the checkbox and revision state = `search_plan.revisions_json` on the step,
  not on the facts;
- held = the row's record is in the archive: a done step with an archived
  artifact in its `search_log`, or an artifact archived under the citation's
  record id or under another id naming the same census page;
- results = `proposal.question_id` pointing at the question the record
  answers.
