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

  // ── Country → Arabic name map (for building location string) ──
  var EXP_COUNTRIES = {
    JO:'الأردن', SA:'السعودية', AE:'الإمارات', KW:'الكويت',
    QA:'قطر',    BH:'البحرين', OM:'عُمان',    EG:'مصر',
    IQ:'العراق', SY:'سوريا',  LB:'لبنان',    PS:'فلسطين',
    YE:'اليمن',  MA:'المغرب', DZ:'الجزائر',  TN:'تونس',
    LY:'ليبيا',  SD:'السودان'
  };

  // ── City lists by country code ──
  var EXP_CITIES = {
    JO:['عمان','إربد','الزرقاء','العقبة','السلط','مادبا','الكرك','معان','جرش','عجلون','الطفيلة'],
    SA:['الرياض','جدة','مكة المكرمة','المدينة المنورة','الدمام','الخبر','الطائف','أبها','تبوك','بريدة'],
    AE:['دبي','أبوظبي','الشارقة','عجمان','رأس الخيمة','الفجيرة','أم القيوين','العين'],
    KW:['مدينة الكويت','حولي','الفروانية','الأحمدي','الجهراء','مبارك الكبير'],
    QA:['الدوحة','الريان','الوكرة','أم صلال','الخور'],
    BH:['المنامة','المحرق','الرفاع','مدينة عيسى','مدينة حمد'],
    OM:['مسقط','صلالة','نزوى','صحار','السيب','مطرح'],
    EG:['القاهرة','الإسكندرية','الجيزة','شرم الشيخ','الأقصر','أسوان','طنطا','المنصورة','بورسعيد'],
    IQ:['بغداد','البصرة','الموصل','أربيل','كربلاء','النجف','السليمانية','كركوك'],
    SY:['دمشق','حلب','حمص','اللاذقية','حماة','دير الزور'],
    LB:['بيروت','طرابلس','صيدا','صور','جونية','زحلة'],
    PS:['رام الله','القدس','غزة','نابلس','الخليل','جنين','أريحا','بيت لحم'],
    YE:['صنعاء','عدن','تعز','الحديدة','إب','ذمار'],
    LY:['طرابلس','بنغازي','مصراتة','الزاوية','البيضاء'],
    TN:['تونس','صفاقس','سوسة','بنزرت','قابس','القيروان'],
    DZ:['الجزائر','وهران','قسنطينة','عنابة','سطيف','تلمسان'],
    MA:['الرباط','الدار البيضاء','فاس','مراكش','مكناس','أكادير','طنجة'],
    SD:['الخرطوم','أم درمان','بورتسودان','كسلا','الأبيض']
  };

  var CUR_YEAR = new Date().getFullYear();

  // ── Populate start year select (newest first) ──
  (function(){
    var sel = f('exStart');
    if(!sel) return;
    for(var y = CUR_YEAR; y >= 1980; y--){
      var o = document.createElement('option');
      o.value = y; o.text = y;
      sel.appendChild(o);
    }
  })();

  // ── Populate / refresh end year select from a minimum year ──
  function _populateEndYear(fromYear, selectedVal){
    var sel = f('exEnd');
    if(!sel) return;
    var min = parseInt(fromYear, 10) || 1980;
    sel.innerHTML = '<option value="">— اختر —</option>';
    for(var y = CUR_YEAR; y >= min; y--){
      var o = document.createElement('option');
      o.value = y; o.text = y;
      if(selectedVal && parseInt(selectedVal, 10) === y) o.selected = true;
      sel.appendChild(o);
    }
  }

  _populateEndYear(1980, '');

  // Start year change → refresh end year (keep current end value if still valid)
  var startSel = f('exStart');
  if(startSel){
    startSel.addEventListener('change', function(){
      var curEnd = fv('exEnd');
      _populateEndYear(this.value || 1980, curEnd);
    });
  }

  // ── City loader ──
  function _expLoadCities(selectedCity){
    var cc      = fv('exCountry');
    var cityWrap= f('exCityWrap');
    var cityEl  = f('exCity');
    if(!cityEl) return;
    var cities = EXP_CITIES[cc] || [];
    if(!cities.length){
      if(cityWrap) cityWrap.style.display = 'none';
      cityEl.innerHTML = '<option value="">— اختر المدينة —</option>';
      return;
    }
    cityEl.innerHTML = '<option value="">— اختر المدينة —</option>';
    cities.forEach(function(c){
      var o = document.createElement('option');
      o.value = c; o.text = c;
      if(selectedCity && c === selectedCity) o.selected = true;
      cityEl.appendChild(o);
    });
    if(cityWrap) cityWrap.style.display = 'block';
  }

  var countrySel = f('exCountry');
  if(countrySel) countrySel.addEventListener('change', function(){ _expLoadCities(''); });

  // ── is_current toggle ──
  var curChk = f('exCurrent');
  if(curChk){
    curChk.addEventListener('change', function(){
      var wrap = f('exEndWrap');
      if(wrap) wrap.style.display = this.checked ? 'none' : 'block';
    });
  }

  // ── Build location string from country+city selects ──
  function _buildLocation(){
    var cc   = fv('exCountry');
    var city = fv('exCity');
    if(!cc) return null;
    var name = EXP_COUNTRIES[cc] || cc;
    return city ? (name + ' - ' + city) : name;
  }

  // ── Prefill location selects from stored location string ──
  function _prefillLocation(loc){
    if(!loc) return;
    var parts = loc.split(' - ');
    var countryName = parts[0].trim();
    var cityName    = parts.length > 1 ? parts[1].trim() : '';
    var code = '';
    for(var cc in EXP_COUNTRIES){
      if(EXP_COUNTRIES[cc] === countryName){ code = cc; break; }
    }
    if(f('exCountry')) f('exCountry').value = code;
    _expLoadCities(cityName);
  }

  // ── Reset all form fields ──
  function _resetForm(){
    if(f('exTitle'))   f('exTitle').value   = '';
    if(f('exCompany')) f('exCompany').value = '';
    if(f('exDesc'))    f('exDesc').value    = '';
    if(f('exStart'))   f('exStart').value   = '';
    if(f('exCountry')) f('exCountry').value = '';
    var cw = f('exCityWrap'); if(cw) cw.style.display = 'none';
    if(f('exCity'))    f('exCity').innerHTML = '<option value="">— اختر المدينة —</option>';
    if(curChk)         curChk.checked = false;
    var wrap = f('exEndWrap'); if(wrap) wrap.style.display = 'block';
    _populateEndYear(1980, '');
    if(errEl) errEl.style.display = 'none';
  }

  // ── Open Add ──
  window._expOpenAdd = function(){
    _mode = 'add'; _editId = null;
    if(titleEl) titleEl.textContent = 'إضافة خبرة';
    _resetForm();
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
    _resetForm();

    if(f('exTitle'))   f('exTitle').value   = e.title       || '';
    if(f('exCompany')) f('exCompany').value = e.company     || '';
    if(f('exDesc'))    f('exDesc').value    = e.description || '';

    // Start year then refresh end year options from that start
    var startY = e.start_date ? String(parseInt(e.start_date, 10)) : '';
    if(f('exStart')) f('exStart').value = startY;
    _populateEndYear(startY || 1980, e.end_date || '');

    // is_current
    var isCurr = !!e.is_current;
    if(curChk) curChk.checked = isCurr;
    var wrap = f('exEndWrap'); if(wrap) wrap.style.display = isCurr ? 'none' : 'block';

    // Location → parse into country+city selects
    _prefillLocation(e.location || '');

    overlay.classList.add('open');
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  };

  // ── Confirm Delete ──
  window._expConfirmDelete = function(expId){
    var id = parseInt(expId, 10);
    scConfirm('هل أنت متأكد من حذف هذه الخبرة؟', function(){ _doDelete(id); });
  };

  function _doDelete(id){
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
      location:    _buildLocation(),
      start_date:  fv('exStart') || null,
      end_date:    isCurr ? null : (fv('exEnd') || null),
      is_current:  isCurr,
      description: fv('exDesc') || null
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

  // ── Experience sort order ──
  function _saveExperienceOrder(oldOrder){
    var list = (window._scProfile && Array.isArray(window._scProfile.experience))
      ? window._scProfile.experience : [];
    var ids = list.map(function(e){ return e.id; });
    reorderExperience(ids)
      .then(function(res){
        if(!res.ok){
          if(window._scProfile) window._scProfile.experience = oldOrder;
          _reRenderExp();
          toast('فشل حفظ الترتيب');
          return;
        }
        _bgRefetch();
      })
      .catch(function(){
        if(window._scProfile) window._scProfile.experience = oldOrder;
        _reRenderExp();
        toast('خطأ في حفظ الترتيب');
      });
  }

  window._expMoveUp = function(expId){
    var id   = parseInt(expId, 10);
    var list = (window._scProfile && Array.isArray(window._scProfile.experience))
      ? window._scProfile.experience : [];
    var idx  = -1;
    for(var i = 0; i < list.length; i++){ if(list[i].id === id){ idx = i; break; } }
    if(idx <= 0) return;
    var oldOrder = list.slice();
    var tmp = list[idx]; list[idx] = list[idx - 1]; list[idx - 1] = tmp;
    _reRenderExp();
    _saveExperienceOrder(oldOrder);
  };

  window._expMoveDown = function(expId){
    var id   = parseInt(expId, 10);
    var list = (window._scProfile && Array.isArray(window._scProfile.experience))
      ? window._scProfile.experience : [];
    var idx  = -1;
    for(var i = 0; i < list.length; i++){ if(list[i].id === id){ idx = i; break; } }
    if(idx < 0 || idx >= list.length - 1) return;
    var oldOrder = list.slice();
    var tmp = list[idx]; list[idx] = list[idx + 1]; list[idx + 1] = tmp;
    _reRenderExp();
    _saveExperienceOrder(oldOrder);
  };

  // ── Three-dots menu toggle / close ──
  // Uses position:fixed + getBoundingClientRect to escape overflow:hidden on .sc-main-card.
  // Decides up/down based on available viewport space.
  window._expMenuToggle = function(btn){
    var menu = btn.nextElementSibling;
    if(!menu) return;
    var isOpen = menu.classList.contains('open');
    var all = document.querySelectorAll('.sc-exp-menu.open');
    for(var i = 0; i < all.length; i++) all[i].classList.remove('open');
    if(!isOpen){
      var rect     = btn.getBoundingClientRect();
      var menuW    = 156;
      var menuH    = 172;
      var spaceBelow = window.innerHeight - rect.bottom;
      var leftPos  = Math.max(4, Math.min(rect.left, window.innerWidth - menuW - 4));
      menu.style.position = 'fixed';
      menu.style.width    = menuW + 'px';
      menu.style.left     = leftPos + 'px';
      menu.style.right    = 'auto';
      if(spaceBelow >= menuH + 8){
        menu.style.top    = (rect.bottom + 5) + 'px';
        menu.style.bottom = 'auto';
      } else {
        menu.style.top    = 'auto';
        menu.style.bottom = (window.innerHeight - rect.top + 5) + 'px';
      }
      menu.classList.add('open');
    }
  };

  window._expMenuClose = function(){
    var all = document.querySelectorAll('.sc-exp-menu.open');
    for(var i = 0; i < all.length; i++) all[i].classList.remove('open');
  };

  document.addEventListener('click', function(e){
    if(!e.target.closest || !e.target.closest('.sc-exp-menu-wrap')){
      window._expMenuClose();
    }
  });

  // close on any scroll anywhere (capture=true catches non-bubbling scroll events)
  window.addEventListener('scroll', window._expMenuClose, true);

  // ── Simple confirm dialog ──
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
