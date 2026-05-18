# dirty-claude

A Claude Code skill that finds and cleans the bloat no other tool catches.

```
/dirty-claude
```

## What it does

Walks you through a one-screen audit of your Claude Code install, surfaces findings with confidence ratings, and lets you greenlight each cleanup. Workflow-preserving by default — never silently changes behavior.

Real findings from one session:
- 8 dead MCPs from a plugin you don't use anymore
- 3 hook matchers pointing at MCPs that don't exist
- An orphan `launchd` agent firing daily, refreshing tokens for a tool uninstalled weeks ago
- 7 ghost entries in `mcp-needs-auth-cache.json`
- MEMORY.md at 384 lines (system truncates past ~200 — half your memory was invisible)
- 47 user skills, 5 actually used in 30 days
- A Windows path (`C:\Users\...`) inside `known_marketplaces.json` from a cross-platform write
- Settings.json carrying 146 lines of permission entries for MCPs gone for weeks

Existing hygiene tools (unclog, mcpick, `/fewer-permission-prompts`) cover token cost and tool management. dirty-claude covers everything else: hook staleness, ghost caches, orphan launchd, MEMORY truncation, project-scoped drift, cross-platform path corruption, plugin schema bugs.

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

Open Claude Code, type `/dirty-claude` (or any trigger phrase like "audit my claude code setup"). The skill takes over, runs the inventory, presents findings, asks for greenlight per finding.

By default it skips disk-storage cleanup. Pass `--storage` if you want size warnings on `~/.claude/file-history/`, `~/Library/Caches/claude-cli-nodejs/`, etc.

## What it does NOT do

- **Token cost auditing** — use [unclog](https://github.com/thomaschill/unclog) (`uv tool install unclog`). dirty-claude tells you to run it.
- **Allowlist generation** — use Anthropic's official `/fewer-permission-prompts` skill.
- **MCP enable/disable UI** — use [mcpick](https://github.com/spences10/mcpick).
- **Behavioral changes** unless you explicitly approve.
- **Hard deletes** unless you explicitly approve. Default is archive (`mv` to `*-archive-YYYY-MM-DD/`).

## Design principles

- Read-only by default
- Per-finding greenlight
- Auto-backup before any edit
- Confidence ratings on every recommendation
- Workflow-preserving: don't change behavior unless told
- Defer to better tools where they exist

## License

MIT. See `LICENSE`.

## Credits

Built from a real Claude Code cleanup session. The gap analysis stands on the shoulders of [unclog](https://github.com/thomaschill/unclog), [mcpick](https://github.com/spences10/mcpick), Anthropic's `/fewer-permission-prompts`, and write-ups by [Sshh](https://blog.sshh.io/p/how-i-use-every-claude-code-feature), [Geoffrey Huntley](https://ghuntley.com/loop/), [alexop.dev](https://alexop.dev/posts/stop-bloating-your-claude-md-progressive-disclosure-ai-coding-tools/), and the [MindStudio context-rot research](https://www.mindstudio.ai/blog/what-is-context-rot-claude-code).
