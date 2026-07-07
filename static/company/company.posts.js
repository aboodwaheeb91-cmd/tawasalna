// company.posts.js — create/edit post, delete post, modal, tag picker, color picker
// Load order: 6th (after jobs)
(function () {
  'use strict';

  var isPostCreating       = false;
  var isPostDeleting       = false;
  var _postHistoryPushed   = false;
  var _selectedTags        = [];       // tag picker state
  var _selectedPostColor   = 'teal';   // color picker state (default = teal)
  var _editingPostId       = null;     // post id being edited, or null in create mode
  var _isEditingPost       = false;    // true when modal is in edit mode

  // ── Tag Picker ────────────────────────────────────────────────
  function _searchTags(q) {
    if (!window.TW || !Array.isArray(TW.POST_TAGS)) return [];
    // Strip "ال" prefix so "التوظيف" matches "توظيف"
    var q2 = (q.length > 2 && q.slice(0, 2) === 'ال') ? q.slice(2) : null;
    return TW.POST_TAGS.filter(function (t) {
      return t.indexOf(q) !== -1 || (q2 && t.indexOf(q2) !== -1);
    }).slice(0, 10);
  }

  function _renderTagChips() {
    var chips = document.getElementById('p-tags-chips');
    var count = document.getElementById('p-tags-count');
    if (!chips) return;
    chips.innerHTML = _selectedTags.map(function (t, i) {
      return '<span class="ptc-chip">'
        + t
        + '<button type="button" class="ptc-chip-x" data-idx="' + i + '" aria-label="إزالة">&#x2715;</button>'
        + '</span>';
    }).join('');
    if (count) count.textContent = _selectedTags.length + '/5';
  }

  function _addTag(tag) {
    if (_selectedTags.length >= 5) {
      if (window.showToast) showToast('يمكن اختيار 5 وسوم كحد أقصى'); return;
    }
    if (!window.TW || !Array.isArray(TW.POST_TAGS) || TW.POST_TAGS.indexOf(tag) === -1) {
      if (window.showToast) showToast('اختر الوسم من القائمة المقترحة'); return;
    }
    if (_selectedTags.indexOf(tag) !== -1) return; // no duplicate
    _selectedTags.push(tag);
    _renderTagChips();
    var search = document.getElementById('p-tags-search');
    if (search) search.value = '';
    _closeTagDropdown();
  }

  function _removeTag(idx) {
    _selectedTags.splice(idx, 1);
    _renderTagChips();
  }

  function _openTagDropdown(results) {
    var dd = document.getElementById('p-tags-dropdown');
    if (!dd) return;
    if (!results.length) { _closeTagDropdown(); return; }
    dd.innerHTML = results.map(function (t) {
      return '<button type="button" class="ptc-option" data-tag="' + t + '">' + t + '</button>';
    }).join('');
    // Use fixed positioning to escape modal overflow-y:auto clipping
    var searchEl = document.getElementById('p-tags-search');
    if (searchEl) {
      var rect = searchEl.getBoundingClientRect();
      dd.style.top   = (rect.bottom + 2) + 'px';
      dd.style.left  = rect.left + 'px';
      dd.style.width = rect.width + 'px';
    }
    dd.style.display = 'block';
  }

  function _closeTagDropdown() {
    var dd = document.getElementById('p-tags-dropdown');
    if (dd) dd.style.display = 'none';
  }

  function _resetTagPicker() {
    _selectedTags = [];
    _renderTagChips();
    _closeTagDropdown();
    var search = document.getElementById('p-tags-search');
    if (search) search.value = '';
  }

  // ── Color Picker ──────────────────────────────────────────────
  function _applyPostColorPreview() {
    var modal = document.querySelector('#postOverlay .modal');
    if (!modal || !window.TW || !TW.POST_THEME_COLORS) return;
    var clr = TW.POST_THEME_COLORS[_selectedPostColor] || TW.POST_THEME_COLORS.teal;
    modal.style.setProperty('--pa', clr.accent);
    modal.style.setProperty('--pa-s', clr.soft);
    modal.style.setProperty('--pa-g', clr.glow);
  }

  function _renderColorPicker() {
    var row = document.getElementById('p-color-row');
    if (!row || !window.TW || !TW.POST_THEME_COLORS) return;
    row.innerHTML = Object.keys(TW.POST_THEME_COLORS).map(function (key) {
      var clr = TW.POST_THEME_COLORS[key];
      var isSel = key === _selectedPostColor;
      return '<button type="button" class="pcc-dot' + (isSel ? ' selected' : '') + '"'
        + ' data-color="' + key + '"'
        + ' title="' + clr.name_ar + '"'
        + ' style="background:' + clr.accent + '">'
        + '</button>';
    }).join('');
    _applyPostColorPreview();
  }

  function _resetColorPicker() {
    _selectedPostColor = 'teal';
    _renderColorPicker(); // _renderColorPicker calls _applyPostColorPreview internally
  }

  function _bindColorPickerEvents() {
    _renderColorPicker();
    var row = document.getElementById('p-color-row');
    if (!row) return;
    row.addEventListener('click', function (e) {
      var btn = e.target.closest('.pcc-dot[data-color]');
      if (!btn) return;
      _selectedPostColor = btn.getAttribute('data-color');
      _renderColorPicker();
      _applyPostColorPreview();
    });
  }

  function _bindTagPickerEvents() {
    var searchEl = document.getElementById('p-tags-search');
    var chipsEl  = document.getElementById('p-tags-chips');
    var ddEl     = document.getElementById('p-tags-dropdown');

    // Portal: move dropdown to <body> so position:fixed is relative to viewport,
    // not the modal (which has transform:translateY that would break fixed children).
    if (ddEl && ddEl.parentNode !== document.body) {
      document.body.appendChild(ddEl);
    }

    if (searchEl) {
      searchEl.addEventListener('input', function () {
        var q = this.value.trim();
        if (q.length < 1) { _closeTagDropdown(); return; }
        _openTagDropdown(_searchTags(q));
      });
      searchEl.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        var dd = document.getElementById('p-tags-dropdown');
        var first = dd ? dd.querySelector('.ptc-option') : null;
        if (first) { _addTag(first.dataset.tag); }
        else if (this.value.trim().length >= 1) {
          if (window.showToast) showToast('اختر الوسم من القائمة المقترحة');
        }
      });
    }

    if (ddEl) {
      ddEl.addEventListener('click', function (e) {
        var opt = e.target.closest('.ptc-option[data-tag]');
        if (opt) _addTag(opt.dataset.tag);
      });
    }

    if (chipsEl) {
      chipsEl.addEventListener('click', function (e) {
        var btn = e.target.closest('.ptc-chip-x[data-idx]');
        if (btn) _removeTag(parseInt(btn.dataset.idx, 10));
      });
    }

    // Close dropdown on outside click.
    // Must also exclude the dropdown itself (now on body, outside #p-tags-wrap).
    document.addEventListener('click', function (e) {
      var dd = document.getElementById('p-tags-dropdown');
      if (e.target.closest('#p-tags-wrap')) return;
      if (dd && dd.contains(e.target)) return;
      _closeTagDropdown();
    });
  }

  // ── Modal mode helpers ────────────────────────────────────────
  function _setModalCreateMode() {
    var titleEl  = document.getElementById('postModalTitle');
    var lblEl    = document.getElementById('createPostBtnLabel');
    var noComEl  = document.getElementById('p-no-comments');
    var bodyEl   = document.getElementById('p-body');
    if (titleEl)  titleEl.textContent  = 'نشر منشور جديد';
    if (lblEl)    lblEl.textContent    = 'نشر';
    if (noComEl)  noComEl.checked      = false;
    if (bodyEl)   bodyEl.value         = '';
    _resetTagPicker();
    _resetColorPicker();
  }

  function _setModalEditMode(post) {
    var titleEl  = document.getElementById('postModalTitle');
    var lblEl    = document.getElementById('createPostBtnLabel');
    var noComEl  = document.getElementById('p-no-comments');
    var bodyEl   = document.getElementById('p-body');
    if (titleEl)  titleEl.textContent  = 'تعديل المنشور';
    if (lblEl)    lblEl.textContent    = 'حفظ التعديل';
    if (bodyEl)   bodyEl.value         = post.body || '';
    if (noComEl)  noComEl.checked      = (post.comments_enabled === false);

    // Tags
    _selectedTags = Array.isArray(post.tags) ? post.tags.slice() : [];
    _renderTagChips();
    var search = document.getElementById('p-tags-search');
    if (search) search.value = '';
    _closeTagDropdown();

    // Color
    _selectedPostColor = (post.theme_color && window.TW && TW.POST_THEME_COLORS && TW.POST_THEME_COLORS[post.theme_color])
      ? post.theme_color : 'teal';
    _renderColorPicker();
    _applyPostColorPreview();
  }

  // ── Modal ─────────────────────────────────────────────────────
  // postData: pass a post object to open in Edit Mode; omit or null for Create Mode.
  function openPostModal(postData) {
    // Guard: DOM event objects must never be treated as post data
    if (postData instanceof Event || (postData && typeof postData.id !== 'number')) postData = null;
    if (!window.companyState || !companyState.permissions.can_edit) return;
    var ov = document.getElementById('postOverlay');
    if (ov) ov.classList.add('show');
    if (postData) {
      _isEditingPost  = true;
      _editingPostId  = postData.id;
      _setModalEditMode(postData);
    } else {
      _isEditingPost  = false;
      _editingPostId  = null;
      _setModalCreateMode();
    }
    if (window.history && !_postHistoryPushed) {
      history.pushState({ modal: 'post' }, '', location.href);
      _postHistoryPushed = true;
    }
  }

  // fromPopstate=true means popstate already moved back; skip history.back().
  function _closePostOverlay(fromPopstate) {
    var ov = document.getElementById('postOverlay');
    if (ov) ov.classList.remove('show');
    _editingPostId  = null;
    _isEditingPost  = false;
    _setModalCreateMode();
    if (_postHistoryPushed && !fromPopstate) {
      _postHistoryPushed = false;
      if (window.history) history.back();
    } else {
      _postHistoryPushed = false;
    }
  }

  function createPost() {
    if (_isEditingPost) { updatePost(); return; }
    if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
    if (!window.companyState || !companyState.permissions.can_edit) {
      if (window.showToast) showToast('غير مصرح', 'error'); return;
    }
    if (isPostCreating) return;

    var bodyEl  = document.getElementById('p-body');
    var noComEl = document.getElementById('p-no-comments');
    var body    = (bodyEl ? bodyEl.value : '').trim();
    if (!body) { if (window.showToast) showToast('اكتب محتوى المنشور', 'error'); return; }

    var tags            = _selectedTags.slice();
    var color           = _selectedPostColor || null;
    var commentsEnabled = !(noComEl && noComEl.checked);

    isPostCreating = true;
    fetch('/company/posts', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
      body:    JSON.stringify({ body: body, tags: tags.length ? tags : null, theme_color: color, comments_enabled: commentsEnabled }),
    })
    .then(function (r) {
      if (!r.ok) throw new Error('create failed: ' + r.status);
      return r.json();
    })
    .then(function () {
      _closePostOverlay();
      if (window.loadPosts) loadPosts(true);
      if (window.showToast) showToast('تم نشر المنشور ✓');
    })
    .catch(function () {
      if (window.showToast) showToast('تعذّر نشر المنشور', 'error');
    })
    .finally(function () { isPostCreating = false; });
  }

  function updatePost() {
    if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
    if (!window.companyState || !companyState.permissions.can_edit) {
      if (window.showToast) showToast('غير مصرح', 'error'); return;
    }
    if (!_editingPostId) return;
    if (isPostCreating) return;

    var bodyEl  = document.getElementById('p-body');
    var noComEl = document.getElementById('p-no-comments');
    var body    = (bodyEl ? bodyEl.value : '').trim();
    if (!body) { if (window.showToast) showToast('اكتب محتوى المنشور', 'error'); return; }

    var tags            = _selectedTags.slice();
    var color           = _selectedPostColor || null;
    var commentsEnabled = !(noComEl && noComEl.checked);

    isPostCreating = true;
    fetch('/company/posts/' + _editingPostId, {
      method:  'PATCH',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
      body:    JSON.stringify({ body: body, tags: tags.length ? tags : null, theme_color: color, comments_enabled: commentsEnabled }),
    })
    .then(function (r) {
      if (!r.ok) throw new Error('update failed: ' + r.status);
      return r.json();
    })
    .then(function () {
      _closePostOverlay();
      if (window.loadPosts) loadPosts(true);
      if (window.showToast) showToast('تم تعديل المنشور ✓');
    })
    .catch(function () {
      if (window.showToast) showToast('تعذّر تعديل المنشور', 'error');
    })
    .finally(function () { isPostCreating = false; });
  }

  function deletePost(postId) {
    if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
    if (!window.companyState || !companyState.permissions.can_edit) {
      if (window.showToast) showToast('غير مصرح', 'error'); return;
    }
    if (isPostDeleting) return;
    if (!confirm('هل تريد حذف هذا المنشور؟')) return;

    isPostDeleting = true;
    fetch('/company/posts/' + postId, {
      method:  'DELETE',
      headers: { 'Authorization': 'Bearer ' + _jwt() },
    })
    .then(function (r) {
      if (!r.ok) throw new Error('delete failed: ' + r.status);
      return r.json();
    })
    .then(function () {
      if (window.loadPosts) loadPosts(true);
      if (window.showToast) showToast('تم حذف المنشور ✓');
    })
    .catch(function () {
      if (window.showToast) showToast('تعذّر حذف المنشور', 'error');
    })
    .finally(function () { isPostDeleting = false; });
  }

  // ── Post share ────────────────────────────────────────────────
  function _sharePostFallback(text) {
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); if (window.showToast) showToast('تم نسخ رابط المنشور ✓'); }
    catch (e) { if (window.showToast) showToast('تعذّر النسخ تلقائياً'); }
    document.body.removeChild(ta);
  }

  function _sharePost(postId) {
    var coName = (window.companyState && companyState.profile && companyState.profile.full_name)
      ? companyState.profile.full_name : 'شركة';
    var twId = (window.companyState && companyState.profile && companyState.profile.tw_id)
      ? companyState.profile.tw_id : null;
    var url = twId
      ? (location.origin || '') + '/u/' + encodeURIComponent(twId)
      : location.href;
    var shareText = 'منشور من ' + coName + ' على تواصلنا:\n' + url;
    if (navigator.share) {
      navigator.share({ title: 'منشور: ' + coName, text: shareText, url: url }).catch(function () {});
    } else if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(shareText)
        .then(function () { if (window.showToast) showToast('تم نسخ رابط المنشور ✓'); })
        .catch(function () { _sharePostFallback(shareText); });
    } else {
      _sharePostFallback(shareText);
    }
  }

  // ── Event bindings ──────────────────────────────────────────────
  function _bindPostEvents() {
    var q = function (id) { return document.getElementById(id); };

    var postModalBtn = q('postModalBtn'); if (postModalBtn) postModalBtn.addEventListener('click', function () { openPostModal(); });

    var postOverlay = q('postOverlay');
    if (postOverlay) postOverlay.addEventListener('click', function (e) {
      if (e.target === this) _closePostOverlay();
    });

    var createPostBtn = q('createPostBtn'); if (createPostBtn) createPostBtn.addEventListener('click', createPost);

    var postCancelBtn = q('postCancelBtn');
    if (postCancelBtn) postCancelBtn.addEventListener('click', _closePostOverlay);
  }

  // ── Post View Tracking ────────────────────────────────────────────────────
  var _viewedThisSession = {};  // post_id → true; resets on page reload
  var _postViewObserver  = null;

  function _getOrCreateVisitorKey() {
    var key = localStorage.getItem('cp_vk');
    if (!key) {
      key = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        var r = Math.random() * 16 | 0;
        return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
      });
      localStorage.setItem('cp_vk', key);
    }
    return key;
  }

  function _fmtViewsCount(n) {
    n = Number(n) || 0;
    if (n >= 1000) { var k = n / 1000; return (k % 1 === 0 ? k : k.toFixed(1)) + 'K مشاهدة'; }
    return n + ' مشاهدة';
  }

  function _sendView(postId) {
    var jwt     = window._jwt ? window._jwt() : '';
    var headers = { 'Content-Type': 'application/json' };
    var body    = {};
    if (jwt) { headers['Authorization'] = 'Bearer ' + jwt; }
    else      { body.visitor_key = _getOrCreateVisitorKey(); }

    fetch('/company/posts/' + postId + '/view', {
      method: 'POST', headers: headers, body: JSON.stringify(body)
    }).then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.status === 'success' && d.recorded) {
          // Bump the displayed count +1 without a full reload
          var card = document.querySelector('.post-card[data-post-id="' + postId + '"]');
          if (!card) return;
          var vEl = card.querySelector('.post-views');
          if (!vEl) return;
          var cur = parseInt(vEl.dataset.viewsCount, 10) || 0;
          var next = cur + 1;
          vEl.dataset.viewsCount = next;
          var svg = vEl.querySelector('svg');
          vEl.innerHTML = (svg ? svg.outerHTML : '') + _fmtViewsCount(next);
        }
      }).catch(function () { /* best-effort — ignore network errors */ });
  }

  function initPostViewTracking(container) {
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
                _sendView(pid);
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

  // ── Post Save ─────────────────────────────────────────────────────────────
  var _ICO_BOOKMARK_OUTLINE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>';
  var _ICO_BOOKMARK_CHECK   = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/><path d="M8.5 10l2.5 2.5 5-5" fill="none" stroke="var(--bg,#070b18)" stroke-width="2"/></svg>';

  function _renderSaveButton(btn, active) {
    btn.innerHTML = (active ? _ICO_BOOKMARK_CHECK : _ICO_BOOKMARK_OUTLINE) + (active ? 'محفوظ' : 'حفظ');
    if (active) { btn.classList.add('save-active');    }
    else        { btn.classList.remove('save-active'); }
    btn.dataset.saved = active ? '1' : '0';
  }

  var _saveDesired   = {};
  var _saveInFlight  = {};
  var _saveOrigState = {};

  function _saveGetBtn(postId) {
    var card = document.querySelector('.post-card[data-post-id="' + postId + '"]');
    return card ? card.querySelector('.pc-btn--save') : null;
  }

  function _dispatchSave(postId) {
    var desired = _saveDesired[postId];
    if (desired === undefined) return;
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) return;

    _saveInFlight[postId] = true;

    fetch('/company/posts/' + postId + '/save', {
      method:  'PUT',
      headers: { 'Authorization': 'Bearer ' + jwt, 'Content-Type': 'application/json' },
      body:    JSON.stringify({ saved: desired })
    })
      .then(function (r) {
        return r.json().then(function (d) { return { status: r.status, ok: r.ok, data: d }; });
      })
      .then(function (res) {
        _saveInFlight[postId] = false;
        var btn  = _saveGetBtn(postId);
        var orig = _saveOrigState[postId];

        if (res.status === 429) {
          if (btn && orig) _renderSaveButton(btn, orig.active);
          delete _saveDesired[postId];
          delete _saveOrigState[postId];
          if (window.showToast) showToast('الرجاء التمهّل قليلاً');
          return;
        }

        if (!res.ok || !res.data || res.data.status !== 'success') {
          if (btn && orig) _renderSaveButton(btn, orig.active);
          delete _saveDesired[postId];
          delete _saveOrigState[postId];
          if (window.showToast) showToast('تعذّر حفظ المنشور');
          return;
        }

        var srvActive = !!res.data.saved;
        var desired   = _saveDesired[postId];

        if (desired !== undefined && desired !== srvActive) {
          _saveOrigState[postId] = { active: srvActive };
          _dispatchSave(postId);
          return;
        }

        if (btn) _renderSaveButton(btn, srvActive);
        delete _saveDesired[postId];
        delete _saveOrigState[postId];
      })
      .catch(function () {
        _saveInFlight[postId] = false;
        var btn  = _saveGetBtn(postId);
        var orig = _saveOrigState[postId];
        if (btn && orig) _renderSaveButton(btn, orig.active);
        delete _saveDesired[postId];
        delete _saveOrigState[postId];
        if (window.showToast) showToast('تعذّر حفظ المنشور');
      });
  }

  function _toggleSave(postId) {
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) {
      if (window.showToast) showToast('سجّل دخولك لحفظ المنشور');
      return;
    }
    var btn = _saveGetBtn(postId);
    if (!btn) return;

    var currentActive = btn.classList.contains('save-active');
    var desired       = !currentActive;

    if (!_saveInFlight[postId]) {
      _saveOrigState[postId] = { active: currentActive };
    }

    _saveDesired[postId] = desired;
    _renderSaveButton(btn, desired);

    if (_saveInFlight[postId]) return;
    _dispatchSave(postId);
  }

  // ── Post Appreciation ─────────────────────────────────────────────────────
  var _ICO_HEART_OUTLINE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';
  var _ICO_HEART_FILLED  = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';

  function _renderAppreciationButton(btn, active, count) {
    var ico   = active ? _ICO_HEART_FILLED : _ICO_HEART_OUTLINE;
    var label = count > 0 ? ('أقدّر · ' + count) : 'أقدّر';
    if (active) { btn.classList.add('appr-active');    }
    else        { btn.classList.remove('appr-active'); }
    btn.dataset.apprCount = count;
    btn.innerHTML = ico + label;
  }

  // ── Desired State Queue — one request in flight per post, UI always immediate ──
  var _apprDesired   = {};  // postId -> bool  (last desired state)
  var _apprInFlight  = {};  // postId -> bool  (request running?)
  var _apprOrigState = {};  // postId -> {active, count}  (pre-click state for rollback)

  function _apprGetBtn(postId) {
    var card = document.querySelector('.post-card[data-post-id="' + postId + '"]');
    return card ? card.querySelector('.pc-btn--appr') : null;
  }

  function _dispatchAppreciation(postId) {
    var desired = _apprDesired[postId];
    if (desired === undefined) return;
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) return;

    _apprInFlight[postId] = true;

    fetch('/company/posts/' + postId + '/appreciation', {
      method:  'PUT',
      headers: { 'Authorization': 'Bearer ' + jwt, 'Content-Type': 'application/json' },
      body:    JSON.stringify({ appreciated: desired })
    })
      .then(function (r) {
        return r.json().then(function (d) { return { status: r.status, ok: r.ok, data: d }; });
      })
      .then(function (res) {
        _apprInFlight[postId] = false;
        var btn = _apprGetBtn(postId);
        var orig = _apprOrigState[postId];

        if (res.status === 403 || res.status === 429) {
          // Owner / rate-limit — full rollback, clear queue
          if (btn && orig) _renderAppreciationButton(btn, orig.active, orig.count);
          delete _apprDesired[postId];
          delete _apprOrigState[postId];
          if (window.showToast) {
            showToast(res.status === 403 ? 'لا يمكنك تقدير منشورك' : 'الرجاء التمهّل قليلاً');
          }
          return;
        }

        if (!res.ok || !res.data || res.data.status !== 'success') {
          if (btn && orig) _renderAppreciationButton(btn, orig.active, orig.count);
          delete _apprDesired[postId];
          delete _apprOrigState[postId];
          if (window.showToast) showToast('تعذّر تسجيل التقدير');
          return;
        }

        var srvActive = !!res.data.appreciated;
        var srvCount  = Number(res.data.appreciations_count) || 0;
        var desired   = _apprDesired[postId];

        if (desired !== undefined && desired !== srvActive) {
          // Server response is stale — user clicked again while request was in flight.
          // Keep UI on desired (no flicker); update orig for accurate rollback on failure.
          _apprOrigState[postId] = { active: srvActive, count: srvCount };
          _dispatchAppreciation(postId);
          return;
        }

        // Server matches desired (or no pending desired) — safe to sync UI.
        if (btn) _renderAppreciationButton(btn, srvActive, srvCount);
        delete _apprDesired[postId];
        delete _apprOrigState[postId];
      })
      .catch(function () {
        _apprInFlight[postId] = false;
        var btn = _apprGetBtn(postId);
        var orig = _apprOrigState[postId];
        if (btn && orig) _renderAppreciationButton(btn, orig.active, orig.count);
        delete _apprDesired[postId];
        delete _apprOrigState[postId];
        if (window.showToast) showToast('تعذّر تسجيل التقدير');
      });
  }

  function _toggleAppreciation(postId) {
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) {
      if (window.showToast) showToast('سجّل دخولك لتقدّر هذا المنشور');
      return;
    }

    var btn = _apprGetBtn(postId);
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
    _renderAppreciationButton(btn, desired, nextCount);

    // If already in flight, the response handler will pick up the new desired
    if (_apprInFlight[postId]) return;

    _dispatchAppreciation(postId);
  }

  // ── Post Comments ─────────────────────────────────────────────────────────
  var _ICO_COMMENT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  var _ICO_CLOCK   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';

  var _cmtOpenPanelId  = null; // postId whose panel is currently visible
  var _cmtEditInFlight = {};   // commentId -> bool — prevents concurrent PATCH requests
  var _cmtOpenMenuId   = null; // commentId whose ⋮ menu is currently open
  var _cmtPortalMenu   = null; // single portal <div> on document.body (lazy-created)
  var _cmtPortalFor    = null; // {cmtId, postId} currently shown in portal
  var _cmtReplyTarget  = {};   // postId -> authorName | null (active reply state)
  var _cmtReplyTargetId = {};  // postId -> commentId | null (reply_to_comment_id to send)

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
    if (top  + menuH > window.innerHeight - 8) top  = rect.top - menuH - 4;
    if (left + menuW > window.innerWidth  - 8) left = window.innerWidth - menuW - 8;
    if (left < 8) left = 8;
    if (top  < 8) top  = 8;
    menu.style.top     = top  + 'px';
    menu.style.left    = left + 'px';
    menu.style.display = 'block';
    _cmtPortalFor  = { cmtId: cmtId, postId: postId };
    _cmtOpenMenuId = cmtId;
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

  // XSS-safe body renderer — handles optional @mention highlight.
  // mentionName: exact author name (may include spaces, e.g. "الشركة العربية الاردنية").
  // Tries exact "@authorName" prefix first; falls back to first @word.
  function _renderCommentBody(bodyEl, text, mentionName) {
    bodyEl.textContent = ''; // clears all children safely (no API data in selector)
    if (!text) return;
    // Try exact compound-name match (from reply_to_author_name)
    if (mentionName) {
      var exactMention = '@' + mentionName;
      if (text.indexOf(exactMention) === 0) {
        var rest = text.slice(exactMention.length);
        var mentionSpan = document.createElement('span');
        mentionSpan.className = 'pc-cmt-mention';
        mentionSpan.textContent = exactMention; // XSS-safe: textContent
        bodyEl.appendChild(mentionSpan);
        if (rest) bodyEl.appendChild(document.createTextNode(rest)); // XSS-safe
        return;
      }
    }
    // Fallback: highlight first @word
    var match = text.match(/^(@\S+)([\s\S]*)$/);
    if (match) {
      var mentionSpan = document.createElement('span');
      mentionSpan.className = 'pc-cmt-mention';
      mentionSpan.textContent = match[1]; // XSS-safe: textContent
      bodyEl.appendChild(mentionSpan);
      if (match[2]) {
        bodyEl.appendChild(document.createTextNode(match[2])); // XSS-safe
      }
    } else {
      bodyEl.textContent = text; // XSS-safe
    }
  }

  // Groups replies under their parent — top-level first, then each parent's replies.
  // Orphan replies (parent deleted) are appended at the end.
  function _cmtRenderComments(comments, list) {
    var map      = {};
    var rendered = {};
    comments.forEach(function (c) { map[String(c.id)] = c; });

    function renderOne(c) {
      if (rendered[c.id]) return;
      rendered[c.id] = true;
      list.appendChild(_cmtBuildItem(c));
      // Render direct replies immediately after parent
      comments.forEach(function (r) {
        if (r.reply_to_comment_id != null && String(r.reply_to_comment_id) === String(c.id)) {
          renderOne(r);
        }
      });
    }

    // Top-level comments first
    comments.forEach(function (c) {
      if (c.reply_to_comment_id == null) renderOne(c);
    });
    // Orphans last (parent was soft-deleted and pruned)
    comments.forEach(function (c) {
      if (!rendered[c.id]) renderOne(c);
    });
  }

  // Insert a new reply after the last existing sibling reply under the same parent.
  function _cmtInsertReply(list, newComment) {
    var parentId = String(newComment.reply_to_comment_id);
    var parentEl = list.querySelector('.pc-cmt-item[data-cmt-id="' + parentId + '"]');
    if (!parentEl) {
      list.appendChild(_cmtBuildItem(newComment));
      return;
    }
    // Walk forward until we pass all siblings with the same reply_to-id
    var lastSibling = parentEl;
    var next = parentEl.nextElementSibling;
    while (next && next.dataset && next.dataset.replyToId === parentId) {
      lastSibling = next;
      next = next.nextElementSibling;
    }
    var newEl    = _cmtBuildItem(newComment);
    var afterEl  = lastSibling.nextElementSibling;
    if (afterEl) list.insertBefore(newEl, afterEl);
    else         list.appendChild(newEl);
  }

  function _cmtBuildItem(c) {
    var el = document.createElement('div');
    el.className = 'pc-cmt-item';
    el.dataset.cmtId = String(c.id);
    // Visual indentation: driven by reply_to_comment_id (not body @)
    if (c.reply_to_comment_id != null) {
      el.classList.add('pc-cmt-visual-reply');
      el.dataset.replyToId = String(c.reply_to_comment_id);
      if (c.reply_to_author_name) el.dataset.replyToAuthor = c.reply_to_author_name;
    }

    // Avatar (32px)
    var ava = document.createElement('div');
    ava.className = 'pc-cmt-ava';
    if (c.author_avatar) {
      var img = document.createElement('img');
      img.src = c.author_avatar;
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

    // Row 1: author name
    var nameEl = document.createElement('span');
    nameEl.className = 'pc-cmt-author';
    nameEl.textContent = c.author_name || ''; // XSS-safe
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

    // Body — XSS-safe via _renderCommentBody (@mention highlighted, rest as text nodes)
    var bodyEl = document.createElement('p');
    bodyEl.className = 'pc-cmt-body';
    _renderCommentBody(bodyEl, c.body, c.reply_to_author_name || null);
    content.appendChild(bodyEl);

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

  function _cmtPopulatePanel(postId) {
    var panel = _cmtGetPanel(postId);
    if (!panel || panel._cmtInitialized) return;
    panel._cmtInitialized = true;

    var list = document.createElement('div');
    list.className = 'pc-cmts-list';
    list.addEventListener('scroll', _cmtHidePortalMenu, { passive: true });

    var loading = document.createElement('div');
    loading.className = 'pc-cmts-loading';
    loading.textContent = 'جاري التحميل…';

    var jwt = window._jwt ? window._jwt() : '';
    var inputRow = document.createElement('div');
    inputRow.className = 'pc-cmts-input-row';
    if (jwt) {
      var ta = document.createElement('textarea');
      ta.className   = 'pc-cmts-ta';
      ta.placeholder = 'اكتب تعليقاً…';
      ta.maxLength   = 1000;
      ta.rows        = 1; // auto-grows via _autoResizeTextarea
      ta.addEventListener('input', function () { _autoResizeTextarea(ta); });
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

  function _cmtLoadComments(postId) {
    var panel = _cmtGetPanel(postId);
    if (!panel) return;
    var list    = panel.querySelector('.pc-cmts-list');
    var loading = panel.querySelector('.pc-cmts-loading');
    if (list)    list.innerHTML = '';
    if (loading) loading.style.display = 'block';

    var jwt = window._jwt ? window._jwt() : '';
    var headers = { 'Content-Type': 'application/json' };
    if (jwt) headers['Authorization'] = 'Bearer ' + jwt;

    fetch('/company/posts/' + postId + '/comments', { headers: headers })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (loading) loading.style.display = 'none';
        if (!list) return;
        var comments = (data && data.comments) ? data.comments : [];
        if (!comments.length) {
          var empty = document.createElement('div');
          empty.className = 'pc-cmts-empty';
          empty.textContent = 'لا توجد تعليقات بعد';
          list.appendChild(empty);
          return;
        }
        _cmtRenderComments(comments, list);
      })
      .catch(function () {
        if (loading) loading.style.display = 'none';
        if (list) {
          var err = document.createElement('div');
          err.className = 'pc-cmts-empty';
          err.textContent = 'تعذّر تحميل التعليقات';
          list.appendChild(err);
        }
      });
  }

  function _toggleCommentPanel(postId) {
    var pid = String(postId);

    // Close any other open panel
    if (_cmtOpenPanelId && _cmtOpenPanelId !== pid) {
      var old = _cmtGetPanel(_cmtOpenPanelId);
      if (old) old.style.display = 'none';
      _cmtOpenPanelId = null;
    }

    var panel = _cmtGetPanel(pid);
    if (!panel) return; // comments_enabled=false — no panel in DOM

    if (panel.style.display !== 'none') {
      panel.style.display = 'none';
      _cmtOpenPanelId = null;
      return;
    }

    // First open: build input row + list shell
    _cmtPopulatePanel(pid);
    panel.style.display = '';
    _cmtLoadComments(pid);
    _cmtOpenPanelId = pid;
  }

  function _cmtHandleSend(postId) {
    var panel = _cmtGetPanel(postId);
    if (!panel) return;
    var ta  = panel.querySelector('.pc-cmts-ta');
    if (!ta) return;
    var body = ta.value.trim();
    if (!body) { if (window.showToast) showToast('اكتب تعليقاً أولاً'); return; }
    if (body.length > 1000) { if (window.showToast) showToast('التعليق طويل جداً (1000 حرف كحد أقصى)'); return; }

    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) { if (window.showToast) showToast('سجّل دخولك للتعليق'); return; }

    var sendBtn = panel.querySelector('.pc-cmts-send');
    if (sendBtn) sendBtn.disabled = true;

    var replyToId = _cmtReplyTargetId[String(postId)]
      ? parseInt(_cmtReplyTargetId[String(postId)], 10)
      : null;
    var payload = { body: body };
    if (replyToId) payload.reply_to_comment_id = replyToId;

    fetch('/company/posts/' + postId + '/comments', {
      method:  'POST',
      headers: { 'Authorization': 'Bearer ' + jwt, 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload)
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, status: r.status, data: d }; }); })
      .then(function (res) {
        if (sendBtn) sendBtn.disabled = false;
        if (!res.ok || !res.data || res.data.status !== 'success') {
          var msg = (res.data && res.data.detail) ? res.data.detail : 'تعذّر إرسال التعليق';
          if (window.showToast) showToast(res.status === 429 ? 'الرجاء التمهّل قليلاً' : msg);
          return;
        }
        ta.value = '';
        ta.style.height = ''; // reset auto-resize after send
        _cmtReplyTarget[String(postId)]   = null;
        _cmtReplyTargetId[String(postId)] = null;
        var rStrip = panel.querySelector('.pc-cmt-reply-strip');
        if (rStrip) rStrip.style.display = 'none';
        var list = panel.querySelector('.pc-cmts-list');
        if (list) {
          var empty = list.querySelector('.pc-cmts-empty');
          if (empty) empty.remove();
          var newComment = res.data.comment;
          if (newComment.reply_to_comment_id != null) {
            _cmtInsertReply(list, newComment); // insert after parent's last sibling reply
          } else {
            list.appendChild(_cmtBuildItem(newComment));
          }
          list.scrollTop = list.scrollHeight;
        }
        _cmtUpdateCount(postId, 1);
      })
      .catch(function () {
        if (sendBtn) sendBtn.disabled = false;
        if (window.showToast) showToast('تعذّر إرسال التعليق');
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

    var originalText    = bodyEl.textContent; // textContent returns full text even with child spans
    var wasVisualReply  = item.classList.contains('pc-cmt-visual-reply');
    var replyToAuthor   = item.dataset.replyToAuthor || null;

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

    // 2. Insert editWrap into DOM FIRST, then hide bodyEl — never a blank gap
    var acts = content.querySelector('.pc-cmt-acts'); // correct parent: content, not item
    if (acts) content.insertBefore(editWrap, acts);
    else content.appendChild(editWrap);
    bodyEl.style.display = 'none';

    // Size to existing text now that the element is in the DOM (scrollHeight is accurate)
    _autoResizeTextarea(editTa);

    // Focus + move cursor to end
    editTa.focus();
    editTa.setSelectionRange(editTa.value.length, editTa.value.length);

    cancelBtn.addEventListener('click', function () {
      bodyEl.style.display = '';
      editWrap.remove();
    });

    saveBtn.addEventListener('click', function () {
      if (_cmtEditInFlight[cmtId]) return; // already saving
      var newBody = editTa.value.trim();
      if (!newBody) { if (window.showToast) showToast('التعليق لا يمكن أن يكون فارغاً'); return; }
      if (newBody.length > 1000) { if (window.showToast) showToast('التعليق طويل جداً (1000 حرف كحد أقصى)'); return; }
      var jwt = window._jwt ? window._jwt() : '';
      if (!jwt) return;

      // 3. Optimistic UI — update text immediately, remove edit UI
      _cmtEditInFlight[cmtId] = true;
      saveBtn.disabled = true;
      _renderCommentBody(bodyEl, newBody, replyToAuthor); // XSS-safe: no innerHTML for API data
      // visual-reply class is driven by reply_to_comment_id (immutable per comment) — no change
      bodyEl.style.display = '';
      editWrap.remove();

      fetch('/company/posts/comments/' + cmtId, {
        method:  'PATCH',
        headers: { 'Authorization': 'Bearer ' + jwt, 'Content-Type': 'application/json' },
        body:    JSON.stringify({ body: newBody })
      })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, status: r.status, data: d }; }); })
        .then(function (res) {
          _cmtEditInFlight[cmtId] = false;
          if (!res.ok || !res.data || res.data.status !== 'success') {
            // Rollback to original text + restore visual-reply state
            _renderCommentBody(bodyEl, originalText, replyToAuthor); // XSS-safe
            if (wasVisualReply) item.classList.add('pc-cmt-visual-reply');
            else item.classList.remove('pc-cmt-visual-reply');
            var msg = (res.data && res.data.detail) ? res.data.detail : 'تعذّر تعديل التعليق';
            if (window.showToast) showToast(res.status === 429 ? 'الرجاء التمهّل قليلاً' : msg);
            return;
          }
          // Confirm with server body + mark as edited (visual-reply class unchanged — driven by reply_to_comment_id)
          var confirmedBody = res.data.comment.body;
          _renderCommentBody(bodyEl, confirmedBody, replyToAuthor); // XSS-safe
          var metaRow = item.querySelector('.pc-cmt-meta-row');
          if (metaRow && !metaRow.querySelector('.pc-cmt-edited')) {
            var editedEl = document.createElement('span');
            editedEl.className = 'pc-cmt-edited';
            editedEl.textContent = '· تم التعديل';
            metaRow.appendChild(editedEl);
          }
        })
        .catch(function () {
          _cmtEditInFlight[cmtId] = false;
          _renderCommentBody(bodyEl, originalText, replyToAuthor); // XSS-safe rollback
          if (wasVisualReply) item.classList.add('pc-cmt-visual-reply');
          else item.classList.remove('pc-cmt-visual-reply');
          if (window.showToast) showToast('تعذّر تعديل التعليق');
        });
    });
  }

  function _cmtHandleDelete(cmtId, postId) {
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) return;

    fetch('/company/posts/comments/' + cmtId, {
      method:  'DELETE',
      headers: { 'Authorization': 'Bearer ' + jwt }
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, status: r.status, data: d }; }); })
      .then(function (res) {
        if (!res.ok || !res.data || res.data.status !== 'success') {
          var msg = (res.data && res.data.detail) ? res.data.detail : 'تعذّر حذف التعليق';
          if (window.showToast) showToast(msg);
          return;
        }
        var panel = _cmtGetPanel(postId);
        if (panel) {
          var item = panel.querySelector('.pc-cmt-item[data-cmt-id="' + cmtId + '"]');
          if (item) {
            item.remove();
            // Show empty state if no comments left
            var list = panel.querySelector('.pc-cmts-list');
            if (list && !list.querySelector('.pc-cmt-item')) {
              var empty = document.createElement('div');
              empty.className = 'pc-cmts-empty';
              empty.textContent = 'لا توجد تعليقات بعد';
              list.appendChild(empty);
            }
          }
        }
        _cmtUpdateCount(postId, -1);
      })
      .catch(function () {
        if (window.showToast) showToast('تعذّر حذف التعليق');
      });
  }

  window.openPostModal        = openPostModal;
  window._closePostOverlay    = _closePostOverlay;
  window.createPost           = createPost;
  window.updatePost           = updatePost;
  window.deletePost           = deletePost;
  window.initPostViewTracking = initPostViewTracking;

  document.addEventListener('DOMContentLoaded', function () {
    _bindPostEvents();
    _bindTagPickerEvents();
    _bindColorPickerEvents();

    // Close 3-dot menus (post and portal comment menu) when clicking outside
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.pc-dots')) {
        document.querySelectorAll('.pc-dots-menu.open').forEach(function (m) {
          m.classList.remove('open');
        });
      }
      if (_cmtPortalMenu && _cmtPortalMenu.style.display !== 'none') {
        if (!e.target.closest('#pc-cmt-portal-menu') && !e.target.closest('.pc-cmt-menu-btn')) {
          _cmtHidePortalMenu();
        }
      }
    });

    // Close portal menu on page scroll
    document.addEventListener('scroll', _cmtHidePortalMenu, { passive: true, capture: true });

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

    // Event delegation for post card buttons
    var postsList = document.getElementById('postsList');
    if (postsList) {
      postsList.addEventListener('click', function (e) {
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
        var lessBtn = e.target.closest('.post-less-btn');
        if (lessBtn) {
          var wrap = lessBtn.closest('.post-body-wrap');
          if (!wrap) return;
          var textSpan = wrap.querySelector('.post-body-text');
          var moreInline = wrap.querySelector('.post-more-inline');
          if (textSpan && wrap._pbShort) textSpan.textContent = wrap._pbShort;
          lessBtn.style.display = 'none';
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
          var postData = window._getPostById ? window._getPostById(epid) : null;
          if (postData) openPostModal(postData);
          return;
        }
        // 3-dot delete
        var delDots = e.target.closest('.pc-dots-delete[data-post-id]');
        if (delDots) {
          var pid = parseInt(delDots.getAttribute('data-post-id'), 10);
          var dm  = document.getElementById('pc-dm-' + pid);
          if (dm) dm.classList.remove('open');
          deletePost(pid);
          return;
        }
        // Share
        var shareBtn = e.target.closest('.pc-btn--share[data-post-id]');
        if (shareBtn) { _sharePost(shareBtn.getAttribute('data-post-id')); return; }
        // Appreciate
        var apprBtn = e.target.closest('.pc-btn--appr[data-post-id]');
        if (apprBtn) { _toggleAppreciation(apprBtn.getAttribute('data-post-id')); return; }
        // Comment panel toggle
        var cmtBtn = e.target.closest('.pc-btn--cmt[data-post-id]');
        if (cmtBtn) { _toggleCommentPanel(cmtBtn.getAttribute('data-post-id')); return; }
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
        // Save
        var saveBtn = e.target.closest('.pc-btn--save[data-post-id]');
        if (saveBtn) { _toggleSave(saveBtn.getAttribute('data-post-id')); return; }
      });
    }
  });
}());
