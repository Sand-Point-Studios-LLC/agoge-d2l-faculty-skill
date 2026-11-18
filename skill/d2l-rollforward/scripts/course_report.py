#!/usr/bin/env python3
"""Write one readable document describing every setting an unpacked D2L export carries.

Standard library only. Reads work/course/ and writes ready-to-import/COURSE-SETTINGS.html.
Nothing here changes the course. Settings the tool has no plain-English name for are listed
raw under "Other settings", so nothing is hidden.
"""
import html, re, sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    LOCAL = ZoneInfo("America/Detroit")
except Exception:
    LOCAL = None

QUIZ_LABELS = {
    "attempts_allowed": ("Attempts allowed", "0 means unlimited."),
    "time_limit": ("Time limit (minutes)", "0 means no limit."),
    "enforce_time_limit": ("Time limit enforced", "yes: D2L ends the attempt when time runs out."),
    "grace_period": ("Grace period (minutes)", "Extra minutes before a late submission is flagged."),
    "late_limit": ("Late rule", "What happens to an attempt submitted after time is up."),
    "late_limit_data": ("Late rule detail", ""),
    "is_forward_only": ("Forward only", "yes: students cannot go back to earlier questions."),
    "paging_type_id": ("Questions per page (code)", ""),
    "show_clock": ("Show clock", "A visible countdown while taking the quiz."),
    "is_single_session": ("Single session", ""),
    "disable_right_click": ("Right-click disabled", ""),
    "disable_pager_access": ("Question list hidden", "Hides the question navigator."),
    "is_attempt_Rldb": ("LockDown Browser to take it", "Does not travel in a package: turn it back on after import."),
    "is_subview_Rldb": ("LockDown Browser to review", ""),
    "annotation_tools_enabled": ("Annotation tools", "Bookmark and strike-through while taking it."),
    "has_schedule_event": ("Calendar entry", ""),
    "category": ("Gradebook category", ""),
    "grade_item": ("Gradebook item", ""),
    "mark_calculation_type": ("Which attempt counts (code)", ""),
    "quiz_start_type": ("Start type (code)", ""),
    "is_active": ("Active", ""),
    "notification_email": ("Notification email", ""),
}
VIEW_LABELS = {
    "show_correct_answers": "shows correct answers",
    "show_class_average": "shows class average",
    "show_score_distribution": "shows score distribution",
}
NOT_IN_EXPORT = [
    ("Release conditions and special access", "No evidence an export carries them. Check each quiz, dropbox and module in D2L."),
    ("Navigation bar, and the FAQ and Links tools", "Their content may travel, but students cannot reach it until the link is added back to the navbar."),
    ("Course homepage widgets and course settings", "orgunitconfig.xml is minimal. Re-check the homepage and the course settings."),
    ("Respondus LockDown Browser and Monitor", "Turn them back on by hand after an import."),
    ("Announcement 'send an email copy'", "No element exists for it. Tick it when you post."),
    ("Anything about people", "Enrolments, grades, attempts, submissions and discussion posts never travel."),
    ("Grade scheme links to publisher tools (LTI)", "A recreated link is not paired. Move the existing one; do not recreate it."),
]


def display_name(name):
    """D2LExport_2368642_SS26-ACC-826-001-..._2026111139 -> SS26-ACC-826-001-..."""
    return re.sub(r"_\d{8,}$", "", re.sub(r"^D2LExport_\d+_", "", name or ""))


def esc(x):
    return html.escape(str(x), quote=True)


def read_xml(p):
    b = Path(p).read_bytes()
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    return ET.fromstring(b)


def tag(e):
    return e.tag.split("}")[-1]


def text(e, path):
    n = e.find(path)
    return (n.text or "").strip() if n is not None and n.text else ""


def ts_local(el):
    """A decomposed <timestamp> (UTC) as a local date-time string, or ''."""
    if el is None:
        return ""
    t = el.find("{*}timestamp")
    if t is None:
        return ""
    try:
        v = {k: int(((t.find("{*}" + k).text) if t.find("{*}" + k) is not None else 0) or 0)
             for k in ("year", "month", "day", "hour", "minutes", "seconds")}
        d = datetime(v["year"], v["month"], v["day"], v["hour"], v["minutes"], v["seconds"], tzinfo=timezone.utc)
    except (ValueError, KeyError):
        return ""
    return (d.astimezone(LOCAL) if LOCAL else d).strftime("%a %b %d %Y, %I:%M %p")


