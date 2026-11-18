#!/usr/bin/env python3
"""Roll a D2L (Brightspace) course export forward to a new term.

Standard library only. Never modifies the original export: every command reads from
put-export-here/ or work/ and writes to work/ or ready-to-import/.

Commands
  unpack     EXPORT.zip            unpack into work/course/
  inventory                        counts, dates, and mentions of old terms
  shift      --days N [--from-date D --to-date D] [--apply]   preview, then move every stored date by whole days
  set        quiz --numbers 3,7 --field attempts_allowed --value 2 [--apply]   change a quiz setting (preview first)
  replace    OLD NEW [--apply]     show (default) or apply a text replacement
  audit                            compare quizzes to class-standards.json
  settings                         plain-English quiz and assignment settings in the unpacked course
  check                            problems that would break an import (also runs inside pack)
  report                           one document with every setting the course has (ready-to-import/COURSE-SETTINGS.html)
  pack                             build ready-to-import/<name>.zip and CHANGES.md
"""
import argparse, os, re, sys, zipfile, json, shutil
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    LOCAL = ZoneInfo("America/Detroit")
except Exception:          # tzdata missing (some Windows installs)
    LOCAL = None

ROOT = Path.cwd()   # the folder the faculty member opened in the agent (Roll-Forward)
WORK = ROOT / "work"
COURSE = WORK / "course"
OUT = ROOT / "ready-to-import"
LOG = WORK / "changes.jsonl"
KIT_VERSION = "0.1.0"
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
TEXT_EXT = {".xml", ".html", ".htm", ".txt", ".css", ".js", ".json", ".csv"}
# Files that mean the export contains people, not just course material.
STUDENT_DATA = re.compile(r"(classlist|userdata|user_data|submissions?/|discussion_posts|user_?progress)", re.I)


def quiz_files():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import course_report
    return course_report.quiz_paths(COURSE)


def export_name():
    """Name of the export that was unpacked (not just the first zip in the folder)."""
    try:
        for ln in LOG.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            if r.get("kind") == "unpack":
                return Path(r["source"]).stem
    except (OSError, ValueError, KeyError):
        pass
    z = next(iter(sorted((ROOT / "put-export-here").glob("*.zip"))), None)
    return z.stem if z else "course"


def die(msg):
    sys.exit("STOP: " + msg)


