#!/usr/bin/env python3
"""Cut a small GEDCOM out of the owner's own export for the harness: the named people, verbatim.

usage: tests/checks/cut_gedcom.py <export.ged> <out.ged> <INDI xref> [<INDI xref> ...] [--fam <FAM xref> ...]

The header and the submitter record are copied as they are; so are the INDI records named, the FAM records named, and every
SOUR record any copied record cites. The one edit is dropping a line whose value points at a record outside the cut (a
family, a person, a media object), with the lines under it. Nothing is written by hand and nothing is renamed, so the
harness file is the owner's file for these people, and cutting it again from a fresh export gives the same shape.
"""
import re, sys

def records(path):
    """The file's level-0 records in order: (xref or None, tag, lines) with the header first."""
    out = []; cur = None
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh.read().splitlines():
            m = re.match(r"^0 (?:@(\w+)@ )?(\w+)", line)
            if m: cur = [m.group(1), m.group(2), []]; out.append(cur)
            if cur: cur[2].append(line)
    return out

def keep_lines(lines, kept):
    """The record's lines with every pointer to a record outside the cut dropped, with the lines under it."""
    out = []; skip_below = None
    for line in lines:
        level = int(line.split(" ", 1)[0])
        if skip_below is not None and level > skip_below: continue
        skip_below = None
        m = re.match(r"^\d+ \w+ @(\w+)@\s*$", line)
        if m and m.group(1) not in kept: skip_below = level; continue
        out.append(line)
    return out

def main():
    args = sys.argv[1:]
    if len(args) < 3: sys.exit(__doc__)
    src, dst = args[0], args[1]; xrefs = set(); fams = set(); into = xrefs
    for a in args[2:]:
        if a == "--fam": into = fams; continue
        into.add(a.strip("@"))
    recs = records(src)
    by_xref = {x: (t, ls) for x, t, ls in recs if x}
    missing = [x for x in xrefs | fams if x not in by_xref]
    if missing: sys.exit(f"not in the export: {missing}")
    head = next(ls for x, t, ls in recs if t == "HEAD")
    subm = {x for x, t, ls in recs if t == "SUBM"}
    chosen = [x for x, t, ls in recs if x in xrefs or x in fams]
    cited = {m.group(1) for x in chosen for line in by_xref[x][1] for m in [re.search(r"@(\w+)@", line)] if m and by_xref.get(m.group(1), ("",))[0] == "SOUR"}
    kept = xrefs | fams | subm | cited
    with open(dst, "w", encoding="utf-8") as fh:
        for line in keep_lines(head, kept): fh.write(line + "\n")
        for x, t, ls in recs:
            if x in kept:
                for line in keep_lines(ls, kept): fh.write(line + "\n")
        fh.write("0 TRLR\n")
    print(f"{len(xrefs)} people, {len(fams)} families, {len(cited)} sources -> {dst}")

if __name__ == "__main__": main()
