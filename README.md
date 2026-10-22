# AgentHelm

**Every agent. One helm.**

AgentHelm is the fleet operations console for coding agents. Run Claude Code,
Codex, OpenCode, Copilot, or a plain shell agent — AgentHelm discovers every
session on your machine with zero config and puts them on one board: status,
current task, last activity, and what each one is costing you. Every pending
permission prompt and question from every tool lands in **one approvals
inbox** you clear in batches. When an agent finishes or gets replaced, a
**handoff brief** is generated automatically and handed to the successor.

Local-first. Your code, prompts, and session data never leave the machine.

## Quickstart

```bash
# Demo fleet (no agents needed) — see the board populated:
python3 -m agenthelm.server --demo            # http://127.0.0.1:7788

# Real discovery (Claude Code + Codex session stores + agent processes):
python3 -m agenthelm.server

# Tests:
python3 -m pytest tests/ -q
```

No dependencies beyond Python 3.10+ (tests need pytest).

## How it works

- **Discovery adapters** read each tool's own session store
  (`~/.claude/projects/*/*.jsonl`, `~/.codex/sessions/**`) and scan the
  process table for other agent CLIs (OpenCode, Copilot, aider,
  cursor-agent). Adapters fail soft: a vendor format change means fewer
  sessions shown, never a wrong board.
- **Fleet scanner** merges sessions, classifies status
  (working / waiting / idle / done / stalled), sums real token usage from
  transcripts where it's logged, and rolls burn up per agent and project.
  Prices are always labeled estimates.
- **Approvals inbox** aggregates pending requests across tools; decisions
  persist to `~/.agenthelm/decisions.json` (append-only audit record).
- **Handoff briefs** render from live session state (task, decisions,
  files touched, open items, successor start-here prompt) at
  `/api/brief/<session_id>`.

API: `GET /api/fleet` (JSON snapshot), `GET /api/brief/<id>`,
`POST /api/approvals/<id>/decide`.

## AgentHelm vs BAND — parity, honestly

BAND (Thenovi AI) launched the category in Oct 2026. This table is the
parity contract; "Staged" rows are on the roadmap (see the business spec)
and are **not** claimed as shipping.

| Capability | BAND | AgentHelm |
|---|---|---|
| Fleet dashboard (projects, owners, blockers, progress) | ✅ | ✅ (this repo) |
| Drill-down fleet → project → agent | ✅ | ✅ |
| Answer / redirect / review in place | ✅ | ✅ via approvals inbox + briefs |
| Shared rooms / chat with @mentions | ✅ | 🔜 v1.1 |
| Agent-to-agent delegation + handoffs | ✅ | 🔜 v1.1 (brief-first) |
| Context carried across handoffs | ✅ | ✅ via handoff briefs |
| CLI companion | ✅ | ✅ (`--demo`, API) |
| Local + remote agents, one view | ✅ | Local ✅ · remote 🔜 later |
| Claude Code / Codex / Copilot / OpenCode adapters | ✅ | ✅ discovery |
| Cursor support | ❌ (at launch) | ✅ generic adapter · first-class v1.1 |
| Custom agents (LangGraph/CrewAI class) | ✅ SDK | 🔜 adapter API v1.1 |
| **Approvals inbox — one queue, batch clear** | ❌ | ✅ |
| **Token/cost burn per agent + project** | ❌ | ✅ |
| **Automatic handoff briefs** | ❌ | ✅ |
| **Task routing with budgets + stop conditions** | ❌ | 🔜 v1.1 |
| Native desktop app (mac/win/linux) | ✅ | 🔜 later (local web console today) |
| Published flat pricing | ❌ (unpublished at launch) | ✅ $0 / $19 / $49 / $499 |

## Layout

```
agenthelm/
  model.py       sessions + approval requests
  adapters.py    Claude/Codex JSONL discovery, process scan, fixtures
  scanner.py     fleet snapshot, burn rollups, decisions store
  briefs.py      handoff brief generator
  dashboard.py   the board page (keyboard-first)
  server.py      stdlib HTTP server + API
tests/           pytest suite (logic + live HTTP smoke)
```

## Status

v0.1 skeleton — the seed of the MVP staging in the business spec
(`../01-positioning.md`): discovery + board + inbox + briefs run today;
deep per-tool prompt capture, routing, and rooms are staged next.
