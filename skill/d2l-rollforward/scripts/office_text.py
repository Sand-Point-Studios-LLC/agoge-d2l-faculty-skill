#!/usr/bin/env python3
"""Find and replace text inside Word (.docx) and PowerPoint (.pptx) files in the working copy.

    python3 office_text.py list
    python3 office_text.py find "office hours" [--regex]
    python3 office_text.py replace "Fall 2025" "Spring 2027" [--regex] [--apply]
    python3 office_text.py pdf-find "office hours"        (needs the pypdf package; PDFs cannot be edited)

Works on work/course/ (the unpacked copy; the original export is never touched). `replace` previews first and
only writes with --apply. Formatting is kept: text inside one run keeps that run's formatting; text that spans
several runs takes the formatting of the first run it touches. Everything else in each file is left byte for byte.
Standard library only. This reads and rewrites the files themselves: it cannot see tracked changes, comments
text boxes inside drawings, or text inside pictures, and it says so.
"""
import argparse, html, re, shutil, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path.cwd()
COURSE = ROOT / "work" / "course"

# which XML parts hold readable text, and the paragraph / text element names for each kind of file
KINDS = {
    ".docx": (re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$"), "w:p", "w:t"),
    ".pptx": (re.compile(r"^ppt/(slides/slide\d+|notesSlides/notesSlide\d+)\.xml$"), "a:p", "a:t"),
}


def die(msg):
    sys.exit("STOP: " + msg)


def files():
    if not COURSE.is_dir():
        die("there is no work/course folder yet. Run `rollforward.py unpack` first, from the folder that holds put-export-here.")
    return sorted(p for p in COURSE.rglob("*") if p.is_file() and p.suffix.lower() in KINDS)


def para_re(tag):
    return re.compile(r"<%s(?:\s[^>]*)?>.*?</%s>" % (tag, tag), re.S)


def text_re(tag):
    return re.compile(r"(<%s(?:\s[^>]*)?>)(.*?)(</%s>)" % (tag, tag), re.S)


def label(part, n_para):
    m = re.search(r"slides/slide(\d+)", part)
    if m:
        return "slide %s" % m.group(1)
    m = re.search(r"notesSlide(\d+)", part)
    if m:
        return "speaker notes, slide %s" % m.group(1)
    return "%s, paragraph %d" % (part.split("/")[-1].replace(".xml", ""), n_para)


def paragraphs(xml, ptag, ttag):
    """Yield (paragraph start, end, [(t_start_in_para, t_end, open, text, close)], joined text)."""
    pr, tr = para_re(ptag), text_re(ttag)
    for pm in pr.finditer(xml):
        runs = [(m.start(), m.end(), m.group(1), html.unescape(m.group(2)), m.group(3)) for m in tr.finditer(pm.group(0))]
        if runs:
            yield pm.start(), pm.end(), runs, "".join(r[3] for r in runs)


def matcher(pattern, regex, ci=False):
    return re.compile(pattern if regex else re.escape(pattern), re.I if ci else 0)


def scan(path):
    """[(part, label, paragraph text)] for every readable paragraph."""
    kind = path.suffix.lower()
    part_re, ptag, ttag = KINDS[kind]
    out = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if part_re.match(name):
                xml = z.read(name).decode("utf-8", errors="replace")
                for i, (_s, _e, _runs, text) in enumerate(((a, b, c, d) for a, b, c, d in paragraphs(xml, ptag, ttag)), 1):
                    out.append((name, label(name, i), text))
    return out


def cmd_list(_a):
    fs = files()
    if not fs:
        print("No Word or PowerPoint files in the working copy.")
        return
    for p in fs:
        try:
            n = len(scan(p))
        except zipfile.BadZipFile:
            print("  %-60s  not a valid Office file, skipped" % p.relative_to(COURSE).as_posix())
            continue
        print("  %-60s  %d paragraphs of text" % (p.relative_to(COURSE).as_posix(), n))
    print("\nNot read: text in pictures, text boxes drawn inside shapes in Word, tracked changes and comments. Old .doc and .ppt files are not supported.")


def snippet(text, m, w=50):
    return "...%s[%s]%s..." % (text[max(0, m.start() - w):m.start()], m.group(0), text[m.end():m.end() + w])


def cmd_find(a):
    rx = matcher(a.pattern, a.regex, True)
    total = 0
    for p in files():
        try:
            hits = [(lab, t, m) for _part, lab, t in scan(p) for m in rx.finditer(t)]
        except zipfile.BadZipFile:
            continue
        if hits:
            print("%s  (%d)" % (p.relative_to(COURSE).as_posix(), len(hits)))
            for lab, t, m in hits[:8]:
                print("    %s: %s" % (lab, snippet(t, m)))
            if len(hits) > 8:
                print("    ... and %d more in this file" % (len(hits) - 8))
        total += len(hits)
    print("\n%d match(es). Nothing changed." % total if total else "No matches in Word or PowerPoint files. (Text in pictures and old .doc/.ppt files is not searched.)")


def replace_in_xml(xml, ptag, ttag, rx, new):
    """Replace matches paragraph by paragraph, keeping the run formatting. Returns (new xml, count)."""
    out, last, count = [], 0, 0
    for ps, pe, runs, text in paragraphs(xml, ptag, ttag):
        ms = list(rx.finditer(text))
        if not ms:
            continue
        bounds, pos = [], 0
        for r in runs:
            bounds.append((pos, pos + len(r[3]))); pos += len(r[3])
        new_texts = [r[3] for r in runs]
        for m in reversed(ms):                      # right to left so earlier offsets stay valid
            rep = m.expand(new) if rx.groups and "\\" in new else new
            touched = [i for i, (b0, b1) in enumerate(bounds) if b0 < m.end() and b1 > m.start()]
            if not touched:
                continue
            f = touched[0]
            b0 = bounds[f][0]
            head = new_texts[f][:max(0, m.start() - b0)]
            lastb0, lastb1 = bounds[touched[-1]]
            tail = new_texts[touched[-1]][max(0, m.end() - lastb0):]
            if len(touched) == 1:
                new_texts[f] = head + rep + tail
            else:
                new_texts[f] = head + rep
                for i in touched[1:-1]:
                    new_texts[i] = ""
                new_texts[touched[-1]] = tail
            count += 1
        seg = xml[ps:pe]
        pieces, cur = [], 0
        for (ts, te, op, _old, cl), nt in zip(runs, new_texts):
            if " xml:space" not in op and (nt != nt.strip() or "  " in nt):
                op = op[:-1] + ' xml:space="preserve">'
            pieces.append(seg[cur:ts]); pieces.append(op + html.escape(nt, quote=False) + cl); cur = te
        pieces.append(seg[cur:])
        out.append(xml[last:ps]); out.append("".join(pieces)); last = pe
    out.append(xml[last:])
    return "".join(out), count


def cmd_replace(a):
    rx = matcher(a.old, a.regex)
    kinds_left = 0
    grand = 0
    for p in files():
        part_re, ptag, ttag = KINDS[p.suffix.lower()]
        try:
            zin = zipfile.ZipFile(p)
        except zipfile.BadZipFile:
            continue
        with zin:
            changes = {}
            n_file = 0
            for name in zin.namelist():
                if part_re.match(name):
                    xml = zin.read(name).decode("utf-8")
                    new_xml, n = replace_in_xml(xml, ptag, ttag, rx, a.new)
                    if n:
                        changes[name] = new_xml; n_file += n
            if not n_file:
                continue
            print("%s  (%d)" % (p.relative_to(COURSE).as_posix(), n_file))
            for _part, lab, t in scan(p):
                m = rx.search(t)
                if m:
                    print("    %s: %s" % (lab, snippet(t, m)))
                    break
            grand += n_file
            if not a.apply:
                continue
            tmp = Path(tempfile.mkdtemp()) / p.name
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if item.filename in changes:
                        data = changes[item.filename].encode("utf-8")
                    zout.writestr(item, data)
            with zipfile.ZipFile(tmp) as chk:           # must still open, and every changed part must still be well formed
                import xml.etree.ElementTree as ET
                assert chk.testzip() is None
                for name in changes:
                    ET.fromstring(chk.read(name))
            shutil.copyfile(tmp, p)
    if a.apply:
        print("\nReplaced %d occurrence(s) in Word and PowerPoint files in the working copy." % grand)
    else:
        print("\n%d occurrence(s). Nothing changed yet. Re-run with --apply to change them." % grand if grand else "No matches in Word or PowerPoint files.")
    if grand:
        print("Open one changed file in Word or PowerPoint before you rely on it: fonts and layout can only be checked by looking.")


def cmd_pdf_find(a):
    try:
        from pypdf import PdfReader
    except ImportError:
        die("reading PDFs needs the pypdf package (python -m pip install pypdf). PDFs cannot be edited either way: change the Word or "
            "PowerPoint file it came from and export a new PDF.")
    rx = matcher(a.pattern, a.regex, True)
    total = 0
    for p in sorted(COURSE.rglob("*.pdf")):
        try:
            pages = [pg.extract_text() or "" for pg in PdfReader(str(p)).pages]
        except Exception as e:
            print("  %s: could not read (%s)" % (p.relative_to(COURSE).as_posix(), type(e).__name__)); continue
        if not any(pages):
            print("  %s: no readable text (a scanned PDF?)" % p.relative_to(COURSE).as_posix()); continue
        for i, t in enumerate(pages, 1):
            for m in rx.finditer(t):
                print("%s  page %d: %s" % (p.relative_to(COURSE).as_posix(), i, snippet(t.replace("\n", " "), m)))
                total += 1
    print("\n%d match(es). PDFs cannot be changed by this kit: edit the source file and export a new PDF." % total)


def main():
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("list").set_defaults(f=cmd_list)
    s = sp.add_parser("find"); s.add_argument("pattern"); s.add_argument("--regex", action="store_true"); s.set_defaults(f=cmd_find)
    s = sp.add_parser("replace"); s.add_argument("old"); s.add_argument("new"); s.add_argument("--regex", action="store_true")
    s.add_argument("--apply", action="store_true"); s.set_defaults(f=cmd_replace)
    s = sp.add_parser("pdf-find"); s.add_argument("pattern"); s.add_argument("--regex", action="store_true"); s.set_defaults(f=cmd_pdf_find)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
