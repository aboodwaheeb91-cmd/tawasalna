// tw-post-comments.js — post comments system (§22c · docs/rules/post-comments.md): comments ·
// replies · @mentions · edit · delete · ⋮ menu · load more · collapse. Moved from
// company.posts.js as-is (task 8.6b-1) — same DOM, classes, data-*, text, API paths, escaping.
// Needs tw_shared.js (twApi · twApiMessage · twT · twSafeImageUrl) — loaded after it.
//
// TwPostComments.create(opts) → { build(postId), load(postId, cursor) } — passed to
// TwPostCard.create({ comments }). Everything page-specific comes in opts:
//   opts.signedIn()         → bool (the page's session check)
//   opts.postOwner(postId)  → { full_name, tw_id, avatar_url } | null (mention suggestions)
// Shared state (portal ⋮ menu · mention menu · reply / mention / in-flight state) lives here
// once per page; the document / body listeners are bound once whatever the number of
// controllers. Each panel remembers its controller (panel._twCmtOpts) and gets one click
// listener for its comment items when it is built.
(function () {
  'use strict';

  var _NO_OPTS = { signedIn: function () { return false; }, postOwner: function () { return null; } };
  function _cmtOpts(postId) {
    var panel = document.getElementById('pc-cmt-panel-' + postId);
    return (panel && panel._twCmtOpts) || _NO_OPTS;
  }
  function _cmtSignedIn(postId) {
    var o = _cmtOpts(postId);
    return !!(o.signedIn && o.signedIn());
  }
  function _cmtPostOwner(postId) {
    var o = _cmtOpts(postId);
    return (o.postOwner && o.postOwner(postId)) || null;
  }

  var _ICO_COMMENT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  var _ICO_CLOCK   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
  // Comment collapse icons — static SVG only (no API data)
  var _ICO_CMT_EXPAND   = '<span class="pc-cmt-ellipsis" aria-hidden="true">…</span><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 8v8"/><path d="m8 12 4 4 4-4"/></svg>';
  var _ICO_CMT_COLLAPSE = '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="m16 12-4-4-4 4"/><path d="M12 16V8"/></svg>';

  var _cmtEditInFlight = {};   // commentId -> bool — prevents concurrent PATCH requests
  var _cmtOpenMenuId   = null; // commentId whose ⋮ menu is currently open
  var _cmtPortalMenu   = null; // single portal <div> on document.body (lazy-created)
  var _cmtPortalFor    = null; // {cmtId, postId} currently shown in portal
  var _cmtReplyTarget  = {};   // postId -> authorName | null (active reply state)
  var _cmtReplyTargetId = {};  // postId -> commentId | null (reply_to_comment_id to send)

  // ── @ Mention Autocomplete state ──────────────────────────────────────────
  var _cmtMentionMenu  = null; // single portal <div> on document.body (lazy-created)
  var _cmtMentionState = {
    open:      false,
    ta:        null,   // active textarea
    postId:    null,   // post panel being typed in
    start:     -1,     // index of the @ character in ta.value
    filtered:  [],     // current filtered candidate names
    activeIdx: -1,     // keyboard-highlighted row index (-1 = none)
  };
  // postId -> [{name, tw_id}] of @mentions selected from autocomplete (cleared on send).
  // Each entry is only sent if '@' + name appears anywhere in the body at send time.
  var _cmtMentionedCandidates = {};
  var _cmtMentionDebounce     = null; // timer handle for API search debounce

  function _cmtGetBtn(postId) {
    var card = document.querySelector('.post-card[data-post-id="' + postId + '"]');
    return card ? card.querySelector('.pc-btn--cmt') : null;
  }

  function _cmtGetPanel(postId) {
    return document.getElementById('pc-cmt-panel-' + postId);
  }

  function _autoResizeTextarea(ta) {
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  }

  function _formatRelativeTime(ts) {
    if (!ts) return '';
    var now  = Date.now();
    var then = new Date(ts).getTime();
    if (isNaN(then)) return '';
    var diff = Math.max(0, now - then);
    var sec  = Math.floor(diff / 1000);
    var min  = Math.floor(sec / 60);
    var hr   = Math.floor(min / 60);
    var day  = Math.floor(hr / 24);
    if (sec < 60)  return 'منذ لحظة';
    if (min === 1) return 'منذ دقيقة';
    if (min < 11)  return 'منذ ' + min + ' دقائق';
    if (min < 60)  return 'منذ ' + min + ' دقيقة';
    if (hr  === 1) return 'منذ ساعة';
    if (hr  < 11)  return 'منذ ' + hr  + ' ساعات';
    if (hr  < 24)  return 'منذ ' + hr  + ' ساعة';
    if (day === 1) return 'منذ يوم';
    if (day < 11)  return 'منذ ' + day + ' أيام';
    return 'منذ ' + day + ' يوم';
  }

  // ── Portal ⋮ menu (single div on body, position:fixed — avoids overflow-y clip) ─
  function _cmtGetPortalMenu() {
    if (!_cmtPortalMenu) {
      _cmtPortalMenu = document.createElement('div');
      _cmtPortalMenu.className = 'pc-cmt-portal-menu';
      _cmtPortalMenu.id = 'pc-cmt-portal-menu';
      document.body.appendChild(_cmtPortalMenu);
    }
    return _cmtPortalMenu;
  }

  function _cmtHidePortalMenu() {
    if (_cmtPortalMenu) _cmtPortalMenu.style.display = 'none';
    _cmtPortalFor  = null;
    _cmtOpenMenuId = null;
  }

  function _cmtShowPortalMenu(btn, cmtId, postId, canEdit, canDelete) {
    var menu = _cmtGetPortalMenu();
    menu.innerHTML = '';
    if (canEdit) {
      var editItem = document.createElement('button');
      editItem.type = 'button';
      editItem.className = 'pc-cmt-menu-item pc-cmt-menu-edit';
      editItem.dataset.cmtId  = cmtId;
      editItem.dataset.postId = postId || '';
      editItem.textContent    = 'تعديل';
      menu.appendChild(editItem);
    }
    if (canDelete) {
      var delItem = document.createElement('button');
      delItem.type = 'button';
      delItem.className = 'pc-cmt-menu-item pc-cmt-menu-del';
      delItem.dataset.cmtId  = cmtId;
      delItem.dataset.postId = postId || '';
      delItem.textContent    = 'حذف';
      menu.appendChild(delItem);
    }
    var rect  = btn.getBoundingClientRect();
    var itemH = 36;
    var menuH = (canEdit ? itemH : 0) + (canDelete ? itemH : 0) + 8;
    var menuW = 108;
    var top   = rect.bottom + 4;
    var left  = rect.left - menuW + rect.width;
    // Use visualViewport.height so the menu stays above the mobile keyboard on iOS Safari
    var _vph  = (window.visualViewport && window.visualViewport.height) || window.innerHeight;
    if (top  + menuH > _vph - 8) top  = rect.top - menuH - 4;
    if (left + menuW > window.innerWidth  - 8) left = window.innerWidth - menuW - 8;
    if (left < 8) left = 8;
    if (top  < 8) top  = 8;
    menu.style.top     = top  + 'px';
    menu.style.left    = left + 'px';
    menu.style.display = 'block';
    _cmtPortalFor  = { cmtId: cmtId, postId: postId };
    _cmtOpenMenuId = cmtId;
  }

  // ── @ Mention Autocomplete ────────────────────────────────────────────────

  function _cmtGetMentionMenu() {
    if (!_cmtMentionMenu) {
      _cmtMentionMenu = document.createElement('div');
      _cmtMentionMenu.className = 'pc-cmt-mention-menu';
      _cmtMentionMenu.id = 'pc-cmt-mention-menu';
      document.body.appendChild(_cmtMentionMenu);
    }
    return _cmtMentionMenu;
  }

  function _cmtCloseMentionMenu() {
    if (_cmtMentionDebounce) { clearTimeout(_cmtMentionDebounce); _cmtMentionDebounce = null; }
    if (_cmtMentionMenu) _cmtMentionMenu.style.display = 'none';
    _cmtMentionState.open      = false;
    _cmtMentionState.ta        = null;
    _cmtMentionState.postId    = null;
    _cmtMentionState.start     = -1;
    _cmtMentionState.filtered  = [];
    _cmtMentionState.activeIdx = -1;
  }

  // Collect candidates {name, tw_id, avatar} from comment authors (DOM) + the post owner (opts.postOwner).
  // XSS-safe: reads textContent / data attributes from DOM elements, never innerHTML.
  function _cmtCollectMentionCandidates(postId) {
    var seen = {};
    var out  = [];
    var panel = _cmtGetPanel(postId);
    if (panel) {
      // Each .pc-cmt-item[data-author-tw-id] has the author's tw_id, avatar, and name
      var items = panel.querySelectorAll('.pc-cmt-item[data-author-tw-id]');
      for (var i = 0; i < items.length; i++) {
        var twId   = items[i].dataset.authorTwId;
        var nameEl = items[i].querySelector('.pc-cmt-author');
        var name   = nameEl ? nameEl.textContent.trim() : '';
        var avatar = items[i].dataset.authorAvatar || null;
        if (name && twId && !seen[twId]) {
          seen[twId] = true;
          out.push({ name: name, tw_id: twId, avatar: avatar || null });
        }
      }
    }
    // Add post owner — opts.postOwner(postId) → { full_name, tw_id, avatar_url } | null
    var cp = _cmtPostOwner(postId);
    if (cp && cp.full_name) {
      var cTwId = cp.tw_id || '';
      if (cTwId && !seen[cTwId]) {
        seen[cTwId] = true;
        out.push({ name: cp.full_name, tw_id: cTwId, avatar: cp.avatar_url || null });
      }
    }
    return out;
  }

  // Returns up to 6 candidates whose .name or .tw_id contains the query (case-insensitive).
  function _cmtFilterMentionCandidates(query, candidates) {
    if (!query) return candidates.slice(0, 6);
    var q = query.toLowerCase();
    var result = [];
    for (var i = 0; i < candidates.length && result.length < 6; i++) {
      var c = candidates[i];
      var nameMatch  = String(c.name  || '').toLowerCase().indexOf(q) !== -1;
      var twIdMatch  = String(c.tw_id || '').toLowerCase().indexOf(q) !== -1;
      if (nameMatch || twIdMatch) result.push(c);
    }
    return result;
  }

  function _cmtSetMentionActive(idx) {
    var menu  = _cmtGetMentionMenu();
    var items = menu.querySelectorAll('.pc-cmt-mention-item');
    for (var i = 0; i < items.length; i++) {
      if (i === idx) items[i].classList.add('pc-cmt-mention-active');
      else           items[i].classList.remove('pc-cmt-mention-active');
    }
    _cmtMentionState.activeIdx = idx;
  }

  function _cmtPositionMentionMenu(ta) {
    var menu = _cmtGetMentionMenu();
    // Anchor on the input-row container for a stable bounding box on mobile.
    // This keeps the menu anchored to the full input area, not just the textarea element.
    var anchor = (ta.closest && ta.closest('.pc-cmts-input-row')) || ta;
    var rect   = anchor.getBoundingClientRect();
    var vp     = window.visualViewport;
    var _vph   = (vp && vp.height)    || window.innerHeight;
    var _vpOff = (vp && vp.offsetTop) || 0;
    // Convert rect to visual-viewport coordinate space (bridges iOS Safari layout/visual gap)
    var rectTopVis    = rect.top    - _vpOff;
    var rectBottomVis = rect.bottom - _vpOff;
    // Calculate available space above and below the anchor
    var spaceAbove = Math.max(0, rectTopVis - 8);
    var spaceBelow = Math.max(0, _vph - rectBottomVis - 8);
    // Cap menu height to whichever side has more room (min 60 so menu is always usable)
    var menuMaxH = Math.min(160, Math.max(spaceAbove, spaceBelow, 60));
    menu.style.maxHeight = menuMaxH + 'px';
    // Measure actual rendered height after maxHeight is applied
    var menuH = menu.offsetHeight || menuMaxH;
    var menuW = 220;
    var top;
    if (spaceAbove >= 90) {
      // Enough room above — preferred on mobile, keeps menu above the keyboard
      top = rectTopVis - menuH - 6;
    } else if (spaceBelow >= 90) {
      // Not enough above but enough below — place below the anchor
      top = rectBottomVis + 4;
    } else {
      // Both sides limited — pick whichever has more space, stay close to anchor
      top = spaceAbove >= spaceBelow
        ? rectTopVis - menuH - 6
        : rectBottomVis + 4;
    }
    // Final clamp: keep menu inside visual viewport
    if (top < 8) top = 8;
    if (top + menuH > _vph - 4) top = Math.max(8, _vph - menuH - 4);
    // Right-align with anchor right edge (RTL layout)
    var left = rect.right - menuW;
    if (left < 8) left = 8;
    if (left + menuW > window.innerWidth - 8) left = window.innerWidth - menuW - 8;
    menu.style.top  = top  + 'px';
    menu.style.left = left + 'px';
  }

  function _cmtOpenMentionMenu(ta, postId, filtered, start) {
    if (!filtered.length) { _cmtCloseMentionMenu(); return; }
    var menu = _cmtGetMentionMenu();
    menu.replaceChildren(); // clear items — no innerHTML (contract: ممنوع innerHTML في mention system)
    for (var i = 0; i < filtered.length; i++) {
      var cand = filtered[i];
      var btn = document.createElement('button');
      btn.type      = 'button';
      btn.className = 'pc-cmt-mention-item';
      btn.dataset.mentionName = cand.name; // XSS-safe: used via textContent
      if (cand.tw_id) btn.dataset.mentionTwId = cand.tw_id;
      // Small avatar circle
      var avaEl = document.createElement('span');
      avaEl.className = 'pc-cmt-mention-ava';
      var candAva = twSafeImageUrl(cand.avatar);
      if (candAva) {
        var img = document.createElement('img');
        img.src = candAva;
        img.alt = '';
        img.className = 'pc-cmt-mention-ava-img';
        avaEl.appendChild(img);
      } else {
        avaEl.textContent = (cand.name || '؟').charAt(0); // XSS-safe: textContent
      }
      var nameSpan = document.createElement('span');
      nameSpan.className  = 'pc-cmt-mention-name';
      nameSpan.textContent = cand.name; // XSS-safe: textContent only
      btn.appendChild(avaEl);
      btn.appendChild(nameSpan);
      menu.appendChild(btn);
    }
    _cmtMentionState.open      = true;
    _cmtMentionState.ta        = ta;
    _cmtMentionState.postId    = postId;
    _cmtMentionState.start     = start;
    _cmtMentionState.filtered  = filtered;
    _cmtMentionState.activeIdx = -1;
    // Measure actual height before final position (visibility:hidden keeps it off-screen)
    menu.style.visibility = 'hidden';
    menu.style.display    = 'block';
    _cmtPositionMentionMenu(ta);
    menu.style.visibility = '';
  }

  // Insert @name + space at the @-mention position, reposition cursor.
  // twId: optional — pushed to _cmtMentionedCandidates[postId] array for validation at send time.
  function _cmtInsertMention(ta, name, twId) {
    var val    = ta.value;
    var start  = _cmtMentionState.start;
    var cursor = ta.selectionStart;
    var before = val.slice(0, start);
    var after  = val.slice(cursor);
    var insert = '@' + name + ' ';
    ta.value   = before + insert + after;
    var newPos = (before + insert).length;
    ta.setSelectionRange(newPos, newPos);
    ta.dispatchEvent(new Event('input')); // trigger auto-resize
    ta.focus();
    // Push candidate into array — deduplicated by tw_id
    var postId = String(_cmtMentionState.postId || '');
    if (postId && twId && name) {
      if (!_cmtMentionedCandidates[postId]) _cmtMentionedCandidates[postId] = [];
      var alreadyAdded = false;
      for (var _mci = 0; _mci < _cmtMentionedCandidates[postId].length; _mci++) {
        if (_cmtMentionedCandidates[postId][_mci].tw_id === twId) { alreadyAdded = true; break; }
      }
      if (!alreadyAdded) _cmtMentionedCandidates[postId].push({ name: name, tw_id: twId });
    }
    _cmtCloseMentionMenu();
  }

  // Merge DOM candidates (first) with API candidates, deduplicating by tw_id.
  function _cmtMergeCandidates(domCands, apiCands) {
    var seen = {};
    var out  = [];
    for (var i = 0; i < domCands.length; i++) {
      if (domCands[i].tw_id && !seen[domCands[i].tw_id]) {
        seen[domCands[i].tw_id] = true;
        out.push(domCands[i]);
      }
    }
    for (var j = 0; j < apiCands.length; j++) {
      if (apiCands[j].tw_id && !seen[apiCands[j].tw_id]) {
        seen[apiCands[j].tw_id] = true;
        out.push(apiCands[j]);
      }
    }
    return out;
  }

  // Extracts the active @-mention query from text at cursor position.
  // Returns { active: bool, start: int, query: string }.
  //
  // Root-cause fix for mobile Arabic keyboard bug:
  //   1. selectionStart can be 0 or stale on mobile → fall back to text.length.
  //   2. iOS/Android inject invisible Unicode directional marks (‎ ‏ ؜)
  //      between @ and the first Arabic character; these make indexOf() return -1 for
  //      every real name, causing the menu to close after the 2nd character is typed.
  function _cmtExtractMentionQuery(text, cursor) {
    var c = (cursor > 0) ? cursor : text.length;
    var atIdx = -1;
    for (var i = c - 1; i >= 0; i--) {
      if (text[i] === '@') { atIdx = i; break; }
      // space (32) or newline (10) — no active @ token before cursor
      if (text.charCodeAt(i) === 32 || text.charCodeAt(i) === 10) break;
    }
    if (atIdx === -1) return { active: false, start: -1, query: '' };
    var raw   = text.slice(atIdx + 1, c);
    // Strip invisible directional/formatting marks that mobile RTL keyboards inject:
    // ‎ LRM · ‏ RLM · ؜ ALM
    // eslint-disable-next-line no-misleading-character-class
    var clean = raw.replace(/[‎‏؜]/g, '');
    // If the cleaned string contains a space/newline, @ is not the active trigger
    if (clean.indexOf(' ') !== -1 || clean.indexOf('\n') !== -1) {
      return { active: false, start: -1, query: '' };
    }
    return { active: true, start: atIdx, query: clean };
  }

  // Called on every textarea input event (and compositionend for Arabic IME keyboards).
  // Shows DOM candidates immediately (zero latency), then merges API results after 100 ms.
  function _cmtHandleMentionInput(ta, postId) {
    var ex = _cmtExtractMentionQuery(ta.value, ta.selectionStart);
    if (!ex.active) { _cmtCloseMentionMenu(); return; }
    var start  = ex.start;
    var query  = ex.query;
    var domCands   = _cmtCollectMentionCandidates(postId);
    var filtered   = _cmtFilterMentionCandidates(query, domCands);
    _cmtOpenMentionMenu(ta, postId, filtered, start);

    // Debounced API search to surface followers/following beyond visible DOM
    if (_cmtMentionDebounce) clearTimeout(_cmtMentionDebounce);
    var capturedStart = start;
    var capturedQuery = query;
    _cmtMentionDebounce = setTimeout(function () {
      _cmtMentionDebounce = null;
      // Stale-response guard: abort if panel closed or user typed past this @ token
      if (!_cmtMentionState.open) return;
      var currEx = _cmtExtractMentionQuery(ta.value, ta.selectionStart);
      if (!currEx.active || currEx.start !== capturedStart || currEx.query !== capturedQuery) return;
      var signedIn = _cmtSignedIn(postId);   // the page's session check (opts.signedIn)
      if (!signedIn) return;
      // Show loading indicator below existing DOM candidates while fetch is in flight
      var _menu = _cmtGetMentionMenu();
      if (_menu.style.display === 'block' && !document.getElementById('pc-cmt-mention-loading')) {
        var _ld = document.createElement('div');
        _ld.id = 'pc-cmt-mention-loading';
        _ld.className = 'pc-cmt-mention-loading';
        var _ldSpan = document.createElement('span');
        _ldSpan.textContent = 'جاري البحث…';
        _ld.appendChild(_ldSpan);
        _menu.appendChild(_ld);
      }
      var url = '/mention/search?q=' + encodeURIComponent(capturedQuery) + '&limit=8';
      twApi(url)
        .then(function (r) {
          var res = r.data || {};
          // Second stale-response guard: re-verify after async gap
          if (!_cmtMentionState.open) return;
          var postEx = _cmtExtractMentionQuery(ta.value, ta.selectionStart);
          if (!postEx.active || postEx.start !== capturedStart || postEx.query !== capturedQuery) return;
          if (!r.ok || !Array.isArray(res.candidates)) {
            var _ldEl = document.getElementById('pc-cmt-mention-loading');
            if (_ldEl) _ldEl.remove();
            return;
          }
          var freshDom    = _cmtCollectMentionCandidates(postId);
          var merged      = _cmtMergeCandidates(freshDom, res.candidates);
          var newFiltered = _cmtFilterMentionCandidates(capturedQuery, merged);
          // _cmtOpenMentionMenu calls menu.replaceChildren() — removes loading item automatically
          _cmtOpenMentionMenu(ta, postId, newFiltered, capturedStart);
        });
    }, 100);
  }

  // Handles Arrow / Enter / Escape inside the textarea.
  function _cmtHandleMentionKeydown(e, ta) {
    if (!_cmtMentionState.open) return;
    var len = _cmtMentionState.filtered.length;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      _cmtSetMentionActive((_cmtMentionState.activeIdx + 1) % len);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      _cmtSetMentionActive((_cmtMentionState.activeIdx - 1 + len) % len);
    } else if (e.key === 'Enter') {
      var idx = _cmtMentionState.activeIdx;
      if (idx >= 0 && idx < len) {
        e.preventDefault();
        var cand = _cmtMentionState.filtered[idx];
        _cmtInsertMention(ta, cand.name, cand.tw_id || null);
      }
    } else if (e.key === 'Escape') {
      _cmtCloseMentionMenu();
    }
  }

  // ── Reply system — prefills @mention + tracks reply_to_comment_id ─────────
  function _cmtHandleReply(postId, authorName, commentId) {
    var panel = _cmtGetPanel(postId);
    if (!panel) return;
    var ta = panel.querySelector('.pc-cmts-ta:not(.pc-cmt-edit-ta)');
    if (!ta) return;
    var strip    = panel.querySelector('.pc-cmt-reply-strip');
    var nameSpan = strip ? strip.querySelector('.pc-cmt-reply-strip-name') : null;
    var mention  = '@' + authorName + ' ';
    var prev     = _cmtReplyTarget[postId];
    if (prev) {
      var prevMention = '@' + prev + ' ';
      if (ta.value.indexOf(prevMention) === 0) {
        ta.value = mention + ta.value.slice(prevMention.length);
      } else {
        ta.value = mention + ta.value;
      }
    } else {
      ta.value = mention + ta.value;
    }
    _cmtReplyTarget[postId]   = authorName;
    _cmtReplyTargetId[postId] = commentId || null;
    if (nameSpan) nameSpan.textContent = authorName; // XSS-safe
    if (strip)    strip.style.display  = 'flex';
    _autoResizeTextarea(ta);
    ta.focus();
    ta.setSelectionRange(mention.length, mention.length);
    // On mobile the keyboard opens after focus() but shrinks the viewport asynchronously.
    // A short delay lets the browser settle before scrolling the input into view.
    setTimeout(function () { ta.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }, 200);
  }

  function _cmtCancelReply(postId) {
    var panel = _cmtGetPanel(postId);
    if (!panel) return;
    var ta    = panel.querySelector('.pc-cmts-ta:not(.pc-cmt-edit-ta)');
    var strip = panel.querySelector('.pc-cmt-reply-strip');
    var prev  = _cmtReplyTarget[postId];
    if (ta && prev) {
      var prevMention = '@' + prev + ' ';
      if (ta.value.indexOf(prevMention) === 0) {
        ta.value = ta.value.slice(prevMention.length);
        _autoResizeTextarea(ta);
      }
    }
    _cmtReplyTarget[postId]   = null;
    _cmtReplyTargetId[postId] = null;
    if (strip) strip.style.display = 'none';
  }

  function _cmtUpdateCount(postId, delta) {
    var btn = _cmtGetBtn(postId);
    if (!btn) return;
    var current = parseInt(btn.dataset.cmtCount, 10) || 0;
    var next = Math.max(0, current + delta);
    btn.dataset.cmtCount = next;
    btn.innerHTML = '';
    var tmp = document.createElement('div');
    tmp.innerHTML = _ICO_COMMENT;
    btn.appendChild(tmp.firstChild);
    var txt = document.createTextNode(next > 0 ? ('تعليق · ' + next) : 'تعليق');
    btn.appendChild(txt);
  }

  // Returns candidate names sorted longest-first (for greedy compound-name matching).
  function _cmtKnownNames(postId) {
    var cands = _cmtCollectMentionCandidates(postId);
    return cands.map(function (c) { return c.name; }).sort(function (a, b) { return b.length - a.length; });
  }

  // XSS-safe body renderer — full-text scan for @mentions at any position.
  // mentionName : exact reply author name (spaces OK) → <a href="/u/tw_id"> if mentionTwId present.
  // mentionTwId : reply author tw_id from DB — makes the reply @mention a clickable link.
  // knownNames  : sorted-longest-first array of known participant names (no tw_id → <span>).
  // mentions    : [{name, tw_id}] DB-backed free @mentions (multiple) → <a> when tw_id present.
  // All text output via textContent/createTextNode — never innerHTML for API data.
  function _renderCommentBody(bodyEl, text, mentionName, mentionTwId, knownNames, mentions) {
    bodyEl.textContent = ''; // clears all children safely
    if (!text) return;

    // Build lookup: [{name, tw_id}] sorted longest-first for compound name matching.
    // Priority: reply author → DB-backed free mentions → knownNames (no tw_id)
    var lookup = [];
    if (mentionName) {
      lookup.push({ name: mentionName, tw_id: mentionTwId || null });
    }
    if (mentions && mentions.length) {
      for (var mi = 0; mi < mentions.length; mi++) {
        var mEntry = mentions[mi];
        if (mEntry && mEntry.name) {
          var dupM = false;
          for (var di = 0; di < lookup.length; di++) { if (lookup[di].name === mEntry.name) { dupM = true; break; } }
          if (!dupM) lookup.push({ name: mEntry.name, tw_id: mEntry.tw_id || null });
        }
      }
    }
    if (knownNames && knownNames.length) {
      for (var ki = 0; ki < knownNames.length; ki++) {
        var kn = knownNames[ki];
        var dupK = false;
        for (var dk = 0; dk < lookup.length; dk++) { if (lookup[dk].name === kn) { dupK = true; break; } }
        if (!dupK) lookup.push({ name: kn, tw_id: null });
      }
    }
    // Longest-first so compound names are matched before their prefixes
    lookup.sort(function (a, b) { return b.name.length - a.name.length; });

    // Full-text scan left-to-right — matches @mention at any position in text
    var pos = 0;
    while (pos < text.length) {
      var atIdx = text.indexOf('@', pos);
      if (atIdx === -1) {
        bodyEl.appendChild(document.createTextNode(text.slice(pos))); // XSS-safe
        break;
      }
      if (atIdx > pos) {
        bodyEl.appendChild(document.createTextNode(text.slice(pos, atIdx))); // XSS-safe
      }
      var scanMatched = false;
      for (var li = 0; li < lookup.length; li++) {
        var entry = lookup[li];
        var cand  = '@' + entry.name;
        if (text.indexOf(cand, atIdx) === atIdx) {
          var endPos  = atIdx + cand.length;
          var nxtCh   = endPos < text.length ? text.charAt(endPos) : '';
          // Boundary: next char must not be Arabic or Latin alphanumeric (prevents partial matches)
          var nxtCode = nxtCh ? nxtCh.charCodeAt(0) : 0;
          var isBound = !nxtCh ||
            !(nxtCode >= 0x0621 && nxtCode <= 0x06FF) && // not Arabic letter
            !(nxtCode >= 65 && nxtCode <= 90) &&          // not A-Z
            !(nxtCode >= 97 && nxtCode <= 122) &&         // not a-z
            !(nxtCode >= 48 && nxtCode <= 57);            // not 0-9
          if (isBound) {
            var mentEl = entry.tw_id ? document.createElement('a') : document.createElement('span');
            mentEl.className = 'pc-cmt-mention';
            mentEl.textContent = cand; // XSS-safe
            if (entry.tw_id) mentEl.href = '/u/' + entry.tw_id; // safe: tw_id from DB/API
            bodyEl.appendChild(mentEl);
            pos = endPos;
            scanMatched = true;
            break;
          }
        }
      }
      if (!scanMatched) {
        // Fallback: render @\S+ as an unlinked span
        var fbM = text.slice(atIdx).match(/^@\S+/);
        if (fbM) {
          var fbEl = document.createElement('span');
          fbEl.className = 'pc-cmt-mention';
          fbEl.textContent = fbM[0]; // XSS-safe
          bodyEl.appendChild(fbEl);
          pos = atIdx + fbM[0].length;
        } else {
          bodyEl.appendChild(document.createTextNode('@')); // XSS-safe
          pos = atIdx + 1;
        }
      }
    }
  }

  // Arabic reply count label.
  function _cmtReplyCountText(n) {
    if (n === 1) return 'عرض رد واحد';
    if (n === 2) return 'عرض ردّين';
    return 'عرض ' + n + ' ردود';
  }

  // Toggle the open/closed state of a replies group (toggle btn + box).
  // Stores count in toggle.dataset.count so delete can update it without knowing the text.
  function _cmtSetToggleState(toggle, box, open, count) {
    toggle.dataset.count = String(count);
    if (open) {
      box.hidden = false;
      toggle.classList.add('pc-cmt-replies-toggle--open');
      toggle.textContent = 'إخفاء الردود';
    } else {
      box.hidden = true;
      toggle.classList.remove('pc-cmt-replies-toggle--open');
      toggle.textContent = _cmtReplyCountText(count);
    }
  }

  // Builds the toggle button + replies box for a parent comment.
  // Both are returned as { toggle, box } — caller inserts them into the list.
  function _cmtBuildRepliesGroup(parentId, replies, knownNames) {
    var toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'pc-cmt-replies-toggle';
    toggle.dataset.parentId = String(parentId);
    toggle.dataset.count    = String(replies.length);
    toggle.textContent = _cmtReplyCountText(replies.length);

    var box = document.createElement('div');
    box.className = 'pc-cmt-replies-box';
    box.dataset.parentId = String(parentId);
    box.hidden = true;

    for (var i = 0; i < replies.length; i++) {
      box.appendChild(_cmtBuildItem(replies[i], knownNames));
    }
    return { toggle: toggle, box: box };
  }

  // Called after a comment element is inserted into the visible DOM.
  // Measures body scrollHeight vs clientHeight (accurate only when element is in a visible container).
  // If text fits in 2 CSS lines: remove is-collapsed, keep expand button hidden.
  // If text overflows: keep is-collapsed, show expand button (inline icon at end of line 2).
  function _cmtCheckCollapse(el) {
    var wrap      = el ? el.querySelector('.pc-cmt-body-wrap') : null;
    var bodyEl    = wrap ? wrap.querySelector('.pc-cmt-body') : null;
    var expandBtn = wrap ? wrap.querySelector('.pc-cmt-expand-btn') : null;
    if (!wrap || !bodyEl || !expandBtn) return;
    if (bodyEl.scrollHeight > bodyEl.clientHeight + 2) {
      // Long text — show expand icon; body stays clamped
      expandBtn.style.display = '';
    } else {
      // Short text — remove clamp, keep expand button hidden
      bodyEl.classList.remove('is-collapsed');
      expandBtn.style.display = 'none';
    }
  }

  // Defers _cmtCheckCollapse to next animation frame — required for elements that were just
  // inserted into a newly-opened replies-box (layout not computed until next paint cycle).
  function _cmtScheduleCollapse(el) {
    requestAnimationFrame(function () { _cmtCheckCollapse(el); });
  }

  // Runs _cmtCheckCollapse on every item inside container (initial load only).
  function _cmtInitCollapseAll(container) {
    var items = container.querySelectorAll('.pc-cmt-item');
    for (var i = 0; i < items.length; i++) _cmtCheckCollapse(items[i]);
  }

  // Re-evaluates collapse state after body text changes (edit flow).
  // Resets to collapsed+expandBtn hidden, then calls _cmtCheckCollapse to re-measure.
  function _cmtRefreshCollapse(item) {
    var wrap    = item ? item.querySelector('.pc-cmt-body-wrap') : null;
    var bodyEl  = wrap  ? wrap.querySelector('.pc-cmt-body')     : null;
    if (!bodyEl || bodyEl.style.display === 'none') return;
    var expandBtn   = wrap.querySelector('.pc-cmt-expand-btn');
    var collapseBtn = wrap.querySelector('.pc-cmt-collapse-btn');
    // Reset to collapsed state before re-measuring
    bodyEl.classList.add('is-collapsed');
    if (expandBtn)   expandBtn.style.display   = 'none';
    if (collapseBtn) collapseBtn.style.display = 'none';
    _cmtCheckCollapse(item); // shows expandBtn if text is long
  }

  // Groups replies under their parent with collapse UI. Orphans appended last.
  function _cmtRenderComments(comments, list) {
    var rendered = {};

    // Collect all author names (longest-first) for compound free-mention highlighting
    var knownNames = comments.map(function (c) { return c.author_name || ''; })
      .filter(Boolean)
      .sort(function (a, b) { return b.length - a.length; });

    // Group replies by parent id — do NOT mark rendered here.
    // Replies are only marked rendered after being inserted into the DOM.
    var parentReplies = {};
    comments.forEach(function (c) {
      if (c.reply_to_comment_id != null) {
        var pid = String(c.reply_to_comment_id);
        if (!parentReplies[pid]) parentReplies[pid] = [];
        parentReplies[pid].push(c);
      }
    });

    // Top-level comments, each followed by their collapsed replies group
    comments.forEach(function (c) {
      if (c.reply_to_comment_id != null) return;
      list.appendChild(_cmtBuildItem(c, knownNames));
      rendered[c.id] = true;
      var replies = parentReplies[String(c.id)] || [];
      if (replies.length) {
        var grp = _cmtBuildRepliesGroup(c.id, replies, knownNames);
        list.appendChild(grp.toggle);
        list.appendChild(grp.box);
        // Mark replies rendered only after their group is in the DOM
        replies.forEach(function (r) { rendered[r.id] = true; });
      }
    });

    // Orphans last — replies whose parent is absent (soft-deleted/pruned or itself a reply)
    comments.forEach(function (c) {
      if (!rendered[c.id]) list.appendChild(_cmtBuildItem(c, knownNames));
    });

    // Evaluate collapse for all rendered items
    _cmtInitCollapseAll(list);
  }

  // Inserts a new reply into the collapsed replies-box for its parent.
  // Creates toggle+box if this is the first reply. Auto-opens the box.
  // Returns the inserted element so callers can scroll it into view.
  function _cmtInsertReply(list, newComment, knownNames) {
    var parentId = String(newComment.reply_to_comment_id);
    var box    = list.querySelector('.pc-cmt-replies-box[data-parent-id="' + parentId + '"]');
    var toggle = list.querySelector('.pc-cmt-replies-toggle[data-parent-id="' + parentId + '"]');

    if (box && toggle) {
      // Existing group: append and auto-open
      var newEl = _cmtBuildItem(newComment, knownNames || null);
      box.appendChild(newEl);
      var count = box.querySelectorAll('.pc-cmt-item').length;
      _cmtSetToggleState(toggle, box, true, count);
      // Schedule collapse check after next paint — box is just opening, layout not yet settled
      _cmtScheduleCollapse(newEl);
      return newEl;
    }

    // First reply — build toggle+box, auto-open
    var grp = _cmtBuildRepliesGroup(newComment.reply_to_comment_id, [newComment], knownNames || null);
    var parentEl = list.querySelector('.pc-cmt-item[data-cmt-id="' + parentId + '"]');
    if (parentEl) {
      var nxt = parentEl.nextElementSibling;
      if (nxt) list.insertBefore(grp.toggle, nxt);
      else     list.appendChild(grp.toggle);
      var nxt2 = grp.toggle.nextElementSibling;
      if (nxt2) list.insertBefore(grp.box, nxt2);
      else      list.appendChild(grp.box);
    } else {
      list.appendChild(grp.toggle);
      list.appendChild(grp.box);
    }
    _cmtSetToggleState(grp.toggle, grp.box, true, 1);
    var firstEl = grp.box.querySelector('.pc-cmt-item');
    // Schedule collapse check after next paint — box just became visible
    if (firstEl) _cmtScheduleCollapse(firstEl);
    return firstEl;
  }

  function _cmtBuildItem(c, knownNames) {
    var el = document.createElement('div');
    el.className = 'pc-cmt-item';
    el.dataset.cmtId = String(c.id);
    // Visual indentation: driven by reply_to_comment_id (not body @)
    if (c.reply_to_comment_id != null) {
      el.classList.add('pc-cmt-visual-reply');
      el.dataset.replyToId = String(c.reply_to_comment_id);
      if (c.reply_to_author_name)  el.dataset.replyToAuthor     = c.reply_to_author_name;
      if (c.reply_to_author_tw_id) el.dataset.replyToAuthorTwId = c.reply_to_author_tw_id;
    }
    // Store author tw_id + avatar for mention candidate collection
    if (c.author_tw_id) {
      el.dataset.authorTwId   = c.author_tw_id;
      el.dataset.authorAvatar = c.author_avatar || '';
    }
    // Build mentions array: junction table first, fall back to old mentioned_tw_id for backward compat
    var itemMentions = [];
    if (c.mentions && c.mentions.length) {
      itemMentions = c.mentions;
    } else if (c.mentioned_tw_id) {
      itemMentions = [{ name: c.mentioned_author_name || '', tw_id: c.mentioned_tw_id }];
    }
    if (itemMentions.length) {
      el.dataset.mentionsJson = JSON.stringify(itemMentions); // used by _cmtHandleEdit
    }

    // Avatar (32px) — <a> if author_tw_id available, <div> otherwise
    var ava = document.createElement(c.author_tw_id ? 'a' : 'div');
    ava.className = 'pc-cmt-ava';
    if (c.author_tw_id) {
      ava.href = '/u/' + c.author_tw_id; // safe: tw_id from API
    }
    var authorAva = twSafeImageUrl(c.author_avatar);
    if (authorAva) {
      var img = document.createElement('img');
      img.src = authorAva;
      img.alt = '';
      img.className = 'pc-cmt-ava-img';
      ava.appendChild(img);
    } else {
      ava.textContent = (c.author_name || '؟').charAt(0);
    }

    var content = document.createElement('div');
    content.className = 'pc-cmt-content';

    // Header: column layout — Row 1: name, Row 2: meta row
    var header = document.createElement('div');
    header.className = 'pc-cmt-header';

    var headerLeft = document.createElement('div');
    headerLeft.className = 'pc-cmt-header-left';

    // Row 1: author name — <a> if author_tw_id available (opens /u/{tw_id})
    var nameEl = document.createElement(c.author_tw_id ? 'a' : 'span');
    nameEl.className = 'pc-cmt-author';
    nameEl.textContent = c.author_name || ''; // XSS-safe
    if (c.author_tw_id) nameEl.href = '/u/' + c.author_tw_id; // safe: tw_id from API
    headerLeft.appendChild(nameEl);

    // Row 2: meta row (time + reply + edited)
    var metaRow = document.createElement('div');
    metaRow.className = 'pc-cmt-meta-row';

    var relTime = _formatRelativeTime(c.created_at);
    if (relTime) {
      var timeEl = document.createElement('span');
      timeEl.className = 'pc-cmt-time';
      var clockIco = document.createElement('span');
      clockIco.className = 'pc-cmt-clock-ico';
      clockIco.innerHTML = _ICO_CLOCK; // static SVG only — no API data
      timeEl.appendChild(clockIco);
      timeEl.appendChild(document.createTextNode(relTime));
      metaRow.appendChild(timeEl);
    }

    if (c.updated_at) {
      var editedEl = document.createElement('span');
      editedEl.className = 'pc-cmt-edited';
      editedEl.textContent = '· تم التعديل';
      metaRow.appendChild(editedEl);
    }

    headerLeft.appendChild(metaRow);
    header.appendChild(headerLeft);

    // Three-dot ⋮ button (portal-based — no inline dropdown)
    if (c.viewer_can_edit || c.viewer_can_delete) {
      var menuBtn = document.createElement('button');
      menuBtn.type = 'button';
      menuBtn.className = 'pc-cmt-menu-btn';
      menuBtn.dataset.cmtId     = String(c.id);
      menuBtn.dataset.canEdit   = c.viewer_can_edit   ? '1' : '0';
      menuBtn.dataset.canDelete = c.viewer_can_delete ? '1' : '0';
      menuBtn.textContent = '⋮';
      header.appendChild(menuBtn);
    }

    content.appendChild(header);

    // Body wrapper — anchors the inline expand icon (position:absolute)
    var bodyWrap = document.createElement('div');
    bodyWrap.className = 'pc-cmt-body-wrap';

    // Body — XSS-safe via _renderCommentBody (@mention highlighted, rest as text nodes)
    var bodyEl = document.createElement('p');
    bodyEl.className = 'pc-cmt-body is-collapsed';
    _renderCommentBody(bodyEl, c.body,
      c.reply_to_author_name || null, c.reply_to_author_tw_id || null,
      knownNames             || null,
      itemMentions.length    ? itemMentions : null);
    bodyWrap.appendChild(bodyEl);

    // Expand icon — shown by _cmtCheckCollapse only when text overflows 2 lines.
    // position:absolute at bottom-inline-end so it overlays end of line 2 (RTL: bottom-left).
    // innerHTML is static SVG only — no API data.
    var expandBtn = document.createElement('button');
    expandBtn.type = 'button';
    expandBtn.className = 'pc-cmt-expand-btn';
    expandBtn.setAttribute('aria-label', 'عرض المزيد');
    expandBtn.innerHTML = _ICO_CMT_EXPAND; // static SVG + ellipsis span — XSS safe
    expandBtn.style.display = 'none'; // hidden until _cmtCheckCollapse shows it
    bodyWrap.appendChild(expandBtn);

    // Collapse icon — shown below expanded text; hidden by default
    var collapseBtn = document.createElement('button');
    collapseBtn.type = 'button';
    collapseBtn.className = 'pc-cmt-collapse-btn';
    collapseBtn.setAttribute('aria-label', 'عرض أقل');
    collapseBtn.innerHTML = _ICO_CMT_COLLAPSE; // static SVG — XSS safe
    collapseBtn.style.display = 'none';
    bodyWrap.appendChild(collapseBtn);

    content.appendChild(bodyWrap);

    // Reply button — below body text (not in meta row)
    var replyBtn = document.createElement('button');
    replyBtn.type = 'button';
    replyBtn.className = 'pc-cmt-reply-btn';
    replyBtn.dataset.cmtId = String(c.id);
    replyBtn.dataset.authorName = c.author_name || '';
    replyBtn.textContent = 'رد';
    content.appendChild(replyBtn);

    // Empty .pc-cmt-acts kept as DOM anchor for _cmtHandleEdit insertBefore
    var acts = document.createElement('div');
    acts.className = 'pc-cmt-acts';
    content.appendChild(acts);

    el.appendChild(ava);
    el.appendChild(content);
    return el;
  }

  function _cmtPopulatePanel(postId, opts) {
    var panel = _cmtGetPanel(postId);
    if (!panel || panel._cmtInitialized) return;
    panel._cmtInitialized = true;
    panel._twCmtOpts = opts;   // the controller that owns this panel (signedIn · postOwner)
    // A new panel for a post that was drawn before (feed re-render — task 8.6b-2) starts from
    // scratch: no reply target / picked mentions / open menus left from the old panel.
    var pid = String(postId);
    delete _cmtReplyTarget[pid];
    delete _cmtReplyTargetId[pid];
    delete _cmtMentionedCandidates[pid];
    if (_cmtMentionState.postId === pid) _cmtCloseMentionMenu();
    if (_cmtPortalFor && String(_cmtPortalFor.postId) === pid) _cmtHidePortalMenu();
    panel.addEventListener('click', _cmtOnPanelClick);   // comment items — one listener per panel

    var list = document.createElement('div');
    list.className = 'pc-cmts-list';
    list.addEventListener('scroll', _cmtHidePortalMenu, { passive: true });
    list.addEventListener('scroll', function () { _cmtCloseMentionMenu(); }, { passive: true });

    var loading = document.createElement('div');
    loading.className = 'pc-cmts-loading';
    loading.textContent = 'جاري التحميل…';

    var signedIn = _cmtSignedIn(postId);   // the page's session check (opts.signedIn)
    var inputRow = document.createElement('div');
    inputRow.className = 'pc-cmts-input-row';
    if (signedIn) {
      var ta = document.createElement('textarea');
      ta.className   = 'pc-cmts-ta';
      ta.placeholder = 'اكتب تعليقاً…';
      ta.maxLength   = 1000;
      ta.rows        = 1; // auto-grows via _autoResizeTextarea
      ta.addEventListener('input', function () {
        _autoResizeTextarea(ta);
        _cmtHandleMentionInput(ta, String(postId));
      });
      // compositionend fires after IME commits the character (Arabic/CJK mobile keyboards).
      // At this point selectionStart is reliable, so filtering produces correct results.
      ta.addEventListener('compositionend', function () {
        _cmtHandleMentionInput(ta, String(postId));
      });
      ta.addEventListener('keydown', function (e) { _cmtHandleMentionKeydown(e, ta); });
      var sendBtn = document.createElement('button');
      sendBtn.type      = 'button';
      sendBtn.className = 'pc-cmts-send';
      sendBtn.dataset.postId = String(postId);
      sendBtn.textContent = 'إرسال';
      // RTL layout: sendBtn first → appears on right; ta fills remainder on left
      inputRow.appendChild(sendBtn);
      inputRow.appendChild(ta);
    } else {
      var guest = document.createElement('div');
      guest.className = 'pc-cmts-guest';
      guest.textContent = 'سجّل دخولك للتعليق';
      inputRow.appendChild(guest);
    }

    // "رداً على" strip — shown when a reply target is active
    var replyStrip = document.createElement('div');
    replyStrip.className = 'pc-cmt-reply-strip';
    replyStrip.style.display = 'none';
    var rText = document.createElement('span');
    rText.textContent = 'رداً على: ';
    var rName = document.createElement('span');
    rName.className = 'pc-cmt-reply-strip-name';
    var rCancel = document.createElement('button');
    rCancel.type = 'button';
    rCancel.className = 'pc-cmt-reply-strip-cancel';
    rCancel.textContent = '×';
    rCancel.addEventListener('click', function () { _cmtCancelReply(String(postId)); });
    replyStrip.appendChild(rText);
    replyStrip.appendChild(rName);
    replyStrip.appendChild(rCancel);

    panel.appendChild(list);
    panel.appendChild(loading);
    panel.appendChild(replyStrip);
    panel.appendChild(inputRow);
  }

  // Comments come one page of threads at a time (task 5.0h — AUD-P2-35): next_cursor → a
  // «عرض المزيد» button at the end of the list loads the next page (cursor = last thread id).
  function _cmtLoadComments(postId, cursor) {
    var panel = _cmtGetPanel(postId);
    if (!panel) return;
    var list    = panel.querySelector('.pc-cmts-list');
    var loading = panel.querySelector('.pc-cmts-loading');
    if (list && !cursor) list.innerHTML = '';
    var oldMore = list && list.querySelector('.pc-cmts-more');
    if (oldMore) oldMore.remove();
    if (loading) loading.style.display = 'block';

    var url = '/company/posts/' + encodeURIComponent(postId) + '/comments'
      + (cursor ? '?cursor=' + encodeURIComponent(cursor) : '');
    twApi(url)
      .then(function (res) {
        if (loading) loading.style.display = 'none';
        if (!list) return;
        if (!res.ok) {
          if (cursor) {
            if (window.showToast) showToast(twT('post.cmt.more_failed'), 'error');
            _cmtAppendMore(postId, list, cursor);
            return;
          }
          var err = document.createElement('div');
          err.className = 'pc-cmts-empty';
          err.textContent = 'تعذّر تحميل التعليقات';
          list.appendChild(err);
          return;
        }
        var data = res.data;
        var comments = (data && data.comments) ? data.comments : [];
        if (!cursor && !comments.length) {
          var empty = document.createElement('div');
          empty.className = 'pc-cmts-empty';
          empty.textContent = 'لا توجد تعليقات بعد';
          list.appendChild(empty);
          return;
        }
        // A comment the viewer sent after page 1 is already in the list (appended on send)
        comments = comments.filter(function (c) {
          return !list.querySelector('.pc-cmt-item[data-cmt-id="' + Number(c.id) + '"]');
        });
        _cmtRenderComments(comments, list);
        if (data && data.next_cursor) _cmtAppendMore(postId, list, data.next_cursor);
      });
  }

  function _cmtAppendMore(postId, list, cursor) {
    var more = document.createElement('button');
    more.type = 'button';
    more.className = 'tw-btn-ghost pc-cmts-more';
    more.textContent = twT('post.cmt.more');
    more.addEventListener('click', function () { _cmtLoadComments(postId, cursor); });
    list.appendChild(more);
  }

  function _cmtHandleSend(postId) {
    var panel = _cmtGetPanel(postId);
    if (!panel) return;
    var ta  = panel.querySelector('.pc-cmts-ta');
    if (!ta) return;
    var body = ta.value.trim();
    if (!body) { if (window.showToast) showToast('اكتب تعليقاً أولاً', 'error'); return; }
    if (body.length > 1000) { if (window.showToast) showToast('التعليق طويل جداً (1000 حرف كحد أقصى)', 'error'); return; }

    var signedIn = _cmtSignedIn(postId);   // the page's session check (opts.signedIn)
    if (!signedIn) { if (window.showToast) showToast('سجّل دخولك للتعليق', 'info'); return; }

    var sendBtn = panel.querySelector('.pc-cmts-send');
    if (sendBtn) sendBtn.disabled = true;

    var replyToId = _cmtReplyTargetId[String(postId)]
      ? parseInt(_cmtReplyTargetId[String(postId)], 10)
      : null;
    // Only send mentioned_tw_ids whose '@name' still appears anywhere in body — prevents stale mentions
    var _mcs = _cmtMentionedCandidates[String(postId)] || [];
    var mentionedTwIdsOut = [];
    for (var mci = 0; mci < _mcs.length; mci++) {
      var mc = _mcs[mci];
      if (mc && mc.tw_id && mc.name && body.indexOf('@' + mc.name) >= 0) {
        mentionedTwIdsOut.push(mc.tw_id);
      }
    }
    var payload = { body: body };
    if (replyToId)                payload.reply_to_comment_id = replyToId;
    if (mentionedTwIdsOut.length) payload.mentioned_tw_ids    = mentionedTwIdsOut;

    twApi('/company/posts/' + encodeURIComponent(postId) + '/comments', { method: 'POST', body: payload })
      .then(function (res) {
        if (sendBtn) sendBtn.disabled = false;
        if (!res.ok || !res.data || res.data.status !== 'success') {
          var msg = twApiMessage(res, 'تعذّر إرسال التعليق');
          if (window.showToast) showToast(res.status === 429 ? 'الرجاء التمهّل قليلاً' : msg, 'error');
          return;
        }
        ta.value = '';
        ta.style.height = ''; // reset auto-resize after send
        _cmtReplyTarget[String(postId)]    = null;
        _cmtReplyTargetId[String(postId)]  = null;
        _cmtMentionedCandidates[String(postId)] = [];
        var rStrip = panel.querySelector('.pc-cmt-reply-strip');
        if (rStrip) rStrip.style.display = 'none';
        var list = panel.querySelector('.pc-cmts-list');
        if (list) {
          var empty = list.querySelector('.pc-cmts-empty');
          if (empty) empty.remove();
          var newComment  = res.data.comment;
          var knownNames  = _cmtKnownNames(String(postId));
          if (newComment.reply_to_comment_id != null) {
            // Reply: insert under parent, scroll only the new element into view
            var newEl = _cmtInsertReply(list, newComment, knownNames);
            if (newEl && newEl.scrollIntoView) {
              newEl.scrollIntoView({ block: 'nearest' });
            }
          } else {
            // Top-level comment: append, check collapse, scroll list to bottom
            var topEl = _cmtBuildItem(newComment, knownNames);
            list.insertBefore(topEl, list.querySelector('.pc-cmts-more'));   // the «more» button stays last
            _cmtScheduleCollapse(topEl); // defer to next paint for accurate layout
            list.scrollTop = list.scrollHeight;
          }
        }
        _cmtUpdateCount(postId, 1);
      });
  }

  function _cmtHandleEdit(cmtId, postId) {
    // Guard: prevent re-entry while a PATCH is in flight
    if (_cmtEditInFlight[cmtId]) return;

    var panel = _cmtGetPanel(postId);
    if (!panel) return;
    var item = panel.querySelector('.pc-cmt-item[data-cmt-id="' + cmtId + '"]');
    if (!item) return;
    var content = item.querySelector('.pc-cmt-content');
    if (!content) return;
    var bodyEl = item.querySelector('.pc-cmt-body');
    if (!bodyEl) return;
    if (item.querySelector('.pc-cmt-edit-ta')) return; // already in edit mode

    var originalText      = bodyEl.textContent; // textContent returns full text even with child spans
    var wasVisualReply    = item.classList.contains('pc-cmt-visual-reply');
    var replyToAuthor     = item.dataset.replyToAuthor     || null;
    var replyToAuthorTwId = item.dataset.replyToAuthorTwId || null;
    var mentionsJson = item.dataset.mentionsJson || '';
    var itemMentions = [];
    try { if (mentionsJson) itemMentions = JSON.parse(mentionsJson); } catch (_e) { itemMentions = []; }

    // 1. Build editWrap fully in memory
    var editWrap  = document.createElement('div');
    editWrap.className = 'pc-cmt-edit-wrap';
    var editTa = document.createElement('textarea');
    editTa.className = 'pc-cmts-ta pc-cmt-edit-ta';
    editTa.maxLength = 1000;
    editTa.rows      = 1;
    editTa.value     = originalText;
    editTa.addEventListener('input', function () { _autoResizeTextarea(editTa); });
    var editBtns = document.createElement('div');
    editBtns.className = 'pc-cmt-edit-btns';
    var saveBtn = document.createElement('button');
    saveBtn.type      = 'button';
    saveBtn.className = 'pc-cmts-send pc-cmt-edit-save';
    saveBtn.textContent = 'حفظ';
    var cancelBtn = document.createElement('button');
    cancelBtn.type      = 'button';
    cancelBtn.className = 'pc-cmt-act pc-cmt-edit-cancel';
    cancelBtn.textContent = 'إلغاء';
    editBtns.appendChild(saveBtn);
    editBtns.appendChild(cancelBtn);
    editWrap.appendChild(editTa);
    editWrap.appendChild(editBtns);

    // 2. Insert editWrap into DOM FIRST, then hide bodyWrap — never a blank gap
    var acts = content.querySelector('.pc-cmt-acts'); // correct parent: content, not item
    if (acts) content.insertBefore(editWrap, acts);
    else content.appendChild(editWrap);
    var bodyWrap = content.querySelector('.pc-cmt-body-wrap');
    if (bodyWrap) bodyWrap.style.display = 'none';

    // Size to existing text now that the element is in the DOM (scrollHeight is accurate)
    _autoResizeTextarea(editTa);

    // Focus + move cursor to end
    editTa.focus();
    editTa.setSelectionRange(editTa.value.length, editTa.value.length);

    cancelBtn.addEventListener('click', function () {
      if (bodyWrap) bodyWrap.style.display = '';
      editWrap.remove();
    });

    saveBtn.addEventListener('click', function () {
      if (_cmtEditInFlight[cmtId]) return; // already saving
      var newBody = editTa.value.trim();
      if (!newBody) { if (window.showToast) showToast('التعليق لا يمكن أن يكون فارغاً', 'error'); return; }
      if (newBody.length > 1000) { if (window.showToast) showToast('التعليق طويل جداً (1000 حرف كحد أقصى)', 'error'); return; }
      var signedIn = _cmtSignedIn(postId);   // the page's session check (opts.signedIn)
      if (!signedIn) return;

      // 3. Optimistic UI — update text immediately, remove edit UI
      _cmtEditInFlight[cmtId] = true;
      saveBtn.disabled = true;
      var editKnownNames = _cmtKnownNames(String(postId));
      _renderCommentBody(bodyEl, newBody, replyToAuthor, replyToAuthorTwId, editKnownNames,
        itemMentions.length ? itemMentions : null); // XSS-safe
      // visual-reply class is driven by reply_to_comment_id (immutable per comment) — no change
      if (bodyWrap) bodyWrap.style.display = '';
      editWrap.remove();
      _cmtRefreshCollapse(item); // re-evaluate collapse for new body length

      twApi('/company/posts/comments/' + encodeURIComponent(cmtId), { method: 'PATCH', body: { body: newBody } })
        .then(function (res) {
          _cmtEditInFlight[cmtId] = false;
          if (!res.ok || !res.data || res.data.status !== 'success') {
            // Rollback — restore original text + visual-reply state + re-evaluate collapse
            _renderCommentBody(bodyEl, originalText, replyToAuthor, replyToAuthorTwId, editKnownNames,
              itemMentions.length ? itemMentions : null); // XSS-safe rollback
            _cmtRefreshCollapse(item);
            if (wasVisualReply) item.classList.add('pc-cmt-visual-reply');
            else item.classList.remove('pc-cmt-visual-reply');
            var msg = twApiMessage(res, 'تعذّر تعديل التعليق');
            if (window.showToast) showToast(res.status === 429 ? 'الرجاء التمهّل قليلاً' : msg, 'error');
            return;
          }
          // Confirm with server body + mark as edited + re-evaluate collapse for confirmed text
          var confirmedBody = res.data.comment.body;
          _renderCommentBody(bodyEl, confirmedBody, replyToAuthor, replyToAuthorTwId, editKnownNames,
            itemMentions.length ? itemMentions : null); // XSS-safe
          _cmtRefreshCollapse(item);
          var metaRow = item.querySelector('.pc-cmt-meta-row');
          if (metaRow && !metaRow.querySelector('.pc-cmt-edited')) {
            var editedEl = document.createElement('span');
            editedEl.className = 'pc-cmt-edited';
            editedEl.textContent = '· تم التعديل';
            metaRow.appendChild(editedEl);
          }
        });
    });
  }

  function _cmtHandleDelete(cmtId, postId) {
    var signedIn = _cmtSignedIn(postId);   // the page's session check (opts.signedIn)
    if (!signedIn) return;

    twApi('/company/posts/comments/' + encodeURIComponent(cmtId), { method: 'DELETE' })
      .then(function (res) {
        if (!res.ok || !res.data || res.data.status !== 'success') {
          if (window.showToast) showToast(twApiMessage(res, 'تعذّر حذف التعليق'), 'error');
          return;
        }
        var panel = _cmtGetPanel(postId);
        if (panel) {
          var list = panel.querySelector('.pc-cmts-list');
          var item = panel.querySelector('.pc-cmt-item[data-cmt-id="' + cmtId + '"]');
          if (item) {
            var replyBox = item.closest('.pc-cmt-replies-box');
            if (replyBox) {
              // Deleted item is a reply inside a box
              item.remove();
              var parentId   = replyBox.dataset.parentId;
              var remaining  = replyBox.querySelectorAll('.pc-cmt-item').length;
              var toggleEl   = list ? list.querySelector('.pc-cmt-replies-toggle[data-parent-id="' + parentId + '"]') : null;
              if (remaining === 0) {
                if (toggleEl) toggleEl.remove();
                replyBox.remove();
              } else {
                if (toggleEl) {
                  var isOpen = !replyBox.hidden;
                  _cmtSetToggleState(toggleEl, replyBox, isOpen, remaining);
                }
              }
            } else {
              // Deleted item is a top-level comment — also remove its replies group
              if (list) {
                var childToggle = list.querySelector('.pc-cmt-replies-toggle[data-parent-id="' + cmtId + '"]');
                var childBox    = list.querySelector('.pc-cmt-replies-box[data-parent-id="' + cmtId + '"]');
                if (childToggle) childToggle.remove();
                if (childBox)    childBox.remove();
              }
              item.remove();
            }
            // Show empty state if no comments remain (top-level or any)
            if (list && !list.querySelector('.pc-cmt-item')) {
              var empty = document.createElement('div');
              empty.className = 'pc-cmts-empty';
              empty.textContent = 'لا توجد تعليقات بعد';
              list.appendChild(empty);
            }
          }
        }
        _cmtUpdateCount(postId, -1);
      });
  }

  // ── Comment item clicks — delegated on each panel (bound once in _cmtPopulatePanel) ──
  function _cmtOnPanelClick(e) {
    // Comment body expand — show full text, switch to collapse icon
    var cmtExpandBtn = e.target.closest('.pc-cmt-expand-btn');
    if (cmtExpandBtn) {
      var bWrap = cmtExpandBtn.closest('.pc-cmt-body-wrap');
      if (bWrap) {
        var bBody = bWrap.querySelector('.pc-cmt-body');
        var bCol  = bWrap.querySelector('.pc-cmt-collapse-btn');
        if (bBody) bBody.classList.remove('is-collapsed');
        cmtExpandBtn.style.display = 'none';
        if (bCol) bCol.style.display = '';
      }
      return;
    }
    // Comment body collapse — re-clamp text, switch back to expand icon
    var cmtCollapseBtn = e.target.closest('.pc-cmt-collapse-btn');
    if (cmtCollapseBtn) {
      var bWrap = cmtCollapseBtn.closest('.pc-cmt-body-wrap');
      if (bWrap) {
        var bBody = bWrap.querySelector('.pc-cmt-body');
        var bExp  = bWrap.querySelector('.pc-cmt-expand-btn');
        if (bBody) bBody.classList.add('is-collapsed');
        cmtCollapseBtn.style.display = 'none';
        if (bExp) bExp.style.display = '';
      }
      return;
    }
    // Replies toggle — open/close replies box
    var repliesToggle = e.target.closest('.pc-cmt-replies-toggle[data-parent-id]');
    if (repliesToggle) {
      var rParentId = repliesToggle.dataset.parentId;
      var rList = repliesToggle.closest('.pc-cmts-list');
      if (rList) {
        var rBox = rList.querySelector('.pc-cmt-replies-box[data-parent-id="' + rParentId + '"]');
        if (rBox) {
          var rCount = parseInt(repliesToggle.dataset.count || '0', 10);
          _cmtSetToggleState(repliesToggle, rBox, rBox.hidden, rCount);
        }
      }
      return;
    }
    // Comment send
    var cmtSend = e.target.closest('.pc-cmts-send[data-post-id]');
    if (cmtSend) { _cmtHandleSend(cmtSend.getAttribute('data-post-id')); return; }
    // Comment three-dot ⋮ button — open/close portal menu
    var cmtMenuBtn = e.target.closest('.pc-cmt-menu-btn[data-cmt-id]');
    if (cmtMenuBtn) {
      e.stopPropagation();
      var cmtId  = cmtMenuBtn.getAttribute('data-cmt-id');
      var pnl    = cmtMenuBtn.closest('.pc-cmts-panel');
      var pId    = pnl ? pnl.dataset.postId : null;
      var canEd  = cmtMenuBtn.getAttribute('data-can-edit')   === '1';
      var canDl  = cmtMenuBtn.getAttribute('data-can-delete') === '1';
      if (_cmtOpenMenuId === cmtId) {
        _cmtHidePortalMenu();
      } else {
        if (_cmtOpenMenuId) _cmtHidePortalMenu();
        _cmtShowPortalMenu(cmtMenuBtn, cmtId, pId, canEd, canDl);
      }
      return;
    }
    // Reply button — prefill @mention + track reply_to_comment_id
    var cmtReplyBtn = e.target.closest('.pc-cmt-reply-btn[data-cmt-id]');
    if (cmtReplyBtn) {
      var pnl = cmtReplyBtn.closest('.pc-cmts-panel');
      if (pnl) _cmtHandleReply(pnl.dataset.postId, cmtReplyBtn.dataset.authorName, cmtReplyBtn.dataset.cmtId);
      return;
    }
  }

  // ── Page-wide listeners — bound once per page (not per controller) ──
  var _cmtGlobalBound = false;
  function _cmtBindGlobal() {
    if (_cmtGlobalBound) return;
    _cmtGlobalBound = true;

    // Close the portal comment menu when clicking outside (post ⋯ menus = TwPostCard)
    document.addEventListener('click', function (e) {
      if (_cmtPortalMenu && _cmtPortalMenu.style.display !== 'none') {
        if (!e.target.closest('#pc-cmt-portal-menu') && !e.target.closest('.pc-cmt-menu-btn')) {
          _cmtHidePortalMenu();
        }
      }
    });

    // Close mention menu when clicking outside
    document.addEventListener('click', function (e) {
      if (_cmtMentionState.open) {
        var menu = document.getElementById('pc-cmt-mention-menu');
        if (menu && !menu.contains(e.target) && e.target !== _cmtMentionState.ta) {
          _cmtCloseMentionMenu();
        }
      }
    });

    // Close portal menu + mention menu on page scroll
    document.addEventListener('scroll', _cmtHidePortalMenu, { passive: true, capture: true });
    document.addEventListener('scroll', function () { _cmtCloseMentionMenu(); }, { passive: true, capture: true });

    // Portal menu item clicks (edit / delete)
    document.body.addEventListener('click', function (e) {
      if (!e.target.closest('#pc-cmt-portal-menu')) return;
      var editItem = e.target.closest('.pc-cmt-menu-edit[data-cmt-id]');
      if (editItem) {
        _cmtHidePortalMenu();
        _cmtHandleEdit(editItem.getAttribute('data-cmt-id'), editItem.getAttribute('data-post-id'));
        return;
      }
      var delItem = e.target.closest('.pc-cmt-menu-del[data-cmt-id]');
      if (delItem) {
        _cmtHidePortalMenu();
        _cmtHandleDelete(delItem.getAttribute('data-cmt-id'), delItem.getAttribute('data-post-id'));
        return;
      }
    });

    // Mention menu item clicks — insert selected name into active textarea
    document.body.addEventListener('click', function (e) {
      if (!_cmtMentionState.open) return;
      var item = e.target.closest('.pc-cmt-mention-item[data-mention-name]');
      if (!item) return;
      var ta = _cmtMentionState.ta;
      if (ta) _cmtInsertMention(ta, item.dataset.mentionName, item.dataset.mentionTwId || null);
    });
  }

  // create(opts) → { build(postId), load(postId, cursor) } — see the header.
  function create(opts) {
    opts = opts || {};
    // Same moment as before (the page's DOMContentLoaded) — or now when the page is ready
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _cmtBindGlobal);
    else _cmtBindGlobal();
    return {
      build: function (postId) { _cmtPopulatePanel(postId, opts); },
      load:  function (postId, cursor) { _cmtLoadComments(postId, cursor); },
    };
  }

  window.TwPostComments = { create: create };
}());
