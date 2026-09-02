document.documentElement.classList.add('nit-js');
/* ============================================================================
   nit-reveal.js — the shared entrance primitive
   ----------------------------------------------------------------------------
   Every brick's scroll reveal goes through this one module. It adds
   .is-revealed once, at 20% visibility, and then stops observing.

   Motion itself lives entirely in CSS (nit-base.css), which means
   prefers-reduced-motion is handled by the token layer without this file
   knowing anything about it. Nothing here reads or branches on motion
   preference; it only ever toggles a class.

   Staggering is expressed as calc(var(--stagger) * n) rather than a computed
   millisecond value, so the reduced-motion override that sets --stagger to 0
   flattens the whole sequence for free.
   ========================================================================== */

const ITEM = '.nit-reveal';
const GROUP = '[data-nit-stagger]';
const STAGGER_CAP = 6;
const THRESHOLD = 0.2;

/* An element taller than most of the viewport can never reach 20% visibility
   while scrolling into view, so it reveals on first contact instead. */
const TALL_RATIO = 0.6;

let observer = null;

function reveal(el) {
  el.classList.add('is-revealed');
}

function getObserver() {
  if (observer) return observer;

  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;

        const tall =
          entry.boundingClientRect.height > window.innerHeight * TALL_RATIO;

        if (tall || entry.intersectionRatio >= THRESHOLD) {
          reveal(entry.target);
          observer.unobserve(entry.target);
        }
      }
    },
    { threshold: [0, THRESHOLD] }
  );

  return observer;
}

function applyStagger(root) {
  for (const group of root.querySelectorAll(GROUP)) {
    let index = 0;
    for (const child of group.children) {
      if (!child.classList.contains('nit-reveal')) continue;
      const step = Math.min(index, STAGGER_CAP - 1);
      child.style.setProperty('--nit-delay', `calc(var(--stagger) * ${step})`);
      index += 1;
    }
  }
}

/**
 * Observe every unrevealed item inside `root`. Safe to call repeatedly —
 * later bricks call it after injecting markup (mobile menu, cart drawer).
 */
export function initReveal(root = document) {
  applyStagger(root);

  const items = root.querySelectorAll(`${ITEM}:not(.is-revealed)`);
  if (!items.length) return;

  if (!('IntersectionObserver' in window)) {
    items.forEach(reveal);
    return;
  }

  const io = getObserver();
  items.forEach((el) => io.observe(el));
}

/* Other bricks ask for a re-scan by event rather than by import. Shopify serves
   assets with a ?v= cache key, so a relative `import './nit-reveal.js'` would
   resolve to a second URL and evaluate this module twice. One listener, one
   observer, one module instance. */
document.addEventListener('nit:reveal', (event) => {
  initReveal(event.detail?.root ?? document);
});

initReveal();

/* ============================================================================
   nit-header.js — Brick 02

   Three jobs, one scroll listener:
     1. Go solid past 80px.
     2. Hide on scroll down, return on scroll up — desktop only.
     3. Open and close the mobile menu.

   The menu is a native <dialog>. showModal() gives a focus trap, Escape
   handling and an inert background for free, so none of that is here.
   ========================================================================== */

const header = document.querySelector('[data-nit-header]');

