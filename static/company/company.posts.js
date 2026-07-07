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

    var postModalBtn = q('postModalBtn'); if (postModalBtn) postModalBtn.addEventListener('click', openPostModal);

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

  // ── Post Appreciation ─────────────────────────────────────────────────────
  function _toggleAppreciation(postId) {
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) {
      if (window.showToast) showToast('سجّل دخولك لتقدّر هذا المنشور');
      return;
    }

    fetch('/company/posts/' + postId + '/appreciate', {
      method:  'POST',
      headers: { 'Authorization': 'Bearer ' + jwt },
    })
      .then(function (r) {
        if (r.status === 403) {
          if (window.showToast) showToast('لا يمكنك تقدير منشورك');
          throw new Error('owner');
        }
        if (!r.ok) throw new Error('http ' + r.status);
        return r.json();
      })
      .then(function (d) {
        if (!d || d.status !== 'success') return;
        var card = document.querySelector('.post-card[data-post-id="' + postId + '"]');
        if (!card) return;
        var btn = card.querySelector('.pc-btn--appr');
        if (!btn) return;

        var count = Number(d.appreciations_count) || 0;
        var active = !!d.appreciated;

        // Swap heart icon
        var icoOutline = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';
        var icoFilled  = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';
        var label = active ? ('أقدّر · ' + count) : 'أقدّر';

        if (active) {
          btn.classList.add('appr-active');
          btn.innerHTML = icoFilled + label;
        } else {
          btn.classList.remove('appr-active');
          btn.innerHTML = icoOutline + label;
        }
        btn.dataset.apprCount = count;
      })
      .catch(function (err) {
        if (err && err.message === 'owner') return;
        if (window.showToast) showToast('تعذّر تسجيل التقدير');
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

    // Close 3-dot menus when clicking outside
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.pc-dots')) {
        document.querySelectorAll('.pc-dots-menu.open').forEach(function (m) {
          m.classList.remove('open');
        });
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
        // Comment
        var cmtBtn = e.target.closest('.pc-btn--cmt[data-post-id]');
        if (cmtBtn) { if (window.showToast) showToast('ميزة التعليقات ستتوفر قريباً'); return; }
        // Save
        var saveBtn = e.target.closest('.pc-btn--save[data-post-id]');
        if (saveBtn) { if (window.showToast) showToast('ميزة حفظ المنشورات ستتوفر قريباً'); return; }
      });
    }
  });
}());
