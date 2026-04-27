# TUI polish — design

**Status:** approved
**Date:** 2026-04-26
**Scope:** `clawd/tui.py` rewrite as a `clawd/tui/` package, plus tests

## Goal

Make the clawd terminal feel delightful to use without busting the under-1k LOC project budget or migrating off Rich.

Three things drive the work:

1. **Always-visible session state.** Today the model/branch/cost/tokens info shows once in the banner, then scrolls away. Users have to run `/cost` to remember what they're paying. A persistent status footer fixes this.
2. **Persistent input history.** Up-arrow at the prompt should recall what you typed yesterday, not just this session.
3. **Readable tool calls.** Today's `→ read_file({'path': 'clawd/tui.py'})` is unreadable for tools whose args contain multi-line content (`write_file`, `bash`). Verb-grammar rendering (`read clawd/tui.py · 251 lines`) makes the transcript scannable.

## Non-goals

Explicitly out of scope:

- Theme switcher (palette is centralized; only one theme ships)
- Mouse support / scroll widgets
- `@filename` path autocomplete
- Spinner / "thinking…" indicator before first streamed token
- Conversation/session list sidebar
- Notification on long turn completion
- Migration to Textual (preserves Rich + adds prompt_toolkit; full Textual stays a forkable side experiment)
- Per-project history (history is global at `~/.config/clawd/history`)
- Context-window usage display (`12.3k / 128k`) — would need a context-limits registry; deferred

## Architecture

Two libraries, naturally serial, no concurrency contention:

```
INPUT phase                        TURN phase
─────────────                      ──────────────
prompt_toolkit owns the screen:    Rich owns the screen:
  • cursor, history, autocomplete    • Live-streaming markdown
  • bottom_toolbar (status footer)   • tool-call rows
  • multi-line edit (alt-enter)      • diff syntax via Syntax widget
returns: prompt string             returns: when agent finishes
```

