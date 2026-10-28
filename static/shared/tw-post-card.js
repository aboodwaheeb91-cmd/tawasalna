// static/shared/tw-post-card.js — Post Card component (DS-CARD · task U.2 · CARDS.md CARD-03 / CARD-12)
//
// The one post card renderer + its button behaviour. U.2 moved the company page card
// (company.render.js → _postCardHtml) here as-is: same DOM, same classes, same data-*, same
// escaping, same text. U.2b moved the behaviour (appreciate / save desired-state queue, view
// tracking, comments panel open / close, ⋯ menu, share) from company.posts.js as-is — bound by
// event delegation on the classes / data-* below. Styles: static/shared/tw-card.css.
// U.3: every part from its system — text twT (post.card.* / action.share) · icons DS-ICON (twIcon)
// · avatar DS-IMAGE (twAvatarHtml) · time twRelativeTime / twFormatDate · buttons from the Actions
// Registry (post_appreciate · post_comment · share · post_save · post_edit · post_delete —
// twActionState decides who sees each; guest on an auth action → twLoginHref).
//
// Usage:
//   TwPostCard.html(post, { authorName, avatarUrl, authorType, authorHref, canEdit, authorId, viewerId, authorTwId })
//     → HTML string (one .post-card)
//     post       — a /company/posts item: id · body · tags[] · theme_color · created_at ·
//                  views_count · appreciations_count · viewer_appreciated · comments_enabled ·
//                  comments_count · viewer_saved
//     authorName — name in the head (escaped here) · first char = avatar fallback
//     avatarUrl  — raw URL; twAvatarHtml checks it (unsafe / missing → initial letter)
//     authorType — emp / co / edu → avatar shape (DS-IMAGE)
//     authorHref — optional (task 8.6b-2): the author's page (/u/{tw_id}) → name + avatar are links
//                  (a card outside its author's page — CARD-R08) · missing → plain text, as before
//     canEdit    — true → owner mode for the registry (⋯ edit / delete) · false → none
//     authorId   — task 8.6c: the author's numeric id from the API (author_id / the company id) ·
//     viewerId   — the session's numeric id (TwAuthSync snapshot) or null for a guest. Ownership =
//                  these two server numbers: canEdit → edit / delete · viewerId === authorId (no
//                  canEdit) → nothing · anyone else → ⋯ report + block (registry: guest = report →
//                  login). No authorId → no report / block. Nothing left → no ⋯ at all.
//     authorTwId — optional: the author's tw_id → the report's target_url (twAccountHref)
//   TwPostCard.apprButtonInner(active, count) → inner HTML of .pc-btn--appr (icon + label)
//   TwPostCard.saveButtonInner(active)        → inner HTML of .pc-btn--save (icon + label)
//   TwPostCard.commentButtonInner(count)      → inner HTML of .pc-btn--cmt (icon + label) — the card
//                                               and TwPostComments (count after send / delete) — task 8.6c
//   TwPostCard.initClamps(container)          → 3-line clamp + «المزيد» for every .post-body-wrap
//   TwPostCard.relativeTime(iso) · TwPostCard.formatViews(n) — the card's meta formatters
//   TwPostCard.create(opts) → { bind(root), trackViews(container), toggleComments(id) }
//     page-specific parts (API paths, session check, share info, edit / delete, comments)
//     come in opts — see create() below
//
// All user / API text (and twT text) goes through twEscHtml / twEscAttr (tw_shared.js) — resolved at call time.
(function () {
  'use strict';

  // Icons = DS-ICON (twIcon) · text = twT (post.card.*) · avatar = DS-IMAGE (twAvatarHtml) ·
  // button visibility = Actions Registry (twActionState — tw_actions.json) — task U.3.
  function ico(name, size, filled) {
    return typeof window.twIcon === 'function' ? window.twIcon(name, { size: size, filled: !!filled }) : '';
  }
  function t(key, vars) { return window.twEscHtml(window.twT(key, vars)); }
  function lbl(key, vars) { return '<span class="tw-act-lbl">' + t(key, vars) + '</span>'; }

  function _truthy(v) { return v === true || v === 'true' || v === 1; }

  // Shared relative time (tw_shared.js twRelativeTime — CARD-R05); kept on TwPostCard for callers.
  function relativeTime(iso) { return window.twRelativeTime(iso); }

  function formatViews(n) {
    n = Number(n) || 0;
    if (n >= 1000) { var k = n / 1000; return window.twT('post.card.views', { count: (k % 1 === 0 ? k : k.toFixed(1)) + 'K' }); }
    return window.twT('post.card.views', { count: n });
  }

  function apprButtonInner(active, count) {
    return ico('heart', 'sm', active) + (count > 0 ? lbl('post.card.appreciate_n', { count: count }) : lbl('post.card.appreciate'));
  }

  function commentButtonInner(count) {
    count = Number(count) || 0;
    return ico('comment', 'sm') + (count > 0 ? lbl('post.card.comment_n', { count: count }) : lbl('post.card.comment'));
  }

  function saveButtonInner(active) {
    return ico(active ? 'bookmark-check' : 'bookmark', 'sm', active) + lbl(active ? 'post.card.saved' : 'post.card.save');
  }

  // One card button from the registry: hidden → '' · else <button type=button data-tw-action>.
  // The card is an HTML string (company list = innerHTML), so clicks go through bind()'s
  // delegation — the registry decides who sees it (twActionState), the same as twAction.
  function actBtn(id, ctx, cls, attrs, inner) {
    if (window.twActionState(id, ctx) === 'hidden') return '';
    return '<button type="button" class="' + cls + '" data-tw-action="' + id + '"' + attrs + '>' + inner + '</button>';
  }

  function html(post, opts) {
    opts = opts || {};
    var esc = window.twEscHtml, escAttr = window.twEscAttr;
    var name = opts.authorName;

    // Resolve theme color — null/unknown → teal
    var colorKey = (post.theme_color && window.TW && TW.POST_THEME_COLORS && TW.POST_THEME_COLORS[post.theme_color])
      ? post.theme_color : 'teal';
    var clr = (window.TW && TW.POST_THEME_COLORS && TW.POST_THEME_COLORS[colorKey])
      || { accent: 'var(--color-categorical-teal)', soft: 'rgba(var(--color-categorical-teal-rgb),.12)', glow: 'rgba(var(--color-categorical-teal-rgb),.18)' };
    var cardStyle = '--pa:' + clr.accent + '; --pa-s:' + clr.soft + '; --pa-g:' + clr.glow;

    // Avatar / logo: DS-IMAGE (URL check + fallback letter + shape by account type)
    var avaHtml = window.twAvatarHtml({ full_name: name, avatar_url: opts.avatarUrl, user_type: opts.authorType }, 'lg');
    // Author link (CARD-R08) — the name is the link; the avatar repeats it outside the tab order
    var href = opts.authorHref ? escAttr(opts.authorHref) : '';
    var avaBox = href
      ? '<a class="post-ava" href="' + href + '" tabindex="-1" aria-hidden="true">' + avaHtml + '</a>'
      : '<div class="post-ava">' + avaHtml + '</div>';
    var nameBox = href
      ? '<a class="post-nm" href="' + href + '">' + esc(name) + '</a>'
      : '<div class="post-nm">' + esc(name) + '</div>';

    // Tags — themed class so they inherit --pa from the card
    var tagsHtml = '';
    if (post.tags && post.tags.length) {
      tagsHtml = '<div class="job-tags">' + post.tags.map(function (tag) {
        return '<span class="jtag jtag-themed">' + esc(tag) + '</span>';
      }).join('') + '</div>';
    }

    // Registry context: canEdit (server permission) = the owner signal (VM mode) · comments flag
    var ctx = { mode: opts.canEdit ? 'owner' : undefined, commentsEnabled: post.comments_enabled !== false };

    // ⋯ menu — shown only when the registry gives at least one item
    var pid = escAttr(String(post.id));
    var dataPid = ' data-post-id="' + pid + '"';
    var menuItems = actBtn('post_edit', ctx, 'pc-dots-edit', dataPid, ico('edit', 'sm') + lbl('post.card.edit'))
      + actBtn('post_delete', ctx, 'pc-dots-delete', dataPid, ico('delete', 'sm') + lbl('post.card.delete'));
    // task 8.6c — report / block the author (not the owner): mode from the server numbers, not from text
    var authorId = parseInt(opts.authorId, 10);
    if (authorId > 0) {
      var viewerId = opts.viewerId == null || opts.viewerId === '' ? null : Number(opts.viewerId);
      var rctx = { mode: (opts.canEdit || viewerId === authorId) ? 'owner' : (viewerId == null ? 'guest' : 'registered') };
      var dataAuthor = dataPid + ' data-author-id="' + authorId + '"'
        + (opts.authorTwId ? ' data-author-tw="' + escAttr(String(opts.authorTwId)) + '"' : '');
      menuItems += actBtn('report', rctx, 'pc-dots-report', dataAuthor, ico('report', 'sm') + lbl('action.report'))
        + actBtn('block', rctx, 'pc-dots-block', dataAuthor, ico('user-minus', 'sm') + lbl('action.block'));
    }
    var dotsHtml = menuItems
      ? '<div class="pc-dots">'
          + '<button type="button" class="pc-dots-btn"' + dataPid + ' aria-label="' + t('post.card.options') + '">' + ico('more', 'lg') + '</button>'
          + '<div class="pc-dots-menu" id="pc-dm-' + pid + '">' + menuItems + '</div>'
        + '</div>'
      : '';

    var appCount   = Number(post.appreciations_count) || 0;
    var appActive  = _truthy(post.viewer_appreciated);
    var cmtCount   = Number(post.comments_count) || 0;
    var saveActive = _truthy(post.viewer_saved);
    var cmtBtn = actBtn('post_comment', ctx, 'pc-btn pc-btn--cmt', dataPid + ' data-cmt-count="' + cmtCount + '"',
      commentButtonInner(cmtCount));

    return '<div class="post-card" data-post-id="' + pid + '" style="' + cardStyle + '">'
      + '<div class="post-head">'
        + avaBox
        + '<div class="post-head-info">'
          + nameBox
          + '<div class="post-meta-row">'
            + '<span class="post-date">' + ico('clock', 'xs') + esc(relativeTime(post.created_at)) + '</span>'
            + '<span class="post-views" data-views-count="' + (Number(post.views_count) || 0) + '">' + ico('eye', 'xs') + esc(formatViews(post.views_count)) + '</span>'
          + '</div>'
        + '</div>'
        + dotsHtml
      + '</div>'
      + '<div class="post-body-wrap">'
        + '<div class="post-body">'
          + '<span class="post-body-text">' + esc(post.body) + '</span>'
          + '<button type="button" class="post-more-inline" aria-label="' + t('post.card.more') + '">'
            + '<span class="post-more-ellipsis">…</span>'
            + ico('show-more', 'lg')
          + '</button>'
        + '</div>'
        + '<button type="button" class="post-less-btn" aria-label="' + t('post.card.less') + '">'
          + ico('show-less', 'lg')
        + '</button>'
      + '</div>'
      + tagsHtml
      + '<div class="pc-actions">'
        + actBtn('post_appreciate', ctx, 'pc-btn pc-btn--appr' + (appActive ? ' appr-active' : ''),
            dataPid + ' data-appr-count="' + appCount + '"', apprButtonInner(appActive, appCount))
        + cmtBtn
        + actBtn('share', ctx, 'pc-btn pc-btn--share', dataPid, ico('share', 'sm') + lbl('action.share'))
        + actBtn('post_save', ctx, 'pc-btn pc-btn--save' + (saveActive ? ' save-active' : ''),
            dataPid + ' data-saved="' + (saveActive ? '1' : '0') + '"', saveButtonInner(saveActive))
      + '</div>'
      + (cmtBtn ? '<div class="pc-cmts-panel" id="pc-cmt-panel-' + pid + '" data-post-id="' + pid + '" style="display:none"></div>' : '')
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
    // Guest on a registry action with auth:true (appreciate / save) → login, back here (BTN-19 rule 3)
    function toLogin() { location.href = twLoginHref(location.pathname + location.search); }
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
            toast(twT('post.card.slow_down'), 'error');
            return;
          }

          if (!res.ok || !res.data || res.data.status !== 'success') {
            if (btn && orig) renderSave(btn, orig.active);
            delete _saveDesired[postId];
            delete _saveOrigState[postId];
            toast(twApiMessage(res, twT('post.card.save_failed')), 'error');
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
      if (!signedIn()) { toLogin(); return; }
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
            toast(twT(res.status === 403 ? 'post.card.own_appreciate' : 'post.card.slow_down'), 'error');
            return;
          }

          if (!res.ok || !res.data || res.data.status !== 'success') {
            if (btn && orig) renderAppr(btn, orig.active, orig.count);
            delete _apprDesired[postId];
            delete _apprOrigState[postId];
            toast(twApiMessage(res, twT('post.card.appreciate_failed')), 'error');
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
      if (!signedIn()) { toLogin(); return; }

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
      try { document.execCommand('copy'); toast(twT('post.card.link_copied'), 'success'); }
      catch (e) { toast(twT('post.card.copy_failed'), 'error'); }
      document.body.removeChild(ta);
    }

    function share(postId) {
      var info = opts.shareInfo(postId);
      var name = info.name, url = info.url;
      var shareText = twT('post.card.share_text', { name: name, url: url });
      if (navigator.share) {
        navigator.share({ title: twT('post.card.share_title', { name: name }), text: shareText, url: url }).catch(function () {});
      } else if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(shareText)
          .then(function () { toast(twT('post.card.link_copied'), 'success'); })
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
      // 3-dot report / block (task 8.6c) — through twAction itself: the same login (guest) /
      // registry confirm (block) path as every other report / block button
      var repDots = e.target.closest('.pc-dots-report[data-author-id]') || e.target.closest('.pc-dots-block[data-author-id]');
      if (repDots) {
        var rdm = document.getElementById('pc-dm-' + repDots.getAttribute('data-post-id'));
        if (rdm) rdm.classList.remove('open');
        var aid = parseInt(repDots.getAttribute('data-author-id'), 10);
        var atw = repDots.getAttribute('data-author-tw');
        var isReport = repDots.classList.contains('pc-dots-report');
        var act = window.twAction(isReport ? 'report' : 'block', { ownerId: aid, onClick: isReport
          ? function () {
              window.twReportDialog({ reportedId: aid, reportedType: 'company',
                targetUrl: atw ? window.twAccountHref({ tw_id: atw }) : undefined });
            }
          : function () { window.twBlockUser(aid); } });
        if (act) act.click();
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
    commentButtonInner: commentButtonInner,
    initClamps: initClamps,
    relativeTime: relativeTime,
    formatViews: formatViews,
    create: create
  };
}());
