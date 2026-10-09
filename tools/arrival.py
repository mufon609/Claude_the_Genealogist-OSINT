#!/usr/bin/env python3
"""The arrival of a record file: archived once, a found run logged on every step it fulfils, read for the tree and decided. One
code path for tools/attach_inbox.py, tools/fetches.py collect and the person screen's "Archive + log": attach archives one
inbox file for its steps, logs the runs, reads the page (copies.read_page) and runs the matcher and the rule on it
(decisions.match_record), then files the original under the tree; attach_inbox takes every file in the inbox by the identity
the file carries (attach.identity) to the steps it fulfils (attach.steps_for, the page's own key first, attach.named_steps);
attach_each runs it one file per transaction, a file whose attach fails rolled back alone and left in the inbox; collect
takes the pages a browser session saved under the names the fetch list printed (fetch_list) into the inbox and attaches
each. What places a file (the identity read from it, the steps it reaches, the owner's word on a record, the lines the tools
print) is tools/attach.py.
"""
import hashlib, json, mimetypes, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import archive_object, downloads_dir, imports_dir, inbox_dir, move_free, now, object_path, ulid
from catalog import collection_tier, withdrawals
from readers import parse_aad_search, parse_fs_search, parse_search
from matcher import fitting_rows
from log_search import hold_unread, holds_record, log as log_search, ran_unchanged, rendered_query, restate, step_source, unread_record
from plan import plan_person
from attach import (
    PHOTO_COLLECTION,
    PHOTO_NAME,
    PHOTOS,
    _rows_of,
    failed,
    identity,
    identity_of_name,
    inbox_files,
    named_steps,
    on_word,
    saved_steps,
    steps_for
)
from fetch_list import IDENTITY_HOLDERS, SAVED_FROM_IDENTITY, named_for, saved_from, waiting
from decisions import match_record

HOUSEHOLD_ROW = "household:"                    # the plan row of a household's own leads (tools/plan.py household_row): its search and its candidates

def _repeat_save(cx, step_id, kind, parsed):
    """The earlier artifact's sha256 when this results page is the same search saved again: an artifact already logged on the
    step carries the same search URL as locator and, read again with the same parser, lists the same rows. The page adds
    nothing to the record of that run; a later run of the same search that answers with other rows is a new run. None when
    this page is not a repeat of anything already logged on the step."""
    parse = {"search": parse_search, "fs_search": parse_fs_search, "aad_search": parse_aad_search}[kind]
    for arts, in cx.execute("SELECT artifacts_json FROM search_log WHERE plan_step_id=? AND artifacts_json IS NOT NULL AND superseded_by IS NULL", (step_id,)):
        for sha in json.loads(arts or "[]"):
            loc = cx.execute("SELECT locator_value FROM artifact WHERE sha256=?", (sha,)).fetchone()
            if not loc or loc[0] != parsed.get("url"): continue
            try:
                with open(object_path(sha), "rb") as fh: earlier = parse(fh.read().decode("utf-8", errors="replace"))
            except (OSError, ValueError): continue
            if _rows_of(kind, earlier) == _rows_of(kind, parsed) and earlier.get("count") == parsed.get("count"): return sha
    return None

def filed_name(ts, src):
    """The name an original is filed under, in the tree's imports/records/: the day it was attached and the file's own name, its
    characters past letters, digits, dot, underscore and hyphen made hyphens; treelib.move_free gives it a free name when another
    original of that day already holds it."""
    return f"{ts[:10]}_{re.sub(r'[^A-Za-z0-9._-]+', '-', os.path.basename(src))}"

def _source_row(cx, sid):
    r = cx.execute("SELECT id, trust_tier, terms, cost FROM source WHERE id=?", (sid,)).fetchone() if sid else None
    return dict(r) if r else {}

def _cost(text):
    t = (text or "").strip().lower(); return next((c for c in ("free", "paid", "member") if t.startswith(c)), "unknown")

