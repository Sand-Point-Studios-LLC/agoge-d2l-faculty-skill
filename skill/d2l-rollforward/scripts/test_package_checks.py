"""Known-answer tests for package_checks. Run: python3 test_package_checks.py"""
import tempfile, unittest
from pathlib import Path
import package_checks as pc

MANIFEST = '<?xml version="1.0"?><manifest xmlns:d2l_2p0="x"><resources>%s</resources></manifest>'


def make(files):
    d = Path(tempfile.mkdtemp())
    for name, text in files.items():
        (d / name).write_text(text, encoding="utf-8")
    return d


class Checks(unittest.TestCase):
    def test_bad_xml_is_found_and_good_is_quiet(self):
        self.assertTrue(pc.xml_wellformed(make({"a.xml": '<a title="Bad "quote"/>'})))
        self.assertFalse(pc.xml_wellformed(make({"a.xml": '<a title="fine &quot;x&quot;"/>'})))

    def test_grade_weights(self):
        g = '<grades><configuration><calculation_options grading_system="%s"/></configuration><categories>%s</categories></grades>'
        cat = '<category><name>c</name><scoring><weight>%s</weight></scoring></category>'
        self.assertTrue(pc.grade_weights(make({"grades_d2l.xml": g % ("1", cat % 40 + cat % 45)})))      # 85, weighted
        self.assertFalse(pc.grade_weights(make({"grades_d2l.xml": g % ("1", cat % 50 + cat % 50)})))     # 100
        self.assertFalse(pc.grade_weights(make({"grades_d2l.xml": g % ("0", cat % 10 + cat % 10)})))     # points: weights ignored

    def test_blank_stem(self):
        q = '<q><assessment><item><presentation><material><mattext>%s</mattext></material></presentation></item></assessment></q>'
        self.assertTrue(pc.quiz_stems(make({"quiz_d2l_1.xml": q % "  "})))
        self.assertFalse(pc.quiz_stems(make({"quiz_d2l_1.xml": q % "What is a key?"})))

    def test_draw_larger_than_bank(self):
        s = ('<q><section><qtimetadata><qti_metadatafield><fieldlabel>qmd_numberofitems</fieldlabel>'
             '<fieldentry>%d</fieldentry></qti_metadatafield></qtimetadata>%s</section></q>')
        refs = "<itemref/>" * 3
        self.assertTrue(pc.quiz_banks(make({"quiz_d2l_1.xml": s % (5, refs)})))
        self.assertFalse(pc.quiz_banks(make({"quiz_d2l_1.xml": s % (2, refs)})))

    def test_instructor_only(self):
        m = '<manifest><organizations><organization><item isvisible="%s"><title>%s</title></item></organization></organizations></manifest>'
        self.assertTrue(pc.instructor_only_visible(make({"imsmanifest.xml": m % ("True", "Exam 1 Answer Key")})))
        self.assertFalse(pc.instructor_only_visible(make({"imsmanifest.xml": m % ("False", "Exam 1 Answer Key")})))
        self.assertFalse(pc.instructor_only_visible(make({"imsmanifest.xml": m % ("True", "Risks and Solutions to Mitigate")})))

    def test_accessibility(self):
        self.assertTrue(pc.page_accessibility(make({"a.html": "<h1>x</h1><h3>y</h3><img src='a.png'>"})))
        self.assertFalse(pc.page_accessibility(make({"a.html": "<h1>x</h1><h2>y</h2><img src='a.png' alt='a chart'>"})))
        self.assertFalse(pc.page_accessibility(make({"a.html": "<h3>starts at three</h3><h4>ok</h4>"})))

    def test_dates_in_text(self):
        self.assertTrue(pc.dates_in_text(make({"a.html": "<p>Due January 15 at noon</p>"})))
        self.assertTrue(pc.dates_in_text(make({"a.html": "<p>Due 3/14</p>"})))
        # 24/7 and 13/5 cannot be dates. (1/2 is ambiguous and IS flagged: it could be January 2nd.)
        self.assertFalse(pc.dates_in_text(make({"a.html": "<p>Support is 24/7, ratio 13/5, version 2.1</p>"})))

    def test_embedded_quiz_images(self):
        self.assertTrue(pc.quiz_embedded_images(make({"quiz_d2l_1.xml": '<q><img src="data:image/png;base64,AAAA"/></q>'})))
        self.assertFalse(pc.quiz_embedded_images(make({"quiz_d2l_1.xml": '<q><img src="a.png"/></q>'})))


def course_dir(quiz_due_utc, standards=None, calendar=None):
    """work/course/ with one quiz due at the given UTC time, plus optional standards and calendar next to work/."""
    import json
    root = Path(tempfile.mkdtemp())
    c = root / "work" / "course"
    c.mkdir(parents=True)
    y, mo, d, h, mi = quiz_due_utc
    (c / "quiz_d2l_1.xml").write_text(
        "<questestinterop><assessment title='Q1'><assess_procextension><date_due><timestamp><year>%d</year><month>%d</month>"
        "<day>%d</day><hour>%d</hour><minutes>%d</minutes><seconds>0</seconds></timestamp></date_due></assess_procextension>"
        "</assessment></questestinterop>" % (y, mo, d, h, mi), encoding="utf-8")
    if standards:
        (root / "class-standards.json").write_text(json.dumps(standards), encoding="utf-8")
    if calendar:
        (root / "calendar.json").write_text(json.dumps(calendar), encoding="utf-8")
    return c


class DueAndCalendar(unittest.TestCase):
    RULE = {"due_rules": {"quiz": "due Sunday 11:59 PM"}}

    def test_due_rule_matches_and_differs(self):
        # 2027-01-18 04:59 UTC is Sunday 2027-01-17, 11:59 PM Eastern
        self.assertEqual(pc.due_rules(course_dir((2027, 1, 18, 4, 59), self.RULE)), [])
        # a day later is Monday 11:59 PM
        self.assertIn("not due Sunday 11:59 PM", pc.due_rules(course_dir((2027, 1, 19, 4, 59), self.RULE))[0])
        # 11:00 PM on a Sunday differs in time
        self.assertIn("not due", pc.due_rules(course_dir((2027, 1, 18, 4, 0), self.RULE))[0])

    def test_due_rule_skips_without_standards(self):
        self.assertTrue(pc.due_rules(course_dir((2027, 1, 18, 4, 59)))[0].startswith(pc.SKIP))

    def test_calendar(self):
        cal = {"first_day": "2027-01-19", "last_day": "2027-05-02", "finals": ["2027-05-03", "2027-05-07"],
               "breaks": [["2027-03-06", "2027-03-14", "spring break"]]}
        ok = course_dir((2027, 2, 8, 4, 59), calendar=cal)                       # Sunday Feb 7, in term
        self.assertEqual(pc.calendar_collisions(ok), [])
        brk = course_dir((2027, 3, 9, 4, 59), calendar=cal)                      # Mar 8, spring break
        self.assertIn("spring break", pc.calendar_collisions(brk)[0])
        early = course_dir((2027, 1, 10, 4, 59), calendar=cal)                   # before classes begin
        self.assertIn("before the first day", pc.calendar_collisions(early)[0])
        self.assertTrue(pc.calendar_collisions(course_dir((2027, 2, 8, 4, 59)))[0].startswith(pc.SKIP))


if __name__ == "__main__":
    unittest.main()
