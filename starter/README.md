# starter/

Files vendored from [claude-code-starter-kit](https://github.com/obatried/claude-code-starter-kit). Installed by `/dirty-claude` when it detects a blank Claude Code install (no `~/.claude/CLAUDE.md` and no baseline `~/.claude/settings.json`).

Re-vendor with:

```bash
cp ../claude-code-starter-kit/CLAUDE.md ./CLAUDE.md
# settings.json is starter-kit's settings.json.example with the "hooks" block stripped
```

The hook from starter-kit is intentionally not vendored here — dirty-claude bootstrap does not install hooks by default. New users discover hooks through `NEXT_STEPS.md` in starter-kit instead.
