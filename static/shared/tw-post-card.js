// static/shared/tw-post-card.js — Post Card component (DS-CARD · task U.2 · CARDS.md CARD-03 / CARD-12)
//
// The one post card renderer + its button behaviour. U.2 moved the company page card
// (company.render.js → _postCardHtml) here as-is: same DOM, same classes, same data-*, same
// escaping, same text. U.2b moved the behaviour (appreciate / save desired-state queue, view
// tracking, comments panel open / close, ⋯ menu, share) from company.posts.js as-is — bound by
// event delegation on the classes / data-* below. Styles: static/shared/tw-card.css.
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
//   TwPostCard.create(opts) → { bind(root), trackViews(container), toggleComments(id) }
//     page-specific parts (API paths, session check, share info, edit / delete, comments)
//     come in opts — see create() below
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

  // ── Behaviour (task U.2b — moved from company.posts.js as-is) ─────────────
  // create(opts) → one controller per page. Everything page-specific comes in opts;
  // the component knows nothing about the page it is on.
  //   opts.signedIn()          → bool (session check — the page's own snapshot helper)
  //   opts.paths.appreciation(id) · opts.paths.save(id) · opts.paths.view(id) → API path (twApi)
  //   opts.visitorKeyName      → localStorage key of the anonymous view key (guests only)
  //   opts.shareInfo(id)       → { name, url } for the share text
  //   opts.onEdit(id) · opts.onDelete(id) — ⋯ menu items (id = integer, menu already closed)
  //   opts.comments.build(id) · opts.comments.load(id) — the comments system (§22c) fills
  //                              the panel; the component only opens / closes it
  // Controller: bind(root) — click delegation on the list (once) · trackViews(container) —
  // after every render · toggleComments(id).
  var _dotsCloseBound = false;

  function create(opts) {
    opts = opts || {};
    var paths    = opts.paths || {};
    var comments = opts.comments || {};
    function signedIn() { return !!(opts.signedIn && opts.signedIn()); }
    function toast(msg, type) { if (window.showToast) showToast(msg, type); }
    function cardBtn(postId, cls) {
      var card = document.querySelector('.post-card[data-post-id="' + postId + '"]');
      return card ? card.querySelector(cls) : null;
    }

    // ── Save — desired-state queue (one request in flight per post, UI immediate) ──
    function renderSave(btn, active) {
      btn.innerHTML = saveButtonInner(active);
      if (active) { btn.classList.add('save-active');    }
      else        { btn.classList.remove('save-active'); }
      btn.dataset.saved = active ? '1' : '0';
    }

    var _saveDesired   = {};
    var _saveInFlight  = {};
    var _saveOrigState = {};

    function dispatchSave(postId) {
      var desired = _saveDesired[postId];
      if (desired === undefined) return;
      if (!signedIn()) return;

      _saveInFlight[postId] = true;

      twApi(paths.save(postId), { method: 'PUT', body: { saved: desired } })
        .then(function (res) {
          _saveInFlight[postId] = false;
          var btn  = cardBtn(postId, '.pc-btn--save');
          var orig = _saveOrigState[postId];

          if (res.status === 429) {
            if (btn && orig) renderSave(btn, orig.active);
            delete _saveDesired[postId];
            delete _saveOrigState[postId];
            toast('الرجاء التمهّل قليلاً', 'error');
            return;
          }

          if (!res.ok || !res.data || res.data.status !== 'success') {
            if (btn && orig) renderSave(btn, orig.active);
            delete _saveDesired[postId];
            delete _saveOrigState[postId];
            toast(twApiMessage(res, 'تعذّر حفظ المنشور'), 'error');
            return;
          }

          var srvActive = !!res.data.saved;
          var desired   = _saveDesired[postId];

          if (desired !== undefined && desired !== srvActive) {
            _saveOrigState[postId] = { active: srvActive };
            dispatchSave(postId);
            return;
          }

          if (btn) renderSave(btn, srvActive);
          delete _saveDesired[postId];
          delete _saveOrigState[postId];
        });
    }

    function toggleSave(postId) {
      if (!signedIn()) {
        toast('سجّل دخولك لحفظ المنشور', 'info');
        return;
      }
      var btn = cardBtn(postId, '.pc-btn--save');
      if (!btn) return;

      var currentActive = btn.classList.contains('save-active');
      var desired       = !currentActive;

      if (!_saveInFlight[postId]) {
        _saveOrigState[postId] = { active: currentActive };
      }

      _saveDesired[postId] = desired;
      renderSave(btn, desired);

      if (_saveInFlight[postId]) return;
      dispatchSave(postId);
    }

    // ── Appreciation — same desired-state queue ──
    function renderAppr(btn, active, count) {
      if (active) { btn.classList.add('appr-active');    }
      else        { btn.classList.remove('appr-active'); }
      btn.dataset.apprCount = count;
      btn.innerHTML = apprButtonInner(active, count);
    }

    var _apprDesired   = {};  // postId -> bool  (last desired state)
    var _apprInFlight  = {};  // postId -> bool  (request running?)
    var _apprOrigState = {};  // postId -> {active, count}  (pre-click state for rollback)

    function dispatchAppr(postId) {
      var desired = _apprDesired[postId];
      if (desired === undefined) return;
      if (!signedIn()) return;

      _apprInFlight[postId] = true;

      twApi(paths.appreciation(postId), { method: 'PUT', body: { appreciated: desired } })
        .then(function (res) {
          _apprInFlight[postId] = false;
          var btn = cardBtn(postId, '.pc-btn--appr');
          var orig = _apprOrigState[postId];

          if (res.status === 403 || res.status === 429) {
            // Owner / rate-limit — full rollback, clear queue
            if (btn && orig) renderAppr(btn, orig.active, orig.count);
            delete _apprDesired[postId];
            delete _apprOrigState[postId];
            toast(res.status === 403 ? 'لا يمكنك تقدير منشورك' : 'الرجاء التمهّل قليلاً', 'error');
            return;
          }

          if (!res.ok || !res.data || res.data.status !== 'success') {
            if (btn && orig) renderAppr(btn, orig.active, orig.count);
            delete _apprDesired[postId];
            delete _apprOrigState[postId];
            toast(twApiMessage(res, 'تعذّر تسجيل التقدير'), 'error');
            return;
          }

          var srvActive = !!res.data.appreciated;
          var srvCount  = Number(res.data.appreciations_count) || 0;
          var desired   = _apprDesired[postId];

          if (desired !== undefined && desired !== srvActive) {
            // Server response is stale — user clicked again while request was in flight.
            // Keep UI on desired (no flicker); update orig for accurate rollback on failure.
            _apprOrigState[postId] = { active: srvActive, count: srvCount };
            dispatchAppr(postId);
            return;
          }

          // Server matches desired (or no pending desired) — safe to sync UI.
          if (btn) renderAppr(btn, srvActive, srvCount);
          delete _apprDesired[postId];
          delete _apprOrigState[postId];
        });
    }

    function toggleAppr(postId) {
      if (!signedIn()) {
        toast('سجّل دخولك لتقدّر هذا المنشور', 'info');
        return;
      }

      var btn = cardBtn(postId, '.pc-btn--appr');
      if (!btn) return;

      // Current UI state (reflects latest desired, not server)
      var currentActive = btn.classList.contains('appr-active');
      var currentCount  = parseInt(btn.dataset.apprCount, 10) || 0;
      var desired       = !currentActive;
      var nextCount     = desired ? currentCount + 1 : Math.max(0, currentCount - 1);

      // Capture original state only before the first in-flight request
      if (!_apprInFlight[postId]) {
        _apprOrigState[postId] = { active: currentActive, count: currentCount };
      }

      // Record desired and update UI immediately
      _apprDesired[postId] = desired;
      renderAppr(btn, desired, nextCount);

      // If already in flight, the response handler will pick up the new desired
      if (_apprInFlight[postId]) return;

      dispatchAppr(postId);
    }

    // ── View tracking ──
    var _viewedThisSession = {};  // post_id → true; resets on page reload
    var _postViewObserver  = null;

    function visitorKey() {
      var key = localStorage.getItem(opts.visitorKeyName);
      if (!key) {
        key = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
          var r = Math.random() * 16 | 0;
          return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
        });
        localStorage.setItem(opts.visitorKeyName, key);
      }
      return key;
    }

    function sendView(postId) {
      var body = {};
      if (!signedIn()) body.visitor_key = visitorKey();

      twApi(paths.view(postId), { method: 'POST', body: body })
        .then(function (res) {
          var d = res.ok ? res.data : null;   // best-effort — a failed view is not shown
          if (d && d.status === 'success' && d.recorded) {
            // Bump the displayed count +1 without a full reload
            var vEl = cardBtn(postId, '.post-views');
            if (!vEl) return;
            var cur = parseInt(vEl.dataset.viewsCount, 10) || 0;
            var next = cur + 1;
            vEl.dataset.viewsCount = next;
            var svg = vEl.querySelector('svg');
            vEl.innerHTML = (svg ? svg.outerHTML : '') + formatViews(next);
          }
        });
    }

    function trackViews(container) {
      // Disconnect previous observer if list was re-rendered
      if (_postViewObserver) { _postViewObserver.disconnect(); _postViewObserver = null; }
      if (!container || typeof IntersectionObserver === 'undefined') return;

      var DWELL_MS = 800; // card must be visible for 800ms before counting
      var timers   = {};  // post_id → timeout handle

      _postViewObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          var pid = entry.target.dataset.postId;
          if (!pid || _viewedThisSession[pid]) return;
          if (entry.isIntersecting) {
            if (!timers[pid]) {
              timers[pid] = setTimeout(function () {
                delete timers[pid];
                if (!_viewedThisSession[pid]) {
                  _viewedThisSession[pid] = true;
                  sendView(pid);
                }
              }, DWELL_MS);
            }
          } else {
            // Card left viewport before dwell time — cancel timer
            if (timers[pid]) { clearTimeout(timers[pid]); delete timers[pid]; }
          }
        });
      }, { threshold: 0.5 });  // 50% of card must be visible

      container.querySelectorAll('.post-card[data-post-id]').forEach(function (card) {
        _postViewObserver.observe(card);
      });
    }

    // ── Comments panel open / close (content = opts.comments) ──
    var _openPanelId = null; // postId whose panel is currently visible
    function panelOf(postId) { return document.getElementById('pc-cmt-panel-' + postId); }

    function toggleComments(postId) {
      var pid = String(postId);

      // Close any other open panel
      if (_openPanelId && _openPanelId !== pid) {
        var old = panelOf(_openPanelId);
        if (old) old.style.display = 'none';
        _openPanelId = null;
      }

      var panel = panelOf(pid);
      if (!panel) return; // comments_enabled=false — no panel in DOM

      if (panel.style.display !== 'none') {
        panel.style.display = 'none';
        _openPanelId = null;
        return;
      }

      // First open: build input row + list shell
      if (comments.build) comments.build(pid);
      panel.style.display = '';
      if (comments.load) comments.load(pid);
      _openPanelId = pid;
    }

    // ── Share (same text / fallbacks as before — /post/{id} = U.6) ──
    function shareFallback(text) {
      var ta = document.createElement('textarea');
      ta.value = text; ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); toast('تم نسخ رابط المنشور ✓', 'success'); }
      catch (e) { toast('تعذّر النسخ تلقائياً', 'error'); }
      document.body.removeChild(ta);
    }

    function share(postId) {
      var info = opts.shareInfo(postId);
      var name = info.name, url = info.url;
      var shareText = 'منشور من ' + name + ' على تواصلنا:\n' + url;
      if (navigator.share) {
        navigator.share({ title: 'منشور: ' + name, text: shareText, url: url }).catch(function () {});
      } else if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(shareText)
          .then(function () { toast('تم نسخ رابط المنشور ✓', 'success'); })
          .catch(function () { shareFallback(shareText); });
      } else {
        shareFallback(shareText);
      }
    }

    // ── Click delegation on the list (card buttons only — comment items stay with §22c) ──
    function onClick(e) {
      // Read more — show full text inline, no overlay
      var moreBtn = e.target.closest('.post-more-inline');
      if (moreBtn) {
        var wrap = moreBtn.closest('.post-body-wrap');
        if (!wrap) return;
        var textSpan = wrap.querySelector('.post-body-text');
        var lessBtn  = wrap.querySelector('.post-less-btn');
        if (textSpan && wrap._pbFull) textSpan.textContent = wrap._pbFull;
        moreBtn.style.display = 'none';
        if (lessBtn) lessBtn.style.display = 'block';
        return;
      }
      // Read less — restore truncated text
      var lessBtn2 = e.target.closest('.post-less-btn');
      if (lessBtn2) {
        var wrap2 = lessBtn2.closest('.post-body-wrap');
        if (!wrap2) return;
        var textSpan2  = wrap2.querySelector('.post-body-text');
        var moreInline = wrap2.querySelector('.post-more-inline');
        if (textSpan2 && wrap2._pbShort) textSpan2.textContent = wrap2._pbShort;
        lessBtn2.style.display = 'none';
        if (moreInline) moreInline.style.display = 'inline-flex';
        return;
      }
      // 3-dot toggle
      var dotsBtn = e.target.closest('.pc-dots-btn[data-post-id]');
      if (dotsBtn) {
        e.stopPropagation();
        var menu = document.getElementById('pc-dm-' + dotsBtn.getAttribute('data-post-id'));
        if (menu) menu.classList.toggle('open');
        return;
      }
      // 3-dot edit
      var editDots = e.target.closest('.pc-dots-edit[data-post-id]');
      if (editDots) {
        var epid = parseInt(editDots.getAttribute('data-post-id'), 10);
        var edm  = document.getElementById('pc-dm-' + epid);
        if (edm) edm.classList.remove('open');
        if (opts.onEdit) opts.onEdit(epid);
        return;
      }
      // 3-dot delete
      var delDots = e.target.closest('.pc-dots-delete[data-post-id]');
      if (delDots) {
        var dpid = parseInt(delDots.getAttribute('data-post-id'), 10);
        var dm   = document.getElementById('pc-dm-' + dpid);
        if (dm) dm.classList.remove('open');
        if (opts.onDelete) opts.onDelete(dpid);
        return;
      }
      // Share
      var shareBtn = e.target.closest('.pc-btn--share[data-post-id]');
      if (shareBtn) { share(shareBtn.getAttribute('data-post-id')); return; }
      // Appreciate
      var apprBtn = e.target.closest('.pc-btn--appr[data-post-id]');
      if (apprBtn) { toggleAppr(apprBtn.getAttribute('data-post-id')); return; }
      // Comment panel toggle
      var cmtBtn = e.target.closest('.pc-btn--cmt[data-post-id]');
      if (cmtBtn) { toggleComments(cmtBtn.getAttribute('data-post-id')); return; }
      // Save
      var saveBtn = e.target.closest('.pc-btn--save[data-post-id]');
      if (saveBtn) { toggleSave(saveBtn.getAttribute('data-post-id')); return; }
    }

    function bind(root) {
      if (root) root.addEventListener('click', onClick);
      // Close ⋯ menus when clicking outside (once per page)
      if (!_dotsCloseBound) {
        _dotsCloseBound = true;
        document.addEventListener('click', function (e) {
          if (!e.target.closest('.pc-dots')) {
            document.querySelectorAll('.pc-dots-menu.open').forEach(function (m) {
              m.classList.remove('open');
            });
          }
        });
      }
    }

    return { bind: bind, trackViews: trackViews, toggleComments: toggleComments };
  }

  window.TwPostCard = {
    html: html,
    apprButtonInner: apprButtonInner,
    saveButtonInner: saveButtonInner,
    initClamps: initClamps,
    relativeTime: relativeTime,
    formatViews: formatViews,
    create: create
  };
}());