def iso_local(s):
    try:
        d = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return s or ""
    return (d.astimezone(LOCAL) if LOCAL else d).strftime("%a %b %d %Y, %I:%M %p")


def natural_key(s):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", s or "")]


def quiz_paths(course):
    """Quiz files in the order a person reads their titles (Pre-Class 2, 3, ... 10, 15), so a quiz number means the same everywhere."""
    out = []
    for p in Path(course).glob("quiz_d2l_*.xml"):
        try:
            a = read_xml(p).find(".//{*}assessment")
            title = a.get("title", "") if a is not None else p.name
        except (ET.ParseError, OSError):
            title = p.name
        out.append((natural_key(title), p.name, p))
    return [x[2] for x in sorted(out, key=lambda r: (r[0], r[1]))]


def grade_names(course):
    p = course / "grades_d2l.xml"
    names = {}
    if p.is_file():
        for i in read_xml(p).iter():
            if tag(i) == "item" and i.get("identifier"):
                names[i.get("identifier")] = text(i, "name")
    return names


def quizzes(course, qdb_text):
    gnames = grade_names(course)
    rows = []
    for p in quiz_paths(course):
        r = read_xml(p)
        a = r.find(".//{*}assessment")
        if a is None:
            continue
        pe = a.find("{*}assess_procextension")
        s = {tag(c): (c.text or "").strip() for c in (pe if pe is not None else []) if len(c) == 0}
        if s.get("grade_item") in gnames:
            s["grade_item"] = gnames[s["grade_item"]]
        dates = {k: ts_local(pe.find("{*}" + k)) for k in ("date_start", "date_end", "date_due")} if pe is not None else {}
        views = []
        for fb in a.findall("{*}assessfeedback"):
            title = fb.get("title", "") or "(untitled view)"
            on = [VIEW_LABELS[k] for k in VIEW_LABELS if text(fb, k) == "yes"]
            views.append("%s: %s%s" % (title, ", ".join(on) or "nothing extra shown",
                                       "; opens " + fb.findtext("release_date/timestamp/year", "") if False else ""))
        items = a.findall(".//{*}itemref") + a.findall(".//{*}item")
        pools = [(sec.get("title", ""), text(sec, "qtimetadata/qti_metadatafield[fieldlabel='qmd_numberofitems']/fieldentry"))
                 for sec in a.iter() if tag(sec) == "section" and sec.find("{*}qtimetadata") is not None]
        rand_order = any(o.get("order_type") == "Random" for o in a.iter() if tag(o) == "order")
        text_all = p.read_text(encoding="utf-8-sig", errors="replace")
        sh = re.findall(r'render_choice[^>]*\bshuffle="(yes|no)"', text_all)
        rows.append({"title": a.get("title", p.name), "settings": s, "dates": dates, "views": views,
                     "questions": len(items), "pools": [x for x in pools if x[1]],
                     "random_from_bank": rand_order, "answer_shuffle": (sh.count("yes"), len(sh)),
                     "data_images": "data:image" in text_all, "file": p.name})
    return rows


def dropboxes(course):
    p = course / "dropbox_d2l.xml"
    out = []
    if not p.is_file():
        return out
    for f in read_xml(p).iter():
        if tag(f) != "folder" or f.get("name") is None:
            continue
        tii = f.find("tii_options")
        out.append({"name": f.get("name"), "due": iso_local(text(f, "date_due")), "out_of": f.get("out_of", ""),
                    "hidden": f.get("is_hidden", ""), "anonymous": f.get("is_anonymous", ""),
                    "files": f.get("files_per_submission", ""), "types": f.get("allowable_file_type", ""),
                    "submissions": f.get("submissions", ""), "group": f.get("folder_group_type", ""),
                    "turnitin": tii.get("tii_enabled", "") if tii is not None else ""})
    return out


def discussions(course):
    out = []
    for p in sorted(course.glob("discussion_d2l_*.xml")):
        r = read_xml(p)
        for f in r.iter():
            if tag(f) != "topic":
                continue
            pr = f.find("properties")
            props = {tag(c): (c.text or "").strip() for c in (pr if pr is not None else [])}
            out.append({"forum": text(r, "forum/content/title"), "topic": text(f, "content/title"), "props": props})
    return out


