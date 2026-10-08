/* home.utils.js — constants and DOM helpers for Home V2
 * Every visible text is a Strings System key (twT · tw_strings.json — home.*). */
(function () {
  'use strict';
  window.Home = window.Home || {};

  var JOB_TYPES = ['full_time', 'part_time', 'remote', 'contract', 'internship'];
  var NEWS_CATS = ['general', 'labor_law', 'opportunity', 'ministry', 'platform', 'agreement'];

  window.Home.utils = {
    /* job_type / news category code → label (unknown code shown as is) */
    jobType: function (code) {
      return JOB_TYPES.indexOf(code) !== -1 ? twT('home.job_type.' + code) : code;
    },

    newsCat: function (code) {
      return NEWS_CATS.indexOf(code) !== -1 ? twT('home.news_cat.' + code) : code;
    },

    /* empty state per filter → { h, p } */
    emptyLabels: function (filter) {
      var f = ['all', 'opportunities', 'posts', 'news'].indexOf(filter) !== -1 ? filter : 'all';
      return { h: twT('home.empty.' + f), p: twT(f === 'news' ? 'home.empty.news_sub' : 'home.empty.sub') };
    },

    timeAgo: function (iso) {
      if (!iso) return '';
      var diff = (Date.now() - new Date(iso).getTime()) / 1000;
      if (!(diff >= 60))    return twT('home.time.now');
      if (diff < 3600)      return twT('home.time.min',   { n: Math.floor(diff / 60) });
      if (diff < 86400)     return twT('home.time.hour',  { n: Math.floor(diff / 3600) });
      if (diff < 2592000)   return twT('home.time.day',   { n: Math.floor(diff / 86400) });
      if (diff < 31536000)  return twT('home.time.month', { n: Math.floor(diff / 2592000) });
      return twT('home.time.year', { n: Math.floor(diff / 31536000) });
    },

    el: function (tag, cls) {
      var e = document.createElement(tag);
      if (cls) e.className = cls;
      return e;
    },

    txt: function (tag, cls, content) {
      var e = this.el(tag, cls);
      e.textContent = content;
      return e;
    },

    /* DS-ICON element (twIconEl) — name = registry meaning name */
    icon: function (name, size) {
      return twIconEl(name, { size: size || 'sm' });
    },

    safeInt: function (v) { return parseInt(v, 10) || 0; },

    /* <i data-tw-icon> placeholders → SVG (DS-ICON) */
    icons: function (root) { if (window.twIcon) twIcon.hydrate(root || document.body); }
  };
}());
