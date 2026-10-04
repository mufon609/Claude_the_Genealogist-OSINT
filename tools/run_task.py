#!/usr/bin/env python3
"""A model run on a step no connector can take: the task rendered from the step, the launcher, the answer checked, the run a row.

usage: tools/run_task.py show [K] [--tree slug] [--db catalog/tree.db]
       tools/run_task.py fetch [K] --model MODEL --effort EFFORT [--budget USD] [--timeout SECONDS] [--by agent:run_task] [--tree slug] [--db catalog/tree.db]
       tools/run_task.py capture --model MODEL --effort EFFORT --out FILE [--budget USD] [--timeout SECONDS] [--tree slug] [--db catalog/tree.db]

docs/RESEARCH-WORKFLOW.md §4 (a model saves the page) and docs/DATA-ARCHITECTURE.md §7 decision 16. One kind of task
exists, `fetch`: a page on the fetch list (tools/fetches.py next) saved in the owner's browser by the page-saves-itself
method. The task is the list's entry rendered by code (fetch_task, render): the link, the file name and tools/save_page.js
with the entry's call in place of the ("FILENAME.html") that ends it. The words a model needs beyond the entry are one
text per kind (tools/tasks/<kind>.md, task_text), its sha256 on every run; no text is composed for one task. A gravestone
photograph (tools/save_image.js) is no task of this kind.

launch starts `claude -p` once, its input closed, in an empty folder of its own: the kind's text as the system prompt, the
rendered task as the prompt, the model and the effort given, the kind's answer schema (--json-schema), a spending limit
(--max-budget-usd), the owner's browser (--chrome), no built-in tool, the kind's own tools allowed and every prompt for
another denied. It returns what the launcher reported, measured: the answer (structured_output) and whether it is the
schema's, total_cost_usd, modelUsage per model with the tokens summed, num_turns, duration_ms, terminal_reason and the
number of permission_denials; a launcher that times out, exits without a result or prints no JSON is `timeout`,
`exit <n>` or `no result`, with nothing measured but the time. The model writes nothing to the catalog: what it saves
lands in the data root's downloads/ folder.

run_fetch is one task end to end: the launch, then tools/fetches.py collect on the data root's downloads/ whatever the
launcher returned, then the outcome as code finds it (judge), never as the model reports it: no_answer, invalid, nothing,
mismatch, or what the attach made of a page whose own identity is the step's (unread, none, read, card, taken). No run is
logged on a step on the model's word. One row of task_run (insert-only) records the launch: the kind, the holder, the
steps, the task as rendered, the text's sha256, the model and effort, the measures, how the run ended, the answer, the
outcome, whether the model's report and the finding differ (the note says how) and the search_log row the page's attach
wrote. `fetch [K]` runs the next K openable pages (one by default), one launch each, one page at a time; `show [K]`
prints the tasks as rendered and launches nothing. Which model and effort a task gets is the caller's to say.

`capture` is for the check's fixtures (tests/fixtures/README.md): it launches the next openable page's task as `fetch`
does and writes the launcher's own output to FILE as it came, with the task beside it as FILE's .task.json; it runs no
collect and writes nothing to the catalog, so the saved page stays in downloads/ to be copied beside the capture.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, downloads_dir, dumps, now, resolve_tree, ulid
from attach import line
import fetches

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = "agent:run_task"
BROWSER = "mcp__claude-in-chrome__"
ANSWERS = {"fetch": {"type": "object", "additionalProperties": False, "required": ["status", "line"],
                     "properties": {"status": {"type": "string", "enum": ["saved", "blocked", "not_saved"]}, "line": {"type": "string"}}}}   # what a task's answer is, per kind
TOOLS = {"fetch": [BROWSER + t for t in ("tabs_context_mcp", "tabs_create_mcp", "navigate", "javascript_tool", "tabs_close_mcp", "browser_batch")]}   # the only tools a kind's task may call
REACHED = ("unread", "none", "read", "card", "taken")           # the outcomes of a page whose own identity is the step's
SCRIPT_CALL = '("FILENAME.html")'                               # what ends tools/save_page.js, replaced by the entry's call

def task_text(kind):
    """The one text of a task kind (tools/tasks/<kind>.md) and its sha256."""
    with open(os.path.join(ROOT, "tools", "tasks", kind + ".md"), "rb") as fh:
        data = fh.read()
    return data.decode("utf-8"), hashlib.sha256(data).hexdigest()

def script(call):
    """tools/save_page.js with the entry's call in place of the call that ends it, and the script's sha256 as the file holds it."""
    with open(os.path.join(ROOT, "tools", "save_page.js"), "rb") as fh:
        data = fh.read()
    js = data.decode("utf-8").rstrip()
    if not js.endswith(SCRIPT_CALL):
        raise SystemExit(f"tools/save_page.js does not end in {SCRIPT_CALL}")
    return js[:-len(SCRIPT_CALL)] + call, hashlib.sha256(data).hexdigest()

def fetch_task(e):
    """A fetch task from one entry of the fetch list (fetches.openable): the holder, the link, the file name, the save script's
    call with the entry's key, and the steps the page serves. An image, or an entry with no link, is no task."""
    if e["how"] != "page" or not e["url"]:
        raise ValueError(f"no fetch task for {e['save_as']}: {'an image' if e['how'] != 'page' else 'no link to open'}")
    return {"kind": "fetch", "holder_id": e["holder_id"], "holder": e["holder"], "link": e["url"], "file": e["save_as"], "call": fetches.page_call(e), "steps": list(e["serves"])}

