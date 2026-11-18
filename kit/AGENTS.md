# Course roll-forward

This folder rolls a D2L course forward to a new term. The `d2l-rollforward` skill in
`.agents/skills/` (the same copy is in `.claude/skills/` for Claude Code) holds the full instructions, the commands and the D2L reference material.
Use it for anything about the export, its dates, or D2L settings. Plain English, answer first.
Never edit `put-export-here/`. Stop if the export holds student information.
Slides use the .pptx named under `pptx_template` in `class-standards.json`, a file in `templates/`. If none is set or the folder is empty, say so and offer HTML or a content draft.
The faculty member can swap it any time; never edit the template itself.
