// static/shared/tw-post-card.js — Post Card component (DS-CARD · task U.2 · CARDS.md CARD-03 / CARD-12)
//
// The one post card renderer. U.2 moved the company page card (company.render.js →
// _postCardHtml) here as-is: same DOM, same classes, same data-*, same escaping, same text.
// Behaviour (appreciate / save desired-state queue, comments panel, view tracking, ⋯ menu)
// stays in company.posts.js — it binds by event delegation on the classes / data-* below.
//
// Usage:
//   TwPostCard.html(post, { authorName, avatarUrl, canEdit }) → HTML string (one .post-card)
//     post       — a /company/posts item: id · body · tags[] · theme_color · created_at ·
//                  views_count · appreciations_count · viewer_appreciated · comments_enabled ·
//                  comments_count · viewer_saved
//     authorName — name in the head (escaped here) · first char = avatar fallback
//     avatarUrl  — raw URL; passes twSafeImageUrl here (unsafe → initial letter)
//     canEdit    — true → ⋯ owner menu (edit / delete) · false → none (visitor)
//   TwPostCard.apprButtonInner(active, count) → inner HTML of .pc-btn--appr (icon + label)
//   TwPostCard.saveButtonInner(active)        → inner HTML of .pc-btn--save (icon + label)
//   TwPostCard.initClamps(container)          → 3-line clamp + «المزيد» for every .post-body-wrap
//   TwPostCard.relativeTime(iso) · TwPostCard.formatViews(n) — the card's meta formatters
//
// All user / API text goes through twEscHtml / twEscAttr (tw_shared.js) — resolved at call time.
(function () {
  'use strict';

  // Inline SVGs (DS-ICON conversion = U.3)
  var ICO_EDIT   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';
  var ICO_TRASH  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>';
  var ICO_EYE    = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
  var ICO_CLOCK  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
  var ICO_SHARE  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>';
  var ICO_HEART_OUTLINE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';
  var ICO_HEART_FILLED  = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';
  var ICO_COMMENT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  var ICO_BOOKMARK       = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>';
  var ICO_BOOKMARK_CHECK = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/><path d="M8.5 10l2.5 2.5 5-5" fill="none" stroke="var(--color-surface-page)" stroke-width="2"/></svg>';
  var ICO_MORE = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 8v8"/><path d="m8 12 4 4 4-4"/></svg>';
  var ICO_LESS = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="m16 12-4-4-4 4"/><path d="M12 16V8"/></svg>';

  function _truthy(v) { return v === true || v === 'true' || v === 1; }

  function relativeTime(iso) {
    if (!iso) return '';
    var then = new Date(iso).getTime();
    if (isNaN(then)) return '';
    var diff = Math.floor((Date.now() - then) / 1000);
    if (diff < 60)      return 'الآن';
    if (diff < 3600)    return 'منذ ' + Math.floor(diff / 60) + ' دقيقة';
    if (diff < 86400)   return 'منذ ' + Math.floor(diff / 3600) + ' ساعة';
    if (diff < 604800)  return 'منذ ' + Math.floor(diff / 86400) + ' يوم';
    if (diff < 2592000) return 'منذ ' + Math.floor(diff / 604800) + ' أسبوع';
    return new Date(iso).toLocaleDateString('ar');
  }

  function formatViews(n) {
    n = Number(n) || 0;
    if (n >= 1000) { var k = n / 1000; return (k % 1 === 0 ? k : k.toFixed(1)) + 'K مشاهدة'; }
    return n + ' مشاهدة';
  }

  function apprButtonInner(active, count) {
    return (active ? ICO_HEART_FILLED : ICO_HEART_OUTLINE) + (count > 0 ? ('أقدّر · ' + count) : 'أقدّر');
  }

  function saveButtonInner(active) {
    return (active ? ICO_BOOKMARK_CHECK : ICO_BOOKMARK) + (active ? 'محفوظ' : 'حفظ');
  }

  function html(post, opts) {
    opts = opts || {};
    var esc = window.twEscHtml, escAttr = window.twEscAttr;
    var name      = opts.authorName;
    var avatarUrl = window.twSafeImageUrl(opts.avatarUrl || '');

    // Resolve theme color — null/unknown → teal
    var colorKey = (post.theme_color && window.TW && TW.POST_THEME_COLORS && TW.POST_THEME_COLORS[post.theme_color])
      ? post.theme_color : 'teal';
    var clr = (window.TW && TW.POST_THEME_COLORS && TW.POST_THEME_COLORS[colorKey])
      || { accent: 'var(--color-categorical-teal)', soft: 'rgba(var(--color-categorical-teal-rgb),.12)', glow: 'rgba(var(--color-categorical-teal-rgb),.18)' };
    var cardStyle = '--pa:' + clr.accent + '; --pa-s:' + clr.soft + '; --pa-g:' + clr.glow;

    // Avatar: real logo or initial letter
    var avaContent = avatarUrl
      ? '<img src="' + escAttr(avatarUrl) + '" alt="">'
      : '<span class="post-ava--init">' + esc((name || '?').charAt(0)) + '</span>';

    // Tags — themed class so they inherit --pa from the card
    var tagsHtml = '';
    if (post.tags && post.tags.length) {
      tagsHtml = '<div class="job-tags">' + post.tags.map(function (t) {
        return '<span class="jtag jtag-themed">' + esc(t) + '</span>';
      }).join('') + '</div>';
    }

    // 3-dot owner menu
    var pid = escAttr(String(post.id));
    var dotsHtml = opts.canEdit
      ? '<div class="pc-dots">'
          + '<button class="pc-dots-btn" data-post-id="' + pid + '" aria-label="خيارات">&#8943;</button>'
          + '<div class="pc-dots-menu" id="pc-dm-' + pid + '">'
            + '<button class="pc-dots-edit" data-post-id="' + pid + '">' + ICO_EDIT + 'تعديل</button>'
            + '<button class="pc-dots-delete" data-post-id="' + pid + '">' + ICO_TRASH + 'حذف</button>'
          + '</div>'
        + '</div>'
      : '';

    var commentsOn = post.comments_enabled !== false;
    var appCount   = Number(post.appreciations_count) || 0;
    var appActive  = _truthy(post.viewer_appreciated);
    var cmtCount   = Number(post.comments_count) || 0;
    var saveActive = _truthy(post.viewer_saved);

    return '<div class="post-card" data-post-id="' + pid + '" style="' + cardStyle + '">'
      + '<div class="post-head">'
        + '<div class="post-ava">' + avaContent + '</div>'
        + '<div class="post-head-info">'
          + '<div class="post-nm">' + esc(name) + '</div>'
          + '<div class="post-meta-row">'
            + '<span class="post-date">' + ICO_CLOCK + relativeTime(post.created_at) + '</span>'
            + '<span class="post-views" data-views-count="' + (Number(post.views_count) || 0) + '">' + ICO_EYE + formatViews(post.views_count) + '</span>'
          + '</div>'
        + '</div>'
        + dotsHtml
      + '</div>'
      + '<div class="post-body-wrap">'
        + '<div class="post-body">'
          + '<span class="post-body-text">' + esc(post.body) + '</span>'
          + '<button type="button" class="post-more-inline" aria-label="عرض المزيد">'
            + '<span class="post-more-ellipsis">…</span>'
            + ICO_MORE
          + '</button>'
        + '</div>'
        + '<button type="button" class="post-less-btn" aria-label="عرض أقل">'
          + ICO_LESS
        + '</button>'
      + '</div>'
      + tagsHtml
      + '<div class="pc-actions">'
        + '<button class="pc-btn pc-btn--appr' + (appActive ? ' appr-active' : '') + '" data-post-id="' + pid + '" data-appr-count="' + appCount + '">' + apprButtonInner(appActive, appCount) + '</button>'
        + (commentsOn
            ? '<button class="pc-btn pc-btn--cmt" data-post-id="' + pid + '" data-cmt-count="' + cmtCount + '">' + ICO_COMMENT + (cmtCount > 0 ? ('تعليق · ' + cmtCount) : 'تعليق') + '</button>'
            : '')
        + '<button class="pc-btn pc-btn--share" data-post-id="' + pid + '">' + ICO_SHARE + 'مشاركة</button>'
        + '<button class="pc-btn pc-btn--save' + (saveActive ? ' save-active' : '') + '" data-post-id="' + pid + '" data-saved="' + (saveActive ? '1' : '0') + '">' + saveButtonInner(saveActive) + '</button>'
      + '</div>'
      + (commentsOn ? '<div class="pc-cmts-panel" id="pc-cmt-panel-' + pid + '" data-post-id="' + pid + '" style="display:none"></div>' : '')
    + '</div>';
  }

  // 3-line clamp: short posts → unclamped · long → binary search to the last word that fits.
  function initClamps(container) {
    container.querySelectorAll('.post-body-wrap').forEach(function (wrap) {
      var body      = wrap.querySelector('.post-body');
      var textSpan  = wrap.querySelector('.post-body-text');
      var moreBtn   = wrap.querySelector('.post-more-inline');
      if (!body || !textSpan || !moreBtn) return;

      var fullText = textSpan.textContent;
      var lh       = parseFloat(getComputedStyle(body).lineHeight) || 22;
      var maxH     = Math.round(lh * 3);

      // scrollHeight works on webkit-line-clamp elements in Chromium (reports true height).
      // Use it to decide whether truncation is needed.
      if (body.scrollHeight <= maxH + 2) {
        // Short post — remove CSS clamp so inline button slot stays hidden & display is normal.
        body.style.cssText = 'display:block;overflow:visible';
        return;
      }

      // Need truncation — switch to unclamped block for binary-search measurements.
      body.style.cssText = 'display:block;overflow:visible';
      moreBtn.style.display = 'inline-flex'; // button width (ellipsis + icon) must be included in measurements

      var lo = 0, hi = fullText.length;
      while (lo < hi - 1) {
        var mid = (lo + hi) >> 1;
        textSpan.textContent = fullText.slice(0, mid);
        if (body.scrollHeight <= maxH + 2) { lo = mid; } else { hi = mid; }
      }

      // Snap to nearest Arabic word boundary (last space)
      var raw       = fullText.slice(0, lo).replace(/\s+$/, '');
      var lastSpace = raw.lastIndexOf(' ');
      // Only snap if the space is reasonably close (keeps at least 60% of lo chars)
      var trimmed   = (lastSpace > lo * 0.6) ? raw.slice(0, lastSpace) : raw;

      textSpan.textContent = trimmed;
      // Store full/short text on the element for the toggle handlers
      wrap._pbFull  = fullText;
      wrap._pbShort = trimmed;
    });
  }

  window.TwPostCard = {
    html: html,
    apprButtonInner: apprButtonInner,
    saveButtonInner: saveButtonInner,
    initClamps: initClamps,
    relativeTime: relativeTime,
    formatViews: formatViews
  };
}());
