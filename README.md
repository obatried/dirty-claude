# dirty-claude

A Claude Code skill that audits and cleans bloat that other hygiene tools tend to miss. It includes a bundled read-only inventory script so the first pass is grounded in local Claude Code state instead of vibes.

```
/dirty-claude
```

## What it does

Walks you through a one-screen audit of your Claude Code install, surfaces findings with confidence ratings, and lets you greenlight each cleanup. Workflow-preserving by default — never silently changes behavior.

Sample findings from one real cleanup session (your install will differ):
- 8 dead MCPs left over from an uninstalled plugin
- 3 hook matchers pointing at MCPs that no longer existed
- An orphan `launchd` agent firing daily, refreshing tokens for a tool uninstalled weeks earlier
- 7 ghost entries in `mcp-needs-auth-cache.json`
- A 384-line MEMORY.md (observed load truncation around the 200-line mark in that session)
- 47 user skills with only 5 invoked in the prior 30 days
- A Windows path (`C:\Users\...`) inside `known_marketplaces.json` from a cross-platform write
- `settings.json` carrying 146 lines of permission entries for MCPs gone for weeks

Existing hygiene tools cover token cost ([unclog](https://github.com/thomaschill/unclog)), MCP/plugin enable-disable ([mcpick](https://github.com/spences10/mcpick)), and permission allowlist scanning (Anthropic's `/fewer-permission-prompts`). dirty-claude focuses on the categories those tools don't: hook matcher staleness, ghost caches, orphan launchd jobs, MEMORY.md size/truncation, project-scoped `~/.claude.json` drift, cross-platform path corruption, plugin schema bugs.

## Install

Drop the skill into your Claude Code skills directory:

```bash
git clone https://github.com/obatried/dirty-claude.git ~/.claude/skills/dirty-claude
```

Verify Claude Code sees it:

```
/dirty-claude
```

## Usage

Open Claude Code, type `/dirty-claude` (or any trigger phrase like "audit my claude code setup"). The skill runs its bundled read-only inventory, presents findings, and stops for greenlight before any cleanup.

By default it skips disk-storage cleanup. Pass `--storage` if you want size warnings on `~/.claude/file-history/`, `~/Library/Caches/claude-cli-nodejs/`, etc.

You can also run the inventory directly:

```bash
python3 ~/.claude/skills/dirty-claude/scripts/dirty_claude_inventory.py
python3 ~/.claude/skills/dirty-claude/scripts/dirty_claude_inventory.py --storage
```

## What it does NOT do

- **Token cost auditing** — use [unclog](https://github.com/thomaschill/unclog) (`uv tool install unclog`). dirty-claude tells you to run it.
- **Allowlist generation** — use Anthropic's official `/fewer-permission-prompts` skill.
- **MCP enable/disable UI** — use [mcpick](https://github.com/spences10/mcpick).
- **Behavioral changes** unless you explicitly approve.
- **Hard deletes** unless you explicitly approve. Default is archive (`mv` to `*-archive-YYYY-MM-DD/`).

## Design principles

- Read-only by default
- Per-finding greenlight
- Bundled read-only inventory before recommendations
- Auto-backup before any edit
- Confidence ratings on every recommendation
- Workflow-preserving: don't change behavior unless told
- Defer to better tools where they exist

## License

MIT. See `LICENSE`.

## Credits

Built from a real Claude Code cleanup session. The gap analysis stands on the shoulders of [unclog](https://github.com/thomaschill/unclog), [mcpick](https://github.com/spences10/mcpick), Anthropic's `/fewer-permission-prompts`, and write-ups by [Sshh](https://blog.sshh.io/p/how-i-use-every-claude-code-feature), [Geoffrey Huntley](https://ghuntley.com/loop/), [alexop.dev](https://alexop.dev/posts/stop-bloating-your-claude-md-progressive-disclosure-ai-coding-tools/), and the [MindStudio context-rot research](https://www.mindstudio.ai/blog/what-is-context-rot-claude-code).
