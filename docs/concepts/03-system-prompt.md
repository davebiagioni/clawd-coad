# Chapter 3: The system prompt

> **Code for this chapter:** `clawd/prompt.py` (54 lines),
> `clawd/skills.py` (58 lines), `clawd/tools/skills.py` (30 lines)

The system prompt is the model's job description. Every turn of the agent
loop, the model re-reads it (whether it likes it or not — the prompt sits
at the top of every request). It is the cheapest, highest-leverage knob in
the whole system: a one-line change can make the difference between a
model that searches before editing and one that hallucinates wildly.

This chapter is short because `clawd`'s prompt is short — 37 lines for
the file, ~25 lines of actual prompt text. Real production agents
(Claude Code, Cursor) ship prompts in the thousands of words. We'll talk
about why, and where you'd add length for your own use.

## `clawd/prompt.py`

```python
from pathlib import Path

BASE = """\
You are clawd, an open-source AI coding assistant. You help with software \
engineering tasks: reading code, making edits, running shell commands, \
searching for things, and answering questions.

# Working environment
You are operating inside a git worktree at {jail_root} on branch {branch}. \
All file operations and shell commands are jailed to this directory. The user \
can review your changes with `git -C {jail_root} diff` and merge with \
`git merge {branch}` from the main repo.

# Tool usage
- Prefer tools over guessing. If you need to know what's in a file, read it.
- Use `read_file` before `edit_file` so you have the exact text to match.
- `edit_file` requires the `old` string to appear exactly once — include enough
  surrounding context to make the match unique.
- Use `glob_files` to discover files by pattern; `grep` to search content.
- `bash` runs with the worktree as its working directory.

# Output style
- Be concise. Prefer doing over explaining.
- When referencing code, use `file_path:line_number`.
- No apologies, no disclaimers, no emoji unless the user uses them first.
- If a task is ambiguous, ask one short clarifying question rather than guessing.
"""


def build_system_prompt(jail_root: Path, branch: str) -> str:
    prompt = BASE.format(jail_root=jail_root, branch=branch)

    claude_md = jail_root / "CLAUDE.md"
    if claude_md.exists():
        prompt += f"\n# Project context (from CLAUDE.md)\n{claude_md.read_text()}\n"

    return prompt
```

## Anatomy of a coding-agent prompt

Most prompts in this category have four sections, in roughly this order:

1. **Identity.** "You are X. You help with Y." Anchors the model to a
   role. Skipping this is fine for frontier models but visibly degrades
   smaller open-source ones.
2. **Working environment.** What world is the model in? Where do its
   tools operate? What are the boundaries? `clawd`'s prompt names the
   worktree path and branch explicitly so the model can mention them when
   answering.
3. **Tool usage rules.** Per-tool gotchas the model can't infer from the
   tool's docstring. Example: "use `read_file` before `edit_file`" exists
   because models love to guess at file contents and then fail
   `edit_file`'s exact-match requirement.
4. **Output style.** Tone, format, terseness, when to ask vs guess.
   Underrated — saves enormous numbers of tokens over a long session.

You can add: safety rules, persona, refusal patterns, examples of good
turns. `clawd` doesn't, on the principle that less prompt is easier to
debug.

## Runtime interpolation

Two values get filled in at session start:

- `{jail_root}` — the absolute path to the worktree. The model uses this
  to give the user concrete `git` commands they can run themselves.
- `{branch}` — the throwaway branch name (`clawd/<thread_id>`). Same
  reason.

