# The plan and the search

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
spouse or parents; run for every person, reviewed or not, and never counting a
person merged into another), unlinked same-surname persons as hints with a generation
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
sources, as for a missing row. A citation at a free holder with no connector
whose link takes nothing from the citation (the holder's form posts, as the SAR
Patriot Research System's does, or its link is the same whatever the citation
says: `catalog.prefills_nothing`) is a fetch step with mode `assisted`: every
citation of that holder opens the same empty form, so there is no page for this
citation to save, only a search a person runs, the citation's own details as
what to look for and the holder's page as where, logged like any assisted
search. It stays off the fetch list (§4), no person waits on it, and its log
stays through a re-plan. A holder whose link carries a field of the citation
stays `fetch`, and so does one with a connector, which asks by the fields and
not by the link. A **search**
is a typed query (`subject_record`, `household`, `couple`, `name`,
`surname_locality`, `obituary`, `probate`) for a missing row, built from the
foundation fields with each field's basis, with its registry sources, one mode
(`auto`, `assisted`, `awaiting_approval`), and what a hit would look like.
A fetch step's fields carry basis `citation`.
Footprint records on relatives are fetch steps under the fact-level question
they serve. A held record that names a person and links their own record makes
a fetch step for that record: a memorial lists each family member with their
own memorial, each step carrying the linked record's own identity
(`memorial_id`) as the locator and the page's words as its fields (basis
`record`). A listed persona accepted as a person makes the step under that
person's cemetery row. Once a memorial is accepted as somebody's own, every
relative it lists that nobody has decided otherwise is a lead: one whose given
name, surname and birth year fit exactly one person of the tree gets the step
under that person's cemetery row; one fitting nobody, or several, is a lead on
the memorial's own person (row `listed relative:<memorial id>`), counted
apart from the documents to decide. A row of a saved search results page that
fits a person the page was fetched for is a lead the same way: a fetch step
for the row's own record on that person's plan (row `search result:`, step key
`fetch:row:<record id>`), its locator the record's own identity (an ark, a
memorial id, an enlistment record's URL) at the holder of the results page, the
row's words as its fields (basis `record`), the page it was found on among
them. A census household not wholly held (`docs/HOUSEHOLDS.md`) is a lead on each
person the tree ties to one of its members, by a link or a card that nobody has
rejected, under a row of the household's own, `household:<year>`, and not the
person's census row, which the person's own census record holds
(`tools/plan.py`'s `household_leads`). Its search is one step (key
`fetch:household:<form and page>:<surname>`, locator kind `household`):
FamilySearch's search of the collection the household's copies are in (its key
from `data/holders.csv`), by the surname most of the members are written under,
the place their census residence gives and the year, never by a given name:
the head's own need not be any member's, and a search by a given name finds a
head of another name only by chance. Its link is the first page of the answer
not yet held: page 1, then, an answer being cut ("120 matching records, page 1
of 6"), each next page in turn (the site's own `count` and `offset`), until
every page is held. The fetch list prints it as a lead with the link and the
name to save under (`familysearch-census-1925-search-peters.html`, a later page
`…-page-2.html`), and the results page reaches the step by the list's key and by
its own fields. The rows of the answer, and of every results page the archive
holds of the same collection for the same surname at the same place, are the
candidates for the household's missing entries, and the record page of the one
the order puts first is a step of its own (key `fetch:row:<ark>`, locator its
ark, under the same row), one at a time (`docs/HOUSEHOLDS.md`: which rows, in what
order, and why one). The order puts first a row whose name fits a person the tree
names in a missing entry's place (the head's, or a line's through a member's
family) or whose record id is a member's but for its last character, whatever its
birth year; and while a page of the answer is not held only such a row is opened:
a row that fits nobody waits until every page is held, the search's next page the
household's one open lead, since a results page gives twenty candidates for one
save and a record page one. The fields of both are the held records' (basis `record`),
never the person's claims, so they open before the baseline is reviewed, as a
cited record's fetch does: they find the rest of a page already held. The
Peters household gives Ruth M Peters and Mary Peters each the search,
FamilySearch's New York 1925 collection (1937489) searched for Peters at
Hempstead, Nassau, in 1925, and each its first candidate, Fred Peters, whose name
fits the file's Fredrick C Peters. Running a step (Go, Search, the log buttons) is the approval;
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
| auto | Chronicling America (loc.gov), the 1950 census site, the Internet Archive's full-text and title search, WikiTree, the VA gravesite locator, the New Jersey death index, the Kentucky death and birth indexes, NARA catalog, Open Archives, Wikidata, the held archive when their connectors exist | the system runs the query, archives raw responses, extracts personas |
| assisted | Find a Grave, the WWII Army enlistment file at the National Archives (AAD), FamilySearch record search (free account), the SAR Patriot Research System, Newspapers.com, Fold3, Archion | the system builds the exact search URL and tells the user what to look for; the user saves the result to `inbox/`, or a session drives the owner's own logged-in browser to save one cited record at a time by the page-saves-itself method below; the system takes it from there |

