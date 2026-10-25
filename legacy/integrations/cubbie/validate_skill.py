"""Offline validator for this instruction-only Skill's strict YAML subset.

This deliberately accepts only name: plain-slug and description: JSON-quoted
string, both valid YAML scalars. It is not a general YAML or Cubbie runtime parser.
"""
import argparse
import json
import re
from pathlib import Path


def validate_skill(folder):
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError("Skill folder is missing")
    entries = list(folder.rglob("*"))
    if any(p.is_symlink() for p in entries):
        raise ValueError("Skill must not contain symbolic links")
    files = [p for p in entries if p.is_file()]
    if len(files) > 300 or sum(p.stat().st_size for p in files) > 5 * 1024 * 1024:
        raise ValueError("Skill exceeds guide package limits")
    if any(p.stat().st_size > 1024 * 1024 for p in files):
        raise ValueError("Skill file exceeds guide limit")
    if {p.relative_to(folder).as_posix() for p in files} != {"SKILL.md"}:
        raise ValueError("Native-only package must contain only SKILL.md; review scripts/manifest permissions before expanding")
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    match = re.fullmatch(r'---\nname: ([a-z0-9]+(?:-[a-z0-9]+)*)\ndescription: ("[^\n]+")\n---\n(.+)', text, re.S)
    if not match:
        raise ValueError("Expected name and quoted description YAML frontmatter followed by instructions")
    name, raw_description, body = match.groups()
    description = json.loads(raw_description)
    if name != folder.name or len(name) > 64 or not isinstance(description, str) or not description.strip():
        raise ValueError("Invalid Skill name or description")
    if not body.strip() or re.search(r'\b(TODO|TBD|FIXME)\b', body):
        raise ValueError("Missing instructions or unfinished placeholders")
    # Installed package must not refer to the repository, local adapters or helpers.
    if re.search(r'\.\./|[A-Za-z]:[\\/]|(?:integrations|tests|docs)/|\bscripts/|\bpython(?:3)?\s|\bpip install\b', body):
        raise ValueError("Skill instructions contain an external file or executable dependency")
    for target in re.findall(r'\]\(([^)]+)\)', body):
        if not target.startswith("https://"):
            path = (folder / target.split("#")[0]).resolve()
            if folder not in path.parents or not path.is_file():
                raise ValueError("Broken or out-of-package reference")
    return {"name": name, "files": len(files), "bytes": sum(p.stat().st_size for p in files),
            "scripts": False, "manifest": False, "secrets": False,
            "runtime": "UNVERIFIED", "validation": "offline package only"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate_skill(args.folder), indent=2))


if __name__ == "__main__":
    main()