def refuse_withdrawn(cx, data):
    """ValueError when these bytes are an archived file withdrawn from the evidence (tools/tombstone.py): saved again, they are
    attached to nothing, and the file stays where it was."""
    sha = hashlib.sha256(data).hexdigest(); w = withdrawals(cx, [sha]).get(sha)
    if w: raise ValueError(f"the file is {sha[:12]}, withdrawn from the archive on {w['at'][:10]} by {w['by']}: {w['reason']}; nothing attached")

def attach(cx, tree_id, slug, name, steps, by, note=None, query=None, kind=None, value=None, parsed=None, about=None):
    """Archive one inbox file for these steps (provenance from the first: the record's kind gives the trust tier, where it was
    retrieved gives terms and cost; the locator is the step's, or the search URL for a results page), log a found run on every
    step not yet logged with it (a results page's log carries the query as run and the number of results), file the original
    under the tree (filed_name, beside another original of that name under a free one, never over it: `filed` the path, and
    `filed_beside` the name it could not take), then parse and match a page new to the archive. A results page on which no candidate fits has its run read
    again as none, the candidates kept on the artifact; one no parser reads (a page whose every reading failed,
    log_search.unread_record) has it read again as unread, the note saying so, and closes nothing; each a new row superseding
    the found one (log_search.restate), whose id `logs` then names. Then the steps the run closes are marked done: a search step by
    the found run; a fetch step only when the page is the record it cites (log_search.holds_record), so a listing that points at
    records leaves it planned. A file withdrawn from the archive is refused (refuse_withdrawn). Returns what happened."""
    src = os.path.join(inbox_dir(), os.path.basename(name))
    if not os.path.isfile(src): raise ValueError("file not in inbox")
    if not steps and not about: raise ValueError("no step to attach to")
    st = steps[0] if steps else {"sources_json": None, "locator_source_id": None, "collection_id": None, "locator_kind": None, "locator_value": None}
    ts = now(); mime = mimetypes.guess_type(src)[0] or "application/octet-stream"
    sources = json.loads(st["sources_json"] or "[]"); kind_row = _source_row(cx, sources[0] if sources else None); from_row = _source_row(cx, st["locator_source_id"]) or kind_row
    col = cx.execute("SELECT name FROM collection WHERE id=?", (st["collection_id"],)).fetchone() if st["collection_id"] else None
    lkind, lvalue, cname = (("url", value, "Find a Grave memorial search") if kind == "search" else ("url", value, "FamilySearch record search") if kind == "fs_search" else ("url", value, "WWII Army Enlistment Records (AAD)") if kind == "aad_search"
                            else ("url", (parsed or {}).get("url") or value, "WWII Army Enlistment Records (AAD)") if kind == "aad_record"
                            else ("url", st["locator_value"], PHOTO_COLLECTION) if kind == "photo"
                            else ("url", value, col[0] if col else None) if kind == "page"
                            else (st["locator_kind"] or "file", st["locator_value"] or os.path.basename(src), col[0] if col else None))
    holder = {"ark": "D03", "memorial": "E01", "search": "E01", "fs_search": "D03", "aad_search": "F01", "aad_record": "F01", "photo": PHOTOS, "page": st["locator_source_id"]}.get(kind)   # the page's own identity says where it came from, whatever holder the step pointed at; a page taken by name comes from the step's holder
    from_row = _source_row(cx, holder) or from_row
    if kind == "photo":                                                              # the stone itself: an image under the gravestone row, tier 1
        kind_row = from_row
        row = cx.execute("SELECT id, name FROM collection WHERE source_id=? AND name=?", (PHOTOS, PHOTO_COLLECTION)).fetchone()
        if not row: cid = ulid(); cx.execute("INSERT INTO collection (id,source_id,name,external_key_kind,external_key) VALUES (?,?,?,?,?)", (cid, PHOTOS, PHOTO_COLLECTION, "other", "findagrave-photo")); row = (cid, PHOTO_COLLECTION)
        st = dict(st); st["collection_id"] = row[0]
    if kind == "ark" and (parsed or {}).get("collection"):                           # the record's own collection at its holder
        own = re.sub(r"^[^•]*•\s*", "", parsed["collection"]).strip()
        row = cx.execute("SELECT id, name FROM collection WHERE source_id=? AND name=?", (holder, own)).fetchone()
        if not row: cid = ulid(); cx.execute("INSERT INTO collection (id,source_id,name,external_key_kind,external_key,trust_tier) VALUES (?,?,?,?,?,?)", (cid, holder, own, "other", own, collection_tier(holder, own))); row = (cid, own)   # the tier the registry gives the collection, from its first record on
        st = dict(st); st["collection_id"], cname = row[0], row[1]
    if kind in ("search", "aad_search", "fs_search"):
        query = {k: {"value": v, "basis": "run"} for k, v in parsed["query"].items()}
        note = "; ".join(x for x in (f"{parsed['count'] if parsed['count'] is not None else len(parsed['rows'])} matching records, page {parsed['page']} of {parsed['pages']}, {len(parsed['rows'])} rows on this page", note) if x)
    with open(src, "rb") as fh: data = fh.read()
    refuse_withdrawn(cx, data)
    sha, new = archive_object(cx, data, mime=mime, source_id=holder or st["locator_source_id"] or (sources[0] if sources else None), collection_id=st["collection_id"], collection_name=cname,
                              locator_kind=lkind, locator_value=lvalue, retrieved_by=by, terms=from_row.get("terms"),
                              cost=_cost(from_row.get("cost")), trust_tier=kind_row.get("trust_tier") or from_row.get("trust_tier"), original_filename=os.path.basename(src), notes=note)
    if kind == "memorial": cx.execute("INSERT OR IGNORE INTO artifact_locator (artifact_sha256,kind,value) VALUES (?,?,?)", (sha, "memorial_id", value))   # the page's own identity, however it was cited
    if kind == "ark": cx.execute("INSERT OR IGNORE INTO artifact_locator (artifact_sha256,kind,value) VALUES (?,?,?)", (sha, "ark", value))
    logs = []
    if not steps and about: logs.append(on_word(cx, tree_id, about, sha, by, note=note, parsed=parsed or {}))   # the owner's word: a fetch step on their plan, done with the found run, so the record is fetched for them from now on
    for s in steps:                                              # logged before the page is read, so the matcher sees every person it was fetched for; done below, once read
        if cx.execute("SELECT 1 FROM search_log WHERE plan_step_id=? AND artifacts_json LIKE ? AND superseded_by IS NULL", (s["id"], f'%"{sha}"%')).fetchone(): continue
        fields = rendered_query(s["query_json"], s["revisions_json"])   # the step's own fields, and for a results page the fields as searched beside them (basis run)
        logs.append((s["id"], log_search(cx, tree_id, by, step_id=s["id"], outcome="found", artifacts=[sha], note="; ".join(x for x in (note, s.get("reason") if isinstance(s, dict) else None) if x), query={**fields, **(query or {})}, done=False)))
    out = {"sha256": sha, "new": new, "mime": mime, "logs": logs, "extraction": None, "proposals": [], "unparsed": None}
    if new and mime.startswith("text/html"):                     # a page is parsed and matched on arrival; an image waits for a transcription
        from readers import RESULTS_LISTINGS
        from copies import read_page
        eid, n = read_page(cx, sha, by); out["extraction"] = eid
        if "failed" in n: out["unparsed"] = n["failed"]
        else: out["proposals"], out["accepted_by_rule"] = match_record(cx, eid, by, about=[about] if about else None)
        is_results_page = cx.execute(f"""SELECT 1 FROM extraction e JOIN extractor x ON x.id=e.extractor_id
                                        WHERE e.id=? AND x.name IN ({','.join('?' * len(RESULTS_LISTINGS))})""", (eid, *RESULTS_LISTINGS)).fetchone()
        fits = fitting_rows(cx, eid)                              # the rows of a pointing listing that fit a person the page was fetched for: leads, never proposals
        if is_results_page and not out["proposals"] and not fits and logs:   # a results page whose own rows fit nobody: the run found nothing for the person, the candidates stay on the artifact
            logs = out["logs"] = [(sid, restate(cx, by, lid, outcome="none", note="no candidate fits")) for sid, lid in logs]
            out["outcome"] = "none"
        for person in dict.fromkeys([who for who, _, _ in fits] + [s["person_id"] for s in steps if s["row_key"].startswith(HOUSEHOLD_ROW)]):   # the rows' own records are fetch steps now, and a household's search moves to its next page or a candidate tried opens the next: the plan says so before anyone asks for the next page
            plan_person(cx, tree_id, person, by)
    if steps and logs and unread_record(cx, sha):                 # a page no parser reads: held on the step's log, read by nobody, closing nothing
        logs = out["logs"] = [(sid, hold_unread(cx, by, lid)) for sid, lid in logs]
        out["outcome"] = "unread"
    if out.get("outcome") not in ("none", "unread") and logs:     # the found run closes a search step; a fetch step only when the page is the record it cites
        kinds = {s["id"]: s["kind"] for s in steps}; record = holds_record(cx, sha)
        for sid, lid in logs:
            if record or kinds.get(sid) != "fetch": cx.execute("UPDATE search_plan SET status='done' WHERE id=?", (sid,))
    filed = filed_name(ts, src)
    out["filed"] = move_free(src, os.path.join(imports_dir(slug), "records"), filed)   # the original leaves the inbox last, so a failure before this point leaves it there
    if os.path.basename(out["filed"]) != filed: out["filed_beside"] = filed           # another original of the day held the name: filed under a free one beside it
    return out

