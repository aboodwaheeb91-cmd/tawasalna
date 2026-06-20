// company.posts.js — create post, delete post, open post modal
// Load order: 6th (after jobs)
(function () {
  'use strict';

  var isPostCreating = false;
  var isPostDeleting = false;

  function openPostModal() {
    if (!window.companyState || !companyState.permissions.can_edit) return;
    var ov = document.getElementById('postOverlay');
    if (ov) ov.classList.add('show');
    if (window.history) history.pushState({ modal: 'post' }, '', location.href);
  }

  function createPost() {
    if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
    if (!window.companyState || !companyState.permissions.can_edit) {
      if (window.showToast) showToast('غير مصرح', 'error'); return;
    }
    if (isPostCreating) return;

    var bodyEl = document.getElementById('p-body');
    var tagsEl = document.getElementById('p-tags');
    var body   = (bodyEl ? bodyEl.value : '').trim();
    if (!body) { if (window.showToast) showToast('اكتب محتوى المنشور', 'error'); return; }

    var tags = (tagsEl ? tagsEl.value : '')
      .split(',').map(function (t) { return t.trim(); }).filter(Boolean);

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
      var ov = document.getElementById('postOverlay');
      if (ov) ov.classList.remove('show');
      if (bodyEl) bodyEl.value = '';
      if (tagsEl) tagsEl.value = '';
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

  // ── Event bindings (commit #2) ──────────────────────────────────
  function _bindPostEvents() {
    var q = function (id) { return document.getElementById(id); };

    var postModalBtn = q('postModalBtn'); if (postModalBtn) postModalBtn.addEventListener('click', openPostModal);

    var postOverlay = q('postOverlay');
    if (postOverlay) postOverlay.addEventListener('click', function (e) {
      if (e.target === this) this.classList.remove('show');
    });

    var createPostBtn = q('createPostBtn'); if (createPostBtn) createPostBtn.addEventListener('click', createPost);

    var postCancelBtn = q('postCancelBtn');
    if (postCancelBtn) postCancelBtn.addEventListener('click', function () {
      var ov = q('postOverlay'); if (ov) ov.classList.remove('show');
    });
  }

  window.openPostModal = openPostModal;
  window.createPost    = createPost;
  window.deletePost    = deletePost;

  document.addEventListener('DOMContentLoaded', function () {
    _bindPostEvents();
    // Event delegation for dynamically-rendered delete buttons
    var postsList = document.getElementById('postsList');
    if (postsList) {
      postsList.addEventListener('click', function (e) {
        var btn = e.target.closest('.post-del[data-post-id]');
        if (btn) deletePost(parseInt(btn.getAttribute('data-post-id'), 10));
      });
    }
  });
}());