if (header) {
  const SOLID_AT = 80; // px, per BRIEF.md brick 02
  const AUTOHIDE_MIN_WIDTH = 900; // below this the header stays put
  const DIRECTION_NOISE = 4; // ignore sub-pixel and trackpad jitter

  const autoHide = header.hasAttribute('data-nit-autohide');
  const desktop = matchMedia(`(min-width: ${AUTOHIDE_MIN_WIDTH}px)`);
  const calm = matchMedia('(prefers-reduced-motion: reduce)');

  let lastY = window.scrollY;
  let ticking = false;

  function update() {
    ticking = false;
    const y = window.scrollY;

    header.classList.toggle('is-stuck', y > SOLID_AT);

    /* A sliding header is movement, so it is withheld from anyone who asked for
       reduced motion — they keep a header that is simply always there. */
    const mayHide = autoHide && desktop.matches && !calm.matches;

    if (!mayHide) {
      header.classList.remove('is-hidden');
      lastY = y;
      return;
    }

    const delta = y - lastY;
    if (Math.abs(delta) > DIRECTION_NOISE) {
      /* Hiding starts well below the point the header goes solid. Sharing one
         threshold meant crossing 80px painted the bar solid and then slid it
         straight off screen — a visible flash of a header that immediately
         leaves. Three header heights is far enough down that going solid and
         hiding read as two separate, deliberate events. */
      const hideAfter = header.offsetHeight * 3;
      header.classList.toggle('is-hidden', delta > 0 && y > hideAfter);
      lastY = y;
    }
  }

  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(update);
  }

  addEventListener('scroll', onScroll, { passive: true });
  desktop.addEventListener('change', update);
  update();

  /* --- Menu --------------------------------------------------------------- */

  const dialog = document.querySelector('[data-nit-menu]');
  const openBtn = document.querySelector('[data-nit-menu-open]');

  if (dialog && openBtn) {
    const setExpanded = (open) =>
      openBtn.setAttribute('aria-expanded', String(open));

    /* Cleanup is a function called directly on every close path, not something
       hung off the dialog's `close` event alone. If that event failed to fire
       the page would stay scroll-locked with no way out — the worst failure
       this component can have, and the one least likely to be noticed in
       testing. The `close` listener stays as a backstop; it is idempotent. */
    function closeMenu() {
      if (dialog.open) dialog.close();
      setExpanded(false);
      document.documentElement.style.overflow = '';
      openBtn.focus();
    }

    openBtn.addEventListener('click', () => {
      dialog.showModal();
      setExpanded(true);
      // Scroll behind a modal dialog is not blocked consistently across
      // browsers, so it is pinned explicitly.
      document.documentElement.style.overflow = 'hidden';
      // Re-run the entrance so the links stagger in each time it opens.
      for (const item of dialog.querySelectorAll('.nit-reveal')) {
        item.classList.remove('is-revealed');
      }
      void dialog.offsetWidth;
      document.dispatchEvent(
        new CustomEvent('nit:reveal', { detail: { root: dialog } })
      );
    });

    // Escape is the one close path the browser owns. Handling the keydown
    // ourselves means the cleanup runs on it too, without waiting on `close`.
    dialog.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      closeMenu();
    });

    dialog.addEventListener('close', closeMenu);

    dialog
      .querySelector('[data-nit-menu-close]')
      ?.addEventListener('click', closeMenu);

    // Following a link closes the menu; without this the page changes
    // underneath an open modal.
    for (const link of dialog.querySelectorAll('a')) {
      link.addEventListener('click', closeMenu);
    }

    // Crossing into the desktop layout hides the dialog in CSS, which would
    // otherwise leave a modal open and the page scroll-locked.
    matchMedia('(min-width: 750px)').addEventListener('change', (event) => {
      if (event.matches && dialog.open) closeMenu();
    });
  }
}

/* ============================================================================
   nit-hero.js — Brick 03

   One job: attach the optional product loop after the page has finished
   loading, so it can never compete with the hero image for bandwidth or delay
   the largest contentful paint.

   The line reveal is not here. It runs on load, which CSS animations already
   do, so it costs no JavaScript.
   ========================================================================== */

const hero = document.querySelector('[data-nit-hero]');
const template = hero?.querySelector('[data-nit-hero-video]');

if (template) {
  const calm = matchMedia('(prefers-reduced-motion: reduce)');

  /* Three reasons never to fetch the loop, all decided before a byte moves:
     the visitor asked for reduced motion, the visitor asked the browser to save
     data, or the connection is slow enough that a decorative video is an
     insult. In every case the still is already correct and stays. */
  function wanted() {
    if (calm.matches) return false;
    const net = navigator.connection;
    if (!net) return true;
    if (net.saveData) return false;
    return !/2g/.test(net.effectiveType || '');
  }

  function attach() {
    if (!wanted()) return;

    const video = template.content.firstElementChild.cloneNode(true);
    template.parentElement.appendChild(video);
    video.preload = 'auto';

    /* Autoplay can be refused, the file can be missing, the codec can be
       unsupported. Any of those and the video removes itself, leaving the still
       that was doing the job perfectly well already. */
    video
      .play()
      .then(() => video.classList.add('is-playing'))
      .catch(() => video.remove());

    video.addEventListener('error', () => video.remove(), { once: true });
  }

  /* Wait for load, then for the browser to be idle. requestIdleCallback is
     absent in Safari, where a short timeout is close enough. */
  function whenIdle(fn) {
    if ('requestIdleCallback' in window) requestIdleCallback(fn, { timeout: 2000 });
    else setTimeout(fn, 200);
  }

  if (document.readyState === 'complete') whenIdle(attach);
  else addEventListener('load', () => whenIdle(attach), { once: true });
}