The toolbar is genuinely pinned at the bottom **only while the prompt is active**. During a streaming response, assistant text scrolls past as today. The moment the agent finishes, the toolbar reappears. This preserves native scrollback (Rich's screen-mode `Live` would not). Same compromise Claude Code itself makes.

A small `SessionLedger` object sits behind the toolbar — accumulates input/output tokens via a LangChain callback, resolves cost via existing `clawd/pricing.py`. The toolbar's render callable reads from the ledger on each redraw.

## Components

### `clawd/tui/theme.py` (~20 LOC)

Centralized color/glyph palette. Tokyo-Night-ish defaults:

- `USER_BAR = "▍"`, `TOOL_GLYPH = "∿"`, `PROMPT_GLYPH = "›"`
- Color names mapped to Rich color tokens: `accent`, `dim`, `success`, `warn`, `error`, `tool`, `user`
- All other modules import constants from here. No inline color literals elsewhere.

### `clawd/tui/ledger.py` (~40 LOC)

```python
@dataclass
class SessionLedger:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    pricing: Pricing | None = None  # cached lookup, fetched once

    def add_usage(self, input_t: int, output_t: int) -> None: ...
    @property
    def total_tokens(self) -> int: ...

class LedgerCallback(BaseCallbackHandler):
    """Reads usage from on_llm_end / on_chat_model_end events."""
    def __init__(self, ledger: SessionLedger): ...
    def on_llm_end(self, response, **kw): ...
```

Pricing is resolved once at session start (async) and cached on the ledger; the callback adds tokens × cached rates without further IO. If pricing isn't registered, cost stays at `0.0` and the toolbar renders `$—` instead of `$0.00`.

`SessionLedger.refresh_pricing()` re-runs the async lookup; the `/cost set` command calls it after registering, so the toolbar starts showing real cost on the next turn without restarting the session.

### `clawd/tui/input.py` (~70 LOC)

Builds and returns a `prompt_toolkit.PromptSession`:

- **History**: `FileHistory("~/.config/clawd/history")`, XDG-friendly path, directory created on first run
- **Completer**: `WordCompleter` over slash command names + exit words, only triggered when line starts with `/`. Meta text is the command's description from the `COMMANDS` dict.
- **Bottom toolbar**: a callable returning formatted text. Reads from the `SessionLedger` and `Settings`. Right-alignment achieved by computing padding from terminal width:
  ```
  [provider-pill] gpt-4.1                    ⎇ main · $0.04 · 12.3k tok
  ```
  Hidden segments: cost hidden if no Langfuse callbacks; tokens shown as `—` before first model call.
- **Key bindings**: emacs defaults (free); `alt-enter` inserts a newline; `enter` submits.
- **Prompt rendering**: `›` glyph in accent color, single space, then editable buffer.

### `clawd/tui/render.py` (~100 LOC)

Owns everything Rich. Two main entry points:

- `replay_history(agent, config)` — reformats the existing replay logic with the new visual style (user bar, tool rows, dividers).
- `run_turn(agent, config, prompt)` — the existing `astream_events` v2 loop, with three improvements:
  1. **Tool-call dispatch.** A small table maps tool names to a `(verb, summarize_args)` pair: `read_file → ("read", lambda a: a["path"])`, `write_file → ("write", lambda a: f"{a['path']} · {len(a['content'].splitlines())} lines")`, `bash → ("shell", lambda a: f"$ {a['cmd']}")`, `web_fetch → ("fetch", lambda a: a["url"])`. Unknown tools fall back to today's `name(args)` form.
  2. **Smart output collapse.** A small `summarize_output(tool_name, output_text)` function:
      - Diff-shaped output → render via Rich `Syntax` with `diff` lexer
      - Shell with exit 0 and short stdout → `✓ <one-line summary>`
      - Long blobs → first 2 lines + `… (N more lines)` in dim
      - Errors / non-zero exits → always rendered in full, red border
  3. **Turn divider** printed after each `run_turn` returns (subtle dim hr).

### `clawd/tui/commands.py` (~60 LOC)

The four existing slash command handlers (`/help`, `/clear`, `/diff`, `/cost`) lifted from `tui.py` with minor styling updates to use `theme.py`. The `COMMANDS` dict is exported from here.

### `clawd/tui/app.py` (~80 LOC)

Banner, main loop, command dispatch, error handling. The connection-error friendly message is preserved. Uses `input.py` to build the prompt session, `render.py` for output, `commands.py` for slash handling, `ledger.py` for token tracking.

### `clawd/tui/__init__.py` (~5 LOC)

Re-exports `run` so `cli.py` stays working: `from .tui import run`.

## File-by-file LOC estimates

```
tui/__init__.py     ~5
tui/app.py          ~80
tui/input.py        ~70
tui/render.py       ~100
tui/ledger.py       ~40
tui/commands.py     ~60
tui/theme.py        ~20
                  ─────
                  ~375  (vs. 250 today: net +125 LOC)
```

Project total: 757 → ~882 LOC. Headroom remaining: ~118 LOC under the 1k ceiling.

**Budget-tightening fallback** if any module overshoots: simplify `summarize_output` to "always truncate at 400 chars + diff-via-Syntax special case." Cost: ~30 LOC. That's the first piece to cut.

## Visual polish — five items

1. **Verb-grammar tool rows** — `∿ read clawd/tui.py · 251 lines`
2. **Smart output collapse** — diffs syntax-highlighted; shell-success summarized; errors always full; long output truncated with line count
3. **User message bar** — `▍ ` in accent color marking the start of each user turn
4. **Subtle turn dividers** — dim `─` line between completed turns
5. **Centralized theme** — one palette dict, easy to swap

## Input layer details

- History path: `~/.config/clawd/history` (XDG-style; `XDG_CONFIG_HOME` honored if set)
- History scope: global (a single recipe like "run the tests" is useful across projects; per-project would add complexity for marginal benefit)
- Slash autocomplete: triggered by leading `/`; tab to accept, escape to dismiss
- Multi-line: alt-enter inserts newline; enter submits; explicit (no quote-balancing magic)
- Key bindings: emacs defaults; ctrl-r reverse search; ctrl-c at prompt clears line; ctrl-c during turn interrupts; ctrl-d on empty exits

## Status footer (style C — airline split)

```
┌──────────────────────────────────────────────────────────────┐
│  [openai] gpt-4.1                    ⎇ main · $0.04 · 12.3k  │
└──────────────────────────────────────────────────────────────┘
```

- Left: provider pill + model name (session-stable identity)
- Right: branch + cost + cumulative token count (turn-volatile state)
- Repaints every 0.5s while at the prompt
- Cost hidden if no Langfuse callbacks; `$—` if pricing not registered; `—` for tokens before first model call

## Testing

### Unit tests

**`tests/test_ledger.py`** (~50 LOC):
- `add_usage` accumulates correctly across multiple calls
- Cost computed from cached pricing
- `cost_usd` stays 0.0 when pricing is None
- Pricing lookup happens once (mock the async call, assert one invocation)

**`tests/test_render.py`** (~80 LOC):
- Per-tool verb-grammar formatting: known tools produce expected strings; unknown tools fall back to `name(args)` form
- Output collapser: short output passes through; long output truncates with line count; diff-shaped output is detected; non-zero shell stays full and red

### Smoke checklist

Manual tests after implementation:

- [ ] `clawd` opens; toolbar visible at the bottom of the prompt
- [ ] Type prompt → toolbar updates with cost/tokens after first turn
- [ ] Up-arrow recalls last prompt; works across `clawd` restarts
- [ ] `/d<tab>` completes to `/diff`
- [ ] Ctrl-r searches history backward
- [ ] Alt-enter inserts a newline; line continues with no submission
- [ ] Ctrl-c during a turn cleanly returns to a fresh prompt
- [ ] Ctrl-d on empty line exits
- [ ] Banner still prints once at startup; replay still shows prior turns with new styling
- [ ] Tool calls render in verb-grammar form for `read_file`, `write_file`, `bash`, `web_fetch`
- [ ] Diff output renders as syntax (try `/diff` after editing a file)
- [ ] Connection-error case still shows the friendly message (try with bad `BASE_URL`)

### What's not tested

The full prompt_toolkit ↔ Rich integration (handoff at prompt close, toolbar redraw, escape-code handling) is not unit-tested. Mocking both libraries deeply enough produces tests that mostly assert the code we wrote. Manual smoke test only.

## Risks & mitigations

- **prompt_toolkit + Rich escape-code interleave bugs.** Mitigation: keep them strictly serial (no Rich writes while a `prompt_async` is open). Smoke test the handoff explicitly.
- **LOC budget creep.** Mitigation: the `summarize_output` simplification noted above is the first cut. If still over, drop the `commands.py` split and inline the four handlers in `app.py` (~−15 LOC of file overhead).
- **Pricing API unavailable at session start.** Mitigation: try/except around the async lookup; ledger silently runs without cost data; toolbar renders `$—`.
- **Bottom toolbar terminal-width edge cases** (very narrow terminals, resize during prompt). Mitigation: prompt_toolkit handles resize natively; on terminals narrower than ~60 cols, drop the right segment to a single line.

## Implementation order

1. **theme.py** — palette constants. Standalone, no deps.
2. **ledger.py** + tests — pure logic, easy to verify.
3. **render.py** + tests — pure formatting logic, easy to verify.
4. **commands.py** — straight lift from current tui.py with theme imports.
5. **input.py** — prompt_toolkit session, completer, bottom_toolbar.
6. **app.py** — main loop, banner, dispatch, error handling — wires everything together.
7. **`__init__.py`** + delete old `tui.py` + update any imports.
8. **Smoke test** — go through the checklist above.

Each step ends with `uv run pytest` passing.
