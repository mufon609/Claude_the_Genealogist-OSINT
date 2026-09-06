# After a match is accepted: every fact the record supports is decided, and the record's exact value can become the tree's

You are the worker session. Read `CLAUDE.md`, `MEMORY.md`, `docs/AUDIT-PROMPT.md` and `docs/DIRECTOR-HANDOVER.md` first. The owner's process per person is: the record's match, then every fact the record supports, then the next person. The tool stops after the match. Noi Davidson's memorial is accepted as hers and her name, birth and death are accepted with it as held evidence, but her burial and plot from the same record sit Undecided because the screen decides only the seven key facts, and the cemetery's name and the plot cannot become what the tree says about her burial. This brief closes both gaps.

Every test runs under a scratch `DATA_ROOT` with a scratch `--db`; the live catalog holds the owner's decisions.

## Phase 1: every fact the record supports is decidable

1. The fact decision covers every event type a person has, not only the seven key facts: burial, residence, occupation, military, immigration and the rest, each as a fact with the same three states and the same held-evidence rule. The seven key facts keep their place at the top as the baseline; the others follow under the same controls. A fact the tree has no event for, but a held record states (an occupation, a military inscription), appears as a fact the record offers, decidable the same way; accepting it creates the event from the persona fact, as the match already does for dated facts.
2. One decision per record: on an accepted match's card, "accept the record's facts" sets Accepted on every assertion that record made on the person which does not disagree with an Accepted value, and lists what it did not touch and why (a disagreement, an absent value). The per-fact decision stays for the rest. The card's Closes line says what the one decision would do before the owner takes it.
3. The decision's summary names each fact it accepted.
4. Test on scratch on Noi Davidson from the live catalog's state: her burial and plot accepted from the memorial; "accept the record's facts" on Raymond Earl Davidson's memorial after its match; the disagreement on a birth place left untouched with the reason.

Commit Phase 1.

## Phase 2: the record's exact value can become the tree's

1. When a held record's fact is more exact than the tree's on the same fact (a cemetery name and plot against a town; Babylon against Suffolk County; a full date against a year), the card offers "take the record's value" beside Accept: the tree's event takes the record's date or place as its value, the earlier value stays as the file's claim on its own assertion, and the change is an audit row naming the record. The place goes through `place_string` like any other; the plot and an inscription are the event's detail. Nothing is taken automatically.
2. A record's value that disagrees with an Accepted value is never taken by this control; it stays a disagreement on the card and in the persona facts, with the decision note as the owner's word on it. That is the home for a field-level disagreement inside one fact, as with Noi's birth place; no new state.
3. Test on scratch: Noi's burial takes the cemetery and plot from the memorial; Raymond's birth takes Babylon; a second run offers nothing more; the file's claim remains visible as its own row.

Commit Phase 2.

## Rules

Plain over clever: the same three states, the same held-evidence rule, no new table if a column will do. Nothing Accepted without a person; "accept the record's facts" is one decision by the person and is recorded as such on every row it touches. Docs: `docs/RESEARCH-CHECKLIST.md` §1 and §6b say which facts are decidable and what the two controls do. Commit per phase with the guard installed; report in the usual shape with the rows verbatim.
