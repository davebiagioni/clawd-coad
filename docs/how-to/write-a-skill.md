# How to write a skill

Skills are short markdown files that give the agent task-specific
instructions on demand. The agent sees the skill's name and description
in its system prompt; it loads the body via `load_skill(name)` only
when one applies.

For the design behind skills, see
[chapter 3: the system prompt](../concepts/03-system-prompt.md).

## Where skills live

```
~/.clawd/skills/*.md          # user-wide, every project
<project>/.clawd/skills/*.md  # this project only (project wins on conflict)
```

`<project>` is the directory you launched `clawd` from (or the git
toplevel if you launched from a subdir). It is **not** the throwaway
worktree the agent edits in — drop your file in the *real* project
root and it'll be picked up next session, no commit required.

`*.md` only — no nested directories, no other extensions. Files
without valid frontmatter are silently skipped.

## Steps

### 1. Pick a name and a "when to use" line

Name is one short kebab-case identifier (`tdd`, `release-checklist`,
`debug-flaky-tests`). The description is one sentence the model will
see in its prompt — focus on **when** the skill applies, not **what**
it contains.

Bad: `description: Notes on TDD.`
Good: `description: Use when adding a feature, before writing implementation code.`

### 2. Write the file

```markdown
---
name: release-checklist
description: Use before tagging a release.
---

# Release checklist

1. Run `uv run pytest` and confirm it's green.
2. Bump the version in `pyproject.toml`.
3. Update `CHANGELOG.md` with a section for the new version.
4. Commit on `main`, tag `vX.Y.Z`, push tags.
5. Open the GitHub release page and paste the changelog entries.
```

The body can be as long as you want — it only enters context when the
model calls `load_skill("release-checklist")`.

### 3. Drop it in

```bash
mkdir -p .clawd/skills              # project-local
cp release-checklist.md .clawd/skills/
```

…or for a skill you want everywhere:

```bash
mkdir -p ~/.clawd/skills
cp tdd.md ~/.clawd/skills/
```

### 4. Restart `clawd`

Skills are discovered at session start. Restart the TUI (`/clear` is
not enough) and you should see your skill listed under
`# Skills available` in the system prompt — verify with `/dump` or by
asking the model what skills it has.

### 5. Try it

Ask the agent to do a task that matches the description. It should
either call `load_skill("...")` itself, or you can prompt explicitly:

```
> use the release-checklist skill to walk me through cutting v0.1
```

## Common issues

- **Skill not picked up.** Check that the file starts with `---\n`,
  that frontmatter has a `name:` field, and that the file is `*.md`.
  Files without valid frontmatter are silently skipped.
- **Model never calls `load_skill` on its own.** The description is
  the only signal the model gets. Rewrite it to start with "Use
  when…" and name a concrete trigger.
- **Skill body is too long and the model misses key points.** Same
  rules as any prompt: lead with the most important step, use short
  bullets, no walls of text.
- **Two skills with the same name.** Project-local wins. Rename one
  if both should be available.

## Related

- [Chapter 3: the system prompt](../concepts/03-system-prompt.md) —
  how skills fit in alongside `CLAUDE.md`.
- [How to add a new tool](add-a-tool.md) — for capabilities, not
  instruction bundles.