def render(task):
    """The task as the model is given it: the entry's link and file name and the script to run, nothing else."""
    js, _ = script(task["call"])
    return f"link: {task['link']}\nfile: {task['file']}\nscript:\n{js}\n"

def valid(answer, schema):
    """Whether an answer is the schema's: an object with every required key and no other, each a string, one of the enum's where it has one."""
    if not isinstance(answer, dict):
        return False
    props = schema["properties"]
    if set(schema["required"]) - set(answer) or set(answer) - set(props):
        return False
    for k, v in answer.items():
        if not isinstance(v, str):
            return False
        if "enum" in props[k] and v not in props[k]["enum"]:
            return False
    return True

def command(kind, text, prompt, model, effort, budget, chrome=True):
    """The launcher's command line for one task."""
    return ["claude", "-p", prompt, "--output-format", "json", "--model", model, "--effort", effort, "--system-prompt", text, "--json-schema", json.dumps(ANSWERS[kind]),
            "--tools", "", "--allowedTools", *TOOLS[kind], "--permission-prompts", "none", "--max-budget-usd", str(budget), "--no-session-persistence", "--chrome" if chrome else "--no-chrome"]

def spawn(cmd, timeout, cwd):
    """The launcher's process, its input closed: (exit status, what it printed). subprocess.TimeoutExpired when it outlives the timeout."""
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    return r.returncode, r.stdout

def measured(kind, status, out, seconds):
    """What a launch reported, measured: ended (the launcher's terminal_reason, or `exit <n>` or `no result` when it printed no
    result), the answer and whether it is the kind's schema's, the cost, the per-model usage with its tokens summed, the turns, the
    time (the launcher's own, or the clock's when it reported none) and the number of tools it was denied."""
    m = {"result": False, "ended": None, "answer": None, "valid": False, "cost_usd": None, "usage": None, "input_tokens": None, "output_tokens": None, "turns": None, "duration_ms": int(seconds * 1000), "denials": None, "raw": out}
    try:
        r = json.loads(out)
    except ValueError:
        r = None
    if not isinstance(r, dict) or r.get("type") != "result":
        m["ended"] = f"exit {status}" if status else "no result"
        return m
    usage = r.get("modelUsage") or {}
    m["result"] = True
    m["ended"] = r.get("terminal_reason") or r.get("subtype") or f"exit {status}"
    m["answer"] = r.get("structured_output")
    m["valid"] = valid(m["answer"], ANSWERS[kind])
    m["cost_usd"] = r.get("total_cost_usd")
    m["usage"] = usage
    m["input_tokens"] = sum((u.get("inputTokens") or 0) + (u.get("cacheReadInputTokens") or 0) + (u.get("cacheCreationInputTokens") or 0) for u in usage.values())
    m["output_tokens"] = sum(u.get("outputTokens") or 0 for u in usage.values())
    m["turns"] = r.get("num_turns")
    if r.get("duration_ms") is not None:
        m["duration_ms"] = r["duration_ms"]
    m["denials"] = len(r.get("permission_denials") or [])
    return m

def launch(kind, prompt, model, effort, budget, timeout, chrome=True):
    """One task at the launcher (command, spawn), in an empty folder of its own so that no project's instructions reach it:
    what it reported (measured). A launcher that outlives the timeout is ended `timeout`, nothing measured but the time."""
    text, _ = task_text(kind)
    cwd = tempfile.mkdtemp(prefix="tree-task-")
    began = time.monotonic()
    try:
        status, out = spawn(command(kind, text, prompt, model, effort, budget, chrome), timeout, cwd)
    except subprocess.TimeoutExpired:
        m = measured(kind, None, "", time.monotonic() - began)
        m["ended"] = "timeout"
        return m
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
    return measured(kind, status, out, time.monotonic() - began)

