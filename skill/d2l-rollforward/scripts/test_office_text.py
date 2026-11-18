"""Tests for office_text.py: a tiny .docx and .pptx are built in memory-sized temp files."""
import re, sys, tempfile, unittest, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import office_text as ot

W = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
     '<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Office hours are on Mon</w:t></w:r><w:r><w:t>day 1:30 &amp; by appointment.</w:t></w:r></w:p>'
     '</w:body></w:document>')
P = ('<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:p>'
     '<a:r><a:t>Fall 2025</a:t></a:r></a:p></p:sld>')


def build(d):
    with zipfile.ZipFile(d / "a.docx", "w") as z:
        z.writestr("[Content_Types].xml", "<x/>"); z.writestr("word/document.xml", W)
    with zipfile.ZipFile(d / "b.pptx", "w") as z:
        z.writestr("ppt/slides/slide1.xml", P)


class T(unittest.TestCase):
    def run_replace(self, old, new, regex=False):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); build(d); ot.COURSE = d
            import argparse
            ot.cmd_replace(argparse.Namespace(old=old, new=new, regex=regex, apply=True))
            return (zipfile.ZipFile(d / "a.docx").read("word/document.xml").decode(),
                    zipfile.ZipFile(d / "b.pptx").read("ppt/slides/slide1.xml").decode(),
                    zipfile.ZipFile(d / "a.docx").namelist())

    def test_replace_across_runs_keeps_first_run_format(self):
        w, _p, names = self.run_replace("Monday 1:30", "Thursday 10:00")
        self.assertIn("Thursday 10:00", re.sub(r"<[^>]+>", "", w)); self.assertIn("<w:b/>", w)
        self.assertEqual(names, ["[Content_Types].xml", "word/document.xml"])

    def test_pptx_and_escape(self):
        _w, p, _ = self.run_replace("Fall 2025", "R&D 2027")
        self.assertIn("R&amp;D 2027", p)

    def test_no_match_changes_nothing(self):
        w, p, _ = self.run_replace("zzz", "y")
        self.assertEqual(w, W); self.assertEqual(p, P)


if __name__ == "__main__":
    unittest.main()
