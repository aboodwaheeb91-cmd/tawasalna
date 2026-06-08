// profile-v2.edu.js — Education Add / Edit / Delete
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.utils.js

(function(){
  var overlay   = document.getElementById('eduOverlay');
  var saveBtn   = document.getElementById('eduSaveBtn');
  var cancelBtn = document.getElementById('eduCancelBtn');
  var closeBtn  = document.getElementById('eduClose');
  if(!overlay || !saveBtn) return;

  function f(id){ return document.getElementById(id); }
  function fv(id){ return ((f(id)||{}).value||'').trim(); }
  function sv(id,v){ var el=f(id); if(el) el.value=(v==null?'':v); }

  var _editId = null;

  // Populate year selects once — runs at module init
  (function _populateEduYears(){
    var selSY = f('eduSY'), selEY = f('eduEY');
    if(!selSY || selSY.options.length > 1) return;
    var now = new Date().getFullYear();
    var opts = '<option value="">— اختر —</option>';
    for(var y = now + 2; y >= 1950; y--) opts += '<option value="'+y+'">'+y+'</option>';
    selSY.innerHTML = opts;
    selEY.innerHTML = opts;
  })();

  function openAdd(){
    _editId = null;
    sv('eduMTitle','إضافة شهادة');
    sv('eduInst',''); sv('eduDeg',''); sv('eduField','');
    sv('eduSY',''); sv('eduEY',''); sv('eduDesc','');
    overlay.classList.add('open');
    var inp=f('eduInst'); if(inp) setTimeout(function(){ inp.focus(); },120);
  }

  function openEdit(entry){
    _editId = entry.id;
    sv('eduMTitle','تعديل الشهادة');
    sv('eduInst',  entry.institution   || '');
    sv('eduDeg',   entry.degree        || '');
    sv('eduField', entry.field         || '');
    sv('eduSY',    entry.start_year    ? String(entry.start_year) : '');
    sv('eduEY',    entry.end_year      ? String(entry.end_year)   : '');
    sv('eduDesc',  entry.description   || '');
    overlay.classList.add('open');
    var inp=f('eduInst'); if(inp) setTimeout(function(){ inp.focus(); },120);
  }

  function closeModal(){ overlay.classList.remove('open'); _editId=null; }

  if(closeBtn)  closeBtn.onclick  = closeModal;
  if(cancelBtn) cancelBtn.onclick = closeModal;
  overlay.addEventListener('click', function(e){ if(e.target===overlay) closeModal(); });

  if(saveBtn) saveBtn.onclick = function(){
    var inst = fv('eduInst');
    if(!inst){ toast('اسم المؤسسة مطلوب'); return; }
    var _emojiFields = [inst, fv('eduDeg'), fv('eduField'), fv('eduDesc')];
    for(var _i=0; _i<_emojiFields.length; _i++){
      if(_emojiFields[_i] && typeof hasEmoji==='function' && hasEmoji(_emojiFields[_i])){ toast('لا يسمح باستخدام الرموز التعبيرية'); return; }
    }
    var payload = {
      institution:  inst,
      degree:       fv('eduDeg')   || null,
      field:        fv('eduField') || null,
      start_year:   fv('eduSY')    ? parseInt(fv('eduSY'))  : null,
      end_year:     fv('eduEY')    ? parseInt(fv('eduEY'))  : null,
      description:  fv('eduDesc')  || null
    };
    saveBtn.disabled=true;

    var isEdit = !!_editId;
    var promise = isEdit
      ? updateEdu(_editId, payload)
      : addEdu(_scUserId, payload);

    promise.then(function(res){
      saveBtn.disabled=false;
      if(!res.ok){ toast((res.data && res.data.detail) || 'حدث خطأ'); return; }
      var entry = res.data.education;
      var cache = window._scProfile;
      if(cache){
        if(isEdit){
          cache.education = (cache.education||[]).map(function(e){ return e.id===entry.id ? entry : e; });
        } else {
          cache.education = (cache.education||[]).concat([entry]);
        }
      }
      _reRenderEdu();
      closeModal();
      toast(isEdit ? 'تم التحديث' : 'تمت الإضافة');
    }).catch(function(){ saveBtn.disabled=false; toast('حدث خطأ'); });
  };

  // ── Build Education HTML ──
  window._buildEduHTML = function(education, isOwner){
    var addBtn = isOwner
      ? '<button class="sc-section-add owner-only" onclick="window._eduOpenAdd()">'
        + '<svg class="ico-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'
        + ' إضافة شهادة</button>'
      : '';
    if(!education || !education.length) return addBtn + '<div class="sc-empty">لا توجد شهادات بعد</div>';

    var rows = '<div class="sc-exp-list">' + education.map(function(e){
      var inst  = esc(e.institution || '');
      var deg   = e.degree  ? esc(e.degree)  : '';
      var field = e.field   ? esc(e.field)   : '';
      var sy    = e.start_year || '';
      var ey    = e.end_year   || '';
      var period = sy ? (sy + (ey ? ' – ' + ey : ' – الآن')) : '';
      var desc  = e.description ? esc(e.description) : '';
      var actions = isOwner
        ? '<div class="sc-exp-menu-wrap owner-only">'
          +'<button class="sc-exp-menu-btn" onclick="window._expMenuToggle(this)" title="خيارات">'
          +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/></svg>'
          +'</button>'
          +'<div class="sc-exp-menu">'
          +'<button class="sc-exp-menu-item" data-edu-json="'+esc(JSON.stringify(e))+'" onclick="window._eduOpenEdit(this.dataset.eduJson);window._expMenuClose()">'
          +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>'
          +' تعديل</button>'
          +'<button class="sc-exp-menu-item sc-exp-menu-del" data-edu-id="'+e.id+'" onclick="window._eduConfirmDelete(this.dataset.eduId);window._expMenuClose()">'
          +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>'
          +' حذف</button>'
          +'</div>'
          +'</div>'
        : '';

      return '<div class="sc-exp-card">'
        + '<div class="sc-exp-head">'
        + '<div class="sc-exp-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="20" height="20"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg></div>'
        + '<div class="sc-exp-body">'
        + '<div class="sc-exp-title">' + (deg ? deg + (field ? ' – ' + field : '') : (field || 'شهادة')) + '</div>'
        + '<div class="sc-exp-company">' + inst + '</div>'
        + (period ? '<div class="sc-exp-period">' + period + '</div>' : '')
        + (desc   ? '<div class="sc-exp-desc">'   + desc   + '</div>' : '')
        + '</div>'
        + actions
        + '</div>'
        + '</div>';
    }).join('') + '</div>';

    return addBtn + rows;
  };

  function _reRenderEdu(){
    var el = document.getElementById('scEduPane');
    if(!el) return;
    var cache     = window._scProfile;
    var education = cache ? (cache.education || []) : [];
    var isOwner   = (window._scViewerType === 'owner');
    el.innerHTML  = window._buildEduHTML(education, isOwner);
  }
  window._reRenderEdu = _reRenderEdu;

  window._eduOpenAdd  = function(){ openAdd(); };
  window._eduOpenEdit = function(json){
    try{ openEdit(JSON.parse(json)); } catch(e){ toast('حدث خطأ'); }
  };
  window._eduConfirmDelete = function(id){
    id = parseInt(id);
    if(!confirm('هل تريد حذف هذه الشهادة؟')) return;
    deleteEdu(id).then(function(res){
      if(!res.ok){ toast('حدث خطأ'); return; }
      var cache = window._scProfile;
      if(cache) cache.education = (cache.education||[]).filter(function(e){ return e.id!==id; });
      _reRenderEdu();
      toast('تم الحذف');
    }).catch(function(){ toast('حدث خطأ'); });
  };

})();
