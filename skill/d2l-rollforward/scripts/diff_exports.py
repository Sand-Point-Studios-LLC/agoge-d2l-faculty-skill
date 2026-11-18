#!/usr/bin/env python3
"""Find out which XML setting a D2L checkbox controls, by diffing two exports.

How to use it (this is how every entry in references/settings-catalog.md was found):
  1. Export the course (or just the one quiz/assignment) from D2L.
  2. Change ONE setting in D2L. Export again.
  3. python3 diff_exports.py before.zip after.zip

It prints every element whose text changed, appeared or disappeared, grouped by file. Ids that D2L
reassigns on every export are ignored. Standard library only. Never modifies either export.
"""
import re, sys, zipfile
import xml.etree.ElementTree as ET
from collections import Counter

NOISE = re.compile(r"(^|/)(id|identifier|resource_code|ident|label)$|globalid|displayid|guid", re.I)


def tag(e):
    return e.tag.split("}")[-1]


def flat(el, path=""):
    here = path + "/" + tag(el)
    kids = list(el)
    for k, v in el.attrib.items():
        yield here + "@" + k.split("}")[-1], v
    if not kids:
        yield here, (el.text or "").strip()
        return
    n = Counter(tag(k) for k in kids)
    seen = Counter()
    for k in kids:
        seen[tag(k)] += 1
        yield from flat(k, here + ("[%d]" % seen[tag(k)] if n[tag(k)] > 1 else ""))


def load(path):
    out = {}
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.lower().endswith(".xml") and not name.startswith("basic_lti"):
                try:
                    root = ET.fromstring(z.read(name).decode("utf-8-sig"))
                except ET.ParseError:
                    continue
                out[name] = dict(flat(root))
    return out


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    a, b = load(sys.argv[1]), load(sys.argv[2])
    changed = 0
    for name in sorted(set(a) | set(b)):
        if name not in a or name not in b:
            print("%s: only in %s" % (name, "AFTER" if name in b else "BEFORE")); changed += 1; continue
        rows = []
        for k in sorted(set(a[name]) | set(b[name])):
            if NOISE.search(k):
                continue
            x, y = a[name].get(k), b[name].get(k)
            if x != y:
                rows.append("    %s\n        before: %s\n        after:  %s" % (k, x, y))
        if rows:
            changed += 1
            print(name); print("\n".join(rows))
    if not changed:
        print("No differences found. The setting may not travel in a package (see settings-catalog.md).")


if __name__ == "__main__":
    main()