def announcements(course):
    p = course / "news_d2l.xml"
    out = []
    if p.is_file():
        for i in read_xml(p).iter():
            if tag(i) == "item":
                out.append({"headline": text(i, "headline"), "start": iso_local(text(i, "date_start")),
                            "end": iso_local(text(i, "date_end")), "draft": text(i, "is_draft"),
                            "show_posted": text(i, "show_date_posted")})
    return out


def grades(course):
    p = course / "grades_d2l.xml"
    if not p.is_file():
        return None
    r = read_xml(p)
    co = r.find("configuration/calculation_options")
    cats = []
    for c in r.iter():
        if tag(c) == "category" and c.find("name") is not None:
            sc = c.find("scoring")
            g = (lambda k: text(sc, k)) if sc is not None else (lambda k: "")
            cats.append({"name": text(c, "name"), "weight": g("weight"), "drop_low": g("low_non_bonus_drop"),
                         "drop_high": g("high_non_bonus_drop"), "max": g("max_item_points")})
    items = [i for i in r.iter() if tag(i) == "item" and i.find("name") is not None]
    return {"options": dict(co.attrib) if co is not None else {}, "cats": cats, "items": len(items)}


def lti(course):
    out = []
    for p in sorted(course.glob("basic_lti_link_*.xml")):
        r = read_xml(p)
        url = text(r, "launch_url")
        out.append({"title": text(r, "title"), "host": re.sub(r"^https?://([^/]+).*", r"\1", url)})
    return out


def other_quiz_keys(rows):
    seen = Counter()
    for r in rows:
        for k in r["settings"]:
            if k not in QUIZ_LABELS and not k.startswith(("date_", "intro_", "attempt_restr")):
                seen[k] += 1
    return seen


PATTERN_KEYS = [("attempts_allowed", "Attempts allowed"), ("time_limit", "Time limit (minutes)"),
                ("enforce_time_limit", "Time limit enforced"), ("grace_period", "Grace period (minutes)"),
                ("is_forward_only", "Forward only"), ("is_attempt_Rldb", "LockDown Browser"),
                ("annotation_tools_enabled", "Annotation tools"), ("show_clock", "Show clock"),
                ("has_schedule_event", "Calendar entry")]


def due_pattern(strings):
    """'Wed Jan 13 2027, 11:00 PM' -> ('Wednesday', '11:00 PM'); counts of each pair."""
    days = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday",
            "Sat": "Saturday", "Sun": "Sunday"}
    c = Counter()
    for s in strings:
        if s and "," in s:
            c[(days.get(s[:3], s[:3]), s.split(", ", 1)[1])] += 1
    return c


def patterns_html(qs, dbs):
    """What the course does most often, and which items differ. Numbers match the quiz table."""
    out = ["<h2>Patterns in this course</h2><p>For each setting: what most items do, and the numbered items "
           "that do something else. Read this first. If a pattern is what you want, nothing to do. If an "
           "outlier is a mistake, tell the agent its number and what it should be.</p>"]
    rows = []
    for key, label in PATTERN_KEYS:
        vals = Counter(tidy(key, q["settings"].get(key, "")) for q in qs)
        if not vals:
            continue
        top, n = vals.most_common(1)[0]
        odd = [(i + 1, tidy(key, q["settings"].get(key, ""))) for i, q in enumerate(qs) if tidy(key, q["settings"].get(key, "")) != top]
        rows.append([label, "%s (%d of %d quizzes)" % (top if top != "" else "(blank)", n, len(qs)),
                     "; ".join("#%d %s" % (i, v if v != "" else "(blank)") for i, v in odd[:10]) + (" ..." if len(odd) > 10 else "")
                     or "none"])
    tl = [i + 1 for i, q in enumerate(qs) if q["settings"].get("time_limit", "0") not in ("", "0") and q["settings"].get("enforce_time_limit") == "no"]
    if tl:
        rows.append(["Time limit shown but not enforced", "%d of %d quizzes" % (len(tl), len(qs)),
                     "#" + ", #".join(map(str, tl[:12])) + (" ..." if len(tl) > 12 else "")])
    sh = [(i + 1, q["answer_shuffle"]) for i, q in enumerate(qs) if q["answer_shuffle"][1] and q["answer_shuffle"][0] != q["answer_shuffle"][1]]
    rows.append(["Answer order shuffled", "all questions on %d of %d quizzes" % (len(qs) - len(sh), len(qs)),
                 "; ".join("#%d (%d of %d)" % (i, a, b) for i, (a, b) in sh[:10]) + (" ..." if len(sh) > 10 else "") or "none"])
    rows.append(["Extra results view", "%d of %d quizzes have one" % (sum(1 for q in qs if q["views"]), len(qs)),
                 "; ".join("#%d" % (i + 1) for i, q in enumerate(qs) if not q["views"][:1])[:200] or "none"])
    out.append(table(["Setting", "Most common", "Different on"], rows, "Quiz settings"))
    dq = due_pattern(q["dates"].get("date_due", "") for q in qs)
    dd = due_pattern(d["due"] for d in dbs)
    dl = []
    for name, c, n in (("Quizzes", dq, len(qs)), ("Assignments", dd, len(dbs))):
        if c:
            dl.append("<li><strong>%s due:</strong> %s</li>" % (name, esc("; ".join("%s %s on %d" % (d, tm, k) for (d, tm), k in c.most_common(6)))))
    if dl:
        out.append("<h3>When things are due</h3><ul>%s</ul>" % "".join(dl))
    return "".join(out)


