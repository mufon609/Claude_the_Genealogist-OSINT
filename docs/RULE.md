# The rule

## 5–7. Extract, match, review

Fetched records go through the evidence layer (extraction → personas). A
record page saved as HTML is parsed on arrival by `tools/extract.py`, which
reads the page's kind from the page itself: a Find a Grave memorial goes to
extractor `rule:findagrave-memorial@0.4.0` (the memorial's name without the
badges beside it, dates,
places, plot, inscription and biography as written and memorial id on one
persona, one persona per family member in the page's own label word with a relation to the
memorial's subject, and in the parsed page every photograph with the type the
page gives it; verified on a real memorial), a Find a Grave search
results page to `rule:findagrave-search@0.1.0` (one persona per row, the
memorial id and URL as its identity), a FamilySearch record page to
`rule:familysearch-record@0.8.1` (one persona per person the page names, in
the page's own role word, a relative given one name only (Thomas, Davidson)
included with the name as written, a row with no name in it (", [1918]") or
the index's UNKNOWN none; one fact per field as written, a member's own
details read as the subject's fields are, its Event Date and Event Place the
record's own event; every value a field
keeps collapsed beneath the one it shows, FamilySearch's edit history, read
too, as a fact of its own whose region marks it alternate, unless it says the
same as the shown value, and beneath an Event Date that shows a time of day
the date it keeps is the event's own date, the time a fact under its own
label; as stated relations (`computed: false` in the region), what the page
shows the record stating, from the side the record states it: each person's
relationship to the household's head as the record's own column states it,
where the page shows that column (the subject's own field, a member's own
details) and who the head is, and, on a census page whose own person is the
head (its own Relationship to Head of Household field says Head), each
relatives-table row that carries a relationship word, the table being worded
from the head's side, the census's own column (a row with a blank cell states
nothing); a parent a field names (Father's Name) toward the subject; on a record of one event (a birth, a marriage, a death, a
naturalization, an obituary), the relatives table's rows for the subject's
parents, spouse and children, the people the record names in those roles, and
on an obituary its brothers and sisters, each survivor named in their
relationship to the deceased; on a marriage record, the one the table files as
the subject's father- or mother-in-law as a parent of the subject's spouse on
the page, the record naming each party's parents (the bride's father is hers);
and on a page whose leading line says "Mentioned in the Record of" another
person, the page's own person being that person's relative, that person's row
alone; a draft registration's Event Date and Event Place a Residence on that
date (the card is filed where the registrant lived); the one person its page
lists under the registrant's Extended Family carries no word, and none is
written for them.
Every other grouping FamilySearch's relatives tables make around the
page's own person (on a census page whose own person is not the head, every
one, since a census states only the relationship to the head and a member's row
gives FamilySearch's word, not the column, and on the head's page a row with a
blank cell; a sibling of anyone but an obituary's deceased, a grandparent, an
in-law; on a relative's page every row but the record's subject's, a mother's
husband among them, a death record naming the deceased's father and mother and
no marriage between them; the couple of the parents listed) is written too, marked
`computed: true`, the site's inference and not the record's statement; the
relatives its fields name as personas; verified on real pages), an Ancestry
index page to `rule:ancestry-index@0.1.0` (built to
Ancestry's page structure, not yet verified on a real page), a FamilySearch search results page to
`rule:familysearch-search@0.1.0` (one persona per row with the record's ark as
its identity), an AAD enlistment results page to `rule:aad-search@0.1.0` and a
full enlistment record to `rule:aad-enlistment@0.1.0`, a 1950 census
site response to `rule:nara-1950-schedule@0.1.0`, a loc.gov OCR response
to `rule:loc-gov-ocr@0.1.0`, the Archive's search inside an item to
`rule:ia-search-inside@0.1.0` and a WikiTree profile with its relatives to
`rule:wikitree-profile@0.1.0`; a page or response no parser claims gets a
failed extraction by `rule:extract@0.1.0` and is reported, its run on the step
logged `unread` (`docs/PLAN-AND-SEARCH.md` §4).
The raw parsed page is in
`extraction.structured_json`. Re-running an
extractor, at any version, supersedes its earlier extraction (`tools/extract.py
--stale` re-reads every page an older version of its parser read, after a
parser changes) and rejects that
extraction's undecided proposals with the note `superseded`; a persona the
earlier extraction had decided carries its decision to the same person on the
page in the new extraction, found by its record id (an ark, a memorial id, an
index's number), else by its role, its row and its name (the decision was about
that entry of the record, whose bytes have not changed; another row of the same
name never takes it, and a persona the new extraction does not find that way
carries only when its name and role are on one persona in each extraction), an
accepted one asserting the new facts the record gives and nothing it already
asserted, a statement a person decided keeping the state they gave it, and the matcher
proposes the rest again. Once for the reading, never once per persona, the
people whose evidence it changed (each person an accepted decision carried to,
everyone whose family a family link that wrote reaches, as a decision's links
reach them, below, and the same of a decision on another copy of the record)
have their plans regenerated, a question
the regeneration closes answered by the decision carried to them, and the rule
goes over their conflicts and their cards are matched again, as a decision does
(`conclude.settle_carried`, below). The matcher is versioned
the same way (`rule:matcher` at the version `tools/match.py` names, raised
with any change to what fits). A card is matched again whenever the evidence
has passed it by (`tools/conclude.py` rematch): one an older matcher wrote; one
left on a reading the page's re-read superseded (a decision the rule took there
and withdrew afterwards, which a re-read, closing only the cards undecided at
the time, never reached); and one the matcher, on the person's evidence as it
now stands, would no longer put to that person (the persona a hint for them
now, `docs/TERMS.md` §0, waiting on the record's own person, or another person fitting). Each
closes with the note `superseded`, as a re-read closes the cards of the reading
it supersedes, and its record's current reading is matched again: the matcher
proposes the persona afresh as it stands and the rule takes what it takes, so a
person the rule created and took back comes back as a card for that person,
never a second one, judged by the creation's own terms (the standing rule,
below), and a persona that is a hint now leaves the cards and stays
a hint on the page. A withdrawn decision closed on a superseded reading leaves
what the withdrawal took back undecided (its statements and its name alias):
closing a card judges nothing it stated, so a family membership resting on it
stays the claim it was, and the card its current reading gets carries the
record's facts again: accepting that card makes them stand. A
card the matcher still puts to the same person keeps its id and takes the
matcher's words, as they now read, as its rationale (one the rule took and
withdrew keeps the words written before the record was taken: its own
statements stand on the person now). Every decision that changes a person's
evidence does this for that person's cards as it is taken (a card, a key fact,
one statement, a place's words, a conflict resolved or reopened, a statement
placed, a link or a divorce on the owner's word, a merge, a decision carried to
a record's new reading or to another copy of it), and
`tools/conclude.py reconsider` does it for every card, and again for the people
whose date or place its own pass over the conflicts kept or gave back. A record
image gets no
automatic extraction: it is read one person per row through the screen's
transcription path. The model reads it by default (extractor `llm:<model>`,
layer 3 like any extraction, `docs/DATA-ARCHITECTURE.md` §1), each persona in
the record's own role word with its facts as written, a birth calculated from
an age and the record's year (qualifier `calculated`, so the matcher allows
two years), its relation to the head, and the line or region it stands on in
the image; a person reads it (extractor `human:<user>`) only on serious doubt,
stated as the reason. An index page whose own name is a slip — an indexer's
transposition or misreading, not a fresh fact — goes through the same path to
the same default. What the reading proposes is decided like any record, the
rule taking it exactly as it takes a parsed record, never by who did the
reading. That is the path for every image until an OCR or HTR extractor
exists.

