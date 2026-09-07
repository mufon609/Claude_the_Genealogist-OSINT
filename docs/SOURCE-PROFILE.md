# What is in the tree, and what to borrow

Measured on the Ahearn import as a file: 117 persons, 43 families, 418 events,
1,225 record citations, 69 Ancestry collections. The file's claims are a guide
to where records are; they are never the work list.

## 1. Foundational facts: who has them, and how many are backed by a record

| Fact | Persons who have it | Backed by ≥1 record citation | Claimed with no record |
|---|---|---|---|
| Name | 117 | 114 | 3 |
| Birth (date or place) | 102 | 85 | 17 |
| Birth place resolved to a real place | 73 | | |
| Death | 77 | 63 | 14 |
| Burial | 55 | 55 | 0 |
| Residence | 49 | 48 | 1 |
| Parents known | 75 | | 42 dead ends |
| Spouse known | 80 | | |
| Marriage event on the family | 20 of 43 families | **3** | 17 |
| Baptism / Probate | 1 / 3 | 1 / 3 | 0 |

Two things stand out. Burial is the best-sourced fact because Find a Grave is
cited everywhere. Marriage is the worst: 40 of 43 couples have no marriage
record, and marriage records are exactly what name parents and maiden names.

## 2. Which kinds of source carry which facts

