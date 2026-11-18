#!/usr/bin/env python3
"""Turn a MediaSpace (Kaltura) embed code into a clean, accessible block for a D2L page.

    python3 video_embed.py --paste "<div ...><iframe ...></iframe></div>" --title "What the video shows"
    python3 video_embed.py --entry 1_abc12345 --title "..." [--widget 1_xyz98765]

Faculty upload the video to mediaspace.msu.edu first, then Share, Embed, and copy the code. Pasting that
whole code is the safe route: nothing here is guessed. Building from an entry ID alone works for the
MSU player but leaves out the per-video widget ID, which has not been confirmed to be optional, so it
says so. Standard library only.
"""
import argparse, html, json, re, sys
from urllib.parse import quote, unquote, urlparse, parse_qs

PARTNER = "811482"        # MSU's Kaltura partner id, from an embed code copied 2026-11-12
UICONF = "54819062"       # the player it uses
HOSTS = {"cdnapisec.kaltura.com", "cdnapi.kaltura.com", "mediaspace.msu.edu"}
SANDBOX = ("allow-downloads allow-forms allow-same-origin allow-scripts allow-top-navigation allow-pointer-lock "
           "allow-popups allow-modals allow-orientation-lock allow-popups-to-escape-sandbox allow-presentation "
           "allow-top-navigation-by-user-activation")


def parse(code):
    """Pull the pieces out of a pasted embed code. Raises ValueError on anything that is not a Kaltura player."""
    m = re.search(r"<iframe\b[^>]*\bsrc\s*=\s*(['\"])(.*?)\1", code, re.I | re.S)
    if not m:
        raise ValueError("I could not find an <iframe> in that. Paste the whole embed code from MediaSpace (Share, then Embed).")
    src = html.unescape(m.group(2))
    u = urlparse(src)
    if u.hostname not in HOSTS:
        raise ValueError("That iframe points at %s, not MediaSpace or Kaltura. I will not build a block from it." % u.hostname)
    q = parse_qs(u.query)
    entry = (q.get("entry_id") or [""])[0]
    if not entry:
        raise ValueError("That embed code has no entry_id, so I cannot tell which video it is.")
    pm = re.search(r"/p/(\d+)/", u.path)
    um = re.search(r"/uiconf_id/(\d+)", u.path)
    widget = ""
    prov = (q.get("config[provider]") or [""])[0]
    if prov:
        try:
            widget = json.loads(unquote(prov)).get("widgetId", "")
        except ValueError:
            pass
    playback = (q.get("config[playback]") or [""])[0]
    t = re.search(r"\btitle\s*=\s*(['\"])(.*?)\1", code, re.I | re.S)
    return {"partner": pm.group(1) if pm else PARTNER, "uiconf": um.group(1) if um else UICONF, "entry": entry,
            "widget": widget, "playback": playback, "title": html.unescape(t.group(2)).strip() if t else ""}


def build(info, title=None):
    """The embed block: responsive, with a real title and the same player settings MediaSpace hands out."""
    title = (title or info.get("title") or "").strip()
    if not title:
        raise ValueError("Give the video a title that says what it shows. Screen reader users hear it before the video plays.")
    cfg = ""
    if info.get("widget"):
        cfg += "&config%5Bprovider%5D=" + quote(json.dumps({"widgetId": info["widget"]}, separators=(",", ":")), safe="")
    if info.get("playback"):          # only echo what MediaSpace itself put in the pasted code
        cfg += "&config%5Bplayback%5D=" + quote(info["playback"], safe="")
    src = ("https://cdnapisec.kaltura.com/p/%s/embedPlaykitJs/uiconf_id/%s?iframeembed=true&entry_id=%s%s"
           % (info["partner"], info["uiconf"], quote(info["entry"], safe=""), cfg))
    return ('<div style="max-width:800px"><div style="position:relative;padding-bottom:60.75%%">'
            '<iframe src="%s" allowfullscreen webkitallowfullscreen mozAllowFullScreen '
            'allow="autoplay *; fullscreen *; encrypted-media *" sandbox="%s" title="%s" '
            'style="position:absolute;top:0;left:0;width:100%%;height:100%%;border:0"></iframe></div></div>'
            % (html.escape(src, quote=True), SANDBOX, html.escape(title, quote=True)))


REMINDER = ("Before you publish: open the page as a student and play the video. Check that MediaSpace shows captions "
            "for it and that they are correct. This tool cannot see inside MediaSpace.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--paste", help="the embed code copied from MediaSpace (Share, Embed)")
    g.add_argument("--entry", help="a MediaSpace entry id such as 1_abc12345 (see the note about the widget id)")
    ap.add_argument("--title"); ap.add_argument("--widget", default="")
    ap.add_argument("--out", help="write the block to this file (recommended: nothing but the code ends up in it)")
    a = ap.parse_args()
    try:
        if a.paste:
            info = parse(a.paste)
        else:
            if not re.fullmatch(r"\d_[a-z0-9]{8}", a.entry):
                raise ValueError("An entry id looks like 1_abc12345.")
            info = {"partner": PARTNER, "uiconf": UICONF, "entry": a.entry, "widget": a.widget, "title": ""}
            if not a.widget:
                print("NOTE: no widget id given. The player may still work for this video, but that is not confirmed. "
                      "Pasting the full embed code from MediaSpace is the safe route.", file=sys.stderr)
        block = build(info, a.title)
        if a.out:
            open(a.out, "w", encoding="utf-8").write(block + "\n")
            print("Wrote the block to %s. Paste its contents into your page." % a.out, file=sys.stderr)
        else:
            print(block)
        print("\nNOTE (not part of the code, do not copy): " + REMINDER, file=sys.stderr)
    except ValueError as e:
        sys.exit("STOP: " + str(e))


if __name__ == "__main__":
    main()
