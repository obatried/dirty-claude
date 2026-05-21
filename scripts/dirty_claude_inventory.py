#!/usr/bin/env python3
"""Read-only Claude Code hygiene inventory for the dirty-claude skill."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import subprocess
from pathlib import Path
from typing import Any


HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
CLAUDE_JSON = HOME / ".claude.json"


def human_size(num: int) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{num} B"


def path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not Path(root, d).is_symlink()]
        for name in files:
            file_path = Path(root, name)
            try:
                if not file_path.is_symlink():
                    total += file_path.stat().st_size
            except OSError:
                pass
    return total


def count_files(path: Path, pattern: str = "*") -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob(pattern) if item.is_file())


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def run_command(command: list[str], timeout: int = 15) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def installed_mcp_names(settings: dict[str, Any], claude_json: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    if isinstance(settings.get("mcpServers"), dict):
        names.update(settings["mcpServers"].keys())
    if isinstance(claude_json.get("mcpServers"), dict):
        names.update(claude_json["mcpServers"].keys())
    projects = claude_json.get("projects")
    if isinstance(projects, dict):
        for project in projects.values():
            if isinstance(project, dict) and isinstance(project.get("mcpServers"), dict):
                names.update(project["mcpServers"].keys())
    return names


def permission_mcp_names(settings: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    permissions = settings.get("permissions")
    if not isinstance(permissions, dict):
        return names
    for key in ("allow", "ask"):
        values = permissions.get(key, [])
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str):
                    match = re.search(r"mcp__([^_]+)__", value)
                    if match:
                        names.add(match.group(1))
    return names


def hook_matcher_mcp_names(settings: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return names
    for hook_entries in hooks.values():
        if not isinstance(hook_entries, list):
            continue
        for entry in hook_entries:
            if not isinstance(entry, dict):
                continue
            matcher = entry.get("matcher", "")
            if isinstance(matcher, str):
                names.update(re.findall(r"mcp__([A-Za-z0-9_-]+)__", matcher))
    return names


def marketplace_windows_paths(path: Path) -> list[str]:
    data = load_json(path)
    hits: list[str] = []
    for name, value in data.items():
        if isinstance(value, dict):
            install_location = str(value.get("installLocation", ""))
            if re.search(r"^[A-Za-z]:\\", install_location):
                hits.append(f"{name}: {install_location}")
    return hits


def launch_agent_findings() -> list[str]:
    launch_dir = HOME / "Library" / "LaunchAgents"
    findings: list[str] = []
    if not launch_dir.exists():
        return findings
    for plist_path in launch_dir.glob("com.*.plist"):
        try:
            with plist_path.open("rb") as handle:
                plist = plistlib.load(handle)
        except Exception:
            continue
        args = plist.get("ProgramArguments") or []
        program = plist.get("Program")
        paths = [program] if isinstance(program, str) else []
        paths.extend(arg for arg in args if isinstance(arg, str) and arg.startswith("/"))
        missing = [p for p in paths if not Path(p).exists()]
        if missing:
            findings.append(f"{plist_path.name}: missing path(s): {', '.join(missing[:3])}")
    return findings


def line_count(path: Path) -> int:
    try:
        return len(path.read_text(errors="ignore").splitlines())
    except OSError:
        return 0


SAFE_DENY_PATTERNS = [
    "Bash(rm -rf /)*",
    "Bash(rm -rf ~)*",
    "Bash(rm -rf .)*",
    "Bash(mkfs.*)",
    "Bash(*curl * | bash*)",
    "Bash(*curl * | sh*)",
    "Bash(*wget * | bash*)",
    "Bash(*wget * | sh*)",
    "Read(**/.ssh/**)",
    "Read(**/credentials*)",
]


def check_claude_md(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "line_count": 0, "has_section_headers": False}
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return {"exists": True, "line_count": 0, "has_section_headers": False}
    return {
        "exists": True,
        "line_count": len(text.splitlines()),
        "has_section_headers": bool(re.search(r"^## ", text, re.MULTILINE)),
    }


def check_settings_baseline(settings: dict[str, Any], path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "has_permissions": False, "deny_coverage": 0}
    permissions = settings.get("permissions", {})
    deny = permissions.get("deny", []) if isinstance(permissions, dict) else []
    if not isinstance(deny, list):
        deny = []
    deny_set = {d for d in deny if isinstance(d, str)}
    coverage = sum(1 for pat in SAFE_DENY_PATTERNS if pat in deny_set)
    return {
        "exists": True,
        "has_permissions": isinstance(permissions, dict) and bool(permissions),
        "deny_coverage": coverage,
    }


def count_wired_hooks(settings: dict[str, Any]) -> int:
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return 0
    total = 0
    for entries in hooks.values():
        if isinstance(entries, list):
            total += len(entries)
    return total


def find_repo_root(start: Path) -> Path | None:
    """Walk up from start until we find a .git directory."""
    for path in [start, *start.parents]:
        if (path / ".git").exists():
            return path
    return None


def check_project_baseline(cwd: Path) -> dict[str, Any] | None:
    """Project-scope checks fire when cwd is inside a git repo (any depth)."""
    repo_root = find_repo_root(cwd)
    if repo_root is None:
        return None
    project_settings_path = repo_root / ".claude" / "settings.json"
    return {
        "repo_root": str(repo_root),
        "claude_md": check_claude_md(repo_root / "CLAUDE.md"),
        "settings": check_settings_baseline(load_json(project_settings_path), project_settings_path),
    }


def json_parse_status(path: Path) -> str:
    """Returns 'missing' | 'valid' | 'corrupt' | 'unreadable'."""
    if not path.exists():
        return "missing"
    try:
        text = path.read_text()
    except OSError:
        return "unreadable"
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return "corrupt"
    return "valid"


def baseline_status_label(claude_md: dict, settings_baseline: dict) -> str:
    """Classify user-scope install as blank / partial / configured for the recap line.

    Hooks are intentionally excluded — they're not bootstrap-installable, so including
    them in classification produces 'partial' labels with no actionable finding.
    """
    has_claude_md = bool(claude_md.get("exists"))
    has_settings_baseline = bool(settings_baseline.get("exists")) and settings_baseline.get("deny_coverage", 0) >= 5
    score = sum([has_claude_md, has_settings_baseline])
    if score == 0:
        return "blank"
    if score == 1:
        return "partial"
    return "configured"


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Claude Code hygiene inventory.")
    parser.add_argument("--storage", action="store_true", help="Include opt-in disk bloat checks.")
    args = parser.parse_args()

    settings_path = CLAUDE_DIR / "settings.json"
    settings = load_json(settings_path)
    claude_json = load_json(CLAUDE_JSON)
    known_marketplaces = CLAUDE_DIR / "plugins" / "known_marketplaces.json"
    auth_cache = load_json(CLAUDE_DIR / "mcp-needs-auth-cache.json")

    print("# dirty-claude inventory")
    print()
    print("| Item | Count / Size |")
    print("|---|---:|")
    print(f"| ~/.claude.json | {human_size(path_size(CLAUDE_JSON))} |")
    projects = claude_json.get("projects", {})
    print(f"| Project entries | {len(projects) if isinstance(projects, dict) else 0} |")
    for name in ("skills", "commands", "agents", "hooks"):
        print(f"| ~/.claude/{name}/ files | {count_files(CLAUDE_DIR / name)} |")
    for name in ("state", "projects", "file-history", "plugins"):
        print(f"| ~/.claude/{name}/ | {human_size(path_size(CLAUDE_DIR / name))} |")
    print(f"| mcp-needs-auth-cache entries | {len(auth_cache) if isinstance(auth_cache, dict) else 0} |")
    print()

    user_claude_md = check_claude_md(CLAUDE_DIR / "CLAUDE.md")
    user_settings_baseline = check_settings_baseline(settings, settings_path)
    user_settings_json_status = json_parse_status(settings_path)
    hooks_wired = count_wired_hooks(settings)
    project_baseline = check_project_baseline(Path.cwd())
    install_label = baseline_status_label(user_claude_md, user_settings_baseline)

    print("## Baseline state")
    print()
    print("| Item | Status |")
    print("|---|---|")
    if user_claude_md["exists"]:
        headers_note = "has section headers" if user_claude_md["has_section_headers"] else "no section headers"
        print(f"| ~/.claude/CLAUDE.md | exists ({user_claude_md['line_count']} lines, {headers_note}) |")
    else:
        print("| ~/.claude/CLAUDE.md | **missing** |")
    if user_settings_json_status == "corrupt":
        print("| ~/.claude/settings.json | **corrupt JSON** (do not auto-edit) |")
    elif user_settings_json_status == "unreadable":
        print("| ~/.claude/settings.json | **unreadable** (permissions issue?) |")
    elif user_settings_baseline["exists"]:
        coverage = user_settings_baseline["deny_coverage"]
        label = "configured" if coverage >= 5 else "bare (low safe-deny coverage)"
        print(f"| ~/.claude/settings.json | {label} ({coverage}/{len(SAFE_DENY_PATTERNS)} safe-deny patterns) |")
    else:
        print("| ~/.claude/settings.json | **missing** |")
    print(f"| Hooks wired in settings.json | {hooks_wired} (informational; not part of bootstrap baseline) |")
    if project_baseline is not None:
        pcm = project_baseline["claude_md"]
        psb = project_baseline["settings"]
        repo_root = project_baseline["repo_root"]
        if pcm["exists"]:
            print(f"| ./CLAUDE.md (repo: {repo_root}) | exists ({pcm['line_count']} lines) |")
        else:
            print(f"| ./CLAUDE.md (repo: {repo_root}) | **missing** (you're inside a git repo) |")
        if psb["exists"]:
            print(f"| ./.claude/settings.json | exists ({psb['deny_coverage']}/{len(SAFE_DENY_PATTERNS)} safe-deny patterns) |")
        else:
            print("| ./.claude/settings.json | not present (optional for project) |")
    print(f"| **Install state** | **{install_label}** |")
    print()

    code, mcp_output = run_command(["claude", "mcp", "list"])
    print("## MCP list")
    print()
    if code == 0 and mcp_output:
        print("```text")
        print(mcp_output)
        print("```")
    else:
        print(f"`claude mcp list` unavailable or failed: {mcp_output or 'no output'}")
    print()

    installed_mcps = installed_mcp_names(settings, claude_json)
    permission_only = sorted(permission_mcp_names(settings) - installed_mcps)
    hook_only = sorted(hook_matcher_mcp_names(settings) - installed_mcps)
    windows_marketplaces = marketplace_windows_paths(known_marketplaces)
    launch_findings = launch_agent_findings()

    print("## Potential findings")
    print()
    if not user_claude_md["exists"]:
        print("- **Missing baseline:** ~/.claude/CLAUDE.md not present. Bootstrap can install the 7-principle starter version.")
    if user_settings_json_status == "corrupt":
        print("- **CRITICAL: corrupt settings.json:** ~/.claude/settings.json exists but JSON is malformed. Do NOT attempt automated merge. Back up + manually repair, or back up + replace with starter baseline. Phase 4 will not auto-edit a file it can't parse.")
    elif user_settings_json_status == "unreadable":
        print("- **Unreadable settings.json:** check file permissions before any bootstrap action.")
    elif not user_settings_baseline["exists"]:
        print("- **Missing baseline:** ~/.claude/settings.json not present. Bootstrap can install a safe-defaults version.")
    elif user_settings_baseline.get("deny_coverage", 0) < 5:
        print(f"- **Bare baseline:** ~/.claude/settings.json exists but covers only {user_settings_baseline['deny_coverage']}/{len(SAFE_DENY_PATTERNS)} safe-deny patterns. Bootstrap can merge missing patterns (valid JSON only).")
    if project_baseline is not None and not project_baseline["claude_md"]["exists"]:
        print(f"- **Missing project baseline:** you're inside the git repo at {project_baseline['repo_root']} but ./CLAUDE.md is not present. Run `/init` or have bootstrap install a starter.")
    if permission_only:
        print(f"- settings.json has permission entries for MCP names not found in config: {', '.join(permission_only)}")
    if hook_only:
        print(f"- settings.json has hook matchers for MCP names not found in config: {', '.join(hook_only)}")
    if windows_marketplaces:
        print("- known_marketplaces.json contains Windows installLocation paths:")
        for hit in windows_marketplaces:
            print(f"  - {hit}")
    if launch_findings:
        print("- LaunchAgents reference missing paths:")
        for finding in launch_findings[:10]:
            print(f"  - {finding}")

    memory_roots = sorted((CLAUDE_DIR / "projects").glob("*/memory/MEMORY.md"))
    large_memory = [(path, line_count(path)) for path in memory_roots if line_count(path) > 200]
    if large_memory:
        print("- MEMORY.md files over 200 lines:")
        for path, lines in large_memory[:10]:
            print(f"  - {path}: {lines} lines")

    baseline_missing = (
        not user_claude_md["exists"]
        or user_settings_json_status in {"corrupt", "unreadable"}
        or not user_settings_baseline["exists"]
        or (user_settings_baseline.get("deny_coverage", 0) < 5)
        or (project_baseline is not None and not project_baseline["claude_md"]["exists"])
    )
    if not any((permission_only, hook_only, windows_marketplaces, launch_findings, large_memory, baseline_missing)):
        print("- No obvious findings from the read-only inventory.")
    print()

    if args.storage:
        print("## Storage checks")
        print()
        cache_path = HOME / "Library" / "Caches" / "claude-cli-nodejs"
        print(f"- ~/.claude/file-history/: {human_size(path_size(CLAUDE_DIR / 'file-history'))}")
        print(f"- ~/Library/Caches/claude-cli-nodejs/: {human_size(path_size(cache_path))}")
        print(f"- cleanupPeriodDays: {settings.get('cleanupPeriodDays', 'not set')}")
        print()

    print("Read-only inventory complete. Review findings before proposing any cleanup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
