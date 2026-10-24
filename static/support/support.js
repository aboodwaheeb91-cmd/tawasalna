// static/support/support.js — /support, public (task 7.1 · 7.2a واجهة · docs/rules/support.md → الواجهة)
//   - everyone: the FAQ from GET /support/meta (category order = the server's) · texts twT('support.faq.{cat}.{id}.q|a')
//     · local search over question + answer · «لم تُحلّ مشكلتي» under each answer → the ticket form with the
//     category + faq_id filled
//   - account (TwAuthSync snapshot): any category → POST /support/tickets · my tickets + status + replies + «تم الحل»
//   - guest: «الدخول والحساب» only, the OTP path → «أرسلنا رابط المتابعة إلى بريدك» + the H number (the link
//     is never shown) · «فقدت رابط المتابعة؟» → POST /support/track/resend · other categories → login link
//   - every request through twApi · every text through textContent (never innerHTML) · dates twFormatDateTime
(function () {
  'use strict';
  var F = window.TwSupportForm, el = F.el;
  var snap = window.TwAuthSync ? TwAuthSync.getSessionSnapshot() : null;
  var signedIn = !!(snap && snap.isAuthenticated);
  var faqBox = document.getElementById('spFaq');
  var search = document.getElementById('spSearch');
  var noHits = document.getElementById('spNoHits');
  var formSec = document.getElementById('spFormSec');
  var newBox = document.getElementById('spNew');
  var resendSec = document.getElementById('spResendSec');
  var mineSec = document.getElementById('spMineSec');
  var listBox = document.getElementById('spList');
  var home = document.getElementById('spHome');
  var thread = document.getElementById('spThread');
  var meta = null;
  var items = [];   // [{cat, id, row, text}]

  document.title = twT('page.title', { page: twT('support.title') });
  twTApply(document.body);
  if (window.twIcon && twIcon.hydrate) twIcon.hydrate(document.body);
  mineSec.hidden = !signedIn;
  resendSec.hidden = signedIn;

  // ── FAQ ──
  function norm(s) { return String(s || '').toLowerCase().replace(/\s+/g, ' ').trim(); }

  function renderFaq() {
    faqBox.textContent = '';
    items = [];
    meta.categories.forEach(function (cat) {
      var ids = (meta.faq || {})[cat] || [];
      if (!ids.length) return;
      var sec = el('section', 'sp-faq-cat');
      sec.appendChild(el('h3', 'sp-faq-cat-title', twT('support.category.' + cat)));
      ids.forEach(function (id) {
        var q = twT('support.faq.' + cat + '.' + id + '.q'), a = twT('support.faq.' + cat + '.' + id + '.a');
        var row = el('details', 'sp-faq');
        row.setAttribute('data-faq', cat + '.' + id);
        row.appendChild(el('summary', 'sp-faq-q', q));
        var body = el('div', 'sp-faq-a');
        body.appendChild(el('p', null, a));
        var canOpen = signedIn || cat === meta.guest_category;
        if (canOpen) {
          var b = F.button('support.faq.not_solved', 'tw-btn tw-btn-ghost');
          b.setAttribute('data-faq-open', cat + '.' + id);
          b.addEventListener('click', function () { openForm(cat, id); });
          body.appendChild(b);
        } else {
          var link = el('a', 'sp-link', twT('support.faq.login_to_open'));
          link.href = twLoginHref('/support');
          body.appendChild(link);
        }
        row.appendChild(body);
        sec.appendChild(row);
        items.push({ cat: cat, id: id, row: row, sec: sec, text: norm(q + ' ' + a) });
      });
      faqBox.appendChild(sec);
    });
    faqBox.removeAttribute('aria-busy');
  }

  function filterFaq() {
    var q = norm(search.value), shown = {}, any = false;
    items.forEach(function (it) {
      var hit = !q || it.text.indexOf(q) !== -1;
      it.row.hidden = !hit;
      if (hit) { shown[it.cat] = true; any = true; }
    });
    items.forEach(function (it) { it.sec.hidden = !shown[it.cat]; });
    noHits.hidden = any;
  }

  // ── ticket form ──
  function openForm(cat, faqId) {
    var form = F.ticketForm({ meta: meta, guest: !signedIn, category: cat, faqId: faqId, onDone: created });
    newBox.textContent = '';
    newBox.appendChild(form.el);
    formSec.hidden = false;
    if (formSec.scrollIntoView) formSec.scrollIntoView({ block: 'start' });
  }

  function created(publicId) {
    if (!signedIn) return;   // the guest form shows its own «أرسلنا رابط المتابعة» + H number
    showToast(twT('support.done.created'), 'success');
    openForm('', '');
    loadList().then(function () { if (publicId) openTicket(publicId); });
  }

  // ── my tickets (account) ──
  function renderList(list) {
    listBox.textContent = '';
    listBox.removeAttribute('aria-busy');
    if (!list.length) { listBox.appendChild(el('p', 'sp-empty', twT('support.mine.empty'))); return; }
    var box = el('div', 'sp-list');
    list.forEach(function (t) {
      var row = el('button', 'sp-row');
      row.type = 'button';
      var body = el('span', 'sp-row-body');
      body.appendChild(el('span', 'sp-row-subject', t.subject));
      body.appendChild(el('span', 'sp-row-meta', t.public_id + ' · ' + twT('support.category.' + t.category) + ' · '
        + twFormatDateTime(t.last_message_at)));
      row.appendChild(body);
      row.appendChild(el('span', 'sp-pill is-' + t.status, twT('support.status_user.' + t.status)));
      row.addEventListener('click', function () { openTicket(t.public_id); });
      box.appendChild(row);
    });
    listBox.appendChild(box);
  }

  function loadList() {
    return twApi('/support/tickets').then(function (res) {
      if (!res.ok) {
        listBox.textContent = '';
        listBox.appendChild(el('p', 'sp-msg is-error', twApiMessage(res, twT('common.load_error'))));
        return;
      }
      renderList((res.data && res.data.items) || []);
    });
  }

  function showHome() {
    thread.hidden = true;
    thread.textContent = '';
    home.hidden = false;
  }

  function openTicket(id) {
    var path = '/support/tickets/' + encodeURIComponent(id);
    twApi(path).then(function (res) {
      if (!res.ok) { showToast(twApiMessage(res, twT('common.load_error')), 'error'); return; }
      home.hidden = true;
      thread.hidden = false;
      thread.textContent = '';
      var back = F.button('support.thread.back', 'tw-btn tw-btn-ghost sp-back');
      back.addEventListener('click', function () { showHome(); loadList(); });
      thread.appendChild(back);
      thread.appendChild(F.thread(res.data, {
        reply: function (body) { return twApi(path + '/messages', { method: 'POST', body: { body: body } }); },
        resolve: function () { return twApi(path + '/close', { method: 'POST' }); },
        reload: function () { openTicket(id); },
      }));
      if (thread.scrollIntoView) thread.scrollIntoView({ block: 'start' });
    });
  }

  // ── start ──
  search.addEventListener('input', filterFaq);
  document.getElementById('spResendBtn').addEventListener('click', function () {
    var box = document.getElementById('spResend');
    if (!box.children.length) box.appendChild(F.resendForm());
    box.hidden = !box.hidden;
  });

  twApi('/support/meta', { auth: false }).then(function (res) {
    if (!res.ok || !res.data) {
      faqBox.textContent = '';
      faqBox.appendChild(el('p', 'sp-msg is-error', twApiMessage(res, twT('common.load_error'))));
      return;
    }
    meta = res.data;
    renderFaq();
    openForm(signedIn ? '' : meta.guest_category, '');
  });
  if (signedIn) {
    loadList();
    // /support?ticket=H… — the bell + support_reply email link (7.2b); the server answers 404 for another's
    var deep = /[?&]ticket=(H[A-Z0-9]{1,40})(?:&|$)/.exec(location.search || '');
    if (deep) openTicket(deep[1]);
  }
})();
