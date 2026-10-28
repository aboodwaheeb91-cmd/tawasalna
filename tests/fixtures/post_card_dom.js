/**
 * post_card_dom.js — tiny DOM for the TwPostCard behaviour tests (task U.2b).
 * Parses the real TwPostCard.html markup (tags / attributes / text) into elements that
 * support what tw-post-card.js uses: querySelector(All) / closest with compound selectors
 * (tag · .class · #id · [attr] · [attr="v"]), classList, dataset, style, innerHTML,
 * outerHTML, textContent, getAttribute, addEventListener + click dispatch with bubbling.
 *
 * Usage: const { makeDocument } = require('./fixtures/post_card_dom.js');
 *        const doc = makeDocument(); const list = doc.createElement('div'); list.innerHTML = html;
 *        doc.body.appendChild(list); doc.click(el);
 */
'use strict';

const VOID = new Set(['img', 'br', 'hr', 'input', 'meta', 'link']);

function camelToData(k) { return 'data-' + k.replace(/[A-Z]/g, c => '-' + c.toLowerCase()); }

function parseSelector(sel) {
  const out = { tag: null, id: null, classes: [], attrs: [] };
  const re = /([a-zA-Z][\w-]*)|\.([\w-]+)|#([\w-]+)|\[([\w-]+)(?:="([^"]*)")?\]/g;
  let m;
  while ((m = re.exec(sel))) {
    if (m[1]) out.tag = m[1].toLowerCase();
    else if (m[2]) out.classes.push(m[2]);
    else if (m[3]) out.id = m[3];
    else out.attrs.push([m[4], m[5]]);
  }
  return out;
}

