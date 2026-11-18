# D2L settings catalog — what each setting is, where it lives, whether it travels

A running catalog of Brightspace settings: what the checkbox does for students, which XML element
carries it in an import package, and whether a package can set it at all. It is the plain-English
companion to `d2l-package-format.md` (the structure) and `d2l-updating-a-live-shell.md` (the traps).

**Evidence tags.** `[OBSERVED]` read from a real MSU export. `[VALIDATED]` also round-tripped through a
real import. `[REPORTED]` stated by the course owner, not yet seen in XML. Nothing here is
`[GUESSED]`; a setting we have not seen goes in "Not yet found" below.

**Add to it the same way every entry was found:** change ONE setting in D2L, export before and after,
run `diff_exports.py before.zip after.zip`, and write down the element that moved.

## Quizzes — `quiz_d2l_<id>.xml`, inside `<assess_procextension>`

| Setting (what a person sees) | Element | What it does | Tag |
|---|---|---|---|
| Start / end / due date | `date_start`, `date_end`, `date_due` (decomposed timestamp: month, day, year, hour, minutes, seconds) | When the quiz opens, closes, is due. **UTC.** | OBSERVED |
| Add to calendar | `has_schedule_event` = yes | Puts the quiz on the course calendar | OBSERVED |
| Attempts allowed | `attempts_allowed` | Number of tries | OBSERVED |
| Time limit, enforce, grace | `time_limit`, `enforce_time_limit`, `grace_period` | Minutes allowed; whether D2L cuts the student off | OBSERVED |
| Late limit | `late_limit`, `late_limit_data` | What happens to a submission after the due date | OBSERVED |
| Forward only, paging, clock | `is_forward_only`, `paging_type_id`, `show_clock` | Whether a student can go back; questions per page; visible countdown | OBSERVED |
| LockDown Browser | `is_attempt_Rldb`, `is_subview_Rldb` | Require Respondus LockDown Browser to take / to review | OBSERVED |
| Export to gradebook | `grade_item` with `is_autoexport="yes"` | Sends the score to the named grade item | OBSERVED |
| Annotation tools | `annotation_tools_enabled` = yes/no, in `assess_procextension` right after `is_single_session` | Students can bookmark questions and strike through answers while taking it. Opt out in `d2l-course.json` with `"annotation_tools": false` | OBSERVED 2026-10-09, real ITM 210 export (Quiz 6) |
| Randomise answer order | `render_choice shuffle="yes"` on each multiple-choice question (inline in the quiz file, or in `questiondb.xml` for banked quizzes) | Shuffles A/B/C/D per student | VALIDATED. **See "Answer order" below.** |
| Random questions from a bank | nested `<section ident="RAND_…">` with `qmd_numberofitems` | Deliver N of the pool | OBSERVED |

### Submission views — `<assessfeedback>` (a quiz can have several)

Each `<assessfeedback title="…">` is one *view* of a finished attempt. A quiz always has the
**Default view**; extra views are how you show different things at different times.