/* ============================================================================
   nit-assurance.js — Brick 04

   One job: the pause control.

   WCAG 2.2.2 Pause, Stop, Hide requires a mechanism to stop content that moves
   for more than five seconds. Hover is not that mechanism — it is unreachable
   by keyboard, and unreachable by touch, which is the only platform this
   marquee runs on. So there is a real button, and this file makes it work.

   Pausing on hover and focus-within is handled in CSS, where it belongs.
   ========================================================================== */

for (const strip of document.querySelectorAll('[data-nit-marquee]')) {
  const toggle = strip.querySelector('[data-nit-marquee-toggle]');
  if (!toggle) continue;

  const iconPause = toggle.querySelector('[data-nit-marquee-icon-pause]');
  const iconPlay = toggle.querySelector('[data-nit-marquee-icon-play]');
  const label = toggle.querySelector('[data-nit-marquee-label]');

  /* Read from the DOM rather than tracking state in a variable: CSS can pause
     the animation too, and two sources of truth would drift. */
  const pauseText = label?.textContent.trim() || 'Pause';
  const playText = pauseText.replace(/^Pause/i, 'Resume');

  toggle.addEventListener('click', () => {
    const paused = strip.classList.toggle('is-paused');

    toggle.setAttribute('aria-pressed', String(paused));
    iconPause?.classList.toggle('is-hidden', paused);
    iconPlay?.classList.toggle('is-hidden', !paused);
    if (label) label.textContent = paused ? playText : pauseText;
  });
}

/* ============================================================================
   nit-anatomy.js — Brick 06

   Watches four sentinels spaced down the tall scroller and latches each
   annotation on as its sentinel crosses the middle of the viewport. Steps
   accumulate, so the diagram finishes fully annotated.

   Why one observer rather than CSS scroll-driven animation with this as a
   fallback: the sequence is discrete, not continuous. Two paths for one
   behaviour would leave the Firefox path — no scroll-driven support there — as
   the least exercised one. See the note in sections/nit-anatomy.liquid.

   Nothing here reads scroll position, measures layout, or runs on every frame.
   The observer fires a handful of times in total and only toggles classes;
   every pixel of movement is a CSS transition on opacity and transform.
   ========================================================================== */

const DESKTOP = '(min-width: 900px)';

