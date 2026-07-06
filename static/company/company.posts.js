// company.posts.js — create post, delete post, open post modal, tag picker
// Load order: 6th (after jobs)
(function () {
  'use strict';

  var isPostCreating       = false;
  var isPostDeleting       = false;
  var _postHistoryPushed   = false;
  var _selectedTags        = [];       // tag picker state

  // ── Tag Picker ────────────────────────────────────────────────
  function _searchTags(q) {
    if (!window.TW || !Array.isArray(TW.POST_TAGS)) return [];
    return TW.POST_TAGS.filter(function (t) {
      return t.indexOf(q) !== -1;
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

  function _bindTagPickerEvents() {
    var searchEl = document.getElementById('p-tags-search');
    var chipsEl  = document.getElementById('p-tags-chips');
    var ddEl     = document.getElementById('p-tags-dropdown');

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

    // Close dropdown on outside click
    document.addEventListener('click', function (e) {
      if (!e.target.closest('#p-tags-wrap')) _closeTagDropdown();
    });
  }

  // ── Modal ─────────────────────────────────────────────────────
  function openPostModal() {
    if (!window.companyState || !companyState.permissions.can_edit) return;
    var ov = document.getElementById('postOverlay');
    if (ov) ov.classList.add('show');
    _resetTagPicker();
    if (window.history && !_postHistoryPushed) {
      history.pushState({ modal: 'post' }, '', location.href);
      _postHistoryPushed = true;
    }
  }

  // fromPopstate=true means popstate already moved back; skip history.back().
  function _closePostOverlay(fromPopstate) {
    var ov = document.getElementById('postOverlay');
    if (ov) ov.classList.remove('show');
    if (_postHistoryPushed && !fromPopstate) {
      _postHistoryPushed = false;
      if (window.history) history.back();
    } else {
      _postHistoryPushed = false;
    }
  }

  function createPost() {
    if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
    if (!window.companyState || !companyState.permissions.can_edit) {
      if (window.showToast) showToast('غير مصرح', 'error'); return;
    }
    if (isPostCreating) return;

    var bodyEl = document.getElementById('p-body');
    var body   = (bodyEl ? bodyEl.value : '').trim();
    if (!body) { if (window.showToast) showToast('اكتب محتوى المنشور', 'error'); return; }

    var tags = _selectedTags.slice();

    isPostCreating = true;
    fetch('/company/posts', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
      body:    JSON.stringify({ body: body, tags: tags.length ? tags : null }),
    })
    .then(function (r) {
      if (!r.ok) throw new Error('create failed: ' + r.status);
      return r.json();
    })
    .then(function () {
      _closePostOverlay();
      if (bodyEl) bodyEl.value = '';
      _resetTagPicker();
      if (window.loadPosts) loadPosts(true);
      if (window.showToast) showToast('تم نشر المنشور ✓');
    })
    .catch(function () {
      if (window.showToast) showToast('تعذّر نشر المنشور', 'error');
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

  window.openPostModal      = openPostModal;
  window._closePostOverlay  = _closePostOverlay;
  window.createPost         = createPost;
  window.deletePost         = deletePost;

  document.addEventListener('DOMContentLoaded', function () {
    _bindPostEvents();
    _bindTagPickerEvents();

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
        // 3-dot toggle
        var dotsBtn = e.target.closest('.pc-dots-btn[data-post-id]');
        if (dotsBtn) {
          e.stopPropagation();
          var menu = document.getElementById('pc-dm-' + dotsBtn.getAttribute('data-post-id'));
          if (menu) menu.classList.toggle('open');
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
        // Like
        var likeBtn = e.target.closest('.pc-btn--like[data-post-id]');
        if (likeBtn) { if (window.showToast) showToast('ميزة الإعجاب بالمنشورات ستتوفر قريباً'); return; }
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
