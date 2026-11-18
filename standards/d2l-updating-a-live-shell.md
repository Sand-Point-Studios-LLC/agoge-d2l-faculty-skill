# Updating a D2L shell that students are already in

How to push content changes into a **live** course without duplicating the tree
or destroying student work. Written 2026-09-02 after doing it to ITM 208's FS26
merged shell with students already working in it — a pre-test taken, two Position
Paper submissions in, and the course open.

For building a package in the first place, see
[`d2l-package-format.md`](d2l-package-format.md). This file is about the case
that spec does not cover: the shell already exists and is in use.

---

## The rule that decides everything

**A course import cannot update an existing shell.** D2L re-maps content
identifiers on import (`d2l-package-format.md` III.2), so it cannot match a
topic you already have. Import the package into a live shell and you get a
second copy of the entire tree beside the first.

**And it will not overwrite files.** A file already at that path is left alone,
so even the content would not land.

So for a live shell, the package is a *source of files*, not something you
import. You replace files in **Manage Files** and do modules and topics by hand.

| What changed | How it gets there |
|---|---|
| A page's text | Replace the file in Manage Files. The topic keeps pointing at it. |
| A new page | Place the file, then create a topic for it. |
| A new module, or a topic moving | By hand. No file operation can do it. |
| A quiz, dropbox or gradebook item | By hand, or accept a duplicate. See the naming trap below and **Quizzes** below. |

---

## The procedure

### 1. Export the live shell — with course files

Course Admin → Export. **Tick "Include course files" on the last screen.** Without
it you get a ~1 MB manifest-only export that proves the topic tree and nothing
about page content. With it, ~700 MB and every page.

A course export contains **no student data** — no `<user>`, `<attempt>` or
`<submission>` element exists in the format. `grades_d2l.xml` carries structure
only. That is why quiz results and assignment submissions can never be moved by
import, and why they are also never at risk from one.

### 2. Build the package and stage the difference

```bash
python spine/shared/tools/build_d2l.py audit   <course>
python spine/shared/tools/build_d2l.py clear   <course> --all
python spine/shared/tools/build_d2l.py declare <course>
python spine/shared/tools/build_d2l.py package <course> -o BUILT.zip

python spine/shared/tools/stage_live_delta.py LIVE-EXPORT.zip BUILT.zip \
       -o D2L-DELTA --zip
```

`stage_live_delta.py` compares **readable text**, not bytes, so a page differing
only in whitespace, an entity, or D2L's own re-serialisation is not counted. On
ITM 208 that turned "everything looks different" into 17 pages out of 406.

Measure every time. Do not assume the delta from a previous run still holds — on
ITM 208 the staged zip was built before one more page was declared, and that page
silently was not in it.

### 3. Upload

Course Admin → **Manage Files**. You land in
`/content/enforced/<course-id>/`, which already holds `content/`,
`questioncollections/` and `resources/`.

**Upload the zip *there* and use its dropdown → Unzip.** Every path inside starts
with `content/`, so it merges into the folder already present and overwrites in
place. Delete the leftover zip.

> 🔴 **Files go inside `content/`, never at the root.** Pages reference assets
> with **relative** paths — `media/itm208-schedule-fs26.jpg`. Dropped at the root,
> where the file browser opens and where drag-and-drop lands things, that resolves
> to a folder which does not exist and every image on the page breaks. This is the
> single most expensive mistake available here; it looks like a corrupted upload
> and is a wrong folder.

**Assets almost never need uploading.** On ITM 208, 536 non-HTML content files
were identical between shell and package and none were new. Check before adding
any — a duplicate image is harder to find later than a missing one.

### 4. Do the modules and topics by hand

Anything that is not a file replacement: new modules, new topics, topics moving
between modules. Small in practice — ITM 208 needed two modules and four topics.

**Move a paired LTI link; never recreate it.** SIMnet links carry grades back
through their pairing. A new link is not paired and silently will not.

### 5. Verify at the consumer

Export again with course files, and re-run `stage_live_delta.py`. Zero
outstanding is the only evidence the upload worked. Also walk the manifest for:

- duplicate module titles
- topics with an empty `href` — see below
- gradebook items in the package that are not in the shell