def attach_held(cx, tree_id, slug, name, about_id, by, note=None):
    """A family-held file (a photograph of an object, a letter, a Bible page) with no record identity: archived under the
    family-held source (M05) with the owner's note as its description, filed under the tree, and put before the matcher for
    the person the owner says it is about. What it says about anyone is read afterwards, one persona at a time (the screen's
    transcription form or the model), and decided on a card. Returns the artifact hash and whether it was new."""
    src = os.path.join(inbox_dir(), os.path.basename(name))
    if not os.path.isfile(src): raise ValueError("file not in inbox")
    ts = now(); mime = mimetypes.guess_type(src)[0] or ("image/heic" if src.lower().endswith(".heic") else "application/octet-stream")
    row = _source_row(cx, "M05")
    col = cx.execute("SELECT id FROM collection WHERE source_id='M05' AND name='Family-held originals'").fetchone()
    cid = col[0] if col else ulid()
    if not col: cx.execute("INSERT INTO collection (id,source_id,name,external_key_kind,external_key) VALUES (?,?,?,?,?)", (cid, "M05", "Family-held originals", "other", "family"))
    with open(src, "rb") as fh: data = fh.read()
    refuse_withdrawn(cx, data)
    sha, new = archive_object(cx, data, mime=mime, source_id="M05", collection_id=cid, collection_name="Family-held originals", locator_kind="file", locator_value=os.path.basename(src),
                              retrieved_by=by, terms=row.get("terms"), cost="free", trust_tier=row.get("trust_tier"), original_filename=os.path.basename(src), notes=note)
    cx.execute("INSERT INTO note (id,tree_id,entity_kind,entity_id,body,author,created_at) VALUES (?,?,?,?,?,?,?)",
               (ulid(), tree_id, "artifact", sha, f"about {cx.execute('SELECT display_name FROM person WHERE id=?', (about_id,)).fetchone()[0]}, on the owner's word" + (f": {note}" if note else ""), by, ts))
    move_free(src, os.path.join(imports_dir(slug), "records"), filed_name(ts, src))
    return sha, new

