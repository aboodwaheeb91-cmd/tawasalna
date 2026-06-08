// profile-v2.langs.js — Languages Add / Delete
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.utils.js

(function(){
  var overlay   = document.getElementById('langOverlay');
  var saveBtn   = document.getElementById('langSaveBtn');
  var cancelBtn = document.getElementById('langCancelBtn');
  var closeBtn  = document.getElementById('langClose');
  if(!overlay || !saveBtn) return;

  function f(id){ return document.getElementById(id); }
  function fv(id){ return ((f(id)||{}).value||'').trim(); }
  function sv(id,v){ var el=f(id); if(el) el.value=(v==null?'':v); }

  function openModal(){
    sv('langName','');
    sv('langLevel','');
    overlay.classList.add('open');
  }
  function closeModal(){ overlay.classList.remove('open'); }

  if(closeBtn)  closeBtn.onclick  = closeModal;
  if(cancelBtn) cancelBtn.onclick = closeModal;
  overlay.addEventListener('click', function(e){ if(e.target===overlay) closeModal(); });

  if(saveBtn) saveBtn.onclick = function(){
    var lang = fv('langName');
    if(!lang){ toast('اسم اللغة مطلوب'); return; }
    if(typeof hasEmoji==='function' && hasEmoji(lang)){ toast('لا يسمح باستخدام الرموز التعبيرية'); return; }
    var payload = { language: lang, level: fv('langLevel') || null };
    saveBtn.disabled=true;
    addLang(_scUserId, payload).then(function(res){
      saveBtn.disabled=false;
      if(!res.ok){ toast((res.data && res.data.detail) || 'حدث خطأ'); return; }
      var entry = res.data.lang;
      var cache = window._scProfile;
      if(cache){
        var existing = (cache.langs||[]).find(function(l){ return l.language===entry.language; });
        if(existing){
          cache.langs = (cache.langs||[]).map(function(l){ return l.language===entry.language ? entry : l; });
        } else {
          cache.langs = (cache.langs||[]).concat([entry]);
        }
      }
      _reRenderLangs();
      closeModal();
      toast('تمت الإضافة');
    }).catch(function(){ saveBtn.disabled=false; toast('حدث خطأ'); });
  };

  // ── Build Languages HTML ──
  window._buildLangsHTML = function(langs, isOwner){
    var addBtn = isOwner
      ? '<button class="sc-section-add owner-only" onclick="window._langOpenAdd()">'
        + '<svg class="ico-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'
        + ' إضافة لغة</button>'
      : '';
    if(!langs || !langs.length) return addBtn + '<div class="sc-empty">لا توجد لغات بعد</div>';

    var rows = '<div class="sc-exp-list">' + langs.map(function(l){
      var langName = esc(l.language || '');
      var level    = l.level ? esc(l.level) : '';
      var actions  = isOwner
        ? '<div class="sc-exp-menu-wrap owner-only">'
          +'<button class="sc-exp-menu-btn" onclick="window._expMenuToggle(this)" title="خيارات">'
          +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/></svg>'
          +'</button>'
          +'<div class="sc-exp-menu">'
          +'<button class="sc-exp-menu-item sc-exp-menu-del" data-lang-id="'+l.id+'" onclick="window._langConfirmDelete(this.dataset.langId);window._expMenuClose()">'
          +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>'
          +' حذف</button>'
          +'</div>'
          +'</div>'
        : '';

      return '<div class="sc-exp-card">'
        + '<div class="sc-exp-head">'
        + '<div class="sc-exp-body">'
        + '<div class="sc-exp-title">' + langName + '</div>'
        + (level ? '<div class="sc-exp-company sc-lang-level">' + level + '</div>' : '')
        + '</div>'
        + actions
        + '</div>'
        + '</div>';
    }).join('') + '</div>';

    return addBtn + rows;
  };

  function _reRenderLangs(){
    var el = document.getElementById('scLangsPane');
    if(!el) return;
    var cache   = window._scProfile;
    var langs   = cache ? (cache.langs || []) : [];
    var isOwner = (window._scViewerType === 'owner');
    el.innerHTML = window._buildLangsHTML(langs, isOwner);
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  }
  window._reRenderLangs = _reRenderLangs;

  window._langOpenAdd = function(){ openModal(); };
  window._langConfirmDelete = function(id){
    id = parseInt(id);
    if(!confirm('هل تريد حذف هذه اللغة؟')) return;
    deleteLang(id).then(function(res){
      if(!res.ok){ toast('حدث خطأ'); return; }
      var cache = window._scProfile;
      if(cache) cache.langs = (cache.langs||[]).filter(function(l){ return l.id!==id; });
      _reRenderLangs();
      toast('تم الحذف');
    }).catch(function(){ toast('حدث خطأ'); });
  };

})();