`compare_live_shell.py` (in ITM 209's build-tools) does the quiz, bank,
announcement, gradebook and dropbox halves of this.

---

## Choose the route by what it costs the person doing it

Count the manual actions before handing anything over, and pick the cheapest
correct route. The same 18 pages can be 17 uploads or one zip and a single
**Unzip**. The same 15 new pages can be 15 topics dragged one at a time, or 3
sub-modules dragged once each — `build_hidden_module.py` groups them by the
destination it reads out of `d2l-structure.json`, so the grouping and the
"Goes to:" note on every item both come from the tree rather than from a list
someone maintains by hand.

Where the cheap route carries a real risk, say both the cost and the risk and
let the instructor choose. Do not quietly pick the safe-but-tedious one.

---

## Quizzes

Quizzes cannot be updated in place, even with Overwrite selected; a full import duplicates the tree.
The only package route (2026-11-08): delete the **unopened** quizzes and their question-library sections,
then import **Quizzes and Question Library only** and never Grades (it duplicates grade columns and the
drop-lowest category). Re-point each quiz at its existing grade item and re-enable Respondus LockDown. A
quiz with attempts can only be repaired by hand. Quiz images must be files imported after their PNGs are
unzipped under `content/`; see `d2l-settings-catalog.md`.

## Traps, each one paid for

**Drag-and-drop puts the file where you are looking.** It does not use the path
from the folder tree you dragged from. It also creates a **new topic named after
the file** rather than replacing anything — and when the file later moves, that
topic is left with an empty `href`, pointing nowhere. It renders as a blank page.
Look for `href=""` in the manifest after any drag-and-drop.

**Respondus renames quizzes.** A LockDown quiz becomes
`Final Exam- Requires Respondus LockDown Browser` — Respondus appends that itself,
and will re-append it if you strip it. So a package's quiz never matches the live
name, and importing one makes a second quiz. Do not import quizzes into a live
shell; if the questions changed, edit the bank in place.

**The gradebook matches by NAME, and categories are not items.** A grade item
whose name differs by a character gets a new column beside the old one, and the
old one keeps the marks. Read `<categories>` and `<items>` **separately** —
"Assurance of Learning" was a category in ITM 208 and "Assurance of Learning -
Pre-test" the item, and conflating them nearly renamed an item onto a category
name, which would have orphaned the column holding real results.

**Deleting is the only thing that destroys student work.** Deleting a quiz
deletes its attempts; deleting an assignment folder deletes its submissions.
Replacing files and adding topics never touch either. When removing a module,
choose **"Remove from Content"**, not "Permanently delete" — on ITM 208 a
duplicate Week 1 held the only copies of three Session B pages, and a permanent
delete would have taken them.

**A shell can hold content no package declares.** Those three Session B pages
were in the shell and in the repo but in no `d2l-structure.json`, so no package
carried them and nothing noticed. `stage_live_delta.py` prints pages that are in
the shell and not the package for exactly this reason — treat them as a question,
not noise.

---

**A `hidden: true` declaration is not evidence the file is in the shell.**
On ITM 208, 2026-09-03: of the solution workbooks declared in
`d2l-structure.json`, all 59 declared visible were present in the live export
and all 45 declared `hidden: true` under `Instructor Materials` were absent.
The correlation is exact, across four modules and twenty-two lessons. The
mechanism is not established &mdash; an import option, or D2L not carrying the
files behind hidden topics &mdash; and it does not matter, because the rule is
the same either way: **before linking a file from a page, confirm the file is
in an export.** Not in the repo. Not in `d2l-structure.json`. In an export.

The cost of assuming otherwise is a page full of links that 404 for every
student, on a page you have just told them to use.

**A file a page links to needs no topic.** This is the cheap half of the same
finding. Manage Files serves anything it holds, so a relative `href` from a
page to a workbook in the same folder resolves whether or not a topic points
at that workbook. Forty-nine solution workbooks reached students through one
**Unzip** and zero topic creations. Reserve hand-built topics for things a
student has to *find* in the module tree; anything reached from a page it sits
beside is a file operation.

---

## Read the artifact, not the folder beside it

Two checks on the same question gave opposite answers on 2026-09-03:

- *"Does every debrief have a solution file?"* asked as **is there a solution
  workbook in this folder** &rarr; 26 of 26, all clear.
- The same question asked as **what does this page actually link, and does that
  file exist** &rarr; 0 of 26. No debrief linked a solution at all, and none of
  the workbooks was in the shell.

The first check was true and useless. Proximity on disk is not delivery, and a
checker that measures the folder will pass a course whose pages reach nothing.
Ask what the consumer receives &mdash; see `completeness-checks.md`, which is
the same lesson from the other end.

---

## Verify a guide against its own starter file

Exercise 10B in ITM 208 promised eighteen data rows against fourteen, three
error values in the `Department` column when they are in a summary block
outside the data, and blank cells to count in a sheet that has none. It had
been written from the lesson's subject matter rather than from the workbook,
and its debrief answered the same imaginary file &mdash; including formulas
citing a named table the workbook does not contain, so every formula on the
page was unrunnable as printed.

Nothing catches this but opening the file. Every count a guide states, every
column name, every named range and every table reference is a claim about a
specific `.xlsx`, and `openpyxl` will answer all of them in a few lines. Two
sibling exercises checked the same way were accurate, so this is a per-artifact
check and not a per-course one.

The related trap: when the starter is shared with another session and already
live, **the guide moves, not the data.** Changing the workbook to match the
prose breaks the exercise that was already using it.

---

## What a course export will never carry

Quiz attempts, assignment submissions, grades, enrolments. None of it is in the
format. Grades can move separately through **Enter Grades → Import** with a CSV
keyed to student and item; attempts and submissions cannot move at all.
