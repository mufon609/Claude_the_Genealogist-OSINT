# Households

**[rule.household.1]** A census household is read off its form (`docs/DATA-ARCHITECTURE.md` §7
decision 21), by code: `tools/households.py` groups the entries of every
current census reading, each persona whose region keeps its place on a form
(`data/record-forms.csv`), and stores the households insert-only with its
version (`household`, `household_member`). No tree's decision goes into a
household; nothing the rule decides reads one yet (the calibration and the
rule's reading come first, `BACKLOG.md`). The rules:

- **[rule.household.2]** **One entry, one member.** An entry is one member however many copies carry
  it: the same record id wherever it is read (a FamilySearch entry's ark, on the
  head's page and on a child's), one line of one image however many readings
  read it, and an entry of one copy that is an entry of another copy of the
  same record (decision 15: code's joins, the entry by its record id, else by
  its name). Each copy's persona of the member keeps what that copy states.
- **[rule.household.3]** **A FamilySearch record page is one household.** Its persons are one record
  of the index: one household under one household identifier, the page's own
  person and every member it lists. A federal household is FamilySearch's
  record, its page the district and sheet; FamilySearch's line is never read
  on a federal form, since every member of the 1900 Lukens record page, the
  page's own person too, carries line 10 while the sheet's image has Milton on
  line 4 and Charlotte on line 7.
- **[rule.household.4]** **On one page, a run of lines.** Where the form bounds a household by a run of
  lines (its `household` column: opened by the head's line, or by the line
  carrying a family number, running to the next), the entries of one page are
  grouped by the line the form's `lines` column reads: a reading's own line down
  its image, and the copy's Line Number only where the column names it (the
  1925 New York index, one person to a page), and then only the page's own
  person's. A page is the image a reading is of, or the form's page locators all
  held alike: for the 1925 New York form the county, the assembly and election
  districts and the page, the county the copy keeps with the districts (the
  reader reads it off the place restated with them, "Hempstead, A.D. 01, E.D.
  06, Nassau, New York"), or, where the copy's locators lack it, off the entry's
  census residence. Two entries of one page with no held head or
  numbered line between them are one run when every line between them is held,
  or when they share a surname as written; across a line not held, and only
  then, the surname is what ties them.
- **[rule.household.5]** **No head held.** A run that holds no head is a household under a head not
  held. The 1925 New York pages of Mary Peters, Wife, line 23, and of Ruth
  Peters, Daughter, line 25, on page 19 of assembly district 01 and election
  district 06 in Nassau, are one household under a head not held, missing the
  head and line 24, not two. The form opens a household only at a head's line
  (the head first, then the family), and each of them states a relationship to
  a head, so each stands in a run some head above her opened; nothing held opens
  a run between lines 23 and 25, so the only way they are two is that line 24,
  which is not held, is a head. A line not held is named missing and never taken
  for a head or for a member; what ties the two across it is what the entries
  themselves state, the one surname they share. Two entries of different
  surnames across a line not held are not tied: each is a household of its own
  under a head not held. When the head's entry and line 24 are held the
  households are grouped again, and if line 24 opens another household, they
  split then.
- **[rule.household.6]** **The head alone, one schedule.** A form that names the head alone (1790 to
  1840) is one line to a household, its entry the head; a reading of the 1890
  form, one schedule to a family, is one household to an image.
- **[rule.household.7]** **What no rule places.** An entry no copy groups and no line places is in no
  household: the 1950 census site's machine reading, which gives no
  relationship and a row the form's rule does not read (of the thirty entries
  it reads off one Nassau schedule, it gives seven row 1 and twenty-one none).

