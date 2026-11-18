# Brightspace (D2L) Native Course Package — Format Notes

**Purpose:** everything known about the D2L-native import package format, consolidated for the
agent inspecting the Spring 2026 course exports. Compiled 2026-08-23.
**Part I** = prior knowledge + web research (read the provenance labels).
**Part II** (bottom half) = findings from actually parsing six real MSU exports on 2026-08-23 —
it answers most of Part I's `[OPEN]` questions and corrects two of its `[OBSERVED]` claims
(nested paths ARE present in real exports; LTI link files carry no BOM). Where the parts
disagree, Part II wins.

**Provenance labels — read these before trusting anything:**

- `[OBSERVED]` — extracted from two real D2L course exports during the `build_d2l.py` work
  (spine/shared/tools/build_d2l.py and CourseStudio's exporter/importer carry these facts in
  their docstrings). Real observations of real exports, but **never round-tripped through an
  actual Brightspace import** — treat as strong hypotheses to confirm against the spring exports.
- `[PUBLIC]` — from D2L community/KB pages, university IT documentation, or third-party vendor
  docs found in web research. Cited inline.
- `[OPEN]` — unknown; a question the spring exports need to answer.

**The headline finding from web research: D2L publishes NO spec for this format.** Community
requests for documentation get pointed at the CSV template inside the quiz-import UI and nothing
else. Every working implementation (Respondus, GetMarked, ours) reverse-engineered real exports.
The spring exports are therefore the authoritative source; these notes are the map of what to
look for and what is already believed.

---

## 1. Container

- `[OBSERVED]` The package is a **zip**. Minimum viable content package =
  `imsmanifest.xml` + `orgunitconfig/orgunitconfig.xml` + the content files.
- `[PUBLIC]` It is a zip **of XML files**: `imsmanifest.xml` as the index, plus **one XML file
  per Brightspace tool** — e.g. `discussion_d2l.xml`, `dropbox_d2l.xml`, `quiz_d2l_XXXXX.xml`.
  (Waterloo LEARN guide; ExamSoft D2L export doc.) D2L KB describes exports as a "modified
  common cartridge formatted zip archive" — i.e. even the *native* format keeps an IMS-style
  manifest as its index. There is no file-based import route without `imsmanifest.xml`.
- `[PUBLIC]` **`imsmanifest.xml` must sit at the zip root**, not in a subfolder. A misplaced or
  malformed manifest causes serious/silent conversion failures. (D2L conversion-troubleshooting
  doc, boris.sdbor.edu mirror.)
