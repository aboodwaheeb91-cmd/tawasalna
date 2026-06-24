/* home.utils.js — constants and DOM helpers for Home V2 */
(function () {
  'use strict';
  window.Home = window.Home || {};

  window.Home.utils = {
    JOB_TYPES: {
      full_time: 'دوام كامل', part_time: 'دوام جزئي',
      remote: 'عن بُعد', contract: 'عقد', internship: 'تدريب'
    },

    NEWS_CATS: {
      general:    'عام',            labor_law:  'قانون العمل',
      opportunity:'فرصة',           ministry:   'وزارة العمل',
      platform:   'أخبار المنصة',   agreement:  'اتفاقية'
    },

    EMPTY_LABELS: {
      all:           { h: 'لا يوجد محتوى بعد',        p: 'ارجع لاحقاً أو جرّب فلتراً آخر' },
      opportunities: { h: 'لا توجد فرص حالياً',        p: 'ارجع لاحقاً أو جرّب فلتراً آخر' },
      posts:         { h: 'لا توجد منشورات بعد',        p: 'ارجع لاحقاً أو جرّب فلتراً آخر' },
      news:          { h: 'لا توجد أخبار منشورة بعد',  p: 'ستظهر هنا الأخبار الرسمية والإعلانات عند نشرها' }
    },

    timeAgo: function (iso) {
      if (!iso) return '';
      var diff = (Date.now() - new Date(iso).getTime()) / 1000;
      if (diff < 60)        return 'الآن';
      if (diff < 3600)      return Math.floor(diff / 60)      + ' د';
      if (diff < 86400)     return Math.floor(diff / 3600)    + ' س';
      if (diff < 2592000)   return Math.floor(diff / 86400)   + ' ي';
      if (diff < 31536000)  return Math.floor(diff / 2592000) + ' ش';
      return Math.floor(diff / 31536000) + ' سنة';
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

    makeAvatar: function (cls, name, avatarUrl) {
      var wrap = this.el('div', cls);
      if (avatarUrl) {
        var img = this.el('img');
        img.alt = '';
        img.setAttribute('loading', 'lazy');
        img.src = avatarUrl;
        wrap.appendChild(img);
      } else {
        wrap.textContent = (name || '?').charAt(0).toUpperCase();
      }
      return wrap;
    },

    safeInt: function (v) { return parseInt(v, 10) || 0; },

    icons: function () { if (window.lucide) lucide.createIcons(); }
  };
}());