function makeDocument() {
  const listeners = new Map();   // element → { type: [fn] }

  class El {
    constructor(tag) {
      this.tagName = tag.toUpperCase(); this._tag = tag.toLowerCase();
      this.attrs = {}; this.children = []; this.parentNode = null; this.style = {};
      const self = this;
      this.classList = {
        contains: c => self._classes().includes(c),
        add: c => { const l = self._classes(); if (!l.includes(c)) { l.push(c); self.attrs.class = l.join(' '); } },
        remove: c => { self.attrs.class = self._classes().filter(x => x !== c).join(' '); },
        toggle: c => (self.classList.contains(c) ? (self.classList.remove(c), false) : (self.classList.add(c), true)),
      };
      this.dataset = new Proxy({}, {
        get: (_, k) => (typeof k === 'string' ? self.attrs[camelToData(k)] : undefined),
        set: (_, k, v) => { self.attrs[camelToData(k)] = String(v); return true; },
      });
    }
    _classes() { return (this.attrs.class || '').split(/\s+/).filter(Boolean); }
    get id() { return this.attrs.id || ''; }
    get className() { return this.attrs.class || ''; }
    set className(v) { this.attrs.class = String(v); }   // task 8.6b-1 — comments build with the DOM API
    set id(v) { this.attrs.id = String(v); }
    get href() { return this.attrs.href || ''; }
    set href(v) { this.attrs.href = String(v); }
    getAttribute(n) { return n in this.attrs ? this.attrs[n] : null; }
    setAttribute(n, v) { this.attrs[n] = String(v); if (n === 'style') this._parseStyle(); }
    _parseStyle() {
      this.style = {};
      String(this.attrs.style || '').split(';').forEach(p => {
        const i = p.indexOf(':'); if (i < 0) return;
        const k = p.slice(0, i).trim().replace(/-([a-z])/g, (_, c) => c.toUpperCase());
        this.style[k] = p.slice(i + 1).trim();
      });
    }
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; }
    removeChild(c) { this.children = this.children.filter(x => x !== c); c.parentNode = null; return c; }
    insertBefore(c, ref) {   // task 8.6b-1 — comments
      if (!ref) return this.appendChild(c);
      c.parentNode = this; this.children.splice(this.children.indexOf(ref), 0, c); return c;
    }
    remove() { if (this.parentNode) this.parentNode.removeChild(this); }
    contains(o) { for (let e = o; e; e = e.parentNode) if (e === this) return true; return false; }
    matches(sel) {
      return sel.split(',').some(s => {
        const p = parseSelector(s.trim());
        if (p.tag && p.tag !== this._tag) return false;
        if (p.id && this.attrs.id !== p.id) return false;
        if (!p.classes.every(c => this.classList.contains(c))) return false;
        return p.attrs.every(([n, v]) => (n in this.attrs) && (v === undefined || this.attrs[n] === v));
      });
    }
    closest(sel) { for (let e = this; e && e.matches; e = e.parentNode) if (e.matches(sel)) return e; return null; }
    _walk(fn) { this.children.forEach(c => { if (c instanceof El) { fn(c); c._walk(fn); } }); }
    querySelectorAll(sel) { const r = []; this._walk(e => { if (e.matches(sel)) r.push(e); }); return r; }
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
    get textContent() { return this.children.map(c => (c instanceof El ? c.textContent : c.text)).join(''); }
    set textContent(t) { this.children = [{ text: String(t) }]; }
    get innerHTML() { return this.children.map(c => (c instanceof El ? c.outerHTML : c.text)).join(''); }
    set innerHTML(h) { this.children = []; parseInto(this, String(h)); }
    get outerHTML() {
      const a = Object.keys(this.attrs).map(k => ' ' + k + '="' + this.attrs[k] + '"').join('');
      return '<' + this._tag + a + '>' + (VOID.has(this._tag) ? '' : this.innerHTML + '</' + this._tag + '>');
    }
    addEventListener(type, fn) {
      if (!listeners.has(this)) listeners.set(this, {});
      (listeners.get(this)[type] = listeners.get(this)[type] || []).push(fn);
    }
    select() {}
  }

  function decode(s) {
    return s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'").replace(/&#8943;/g, '⋯').replace(/&amp;/g, '&');
  }

  function parseInto(root, html) {
    const re = /<(\/?)([a-zA-Z][\w-]*)((?:\s+[\w:-]+(?:="[^"]*")?)*)\s*(\/?)>|([^<]+)/g;
    let cur = root, m;
    while ((m = re.exec(html))) {
      if (m[5] !== undefined) { cur.children.push({ text: decode(m[5]) }); continue; }
      const tag = m[2].toLowerCase();
      if (m[1]) { if (cur !== root) cur = cur.parentNode; continue; }
      const el = new El(tag);
      (m[3].match(/[\w:-]+(?:="[^"]*")?/g) || []).forEach(a => {
        const i = a.indexOf('=');
        if (i < 0) el.attrs[a] = ''; else el.attrs[a.slice(0, i)] = decode(a.slice(i + 2, -1));
      });
      el._parseStyle();
      cur.appendChild(el);
      if (!m[4] && !VOID.has(tag)) cur = el;
    }
  }

  const body = new El('body');
  const docListeners = {};
  const document = {
    body,
    createElement: t => new El(t),
    createTextNode: t => ({ text: String(t) }),
    getElementById: id => body.querySelector('#' + id),
    querySelector: s => body.querySelector(s),
    querySelectorAll: s => body.querySelectorAll(s),
    addEventListener: (t, fn) => { (docListeners[t] = docListeners[t] || []).push(fn); },
    execCommand: () => true,
    // dispatch a click on el: bubbles el → … → body → document (stopPropagation honoured)
    click(el) {
      let stopped = false;
      const e = { target: el, stopPropagation() { stopped = true; }, preventDefault() {} };
      for (let n = el; n && !stopped; n = n.parentNode) {
        const l = listeners.get(n);
        if (l && l.click) l.click.forEach(fn => fn(e));
      }
      if (!stopped) (docListeners.click || []).forEach(fn => fn(e));
    },
  };
  return document;
}

module.exports = { makeDocument };
