---
name: dirty-claude
description: |
  Audit and clean up a Claude Code installation specifically: MCP servers, MEMORY.md, settings.json, hooks, skills, agents, plugins, ghost caches, orphan launchd jobs. Read-only by default with per-finding greenlight. Use only when user mentions Claude Code internals such as MCP, hooks, plugins, MEMORY, settings.json, ~/.claude, "dirty claude", "/dirty-claude", "audit my claude code setup", "cc hygiene", "clean up my .claude directory", "audit claude code hooks", or "find orphan launchd for claude". Do not trigger on generic codebase cleanup.
allowed-tools:
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/dirty_claude_inventory.py *)
---

# /dirty-claude

Walk a user through a comprehensive Claude Code installation cleanup. **Read-only audit by default**, with per-finding greenlight before any change. Workflow-preserving — never silently changes behavior.

Born from one real cleanup session that surfaced dead MCPs, broken hook matchers pointing at uninstalled tools, an orphan launchd job, ghost cache entries, a MEMORY.md large enough to truncate on load (observed at ~200 lines in that session), a Windows path inside `known_marketplaces.json` from a cross-platform write, and a long tail of unused skills/commands. The set of categories below was distilled from that session and from the gaps identified in existing tools.

## Where this fits in the landscape

| Tool | What it does | Where dirty-claude defers |
|---|---|---|
| [`unclog`](https://github.com/thomaschill/unclog) (MIT, Thomas Chill) | Skill/command/MCP/agent token cost + 30-day invocation walk from session JSONLs. Interactive picker. | **dirty-claude defers to unclog for token-cost inventory.** Recommend `uv tool install unclog && unclog` for that piece. |
| [`/fewer-permission-prompts`](https://code.claude.com/docs/en/commands) (Anthropic official, ships with Claude Code) | Scans transcripts to suggest allowlist patterns | **dirty-claude defers** — run it before this skill |
| [`mcpick`](https://github.com/spences10/mcpick) (MIT, Scott Spence) | TUI to enable/disable MCPs + plugins, cache pruning | Complementary — use mcpick for enable/disable; dirty-claude for audit |

dirty-claude focuses on categories the above tools don't fully cover: hook matcher staleness, MEMORY.md size/load truncation, ghost caches, orphan launchd agents, project-scoped `~/.claude.json` drift, cross-platform marketplace path corruption from Windows↔macOS writes, and workflow-preserving restructure patterns.

## Phases

### Phase 1 — Inventory (read-only, fast)

Run the bundled read-only inventory first:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/dirty_claude_inventory.py
```

If the user passed `--storage`, include that flag:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/dirty_claude_inventory.py --storage
```

The script only reads local Claude Code state and prints Markdown. If it fails, report the error and continue manually with read-only commands.

Counts and sizes — no edits:
- MCP servers: working / needs-auth / failed-to-connect (via `claude mcp list`)
- `~/.claude.json`: file size, count of project-scoped entries
- `~/.claude/skills/`, `commands/`, `agents/`, `hooks/`: file counts
- Plugins: enabled / failed-to-load / marketplaces registered
- MEMORY.md: line count + truncation risk (system truncates past ~200 lines)
- `~/.claude/state/`, `~/.claude/projects/`, `file-history/`, `plugins/` sizes
- `~/Library/Caches/claude-cli-nodejs/` size (not covered by `cleanupPeriodDays`)

Output a one-screen summary table.

### Phase 2 — Audit by category

#### A. MCP health
- **Failed-to-connect MCPs.** Likely stale URL or vendor renamed (e.g., Mapbox now rejects OAuth client names containing "mapbox" — re-register with a brand-free alias).
- **"Needs auth" MCPs.** Separate intentional (e.g., paid data vendor not subscribed) from drift.
- **Plugin-shipped MCPs.** If user uninstalled the plugin but `~/.claude.json` still references its MCPs, surface for cleanup.
- **Project-scoped MCP drift.** `~/.claude.json` `projects[<path>].mcpServers` often retains MCPs after global cleanup. Walk each project.
- **Redundant MCPs.** When two installed MCPs cover the same surface (e.g., `gdrive` reference MCP + `google-multi` covering Drive across multiple accounts), flag the narrower one for removal.
- **`settings.json` permission allowlist drift.** Scan `permissions.allow` and `permissions.ask` for entries matching `mcp__<name>__*` where `<name>` is not in the current installed-MCP list. Common after MCP renames or plugin uninstalls — leaves dozens or hundreds of dead permission entries. Propose removal; preserve any wildcard or non-MCP entries.

#### B. Hook matcher staleness  *(unique to dirty-claude)*
For each hook in `~/.claude/settings.json`, check matcher regex against currently-installed MCPs. Flag matchers referencing tools that don't exist. Common pattern: MCP gets renamed/replaced (e.g., `workspace-mcp` → `google-multi`), hook matchers stay tied to old names, hooks silently never fire, user thinks auto-approval is broken.

Propose matcher patches.

#### C. Ghost caches  *(unique)*
- `~/.claude/mcp-needs-auth-cache.json` — entries for uninstalled plugin MCPs survive uninstall. Rebuild without ghosts (preserve legit "needs auth" entries).
- `~/.claude/hooks/*.bak` and `*.disabled` — stale snapshots referenced from configs that may not actually fire.
- Stale `settings.json.bak-*` files (keep latest, archive rest).

#### D. Orphan launchd agents  *(unique, macOS-specific)*
Walk `~/Library/LaunchAgents/com.*`. For each, check what scripts/MCPs it references. Flag agents that:
- Refresh tokens for uninstalled MCPs
- Run scripts that no longer exist
- Fire daily and silently fail

#### E. MEMORY.md size + load truncation  *(unique)*
- Large MEMORY.md files can hit a load-truncation threshold observed around line 200 in tested sessions (verify against your version of Claude Code before relying on the exact cutoff). Flag files past 200 lines for review.
- Propose project + topic conditional-load restructure:
  ```
  memory/
  ├── MEMORY.md                       (lean: rules + identity + pointers, <150 lines)
  ├── projects/<name>.md              (load on project mention)
  └── topics/<name>.md                (load on task type — voice, browser, payments, etc.)
  ```
- Audit `@-import` chains for dead links.

#### F. Per-project `~/.claude.json` drift
- Find project entries with MCPs uninstalled from global scope.
- **Cross-platform write artifact**: `installLocation` containing `C:\...` paths from a prior Windows session. Triggers `claude plugin marketplace update` failures. Fix: `claude plugin marketplace remove <name> && claude plugin marketplace add <name>`. (In a Claude Code session, equivalent commands are also available via `/plugin marketplace`.)

#### G. Skill / command / agent inventory
- **Defer to `unclog`** for skill + command + MCP token cost and 30-day invocation counts from session JSONLs (real ground truth).
- dirty-claude adds: zero-reference agent detection (grep skills/commands/settings/hooks for each agent name; if zero references, archive).
- "Older version, X is the rebuild" duplicates (heuristic: name suffixes like `-old`, parallel `newsletter` vs `nl`).

#### H. Plugin install state
- `enabledPlugins` entries that don't resolve in any marketplace (renamed/removed upstream).
- Failed-to-load plugins: often empty `hooks.json` shipped in plugin (Zod expects `{"hooks": {}}`, plugin ships `{}`). Local patch documented; file upstream PR.
- Marketplaces with cross-platform path corruption (see F).

#### I. Archived project purge  *(in main flow — frequent vibe-coder failure mode)*
Most CC users accumulate `~/.claude.json` `projects[<path>]` entries for repos they've abandoned. Each carries full transcripts, file-history, task state, and permission grants. `claude project purge <path>` (v2.1.126+) cleanly removes all of it.

Detection heuristics for purge candidates:
- Project last touched (per most recent session JSONL mtime) more than 30/60/90 days ago
- Repo no longer exists on disk
- Project marked archived in user's memory / notes (search `feedback_*archived*` patterns)
- Project name matches a removed Vercel project, killed git repo, etc.

Always `--dry-run` first to show the item count per path before executing. `tar` transcripts to `~/archive/` if user wants a reversible snapshot.

#### J. Disk bloat  *(OPT-IN — many users don't care about storage)*
Only run with `--storage` flag or explicit user request:
- `~/.claude/file-history/` >5GB. Issue [anthropics/claude-code#10107](https://github.com/anthropics/claude-code/issues/10107) reports user cases with hundreds of GB; treat as a known accumulation risk, not a formal limit.
- `~/Library/Caches/claude-cli-nodejs/` not covered by `cleanupPeriodDays`.
- Session JSONLs grown unbounded.
- `cleanupPeriodDays` setting absent (retention sweep off by default).
- Multiple stale `.backup.*` files.

### Phase 3 — Per-finding triage

For each finding:
- **Diff or before/after.** Show what would change.
- **Risk:** `SAFE` (deletes confirmed-orphaned files) / `NEEDS_REVIEW` (might affect workflow) / `DESTRUCTIVE` (irreversible).
- **Workflow impact:** `NONE` / `RESTORE_BROKEN_UX` (e.g., re-enable auto-approve hook) / `BEHAVIORAL_CHANGE` (e.g., wildcard permissions).
- **Confidence:** 10/10 (verified) → 1/10 (inferred). State the verification method.
- **Per-item greenlight** required for `NEEDS_REVIEW` and `DESTRUCTIVE`. `SAFE` items can be batched.

Stop after presenting findings unless the user explicitly greenlights cleanup. Do not edit files, move archives, run `claude project purge`, remove marketplaces, or change hooks during the same response that first presents findings.

### Phase 4 — Execute with backups

Only enter this phase after explicit user approval for the specific finding or batch.

- Auto-backup before any edit: `settings.json.bak-YYYY-MM-DD`, `MEMORY.md.bak-YYYY-MM-DD`, `.claude.json.bak-YYYY-MM-DD`.
- Default to **archive, not delete**: `mv` to `~/.claude/<thing>-archive-YYYY-MM-DD/`.
- Hard-delete only when user explicitly confirms.

### Phase 5 — Recap

- Bullet list of what changed (file:before-line-count → after-line-count).
- Items deferred / left for user (interactive runs, browser OAuth, etc.).
- Roadmap file for items parked: `~/.claude/projects/-Users-<...>-CC/memory/projects/cc-cleanup-roadmap.md`.

## Design principles

- **Workflow-preserving by default.** If a cleanup would change behavior, flag for review.
- **Show before delete.** Diff or content preview for every destructive action.
- **Backup before write.** Always.
- **Per-item greenlight.** Batched only for `SAFE` items.
- **Acknowledge other tools.** When a category is covered by unclog / mcpick / `/fewer-permission-prompts`, defer with the install one-liner.
- **Confidence ratings inline.** Don't paste recommendations without grading evidence.
- **Disk bloat is opt-in.** Some users care about storage, some don't. Don't assume.

## Trigger phrases

User invokes via: "dirty claude", "/dirty-claude", "audit my claude code setup", "cc hygiene", "clean up cc", "what's bloated in claude code", "claude code spring cleaning", "find orphan launchd", "check my MEMORY.md size", "audit my hooks".

## Credits

- **[unclog](https://github.com/thomaschill/unclog)** — Python CLI by thomaschill. dirty-claude defers to it for skill/command/MCP token cost + 30-day invocation tracking. MIT.
- **[`/fewer-permission-prompts`](https://docs.claude.com/claude-code)** — Anthropic official skill for allowlist scanning.
- **[mcpick](https://github.com/spences10/mcpick)** by spences10 — TUI for enable/disable. Complementary.
- **Power-user write-ups that informed the gap analysis:** [blog.sshh.io](https://blog.sshh.io/p/how-i-use-every-claude-code-feature), [ghuntley.com](https://ghuntley.com/loop/), [alexop.dev](https://alexop.dev/posts/stop-bloating-your-claude-md-progressive-disclosure-ai-coding-tools/), [mindstudio context-rot research](https://www.mindstudio.ai/blog/what-is-context-rot-claude-code).
- Built from a real 4-hour cleanup session where every category above produced findings nothing else caught.
