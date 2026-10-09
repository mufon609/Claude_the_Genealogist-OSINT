#!/usr/bin/env python3
"""The tools' imports against their layers: every import cycle among the modules, and every import that reaches a layer
above its own.

usage: tests/checks/import_cycles.py [--verbose]

The graph is read with ast from tools/*.py, the package tools/connectors/ as one module (`connectors`) and
app/person/server.py (`server`), nothing run: an edge is any `import m` or `from m import ...` of another module of that
set, at the top level or inside a function or class alike, since a deferred import is still a dependency, only one Python
resolves late. Imports of the standard library are not edges. LAYERS below is the layering the tools keep (schema/README.md, Layers):
a module imports from its own layer or the layers below it, never from one above, and no import closes a cycle.

Prints each elementary cycle once, starting from its first module by name, with the lines of each import that makes it
(and the def holding a deferred one); each pair of modules whose import reaches a layer above the importer's; each module
of the set the table does not place; then the number of imports deferred inside functions, per module. Exits nonzero
when any cycle, upward import or unplaced module exists. --verbose also prints every edge. Run by tools/check.py.
"""
import argparse, ast, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LAYERS = {
    0: ["treelib", "forms"],
    1: ["catalog"],
    2: ["readers", "matcher", "households", "resolve_places", "footprint", "checklist", "connectors"],
    3: ["log_search", "plan", "attach", "fetch_list"],
    4: ["rule", "decisions", "copies", "merges", "reconsider", "conflicts", "arrival", "facts", "proof", "cards", "overview"],
    5: ["conclude", "extract", "match", "fetches", "turn", "turns", "queue", "run_step", "run_task", "tree", "ingest_gedcom", "initdb", "backup", "tombstone",
        "cite", "backfill_aliases", "attach_inbox", "check", "server"],
}
LAYER = {m: n for n, ms in LAYERS.items() for m in ms}

def modules(root=ROOT):
    """{module name: [paths relative to root]} for tools/*.py, tools/connectors/*.py as `connectors`, and
    app/person/server.py as `server`."""
    out = {name[:-3]: [os.path.join("tools", name)] for name in sorted(os.listdir(os.path.join(root, "tools"))) if name.endswith(".py")}
    out["connectors"] = [os.path.join("tools", "connectors", name) for name in sorted(os.listdir(os.path.join(root, "tools", "connectors"))) if name.endswith(".py")]
    out["server"] = [os.path.join("app", "person", "server.py")]
    return out

def edges(root=ROOT):
    """[(importer, imported, place, holder)] over modules(): place is the import's line, preceded by its file's name where
    the module is a package; holder is the qualified name of the def or class the import sits in, None at the top level."""
    known, out = modules(root), []
    def walk(node, name, place, holder):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                walk(child, name, place, f"{holder}.{child.name}" if holder else child.name)
                continue
            targets = []
            if isinstance(child, ast.Import): targets = [a.name.split(".")[0] for a in child.names]
            elif isinstance(child, ast.ImportFrom) and child.level == 0 and child.module: targets = [child.module.split(".")[0]]
            out.extend((name, t, place(child.lineno), holder) for t in targets if t in known and t != name)
            walk(child, name, place, holder)
    for name, paths in known.items():
        for rel in paths:
            with open(os.path.join(root, rel), encoding="utf-8") as fh: tree = ast.parse(fh.read(), rel)
            walk(tree, name, (lambda line, f=os.path.basename(rel): f"{f}:{line}") if len(paths) > 1 else str, None)
    return out

def cycles(graph):
    """Every elementary cycle of graph = {node: set of nodes}, each once, as a list of nodes starting from its least node
    by name: a walk from each node through nodes after it in that order only."""
    order = sorted(graph); found = []
    for i, start in enumerate(order):
        allowed = set(order[i:])
        def walk(node, path, on):
            for nxt in sorted(graph.get(node, ())):
                if nxt == start: found.append(path[:])
                elif nxt in allowed and nxt not in on:
                    on.add(nxt); path.append(nxt); walk(nxt, path, on); path.pop(); on.discard(nxt)
        walk(start, [start], {start})
    return sorted(found, key=lambda c: (len(c), c))

def measure(root=ROOT):
    """(cycles with each import's lines, upward imports, unplaced modules, deferred imports per module, edges)."""
    es = edges(root); graph, where = {}, {}
    for a, b, line, holder in es:
        graph.setdefault(a, set()).add(b)
        where.setdefault((a, b), []).append(f"{line}" + (f" in {holder}" if holder else ""))
    found = [(c, [(c[k], c[(k + 1) % len(c)], where[(c[k], c[(k + 1) % len(c)])]) for k in range(len(c))]) for c in cycles(graph)]
    upward = sorted({(a, b) for a, b, _, _ in es if a in LAYER and b in LAYER and LAYER[b] > LAYER[a]})
    unplaced = sorted(m for m in modules(root) if m not in LAYER)
    deferred = {}
    for a, _, _, holder in es:
        if holder: deferred[a] = deferred.get(a, 0) + 1
    return found, [(a, LAYER[a], b, LAYER[b], where[(a, b)]) for a, b in upward], unplaced, deferred, es

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    found, upward, unplaced, deferred, es = measure()
    print(f"{len(found)} cycles")
    for c, steps in found:
        print("  " + " -> ".join(c + [c[0]]))
        for a, b, lines in steps: print(f"      {a} imports {b}: line {', '.join(lines)}")
    print(f"{len(upward)} imports reach a layer above their own")
    for a, la, b, lb, lines in upward: print(f"  {a} (layer {la}) imports {b} (layer {lb}): line {', '.join(lines)}")
    print(f"{len(unplaced)} modules the layer table does not place" + (": " + ", ".join(unplaced) if unplaced else ""))
    print("imports deferred inside functions: " + (", ".join(f"{m} {n}" for m, n in sorted(deferred.items(), key=lambda kv: (-kv[1], kv[0]))) or "none"))
    if args.verbose:
        print("every edge:")
        for a, b, line, holder in sorted(es): print(f"  {a} -> {b} line {line}" + (f" in {holder}" if holder else ""))
    return 1 if found or upward or unplaced else 0

if __name__ == "__main__":
    sys.exit(main())