SKIP_KEYS = {"id", "identifier", "identifierref", "resource_code", "name", "title", "description", "sort_order",
             "grade_item", "grade_item_id", "folder_group_type", "folder_group_type_rc", "headline", "content",
             "display_order", "category_id", "short_name", "text", "instructions", "launch_url", "href", "file_name",
             "links", "date_start", "date_end", "date_due", "end_date", "start_date", "start_day", "end_day",
             "availability_date", "out_of", "max_grade", "scoreMaximum", "label", "date_posted"}


def leafmap(el, skip_children=()):
    """Short settings of one element: its attributes and its simple child values."""
    m = {}
    for k, v in el.attrib.items():
        k = k.split("}")[-1]
        if k not in SKIP_KEYS and len(v) <= 30:
            m[k] = v
    for c in el:
        n = tag(c)
        if n in SKIP_KEYS or n in skip_children:
            continue
        if len(c) == 0 and c.text is not None and len(c.text.strip()) <= 30:
            m[n] = c.text.strip()
        for k, v in c.attrib.items():
            k = k.split("}")[-1]
            if len(c) == 0 and k not in SKIP_KEYS and len(v) <= 30 and n not in ("category", "folder", "item"):
                m[n + "." + k] = v
    return m


FRIENDLY = {"ai human origin": "AI or human origin flag", "allowable file type": "allowed file types (0 = any)",
            "completion type": "completion tracking (D2L code)", "files per submission": "files per submission (0 = any)",
            "folder is retricted": "folder restricted", "folder type": "folder type (D2L code)", "submission type": "submission type (D2L code)",
            "submissions": "submissions per student (D2L code)", "WeightDistributionType": "weight distribution (code)",
            "scheme id": "grade scheme", "dates in calendar": "dates shown in calendar", "can exceed weight": "may exceed its weight",
            "type id": "item type (1 = numeric)", "low non bonus drop": "drop lowest", "high non bonus drop": "drop highest",
            "kind": "kind of item", "has due": "has a due date", "has end": "has an end date", "rating type id": "rating type (D2L code)"}


def tidy(key, v):
    v = {"true": "true", "false": "false"}.get(str(v).lower(), v)
    if key in ("time_limit", "grace_period") and v == "0":
        return "0 (none)"
    return v


def short(nm, n=28):
    return nm if len(nm) <= n else nm[:n].rstrip() + "\u2026"


