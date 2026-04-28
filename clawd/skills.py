import subprocess
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


def _project_root() -> Path:
    """The launch-time project root: git toplevel of cwd, falling back to cwd.

    Skills are tied to the project the user launched clawd from, NOT to the
    throwaway worktree the agent edits in. A project skill committed to the
    repo would also be visible inside the worktree, but the common case is
    "drop a file in `.clawd/skills/` and use it" — which only works if we
    look at the launch directory.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (FileNotFoundError, OSError):
        pass
    return Path.cwd()


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


def discover_skills() -> dict[str, Skill]:
    """Find all skills available to this session.

    Looks in `~/.clawd/skills/*.md` (user-wide) and `<project>/.clawd/skills/*.md`
    where `<project>` is the launch-time project root (git toplevel of cwd, or
    cwd itself if not in a repo). Project skills override user skills with the
    same name.
    """
    found: dict[str, Skill] = {}
    project_dir = _project_root() / ".clawd" / "skills"
    for d in (USER_SKILLS_DIR, project_dir):
        if not d.exists():
            continue
        for p in sorted(d.glob("*.md")):
            skill = _parse(p)
            if skill:
                found[skill.name] = skill
    return found
