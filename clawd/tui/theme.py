"""Centralized palette and glyphs.

All Rich/prompt_toolkit modules in `clawd.tui` import colors and glyphs from here so
the look-and-feel can be tweaked in one place.
"""

USER_BAR = "▍"
TOOL_GLYPH = "∿"
PROMPT_GLYPH = "›"
DIVIDER = "─"
BRANCH_GLYPH = "⎇"

# Rich color names (portable across terminal palettes).
ACCENT = "cyan"
USER = "blue"
TOOL = "magenta"
SUCCESS = "green"
WARN = "yellow"
ERROR = "red"
DIM = "bright_black"
TEXT = "white"

PROVIDER_COLOR = {
    "openai": "green",
    "anthropic": "magenta",
}
