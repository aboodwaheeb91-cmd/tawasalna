/**
 * test_ds_overlay_runtime.js — DS-OVL Runtime V1 (static/shared/tw-overlay.js · OVERLAY-SYSTEM.md OVL-39)
 * Runs the REAL tw-overlay.js in a Node vm with a tiny fake DOM.
 *   A  twConfirm true / false · ARIA · Escape · focus trap · focus restore · scroll lock + inert
 *   B  danger: focus on «إلغاء», backdrop does not close · non-danger backdrop closes · twAlert
 *   C  twModal busy action — Escape / backdrop ignored while the action runs
 *   E  Escape with an open tw-select dropdown inside a dialog closes the dropdown only (PR 3.10)
 *   D  wiring — PAGE_ASSETS entry · appointment-room loads it after the shell
 *   R  REPORT ONLY (never fails): native alert / confirm / prompt still in the site
 *
 * Run: node test_ds_overlay_runtime.js
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log('  PASS  ' + name); }
  else      { failed++; console.log('  FAIL  ' + name + (detail !== undefined ? ' — ' + detail : '')); }
}
const read = f => fs.readFileSync(f, 'utf8');

// ── fake DOM ──────────────────────────────────────────────────────────────
function makeEnv() {
  const timers = [];
  const docListeners = {};
  let doc;
  class El {
    constructor(tag) {
      this.tagName = String(tag).toUpperCase(); this.nodeType = 1;
      this.children = []; this.parentNode = null; this.attrs = {}; this.style = {};
      this.listeners = {}; this.hidden = false; this.disabled = false; this.type = '';
      this.textContent = ''; this.className = '';
      const self = this;
      this.classList = {
        add(c) { const s = self.className.split(' ').filter(Boolean); if (!s.includes(c)) s.push(c); self.className = s.join(' '); },
        remove(c) { self.className = self.className.split(' ').filter(x => x && x !== c).join(' '); },
        contains(c) { return self.className.split(' ').includes(c); },
      };
    }
    get id() { return this.attrs.id || ''; }
    set id(v) { this.attrs.id = String(v); }
    setAttribute(k, v) { this.attrs[k] = String(v); }
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
    hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); }
    removeAttribute(k) { delete this.attrs[k]; }
    appendChild(c) { if (c.parentNode) c.parentNode.removeChild(c); this.children.push(c); c.parentNode = this; return c; }
    removeChild(c) { this.children = this.children.filter(x => x !== c); c.parentNode = null; return c; }
    contains(n) { for (; n; n = n.parentNode) if (n === this) return true; return false; }
    get isConnected() { return doc.documentElement.contains(this); }
    addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); }
    fire(t, ev) { (this.listeners[t] || []).forEach(fn => fn(ev || { target: this })); }
    click() { if (!this.disabled) this.fire('click', { target: this }); }
    focus() {
      doc.activeElement = this;
      (docListeners.focusin || []).forEach(fn => fn({ target: this }));
    }
  }
  const html = new El('html'), head = new El('head'), body = new El('body');
  html.appendChild(head); html.appendChild(body);
  doc = {
    documentElement: html, head, body, activeElement: body,
    createElement: t => new El(t),
    addEventListener: (t, fn) => { (docListeners[t] = docListeners[t] || []).push(fn); },
    getElementById(id) {
      const walk = n => { if (n.id === id) return n; for (const k of n.children) { const r = walk(k); if (r) return r; } return null; };
      return walk(html);
    },
    querySelector() { const walk = n => { if (n.tagName === 'MAIN' || n.tagName === 'H1') return n; for (const k of n.children) { const r = walk(k); if (r) return r; } return null; }; return walk(body); },
  };
  const ctx = {
    document: doc, console, Promise, Number, String,
    innerWidth: 1000,
    setTimeout: fn => { timers.push(fn); return timers.length; },
  };
  ctx.window = ctx;
  html.clientWidth = 985;   // 15px scrollbar
  vm.createContext(ctx);
  vm.runInContext(read('static/shared/tw-overlay.js'), ctx);
  const key = (k, shift, alreadyPrevented) => {
    const ev = { key: k, shiftKey: !!shift, prevented: false, defaultPrevented: !!alreadyPrevented,
                 preventDefault() { this.prevented = true; this.defaultPrevented = true; } };
    (docListeners.keydown || []).forEach(fn => fn(ev));
    return ev;
  };
  const flush = async () => { while (timers.length) timers.shift()(); await new Promise(r => setImmediate(r)); };
  const page = new El('main'); body.appendChild(page);
  const trigger = new El('button'); page.appendChild(trigger);
  const surface = () => { const r = body.children.find(c => c.className.startsWith('tw-ovl')); return r && r.children[1]; };
  const buttons = () => { const s = surface(); const out = []; const w = n => { for (const k of n.children) { if (k.tagName === 'BUTTON') out.push(k); w(k); } }; if (s) w(s); return out; };
  const backdrop = () => body.children.find(c => c.className.startsWith('tw-ovl')).children[0];
  return { ctx, doc, body, html, page, trigger, key, flush, surface, buttons, backdrop, El };
}

(async () => {
  // ── A ──────────────────────────────────────────────────────────────────
  {
    const E = makeEnv();
    E.trigger.focus();
    const p = E.ctx.twConfirm({ title: 'قبول الموعد', message: 'هل تؤكد؟', confirmText: 'قبول' });
    const s = E.surface();
    check('A1 role=dialog + aria-modal=true', s.getAttribute('role') === 'dialog' && s.getAttribute('aria-modal') === 'true');
    const t = E.doc.getElementById(s.getAttribute('aria-labelledby'));
    check('A2 aria-labelledby → the title', !!t && t.textContent === 'قبول الموعد');
    check('A3 dir=rtl on the overlay root', s.parentNode.getAttribute('dir') === 'rtl');
    const [cancel, ok] = E.buttons();
    check('A4 non-danger: initial focus on the confirm button', E.doc.activeElement === ok && ok.className.includes('is-primary'));
    check('A5 scroll lock on <html> + scrollbar gap', E.html.style.overflow === 'hidden' && E.body.style.paddingRight === '15px');
    check('A6 page content is inert while open', E.page.hasAttribute('inert'));
    // focus trap
    E.key('Tab');                       // ok is last → wraps to first
    check('A7 Tab on the last button wraps to the first', E.doc.activeElement === cancel);
    E.key('Tab', true);                 // Shift-Tab on first → last
    check('A8 Shift-Tab on the first button wraps to the last', E.doc.activeElement === ok);
    E.trigger.focus();                  // something steals focus to the background
    check('A9 focus that escapes is pulled back inside', s.contains(E.doc.activeElement));
    ok.click(); await E.flush();
    check('A10 confirm → true', (await p) === true);
    check('A11 closed: overlay removed, inert + scroll lock released',
      !E.surface() && !E.page.hasAttribute('inert') && E.html.style.overflow === undefined && E.body.style.paddingRight === undefined);
    check('A12 focus restored to the trigger', E.doc.activeElement === E.trigger);

    E.trigger.focus();
    const p2 = E.ctx.twConfirm({ message: 'x' });
    E.buttons()[0].click(); await E.flush();
    check('A13 cancel → false', (await p2) === false);

    E.trigger.focus();
    const p3 = E.ctx.twConfirm({ message: 'x' });
    const ev = E.key('Escape'); await E.flush();
    check('A14 Escape → false + closed + focus restored', (await p3) === false && ev.prevented && !E.surface() && E.doc.activeElement === E.trigger);
  }

  // ── B ──────────────────────────────────────────────────────────────────
  {
    const E = makeEnv();
    E.trigger.focus();
    const p = E.ctx.twConfirm({ title: 'إغلاق الغرفة نهائياً', message: 'm', confirmText: 'إغلاق الغرفة', danger: true });
    const [cancel, ok] = E.buttons();
    check('B1 danger: first focus on «إلغاء»', E.doc.activeElement === cancel && cancel.textContent === 'إلغاء');
    check('B2 danger: confirm button uses the danger variant', ok.className.includes('is-danger'));
    E.backdrop().click(); await E.flush();
    check('B3 danger: backdrop click does NOT close', !!E.surface());
    E.key('Escape'); await E.flush();
    check('B4 danger: Escape still cancels → false', (await p) === false && !E.surface());

    const p2 = E.ctx.twConfirm({ message: 'x' });
    E.backdrop().click(); await E.flush();
    check('B5 non-danger: backdrop click closes → false', (await p2) === false && !E.surface());

    let done = false;
    const p3 = E.ctx.twAlert({ title: 'تنبيه', message: 'm' }).then(() => { done = true; });
    check('B6 twAlert: focus on «حسناً»', E.doc.activeElement === E.buttons()[0] && E.buttons()[0].textContent === 'حسناً');
    E.buttons()[0].click(); await E.flush(); await p3;
    check('B7 twAlert resolves on OK', done);
  }

  // ── C ──────────────────────────────────────────────────────────────────
  {
    const E = makeEnv();
    E.trigger.focus();
    let release, closedWith = null;
    const content = new E.El('div');
    const m = E.ctx.twModal({
      title: 'سبب الإلغاء', content,
      actions: [{ text: 'إلغاء' }, { text: 'حفظ', variant: 'primary', onClick: () => new Promise(r => { release = r; }) }],
      onClose: r => { closedWith = r; },
    });
    check('C1 twModal: initial focus on the title (surface-heading)', E.doc.activeElement.tagName === 'H2');
    check('C2 twModal: content placed inside the dialog', E.surface().contains(content));
    const save = E.buttons().find(b => b.textContent === 'حفظ');
    save.click();
    check('C3 busy: buttons disabled + aria-busy', save.disabled && E.surface().getAttribute('aria-busy') === 'true');
    E.key('Escape'); E.backdrop().click(); await E.flush();
    check('C4 busy: Escape and backdrop ignored', !!E.surface() && closedWith === null);
    release(); await E.flush(); await E.flush();
    check('C5 action resolved → closed (reason action) + focus restored',
      !E.surface() && closedWith === 'action' && E.doc.activeElement === E.trigger);
    check('C6 returns { close, setBusy }', typeof m.close === 'function' && typeof m.setBusy === 'function');
  }

  // ── E ──────────────────────────────────────────────────────────────────
  console.log('\nE — Escape + open tw-select dropdown (dropdown first, dialog stays)');
  {
    const E = makeEnv();
    E.trigger.focus();
    let closedWith = null;
    E.ctx.twModal({ title: 'تحديد موعد', content: new E.El('div'), actions: [{ text: 'إلغاء' }],
                    onClose: r => { closedWith = r; } });
    // tw-select (window capture, before the dialog's document listener) already used this Escape
    E.key('Escape', false, true); await E.flush();
    check('E1 defaultPrevented Escape (dropdown closed it) → dialog stays open', !!E.surface() && closedWith === null);
    E.key('Escape'); await E.flush();
    check('E2 next Escape (no dropdown) → dialog closes (reason escape)', !E.surface() && closedWith === 'escape');
    const sel = read('static/shared/tw-select.js');
    const h = sel.split("window.addEventListener('keydown', function(e){")[1] || '';
    const body = h.split('}, true);')[0];
    check('E3 tw-select: Escape handler on window, capture phase, only while a dropdown is open',
      /if\(!_cur \|\| \(e\.key !== 'Escape' && e\.key !== 'Esc'\)\) return;/.test(body)
      && h.indexOf('}, true);') > 0);
    check('E4 tw-select: open dropdown + Escape → preventDefault + stopPropagation + close',
      /e\.preventDefault\(\);[\s\S]*e\.stopPropagation\(\);[\s\S]*_close\(\);/.test(body));
  }

  // ── D ──────────────────────────────────────────────────────────────────
  {
    const shell = read('page_shell.py');
    check('D1 PAGE_ASSETS has tw-overlay.js', /"tw-overlay\.js":\s*os\.path\.join\("static", "shared", "tw-overlay\.js"\)/.test(shell));
    const room = read('appointment-room.html');
    const at = room.indexOf('/static/shared/tw-overlay.js?v={{v:tw-overlay.js}}');
    check('D2 appointment-room loads tw-overlay.js after the shell scripts', at > room.indexOf('<!--tw:shell-scripts-->'));
    const src = read('static/shared/tw-overlay.js');
    check('D3 tw-overlay.js: no hex / rgb colour literals (DS-COLOR tokens only)', !/#[0-9a-fA-F]{3,6}\b|rgba?\(/.test(src));
  }

  // ── R — report only ────────────────────────────────────────────────────
  {
    const SKIP = new Set(['node_modules', '.git', 'vendor', 'flags']);
    const files = [];
    (function walk(dir) {
      for (const n of fs.readdirSync(dir, { withFileTypes: true })) {
        if (SKIP.has(n.name)) continue;
        const p = path.join(dir, n.name);
        if (n.isDirectory()) walk(p);
        else if (/\.(html|js)$/.test(n.name) && !/^test_/.test(n.name) && n.name !== 'tw-overlay.js') files.push(p);
      }
    })('.');
    const re = /(^|[^\w$.])(?:window\.)?(alert|confirm|prompt)\(/g;
    const rows = []; const tot = { alert: 0, confirm: 0, prompt: 0 };
    for (const f of files) {
      const c = { alert: 0, confirm: 0, prompt: 0 };
      read(f).split('\n').forEach(line => {
        const t = line.trim();
        if (t.startsWith('//') || t.startsWith('*')) return;
        for (const m of line.matchAll(re)) c[m[2]]++;
      });
      const n = c.alert + c.confirm + c.prompt;
      if (n) { rows.push([f, c, n]); tot.alert += c.alert; tot.confirm += c.confirm; tot.prompt += c.prompt; }
    }
    rows.sort((a, b) => b[2] - a[2]);
    console.log('\n  REPORT  native alert / confirm / prompt left (DS-OVL migration debt — report only):');
    rows.forEach(([f, c]) => console.log('          ' + f.replace(/^\.\//, '') + '  alert ' + c.alert + ' · confirm ' + c.confirm + ' · prompt ' + c.prompt));
    console.log('          TOTAL  alert ' + tot.alert + ' · confirm ' + tot.confirm + ' · prompt ' + tot.prompt + '  (' + rows.length + ' files)');
  }

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