- `[PUBLIC]` **File paths inside the package must be ≤ 128 characters** (Windows-derived limit
  in D2L's converter). Long lesson-folder + long filename combinations are a real risk for our
  content tree — audit path lengths before packaging.
- `[OBSERVED]` **`imsmanifest.xml` and `orgunitconfig.xml` both carry a UTF-8 BOM**
  (`EF BB BF`) in both exemplar exports. Preserved deliberately in our builders.
- `[OBSERVED]` Both exemplar exports shipped content files **flat** at the zip root level.
  Nested hrefs (preserving a directory tree) are *believed* legal but **unvalidated on a real
  import** — this is explicitly flagged in CourseStudio's exporter. → Check whether the spring
  exports nest or flatten, and mirror whatever they do.

## 2. imsmanifest.xml

### Namespaces `[OBSERVED]`

```xml
<manifest identifier="D2L_xxxxxxxxxx"
    xmlns:d2l_2p0="http://desire2learn.com/xsd/d2lcp_v2p0"
    xmlns:scorm_1p2="http://www.adlnet.org/xsd/adlcp_rootv1p2"
    xmlns:imsmd="http://www.imsglobal.org/xsd/imsmd_rootv1p2p1"
    xmlns="http://www.imsglobal.org/xsd/imscp_v1p1">
```

### Structure `[OBSERVED]`

- `<metadata>` holds the course title:
  `imsmd:lom > imsmd:general > imsmd:title > imsmd:langstring xml:lang="en"`.
- `<organizations default="d2l_orgs">` contains one
  `<organization identifier="d2l_org">` whose nested `<item>` tree is the module/topic
  hierarchy students see.
- `<resources>` holds one `<resource>` per item, plus one for orgunitconfig.

### Item rules `[OBSERVED]` — the two known import-breakers

1. **`d2l_2p0:id` is a document-order counter starting at 1 with NO gaps.** Gaps break import.
2. **Every `<item identifierref="X">` must have a matching `<resource identifier="X">`.**

Item shape:

```xml
<item identifier="1000007" identifierref="RES_CONTENT_1000007" d2l_2p0:id="1"
      description="" completion_type="2" d2l_2p0:ai_human_origin="0">
    <title>Lesson 01 — Excel Basics</title>
    <!-- child items nest here; a module is an item with children and no file -->
</item>
```

- `[OBSERVED]` `completion_type="2"` on every item in the exemplars. `[OPEN]` what other
  values mean (likely required/optional completion tracking).
- `[OBSERVED]` `d2l_2p0:ai_human_origin="0"` present in current exports (an AI-provenance
  flag). `[OPEN]` accepted values.
- `[OBSERVED]` Our builders use `ident` values starting at 1000000 stepping by 7 — that is a
  **choice, not an observed requirement**; the real requirement is only uniqueness +
  matching identifierref. Check what the spring exports actually use.

### Resource shape `[OBSERVED]`

```xml
<resource identifier="RES_CONTENT_1000007" type="webcontent"
    d2l_2p0:material_type="content" d2l_2p0:link_target=""
    href="Lesson 01 - Excel Basics.html" title="" />
```

- `d2l_2p0:material_type` values seen: **`content`** (a file topic), **`contentmodule`**
  (a module — empty href), **`orgunitconfig`** (the course-config resource, href
  `orgunitconfig/orgunitconfig.xml`).
- `[OPEN]` **The material_type values for every other tool are the key thing to harvest from
  the spring exports** — quizzes, dropboxes, news, discussions, calendar entries all
  presumably appear as resources with their own material_type (or the tool XML files are
  referenced some other way). Record the exact value per tool, and whether the tool files
  appear in `<resources>` at all or ride along unreferenced.

### orgunitconfig `[OBSERVED]`

`orgunitconfig/orgunitconfig.xml`, UTF-8 BOM, minimal form:

```xml
<?xml version="1.0" encoding="utf-8"?>
<orgunit identifier="{uuid4}" />
```

`[OPEN]` Real exports likely carry more here (course offering settings, start/end dates,
colors?). Diff the spring export's orgunitconfig against this minimal form — if course-level
dates live here, that matters for the "due dates" requirement.

## 3. Per-tool XML files — the undocumented core

This is the part with **no public documentation anywhere** and the reason the spring exports
are the spec. Known/expected files and what to extract from each:

| Tool | Expected file(s) | What to document from the spring export |
|---|---|---|
| Quizzes | `quiz_d2l_XXXXX.xml` (one per quiz?) | See §4 below — QTI 1.2 dialect |
| Question Library | possibly separate `questiondb`/section files | How banks vs quizzes are split; how a quiz references bank sections (our model: bank of ~25, deliver 15 random — where does that setting live?) |
| Assignments (Dropbox) | `dropbox_d2l.xml` | Folder name, instructions HTML, **due date / start / end**, submission type, grade-item link, group vs individual, Turnitin flags |
| Announcements (News) | `news_d2l.xml` (name unconfirmed) | Title, HTML body, start/publish date, whether attachments are packaged |
| Discussions | `discussion_d2l.xml` | Forums vs topics nesting, grade links |
| Calendar / due dates | schedule/calendar file (name `[OPEN]`) | Whether due dates live on the tool item, in a schedule file, or both; date format & timezone handling |
| Grades | gradebook XML (name `[OPEN]`) | Grade items, categories, weights, association ids used by dropbox/quiz files |
| Content dates/restrictions | manifest? tool file? | Where a content topic's due/start/end dates live — **not** in the minimal manifests we've built |

Cross-cutting `[OPEN]` questions for every tool file:

- **ID cross-referencing:** how does a dropbox point at its grade item, a quiz at its
  category, a calendar entry at its parent object? Internal numeric ids from the source org
  won't exist on import — figure out which ids are re-mapped on import vs which must be
  internally consistent within the package.
- **Date format:** exact timestamp format and whether times are UTC or org-local.
- **HTML payload encoding:** inline CDATA vs referenced .html files.
- **Does partial packaging work** — can a package carry *only* dropboxes + news + dates and
  import into a course that already has content, or does import expect the full set?
  (D2L's import UI lets you select components, which suggests yes.)

## 4. Quiz format specifics

- `[PUBLIC]` Quiz export files are **"D2L QTI XML", based on IMS QTI 1.2 with D2L-proprietary
  extensions** (Respondus support docs; Clarkson's Moodle-migration doc). Note: QTI 1.2 here
  is a *dialect inside the native package*, not the separate IMS-CC route — you don't opt out
  of it by avoiding Common Cartridge.
- `[PUBLIC]` **Quiz *settings*** (time limits, attempts, shuffle, number of questions delivered
  per attempt, availability/due dates) travel in the export alongside the questions — the CSV
  import route carries **questions only**, into the Question Library, with no quiz setup. This
  is why the CSV path we've used to date can't satisfy "package sets up the quizzes."
- `[PUBLIC]` Images/attachments referenced by questions must be exported with course files or
  the references break (D2L community).
- **Second exemplar available on demand:** Respondus 4.0 (site-licensed at most universities;
  Windows) can "Export QTI XML for manual upload to Brightspace" — a known-good generated quiz
  package from a tool that has done this for 15+ years. Diffing a Respondus-generated package
  against a real D2L export would separate "required" from "incidental" markup. User guide:
  web.respondus.com/wp-content/uploads/2019/08/Respondus40UserGuideD2L.pdf

## 5. Import behavior facts `[PUBLIC]`

- Import path: Course Admin → **Import/Export/Copy Components → Import Components → from a
  course package** → upload zip → Import All Components (or select components).
- Content items from the manifest land in the Content tool; on *conversion* (non-native
  packages) they land under a module called "Imported Lessons" — a native Brightspace package
  should preserve its own module tree instead. Confirm with a sandbox import.
- Component selection at import time exists — the importer can carry quizzes, question
  libraries, assignments, discussions, announcements, calendar, grades (D2L KB
  "Import/Export/Copy Components").
- Validation advice from D2L support is thin: run the manifest through an XML validator;
  beyond well-formedness you find out at import time. **There is no public validator for the
  D2L package format.** Budget for test imports into a sandbox course (MSU D2L help:
  help.d2l.msu.edu) as the only real verification.

## 6. What already exists (so the other agent doesn't reinvent)

- `spine/shared/tools/build_d2l.py` — builds manifest + orgunitconfig + content zip; encodes
  every `[OBSERVED]` fact above; **content topics only** (no tool XML). Never proven against a
  live import.
- CourseStudio `backend/app/exporter/d2l_export.py` / `importer/d2l_import.py` — same format
  knowledge, plus a *parser* of real export zips (BOM-tolerant, walks the org item tree,
  records non-file resources as `skipped`). The importer's `skipped` report on a spring export
  is a fast way to enumerate every non-content resource type present.
- No third-party or open-source tool found (GitHub topics `brightspace`, `d2l-brightspace`;
  PyPI) that generates the full native package. Quiz-only commercial tools: Respondus 4.0,
  GetMarked Digitaliser, Formswrite.
- Alternative route for completeness: the Brightspace/Valence REST API
  (docs.valence.desire2learn.com — current as of Aug 2026) has documented create/update for
  modules/topics (with dates), dropbox folders, news, calendar, grades; quiz creation coverage
  is historically the weak spot. Needs an app ID/key from MSU IT. D2L's own
  `Brightspace/update-course-action` on GitHub drives content this way. Not a package — out of
  scope per the current decision, but it is the only *documented* interface to these objects.

## 7. Suggested extraction checklist for the spring exports

1. Inventory the zip: every filename, which are referenced from `<resources>`, with which
   `material_type`.
2. For each tool file: full element/attribute inventory from a populated example; mark which
   attributes vary between instances and which are constant boilerplate.
3. All dates: where they live, format, timezone behavior.
4. The id graph: every cross-file reference (grade item ↔ dropbox ↔ calendar ↔ content).
5. Quiz chain end-to-end: question library → section → quiz → settings → grade item.
6. orgunitconfig.xml in full.
7. Whether content hrefs are flat or nested.
8. Manifest counter/ident scheme actually used.
9. Anything with `ai_human_origin` or other d2l_2p0 attributes not listed here.

---

# PART II — Parsed findings from six real MSU exports (2026-08-23)

Parsed from the D2L export zips in `~/Downloads` (XML extracted to this session's scratchpad).
Everything below is `[OBSERVED]` in real MSU Brightspace exports — the strongest evidence we
have short of a round-trip import test. Corpus:

| Tag | Zip (Downloads) | What it is |
|---|---|---|
| itm209 | `D2LExport_2458936_SS26-ITM-209-730..._20268537.zip` (1.5 GB, 972 entries) | Full course: content, 20 quizzes, questiondb, dropbox, news, grades, checklist, rubrics, 24 LTI links |
| bus491 | `D2LExport_2547302_SS26-BUS-491-302..._202681429.zip` (199 MB) | Full course, 11 quizzes, 5 LTI links |
| bus491-fs25 | `D2LExport_2476549_FS25-BUS-491-301..._202612330.zip` (58 KB) | **News-only partial export** |
| merged-grades | `D2LExport_2566532_SS26MERGED..._202642410.zip` (4 KB) | **Grades-only partial export** |
| merged-quiz | `...202642410 (1).zip` (0.1 MB) | **Quizzes+questiondb-only partial export** |
| itm444 | `D2LExport_2571455_SS26MERGED..._202611204.zip` (150 MB) | Content + dropbox + grades + rubrics + checklist, no quizzes |

## II.1 Container — confirmed and corrected

- Content files sit **flat at the zip root**, original filenames preserved (spaces, `&`, `#`,
  parentheses all fine). **Nested folders DO occur** and are therefore legal:
  `orgunitconfig/orgunitconfig.xml`, **`news/<file>.html`** (announcement attachments), and
  a content template tree (`Daylight_HTML_Template/assets/img/banner_03.jpg`). This settles
  Part I's open nested-href question: real exports contain nested paths.
- **BOM rule (corrected):** every `imsmanifest.xml`, `orgunitconfig.xml`, `*_d2l.xml`,
  `questiondb.xml`, and `quiz_d2l_*.xml` starts with the UTF-8 BOM. **`basic_lti_link_*.xml`
  files have NO BOM.**
- Manifest `identifier="D2L_<number>"` where the number is the export/org id from the zip name
  (e.g. `D2L_2547302`).
- In the manifest, the orgunitconfig href uses a **backslash**: `orgunitconfig\orgunitconfig.xml`.
- The orgunitconfig `<resource>`'s `identifier` **equals the uuid inside orgunitconfig.xml**
  (`<orgunit identifier="987317ed-..."/>`). orgunitconfig stayed **minimal in every export** —
  one self-closing element, no course settings. Part I's guess that dates might live there: no.

## II.2 imsmanifest.xml — real structure

Metadata block: title = org-unit name, `imsmd:keyword` = the org-unit code
(`SS26-BUS-491-302-226228051-EL-08-118`), `imsmd:language` = `en-us`; langstrings use
`xml:lang="en-us"` (not plain `en`).

**Partial packages are real and minimal.** The grades-only export's manifest has **no
`<organizations>` at all** — just `<resources>` with orgunitconfig + `res_grades`. Same shape
for news-only and quiz-only. A package carrying only the tool XML you want to set up is valid.

**`<item>` attribute census** (387 items bus491 / 860 items itm209 — actual parser, not grep):

| Attribute | Presence | Notes |
|---|---|---|
| `identifier` | all | numeric — D2L's content-object id, NOT a synthetic scheme |
| `identifierref` | all | `RES_CONTENT_<same number>` |
| `d2l_2p0:id` | all | document-order counter from 1, gapless (confirmed) |
| `d2l_2p0:resource_code` | ~95% | `michiganstate-<8 digits>` — org-wide object id (see II.7) |
| `description` | all | may hold entity-escaped HTML |
| `completion_type` | all | `2` throughout |
| `d2l_2p0:ai_human_origin` | all | `0` throughout |
| `date_start` / `date_due` / `date_end` | on dated topics (28/16/28 in bus491) | **content-topic dates live HERE**, ISO `YYYY-MM-DDTHH:MM:SS`, no zone suffix — values like `04:59:59` for a "11:59 PM Eastern" deadline ⇒ **stored as UTC** |
| `isvisible` | rare | hidden topics |
| `resource_type_key` | activity topics | see below |

`resource_type_key` values observed: `D2L.LE.Quizzing.Quiz`, `D2L.LE.Dropbox.Dropbox`,
`D2L.LE.Checklist.ChecklistEntity`, `D2L.LE.Lti.Link`, `D2L.Video`.

**`material_type` full census** (both manifests):
`content`, `contentmodule`, `contentlink`, `orgunitconfig`, `d2lquiz`, `d2lquestionlibrary`,
`d2lnews`, `d2ldropbox`, `d2lgrades`, `d2lsyllabus`, `d2lcourseimage`, `d2lchecklist`,
`d2lrubrics`, `imsbasiclti_xmlv1p0`.

**Tool resources use fixed identifiers** — one each of:
`res_grades`, `res_news`, `res_dropbox`, `res_syllabus`, `res_courseimage`, `res_chklist`,
`res_rubrics`, `res_question_library`; quizzes are `res_quiz_<quizid>` (one per quiz, href
`quiz_d2l_<quizid>.xml`, `title` = quiz name); LTI links are `RES_LTI_CONTENT_<id>` (href
`basic_lti_link_<id>.xml`, optional `d2l_2p0:grade_item="michiganstate-<id>"` attribute).

**How an activity appears in the content tree:** an `<item>` with `resource_type_key` whose
resource is `material_type="contentlink"`, `link_target="_self"`, and href a **quicklink URL
with a literal `{orgUnitId}` placeholder**:

```
/d2l/common/dialogs/quickLink/quickLink.d2l?ou={orgUnitId}&type=quiz&rcode=michiganstate-10914609
/d2l/common/dialogs/quickLink/quickLink.d2l?ou={orgUnitId}&type=dropbox&rcode=michiganstate-8116063
/d2l/common/dialogs/quickLink/quickLink.d2l?ou={orgUnitId}&type=checklist&rCode=michiganstate-5574507
/d2l/common/dialogs/quickLink/quickLink.d2l?ou={orgUnitId}&type=lti&rCode=michiganstate-11340605
```

The `rcode`/`rCode` (casing varies!) matches the `resource_code` of the object defined in the
tool XML — that is the join between content tree and tool. External-URL topics are also
`contentlink` with the raw URL and `link_target="_blank"`.

## II.3 dropbox_d2l.xml — complete observed schema

```xml
<dropbox xmlns:d2l_2p0="http://desire2learn.com/xsd/d2lcp_v2p0">
  <folder name="Lesson 1 Exercise" id="433" submission_type="0" completion_type="0"
          allowable_file_type="0" folder_type="2" sort_order="1" out_of="10.000000000"
          grade_item="michiganstate-11448673" folder_is_retricted="false"
          files_per_submission="0" submissions="2" ai_human_origin="0"
          resource_code="michiganstate-11054522" is_hidden="false" is_anonymous="false">
    <blti xmlns="asset_processors" />
    <instructions text_type="text/plain|text/html"><text>escaped HTML or empty</text></instructions>
    <date_due>2026-02-02T04:59:59</date_due>
  </folder>
  ...
</dropbox>
```

- **`folder_is_retricted` is misspelled IN THE FORMAT.** Reproduce the typo.
- `grade_item="michiganstate-<id>"` links to the grade item by resource_code; **omit the
  attribute entirely for an ungraded folder** (observed).
- Points as `out_of` with 9 decimal places. Due date as a child element, UTC ISO string.
- `is_hidden="true"` observed on a hidden folder.

## II.4 news_d2l.xml (announcements)

```xml
<news>
  <item id="409">
    <headline>BUS 491 starts on 1/26/2026</headline>
    <content text_type="text/html">&lt;p&gt;escaped HTML body&lt;/p&gt;</content>
    <show_date_posted>True</show_date_posted>
    <is_global>False</is_global>
    <is_draft>False</is_draft>
    <only_show_in_course>False</only_show_in_course>
    <sort_order>0</sort_order>
    <date_start>2026-01-13T16:48:00</date_start>
    <!-- optional: <date_end>, <attachment_set><file><file_name>...</file_name></file>... -->
  </item>
</news>
```

**There is no email-copy field, and this was measured.** Teagan asked on 2026-09-03 that
announcements post with the "send an email copy" box ticked. Across **fourteen**
`news_d2l.xml` files and **185** announcement items from real MSU exports, the only elements
that ever appear inside an `<item>` are the nine above plus `date_end` and `attachment_set`.
No `email`, `notify`, `alert` or `send` element exists in any of them.

So the setting does not round-trip through a package and cannot be set by a generator. It is
a tick at post time, per announcement, and belongs in the posting procedure. Do not go
looking for it again.

Booleans are `True`/`False` (capitalized) here, unlike the lowercase `true`/`false` in
dropbox/grades. Attachment files ship under **`news/` in the zip**. `date_start` doubles as
the publish/release date.

## II.5 grades_d2l.xml

Root `<grades xmlns:d2l_2p0>` with **four** sections, in this order:

0. `<schemes>` `[?]` — the grade scheme. Optional in a package; when absent D2L falls back
   to the org default. Structure, from a real ITM 208 export:

   ```xml
   <schemes default_scheme_identifier="56720">
     <scheme identifier="56720" name="Scheme" short_name=""
             is_valid="true" is_org_scheme="false">
       <range percent_start="0" assigned_value="100.000000000"
              symbol="See Syllabus for Grade Scale" color_id="1" />
     </scheme>
   </schemes>
   ```

   `<range>` repeats per band, ascending by `percent_start`; the lowest must start at 0.
   `assigned_value` is optional in the D2L UI ("Assigned Value %") — the builder omits the
   attribute when the config does not set it.

   **`[?]` — only a single-range scheme has ever been observed in an export.** Multi-range
   emission and the omitted `assigned_value` are constructed from the attribute names and
   are NOT validated. Round-trip a dev-shell import before trusting either.

   Why it matters beyond cosmetics: MSU's Grades Submission widget requires a **4.0 scheme**
   with the grade scheme symbol displayed, and the EASE report's `Grade` field is likewise
   0.0–4.0. A package with no scheme produces a gradebook that can only export percentages.
   Declaring a scheme also flips `org_unit_display_options/@show_symbol` to `1`.


1. `<configuration>`: `<calculation_options auto_update_final_grade grading_system
   include_empty_grades_in_final release_adjusted_grade auto_release_final_grade/>` and
   `<org_unit_display_options decimals_displayed show_points show_colour show_symbol
   show_weighted decimals_displayed_my_grades max_characters show_final_grade_calc/>`.
2. `<categories>`: `<category id identifier resource_code>` → `name`, `short_name`,
   `sort_order`, `show_average`, `show_distribution`, `description`, `is_active`, and
   `<scoring>`: `weight`, `can_exceed_weight`, `WeightDistributionType`, `is_auto_pointed`,
   `high_non_bonus_drop`, `low_non_bonus_drop` (**the drop-lowest-N settings**),
   `max_item_points`, `exclude_from_final_grade_calc`.
3. `<items>`: `<item id identifier dates_in_calendar resource_code>` → `name`, `sort_order`,
   `description`, `type_id`, `is_active`, `is_offline_activity`, `<scoring>` …

Every grade object has BOTH a small local `id`, a numeric `identifier` (e.g. `3525486`), and a
`resource_code` — other files link by `resource_code` (dropbox) or by `identifier` (quiz).

## II.6 Quizzes — quiz_d2l_<id>.xml + questiondb.xml

Both are QTI 1.2 `questestinterop` documents with `d2l_2p0` extension elements.

**Quiz shell:** `<assessment d2l_2p0:id title ident="res_quiz_<id>" d2l_2p0:resource_code>`.
ALL quiz *setup* lives in `<assess_procextension>`:

- `<grade_item d2l_2p0:is_autoexport="yes" resource_code="michiganstate-11448663">3525486</grade_item>`
  — element text = the grades_d2l.xml `identifier`; the "export to gradebook" switch is here.
- **Dates are decomposed timestamps**, not ISO strings:
  `<d2l_2p0:date_start><d2l_2p0:timestamp><d2l_2p0:month>1</...><d2l_2p0:day>26</...>
  <d2l_2p0:year>2026</...><d2l_2p0:hour>5</...><d2l_2p0:minutes>1</...>
  <d2l_2p0:seconds>0</...></d2l_2p0:timestamp></d2l_2p0:date_start>` — same for
  `date_end`, `date_due`. Values again UTC.
- `<d2l_2p0:has_schedule_event>yes</...>` — **this is the calendar entry switch.**
- Attempts/timing: `attempts_allowed`, `time_limit`, `enforce_time_limit`, `grace_period`,
  `late_limit`, `late_limit_data`, `mark_calculation_type`, `is_forward_only`,
  `paging_type_id`, `quiz_start_type`, `show_clock`, `is_single_session`.
- LockDown Browser: `is_attempt_Rldb`, `is_subview_Rldb`.
- `<is_active>yes</is_active>`; `disable_right_click`, `disable_pager_access`,
  `notification_email`, `intro_message`.
- `<assessfeedback>`: submission-view settings — `response_display_type_id`,
  `show_correct_answers`, `show_class_average`, etc.

**Questions:** inside `<section ident="CONTAINER_SECTION">`, two modes observed:

1. **Inline** — full `<item>` elements embedded in the quiz file (bus491 lesson quizzes:
   15 fixed MC questions).
2. **Random-from-bank** — nested `<section ident="RAND_<id>">` with
   `<selection_ordering><order order_type="Random"/></selection_ordering>`, a
   `qmd_numberofitems` metadata field (e.g. 35 = how many are delivered), and one
   `<itemref linkrefid="QUES_<qid>_<vid>"><d2l_2p0:file href="questiondb.xml"/>
   <d2l_2p0:points>1.000000000</d2l_2p0:points><d2l_2p0:difficulty>1</...>
   <d2l_2p0:isbonus>no</...><d2l_2p0:ismandatory>no</...></itemref>` **per pool question** —
   i.e. the pool is enumerated by reference into the question library, and D2L picks
   `qmd_numberofitems` of them at delivery. This is exactly our bank-of-25-deliver-15 model.

**Question item format** (same in quiz files and questiondb):
`<item d2l_2p0:id ident="OBJ_<id>" label="QUES_<questionId>_<versionId>" d2l_2p0:page title>`
with `itemmetadata/qtimetadata` fields: `qmd_computerscored`, `qmd_questiontype`
(`Multiple Choice`), `qmd_weighting`, `qmd_globalid` (uuid), `qmd_displayid`,
`qmd_aihumanorigin` (`HumanGenerated`); `itemproc_extension` (`difficulty`, `isbonus`,
`ismandatory`); `presentation/flow/material/mattext texttype="text/html"` +
`response_lid/render_choice` for options; `response_extension` (`display_style`,
`enumeration`, `grading_type`); `resprocessing` with `respcondition/conditionvar/varequal`
and `setvar`; per-option `<itemfeedback>` (**per-option feedback is representable here** —
this is where the CSV pipeline's feedback should land).

**questiondb.xml:** `questestinterop → <objectbank ident="QLIB_<orgid>">` → `<section
ident="SECT_<id>" title>` per library folder (with `sectionproc_extension` display flags) →
question items. Quiz `itemref linkrefid` matches the item's `label`. Note: Respondus
LockDown creates a junk section titled "Respondus LockDown Browser Storage - DO NOT DELETE" —
ignore/preserve, don't emulate.

## II.6a Written-response questions — ⚠️ CONSTRUCTED, NOT OBSERVED

**Added 2026-08-24 for BUS 210's mixed-format final exam (60 MC + 4 written response = 100
points).** Everything else in Part II came from parsing real exports. **This section did not.**

`[OPEN — the important one]` **Every question in all six real MSU exports is
`qmd_questiontype = Multiple Choice`.** There is no observed written-response exemplar in any
export we hold, D2L publishes no schema, and there is no public validator. What
`build_d2l.py:_wr_question_xml` emits is therefore a *reasoned construction*, not a recorded fact,
and it is labelled as such in its own docstring.

Teagan chose to ship it unvalidated on 2026-08-24 with the risk stated. Treat every claim below as
`[OPEN]` until a test import confirms or refutes it.

### What it emits, and why

Built from IMS QTI 1.2 plus the D2L extensions whose meaning is unambiguous from the MC items
sitting beside it in the same file:

```xml
<item ident="OBJ_<id>" label="QUES_<qid>_1" d2l_2p0:page="1" title="...">
  <itemmetadata><qtimetadata>
    qmd_computerscored  = no                 <!-- differs from MC: a human marks it -->
    qmd_questiontype    = Written Response   <!-- GUESS: D2L's UI calls the type "Written Response (WR)" -->
    qmd_weighting       = 10.000000000
    qmd_globalid, qmd_displayid, qmd_aihumanorigin   <!-- same as MC -->
  </qtimetadata></itemmetadata>
  <itemproc_extension>difficulty / isbonus / ismandatory
    [+ <d2l_2p0:initial_text> when the CSV supplies InitialText]</itemproc_extension>
  <presentation><flow>
    <material><mattext texttype="text/html">STEM</mattext></material>
    <response_str ident="<label>_STR" rcardinality="Single">
      <render_fib fibtype="String" rows="10" columns="80" prompt="Box" />
    </response_str>
  </flow></presentation>
  <itemfeedback ident="<label>_KEY">…AnswerKey…</itemfeedback>
  <!-- NO <resprocessing> — nothing is auto-scored -->
</item>
```

**The three specific guesses, in order of how likely they are to be what breaks an import:**

1. **`qmd_questiontype` = `Written Response`.** D2L's interface names the type "Written Response
   Question (WR)" and the CSV import format uses `WR`, so this is the natural string — but the
   export could equally use `Long Answer`, `Essay` or `WR`.
2. **`render_fib` rather than `render_fblock`.** QTI 1.2 renders free text with `render_fib`;
   `render_fblock` belongs to other dialects. `rows`/`columns` are the 1.2 spelling.
3. **Omitting `<resprocessing>` entirely.** Consistent with `qmd_computerscored=no`, but D2L may
   still expect an empty block.

### `[OBSERVED]` — and this part is solid

**Points ride on the `itemref` in the quiz file, not on the question item.** That was already
visible in the MC exports (`<d2l_2p0:points>1.000000000</d2l_2p0:points>` per itemref) and it is
what makes a mixed-format paper expressible at all. `build_d2l.py` now takes the per-question
`Points` value from the CSV instead of hardcoding 1, so BUS 210's exam emits 60 refs at 1.0 and 4 at
10.0 — **verified at 100.000 in the built package.** MC output is byte-identical to before the
change, so ITM 208 and ITM 210 are unaffected.

### How to replace this section with fact

The method that produced the rest of Part II: **create one written-response question by hand in the
dev shell ("ITM 208 Development"), export the course, and diff its `<item>` against what
`_wr_question_xml` emits.** Ten minutes, and it converts three guesses into three observations. Do
this before anyone relies on a written-response import in a live course.

---

## II.7 The ID graph (Part I's biggest open question — answered)

- **`resource_code` = `<orgname>-<number>`** (`michiganstate-11054522`) is the org-wide object
  id and the universal cross-file join key: quicklink `rcode` ↔ tool object; dropbox
  `grade_item` ↔ grade item; quiz `grade_item/@resource_code` ↔ grade item; LTI resource
  `d2l_2p0:grade_item` ↔ grade item.
- Grades objects additionally expose a numeric `identifier`, which the quiz `grade_item`
  element references as text — so quizzes link to grades **two ways at once**.
- Question references: `QUES_<questionId>_<versionId>` labels.
- Manifest `item/@identifier` = content object id, `identifierref` = `RES_CONTENT_<same>`.
- `[OPEN]` (only remaining unknown): which of these the importer re-maps vs. requires. Safe
  strategy for a generated package: mint unique internally-consistent values in every slot
  and keep every cross-reference coherent; test whether an invented org prefix imports.

## II.8 Remaining unknowns after parsing

1. Import-time id re-mapping semantics (above) — only answerable by a test import.
2. `courseimage_d2l.xml` points at an org-relative `/images/<uuid>` path not present in the
   zip — probably non-portable; safe to omit from generated packages.
3. Exact boolean/enum domains for fields we only saw one value of (`completion_type="2"`,
   `folder_type="2"`, `submission_type="0"`, `grading_system`, `type_id`…). Generate what the
   exports show; vary nothing untested.
4. Whether `{orgUnitId}` in quicklink hrefs is substituted at import (almost certainly — it's
   a literal placeholder in every export).
5. Timezone: values are consistent with UTC storage of Eastern-time deadlines; confirm with
   one known deadline before generating dates at scale.

### Sources

- Waterloo LEARN export/import internals: math.uwaterloo.ca/~pkates/LT3/learn-d2l/archive.html
- D2L import compatibility & troubleshooting (mirror): boris.sdbor.edu/d2ldocs/LearnerHelp_201912/brightspace/requirements/all/
- D2L KB — Import/Export/Copy Components: community.d2l.com/brightspace/kb/articles/16771
- D2L KB — course import & conversion support: community.d2l.com/brightspace/kb/articles/4774
- Community: "Proper documentation for CSV file format, please": community.d2l.com/brightspace/discussion/115
- Community: "Seeking Detailed Info on CSV/XML Quiz Formats": community.d2l.com/brightspace/discussion/2891
- ExamSoft — D2L export questions (names quiz_d2l_XXXXX.xml): support.examsoft.com/hc/en-us/articles/11147398194445
- Clarkson — D2L quiz → Moodle (QTI 1.2 dialect): bookstack.clarkson.edu/books/moodle/page/export-d2lbrightspace-quiz-for-import-into-moodle
- Respondus 4.0 D2L guide + manual import: web.respondus.com / support.respondus.com articles 4409607287195, 4409595709339
- Brightspace API reference: docs.valence.desire2learn.com/reference.html (content: /res/content.html)
- D2L update-course-action: github.com/Brightspace/update-course-action
- MSU D2L export help: help.d2l.msu.edu/msu-docs/course-export-and-backing-up

---

# PART III — VALIDATED: live import round-trip, 2026-08-24

A hand-generated probe package (`D2L-FORMAT-PROBE.zip`, 8 files, built strictly from Part II's
rules with entirely invented ids in the `9xxxxxxx` range) was imported into the MSU dev shell
**ITM 208 Development** (`DEV23-tdixon-20251104`) via Course Admin → Import/Export/Copy
Components → Import All Components, then re-exported and diffed.

**Import log:** "Conversion can be natively handled … No conversion by service is necessary,
converts natively in LE … Import is now complete with status Completed" (3 seconds). D2L
recognised the generated package as a **native Brightspace package** — the format spec above
is sufficient to produce one.

## III.1 What the round-trip proved

Everything in the probe survived import and re-export:

- Module + content topic with `date_start`/`date_due`/`date_end` — dates echoed byte-identical
  (UTC convention confirmed: `2026-09-08T03:59:59` displayed as Sep 7 11:59 PM ET).
- Quiz + dropbox **quicklink topics** — `{orgUnitId}` placeholder and `rcode=` joins resolved;
  re-export reproduces them with the SAME invented rcodes.
- Dropbox: graded folder kept its `grade_item` link, HTML instructions, due date; hidden
  ungraded folder kept `is_hidden="true"`; the `folder_is_retricted` typo round-trips.
- Grades: category weight 10%, **drop-lowest-1** (`low_non_bonus_drop`), both items inside the
  category (`category_id` refs rewritten coherently).
- Quiz: attempts=1, decomposed-timestamp dates, `has_schedule_event=yes`,
  `grade_item is_autoexport=yes` re-pointed to the imported grade item, and the
  **random 2-of-3 bank draw** (`selection_ordering Random` + `qmd_numberofitems=2` + three
  `itemref`s into questiondb) fully intact.
- Question library: section, 3 MC questions, **all 12 per-option `itemfeedback` blocks**.
- D2L auto-added `res_syllabus` and `res_courseimage` resources on export (course-level
  objects that always exist) — a generated package does not need to include them.

## III.2 Id-remapping semantics (II.8 item 1 — answered)

| Id kind | On import D2L… |
|---|---|
| Manifest item `identifier` / `RES_CONTENT_*` | **re-mapped** to new content-object ids |
| Tool-local `id` attrs (dropbox folder, news item, grades category/item) | **re-mapped** to small local ids |
| Grades numeric `identifier` | **re-mapped**; cross-refs (`category_id`, quiz `grade_item` text) rewritten to match |
| Quiz object id (`quiz_d2l_<id>`, `res_quiz_<id>`) | **re-mapped** |
| `QUES_<qid>_<vid>` question labels | **re-mapped**; quiz `itemref linkrefid`s rewritten to match |
| `resource_code` (`michiganstate-9xxxxxxx`, invented) | **KEPT** for content items, quiz, dropbox folders, grade *items*, quicklink rcodes (grade *category* got a fresh one) |
| `qmd_globalid` (invented uuids) | **KEPT** — this is a question's stable global identity |

Rule for generators: ids only need to be **internally consistent and unique within the
package**. Invent them freely (org-prefixed `resource_code`s in an unused high range);
D2L re-maps the numeric ids and rewrites every cross-reference itself.

## III.2a Updating a shell that already exists

Everything above describes building a package and importing it into a shell
that is empty or disposable. Once a shell is LIVE - students enrolled, work
submitted - import is the wrong tool: the id re-mapping in III.2 means D2L
cannot match your existing topics, so an import duplicates the whole tree,
and it will not overwrite files that are already there.

**Tested 2026-09-16: the import dialog's "Overwrite the existing file" does not
change this for quizzes.** Teagan imported a one-quiz package (5 questions)
into the dev shell, then a second build with the same quiz, grade item and
content ids, the same `qmd_globalid` on every surviving question, and
Advanced Options > "When an existing file is encountered: Overwrite the
existing file" selected. The quiz duplicated. That option governs files under
Manage Files only; quizzes and question-library items are tool records, and
import adds new ones. A kept `qmd_globalid` is not used to match on import.
Fixture and both packages: `_d2l/overwrite-test/` (`make_owt.py 1|2`).

Measured from the dev shell's component export and Manage Files download after
both imports:

- **Everything duplicated except the file.** Two content modules, two quizzes, two
  question-library sections (identical `qmd_globalid`s in both), two grade
  categories, two grade items. The one HTML page exists once, at its path, and
  holds the v2 text: file overwrite did work, for the file.
- **The second quiz is broken in two ways.** Its resource codes were already
  taken, so D2L gave the v2 quiz and grade item fresh codes
  (`michiganstate-12074852`, `-12074850`). But the v2 module's quicklink kept
  `rcode=michiganstate-97000006`, so **both modules' quiz links open the v1 quiz**,
  and the v2 quiz has **no `grade_item`** - it is not connected to the gradebook.
  A re-import into a shell that already holds the quiz therefore looks like it
  added the new version while students are still sent to the old one.
- **Manage Files holds no quiz data.** 958 files, no quiz XML, no question text;
  the only "Quiz" files are the HTML practice self-checks.

The procedure for that case, with the traps it cost to find, is in
[`d2l-updating-a-live-shell.md`](d2l-updating-a-live-shell.md). Read it
before touching a course students are in.

## III.3 Remaining caveats (minor)

- The re-export did not contain `probe-topic.html` even though its manifest references it —
  the "include course files" option in the export dialog governs whether files ship; the
  topic itself imported and displayed fine.
- Untested beyond MC: other question types, discussions, checklist/rubric import (present in
  Part II schemas from real exports but not exercised by the probe).
- Probe generator: session scratchpad `d2l/make_probe_package.py` (2026-08-24); regenerate
  from this spec if needed — it is ~300 lines of f-strings over Part II.
- **Implementation:** as of 2026-08-24, `shared/tools/build_d2l.py` implements this spec in
  full — a course adds `d2l-course.json` (announcements, gradebook, dropboxes, quizzes with
  bank CSVs, topic dates, quicklink placements) and the four-stage pipeline emits the complete
  package. Dates are authored as course-local wall-clock time and converted to UTC by the
  tool. Tool inputs are master-frozen exactly like content.

**Status: this spec is validated for generating native Brightspace import packages carrying
content + dates, announcements, assignment dropboxes, gradebook structure, question banks,
and fully-configured quizzes.**

## III.4 Round-trip 2 — the full toolchain (2026-08-24, later the same day)

`D2L-FULL-TEST.zip` — built by the extended `build_d2l.py` from a fixture course through the
real audit → declare → package pipeline — imported natively into the same dev shell
("no conversion by service is necessary", Completed in 3s) and was re-exported. Verified, 21/21:

- **Nested content paths WORK** (`content/Lesson 01/Topics/…`, em-dash filename, U+2014 intact).
  D2L accepts forward-slash hrefs and normalises them to **backslashes** on re-export — emit
  either; expect backslashes back.
- Topic dates in both DST regimes round-tripped exactly (EDT `03:59:59Z`, EST `04:59:59Z`
  renderings), confirming the wall-clock→UTC conversion.
- Both announcements (one body sourced from a file), both grade categories with drop-lowest,
  graded + hidden dropbox folders, quiz→grade-item link, 2-of-4 random draw, per-option
  feedback, and the deterministic `qmd_globalid`s all preserved — the invented
  `michiganstate-91xxxxxx` resource codes again kept verbatim.

**Status: the generator (`build_d2l.py` + `d2l-course.json`), not just the format, is
validated end-to-end.** Remaining untested: non-MC question types (out of scope by
quiz-standards.md), discussions, checklists, rubrics, news attachments.

---

# Part IV — Survey, Links, FAQ, and the real free-text question type

Source: `D2LExport_2545446_DEV23-tdixon-20251104-ITM208Development_20269421.zip`, a
deliberately minimal shell Teagan built and exported on **2026-09-03** to settle exactly these
questions. 963 entries, five top-level XML files. Everything in this Part is `[OBSERVED]`.

This is the method that produced Parts II and III, applied once more: **build one by hand,
export, read the bytes.** It was worth it — the first thing it found was a four-year-shaped
hole in something we were about to ship.

## IV.0 🔴 `Written Response` is not a D2L question type

`_wr_question_xml` was flagged `UNVALIDATED` and marked "the first thing to suspect" if an
import ever rejected the exam. It was wrong in five places. BUS 210's final exam carries
**four of these, 20 of its 100 points.**

| field | constructed guess | observed |
|---|---|---|
| `qmd_questiontype` | `Written Response` | **`Long Answer`** |
| `qmd_computerscored` | `no` | **`yes`** — even though a human marks it |
| `response_str/@rcardinality` | `Single` | **`Multiple`** |
| `response_extension` | *absent* | **three flags** (below) |
| `render_fib` | self-closing | **contains a `response_label`** |

Correct in the guess: **no `<resprocessing>`** block, because nothing is auto-scored.

The observed Long Answer item, in full:

```xml
<presentation><flow>
  <material><mattext texttype="text/html">&lt;p&gt;Written Response&lt;/p&gt;</mattext></material>
  <response_extension>
    <d2l_2p0:has_signed_comments>no</d2l_2p0:has_signed_comments>
    <d2l_2p0:has_htmleditor>yes</d2l_2p0:has_htmleditor>
    <d2l_2p0:has_fileupload>yes</d2l_2p0:has_fileupload>
  </response_extension>
  <response_str ident="QUES_..._STR" rcardinality="Multiple">
    <render_fib rows="15" columns="100" prompt="Box" fibtype="String">
      <response_label ident="QUES_..._LA">
        <material><mattext texttype="text/plain" /></material>
      </response_label>
    </render_fib>
  </response_str>
</flow></presentation>
```

**Still unobserved**, and emitted only when a bank fills them: an `<itemfeedback>` answer key
on a Long Answer (legal on MC items in the same file, untested here), and
`d2l_2p0:initial_text`.

### `Short Answer` is a different type again

Not needed by any course today, recorded so nobody confuses it with Long Answer. It carries
**one `response_str` per blank**, an `<outcomes>` block declaring `Blank_1`, `Blank_2`…, a
`respcondition` per accepted string with `case="no"`, and a closing catch-all:

```xml
<respcondition><conditionvar><other /></conditionvar>
  <setvar varname="que_score" action="Set">D2L_Correct</setvar></respcondition>
```

Its `setvar` values are **50** per blank while `qmd_weighting` is `0` — a vestigial
answer-match weight that scores nothing. **`qmd_weighting`, not `setvar`, is what makes a
question ungraded.**

## IV.1 Surveys — `material_type="d2lsurvey"`

A survey is a **quiz in QTI form with every question weighted 0**. Same `<questestinterop>`
root, same `<assessment>`, same item structure, same `CONTAINER_SECTION`. All four question
types appeared in one survey: Multiple Choice, True/False, Long Answer, Short Answer.

Manifest resource:

```xml
<resource identifier="res_survey_1197620" type="webcontent"
          d2l_2p0:material_type="d2lsurvey" href="survey_d2l_1197620.xml" title="Test" />
```

The `<assessment>` carries `d2l_2p0:resource_code="michiganstate-12040511"` — the quicklink
`rcode`, the same join key described in II.7. **Surveys share the quiz resource-code space.**

`<assess_procextension>` — the survey-specific fields, and what is absent matters as much as
what is present:

```xml
<d2l_2p0:submission_message texttype="text/html"/>
<category ident="88559" d2l_2p0:sortorder="1">Test Category</category>
<d2l_2p0:anonymous>no</d2l_2p0:anonymous>
<d2l_2p0:instant_feedback>yes</d2l_2p0:instant_feedback>
<is_active>no</is_active>
<d2l_2p0:date_start/><d2l_2p0:date_end/>
<d2l_2p0:has_schedule_event>no</d2l_2p0:has_schedule_event>
<d2l_2p0:attempts_allowed>unlimited</d2l_2p0:attempts_allowed>
<d2l_2p0:is_forward_only>no</d2l_2p0:is_forward_only>
```

**No grade item, no time limit, no lockdown, no late policy.** `anonymous` and
`is_forward_only` are the two fields a quiz has no equivalent for. Every MC `setvar` is
`0.000000000`, and `qmd_weighting` is `0` on every question.

## IV.2 Links — `material_type="d2llinks"`

One file, `links_d2l.xml`, holding every category. Simple enough to quote whole:

```xml
<externallinks>
  <link_category id="1" sort_order="1" is_public="False">
    <name>Link Category</name>
    <description text_type="text/html" />
    <links>
      <link id="2">
        <title>Test</title>
        <description text_type="text/html" />
        <url>https://sandpointstudios.ltd</url>
        <sort_order>1</sort_order>
        <launch_new_window>True</launch_new_window>
      </link>
    </links>
  </link_category>
</externallinks>
```

Note `is_public` and `launch_new_window` are Python-style `False`/`True`, **not** the `no`/`yes`
used throughout the quiz dialect. Manifest identifier is the literal `res_links`.

## IV.3 FAQ — `material_type="d2lfaq"`

```xml
<faq>
  <category id="4" sort_order="1" is_public="False">
    <name>Test Category</name>
    <description text_type="text/html" />
    <item id="5" sort_order="1">
      <question>How do I solve this?</question>
      <answer text_type="text/html">&lt;p&gt;Ask Claude&lt;/p&gt;</answer>
    </item>
  </category>
</faq>
```

Manifest identifier is the literal `res_faq`. Answers are HTML-escaped; questions are plain
text. **`id` numbers are one sequence shared across tools** — links used 1 and 2, the FAQ
picked up at 4 and 5, and the survey assessment is 3.

## IV.4 🔴 Navigation bars do NOT travel in a course package

Searched the whole 963-entry export for `navbar`, `nav_`, `homepage`, `widget`, `theme` and
`brand`: **zero entries.** Teagan confirmed it independently the same day by exporting a
course with a custom navbar and importing it elsewhere — the navbar did not arrive.

Navbars, homepages and widgets are **org-unit presentation settings, not content**. Moving one
needs *Copy Course Components* between shells on the same instance, or rebuilding it by hand.
Do not promise a navbar in an import package.

### 🔴 And that strands the FAQ and Links, because they cannot go in the content tree

Confirmed by Teagan, 2026-09-04: **only a survey can be added to a content module.** The FAQ
and Links tools are reached from a navbar link and nothing else.

Put those two facts together and a fresh import produces tools that hold their content and
that **no student can reach**. Nothing errors. The package validates, the XML parses, the
entries are all there, and the FAQ is invisible.

Two ways out, and the second is the durable one:

1. Add the navbar links by hand, once per shell. Fine for one course, forgotten by the
   third.
2. **Render the same config as ordinary content pages as well.** BUS 210 does this:
   `tools/build_faq_links_pages.py` reads the same `faq` and `links` blocks from
   `d2l-course.json` and emits two Getting Started pages, so the content travels in the
   content tree whatever the navbar does. One source, two renderings — edit the config and
   re-run, never edit the HTML.

The survey needs neither workaround: `place_in` puts it in a module directly.

### Placing a survey in a module `[V]` — confirmed 2026-09-04

`resource_type_key="D2L.LE.Survey.Survey"`, `type=survey` in the quicklink. The inference
from the `D2L.LE.<Tool>.<Object>` pattern was right.

⚠ One real difference the guess missed: the query parameter is **`rCode`**, capital C, where
quiz and dropbox use lowercase `rcode`. D2L emits both spellings itself — `rcode` for quiz
and dropbox, `rCode` for checklist, lti and survey — so `RCODE_PARAM` in `build_d2l.py` now
matches per type rather than assuming case-insensitivity.

## IV.5 Course image — `material_type="d2lcourseimage"`

```xml
<course_appearance><course_image>
  <pictureId /><hasCatalogPic>True</hasCatalogPic>
  <picLocation>/images/4f48bf35-103d-4a0c-8a05-072b6b7a1869</picLocation>
</course_image></course_appearance>
```

`picLocation` is a shell-local path, so it is **not portable between instances**.

## IV.6 Two smaller observations

**A component-only export has no `<organizations>` element at all** — this one ships only
`<resources>`. Not a new finding: §8 of the canonical guide already records partial packages
behaving this way, from a grades-only export. Noted here as a second independent
confirmation, not a discovery.

**`qmd_aihumanorigin` is real and D2L emits it.** Every observed question carries
`HumanGenerated`. `build_d2l.py` already emits this — confirmed correct rather than invented.

## IV.7 What is still unobserved after Part IV

Discussions, checklists, rubrics, news attachments, release conditions, intelligent agents,
and groups. Same method applies: build one in the dev shell, export, read the bytes.

## IV.8 What the generator emits from this Part

`build_d2l.py` implements all three the same day the schemas were read, driven from
`d2l-course.json`:

| key | emits | notes |
|---|---|---|
| `surveys` | `survey_d2l_<id>.xml` | questions inline in `CONTAINER_SECTION`, no question library, no random draw |
| `faq` | `faq_d2l.xml` | `res_faq`; answers are HTML and get escaped, matching the exemplar |
| `links` | `links_d2l.xml` | `res_links`; `True`/`False` booleans, absolute URLs enforced |

`parse_bank_csv(path, survey=True)` inverts its correctness check: a survey question with
**no** 100-weighted option is correct, and one **with** an option marked correct is now a
build error. Both directions are enforced, because a bank that silently means the opposite
of what it says is worse than either failure.

`validate_tools` refuses an empty FAQ or link category and a non-absolute URL. An empty
category imports as a heading with nothing under it — visible to students, useless, and the
kind of thing that survives precisely because nothing errors on it.

**One inference remains.** Placing a survey in the content tree needs a
`resource_type_key`, and only `D2L.LE.Quizzing.Quiz` and `D2L.LE.Dropbox.Dropbox` have ever
been observed. `D2L.LE.Survey.Survey` follows the pattern but is a guess; it is marked as
one in `RTK`, and an unknown type now exits with the fix rather than a bare `KeyError`.
Worst case is a dead link in the module — the survey still lands under Course Tools — and
the fallback is to drop `place_in` and name it in bold on the lesson page.
