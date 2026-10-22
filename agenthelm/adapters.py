"""Discovery adapters.

Each adapter finds agent sessions from one tool's own on-disk session store
or process table — zero configuration, read-only. Adapters must never raise:
a broken adapter means "no sessions from that tool", never a crashed board
(SOP-4: fail soft, never fabricate state).
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import time

from .model import AgentSession, ApprovalRequest, derive_status

MAX_SESSION_AGE_SECS = 24 * 3600  # board shows the last day of work
MAX_SESSIONS_PER_TOOL = 20
BLENDED_USD_PER_TOKEN = 3.0 / 1_000_000  # rough blended rate; cost is labeled estimate


def _first_user_text(path: str, max_lines: int = 200) -> str:
    """Best-effort first user prompt from a JSONL session transcript."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= max_lines:
                    break
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                msg = rec.get("message") if isinstance(rec, dict) else None
                if isinstance(msg, dict) and msg.get("role") == "user":
                    content = msg.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip().splitlines()[0][:140]
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                txt = str(part.get("text", "")).strip()
                                if txt:
                                    return txt.splitlines()[0][:140]
    except OSError:
        pass
    return ""


def _usage_tokens(path: str, max_lines: int = 5000) -> int:
    """Sum real token usage from a JSONL transcript (0 if none recorded)."""
    total = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= max_lines:
                    break
                if '"usage"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                msg = rec.get("message") if isinstance(rec, dict) else None
                usage = msg.get("usage") if isinstance(msg, dict) else None
                if isinstance(usage, dict):
                    for key in ("input_tokens", "output_tokens",
                                "cache_creation_input_tokens", "cache_read_input_tokens"):
                        val = usage.get(key)
                        if isinstance(val, (int, float)):
                            total += int(val)
    except OSError:
        pass
    return total


class Adapter:
    tool = "base"

    def discover(self) -> list[AgentSession]:
        return []


class JsonlStoreAdapter(Adapter):
    """Shared logic for tools that keep one JSONL transcript per session."""

    store_glob: str = ""
    tool: str = ""

    def _project_name(self, path: str) -> str:
        return os.path.basename(os.path.dirname(path)) or self.tool

    def discover(self) -> list[AgentSession]:
        now = time.time()
        sessions: list[AgentSession] = []
        try:
            paths = glob.glob(os.path.expanduser(self.store_glob), recursive=True)
        except Exception:
            return sessions
        paths = [p for p in paths if os.path.isfile(p)]
        paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        for path in paths[:MAX_SESSIONS_PER_TOOL]:
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if now - mtime > MAX_SESSION_AGE_SECS:
                continue
            tokens = _usage_tokens(path)
            sessions.append(AgentSession(
                id=f"{self.tool}:{os.path.basename(path)}",
                tool=self.tool,
                project=self._project_name(path),
                cwd="",
                task=_first_user_text(path),
                status=derive_status(mtime, now),
                last_activity=mtime,
                started_at=mtime,
                tokens=tokens,
                cost_usd=round(tokens * BLENDED_USD_PER_TOKEN, 4),
                burn_estimated=True,  # tokens real where logged; price always an estimate
            ))
        return sessions


class ClaudeCodeAdapter(JsonlStoreAdapter):
    tool = "claude-code"
    store_glob = "~/.claude/projects/*/*.jsonl"

    def _project_name(self, path: str) -> str:
        enc = os.path.basename(os.path.dirname(path))
        decoded = enc.replace("-", "/")
        return os.path.basename(decoded.rstrip("/")) or enc


class CodexAdapter(JsonlStoreAdapter):
    tool = "codex"
    store_glob = "~/.codex/sessions/**/*.jsonl"

    def _project_name(self, path: str) -> str:
        return "codex-session"


