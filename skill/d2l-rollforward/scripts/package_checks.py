#!/usr/bin/env python3
"""Checks that run before a package is built (and on demand: `rollforward.py check`).

Standard library only. Prints problems only. `errors` stop the pack; `warnings` are shown and
the pack goes ahead, because D2L's own exports already carry some dead references.
"""
import html, re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

SKIP_SCHEME = re.compile(r"^(/d2l/|https?:|mailto:|tel:|javascript:|data:|#|\{|\$|//)", re.I)
ARCHIVE = re.compile(r"(^|/)(_archive[^/]*|_backup[^/]*|backup|old|archive)(/|$)", re.I)
REF = re.compile(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", re.I)


def _rel(course, p):
    return Path(p).relative_to(course).as_posix()


def xml_wellformed(course):
    """Every .xml file must parse. One bad quote makes D2L refuse the whole package."""
    bad = []
    for p in sorted(Path(course).rglob("*.xml")):
        try:
            b = p.read_bytes()
            ET.fromstring(b[3:] if b.startswith(b"\xef\xbb\xbf") else b)
        except ET.ParseError as e:
            bad.append("%s does not parse (%s). D2L would refuse the package." % (_rel(course, p), e))
    return bad


def manifest_hrefs(course):
    """Files the manifest points at that are not in the course folder."""
    course = Path(course)
    try:
        root = ET.fromstring((course / "imsmanifest.xml").read_bytes().lstrip(b"\xef\xbb\xbf"))
    except (ET.ParseError, FileNotFoundError):
        return []
    miss = []
    for el in root.iter():
        h = el.get("href")
        if h is None or el.tag.split("}")[-1] != "resource":
            continue
        kind = [v for k, v in el.attrib.items() if k.endswith("material_type")]
        if h == "":
            if "contentmodule" not in kind:   # a module is a folder, so it has no file
                miss.append("a manifest resource (%s) has an empty href; it will render as a blank page"
                            % (el.get("identifier") or "no id"))
        elif not SKIP_SCHEME.match(h) and not (course / unquote(h).replace("\\", "/")).exists():
            miss.append("manifest points at %s, which is not in the package" % h)
    return miss


def broken_references(course, limit=25):
    """Pages whose src/href point at a file that is not in the package."""
    course = Path(course)
    out = []
    for p in sorted(course.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in {".html", ".htm"}:
            continue
        t = p.read_bytes().decode("utf-8", errors="replace")
        for m in REF.finditer(t):
            ref = html.unescape(m.group(1)).strip()
            if not ref or SKIP_SCHEME.match(ref):
                continue
            target = unquote(ref.split("#")[0].split("?")[0])
            if not target:
                continue
            if ".fld/" in target.replace("\\", "/") or target.lower().endswith((".thmx", "filelist.xml", "colorschememapping.xml")):
                continue          # leftovers of Word's "save as web page": harmless
            if not (p.parent / target).exists() and not (course / target.lstrip("/")).exists():
                out.append("%s points at %s, which is not in the package" % (_rel(course, p), ref))
                if len(out) >= limit:
                    out.append("(more not shown)")
                    return out
    return out


def archive_folders(course):
    course = Path(course)
    return sorted({"%s would ship to students" % _rel(course, p) for p in course.rglob("*")
                   if p.is_file() and ARCHIVE.search(_rel(course, p))})[:10]


def quiz_embedded_images(course):
    """D2L rewrites base64 images inside imported quizzes to javascript://, so students see a broken image."""
    course = Path(course)
    out = []
    for p in sorted(list(course.glob("quiz_d2l_*.xml")) + list(course.glob("questiondb.xml"))):
        n = p.read_bytes().count(b"data:image")
        if n:
            out.append("%s has %d picture(s) embedded inside the quiz. D2L breaks those on import; use image files." % (p.name, n))
    return out


MEDIA = {".mp4", ".m4v", ".mov", ".webm", ".mp3", ".m4a", ".wav"}
CAPTION = {".vtt", ".srt", ".sbv"}


def media_without_captions(course):
    """Video and audio files with no caption file beside them (same name, .vtt or .srt)."""
    course = Path(course)
    caps = {p.with_suffix("").name.lower() for p in course.rglob("*") if p.suffix.lower() in CAPTION}
    caps |= {Path(p.stem).stem.lower() for p in course.rglob("*") if p.suffix.lower() in CAPTION}
    missing = [_rel(course, p) for p in sorted(course.rglob("*"))
               if p.is_file() and p.suffix.lower() in MEDIA and p.stem.lower() not in caps]
    if not missing:
        return []
    shown = ", ".join(missing[:5]) + (" and %d more" % (len(missing) - 5) if len(missing) > 5 else "")
    return ["%d video/audio file(s) have no caption file beside them (%s). Captions need to be accurate and in sync. "
            "This tool only checks that a caption file exists. Videos hosted on MediaSpace or YouTube are not checked at all." % (len(missing), shown)]


def unlisted_files(course):
    """Files that no manifest entry and no page refers to: students can never reach them."""
    course = Path(course)
    named = set()
    try:
        root = ET.fromstring((course / "imsmanifest.xml").read_bytes().lstrip(b"\xef\xbb\xbf"))
        for el in root.iter():
            h = el.get("href")
            if h:
                named.add(unquote(h).replace("\\", "/").lower())
    except (ET.ParseError, FileNotFoundError):
        return []
    blob = b""
    for p in course.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".html", ".htm", ".xml"}:
            blob += p.read_bytes().lower() + b"\n"
    text = blob.decode("utf-8", errors="replace")
    orphans = []
    for p in sorted(course.rglob("*")):
        r = _rel(course, p)
        if not p.is_file() or r.lower() in named or p.suffix.lower() in {".xml"} or "/" not in r and r.endswith(".html"):
            continue
        name = p.name.lower()
        pat = re.compile(r"(?<![a-z0-9])(%s|%s)" % (re.escape(name), re.escape(name.replace(" ", "%20"))))
        if pat.search(text):
            continue
        orphans.append(r)
    if not orphans:
        return []
    return ["%d file(s) are in the package but nothing links to them, so students cannot reach them (%s%s)."
            % (len(orphans), ", ".join(orphans[:4]), " and more" if len(orphans) > 4 else "")]



def _xml(p):
    b = Path(p).read_bytes()
    return ET.fromstring(b[3:] if b.startswith(b"\xef\xbb\xbf") else b)


def _tag(e):
    return e.tag.split("}")[-1]


def grade_weights(course):
    """A weighted gradebook whose category weights do not add to 100. Points gradebooks (system 0) ignore weights."""
    p = Path(course) / "grades_d2l.xml"
    if not p.is_file():
        return []
    try:
        r = _xml(p)
    except ET.ParseError:
        return []
    co = r.find("configuration/calculation_options")
    if co is None or co.get("grading_system", "0") == "0":
        return []
    w = []
    for c in r.iter():
        if _tag(c) == "category" and c.find("name") is not None:
            try:
                w.append(float(c.findtext("scoring/weight") or 0))
            except ValueError:
                pass
    if w and abs(sum(w) - 100) > 0.01:
        return ["The gradebook is not set to points, and its %d category weights add to %g, not 100. If it is meant to be "
                "weighted, students' grades will not calculate as you expect. If it is meant to be points, change the "
                "grading system in D2L." % (len(w), sum(w))]
    return []


def _plain(s):
    return re.sub(r"<[^>]+>", "", html.unescape(s or "")).strip()


def quiz_stems(course):
    """Quiz questions whose text is empty. The answers can still look fine, so this hides until a student sees it."""
    course = Path(course)
    out = []
    for p in sorted(list(course.glob("quiz_d2l_*.xml")) + list(course.glob("questiondb.xml"))):
        try:
            r = _xml(p)
        except ET.ParseError:
            continue
        blank = 0
        total = 0
        for it in r.iter():
            if _tag(it) != "item":
                continue
            total += 1
            mt = None
            for m in it.iter():
                if _tag(m) == "mattext":
                    mt = m
                    break
            if mt is None or not _plain(mt.text):
                blank += 1
        if blank:
            out.append("%s has %d of %d questions with no question text." % (p.name, blank, total))
    return out[:10]


def time_limit_not_enforced(course):
    """A time limit that is set but not enforced: students are shown a limit that does nothing."""
    course = Path(course)
    n = bad = 0
    for p in sorted(course.glob("quiz_d2l_*.xml")):
        t = p.read_text(encoding="utf-8-sig", errors="replace")
        m = re.search(r"<(?:\w+:)?time_limit>\s*(\d+)\s*<", t)
        e = re.search(r"<(?:\w+:)?enforce_time_limit>\s*(\w+)\s*<", t)
        if m and int(m.group(1)) > 0:
            n += 1
            if e and e.group(1).lower() == "no":
                bad += 1
    if not bad:
        return []
    return ["%d of %d quizzes with a time limit do not enforce it (the limit is shown to students and does nothing). "
            "Change it only if that is not what you intend." % (bad, n)]


def quiz_banks(course):
    """A random draw larger than the pool it draws from."""
    course = Path(course)
    out = []
    for p in sorted(course.glob("quiz_d2l_*.xml")):
        try:
            r = _xml(p)
        except ET.ParseError:
            continue
        for sec in r.iter():
            if _tag(sec) != "section":
                continue
            n = None
            for f in sec.findall("{*}qtimetadata/{*}qti_metadatafield"):
                if f.findtext("{*}fieldlabel") == "qmd_numberofitems":
                    n = f.findtext("{*}fieldentry")
            refs = [x for x in sec if _tag(x) in ("itemref", "item")]
            if n and n.isdigit() and refs and int(n) > len(refs):
                out.append("%s: a section delivers %s questions but holds only %d." % (p.name, n, len(refs)))
    return out[:10]


INSTRUCTOR = re.compile(r"(answer keys?\b|solutions? (guide|key|manual)|instructor('?s)? (guide|only|notes|copy|version|use only|manual)|"
                        r"for instructors? only|\bTA (guide|notes|only|version)|\(TA\)|confidential|do not (share|distribute)|grader (guide|notes))", re.I)


def instructor_only_visible(course):
    """Items that read like instructor material but are not hidden from students."""
    course = Path(course)
    try:
        mf = _xml(course / "imsmanifest.xml")
    except (ET.ParseError, FileNotFoundError):
        return []
    out = []
    for el in mf.iter():
        if _tag(el) == "item" and el.get("isvisible", "True") != "False":
            title = el.findtext("{*}title") or ""
            if INSTRUCTOR.search(title):
                out.append(title.strip())
    if not out:
        return []
    return ["%d item(s) read like instructor material but are visible to students: %s%s. Hide them, or confirm they are meant to be seen."
            % (len(out), "; ".join(out[:4]), " and more" if len(out) > 4 else "")]


class _A11y(__import__("html.parser", fromlist=["HTMLParser"]).HTMLParser):
    def __init__(self):
        super().__init__()
        self.noalt = 0
        self.longalt = 0
        self.skips = 0
        self.last = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "img":
            if "alt" not in a:
                self.noalt += 1
            elif len(a["alt"] or "") > 200:
                self.longalt += 1
        if re.fullmatch(r"h[1-6]", tag):
            lvl = int(tag[1])
            if self.last and lvl > self.last + 1:
                self.skips += 1
            self.last = lvl


def page_accessibility(course):
    """Images with no alt attribute, alt text over 200 characters, and heading levels that skip."""
    course = Path(course)
    noalt = longalt = skips = pages = 0
    worst = []
    for p in sorted(course.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in {".html", ".htm"}:
            continue
        a = _A11y()
        try:
            a.feed(p.read_bytes().decode("utf-8", errors="replace"))
        except Exception:
            continue
        if a.noalt or a.longalt or a.skips:
            pages += 1
            noalt += a.noalt
            longalt += a.longalt
            skips += a.skips
            worst.append((a.noalt + a.longalt + a.skips, _rel(course, p)))
    if not pages:
        return []
    worst.sort(reverse=True)
    parts = []
    if noalt:
        parts.append("%d image(s) with no alt text" % noalt)
    if longalt:
        parts.append("%d with alt text over 200 characters" % longalt)
    if skips:
        parts.append("%d heading level skip(s)" % skips)
    return ["%d page(s) have accessibility problems: %s. Worst: %s." % (pages, ", ".join(parts), ", ".join(w[1] for w in worst[:3]))]


MONTH = r"(Jan(uary|\.)?|Feb(ruary|\.)?|Mar(ch|\.)?|Apr(il|\.)?|May|June?|July?|Aug(ust|\.)?|Sep(t(ember)?|\.)?|Oct(ober|\.)?|Nov(ember|\.)?|Dec(ember|\.)?)"
PROSE_DATE = re.compile(r"\b%s\s+\d{1,2}(st|nd|rd|th)?\b|\b(1[0-2]|0?[1-9])/([12]\d|3[01]|0?[1-9])(/(20)?\d\d)?\b" % MONTH)


def dates_in_text(course):
    """Dates written in page text. The shift moves stored dates only, so these must be read and updated by hand."""
    course = Path(course)
    pages = []
    for p in sorted(course.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in {".html", ".htm"}:
            continue
        text = re.sub(r"<[^>]+>", " ", p.read_bytes().decode("utf-8", errors="replace"))
        n = len(PROSE_DATE.findall(text))
        if n:
            pages.append((n, _rel(course, p)))
    if not pages:
        return []
    pages.sort(reverse=True)
    return ["%d page(s) mention specific dates in their text (%d mentions). The date shift does not move these. Start with: %s."
            % (len(pages), sum(n for n, _ in pages), ", ".join("%s (%d)" % (f, n) for n, f in pages[:3]))]


def ungraded_backing(course):
    """Gradebook items with no quiz, assignment, discussion or tool behind them (manual entries)."""
    course = Path(course)
    gp = course / "grades_d2l.xml"
    if not gp.is_file():
        return []
    try:
        items = {}
        for i in _xml(gp).iter():
            if _tag(i) == "item" and i.find("name") is not None:
                items[(i.get("id"), i.get("identifier"), i.get("resource_code"))] = i.findtext("name")
    except ET.ParseError:
        return []
    used = set()
    for p in course.glob("quiz_d2l_*.xml"):
        qt = p.read_text(encoding="utf-8-sig", errors="replace")
        used |= set(re.findall(r"<grade_item[^>]*>\s*(\d+)\s*<", qt)) | set(re.findall(r'<grade_item[^>]*resource_code="([^"]+)"', qt))
    dp = course / "dropbox_d2l.xml"
    if dp.is_file():
        used |= set(re.findall(r'grade_item="([^"]+)"', dp.read_text(encoding="utf-8-sig", errors="replace")))
    for p in course.glob("basic_lti_link_*.xml"):   # publisher tools that return a grade
        used |= set(re.findall(r"d2l_resource_code\"?>\s*([^<\s]+)", p.read_text(encoding="utf-8-sig", errors="replace")))
    for p in course.glob("discussion_d2l_*.xml"):
        used |= set(re.findall(r"grade_item_id>\s*([^<\s]+)", p.read_text(encoding="utf-8-sig", errors="replace")))
    names = [n for k, n in items.items() if not (set(k) & used)]
    if not names:
        return []
    if len(names) == len(items):
        return ["No gradebook item could be matched to a quiz, assignment or discussion, so this check could not tell what is behind them."]
    return ["%d of %d gradebook items have no quiz, assignment or discussion behind them (fine for participation or "
            "manual grades; check the rest): %s%s." % (len(names), len(items), "; ".join(n for n in names[:4] if n), " and more" if len(names) > 4 else "")]


SKIP = "__skipped__:"
DAYNAMES = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday"}
WHEN = "%a %b %d %Y, %I:%M %p"


def _root(course):
    return Path(course).resolve().parent.parent   # work/course -> the folder the faculty member opened


def _json(path):
    import json
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _parse_rule(text):
    """'due Sunday 11:59 PM' -> ('Sunday', '11:59 PM'). Either part may be None."""
    m = re.search(r"(mon|tue|wed|thu|fri|sat|sun)[a-z]*", text or "", re.I)
    tm = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", text or "", re.I)
    return (DAYNAMES[m.group(1).lower()] if m else None,
            "%d:%s %s" % (int(tm.group(1)), tm.group(2), tm.group(3).upper()) if tm else None)


def _short(s, n=44):
    s = (s or "").strip()
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0].rstrip(" -,:;") + "\u2026"


def _items(course):
    """[(kind, number, name, due string, close string)] for quizzes and assignments, in report order."""
    sys_path = str(Path(__file__).resolve().parent)
    import sys
    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    import course_report as cr
    course = Path(course)
    out = []
    for i, q in enumerate(cr.quizzes(course, "")):
        out.append(("quiz", i + 1, q["title"], q["dates"].get("date_due", ""), q["dates"].get("date_end", "")))
    for i, d in enumerate(cr.dropboxes(course)):
        out.append(("assignment", i + 1, d["name"], d["due"], ""))
    return out


def due_rules(course):
    """Items whose due day or time differs from the faculty member's own rule (class-standards.json, due_rules)."""
    rules = (_json(_root(course) / "class-standards.json") or {}).get("due_rules") or {}
    parsed = {k: _parse_rule(v) for k, v in rules.items() if k in ("quiz", "assignment")}
    parsed = {k: v for k, v in parsed.items() if v != (None, None)}
    if not parsed:
        return [SKIP + "no due-day rule saved yet"]
    out = []
    for kind, (day, time) in parsed.items():
        rows = [x for x in _items(course) if x[0] == kind and x[3]]
        bad = []
        for _, n, name, due, _c in rows:
            got_day = DAYNAMES.get(due[:3].lower(), "")
            got_time = due.split(", ", 1)[1].lstrip("0") if ", " in due else ""
            if (day and got_day != day) or (time and got_time != time):
                bad.append("#%d %s (due %s)" % (n, _short(name), due))
        if bad:
            want = " ".join(x for x in (day, time) if x)
            out.append("%d of %d %s items are not due %s, your rule: %s%s." % (
                len(bad), len(rows), kind, want, "; ".join(bad[:5]), " and more" if len(bad) > 5 else ""))
    return out


def calendar_collisions(course):
    """Due or close dates that fall on a break, outside the term, or before it starts (calendar.json)."""
    from datetime import datetime, date
    cal = _json(_root(course) / "calendar.json")
    if not cal or not cal.get("first_day"):
        return [SKIP + "no term calendar saved yet"]
    try:
        first = date.fromisoformat(cal["first_day"])
        end = date.fromisoformat((cal.get("finals") or [cal.get("last_day") or cal["first_day"]])[-1])
        breaks = [(date.fromisoformat(b[0]), date.fromisoformat(b[1]), b[2] if len(b) > 2 else "a break") for b in cal.get("breaks", [])]
    except (ValueError, KeyError, IndexError):
        return [SKIP + "term calendar unreadable"]
    out = []
    for kind, n, name, due, close in _items(course):
        for label, s in (("due", due), ("closes", close)):
            if not s:
                continue
            try:
                d = datetime.strptime(s, WHEN).date()
            except ValueError:
                continue
            why = None
            if d < first:
                why = "is before the first day of classes (%s)" % first
            elif d > end:
                why = "is after the term ends (%s)" % end
            else:
                for a, b, nm in breaks:
                    if a <= d <= b:
                        why = "falls in %s (%s to %s)" % (nm, a, b)
            if why:
                out.append("%s #%d %s %s %s, which %s." % (kind, n, _short(name), label, s, why))
    after = [o for o in out if "is after the term ends" in o]
    before = [o for o in out if "is before the first day" in o]
    if len(out) >= 8 and len(after) == len(out):
        return ["%d due or close dates are all after the term ends (%s). The dates in this course were probably shifted to a different term than "
                "the one in calendar.json: check the new first day you gave `shift` and the first_day in calendar.json." % (len(out), end)]
    if len(out) >= 8 and len(before) == len(out):
        return ["%d due or close dates are all before the first day of classes (%s). The dates in this course were probably shifted to a different term than "
                "the one in calendar.json: check the new first day you gave `shift` and the first_day in calendar.json." % (len(out), first)]
    if len(out) > 8:
        return ["%d due or close dates are outside the term or in a break. First 8 shown:" % len(out)] + out[:8] + ["...and %d more." % (len(out) - 8)]
    return out


# (id, what it looks for, function, "error" stops a pack, "warn" is shown and the pack goes ahead)
CHECKS = [
    ("xml", "Every XML file is well formed", xml_wellformed, "error"),
    ("manifest", "Files the manifest names are in the package", manifest_hrefs, "warn"),
    ("references", "Pages point at images and files that exist", broken_references, "warn"),
    ("archive", "No archive or backup folders would ship", archive_folders, "warn"),
    ("quiz-images", "No pictures embedded inside quizzes", quiz_embedded_images, "warn"),
    ("captions", "Video and audio files have a caption file beside them (accuracy not checked)", media_without_captions, "warn"),
    ("unlisted", "No files that nothing links to", unlisted_files, "warn"),
    ("grade-weights", "Gradebook category weights add to 100 when weighted", grade_weights, "warn"),
    ("quiz-stems", "No blank quiz question text", quiz_stems, "warn"),
    ("quiz-bank", "Random draw is not larger than its bank", quiz_banks, "warn"),
    ("time-limit", "A time limit that is set is also enforced", time_limit_not_enforced, "warn"),
    ("instructor-only", "Instructor-only material is hidden", instructor_only_visible, "warn"),
    ("alt-text", "Images have an alt attribute and headings do not skip (the alt text itself is not judged)", page_accessibility, "warn"),
    ("dates-format", "Dates written in page text (the shift cannot move these)", dates_in_text, "warn"),
    ("graded-items", "Gradebook items with nothing behind them", ungraded_backing, "warn"),
    ("due-rules", "Due days and times match your own due-date rules", due_rules, "warn"),
    ("calendar-collisions", "No due date falls on a break or outside the term", calendar_collisions, "warn"),
]
# Planned, not built. Shown as "not built yet" so nobody mistakes silence for a pass.
PLANNED = [
    ("dates-agree", "Due dates agree across quiz, assignment, syllabus and announcements"),
    ("question-order", "Question order matches your choice (the setting is not read yet)"),
    ("student-data-content", "Student names and IDs inside files (today only file names are checked)"),
    ("caption-quality", "Captions are accurate and in sync, and MediaSpace videos have captions"),
    ("office-pdf", "Accessibility of Word, PowerPoint, Excel and PDF files"),
    ("page-links", "No links from one content page to another"),
    ("alt-text-quality", "Alt text says something useful, and quizzes and announcements are scanned too"),
    ("question-banks-reuse", "Question banks that have circulated for several terms"),
    ("special-access", "Accommodations and special access carried over (cannot be read from an export)"),
]


def run_all(course):
    """Run every registered check. Returns [{id, title, severity, problems}]."""
    out = []
    for i, ti, fn, sev in CHECKS:
        probs = fn(course)
        r = {"id": i, "title": ti, "severity": sev, "problems": probs}
        if probs and probs[0].startswith(SKIP):
            r["problems"], r["note"] = [], "not run: " + probs[0][len(SKIP):].strip()
        out.append(r)
    return out


def run(course):
    errors, warnings = [], []
    for r in run_all(course):
        (errors if r["severity"] == "error" else warnings).extend(r["problems"])
    return errors, warnings


def record(log_path, results, now=None):
    """Remember when each check last ran and what it found."""
    import json
    from datetime import datetime
    log_path = Path(log_path)
    try:
        log = json.loads(log_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log = {}
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M")
    for r in results:
        lead = [re.match(r"(\d+)\b", x) for x in r["problems"]]
        items = sum(int(m.group(1)) for m in lead) if r["problems"] and all(lead) else len(r["problems"])
        log[r["id"]] = {"title": r["title"], "last_run": stamp, "problems": len(r["problems"]), "items": items,
                        "details": list(r["problems"])[:25], "note": r.get("note", "")}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, indent=1), encoding="utf-8")


def status_rows(log_path):
    """[(title, last run, result)] for every check, including planned and never-run ones."""
    import json
    try:
        log = json.loads(Path(log_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log = {}
    rows = []
    for i, ti, _fn, _sev in CHECKS:
        e = log.get(i)
        rows.append((ti, e["last_run"] if e else "never run",
                     (e.get("note") or ("nothing found" if not e["problems"] else "%d to look at" % e.get("items", e["problems"]))) if e else "-"))
    if "quiz-settings" in log:
        e = log["quiz-settings"]
        rows.append((e["title"], e["last_run"], e.get("note") or ("nothing found" if not e["problems"] else "%d to look at" % e.get("items", e["problems"]))))
    else:
        rows.append(("Quiz settings match your standards (attempts, time limit, answer order, views)", "never run", "not run yet"))
    for i, ti in PLANNED:
        e = log.get(i)
        rows.append((ti, e["last_run"] if e else "-", ("nothing found" if not e["problems"] else "%d to look at" % e.get("items", e["problems"])) if e else "not built yet"))
    def group(r):
        res = r[2]
        return 0 if "to look at" in res else 1 if res == "nothing found" else 3 if res == "not built yet" else 2
    return sorted(rows, key=group)


def details(log_path):
    """{id: (title, last_run, [problem text])} for every check that has run."""
    import json
    try:
        log = json.loads(Path(log_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: (v["title"], v["last_run"], v.get("details", [])) for k, v in log.items()}
