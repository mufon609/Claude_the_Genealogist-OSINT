"""Every global name a module reads is one it defines, imports or Python provides, and every name it takes from another module of
this repository is one that module defines.

A function that reads a name its module never binds fails only when it runs, and one no scenario reaches fails in the owner's
hands: the failure a function moved to another module makes when an import stayed behind. The check runs nothing. It
compiles each file and lets the compiler decide, in every code object (the module, each class body, function, lambda and generator), which reads are of the
module's own names rather than a local, a parameter, a closure's or an `except ... as` name: those are LOAD_GLOBAL, and
LOAD_NAME in a module or class body. A name is defined when the module binds it at its top level (a def, a class, an
assignment, an import, in a branch or not) or a function binds it under `global`; a name imported inside a function is that
function's own. A `from <module of the repository> import name` must name something that module defines at its top level, or
one of its submodules. A star import is reported, since what it brings in cannot be known without running it.

Files: every .py under tools/ (connectors included) and tests/checks/, and app/person/server.py. A name defined by running
code (`globals()[...] = ...`, `exec`) is not seen, so a module that does that is reported where it reads such a name; code
the compiler drops as unreachable (after a `return`) is not read, since it cannot fail. The check's own example (EXAMPLE) is
held to what the running Python's compiler says, so a Python that names its instructions otherwise fails that, never passes
by seeing nothing.
"""
import ast, builtins, dis, inspect, os, types
from common import ROOT

PROVIDED = set(dir(builtins)) | {"__file__", "__builtins__", "__cached__", "__path__"}   # what a module starts with besides the builtins
READS = {"LOAD_GLOBAL", "LOAD_NAME", "LOAD_FROM_DICT_OR_GLOBALS"}
STORES = {"STORE_GLOBAL", "STORE_NAME"}

def bodies(code, parent=None):
    """Every code object of a compiled module with the one that holds it, the module's own first."""
    yield code, parent
    for const in code.co_consts:
        if isinstance(const, types.CodeType): yield from bodies(const, code)

def class_body(code, root): return code is not root and not code.co_flags & inspect.CO_OPTIMIZED

def imports_of(tree):
    """Each `from module import name` of a tree as (function, line, module, name), name `*` for a star import, relative imports
    left out; function is the qualified name (as the compiler writes it) of the def or class holding it, `<module>` at the top
    level."""
    def walk(node, within, holder):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ImportFrom):
                if child.level == 0: yield from ((holder, child.lineno, child.module, a.name) for a in child.names)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)): yield from walk(child, f"{within}{child.name}.<locals>.", within + child.name)
            elif isinstance(child, ast.ClassDef): yield from walk(child, f"{within}{child.name}.", within + child.name)
            else: yield from walk(child, within, holder)
    return list(walk(tree, "", "<module>"))

def scan(source, path):
    """What one module says: (defined, reads, imports). defined is the set of names it binds at its top level; reads is
    [(function, line, name)], each name a body reads from the module's namespace that the module does not define and Python
    does not provide; imports is imports_of the source."""
    root = compile(source, path, "exec", dont_inherit=True)
    defined, own, loads = set(), {}, {}
    for code, _ in bodies(root):
        own[code], loads[code], line = set(), [], code.co_firstlineno
        for ins in dis.get_instructions(code):
            if ins.opname in READS or ins.opname in STORES:
                if ins.positions and ins.positions.lineno: line = ins.positions.lineno
                if ins.opname in READS: loads[code].append((ins.opname, ins.argval, line))
                elif ins.opname == "STORE_GLOBAL": defined.add(ins.argval)
                else:
                    own[code].add(ins.argval)
                    if code is root: defined.add(ins.argval)
    reads = set()
    for code, parent in bodies(root):
        for op, name, line in loads[code]:
            if name in defined or name in PROVIDED: continue
            visible = set() if op == "LOAD_GLOBAL" else own[code]
            if op == "LOAD_FROM_DICT_OR_GLOBALS" and class_body(parent, root): visible = visible | own[parent]
            if name not in visible: reads.add((code.co_qualname, line, name))
    return defined, sorted(reads, key=lambda r: (r[1], r[0], r[2])), imports_of(ast.parse(source, path))

