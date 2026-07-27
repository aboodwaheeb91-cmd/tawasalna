// profile-v2.edit.js — Edit Profile Modal Phase 1 (Correction Round)
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.render.js, profile-v2.utils.js

(function(){
  var overlay    = document.getElementById('epOverlay');
  var closeBtn   = document.getElementById('epClose');
  var cancelBtn  = document.getElementById('epCancelBtn');
  var saveBtn    = document.getElementById('epSaveBtn');
  var editBtn    = document.getElementById('scEditProfileBtn');
  var errEl      = document.getElementById('epErr');

  if(!overlay || !editBtn) return;

  // cached professions list
  var _profList = [];
  var _profListLoaded = false;  // true once hydration completes with a loaded list

  // ── DS-FRM async race guard (§20) ──
  // Incremented on open AND on close. Async callbacks capture the generation at
  // call-time and bail if it no longer matches the current value.
  var _editSession = 0;

  // ── Dirty State snapshot (§14) ──
  var _snapshot = null;

  // ── In-flight guard (§13) ──
  var _inFlight = false;

  // ── Legacy name mode (§1) ──
  // true when profile has full_name but no first_name/last_name.
  var _legacyMode = false;

  // ── DOB year/day option population ──
  (function(){
    var d = document.getElementById('epDobD');
    if(!d) return;
    for(var i=1; i<=31; i++){
      var o = document.createElement('option');
      o.value = String(i).padStart(2,'0'); o.text = i;
      d.appendChild(o);
    }
  })();

  (function(){
    var y = document.getElementById('epDobY');
    if(!y) return;
    var cur = new Date().getFullYear();
    for(var i = cur - 15; i >= 1940; i--){
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
    var entry  = window.TW && TW.countryEntry ? TW.countryEntry(cc) : null;
    var cities = entry ? (TW.CITIES[entry.name_ar] || []) : [];
    if(!cities.length){
      if(cityWrap) cityWrap.style.display = 'none';
      var ph = document.createElement('option'); ph.value = ''; ph.text = '— اختر المدينة —';
      cityEl.innerHTML = ''; cityEl.appendChild(ph);
      if(window.scSelectInit) scSelectInit();
      return;
    }
    cityEl.innerHTML = '';
    var ph2 = document.createElement('option'); ph2.value = ''; ph2.text = '— اختر المدينة —';
    cityEl.appendChild(ph2);
    cities.forEach(function(c){
      var o = document.createElement('option');
      o.value = c; o.text = c;
      if(selectedCity && c === selectedCity) o.selected = true;
      cityEl.appendChild(o);
    });
    if(cityWrap) cityWrap.style.display = 'block';
    if(window.scSelectInit) scSelectInit();
  };

  // ── DS-VAL field error helpers (§8/§16) ──
  var _CONTENT_MSG = 'لا يسمح باستخدام كلمات غير لائقة أو غير مهنية داخل هذا الحقل';

  function _setAriaInvalid(inputEl, errEl, msg){
    if(inputEl){
      inputEl.classList.add('ep-input-err');
      inputEl.setAttribute('aria-invalid', 'true');
    }
    if(errEl){ errEl.textContent = msg || _CONTENT_MSG; errEl.classList.add('show'); }
    if(errEl) errEl.scrollIntoView({behavior:'smooth', block:'nearest'});
  }

  function _clearAriaInvalid(inputEl, errEl){
    if(inputEl){
      inputEl.classList.remove('ep-input-err');
      inputEl.setAttribute('aria-invalid', 'false');
    }
    if(errEl){ errEl.textContent = ''; errEl.classList.remove('show'); }
  }

  function _setDobAriaInvalid(msg){
    ['epDobD','epDobM','epDobY'].forEach(function(id){
      var el = document.getElementById(id);
      if(el) el.setAttribute('aria-invalid', 'true');
    });
    var dobErrEl = document.getElementById('epDobErr');
    if(dobErrEl){ dobErrEl.textContent = msg || 'تاريخ ميلاد غير صحيح'; dobErrEl.classList.add('show'); }
  }

  function _clearDobAriaInvalid(){
    ['epDobD','epDobM','epDobY'].forEach(function(id){
      var el = document.getElementById(id);
      if(el) el.setAttribute('aria-invalid', 'false');
    });
    var dobErrEl = document.getElementById('epDobErr');
    if(dobErrEl){ dobErrEl.textContent = ''; dobErrEl.classList.remove('show'); }
  }

  function _clearAllFieldErrs(){
    ['epFirstName','epMidName','epLastName'].forEach(function(id){
      var el = document.getElementById(id);
      if(el){ el.classList.remove('ep-input-err'); el.setAttribute('aria-invalid','false'); }
    });
    var nameErr = document.getElementById('epNameErr');
    if(nameErr){ nameErr.textContent=''; nameErr.classList.remove('show'); }
    var bioEl   = document.getElementById('epShortBio');
    var bioErr  = document.getElementById('epShortBioErr');
    if(bioEl){ bioEl.classList.remove('ep-input-err'); bioEl.setAttribute('aria-invalid','false'); }
    if(bioErr){ bioErr.textContent=''; bioErr.classList.remove('show'); }
    _clearDobAriaInvalid();
  }

  // ── Helpers: set aria-required on name inputs dynamically ──
  function _setNameRequired(required){
    ['epFirstName','epLastName'].forEach(function(id){
      var el = document.getElementById(id);
      if(el) el.setAttribute('aria-required', required ? 'true' : 'false');
    });
  }

  // ── Migration detection: any of first/mid/last is typed → migration started ──
  function _isMigrating(){
    var first = ((document.getElementById('epFirstName')||{}).value||'').trim();
    var mid   = ((document.getElementById('epMidName')  ||{}).value||'').trim();
    var last  = ((document.getElementById('epLastName') ||{}).value||'').trim();
    return !!(first || mid || last);
  }

  // Auto-clear name errors on input
  ['epFirstName','epMidName','epLastName'].forEach(function(id){
    var el = document.getElementById(id);
    if(!el) return;
    el.addEventListener('input', function(){
      // In legacy mode, once user starts typing → migration → fields become required
      if(_legacyMode && _isMigrating()){
        _setNameRequired(true);
      } else if(_legacyMode && !_isMigrating()){
        _setNameRequired(false);
      }
      if(el.classList.contains('ep-input-err') && (!window._scCheckProfessional || !window._scCheckProfessional(el.value))){
        el.classList.remove('ep-input-err');
        el.setAttribute('aria-invalid','false');
      }
      var anyBad = ['epFirstName','epMidName','epLastName'].some(function(i){
        var e = document.getElementById(i);
        return e && window._scCheckProfessional && window._scCheckProfessional(e.value);
      });
      if(!anyBad){
        var div = document.getElementById('epNameErr');
        if(div){ div.textContent=''; div.classList.remove('show'); }
      }
      // Clear required error once user types the required field
      var first = ((document.getElementById('epFirstName')||{}).value||'').trim();
      var last  = ((document.getElementById('epLastName') ||{}).value||'').trim();
      if(first){
        var fn = document.getElementById('epFirstName');
        if(fn){ fn.classList.remove('ep-input-err'); fn.setAttribute('aria-invalid','false'); }
      }
      if(last){
        var ln = document.getElementById('epLastName');
        if(ln){ ln.classList.remove('ep-input-err'); ln.setAttribute('aria-invalid','false'); }
        var nameErr = document.getElementById('epNameErr');
        if(nameErr && nameErr.textContent.indexOf('مطلوب') !== -1){ nameErr.textContent=''; nameErr.classList.remove('show'); }
      }
    });
  });

  var _epShortBioInput = document.getElementById('epShortBio');
  if(_epShortBioInput) _epShortBioInput.addEventListener('input', function(){
    if(!window._scCheckProfessional || !window._scCheckProfessional(_epShortBioInput.value))
      _clearAriaInvalid(_epShortBioInput, document.getElementById('epShortBioErr'));
  });

  // ── DS-FRM Reset (§5/§19) ──
  function _resetForm(){
    ['epFirstName','epMidName','epLastName'].forEach(function(id){
      var el = document.getElementById(id); if(el) el.value = '';
    });
    ['epDobD','epDobM','epDobY'].forEach(function(id){
      var el = document.getElementById(id); if(el) el.value = '';
    });
    var avEl = document.getElementById('epAvail'); if(avEl) avEl.value = '';
    var sh   = document.getElementById('epShortBio'); if(sh) sh.value = '';
    var profEl = document.getElementById('epProfession');
    if(profEl){
      profEl.innerHTML = '';
      var ph = document.createElement('option'); ph.value=''; ph.text='جاري التحميل…';
      profEl.appendChild(ph);
    }
    // Legacy row hidden by default; name row visible
    var legRow = document.getElementById('epLegacyNameRow');
    if(legRow) legRow.style.display = 'none';
    var nameRow = document.getElementById('epNameRow');
    if(nameRow) nameRow.style.display = '';
    _legacyMode = false;
    _profListLoaded = false;
    _setNameRequired(true);
    _clearAllFieldErrs();
    if(errEl){ errEl.textContent=''; errEl.style.display='none'; }
    _setSaveBtnNormal();
  }

  // ── BTN-18 save button loading state (§12) ──
  function _setSaveBtnLoading(){
    if(!saveBtn) return;
    saveBtn.disabled = true;
    saveBtn.setAttribute('aria-busy','true');
    saveBtn.classList.add('ep-save--loading');
    saveBtn.dataset.origText = saveBtn.textContent;
    saveBtn.textContent = '';
  }
  function _setSaveBtnNormal(){
    if(!saveBtn) return;
    saveBtn.disabled = false;
    saveBtn.setAttribute('aria-busy','false');
    saveBtn.classList.remove('ep-save--loading');
    saveBtn.textContent = saveBtn.dataset.origText || 'حفظ التغييرات';
  }

  // ── In-flight: lock/unlock Cancel + X (§9) ──
  function _lockControls(){
    if(cancelBtn){ cancelBtn.disabled = true; cancelBtn.setAttribute('aria-disabled','true'); }
    if(closeBtn){ closeBtn.disabled = true; closeBtn.setAttribute('aria-disabled','true'); }
  }
  function _unlockControls(){
    if(cancelBtn){ cancelBtn.disabled = false; cancelBtn.setAttribute('aria-disabled','false'); }
    if(closeBtn){ closeBtn.disabled = false; closeBtn.setAttribute('aria-disabled','false'); }
  }

  // ── Profession options via DOM APIs (§10) ──
  function _buildProfessionOptions(profEl, list, currentProfession){
    var groups = {};
    list.forEach(function(pr){
      var g = pr.category_group || 'أخرى';
      if(!groups[g]) groups[g] = [];
      groups[g].push(pr);
    });
    profEl.innerHTML = '';
    var placeholder = document.createElement('option');
    placeholder.value = ''; placeholder.text = '— اختر التخصص —';
    profEl.appendChild(placeholder);
    Object.keys(groups).forEach(function(g){
      var og = document.createElement('optgroup');
      og.label = g;
      groups[g].forEach(function(pr){
        var opt = document.createElement('option');
        opt.value = String(pr.id);
        opt.text  = pr.name_ar;
        opt.dataset.icon = (pr.icon || 'briefcase').replace(/"/g,'');
        if(currentProfession && currentProfession.id === pr.id) opt.selected = true;
        og.appendChild(opt);
      });
      profEl.appendChild(og);
    });
  }

  // ── DS-FRM Hydration (§6/§19) ──
  function _hydrateForm(p, profList, session){
    if(_editSession !== session) return;  // stale — abort (§20 + §8 close invalidation)

    // Detect legacy name mode (§1)
    var hasStructured = !!(p.first_name && p.last_name);
    _legacyMode = !hasStructured && !!(p.full_name);

    var legRow  = document.getElementById('epLegacyNameRow');
    var legText = document.getElementById('epLegacyNameText');

    if(_legacyMode){
      // Show the info note — name row stays visible with empty fields
      if(legRow){ legRow.style.display = ''; }
      if(legText) legText.textContent = p.full_name || '';
      // Fields start empty; aria-required false until migration starts
      _setNameRequired(false);
    } else {
      if(legRow){ legRow.style.display = 'none'; }
      var fn = document.getElementById('epFirstName');
      var mn = document.getElementById('epMidName');
      var ln = document.getElementById('epLastName');
      if(fn) fn.value = p.first_name  || '';
      if(mn) mn.value = p.middle_name || '';
      if(ln) ln.value = p.last_name   || '';
      _setNameRequired(true);
    }

    // DOB
    var dob = p.dob || '';
    if(dob && dob.length === 10){
      var dp = dob.split('-');
      var dy = document.getElementById('epDobY'); if(dy) dy.value = dp[0];
      var dm = document.getElementById('epDobM'); if(dm) dm.value = dp[1];
      var dd = document.getElementById('epDobD'); if(dd) dd.value = dp[2];
    }

    // Country + City
    var countryEl = document.getElementById('epCountry');
    if(countryEl && window.TW && TW.fillCountries){
      TW.fillCountries(countryEl, '— اختر البلد —', { valueMode: 'code', withFlags: true, force: true });
    }
    if(countryEl) countryEl.value = p.country || '';
    epLoadCities(p.city || '');

    // Availability
    var avEl = document.getElementById('epAvail');
    if(avEl) avEl.value = p.avail || '';

    // Profession (§10 — DOM APIs)
    var profEl = document.getElementById('epProfession');
    if(profEl && profList && profList.length){
      _buildProfessionOptions(profEl, profList, p.profession || null);
    } else if(profEl && profList){
      var errOpt = document.createElement('option');
      errOpt.value = ''; errOpt.text = '— اختر التخصص —';
      profEl.innerHTML = ''; profEl.appendChild(errOpt);
    }

    // Short bio
    var shortBioEl = document.getElementById('epShortBio');
    if(shortBioEl) shortBioEl.value = p.short_bio || '';

    _profListLoaded = true;

    // Dirty State snapshot (§14) — capture after all fields are set
    _snapshot = _captureSnapshot();

    if(window.scSelectInit) scSelectInit();
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  }

  // ── Dirty State snapshot capture (§14) ──
  function _captureSnapshot(){
    return {
      firstName:  ((document.getElementById('epFirstName')||{}).value||'').trim(),
      midName:    ((document.getElementById('epMidName')  ||{}).value||'').trim(),
      lastName:   ((document.getElementById('epLastName') ||{}).value||'').trim(),
      dobY:       ((document.getElementById('epDobY')||{}).value||'').trim(),
      dobM:       ((document.getElementById('epDobM')||{}).value||'').trim(),
      dobD:       ((document.getElementById('epDobD')||{}).value||'').trim(),
      country:    ((document.getElementById('epCountry')   ||{}).value||'').trim(),
      city:       ((document.getElementById('epCity')      ||{}).value||'').trim(),
      avail:      ((document.getElementById('epAvail')     ||{}).value||'').trim(),
      profId:     ((document.getElementById('epProfession')||{}).value||'').trim(),
      shortBio:   ((document.getElementById('epShortBio')||{}).value||'').trim(),
    };
  }

  function _isDirty(){
    if(!_snapshot) return false;
    var cur = _captureSnapshot();
    return (
      cur.firstName !== _snapshot.firstName ||
      cur.midName   !== _snapshot.midName   ||
      cur.lastName  !== _snapshot.lastName  ||
      cur.dobY      !== _snapshot.dobY      ||
      cur.dobM      !== _snapshot.dobM      ||
      cur.dobD      !== _snapshot.dobD      ||
      cur.country   !== _snapshot.country   ||
      cur.city      !== _snapshot.city      ||
      cur.avail     !== _snapshot.avail     ||
      cur.profId    !== _snapshot.profId    ||
      cur.shortBio  !== _snapshot.shortBio
    );
  }
  window._epIsDirty = _isDirty;

  // ── Open Modal (§19) ──
  function openModal(){
    var session = ++_editSession;   // advance generation before any async work (§20/§8)
    _resetForm();
    overlay.classList.add('open');

    var p = window._scProfile || {};

    var profEl = document.getElementById('epProfession');
    if(profEl && (!_profList || !_profList.length)){
      getProfessions()
        .then(function(list){
          if(_editSession !== session) return;  // stale session — abort
          _profList = list;
          _hydrateForm(p, list, session);
        })
        .catch(function(){
          if(_editSession !== session) return;
          if(profEl){
            profEl.innerHTML = '';
            var errOpt = document.createElement('option');
            errOpt.value = ''; errOpt.text = 'تعذّر تحميل التخصصات';
            profEl.appendChild(errOpt);
          }
          _hydrateForm(p, [], session);
        });
    } else {
      _hydrateForm(p, _profList, session);
    }
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  }

  // ── Close Modal (§19/§8) ──
  function closeModal(){
    if(_inFlight) return;   // §13: lock close during save
    ++_editSession;         // §8: invalidate any pending async work (open session → closed)
    overlay.classList.remove('open');
    _clearAllFieldErrs();
    if(errEl){ errEl.textContent=''; errEl.style.display='none'; }
  }

  editBtn.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', function(e){ if(e.target === overlay) closeModal(); });

  // ── Canonical profile update (§6) ──
  // Uses server-confirmed response values — request payload is never used as source.
  function applyCanonicalProfile(profile){
    if(!profile) return;

    // Update in-memory canonical state
    if(window._scProfile){
      if(profile.full_name  !== undefined) window._scProfile.full_name   = profile.full_name;
      if(profile.first_name !== undefined) window._scProfile.first_name  = profile.first_name;
      if(profile.middle_name!== undefined) window._scProfile.middle_name = profile.middle_name;
      if(profile.last_name  !== undefined) window._scProfile.last_name   = profile.last_name;
      if(profile.short_bio  !== undefined) window._scProfile.short_bio   = profile.short_bio;
      if(profile.dob        !== undefined) window._scProfile.dob         = profile.dob;
      if(profile.country    !== undefined) window._scProfile.country     = profile.country;
      if(profile.city       !== undefined) window._scProfile.city        = profile.city;
      if(profile.avail      !== undefined) window._scProfile.avail       = profile.avail;
      // profession: update from server canonical response (never from payload)
      if('profession_id' in profile){
        if(profile.profession_id === null || profile.profession_id === undefined){
          window._scProfile.profession = null;
        } else if(window._scProfile.profession && window._scProfile.profession.id !== profile.profession_id){
          // will be resolved below from _profList
        }
      }
    }

    // Name (§7) — use canonical full_name from server
    if(profile.full_name){
      var nameEl = document.getElementById('scName');
      if(nameEl) nameEl.textContent = profile.full_name;
      requestAnimationFrame(function(){ if(window._fitName) window._fitName(); });
    }

    // Short bio (header)
    if(profile.short_bio !== undefined){
      var headerBioEl = document.getElementById('scBio');
      if(headerBioEl) headerBioEl.textContent = profile.short_bio || '';
      requestAnimationFrame(function(){
        if(headerBioEl){
          var moreBtn = document.getElementById('scBioMore');
          if(moreBtn) moreBtn.style.display = headerBioEl.scrollHeight > headerBioEl.clientHeight + 2 ? 'inline-block' : 'none';
        }
      });
    }

    // DOB → age display
    if('dob' in profile){
      if(profile.dob){
        var birth = new Date(profile.dob);
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
        var ageEl2 = document.getElementById('scAge');
        if(ageEl2) ageEl2.style.display = 'none';
      }
    }

    // Country / city location block
    if('country' in profile && window._scProfile) window._scProfile.country = profile.country || '';
    if('city'    in profile && window._scProfile) window._scProfile.city    = profile.city    || '';
    (function(){
      var _p   = window._scProfile || {};
      var _loc = document.getElementById('scLoc');
      if(!_loc || !window._buildLocText) return;
      var _lt = window._buildLocText(_p.country || '', _p.city || '', _p.location || '');
      if(_lt){
        _loc.innerHTML = '';
        if(window.TW && TW.countryFlagEl && _p.country){
          var _fl = TW.countryFlagEl(_p.country);
          if(_fl) _loc.appendChild(_fl);
        }
        var _pin = document.createElement('i');
        _pin.setAttribute('data-lucide','map-pin'); _pin.className = 'ico-sm';
        _loc.appendChild(_pin);
        var _ltSp = document.createElement('span'); _ltSp.textContent = _lt;
        _loc.appendChild(_ltSp);
        _loc.style.display = 'inline-flex';
        _loc.style.alignItems = 'center';
        _loc.style.gap = '4px';
      } else {
        _loc.innerHTML = ''; _loc.style.display = '';
      }
      if(window.lucide && lucide.createIcons) lucide.createIcons();
    })();

    // Availability dot
    if(profile.avail !== undefined && window._renderAvailDot)
      window._renderAvailDot(profile.avail || null, true);

    // Profession — from server response canonical profession_id (§7: no payload contamination)
    if('profession_id' in profile){
      var titleEl = document.getElementById('scTitle');
      if(profile.profession_id && _profList.length){
        var prof = null;
        for(var i=0; i<_profList.length; i++){
          if(_profList[i].id === profile.profession_id){ prof = _profList[i]; break; }
        }
        if(prof){
          if(titleEl){
            titleEl.innerHTML = '<i data-lucide="' + (prof.icon || 'briefcase') + '" class="ico-sm"></i> ';
            var profSpan = document.createElement('span'); profSpan.textContent = prof.name_ar;
            titleEl.appendChild(profSpan);
          }
          if(window._scProfile) window._scProfile.profession = prof;
          if(window.lucide && lucide.createIcons) lucide.createIcons();
        }
      } else if(!profile.profession_id){
        // Cleared — show empty state
        if(titleEl) titleEl.innerHTML = '';
        if(window._scProfile) window._scProfile.profession = null;
      }
    }
  }

  // ── Route field-level error from 422 response to correct error element ──
  function _routeFieldError(detail){
    var code    = detail.code  || '';
    var field   = detail.field || '';
    var message = detail.error || detail.message || 'حدث خطأ في التحقق من البيانات';
    if(code === 'first_name_required' || code === 'last_name_required' || field === 'first_name' || field === 'last_name' || field === 'name'){
      var nameErrEl = document.getElementById('epNameErr');
      var inputId = (code === 'first_name_required' || field === 'first_name') ? 'epFirstName' : 'epLastName';
      _setAriaInvalid(document.getElementById(inputId), nameErrEl, message);
    } else if(code.indexOf('dob') === 0 || field === 'dob'){
      _setDobAriaInvalid(message);
    } else {
      if(errEl){ errEl.textContent = message; errEl.style.display = 'block'; }
    }
    if(window.toast) window.toast(message);
  }

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
    var dobY  = ((document.getElementById('epDobY')||{}).value||'').trim();
    var dobM  = ((document.getElementById('epDobM')||{}).value||'').trim();
    var dobD  = ((document.getElementById('epDobD')||{}).value||'').trim();
    var country    = ((document.getElementById('epCountry')   ||{}).value||'').trim();
    var city       = ((document.getElementById('epCity')      ||{}).value||'').trim();
    var avail      = ((document.getElementById('epAvail')     ||{}).value||'').trim();
    var profVal    = ((document.getElementById('epProfession')||{}).value||'').trim();
    var shortBioVal= ((document.getElementById('epShortBio')||{}).value||'').trim();

    _clearAllFieldErrs();
    if(errEl){ errEl.textContent=''; errEl.style.display='none'; }

    var hasErr = false;

    // Professional content guard
    var _checkFields = [
      {v: first,       inputId: 'epFirstName', errId: 'epNameErr'},
      {v: mid,         inputId: 'epMidName',   errId: 'epNameErr'},
      {v: last,        inputId: 'epLastName',  errId: 'epNameErr'},
      {v: shortBioVal, inputId: 'epShortBio',  errId: 'epShortBioErr'}
    ];
    var _lastErrMsg = _CONTENT_MSG;
    for(var _ei=0; _ei<_checkFields.length; _ei++){
      var _ef = _checkFields[_ei];
      var _pcErr = window._scCheckProfessional && window._scCheckProfessional(_ef.v);
      if(_pcErr){
        var _inp = document.getElementById(_ef.inputId);
        var _div = document.getElementById(_ef.errId);
        _setAriaInvalid(_inp, _div, _pcErr);
        _lastErrMsg = _pcErr;
        hasErr = true;
      }
    }
    if(hasErr){
      var _fe = document.querySelector('#epOverlay .ep-field-err.show');
      if(_fe) _fe.scrollIntoView({behavior:'smooth', block:'nearest'});
      if(window.toast) window.toast(_lastErrMsg);
      return;
    }

    // DS-VAL: name required fields
    // Legacy mode untouched: skip entirely (no name mutation)
    // Legacy mode + migration started (any of first/mid/last typed): require first + last
    // Structured mode: always require first + last
    var _nameMutation = !_legacyMode || _isMigrating();
    if(_nameMutation){
      var nameErrEl = document.getElementById('epNameErr');
      if(!first){
        _setAriaInvalid(document.getElementById('epFirstName'), nameErrEl, 'الاسم الأول مطلوب');
        hasErr = true;
      }
      if(!last){
        if(!hasErr){
          _setAriaInvalid(document.getElementById('epLastName'), nameErrEl, 'اسم العائلة مطلوب');
        } else {
          var ln = document.getElementById('epLastName');
          if(ln){ ln.classList.add('ep-input-err'); ln.setAttribute('aria-invalid','true'); }
        }
        hasErr = true;
      }
    }
    if(hasErr) return;

    // DS-VAL: DOB partial completion — all 3 or none
    var dobFilled = [dobY, dobM, dobD].filter(Boolean).length;
    if(dobFilled > 0 && dobFilled < 3){
      _setDobAriaInvalid('يرجى اختيار اليوم والشهر والسنة كاملاً');
      return;
    }
    var dob = (dobY && dobM && dobD) ? (dobY + '-' + dobM + '-' + dobD) : null;

    // Build payload (§3 Tri-state: send null = CLEAR, omit = no change, value = set)
    var payload = {};

    // short_bio: always send (user can clear it with empty textarea → null)
    payload.short_bio = shortBioVal || null;

    // Name — only include when mutation started
    if(_nameMutation){
      payload.first_name  = first;
      payload.middle_name = mid  || null;
      payload.last_name   = last;
    }

    // DOB: null = clear
    payload.dob     = dob;
    // Location: null = clear
    payload.country = country || null;
    payload.city    = city    || null;
    // Availability: null = clear
    payload.avail   = avail   || null;

    // Profession: null = clear (only when list is loaded — prevents clearing on async race)
    if(_profListLoaded){
      payload.profession_id = profVal ? parseInt(profVal, 10) : null;
    } else if(profVal){
      payload.profession_id = parseInt(profVal, 10);
    }
    // If _profListLoaded is false and profVal is empty: omit profession_id (no change)

    // BTN-18 loading (§12) + in-flight lock (§13) + controls lock (§9)
    _inFlight = true;
    _setSaveBtnLoading();
    _lockControls();

    updateProfile(uid, payload)
      .then(function(res){
        if(!res.ok){
          var _det = res.data && res.data.detail;
          if(_det && typeof _det === 'object' && _det.code){
            // Typed ProfileValidationError — route to correct field
            _routeFieldError(_det);
          } else {
            var msg = (_det && typeof _det === 'object' && _det.message)
              ? _det.message
              : (typeof _det === 'string' ? _det : 'حدث خطأ أثناء الحفظ');
            if(window.toast) window.toast(msg);
            if(errEl){ errEl.textContent = msg; errEl.style.display = 'block'; }
          }
          return;
        }
        // 1. Release lock + close + toast
        _inFlight = false;
        _unlockControls();
        closeModal();
        if(window.toast) window.toast('تم حفظ التغييرات بنجاح');
        // 2. Canonical update from server response (§6 — no payload contamination)
        var canonicalProfile = (res.data && res.data.profile) ? res.data.profile : null;
        if(canonicalProfile) applyCanonicalProfile(canonicalProfile);
        if(window._updateCompletion) window._updateCompletion();
        // 3. Background re-fetch for full sync — log on failure (no silent catch)
        getProfile(_scProfileKey)
          .then(function(freshRes){
            if(freshRes && window.renderProfile) window.renderProfile(freshRes);
            if(window.lucide && lucide.createIcons) lucide.createIcons();
          })
          .catch(function(syncErr){
            console.warn('[edit-profile] background sync failed after successful save:', syncErr);
          });
      })
      .catch(function(){
        var _msg = 'خطأ في الاتصال بالخادم';
        if(window.toast) window.toast(_msg);
        if(errEl){ errEl.textContent = _msg; errEl.style.display = 'block'; }
      })
      .finally(function(){
        _inFlight = false;
        _unlockControls();
        _setSaveBtnNormal();
      });
  });
})();
