"""Tests for video_embed. The sample is an embed code copied from MediaSpace on 2026-11-12 (a public video)."""
import unittest, video_embed as ve

SAMPLE = """<div style="max-width:800px"><div style="position:relative;padding-bottom:60.75%"><iframe id="kaltura_player" src='https://cdnapisec.kaltura.com/p/811482/embedPlaykitJs/uiconf_id/54819062?iframeembed=true&amp;entry_id=1_oxcbfgle&amp;config%5Bprovider%5D=%7B%22widgetId%22%3A%221_kola23g3%22%7D&amp;config%5Bplayback%5D=%7B%22startTime%22%3A0%7D'  allowfullscreen webkitallowfullscreen mozAllowFullScreen allow="autoplay *; fullscreen *; encrypted-media *" sandbox="allow-downloads allow-forms" title="Tracing the History of Artificial Intelligence" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0"></iframe></div></div>"""


class Embed(unittest.TestCase):
    def test_parse_sample(self):
        i = ve.parse(SAMPLE)
        self.assertEqual((i["partner"], i["uiconf"], i["entry"], i["widget"]), ("811482", "54819062", "1_oxcbfgle", "1_kola23g3"))
        self.assertEqual(i["title"], "Tracing the History of Artificial Intelligence")

    def test_round_trip_keeps_the_player_url(self):
        i = ve.parse(SAMPLE)
        out = ve.build(i)
        again = ve.parse(out)
        self.assertEqual({k: again[k] for k in ("partner", "uiconf", "entry", "widget")}, {k: i[k] for k in ("partner", "uiconf", "entry", "widget")})
        self.assertIn('title="Tracing the History of Artificial Intelligence"', out)

    def test_title_is_required(self):
        i = ve.parse(SAMPLE); i["title"] = ""
        with self.assertRaises(ValueError):
            ve.build(i)

    def test_refuses_other_sites_and_missing_entry(self):
        with self.assertRaises(ValueError):
            ve.parse('<iframe src="https://evil.example.com/p/1/?entry_id=1_aaaaaaaa"></iframe>')
        with self.assertRaises(ValueError):
            ve.parse('<iframe src="https://cdnapisec.kaltura.com/p/811482/embedPlaykitJs/uiconf_id/1?iframeembed=true"></iframe>')
        with self.assertRaises(ValueError):
            ve.parse("no iframe here")

    def test_entry_only_omits_the_widget(self):
        out = ve.build({"partner": ve.PARTNER, "uiconf": ve.UICONF, "entry": "1_abc12345", "widget": ""}, "A title")
        self.assertNotIn("widgetId", out.replace("%22", '"'))

    def test_title_is_escaped(self):
        out = ve.build(ve.parse(SAMPLE), 'Say "hi" <b>')
        self.assertIn("&quot;hi&quot; &lt;b&gt;", out)


if __name__ == "__main__":
    unittest.main()