def pattern_rows(records, label_len=28):
    """records: [(name, {setting: value})]. One row per setting that is not unique per item."""
    keys = sorted({k for _, m in records for k in m})
    rows = []
    for k in keys:
        vals = [tidy(k, m.get(k, "")) for _, m in records]
        c = Counter(vals)
        if len(c) > max(6, len(records) // 2):
            continue
        top, n = c.most_common(1)[0]
        odd = [(i + 1, nm, v) for i, ((nm, _), v) in enumerate(zip(records, vals)) if v != top]
        txt = "; ".join('#%d %s: %s' % (i, short(nm, label_len), v if v != "" else "(blank)") for i, nm, v in odd[:8])
        rows.append([FRIENDLY.get(k.replace("_", " "), k.replace("_", " ")), "%s (%d of %d)" % (top if top != "" else "(blank)", n, len(records)),
                     (txt + (" ..." if len(odd) > 8 else "")) or "none"])
    return rows


def tool_records(course):
    """Items of every tool (other than quizzes), as [(name, settings)] per tool."""
    out = {}
    p = course / "dropbox_d2l.xml"
    if p.is_file():
        out["Assignments"] = [(f.get("name", ""), leafmap(f, ("instructions", "tii_options", "availability_end")))
                              for f in read_xml(p).iter() if tag(f) == "folder" and f.get("name")]
    discs = []
    for p in sorted(course.glob("discussion_d2l_*.xml")):
        for f in read_xml(p).iter():
            if tag(f) == "topic":
                discs.append((text(f, "content/title"), leafmap(f.find("properties")) if f.find("properties") is not None else {}))
    if discs:
        out["Discussions"] = discs
    p = course / "news_d2l.xml"
    if p.is_file():
        out["Announcements"] = [(text(i, "headline"), leafmap(i, ("attachment_set", "file"))) for i in read_xml(p).iter() if tag(i) == "item"]
    p = course / "grades_d2l.xml"
    if p.is_file():
        r = read_xml(p)
        cats = [(text(c, "name"), leafmap(c.find("scoring")) if c.find("scoring") is not None else {}) for c in r.iter() if tag(c) == "category" and c.find("name") is not None]
        items = [(text(i, "name"), dict(leafmap(i.find("scoring")) if i.find("scoring") is not None else {},
                                        **{k: v for k, v in leafmap(i, ("scoring", "description")).items()})) for i in r.iter() if tag(i) == "item" and i.find("name") is not None]
        if cats:
            out["Gradebook categories"] = cats
        if items:
            out["Gradebook items"] = items
    p = course / "schedule_d2l.xml"
    if p.is_file():
        out["Calendar events"] = [(text(e, "title"), leafmap(e, ("description",))) for e in read_xml(p).iter() if tag(e) == "event"]
    p = course / "checklist_d2l.xml"
    if p.is_file():
        out["Checklists"] = [(text(c, "name"), leafmap(c)) for c in read_xml(p).iter() if tag(c) == "checklist"]
    ltis = []
    for q in sorted(course.glob("basic_lti_link_*.xml")):
        r = read_xml(q)
        ltis.append((text(r, "title"), {"opens": re.sub(r"^https?://([^/]+).*", r"\1", text(r, "launch_url"))}))
    if ltis:
        out["Outside tools (LTI)"] = ltis
    # Modules and content: what the manifest says about each topic
    try:
        mf = ET.fromstring((course / "imsmanifest.xml").read_bytes().lstrip(b"\xef\xbb\xbf"))
    except (ET.ParseError, FileNotFoundError):
        return out
    kind = {}
    for el in mf.iter():
        if tag(el) == "resource":
            kind[el.get("identifier")] = ([v for k, v in el.attrib.items() if k.endswith("material_type")] or [""])[0], el.get("link_target", "")
    mods = []
    for el in mf.iter():
        if tag(el) == "item" and el.get("identifierref") in kind:
            m = leafmap(el)
            m["kind"], lt = kind[el.get("identifierref")]
            if lt:
                m["link_target"] = lt
            m["has_due"] = "yes" if el.get("date_due") or any(k.endswith("date_due") for k in el.attrib) else "no"
            m["has_end"] = "yes" if el.get("date_end") else "no"
            mods.append((text(el, "title") or el.findtext("{*}title") or "(untitled)", m))
    if mods:
        out["Modules and content"] = mods
    return out


def other_patterns_html(course):
    h = []
    for name, recs in tool_records(Path(course)).items():
        rows = pattern_rows(recs)
        if recs and rows:
            diff = [r for r in rows if r[2] != "none"]
            same = [r for r in rows if r[2] == "none"]
            h.append("<h3>%s (%d)</h3>" % (esc(name), len(recs)))
            if diff:
                h.append(table(["Setting", "Most common", "Different on"], diff, name + ": settings that differ between items"))
            else:
                h.append("<p>Every item in this group is set the same way.</p>")
            if same:
                h.append("<details><summary>Same on every item (%d settings)</summary>%s</details>"
                         % (len(same), table(["Setting", "Value"], [[r[0], r[1]] for r in same], name + ": settings that are the same everywhere")))
    return "".join(h)


def table(headers, rows, caption):
    h = "".join("<th scope='col'>%s</th>" % esc(x) for x in headers)
    b = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % esc(c) for c in r) for r in rows)
    return "<table><caption>%s</caption><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (esc(caption), h, b)


