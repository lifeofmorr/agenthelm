/* ============================================================
   CINE MODULE — SIM (process visualizer / simulator)
   Archetype 3 of the Cinematic Kit interactive library.
   The visitor operates the product's workflow: play / pause,
   speed, scrub, and — where the product has approvals — clear
   the decisions that stall the work. Dependency-free.

   Determinism: agent state is a pure function of (sim time,
   approval times). Scrubbing backwards discards later
   approvals and replays from zero, so the board never lies
   about how it got somewhere.

   All fleet data comes from config and is demo data — the
   mount face carries the Demo chip and demoNote. Token counts
   are illustrative arithmetic (rate × working seconds), never
   presented as live usage.

   Mount / config contract: see modules/README.md.
   ============================================================ */
(function () {
  "use strict";
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function clock(t) {
    var m = Math.floor(t / 60), s = Math.floor(t % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function mount(root) {
    var cfgNode = root.querySelector(".cine-mod-config");
    if (!cfgNode) return;
    var cfg;
    try { cfg = JSON.parse(cfgNode.textContent); } catch (e) { return; }
    var duration = cfg.duration || 120;
    var agentsCfg = cfg.agents || [];
    if (!agentsCfg.length) return;

    var panel = el("div", "cmod-panel");
    if (cfg.eyebrow) panel.appendChild(el("p", "cmod-eyebrow", cfg.eyebrow));
    if (cfg.title) panel.appendChild(el("h3", "cmod-title", cfg.title));
    if (cfg.intro) panel.appendChild(el("p", "cmod-intro", cfg.intro));
    panel.appendChild(el("span", "cmod-demo", "Interactive demo"));

    /* ---- controls ---- */
    var controls = el("div", "cmod-sim-controls");
    var playBtn = el("button", "cmod-btn", "▶ Play");
    playBtn.type = "button";
    controls.appendChild(playBtn);
    var seg = el("div", "cmod-seg");
    var speeds = [0.5, 1, 2], speed = 1, segBtns = [];
    speeds.forEach(function (sp) {
      var b = el("button", sp === 1 ? "on" : "", sp + "×");
      b.type = "button";
      b.setAttribute("aria-label", "Speed " + sp + "×");
      b.addEventListener("click", function () {
        speed = sp;
        segBtns.forEach(function (x) { x.classList.remove("on"); });
        b.classList.add("on");
      });
      segBtns.push(b); seg.appendChild(b);
    });
    controls.appendChild(seg);
    var scrub = document.createElement("input");
    scrub.type = "range"; scrub.min = 0; scrub.max = duration; scrub.step = 0.5; scrub.value = 0;
    scrub.setAttribute("aria-label", "Scrub the session clock");
    controls.appendChild(scrub);
    var clockElm = el("span", "cmod-clock", "0:00 / " + clock(duration));
    controls.appendChild(clockElm);
    panel.appendChild(controls);

    /* ---- board ---- */
    var board = el("div", "cmod-sim-board");
    var rows = {};
    agentsCfg.forEach(function (a) {
      var row = el("div", "cmod-agent");
      var name = el("div", "cmod-agent-name");
      name.appendChild(el("strong", "", a.name));
      name.appendChild(el("span", "cmod-agent-tool", a.tool));
      row.appendChild(name);
      row.appendChild(el("p", "cmod-agent-task", a.task));
      var track = el("div", "cmod-track");
      var fillBar = el("div", "cmod-track-fill");
      track.appendChild(fillBar);
      row.appendChild(track);
      var note = el("p", "cmod-agent-note", "Queued");
      row.appendChild(note);
      var pill = el("span", "cmod-pill queued", "Queued");
      row.appendChild(pill);
      board.appendChild(row);
      rows[a.id] = { row: row, fill: fillBar, note: note, pill: pill };
    });
    panel.appendChild(board);

    var inbox = el("div", "cmod-inbox");
    panel.appendChild(inbox);
    var meta = el("p", "cmod-sim-meta", "");
    panel.appendChild(meta);

    if (cfg.cta) {
      var ctaRow = el("div", "cmod-cta-row");
      var a = el("a", "cmod-cta", cfg.cta.label);
      a.href = cfg.cta.href;
      ctaRow.appendChild(a);
      if (cfg.cta.note) ctaRow.appendChild(el("span", "cmod-cta-note", cfg.cta.note));
      panel.appendChild(ctaRow);
    }
    if (cfg.demoNote) panel.appendChild(el("p", "cmod-note", cfg.demoNote));
    root.appendChild(panel);

    /* ---- simulation core ---- */
    var approvals = {}; // blockId -> sim time approved
    var time = 0, playing = false, state = null;

    function freshState() {
      var s = {};
      agentsCfg.forEach(function (a) {
        s[a.id] = {
          cfg: a, progress: 0, mode: "working",
          block: null, blocksDone: {}, stallUsed: false,
          stallUntil: 0, doneAt: null, stalls: 0
        };
      });
      return s;
    }

    function stepAgent(st, now, dt) {
      var a = st.cfg;
      if (st.mode === "done") return;
      if (st.mode === "waiting") {
        if (st.block && approvals[st.block.id] != null && approvals[st.block.id] <= now + dt) {
          st.blocksDone[st.block.id] = true;
          st.block = null;
          st.mode = "working";
        } else return;
      }
      if (st.mode === "stalled") {
        if (now >= st.stallUntil) st.mode = "working"; else return;
      }
      if (st.mode !== "working") return;
      var room = dt;
      // next trigger within reach?
      var nextBlock = null;
      (a.blocks || []).forEach(function (b) {
        if (!st.blocksDone[b.id] && st.block !== b) {
          var at = b.at * a.work;
          if (st.progress < at && st.progress + room >= at) {
            if (!nextBlock || at < nextBlock.at) nextBlock = { b: b, at: at };
          }
          if (st.progress >= at && !st.blocksDone[b.id] && approvals[b.id] == null) {
            // already at/past threshold without approval (can happen after scrub) — block now
            st.mode = "waiting"; st.block = b; return;
          }
        }
      });
      if (st.mode !== "working") return;
      var stallAt = a.stall ? a.stall.at * a.work : Infinity;
      if (nextBlock && nextBlock.at <= stallAt) {
        st.progress = nextBlock.at;
        st.mode = "waiting"; st.block = nextBlock.b;
        return;
      }
      if (!st.stallUsed && isFinite(stallAt) && st.progress < stallAt && st.progress + room >= stallAt) {
        st.progress = stallAt;
        st.mode = "stalled"; st.stallUsed = true; st.stalls++;
        st.stallUntil = now + a.stall.dur;
        return;
      }
      st.progress = Math.min(a.work, st.progress + room);
      if (st.progress >= a.work) { st.mode = "done"; st.doneAt = now; }
    }

    function compute(target) {
      state = freshState();
      var t = 0, dt = 0.25;
      while (t < target) {
        var step = Math.min(dt, target - t);
        agentsCfg.forEach(function (a) { stepAgent(state[a.id], t, step); });
        t += step;
      }
      return state;
    }

    function tokensTotal() {
      var total = 0;
      agentsCfg.forEach(function (a) { total += state[a.id].progress * (a.rate || 0); });
      return Math.round(total);
    }

    function render() {
      var waiting = [], doneCount = 0, stalls = 0;
      agentsCfg.forEach(function (a) {
        var st = state[a.id], r = rows[a.id];
        var pct = Math.min(100, st.progress / a.work * 100);
        r.fill.style.width = pct + "%";
        var pillCls = "cmod-pill ", pillTxt = "", note = "";
        if (st.mode === "working") { pillCls += "working"; pillTxt = "Working"; note = "On task — " + Math.round(pct) + "% through."; }
        if (st.mode === "waiting") {
          pillCls += "waiting"; pillTxt = "Waiting on you";
          note = "Asked: " + (st.block ? st.block.label : "");
          waiting.push(st);
        }
        if (st.mode === "stalled") { pillCls += "stalled"; pillTxt = "Stalled"; note = "No output — the board flags it instead of letting it burn quietly."; }
        if (st.mode === "done") { pillCls += "done"; pillTxt = "Done"; note = "Done at " + clock(st.doneAt || 0) + " — handoff brief written for the next agent."; doneCount++; }
        stalls += st.stalls;
        r.pill.className = pillCls; r.pill.textContent = pillTxt;
        r.note.textContent = note;
      });

      inbox.innerHTML = "";
      if (waiting.length) {
        inbox.appendChild(el("p", "cmod-inbox-title", "Approvals inbox — " + waiting.length + " waiting"));
        waiting.forEach(function (st) {
          var item = el("div", "cmod-inbox-item");
          var txt = el("p", "cmod-inbox-text", "");
          txt.appendChild(el("strong", "", st.cfg.name + " · "));
          txt.appendChild(document.createTextNode(st.block ? st.block.label : ""));
          item.appendChild(txt);
          var btn = el("button", "cmod-btn small", "Approve");
          btn.type = "button";
          btn.setAttribute("data-approve", st.block ? st.block.id : "");
          btn.addEventListener("click", function () {
            if (!st.block) return;
            approvals[st.block.id] = time;
            compute(time);
            render();
          });
          item.appendChild(btn);
          inbox.appendChild(item);
        });
      }

      var cleared = Object.keys(approvals).length;
      var allDone = doneCount === agentsCfg.length;
      meta.textContent =
        "Clock " + clock(time) + " · " + tokensTotal().toLocaleString("en-US") + " tokens burned" +
        " · " + doneCount + " of " + agentsCfg.length + " agents done" +
        " · " + cleared + " decision" + (cleared === 1 ? "" : "s") + " cleared" +
        (stalls ? " · " + stalls + " stall" + (stalls === 1 ? "" : "s") + " flagged" : "") +
        (allDone ? " · Session complete — every brief is written." : "");
      clockElm.textContent = clock(time) + " / " + clock(duration);
      if (document.activeElement !== scrub) scrub.value = time;
      playBtn.textContent = playing ? "❚❚ Pause" : (time > 0 && !allDone ? "▶ Resume" : "▶ Play");
      if (allDone) { playing = false; playBtn.textContent = "↺ Replay"; }
    }

    /* ---- transport ---- */
    var lastTs = null;
    function loop(ts) {
      if (!playing) return;
      if (lastTs == null) lastTs = ts;
      var dtReal = (ts - lastTs) / 1000;
      lastTs = ts;
      var next = Math.min(duration, time + dtReal * speed * 4); // 4 sim-s per real-s at 1×
      time = next;
      compute(time);
      render();
      if (time >= duration || agentsCfg.every(function (a) { return state[a.id].mode === "done"; })) {
        playing = false; render(); return;
      }
      requestAnimationFrame(loop);
    }
    function setPlaying(p) {
      if (p && agentsCfg.every(function (a) { return state && state[a.id].mode === "done"; })) {
        // replay from zero
        approvals = {}; time = 0;
      }
      playing = p;
      lastTs = null;
      if (p) requestAnimationFrame(loop);
      render();
    }
    playBtn.addEventListener("click", function () { setPlaying(!playing); });
    scrub.addEventListener("input", function () {
      var v = Number(scrub.value);
      if (v < time) {
        Object.keys(approvals).forEach(function (k) { if (approvals[k] > v) delete approvals[k]; });
      }
      time = v;
      compute(time);
      render();
    });

    compute(0);
    render();

    if (!reduced && "IntersectionObserver" in window) {
      var seen = false;
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting && !seen) { seen = true; setPlaying(true); io.disconnect(); }
        });
      }, { threshold: 0.35 });
      io.observe(panel);
    }

    root._cineSim = {
      play: function () { setPlaying(true); },
      pause: function () { setPlaying(false); },
      scrubTo: function (t) { time = Math.max(0, Math.min(duration, t)); compute(time); render(); },
      approveFirst: function () {
        var btn = inbox.querySelector("[data-approve]");
        if (btn) { btn.click(); return true; }
        return false;
      },
      state: function () {
        var agents = {};
        agentsCfg.forEach(function (a) {
          agents[a.id] = { mode: state[a.id].mode, progress: state[a.id].progress };
        });
        return { time: time, approvals: approvals, tokens: tokensTotal(), agents: agents };
      }
    };
  }

  document.querySelectorAll('[data-cine-mod="sim"]').forEach(mount);
})();
