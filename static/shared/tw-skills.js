// static/shared/tw-skills.js
// Shared skill catalog loader and search helpers.
// Namespace: window.TW
// Load order: after tw-options-data.js, before any page skill module.
//
// Data flow:
//   1. On load — TW._catalog is pre-populated from TW.SKILL_CATALOG (static fallback, ~90 skills)
//   2. Async   — fetch('/skills/catalog') replaces TW._catalog with full DB list (~335 skills)
//   3. Helpers — TW.searchSkills / normalizeSkill / getSkillIcon always read TW._catalog
//
// Internal catalog format: { slug, en, ar, kw, icon }
// DB API format:            { id, slug, name_en, name_ar, keywords, icon, category_group, sort_order }
// TW.SKILL_CATALOG format:  { slug, name_ar, icon, group }

(function () {
  'use strict';

  window.TW = window.TW || {};

  var _FALLBACK_ICON = 'circle-check';

  // ── Format converters ──────────────────────────────────────────
  function _fromApi(item) {
    return {
      slug: item.slug,
      en:   item.name_en  || item.slug,
      ar:   item.name_ar  || item.slug,
      kw:   item.keywords || '',
      icon: item.icon     || _FALLBACK_ICON,
    };
  }

  function _fromStaticFallback(item) {
    // TW.SKILL_CATALOG: { slug, name_ar, icon, group }
    // en: use name_ar if it looks like ASCII (e.g. "Python"), else derive from slug
    var en = item.name_ar && /^[\x20-\x7E]+$/.test(item.name_ar.trim())
      ? item.name_ar.trim()
      : item.slug.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    return {
      slug: item.slug,
      en:   en,
      ar:   item.name_ar  || en,
      kw:   '',
      icon: item.icon     || _FALLBACK_ICON,
    };
  }

  // ── Initialize catalog from static fallback ───────────────────
  TW._catalog = [];
  TW._catalogReady = false;

  (function _seedFromFallback() {
    var fb = TW.SKILL_CATALOG;
    if (!fb || !fb.length) return;
    TW._catalog = fb.map(_fromStaticFallback);
  })();

  // ── Async fetch from DB ───────────────────────────────────────
  var _pendingCallbacks = [];

  function _notifyReady() {
    TW._catalogReady = true;
    for (var i = 0; i < _pendingCallbacks.length; i++) {
      try { _pendingCallbacks[i](TW._catalog); } catch (e) {}
    }
    _pendingCallbacks = [];
  }

  function _fetchCatalog() {
    fetch('/skills/catalog')
      .then(function (r) {
        if (!r.ok) throw new Error('skills/catalog ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (Array.isArray(data) && data.length) {
          TW._catalog = data.map(_fromApi);
        }
        _notifyReady();
      })
      .catch(function () {
        // API failed — static fallback stays in TW._catalog; mark ready anyway
        _notifyReady();
      });
  }

  _fetchCatalog();

  // ── TW.loadSkillCatalog(callback) ────────────────────────────
  // Call callback(catalog) immediately if already loaded, else queue it.
  TW.loadSkillCatalog = function (cb) {
    if (TW._catalogReady) {
      if (cb) try { cb(TW._catalog); } catch (e) {}
    } else {
      if (cb) _pendingCallbacks.push(cb);
    }
  };

  // ── TW._getSkillEntry(name) ───────────────────────────────────
  // Returns { slug, en, ar, kw, icon } or null.
  // Matches by en (case-insensitive), slug, or ar.
  TW._getSkillEntry = function (name) {
    if (!name) return null;
    var nl = name.toLowerCase().trim();
    var cat = TW._catalog;
    for (var i = 0; i < cat.length; i++) {
      var s = cat[i];
      if (s.slug === nl || s.en.toLowerCase() === nl || s.ar === name.trim()) return s;
    }
    return null;
  };

  // ── TW._isOfficialSkill(name) ─────────────────────────────────
  TW._isOfficialSkill = function (name) {
    return !!TW._getSkillEntry(name);
  };

  // ── TW.searchSkills(q, maxResults) ───────────────────────────
  // Returns up to maxResults (default 8) matching catalog entries.
  TW.searchSkills = function (q, maxResults) {
    if (!q || q.length < 1) return [];
    var max = maxResults || 8;
    var ql = q.toLowerCase();
    var results = [];
    var cat = TW._catalog;
    for (var i = 0; i < cat.length; i++) {
      var s = cat[i];
      if (s.en.toLowerCase().indexOf(ql) !== -1
       || s.ar.indexOf(q) !== -1
       || s.slug.indexOf(ql) !== -1
       || s.kw.toLowerCase().indexOf(ql) !== -1) {
        results.push(s);
        if (results.length >= max) break;
      }
    }
    return results;
  };

  // ── TW.normalizeSkill(raw) ────────────────────────────────────
  // Returns canonical en name if found in catalog, else returns trimmed raw.
  TW.normalizeSkill = function (raw) {
    if (!raw) return '';
    var cleaned = raw.trim();
    var ql = cleaned.toLowerCase();
    var cat = TW._catalog;
    for (var i = 0; i < cat.length; i++) {
      var s = cat[i];
      if (s.slug === ql || s.en.toLowerCase() === ql || s.ar === cleaned) return s.en;
      var kws = s.kw.split(' ');
      for (var j = 0; j < kws.length; j++) {
        if (kws[j] && kws[j].toLowerCase() === ql) return s.en;
      }
    }
    return cleaned;
  };

  // ── TW.getSkillIcon(name) ─────────────────────────────────────
  // Returns Lucide icon name string (falls back to _FALLBACK_ICON).
  TW.getSkillIcon = function (name) {
    var entry = TW._getSkillEntry(name);
    return (entry && entry.icon) ? entry.icon : _FALLBACK_ICON;
  };

}());
