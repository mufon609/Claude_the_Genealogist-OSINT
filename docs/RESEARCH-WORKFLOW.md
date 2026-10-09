# Research workflow

The app does not start from records and it does not start from hints. It starts
from what the family already knows and has approved, turns the gaps into
questions about people, and works each question down a ladder of searches that
does not need a name until a name has been found.

```
 ┌──────────┐   ┌───────────┐   ┌──────┐   ┌────────┐   ┌─────────┐   ┌───────┐   ┌────────┐
 │ BASELINE │ → │ QUESTIONS │ → │ PLAN │ → │ SEARCH │ → │ EXTRACT │ → │ MATCH │ → │ REVIEW │ ─┐
 └──────────┘   └───────────┘   └──────┘   └────────┘   └─────────┘   └───────┘   └────────┘  │
      ▲            (auto)        (generated)     (auto/assisted,  (layer 3)   (proposals    (person-      │
      │                                           logged)                     answer a Q)    centred)     │
      └────────────────────────────────────────────────────────────────────────────────────────────────┘
```

The workflow is stated in five parts, one file each.

- [Terms and the decision model](TERMS.md) (§0, §1, §2): the terms a claim, a
  lead and a hint; which documents the rule may accept on its own, with the
  table of each kind's standing; the baseline of what is known and approved;
  and the questions generated from its gaps, with the merge that settles a
  duplicate.
- [The plan and the search](PLAN-AND-SEARCH.md) (§3, §4): the search ladder
  and the family footprint, the plan's fetch and search steps, the modes of a
  search, the page that saves itself and the fetch list, a model saving the
  page, the connectors and the runner, and the research log.
- [The rule](RULE.md) (§5–7): extraction and matching, what accepting a
  record writes, what of an event's value is accepted, one event folded, the
  standing rule with the name, the route through a stated relationship and
  creation, a page anyone can edit, identity tested, the limits of one life,
  rejection, withdrawal and `reconsider`, the conflicts, and the proof
  standard.
- [Households](HOUSEHOLDS.md): a census household read off its form, what it
  misses named, and the missing entries fetched one candidate at a time.
- [The loop](LOOP.md) (§8 onward): a turn, the queue, the resume and the
  runner; the worked example; the schema of questions, steps and the log; and
  the rules that hold throughout.
