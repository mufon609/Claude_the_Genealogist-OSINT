"""Connectors: one small module per free source with a documented endpoint, run by tools/run_step.py.

The contract, and nothing else:
  SOURCE      the registry id (data/data-sources.csv) the connector runs against; its row's Connector column names the module.
  COLLECTION  the collection name archived responses are filed under.
  RATE        {kind: requests per minute} the source documents, per request kind; the runner paces to it.
  requests(fields) -> [{"url": ..., "kind": "search", ...}]
              the requests a search step's rendered fields turn into, without sending them (--dry-run shows these); anything
              else on the request (a year window, the words searched) comes back to hits(). Three keys the runner reads:
              "data": {field: value} is posted to the url as a form, for a source whose search only posts; "locator" is the
              identity the response is archived under when the url alone does not carry the query (a posted search);
              "record": True says the response is itself the record (a results page listing what was found), read by the
              extractor as a hit's own record would be.
  total(body) -> int or None
              how many results the source says it has for the request, from the response bytes; goes in the log note.
  hits(url, body[, request]) -> [hit]
              the records a response names, from the response bytes; each hit is
              {"label": text for the log, "locator": {"kind", "value"}, "notes": {... what the response said about the record ...},
               "fetch": [{"url", "kind": "json" | "text" | "image"}]}: the record's own transcription, text or image to archive.
              A fetch with "record": False is archived but not read as a record (an item's metadata). A fetch may carry
              "then": a name for follow(). A fetch computed locally from a response already in hand (a surname's own rows out
              of a whole downloaded file) carries "bytes": the content itself, so the runner archives it without a request of
              its own, and "derived_from": the sha256 of the artifact it was computed from (request["archived_sha"] carries the
              current top-level request's own sha256 once archived, for hits() to read); when the request has one, the request
              dict passed to hits() carries it too.
  Optional:
  ROWS        the checklist rows (the record part of a step's row_key: "death record") the connector answers a search step
              for, when its source's row covers more kinds than the connector reads (a vital-records row whose connector
              reads the death index alone); without it the connector answers every search step its source is on. A fetch
              step is gated by its citation's own collection in requests() instead.
  next_page(url, body) -> url or None    the next page of the same search while the source's total stays small.
  narrow(url, body) -> text or None      what the step needs when the source answers with too many results.
  follow(fetch, body, hit) -> [fetch]    more to fetch once a response is in (an item's metadata names the server its pages
                                         are read from); applied to every fetched response, so a chain can be followed.
The connector never opens a connection: the runner sends every request with treelib.USER_AGENT, archives every response as it
came, logs the run, and hands what it archived to the extractor and matcher. A connector's fields are the step's, after the
person's include and revise: given, surname, birth_year, state, death_year, place, year, spouse, parents ... each {value, basis}.
"""
import importlib

def load(name):
    """The connector module named in the registry's Connector column."""
    return importlib.import_module(f"connectors.{name}")

def answers(name, record):
    """Whether the connector named answers a search step on this checklist row: every row unless the connector declares ROWS,
    then only those. record: the row's record name, or a row_key ("death record:" and "death record" alike)."""
    rows = getattr(load(name), "ROWS", None)
    return not rows or (record or "").split(":", 1)[0].strip().lower() in {r.lower() for r in rows}

def value(fields, key):
    v = (fields or {}).get(key)
    return v.get("value") if isinstance(v, dict) else v