def judge(task, m, new, results):
    """The outcome of a fetch task as code finds it, from the files that came into downloads/ while the launcher ran (`new`) and
    what collect made of the folder (`results`): (outcome, the search_log row the page's attach wrote on a step of the task, the
    note). A page that reached a step of the task (its own identity is the step's, attach.named_steps and steps_for) is what the
    attach made of it: unread, none, taken (the rule took a proposal), card (proposals wait) or read; a results page saved again
    with the rows already logged is none. A file that came in and reached no step of the task is a mismatch, the note collect's
    own line for it. With no file: no_answer when the launcher gave no result, invalid when its answer is not the schema's,
    nothing otherwise."""
    steps = set(task["steps"])
    reached = [r for r in results if not r.get("left") and steps & {s[0] for s in r.get("steps") or []}]
    if reached:
        r = reached[0]
        outcome = r["outcome"] if r.get("outcome") in ("unread", "none") else "taken" if r.get("accepted_by_rule") else "card" if r.get("proposals") else "read"
        log_id = next((lid for sid, lid in r.get("logs") or [] if sid in steps), None)
        return outcome, log_id, line(r)
    mine = [r for r in results if r["file"] in new]
    repeat = next((r for r in mine if r.get("repeat")), None)
    if repeat:
        return "none", None, line(repeat)
    if mine:
        return "mismatch", None, line(mine[0])
    if new:
        return "mismatch", None, f"{', '.join(new)} came into the folder and collect left it there: neither a saved-from identity the attach reads nor the name the list printed"
    if not m["result"]:
        return "no_answer", None, f"the launcher gave no result ({m['ended']})"
    if not m["valid"]:
        return "invalid", None, f"the answer is not the schema's: {dumps(m['answer'])[:300]}"
    return "nothing", None, "no page came into the folder"

def difference(m, outcome):
    """How the model's report and code's finding differ, or None: it reported the page saved and no page of the step's came in, it
    reported it not saved and one did, or it gave no valid answer and one did."""
    got = outcome in REACHED
    if not m["valid"]:
        return "no valid answer, and a page of the step's came in" if got else None
    said = m["answer"]["status"] == "saved"
    if said and not got:
        return f"the model reported the page saved ({m['answer']['line'][:200]}), and no page of the step's came in"
    if got and not said:
        return f"the model reported {m['answer']['status']} ({m['answer']['line'][:200]}), and a page of the step's came in"
    return None

