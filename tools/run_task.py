#!/usr/bin/env python3
"""A model run on a step no connector can take: the task rendered from the step, the launcher, the answer checked, the run a row.

usage: tools/run_task.py show [K] [--tree slug] [--db catalog/tree.db]
       tools/run_task.py fetch [K] --model MODEL --effort EFFORT [--budget USD] [--timeout SECONDS] [--by agent:run_task] [--tree slug] [--db catalog/tree.db]
       tools/run_task.py next --model MODEL [--tree slug] [--db catalog/tree.db]
       tools/run_task.py done [--answer TEXT] [--tokens N] [--tool-uses N] [--duration-ms N] [--out FILE] --by "agent:<session> for user:<name>" [--db catalog/tree.db]
       tools/run_task.py capture --model MODEL --effort EFFORT --out FILE [--budget USD] [--timeout SECONDS] [--tree slug] [--db catalog/tree.db]
       tools/run_task.py write

docs/PLAN-AND-SEARCH.md §4 (a model saves the page) and docs/DATA-ARCHITECTURE.md §7 decisions 16 and 19. One kind of task
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

What starts a task and returns its measures is one seam (decision 19). opened is a task as it stands before any launcher
has it: the task, its text's and its script's sha256, the files in the data root's downloads/ and the time. finish takes
that and a launcher's measures, from whichever launcher: tools/fetches.py collect on downloads/ whatever the launcher
returned, then the outcome as code finds it (judge), never as the model reports it, from the files that came into the folder
while the launcher ran alone: no_answer, invalid, nothing, mismatch, or what the attach made of a page whose own identity is
the step's (unread, none, read, card, taken). A file collect took that was in the folder before the task opened is not the
model's, and the note names it so; a task that produced more than one file is said to have, with their names. No run is logged on a
step on the model's word. One row of task_run (insert-only) records the launch: the launcher, the kind, the holder, the
steps, the task as rendered, the text's sha256, the model and effort, the measures, how the run ended, the answer, the
outcome, whether the model's report and the finding differ (the note says how) and the search_log row the page's attach
wrote. Neither knows which launcher ran the task.

Two launchers stand behind the seam. The headless one (launch, above) is run_fetch: opened, launched, finished in one call.
`fetch [K]` runs the next K openable pages (one by default) that way, one launch each, one page at a time; the model and
effort are the caller's to say. A headless launch has nobody to approve a browser action, so a page is not saved by it.

The session's launcher is a Claude Code session the owner is at, which spawns the task as a subagent so that the browser's
permission prompt reaches the owner. Its fixed words are two files code writes (claude_files, `write`) and tools/check.py
holds to what code would write: the agent file .claude/agents/tree-fetch.md (the kind's text as the subagent's system
prompt, the form of its answer written from the kind's schema, the kind's tools and no other, the effort) and the skill
file .claude/skills/tree-fetch/SKILL.md (tools/tasks/fetch.skill.md: the session's part). `next --model MODEL` hands out
the next openable page's task: it writes the task as opened beside the database (<db>.task-state.json) and prints the
agent to spawn, the model and the task as rendered, which the session passes as the subagent's prompt unchanged. One task
is out at a time: `next` refuses while one is. `done` takes what the session was given when the subagent ended (--answer
its last message as it came, --tokens, --tool-uses, --duration-ms) and finishes the task handed out; with no --answer the
subagent gave none (`no result`), and the time is the clock's since the task was handed out when the session gives none;
--out FILE keeps what the session reported, as it came, for the check's fixtures (tests/fixtures/README.md). A subagent's model is
set per spawn; its effort is not, so the effort a session's run records is the agent file's (SESSION_EFFORT), and `next`
takes no --effort. A session is given one token count and no cost, turns or refusals: those columns stay empty.

`show [K]` prints the tasks as rendered and launches nothing.

`capture` is for the check's fixtures (tests/fixtures/README.md): it launches the next openable page's task as `fetch`
does and writes the launcher's own output to FILE as it came, with the task beside it as FILE's .task.json; it runs no
collect and writes nothing to the catalog, so the saved page stays in downloads/ to be copied beside the capture.
"""
import argparse, calendar, hashlib, json, os, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, downloads_dir, dumps, now, resolve_tree, ulid, write_json_whole
from attach import line
import fetch_list
from arrival import collect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = "agent:run_task"
AGENT = {"fetch": "tree-fetch"}                                 # the agent and the skill of a kind, by the name Claude Code knows them under
SESSION_EFFORT = {"fetch": "low"}                               # the effort the kind's agent file carries: a spawn cannot set one
EMPTY_MCP = '{"mcpServers":{}}'                                 # the headless launch's own MCP configuration: none, so no connector's tools load
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
    """A fetch task from one entry of the fetch list (fetch_list.openable): the holder, the link, the file name, the save script's
    call with the entry's key, and the steps the page serves. An image, or an entry with no link, is no task."""
    if e["how"] != "page" or not e["url"]:
        raise ValueError(f"no fetch task for {e['save_as']}: {'an image' if e['how'] != 'page' else 'no link to open'}")
    return {"kind": "fetch", "holder_id": e["holder_id"], "holder": e["holder"], "link": e["url"], "file": e["save_as"], "call": fetch_list.page_call(e), "steps": list(e["serves"])}

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
    """The headless launcher's command line for one task. No MCP configuration but its own empty one is read
    (--strict-mcp-config), so the account's connector tools do not load; the browser's tools come with --chrome."""
    return ["claude", "-p", prompt, "--output-format", "json", "--model", model, "--effort", effort, "--system-prompt", text, "--json-schema", json.dumps(ANSWERS[kind]),
            "--tools", "", "--allowedTools", *TOOLS[kind], "--permission-prompts", "none", "--max-budget-usd", str(budget), "--no-session-persistence", "--strict-mcp-config", "--mcp-config", EMPTY_MCP, "--chrome" if chrome else "--no-chrome"]

