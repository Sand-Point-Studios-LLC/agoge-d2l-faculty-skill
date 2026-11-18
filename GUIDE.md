# Roll your course forward with an AI agent

A start-to-finish guide for Mac and Windows. You do not need to know how to code. You will export
your course from D2L, let an AI agent update it by chatting, and import the result into a new,
empty course shell. Plan on about two hours the first time (setup is most of it).

> **DRAFT (2026-10-27).** Items marked **[VERIFY]** depend on the current ChatGPT/Codex app and on
> where the kit is hosted. The kit itself is built (`build_kit.py`) and tested on a synthetic export,
> not yet on a full real one. Check each item before this goes to faculty.

## The idea in one paragraph

The agent works on a folder on your computer. You put your D2L export in that folder, tell the agent
what to change in plain English, and it edits the files and builds a new import package. **Your live
course is never touched.** The new package goes into a fresh empty shell, you look it over, and only
then does it become the course students see.

## Before you start (one time)

You need three things.

1. **An MSU ChatGPT account with the Edu seat.** Sign in at chatgpt.com with your MSU login. If it
   asks you to pick a workspace, pick the MSU one.
2. **The ChatGPT desktop app, which includes Codex.**
   - **Mac:** download it from the ChatGPT apps page and drag it to Applications. Apple Silicon
     Macs (2020 and later) take the standard build; older Intel Macs take the Intel build.
   - **Windows:** open the Microsoft Store, search "ChatGPT", click **Get**. Or open PowerShell and
     run `winget install --id 9PLM9XGG6VKS -s msstore`.
3. **Python 3.** The package-building tool needs it. Neither platform ships it ready to use.
   - **Mac:** go to python.org/downloads, click the big yellow **Download Python** button, open the
     file, and click **Continue** until it finishes.
   - **Windows:** Microsoft Store, search "Python 3.13", click **Get**.
   - To check: open the agent (below) and type *"Is Python 3 installed? Tell me the version."*

On Windows the agent also works better with **Git** installed (git-scm.com, accept every default).
It is optional but gives you a "revert" button if you dislike a change.

## Part 1 — Export your course from D2L

1. Open the course you want to copy forward.
2. Click **Course Admin** in the navbar, then **Import / Export / Copy Components**.
3. Choose **Export Components**, then **Start**.
4. Choose **Select Components**, and tick **Include course files** and everything you want carried forward: Content, Dropbox,
   Quizzes, Question Library, News (announcements), Grades, Calendar.
5. **Do not tick anything that carries student information:** user data, submissions, grades
   *entered by students*, discussion posts. If a box mentions "User Progress" or "Submissions," leave
   it unticked.
6. Click **Continue**, then **Export**. When the status says finished, click **Download** and save
   the `.zip` file. **Do not unzip it.**

## Part 2 — Set up your working folder

1. Download the roll-forward kit **[VERIFY: final name and link]**. It is a zip called
   `rollforward-kit.zip`.
2. Unzip it into your Documents folder. You get a folder called `Roll-Forward`.
   - **Mac:** double-click the zip.
   - **Windows:** right-click, then **Extract All…**, then **Extract**.
3. Inside `Roll-Forward`, open the folder called `put-export-here` and move your D2L `.zip` into it.

Leave the folder structure alone. The file called `AGENTS.md` and the hidden `.agents` folder hold the
agent's instructions (a Codex *skill* called `d2l-rollforward`). It reads them automatically, and you
never need to open them. The skill is also available on its own as `d2l-rollforward-skill.zip`.

## Part 3 — Open the folder in the agent

1. Open the ChatGPT app and sign in.
2. Choose **Codex**, then **Open a folder**, and pick `Roll-Forward`. **[VERIFY: exact menu wording]**
3. Under the message box, set the permission mode to **Ask for approval**. The agent will then pause
   and ask before it changes or runs anything. Leave it there for your first run.

## Part 4 — Talk to it

**First, say what you want your class to be like.** Start with *"Walk me through my class standards."* The agent asks, one item at a time, how you want quizzes, assignments, late work and announcements to behave (attempts, review after the quiz closes, annotation tools, LockDown Browser, and so on). It saves your answers and later tells you where your old course differs. About ten minutes.