| Source family | Persons touched | Facts it supplies here | Tier |
|---|---|---|---|
| Burial (Find a Grave, cemetery, veterans' gravesites) | 54 | Burial 55, Death 44, Birth 41 | T3 |
| Compiled (family history books, Family Histories 1500–2000, SAR applications) | 52 | Birth 25, Death 10, Marriage 3 | T3 |
| Vital (PA/MA/KY/TN/NJ/OH births, deaths, marriages, church & town) | 51 | Birth 42, Death 29, Marriage 2, Baptism 1 | T1/T2 |
| Census 1790–1950 | 43 | Residence 94, Birth 64 | T1 |
| Military (draft cards, enlistment, pensions, veterans files) | 19 | Residence 8, Birth 6 | T1/T2 |
| Probate / land / tax | 13 | Probate 3, Residence 4 | T1 |
| Newspaper (obituary index, obituary collection) | 10 | Birth, Death, Residence, Burial 5–7 each | T3 |
| Social Security (SSDI, applications & claims) | 5 | Birth 2, Death 2 | T2 |
| Directories / voter registration | 5 | Residence 4 | T2 |
| Immigration / naturalization | 3 | Arrival 2, Birth 2 | T1 |

Top single collections: Find a Grave (229 citations, 54 persons), Family
History Books (63, 26), North America Family Histories (61, 28), then the
1880/1910/1920/1940 censuses (43–46 each), PA death certificates (37, 14).

**Source strength per person:** 76 people have at least one primary or
official source. 38 rest only on compiled books, Find a Grave, or obituaries.
3 have no record citation at all (the duplicate Thomas Ahearn, George R and
Neely Dobson McCrary).

**Where and when the tree lives** (births with a resolved place): Pennsylvania
1700s and 1750s (Schwenkfelder/Mennonite), Pennsylvania, Massachusetts and
Kentucky 1850s, Massachusetts and New York 1900s, Ireland 1800s. That is the
record landscape every search plan must be tuned to.

## 3. Real examples: fact → source

**Abram C. Brant (1880–1961)** — parents Abraham B. Brant & Sarah Cassel; spouse Charlotte D. Lukens

| Fact | Value | Found in |
|---|---|---|
| Birth | 20 Sep 1880, Worcester Township PA | PA death certificate, PA birth certificate, 1910 & 1920 census, Find a Grave, Family History Books |
| Residence | 1910 Philadelphia; 1920 Warwick Twp | 1910 census; 1920 census |
| Death | 10 Oct 1961, Pottstown | PA death certificate, Find a Grave |
| Burial | Norristown | Find a Grave |
| Marriage | — | **none** |

Well-sourced person; the gap is the marriage record (which would confirm
Charlotte's parents) and the 1900 census (the one census he is missing).

**Helen Sara Brant (1909–1986)** — 11 sources on her birth alone (census ×3,
church record, SSDI, birth certificate, marriage, obituary, Find a Grave, books),
a baptism at Penns Park in 1918 from the church-and-town collection, residences
1910–1956 from census and SSDI, death from SSDI, Find a Grave and obituary.
This is what a finished profile looks like in this tree.

**Frederick Michael Ahearn (1907–2001)** — birth backed by the MA birth record,
WWII draft card, three censuses, SSDI, marriage and Find a Grave; residence
trail 1910 Northampton → 1940 Caln Township → 1961 New York → death Boca Raton.

**Thomas Ahearn (1846–1902), the well-sourced one** — parents James Ahearn &
Johanna Barry; birth from MA death and marriage records and two censuses;
residence 1870, 1880 Sunderland; death and probate 1902 from MA records.
**His duplicate** (same birth date, spouse Alice McGee) has zero citations and
no parents. The tree owner built the same man twice.

**Minerva E (b. Feb 1815 Tennessee)** — no surname, no parents. Everything
known comes from the 1850 and 1870 censuses (household of Robert Powell
McCrary); her death "aft 1900, Lampasas County" is uncited. Her surname is in
records about her children (Kentucky death certificates already cited on them).

**David St Johns Heebner (1696–1784)** — Schwenkfelder immigrant. Birth and
death from the Lancaster Mennonite Vital Records only; burial from Find a
Grave; no parents; five conflicting marriage entries. Everything before 1734
is in Silesian and Saxon records this tree has never touched.

## 4. What to borrow from the other genealogy UIs

| From | Pattern | Why it fits our design |
|---|---|---|
| Ancestry person page | **Facts in the middle, Sources on the right, and a line drawn between each fact and the sources that support it** | it is exactly `event ← assertion ← record`; ours adds the three-state status on the line |
| FamilySearch | **Attach a source to a person**, and the "reason this is correct" box when you change a conclusion | the document is the decision and its facts come with it; the box is the decision note. Not borrowed: ticking facts one by one |
| WikiTree | **Unsourced / needs-research flags** on a profile and a plain-text research-notes section | our Undecided state made visible; the research log lives with the person |
| MyHeritage | **Consistency checker**: a list of contradictions per tree (child born before parent, five marriage dates) | our `conflict` and `duplicate_person` questions, generated not typed |
| Gramps | **Evidence model**: citation belongs to a source, source belongs to a repository; places are a hierarchy with dated names | already in the schema; keep it visible in the UI |
| All of them | **Suggested records / hints per person** | keep the idea, but only after the person's baseline is reviewed, and framed as answers to that person's questions |

What not to borrow: shaky-leaf hints on unreviewed people, member-tree
suggestions as evidence, and any score badge.

## 5. The person screen (the only screen that matters first)

```
┌ Person ──────────────────────────────────────────────────────────────────────┐
│ Abram C. Brant  1880–1961          parents: Abraham B. Brant, Sarah Cassel    │
│ status: 0 of 7 key facts Accepted  spouse: Charlotte D. Lukens               │
├ Facts ───────────────────────────────┬ Sources ─────────────────────────────┤
│ Birth  20 Sep 1880 Worcester Twp     │ PA birth certificate 1906-1917  [T1] │
│        ● Accept ○ Reject ○ Undecided │ PA death certificate 1961       [T1] │
│ Death  10 Oct 1961 Pottstown         │ 1910 census · 1920 census       [T1] │
│ Burial Norristown                    │ Find a Grave                    [T3] │
│ Marriage — (no record)               │ Family History Books            [T3] │
│ Residence 1910 · 1920                │                                      │
├ Questions ─────────────────────────────────────────────────────────────────┤
│ • Marriage to Charlotte D. Lukens is unrecorded → PA marriages 1852-1968    │
│ • Missing from the 1900 census → search Worcester Twp / Philadelphia 1900  │
│ • 6 record citations not yet fetched → fetch, then review each fact         │
└─────────────────────────────────────────────────────────────────────────────┘
```

One person. Facts on the left showing the status their documents gave them.
Sources on the right, tiered, each linked to the facts it supports; the source
is what is decided. Questions underneath, each with the next concrete step.
Nothing else on the first screen.

This is the same screen as `docs/RESEARCH-CHECKLIST.md` §6, which is the
authoritative description: the facts-and-sources block is its *foundation*
region, and the questions are its checklist *tasks*.

## 6. Splitting the work between agents / skills

The split follows the source families in section 2, because each family has
its own access path, its own record shape, and its own way of naming relatives.

| Agent / skill | Sources (registry IDs) | Produces | Ladder rungs |
|---|---|---|---|
| **Owner** (deciding documents; the standing rule deciding the certain ones) | the held records | a record Accepted or Rejected as the person's, its facts with it | before anything |
| **Footprint** | the catalog itself | for a question: ranked records already attached to relatives; duplicate check | 0 |
| **Census** | D01–D05 | households, ages, birthplaces, co-residents → candidate parents/spouses | 1, 3 |
| **Vital & church** | C01–C11, I01–I09 | parents' names, maiden names, exact dates; Schwenkfelder/Mennonite/Dutch/Irish registers | 1, 2 |
| **Burial** | E01–E04 | death/burial dates, family plot links; T3, always to be confirmed elsewhere | 2 |
| **Newspaper** | H01–H06 | obituaries: survivors, maiden names, places | 2 |
| **Compiled & books** | L01–L03, DAR/SAR | hints (never proof); full-text search of published genealogies | 2, 5 |
| **Probate, land, tax** | J01–J04 | heirs, relationships pre-1850 | 2 |
| **Migration** | G01–G05, I04–I09 | origin village, arrival, naturalization; the Silesia→PA and Ireland→MA jumps | 2, 4 |
| **Place** | N01–N07 | resolves strings, keeps jurisdiction history (Montgomery Co. 1784, Norriton 1909) | support |
| **Names & aliases** | O01–O04 + `alias` | variants, phonetic keys, query expansion | support |
| **Fetcher** | the free holders of cited collections (FamilySearch, Find a Grave, the National Archives; Ancestry is a citation source only) and assisted sources (Newspapers.com) | the holder's link and the citation's own details as "what to look for"; archives what the user drops in `inbox/` | all |
| **Extractor** | archived images / index JSON | personas and facts from a record (index parse, OCR/HTR, LLM reading) | all |
| **Matcher** | personas vs tree | proposals that answer a question | all |
| **Research log** | every search | outcome incl. negative results | all |

Each agent has a narrow contract: given a question and the Accepted baseline,
return either archived records plus personas, or a logged negative. None of
them changes a conclusion. Only the review step does.