What a reader of an image writes is one text, `app/person/read_record.md`, and
a reading records what read it. A model's reading names its model id (refused
without one) and the version the id carries, a person's reading names the user,
and the extractor row of either carries as its prompt hash the sha256 of that
file as it stood at the reading. The reader is the actor of everything the
reading writes, the matcher's proposals included. Every persona carries a
`line` or a `bbox` on the image (refused without one, the refusal naming the
persona), and the extraction keeps what the image is, `image_is`: `record`, the
record made at the event, or `index`, an index or abstract of it. The number the
record gives itself (a certificate's state file number) is written as `number` on
the persona it is the record of, and joins the image to another copy giving the
same number of the same year (a state index's line). A refused reading writes
nothing.

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
accepted person's relatives, claims included, and against every person of the
tree the fitting check below reaches; a persona with a full name whom the record
relates to the accepted person by a word of kinship and that fits nobody is
proposed as a new person then, never before. A word of kinship is a child, a
parent, a spouse or a sibling, or a word the record files under another heading
that names a relative (a grandson, a daughter-in-law, a half brother, a maternal
grandmother). Nobody is created from any other persona, and none of them is a
card: a persona with no full name (a surname alone, a given name alone, a given
name and an initial), or one the record relates to the accepted person only by a
word that is no kinship (an informant, an officiant, a pastor filed as "other
relative"), by the heading "other" with no word, or by no word at all, stays a
hint on the page that says why. So
a household or a profile is decided one person after another, each on the
record's own words about the last. The comparison
is on name, sex, birth and death dates, birth, burial and death place, each
against the person's event of its type as the tree shows it (the one standing on
the strongest ground, never one left with no statement but rejected ones, which
is none of the person's events: below), the
residence the record gives against every place the tree knows the person at,
and the relationships the record states; a persona fits only on more than a
name and a year (a place, a death, a full date or a stated relationship); a census index's estimated birth year and a
household member's age become a calculated birth year the matcher allows two
years on. Two dates that both give a month, neither marked about, estimated or calculated, agree only in the same month:
June 1901 and July 1901 disagree, in the same year, as 26 June 1901 and July 1901 do, and a month against a full date of it
agrees to the month and says the record gives only the month; where either is marked about, estimated or calculated the
months are not compared (such a date agrees within two years), and the rationale says so and names the side so marked
(about June 1901 against July 1901), never that a side gives only a year. As a bare year against a full date agrees on the year only and says so (`docs/PLAN-AND-SEARCH.md` §4), a place agrees on the part it
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
William, Charley for Charles) and across a one-letter slip in a longer name.
Given names that both carry a middle name or initial disagree when those
differ (John A. against John D.): the persona never fits, it is a card for the
owner with the middle name named as the disagreement, and once the record is
accepted the difference is a `conflict` question on the person. A middle name
agrees as an initial, a short form or a spelling variant of the tree's (Sarah
for Sara, Micheal for Michael), and an initial standing for another surname
the person holds is no middle name to compare (Helen B. for a woman born
Brant); a middle name on one side only is no difference. A
wife written under her husband's surname is not a surname disagreement, nor is
any woman's the record otherwise shows married: a daughter or sister carrying
another surname beside a son-in-law or brother-in-law of that surname on the
same record, or written "Mrs." Only a woman's: a persona the record says is
male, or put to a person the tree holds as male, is never read so (a man whose
record names his wife, or names a son-in-law of the surname it writes him under);
where neither the record nor the tree gives the sex, the record's own words
(a wife, a daughter or a sister, "Mrs.") are what make her the woman read so.
The name as written that an accepted record leaves as an alias is read the same
way: it is a married name only where she is read so, never a man's
(`conclude.shown_married`). A
persona of the same name as a candidate that disagrees on something else is
proposed as that candidate when more than the name ties it to them, with the
disagreement in its rationale, so the owner sees the likely identity and the
difference together; the rule never takes such a proposal, and when another
persona on the same page fits that candidate, or is already accepted as them,
the near one is not proposed at all: one decision is put once, and the near
persona stays a hint on the page. A namesake is not proposed either: a persona
on a record reached by a name search alone (a search step's own result, or the
record behind a row of a results page), whose only agreement with the candidate
is the name, the sex and at most a year of birth the record gives bare, and that
disagrees on anything, stays a hint on the page that says so, naming what of
them agrees (a year of birth only where it does). More than the
name ties a persona to the person, and it is proposed as above: a record the
file cites, one a held record links or one attached on the owner's word (none
of them reached by a name search alone); a relationship the record states to a
persona accepted on it, fitting a person, or carrying a card; a full date, or a
month of birth the record gives that agrees to the month; a place that agrees at
any level.
A persona of the same name that disagrees on both its dates is not a likely
identity either: it stays a hint on the page, never a card. Nor is one born
more than the matcher's window of three years from the candidate: another
generation of the same name (a daughter named for her mother, a son for his
father) is never put to the elder, so the persona goes on to the fitting
check and the new-person route like anyone the tree does not hold (Annie
Lukens, born 1899 in her parents' 1900 household, is no near match for her
mother Anna Marie, born 1863).
A row of a search results page that points at records (FamilySearch, Find a
Grave, AAD) is never a card, whatever it agrees on: its own record is the
document. The row that fits the person the page was fetched for, by the
comparison above (more than a name and a year, nothing disagreeing), is a lead:
a fetch step on that person's plan for the row's own record (`tools/plan.py`,
row `search result:`, the results page's holder as the locator source, the
row's words as its fields and the page it was found on); every other row stays
a hint on the page. A row of a listing that is the record itself (the gravesite
locator's results, the death indexes') is proposed like a persona of any
record, and one of those, a schedule row or a name in running text that agrees
on the name alone is a hint on the page, never a card. One proposal per persona: `persona_match`
with the candidate that fits, or `new_person` when nobody does and the persona
is someone to create (above). The rationale
is plain words, which fields agree, which disagree, which are absent; no score
is stored or shown. A proposal carries the step's question when the step has
one, so it **answers a question**: "Is the James Ahearn in this 1870 household
Thomas's father?" Review happens on the person's screen, on the held record.
The decision is about the document: is this record's persona this person. A
record is every copy the archive holds of it (`docs/DATA-ARCHITECTURE.md` §7
decision 15, `same_record`: FamilySearch's index page, the image, a state
index's line), so its entry is put to the owner once, on whichever copy first
carried a card for it; a decision on any copy's entry carries to every copy's
persona of that entry under the one decision (`conclude.carry`: the link, the
copy's facts and family links, as the decision wrote them on the copy decided),
the reading of an image with no card of its own decided with the page, and a
rejection or a withdrawal reaches every copy the same way. A copy decided
otherwise on its own, by a person or the rule, keeps its own decision. The rule
judges the record as every copy holds it: taken on the points of the copy that
earns them, refused when any copy's persona of the entry disagrees against an
accepted value or fails the identity tests. A copy archived after the decision
takes it as it is read, and `tools/conclude.py reconsider` carries every
decision to every joined copy first.
Accepting writes the persona link Accepted and an Accepted assertion from each
fact the record states to the person: Name and Sex assert the person; a fact
about the record or the page (its id, an age at death) asserts nothing; every
other fact asserts one event, never several (one statement, one event). A fact
of a type a life holds once (Birth, Death, Burial, Cremation) lands on the
person's one event of that type whatever its date or place: a date or place
that differs is the conflict question below, never a second event, and only a
person with no event of the type gets one from the fact. Any other fact lands
on the person's event of its type whose own date agrees most closely with the
record's: the same day, then the same month, then the same year, then within
two years when either date is marked about, estimated or calculated (so
"19 November 1920" lands on an event the file dates "abt 1921"), among the
events whose place agrees with the record's or is absent when any does; an
undated fact lands on the person's one event of the type; a dated fact that
fits none makes an event of its own from the record's date. Where the record
does not choose (two or more events equally close, an undated fact among
several events of the type, a fact of a type a life holds once that fits none
of the person's several), the fact asserts none of them and is raised as a
`conflict` question naming the record, its date and the events to choose from
(`Catalog.unplaced`) until the owner places it on the event they mean
(`tools/conclude.py place`, which also moves a statement asserted on the
wrong event of the type, a family's as a person's; an event left with no
statement but rejected ones, one an older reading made of a misread value,
leaves the person's events and stays for the audit trail). A value the page
keeps beneath the one it shows is never raised so: it is never accepted with
its record, never ground for the rule and never a conflict, so where it stands
decides nothing to ask the owner about, and it stays with its record, no field
of the record's on its decision card; placed by
the owner all the same, it is written undecided and marked, as an acceptance
writes it where the event is plain. A statement placed is written under the
decision that accepted the record, so a rejection or a withdrawal of that
decision reaches it like any other it wrote. An attribute the
record states (an occupation, an inscription) asserts the person's attribute
of that type with the record's value, chosen the same way among several of
that value, created when the person has none. A record's fact already stated
on one of the person's events, through an earlier reading of the record or
placed there by the owner, stays where it is. Where the
record says the persona is the child, parent or spouse of a persona already
accepted as a person on the same record, the family link between the two
carries an Accepted assertion on the artifact too, created in a family of the
right shape when the tree lacks the link: a parent-child relation is evidence
on the child's membership, in the family where the child already stands under
that parent, else in the child's family of one parent (the named parent its
second, unless the two are already partners of another family), else in a
family of the parent whose every other partner the record itself names as the
child's parent (accepted on it, or put to its persona by a card still open),
else in a new family of that parent alone: a census that makes a child the
head's and a woman the head's wife names no mother, so the child is never
placed beside a wife, a second wife above all, the record does not name as
theirs; a spouse relation is evidence on both partners', and the family
facts the record states (a Marriage and its date and place) are asserted on one
of that family's own events of the type, chosen as a person's is, created when
none fits and raised for the owner when the choice is theirs (a marriage index
accepted for one partner waits for the other's acceptance on it, which writes
it). A relationship the record's indexer computed rather than the record
stating it (FamilySearch's relatives tables around a census's own person:
"Mother", "Sister", the parents' couple) is written the same way with an
Undecided assertion, as a sibling placement is, the decision's note saying the
indexer, not the record, states it; beside a relationship the record states
between the same two it adds nothing. A sibling
stated on the record places the person as a child of the other's accepted
parents with an Undecided assertion (the record states the sibling, not the
parents), and only when the other is an accepted child of one family and
neither of that family's partners died, on accepted evidence, before the
person was born (a mother before the birth, a father more than a year
before it): a half sibling is possible, a placement under the couple is not,
and the decision's note says why nothing was placed; otherwise a sibling
gives no membership. On a page anyone can edit (T4) the
decision is an identity: the persona link is Accepted, and the family
memberships the page states are created where the tree lacks them, each with
an Undecided assertion, the way a sibling placement already is, for the
relatives `docs/TERMS.md` §0 names; every fact the page types is written as an Undecided
assertion too, what the page says, never accepted by the decision and never
ground for the rule. **A person's own decision on a statement** is one a
person, or a session acting for them, takes on that statement itself: a key
fact decided (`tools/conclude.py fact … accept|reject|undecided`, the vouch
included, as is the owner's word placing a link or a divorce on a record), one
statement decided (`tools/conclude.py assertion`), and a card's rejection, for
every statement its decision wrote and every family link it was one of the two
acceptances for (below), save one a person had decided on its own; what an acceptance of a record writes with
it (its statements accepted, and the undecided ones of a page anyone can edit,
an indexer's grouping, a sibling placement or a value the page keeps beneath),
a re-read, a carry to another copy, a withdrawal and the import never make one,
whoever acted. A statement a person decided keeps that state until a person
decides it again: no acceptance of its record, by a person or the rule, no
re-read, carry or withdrawal changes it; any other statement already on the
tree moves only from Undecided to Accepted when its record is accepted again
(one the rule took back standing again). Every statement records who set the
state it now has (`assertion.asserted_by`) and whether that was a person's own
decision on it (`assertion.person_decided`). Where the
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

**What of an event's value is accepted.** An event shows one date and one
place, its own value, which the import, a fold or a resolution set and which
no record's statement overwrites. Of that value, what an accepted statement on
the event gives is accepted, and only that. The date is accepted to the day
where an accepted statement gives that day, to the month or the year where one
gives no more than that month or year, and a date the event shows as about,
calculated, estimated or bounded is accepted only where an accepted statement's
own date lies wholly inside it: an accepted census's year worked from an age
(CAL 1879) accepts no part of 6 April 1880, and the event's 6 April 1880 is
then a claim beside it. The place is accepted to the level an accepted
statement names (the state, where the record gives only the state; the whole,
where one names the place itself, a place inside it, the same place at another
granularity or by a name it held). The owner's own word on the fact (a vouch,
or the owner's word on a link or a divorce) gives the event's value whole. A
statement gives nothing accepted when it is not accepted, when it is not of the
event's own type, when it carries a mark (a sibling placement, a value a page
keeps beneath the one it shows, a grouping the indexer computed), when its
record is withdrawn from the evidence (`tools/tombstone.py`: the statement stays
as written, its status unchanged, and is evidence for nothing,
`docs/DATA-ARCHITECTURE.md` §2), and when a standing resolution set it aside,
the event's value decided against it. What
the event shows beyond what is accepted is a claim, and is said to be one, with
what it rests on (the file's claim, a page anyone can edit, a record not yet
accepted), wherever the value is shown or read: the proof summary, the person
screen's foundation and the fields its searches are built from, the decision
card's side of the tree, and the tree overview; an accepted statement that gives
no part of it (that calculated year, or another date) is named beside it. A key
fact is decided once a record stating it is accepted (`docs/TERMS.md` §1), and deciding it is
not accepting all its event shows. The standing rule reads what the accepted
statements give, never the shown value on its own (What the rule counts,
below). A date's point rests on an accepted statement that gives the date the
record gives, whatever the event shows beside it; a place's on one that gives
the place the event shows, whole, so a place the event shows on a claim earns
nothing. A record is refused when its date, or its death or
burial place, disagrees with what an accepted statement on the event gives,
though it agrees with a claim the event shows; a record that disagrees only
with a claim the event shows is not refused, and the difference becomes a
conflict question once it is taken. Two places that each name a part of the
event's own place, neither a place inside it, do not disagree (a death index's
state and an obituary's town written without it), as the conflict questions
read them. A birth place never vetoes, and a page
anyone can edit that contradicts an accepted statement holding primary
information is a contradiction of it, not a veto (the standing rule, below).

**One event, folded.** A person's events of one type, or a family's, are one
event when their places agree or one is absent and either the type is one a
life holds once or their dates agree on the year without giving a different
month or day (26 Jun 1901 and 1901 are one; 1728 and 1730 are not, nor two
marriages of one year at Amherst and at Northampton). The import writes a
file's repeated facts that way, one event carrying each fact's citations as
statements; a merge folds the kept person's events and a folded family's the
same way; and `tools/initdb.py --migrate` folds once what an older import or
older decisions wrote apart, one audit row per event folded under the
migration's own actor (`conclude.fold`). The kept event is the one whose date
or place the owner has spoken on (a resolution of theirs, or a reopen), else
one a resolution of the rule's names, else the one carrying the most accepted
statements, then the most statements, then the earliest. The other event's
statements and notes move onto it as they are, statuses unchanged (a second
statement of the same record fact stays where it was); the kept event takes a
date it lacks, or one that agrees with its own and says more (26 Jun 1901 over
1901 or Jun 1901, 24 April 1876 over CAL 1875; never 26 Jun 1901 over Jul 1901,
another month), and a place it lacks, never on a date or
place the owner or the rule has decided, and never a date that a date an
accepted statement on either event gives disagrees with (the owner's word
gives its event's own date): a fold never sets an accepted record's date aside
for a claim; and the emptied event leaves the
person's or family's events, its row kept for the audit trail. Dates that
differ, on a type a life holds once, leave the kept event's own value and the
other in its statements: the conflict question above, which the rule's classes
may settle or the owner resolves. Two events that each carry the owner's word
on their date or place are never folded into one: the migration refuses,
writing nothing, until the owner has answered one of them.

**The standing rule.** After the matcher writes its proposals, the rule takes a
`persona_match` on the owner's behalf when the record is of a kind that
identifies a person fully. The kinds are data: `data/evidence-classes.csv` gives
each kind a standing (automated, the rule may take it; identity, a page anyone
can edit that identifies a person; hint) and a record takes the standing of the
most specific of its kinds that gives one (`catalog.record_kinds`), a kind the
table does not hold being a hint. That is `docs/TERMS.md` §0's list: a census from 1850 (before
it the head alone is named), a 1950 schedule, a certificate or index of birth,
death or marriage, a church register entry once it is dated and names the
parents, Social Security, naturalization, draft cards and service records, a
veteran's gravesite, a gravestone's photograph once read; a land, probate or
public records index, a passenger list, a compiled genealogy and a row of a
results page are hints. A record read by hand or by the model is judged exactly
as one a rule parsed, by its kinds, its tier and the facts that agree, never by
who did the reading. A record is judged as its current reading gives it: a card
or a decision written on an earlier reading of the page is judged on the persona
of the same entry in the reading that superseded it, with the facts and
relationships that reading gives, and one whose entry that reading no longer has
(a reader that read the page again gives no such row: one an older reader read
twice, a row with no name) is refused as no longer read, never judged on the
superseded reading's own persona: `reconsider` withdraws such a decision of the
rule's, and the record's current reading is matched again.

On a record nobody can edit at will (T1–T3) the rule takes the persona when the
given name and surname agree with the accepted name (a wife under her married
surname agrees too — that is how her own obituary can name her at all; a
surname one letter apart is a card), the facts that agree make two points (What
the rule counts, below) and nothing disagrees against an accepted value: what
the accepted statements on the event give, never what the event shows (What of
an event's value is accepted, above), so a record agreeing with a date the
event shows on the file's claim alone is refused where an accepted statement
gives another. A disagreement with a value that rests on no accepted assertion
is no veto and becomes a conflict question once the record is taken; a stated relationship
vetoes only against a link the tree holds on accepted evidence (a sister the
file alone places in another family is no veto); a birth place, secondary on
nearly every record and never a point, never vetoes. An obituary or newspaper
text is such a kind only once read, and only on its own ground: one of its
points must be a relative it states who is that relative in the tree on trusted
evidence — no number of agreeing dates or places substitutes, because the named
survivors are what identifies the person here (`docs/TERMS.md` §0).

**Which variants the rule counts as the name.** The name the rule compares a
persona with, on every route and for every relative it reads a persona as, is
the person's own name rows (the name, and a birth or married name split out of
it) and the aliases accepted for them, and nothing else. An alias takes the
standing of the record it came from: the name as written on a record accepted
for the person is an accepted alias when the record is one nobody can edit at
will (T1–T3), and an undecided one from a page anyone can edit; an undecided
alias, such a page's, one `tools/backfill_aliases.py` wrote, or one a withdrawal
or a give-back of copies took back with its decision, is no name the rule
stands on. The matcher reads every alias not rejected where a wider name only
widens the search or the caution: when it looks for the people a record may be
about, when it compares a persona to propose a card, and in the rule's own test
that nobody else fits as well (Identity is tested, below); the search reads
them all as well (`docs/DATA-ARCHITECTURE.md` §8). A withdrawal returns the
alias its decision wrote to undecided with the statements, so a decision taken
back no longer shapes later ones; a rejection turns it rejected.

A persona whose name the tree does not yet hold on such ground is taken through
a relationship the record states (child, parent, spouse, sibling; never one its
indexer computed) to a persona accepted on the same record as a person the tree
links to the candidate by that relation, claimed or accepted, when the given
name and surname agree with the candidate's and a birth year agrees where both
have one; the record's own name fact then documents the name. The tree links
the two so when, in a family joining them, each one's membership carries an
accepted statement or the file's claim, which is the import's own statement of
that membership, not rejected, and nothing else: a sibling placement, a page
anyone can edit, an indexer's grouping, a statement from the record under
decision on any of its copies and a claim whose own citation is that record
claim nothing. A stated sibling
of a person accepted on the record fits a candidate who is a child of that
person's parents, claimed or accepted, or who has no parents in the tree and
whose surname agrees, and is placed as a child of those parents with an
undecided assertion. A persona a trusted record (T1–T2, or an obituary once
read) names in a relationship it states to a person accepted on it, who fits
nobody in the tree after the fitting check, is created by the rule with the
record's facts and the family link accepted, and enters the queue. A creation
written on an earlier reading of the record is judged on the same entry of the
reading that superseded it by these same terms, the fitting check not counting
the person it made: while that reading meets them the creation stands on the
entry and a card putting the entry to that person is taken on them where nothing
it states disagrees against an accepted value, and when it no longer meets them
the creation is withdrawn. The fitting
check, run before any creation, looks across the whole tree: a person whose
surname or birth surname agrees, as written or as a spelling variant, and whose
birth year lies within the matcher's window where both give one (a person
already placed in a family only when the given name agrees too), or who stands
in the same stated relationship to the same accepted person, fits and is
proposed instead: the grandson an obituary writes Matthew Ahern is put to the
tree's Matthew Alan Ahearn, never created a second time.

On a page anyone can edit that identifies a person (a memorial, a profile) the
rule takes the identity alone, when the name agrees and at least three of birth
date to the day, death date to the day, burial place, and a stated parent or
spouse who is that relative in the tree agree with the tree, claimed or
accepted, a claim the file cites to that very page not among them (the reason
names what it left out). A date or a place is claimed or accepted as a link is:
the event carries the file's claim of it or an accepted statement giving it, so
an undecided fact another page anyone can edit types, a value a page keeps
beneath the one it shows, a statement a withdrawal left undecided and one a
standing resolution set aside count for nothing; what the event itself shows
counts only through a statement that gives it, and a day the page gives counts
on such a statement whatever day the event shows. However many relatives the page lists, they make one
of the four at most: a parent or a spouse the page states, never a child or a
sibling, whom the tree links to the person as the route through a stated
relationship reads a link (claimed or accepted, above). A date or place the page
gives that disagrees with an accepted statement holding primary information is
no veto there: such a page is
not trusted for a fact, so the primary record's value stands and the page's,
written undecided like every fact it types, is a contradiction of it, a conflict
question the classes decide for the primary record, the page named on the side
set aside (the owner, 3 Oct 2026: "use the primary document and just tag the find
a grave as a contradiction"); a relative a memorial lists is a lead, never a card
(`docs/TERMS.md` §0, `docs/PLAN-AND-SEARCH.md` §3), and one a profile lists by name and years alone has at most the
stated relation and is a card for the owner.

**Identity is tested, not assumed** (`docs/DATA-ARCHITECTURE.md` §7 decision
12). Before the rule takes a record by any route above, or creates a person
from it, three tests, each a refusal with its reason in words when it fails,
the card staying the owner's: nobody else fits as well (the persona compared
with every person of the tree not merged into another, spelling variants and
short forms as the matcher compares them; another person who fits on as much
as the candidate or more is named, and for a person the rule would create,
anyone who fits or whom the fitting check reaches); the person holds no other
accepted persona on that reading of the record (two rows of one page are two
people); and nothing the record would add falls outside the person's life as
accepted (their accepted statements' own dates): a dated fact after the
accepted death or before the accepted birth (the death, a burial, a cremation,
a will and its probate excepted after the death, the birth itself before the
birth), or a parent-child relationship it states to a person accepted on it
that breaks the limits of one life below.

**The limits of one life.** Every plan regeneration tests each person's family
links, every one the tree holds that is not rejected (accepted, the file's
claim, a sibling placement the rule wrote, a membership a page anyone can edit
states: a link the tree holds is tested whatever it rests on), and their
accepted dated statements against the limits of one life, which are data
(`data/life-limits.csv`, the reasoning in `data/DATA-SOURCES.md`), beside the
conflicts (`Catalog.beyond_life`): a statement dated after the death or before
the birth; a mother or a father too young or too old at a child's birth; a
child born after the mother's death, or more than ten months after the
father's; one person in two places in one census year (two accepted census
records of that year whose places agree neither way). The dates are the
events' own as the tree shows them, whatever stands behind them, and only what
holds over every day each date can stand for counts, so a bare year asks
nothing a finer date of it might keep. A hit is an `identity` question on the
person (on the child, for a link) naming both dates, the records or claims
behind each and the limit broken; nothing is changed, and the question closes
when its gap has gone or the owner dismisses it.

The proposal records the rule as the decider with its
reason in words, the audit row says the same, and the card shows "accepted by
rule" with a Reject control: rejecting turns the link, every assertion and the
name alias the rule wrote rejected, and every family link the decision was one of
the two acceptances for, the links a withdrawal takes back (below): the persona is
not that person, so the record states no link of theirs, and the rejection is the
person's own decision on each of those statements, so no later acceptance of the
other card on the record writes the link again. Rejecting a card whose decision
the rule took back turns rejected what that decision wrote, and the links its
withdrawal took back, the same way. Any acceptance, a session's or a person's as
much as the rule's, a person takes back the same way, with the reason
(`tools/conclude.py decide <proposal> reject --note "…"`): what a withdrawal
takes back turns rejected as the person's own decision, the questions the
decision answered are closed so the plan reopens those whose gap is back, the
plans of everyone the links reached are regenerated, and one audit row records
it; in every rejection a statement a person decided on its own since keeps the
state they gave it. A proposal the rule does not take is a card for the owner
with the reason it was not taken. The rule creates a person only as above,
through the fitting check; every other `new_person` proposal is a card for
the owner. The rule
can take a decision back: `tools/conclude.py reconsider`, once it has carried
every decision to every copy of its record (above), examines every
decision it made, in the order the rule took them (the second it decided, then
its accept row in the audit log, which `decide` writes as the decision takes
effect), as the rule stands now and on the ground that stood before it (its own
assertions and those of later rule decisions do not count), withdraws one it
would no longer take, its assertions and the name alias it wrote back to
undecided, recorded as the rule's (a statement a person has decided on its own
since keeps the state they gave it), and the record is a card for the owner again
with the reason; accepting that card makes everything the decision had written
stand again. One it keeps it brings to what a decision writes now, recorded as the
rule's, one audit row each: the name alias it wrote takes the standing of its
record, and a family link it wrote accepted that the record's current reading
gives as its indexer's grouping goes undecided, noted as the indexer's (a
statement a person has decided on its own keeps its state); the same under a
person's own decision it never changes, and lists as theirs to answer. A withdrawal also takes back the family links its decision was one
of the two acceptances for (a link another decision on the record wrote between
the two people, with the family facts written with a spouse link), unless another
pair accepted on the record still states it or a person decided its status on
their own, and a decision examined after it in the same pass stands on none of
them. It then matches again every card the evidence has passed by
(above: one an older matcher wrote, one left on a superseded reading, a
decision it has just withdrawn there included, and one the matcher would no
longer put to that person), and examines every card still undecided
the same way and takes one it would now take, recorded as the rule; a decision
can open another card, so it passes again until nothing new is taken. Then it
goes over the conflicts: every conflict it resolved is examined again, newest
first on each date or place, and one it would no longer resolve so (the
statement it kept rejected, primary information arrived against it) is taken
back, the event's value restored from the resolution's own record of it and
the question open again for the owner; then every open conflict on an event's
date or place is resolved where the classes decide it (the proof standard
below), the rest left to the owner with the rule's reason. Run it
after any change to the rule, to the matcher or to a source's tier.

Every accept, of a match, a new person or a fact,
regenerates the person's plan in the same request, and the plans of everyone
whose family its links change: for each membership its statements state (on
every copy of the record), the member and the family's partners, a child's
statement being each parent's child and a partner's the other's spouse, and
everyone in a family a link puts someone into anew (Annie joining Milton's
family as Charlotte's mother gives him a spouse; Charlotte placed under him
gives her parents); so does a rejection, a key fact or one statement decided,
and the rule's withdrawal, for the links they turn rejected, decide or take
back, a decision carried to a record's new reading or to another copy of it and
the owner's word giving a copy back, for the links they write or give back
(`conclude.link_people`), and a merge, for everyone in each family the
duplicate's memberships move into or a fold empties another into (the kept
person's spouses, children, parents and siblings there). An open question of
kind `missing_parents`, `unverified_claim` or `missing_fact` that the
regeneration closes is closed as `answered` with the proposal that brought the
evidence; a `conflict` closes when it is resolved with a written reason, by a
person or by the rule, or a person dismisses it with a written reason of their
own, and, like any question, as `gap_gone` when a regeneration no longer finds
the disagreement (one side rejected or withdrawn), opening again if it returns.
A conflict is never dismissed without a reason: the person screen's Dismiss
asks for it and `tools/log_search.py --dismiss <question> --note "…"` refuses
a conflict without one; the reason is kept on the closed question and on the
audit row that closes it. A dismissal keeps neither side and changes no event:
keeping a statement is `resolve`. Resolving
(`tools/conclude.py resolve <question> --keep <statement> --note "…"`) names
the statement whose date or place the event keeps: that value becomes the
event's own (the place only once its words are resolved to a place), the
question closes `resolved` with the reason and the resolution in it, one audit
row names the value kept, the event's value before and every statement set
aside, and each statement stays as its record says it. The same
difference read afterwards from the kept side is closed with it, so a
regeneration reopens nothing, while a statement that comes later makes a
question of its own. Every decision that changes a person's evidence (a card,
a key fact, one statement, a place's words, a conflict resolved or reopened, a
statement placed, a link or a divorce on the owner's word, a merge, a decision
carried to a record's new reading or to another copy of it) regenerates
the plans of the people it changes and then lets the rule go over their
conflicts, as `reconsider` does for everyone, and then matches their undecided
cards again (§5–7: the matcher's words as they now read, or the card superseded
when the matcher no longer puts the persona to them), in the decision itself,
whichever command or screen takes it (`conclude.settle_people`): a resolution of
the rule's resting on a statement the owner has just rejected is taken back
there and then, never left for the next `reconsider`, while a date or place the
owner has resolved or reopened stays theirs. The rule resolves through the same path,
recorded as `rule:classes-favour-one-side for <owner>`, when the classes favour
one side without doubt (`conclude.classes_decide`): the statement it keeps
holds the event first-hand (primary information, accepted, from a record whose
source class is original or derivative and nobody can edit at will, direct, and
the event the record was made for: an event the classes table names primary
for the record's kind, such as a census household's residence or a death
record's death, for anyone on it, any other only for the person the record is
about, so a parent's birthplace on a child's birth register decides nothing),
no statement that differs from it holds primary information or the owner's own
word (a vouch, the file's uncited claim the owner accepted), and the
statements that agree with it agree with one another, so a county kept while
two towns in it still differ never closes a difference the classes do not
decide; a place it keeps only once its words are resolved, waiting on the
owner's answer to them otherwise. A date or place the owner has resolved,
dismissed a difference on, or reopened is the owner's from then on, and the
rule never decides there. The owner's own resolve on a question the rule
resolved takes the rule's resolution back first; `tools/conclude.py reopen
<question> --note "…"` takes it back without keeping anything, the event's
value restored and the question open again. Every decision of the rule on a
conflict, a resolution made or taken back, is told in words where it is made:
in the answer of the decision that led to it (the command line's and the
person screen's) and in the report of the turn, each naming the person, the
date or place kept, the rule's reason and the question id `reopen` takes.
Accepting grows the baseline, which generates new questions.

### The proof standard

**Accepted.** Automated decisions follow the Genealogical Proof Standard
(Board for Certification of Genealogists): reasonably exhaustive research,
complete and accurate citations, analysis and correlation of the evidence,
resolution of conflicting evidence, and a soundly reasoned written
conclusion. The standard governs conclusions, a person's key facts; the
standing rule's decision that a record is about a person is linkage, the
ground those conclusions stand on, and rests on the same analysis. All of it
is words, never numbers (`CLAUDE.md` hard rule 1).

- **Classes, as data.** Each record kind and field carries a source class
  (original: the record made at the event, its image; derivative: an index,
  abstract or transcript; authored: a compiled genealogy, a memorial page, a
  family tree), an information class for each fact (primary: from someone with
  first-hand knowledge, the record's own event; secondary: the rest, a birth
  date on a death record, an age on a census; indeterminable), and for each
  relationship whether the record states it or the indexer computed it (a
  census states each person's relationship to the head; FamilySearch's
  "mother" and "sister" groupings are its own), with the original a
  derivative comes from, the words a record is named by. Which files are copies
  of one record is `same_record`'s, never those words alone
  (`docs/DATA-ARCHITECTURE.md` §7 decision 15: one record, cited once, its copies
  beneath it).
  The table is `data/evidence-classes.csv`, read when needed; a class never
  becomes a weight.
- **What the rule counts.** A point is a birth date, a death date, a death or
  burial place, or a relationship the record gives that agrees with the tree,
  and it rests on the tree's own statement of that very date, place or link:
  accepted, from a source nobody can edit at will or on the owner's own word (a
  vouch, or the file's uncited claim the owner accepted), giving the value
  compared (What of an event's value is accepted, above): a record whose date
  agrees with such a statement earns its point though the event shows a claim
  beside it, one whose date agrees only with a claim the event shows earns
  none for it, and a place earns its point where such a statement gives the
  place the event shows, whole. A date agreeing to the day, or a relationship, counts double, and
  any other date once, whatever the information class of the statement it
  rests on: the information class weighs which of two statements that differ
  is right (Conflicts, below), while a day or a relative two records nobody
  can edit both give marks one person whoever informed them
  (`docs/DATA-ARCHITECTURE.md` §7 decision 14). A date bounded before, after
  or between (from–to) is compared as its range, edges included: a date or
  range wholly outside it disagrees, and one inside it or overlapping it
  neither agrees nor disagrees, so a bound is never a day or a year of birth
  or death, never a point and never a veto. A relationship the record's
  indexer computed counts once at most, is never an obituary's survivor and
  never an accepted family link. A statement marked as a sibling placement, a
  value the page keeps beneath the one it shows or a link the record's indexer
  computed is never the ground of a point, nor a link, a date or a place the tree
  holds against a record or claims, whatever its status: the record does not state it. Nor is a
  statement resting on a file withdrawn from the evidence (`tools/tombstone.py`), whatever its
  status: it stays as written and is evidence for nothing, no side of a conflict, no date the
  limits of one life test, and no record the written conclusion counts (it names the record
  withdrawn); the rule takes no card on such a file, the withdrawal closes the cards still open
  on it (rejected under who withdrew it, the note `withdrawn`, as a re-read closes the cards of the
  reading it supersedes), a card on it cannot be accepted, the refusal naming the tombstone, and a
  key fact's accept acts on none of its statements. For the
  same reason a value the page keeps beneath the one it shows is no name, date or place of the
  record's when the record is compared with the tree: the given name and surname the rule tests
  are the ones the page shows (a shown Fred M Ahern with Fred M. Ahearn beneath agrees as a
  spelling variant, never as written), and it is no side of a conflict. A place
  the record gives coarser than the tree's own (a state or a county against a
  town) agrees, is said in the reason, and earns nothing. A record
  counts once wherever it is held: a statement from any copy of the record
  under decision (`same_record`) is no ground for its point, nor is one from a
  record of the same original about the same person's same event that the code
  cannot show to be its copy (the state's index line and FamilySearch's index of
  one certificate, two papers' obituaries of one death: the owner's ruling,
  count once), never one from another person's record of the same kind. A stated relationship
  counts only when the related persona is accepted on the record or fits its
  tree relative on something besides that relationship (a couple's index
  entry, two names and a date, takes neither of them); a link the file alone
  claims counts once, when that relative's persona fits on more than a name.
  A claim whose own citation is the record under decision never counts, nor
  does a statement on a page anyone can edit. Given names that differ in a
  middle name or initial disagree.
- **Conflicts: kept, cited, pointed out, then decided.** A record that
  differs from the tree's value is still accepted for what it says: its
  statement stays, cited to the archived record, and the difference is a
  conflict question on the person, never an overwrite and never a silent
  drop; a birth place, secondary on nearly every record kind and never a
  point, never vetoes. The tree's value is decided, not inherited from
  whichever record arrived first. The rule decides a conflict when the
  classes favour one side without doubt: the side resting on the record of
  the event itself, primary information from an original or a derivative of
  one, against a side resting only on secondary information, on a page anyone
  can edit, or on the file's bare claim. It writes that reasoning as the
  resolution's reason, recorded as acting on the owner's word and reversible
  like its other decisions (`reconsider` re-examines it). Every other
  conflict (two primary sources apart, both sides secondary, a classes table
  silent) is a card for the owner, who closes it with a written reason
  naming the value kept (`tools/conclude.py resolve`). Either way the kept
  value becomes the event's own, the statements set aside stay as evidence
  with their citations, and the proof summary prints the resolution and its
  reason.
- **Reasonably exhaustive research.** A key fact's research is its checklist
  rows, each held, searched with nothing found at every source, cited and not
  yet fetched, or blocked. It is stated with the conclusion, not a gate.
- **The written conclusion.** `tools/proof.py "<person>"` writes, for each
  key fact, the value with what of it is accepted and what is a claim (What of
  an event's value is accepted, above), the evidence, each record once with its copies beneath
  it, with its class words and its citation, what agrees, each conflict with its question id (the
  one `tools/conclude.py resolve` and `reopen` take) and how it was resolved,
  the research by row, and who decided (the owner, or a session acting for them,
  only where a person's own decision on that statement set its status; else what set
  it: the record's acceptance, a re-read or a carry, the rule); a fact resting on indirect evidence,
  a value part of which is a claim, or an open conflict says that an argument
  is still owed. An open conflict on an
  event's date or place carries the rule's own reading of it, from the test
  that decides it (`classes_decide`): the statement the rule would keep and why,
  or why it would not decide (no side primary, primary on both sides, a place
  not yet resolved, the owner's own word or earlier decision). The test is over
  the event's date or place as a whole, so two conflicts on it share one reading.
  A record's locator is printed once per proof, at its first mention, and
  every later mention is its number. Pure code: the model reads only what code
  cannot, a handwritten image or a newspaper's text.
