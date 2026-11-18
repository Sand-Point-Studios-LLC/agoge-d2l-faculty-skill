# Standards walkthrough

You are helping a faculty member say how THEIR course works. Academic freedom is the point: there is
no right answer, and nothing here is a default you should steer toward. Many faculty do not know what
D2L can do, so each item has three jobs: **teach** (what it is), **offer** (the usual choices and what
each costs), **ask** (their choice). Then save it.

## How to run it

0. **Start from their course, not a blank page.** If an export is already unpacked (there is a `work/course`
   folder), run `report` first. If not, ask whether they have put their export in `put-export-here` and
   offer to run `unpack` and `report`. Then, for each section below, open with what THEIR course does now,
   taken from the **Patterns** section of COURSE-SETTINGS.html, in one or two plain sentences: "Your 21
   quizzes allow one attempt; number 11 allows two. Do you want to keep that?" Then teach, offer and ask as
   below. If there is no export, run the walkthrough from the questions alone and say so.
1. One item type at a time (quizzes, assignments, discussions, announcements, dates, layout, formats). Ask
   which they want to start with. Say they can stop after any section and pick it up later.
2. For each setting: say what their course does now, what it does in one plain sentence, give the usual
   choices with one line of cost for each, then ask. Never more than three settings before you stop and let
   them answer.
3. If they say "I don't know" or "what do you recommend": give the common choice and the reason in one
   sentence, say it is their call, and record **"undecided"**, not the common choice.
4. If the course differs from itself (most quizzes one way, a few another), name the numbered outliers and
   ask whether they are on purpose. Do not assume the majority is right.
5. Save answers to `class-standards.json` in the folder they opened (one file per course; they can copy it
   to another course and edit it). Read it back to them in plain words and ask "is that right?"
6. Never write a choice into the file that they did not make. Seeing a pattern is not a choice.

## Saving

Keys the `audit` command compares today are marked **checked**. The rest are **recorded**: you use them
when you help them, and the tool does not check them yet. Say which is which if asked.

```json
{
  "quiz": {"attempts_allowed": 1, "annotation_tools": true, "additional_view_after_close": true,
           "lockdown": false, "calendar_event": true, "time_limit_minutes": null},
  "due_rules": {"quiz": "Sunday 11:59 PM", "assignment": "Sunday 11:59 PM"},
  "layout": "by week, then lesson",
  "default_formats": {"lesson_page": "html", "slides": "pptx", "assignment_template": "docx"},
  "confirm_format_each_time": true,
  "pptx_template": "templates/My-Template.pptx",
  "notes": "anything else they told you"
}
```

A value of `null` or a missing key means they have not decided. Do not flag it.

## 1. Quizzes

Ask first: "Do all your quizzes work the same way, or do you have kinds, like practice, weekly, and exams?"
If kinds, keep one set of answers per kind: `"quiz": {"weekly": {...}, "exam": {...}, "practice": {...}}`.
(`audit` reads a single flat `quiz` block today. With kinds, tell them you will compare by hand.)

**Attempts** (`attempts_allowed`, **checked**; 0 means unlimited)
- 1 attempt: strictest; mistakes cost points. Common for exams.
- 2 or 3: students can learn from a miss; D2L keeps the best or the last (their choice, see below).
- Unlimited: good for practice that carries no grade.
- Trap: a quiz that already has attempts cannot be changed by reimport. Decide before the term starts.

**Which attempt counts** (recorded). Highest, average, first or last. Matters only if attempts are more than 1.

**Time limit** (`time_limit_minutes`, **checked**; blank means no limit)
- "Set" and "enforced" are different boxes. A time limit that is not enforced is shown to students and
  does nothing. If they want a limit to bite, both must be on.
- Grace period: a few extra minutes before D2L marks it late.

**Forward only, one question per page, clock** (recorded). Forward only stops students going back; that
is stricter and frustrates some students. The clock is a visible countdown.

**Answer order** (A/B/C/D shuffled; always worth a look)
- Shuffling stops two neighbours seeing the same order, and stops a bank where the right answer is
  always listed first from showing up at A.
- Trap: shuffling is a per-question box, so a quiz can be half shuffled. `audit` reports it.
- Opt out only where the options are steps in a sequence ("first, second, third").

**Question order** (recorded). Random order of the questions themselves, separate from answer order.
Also: draw 15 from a bank of 25, which gives each student a different quiz and discourages sharing.
Trap: the draw size must not exceed the bank. Say which of these they want.

**Annotation tools** (`annotation_tools`, **checked**). Students can bookmark a question and strike
through answers while taking it. Some faculty want them off for exams.

**Extra results view after close** (`additional_view_after_close`, **checked**). A second view of the
quiz that opens later, for example the morning after it closes, and shows questions, correct answers
and the student's own responses. The default view shows the grade only. Options: none (grade only),
or one view with a release time. Trap: a package made before 2026-10-09 may lack it.