for (const section of document.querySelectorAll('[data-nit-anatomy]')) {
  const spots = [...section.querySelectorAll('[data-nit-anatomy-spot]')];
  const rail = [...section.querySelectorAll('[data-nit-anatomy-rail]')];
  const sentinels = [...section.querySelectorAll('[data-nit-anatomy-sentinel]')];
  const list = section.querySelector('[data-nit-anatomy-spots]');
  if (!spots.length) continue;

  const desktop = matchMedia(DESKTOP);
  const calm = matchMedia('(prefers-reduced-motion: reduce)');

  /* Below 900px the hotspot list is a horizontally scrolling region, which
     needs a name and to be keyboard reachable. Above it, the same element is a
     static overlay — where a tab stop leading nowhere and a label describing a
     swipe nobody can perform are both noise.

     role is never touched. An earlier version removed it on desktop, which
     stripped the authored role="list" — and since list-style is none here,
     Safari drops list semantics entirely without it. Only the two attributes
     that genuinely differ between layouts are toggled. */
  function syncListSemantics() {
    if (!list) return;
    if (desktop.matches) {
      list.removeAttribute('tabindex');
      list.removeAttribute('aria-label');
    } else {
      list.setAttribute('tabindex', '0');
      if (list.dataset.label) list.setAttribute('aria-label', list.dataset.label);
    }
  }

  // Preserve the authored label before the first removal can discard it.
  if (list && list.getAttribute('aria-label')) {
    list.dataset.label = list.getAttribute('aria-label');
  }

  function setStep(index) {
    spots.forEach((spot, i) => spot.classList.toggle('is-revealed', i <= index));
    rail.forEach((step, i) => step.classList.toggle('is-current', i === index));
  }

  function revealAll() {
    spots.forEach((spot) => spot.classList.add('is-revealed'));
    rail.forEach((step) => step.classList.add('is-current'));
  }

  let observer = null;

  function observe() {
    if (observer || !sentinels.length) return;

    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          setStep(Number(entry.target.dataset.nitAnatomySentinel));
        }
      },
      /* A band one pixel tall across the middle of the viewport: a sentinel
         intersects it at the moment it crosses the centre line. */
      { rootMargin: '-50% 0px -50% 0px', threshold: 0 }
    );

    sentinels.forEach((s) => observer.observe(s));
  }

  function unobserve() {
    observer?.disconnect();
    observer = null;
  }

  function apply() {
    syncListSemantics();

    /* Reduced motion, no observer support, or the card layout — in all three
       the whole diagram is simply present. On mobile the cards scroll rather
       than reveal, so a partially hidden set would hide content behind a
       gesture nobody was told to make. */
    if (calm.matches || !('IntersectionObserver' in window) || !desktop.matches) {
      unobserve();
      revealAll();
      return;
    }

    setStep(-1);
    observe();
  }

  desktop.addEventListener('change', apply);
  calm.addEventListener('change', apply);
  apply();
}

/* ============================================================================
   nit-360.js — the turntable viewer
   ----------------------------------------------------------------------------
   Frames shot at even angular intervals, swapped under the pointer. Nothing
   here is 3D: a 360 spin is a flipbook, and treating it as one keeps it to a
   canvas and a frame index instead of a renderer.

   MODES. data-nit-360-src carries a URL with an {i} token — the frame number,
   zero-padded to data-nit-360-pad. Given one, the viewer preloads every frame
   and plays photographs. Left empty, it draws a schematic turntable and
   reports the angle each frame is waiting for, so the control can be judged,
   and the shoot specified, before a single frame has been taken.

   MOTION. The intro spin exists because a still frame gives no hint that it
   turns. It is one rotation, it stops itself, and any interaction cancels it —
   so it never becomes motion the user cannot stop (WCAG 2.2.2). Under
   prefers-reduced-motion it does not run at all, and inertia is switched off
   with it: the frame then follows the finger exactly and stops when it stops.

   Angle is the state; the frame index is derived from it. Keeping it that way
   means drag, keys, inertia and the intro all write to one number, and the
   frame count can change without touching any of them.
   ========================================================================== */

