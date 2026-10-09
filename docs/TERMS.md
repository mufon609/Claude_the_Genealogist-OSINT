# Terms and the decision model

## 0. Terms

**[rule.terms.1]** **Claim.** What the imported file or a searcher says without a record behind it.
An Undecided fact in a query carries basis `claim`; an Accepted one carries
`accepted`, a date or a place only as far as an accepted statement gives it
(`docs/RULE.md`, what of an event's value is accepted: a birth year the accepted census
gives is accepted, a day only the file gives is a claim); a citation's own detail carries `citation`, a checklist row's value
`row`, what a held record itself says (the name as written, the record it
links) `record`, and the search as it was run on a saved results page `run`.
Nothing is searched on claims alone. **[rule.terms.2]** Outside a query a statement that is not
accepted is undecided, whatever it rests on (`Catalog.basis`, a key fact's
basis); the file's word is the import's own statement, not rejected, and a
test that reads a link or a value "claimed or accepted" counts that statement
and accepted ones alone, never a sibling placement, an indexer's grouping, a
page anyone can edit or a link a withdrawn decision left: the route through a
stated relationship and a page's identity (`docs/RULE.md`), the queue's edge and the
overview's claimed parents and spouses (`docs/LOOP.md` §8, `docs/RESEARCH-CHECKLIST.md` §6b).
**[rule.terms.3]** The limits of one life (`docs/RULE.md`) and the living default's tiers
(`docs/DATA-ARCHITECTURE.md` §7 decision 3) count every family link the tree
holds that is not rejected.

**[rule.terms.4]** **Lead.** A piece of follow-up work about one person that the evidence produced
and the loop can act on: a record to fetch because a held record names it
(the parent's memorial linked from Raymond Earl Davidson's), a search to run
because an accepted fact makes it possible (the 1950 household at the address
the 1940 census gives), the record behind a row of a search results page that
fits the person the search was run for, a person named on an accepted record
who is not yet in the tree, the entries a census household holding the person
lacks (the head of the 1925 household Mary and Ruth Peters' pages make: its
collection's search, page by page, and the record behind each row of the
answer that could be the head, one at a time, `docs/HOUSEHOLDS.md`). A lead has a person, what to do, where to do it, and what produced it
(the record, fact or citation). Leads are the queue of work; every lead is a
plan step with its log, so what was tried and what it gave is never lost. A
lead closes when it is run, found or none, or when its gap has gone. Accepting
a document produces leads; running them consumes leads. The file's citations
are leads whose origin is the file.

**[rule.terms.5]** **Hint.** A document, or a row on a search page, that overlaps the person on
some of what identifies them but not on enough for the matcher to propose it or
the rule to accept it: the surname, the place and the period agree, but there
is no age, no full name, no stated relationship. A census whose form names
the head and counts the rest (`data/record-forms.csv`, 1790 to 1840); a tax list; a directory line; a search row
with a bare year; a newspaper hit before its text is read. Hints are kept on
the person with what agrees and what is missing, for research when the leads
run dry. A document already accepted as the person's can also stay a hint
while it still has work in it (the pre-1850 household accepted as the family's,
the children not yet identified). A hint never becomes a fact on its own;
research turns it into a lead or a match. A namesake a name search reached
(the name, the sex and a bare year agreeing, something disagreeing, nothing
more tying it to the person) and a persona nobody is created from (no full
name, or no word of kinship to a person accepted on the record) are hints too,
each saying why it is not a card (`docs/RULE.md`). A row of a search results page is
never proposed as a match, whatever it agrees on: its own record is the
document, so the row is a hint, or, when it fits the person the search was
run for (`docs/RULE.md`: more than a name and a year), a lead for that record. Hints are shown only on a person
whose baseline is reviewed, never as a feed.

