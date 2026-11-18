# Faculty kit site

A small knowledge base, built with `python3 site/build_site.py` into `site/dist/` (not committed).

**Add an article:** put a file in `site/content/`, for example `quiz-attempts.html`. Start it with:

```
<!--
title: What attempts mean on a quiz
category: Quizzes
order: 10
verified: 2026-11-12
-->
<h1>...</h1>
```

then the body in plain HTML. Rebuild. It appears in "All articles" under its category, with its last-checked date.
Update `verified` whenever you re-check an article against D2L.

**Moving it later (SharePoint or anywhere):** the articles are plain HTML bodies with a few lines of
metadata, no scripts and no server. Convert them to SharePoint pages, Word or PDF as needed. Do not
assume SharePoint will display an uploaded .html file as a web page; document libraries commonly
offer it as a download. Check in your tenant before choosing that route.

**Developer note: `references/` is generated.** `skill/d2l-rollforward/references/` is git-ignored and is filled by
`build_kit.py` from `standards/` (one source). In a source checkout you will not see it, but SKILL.md and some
tool messages name files in it. The built kit zip always contains it. Test the kit as built (unzip
`rollforward-kit-contents.zip`), not only from the source tree.
