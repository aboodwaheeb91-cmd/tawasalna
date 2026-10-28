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
    chips.replaceChildren();
    _selectedTags.forEach(function (t, i) {
      var span = document.createElement('span');
      span.className = 'ptc-chip';
      span.appendChild(document.createTextNode(t));
      var x = document.createElement('button');
      x.type = 'button';
      x.className = 'ptc-chip-x';
      x.dataset.idx = String(i);
      x.setAttribute('aria-label', 'إزالة');
      x.textContent = '✕';
      span.appendChild(x);
      chips.appendChild(span);
    });
    if (count) count.textContent = _selectedTags.length + (twLimit('post_tags_max') ? '/' + twLimit('post_tags_max') : '');
  }

  // Tag count + body length = the server's limits (twLimit — tw_limits.py, task 5.0h)
  function _addTag(tag) {
    var maxTags = twLimit('post_tags_max');
    if (maxTags && _selectedTags.length >= maxTags) {
      if (window.showToast) showToast(twT('limits.post_tags_max', { max: maxTags }), 'error'); return;
    }
    if (!window.TW || !Array.isArray(TW.POST_TAGS) || TW.POST_TAGS.indexOf(tag) === -1) {
      if (window.showToast) showToast(twT('limits.post_tags_invalid'), 'error'); return;
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
          if (window.showToast) showToast('اختر الوسم من القائمة المقترحة', 'error');
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
    if (titleEl)  titleEl.textContent  = twT('company.new_post');
    if (lblEl)    lblEl.textContent    = twT('company.post_form.publish');
    if (noComEl)  noComEl.checked      = false;
    if (bodyEl)   bodyEl.value         = '';
    if (bodyEl && twLimit('post_body_max')) bodyEl.maxLength = twLimit('post_body_max');
    _resetTagPicker();
    _resetColorPicker();
  }

  function _setModalEditMode(post) {
    var titleEl  = document.getElementById('postModalTitle');
    var lblEl    = document.getElementById('createPostBtnLabel');
    var noComEl  = document.getElementById('p-no-comments');
    var bodyEl   = document.getElementById('p-body');
    if (titleEl)  titleEl.textContent  = twT('company.post_form.edit_title');
    if (lblEl)    lblEl.textContent    = twT('company.post_form.save_edit');
    if (bodyEl)   bodyEl.value         = post.body || '';
    if (bodyEl && twLimit('post_body_max')) bodyEl.maxLength = twLimit('post_body_max');
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
    if (!TwCompanyPage.signedIn()) { location.href = twLoginHref(location.pathname + location.search); return; }
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
    twApi('/company/posts', {
      method: 'POST',
      body:   { body: body, tags: tags.length ? tags : null, theme_color: color, comments_enabled: commentsEnabled },
    }).then(function (res) {
      isPostCreating = false;
      if (!res.ok) {
        if (window.showToast) showToast(twApiMessage(res, 'تعذّر نشر المنشور'), 'error');
        return;
      }
      _closePostOverlay();
      if (window.loadPosts) loadPosts(true);
      if (window.showToast) showToast('تم نشر المنشور ✓', 'success');
    });
  }

  function updatePost() {
    if (!TwCompanyPage.signedIn()) { location.href = twLoginHref(location.pathname + location.search); return; }
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
    twApi('/company/posts/' + encodeURIComponent(_editingPostId), {
      method: 'PATCH',
      body:   { body: body, tags: tags.length ? tags : null, theme_color: color, comments_enabled: commentsEnabled },
    }).then(function (res) {
      isPostCreating = false;
      if (!res.ok) {
        if (window.showToast) showToast(twApiMessage(res, 'تعذّر تعديل المنشور'), 'error');
        return;
      }
      _closePostOverlay();
      if (window.loadPosts) loadPosts(true);
      if (window.showToast) showToast('تم تعديل المنشور ✓', 'success');
    });
  }

  function deletePost(postId) {
    if (!TwCompanyPage.signedIn()) { location.href = twLoginHref(location.pathname + location.search); return; }
    if (!window.companyState || !companyState.permissions.can_edit) {
      if (window.showToast) showToast('غير مصرح', 'error'); return;
    }
    if (isPostDeleting) return;
    if (typeof window.twConfirm !== 'function') {   // fail closed — never delete unconfirmed (DS-OVL)
      console.error('[Company] deletePost needs tw-overlay.js (DS-OVL)');
      return;
    }

    twConfirm({
      title:       twT('company.post.delete_title'),
      message:     twT('company.post.delete_msg'),
      confirmText: twT('company.post.delete_confirm'),
      danger:      true,
    }).then(function (ok) {
      if (!ok || isPostDeleting) return;
      isPostDeleting = true;
      twApi('/company/posts/' + encodeURIComponent(postId), { method: 'DELETE' }).then(function (res) {
        isPostDeleting = false;
        if (!res.ok) {
          if (window.showToast) showToast(twApiMessage(res, twT('company.post.delete_failed')), 'error');
          return;
        }
        if (window.loadPosts) loadPosts(true);
        if (window.showToast) showToast(twT('company.post.deleted'), 'success');
      });
    });
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
    // Wrapped: passing _closePostOverlay directly made the click Event its `fromPopstate`
    // argument (truthy) → the modal's history entry was never popped.
    if (postCancelBtn) postCancelBtn.addEventListener('click', function () { _closePostOverlay(); });
  }

  // ── Post Comments = TwPostComments (task 8.6b-1 — static/shared/tw-post-comments.js) ──
  var _comments = TwPostComments.create({
    signedIn:  function () { return TwCompanyPage.signedIn(); },   // TwAuthSync snapshot (company.state.js)
    postOwner: function () { return (window.companyState && companyState.profile) || null; },   // mention suggestions
  });

  // ── Post card behaviour = TwPostCard (task U.2b) — only the page-specific parts live here ──
  function _postPath(postId, action) {
    return '/company/posts/' + encodeURIComponent(postId) + '/' + action;
  }
  var _postCard = TwPostCard.create({
    signedIn: function () { return TwCompanyPage.signedIn(); },   // TwAuthSync snapshot (company.state.js)
    paths: {
      appreciation: function (id) { return _postPath(id, 'appreciation'); },
      save:         function (id) { return _postPath(id, 'save'); },
      view:         function (id) { return _postPath(id, 'view'); },
    },
    visitorKeyName: 'cp_vk',
    shareInfo: function () {
      var coName = (window.companyState && companyState.profile && companyState.profile.full_name)
        ? companyState.profile.full_name : 'شركة';
      var twId = (window.companyState && companyState.profile && companyState.profile.tw_id)
        ? companyState.profile.tw_id : null;
      var url = twId
        ? (location.origin || '') + '/u/' + encodeURIComponent(twId)
        : location.href;
      return { name: coName, url: url };
    },
    onEdit: function (postId) {
      var postData = window._getPostById ? window._getPostById(postId) : null;
      if (postData) openPostModal(postData);
    },
    onDelete: deletePost,
    comments: { build: _comments.build, load: _comments.load },
  });

  window.openPostModal        = openPostModal;
  window._closePostOverlay    = _closePostOverlay;
  window.createPost           = createPost;
  window.updatePost           = updatePost;
  window.deletePost           = deletePost;
  window.initPostViewTracking = function (container) { _postCard.trackViews(container); };

  document.addEventListener('DOMContentLoaded', function () {
    _bindPostEvents();
    _bindTagPickerEvents();
    _bindColorPickerEvents();

    // Card buttons = TwPostCard · comment items = TwPostComments (per panel)
    _postCard.bind(document.getElementById('postsList'));
  });
}());