**Which documents the rule may accept on its own.** This paragraph and `docs/RULE.md`
are the one full statement of the decision model and the standing rule.
**[rule.standing.1]** Imports and AI output arrive Undecided, and a conclusion needs an Accepted
assertion. A person accepts documents: the one decision is whether a record
is about this person, and yes accepts everything the record states. **[rule.standing.2]** The
standing rule (`docs/RULE.md`) takes that decision on the owner's behalf, recorded as
acting on their word and reversible, when the document agrees with what the
person already accepted, and everything the document states comes with it; a
disagreement with a value that rests on no accepted assertion is not a veto —
the record is still taken on its points, and the difference becomes a
conflict question, never a silent overwrite or a silent drop. **[rule.standing.3]** It may do so
only for document kinds that identify a person fully (the table below, kept as
each kind's standing in `data/evidence-classes.csv`), from sources nobody can
edit at will (registry tiers T1–T3: certificates, census, obituaries,
published works), and only counting accepted facts that themselves rest on
such a source or on the owner's own word, each a statement of the very date
or place it counts for (`docs/RULE.md`, "What the rule counts"). **[rule.own.1]** A person's own decision
on a statement (`docs/RULE.md`) is never undone by the rule, by a record read again or by
a decision carried from another copy of the record: the statement keeps the
state the person gave it. **[rule.editable.1]** A page anyone can edit (T4: Find a
Grave, member trees) identifies a person but never builds their facts:
accepting it, by the owner or by the rule, writes the persona link, and every
fact the page types is written as an undecided assertion, what the page says,
never accepted and never a ground the rule stands on, one that differs from a primary record the tree
holds a contradiction of it and never a veto; **[rule.editable.2]** the rule takes such an identity when the name agrees and
at least three of birth date to the day, death date to the day, burial place,
and a stated parent or spouse who is that relative in the tree agree with the
tree, claimed or accepted. **[rule.editable.3]** A family membership such a page states is created
where the tree lacks it, with an undecided assertion, the way a sibling
placement already is, for a relative accepted on the same page or one whose
given name, surname and birth year fit exactly one person of the tree (the
names as the matcher agrees them, a surname written the same or a spelling
variant of it, never one letter apart; `docs/RULE.md`); that
relative's persona is then traced to that person with an undecided link, and
a person who rejected that persona is no fit. **[rule.editable.4]** The relatives a memorial lists
are leads, never cards: the matcher proposes none of them, and each is a fetch
step for their own memorial (`docs/PLAN-AND-SEARCH.md` §3). **[rule.editable.5]** A person whose accepted facts rest on T4
alone is marked so on their card until a trusted record about them is
accepted. **[rule.editable.6]** A memorial's gravestone photographs are primary sources (T1): each
is a fetch step, saved in the owner's browser one at a time, archived under
the registry's gravestone-photograph row and read by the transcription path
into a card like any other image. **[rule.standing.4]** Every other kind is a hint until a person
reads it, and anything less certain than the rule is a card for the owner.
The starting list, to be refined as records are met:

| Document | What it gives | Standing |
|---|---|---|
| Federal or state census 1850 on | full names and ages; relationships from 1880 | automated |
| Federal census 1790–1840 | the head's name, the rest counted | hint |
| Find a Grave memorial | full name, dates, cemetery, linked family, gravestone photographs | the identity by the rule when the name and three of birth day, death day, burial place, a stated parent or spouse agree; each relative it lists a lead, never a card; a membership it states created where the tree lacks it for a listed relative who fits exactly one person by name and birth year, undecided like its facts; each gravestone photograph a fetch step |
| Death, birth, marriage certificate or index | full name, dates, parents or spouse | automated |
| Social Security index, draft cards, service records (an Army enlistment), veterans' files and gravesites | full name, exact birth date or year | automated |
| Naturalization petition, declaration or index | full name, birth date and place, residence, spouse | automated |
| Church register entry | names and dates when the register keeps them | automated when dated and the parents are named; hint otherwise |
| Obituary, newspaper hit | free text | hint until the text is read (by hand or by the model); then the named survivors decide: automated for the person it names once a stated relative it names is a relative the tree already links on trusted evidence, never on dates or places alone |
| Will, probate, land, tax, directory | names, no ages | hint |
| Compiled genealogy, family Bible | lineage, no proof | hint, never proof |
| A row on a search results page | name, years, place | never a card: a hint on the page, its own record is the document; a row that fits the person the search was run for is a lead for that record |

## 1. Baseline: what we know and have approved

An imported tree is a set of **claims**, not knowledge. The Ahearn import, as
imported on 5 September 2026, had 232 facts with no citation at all and 1,122
citations that point at records we did not hold. None of that is a baseline;
the live checklist says where the review stands now.

- A person accepts documents, not facts: the decision on a held record is
  whether it is about this person, and every fact the record states comes with
  it (`docs/RULE.md`). **[rule.terms.6]** Key facts: name, sex, birth, death, parents, spouses, children;
  each is **Accepted**, **Rejected** or **Undecided** according to the documents
  behind it. A person is *baseline-complete* when no key fact is Undecided. **[rule.terms.7]** A
  person may accept a fact on their own knowledge (a vouch): the fact then
  traces to the tree file as the archived claim, the acceptance is the
  person's, it is Accepted like any other, and the record fetch still runs. The
  standing rule (§0, `docs/RULE.md`) accepts on the person's behalf a document that
  agrees with what they already accepted.
- **[rule.terms.8]** Only Accepted facts feed searches. An Undecided fact is a claim and is
  labelled as such in every query: every query field is `{value, basis}` with
  basis `accepted` or `claim`, a date or a place `accepted` only as far as an
  accepted statement gives the value the field carries (`docs/RULE.md`). A Rejected fact is left out, and a relative
  whose family link is Rejected is not a relative to the footprint or the
  checklist.
- Review is person-centred: one person, their claims, the records behind each,
  verdict per fact. This is the first screen.

## 2. Questions: generated from gaps in the baseline

**[rule.terms.9]** Questions are always about a person. They are generated, not typed:

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
| `identity` | a family link or an accepted statement beyond the limits of one life (`docs/RULE.md`) | Joe Davidson, born 1925, a child of Lena Howard Bell, who died in 1918 |

42 of the 117 people in the file as imported are dead ends. Ranking: home person's direct line
first, then tractability (era and place with good record coverage in the
registry), then how many other questions an answer would unlock. **[rule.terms.10]** Until its subject is
baseline-complete (no key fact Undecided) a question gets no search steps and
no footprint or unlinked persons; only fetch steps for records the
tree already cites exist, because the review needs those records. **[rule.terms.11]** The duplicate
check and the limits of one life run for every person, reviewed or not: a
second entry or an impossible link is settled before anything is built on it.

**[rule.merge.1]** A duplicate is settled by merging it into the person it duplicates
(`tools/conclude.py merge`), which answers the `duplicate_person` question on
both sides. Everything the duplicate holds moves to the kept person: its
persona links, statements, event and family memberships, name aliases, plan
steps, runs and questions. **[rule.merge.2]** Where the kept person already holds the same thing,
the duplicate's is folded onto theirs: a membership of the same family and role
gives its statements to the kept person's; a link to the same persona leaves
the kept person's decision standing, and gives its own only where the kept
person's link is undecided, which is no decision; an alias of the same words
leaves the kept person's; a question of the same key, in any status, is the
kept person's question asked twice, and the duplicate's closes, where open, as
answered by the merge. **[rule.merge.3]** The duplicate's row stays for the audit trail, out of
every listing, holding nothing open and no decision. The merge run again on a
merged pair completes what an older merge left on the duplicate.
