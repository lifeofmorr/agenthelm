"""AgentHelm skeleton tests — pure logic + a real HTTP smoke test."""
import json
import threading
import time
import urllib.request

import pytest

from agenthelm.adapters import FixtureAdapter
from agenthelm.briefs import generate_brief
from agenthelm.dashboard import render_dashboard
from agenthelm.scanner import ApprovalsStore, FleetScanner
from agenthelm.server import make_server


@pytest.fixture()
def scanner(tmp_path):
    store = ApprovalsStore(str(tmp_path / "decisions.json"))
    return FleetScanner([FixtureAdapter(now=1_000_000.0)], store), store


def test_fixture_adapter_covers_multiple_tools():
    sessions = FixtureAdapter(now=1_000_000.0).discover()
    tools = {s.tool for s in sessions}
    assert len(sessions) >= 3
    assert len(tools) >= 2, f"fixture fleet must span 2+ agent types, got {tools}"
    assert any(s.approvals for s in sessions), "fixture fleet needs a pending approval"


def test_scanner_totals_and_project_rollup(scanner):
    sc, _ = scanner
    snap = sc.scan()
    t = snap["totals"]
    assert t["agents"] == 4
    assert t["pending_approvals"] == 2
    assert t["tokens"] == sum(s["tokens"] for s in snap["sessions"])
    assert snap["totals"]["projects"]["billing-service"]["agents"] == 2
    assert t["by_status"]["working"] == 1
    assert t["by_status"]["waiting"] == 1


def test_approvals_store_decide_persists(scanner, tmp_path):
    sc, store = scanner
    assert store.decide("appr-demo-1", "approved") is True
    assert store.decide("appr-demo-1", "bogus") is False
    snap = sc.scan()
    assert snap["totals"]["pending_approvals"] == 1
    # decision survives a reload from disk
    store2 = ApprovalsStore(str(tmp_path / "decisions.json"))
    assert store2.decisions["appr-demo-1"]["status"] == "approved"


def test_brief_sections(scanner):
    sc, _ = scanner
    sess = next(s for s in sc.scan()["sessions"] if s["id"] == "codex:demo-tests")
    brief = generate_brief(sess)
    for needle in ("# Handoff brief", "## Decisions & approvals",
                   "## Files touched", "## Open items", "Start-here prompt"):
        assert needle in brief, needle
    assert "Write regression tests" in brief


def test_dashboard_renders():
    html = render_dashboard()
    assert "AgentHelm" in html
    assert "Approvals inbox" in html
    assert "/api/fleet" in html


def test_server_endpoints(scanner):
    sc, _ = scanner
    server = make_server(sc, sc.store, "127.0.0.1", 0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        with urllib.request.urlopen(base + "/", timeout=5) as resp:
            assert resp.status == 200
            assert b"AgentHelm" in resp.read()
        with urllib.request.urlopen(base + "/api/fleet", timeout=5) as resp:
            data = json.loads(resp.read())
        assert data["totals"]["agents"] == 4
        req = urllib.request.Request(
            base + "/api/approvals/appr-demo-2/decide",
            data=json.dumps({"decision": "denied"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert json.loads(resp.read())["ok"] is True
        with urllib.request.urlopen(base + "/api/brief/codex:demo-tests", timeout=5) as resp:
            assert resp.status == 200
            assert b"Handoff brief" in resp.read()
    finally:
        server.shutdown()
        thread.join(timeout=5)