**Adjusting a prefilled search.** A person at the keyboard may change the
fields of a prefilled search before running it (a wider year, a middle name,
a place spelt as the site wants it); the run's log carries the fields as run,
so the change is a logged act. A link that is wrong for the citation itself
(a suffix taken as a surname) is a defect: report it, do not work around it.

**A cited record whose holder's link prefills nothing.** A cited record at a
holder whose link takes nothing from the citation (the SAR Patriot Research
System's search form posts, and its `robots.txt` disallows the search to every
agent) is an assisted fetch step (§3), a search to run by hand and not a page to
save: the screen shows the citation's own details (the collection, the name the
citation sits on, the page text's parts) as what to look for and the holder's
own page as where; the owner runs the search there and logs it as for any
assisted search (nothing found, blocked, or a page saved into `inbox/` and
attached to the step). The step is never on `tools/fetches.py`'s list, which is
the pages the page-saves-itself method can save: the same empty form listed once
per citation and person is a page nobody can save as an answer.

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
the owner's own browser in one call and never read through the model.
`tools/fetches.py next` names the next pages (five by default): the link to
open, the file name to save under, the people waiting and the call for the
script, one line each. For each page: open a new tab, navigate
it to the link and run `tools/save_page.js` in it with the line's call in place
of the `("FILENAME.html")` that ends the script
(a navigate and the script go in one batch call), read the one line it returns,
close the tab: three calls and no screenshot. The script waits up to fifteen
seconds for the page's own markup, then clones the document, removes `iframe`,
`script`, `style`, `link` and `noscript` elements, hands the result to the
browser as a download, and says `ok <kind> <bytes>B`, the kind being the one
the parsers read: `fs-search` (a FamilySearch results page, rows or "No
Results"), `fs-record`, `fg-memorial`, `fg-search`, `aad`. A page of none of
those is not saved, and the line says why: `BLOCKED signin`, `BLOCKED
challenge`, `EMPTY no-script fallback` (nothing rendered), or `UNKNOWN <title>`
(true as the script's second argument saves it anyway). That line is the check:
look at the page only when it says something else than ok, and never run a fetch
loop in the page. The script is one awaited call (`await (async function …`):
the browser tool returns an awaited value and gives `{}` for a promise still
pending, so a bare call saves the page and returns no line, and whoever ran it
runs it again and saves the page twice. The browser saves into the data root's own `downloads/`
folder (the repository's `downloads/` for the live tree): the owner sets it as
the browser's download location once, in a browser profile kept for tree work
if they prefer, and no tool reads the owner's own download folder. If the browser is set to ask where to save each
download, turn that off first or answer the dialog by hand; a dialog left open
blocks every later browser call. Chrome lets a page start one download without
a hand on it: a second page saved in the same tab lands nowhere, so each page
gets its own tab, closed after the file arrives. `tools/fetches.py list` prints
the pages the page-saves-itself method can save: every planned fetch step at a
holder without a connector, once, leads from held records first, with the link
to open, the people waiting on it, the file name to save under and the call,
leaving out
the pages whose steps have all been run on unchanged fields (`--all` brings
them back); `next` takes the same pages in the same order.

The call is the file name, whether to save a page of no known kind anyway
(`true` at a holder whose pages the script knows by no markup of its own), and
the page's key: the plan steps the page serves (those of every entry with that
link and file name). The script writes the key as a second comment under the
saved-from line, `<!-- for steps <id>,<id> -->`; a page saved by hand has no call
and carries no key. `collect` reads the key from the page's bytes, never from its
file name, and reaches the steps it names first, once it has checked that each
is a planned fetch step of this tree and that the page's own identity does not
contradict it: a record page whose ark, memorial or AAD record is not the record
the step asks for, a results page where the step asks for one record, and a
results page of a collection the citation is not of all contradict it. A step
the page contradicts, or the plan no longer has, is set aside and the line
`collect` prints says so; the steps the page's own identity reaches (the
inference from its collection and the name searched, the same search serving
other people's steps) are taken beside the key's, and are all it reaches when the
page has no key. A gravestone photograph carries no key: its bytes are the
photograph, and its file name names its one step.

A row of a saved
results page that fits the person (`docs/RULE.md`) is a lead of its own, a fetch step for the
row's own record under row `search result:`, and is listed as that record's page
in the search link's place, under the record-page name with the row's ark filled
in, until a page carrying that ark is archived: the listing pointed at the record
and is not one. A step at a browse-only holder (`catalog.browse_only`:
a FamilySearch images-only collection, browsed by hand, film by film, with no
search or record page for a browser to save) stays on the plan, fetchable,
with the reason in its rationale, but never reaches this list.
`tools/fetches.py collect` then moves every saved page from `downloads/`
(or `--folder`) into `inbox/` (beside a file of the same name already there it
takes a free name, `<name> (2).html`, never writing over it, and its line says so)
and attaches each by its own identity,
read from the saved-from line the browser wrote (`tools/save_page.js`) when
that line is a FamilySearch record or search URL, a Find a Grave memorial or
search, or an AAD record or search — whatever the file is named, since Chrome
may have sanitized or de-duplicated the name the list printed — and to the
steps its key names. A FamilySearch
link that is the collection's own search (no ark yet known) is listed to save
under `familysearch-<collection words>-search-<given>-<surname>.html`, the
given name and surname the search's own, so the several people's steps one
search serves share one name; a census collection's search carries the row's
own year too (`familysearch-census-<year>-search-<given>-<surname>.html`), so
a person's two census searches (the 1925 New York state census and the 1930
federal census) do not share a name, and a later page of a search's answer, its
link carrying the site's `count` and `offset`, ends `-page-<n>`
(`familysearch-census-1925-search-peters-page-2.html`); a link that is a record page is listed
under `familysearch-<collection words>-<year>-<ark id>.html`, the ark id read
off the page once saved. Two different links that would take one name (a
person's 1910 census searched once narrowed to a residence and once not) each
carry the first six characters of their own link's sha1 before `.html`, so no
page is told to save under another's name. For a page from a holder whose pages carry no identity
the attach reads (a Legacy.com obituary), by the name
the list printed, whole: such a page is listed once per citation and person
waiting on it, under a name that carries the citation's own record locator
(the step's key when it has none) and ends in that person's six characters,
so one person's several pages of one collection are told apart as two
people's are, and no name waits on a year the citation may not carry; the
saved file goes to that person's steps on that citation alone, archived under
that holder with the page's own URL as locator and reported unparsed until a
parser claims it. Its run is logged `unread`, not found, the note saying that no
parser reads the page: the page is held on the step's log, still fetched for
that person, and the step stays planned, for a page no parser reads holds
nothing a program knows and closes nothing. A name is not an identity: at a
holder whose pages carry their own (FamilySearch, Find a Grave, AAD) a file
saved under the list's name with no saved-from line is not the page, whoever
or whatever saved it, and collect leaves it where it is. The run on the step's own fields
keeps the step off the fetch list while the page waits. The run stays as what
happened when a parser is added and the page is read again
(`tools/extract.py <sha256>`): the step is then closed the way any fetch step
is, by a record page that holds its citation. An image, and a page the model or a
person has read through the transcription path, is not this case: its run is
found, as for any record. A file with neither a recognised saved-from line nor a
listed name is left in the folder. A results page saved again with the same
rows already logged on the step is a repeat: nothing new to archive, so the
file is removed with none archived twice, and a none run is logged on the
step's current fields, the note naming the earlier artifact, wherever the
step wasn't already answered on those fields. Never encode a page and read
it out through the model in slices.

**A model saves the page.** `tools/run_task.py` hands a page on the fetch
list to a model in place of a hand (`docs/DATA-ARCHITECTURE.md` §7 decisions
16 and 19). The task is the list's own entry, rendered by code: the link, the file
name, and `tools/save_page.js` with the entry's call in place of the
`("FILENAME.html")` that ends it. What the model needs beyond the entry is
one text for the kind of task, `tools/tasks/fetch.md`, the method above in the
model's terms and the standing rules on sources (one page, the link as given,
a challenge or a sign-in reported and never passed); nothing is written for
one task. The model writes nothing to the catalog: the page it saves lands in
the data root's `downloads/` as a page saved by hand does, and `collect` takes
it. The browser's download location is the owner's setting, made once: a page
the browser saves anywhere else is not found, and the run says so (the model
reported the page saved, and no page came in).

What starts the task and returns its measures is a launcher, and there are
two behind one seam; what renders the task, judges the answer and records the
run is the same code for both and does not know which ran it.

- **A session the owner is at** (`next`, `done`). A browser action needs a
  person's approval, so a page is saved by a subagent of a Claude Code session
  where the prompt reaches the owner. The fixed words are two files under
  `.claude/` that code writes (`tools/run_task.py write`) and `tools/check.py`
  holds to what code would write: the agent `tree-fetch` (the kind's text as
  its system prompt, the form of its answer written from the kind's schema,
  the browser's tabs, navigation and script as its only tools, its effort, no
  project instructions) and the skill `tree-fetch` (`tools/tasks/fetch.skill.md`,
  the session's part). The session composes nothing: `tools/run_task.py next
  --model M` hands out the next page's task (the agent, the model, the task
  as rendered) and writes it beside the database; the session spawns the
  agent on that model with exactly that text; when the subagent ends,
  `tools/run_task.py done` takes its last message as it came and the numbers
  the session was given for it (tokens, tool uses, time), and collects,
  judges and records. One task is out at a time. The model is set per spawn;
  the effort is the agent file's, which a spawn cannot change, so `next`
  takes none and the run records the file's. A subagent that ends with no
  message is reported with no answer.
- **A headless prompt** (`fetch`). `claude -p` once per page with its input
  closed: the text as the system prompt, the rendered entry as the prompt, the
  model and the effort it was told, a JSON schema for the answer (`saved`,
  `blocked` or `not_saved`, and the script's one line), a spending limit, no
  MCP configuration but an empty one of its own (so no connector's tools
  load), the owner's browser (`--chrome`), and no tool but the browser's tabs,
  navigation and script. Nobody is there to approve a browser action, so the
  launcher refuses it and no page is saved this way: it is the launcher for a
  task that needs no approval.

The answer is checked, never believed. After a launcher returns, whatever it
returned, `collect` runs, and the run's outcome is what code finds: `no_answer`
(the launcher timed out, failed or gave no result, and no page came in:
a holder's silence), `invalid` (a result whose answer is not the schema's),
`nothing` (a valid answer and no page), `mismatch` (a page came in and did not
reach the entry's steps: its own identity is another record's, or `collect`
left it), and, for a page whose own identity is the step's, what the attach
made of it: `unread`, `none`, `read`, `card` (the matcher's proposals wait for
the owner) or `taken` (the rule took one). Only a file that came into the folder
while the launcher ran is the task's: one `collect` took that was there before
the task opened (saved earlier by hand, or put back by an attach that failed) is
attached as any page saved by hand is, and the run's note names it as not the
model's; a task that produced more than one file says so, with their names. No run is logged on a step on the
model's word: a `blocked` answer leaves the step as it stood, and the run's
row says what the model reported. Where the report and the finding differ (the
model says saved and no page of the step's came in, or says not saved and one
did), the row is marked and its note says how.

Every launch is a row of `task_run`, insert-only: the launcher, the kind of
task, the holder, the steps, the task as rendered, the text's sha256, the
model and the effort, what the launcher measured, how the run ended (the
launcher's own terminal reason, or `timeout`, `exit <n>`, `no result`), the
answer, the outcome, and the `search_log` row the page's attach wrote. The
headless launcher reports tokens in and out, cost, turns, time, per-model
usage and the tools it refused; a session is given one token count, the tool
uses and the time, and the other columns stay empty. The total of tokens is
the one measure both give. These measures say what a task costs at a model
and never reach a card. `tools/run_task.py show` prints the rendered tasks
and launches nothing; which model a task gets is the caller's to say on the
command line, and a gravestone photograph (`tools/save_image.js`) is not yet
a task.

**When the site blocks the fetch.** When a source answers a page save or a
search in the owner's browser with a challenge or a sign-in (the script's
`BLOCKED` line), the session notifies the owner and waits; once the owner has
passed it by hand, the session continues. The session never passes a challenge
itself, and a challenge does not by itself make the source assisted-only.

**The image saves itself.** A gravestone photograph on a memorial accepted as
a person's own (by the owner or by the rule) is a fetch step of its own under
the cemetery row, one per photograph the page types Grave, with the image's
URL as its locator and the page's words (the memorial, the photograph's id,
its caption and type) as its fields; `tools/fetches.py list` prints it with
the file name to save under and says it is an image. Open the image's own URL
in a new tab and run `tools/save_image.js` in it with the name filled in: the
tab fetches its own bytes and hands them to the browser as a download, and the
script's one line says `ok image <type> <bytes>B` or `BLOCKED <why>` (nothing is
saved when the answer is not an image: a challenge or a sign-in comes back as a
page); the script is one awaited call, as the page's is, so the line comes back;
`collect` moves it to `inbox/` and attaches it to its step by that name (an
image carries no identity in its bytes; a second download of one name, Chrome's
` (1)`, or the free name a file of its name in the inbox gives it, ` (2)`, is
the same name), archived under the gravestone row
(E05, tier 1) with the image's URL as locator, logged found, never parsed. It
is read one person at a time by the transcription path, the screen's form or
the model, into a card like any other image.
`tools/attach_inbox.py` then takes every file in `inbox/`: it reads the
record's own identity from the file (the memorial id, the ark), archives it
once, logs a found run on every fetch step whose citation carries that
identity (a record page a listing pointed at reaches the lead its row made and
the steps the listing was logged on, for the person its row fits), marks the step done when
the page is the record it cites, and runs the extractor and matcher once; the screen's own attach
does the same for the step the person chose plus every other step the record
fulfils. A file whose identity matches no step stays in the inbox. Collect
and the inbox's attach take one file per transaction: a file whose attach fails
is rolled back alone, named with the failure, and left where it was (a page
taken by its name in `downloads/`, any other in `inbox/`) for the next try,
the files before and after it attached. An object the failed try already
wrote into the archive is harmless: the archive is content-addressed, so the
next try writes the same bytes under the same hash, with its artifact row.

**A link on the owner's word.** When a record stops short of naming both
parties in full (a marriage index that gives the spouse's surname by four
letters), the owner can place a person in a family on their own word about
that record (`decisions.link_on_word`): the membership carries one Accepted
assertion on the artifact, vouched, with the owner's reason, and a marriage
the record dates becomes the couple's Marriage event on the same evidence. A
divorce is a `Divorce` event on the couple's family (`decisions.divorce`), dated
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
statement) on the owner's word about whom it concerns
(`tools/attach_inbox.py <file> --about "<person>"`), filed under the tree,
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
extractor makes one persona per row. The audit is the matcher's own
comparison of every row with the person, dates compared as dates (a different
day in the same year disagrees, and so does a different month where both give
one; a bare year against a full date agrees on the year only and says so): a row fits when the given name and the surname agree
with a death date, a place or a birth date to the day, and nothing compared
disagrees. No row is proposed as a card. A row that fits is a lead, a fetch
step for its own memorial on the person's plan, saved by the one-call method
and attached like any memorial; a row that agrees on the name alone, or fits
nobody, stays a candidate on the page, and the candidate card lists every row
with its fields as agrees, disagrees or absent, its memorial URL and the lead
a fitting row made. No fit at all sets the run to `none`. Nothing is fetched by
the audit. A second page of results is a second run of the step, never
automatic.

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
relatives it names, and the matcher's comparison reads every row as it reads a
memorial search's. A row that fits is a lead, never a card: the plan, written
again for the person when the page is attached, gives the row's own record a
fetch step. The listing points at a record and is not one, so the run is found
with the page, the fetch step it was saved for stays planned, the row is not
held, and the row's own record page takes the search link's place on the fetch
list; saved by the same method, it reaches the lead and, through the listing
that pointed at it, the step, is archived under the step's citation, and
closes both. A page of a household's own search (§3, `docs/HOUSEHOLDS.md`) reaches
the household's search step by its own fields as well as by the list's key,
whatever page of the answer it is: the collection, the surname, the place and
the year, and no given name; the plan is written again for the people whose
household lead a page reached, so the search's next page and the next
candidate are on the list before anyone asks. A candidate's record page reaches
its step by the key and by its ark, never the household's search, which a
record of one row does not answer. A fetch step is done only when a record page holds its
citation; a done step whose found runs hold only listings or pages no parser
read (a hand's found run) is planned again by the plan, and a page no parser
reads is logged `unread` by the attach, never found, and closes no step, nor
does a connector's answer of records no parser reads, a page or a JSON or text
response alike (below). When
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
death, rank, branch, war period, cemetery, section and site; a dependent's row
names the veteran the dependent is buried with, a persona of the row related as
written, and its rank and branch are the veteran's),
`nj_death_index` on C09 (the New Jersey death index 2001-2017 as Reclaim The
Records' CSV files on the Internet Archive, fetched whole and read locally;
the death record row alone, since C09 sits on the birth and marriage rows
too; the surname's own rows out of the whole file are the record, a none run
when none fits anyone), and `ky_vital_index` on C06 (the Kentucky death and
birth indexes 1911-1989 as Reclaim The Records' plain-text files on the
Internet Archive, one a year, fetched whole and read locally; the death and
birth record rows of a Kentucky event, the step's year alone when the tree's
year is accepted and the year either side when it is claimed, a search step's
year equal to its birth year being the birth row's; the surname's rows whose
given name shares the step's first letter are the record, and on the death row
the other surnames the person's names carry are asked too; a fetch step only
when its citation of either index names its year, which the file's own
citations do not, so those stay at FamilySearch first and are logged none at
C06 with the year wanted).
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
hash, and the extractor and matcher run on each hit's record. The run is
logged before its records are read, so one whose records are all records no
parser reads, whatever their form (a web page, a JSON or text response; an
image or an item's metadata is never read as a record), is then set to
`unread`, as the attach logs a page no parser reads saved by hand: the records
are held on the step's log, the note says so, and no step is closed, the other
household members' steps a census page was logged on included.
A run with any record a parser reads is `found` (or, when every record is a
results listing none of whose rows fits anyone, `none`) as before. `found`
means a hit's record or image arrived: a hit none of whose records arrived (the
1950 schedule and its image both timed out, an Archive item's metadata failed,
named no server or could not be read) is a request the source did not answer,
its name logged unanswered and the next name tried, and a run whose hits are
all such is logged `error`, the step asked again and no household member's step
logged. A run that
fails is an error run, never a stop: when the reading or the matching of its
records raises (a parser or the matcher failing on a record), what the reading
wrote is rolled back, the run's own row and the responses it archived are
kept, and the run is restated as `error` with the exception in its note, every
step it was logged on back to the status it had; when the connector raises
before the run is logged (it cannot build its requests from the step's fields),
what it wrote is rolled back and an `error` run with the exception in its note
is logged in its place. Either way the step stays runnable at that source, as
for a source that did not answer, and the runner goes on to the next step.
A place field that carries several names (§3) is tried one name at a time, in
that order, and the run stops at the first name that gets a hit. The requests a
name makes are built before any is sent, and a request already made on the run
is never made again: a connector that reads a place only as a state and a
county (the 1950 census site, loc.gov), or not at all (the Archive's
newspapers), builds one request for two names of one place, which a
rate-limited holder cannot answer differently, so the second name is logged as
tried and sends nothing, the run's note saying which name's request it
repeated. Every name tried, asked or not, is on the logged run's
query, and so is whether the run stopped at a hit. A name one of whose requests
the source did not answer (a timeout, a challenge, a refusal), or whose request
repeated such a one, is logged unanswered beside them, and the run does not read
back as the step's own fields: the step is asked again, as a run logged `error`
is. Otherwise a run that tried them all reads back as the step's own fields,
and so does a run that stopped at the name that got a hit, whatever names follow it and whatever the hit came to: a record
found (a fetch step whose hit came from a connector other than its holder stays
planned for the holder's own page), a book the Archive only lends (a `none`
run), a listing none of whose rows fits anyone (a `none` run), and that
connector is not asked the same query again. A name added or dropped before the
one the run stopped on, or added after a run that tried them all, is a change in
the step's fields, and the step is asked again. A run logged before the mark
existed reads by its outcome: found stopped at its hit, none tried every name.
The runner runs a fetch step the same way when the citation's free holder has a
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
outcome (`found`, `none`, `blocked`, `error`, `unread`), artifacts produced.
"Searched the 1880 census of Worcester Township for Brant, none found" is
evidence and stays. `found` is a record or page archived and read; `unread` is
a record archived that no parser reads, whatever its form, a web page or a
connector's JSON or text response (its every extraction failed, no reading of
it by the model or a person; an image is read by the transcription path, never
by a parser, and is not this case), whether the attach saved it from the
browser or a connector's answer was archived: held on the step's log, the step
stays planned, and what a program can rely on is that nothing was read from it.

A `missing_fact` or `unverified_claim` question is about the absence of a
claim, so it closes as answered the moment an accepted document supplies the
claim; the document's assertion is Accepted with the document, and a value that
differs from the tree's is a `conflict` question, not a silent change.