{
  const ROOT = '[data-nit-360]';
  const TAU = Math.PI * 2;

  /* Behavioural constants. Durations that CSS can see live in the token layer;
     these govern the gesture itself and have no CSS counterpart. */
  const SWEEP = 0.9; /* fraction of the stage width that turns it once */
  const FRICTION = 0.92; /* per-frame inertia decay */
  const MIN_SPIN = 0.02; /* deg/frame below which inertia is finished */
  /* deg/frame. Capped low on purpose: the coast after release is roughly
     CAP * FRICTION / (1 - FRICTION), so 6 settles within about a
     quarter-turn. A faster flick spins past the angle the shopper was
     reaching for, which reads as the control fighting them. */
  const FLING_CAP = 6;
  const KEY_STEP = 1; /* frames per arrow press */
  const INTRO_MS = 2400; /* one unhurried rotation */
  const ANNOUNCE_MS = 400; /* settle before speaking, or arrows chatter */

  const calm = matchMedia('(prefers-reduced-motion: reduce)');

  function mod(n, m) {
    return ((n % m) + m) % m;
  }

  /* Tokens are read off the element rather than written here, so the one rule
     that matters — no raw colour outside nit-tokens.css — survives a module
     that has to paint pixels itself. */
  function palette(el) {
    const cs = getComputedStyle(el);
    return {
      hairline: cs.getPropertyValue('--hairline-hi').trim(),
      faint: cs.getPropertyValue('--text-faint').trim(),
      accent: cs.getPropertyValue('--accent').trim(),
    };
  }

  function build(el) {
    /* getAttribute, not dataset. A data- name whose dash precedes a digit is
       not folded into camelCase — data-nit-360-frames arrives as
       dataset['nit-360Frames'], which no property access will ever find. Read
       the attributes by their real names and the trap disappears. */
    const attr = function (name, fallback) {
      const v = el.getAttribute('data-nit-360-' + name);
      return v === null || v === '' ? fallback : v;
    };

    const frames = Math.max(2, parseInt(attr('frames', ''), 10) || 36);
    const template = attr('src', '').trim();
    const poster = attr('poster', '').trim();
    const pad = parseInt(attr('pad', ''), 10) || 0;
    const reverse = el.hasAttribute('data-nit-360-reverse');

    /* Three states, one component, in order of what has actually been shot:
       frames once the turntable exists, poster while only a single still
       does, schematic while there is neither. A poster is not a degraded
       360 — it does not pretend to turn, so it takes no drag handlers, no
       hint and no focus stop. Adding data-nit-360-src is the whole upgrade. */
    const mode = template ? 'frames' : poster ? 'poster' : 'schematic';
    const spins = mode !== 'poster';
    const step = 360 / frames;

    el.setAttribute('data-nit-360-mode', mode);
    el.setAttribute('role', 'img');
    if (spins) el.setAttribute('tabindex', '0');
    el.setAttribute(
      'aria-label',
      attr('label', 'Product shown from every angle')
    );

    const canvas = document.createElement('canvas');
    canvas.className = 'nit-360__canvas';
    el.append(canvas);
    const ctx = canvas.getContext('2d');

    const overlay = document.createElement('div');
    overlay.className = 'nit-360__overlay';

    if (mode === 'schematic') {
      const spec = document.createElement('div');
      spec.className = 'nit-360__spec';
      const slot = document.createElement('p');
      slot.className = 'nit-label';
      slot.textContent = attr('slot', '360');
      const shot = document.createElement('p');
      shot.className = 'nit-360__shot nit-small';
      shot.textContent = attr('shot', '');
      const dims = document.createElement('p');
      dims.className = 'nit-label nit-360__dims nit-nums';
      dims.textContent = attr('dims', '');
      spec.append(slot, shot, dims);
      overlay.append(spec);
    }

    const hint = spins ? document.createElement('p') : null;
    if (hint) {
      hint.className = 'nit-label nit-360__hint';
      hint.innerHTML =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" ' +
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="M3 12h18"/><path d="M7 8l-4 4 4 4"/><path d="M17 8l4 4-4 4"/></svg>' +
        '<span>Drag to rotate</span>';
      overlay.append(hint);
    }
    el.append(overlay);

    let readout = null;
    if (mode === 'schematic') {
      readout = document.createElement('p');
      readout.className = 'nit-label nit-360__readout nit-nums';
      el.append(readout);
    }

    /* Keyboard users get the angle spoken; drag users would be interrupted by
       it constantly, so only the settled value is ever announced. A poster has
       no angle to report, so it gets no live region to leave sitting empty. */
    const live = document.createElement('span');
    if (spins) {
      live.className = 'nit-visually-hidden';
      live.setAttribute('aria-live', 'polite');
      el.append(live);
    }

    let progress = null;
    if (mode === 'frames') {
      progress = document.createElement('div');
      progress.className = 'nit-360__progress';
      el.append(progress);
    }

    let colors = palette(el);
    let angle = 0; /* degrees, the single source of truth */
    let spin = 0; /* deg per frame, inertia */
    let width = 0;
    let height = 0;
    let engaged = false;
    let raf = 0;
    let announceTimer = 0;
    let introStart = 0;
    let introRunning = false;
    const images = [];
    let ready = mode === 'schematic';

    function frameIndex() {
      const i = Math.round(mod(angle, 360) / step);
      return mod(reverse ? -i : i, frames);
    }

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = el.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      colors = palette(el);
      draw();
    }

    /* --- Schematic --------------------------------------------------------
       A turntable, its shoot positions as dots, and a wireframe mass standing
       on it. Deliberately crude: a placeholder that looks designed has a habit
       of quietly becoming the design, and this one has to survive being looked
       at for longer than a static card ever would.
       -------------------------------------------------------------------- */
    function drawSchematic() {
      const rad = (angle * Math.PI) / 180;
      const cx = width / 2;
      const cy = height * 0.4;
      const s = Math.min(width, height) * 0.26;
      const rx = s;
      const ry = s * 0.3;
      const floor = cy + s * 0.72;

      ctx.lineWidth = 1;

      ctx.strokeStyle = colors.hairline;
      ctx.globalAlpha = 0.5;
      ctx.beginPath();
      ctx.ellipse(cx, floor, rx, ry, 0, 0, TAU);
      ctx.stroke();
      ctx.globalAlpha = 1;

      const current = frameIndex();
      for (let i = 0; i < frames; i += 1) {
        const a = (i / frames) * TAU - rad + Math.PI / 2;
        const px = cx + Math.cos(a) * rx;
        const py = floor + Math.sin(a) * ry;
        const front = (Math.sin(a) + 1) / 2; /* 1 nearest the viewer */
        const isCurrent = i === current;
        ctx.beginPath();
        ctx.arc(px, py, isCurrent ? 3 : 1.5, 0, TAU);
        ctx.fillStyle = isCurrent ? colors.accent : colors.faint;
        ctx.globalAlpha = isCurrent ? 1 : 0.25 + front * 0.45;
        ctx.fill();
      }
      ctx.globalAlpha = 1;

      const bw = s * 0.42;
      const bd = s * 0.42;
      const bh = s * 0.95;
      const focal = s * 4;
      const cos = Math.cos(rad);
      const sin = Math.sin(rad);

      function project(x, y, z) {
        const px = x * cos - z * sin;
        const pz = x * sin + z * cos;
        const k = focal / (focal + pz);
        return [cx + px * k, floor + y * k * 0.92];
      }

      const corners = [
        [-bw, 0, -bd],
        [bw, 0, -bd],
        [bw, 0, bd],
        [-bw, 0, bd],
        [-bw, -bh, -bd],
        [bw, -bh, -bd],
        [bw, -bh, bd],
        [-bw, -bh, bd],
      ].map(function (c) {
        return project(c[0], c[1], c[2]);
      });

      const edges = [
        [0, 1], [1, 2], [2, 3], [3, 0],
        [4, 5], [5, 6], [6, 7], [7, 4],
        [0, 4], [1, 5], [2, 6], [3, 7],
      ];

      ctx.strokeStyle = colors.hairline;
      ctx.globalAlpha = 0.85;
      ctx.beginPath();
      edges.forEach(function (e) {
        ctx.moveTo(corners[e[0]][0], corners[e[0]][1]);
        ctx.lineTo(corners[e[1]][0], corners[e[1]][1]);
      });
      ctx.stroke();
      ctx.globalAlpha = 1;

      if (readout) {
        /* Escaped, not literal. This string is rendered, and the document
           declares no charset — the same reason the markup spells its
           punctuation &#215; and &middot; rather than typing it. */
        readout.textContent =
          Math.round(mod(angle, 360)) +
          '\u00B0 \u00B7 ' +
          (current + 1) +
          '/' +
          frames;
      }
    }

    /* --- Frames ----------------------------------------------------------- */
    function drawFrame() {
      const img = images[frameIndex()];
      ctx.clearRect(0, 0, width, height);
      if (!img || !img.complete || !img.naturalWidth) return;
      const scale = Math.min(width / img.naturalWidth, height / img.naturalHeight);
      const w = img.naturalWidth * scale;
      const h = img.naturalHeight * scale;
      ctx.drawImage(img, (width - w) / 2, (height - h) / 2, w, h);
    }

    function draw() {
      if (!width || !height) return;
      ctx.clearRect(0, 0, width, height);
      if (mode === 'schematic') drawSchematic();
      else if (ready) drawFrame();
    }

    function loadPoster() {
      const img = new Image();
      img.decoding = 'async';
      img.addEventListener('load', function () {
        ready = true;
        draw();
      }, { once: true });
      img.src = poster;
      images[0] = img;
    }

    function announce() {
      window.clearTimeout(announceTimer);
      announceTimer = window.setTimeout(function () {
        live.textContent = Math.round(mod(angle, 360)) + ' degrees';
      }, ANNOUNCE_MS);
    }

    function engage() {
      if (engaged) return;
      engaged = true;
      el.classList.add('is-engaged');
      introRunning = false;
    }

    function tick() {
      raf = 0;
      let live_ = false;

      if (introRunning) {
        const t = (performance.now() - introStart) / INTRO_MS;
        if (t >= 1) {
          angle = 0;
          introRunning = false;
        } else {
          /* ease-in-out, so it starts and ends without a jolt */
          const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
          angle = e * 360;
          live_ = true;
        }
      } else if (Math.abs(spin) > MIN_SPIN) {
        angle += spin;
        spin *= FRICTION;
        live_ = true;
      } else {
        spin = 0;
      }

      draw();
      if (live_) raf = requestAnimationFrame(tick);
    }

    function schedule() {
      if (!raf) raf = requestAnimationFrame(tick);
    }

    /* --- Pointer ----------------------------------------------------------
       Pointer events unify mouse, touch and pen, and setPointerCapture keeps
       the drag alive when the finger leaves the stage. Vertical scrolling is
       never captured — touch-action: pan-y in CSS has already conceded it.
       -------------------------------------------------------------------- */
    let dragging = false;
    let lastX = 0;

    if (spins) {
    el.addEventListener('pointerdown', function (ev) {
      if (ev.button !== undefined && ev.button !== 0) return;
      dragging = true;
      lastX = ev.clientX;
      spin = 0;
      engage();
      el.classList.add('is-holding');
      el.setPointerCapture(ev.pointerId);
    });

    el.addEventListener('pointermove', function (ev) {
      if (!dragging) return;
      const dx = ev.clientX - lastX;
      lastX = ev.clientX;
      const delta = (dx / (width * SWEEP)) * 360;
      angle += delta;
      spin = calm.matches ? 0 : Math.max(-FLING_CAP, Math.min(FLING_CAP, delta));
      draw();
    });

    function release(ev) {
      if (!dragging) return;
      dragging = false;
      el.classList.remove('is-holding');
      if (ev && ev.pointerId !== undefined && el.hasPointerCapture(ev.pointerId)) {
        el.releasePointerCapture(ev.pointerId);
      }
      if (!calm.matches) schedule();
      announce();
    }

    el.addEventListener('pointerup', release);
    el.addEventListener('pointercancel', release);
    }

    if (spins) el.addEventListener('keydown', function (ev) {
      let dir = 0;
      if (ev.key === 'ArrowLeft') dir = -1;
      else if (ev.key === 'ArrowRight') dir = 1;
      else if (ev.key === 'Home') {
        engage();
        spin = 0;
        angle = 0;
        draw();
        announce();
        ev.preventDefault();
        return;
      } else return;

      engage();
      spin = 0;
      angle += dir * step * KEY_STEP;
      draw();
      announce();
      ev.preventDefault();
    });

    /* --- Loading ---------------------------------------------------------- */
    function load() {
      let done = 0;
      for (let i = 0; i < frames; i += 1) {
        const n = String(i + 1).padStart(pad, '0');
        const img = new Image();
        img.decoding = 'async';
        img.src = template.replace('{i}', n);
        images[i] = img;
        const settle = function () {
          done += 1;
          el.style.setProperty('--nit-360-loaded', String(done / frames));
          if (done === frames) {
            ready = true;
            if (progress) progress.remove();
            draw();
            maybeIntro();
          }
        };
        if (img.complete) settle();
        else {
          img.addEventListener('load', settle, { once: true });
          img.addEventListener('error', settle, { once: true });
        }
      }
    }

    function maybeIntro() {
      if (engaged || calm.matches || !ready) return;
      introRunning = true;
      introStart = performance.now();
      schedule();
    }

    /* The intro waits for the viewer to actually be on screen, so a spin that
       exists to be noticed is not spent above the fold of someone's scroll. */
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              io.disconnect();
              maybeIntro();
            }
          });
        },
        { threshold: 0.5 }
      );
      io.observe(el);
    } else {
      maybeIntro();
    }

    if ('ResizeObserver' in window) new ResizeObserver(resize).observe(el);
    else window.addEventListener('resize', resize);

    resize();
    if (mode === 'frames') load();
    else if (mode === 'poster') loadPoster();
  }

  document.querySelectorAll(ROOT).forEach(build);
}