def problems(files):
    """The unresolved names of files = {path: (module name, source)}, as tuples: ("read", path, function, line, name),
    ("import", path, function, line, module, name) for a name the repository's module does not define, ("star", path,
    function, line, module), ("syntax", path, message)."""
    found, out = {}, []
    for path, (module, source) in files.items():
        try: found[path] = scan(source, path)
        except SyntaxError as e: out.append(("syntax", path, f"{e.msg} (line {e.lineno})"))
    defined = {files[p][0]: d for p, (d, _, _) in found.items()}
    for path, (_, reads, imports) in found.items():
        out += [("read", path, function, line, name) for function, line, name in reads]
        for function, line, module, name in imports:
            if name == "*": out.append(("star", path, function, line, module))
            elif module in defined and name not in defined[module] and f"{module}.{name}" not in defined: out.append(("import", path, function, line, module, name))
    return out

def words(found):
    """Each unresolved name as one failure text: a name once per file, with every function and line that reads it."""
    where, said = {}, []
    at = lambda function, line: f"{'the top level' if function == '<module>' else function} (line {line})"
    for f in found:
        if f[0] == "read": where.setdefault((f[0], f[1], f[4]), []).append(at(f[2], f[3]))
        elif f[0] == "import": where.setdefault((f[0], f[1], f[4], f[5]), []).append(at(f[2], f[3]))
        elif f[0] == "star": said.append(f"{f[1]}: `from {f[4]} import *` in {at(f[2], f[3])} brings in names no one can check")
        else: said.append(f"{f[1]}: does not compile: {f[2]}")
    for key, spots in where.items():
        if key[0] == "read": said.append(f"{key[1]} reads {key[2]!r}, which it does not define, import or get from Python: {', '.join(spots)}")
        else: said.append(f"{key[1]} imports {key[3]!r} from {key[2]}, which defines no such name: {', '.join(spots)}")
    return said

def repository(root):
    """The files to read under a repository root, {path relative to it: (module name as the tools import it, source)}."""
    out = {}
    for base in ("tests/checks", "app/person", "tools"):
        for here, dirs, names in os.walk(os.path.join(root, base)):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for name in sorted(names):
                full = os.path.join(here, name); rel = os.path.relpath(full, root)
                if not name.endswith(".py") or (base == "app/person" and name != "server.py"): continue
                parts = os.path.relpath(full, os.path.join(root, base))[:-3].split(os.sep)
                module = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
                with open(full, encoding="utf-8") as fh: out[rel] = (module, fh.read())
    return out

EXAMPLE = '''import os
try: import tomllib
except ImportError: tomllib = None
from partner import real, ghost, sub
from never import *
LATE = os.sep
def reads(a, b=in_default):
    global SET_HERE
    SET_HERE = 1
    from partner import local_import, ghost_in_function
    kept = [x for x in a if in_comprehension(x)] + [local_import, LATE, END, tomllib]
    return kept, missing_in_function, (lambda q: q + in_lambda)
def setter(): return SET_HERE
END = 2
class Klass(in_base):
    attr = 1
    other = attr + in_class_body
    def method(self, attr):
        try: pass
        except ValueError as err: print(err, attr, in_except)
        def inner(): return attr + in_closure
        return inner, (g for g in attr if in_generator)
    def annotated(self) -> attr: pass
'''
PARTNER = "real = 1\nlocal_import = 2\nfrom elsewhere import sub_of_partner\n"
CASES = [("read", "example.py", "<module>", 7, "in_default"), ("read", "example.py", "<module>", 15, "in_base"), ("read", "example.py", "Klass", 17, "in_class_body"),
         ("read", "example.py", "reads", 11, "in_comprehension"), ("read", "example.py", "reads", 12, "missing_in_function"), ("read", "example.py", "reads.<locals>.<lambda>", 12, "in_lambda"),
         ("read", "example.py", "Klass.method", 20, "in_except"), ("read", "example.py", "Klass.method.<locals>.inner", 21, "in_closure"), ("read", "example.py", "Klass.method.<locals>.<genexpr>", 22, "in_generator"),
         ("import", "example.py", "<module>", 4, "partner", "ghost"), ("import", "example.py", "reads", 10, "partner", "ghost_in_function"), ("star", "example.py", "<module>", 5, "never")]

def example():
    """EXAMPLE and a partner module it imports from, run through the same reading as the repository: the unresolved names
    CASES lists, and no other, among constructs where a name is its own (a parameter, an `except ... as`, a comprehension's
    variable, a name set under `global`, one defined further down, one imported in a function, one a method's annotation
    reads from the class)."""
    got = sorted(problems({"example.py": ("example", EXAMPLE), "partner.py": ("partner", PARTNER), "partner/sub.py": ("partner.sub", "")}), key=repr)
    return [] if got == sorted(CASES, key=repr) else [f"the check's own example gave {got}, expected {CASES}"]

def check(root=ROOT):
    """The failure texts of the repository at root: the example's, then every unresolved name of its files."""
    return example() + words(problems(repository(root)))
