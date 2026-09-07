"""Connectors: one small module per free source with a documented endpoint, run by tools/run_step.py.

The contract, and nothing else:
  SOURCE      the registry id (data/data-sources.csv) the connector runs against; its row's Connector column names the module.
  COLLECTION  the collection name archived responses are filed under.
  RATE        {kind: requests per minute} the source documents, per request kind; the runner paces to it.
  requests(fields) -> [{"url": ..., "kind": "search", ...}]
              the requests a search step's rendered fields turn into, without sending them (--dry-run shows these); anything
              else on the request (a year window, the words searched) comes back to hits().
  total(body) -> int or None
              how many results the source says it has for the request, from the response bytes; goes in the log note.
  hits(url, body[, request]) -> [hit]
              the records a response names, from the response bytes; each hit is
              {"label": text for the log, "locator": {"kind", "value"}, "notes": {... what the response said about the record ...},
               "fetch": [{"url", "kind": "json" | "text" | "image"}]}: the record's own transcription, text or image to archive.
              A fetch with "record": False is archived but not read as a record (an item's metadata). A fetch may carry
              "then": a name for follow().
  Optional:
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

def value(fields, key):
    v = (fields or {}).get(key)
    return v.get("value") if isinstance(v, dict) else v
