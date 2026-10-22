"""Core data model for AgentHelm.

A Session is one running (or recently finished) agent. An ApprovalRequest is
one decision an agent is waiting on a human for — the unit the Approvals
Inbox is built around.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

STATUSES = ("working", "waiting", "idle", "done", "stalled")

# A session with no file/process activity for this long is "stalled" if it
# never reached a terminal state.
STALL_AFTER_SECS = 30 * 60


@dataclass
class ApprovalRequest:
    id: str
    session_id: str
    kind: str  # "permission" | "question" | "decision"
    summary: str
    created_at: float
    status: str = "pending"  # pending | approved | denied | answered
    answer: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentSession:
    id: str
    tool: str  # "claude-code" | "codex" | "opencode" | "shell" | ...
    project: str
    cwd: str = ""
    task: str = ""
    status: str = "idle"  # one of STATUSES
    last_activity: float = 0.0
    started_at: float = 0.0
    pid: int | None = None
    tokens: int = 0
    cost_usd: float = 0.0
    burn_estimated: bool = True  # False only when tokens came from real usage logs
    files_touched: list = field(default_factory=list)
    approvals: list = field(default_factory=list)  # list[ApprovalRequest]

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def derive_status(last_activity: float, now: float, terminal: bool = False) -> str:
    """Map last-activity age to a board status."""
    if terminal:
        return "done"
    age = now - last_activity
    if age <= 180:
        return "working"
    if age <= STALL_AFTER_SECS:
        return "idle"
    return "stalled"


def now_ts() -> float:
    return time.time()
