#!/usr/bin/env python3
"""The rule's clause identifiers: every one a docstring cites is held by a doc, and each is written once.

usage: tests/checks/rule_ids.py [--verbose]

A clause of the rule that code implements opens with its identifier in bold brackets, `**[rule.points.2]**`: a dotted
name of the part and a serial within it, never renumbered (docs/RESEARCH-WORKFLOW.md names the files that hold them). A
function that implements a clause cites the identifier in its docstring, on its own line at the end: `Implements
[rule.points.2], [rule.points.3].` The identifiers are read from every .md under docs/; the citations from every
docstring (module, class or function, read with ast, nothing run) of the .py files under tools/ (connectors included),
tests/checks/ and app/person/server.py. Fails where a docstring cites an identifier no doc holds, and where a doc writes
one identifier twice. --verbose lists the identifiers no docstring cites, in the order of their parts and serials.
"""
import argparse, ast, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HELD = re.compile(r"\*\*\[(rule\.[a-z]+\.[0-9]+)\]\*\*")    # a clause's own identifier, where the clause opens
CITED = re.compile(r"\[(rule\.[a-z]+\.[0-9]+)\]")           # an identifier a docstring names

def held(root=ROOT):
    """{identifier: [(doc path, line)]} for every identifier the docs under docs/ write."""
    out = {}
    docs = os.path.join(root, "docs")
    for name in sorted(os.listdir(docs)):
        if not name.endswith(".md"): continue
        path = os.path.join("docs", name)
        with open(os.path.join(root, path)) as f:
            for n, line in enumerate(f, 1):
                for m in HELD.finditer(line): out.setdefault(m.group(1), []).append((path, n))
    return out

def sources(root=ROOT):
    """The .py files whose docstrings may cite an identifier, relative to root."""
    out = []
    for top in ("tools", os.path.join("tests", "checks")):
        for d, _, names in os.walk(os.path.join(root, top)):
            out += [os.path.relpath(os.path.join(d, n), root) for n in names if n.endswith(".py")]
    return sorted(out) + [os.path.join("app", "person", "server.py")]

def cited(root=ROOT):
    """{identifier: [(file, the def or class citing it, or <module>)]} from every docstring of sources()."""
    out = {}
    for path in sources(root):
        with open(os.path.join(root, path)) as f: tree = ast.parse(f.read(), path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)): continue
            doc = ast.get_docstring(node, clean=False)
            if not doc: continue
            where = getattr(node, "name", "<module>")
            for m in CITED.finditer(doc): out.setdefault(m.group(1), []).append((path, where))
    return out

def order(ident):
    _, part, serial = ident.split(".")
    return part, int(serial)

def check(root=ROOT):
    """(failures in words, the identifiers no docstring cites)."""
    h, c = held(root), cited(root)
    bad = [f"{ident} cited by {', '.join(f'{p} {w}' for p, w in sorted(set(where)))} is held by no doc under docs/"
           for ident, where in sorted(c.items(), key=lambda kv: order(kv[0])) if ident not in h]
    bad += [f"{ident} is written {len(at)} times: {', '.join(f'{p}:{n}' for p, n in at)}"
            for ident, at in sorted(h.items(), key=lambda kv: order(kv[0])) if len(at) > 1]
    uncited = [f"{ident} ({h[ident][0][0]}:{h[ident][0][1]})" for ident in sorted(h, key=order) if ident not in c]
    return bad, uncited

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    bad, uncited = check()
    for line in bad: print("FAIL " + line)
    h = held()
    print(f"{len(h)} identifiers held, {len(h) - len(uncited)} cited by a docstring, {len(uncited)} cited by none")
    if a.verbose:
        for line in uncited: print("uncited " + line)
    sys.exit(1 if bad else 0)

if __name__ == "__main__": main()
