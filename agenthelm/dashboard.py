"""The fleet board page. Server-rendered shell; data loads from
/api/fleet and re-renders client-side every 2 seconds so interactions
stay instant. Fully keyboard-operable: j/k move in the approvals inbox,
a = approve, d = deny, r = refresh now.
"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AgentHelm — Fleet Board</title>
<style>
  :root { --bg:#0b1220; --panel:#121c30; --line:#22304d; --txt:#e8eef8; --dim:#93a5c4;
          --amber:#f5a623; --green:#2fbf71; --red:#e5484d; --slate:#5b6b8c; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font:14px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  header { display:flex; flex-wrap:wrap; gap:12px; align-items:baseline;
           padding:14px 20px; border-bottom:1px solid var(--line); }
  header h1 { font-size:19px; margin:0; letter-spacing:.2px; }
  header h1 .helm { color:var(--amber); }
  .totals { display:flex; gap:16px; flex-wrap:wrap; margin-left:auto; color:var(--dim); }
  .totals b { color:var(--txt); font-variant-numeric:tabular-nums; }
  main { padding:16px 20px 40px; max-width:1240px; margin:0 auto; }
  h2 { font-size:13px; text-transform:uppercase; letter-spacing:.12em; color:var(--dim); margin:22px 0 10px; }
  .inbox-empty, .empty { color:var(--dim); border:1px dashed var(--line); border-radius:10px; padding:14px; }
  .approval { display:flex; gap:12px; align-items:flex-start; background:var(--panel);
              border:1px solid var(--line); border-left:4px solid var(--amber);
              border-radius:10px; padding:12px 14px; margin-bottom:8px; }
  .approval.sel { outline:2px solid var(--amber); }
  .approval .meta { color:var(--dim); font-size:12px; }
  .approval .sum { flex:1; }
  button { background:#1a2742; color:var(--txt); border:1px solid var(--line);
           border-radius:7px; padding:5px 12px; cursor:pointer; font:inherit; }
  button:hover { border-color:var(--amber); }
  button.ok:hover { border-color:var(--green); }
  button.no:hover { border-color:var(--red); }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(290px,1fr)); gap:12px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px; }
  .card h3 { margin:0 0 2px; font-size:15px; }
  .card .tool { color:var(--dim); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }
  .card .task { margin:8px 0; min-height:42px; }
  .card .row { display:flex; justify-content:space-between; color:var(--dim); font-size:12.5px; }
  .card .row b { color:var(--txt); font-variant-numeric:tabular-nums; }
  .chip { display:inline-block; padding:1px 9px; border-radius:99px; font-size:12px; border:1px solid var(--line); }
  .chip.working { color:var(--green); border-color:var(--green); }
  .chip.waiting { color:var(--amber); border-color:var(--amber); }
  .chip.idle { color:var(--dim); }
  .chip.done { color:var(--slate); }
  .chip.stalled { color:var(--red); border-color:var(--red); }
  .keys { color:var(--dim); font-size:12px; margin-top:26px; }
  kbd { background:#1a2742; border:1px solid var(--line); border-bottom-width:2px;
        border-radius:5px; padding:0 5px; font-size:11px; }
  pre.brief { white-space:pre-wrap; background:var(--panel); border:1px solid var(--line);
              border-radius:10px; padding:14px; max-height:420px; overflow:auto; }
</style></head>
<body>
<header>
  <h1><span class="helm">&#9095;</span> AgentHelm <span style="color:var(--dim);font-weight:400">fleet board</span></h1>
  <div class="totals" id="totals">loading&hellip;</div>
</header>
<main>
  <h2>Approvals inbox <span id="appr-count"></span></h2>
  <div id="inbox"></div>
  <h2>Fleet</h2>
  <div class="grid" id="fleet"></div>
  <div id="brief-wrap"></div>
  <p class="keys">Keys: <kbd>j</kbd>/<kbd>k</kbd> select approval &middot; <kbd>a</kbd> approve &middot;
     <kbd>d</kbd> deny &middot; <kbd>b</kbd> brief for first selected session &middot; <kbd>r</kbd> refresh</p>
</main>
<script>
let state = { approvals: [], sessions: [], sel: 0 };

function esc(s){ const d=document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; }
function ago(ts){ if(!ts) return '—'; const s = Math.max(0, (Date.now()/1000 - ts)|0);
  if (s < 60) return s + 's ago'; if (s < 3600) return ((s/60)|0) + 'm ago';
  if (s < 86400) return ((s/3600)|0) + 'h ago'; return ((s/86400)|0) + 'd ago'; }
function money(v){ return '$' + Number(v||0).toFixed(2); }

async function refresh(){
  try {
    const r = await fetch('/api/fleet'); const data = await r.json();
    state.sessions = data.sessions; state.approvals = data.approvals_pending;
    if (state.sel >= state.approvals.length) state.sel = Math.max(0, state.approvals.length - 1);
    render(data);
  } catch(e) { /* keep last render; next tick retries */ }
}

function render(data){
  const t = data.totals, bs = t.by_status || {};
  document.getElementById('totals').innerHTML =
    '<span><b>' + t.agents + '</b> agents</span>' +
    '<span><b>' + (bs.working||0) + '</b> working</span>' +
    '<span><b>' + (bs.waiting||0) + '</b> waiting</span>' +
    '<span><b>' + t.pending_approvals + '</b> approvals pending</span>' +
    '<span>burn <b>' + Number(t.tokens).toLocaleString() + '</b> tok &middot; <b>' + money(t.cost_usd) + '</b> est.</span>';
  document.getElementById('appr-count').textContent = t.pending_approvals ? '(' + t.pending_approvals + ' waiting on you)' : '';

  const inbox = document.getElementById('inbox');
  if (!state.approvals.length) {
    inbox.innerHTML = '<div class="inbox-empty">Inbox zero. No agent is waiting on a decision.</div>';
  } else {
    inbox.innerHTML = state.approvals.map(function(a, i){
      const sess = state.sessions.find(s => s.id === a.session_id) || {};
      return '<div class="approval' + (i === state.sel ? ' sel' : '') + '">' +
        '<div class="sum"><div>' + esc(a.summary) + '</div>' +
        '<div class="meta">' + esc(a.kind) + ' &middot; ' + esc(sess.project || '') +
        ' (' + esc(sess.tool || '') + ') &middot; ' + ago(a.created_at) + '</div></div>' +
        '<button class="ok" onclick="decide(\\'' + a.id + '\\',\\'approved\\')">Approve</button>' +
        '<button class="no" onclick="decide(\\'' + a.id + '\\',\\'denied\\')">Deny</button></div>';
    }).join('');
  }

  document.getElementById('fleet').innerHTML = state.sessions.map(function(s){
    return '<div class="card"><div class="tool">' + esc(s.tool) + '</div>' +
      '<h3>' + esc(s.project) + '</h3>' +
      '<span class="chip ' + esc(s.status) + '">' + esc(s.status) + '</span>' +
      '<p class="task">' + esc(s.task || '(no task recorded)') + '</p>' +
      '<div class="row"><span>last activity</span><b>' + ago(s.last_activity) + '</b></div>' +
      '<div class="row"><span>tokens</span><b>' + Number(s.tokens||0).toLocaleString() + '</b></div>' +
      '<div class="row"><span>cost (est.)</span><b>' + money(s.cost_usd) + '</b></div>' +
      '<div class="row"><span></span><button onclick="brief(\\'' + encodeURIComponent(s.id) + '\\')">Handoff brief</button></div></div>';
  }).join('') || '<div class="empty">No agent sessions discovered yet. Start Claude Code or Codex, or run with --demo.</div>';
}

async function decide(id, decision){
  await fetch('/api/approvals/' + encodeURIComponent(id) + '/decide', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({decision: decision})
  });
  refresh();
}

async function brief(id){
  const r = await fetch('/api/brief/' + id);
  const txt = await r.text();
  document.getElementById('brief-wrap').innerHTML =
    '<h2>Handoff brief</h2><pre class="brief">' + esc(txt) + '</pre>';
  document.getElementById('brief-wrap').scrollIntoView({behavior:'smooth'});
}

document.addEventListener('keydown', function(e){
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  const k = e.key.toLowerCase();
  if (k === 'r') refresh();
  if (k === 'j') { state.sel = Math.min(state.sel + 1, state.approvals.length - 1); refresh(); }
  if (k === 'k') { state.sel = Math.max(state.sel - 1, 0); refresh(); }
  if (k === 'a' && state.approvals[state.sel]) decide(state.approvals[state.sel].id, 'approved');
  if (k === 'd' && state.approvals[state.sel]) decide(state.approvals[state.sel].id, 'denied');
  if (k === 'b' && state.sessions.length) brief(encodeURIComponent(state.sessions[0].id));
});

refresh();
setInterval(refresh, 2000);
</script>
</body></html>
"""


def render_dashboard() -> str:
    return PAGE
