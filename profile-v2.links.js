// profile-v2.links.js — Links Add / Delete
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.utils.js

(function(){
  var overlay   = document.getElementById('linkOverlay');
  var saveBtn   = document.getElementById('linkSaveBtn');
  var cancelBtn = document.getElementById('linkCancelBtn');
  var closeBtn  = document.getElementById('linkClose');
  if(!overlay || !saveBtn) return;

  function f(id){ return document.getElementById(id); }
  function fv(id){ return ((f(id)||{}).value||'').trim(); }
  function sv(id,v){ var el=f(id); if(el) el.value=(v==null?'':v); }

  var LINK_LABELS = {
    linkedin:'LinkedIn', github:'GitHub', website:'الموقع الشخصي',
    twitter:'Twitter / X', instagram:'Instagram', behance:'Behance',
    portfolio:'Portfolio', other:'رابط'
  };
  var LINK_ICONS = {
    linkedin:'linkedin', github:'github', website:'globe',
    twitter:'twitter', instagram:'instagram', behance:'layers',
    portfolio:'layout', other:'link'
  };

  function openModal(){
    sv('linkType','linkedin');
    sv('linkUrl','');
    overlay.classList.add('open');
    var inp=f('linkUrl'); if(inp) setTimeout(function(){ inp.focus(); },120);
  }
  function closeModal(){ overlay.classList.remove('open'); }

  if(closeBtn)  closeBtn.onclick  = closeModal;
  if(cancelBtn) cancelBtn.onclick = closeModal;
  overlay.addEventListener('click', function(e){ if(e.target===overlay) closeModal(); });

  if(saveBtn) saveBtn.onclick = function(){
    var url = fv('linkUrl');
    if(!url){ toast('الرابط مطلوب'); return; }
    var payload = { link_type: fv('linkType') || 'other', url: url };
    saveBtn.disabled=true;
    addLink(_scUserId, payload).then(function(res){
      saveBtn.disabled=false;
      if(!res.ok){ toast((res.data && res.data.detail) || 'حدث خطأ'); return; }
      var entry = res.data.link;
      var cache = window._scProfile;
      if(cache){
        var existing = (cache.links||[]).find(function(l){ return l.link_type===entry.link_type; });
        if(existing){
          cache.links = (cache.links||[]).map(function(l){ return l.link_type===entry.link_type ? entry : l; });
        } else {
          cache.links = (cache.links||[]).concat([entry]);
        }
      }
      _reRenderLinks();
      closeModal();
      toast('تمت الإضافة');
    }).catch(function(){ saveBtn.disabled=false; toast('حدث خطأ'); });
  };

  // ── Build Links HTML ──
  window._buildLinksHTML = function(links, isOwner){
    var addBtn = isOwner
      ? '<button class="sc-section-add owner-only" onclick="window._linkOpenAdd()">'
        + '<svg class="ico-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'
        + ' إضافة رابط</button>'
      : '';
    if(!links || !links.length) return addBtn + '<div class="sc-empty">لا توجد روابط بعد</div>';

    var rows = '<div class="sc-links-list">' + links.map(function(l){
      var ltype   = l.link_type || 'other';
      var label   = esc(LINK_LABELS[ltype] || ltype);
      var icon    = LINK_ICONS[ltype] || 'link';
      var urlText = esc(l.url || '');
      var actions = isOwner
        ? '<div class="sc-exp-menu-wrap owner-only">'
          +'<button class="sc-exp-menu-btn" onclick="window._expMenuToggle(this)" title="خيارات">'
          +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/></svg>'
          +'</button>'
          +'<div class="sc-exp-menu">'
          +'<button class="sc-exp-menu-item sc-exp-menu-del" data-link-id="'+l.id+'" onclick="window._linkConfirmDelete(this.dataset.linkId);window._expMenuClose()">'
          +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>'
          +' حذف</button>'
          +'</div>'
          +'</div>'
        : '';

      return '<div class="sc-link-item">'
        + '<div class="sc-link-icon"><i data-lucide="' + icon + '" class="ico-sm"></i></div>'
        + '<div class="sc-link-info">'
        + '<div class="sc-link-type">' + label + '</div>'
        + '<a href="' + urlText + '" target="_blank" rel="noopener" class="sc-link-url">' + urlText + '</a>'
        + '</div>'
        + actions
        + '</div>';
    }).join('') + '</div>';

    return addBtn + rows;
  };

  function _reRenderLinks(){
    var el = document.getElementById('scLinksPane');
    if(!el) return;
    var cache   = window._scProfile;
    var links   = cache ? (cache.links || []) : [];
    var isOwner = (window._scViewerType === 'owner');
    el.innerHTML = window._buildLinksHTML(links, isOwner);
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  }
  window._reRenderLinks = _reRenderLinks;

  window._linkOpenAdd = function(){ openModal(); };
  window._linkConfirmDelete = function(id){
    id = parseInt(id);
    if(!confirm('هل تريد حذف هذا الرابط؟')) return;
    deleteLink(id).then(function(res){
      if(!res.ok){ toast('حدث خطأ'); return; }
      var cache = window._scProfile;
      if(cache) cache.links = (cache.links||[]).filter(function(l){ return l.id!==id; });
      _reRenderLinks();
      toast('تم الحذف');
    }).catch(function(){ toast('حدث خطأ'); });
  };

})();