Paste this first message exactly. Replace the bracketed parts.

```
I'm rolling [COURSE NAME] forward from [Fall 2025] to [Spring 2027].
My D2L export is in put-export-here. Please unpack it, then give me a plain-English
inventory: how many modules, pages, quizzes, assignments and announcements there are,
and every date and every mention of the old semester you can find. Don't change
anything yet.
```

Read what it gives you. Then work in steps, in your own words. Examples that work well:

- *"The first day of class is January 12. Shift every due date to match, keeping the same weekday."*
- *"There's no class on Monday, March 15. Move anything due that day to Wednesday."*
- *"Replace 'Fall 2025' with 'Spring 2027' everywhere, and show me each place before you do it."*
- *"The syllabus says my office hours are Tuesdays at 2. Change them to Thursdays at 10."*
- *"Week 7's reading link is dead. What was it pointing to?"*
- *"Add a new announcement for week 1 welcoming students. Use the same tone as my other ones."*

**Say "show me" whenever you want to see the change first.** It will show the before and after.
You can also say *"undo that"* or *"put it back how it was."*

When you are happy, say:

```
Build the import package and tell me what's in it.
```

It writes a zip into the `ready-to-import` folder and gives you a summary, including a list of
everything it changed. **Keep that list.** It is your record of what is different this semester.

## Part 5 — Import into a new shell

> **Never import into a course students are already in.** D2L can't merge an import into existing
> content. You would get a second copy of everything sitting beside the first.

1. Find your new term's course in D2L. MSU creates an empty shell for every section automatically once you are listed as the instructor of record, so there is nothing to request. If it isn't there yet, your department scheduler hasn't assigned you to the section.
2. Open the new shell. Click **Course Admin**, then **Import / Export / Copy Components**.
3. Choose **Import Components**, then **Upload**, and pick the zip from `ready-to-import`.
4. Click **Import All Components**. Wait for the status to read *Completed*.
5. Click through the course as a student would: the first week, one quiz, one assignment, the
   calendar. Check dates and due times in particular.
6. When it looks right, make the shell visible to students.

## Ask it about D2L settings

The skill knows what many D2L settings do and whether a package can carry them. Try:

- *"Show me the settings on every quiz in plain English."*
- *"Does my quiz have a view that opens after it closes? What does it show?"*
- *"Are annotation tools on? What are they?"*
- *"Can an import package set the email-copy box on announcements?"* (It cannot.)

To find out what a setting controls, export the course, change only that one setting in D2L, export
again, and ask: *"Compare these two exports and tell me what changed."* New findings are added to
the shared settings catalog.

## Safety, in plain terms

- **Your original course is never changed.** The agent works on copies in the folder.
- **No student data goes in.** If your export contains any, tell the agent and it will stop. Start the
  export over with the student boxes unticked.
- **Check the dates yourself.** The agent is good at shifting them and can still miss one written
  as prose, such as "due the Friday after break."
- **It can be wrong about content.** It updates what you tell it to. It does not know your course has
  changed in ways you haven't mentioned.
- **Keep Ask for approval on** until you trust it.

## If something goes wrong

| What you see | What to do |
|---|---|
| "Python not found" | Install Python (see Before you start), restart the app, ask again. |
| Windows: a script is "blocked" or "not digitally signed" | Ask the agent: *"Fix the PowerShell execution policy for me, and explain what it will change first."* |
| Mac: "cannot be opened because the developer cannot be verified" | Open **System Settings → Privacy & Security**, scroll down, click **Open Anyway**. |
| The import finishes with warnings | Copy the warnings into the chat and say *"explain these."* |
| The agent says it can't find your export | Check that the zip is directly inside `put-export-here` and is still zipped. |
| Anything else | Paste the exact message into the chat. It can usually diagnose it. |

## Sharing this with your own agent

If you use a different agent, give it two things: this guide and the `AGENTS.md` file from the kit.
Together they carry everything it needs to work on the same folder the same way.
