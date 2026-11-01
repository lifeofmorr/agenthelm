/* ============================================================
   CINEMATIC KIT v3 — behavior layer (companion to cinematic.css)
   Progressive enhancement: pages are complete without this file.

   The script tag carries the per-business skin:
     <script src="cinematic/cinematic.js" defer
        data-hero="assets/hero-cine.svg"
        data-accent="#2997ff" data-accent-2="#64d2ff"
        data-pos="68% 50%"></script>

   It: marks <body class="cine">, builds the hero stage (render
   layer + scrim + accent glow + vignette + grain) inside the
   first .hero, runs scroll + pointer parallax on the layers,
   adds pointer-tracked 3D tilt to cards, reveal choreography on
   pages that don't already run the v2 .reveal system, and the
   nav scroll shadow. Touch and reduced-motion get the still,
   fully-legible version.
   ============================================================ */
(function () {
  var me = document.currentScript;
  var cfg = (me && me.dataset) || {};
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var finePointer = window.matchMedia('(pointer: fine)').matches;
  document.body.classList.add('cine');

  /* ---------- hero stage ---------- */
  var hero = document.querySelector('.hero');
  if (hero && cfg.hero) {
    hero.classList.add('cine-hero');
    /* skin vars go on the HERO (every hero descendant inherits them),
       and on the stage for its own glow layer */
    if (cfg.accent) hero.style.setProperty('--cine-accent', cfg.accent);
    if (cfg.accent2) hero.style.setProperty('--cine-accent-2', cfg.accent2);
    var stage = document.createElement('div');
    stage.className = 'cine-stage';
    stage.setAttribute('aria-hidden', 'true');
    if (cfg.accent) stage.style.setProperty('--cine-accent', cfg.accent);
    if (cfg.accent2) stage.style.setProperty('--cine-accent-2', cfg.accent2);
    if (cfg.pos) stage.style.setProperty('--cine-pos', cfg.pos);
    stage.innerHTML =
      '<div class="cine-layer" data-depth="0.05"><img src="' + cfg.hero + '" alt="" fetchpriority="high"></div>' +
      '<div class="cine-scrim"></div>' +
      '<div class="cine-glow" data-depth="0.02"></div>' +
      '<div class="cine-vignette"></div>' +
      '<div class="cine-grain"></div>';
    hero.insertBefore(stage, hero.firstChild);

    /* full-bleed escape when the hero sits inside a container */
    var r = hero.getBoundingClientRect();
    if (r.width < window.innerWidth - 24) stage.classList.add('cine-bleed');

    if (!reduced) {
      var layers = stage.querySelectorAll('[data-depth]');
      var px = 0, py = 0, tx = 0, ty = 0, ticking = false;
      function render() {
        ticking = false;
        var rect = hero.getBoundingClientRect();
        var prog = Math.max(-1, Math.min(1, -rect.top / Math.max(1, rect.height)));
        layers.forEach(function (l) {
          var d = parseFloat(l.getAttribute('data-depth'));
          var y = prog * d * 220 + ty * d * 260;
          var x = tx * d * 260;
          l.style.transform = 'translate3d(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px,0)';
        });
      }
      function queue() { if (!ticking) { ticking = true; requestAnimationFrame(render); } }
      window.addEventListener('scroll', queue, { passive: true });
      window.addEventListener('resize', queue);
      if (finePointer) {
        hero.addEventListener('pointermove', function (e) {
          var b = hero.getBoundingClientRect();
          tx = (e.clientX - b.left) / b.width - 0.5;
          ty = (e.clientY - b.top) / b.height - 0.5;
          queue();
        });
        hero.addEventListener('pointerleave', function () { tx = 0; ty = 0; queue(); });
      }
      queue();
    }
  }

  /* ---------- 3D tilt cards ---------- */
  if (finePointer && !reduced) {
    var cards = document.querySelectorAll(
      '.card, .window, .panel, .widget-slot, .step, .plan, .tier, .price-card');
    cards.forEach(function (el) {
      el.classList.add('cine-tilt');
      var raf = null;
      el.addEventListener('pointermove', function (e) {
        var b = el.getBoundingClientRect();
        var x = (e.clientX - b.left) / b.width, y = (e.clientY - b.top) / b.height;
        el.style.setProperty('--cine-mx', (x * 100).toFixed(1) + '%');
        el.style.setProperty('--cine-my', (y * 100).toFixed(1) + '%');
        if (raf) return;
        raf = requestAnimationFrame(function () {
          raf = null;
          el.classList.add('cine-tilting');
          el.style.transform = 'perspective(1100px) rotateX(' +
            ((0.5 - y) * 6).toFixed(2) + 'deg) rotateY(' +
            ((x - 0.5) * 8).toFixed(2) + 'deg) translateY(-3px)';
        });
      });
      el.addEventListener('pointerleave', function () {
        if (raf) cancelAnimationFrame(raf);
        raf = null;
        el.classList.remove('cine-tilting');
        el.style.transform = '';
      });
    });
  }

  /* ---------- reveal choreography (skip pages on the v2 system) ---------- */
  if (!document.querySelector('.reveal') && 'IntersectionObserver' in window && !reduced) {
    var targets = document.querySelectorAll('section .card, section .step, .sec-head');
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('cine-in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    targets.forEach(function (el) { el.setAttribute('data-cine-reveal', ''); io.observe(el); });
  }

  /* ---------- nav scroll shadow ---------- */
  var nav = document.querySelector('header.site');
  if (nav) {
    var onScroll = function () {
      nav.classList.toggle('cine-scrolled', window.scrollY > 24);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }
})();
