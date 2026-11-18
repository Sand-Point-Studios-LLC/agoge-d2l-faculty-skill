#!/usr/bin/env python3
"""Build the faculty kit website (plain HTML, no dependencies) into site/dist/.

    python3 site/build_site.py

Pages are defined below. Every page shares one header, one stylesheet and one footer, reads
well in a browser and prints cleanly. No page claims anything the tool cannot do yet: the
"not built yet" list lives on the Start Here page.
"""
import html, re, shutil
from pathlib import Path

here = Path(__file__).resolve().parent
dist = here / "dist"

CSS = """
:root{--g:#18453B;--m:#137A63;--bg:#fff;--fg:#242424;--soft:#e9f3ef;--line:#c9d6d1;--hd:#18453B}
@media(prefers-color-scheme:dark){:root{--bg:#14191a;--fg:#e8eeec;--soft:#1d2b27;--line:#34463f;--g:#8fd1bd;--m:#6cc4aa;--hd:#0f2a24}}
*{box-sizing:border-box}body{font:17px/1.6 system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:var(--bg);color:var(--fg)}
header{background:var(--hd);color:#fff;padding:.8rem 1rem}header a{color:#fff;margin-right:1rem;text-decoration:none;font-weight:600;display:inline-block;padding:.2rem 0}
header a:hover{text-decoration:underline}header a[aria-current]{border-bottom:3px solid #fff}
a:focus-visible,summary:focus-visible{outline:3px solid #ffbf47;outline-offset:2px}
.skip{position:absolute;left:-999px;top:0}.skip:focus{left:.5rem;top:.5rem;background:#fff;color:#000;padding:.5rem .8rem;z-index:10}
.tbl{overflow-x:auto}
main{max-width:46rem;margin:0 auto;padding:1.2rem 1rem 3rem}h1,h2{color:var(--g)}h1{line-height:1.2}
h2{border-bottom:2px solid var(--m);padding-bottom:.25rem;margin-top:2rem}
.card{background:var(--soft);border-left:5px solid var(--m);padding:.8rem 1rem;margin:1rem 0;border-radius:4px}
button.copy{font:inherit;font-size:.85rem;margin:-.4rem 0 .9rem;padding:.25rem .8rem;border:1px solid var(--g);background:var(--bg);color:var(--g);border-radius:4px;cursor:pointer}button.copy:focus-visible{outline:3px solid var(--g);outline-offset:2px}
@media print{button.copy{display:none}}
pre{background:var(--soft);border:1px solid var(--line);padding:.7rem .9rem;border-radius:6px;overflow-x:auto;white-space:pre-wrap;word-break:break-word}
code{font-family:ui-monospace,Consolas,monospace;font-size:.92em}
details{border:1px solid var(--line);border-radius:6px;margin:.6rem 0;padding:.2rem .8rem}summary{cursor:pointer;font-weight:600;padding:.4rem 0}
ol li,ul li{margin:.35rem 0}table{border-collapse:collapse;width:100%}th,td{border:1px solid var(--line);padding:.45rem;text-align:left;vertical-align:top}
th{background:var(--soft)}footer{border-top:1px solid var(--line);padding:1rem;text-align:center;font-size:.9rem}
a{color:var(--m)}
@media print{header,footer,.skip{display:none}main{max-width:none}details>*{display:block}
a[href^=http]::after{content:" (" attr(href) ")";font-size:.85em}}
"""

NAV = []   # filled from the articles by main()


def block(text):
    return "<pre><code>%s</code></pre>" % html.escape(text)


