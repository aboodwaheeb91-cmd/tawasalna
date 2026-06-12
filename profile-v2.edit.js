// profile-v2.edit.js — Edit Profile Modal (Phase 2 + Confirmed Local Update)
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.render.js, profile-v2.utils.js

(function(){
  var overlay   = document.getElementById('epOverlay');
  var closeBtn  = document.getElementById('epClose');
  var cancelBtn = document.getElementById('epCancelBtn');
  var saveBtn   = document.getElementById('epSaveBtn');
  var editBtn   = document.getElementById('scEditProfileBtn');
  var errEl     = document.getElementById('epErr');

  if(!overlay || !editBtn) return;

  // ── Cities data ──
  var EP_CITIES = {
    JO:['عمان','إربد','الزرقاء','العقبة','السلط','مادبا','الكرك','معان','جرش','عجلون','الطفيلة'],
    SA:['الرياض','جدة','مكة المكرمة','المدينة المنورة','الدمام','الخبر','الطائف','أبها','تبوك','القطيف','بريدة'],
    AE:['دبي','أبوظبي','الشارقة','عجمان','رأس الخيمة','الفجيرة','أم القيوين','العين'],
    KW:['مدينة الكويت','حولي','الفروانية','الأحمدي','الجهراء','مبارك الكبير'],
    QA:['الدوحة','الريان','الوكرة','أم صلال','الخور','الشمال'],
    BH:['المنامة','المحرق','الرفاع','مدينة عيسى','مدينة حمد'],
    OM:['مسقط','صلالة','نزوى','صحار','السيب','مطرح','البريمي'],
    EG:['القاهرة','الإسكندرية','الجيزة','شرم الشيخ','الأقصر','أسوان','طنطا','المنصورة','الفيوم','بورسعيد'],
    IQ:['بغداد','البصرة','الموصل','أربيل','كربلاء','النجف','السليمانية','كركوك'],
    SY:['دمشق','حلب','حمص','اللاذقية','حماة','دير الزور','الرقة','درعا'],
    LB:['بيروت','طرابلس','صيدا','صور','جونية','زحلة'],
    PS:['رام الله','القدس','غزة','نابلس','الخليل','جنين','أريحا','بيت لحم'],
    YE:['صنعاء','عدن','تعز','الحديدة','إب','ذمار','مأرب'],
    LY:['طرابلس','بنغازي','مصراتة','الزاوية','البيضاء','سبها'],
    TN:['تونس','صفاقس','سوسة','بنزرت','قابس','القيروان'],
    DZ:['الجزائر','وهران','قسنطينة','عنابة','سطيف','تلمسان'],
    MA:['الرباط','الدار البيضاء','فاس','مراكش','مكناس','أكادير','طنجة'],
    SD:['الخرطوم','أم درمان','بورتسودان','كسلا','الأبيض']
  };

  // cached professions list — set on open, used in applyLocalUpdate
  var _profList = [];

  // ── Populate DOB day options ──
  (function(){
    var d = document.getElementById('epDobD');
    if(!d) return;
    for(var i=1; i<=31; i++){
      var o = document.createElement('option');
      o.value = String(i).padStart(2,'0'); o.text = i;
      d.appendChild(o);
    }
  })();

  // ── Populate DOB year options ──
  (function(){
    var y = document.getElementById('epDobY');
    if(!y) return;
    var cur = new Date().getFullYear();
    for(var i=cur-15; i>=1940; i--){
      var o = document.createElement('option');
      o.value = i; o.text = i;
      y.appendChild(o);
    }
  })();

  // ── City loader — global so onchange="epLoadCities()" works ──
  window.epLoadCities = function(selectedCity){
    var cc       = (document.getElementById('epCountry')||{}).value || '';
    var cityWrap = document.getElementById('epCityWrap');
    var cityEl   = document.getElementById('epCity');
    if(!cityEl) return;
    var cities = EP_CITIES[cc] || [];
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
  };

  // ── Confirmed Local Update — runs immediately after PUT succeeds ──
  function applyLocalUpdate(payload){
    // Name — update from parts (backend builds full_name, we mirror it locally)
    var _builtName = [payload.first_name, payload.middle_name, payload.last_name]
      .filter(function(x){ return x && x.trim(); }).join(' ');
    if(_builtName){
      var nameEl = document.getElementById('scName');
      if(nameEl) nameEl.textContent = _builtName;
      if(window._scProfile){
        window._scProfile.full_name   = _builtName;
        window._scProfile.first_name  = payload.first_name  || '';
        window._scProfile.middle_name = payload.middle_name || '';
        window._scProfile.last_name   = payload.last_name   || '';
      }
      requestAnimationFrame(function(){ if(window._fitName) window._fitName(); });
    }

    // Bio — update header bio, about tab, and overflow button
    if(payload.bio !== undefined){
      var bioEl = document.getElementById('scBio');
      if(bioEl) bioEl.textContent = payload.bio;
      var aboutEl = document.getElementById('scAboutText');
      if(aboutEl){
        aboutEl.textContent = payload.bio || 'لا توجد نبذة بعد';
        var _hint = aboutEl.nextElementSibling;
        if(_hint && _hint.classList && _hint.classList.contains('sc-ab-empty-hint'))
          _hint.style.display = 'none';
      }
      requestAnimationFrame(function(){
        if(bioEl){
          var moreBtn = document.getElementById('scBioMore');
          if(moreBtn) moreBtn.style.display = bioEl.scrollHeight > bioEl.clientHeight + 2 ? 'inline-block' : 'none';
        }
      });
      if(window._scProfile) window._scProfile.bio = payload.bio;
    }

    // DOB → compute and display age
    if('dob' in payload){
      if(payload.dob){
        var birth = new Date(payload.dob);
        if(!isNaN(birth.getTime())){
          var age = Math.floor((Date.now() - birth.getTime()) / (365.25*24*3600*1000));
          var ageEl = document.getElementById('scAge');
          if(ageEl){
            if(age > 0 && age < 150){
              ageEl.innerHTML = '<i data-lucide="cake" class="ico-sm"></i> ' + age + ' سنة';
              ageEl.style.display = 'flex';
            }
          }
        }
      } else {
        var ageEl = document.getElementById('scAge');
        if(ageEl) ageEl.style.display = 'none';
      }
      if(window._scProfile) window._scProfile.dob = payload.dob;
    }

    // Country / city — update cache then refresh scLoc DOM immediately
    if('country' in payload && window._scProfile) window._scProfile.country = payload.country || '';
    if('city'    in payload && window._scProfile) window._scProfile.city    = payload.city    || '';
    if(payload.avail !== undefined && window._scProfile) window._scProfile.avail = payload.avail;
    (function(){
      var _p   = window._scProfile || {};
      var _loc = document.getElementById('scLoc');
      if(!_loc || !window._buildLocText) return;
      var _lt = window._buildLocText(_p.country || '', _p.city || '', _p.location || '');
      if(_lt){
        _loc.innerHTML = '<i data-lucide="map-pin" class="ico-sm"></i> ' + esc(_lt);
        _loc.style.display = 'inline-flex';
        _loc.style.alignItems = 'center';
        _loc.style.gap = '4px';
      } else {
        _loc.innerHTML = '';
        _loc.style.display = '';
      }
      if(window.lucide && lucide.createIcons) lucide.createIcons();
    })();

    // Profession — look up from cached list to get name_ar + icon
    if(payload.profession_id && _profList.length){
      var prof = null;
      for(var i=0; i<_profList.length; i++){
        if(_profList[i].id === payload.profession_id){ prof = _profList[i]; break; }
      }
      if(prof){
        var titleEl = document.getElementById('scTitle');
        if(titleEl){
          titleEl.innerHTML = '<i data-lucide="' + (prof.icon || 'briefcase') + '" class="ico-sm"></i> ' + prof.name_ar;
        }
        if(window._scProfile) window._scProfile.profession = prof;
        if(window.lucide && lucide.createIcons) lucide.createIcons();
      }
    }
  }

  // ── Open Modal — prefill all fields ──
  function openModal(){
    var p = window._scProfile || {};

    // Name: use stored name parts if available, split only as legacy fallback
    var fn = document.getElementById('epFirstName');
    var mn = document.getElementById('epMidName');
    var ln = document.getElementById('epLastName');
    if(p.first_name){
      if(fn) fn.value = p.first_name;
      if(mn) mn.value = p.middle_name || '';
      if(ln) ln.value = p.last_name   || '';
    } else {
      var parts = (p.full_name || '').trim().split(/\s+/).filter(Boolean);
      if(fn) fn.value = parts[0] || '';
      if(ln) ln.value = parts.length > 1 ? parts[parts.length-1] : '';
      if(mn) mn.value = parts.length > 2 ? parts.slice(1,-1).join(' ') : '';
    }

    // DOB
    var dob = p.dob || '';
    if(dob && dob.length === 10){
      var dp = dob.split('-');
      var dy = document.getElementById('epDobY'); if(dy) dy.value = dp[0];
      var dm = document.getElementById('epDobM'); if(dm) dm.value = dp[1];
      var dd = document.getElementById('epDobD'); if(dd) dd.value = dp[2];
    } else {
      var dy = document.getElementById('epDobY'); if(dy) dy.value = '';
      var dm = document.getElementById('epDobM'); if(dm) dm.value = '';
      var dd = document.getElementById('epDobD'); if(dd) dd.value = '';
    }

    // Country + City
    var countryEl = document.getElementById('epCountry');
    if(countryEl) countryEl.value = p.country || '';
    epLoadCities(p.city || '');

    // Availability
    var avEl = document.getElementById('epAvail');
    if(avEl) avEl.value = p.avail || '';

    // Profession — load list and cache it
    var profEl = document.getElementById('epProfession');
    if(profEl){
      profEl.innerHTML = '<option value="">جاري التحميل…</option>';
      getProfessions()
        .then(function(list){
          _profList = list;
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
              var sel  = (p.profession && p.profession.id === pr.id) ? ' selected' : '';
              var icon = (pr.icon || 'briefcase').replace(/"/g,'');
              html += '<option value="' + pr.id + '"' + sel + ' data-icon="' + icon + '">' + pr.name_ar + '</option>';
            });
            html += '</optgroup>';
          });
          profEl.innerHTML = html;
          if(window.lucide && lucide.createIcons) lucide.createIcons();
        })
        .catch(function(){ profEl.innerHTML = '<option value="">تعذّر تحميل التخصصات</option>'; });
    }

    // Bio
    var bioEl = document.getElementById('epBio');
    if(bioEl) bioEl.value = p.bio || '';

    if(errEl) errEl.style.display = 'none';
    overlay.classList.add('open');
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  }

  // ── Inline field-error helpers ──
  var _CONTENT_MSG = 'لا يسمح باستخدام كلمات غير لائقة أو غير مهنية داخل هذا الحقل';

  function _showFieldErr(inputEl, errId, msg){
    var div = document.getElementById(errId);
    if(inputEl) inputEl.classList.add('ep-input-err');
    if(div){ div.textContent = msg || _CONTENT_MSG; div.classList.add('show'); }
    if(div) div.scrollIntoView({behavior:'smooth', block:'nearest'});
  }

  function _clearFieldErr(inputEl, errId){
    var div = document.getElementById(errId);
    if(inputEl) inputEl.classList.remove('ep-input-err');
    if(div){ div.textContent = ''; div.classList.remove('show'); }
  }

  function _clearAllFieldErrs(){
    ['epFirstName','epMidName','epLastName'].forEach(function(id){
      var el = document.getElementById(id); if(el) el.classList.remove('ep-input-err');
    });
    ['epNameErr','epBioErr'].forEach(function(id){
      var div = document.getElementById(id);
      if(div){ div.textContent=''; div.classList.remove('show'); }
    });
    var bio = document.getElementById('epBio');
    if(bio) bio.classList.remove('ep-input-err');
  }

  // Auto-clear name row when user edits and content is now clean
  function _checkNameErr(){
    ['epFirstName','epMidName','epLastName'].forEach(function(id){
      var el = document.getElementById(id);
      if(el && el.classList.contains('ep-input-err') && !window._scCheckProfessional(el.value)){
        el.classList.remove('ep-input-err');
      }
    });
    var anyBad = ['epFirstName','epMidName','epLastName'].some(function(id){
      var el = document.getElementById(id);
      return el && window._scCheckProfessional && window._scCheckProfessional(el.value);
    });
    if(!anyBad){
      var div = document.getElementById('epNameErr');
      if(div){ div.textContent=''; div.classList.remove('show'); }
    }
  }
  ['epFirstName','epMidName','epLastName'].forEach(function(id){
    var el = document.getElementById(id);
    if(el) el.addEventListener('input', _checkNameErr);
  });

  // Auto-clear bio error
  var _epBioInput = document.getElementById('epBio');
  if(_epBioInput) _epBioInput.addEventListener('input', function(){
    if(!window._scCheckProfessional || !window._scCheckProfessional(_epBioInput.value))
      _clearFieldErr(_epBioInput, 'epBioErr');
  });

  function closeModal(){
    overlay.classList.remove('open');
    _clearAllFieldErrs();
    if(errEl) errEl.style.display = 'none';
  }

  editBtn.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', function(e){ if(e.target === overlay) closeModal(); });

  // ── Save ──
  saveBtn.addEventListener('click', function(){
    var uid = window._scUserId;
    if(!uid){
      if(errEl){ errEl.textContent = 'خطأ: لم يتم التعرف على المستخدم'; errEl.style.display = 'block'; }
      return;
    }

    var first = ((document.getElementById('epFirstName')||{}).value||'').trim();
    var mid   = ((document.getElementById('epMidName')  ||{}).value||'').trim();
    var last  = ((document.getElementById('epLastName') ||{}).value||'').trim();
    var fullName = [first, mid, last].filter(Boolean).join(' ');

    var dobY = ((document.getElementById('epDobY')||{}).value||'').trim();
    var dobM = ((document.getElementById('epDobM')||{}).value||'').trim();
    var dobD = ((document.getElementById('epDobD')||{}).value||'').trim();
    var dob  = (dobY && dobM && dobD) ? (dobY + '-' + dobM + '-' + dobD) : '';

    var country = ((document.getElementById('epCountry')   ||{}).value||'').trim();
    var city    = ((document.getElementById('epCity')      ||{}).value||'').trim();
    var avail   = ((document.getElementById('epAvail')     ||{}).value||'').trim();
    var profVal = ((document.getElementById('epProfession')||{}).value||'').trim();
    var bioVal  = ((document.getElementById('epBio')       ||{}).value||'').trim();

    var payload = { bio: bioVal };
    // Send name parts — backend builds full_name automatically
    payload.first_name  = first;
    payload.middle_name = mid;
    payload.last_name   = last;
    payload.dob     = dob     || null;
    payload.country = country || null;
    payload.city    = city    || null;
    payload.avail   = avail   || null;
    if(profVal) payload.profession_id = parseInt(profVal, 10);

    // Professional content guard — clear previous state, then mark ALL offending fields
    _clearAllFieldErrs();
    var _contentErr = false;
    var _checkFields = [
      {v: first,  inputId: 'epFirstName', errId: 'epNameErr'},
      {v: mid,    inputId: 'epMidName',   errId: 'epNameErr'},
      {v: last,   inputId: 'epLastName',  errId: 'epNameErr'},
      {v: bioVal, inputId: 'epBio',       errId: 'epBioErr'}
    ];
    var _lastErrMsg = _CONTENT_MSG;
    for(var _ei=0; _ei<_checkFields.length; _ei++){
      var _ef = _checkFields[_ei];
      var _pcErr = window._scCheckProfessional && window._scCheckProfessional(_ef.v);
      if(_pcErr){
        var _inp = document.getElementById(_ef.inputId);
        if(_inp) _inp.classList.add('ep-input-err');
        var _div = document.getElementById(_ef.errId);
        if(_div){ _div.textContent = _pcErr; _div.classList.add('show'); }
        _lastErrMsg = _pcErr;
        _contentErr = true;
      }
    }
    if(_contentErr){
      var _fe = document.querySelector('#epOverlay .ep-field-err.show');
      if(_fe) _fe.scrollIntoView({behavior:'smooth', block:'nearest'});
      if(window.toast) window.toast(_lastErrMsg);
      return;
    }

    if(errEl) errEl.style.display = 'none';
    saveBtn.disabled = true;
    saveBtn.textContent = 'جاري الحفظ…';

    updateProfile(uid, payload)
      .then(function(res){
        if(!res.ok){
          var _det = res.data && res.data.detail;
          var msg = (_det && typeof _det === 'object' && _det.message)
            ? _det.message
            : (typeof _det === 'string' ? _det : 'حدث خطأ أثناء الحفظ');
          if(window.toast) window.toast(msg);
          if(errEl){ errEl.textContent = msg; errEl.style.display = 'block'; }
          return;
        }
        // 1. Close modal + toast immediately
        closeModal();
        if(window.toast) window.toast('تم حفظ التغييرات بنجاح');
        // 2. Confirmed Local Update — no waiting for re-fetch
        applyLocalUpdate(payload);
        // 3. Background re-fetch for full sync (score not included, runs separately)
        getProfile(_scProfileKey)
          .then(function(freshRes){
            if(freshRes && window.renderProfile) window.renderProfile(freshRes);
            if(window.lucide && lucide.createIcons) lucide.createIcons();
          })
          .catch(function(){ /* silent — local update already applied */ });
      })
      .catch(function(){
        var _msg = 'خطأ في الاتصال بالخادم';
        if(window.toast) window.toast(_msg);
        if(errEl){ errEl.textContent = _msg; errEl.style.display = 'block'; }
      })
      .finally(function(){
        saveBtn.disabled = false;
        saveBtn.textContent = 'حفظ التغييرات';
      });
  });
})();