def attach_each(cx, tree_id, slug, by, names, about=None):
    """attach_inbox on the files named, one file per transaction: a file whose attach fails is rolled back alone and stays in
    the inbox untouched for the next try, named with the failure, and the files before and after it stay attached. An object
    the failed try already wrote into the archive is harmless: the archive is content-addressed, and the next try writes the
    same bytes under the same hash with its artifact row."""
    results = []
    for name in names:
        cx.execute("BEGIN")
        try: results += attach_inbox(cx, tree_id, slug, by, [name], about=about); cx.commit()
        except Exception as e: cx.rollback(); results.append(failed(name, e))
    return results

def attach_inbox(cx, tree_id, slug, by, names=None, about=None):
    """Every file in the inbox (or the named ones): identity from the file, the steps it fulfils, attach. A file with no
    identity or no step stays in the inbox, unless the owner says whom a record is about (about: person id): then a record
    with an identity but no step is archived under its holder, given a fetch step on that person's plan done with the found
    run (on_word), and put before the matcher for them; and a file that is no web page and carries no record identity (a
    photograph or scan of something the family holds) is a family-held original (attach_held). Returns one result per
    file."""
    names = names or inbox_files()
    results = []
    for name in names:
        path = os.path.join(inbox_dir(), os.path.basename(name)); r = {"file": os.path.basename(name), "identity": None, "steps": [], "left": None}
        if not os.path.isfile(path): r["left"] = "not in the inbox"; results.append(r); continue
        with open(path, "rb") as fh: data = fh.read()
        page = (mimetypes.guess_type(path)[0] or "").startswith("text/html"); text = data.decode("utf-8", errors="replace") if page else ""
        kind, value, parsed = identity(text) if page else identity_of_name(name)
        if not kind and about and not (mimetypes.guess_type(path)[0] or "").startswith("text/html"):   # a family-held original, on the owner's word about whom it concerns
            sha, new = attach_held(cx, tree_id, slug, name, about, by)
            r.update({"identity": "family-held original", "sha256": sha, "held": True, "new": new}); results.append(r); continue
        if not kind: r["left"] = "no record identity read from the file (not a Find a Grave memorial or results page, not a FamilySearch record page, not a photograph under the name the fetch list printed)"; results.append(r); continue
        r["identity"] = f"{kind} {value}"
        ids = saved_steps(text); keyed, aside = named_steps(cx, tree_id, ids, kind, value, parsed)   # the steps the page was saved for first, the steps its identity reaches beside them
        if ids: r["key"] = {"named": len(ids), "taken": len(keyed), "aside": aside}
        steps = keyed + [s for s in steps_for(cx, tree_id, kind, value, parsed) if s["id"] not in {k["id"] for k in keyed}]
        if kind in ("search", "fs_search", "aad_search") and steps:  # the same search saved again is an answer: a none run on the fields as now rendered, wherever the step wasn't already answered on them
            fresh = []
            for s in steps:
                sha = _repeat_save(cx, s["id"], kind, parsed)
                if not sha: fresh.append(s); continue
                rendered = rendered_query(s["query_json"], s["revisions_json"])
                if not ran_unchanged(cx, s, rendered, step_source(s)):
                    log_search(cx, tree_id, by, step_id=s["id"], outcome="none", query=rendered,
                               note=f"the rows are those already logged, artifact {sha[:12]}: a repeat save")
            if not fresh:
                os.remove(path)
                r["repeat"] = "the same search, with the same rows, is already logged on every step it fits: a repeat save"
                results.append(r); continue
            steps = fresh
        r["steps"] = [(s["id"], cx.execute("SELECT display_name FROM person WHERE id=?", (s["person_id"],)).fetchone()[0], s["row_key"], s.get("reason")) for s in steps]
        if not steps and not about: r["left"] = "no search step in this tree has this search's fields, and no fetch step's citation was searched for by this name at this holder" if kind in ("search", "fs_search") else "no step in this tree asks for this photograph" if kind == "photo" else "no fetch step in this tree cites this record"; results.append(r); continue
        r.update(attach(cx, tree_id, slug, name, steps, by, note=f"attached from the inbox by identity: {kind} {value}" + (" on the owner's word about the person" if not steps else ""), kind=kind, value=value, parsed=parsed, about=about))
        results.append(r)
    return results

