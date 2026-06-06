// profile-v2.edit.js — Edit Profile Modal (Phase 1: profession + bio)
// Depends on: profile-v2.state.js (_jwt, _scUserId, _scProfileKey, _scProfile)
//             profile-v2.api.js (getProfessions, updateProfile, getProfile)
//             profile-v2.render.js (window.renderProfile)
//             profile-v2.utils.js (window.toast)

(function(){
  var overlay   = document.getElementById('epOverlay');
  var closeBtn  = document.getElementById('epClose');
  var cancelBtn = document.getElementById('epCancelBtn');
  var saveBtn   = document.getElementById('epSaveBtn');
  var editBtn   = document.getElementById('scEditProfileBtn');
  var errEl     = document.getElementById('epErr');

  if(!overlay || !editBtn) return;

  function openModal(){
    var p = window._scProfile || {};

    var bioEl = document.getElementById('epBio');
    if(bioEl) bioEl.value = p.bio || '';

    var profEl = document.getElementById('epProfession');
    if(profEl){
      profEl.innerHTML = '<option value="">جاري التحميل…</option>';
      getProfessions()
        .then(function(list){
          var groups = {};
          list.forEach(function(pr){
            var g = pr.category_group || 'أخرى';
            if(!groups[g]) groups[g] = [];
            groups[g].push(pr);
          });
          var html = '<option value="">— اختر التخصص —</option>';
          Object.keys(groups).forEach(function(g){
            html += '<optgroup label="' + g + '">';
            groups[g].forEach(function(pr){
              var sel = (p.profession && p.profession.id === pr.id) ? ' selected' : '';
              html += '<option value="' + pr.id + '"' + sel + '>' + pr.name_ar + '</option>';
            });
            html += '</optgroup>';
          });
          profEl.innerHTML = html;
          if(window.lucide && lucide.createIcons) lucide.createIcons();
        })
        .catch(function(){ profEl.innerHTML = '<option value="">تعذّر تحميل التخصصات</option>'; });
    }

    if(errEl) errEl.style.display = 'none';
    overlay.classList.add('open');
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  }

  function closeModal(){
    overlay.classList.remove('open');
  }

  editBtn.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', function(e){ if(e.target === overlay) closeModal(); });

  saveBtn.addEventListener('click', function(){
    var uid = window._scUserId;
    if(!uid){ if(errEl){ errEl.textContent = 'خطأ: لم يتم التعرف على المستخدم'; errEl.style.display = 'block'; } return; }

    var profEl = document.getElementById('epProfession');
    var profVal = profEl ? profEl.value : '';
    var bioVal  = (document.getElementById('epBio').value || '').trim();

    var payload = {};
    if(profVal) payload.profession_id = parseInt(profVal, 10);
    payload.bio = bioVal;

    if(errEl) errEl.style.display = 'none';
    saveBtn.disabled = true;
    saveBtn.textContent = 'جاري الحفظ…';

    updateProfile(uid, payload)
      .then(function(res){
        if(!res.ok){
          var msg = (res.data && res.data.detail) ? res.data.detail : 'حدث خطأ أثناء الحفظ';
          if(errEl){ errEl.textContent = msg; errEl.style.display = 'block'; }
          return;
        }
        closeModal();
        if(window.toast) window.toast('تم حفظ التغييرات بنجاح');
        return getProfile(_scProfileKey)
          .then(function(freshRes){
            if(freshRes && window.renderProfile) window.renderProfile(freshRes);
            if(window.lucide && lucide.createIcons) lucide.createIcons();
          });
      })
      .catch(function(){ if(errEl){ errEl.textContent = 'خطأ في الاتصال بالخادم'; errEl.style.display = 'block'; } })
      .finally(function(){ saveBtn.disabled = false; saveBtn.textContent = 'حفظ التغييرات'; });
  });
})();
