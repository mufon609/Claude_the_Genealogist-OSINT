# From a file in the inbox to a card in front of the owner, with no hand steps between

You are the worker session. Read `CLAUDE.md`, `MEMORY.md`, `docs/AUDIT-PROMPT.md` and `docs/DIRECTOR-HANDOVER.md` first. Cited Find a Grave memorials now arrive in `inbox/` by the page-saves-itself method in `docs/RESEARCH-WORKFLOW.md` §4, six of them already for the owner's approved family. Today each file is attached by hand: someone finds the step, posts the log, and reads the proposals out of the database. The owner will not have data pile up without a process, so this brief closes that gap: a file in the inbox is attached to every step it fulfils, extracted, matched, and rendered as decision cards, by one tool, with nothing typed in between. The owner decides on the cards; the director records the decisions.

Every test runs under a scratch `DATA_ROOT` with a scratch `--db`. The live catalog and the real `inbox/` are not touched; copy the inbox files into the scratch inbox.

## Phase 1: attach by identity

1. `tools/attach_inbox.py [--tree] [file ...]` (all inbox files when none are named): for each file, read the record's own identity from the file, not from its name: a Find a Grave memorial id from the memorial's own markup, a FamilySearch ark from the record page. Find every fetch step in the tree whose citation carries that identity (the memorial URL in the step's fields; for an ark, the artifact locator once the record is archived, else the collection and details). Archive the file once through the same path the screen uses (the attach in `app/person/server.py`, moved into a module both can import so the screen and the tool are one code path), log a found run on every step the record fulfils, and run the extractor and matcher once, after the log rows exist, so the matcher sees every person the record was fetched for. A file whose identity matches no step is left in the inbox and reported, not archived. Print one line per file: identity, steps fulfilled with their people, artifact hash, extraction id, proposals written.
2. The attach sequencing defect (the matcher ran before the log row existed) is fixed by this ordering if it is not already fixed in your earlier phase; either way the test below proves it.
3. Test on scratch with the six memorials in the inbox: every step sharing a memorial is done and held, each proposal carries the step and question of a person the record was fetched for, a second run changes nothing, integrity and foreign keys clean.

Commit Phase 1.

## Phase 2: the card

1. `tools/cards.py "<person>"` (and `--all` for every person with an Undecided proposal) prints each Undecided proposal as one card in plain text, in the shape the owner approved (`docs/DIRECTOR-HANDOVER.md`, the decision card): a one-line highlight of what the record is and the links it makes; the person and the fact or link with the file's claim; the record with holder, collection, own identity and trust tier; the primary document, as the archived path and the holder's page; the fields as agrees, disagrees or absent, taken from the matcher's rationale and the persona facts; the relationships the record states and who on it is already matched or accepted; what accepting would close, computed from the person's open questions and steps; anything odd. No scores, no counts dressed as scores. `--json` gives the same card as data for the screen later.
2. The screen's proposal panel shows the same card from the same function, so the two never drift.
3. Test on scratch: the cards for the six memorials, verbatim in the report. The director reads those cards to the owner.

Commit Phase 2.

## Phase 3: the loop after a decision

1. Deciding a card (the existing proposal decision) already regenerates the plan and closes questions. Add what the owner asked to see: the decision's response names what closed and what the plan does next, so the director can say it in one line.
2. Test on scratch: accept Noi Davidson's memorial match and read back what closed; accept Raymond Earl Davidson's; reject one new-person proposal; a re-run of `attach_inbox.py` and `cards.py` afterwards shows the remaining cards only.

Commit Phase 3.

## Rules

Plain over clever: one attach path, one card function, both shared by the tool and the screen. Nothing Accepted without a person. Commit per phase with the guard installed. Report in the usual shape with the six cards verbatim and one line per file attached.