class GenericShellAdapter(Adapter):
    """Tracks long-running agent CLIs by process scan (OpenCode, Copilot,
    aider, Cursor-agent, and friends). This is also the fallback that keeps
    sessions visible when a vendor changes its session-store format."""

    PATTERNS = {
        "opencode": "opencode",
        "copilot": "copilot",
        "aider": "aider",
        "cursor": "cursor-agent",
    }

    def discover(self) -> list[AgentSession]:
        now = time.time()
        sessions: list[AgentSession] = []
        for tool, pattern in self.PATTERNS.items():
            try:
                out = subprocess.run(
                    ["pgrep", "-af", pattern],
                    capture_output=True, text=True, timeout=5,
                )
            except (OSError, subprocess.SubprocessError):
                continue
            for line in out.stdout.splitlines():
                parts = line.strip().split(None, 1)
                if not parts or not parts[0].isdigit():
                    continue
                pid = int(parts[0])
                cmd = parts[1] if len(parts) > 1 else pattern
                cwd = ""
                try:
                    cwd = os.readlink(f"/proc/{pid}/cwd")
                except OSError:
                    pass
                sessions.append(AgentSession(
                    id=f"{tool}:pid{pid}",
                    tool=tool,
                    project=os.path.basename(cwd) if cwd else tool,
                    cwd=cwd,
                    task=cmd[:140],
                    status="working",
                    last_activity=now,
                    started_at=now,
                    pid=pid,
                ))
        return sessions


class FixtureAdapter(Adapter):
    """Deterministic demo fleet — lets the board (and the tests, and a
    prospect's first run) render populated with no agents installed."""

    tool = "fixture"

    def __init__(self, now: float | None = None):
        self.now = now if now is not None else time.time()

    def discover(self) -> list[AgentSession]:
        n = self.now
        return [
            AgentSession(
                id="claude-code:demo-refactor", tool="claude-code",
                project="billing-service", cwd="~/work/billing-service",
                task="Refactor invoice PDF generation into a worker queue",
                status="working", last_activity=n - 20, started_at=n - 2400,
                tokens=812_400, cost_usd=2.44, burn_estimated=True,
                files_touched=["src/invoices/pdf.ts", "src/queue/worker.ts"],
            ),
            AgentSession(
                id="codex:demo-tests", tool="codex",
                project="billing-service", cwd="~/work/billing-service",
                task="Write regression tests for the refund flow",
                status="waiting", last_activity=n - 300, started_at=n - 1800,
                tokens=402_150, cost_usd=1.21, burn_estimated=True,
                approvals=[ApprovalRequest(
                    id="appr-demo-1", session_id="codex:demo-tests",
                    kind="permission",
                    summary="Run `npm test -- --watchAll=false` outside the sandbox?",
                    created_at=n - 280,
                )],
            ),
            AgentSession(
                id="opencode:demo-migration", tool="opencode",
                project="data-migration", cwd="~/work/data-migration",
                task="Draft migration 0042 (add index on orders.created_at)",
                status="idle", last_activity=n - 1500, started_at=n - 5400,
                tokens=96_020, cost_usd=0.29, burn_estimated=True,
                approvals=[ApprovalRequest(
                    id="appr-demo-2", session_id="opencode:demo-migration",
                    kind="question",
                    summary="Backfill the new column now, or leave it nullable until the next deploy?",
                    created_at=n - 1400,
                )],
            ),
            AgentSession(
                id="claude-code:demo-docs", tool="claude-code",
                project="agenthelm", cwd="~/work/agenthelm",
                task="Draft the launch comparison page",
                status="done", last_activity=n - 7200, started_at=n - 10800,
                tokens=210_300, cost_usd=0.63, burn_estimated=True,
                files_touched=["site/features.html"],
            ),
        ]


def default_adapters(demo: bool = False) -> list[Adapter]:
    if demo:
        return [FixtureAdapter()]
    adapters: list[Adapter] = [ClaudeCodeAdapter(), CodexAdapter(), GenericShellAdapter()]
    if os.environ.get("AGENTHELM_FIXTURES") == "1":
        adapters.append(FixtureAdapter())
    return adapters
