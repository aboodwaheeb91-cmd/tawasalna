// static/shared/tw-overlay.js — DS-OVL Runtime V1 (F33 · docs/design-system/OVERLAY-SYSTEM.md OVL-39)
//
// Usage:
//   twConfirm({ title, message, confirmText, cancelText, danger }) → Promise<boolean>
//   twAlert({ title, message, okText })                            → Promise<void>
//   twModal({ title, content: Element, actions, dismissible, onClose }) → { close, setBusy, el }
//     actions: [{ text, variant: 'primary'|'danger'|'secondary', onClick(ctl) }]
//       onClick may return a Promise → the dialog is busy (buttons disabled, Escape and
//       backdrop ignored) until it settles; resolved value === false keeps it open,
//       anything else closes it (reason 'action'). A rejected Promise keeps it open.
//       No onClick → the button closes the dialog (reason 'cancel').
//
// Contract (OVL-39):
//   - role="dialog" + aria-modal="true" + aria-labelledby → the title (aria-describedby → message).
//   - Escape closes the TOP layer only (reason 'escape') — never while busy.
//   - Backdrop click closes only dismissible layers: twAlert, twConfirm without danger,
//     twModal unless dismissible:false. danger:true → never by backdrop.
//   - Focus trap: Tab / Shift-Tab wrap inside the top surface; focus that escapes is pulled back.
//   - Initial focus: danger confirm → «إلغاء» · confirm → confirm button · alert → OK ·
//     twModal → the title (surface-heading, OVL-17).
//   - Focus restore: the element that had focus when the layer opened (if still in the DOM
//     and focusable) → else the layer below → else <main> / <h1> (never document.body).
//   - Background isolation (OVL-18): every other <body> child gets `inert` while any layer is
//     open — kept through the closing animation.
//   - Scroll lock (OVL-19): reference-counted on <html>; unlock only when the last layer closes.
//   - Colors / sizes / icons: DS-COLOR / DS-SIZE tokens only; icons via twIconEl (DS-ICON) when
//     tw-icons.js is on the page. Text is Arabic, dir="rtl".
//   - Loaded as a page asset (PAGE_ASSETS → {{v:tw-overlay.js}}) — never in the Page Shell.
//   - ❌ alert() / confirm() / prompt() in a page touched from now on — use these.
(function () {
  'use strict';

  var STYLE_ID = 'tw-ovl-style';
  var CLOSE_MS = 160;   // exit transition + timeout fallback (OVL-07) — no animationend dependency
  var CSS = ''
    // DS-OVL band (OVL-14 — placeholder until Global Layer Tokens): 9000 = under the tw-select
    // dropdown (9500, so a select inside a dialog still opens) and under the toast (9999).
    + '.tw-ovl{position:fixed;inset:0;z-index:9000;display:flex;align-items:center;justify-content:center;'
    + 'padding:var(--space-8);direction:rtl;font-family:inherit}'
    + '.tw-ovl-bg{position:absolute;inset:0;background:var(--color-surface-page);opacity:0;transition:opacity .16s}'
    + '.tw-ovl.is-open .tw-ovl-bg{opacity:.8}'
    + '.tw-ovl-surface{position:relative;width:100%;max-width:420px;max-height:calc(100dvh - 2 * var(--space-8));'
    + 'display:flex;flex-direction:column;background:var(--color-surface-card-solid);'
    + 'border:1px solid var(--color-border-default);border-radius:var(--radius-3xl);'
    + 'color:var(--color-text-primary);opacity:0;transform:scale(.96);transition:opacity .16s,transform .16s;outline:none}'
    + '.tw-ovl.is-open .tw-ovl-surface{opacity:1;transform:none}'
    + '.tw-ovl.is-closing .tw-ovl-surface{opacity:0;transform:scale(.96)}'
    + '.tw-ovl.is-closing .tw-ovl-bg{opacity:0}'
    + '.tw-ovl-head{display:flex;align-items:center;gap:var(--space-5);padding:var(--space-10) var(--space-10) 0}'
    + '.tw-ovl-ico{display:inline-flex;flex-shrink:0;color:var(--color-status-info)}'
    + '.tw-ovl-ico.is-danger{color:var(--color-status-danger)}'
    + '.tw-ovl-title{flex:1;margin:0;font-size:var(--size-font-2xl);font-weight:700;outline:none}'
    + '.tw-ovl-x{display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;'
    + 'width:var(--size-control-icon-md);height:var(--size-control-icon-md);border:none;border-radius:var(--radius-sm);'
    + 'background:transparent;color:var(--color-text-secondary);cursor:pointer}'
    + '.tw-ovl-x:hover{background:var(--color-surface-input);color:var(--color-text-primary)}'
    + '.tw-ovl-body{padding:var(--space-6) var(--space-10) 0;overflow-y:auto;font-size:var(--size-font-lg);'
    + 'line-height:1.7;color:var(--color-text-secondary)}'
    + '.tw-ovl-msg{margin:0;white-space:pre-line}'
    + '.tw-ovl-actions{display:flex;flex-wrap:wrap;gap:var(--space-4);justify-content:flex-start;'
    + 'padding:var(--space-10);padding-bottom:calc(var(--space-10) + env(safe-area-inset-bottom, 0px))}'
    + '.tw-ovl-btn{min-height:var(--size-control-md);padding:0 var(--space-10);border-radius:var(--radius-control);'
    + 'font:inherit;font-size:var(--size-font-lg);font-weight:700;cursor:pointer;border:1px solid transparent}'
    + '.tw-ovl-btn:focus-visible,.tw-ovl-x:focus-visible{outline:2px solid var(--color-border-focus);outline-offset:2px}'
    + '.tw-ovl-btn[disabled]{opacity:.5;cursor:default}'
    + '.tw-ovl-btn.is-primary{background:var(--color-brand-primary);color:var(--color-surface-page)}'
    + '.tw-ovl-btn.is-danger{background:var(--color-status-danger);color:var(--color-surface-page)}'
    + '.tw-ovl-btn.is-secondary{background:transparent;border-color:var(--color-border-strong);color:var(--color-text-secondary)}'
    + '.tw-ovl-btn.is-secondary:hover{color:var(--color-text-primary)}'
    + '@media (prefers-reduced-motion: reduce){.tw-ovl-bg,.tw-ovl-surface{transition:none}}';

  var stack = [];        // open layers, last = top (OVL-08)
  var inertEls = [];     // body children this module made inert
  var scrollSaved = null;
  var uid = 0;
  var keyBound = false;

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var s = document.createElement('style');
    s.id = STYLE_ID;
    s.textContent = CSS;
    (document.head || document.body).appendChild(s);
  }

  function icon(name, size) {
    if (typeof window.twIconEl !== 'function') return null;   // DS-ICON is optional
    return window.twIconEl(name, { size: size || 'lg' });
  }

  // ── focus helpers (walk children — no selector engine needed) ──────────────
  var NATIVE = { BUTTON: 1, INPUT: 1, SELECT: 1, TEXTAREA: 1 };
  function isFocusable(el) {
    if (!el || el.nodeType !== 1 || el.hidden || el.disabled) return false;
    if (el.hasAttribute && el.hasAttribute('inert')) return false;
    var tag = el.tagName;
    var ti = el.getAttribute ? el.getAttribute('tabindex') : null;
    if (ti !== null && ti !== undefined) return Number(ti) >= 0;
    if (NATIVE[tag]) return !(tag === 'INPUT' && el.type === 'hidden');
    if (tag === 'A') return !!(el.getAttribute && el.getAttribute('href'));
    return false;
  }
  function focusables(root) {
    var out = [];
    (function walk(n) {
      var kids = n.children || [];
      for (var i = 0; i < kids.length; i++) {
        var k = kids[i];
        if (k.hidden || (k.hasAttribute && k.hasAttribute('inert'))) continue;
        if (isFocusable(k)) out.push(k);
        walk(k);
      }
    })(root);
    return out;
  }
  function canRestore(el) {
    return !!el && el !== document.body && el.isConnected !== false && !el.disabled
      && typeof el.focus === 'function' && !insideInert(el);
  }
  function insideInert(el) {
    for (var n = el; n && n !== document.body; n = n.parentNode) {
      if (n.hasAttribute && n.hasAttribute('inert')) return true;
    }
    return false;
  }

  // ── isolation + scroll lock (reference-counted by the stack size) ──────────
  function isolate(root) {
    var kids = document.body.children || [];
    for (var i = 0; i < kids.length; i++) {
      var k = kids[i];
      if (k === root || (k.className && String(k.className).indexOf('tw-ovl') === 0)) continue;
      if (k.hasAttribute('inert')) continue;
      k.setAttribute('inert', '');
      inertEls.push(k);
    }
  }
  function lockScroll() {
    if (scrollSaved) return;
    var html = document.documentElement;
    var gap = (window.innerWidth || 0) - (html.clientWidth || 0);
    scrollSaved = { overflow: html.style.overflow, pad: document.body.style.paddingRight };
    html.style.overflow = 'hidden';
    if (gap > 0) document.body.style.paddingRight = gap + 'px';   // no layout shift
  }
  function releaseAll() {   // last layer gone
    inertEls.forEach(function (el) { el.removeAttribute('inert'); });
    inertEls = [];
    if (scrollSaved) {
      document.documentElement.style.overflow = scrollSaved.overflow;
      document.body.style.paddingRight = scrollSaved.pad;
      scrollSaved = null;
    }
  }

  function top() { return stack[stack.length - 1] || null; }

  function onKey(e) {
    var L = top();
    if (!L || L.state !== 'open') return;
    if (e.key === 'Escape' || e.key === 'Esc') {
      e.preventDefault();
      if (!L.busy) L.close('escape');
      return;
    }
    if (e.key !== 'Tab') return;
    var f = focusables(L.surface);
    if (!f.length) { e.preventDefault(); L.surface.focus(); return; }
    var first = f[0], last = f[f.length - 1], cur = document.activeElement;
    var inside = L.surface.contains(cur);
    if (e.shiftKey && (cur === first || !inside || cur === L.surface)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && (cur === last || !inside)) { e.preventDefault(); first.focus(); }
  }
  function onFocusIn(e) {
    var L = top();
    if (L && L.state !== 'closed' && e.target && !L.root.contains(e.target)) {
      var f = focusables(L.surface);
      (f[0] || L.surface).focus();
    }
  }
  function bindKeys() {
    if (keyBound) return;
    keyBound = true;
    document.addEventListener('keydown', onKey, true);
    document.addEventListener('focusin', onFocusIn, true);
  }

  function makeBtn(text, variant) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'tw-ovl-btn is-' + (variant || 'secondary');
    b.textContent = String(text);
    return b;
  }

  // ── core: open one layer ───────────────────────────────────────────────────
  function openLayer(o) {
    injectStyle();
    bindKeys();
    var id = 'tw-ovl-' + (++uid);
    var trigger = document.activeElement;

    var root = document.createElement('div');
    root.className = 'tw-ovl';
    root.setAttribute('dir', 'rtl');
    var bg = document.createElement('div');
    bg.className = 'tw-ovl-bg';
    var surface = document.createElement('div');
    surface.className = 'tw-ovl-surface';
    surface.setAttribute('role', 'dialog');
    surface.setAttribute('aria-modal', 'true');
    surface.setAttribute('aria-labelledby', id + '-t');
    surface.setAttribute('tabindex', '-1');

    var head = document.createElement('div');
    head.className = 'tw-ovl-head';
    if (o.icon) {
      var ic = icon(o.icon, 'xl');
      if (ic) {
        var icw = document.createElement('span');
        icw.className = 'tw-ovl-ico' + (o.danger ? ' is-danger' : '');
        icw.appendChild(ic);
        head.appendChild(icw);
      }
    }
    var title = document.createElement('h2');
    title.className = 'tw-ovl-title';
    title.id = id + '-t';
    title.setAttribute('tabindex', '-1');
    title.textContent = String(o.title || '');
    head.appendChild(title);
    surface.appendChild(head);

    var L = {
      root: root, surface: surface, title: title, state: 'opening', busy: false,
      dismissible: !!o.dismissible, buttons: [], xBtn: null,
    };

    if (o.closeButton) {
      var x = document.createElement('button');
      x.type = 'button';
      x.className = 'tw-ovl-x';
      x.setAttribute('aria-label', 'إغلاق');
      var xi = icon('close', 'md');
      if (xi) x.appendChild(xi); else x.textContent = '×';
      x.addEventListener('click', function () { if (!L.busy) L.close('close-button'); });
      head.appendChild(x);
      L.xBtn = x;
    }

    var body = document.createElement('div');
    body.className = 'tw-ovl-body';
    if (o.message != null && o.message !== '') {
      var p = document.createElement('p');
      p.className = 'tw-ovl-msg';
      p.id = id + '-d';
      p.textContent = String(o.message);
      body.appendChild(p);
      surface.setAttribute('aria-describedby', p.id);
    }
    if (o.content) body.appendChild(o.content);
    surface.appendChild(body);

    var foot = document.createElement('div');
    foot.className = 'tw-ovl-actions';
    (o.actions || []).forEach(function (a) {
      var b = makeBtn(a.text, a.variant);
      b.addEventListener('click', function () { if (!L.busy && L.state === 'open') a.run(b); });
      foot.appendChild(b);
      L.buttons.push(b);
      a.el = b;
    });
    if (L.buttons.length) surface.appendChild(foot);

    root.appendChild(bg);
    root.appendChild(surface);
    bg.addEventListener('click', function () {
      if (L === top() && L.dismissible && !L.busy && L.state === 'open') L.close('backdrop');
    });

    L.setBusy = function (on) {
      L.busy = !!on;
      surface.setAttribute('aria-busy', on ? 'true' : 'false');
      L.buttons.concat(L.xBtn ? [L.xBtn] : []).forEach(function (b) { b.disabled = !!on; });
    };

    L.close = function (reason) {
      if (L.state === 'closing' || L.state === 'closed') return;
      L.state = 'closing';
      root.classList.add('is-closing');   // isolation stays on through the animation (OVL-07)
      setTimeout(function () {
        L.state = 'closed';
        if (root.parentNode) root.parentNode.removeChild(root);
        var i = stack.indexOf(L);
        if (i >= 0) stack.splice(i, 1);
        if (!stack.length) releaseAll();
        restoreFocus(trigger);
        if (typeof o.onClose === 'function') o.onClose(reason || 'system');
      }, CLOSE_MS);
    };

    stack.push(L);
    document.body.appendChild(root);
    isolate(root);
    lockScroll();
    // parent layer (if any) becomes background too
    if (stack.length > 1) { var P = stack[stack.length - 2]; P.root.setAttribute('inert', ''); L.parent = P; }
    L.state = 'open';
    var raf = window.requestAnimationFrame || function (fn) { return setTimeout(fn, 0); };
    raf(function () { root.classList.add('is-open'); });

    var target = typeof o.initialFocus === 'function' ? o.initialFocus(L) : null;
    (target || title).focus();
    return L;
  }

  function restoreFocus(trigger) {
    var T = top();
    if (T) T.root.removeAttribute('inert');
    if (canRestore(trigger) && (!T || T.root.contains(trigger))) { trigger.focus(); return; }
    if (T) { (focusables(T.surface)[0] || T.surface).focus(); return; }
    if (canRestore(trigger)) { trigger.focus(); return; }
    var land = document.querySelector && document.querySelector('main, [role="main"], h1');
    if (land) {
      if (!isFocusable(land)) land.setAttribute('tabindex', '-1');
      land.focus();
    }
  }

  // ── public API ─────────────────────────────────────────────────────────────
  function twModal(opts) {
    opts = opts || {};
    var ctl = {};
    var acts = (opts.actions || []).map(function (a) {
      return {
        text: a.text, variant: a.variant || 'secondary',
        run: function () {
          if (typeof a.onClick !== 'function') { L.close('cancel'); return; }
          var r;
          try { r = a.onClick(ctl); } catch (e) { console.error('[tw-overlay] action failed', e); return; }
          if (r && typeof r.then === 'function') {
            L.setBusy(true);
            r.then(function (v) { L.setBusy(false); if (v !== false) L.close('action'); },
                   function (e) { L.setBusy(false); console.error('[tw-overlay] action failed', e); });
          } else if (r !== false) {
            L.close('action');
          }
        },
      };
    });
    var L = openLayer({
      title: opts.title, content: opts.content, message: opts.message, actions: acts,
      dismissible: opts.dismissible !== false, closeButton: opts.dismissible !== false,
      onClose: opts.onClose,
    });
    ctl.close = function (reason) { L.close(reason || 'system'); };
    ctl.setBusy = L.setBusy;
    ctl.el = L.surface;
    return ctl;
  }

  function twConfirm(opts) {
    opts = opts || {};
    var danger = !!opts.danger;
    return new Promise(function (resolve) {
      var result = false;
      var acts = [
        { text: opts.cancelText || 'إلغاء', variant: 'secondary', run: function () { L.close('cancel'); } },
        { text: opts.confirmText || 'تأكيد', variant: danger ? 'danger' : 'primary',
          run: function () { result = true; L.close('confirm'); } },
      ];
      var L = openLayer({
        title: opts.title || 'تأكيد', message: opts.message, actions: acts, danger: danger,
        icon: danger ? 'alert' : null,
        dismissible: !danger,   // danger → never closed by a backdrop click
        initialFocus: function () { return danger ? acts[0].el : acts[1].el; },   // OVL-27
        onClose: function () { resolve(result); },
      });
    });
  }

  function twAlert(opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      var acts = [{ text: opts.okText || 'حسناً', variant: 'primary', run: function () { L.close('confirm'); } }];
      var L = openLayer({
        title: opts.title || 'تنبيه', message: opts.message, actions: acts, icon: 'info',
        dismissible: true,
        initialFocus: function () { return acts[0].el; },
        onClose: function () { resolve(); },
      });
    });
  }

  window.twConfirm = twConfirm;
  window.twAlert = twAlert;
  window.twModal = twModal;
}());
