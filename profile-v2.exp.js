// profile-v2.exp.js — Experience Add / Edit / Delete
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.utils.js, profile-v2.render.js

(function(){
  var overlay   = document.getElementById('exOverlay');
  var closeBtn  = document.getElementById('exClose');
  var cancelBtn = document.getElementById('exCancelBtn');
  var saveBtn   = document.getElementById('exSaveBtn');
  var errEl     = document.getElementById('exErr');
  var titleEl   = document.getElementById('exModalTitle');

  if(!overlay || !saveBtn) return;

  var _mode   = 'add';
  var _editId = null;

  function f(id){ return document.getElementById(id); }
  function fv(id){ return ((f(id)||{}).value||'').trim(); }

  // Toggle end year visibility based on is_current
  var curChk = f('exCurrent');
  if(curChk){
    curChk.addEventListener('change', function(){
      var wrap = f('exEndWrap');
      if(wrap) wrap.style.display = this.checked ? 'none' : 'block';
    });
  }

  // ── Open Add ──
  window._expOpenAdd = function(){
    _mode = 'add'; _editId = null;
    if(titleEl) titleEl.textContent = 'إضافة خبرة';
    var form = f('exForm');
    if(form){
      var inputs = form.querySelectorAll('input,textarea');
      for(var i=0; i<inputs.length; i++) inputs[i].value = '';
    }
    if(curChk) curChk.checked = false;
    var wrap = f('exEndWrap'); if(wrap) wrap.style.display = 'block';
    if(errEl) errEl.style.display = 'none';
    overlay.classList.add('open');
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  };

  // ── Open Edit ──
  window._expOpenEdit = function(expId){
    var id = parseInt(expId, 10);
    var list = (window._scProfile && Array.isArray(window._scProfile.experience))
      ? window._scProfile.experience : [];
    var e = null;
    for(var i=0; i<list.length; i++){ if(list[i].id === id){ e = list[i]; break; } }
    if(!e){ toast('لم يتم العثور على الخبرة'); return; }

    _mode = 'edit'; _editId = id;
    if(titleEl) titleEl.textContent = 'تعديل الخبرة';
    if(f('exTitle'))    f('exTitle').value    = e.title       || '';
    if(f('exCompany'))  f('exCompany').value  = e.company     || '';
    if(f('exStart'))    f('exStart').value    = e.start_date  || '';
    if(f('exEnd'))      f('exEnd').value      = e.end_date    || '';
    if(f('exLocation')) f('exLocation').value = e.location    || '';
    if(f('exDesc'))     f('exDesc').value     = e.description || '';
    var isCurr = !!e.is_current;
    if(curChk) curChk.checked = isCurr;
    var wrap = f('exEndWrap'); if(wrap) wrap.style.display = isCurr ? 'none' : 'block';
    if(errEl) errEl.style.display = 'none';
    overlay.classList.add('open');
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  };

  // ── Confirm Delete ──
  window._expConfirmDelete = function(expId){
    var id = parseInt(expId, 10);
    scConfirm('هل أنت متأكد من حذف هذه الخبرة؟', function(){ _doDelete(id); });
  };

  function _doDelete(id){
    var uid = window._scUserId;
    if(!uid){ toast('خطأ: لم يتم التعرف على المستخدم'); return; }
    deleteExperience(id)
      .then(function(res){
        if(!res.ok){ toast('حدث خطأ أثناء الحذف'); return; }
        if(window._scProfile && Array.isArray(window._scProfile.experience)){
          window._scProfile.experience = window._scProfile.experience.filter(function(e){ return e.id !== id; });
        }
        toast('تم حذف الخبرة');
        _reRenderExp();
        _bgRefetch();
      })
      .catch(function(){ toast('خطأ في الاتصال بالخادم'); });
  }

  // ── Close ──
  function closeModal(){ overlay.classList.remove('open'); }
  closeBtn.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', function(e){ if(e.target === overlay) closeModal(); });

  // ── Save ──
  saveBtn.addEventListener('click', function(){
    var uid = window._scUserId;
    if(!uid){ showErr('خطأ: لم يتم التعرف على المستخدم'); return; }

    var title   = fv('exTitle');
    var company = fv('exCompany');
    if(!title)   { showErr('المسمى الوظيفي مطلوب'); return; }
    if(!company) { showErr('اسم الشركة مطلوب'); return; }

    var isCurr = !!(curChk && curChk.checked);
    var payload = {
      title:       title,
      company:     company,
      location:    fv('exLocation') || null,
      start_date:  fv('exStart')    || null,
      end_date:    isCurr ? null : (fv('exEnd') || null),
      is_current:  isCurr,
      description: fv('exDesc')     || null
    };

    if(errEl) errEl.style.display = 'none';
    saveBtn.disabled    = true;
    saveBtn.textContent = 'جاري الحفظ…';

    var req = (_mode === 'edit')
      ? updateExperience(_editId, payload)
      : addExperience(uid, payload);

    req.then(function(res){
        if(!res.ok){
          showErr((res.data && res.data.detail) || 'حدث خطأ أثناء الحفظ');
          return;
        }
        var entry = res.data.experience;
        if(!window._scProfile) window._scProfile = {};
        if(!Array.isArray(window._scProfile.experience)) window._scProfile.experience = [];
        if(_mode === 'add'){
          window._scProfile.experience.unshift(entry);
        } else {
          window._scProfile.experience = window._scProfile.experience.map(function(e){
            return (e.id === _editId) ? entry : e;
          });
        }
        closeModal();
        toast(_mode === 'add' ? 'تمت إضافة الخبرة' : 'تم تعديل الخبرة');
        _reRenderExp();
        _bgRefetch();
      })
      .catch(function(){ showErr('خطأ في الاتصال بالخادم'); })
      .finally(function(){
        saveBtn.disabled    = false;
        saveBtn.textContent = 'حفظ';
      });
  });

  function showErr(msg){
    if(errEl){ errEl.textContent = msg; errEl.style.display = 'block'; }
  }

  function _reRenderExp(){
    var expEl = document.getElementById('scExpPane');
    if(!expEl || !window._buildExpHTML) return;
    var exp = (window._scProfile && Array.isArray(window._scProfile.experience))
      ? window._scProfile.experience : [];
    expEl.innerHTML = window._buildExpHTML(exp, window._scViewerType === 'owner');
    if(window.lucide && lucide.createIcons) lucide.createIcons();
    var statEl = document.getElementById('scStatExp');
    if(statEl) statEl.textContent = exp.length;
  }

  function _bgRefetch(){
    if(!window._scProfileKey) return;
    getProfile(window._scProfileKey)
      .then(function(freshRes){
        if(freshRes && window.renderProfile) window.renderProfile(freshRes);
        if(window.lucide && lucide.createIcons) lucide.createIcons();
      })
      .catch(function(){});
  }

  // ── Simple confirm dialog (no alert) ──
  window.scConfirm = function(msg, onYes){
    var old = document.getElementById('_scConfirmBox');
    if(old) old.remove();
    var box = document.createElement('div');
    box.id = '_scConfirmBox';
    box.style.cssText = 'position:fixed;inset:0;z-index:2000;background:rgba(7,11,24,.85);display:flex;align-items:center;justify-content:center';
    var inner = document.createElement('div');
    inner.style.cssText = 'background:#0f1420;border:1px solid rgba(255,255,255,.12);border-radius:16px;padding:24px 22px;max-width:300px;width:88%;text-align:center;font-family:\'Cairo\',sans-serif;direction:rtl';
    inner.innerHTML =
      '<p style="color:#fff;font-size:.9rem;margin-bottom:18px;line-height:1.6">'+esc(msg)+'</p>'
      +'<div style="display:flex;gap:10px;justify-content:center">'
      +'<button id="_scConfNo"  style="flex:1;height:38px;border-radius:9px;border:1px solid rgba(255,255,255,.12);background:none;color:#9aa5b4;font-family:inherit;font-size:.85rem;cursor:pointer">إلغاء</button>'
      +'<button id="_scConfYes" style="flex:1;height:38px;border-radius:9px;border:none;background:linear-gradient(135deg,#f87171,#dc2626);color:#fff;font-family:inherit;font-size:.85rem;font-weight:700;cursor:pointer">حذف</button>'
      +'</div>';
    box.appendChild(inner);
    document.body.appendChild(box);
    document.getElementById('_scConfNo').onclick  = function(){ box.remove(); };
    document.getElementById('_scConfYes').onclick = function(){ box.remove(); onYes(); };
    box.addEventListener('click', function(e){ if(e.target === box) box.remove(); });
  };
})();
