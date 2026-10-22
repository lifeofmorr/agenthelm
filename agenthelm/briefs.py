"""Automatic handoff briefs.

When an agent finishes or is replaced, the successor (human or agent)
should not need the old transcript. A brief is the distilled record:
task, state, decisions, files, open items, and a start-here prompt.
Deterministic string building — same session in, same brief out.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _iso(ts: float) -> str:
    if not ts:
        return "unknown"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def generate_brief(session: dict) -> str:
    """Build a markdown handoff brief from a session dict (scanner shape)."""
    approvals = session.get("approvals", [])
    decided = [a for a in approvals if a.get("status") != "pending"]
    pending = [a for a in approvals if a.get("status") == "pending"]
    files = session.get("files_touched", [])

    lines = [
        f"# Handoff brief — {session.get('project', '?')} ({session.get('tool', '?')})",
        "",
        f"**Task:** {session.get('task') or '(no task recorded)'}",
        f"**Status:** {session.get('status', '?')} · **Last activity:** {_iso(session.get('last_activity', 0))}",
        f"**Working directory:** {session.get('cwd') or '(unknown)'}",
        f"**Burn so far:** {session.get('tokens', 0):,} tokens · ${session.get('cost_usd', 0):.2f}"
        + (" (cost estimated)" if session.get("burn_estimated") else ""),
        "",
        "## Decisions & approvals",
    ]
    if decided:
        for a in decided:
            suffix = f" — {a['answer']}" if a.get("answer") else ""
            lines.append(f"- [{a['status']}] ({a['kind']}) {a['summary']}{suffix}")
    else:
        lines.append("- None recorded.")

    lines += ["", "## Files touched"]
    if files:
        lines += [f"- `{f}`" for f in files]
    else:
        lines.append("- None recorded.")

    lines += ["", "## Open items"]
    if pending:
        for a in pending:
            lines.append(f"- Still waiting on a human: ({a['kind']}) {a['summary']}")
    if session.get("status") in ("stalled", "waiting"):
        lines.append(f"- Session is {session['status']} — pick it up or close it deliberately.")
    if not pending and session.get("status") not in ("stalled", "waiting"):
        lines.append("- None. Session ended clean or was never blocked.")

    lines += [
        "",
        "## Start-here prompt for the successor",
        "",
        f"You are taking over a {session.get('tool', 'agent')} session in "
        f"{session.get('project', 'this project')}. Task: {session.get('task') or '(see brief)'}. "
        "Read this brief, check the files listed, resolve the open items first, "
        "and continue from the last state above — do not restart the task from scratch.",
        "",
    ]
    return "\n".join(lines)
