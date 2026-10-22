"""Fleet scanning: merge every adapter's sessions into one snapshot, roll
up burn per agent and per project, and aggregate the cross-tool approvals
queue. Decisions made in the inbox persist to a local JSON store so the
console (and the audit trail) survives restarts.
"""
from __future__ import annotations

import json
import os
import time

from .adapters import Adapter
from .model import STATUSES

DEFAULT_STATE_PATH = "~/.agenthelm/decisions.json"


class ApprovalsStore:
    """Append-only record of human decisions on approval requests."""

    def __init__(self, path: str = DEFAULT_STATE_PATH):
        self.path = os.path.expanduser(path)
        self.decisions: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self.decisions = data
        except (OSError, ValueError):
            self.decisions = {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.decisions, fh, indent=2)
        except OSError:
            pass

    def decide(self, approval_id: str, decision: str, answer: str = "") -> bool:
        if decision not in ("approved", "denied", "answered"):
            return False
        self.decisions[approval_id] = {
            "status": decision,
            "answer": answer,
            "decided_at": time.time(),
        }
        self._save()
        return True

    def apply(self, approval: dict) -> dict:
        """Overlay a recorded decision onto a pending approval dict."""
        rec = self.decisions.get(approval.get("id", ""))
        if rec and approval.get("status") == "pending":
            approval = dict(approval)
            approval["status"] = rec["status"]
            approval["answer"] = rec.get("answer", "")
        return approval


class FleetScanner:
    def __init__(self, adapters: list[Adapter], store: ApprovalsStore | None = None):
        self.adapters = adapters
        self.store = store or ApprovalsStore()

    def scan(self) -> dict:
        sessions = []
        for adapter in self.adapters:
            try:
                sessions.extend(adapter.discover())
            except Exception:
                continue  # fail soft per SOP-4
        sessions.sort(key=lambda s: s.last_activity, reverse=True)

        by_status = {s: 0 for s in STATUSES}
        projects: dict[str, dict] = {}
        approvals: list[dict] = []
        total_tokens = 0
        total_cost = 0.0

        session_dicts = []
        for s in sessions:
            by_status[s.status] = by_status.get(s.status, 0) + 1
            total_tokens += s.tokens
            total_cost += s.cost_usd
            proj = projects.setdefault(s.project, {"agents": 0, "tokens": 0, "cost_usd": 0.0})
            proj["agents"] += 1
            proj["tokens"] += s.tokens
            proj["cost_usd"] = round(proj["cost_usd"] + s.cost_usd, 4)
            d = s.to_dict()
            d["approvals"] = [self.store.apply(a) for a in d.get("approvals", [])]
            approvals.extend(a for a in d["approvals"] if a["status"] == "pending")
            session_dicts.append(d)

        approvals.sort(key=lambda a: a["created_at"])
        return {
            "generated_at": time.time(),
            "sessions": session_dicts,
            "approvals_pending": approvals,
            "totals": {
                "agents": len(session_dicts),
                "by_status": by_status,
                "tokens": total_tokens,
                "cost_usd": round(total_cost, 4),
                "pending_approvals": len(approvals),
                "projects": projects,
            },
        }