Telling the model where it lives is cheap and helps it produce
grounded answers ("I edited `main.py`" → "I edited
`/Users/me/.clawd/worktrees/default/main.py`"). Without it the model
either hand-waves or hallucinates a path.

## CLAUDE.md merge

```python
claude_md = jail_root / "CLAUDE.md"
if claude_md.exists():
    prompt += f"\n# Project context (from CLAUDE.md)\n{claude_md.read_text()}\n"
```

If the project has a `CLAUDE.md` file at its root, its contents get
appended to the prompt. This is a deliberate borrow from Claude Code's
convention — your project tells the agent its conventions, build
commands, gotchas, etc., and that file travels with the repo.

A meta-note: the filename is provider-agnostic by design here even though
the *name* is Anthropic-flavored. Two reasons we kept the name:

- It's already an emerging convention; users dropping `clawd` into a
  project that already has a `CLAUDE.md` get the right behavior for free.
- Renaming it (say to `AGENTS.md`) would split the world. Aider uses
  `CONVENTIONS.md`. There's no winning name yet.

A reasonable variant: support multiple filenames with a precedence order
(`AGENTS.md` → `CLAUDE.md` → `CONVENTIONS.md`). Two extra lines of code.

## Skills: on-demand instruction bundles

`CLAUDE.md` solves "things every turn should know about this project."
Skills solve a different problem: "things only *some* turns need to
know, and they're long."

A skill is a markdown file with yaml frontmatter:

```markdown
---
name: tdd
description: Use when adding a new feature, before writing implementation code.
---
# Test-Driven Development

Write the failing test first. Run it. Watch it fail. Then implement
just enough to make it pass. ...
```

At session start, `discover_skills()` walks two directories:

- `~/.clawd/skills/*.md` — skills you carry across projects
- `<project>/.clawd/skills/*.md` — skills tied to this project

`<project>` is the launch-time project root: the git toplevel of the
directory you ran `clawd` from (falling back to that directory itself
if you're not inside a git repo). Crucially, this is **not** the
throwaway worktree the agent edits in — a skill committed to your
repo *would* also appear in the worktree, but the common case is
"drop a file and use it without committing," and that only works
when we look at the launch dir.

Project skills win when names collide. Each file's frontmatter
contributes a one-line entry to the system prompt:

```
# Skills available
Call `load_skill(name)` when one applies:
- `tdd`: Use when adding a new feature, before writing implementation code.
- `release-checklist`: Use before tagging a release.
```

The bodies are *not* injected. The model sees only the names and
descriptions and decides when to call `load_skill(name)`, which is a
tool that returns the full body.

This is a deliberate split:

- **Descriptions go in the prompt.** They have to, otherwise the model
  doesn't know what's available. They're short by design — one
  sentence, focused on *when* to use the skill.
- **Bodies stay on disk until needed.** A 1000-word "how to do TDD"
  doc would burn 1.5k tokens on every turn if it lived in the prompt.
  Loading it on demand pays the cost only when relevant.

This is the same pattern Claude Code uses for its skills system; we
copied the shape because it works. The format is a strict subset (no
nested directories, no globbed file references, no platform-specific
tool name remapping) — enough for the common case, not enough to
re-implement the full spec.

When *not* to use skills:

- "Always do X" — that's a `CLAUDE.md` line, not a skill.
- "Reference docs the model can grep" — that's a file in the repo, not
  a skill.
- "Override default behavior" — better as a `CLAWD_*` env var; skills
  are advice, not configuration.

The recipe for writing one is at
[how-to/write-a-skill](../how-to/write-a-skill.md).

## Why so short?

Frontier-model coding agents ship prompts that run thousands of words.
A back-of-envelope reason for the length:

- Detailed safety policy
- Long lists of tools, each with quirks
- Subagent coordination rules
- Multi-step workflows (planning, editing, validating)
- Refusal patterns and persona
- Example turns

`clawd` ships with seven tools, one persona, no subagents, no examples.
Every line of prompt is a line you have to debug when the model behaves
unexpectedly. Start short, lengthen on evidence.

A useful discipline: when you find yourself wanting to add a rule to the
prompt, first try changing the *tool* (better docstring, better error
message, removed footgun). Tools are constraints the model cannot
ignore; prompts are suggestions it might.

## Token cost

The whole prompt, including `CLAUDE.md`, is ~300–500 tokens for `clawd`
in its current state. With prompt caching (Anthropic / OpenAI both
support it), the prompt portion is essentially free across turns within
a session. Without caching, you pay for it on every turn — for a 50-turn
session, that's 15–25k tokens just on prompt.

`clawd` doesn't currently enable caching; doing so would be a small
change in `llm.py` (add `cache_control` markers for Anthropic, or rely
on automatic OpenAI caching).

## What's missing

- **Tool examples in the prompt.** Sometimes models struggle with a
  tool's signature; a one-line example in the system prompt fixes it
  faster than retraining.
- **Dynamic context.** Some agents inject the current `git status`, the
  open file in the editor, recent shell history. Tradeoff: more context
  → better grounding → more tokens → slower turns.
- **Persona.** Some users want their agent to be terse and dry; some
  want it to explain reasoning. Easy to add a `CLAWD_PERSONA` config.

## Exercise

Run a non-trivial task ("refactor `agent.py` to remove the dataclass")
twice — once with the prompt as-is, once with the entire `# Tool usage`
section deleted. Observe the difference in tool-call patterns, error
recovery, and turn count.

This is the cheapest experiment you can run in this whole tutorial, and
it's the most informative.