**[rule.household.8]** Each member keeps its relationship to the head as its copy states it, as
written: the Relationship to Head of Household field, a relation the record
states toward another person of its reading (a census states the relationship
to the head alone), or a reading's own role word. No other tie among the
members is stated: the wife and the daughter of one head are each the head's.
**[rule.household.9]** A household is complete when nothing the form's rule shows is missing: its head
held and, where every member's line is read, no line between the first and the
last missing. What is missing is named, the head first ("the head", "line
24"), and never filled in by guess; a household a record page lists in full is
not missing a member whose line no copy gives. **[rule.household.10]** `tools/households.py show`
prints the households as the script groups them now, and `write` stores them
where they changed; the plan groups them again before it reads them. **[rule.household.11]** A
household not wholly held is a lead on the people a tree ties to it (`docs/PLAN-AND-SEARCH.md` §3).

**[rule.household.12]** **The missing entries fetched.** A household not wholly held leads to what it
misses (`tools/households.py` `answer` and `candidates`, `tools/plan.py`
`household_leads`, the steps `docs/PLAN-AND-SEARCH.md` §3 describes). Its own search, FamilySearch's
collection searched by the surname, the place and the year, is saved page by
page: the first page of its answer not held is the step's next save, and the
step goes once every page is held, its log kept. The candidates for the missing
entries are the rows of every results page the archive holds of that collection
for that surname at that place, the household's own search's pages and an
earlier search's with a given name alike (the nine rows of the search Mary
Peters's own citation made count beside the hundred and twenty of the
household's), each row once: a row is a candidate when it carries the
household's surname as written and its place (the minor division and the
county), and its own record page is not held.

- **[rule.household.13]** **Left out.** Where the head alone is missing, a row whose birth year the
  form's household rule and the life limits rule out for the head. The form
  states each member's relationship to the head, so the head is the parent of
  a member stated son or daughter and the child of one stated father or
  mother, and a row born where that parent or child cannot be by
  `data/life-limits.csv` (`catalog.parent_limit`, the row's sex unknown and so
  the wider bounds, and only what holds over every year a calculated age can
  stand for) is no head. Where a line is missing too, such a row stays, a
  candidate for the line alone: a line not held can be anyone. For Ruth Peters's
  page alone, missing its head, the rows of the answer's first page born about
  1914 to 1920 are left out; once Mary's page is held and line 24 is missing
  beside the head, they are candidates for line 24.
- **[rule.household.14]** **The order.** The head's candidates first (`docs/DATA-ARCHITECTURE.md` §7 decision 21: the head's entry
  first), then those for the lines alone, each in the order the household
  itself makes likelier: a record id that differs from a member's in its last
  character alone, since FamilySearch gives the entries of one household ids
  that differ only there (44 of the 46 members of the twelve held census record
  pages that list a household, measured against the page's own person, and
  Mary's and Ruth's 1925 entries on lines 23 and 25, KS4R-RTM and KS4R-RTQ);
  for the head, a name that fits a relative the tree names for the members in
  the head's place (the person it names as the daughter's parent and the wife's
  husband: the file's Fredrick C Peters for the Peters household), the names
  agreed as the matcher agrees them and a birth year within two, which orders
  the candidates and never decides one, and is never a field of the search; for
  the head, a birth year nearer that of the member stated the head's wife or
  husband; a row that gives a birth year before one that gives none; then the
  answer's own order, the household's own search's pages first.
- **[rule.household.15]** **One at a time.** The record page of the first candidate is the one lead
  open (`OPEN_AT_ONCE` is one). The loop never waits on a person who waits on
  pages (`docs/LOOP.md` §8), so a household's next candidate costs that household one more
  round of saving in the browser, and the loop goes on. Every page opened
  beyond the one that holds the missing entry is a page saved for nothing, and
  the order cannot say which page that is: one at a time saves no page the
  household no longer needs, each page saved answering whether the next is
  wanted. What would justify more is a measure the project does not yet have:
  how far down its order a household's missing entries are found, which the
  candidates' steps and their runs record as they accumulate, against what a
  round of saving costs beyond its pages (a page's own cost is what the fetch
  task's runs in `task_run` measure; a round's is recorded nowhere yet); with
  both, the number that saves the fewest pages for the rounds spent follows.
- **[rule.household.16]** **Tried.** A candidate whose record page is held has been tried, whatever it
  showed. Its page's locators place it, on the household's page and in its run,
  where the households grouped again hold it (the household is then complete or
  still missing what it misses: Mary's page saved as a candidate for Ruth's
  household makes it hers and Mary's, missing the head and line 24), or off it,
  where the next candidate's rationale says it was; either way the next
  candidate is opened in its place, the order worked out again on what is held
  then (a page of the answer newly held can put another row first, and a
  candidate opened and never saved then leaves the plan).
- **[rule.household.17]** **When it stops.** Once the missing entries are held the household is complete
  and its leads go. Once every page of its answer is held and the candidates
  have run out, the household stays as stored, incomplete, naming what it
  misses, and leads nowhere more. No page of the Peters household's head is held
  yet, so it has been seen complete nowhere.
