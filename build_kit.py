#!/usr/bin/env python3
"""Build rollforward-kit.zip (the Roll-Forward folder faculty download) and, beside it,
d2l-rollforward-skill.zip (the skill alone) and d2l-rollforward-plugin.zip (the same skill as a plugin).

The skill's references/ are COPIED from standards/ at build time, so the spec has one source.
Outputs are not committed.
"""
import shutil, zipfile
from pathlib import Path
here = Path(__file__).resolve().parent
std = here / "standards"
skill = here / "skill" / "d2l-rollforward"
REFS = {"d2l-settings-catalog.md": "settings-catalog.md", "d2l-package-format.md": "d2l-package-format.md",
        "d2l-updating-a-live-shell.md": "d2l-updating-a-live-shell.md",
        "d2l-standards-interview.md": "standards-interview.md"}
(skill / "references").mkdir(exist_ok=True)   # git-ignored, so absent in a fresh clone
for src, dst in REFS.items():
    shutil.copyfile(std / src, skill / "references" / dst)

def files(root):
    return [p for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts]

with zipfile.ZipFile(here / "d2l-rollforward-skill.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for p in files(skill):
        z.write(p, "d2l-rollforward/" + p.relative_to(skill).as_posix())
with zipfile.ZipFile(here / "rollforward-kit.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for p in files(here / "kit"):
        z.write(p, "Roll-Forward/" + p.relative_to(here / "kit").as_posix())
    for p in files(skill):   # Codex reads repo skills from .agents/skills, Claude Code from .claude/skills
        z.write(p, "Roll-Forward/.agents/skills/d2l-rollforward/" + p.relative_to(skill).as_posix())
        z.write(p, "Roll-Forward/.claude/skills/d2l-rollforward/" + p.relative_to(skill).as_posix())
# The same kit without the Roll-Forward wrapper, for unzipping straight into a folder that is already open.
with zipfile.ZipFile(here / "rollforward-kit-contents.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for p in files(here / "kit"):
        z.write(p, p.relative_to(here / "kit").as_posix())
    for p in files(skill):
        z.write(p, ".agents/skills/d2l-rollforward/" + p.relative_to(skill).as_posix())
        z.write(p, ".claude/skills/d2l-rollforward/" + p.relative_to(skill).as_posix())
import json
PLUGIN = {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
          "name": "d2l-rollforward", "version": "0.1.0", "license": "Apache-2.0",
          "description": "Roll a Brightspace (D2L) course export forward to a new term, audit quiz settings against your class standards, and look up what D2L settings do.",
          "author": {"name": "Sand Point Studios"},
          "repository": "https://github.com/Sand-Point-Studios-LLC/agoge-d2l-faculty-skill"}
with zipfile.ZipFile(here / "d2l-rollforward-plugin.zip", "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("d2l-rollforward-plugin/plugin.json", json.dumps(PLUGIN, indent=2) + "\n")
    for p in files(skill):   # the portable layout discovers skills/<name>/SKILL.md from the root
        z.write(p, "d2l-rollforward-plugin/skills/d2l-rollforward/" + p.relative_to(skill).as_posix())
print("wrote rollforward-kit.zip, rollforward-kit-contents.zip, d2l-rollforward-skill.zip and d2l-rollforward-plugin.zip")