**LockDown Browser and Monitor** (`lockdown`, **checked**). Does not travel in a package. Whatever they
choose, the faculty member turns it back on by hand after import.

**Show class average and score distribution** (recorded). Off is the usual choice for a graded quiz.

**Calendar entry** (`calendar_event`, **checked**). Puts the due date in the D2L calendar.

**Naming.** Name a quiz for what it covers ("Quiz - Lessons 4 & 5"), not by number ("Quiz 7").
Renaming a graded item that has marks makes a second gradebook column on import.

**Pictures in quizzes.** They must be image files, not embedded. D2L breaks embedded pictures in
imported quizzes. `check` reports it.

## 2. Due dates and open dates

Ask: "For each kind of work, what day and time is it due? Does it open on a set day? Does it close at the
same moment, or later?" Offer the three D2L dates: **opens**, **due**, **closes**. Late work is accepted
between due and closes.
- Common choice: due on a weekend night so students plan around their week.
- Whatever they choose, record it per type: `"due_rules": {"quiz": "Sunday 11:59 PM", ...}`.
- After `shift`, list every item whose day or time differs from the rule, and every one that lands on a
  break or finals day. Show the list; do not change dates yourself.

**The calendar.** Do not give term dates from memory. Look them up on the official MSU Registrar
calendar (reg.msu.edu, "Academic Calendar") and the Broad calendar, show the first day, last day, finals
and breaks with the source and today's date, and ask them to confirm. Ask whether their sections meet on
different days (Mon/Wed and Tue/Thu lose different meetings at a holiday). If you cannot reach the web,
ask them to paste the calendar text.

## 3. Assignments

Ask about each:
- **Points and what the points are for.** (Weighted gradebooks must add to 100; points-based ones do not.)
- **Files allowed and how many.** Any, or a list. A named template helps ("LastName_FirstName").
- **Anonymous marking** (usually off), **Turnitin** (off in a package; set it in D2L).
- **Late work.** D2L can accept late, with a due and a close date; a penalty is a policy, not a setting.
  Ask what they want, and say plainly that the tool does not apply penalties.
- **Resubmission.** One attempt, or more.
- **Hidden until.** Anything students should not see yet (an answer guide, a later assignment).
- Trap: "instructor only" material must be hidden in the manifest and still ships in the package unless
  removed. Use `check` and look.

## 4. Discussions

What exports is thin (forum and topic settings, not posts). Ask: must students post before they can read
others, is approval needed, anonymous or not, graded (out of how many), group restrictions. Say honestly
that the tool carries only these, and that rubrics and release conditions are not known to travel.

## 5. Announcements

Ask: what day and time do they post, how many per week, and do they want them in the package.
Trap: "send an email copy" does not travel. Tick it when posting. Images must be attached or embedded,
never hotlinked or relative.

## 6. Layout

There is no right layout. Ask: "How should a student find things? By week, by topic, by lesson, by tool?"
Common patterns: Start Here module, then one module per week; or one per topic. Ask what goes inside a
module (overview, readings, slides, practice, quiz). Record it in `layout`. Say honestly that the tool
reads and reports layout today; it does not reorganize modules.

## 7. Formats for new documents

Ask: "When you make something new, what format do you want by default?" Go kind by kind and let them
answer for each: **lesson or reading page**, **slides**, **assignment instructions**, **handout or guide**,
**syllabus**. Teach the choices in one line each:
- **HTML page**: opens inside D2L with nothing to download, is the easiest to make accessible, and is easy to
  reuse in another format later. D2L cannot link from one page to another, so refer to pages by bold name.
- **Word (.docx)**: students can edit it and fill it in, but they have to download it. Good for a template
  students complete.
- **PowerPoint (.pptx)**: for presenting. Uses the .pptx they name under
  `templates/` (record `pptx_template`); if there is none, say so and offer HTML or a content draft.
- **PDF**: fixed layout that looks the same everywhere. Accessible only if it is properly tagged, and this
  kit does not check that.
- **Ask me each time**: a real answer. Record `"ask"`.

Then ask: "When I make something new, do you want me to **check the format with you each time**, or just use
your default?" Recommend checking each time (it costs one sentence and catches the cases where the usual
choice is wrong), but it is their call.

Save as `"default_formats": {"lesson_page": "html", "slides": "pptx", "assignment_template": "docx", ...}`
and `"confirm_format_each_time": true` (or `false`).

**Be honest about what the tool can produce today.** HTML is the one format you can write directly. Word,
PowerPoint and PDF need extra programs the faculty member may not have, and the kit has no builder for
them yet. If their default is one of those, say so, record their choice anyway, and offer either HTML now
or to draft the content for them to paste into Word or PowerPoint. Never silently switch format.

## 8. What an export does not carry

Say this at the end, every time, and offer the report: release conditions and special access, the
navbar (and so FAQ and Links), homepage widgets, LockDown and Monitor, the announcement email copy,
anything about people, and publisher tool (LTI) pairings. These are checked by hand in D2L.