/* ============================================================================
   nit-gallery.js — the hero's views
   ----------------------------------------------------------------------------
   The track scrolls and snaps on its own; this file only adds the controls and
   keeps them in step with it. Every position is read back from scrollLeft
   rather than held in a variable, so a swipe, a wheel, a dot, an arrow and a
   keyboard scroll all converge on the same answer and none of them can leave
   the dots disagreeing with what is on screen.

   Slides are exactly one track-width wide, which makes index and offset the
   same fact expressed two ways and removes any need to measure elements.
   ========================================================================== */

{
  const GALLERY = '[data-nit-gallery]';

  const calm = matchMedia('(prefers-reduced-motion: reduce)');

  function build(root) {
    const track = root.querySelector('.nit-gallery__track');
    const slides = Array.from(root.querySelectorAll('.nit-gallery__slide'));
    if (!track || slides.length < 2) return;

    track.setAttribute('role', 'group');
    track.setAttribute('aria-label', root.getAttribute('data-nit-gallery-label') || 'Product views');

    const dots = document.createElement('ul');
    dots.className = 'nit-gallery__dots';

    const buttons = slides.map(function (slide, i) {
      const li = document.createElement('li');
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'nit-gallery__dot';
      /* Named by what the slide shows, not by its number — the image's own alt
         text is already the best description anyone has written of it. */
      const img = slide.querySelector('img');
      b.setAttribute('aria-label', img ? img.alt : 'View ' + (i + 1) + ' of ' + slides.length);
      b.addEventListener('click', function () { go(i); });
      li.append(b);
      dots.append(li);
      return b;
    });
    root.append(dots);

    function arrow(dir, label, path) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'nit-gallery__arrow nit-gallery__arrow--' + dir;
      b.setAttribute('aria-label', label);
      b.innerHTML = path;
      b.addEventListener('click', function () { go(current() + (dir === 'next' ? 1 : -1)); });
      root.append(b);
      return b;
    }
    const prev = arrow('prev', 'Previous view',
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>');
    const next = arrow('next', 'Next view',
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>');

    const live = document.createElement('span');
    live.className = 'nit-visually-hidden';
    live.setAttribute('aria-live', 'polite');
    root.append(live);

    function current() {
      const w = track.clientWidth || 1;
      return Math.max(0, Math.min(slides.length - 1, Math.round(track.scrollLeft / w)));
    }

    function go(i) {
      const n = Math.max(0, Math.min(slides.length - 1, i));
      track.scrollTo({
        left: n * track.clientWidth,
        behavior: calm.matches ? 'auto' : 'smooth',
      });
    }

    let last = -1;
    function sync() {
      const i = current();
      buttons.forEach(function (b, n) { b.setAttribute('aria-current', String(n === i)); });
      prev.disabled = i === 0;
      next.disabled = i === slides.length - 1;
      if (i !== last) {
        last = i;
        live.textContent = 'View ' + (i + 1) + ' of ' + slides.length;
      }
    }

    /* scroll fires continuously through a snap; rAF-coalescing keeps the dots
       to one update per frame instead of one per scroll event. */
    let queued = false;
    track.addEventListener('scroll', function () {
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () { queued = false; sync(); });
    }, { passive: true });

    if ('ResizeObserver' in window) new ResizeObserver(sync).observe(track);
    sync();
  }

  document.querySelectorAll(GALLERY).forEach(build);
}
