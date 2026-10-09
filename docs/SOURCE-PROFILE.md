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
| Burial (Find a Grave, cemetery, veterans' gravesites) | 54 | Burial 55, Death 44, Birth 41 | T4 for Find a Grave; T1–T3 for the rest (§6) |
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
│ Burial Norristown                    │ Find a Grave                    [T4] │
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

## 6. How the work splits across the tools

The work splits by what each part does; the source families in section 2
decide only which registry rows a checklist row searches.

| Part | Where | Does |
|---|---|---|
| The owner | the person screen, `tools/conclude.py` | decides documents (is this record about this person) and every card the rule leaves; their own word on a fact, a link, a place or whether a person is alive |
| The standing rule | `tools/conclude.py` | takes the decisions the owner's written rules make certain, on their word and reversibly (`docs/TERMS.md` §0, `docs/RULE.md`) |
| Checklist and plan | `tools/checklist.py`, `tools/footprint.py`, `tools/plan.py` | the records that should exist and the gaps; a fetch step per citation or lead, a search step per missing row, the family footprint first |
| Connectors | `tools/connectors/`, `tools/run_step.py` | one module per free source with an endpoint (loc.gov, the 1950 census site, the Internet Archive's newspapers, directories and books, WikiTree, the VA gravesite locator, the New Jersey death index, the Kentucky death and birth indexes); every response archived, every run logged |
| The owner's browser | `tools/fetches.py`, `tools/save_page.js`, `tools/save_image.js` | the pages a source without a connector serves (FamilySearch, Find a Grave), saved one at a time and collected by their own identity; Ancestry is a citation source only |
| Extractor | `tools/extract.py` | personas, facts and relations from an archived page or response, one parser per page kind; an image read by the model, or by a person on serious doubt |
| Matcher | `tools/match.py` | proposals that answer a question, the rationale in words |
| The loop | `tools/queue.py`, `tools/turn.py`, `tools/turns.py` | the next person at the edge of the confirmed tree, their plan run end to end, then the next |
| Places and names | `tools/resolve_places.py`, `tools/backfill_aliases.py` | place strings resolved, with a place's dated names; the names records write as aliases |
| Research log | `search_log` | every run, including nothing found |

Burial sources by tier (`data/data-sources.csv`): Find a Grave memorials and
BillionGraves (E01, E02) are user-contributed pages (T4), identities and
leads, never facts; the VA gravesite locator (E03) is T2; cemetery
transcriptions (E04) are T3; a memorial's gravestone photographs (E05) are
primary sources (T1).

No part changes a conclusion but a decision: the owner's, or the standing
rule's on the owner's written terms.