def spawn(cmd, timeout, cwd):
    """The launcher's process, its input closed: (exit status, what it printed). subprocess.TimeoutExpired when it outlives the timeout."""
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    return r.returncode, r.stdout

def measured(kind, status, out, seconds):
    """What a launch reported, measured: ended (the launcher's terminal_reason, or `exit <n>` or `no result` when it printed no
    result), the answer and whether it is the kind's schema's, the cost, the per-model usage with its tokens summed, the turns, the
    time (the launcher's own, or the clock's when it reported none) and the number of tools it was denied."""
    m = {"result": False, "ended": None, "answer": None, "valid": False, "cost_usd": None, "usage": None, "input_tokens": None, "output_tokens": None, "total_tokens": None, "tool_uses": None, "turns": None, "duration_ms": int(seconds * 1000), "denials": None, "raw": out}
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
    m["total_tokens"] = m["input_tokens"] + m["output_tokens"]
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

def reported(kind, answer, tokens, tool_uses, duration_ms, seconds):
    """What a session reported of its subagent, in the shape measured gives: the answer is the subagent's last message read as
    JSON (the message itself when it is not JSON, which is no valid answer), ended `completed`, or `no result` when the session
    was given no message; the tokens, the tool uses and the time are the session's own numbers, the time the clock's since the
    task was handed out when it gave none. A session is given no cost, turns, per-model usage or refusals."""
    m = {"result": answer is not None, "ended": "completed" if answer is not None else "no result", "answer": None, "valid": False, "cost_usd": None, "usage": None, "input_tokens": None, "output_tokens": None,
         "total_tokens": tokens, "tool_uses": tool_uses, "turns": None, "duration_ms": duration_ms if duration_ms is not None else int(seconds * 1000), "denials": None, "raw": answer}
    if answer is None:
        return m
    try:
        m["answer"] = json.loads(answer)
    except ValueError:
        m["answer"] = answer
    m["valid"] = valid(m["answer"], ANSWERS[kind])
    return m

def judge(task, m, new, results):
    """The outcome of a fetch task as code finds it, from the files that came into downloads/ while the launcher ran (`new`) and
    what collect made of the folder (`results`): (outcome, the search_log row the page's attach wrote on a step of the task, the
    note). Only a file that came in while the launcher ran is the task's: one collect took that was in the folder before (saved
    earlier by hand, or put back there by an attach that failed) is attached as any page saved by hand is, and named in the note
    as not the model's; and a task that produced more than one file is said to have, with their names. A page of the task's
    that reached a step of the task (its own identity is the step's, attach.named_steps and steps_for) is what the attach made
    of it: unread, none, taken (the rule took a proposal), card (proposals wait) or read; a results page saved again with the
    rows already logged is none. A file that came in and reached no step of the task is a mismatch, the note collect's own
    line for it. With no file: no_answer when the launcher gave no result, invalid when its answer is not the schema's,
    nothing otherwise."""
    mine = [r for r in results if r["file"] in new]
    others = [r["file"] for r in results if r["file"] not in new]
    said = ([f"the task produced {len(new)} files: {', '.join(new)}"] if len(new) > 1 else []) + \
           ([f"collect also took {', '.join(others)}, in the folder before the task: not the model's"] if others else [])
    outcome, log_id, note = judged(task, m, new, mine)
    return outcome, log_id, "; ".join([note] + said)

