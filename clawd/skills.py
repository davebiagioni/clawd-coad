from dataclasses import dataclass
from pathlib import Path

import yaml

USER_SKILLS_DIR = Path("~/.clawd/skills").expanduser()


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    path: Path


def _project_skills_dir(jail_root: Path) -> Path:
    return jail_root / ".clawd" / "skills"


def _parse(path: Path) -> Skill | None:
    text = path.read_text()
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    try:
        meta = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return None
    name = meta.get("name")
    if not name:
        return None
    body = text[end + 5 :].lstrip("\n")
    return Skill(
        name=str(name),
        description=str(meta.get("description", "")),
        body=body,
        path=path,
    )


def discover_skills(jail_root: Path) -> dict[str, Skill]:
    """Find all skills available to this session.

    Looks in `~/.clawd/skills/*.md` (user-wide) and `<jail_root>/.clawd/skills/*.md`
    (project-local). Project skills override user skills with the same name.
    """
    found: dict[str, Skill] = {}
    for d in (USER_SKILLS_DIR, _project_skills_dir(jail_root)):
        if not d.exists():
            continue
        for p in sorted(d.glob("*.md")):
            skill = _parse(p)
            if skill:
                found[skill.name] = skill
    return found
