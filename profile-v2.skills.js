// profile-v2.skills.js — Skills Add / Delete
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.utils.js

(function(){
  var overlay   = document.getElementById('skillOverlay');
  var saveBtn   = document.getElementById('skillSaveBtn');
  var cancelBtn = document.getElementById('skillCancelBtn');
  var closeBtn  = document.getElementById('skillClose');
  if(!overlay || !saveBtn) return;

  function f(id){ return document.getElementById(id); }
  function fv(id){ return ((f(id)||{}).value||'').trim(); }
  function sv(id,v){ var el=f(id); if(el) el.value=(v==null?'':v); }

  function openModal(){
    sv('skillName','');
    sv('skillLevel','');
    overlay.classList.add('open');
    var inp=f('skillName'); if(inp) setTimeout(function(){ inp.focus(); },120);
  }
  function closeModal(){ overlay.classList.remove('open'); }

  if(closeBtn)  closeBtn.onclick  = closeModal;
  if(cancelBtn) cancelBtn.onclick = closeModal;
  overlay.addEventListener('click', function(e){ if(e.target===overlay) closeModal(); });

  if(saveBtn) saveBtn.onclick = function(){
    var skill = fv('skillName');
    if(!skill){ toast('اسم المهارة مطلوب'); return; }
    if(typeof hasEmoji==='function' && hasEmoji(skill)){ toast('لا يسمح باستخدام الرموز التعبيرية'); return; }
    var payload = { skill: skill, level: fv('skillLevel') || null };
    saveBtn.disabled=true;
    addSkill(_scUserId, payload).then(function(res){
      saveBtn.disabled=false;
      if(!res.ok){ toast((res.data && res.data.detail) || 'حدث خطأ'); return; }
      var entry = res.data.skill;
      var cache = window._scProfile;
      if(cache){
        var existing = (cache.skills||[]).find(function(s){ return s.skill===entry.skill; });
        if(existing){
          cache.skills = (cache.skills||[]).map(function(s){ return s.skill===entry.skill ? entry : s; });
        } else {
          cache.skills = (cache.skills||[]).concat([entry]);
        }
      }
      _reRenderSkills();
      closeModal();
      toast('تمت الإضافة');
    }).catch(function(){ saveBtn.disabled=false; toast('حدث خطأ'); });
  };

  // ── Build Skills HTML ──
  window._buildSkillsHTML = function(skills, isOwner){
    var addBtn = isOwner
      ? '<button class="sc-section-add owner-only" onclick="window._skillOpenAdd()">'
        + '<svg class="ico-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'
        + ' إضافة مهارة</button>'
      : '';
    if(!skills || !skills.length) return addBtn + '<div class="sc-empty">لا توجد مهارات بعد</div>';

    var chips = '<div class="sc-skills-wrap">' + skills.map(function(s){
      var name  = esc(s.skill || '');
      var level = s.level ? esc(s.level) : '';
      var del   = isOwner
        ? ' <span class="sc-skill-del owner-only" data-skill-id="'+s.id+'" onclick="window._skillConfirmDelete(this.dataset.skillId)" title="حذف">×</span>'
        : '';
      return '<span class="sc-skill-chip">'
        + name
        + (level ? ' <em class="sc-skill-level">'+level+'</em>' : '')
        + del
        + '</span>';
    }).join('') + '</div>';

    return chips + addBtn;
  };

  function _reRenderSkills(){
    var el = document.getElementById('scSkillsPane');
    if(!el) return;
    var cache   = window._scProfile;
    var skills  = cache ? (cache.skills || []) : [];
    var isOwner = (window._scViewerType === 'owner');
    el.innerHTML = window._buildSkillsHTML(skills, isOwner);
  }
  window._reRenderSkills = _reRenderSkills;

  window._skillOpenAdd = function(){ openModal(); };
  window._skillConfirmDelete = function(id){
    id = parseInt(id);
    if(!confirm('هل تريد حذف هذه المهارة؟')) return;
    deleteSkill(id).then(function(res){
      if(!res.ok){ toast('حدث خطأ'); return; }
      var cache = window._scProfile;
      if(cache) cache.skills = (cache.skills||[]).filter(function(s){ return s.id!==id; });
      _reRenderSkills();
      toast('تم الحذف');
    }).catch(function(){ toast('حدث خطأ'); });
  };

})();
