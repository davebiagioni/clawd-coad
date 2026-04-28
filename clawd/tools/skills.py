from pathlib import Path

from langchain_core.tools import BaseTool, tool

from ..skills import discover_skills


def make_skills_tool(jail_root: Path) -> BaseTool | None:
    """Build the `load_skill` tool, or return None if no skills are installed.

    The session prompt lists available skills with their descriptions; the model
    calls `load_skill(name)` to pull in the full instruction body on demand.
    """
    if not discover_skills(jail_root):
        return None

    @tool
    def load_skill(name: str) -> str:
        """Load the full content of a skill by name.

        Skills are on-demand instruction bundles for specialized tasks. The system
        prompt lists which ones are available and when each applies; pick by name.
        """
        skills = discover_skills(jail_root)
        if name not in skills:
            available = ", ".join(sorted(skills)) or "none"
            return f"unknown skill {name!r}; available: {available}"
        return skills[name].body

    return load_skill