def log(kind, **kw):
    WORK.mkdir(exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": kind, **kw}) + "\n")


NOT_UTF8 = []


def text_files():
    """Text files that are valid UTF-8. Others (old Word-saved pages, spreadsheets saved as CSV) are never rewritten:
    rewriting would turn accented letters into question marks. They are collected in NOT_UTF8 so a command can say so."""
    NOT_UTF8.clear()
    for p in sorted(COURSE.rglob("*")):
        if p.is_file() and p.suffix.lower() in TEXT_EXT:
            try:
                p.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                NOT_UTF8.append(p.relative_to(COURSE).as_posix())
                continue
            yield p


def say_not_utf8():
    if NOT_UTF8:
        print("NOTE: %d file(s) are not plain UTF-8 text, so they were left alone (a change could damage accented letters): %s%s" % (
            len(NOT_UTF8), ", ".join(NOT_UTF8[:5]), " and more" if len(NOT_UTF8) > 5 else ""))


def read(p):
    """Return (text, bom). BOM must survive: D2L's own files carry one."""
    b = p.read_bytes()
    bom = b.startswith(b"\xef\xbb\xbf")
    return b[3:].decode("utf-8") if bom else b.decode("utf-8", errors="replace"), bom


def write(p, text, bom):
    p.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def cmd_unpack(a):
    z = Path(a.export)
    if not z.is_file():
        found = sorted(Path(ROOT / "put-export-here").glob("*.zip"))
        if len(found) != 1:
            die("give the path to the export zip (found %d in put-export-here)" % len(found))
        z = found[0]
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
        if "imsmanifest.xml" not in names:
            die("imsmanifest.xml is not at the top of this zip. Is this a D2L export?")
        bad = [n for n in names if STUDENT_DATA.search(n)]
        if bad:
            die("this export looks like it contains student information (%s). "
                "Re-export with the student boxes unticked." % bad[0])
        if COURSE.exists():
            shutil.rmtree(COURSE)
        COURSE.mkdir(parents=True)
        root = COURSE.resolve()
        for n in names:
            dest = (COURSE / n).resolve()
            if root not in dest.parents and dest != root:
                die("unsafe path in zip: " + n)
        zf.extractall(COURSE)
    if LOG.exists():
        LOG.unlink()
    log("unpack", source=z.name, files=len(names))
    print("Unpacked %d files from %s" % (len(names), z.name))


def to_local(s):
    d = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return d.astimezone(LOCAL) if LOCAL else d


def shift_one(s, days):
    """Shift a stored-UTC stamp by whole *local* days, so 11:59 PM stays 11:59 PM across DST."""
    d = to_local(s)
    if LOCAL:
        naive = d.replace(tzinfo=None) + timedelta(days=days)
        d = naive.replace(tzinfo=LOCAL)
    else:
        d = d + timedelta(days=days)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


TS_RE = re.compile(
    r"(<(?:\w+:)?timestamp>\s*)"
    r"<(\w+:)?month>(\d+)</(?:\w+:)?month>\s*<(?:\w+:)?day>(\d+)</(?:\w+:)?day>\s*"
    r"<(?:\w+:)?year>(\d+)</(?:\w+:)?year>\s*<(?:\w+:)?hour>(\d+)</(?:\w+:)?hour>\s*"
    r"<(?:\w+:)?minutes>(\d+)</(?:\w+:)?minutes>\s*<(?:\w+:)?seconds>(\d+)</(?:\w+:)?seconds>")


def shift_ts(m, days):
    """Quiz dates are decomposed UTC fields, not ISO strings. Shift them the same way."""
    mo, d, y, h, mi, se = (int(m.group(i)) for i in range(3, 9))
    new = shift_one("%04d-%02d-%02dT%02d:%02d:%02d" % (y, mo, d, h, mi, se), days)
    dt = datetime.strptime(new, "%Y-%m-%dT%H:%M:%S")
    pre = m.group(2) or ""
    f = lambda n, v: "<%s%s>%d</%s%s>" % (pre, n, v, pre, n)
    return m.group(1) + f("month", dt.month) + f("day", dt.day) + f("year", dt.year) + \
        f("hour", dt.hour) + f("minutes", dt.minute) + f("seconds", dt.second)


def cmd_inventory(a):
    need_course()
    man = (COURSE / "imsmanifest.xml").read_text(encoding="utf-8-sig")
    mats = Counter(re.findall(r'material_type="([^"]+)"', man))
    print("Tools and content in this export:")
    for k, v in sorted(mats.items()):
        print("  %-22s %d" % (k, v))
    dates = []
    in_parts = 0
    for p in text_files():
        t, _ = read(p)
        dates += [(m, p.name) for m in DATE_RE.findall(t)]
        in_parts += len(TS_RE.findall(t))
    print("\nDates found: %d (%d stored as date-times, %d quiz dates stored in parts)" % (len(dates) + in_parts, len(dates), in_parts))
    if dates:
        ls = sorted(to_local(d).strftime("%Y-%m-%d %a") for d, _ in dates)
        print("  earliest %s, latest %s (Eastern)" % (ls[0], ls[-1]))
    pat = re.compile(r"\b(Fall|Spring|Summer|FS|SS|US)\s?'?(20)?\d{2}\b", re.I)
    hits = Counter()
    for p in text_files():
        t, _ = read(p)
        for m in pat.finditer(t):
            hits[m.group(0)] += 1
    print("\nMentions of a semester:")
    for k, v in hits.most_common(15):
        print("  %-14s %d" % (k, v))
    if not hits:
        print("  none")
    print("\nNote: dates written in prose (\"due the Friday after break\") are NOT in the count above.")


def cmd_shift(a):
    need_course()
    if LOCAL is None:
        die("time zone data is missing on this computer, so 11:59 PM could end up an hour off after a daylight-saving change. "
            "Install it with:  python -m pip install tzdata   (then run this again).")
    if a.from_date and a.to_date:
        d1 = datetime.strptime(a.from_date, "%Y-%m-%d")
        d2 = datetime.strptime(a.to_date, "%Y-%m-%d")
        days = (d2 - d1).days
        if days % 7:
            print("WARNING: that shift is not a whole number of weeks (%d days), so weekdays change." % days)
    elif a.days is not None:
        days = a.days
    else:
        die("give --days N, or --from-date and --to-date (first day of class, old and new)")
    if a.apply and LOG.exists() and not a.again:
        for ln in LOG.read_text(encoding="utf-8").splitlines():
            if json.loads(ln).get("kind") == "shift":
                die("dates in this working copy were already moved. Moving them again would stack the shifts. "
                    "Run `unpack` to start over from the original, or add --again if you really mean it.")
    n = iso_n = parts_n = 0
    files = 0
    per_file = []
    pending = []                   # (path, new text, bom): written only after every file was computed without error
    seen = []                      # (old, new) examples of date-times, for the preview
    every = []                     # (old, new) for every date-time, so the preview can match inventory
    for p in text_files():
        t, bom = read(p)
        c = [0]
        def f(m):
            try:
                datetime.strptime(m.group(0), "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                return m.group(0)               # looks like a date but is not one (0000-00-00..., 2026-02-30...)
            c[0] += 1
            if re.search(r"release_date>\s*$", t[max(0, m.start() - 40):m.start()]):
                # quiz extra-view release dates are LOCAL wall-clock, not UTC: no zone conversion
                d = datetime.strptime(m.group(0), "%Y-%m-%dT%H:%M:%S") + timedelta(days=days)
                return d.strftime("%Y-%m-%dT%H:%M:%S")
            new_ = shift_one(m.group(0), days)
            every.append((m.group(0), new_))
            if p.name in ("dropbox_d2l.xml", "news_d2l.xml", "schedule_d2l.xml") and len(seen) < 4000:
                seen.append((m.group(0), new_))      # the dates a person recognizes, for the preview
            return new_
        new = DATE_RE.sub(f, t)
        iso_n += c[0]
        k0 = c[0]
        def g(m):
            try:
                out = shift_ts(m, days)
            except ValueError:
                return m.group(0)
            c[0] += 1
            return out
        new = TS_RE.sub(g, new)
        parts_n += c[0] - k0
        if c[0]:
            if a.apply:
                pending.append((p, new, bom))
            files += 1
            n += c[0]
            per_file.append((c[0], p.name))
    detail = "%d dates (%d stored as date-times, %d quiz dates stored in parts)" % (n, iso_n, parts_n)
    say_not_utf8()
    if a.apply:
        log("shift", days=days, dates=n, files=files)
        for p_, new_, bom_ in pending:
            write(p_, new_, bom_)
        print("Moved %s in %d files by %+d days." % (detail, files, days))
    else:
        print("PREVIEW: moving every stored date by %+d days would change %s in %d files." % (days, detail, files))
        groups = Counter()
        for c_, name in per_file:
            groups["quiz files" if name.startswith("quiz_d2l_") else name] += c_
        for name, c_ in groups.most_common():
            print("  %4d  %s%s" % (c_, name, "" if name != "quiz files" else " (%d files)" % sum(1 for _, nm in per_file if nm.startswith("quiz_d2l_"))))
        if seen:
            first = min(seen, key=lambda r: r[0]); last = max(seen, key=lambda r: r[0])
            show = lambda s: to_local(s).strftime("%a %b %d %Y, %I:%M %p")
            print("\nExamples from your assignments, announcements and calendar, in Eastern time (compare these with your new calendar):")
            print("  earliest:  %s  ->  %s" % (show(first[0]), show(first[1])))
            print("  latest:    %s  ->  %s" % (show(last[0]), show(last[1])))
            if every:
                lo = min(every, key=lambda r: r[0]); hi = max(every, key=lambda r: r[0])
                if (lo[0], hi[0]) != (first[0], last[0]):
                    print("Across every stored date-time (old gradebook, quiz and manifest entries too; this is the range `inventory` shows):")
                    print("  earliest:  %s  ->  %s" % (show(lo[0]), show(lo[1])))
                    print("  latest:    %s  ->  %s" % (show(hi[0]), show(hi[1])))
        print("\nNothing has changed. Dates written in page text, Word files and slides are not moved.\n"
              "When you are happy with this, run the same command again with --apply.")


TITLE_RES = [re.compile(r"<title[^>]*>\s*([^<]{1,120}?)\s*</title>", re.I),
             re.compile(r" title=\"([^\"]{1,120})\""), re.compile(r"<name>\s*([^<]{1,120}?)\s*</name>", re.I)]
CODE_CHAR = re.compile(r"[A-Za-z0-9_]")


def item_name(p, t):
    """A person-readable name for the file a match is in: its own title when it has one."""
    for rx in TITLE_RES:
        m = rx.search(t)
        if m:
            return m.group(1)
    return p.name


WORD_ATTRS = {"title", "alt", "label", "name", "description"}


def kind_of(t, i, old, suffix):
    """'word' (students read it), 'code' (a course code such as SS26-ACC-826-001) or 'link' (an id, href or src: never changed)."""
    if suffix in (".xml", ".html", ".htm"):
        lt, gt = t.rfind("<", 0, i), t.rfind(">", 0, i)
        if lt > gt:                                           # inside a tag, so inside an attribute
            m = re.search(r'([\w:.-]+)\s*=\s*"[^"]*$', t[max(0, i - 400):i])
            if not (m and m.group(1).split(":")[-1].lower() in WORD_ATTRS):
                return "link"
    before = t[i - 1] if i > 0 else " "
    after = t[i + len(old):i + len(old) + 4]
    if re.match(r"[-_]\d{1,2}(?![0-9A-Za-z])", after):        # 2025-26 is a range of years
        return "word"
    if before.isalnum() and before.isascii() or after[:1].isalnum() and after[:1].isascii():
        return "code"
    if re.match(r"[-_][A-Z0-9]", after) or (before in "-_" and i > 1 and re.match(r"[A-Z0-9]", t[i - 2])):
        return "code"
    return "word"


def cmd_replace(a):
    need_course()
    from xml.sax.saxutils import escape
    import xml.etree.ElementTree as ET
    skip_codes = getattr(a, "skip_codes", False)
    rows = []
    for p in text_files():
        t, bom = read(p)
        hits = [m.start() for m in re.finditer(re.escape(a.old), t)]
        if not hits:
            continue
        kinds = {"word": [], "code": [], "link": []}
        for i in hits:
            kinds[kind_of(t, i, a.old, p.suffix.lower())].append(i)
        rows.append((p, t, bom, kinds))
    say_not_utf8()
    if not rows:
        print("Did not find %r in the course's pages and settings files. Word and PowerPoint files are searched separately: office_text.py find %r" % (a.old, a.old))
        return
    tot = {k: sum(len(r[3][k]) for r in rows) for k in ("word", "code", "link")}

    def ctx(t, i):
        return "...%s[%s]%s..." % (t[max(0, i - 45): i].replace(chr(10), " "), a.old, t[i + len(a.old): i + len(a.old) + 45].replace(chr(10), " "))
    private = lambda p: p.name.startswith("quiz_d2l_") or p.name.startswith("questiondb")
    if not a.apply:
        print("Where %r appears: %d in ordinary text, %d inside course codes, %d inside ids or links (those are never changed).\n" % (
            a.old, tot["word"], tot["code"], tot["link"]))
        for p, t, bom, k in rows:
            print("%s  [%s]" % (item_name(p, t), p.relative_to(COURSE)))
            if private(p):
                print("    %d in ordinary text, %d in codes, %d in ids (quiz text is not shown here)" % (len(k["word"]), len(k["code"]), len(k["link"])))
                continue
            for i in k["word"][:3]:
                print("    text:  " + ctx(t, i))
            if len(k["word"]) > 3:
                print("    ... and %d more in ordinary text in this file" % (len(k["word"]) - 3))
            for i in k["code"][:1]:
                print("    code:  " + ctx(t, i))
            if len(k["code"]) > 1:
                print("    ... and %d more inside codes in this file" % (len(k["code"]) - 1))
            if k["link"]:
                print("    %d inside an id or link in this file (left as is)" % len(k["link"]))
        print()
        print("%d occurrence(s) in %d file(s) could be changed. Nothing changed yet." % (tot["word"] + tot["code"], len(rows)))
        print("This searched pages and settings files only. Word and PowerPoint files are searched separately: office_text.py find %r (PDFs cannot be edited)." % a.old)
        if tot["code"]:
            print("NOTE: %d of these sit inside a course code (for example SS26-ACC-826-001-...), which students do not read as words. "
                  "Replacing them keeps the new course's codes in step with the term; leaving them keeps the old codes. "
                  "Add --skip-codes to change only the ordinary text. Decide with the faculty member before --apply." % tot["code"])
        if tot["link"]:
            print("NOTE: %d more are inside ids, file names or links. A package cannot rename files, so these are never changed." % tot["link"])
        print("Re-run with --apply to change them.")
        return
    done_w = done_c = left_c = 0
    for p, t, bom, k in rows:
        new_text = a.new
        if p.suffix.lower() in (".xml", ".html", ".htm"):
            new_text = escape(a.new, {'"': "&quot;"})       # & < and " in new text must be escaped or the file breaks
        take = sorted(k["word"] + ([] if skip_codes else k["code"]))
        if not take:
            left_c += len(k["code"])
            continue
        out, last = [], 0
        for i in take:
            out.append(t[last:i]); out.append(new_text); last = i + len(a.old)
        out.append(t[last:]); out = "".join(out)
        if p.suffix.lower() == ".xml":
            try:
                ET.fromstring(out.encode("utf-8"))
            except ET.ParseError as e:
                print("  SKIPPED %s: the change would break the file (%s)" % (p.relative_to(COURSE), e))
                continue
        write(p, out, bom)
        done_w += len(k["word"]); done_c += 0 if skip_codes else len(k["code"])
        left_c += len(k["code"]) if skip_codes else 0
    log("replace", old=a.old, new=a.new, count=done_w + done_c, in_codes=done_c, skipped_codes=left_c, left_in_ids=tot["link"])
    print("Replaced %d occurrence(s): %d in ordinary text, %d inside course codes%s. %d inside ids or links were left as they are." % (
        done_w + done_c, done_w, done_c, (" (%d code occurrences left as they were)" % left_c) if left_c else "", tot["link"]))


CHECK_LOG = WORK / "check-log.json"


def run_checks():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import package_checks
    results = package_checks.run_all(COURSE)
    package_checks.record(CHECK_LOG, results)
    import argparse as _ap
    cmd_audit(_ap.Namespace(quiet=True))      # keeps the quiz-settings row current
    errors, warnings = [], []
    for r in results:
        (errors if r["severity"] == "error" else warnings).extend(r["problems"])
    return errors, warnings


def write_quality_report(quiet=False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import course_report
    OUT.mkdir(exist_ok=True)
    name = export_name()
    course_report.quality_report(CHECK_LOG, OUT / "QUALITY-REPORT.html", name)
    if not quiet:
        print("\nReadable report: %s" % (OUT / "QUALITY-REPORT.html"))


def print_status():
    import package_checks
    print("\nQuality checks, last run:")
    for ti, when, res in package_checks.status_rows(CHECK_LOG):
        print("  %-34s %-17s %s" % (res, when, ti))


def cmd_check(a):
    need_course()
    errors, warnings = run_checks()
    for e in errors:
        print("PROBLEM: " + e)
    for w in warnings:
        print("CHECK:   " + w)
    if not (errors or warnings):
        print("No problems found.")
    else:
        print("\n%d problem(s) that stop a package, %d thing(s) to look at." % (len(errors), len(warnings)))
    print_status()
    write_quality_report()


def cmd_pack(a):
    need_course()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    errors, warnings = run_checks()
    if errors:
        for e in errors:
            print("PROBLEM: " + e)
        die("fix the problems above first. D2L would refuse this package.")
    if warnings:
        print("%d thing(s) to look at before you import (none stops the package; details are in QUALITY-REPORT.html):" % len(warnings))
        for w in warnings:
            print("  - " + (w if len(w) <= 240 else w[:240].rsplit(" ", 1)[0] + " ... (full list in QUALITY-REPORT.html)"))
    OUT.mkdir(exist_ok=True)
    base = export_name()
    src = next((z for z in (ROOT / "put-export-here").glob("*.zip") if z.stem == base), None) or next((ROOT / "put-export-here").glob("*.zip"), None)
    renamed = False
    if LOG.exists():
        for ln in LOG.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            if r.get("kind") == "replace" and r.get("old") and r["old"] in base:
                base = base.replace(r["old"], r["new"]); renamed = True
    name = base + "_rolled-forward.zip"
    # Hrefs are relative to the manifest; the 128-char path limit is D2L's.
    long_ = [str(p.relative_to(COURSE)) for p in COURSE.rglob("*")
             if p.is_file() and len(str(p.relative_to(COURSE))) > 128]
    if long_:
        die("path longer than 128 characters, D2L will reject it: " + long_[0])
    target = OUT / name
    print("\nBuilding the package. A big course takes about a minute; nothing is wrong while it is quiet.")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(COURSE / "imsmanifest.xml", "imsmanifest.xml")   # manifest first, at the root
        for p in sorted(COURSE.rglob("*")):
            if p.is_file() and p.name != "imsmanifest.xml":
                zf.write(p, p.relative_to(COURSE).as_posix())
    with zipfile.ZipFile(target) as zf:
        assert zf.testzip() is None
    import hashlib
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["# What changed in this roll-forward", "", "- **when**: %s" % stamp, "- **kit version**: %s" % KIT_VERSION]
    if src:
        h = hashlib.sha256()
        with open(src, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        lines.append("- **original export**: %s (%.1f MB, sha256 %s)" % (src.name, src.stat().st_size / 1e6, h.hexdigest()))
    if LOG.exists():
        for ln in LOG.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            k = r.pop("kind")
            if k == "set":
                lines += ["- **changed a setting**: " + d for d in r["detail"]]
            elif k == "unpack":
                lines.append("- **unpacked**: %s (%s files)" % (r.get("source"), r.get("files")))
            elif k == "shift":
                lines.append("- **moved dates**: %s stored dates in %s files by %+d days" % (r.get("dates"), r.get("files"), r.get("days", 0)))
            elif k == "replace":
                lines.append("- **replaced text**: \"%s\" with \"%s\", %s times (%s of them inside course codes or ids%s)" % (
                    r.get("old"), r.get("new"), r.get("count"), r.get("in_codes", 0),
                    ", %s code occurrences deliberately left" % r["skipped_codes"] if r.get("skipped_codes") else ""))
            else:
                lines.append("- **%s**: %s" % (k, ", ".join("%s=%s" % kv for kv in r.items())))
    lines.append("- **not changed**: dates written in page text, Word files and slides are not moved (see QUALITY-REPORT.html)")
    (OUT / "CHANGES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    import course_report
    course_report.changes_page(lines, OUT / "CHANGES.html", target.stem)
    hist = OUT / "history"
    hist.mkdir(exist_ok=True)
    course_report.changes_page(lines, hist / ("CHANGES-%s.html" % datetime.now().strftime("%Y%m%d-%H%M")), target.stem)
    write_quality_report(quiet=True)
    print("\nDONE. Your package is %s (%.1f MB)." % (target.name, target.stat().st_size / 1e6))
    print("  Folder: %s" % OUT)
    if renamed:
        print("  The package name uses the new term, from your replace. The shell's own name is set in D2L, not here.")
    else:
        print("  The package keeps the original export's name (it may still show the old term). The name does not affect the import; name the new shell yourself in D2L.")
    print("  Next: import it into a NEW, EMPTY course shell (never one with students), then work through the after-import checklist.")
    print("  What changed: %s" % (OUT / "CHANGES.html"))
    print("  Quality report: %s" % (OUT / "QUALITY-REPORT.html"))


LABELS = {
    "attempts_allowed": "attempts allowed (0 = unlimited)", "time_limit": "time limit (minutes)",
    "enforce_time_limit": "time limit enforced", "grace_period": "grace period (minutes)",
    "is_forward_only": "forward only (no going back)", "show_clock": "show clock",
    "is_attempt_Rldb": "LockDown Browser for attempts", "is_subview_Rldb": "LockDown Browser for review",
    "has_schedule_event": "calendar entry", "annotation_tools_enabled": "annotation tools (bookmark, strike through)",
    "show_correct_answers": "shows correct answers", "response_display_type_id": "what a view shows (id)",
    "release_date": "view opens (LOCAL time, not UTC)", "show_class_average": "shows class average",
    "show_score_distribution": "shows score distribution", "is_active": "active",
}


def flat(el, path=""):
    tag = el.tag.split("}")[-1]
    here = path + "/" + tag
    kids = list(el)
    if not kids:
        yield here, (el.text or "").strip()
        return
    seen = Counter()
    for k in kids:
        t = k.tag.split("}")[-1]
        seen[t] += 1
        yield from flat(k, here + ("[%d]" % seen[t] if sum(1 for x in kids if x.tag == k.tag) > 1 else ""))


def cmd_settings(a):
    """Describe each quiz's setup in words. Unknown settings are listed raw so nothing is hidden."""
    import xml.etree.ElementTree as ET
    need_course()
    files = quiz_files()
    if not files:
        print("No quizzes in this export.")
    for p in files:
        root = ET.fromstring(read(p)[0])
        title = root.find(".//{*}assessment")
        title = (title if title is not None else root).get("title", p.name)
        print("\n== %s ==" % title)
        for path, val in flat(root):
            if "/assess_procextension" not in path and "/assessfeedback" not in path:
                continue
            leaf = path.split("/")[-1].split("[")[0].split(":")[-1]
            if leaf in LABELS and val != "":
                print("  %-44s %s" % (LABELS[leaf], val))
    print("\nSee references/settings-catalog.md for what each setting does and what travels in a package.")


def quiz_facts(root, text=""):
    """The quiz settings a class standard or a house check can name, read from one quiz file."""
    f = {}
    views = 0
    for path, val in flat(root):
        leaf = path.split("/")[-1].split("[")[0].split(":")[-1]
        if "assessfeedback" in path and path.endswith("response_display_type_id"):
            views += 1
        if "/assess_procextension" in path:
            f.setdefault(leaf, val)
    yes = lambda k: f.get(k, "").lower() == "yes"
    sh = re.findall(r'render_choice[^>]*\bshuffle="(yes|no)"', text)
    return {"attempts_allowed": int(f["attempts_allowed"]) if f.get("attempts_allowed", "").isdigit() else None,
            "annotation_tools": yes("annotation_tools_enabled"),
            "additional_view_after_close": views > 1,
            "lockdown": yes("is_attempt_Rldb"),
            "calendar_event": yes("has_schedule_event"),
            "time_limit_minutes": int(f["time_limit"]) if f.get("time_limit", "").isdigit() and f.get("enforce_time_limit", "").lower() == "yes" else None,
            "_dated": "date_end" in text,
            "_shuffle_off": sh.count("no"), "_shuffle_total": len(sh)}


def cmd_audit(a):
    """Two parts: the faculty member's own standards (if they have set any), then checks that
    are always worth reporting. Read-only."""
    import xml.etree.ElementTree as ET
    quiet = getattr(a, "quiet", False)
    out = (lambda *x, **k: None) if quiet else print
    need_course()
    sf = ROOT / "class-standards.json"
    want = json.loads(sf.read_text(encoding="utf-8")).get("quiz", {}) if sf.is_file() else {}
    want = {k: v for k, v in want.items() if v is not None}
    files = quiz_files()
    if not sf.is_file():
        out("(No class-standards.json yet, so only the built-in checks run. "
              "See references/standards-interview.md.)")
    differ = notes = 0
    tally = Counter()
    detail_lines = []
    for p in files:
        text = read(p)[0]
        root = ET.fromstring(text)
        asm = root.find(".//{*}assessment")
        title = (asm if asm is not None else root).get("title", p.name)
        got = quiz_facts(root, text)
        lines = ["  %-30s now %-8s you want %s" % (k, got.get(k), v)
                 for k, v in want.items() if got.get(k) != v]
        flags = []
        if got["_shuffle_off"]:
            flags.append("answer order is NOT shuffled on %d of %d questions in this file. If the right answer "
                         "is listed first in your banks, students see it at A. A quiz that already has attempts "
                         "cannot be fixed by reimport." % (got["_shuffle_off"], got["_shuffle_total"]))
        if "annotation_tools" not in want and got["_dated"] and not got["annotation_tools"]:
            tally["annotation off"] += 1
        if "additional_view_after_close" not in want and got["_dated"] and not got["additional_view_after_close"]:
            tally["no extra view"] += 1
        if lines or flags:
            out("\n%s" % title)
            differ += bool(lines)
            notes += bool(flags)
            out("\n".join(lines))
            detail_lines += ["%s: %s" % (title, l.strip()) for l in lines]
            for fl in flags:
                out("  FLAG: " + fl)
                detail_lines.append("%s: %s" % (title, fl))
    qdb = COURSE / "questiondb.xml"
    if qdb.is_file():
        sh = re.findall(r'render_choice[^>]*\bshuffle="(yes|no)"', read(qdb)[0])
        if sh.count("no"):
            out("\nQuestion library: answer order is NOT shuffled on %d of %d multiple-choice questions."
                  % (sh.count("no"), len(sh)))
    if tally:
        out("\nFor your information (these are choices, not errors; set them in your standards to stop this note): "
              + "; ".join("%d quiz(zes) with %s" % (v, k) for k, v in tally.items()) + ".")
    if sf.is_file():
        out("\n%d quizzes checked against your standards: %d differ, %d have other flags." % (len(files), differ, notes))
    else:
        out("\n%d quizzes read. No standards are saved yet, so nothing was compared with your wishes. %d have a flag that applies to everyone (answer order)." % (len(files), notes))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import package_checks
    r = {"id": "quiz-settings", "title": "Quiz settings match your standards (attempts, time limit, answer order, views)",
         "problems": detail_lines}
    if not sf.is_file():
        r["note"] = "no standards saved: partly checked"
    elif not want:
        r["note"] = "your standards file has nothing about quizzes: partly checked"
    package_checks.record(CHECK_LOG, [r])
    if not quiet:
        write_quality_report()
    out("Fixes are a reimport into a NEW shell, or by hand in a live one: see references/d2l-updating-a-live-shell.md.")


def cmd_report(a):
    """Write ready-to-import/COURSE-SETTINGS.html: every setting the export carries, in plain words."""
    need_course()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import course_report
    OUT.mkdir(exist_ok=True)
    name = export_name()
    errors, warnings = run_checks()       # so the report and the quality report are never out of step
    write_quality_report()
    n = course_report.build(COURSE, name, OUT / "COURSE-SETTINGS.html")
    print("Ran the quality checks: %d stop an import, %d to look at. See QUALITY-REPORT.html." % (len(errors), len(warnings)))
    print_status()
    print("Wrote %s\n  %s" % (OUT / "COURSE-SETTINGS.html", ", ".join("%d %s" % (v, k) for k, v in n.items())))


SET_FIELDS = {
    "attempts_allowed": ("whole number, 0 = unlimited", lambda v: v.isdigit()),
    "time_limit": ("minutes, 0 = none", lambda v: v.isdigit()),
    "enforce_time_limit": ("yes or no", lambda v: v in ("yes", "no")),
    "grace_period": ("minutes", lambda v: v.isdigit()),
    "is_forward_only": ("yes or no", lambda v: v in ("yes", "no")),
    "show_clock": ("yes or no", lambda v: v in ("yes", "no")),
    "annotation_tools_enabled": ("yes or no", lambda v: v in ("yes", "no")),
    "has_schedule_event": ("yes or no", lambda v: v in ("yes", "no")),
}


def cmd_set(a):
    """Change one quiz setting on chosen quizzes (numbers as in the settings report). Preview unless --apply."""
    import xml.etree.ElementTree as ET
    need_course()
    if a.field not in SET_FIELDS:
        die("'%s' is not a setting I can change. I can set: %s" % (a.field, ", ".join(SET_FIELDS)))
    hint, ok = SET_FIELDS[a.field]
    if not ok(a.value):
        die("%s must be %s" % (a.field, hint))
    files = quiz_files()
    try:
        nums = [int(x) for x in a.numbers.split(",") if x.strip()]
    except ValueError:
        die("--numbers looks like 3,7,12 (the # column in the report)")
    bad = [n for n in nums if n < 1 or n > len(files)]
    if not nums or bad:
        die("quiz number%s %s not found. Numbers run from 1 to %d, as in the # column of the settings report." % ("s" if len(bad) > 1 else "", ", ".join(map(str, bad)) or "(none given)", len(files)))
    pat = re.compile(r"(<(?:\w+:)?%s(?:\s[^>]*)?>)([^<]*)(</(?:\w+:)?%s>)" % (a.field, a.field))
    detail = []
    for n in nums:
        p = files[n - 1]
        t, bom = read(p)
        title = ET.fromstring(t).find(".//{*}assessment").get("title", p.name)
        m = pat.search(t)
        if not m:
            print("  #%d %s: this quiz has no %s setting to change" % (n, title, a.field))
            continue
        old = m.group(2).strip()
        if old == a.value:
            print("  #%d %s: already %s" % (n, title, a.value))
            continue
        out = t[:m.start(2)] + a.value + t[m.end(2):]
        ET.fromstring(out)   # must still parse
        detail.append("quiz #%d %s: %s %s -> %s" % (n, title, a.field, old or "(blank)", a.value))
        print("  #%d %s: %s %s -> %s" % (n, title, a.field, old or "(blank)", a.value))
        if a.apply:
            write(p, out, bom)
    if a.apply and detail:
        log("set", detail=detail)
        print("\nChanged %d quiz(zes)." % len(detail))
    elif detail:
        print("\nNothing has changed yet. Run again with --apply to make these changes.")
    print("Only use this for a NEW, empty shell. A quiz that already has attempts cannot be changed by importing a package.")


def need_course():
    if not (COURSE / "imsmanifest.xml").is_file():
        die("nothing unpacked yet. Run: python tools/rollforward.py unpack")


def main():
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8", errors="replace")      # a Windows console must not crash on an accent or emoji
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("unpack"); s.add_argument("export", nargs="?", default=""); s.set_defaults(f=cmd_unpack)
    sp.add_parser("inventory").set_defaults(f=cmd_inventory)
    s = sp.add_parser("shift"); s.add_argument("--days", type=int)
    s.add_argument("--from-date"); s.add_argument("--to-date")
    s.add_argument("--apply", action="store_true"); s.add_argument("--again", action="store_true"); s.set_defaults(f=cmd_shift)
    s = sp.add_parser("replace"); s.add_argument("old"); s.add_argument("new")
    s.add_argument("--apply", action="store_true"); s.add_argument("--skip-codes", action="store_true"); s.set_defaults(f=cmd_replace)
    sp.add_parser("audit").set_defaults(f=cmd_audit)
    sp.add_parser("settings").set_defaults(f=cmd_settings)
    sp.add_parser("check").set_defaults(f=cmd_check)
    s = sp.add_parser("set"); s.add_argument("kind", choices=["quiz"]); s.add_argument("--numbers", required=True)
    s.add_argument("--field", required=True); s.add_argument("--value", required=True)
    s.add_argument("--apply", action="store_true"); s.set_defaults(f=cmd_set)
    sp.add_parser("report").set_defaults(f=cmd_report)
    sp.add_parser("pack").set_defaults(f=cmd_pack)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