def record(cx, tree_id, by, task, sha, script_sha, model, effort, started, m, outcome, log_id, note, differs):
    """One launch into task_run, with its audit row. Returns the row's id."""
    rid = ulid()
    rendered = {k: task[k] for k in ("link", "file", "call")}
    rendered["script_sha256"] = script_sha
    cx.execute("""INSERT INTO task_run (id,tree_id,task_kind,holder_id,plan_step_ids_json,task_json,task_text_sha256,model,effort,started_at,launched_by,
                                        input_tokens,output_tokens,cost_usd,turns,duration_ms,usage_json,ended,denials,answer_json,outcome,differs,note,search_log_id)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (rid, tree_id, task["kind"], task["holder_id"], dumps(task["steps"]), dumps(rendered), sha, model, effort, started, by,
                m["input_tokens"], m["output_tokens"], m["cost_usd"], m["turns"], m["duration_ms"], dumps(m["usage"]) if m["usage"] is not None else None, m["ended"], m["denials"],
                dumps(m["answer"]) if m["answer"] is not None else None, outcome, bool(differs), "; ".join(x for x in (differs, note) if x) or None, log_id))
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, now(), by, "insert", "task_run", rid, dumps({"kind": task["kind"], "steps": task["steps"], "model": model, "effort": effort, "outcome": outcome, "search_log": log_id})))
    return rid

def run_fetch(cx, tree_id, slug, entry, by, model, effort, budget, timeout):
    """One fetch task end to end: launched, the folder collected whatever the launcher returned (one file per transaction, as
    fetches.collect keeps them), the outcome judged, the launch recorded in a transaction of its own. Returns the row as a dict
    with the collect's results."""
    task = fetch_task(entry)
    _, sha = task_text("fetch")
    _, script_sha = script(task["call"])
    folder = downloads_dir()
    before = set(os.listdir(folder))
    started = now()
    m = launch("fetch", render(task), model, effort, budget, timeout)
    new = sorted(set(os.listdir(folder)) - before)
    _, results = fetches.collect(cx, tree_id, slug, by)
    outcome, log_id, note = judge(task, m, new, results)
    differs = difference(m, outcome)
    cx.execute("BEGIN")
    try:
        rid = record(cx, tree_id, by, task, sha, script_sha, model, effort, started, m, outcome, log_id, note, differs)
        cx.commit()
    except Exception:
        cx.rollback()
        raise
    return {"id": rid, "task": task, "ended": m["ended"], "answer": m["answer"], "cost_usd": m["cost_usd"], "turns": m["turns"], "duration_ms": m["duration_ms"],
            "outcome": outcome, "differs": differs, "note": note, "search_log": log_id, "results": results}

def run_line(r):
    """One run as the tool prints it, in words."""
    cost = f"${r['cost_usd']:.4f}" if r["cost_usd"] is not None else "no cost reported"
    said = r["answer"]["status"] if isinstance(r["answer"], dict) and "status" in r["answer"] else "no answer"
    out = f"{r['task']['file']}: {r['outcome']} (the launcher ended {r['ended']}, {r['turns'] if r['turns'] is not None else 'no'} turn(s), {r['duration_ms']} ms, {cost}; the model reported {said}); {r['note']}"
    return out + (f"; the report and the finding differ: {r['differs']}" if r["differs"] else "") + f"; run {r['id']}"

def main():
    ap = argparse.ArgumentParser(description="A model run on the pages the fetch list names: show the tasks as rendered, fetch them (one launch per page, the answer checked, a task_run row each), or capture one launch's output for the check's fixtures.")
    ap.add_argument("cmd", choices=["show", "fetch", "capture"])
    ap.add_argument("count", nargs="?", type=int, default=1, help="show, fetch: how many of the next openable pages")
    ap.add_argument("--model", help="fetch, capture: the model to launch, an alias or a full name")
    ap.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], help="fetch, capture: the effort level")
    ap.add_argument("--budget", type=float, default=0.25, help="the launcher's spending limit for one task, in dollars")
    ap.add_argument("--timeout", type=int, default=300, help="seconds before a launcher that has not returned is stopped")
    ap.add_argument("--out", help="capture: the file the launcher's output is written to")
    ap.add_argument("--tree")
    ap.add_argument("--db", default=DB)
    ap.add_argument("--by", default=RUNNER)
    a = ap.parse_args()
    cx = connect(a.db, rows=True)
    tree_id, slug = resolve_tree(cx, a.tree)
    entries = [e for e in fetches.openable(cx, tree_id) if e["how"] == "page"]
    if a.cmd == "show":
        text, sha = task_text("fetch")
        print(f"task text tools/tasks/fetch.md sha256 {sha}; tools: {', '.join(TOOLS['fetch'])}")
        for e in entries[:a.count]:
            print("\n" + render(fetch_task(e)))
        return
    if not a.model or not a.effort:
        sys.exit("give --model and --effort: which a task gets is the caller's to say")
    if not entries:
        sys.exit("no page waiting that a task can open")
    if a.cmd == "capture":
        if not a.out:
            sys.exit("give --out, the file the launcher's output is written to")
        task = fetch_task(entries[0])
        m = launch("fetch", render(task), a.model, a.effort, a.budget, a.timeout)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(m["raw"])
        with open(os.path.splitext(a.out)[0] + ".task.json", "w", encoding="utf-8") as fh:
            json.dump({"task": task, "task_text_sha256": task_text("fetch")[1], "model": a.model, "effort": a.effort, "captured_at": now(), "ended": m["ended"]}, fh, indent=1)
        print(f"{task['file']}: the launcher ended {m['ended']}; its output is {a.out}; nothing collected, the saved page is in {downloads_dir()}")
        return
    tried = set()
    for _ in range(a.count):                                     # one page at a time, the list read again after each: a page taken is no longer open, and one tried is not launched twice in a call
        entries = [e for e in fetches.openable(cx, tree_id) if e["how"] == "page" and (e["url"], e["save_as"]) not in tried]
        if not entries:
            break
        tried.add((entries[0]["url"], entries[0]["save_as"]))
        print(run_line(run_fetch(cx, tree_id, slug, entries[0], a.by, a.model, a.effort, a.budget, a.timeout)))

if __name__ == "__main__": main()