def spread(rows, key):
    c = Counter(r["settings"].get(key, "") for r in rows)
    return "; ".join("%s on %d" % (v if v != "" else "(blank)", n) for v, n in sorted(c.items(), key=lambda x: -x[1]))


PAGE_CSS = (":root{--fg:#242424;--bg:#fff;--g:#18453B;--soft:#e9f3ef;--line:#bbb;--ok:#18453B;--look:#7a3b00}"
            "@media(prefers-color-scheme:dark){:root{--fg:#e8eeec;--bg:#14191a;--g:#8fd1bd;--soft:#1d2b27;--line:#4a5b55;--ok:#8fd1bd;--look:#ffbf47}}"
            "body{font:16px/1.55 system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;color:var(--fg);background:var(--bg);overflow-wrap:anywhere}"
            "h1,h2,h3{color:var(--g)}table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.92rem}"
            "caption{text-align:left;font-weight:600;padding:.3rem 0}th,td{border:1px solid var(--line);padding:.4rem;text-align:left;vertical-align:top}"
            "th{background:var(--soft)}summary{cursor:pointer;font-weight:600;margin:.4rem 0}.ok{color:var(--ok);font-weight:600}"
            ".look{color:var(--look);font-weight:600}.gap{font-weight:600}.tbl{overflow-x:auto}"
            "a{color:var(--g)}a:focus-visible,summary:focus-visible,.tbl:focus-visible{outline:3px solid var(--g);outline-offset:2px;box-shadow:0 0 0 5px var(--bg)}"
            ".skip{position:absolute;left:-999px}.skip:focus{left:.5rem;top:.5rem;background:#fff;color:#000;padding:.4rem .8rem}"
            "@media print{body{margin:0;max-width:none}details>*{display:block}.skip{display:none}}")


def page(title, body):
    body = body.replace("<table", "<div class='tbl' tabindex='0' role='region' aria-label='Table, scrolls sideways if wide'><table").replace("</table>", "</table></div>")
    return ("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>%s</style></head><body><a class='skip' href='#main'>Skip to content</a><main id='main'>%s</main>"
            "<script>addEventListener('beforeprint',function(){document.querySelectorAll('details').forEach(function(d){d.open=true})})</script>"
            "</body></html>" % (esc(title), PAGE_CSS, body))