def collect(cx, tree_id, slug, by, folder=None):
    """Every page in the data root's downloads folder (or the folder given) saved under a name the list printed: a gravestone
    photograph by its own name (it carries no identity in its bytes), and any .html file whose saved-from line (the browser's
    own comment, tools/save_page.js) is a FamilySearch record or search URL, a Find a Grave memorial or search, or an AAD
    record or search, moved to inbox/ under its own name and attached by that identity (tools/attach.py identity), whatever
    the name says, to the steps its key names first when it carries one (attach.named_steps). A file of the same name already
    in the inbox is never written over: the page takes a free name beside it (treelib.move_free), its result naming that
    name as `inbox_as` and keeping the name it was saved under as `file`. A page from a holder whose pages
    carry no identity the attach reads is taken by the by-name path
    instead, under the list's own name, and attached to the steps of the one citation and person the name carries, archived
    under that holder with its own URL as locator. A name is not an identity: at a holder whose pages carry their own
    (IDENTITY_HOLDERS) a file under the list's name with no saved-from line is not the page, whoever or whatever saved it,
    and is left where it is, as a file with neither is. The pages taken by name go first,
    then those taken by identity, each file in a transaction of its own (arrival.attach_each): a file whose transaction fails
    is rolled back alone and named with the failure, a page taken by name put back in the folder it was saved in (only collect
    takes a page by its name), a page taken by identity left in the inbox (attach_inbox.py, and the next turn, take it again).
    Returns (the names the pages taken have in the inbox, the attach results)."""
    folder = folder or downloads_dir(); by_identity, results = [], []
    entries = waiting(cx, tree_id)
    for f in sorted(os.listdir(folder)):
        path = os.path.join(folder, f)
        if not os.path.isfile(path): continue
        if PHOTO_NAME.fullmatch(f) or (f.lower().endswith(".html") and SAVED_FROM_IDENTITY.search(saved_from(path) or "")): by_identity.append(f); continue
        e = named_for(f, entries)
        if not e or not f.lower().endswith(".html"): continue
        if e["holder_id"] in IDENTITY_HOLDERS: continue          # this holder's pages carry their own identity: a file under the list's name without it is not the page
        dst = move_free(path, inbox_dir()); taken = os.path.basename(dst)   # beside a file of the same name already in the inbox, never over it
        cx.execute("BEGIN")
        try:
            url = saved_from(dst) or e["url"]
            steps = [{**dict(r), "reason": "saved under the name the fetch list printed for this page"} for sid in e["step_ids"] for r in cx.execute("SELECT * FROM search_plan WHERE id=?", (sid,))]
            r = {"file": f, "identity": f"page {url}", "steps": [(s["id"], cx.execute("SELECT display_name FROM person WHERE id=?", (s["person_id"],)).fetchone()[0], s["row_key"], s["reason"]) for s in steps], "left": None}
            r.update(attach(cx, tree_id, slug, taken, steps, by, note=f"saved in the browser under the fetch list's name at {e['holder']}", kind="page", value=url)); cx.commit()
            if taken != f: r["inbox_as"] = taken
        except Exception as ex:
            cx.rollback()
            back = move_free(dst, folder, f) if os.path.exists(dst) else path   # the attach files the original last, so a failure before that leaves it in the inbox to put back
            r = failed(os.path.basename(back), ex, folder)
        results.append(r)
    inbox = {}                                                   # the name each page taken by identity has in the inbox -> the name it was saved under
    for f in by_identity: inbox[os.path.basename(move_free(os.path.join(folder, f), inbox_dir()))] = f
    attached = attach_each(cx, tree_id, slug, by, list(inbox))
    for r in attached:
        if inbox.get(r["file"], r["file"]) != r["file"]: r["inbox_as"], r["file"] = r["file"], inbox[r["file"]]
    return list(inbox) + [r.get("inbox_as") or r["file"] for r in results], attached + results
