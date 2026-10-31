// profile-v2.certs.js — Certificate PDFs of courses / education (task 8.7 · docs/rules/certificates.md)
// Depends on: tw_shared.js (twApi · twApiMessage · twT · twTApply · twLimit · twSafeLinkUrl · twEscHtml ·
// twEscAttr · showToast), the DS-ICON registry (twIcon · twIconEl — loaded by the page), DS-OVL (twModal · twConfirm).
//
// The server decides everything: has_certificate / can_view_certificate come in the profile reply (computed per
// viewer by cert_access.can_view); a view link is asked for at click time (GET /certificates/{kind}/{id}/view) and
// shown in a sandboxed iframe + «فتح بتبويب جديد». Hiding the button is UX only (F21).
// ❌ a file path / name from here · ❌ caching a signed link · ❌ a public certificate URL.
(function(){
  'use strict';

  var KINDS = { course: 'courses', education: 'education' };   // URL kind → profile list key

  function maxLabel(){ return Math.floor(Number(twLimit('cert_max_bytes')) / 1048576) + ' MB'; }

  // ── API (twApi only) ──
  function apiUpload(kind, id, dataUrl){
    return twApi('/' + kind + '/' + Number(id) + '/certificate', { method: 'POST', body: { data_url: dataUrl } });
  }
  function apiRemove(kind, id){
    return twApi('/' + kind + '/' + Number(id) + '/certificate', { method: 'DELETE' });
  }
  function apiView(kind, id){
    return twApi('/certificates/' + kind + '/' + Number(id) + '/view');
  }

  function readDataUrl(file){
    return new Promise(function(resolve, reject){
      var r = new FileReader();
      r.onload = function(){ resolve(String(r.result || '')); };
      r.onerror = function(){ reject(new Error('read_failed')); };
      r.readAsDataURL(file);
    });
  }

  // Profile cache → the entry of (kind, id) gets the server's new flags, then the section re-renders.
  function patchCache(kind, id, data){
    var cache = window._scProfile, key = KINDS[kind];
    if(cache && Array.isArray(cache[key])){
      cache[key] = cache[key].map(function(e){
        if(e.id !== id) return e;
        var n = Object.assign({}, e, { has_certificate: !!data.has_certificate,
                                       can_view_certificate: !!data.can_view_certificate });
        if(kind === 'course' && data.has_certificate) n.certificate_url = null;   // the PDF replaced the old link
        return n;
      });
    }
    var rr = kind === 'course' ? window._reRenderCourses : window._reRenderEdu;
    if(typeof rr === 'function') rr();
  }

  // ── Field inside a section modal (courseCert* / eduCert*) ──
  function field(prefix, kind){
    function el(s){ return document.getElementById(prefix + 'Cert' + s); }
    var input = el('File'), pick = el('Pick'), del = el('Del'), status = el('Status'),
        err = el('Err'), hint = el('Hint'), wrap = el('Wrap');
    if(!input || !pick || !wrap) return null;
    var st = { id: null, has: false, pending: null, busy: false };
    if(hint) hint.textContent = twT('cert.field.hint', { max: maxLabel() });

    function setErr(msg){ if(err) err.textContent = msg || ''; }
    function paint(){
      var label = st.pending ? st.pending.name
                : (st.has ? twT('cert.field.has_file') : twT('cert.field.no_file'));
      if(st.busy) label = twT('cert.uploading');
      if(status) status.textContent = label;
      pick.disabled = st.busy;
      var span = pick.querySelector('[data-cert-pick-label]');
      if(span) span.textContent = twT(st.has || st.pending ? 'cert.replace' : 'cert.upload');
      if(del){ del.hidden = !(st.has && st.id); del.disabled = st.busy; }
    }

    function send(id, file){
      st.busy = true; setErr(''); paint();
      return readDataUrl(file).then(function(du){ return apiUpload(kind, id, du); })
        .then(function(res){
          if(!res.ok){
            if(res.status !== 401) setErr(twApiMessage(res, twT('cert.err.upload_failed')));
            return false;
          }
          st.has = true; st.pending = null;
          patchCache(kind, id, res.data || {});
          showToast(twT('cert.uploaded'), 'success');
          return true;
        }, function(){ setErr(twT('cert.err.upload_failed')); return false; })
        .then(function(ok){ st.busy = false; input.value = ''; paint(); return ok; });
    }

    pick.addEventListener('click', function(){ if(!st.busy) input.click(); });
    input.addEventListener('change', function(){
      var file = input.files && input.files[0];
      setErr('');
      if(!file) return;
      // UX pre-check only — the server checks the bytes (magic · size · content) and decides.
      if(file.size > Number(twLimit('cert_max_bytes'))){
        setErr(twT('cert.err.too_large', { max: maxLabel() })); input.value = ''; return;
      }
      if(st.id){ send(st.id, file); return; }
      st.pending = file; paint();   // new row: sent right after the row is saved (flush)
    });
    if(del) del.addEventListener('click', function(){
      if(!st.id || st.busy) return;
      twConfirm({ title: twT('cert.remove_confirm.title'), message: twT('cert.remove_confirm.message'),
                  confirmText: twT('cert.remove'), danger: true }).then(function(yes){
        if(!yes) return;
        st.busy = true; setErr(''); paint();
        apiRemove(kind, st.id).then(function(res){
          st.busy = false;
          if(!res.ok){
            if(res.status !== 401) setErr(twApiMessage(res, twT('cert.err.delete_failed')));
            paint(); return;
          }
          st.has = false; paint();
          patchCache(kind, st.id, res.data || {});
          showToast(twT('cert.removed'), 'success');
        });
      });
    });

    return {
      // entry = the row being edited (null = a new row)
      reset: function(entry){
        st.id = entry ? entry.id : null; st.has = !!(entry && entry.has_certificate);
        st.pending = null; st.busy = false; input.value = ''; setErr(''); paint();
      },
      // after a new row is saved: upload the file chosen before saving → Promise<bool> (true = nothing failed)
      flush: function(id){
        st.id = id;
        if(!st.pending) return Promise.resolve(true);
        return send(id, st.pending);
      },
      focus: function(){ pick.focus(); }
    };
  }

  // ── Card pieces (HTML strings — every value escaped) ──
  function viewButtonHtml(kind, entry){
    if(!entry || !entry.can_view_certificate) return '';
    return '<button type="button" class="sc-cert-link" data-tw-cert-view="' + twEscAttr(kind) + '" data-id="'
      + Number(entry.id) + '">' + twIcon('eye', { size: 'xs' }) + ' ' + twEscHtml(twT('cert.view')) + '</button>';
  }

  // Legacy external link (courses only) — the server returns certificate_url to the owner only; shown to the
  // owner only, with «استبدل بملف PDF».
  function legacyHtml(entry, isOwner){
    if(!isOwner || !entry || !entry.certificate_url) return '';
    var safe = twSafeLinkUrl(entry.certificate_url);   // §54 rule 4b — unsafe → plain text
    var link = safe
      ? '<a href="' + twEscAttr(safe) + '" target="_blank" rel="noopener noreferrer" class="sc-cert-link">'
        + twIcon('link', { size: 'xs' }) + ' ' + twEscHtml(twT('cert.legacy.label')) + '</a>'
      : '<span class="sc-cert-link">' + twEscHtml(entry.certificate_url) + '</span>';
    return '<div class="sc-cert-legacy">' + link
      + '<button type="button" class="sc-cert-btn" data-tw-cert-replace="' + Number(entry.id) + '">'
      + twIcon('upload', { size: 'xs' }) + ' ' + twEscHtml(twT('cert.legacy.replace')) + '</button></div>';
  }

  // ── Viewer: twModal + sandboxed iframe + «فتح بتبويب جديد» ──
  function openViewer(kind, id){
    if(!KINDS[kind]) return Promise.resolve(false);
    return apiView(kind, id).then(function(res){
      var url = res.ok && res.data ? twSafeLinkUrl(res.data.url || '') : '';
      if(!url){
        if(res.status !== 401) showToast(twApiMessage(res, twT('cert.err.view_failed')), 'error');
        return false;
      }
      var box = document.createElement('div');
      box.className = 'sc-cert-viewer';
      var frame = document.createElement('iframe');
      frame.className = 'sc-cert-frame';
      frame.title = twT('cert.preview.frame_title');
      // The PDF comes from the storage origin (cross-origin): allow-same-origin there grants nothing on this
      // site; no forms / popups / top navigation. The browser may still refuse a PDF in a sandbox → the
      // «فتح بتبويب جديد» link below is always there.
      frame.setAttribute('sandbox', 'allow-scripts allow-same-origin');
      frame.setAttribute('referrerpolicy', 'no-referrer');
      frame.src = url;
      var note = document.createElement('p');
      note.className = 'sc-cert-note';
      note.textContent = twT('cert.preview.fallback');
      var open = document.createElement('a');
      open.className = 'sc-cert-btn';
      open.href = url;
      open.target = '_blank';
      open.rel = 'noopener noreferrer';
      open.appendChild(twIconEl('link', { size: 'sm' }));
      open.appendChild(document.createTextNode(' ' + twT('cert.open_new_tab')));
      box.appendChild(frame); box.appendChild(note); box.appendChild(open);
      twModal({ title: twT('cert.preview.title'), content: box,
                actions: [{ text: twT('cert.close'), variant: 'secondary' }] });
      return true;
    });
  }

  // One delegated listener for every card (no inline onclick)
  document.addEventListener('click', function(e){
    var v = e.target && e.target.closest ? e.target.closest('[data-tw-cert-view]') : null;
    if(v){ e.preventDefault(); openViewer(v.getAttribute('data-tw-cert-view'), parseInt(v.getAttribute('data-id'), 10)); return; }
    var r = e.target && e.target.closest ? e.target.closest('[data-tw-cert-replace]') : null;
    if(r && typeof window._courseOpenEdit === 'function'){
      e.preventDefault();
      window._courseOpenEdit(r.getAttribute('data-tw-cert-replace'), { focusCert: true });
    }
  });

  window.TwProfileCert = { field: field, viewButtonHtml: viewButtonHtml, legacyHtml: legacyHtml,
                           openViewer: openViewer };
})();