def quality_report(log_path, out_path, name):
    """A readable page: each check, when it last ran, what it found, and what to do."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import package_checks
    det = package_checks.details(log_path)
    rows = package_checks.status_rows(log_path)
    b = ["<h1>Quality report: %s</h1>" % esc(display_name(name)),
         "<p>Generated %s. &ldquo;Nothing found&rdquo; means only that this check found nothing. It does not mean the course is accessible or that the import will work. "
         "A check marked &ldquo;not built yet&rdquo; does not exist, so silence from it is not a pass. This tool does not make a course accessible and does not replace your own review. "
         "You remain responsible for what you import. Nothing here changes your course.</p>" % datetime.now().strftime("%Y-%m-%d %H:%M"),
         "<h2>At a glance</h2>", "<table><caption>Every check and when it last ran</caption><thead><tr><th scope='col'>Check</th>"
         "<th scope='col'>Last run</th><th scope='col'>Result</th></tr></thead><tbody>"]
    for ti, when, res in rows:
        cls = "ok" if res == "nothing found" else ("look" if "look at" in res else "gap")
        mark = "&#10003; " if res == "nothing found" else ("&#9888; " if "look at" in res else "&#9675; ")
        b.append("<tr><td>%s</td><td>%s</td><td class='%s'>%s%s</td></tr>" % (esc(ti), esc(when), cls, mark, esc(res)))
    b.append("</tbody></table>")
    found = [(k, v) for k, v in det.items() if v[2]]
    if found:
        b.append("<h2>What to look at</h2>")
        for k, (ti, when, items) in found:
            b.append("<h3>%s</h3><ul>%s</ul>" % (esc(ti), "".join("<li>%s</li>" % esc(i) for i in items)))
    else:
        b.append("<h2>What to look at</h2><p>Nothing flagged by the checks that have run.</p>")
    Path(out_path).write_text(page("Quality report: " + name, "".join(b)), encoding="utf-8")


def changes_page(lines, out_path, name):
    items = "".join("<li>%s</li>" % esc(l.lstrip("- ").replace("**", "")) for l in lines if l.startswith("- "))
    Path(out_path).write_text(page("What changed: " + name,
        "<h1>What changed in this roll-forward</h1><p>%s</p><p>This is a record of what the tool did, with counts. It is not a before-and-after list of every date. "
        "Where a setting was changed, the old and new values are shown.</p><ul>%s</ul>"
        "<p>Check these in D2L after you import into a new, empty shell: open one question in each quiz, one page with "
        "an image and one with a video as a student, and every due date.</p>" % (esc(name), items or "<li>No changes recorded.</li>")),
        encoding="utf-8")


def build(course, name, out_path):
    course = Path(course)
    qs, dbs, ds, ns = quizzes(course, ""), dropboxes(course), discussions(course), announcements(course)
    gr, lt = grades(course), lti(course)
    body = []
    body.append("<h1>Course settings: %s</h1>" % esc(display_name(name)))
    body.append("<p>Everything this export says about how the course is set up, in plain words. "
                "Generated %s. It does not change anything.</p>" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    body.append("<h2>At a glance</h2><ul><li>%d quizzes</li><li>%d assignment folders</li><li>%d discussion topics</li>"
                "<li>%d announcements</li><li>%d gradebook categories, %s items</li><li>%d publisher tool links</li></ul>"
                % (len(qs), len(dbs), len(ds), len(ns), len(gr["cats"]) if gr else 0, gr["items"] if gr else "0", len(lt)))

    body.append(patterns_html(qs, dbs) if qs else "<h2>Patterns in this course</h2>")
    body.append(other_patterns_html(course))
    if qs:
        body.append("<h2>Quizzes</h2><p>How the quiz settings vary across this course:</p><ul>")
        for k in ("attempts_allowed", "time_limit", "enforce_time_limit", "is_forward_only", "is_attempt_Rldb",
                  "annotation_tools_enabled", "show_clock", "grace_period", "late_limit"):
            body.append("<li><strong>%s:</strong> %s</li>" % (esc(QUIZ_LABELS[k][0]), esc(spread(qs, k))))
        notshuf = [q for q in qs if q["answer_shuffle"][1] and q["answer_shuffle"][0] != q["answer_shuffle"][1]]
        body.append("<li><strong>Answer order (A/B/C/D) not fully shuffled:</strong> %d of %d quizzes%s</li>"
                    % (len(notshuf), len(qs), (": " + esc("; ".join("%s (%d of %d questions shuffled)" % (q["title"], *q["answer_shuffle"]) for q in notshuf))) if notshuf else ""))
        body.append("<li><strong>Extra results views:</strong> %d of %d quizzes define at least one view.</li></ul>"
                    % (sum(1 for q in qs if q["views"]), len(qs)))
        body.append(table(["#", "Quiz", "Attempts", "Time limit", "Opens", "Closes", "Due", "Questions", "Question order random (ordering setting)"],
                          [[i + 1, q["title"], q["settings"].get("attempts_allowed", ""), q["settings"].get("time_limit", ""),
                            q["dates"].get("date_start", ""), q["dates"].get("date_end", ""), q["dates"].get("date_due", ""),
                            q["questions"], ", ".join("%s: %s" % x for x in q["pools"]) or ("yes" if q["random_from_bank"] else "no")]
                           for i, q in enumerate(qs)], "Every quiz at a glance (times shown Eastern)"))
        body.append("<h3>Every setting, quiz by quiz</h3>")
        for q in qs:
            body.append("<details><summary>#%d  %s</summary>" % (qs.index(q) + 1, esc(q["title"])))
            rows = [[QUIZ_LABELS[k][0], v, QUIZ_LABELS[k][1]] for k, v in q["settings"].items() if k in QUIZ_LABELS and v != ""]
            rows += [["Results view", vw, ""] for vw in q["views"]]
            body.append(table(["Setting", "Value", "What it means"], rows, q["title"]))
            extra = [(k, v) for k, v in q["settings"].items() if k not in QUIZ_LABELS and v != "" and not k.startswith(("date_", "intro_"))]
            if extra:
                body.append("<p>Other settings: %s</p>" % esc(", ".join("%s=%s" % kv for kv in extra)))
            if q["data_images"]:
                body.append("<p><strong>Watch:</strong> this quiz has pictures embedded inside it. D2L breaks those on import. See the images note in the quiz topic.</p>")
            body.append("</details>")

    if dbs:
        body.append("<h2>Assignments</h2>")
        body.append(table(["Folder", "Due", "Out of", "Hidden", "Anonymous", "Files allowed", "Turnitin"],
                          [[d["name"], d["due"], d["out_of"], d["hidden"], d["anonymous"], d["files"] or "any", d["turnitin"]] for d in dbs],
                          "Every assignment folder"))
    if ds:
        body.append("<h2>Discussions</h2>")
        keys = ["must_post_to_participate", "requires_approval", "allow_anon", "is_hidden", "score_out_of", "is_auto_score", "uses_group_restrictions"]
        body.append(table(["Forum", "Topic"] + keys, [[d["forum"], d["topic"]] + [tidy(k, d["props"].get(k, "")) for k in keys] for d in ds],
                          "Every discussion topic"))
    if ns:
        body.append("<h2>Announcements</h2><p>%d in total.</p>" % len(ns))
        body.append(table(["Headline", "Posts", "Ends", "Draft"], [[n["headline"], n["start"], n["end"], tidy("draft", n["draft"])] for n in ns], "Every announcement"))
    if gr:
        body.append("<h2>Gradebook</h2>")
        o = gr["options"]
        body.append("<p>Final grade calculation: %s. Grading system code %s (see the settings catalog for what each code means).</p>"
                    % (esc(", ".join("%s=%s" % kv for kv in o.items())), esc(o.get("grading_system", "?"))))
        tot = 0.0
        for c in gr["cats"]:
            try:
                tot += float(c["weight"] or 0)
            except ValueError:
                pass
        body.append(table(["Category", "Weight", "Drop lowest", "Drop highest"], [[c["name"], c["weight"], c["drop_low"], c["drop_high"]] for c in gr["cats"]],
                          "Gradebook categories"))
        if tot and abs(tot - 100) > 0.01:
            body.append("<p><strong>Check:</strong> the category weights add to %g, not 100. That is correct for a points-based "
                        "gradebook and a problem for a weighted one.</p>" % tot)
    if lt:
        body.append("<h2>Publisher and outside tools (LTI)</h2>")
        body.append(table(["Link", "Opens"], [[x["title"], x["host"]] for x in lt], "Outside tools"))
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import package_checks
        rows = package_checks.status_rows(course.parent / "check-log.json")
        body.append("<h2>Quality checks: when each last ran</h2><p>Run <code>check</code> and <code>audit</code> to refresh. "
                    "&ldquo;Not built yet&rdquo; means the check does not exist, so silence is not a pass.</p>")
        body.append(table(["Check", "Last run", "Result"], [list(r) for r in rows], "Quality checks"))
    except Exception:
        pass
    body.append("<h2>What an export does not carry</h2><p>Check these by hand in D2L after any import.</p><dl>")
    for t, d in NOT_IN_EXPORT:
        body.append("<dt>%s</dt><dd>%s</dd>" % (esc(t), esc(d)))
    body.append("</dl>")
    unk = other_quiz_keys(qs)
    if unk:
        body.append("<h2>Other quiz settings found</h2><p>No plain-English name yet: %s.</p>" % esc(", ".join("%s (%d)" % kv for kv in unk.items())))

    doc = "".join(body)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import package_checks
        det = package_checks.details(course.parent / "check-log.json")
        first = [(ti, items[0]) for _k, (ti, _w, items) in det.items() if items]
        if first:
            wl = ("<h2>Worth a look first</h2><p>The main things the quality checks found. Full detail is in the quality report.</p><ul>"
                  + "".join("<li>%s</li>" % esc(i[:260]) for _t, i in first[:6]) + "</ul>")
            doc = doc.replace("<h2>Patterns in this course</h2>", wl + "<h2>Patterns in this course</h2>", 1)
    except Exception:
        pass
    heads = re.findall(r"<h2>(.*?)</h2>", doc)
    toc = "<nav aria-label='On this page'><strong>Jump to:</strong> " + " &middot; ".join(
        "<a href='#s%d'>%s</a>" % (i, h) for i, h in enumerate(heads)) + "</nav>"
    for i, h in enumerate(heads):
        doc = doc.replace("<h2>%s</h2>" % h, "<h2 id='s%d'>%s</h2>" % (i, h), 1)
    doc = doc.replace("<h2 id='s0'>", toc + "<h2 id='s0'>", 1) if heads else doc
    Path(out_path).write_text(page("Course settings: " + name, doc), encoding="utf-8")
    return {"quizzes": len(qs), "dropboxes": len(dbs), "discussions": len(ds), "announcements": len(ns), "lti": len(lt)}