def page(fname, title, body):
    nav = "".join('<a href="%s"%s>%s</a>' % (f, ' aria-current="page"' if f == fname else "", t) for f, t in NAV)
    return ("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>%s | D2L roll-forward kit</title><style>%s</style></head><body><a class='skip' href='#main'>Skip to content</a>"
            "<header><nav aria-label='Pages'>%s</nav></header><main id='main'>%s</main>"
            "<footer>Agoge D2L Faculty Skill. Open source (Apache-2.0) from Sand Point Studios.</footer>"
            "<script>(function(){document.querySelectorAll('pre > code').forEach(function(c){var p=c.parentNode;var b=document.createElement('button');b.type='button';b.className='copy';b.textContent='Copy';b.setAttribute('aria-label','Copy this prompt');"
            "b.onclick=function(){var t=c.textContent;var done=function(){b.textContent='Copied';setTimeout(function(){b.textContent='Copy'},1500)};"
            "if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(done,function(){sel()})}else{sel()}"
            "function sel(){var r=document.createRange();r.selectNodeContents(c);var g=getSelection();g.removeAllRanges();g.addRange(r);try{document.execCommand('copy');done()}catch(e){b.textContent='Press Ctrl+C'}}};"
            "p.parentNode.insertBefore(b,p.nextSibling)})})()</script>"
            "<script>addEventListener('beforeprint',function(){document.querySelectorAll('details').forEach(function(d){d.open=true})})</script>"
            "</body></html>" % (html.escape(title), CSS, nav, body.replace("<table", "<div class='tbl'><table").replace("</table>", "</table></div>")))


META = re.compile(r"\A<!--\s*(.*?)-->\s*", re.S)


def load_articles():
    """Each article is site/content/<name>.html: a small front-matter comment, then the page body."""
    arts = []
    for p in sorted((here / "content").glob("*.html")):
        raw = p.read_text(encoding="utf-8")
        m = META.match(raw)
        meta = dict(l.split(":", 1) for l in (m.group(1).strip().splitlines() if m else []) if ":" in l)
        meta = {k.strip(): v.strip() for k, v in meta.items()}
        arts.append({"file": p.name, "title": meta.get("title", p.stem), "category": meta.get("category", "Other"),
                     "order": int(meta.get("order", 99)), "verified": meta.get("verified", ""),
                     "body": raw[m.end():] if m else raw})
    return sorted(arts, key=lambda a: (a["order"], a["title"]))


def all_articles_body(arts):
    out = ["<h1>All articles</h1><p>Every article, grouped by topic, with the date each was last checked.</p>"]
    for cat in dict.fromkeys(a["category"] for a in arts):
        out.append("<h2>%s</h2><ul>" % html.escape(cat))
        for a in arts:
            if a["category"] == cat:
                out.append('<li><a href="%s">%s</a> <small>(checked %s)</small></li>' % (a["file"], html.escape(a["title"]), html.escape(a["verified"] or "not yet")))
        out.append("</ul>")
    return "".join(out)


def main():
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir()
    kit = here.parent / "rollforward-kit.zip"
    if kit.is_file():   # build it first with: python3 build_kit.py
        (dist / "downloads").mkdir()
        for z in ("rollforward-kit.zip", "rollforward-kit-contents.zip"):
            if (here.parent / z).is_file():
                shutil.copy(here.parent / z, dist / "downloads" / z)
    else:
        print("WARNING: rollforward-kit.zip not built; the download link will be dead")
    arts = load_articles()
    NAV[:] = [("index.html", "Start here"), ("quick-start.html", "One page"), ("setup.html", "Set up"), ("prompts.html", "Prompt card"), ("all-prompts.html", "All prompts"),
              ("faq.html", "FAQ"), ("all.html", "All articles")]
    for a in arts:
        foot = ('<p><small>Last checked %s.</small></p>' % html.escape(a["verified"])) if a["verified"] else ""
        (dist / a["file"]).write_text(page(a["file"], a["title"], a["body"] + foot), encoding="utf-8")
    (dist / "all.html").write_text(page("all.html", "All articles", all_articles_body(arts)), encoding="utf-8")
    print("built %d articles in %s" % (len(arts), dist))


if __name__ == "__main__":
    main()