| Setting | Element | What it does |
|---|---|---|
| Additional view | a second `<assessfeedback title="Additional view">` | A second view that opens later, e.g. the morning after the quiz closes |
| When the view opens | `release_date` | **Local wall-clock time, not UTC** (the quiz's own dates are UTC). Quiz closing 10/11 23:59:59 Eastern has a view release of 10/12 00:01:00 |
| What the view shows | `response_display_type_id`, `show_correct_answers` | Question text and responses; whether right answers are revealed |
| Class statistics | `show_class_average`, `show_score_distribution` | Show the student where they sit in the class |
| Duration, IP limit | `duration`, `submission_restrictip` | `0` means no limit |

**The two views side by side.** Default view: `response_display_type_id` 1, correct answers no (grade
only). Additional view: id 2, correct answers yes, plus the student's own responses. A dated quiz or exam
gets the extra view unless it opts out with `"review_after_close": false`; a quiz with
`show_feedback: false` or no end date never gets one.

**Time zones, the part that bites.** `date_start`, `date_end`, `date_due` are UTC; `release_date` is local
wall-clock. A quiz closing 11/15 23:59:59 Eastern has `date_due` 11/16 04:59:59 UTC and `release_date`
11/16 00:01:00. `rollforward.py shift` handles both (UTC in Eastern time, `release_date` with no
conversion); never shift either by hand.

**How we use it (standing default, 2026-10-09; in `build_d2l.py` on main since PR #45):** grade only in the Default view while the quiz is
open; an Additional view opening 12:01 AM the day after close shows every question, the correct
answers and the student's own responses. Practice tests (no end date) skip it. An import
from before that date lacks the view: reimport, do not hand-edit.

## Answer order — a bug that put the right answer at A (fixed 2026-09-27, commit 8a831d0)

`build_d2l.py` used to hard-code `shuffle="no"` on every question. In our banks the correct option is
listed first, so a quiz imported before 2026-09-27 had the right answer at A for every student. The
builder now writes `shuffle="yes"` and refuses to package otherwise; a quiz whose options are steps in a
sequence opts out with `"shuffle_options": false`. `rollforward.py audit` flags any multiple-choice
question with shuffle off, in the quiz files and in `questiondb.xml`.

**A quiz that already has attempts cannot be fixed by reimport.** Reimporting makes a second quiz and
leaves the attempts on the first (see "Quizzes in a live shell").

## Quizzes imported before the current defaults lack them

Anything imported before 2026-10-09 has no extra view, and some quizzes carry annotation off (ITM 210
Quizzes 8, 10, 12 and both exams did). The fix is a reimport, not a hand edit. Where the quiz already has
attempts, it can only be repaired by hand in D2L.

## Quiz images must be files, not embedded data

D2L rewrites a base64 `data:` image in imported quiz content to `src="javascript://"`, so students see a
broken image and its alt text (observed 2026-09-08: 79 of 80 image questions in a live ITM 210 export).
The same data image renders fine in announcements and content topics: this is quizzes only.

- Banks write `[[diagram:name]]`; `expand_diagrams.py` turns it into `<img src="content/_diagrams/name.png">`
  and the PNGs ship in the package.
- **Import order matters.** In Manage Files, upload and unzip the PNGs inside `content/` (under the
  course's enforced folder) **before** importing the quizzes. A root-level upload breaks the relative path.
- Confirmed 2026-11-08 (reported): the ITM 210 practice final and Exam 1 SQL show their images to students
  this way.
- D2L's editor truncates alt text at 200 characters; an imported alt keeps its full length (358 seen
  intact). Fix images in the source and reimport; do not edit them live.

## Assignments (Dropbox) — `dropbox_d2l.xml`, one `<folder>` each `[OBSERVED]`

| Setting | Where | What it does |
|---|---|---|
| Points | `out_of` (9 decimals) | Maximum score |
| Due date | child `<date_due>` | UTC |
| Hidden | `is_hidden` | Students cannot see the folder |
| Anonymous marking | `is_anonymous` | Hides student names from the marker |
| Submission type, files per submission | `submission_type`, `files_per_submission` | File vs text; how many files |
| Linked grade item | `grade_item` | Omit the attribute for an ungraded folder |
| Instructions | `<instructions text_type>` | The text students read |

Note: `folder_is_retricted` is misspelled **in the format itself**. Keep the typo.

## Content — `imsmanifest.xml`, on each `<item>` `[OBSERVED]`

`date_start`, `date_due`, `date_end` (UTC, ISO), `isvisible` (hidden topics), `resource_type_key`
(what kind of activity). Activities link to their tool by `resource_code` through a quicklink.

## Announcements — `news_d2l.xml` `[OBSERVED]`

`date_start` is both the post time and the release time. `is_draft`, `sort_order`, optional `date_end`
and attachments (under `news/`). Booleans are capitalised `True`/`False` here and lowercase elsewhere.

## Does NOT travel in a package

- **"Send an email copy" on an announcement.** Measured across 185 real announcements: no element
  exists. Tick it at post time.
- **Navigation bars**, and so the FAQ and Links tools that hang off them (`d2l-package-format.md` IV.4).
- **Course settings** in `orgunitconfig.xml`, which was minimal in every export.
- **Anything about people:** enrolments, grades, quiz attempts, submissions, discussion posts.
- **Respondus-renamed quiz titles.** Respondus appends text to a LockDown quiz name in the live shell,
  so a package's quiz never matches it and importing makes a second quiz.

## Quizzes in a live shell (what can and cannot be done)

A full import into a live shell duplicates the whole tree, and quizzes cannot be updated in place even
with Overwrite selected. The only route (reported 2026-11-08; the shared live-shell standard now carries it):
delete the **unopened** quizzes and their question-library sections, import **"Quizzes and Question Library
only"**, then re-point each quiz at its existing grade item and re-enable Respondus LockDown. Never include
Grades: it duplicates grade columns and the drop-lowest category. A quiz with attempts can only be repaired
by hand.

## Quiz-only packages

For a live shell, build a package of just the quizzes you need. `package_quizzes.py` in the ITM 209
course repo (`resources/build-tools/`, on branch `vigil/itm209-tableau-recorded-lectures`) does it
from course source: chosen quizzes, only the diagram PNGs they use, one empty module per placement so the
quiz links have somewhere to land, no dropboxes, no news, and grade items **with no category** (importing
the category would add a second "Quizzes (lowest dropped)" beside the live one). Move the new items into the
live category by hand. It needs the course's `d2l-course.json` and banks, so it works from a course repo,
not from a faculty member's export; the skill does not yet have an export-only equivalent.

## Not yet found (find these with `diff_exports.py`)

Quiz restrictions (release conditions), special access, per-question feedback toggles at quiz level,
rubric attachment, availability-by-group, discussion settings, checklist and survey options beyond
`d2l-package-format.md` Part IV. Record each as soon as it is diffed.
