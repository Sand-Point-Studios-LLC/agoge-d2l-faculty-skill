# Quality checks for the faculty kit

**Status as of 2026-11-12:** the registry in `package_checks.py` is the source of truth. The quality report shows each check, when it last ran, and lists the planned ones as "not built yet". This file is the plan; where it disagrees with the report, the report is right.

Draft 2026-11-12. Every check must run with Python alone (no server, no GitHub, no pip), print only
problems, and say in plain words what to do. A check that cries wolf gets ignored, so each one is
high-precision or marked **warn**.

Status: **have** = already in `rollforward.py`; **port** = exists in the maintainers' private tooling, needs a standard-library
version for faculty; **new** = from this semester's failures, nothing exists yet.
Source for the failures: the pitfall research of 2026-11-12 (35 items; see the sources named there).

## A. Before packing (these protect the import)
| # | Check | Why | Status |
|---|---|---|---|
| A1 | Every XML file parses | One unescaped `"` made D2L refuse a 669 MB package with "Conversion failed" | **have** (2026-11-12) |
| A2 | Every file in the zip is declared in `imsmanifest.xml`, and `imsmanifest.xml` is first and at the root | A package that declares nothing imports nothing | **have** (2026-11-12) |
| A3 | `replace --apply` escapes `&`, `<`, `"` inside XML | Same failure as A1, caused by our own tool | **have** (2026-11-12) |
| A4 | Every `src` / `href` on every page resolves to a file in the zip (decode `&amp;` and `%20`) | A package had 129 pages and no images | **have** (2026-11-12) |
| A5 | Nothing named `_archive*`, `_backup`, `old` ships | Archive folders reached students | **have** (2026-11-12) |
| A6 | Paths under 128 characters | D2L path limit | port |
| A7 | No empty `href=""` topics | Drag-and-drop leaves orphan topics that render blank | **have** (2026-11-12) |

## B. Quizzes
| # | Check | Why | Status |
|---|---|---|---|
| B1 | Answer order shuffled (or the faculty member opted out) | Right answer listed first shows up at A | have |
| B2 | Annotation tools match the faculty member's choice | Varies by faculty | have (make it a choice, not a default) |
| B3 | Extra results view matches the faculty member's choice | Varies by faculty | have (same) |
| B4 | Attempts, time limit and "time limit enforced" agree with the syllabus | ACC 826 shows 120 minutes set but not enforced on all 21 quizzes | **have** (time-limit check, 2026-11-12) |
| B5 | Question order random matches the faculty member's choice | Not read today; element unconfirmed | new (confirm element first) |
| B6 | Random-draw size does not exceed the bank | Drew 15 of a 10-question bank | **have** (2026-11-12) |
| B7 | No blank question stems | A generator put stems in the wrong column; options still passed | **have** (2026-11-12) |
| B8 | No `data:` images inside a quiz | D2L rewrites them to `javascript://`; students see a broken image | **have** (2026-11-12) |
| B9 | Quiz title carries no "Quiz 7" style number | Renaming a graded item makes a second gradebook column | new (warn) |
| B10 | LockDown settings listed for re-enabling by hand | Respondus is not carried in a package | new (reminder) |

## C. Dates
| # | Check | Why | Status |
|---|---|---|---|
| C1 | New first day is the same weekday as the old one | Otherwise every weekday moves | have |
| C2 | Dates that disagree: manifest, quiz, dropbox, syllabus, announcements | A dropbox closed two weeks before the announcement said | new |
| C3 | Dates not in ISO form (month names, `11/4`, `11:59 PM`) | The shift only moves ISO stamps and quiz timestamps | **partial**: lists pages with dates in text; Word, slides and PDFs not read |
| C4 | Dates inside Word, PowerPoint, Excel and PDF attachments | The shift never opens them | new (list only) |
| C5 | Break weeks and finals checked against the published calendar | Finals shipped a week early | new (asks, does not guess) |

## D. Pages and accessibility
| # | Check | Why | Status |
|---|---|---|---|
| D1 | Every image has alt text; long alt text listed | Accessibility; the D2L editor truncates at 200 | **partial**: alt attribute only, not alt quality |
| D2 | Heading levels do not skip | Screen readers | **have** (heading skips) |
| D3 | No links from one content page to another | D2L rewrites the tree and the links break | port (`no-cross-document-links.yaml`) |
| D4 | Instructor-only titles ("answer key", "TA", "solution") are hidden | Four TA guides reached students | **partial**: obvious names only |
| D5 | Videos have captions and a transcript | Accessibility | port (`check_video_caption_pairing.py`) |
| D6 | No hotlinked images in announcements | They break; relative paths do not resolve in news items | new |
| D7 | Embedded files under the size ceiling | Embed limits in `embedding.yaml` | port (`shrink_embeds.py`) |
| D8 | Old term names, in several spellings, including inside tags and attachments | A search for "Fall 2025" misses "F25" and split tags | have (widen) |

## E. Course set-up
| # | Check | Why | Status |
|---|---|---|---|
| E1 | Gradebook category weights add to 100 (when weighted) | A weighted book with no weights showed 0% to everyone | **have** (2026-11-12) |
| E2 | Every graded item has something behind it (quiz, dropbox or tool link) | 720 of 1,010 points had no artifact | **partial**: gradebook items with nothing behind them |
| E3 | Export has course files (not a ~1 MB manifest-only export) | Looks fine, carries no content | new |
| E4 | Navbar-only tools (FAQ, Links) flagged | Students cannot reach them after import | new |
| E5 | Export holds no student data, by content and not only by name | A gradebook was committed once | have (name only; add content) |
| E6 | Outside-tool (LTI) links listed: move, never recreate | A new link is not paired and returns no grades | new (reminder) |

## F. After import (for the faculty member, not the tool)
Done by hand in the new shell. `report` prints this list.
1. Open one question in every quiz in student preview.
2. Open one page with an image and one with a video as a student.
3. Check each due date against the syllabus.
4. Turn LockDown and Monitor back on.
5. Re-add FAQ and Links to the navbar if they were used.
6. Tick "send an email copy" on announcements if wanted.

## Rules for adding a check
- Say what it found in plain words, and what to do next.
- Print nothing when there is nothing to report.
- Test it on a real export and on a synthetic one with a known answer.
- If a check could be wrong, mark it **warn** and say so in the message.
