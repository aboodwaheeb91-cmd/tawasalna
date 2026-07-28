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

  // ── Name error ownership (§2) ──
  // Tracks which name field currently owns the server error shown in #epNameErr.
  // 'first_name'|'last_name'|'middle_name'|'name'|null
  var _nameErrorOwner = null;

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

  // ── Select error helpers — sets aria-invalid on native; MutationObserver in tw-select.js propagates to trigger ──
  function _setSelectErr(selectId, errElId, msg){
    var sel = document.getElementById(selectId);
    var err = document.getElementById(errElId);
    if(sel) sel.setAttribute('aria-invalid','true');
    if(err){ err.textContent = msg || _CONTENT_MSG; err.classList.add('show'); }
    if(err) err.scrollIntoView({behavior:'smooth',block:'nearest'});
  }
  function _clearSelectErr(selectId, errElId){
    var sel = document.getElementById(selectId);
    var err = document.getElementById(errElId);
    if(sel) sel.setAttribute('aria-invalid','false');
    if(err){ err.textContent=''; err.classList.remove('show'); }
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
    _nameErrorOwner = null;
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
    _clearSelectErr('epCountry',    'epCountryErr');
    _clearSelectErr('epCity',       'epCityErr');
    _clearSelectErr('epAvail',      'epAvailErr');
    _clearSelectErr('epProfession', 'epProfErr');
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
        // Clear nameErr only when _nameErrorOwner is null (content-violation message, safe to auto-clear)
        // If _nameErrorOwner is set, the error is from the server — only clear when the owner field is filled
        var div = document.getElementById('epNameErr');
        if(div && div.textContent && _nameErrorOwner === null){
          div.textContent=''; div.classList.remove('show');
        }
      }
      // Clear field error once user provides a value for the field that owns the server error
      var first = ((document.getElementById('epFirstName')||{}).value||'').trim();
      var mid2  = ((document.getElementById('epMidName')  ||{}).value||'').trim();
      var last  = ((document.getElementById('epLastName') ||{}).value||'').trim();
      if(first){
        var fn = document.getElementById('epFirstName');
        if(fn){ fn.classList.remove('ep-input-err'); fn.setAttribute('aria-invalid','false'); }
        if(_nameErrorOwner === 'first_name'){
          var _ne1 = document.getElementById('epNameErr');
          if(_ne1){ _ne1.textContent=''; _ne1.classList.remove('show'); }
          _nameErrorOwner = null;
        }
      }
      if(mid2 && _nameErrorOwner === 'middle_name'){
        var mn2 = document.getElementById('epMidName');
        if(mn2){ mn2.classList.remove('ep-input-err'); mn2.setAttribute('aria-invalid','false'); }
        var _ne2 = document.getElementById('epNameErr');
        if(_ne2){ _ne2.textContent=''; _ne2.classList.remove('show'); }
        _nameErrorOwner = null;
      }
      if(last){
        var ln = document.getElementById('epLastName');
        if(ln){ ln.classList.remove('ep-input-err'); ln.setAttribute('aria-invalid','false'); }
        if(_nameErrorOwner === 'last_name'){
          var _ne3 = document.getElementById('epNameErr');
          if(_ne3){ _ne3.textContent=''; _ne3.classList.remove('show'); }
          _nameErrorOwner = null;
        }
      }
    });
  });

  var _epShortBioInput = document.getElementById('epShortBio');
  if(_epShortBioInput) _epShortBioInput.addEventListener('input', function(){
    if(!window._scCheckProfessional || !window._scCheckProfessional(_epShortBioInput.value))
      _clearAriaInvalid(_epShortBioInput, document.getElementById('epShortBioErr'));
  });

  // Field-specific server error lifetime for custom selects (Item 5 — SEL-10/DS-VAL)
  // tw-select.js dispatches native change event on selection; clears only that field's error
  [
    {id:'epCountry',    errId:'epCountryErr'},
    {id:'epCity',       errId:'epCityErr'},
    {id:'epAvail',      errId:'epAvailErr'},
    {id:'epProfession', errId:'epProfErr'},
  ].forEach(function(f){
    var el = document.getElementById(f.id);
    if(!el) return;
    el.addEventListener('change', function(){ _clearSelectErr(f.id, f.errId); });
  });

  // ── DS-FRM Reset (§5/§19) ──
  function _resetForm(){
    ['epFirstName','epMidName','epLastName'].forEach(function(id){
      var el = document.getElementById(id); if(el) el.value = '';
    });
    ['epDobD','epDobM','epDobY'].forEach(function(id){
      var el = document.getElementById(id); if(el) el.value = '';
    });
    // Country + city reset
    var countryEl = document.getElementById('epCountry');
    if(countryEl) countryEl.value = '';
    var cityEl = document.getElementById('epCity');
    if(cityEl){
      cityEl.innerHTML = '';
      var phCity = document.createElement('option'); phCity.value=''; phCity.text='— اختر المدينة —';
      cityEl.appendChild(phCity);
    }
    var cityWrap = document.getElementById('epCityWrap');
    if(cityWrap) cityWrap.style.display = 'none';
    var avEl = document.getElementById('epAvail'); if(avEl) avEl.value = '';
    var sh   = document.getElementById('epShortBio'); if(sh) sh.value = '';
    // Profession transient state reset — disabled until list loads (Item 5)
    var profEl = document.getElementById('epProfession');
    if(profEl){
      profEl.innerHTML = '';
      var ph = document.createElement('option'); ph.value=''; ph.text='جاري التحميل…';
      profEl.appendChild(ph);
      profEl.disabled = true;
    }
    // Legacy row hidden by default; name row visible
    var legRow = document.getElementById('epLegacyNameRow');
    if(legRow) legRow.style.display = 'none';
    var nameRow = document.getElementById('epNameRow');
    if(nameRow) nameRow.style.display = '';
    _legacyMode = false;
    _profListLoaded = false;
    _snapshot = null;  // invalidate stale snapshot
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

  // ── DS-FRM Hydration — canonical fields (§6/§19) ──
  // Hydrates ALL fields except profession. Called IMMEDIATELY on open.
  function _hydrateCanonicalFields(p, session){
    if(_editSession !== session) return;

    // Detect legacy name mode (§1)
    var hasStructured = !!(p.first_name && p.last_name);
    _legacyMode = !hasStructured && !!(p.full_name);

    var legRow  = document.getElementById('epLegacyNameRow');
    var legText = document.getElementById('epLegacyNameText');

    if(_legacyMode){
      if(legRow){ legRow.style.display = ''; }
      if(legText) legText.textContent = p.full_name || '';
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

    // Short bio
    var shortBioEl = document.getElementById('epShortBio');
    if(shortBioEl) shortBioEl.value = p.short_bio || '';

    // Snapshot captured after canonical fields (profession added when it loads)
    _snapshot = _captureSnapshot();

    if(window.scSelectInit) scSelectInit();
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  }

  // ── DS-FRM Hydration — profession control only (async) ──
  // Updates ONLY the profession <select>. Never touches canonical fields or snapshot.
  function _hydrateProfession(p, profList, session){
    if(_editSession !== session) return;
    var profEl = document.getElementById('epProfession');
    if(!profEl) return;
    _profListLoaded = !!(profList && profList.length);
    if(_profListLoaded){
      _buildProfessionOptions(profEl, profList, p.profession || null);
      profEl.disabled = false;  // enable after successful load (Item 5)
    } else {
      profEl.innerHTML = '';
      var errOpt = document.createElement('option');
      errOpt.value = ''; errOpt.text = '— اختر التخصص —';
      profEl.appendChild(errOpt);
    }
    // Update snapshot with profession value now that it's loaded
    if(_snapshot) _snapshot.profId = ((document.getElementById('epProfession')||{}).value||'').trim();
    if(window.scSelectInit) scSelectInit();
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

    // Canonical fields hydrate IMMEDIATELY — never gated on professions (FRM-06)
    _hydrateCanonicalFields(p, session);

    // Professions async — update ONLY the profession control, never canonical fields
    if(!_profList || !_profList.length){
      // Pending state: show current profession value while fetching so user sees context (Item 5)
      if(p.profession){
        var _pEl = document.getElementById('epProfession');
        if(_pEl){
          _pEl.innerHTML = '';
          var _pOpt = document.createElement('option');
          _pOpt.value = String(p.profession.id || ''); _pOpt.text = p.profession.name_ar || '';
          _pOpt.selected = true; _pEl.appendChild(_pOpt);
          if(window.scSelectInit) scSelectInit();
        }
      }
      getProfessions()
        .then(function(list){
          if(_editSession !== session) return;
          _profList = list;
          _hydrateProfession(p, list, session);
        })
        .catch(function(){
          if(_editSession !== session) return;
          // Failure: preserve current value + disabled; only use error text when no profession set (Item 5)
          _profListLoaded = false;
          var profEl = document.getElementById('epProfession');
          if(profEl){
            if(!p.profession){
              profEl.innerHTML = '';
              var errOpt = document.createElement('option');
              errOpt.value = ''; errOpt.text = 'تعذّر تحميل التخصصات';
              profEl.appendChild(errOpt);
            }
            profEl.disabled = true;
            if(window.scSelectInit) scSelectInit();  // sync custom trigger label
          }
        });
    } else {
      _hydrateProfession(p, _profList, session);
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
            titleEl.innerHTML = '';
            var _profIcon = document.createElement('i');
            // Sanitize icon name: Lucide names are [a-z0-9-] only
            var _iconName = String(prof.icon || 'briefcase').replace(/[^a-z0-9-]/g, '') || 'briefcase';
            _profIcon.setAttribute('data-lucide', _iconName);
            _profIcon.className = 'ico-sm';
            titleEl.appendChild(_profIcon);
            titleEl.appendChild(document.createTextNode(' '));
            var profSpan = document.createElement('span'); profSpan.textContent = prof.name_ar;
            titleEl.appendChild(profSpan);
          }
          if(window._scProfile) window._scProfile.profession = prof;
          if(window.lucide && lucide.createIcons) lucide.createIcons({nodes:[titleEl]});
        }
      } else if(!profile.profession_id){
        // Cleared — show empty state
        if(titleEl) titleEl.innerHTML = '';
        if(window._scProfile) window._scProfile.profession = null;
      }
    }
  }

  // ── Route normalized field error to correct error element (API-MUT-11 consumer) ──
  function _routeFieldError(err){
    var code    = err.code    || '';
    var field   = err.field   || '';
    var message = err.message || 'حدث خطأ في التحقق من البيانات';
    if(code === 'first_name_required' || code === 'last_name_required' ||
       code === 'emp_name_mutation_forbidden' ||
       field === 'first_name' || field === 'last_name' || field === 'middle_name' ||
       field === 'name' || field === 'full_name'){
      var nameErrEl = document.getElementById('epNameErr');
      var inputId = (code === 'last_name_required' || field === 'last_name') ? 'epLastName'
                  : field === 'middle_name' ? 'epMidName' : 'epFirstName';
      _nameErrorOwner = (code === 'last_name_required' || field === 'last_name') ? 'last_name'
                      : field === 'middle_name' ? 'middle_name' : 'first_name';
      _setAriaInvalid(document.getElementById(inputId), nameErrEl, message);
    } else if(code.indexOf('dob') === 0 || field === 'dob'){
      _setDobAriaInvalid(message);
    } else if(field === 'short_bio'){
      _setAriaInvalid(document.getElementById('epShortBio'), document.getElementById('epShortBioErr'), message);
    } else if(field === 'country'){
      _setSelectErr('epCountry', 'epCountryErr', message);
    } else if(field === 'city'){
      _setSelectErr('epCity', 'epCityErr', message);
    } else if(field === 'avail'){
      _setSelectErr('epAvail', 'epAvailErr', message);
    } else if(field === 'profession_id' || field === 'profession'){
      _setSelectErr('epProfession', 'epProfErr', message);
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

    // Build delta payload (FRM-09 tri-state: send value = SET, send null = CLEAR, omit = no change)
    // Only send fields that changed from snapshot. If snapshot is null, treat all as changed.
    var payload = {};
    var _snap = _snapshot;  // may be null if modal was opened before hydration (safety fallback)

    // Name — Atomic Group: send all or none
    // Structured account: compare each part vs snapshot — omit group if unchanged
    // Legacy account: only if migration started (user typed into name fields)
    var _nameGroupChanged;
    if(_legacyMode){
      _nameGroupChanged = _isMigrating();
    } else {
      _nameGroupChanged = !_snap ||
        first !== _snap.firstName ||
        mid   !== _snap.midName   ||
        last  !== _snap.lastName;
    }
    if(_nameGroupChanged){
      payload.first_name  = first;
      payload.middle_name = mid  || null;
      payload.last_name   = last;
    }

    // short_bio: include only if changed
    var _sbChanged = !_snap || shortBioVal !== _snap.shortBio;
    if(_sbChanged) payload.short_bio = shortBioVal || null;

    // DOB: include only if changed (compare all three parts)
    var _dobChanged = !_snap || (dobY !== _snap.dobY || dobM !== _snap.dobM || dobD !== _snap.dobD);
    if(_dobChanged) payload.dob = dob;

    // Country: include only if changed
    var _countryChanged = !_snap || country !== _snap.country;
    if(_countryChanged) payload.country = country || null;

    // City: include only if changed
    var _cityChanged = !_snap || city !== _snap.city;
    if(_cityChanged) payload.city = city || null;

    // Availability: include only if changed
    var _availChanged = !_snap || avail !== _snap.avail;
    if(_availChanged) payload.avail = avail || null;

    // Profession: null = clear (only when list is loaded — prevents clearing on async race)
    // Include only if changed
    var _profChanged = !_snap || profVal !== _snap.profId;
    if(_profChanged){
      if(_profListLoaded){
        payload.profession_id = profVal ? parseInt(profVal, 10) : null;
      } else if(profVal){
        payload.profession_id = parseInt(profVal, 10);
      }
    }

    // BTN-18 loading (§12) + in-flight lock (§13) + controls lock (§9)
    _inFlight = true;
    _setSaveBtnLoading();
    _lockControls();

    updateProfile(uid, payload)
      .then(function(res){
        if(!res.ok){
          // Use single normalizer — no direct detail parsing (API-MUT-11)
          var _norm = window.normalizeErrorResponse ? normalizeErrorResponse(res.data) : {fieldErrors:[], generalError:null};
          if(_norm.fieldErrors.length){
            _norm.fieldErrors.forEach(function(fe){ _routeFieldError(fe); });
            // Focus first invalid control per DOM order
            // For custom selects, MutationObserver may not have fired yet — use scSelectTriggerFor
            var _errEls = document.querySelectorAll('#epOverlay .ep-input-err, #epOverlay [aria-invalid="true"]');
            var firstErr = null;
            for(var _fi=0; _fi < _errEls.length; _fi++){
              var _errEl = _errEls[_fi];
              if(_errEl.tagName === 'SELECT'){
                var _selTrg = window.scSelectTriggerFor ? scSelectTriggerFor(_errEl) : null;
                if(_selTrg){ firstErr = _selTrg; break; }
              } else { firstErr = _errEl; break; }
            }
            if(firstErr) firstErr.focus();
          } else {
            var _msg = (_norm.generalError && _norm.generalError.message) || 'حدث خطأ أثناء الحفظ';
            if(window.toast) window.toast(_msg);
            if(errEl){ errEl.textContent = _msg; errEl.style.display = 'block'; }
          }
          return;
        }
        // 1. Release lock + close + toast
        _inFlight = false;
        _unlockControls();
        closeModal();
        if(window.toast) window.toast('تم حفظ التغييرات بنجاح');
        // 2. Canonical update from server response (§6 — no payload contamination; FRM-17)
        // No background re-fetch: applyCanonicalProfile handles all display updates (FRM-18)
        var canonicalProfile = (res.data && res.data.profile) ? res.data.profile : null;
        if(canonicalProfile) applyCanonicalProfile(canonicalProfile);
        if(window._updateCompletion) window._updateCompletion();
        if(window.lucide && lucide.createIcons) lucide.createIcons();
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