def judged(task, m, new, mine):
    """judge's outcome, search_log row and note from the task's own files alone (`mine`, collect's results for the files in
    `new`)."""
    steps = set(task["steps"])
    reached = [r for r in mine if not r.get("left") and steps & {s[0] for s in r.get("steps") or []}]
    if reached:
        r = reached[0]
        outcome = r["outcome"] if r.get("outcome") in ("unread", "none") else "taken" if r.get("accepted_by_rule") else "card" if r.get("proposals") else "read"
        log_id = next((lid for sid, lid in r.get("logs") or [] if sid in steps), None)
        return outcome, log_id, line(r)
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

def record(cx, tree_id, by, launcher, task, sha, script_sha, model, effort, started, m, outcome, log_id, note, differs):
    """One launch into task_run, with its audit row. Returns the row's id."""
    rid = ulid()
    rendered = {k: task[k] for k in ("link", "file", "call")}
    rendered["script_sha256"] = script_sha
    cx.execute("""INSERT INTO task_run (id,tree_id,task_kind,holder_id,plan_step_ids_json,task_json,task_text_sha256,model,effort,started_at,launched_by,launcher,
                                        input_tokens,output_tokens,total_tokens,tool_uses,cost_usd,turns,duration_ms,usage_json,ended,denials,answer_json,outcome,differs,note,search_log_id)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (rid, tree_id, task["kind"], task["holder_id"], dumps(task["steps"]), dumps(rendered), sha, model, effort, started, by, launcher,
                m["input_tokens"], m["output_tokens"], m["total_tokens"], m["tool_uses"], m["cost_usd"], m["turns"], m["duration_ms"], dumps(m["usage"]) if m["usage"] is not None else None, m["ended"], m["denials"],
                dumps(m["answer"]) if m["answer"] is not None else None, outcome, bool(differs), "; ".join(x for x in (differs, note) if x) or None, log_id))
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, now(), by, "insert", "task_run", rid, dumps({"kind": task["kind"], "launcher": launcher, "steps": task["steps"], "model": model, "effort": effort, "outcome": outcome, "search_log": log_id})))
    return rid

def opened(entry):
    """A fetch task as it stands before a launcher has it: the task, its text's and its script's sha256, the files in the data
    root's downloads/ and the time. Plain data, so a launcher that returns in another process is handed it from a file."""
    task = fetch_task(entry)
    _, sha = task_text(task["kind"])
    _, script_sha = script(task["call"])
    return {"task": task, "text_sha256": sha, "script_sha256": script_sha, "before": sorted(os.listdir(downloads_dir())), "started_at": now()}

def finish(cx, tree_id, slug, by, o, launcher, model, effort, m):
    """A task a launcher has returned from, whichever launcher: the folder collected whatever it returned (one file per
    transaction, as arrival.collect keeps them), the outcome judged, the launch recorded in a transaction of its own. Returns
    the row as a dict with the collect's results."""
    task = o["task"]
    new = sorted(set(os.listdir(downloads_dir())) - set(o["before"]))
    _, results = collect(cx, tree_id, slug, by)
    outcome, log_id, note = judge(task, m, new, results)
    differs = difference(m, outcome)
    cx.execute("BEGIN")
    try:
        rid = record(cx, tree_id, by, launcher, task, o["text_sha256"], o["script_sha256"], model, effort, o["started_at"], m, outcome, log_id, note, differs)
        cx.commit()
    except Exception:
        cx.rollback()
        raise
    return {"id": rid, "launcher": launcher, "task": task, "ended": m["ended"], "answer": m["answer"], "cost_usd": m["cost_usd"], "turns": m["turns"], "total_tokens": m["total_tokens"], "tool_uses": m["tool_uses"],
            "duration_ms": m["duration_ms"], "outcome": outcome, "differs": differs, "note": note, "search_log": log_id, "results": results}

def run_fetch(cx, tree_id, slug, entry, by, model, effort, budget, timeout):
    """One fetch task at the headless launcher, end to end: opened, launched, finished."""
    o = opened(entry)
    m = launch("fetch", render(o["task"]), model, effort, budget, timeout)
    return finish(cx, tree_id, slug, by, o, "headless", model, effort, m)

def state_path(db_path):
    """The file beside the database that holds the task a session was handed, until the session reports it done."""
    return db_path + ".task-state.json"

def handed(db_path):
    """The task handed out and not yet reported done, as hand_out wrote it; None when none is out."""
    try:
        with open(state_path(db_path), encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None

def hand_out(tree_id, db_path, entry, model):
    """A fetch list entry's task handed to a session: opened, written beside the database with the tree, the model the session
    is to spawn it on and the agent file's effort, and returned (handout prints it). Refused while a task is out."""
    out = handed(db_path)
    if out:
        raise SystemExit(f"a task is out, handed at {out['opened']['started_at']}: {out['opened']['task']['file']}; report it with tools/run_task.py done (no --answer when the subagent gave none) before the next")
    o = opened(entry)
    state = {"tree_id": tree_id, "model": model, "effort": SESSION_EFFORT[o["task"]["kind"]], "opened": o}
    write_json_whole(state_path(db_path), state, indent=1)
    return state

def handout(state):
    """A handed task as the session reads it: the agent to spawn, the model to spawn it on, and the task as rendered, which is
    the subagent's prompt from the line after `prompt:` to the end."""
    task = state["opened"]["task"]
    return f"agent: {AGENT[task['kind']]}\nmodel: {state['model']}\nprompt:\n{render(task)}"

def report_done(cx, tree_id, slug, db_path, by, answer, tokens, tool_uses, duration_ms, out=None):
    """The task handed out, reported done by the session with what it was given of its subagent (reported), finished as any
    launcher's task is, and no longer out. Refused when no task is out or the one out is another tree's. With `out`, what the
    session reported is written to that file first, as it came, for the check's fixtures."""
    state = handed(db_path)
    if not state:
        raise SystemExit("no task is out: tools/run_task.py next hands one out")
    if state["tree_id"] != tree_id:
        raise SystemExit("the task that is out was handed out on another tree: name it with --tree")
    o = state["opened"]
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump({"answer": answer, "tokens": tokens, "tool_uses": tool_uses, "duration_ms": duration_ms, "model": state["model"], "effort": state["effort"], "task": o["task"], "task_text_sha256": o["text_sha256"], "captured_at": now()}, fh, indent=1)
    waited = time.time() - calendar.timegm(time.strptime(o["started_at"], "%Y-%m-%dT%H:%M:%SZ"))
    m = reported(o["task"]["kind"], answer, tokens, tool_uses, duration_ms, max(waited, 0))
    r = finish(cx, tree_id, slug, by, o, "session", state["model"], state["effort"], m)
    os.remove(state_path(db_path))
    return r

def answer_form(kind):
    """The form of a kind's answer in words, written from its schema (ANSWERS) for a subagent, which is given no schema: its
    last message is one JSON object with the schema's keys."""
    props = ANSWERS[kind]["properties"]
    keys = ", ".join(f"`{k}`" + (" (one of " + ", ".join(f"`{v}`" for v in p["enum"]) + ")" if "enum" in p else "") for k, p in props.items())
    return f"Your last message is the answer and nothing else, with no code fence around it: one JSON object with the keys {keys}, each a string.\n"

def claude_files():
    """The fixed words where Claude reads them, as code writes them: {path under the repository: content}. Per kind, the agent
    file (.claude/agents/<agent>.md: the name, a description, the kind's tools and no other, the effort, no project
    instructions, then the kind's one text and the form of its answer) and the skill file (.claude/skills/<agent>/SKILL.md:
    the name, a description, never loaded but when asked for, then tools/tasks/<kind>.skill.md with the agent's name in
    place)."""
    files = {}
    for kind, agent in AGENT.items():
        text, _ = task_text(kind)
        with open(os.path.join(ROOT, "tools", "tasks", kind + ".skill.md"), encoding="utf-8") as fh:
            skill = fh.read()
        head = f"---\nname: {agent}\ndescription: Runs one {kind} task of tools/run_task.py, given as its prompt unchanged. Spawned only by the {agent} skill.\ntools: {', '.join(TOOLS[kind])}\neffort: {SESSION_EFFORT[kind]}\nomitClaudeMd: true\n---\n\n"
        files[f".claude/agents/{agent}.md"] = head + text + "\n" + answer_form(kind)
        head = f"---\nname: {agent}\ndescription: Has a model run the next {kind} task of tools/run_task.py as a subagent, with the owner present, and reports it done.\ndisable-model-invocation: true\n---\n\n"
        files[f".claude/skills/{agent}/SKILL.md"] = head + skill.replace("{agent}", agent)
    return files

def stale_files():
    """The files of claude_files that differ on disk from what code would write, or are missing."""
    bad = []
    for path, content in claude_files().items():
        try:
            with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
                same = fh.read() == content
        except FileNotFoundError:
            same = False
        if not same:
            bad.append(path)
    return bad

def run_line(r):
    """One run as the tool prints it, in words."""
    cost = f"${r['cost_usd']:.4f}" if r["cost_usd"] is not None else "no cost reported"
    said = r["answer"]["status"] if isinstance(r["answer"], dict) and "status" in r["answer"] else "no answer"
    count = f"{r['tool_uses']} tool use(s)" if r["tool_uses"] is not None else f"{r['turns'] if r['turns'] is not None else 'no'} turn(s)"
    tokens = f"{r['total_tokens']} tokens, " if r["total_tokens"] is not None else ""
    out = f"{r['task']['file']}: {r['outcome']} (the {r['launcher']} launcher ended {r['ended']}, {count}, {tokens}{r['duration_ms']} ms, {cost}; the model reported {said}); {r['note']}"
    return out + (f"; the report and the finding differ: {r['differs']}" if r["differs"] else "") + f"; run {r['id']}"

def main():
    ap = argparse.ArgumentParser(description="A model run on the pages the fetch list names: show the tasks as rendered; fetch them at the headless launcher (one launch per page, the answer checked, a task_run row each); "
                                             "next and done for a session that spawns the task as a subagent (the task handed out, then collected, judged and recorded with the session's measures); "
                                             "capture one headless launch's output for the check's fixtures; write the agent and skill files under .claude/.")
    ap.add_argument("cmd", choices=["show", "fetch", "next", "done", "capture", "write"])
    ap.add_argument("count", nargs="?", type=int, default=1, help="show, fetch: how many of the next openable pages")
    ap.add_argument("--model", help="fetch, capture: the model to launch, an alias or a full name; next: the model the session spawns the subagent on")
    ap.add_argument("--answer", help="done: the subagent's last message, as it came; left out when it gave none")
    ap.add_argument("--tokens", type=int, help="done: the tokens the session was told its subagent used")
    ap.add_argument("--tool-uses", type=int, help="done: the tool uses the session was told")
    ap.add_argument("--duration-ms", type=int, help="done: the time the session was told, in milliseconds")
    ap.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], help="fetch, capture: the effort level")
    ap.add_argument("--budget", type=float, default=0.25, help="the launcher's spending limit for one task, in dollars")
    ap.add_argument("--timeout", type=int, default=300, help="seconds before a launcher that has not returned is stopped")
    ap.add_argument("--out", help="capture: the file the launcher's output is written to; done: a file what the session reported is written to as well")
    ap.add_argument("--tree")
    ap.add_argument("--db", default=DB)
    ap.add_argument("--by", default=RUNNER)
    a = ap.parse_args()
    if a.cmd == "write":
        for path, content in claude_files().items():
            os.makedirs(os.path.dirname(os.path.join(ROOT, path)), exist_ok=True)
            with open(os.path.join(ROOT, path), "w", encoding="utf-8") as fh:
                fh.write(content)
            print(path)
        return
    cx = connect(a.db, rows=True)
    tree_id, slug = resolve_tree(cx, a.tree)
    if a.cmd == "next":
        if not a.model:
            sys.exit("give --model: which model a task is spawned on is the caller's to say")
        if a.effort:
            sys.exit(f"a subagent's effort is the agent file's ({SESSION_EFFORT['fetch']}), not the spawn's: leave --effort out")
        entries = [e for e in fetch_list.openable(cx, tree_id) if e["how"] == "page"]
        if not entries:
            sys.exit("no page waiting that a task can open")
        print(handout(hand_out(tree_id, a.db, entries[0], a.model)), end="")
        return
    if a.cmd == "done":
        print(run_line(report_done(cx, tree_id, slug, a.db, a.by, a.answer, a.tokens, a.tool_uses, a.duration_ms, a.out)))
        return
    entries = [e for e in fetch_list.openable(cx, tree_id) if e["how"] == "page"]
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
        entries = [e for e in fetch_list.openable(cx, tree_id) if e["how"] == "page" and (e["url"], e["save_as"]) not in tried]
        if not entries:
            break
        tried.add((entries[0]["url"], entries[0]["save_as"]))
        print(run_line(run_fetch(cx, tree_id, slug, entries[0], a.by, a.model, a.effort, a.budget, a.timeout)))

if __name__ == "__main__": main()
