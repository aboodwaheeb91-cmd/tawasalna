// company.main.js — bootstrap, navigation, modals, follow, cover, report
// Load order: 7th (last — depends on all other modules)
(function () {
  'use strict';

  // ── Navigation ─────────────────────────────────────────────────
  function switchTab(name, el) {
    document.querySelectorAll('.sc-tab').forEach(function (t) { t.classList.remove('active'); });
    el.classList.add('active');
    ['jobs', 'posts', 'about', 'ratings'].forEach(function (t) {
      var el2 = document.getElementById('tab-' + t);
      if (el2) el2.style.display = t === name ? 'block' : 'none';
    });
    if (name === 'posts' && window.loadPosts) loadPosts();
  }

  function doLogout() {
    try {
      Object.keys(localStorage)
        .filter(function (k) { return k.startsWith('tw_'); })
        .forEach(function (k) { localStorage.removeItem(k); });
    } catch (e) {}
    window.location.href = '/login';
  }

  // ── Dropdown menu ──────────────────────────────────────────────
  var _menuOpen      = false;
  var _branchesLoaded = false; // true only after GET /company/branches succeeds
  function toggleMenu(e) {
    e.stopPropagation();
    var m = document.getElementById('coMenuDropdown');
    if (!m) return;
    _menuOpen = !_menuOpen;
    m.classList.toggle('open', _menuOpen);
  }
  document.addEventListener('click', function (e) {
    var wrap = document.getElementById('coMenuWrap');
    var m    = document.getElementById('coMenuDropdown');
    if (_menuOpen && m && wrap && !wrap.contains(e.target)) {
      _menuOpen = false;
      m.classList.remove('open');
    }
  });

  // ── Follow ─────────────────────────────────────────────────────
  var isFollowLoading = false;

  function toggleFollow() {
    if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
    if (!window.companyState || !companyState.permissions.can_follow) return;
    if (isFollowLoading) return;

    var companyId = new URLSearchParams(location.search).get('id');
    if (!companyId) return;

    var prevFollowing = !!companyState.permissions.is_following;
    var prevCount     = companyState.stats.followers_count || 0;
    var willFollow    = !prevFollowing;

    // Optimistic update
    companyState.permissions.is_following = willFollow;
    companyState.stats.followers_count    = prevCount + (willFollow ? 1 : -1);
    if (companyState.stats.followers_count < 0) companyState.stats.followers_count = 0;
    if (window.renderFollowBtn) renderFollowBtn();
    if (window.renderStats)     renderStats();

    isFollowLoading = true;
    var btn = document.getElementById('followBtn');
    if (btn) btn.disabled = true;

    fetch('/company/follow/' + companyId, {
      method:  willFollow ? 'POST' : 'DELETE',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
    })
    .then(function (r) {
      if (!r.ok) throw new Error('follow failed: ' + r.status);
      return r.json();
    })
    .then(function (data) {
      companyState.permissions.is_following = !!data.following;
      if (typeof data.followers_count === 'number')
        companyState.stats.followers_count = data.followers_count;
      if (window.renderFollowBtn) renderFollowBtn();
      if (window.renderStats)     renderStats();
    })
    .catch(function () {
      companyState.permissions.is_following = prevFollowing;
      companyState.stats.followers_count    = prevCount;
      if (window.renderFollowBtn) renderFollowBtn();
      if (window.renderStats)     renderStats();
      if (window.showToast) showToast('تعذّر تحديث المتابعة', 'error');
    })
    .finally(function () {
      isFollowLoading = false;
      if (btn) btn.disabled = false;
    });
  }

  // ── Contact modal ──────────────────────────────────────────────
  function openContact() {
    var el = document.getElementById('contactOverlay');
    if (el) el.classList.add('show');
    if (window.history) history.pushState({ modal: 'contact' }, '', location.href);
  }
  function closeContact(e) {
    var el = document.getElementById('contactOverlay');
    if (!e || e.target === el) el && el.classList.remove('show');
  }
  function sendMsg() {
    var subject = (document.getElementById('msg-subject') || {}).value || 'رسالة جديدة';
    var body    = ((document.getElementById('msg-body') || {}).value || '').trim();
    if (!body) { if (window.showToast) showToast('أدخل الرسالة', 'error'); return; }
    var coId = new URLSearchParams(location.search).get('id');
    if (coId && window._jwt && _jwt()) {
      fetch('/admin/message', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
        body:    JSON.stringify({ user_id: parseInt(coId) || 0, subject: subject, message: body }),
      }).catch(function () {});
    }
    if (window.showToast) showToast('تم إرسال رسالتك ✓');
    closeContact();
  }

  // ── Country / city / options — delegated to window.TW (tw-options-data.js) ──
  // _CO_COUNTRIES, _CO_CITIES, _populateFoundedYears removed — use TW helpers.

  function _coPopulateCountries() {
    TW.fillCountries(document.getElementById('e-country'), '— اختر الدولة —',
      { valueMode: 'name_ar', withFlags: true });
  }

  function _coLoadCities(country, selectedCity) {
    TW.fillCities(document.getElementById('e-city-sel'), country, selectedCity);
  }

  function _populateTypeOptions() {
    TW.fillSelect(document.getElementById('e-type'), TW.COMPANY_TYPES, '— اختر تصنيف الجهة —');
  }

  function _populateSizeOptions() {
    TW.fillSelect(document.getElementById('e-size'), TW.COMPANY_SIZES, '— اختر —');
  }

  function _makeMf(labelText, child, extraClass) {
    var mf = document.createElement('div');
    mf.className = 'mf' + (extraClass ? ' ' + extraClass : '');
    var lbl = document.createElement('label');
    lbl.textContent = labelText;
    mf.appendChild(lbl);
    mf.appendChild(child);
    return mf;
  }

  // ── Branches ─────────────────────────────────────────────────
  function _addBranchRow(data) {
    data = data || {};
    var list = document.getElementById('branchesList');
    if (!list) return;

    var idx = list.children.length + 1;
    var row = document.createElement('div');
    row.className = 'branch-row';

    // Header
    var hdr = document.createElement('div');
    hdr.className = 'branch-row-hdr';
    var num = document.createElement('span');
    num.className   = 'branch-row-num';
    num.textContent = 'فرع ' + idx;
    var del = document.createElement('button');
    del.type        = 'button';
    del.className   = 'branch-row-del';
    del.textContent = '✕ حذف';
    del.setAttribute('aria-label', 'حذف الفرع');
    del.addEventListener('click', function () { list.removeChild(row); });
    hdr.appendChild(num);
    hdr.appendChild(del);

    // Branch name — hidden by default; shown if data.branch_name exists or user clicks toggle
    var inpName = document.createElement('input');
    inpName.type        = 'text';
    inpName.className   = 'b-name';
    inpName.placeholder = 'اسم الفرع (اختياري)';
    inpName.value       = data.branch_name || '';
    var hasName       = !!(data.branch_name && data.branch_name.trim());
    var nameFieldWrap = null;   // assigned below after _makeMf is called

    var toggleBtn       = document.createElement('button');
    toggleBtn.type      = 'button';
    toggleBtn.className = 'branch-name-toggle-btn';
    toggleBtn.textContent = '+ إضافة اسم مخصص للفرع';
    if (hasName) toggleBtn.style.display = 'none';

    // Fields grid
    var fields = document.createElement('div');
    fields.className = 'branch-fields';

    // Country select, class b-country for DOM query
    // Default to HQ country when adding a new branch (data.country empty)
    var _defaultCountry = data.country ||
      (window.companyState && companyState.profile ? (companyState.profile.country || '') : '');
    var selCountry = document.createElement('select');
    selCountry.className = 'ep-select b-country';
    TW.fillCountries(selCountry, '— الدولة —', { valueMode: 'name_ar', withFlags: true });
    if (_defaultCountry) selCountry.value = _defaultCountry;

    // City select, class b-city; pre-filled when country is known
    var selCity = document.createElement('select');
    selCity.className = 'ep-select b-city';
    if (_defaultCountry) {
      TW.fillCities(selCity, _defaultCountry, data.city || '');
    } else {
      selCity.innerHTML = '<option value="">— المدينة —</option>';
    }
    selCountry.addEventListener('change', function () {
      TW.fillCities(selCity, this.value, '');
      if (window.scSelectInit) scSelectInit();
    });

    // District input, class b-district
    var inpDistrict = document.createElement('input');
    inpDistrict.type        = 'text';
    inpDistrict.className   = 'b-district';
    inpDistrict.placeholder = 'مثال: حي العليا، شارع...';
    inpDistrict.value       = data.district || '';

    fields.appendChild(_makeMf('الدولة *',                  selCountry));
    fields.appendChild(_makeMf('المحافظة / المدينة',        selCity));
    fields.appendChild(_makeMf('المنطقة / الحي (اختياري)',  inpDistrict));

    nameFieldWrap = _makeMf('اسم الفرع (اختياري)', inpName, 'branch-name-field');
    if (!hasName) nameFieldWrap.style.display = 'none';
    toggleBtn.addEventListener('click', function () {
      nameFieldWrap.style.display = '';
      toggleBtn.style.display     = 'none';
      inpName.focus();
    });

    row.appendChild(hdr);
    row.appendChild(toggleBtn);
    row.appendChild(nameFieldWrap);
    row.appendChild(fields);
    list.appendChild(row);
    if (window.scSelectInit) scSelectInit();
  }

  // ── Edit modal ─────────────────────────────────────────────────
  function openEditModal() {
    if (!window.companyState || !companyState.permissions.can_edit) return;
    var p      = companyState.profile || {};
    var c      = companyState.company || {};
    var setVal = function (id, v) {
      var el = document.getElementById(id); if (el) el.value = v || '';
    };
    setVal('e-name',     p.full_name);
    setVal('e-desc',     p.bio);
    setVal('e-district', p.location || '');

    // Type / size — from shared TW data
    _populateTypeOptions();
    _populateSizeOptions();
    setVal('e-type', c.industry || c.company_type || '');
    setVal('e-size', c.company_size || '');

    // Founded year dropdown — from TW helper
    TW.fillFoundedYears(document.getElementById('e-founded'));
    setVal('e-founded', c.founded_year ? String(c.founded_year) : '');

    // Country & city dropdowns — from TW helpers
    _coPopulateCountries();
    var savedCountry = p.country || '';
    setVal('e-country', savedCountry);
    _coLoadCities(savedCountry, p.city || '');

    // Branches: reset flag, disable save, show loading, then fetch
    _branchesLoaded = false;
    var saveBtn = document.getElementById('editSaveBtn');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.style.opacity = '0.5'; }

    var bList = document.getElementById('branchesList');
    var bCoId = (companyState.profile || {}).id;
    if (bList) {
      bList.innerHTML = '<div class="branch-loading">جاري تحميل الفروع...</div>';
    }
    if (bCoId) {
      fetch('/company/branches/' + bCoId)
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function (d) {
          if (bList) {
            bList.innerHTML = '';
            (d.branches || []).forEach(function (b) { _addBranchRow(b); });
          }
          _branchesLoaded = true;
          if (saveBtn) { saveBtn.disabled = false; saveBtn.style.opacity = ''; }
        })
        .catch(function () {
          if (bList) {
            bList.innerHTML =
              '<div class="branch-load-err">تعذّر تحميل الفروع، حاول إغلاق المودال وإعادة فتحه</div>';
          }
          if (window.showToast) showToast('تعذّر تحميل الفروع', 'error');
          // save stays disabled — _branchesLoaded remains false
        });
    } else {
      // No company ID yet — treat as empty branches
      if (bList) bList.innerHTML = '';
      _branchesLoaded = true;
      if (saveBtn) { saveBtn.disabled = false; saveBtn.style.opacity = ''; }
    }

    var ov = document.getElementById('editOverlay');
    if (ov) ov.classList.add('show');
    if (window.history) history.pushState({ modal: 'edit' }, '', location.href);

    // Apply custom dropdown to all ep-select elements inside the modal
    if (window.scSelectInit) scSelectInit();
  }
  function closeEdit(e) {
    var el = document.getElementById('editOverlay');
    if (!e || e.target === el) el && el.classList.remove('show');
  }
  function _parseOk(r) {
    if (!r.ok) return r.json().then(function (d) { throw new Error(d.detail || ('HTTP ' + r.status)); });
    return r.json();
  }

  // ── Confirmed Immediate Update helper ─────────────────────────
  // Called only after all 3 PUTs succeed. Updates companyState + partial DOM.
  // Does NOT call renderAll() — calls renderProfile() + renderBranches() only.
  function _applyCompanyLocalUpdate(profilePayload, companyPayload, branchesArr) {
    if (!window.companyState) return;
    var p = companyState.profile  = companyState.profile  || {};
    var c = companyState.company  = companyState.company  || {};
    // Profile fields
    if (profilePayload.full_name !== undefined) p.full_name = profilePayload.full_name;
    if (profilePayload.bio       !== undefined) p.bio       = profilePayload.bio;
    if (profilePayload.country   !== undefined) p.country   = profilePayload.country;
    if (profilePayload.city      !== undefined) p.city      = profilePayload.city;
    if (profilePayload.location  !== undefined) p.location  = profilePayload.location;
    // Company fields
    if (companyPayload.industry      !== undefined) c.industry      = companyPayload.industry;
    if (companyPayload.company_type  !== undefined) c.company_type  = companyPayload.company_type;
    if (companyPayload.founded_year  !== undefined) c.founded_year  = companyPayload.founded_year;
    if (companyPayload.company_size  !== undefined) c.company_size  = companyPayload.company_size;
    // Branches
    companyState.branches = branchesArr;
    // Partial re-render — profile header + branches only
    if (window.renderProfile)  renderProfile();
    if (window.renderBranches) renderBranches(companyState.branches);
    if (window.lucide)         lucide.createIcons();
  }

  function saveEdit() {
    if (!window.companyState || !companyState.permissions.can_edit) return;
    if (!_branchesLoaded) {
      if (window.showToast) showToast('يرجى الانتظار حتى اكتمال تحميل الفروع', 'error');
      return;
    }
    var val  = function (id) { return (document.getElementById(id) || {}).value || ''; };
    var name = val('e-name').trim();
    if (!name) { if (window.showToast) showToast('أدخل اسم الشركة', 'error'); return; }
    var coType = val('e-type');
    if (!coType) { if (window.showToast) showToast('يجب تحديد تصنيف الجهة', 'error'); return; }

    // Prevent double submit
    var saveBtn = document.getElementById('editSaveBtn');
    if (saveBtn && saveBtn.disabled) return;
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'جاري الحفظ…'; }

    var coId = (companyState.profile || {}).id;
    var jwt  = _jwt();
    var hdrs = { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + jwt };

    // Capture payloads before modal closes (modal stays open during save)
    var profilePayload = {
      full_name: name,
      bio:       val('e-desc'),
      country:   val('e-country'),
      city:      val('e-city-sel'),
      location:  val('e-district'),
    };

    var founderVal = parseInt(val('e-founded'), 10);
    var coPayload  = { industry: coType, company_type: coType };
    if (!isNaN(founderVal) && founderVal > 1800) coPayload.founded_year = founderVal;
    if (val('e-size')) coPayload.company_size = val('e-size');

    // ── 3. Collect branches from modal DOM ────────────────────────
    var branchRows  = document.querySelectorAll('#branchesList .branch-row');
    var branchesArr = [];
    [].forEach.call(branchRows, function (row) {
      var country = ((row.querySelector('.b-country') || {}).value || '').trim();
      if (!country) return;
      branchesArr.push({
        branch_name: ((row.querySelector('.b-name')     || {}).value || '').trim(),
        country:     country,
        city:        ((row.querySelector('.b-city')     || {}).value || '').trim(),
        district:    ((row.querySelector('.b-district') || {}).value || '').trim(),
      });
    });

    // ── 1. Update base profile (profiles table) ───────────────────
    var p1 = fetch('/profile/' + coId, {
      method: 'PUT', headers: hdrs,
      body: JSON.stringify(profilePayload),
    }).then(_parseOk);

    // ── 2. Update company_profiles table ──────────────────────────
    var p2 = fetch('/company/profile/' + coId, {
      method: 'PUT', headers: hdrs,
      body: JSON.stringify(coPayload),
    }).then(_parseOk);

    // ── 3. Update branches (snapshot replace) ─────────────────────
    var p3 = fetch('/company/branches/' + coId, {
      method: 'PUT', headers: hdrs,
      body: JSON.stringify({ branches: branchesArr }),
    }).then(_parseOk);

    Promise.all([p1, p2, p3])
      .then(function () {
        // Close modal only after API confirms success
        var ov = document.getElementById('editOverlay');
        if (ov) ov.classList.remove('show');
        if (window.showToast) showToast('تم الحفظ ✓');
        // Immediate DOM update from captured payloads — no full reload wait
        _applyCompanyLocalUpdate(profilePayload, coPayload, branchesArr);
        // Background state sync — silent, no renderAll
        if (window.loadData) loadData({ silent: true });
      })
      .catch(function (err) {
        // Keep modal open — user can correct and retry
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'حفظ'; }
        if (window.showToast) showToast((err && err.message) || 'خطأ في الحفظ', 'error');
      });
  }

  // ── Cover photo ────────────────────────────────────────────────
  function setCover(src) {
    var img = document.getElementById('coverImg');
    if (!img) return;
    img.src = src; img.style.display = 'block';
    setTimeout(function () { img.style.opacity = '1'; }, 50);
  }
  function uploadCover(input) {
    if (!input.files[0]) return;
    var reader = new FileReader();
    reader.onload = function (e) { setCover(e.target.result); };
    reader.readAsDataURL(input.files[0]);
  }

  // ── Logo photo — upload to Supabase + persist url in profiles.avatar_url ──
  function uploadLogo(input) {
    var file = input.files && input.files[0];
    input.value = '';
    if (!file) return;

    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
      if (window.showToast) showToast('يُقبل: JPEG أو PNG أو WebP فقط', 'error');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      if (window.showToast) showToast('حجم الصورة يتجاوز الحد الأقصى 5MB', 'error');
      return;
    }

    var userId = window.companyState && companyState.profile && companyState.profile.id;
    if (!userId) return;
    var jwt = window._jwt ? _jwt() : '';

    var camBtn = document.getElementById('coLogoCamBtn');
    var logoEl = document.getElementById('coLogo');
    if (camBtn) camBtn.disabled = true;
    if (logoEl) logoEl.style.opacity = '0.5';

    var reader = new FileReader();
    reader.onload = function (e) {
      var dataUrl = e.target.result;

      fetch('/upload/image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + jwt },
        body: JSON.stringify({ user_id: userId, bucket: 'avatars', filename: 'logo', data_url: dataUrl })
      })
      .then(function (r) {
        if (!r.ok) throw new Error('upload_fail');
        return r.json();
      })
      .then(function (res) {
        // Use server URL when it's a real hosted URL; otherwise fall back to
        // the original dataUrl. Mirrors Profile V2 (profile-v2.avatar.js)
        // which always calls updateProfile() regardless of dev_mode — storing
        // base64 in DB is not production-ideal; follow-up PR
        // fix/storage-upload-production-mode will resolve this by configuring
        // SUPABASE_URL + SUPABASE_SERVICE_KEY so the server always returns a
        // real URL.
        var url = (res && res.url) ? res.url : dataUrl;
        return fetch('/profile/' + userId, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + jwt },
          body: JSON.stringify({ avatar_url: url })
        })
        .then(function (r2) {
          if (!r2.ok) throw new Error('save_fail');
          return url;
        });
      })
      .then(function (url) {
        if (window.companyState && companyState.profile) {
          companyState.profile.avatar_url = url;
        }
        if (window.renderProfile) renderProfile();
        if (window.showToast) showToast('تم حفظ الشعار ✓');
      })
      .catch(function () {
        if (window.showToast) showToast('تعذر رفع الصورة، حاول مرة أخرى', 'error');
      })
      .finally(function () {
        if (camBtn) camBtn.disabled = false;
        if (logoEl) logoEl.style.opacity = '';
      });
    };
    reader.readAsDataURL(file);
  }

  // ── Report modal ───────────────────────────────────────────────
  var _reportTargetId = null, _reportTargetType = 'company', _reportTargetUrl = '';
  function openReportModal(targetId, targetType, targetUrl) {
    _reportTargetId   = targetId;
    _reportTargetType = targetType || 'company';
    _reportTargetUrl  = targetUrl  || location.href;
    var el = document.getElementById('reportModal');
    if (el) el.style.display = 'flex';
    var reason = document.getElementById('reportReason');
    if (reason) reason.value = '';
  }
  function closeReportModal() {
    var el = document.getElementById('reportModal');
    if (el) el.style.display = 'none';
  }
  function submitReport() {
    var type   = (document.getElementById('reportType')    || {}).value || '';
    var reason = ((document.getElementById('reportReason') || {}).value || '').trim();
    if (!reason) { if (window.showToast) showToast('اكتب سبب البلاغ', 'error'); return; }
    if (!_reportTargetId) { if (window.showToast) showToast('خطأ في البلاغ', 'error'); return; }
    var btn = document.getElementById('reportSubmitBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'جاري الإرسال...'; }
    fetch('/reports/submit', {
      method:  'POST',
      headers: {
        'Content-Type':  'application/json',
        'Authorization': 'Bearer ' + (window._jwt ? _jwt() : ''),
      },
      body: JSON.stringify({
        reported_id:   _reportTargetId,
        reported_type: _reportTargetType,
        report_type:   type,
        reason:        reason,
        target_url:    _reportTargetUrl,
      }),
    })
    .then(function (r) {
      if (r.ok) { if (window.showToast) showToast('تم إرسال البلاغ ✓'); closeReportModal(); }
      else throw new Error();
    })
    .catch(function () {
      if (window.showToast) showToast('خطأ في إرسال البلاغ', 'error');
    })
    .finally(function () {
      if (btn) { btn.disabled = false; btn.textContent = '🚨 إرسال البلاغ'; }
    });
  }

  // ── Bootstrap (Rule #10 — idempotent) ──────────────────────────
  function initCompanyProfile() {
    if (window.__companyBooted) return;
    window.__companyBooted = true;
    if (window._applyLoadingState) _applyLoadingState(true);
    if (window.loadData) loadData();
  }

  // ── Expose ─────────────────────────────────────────────────────
  window.switchTab                = switchTab;
  window.doLogout                 = doLogout;
  window.toggleMenu               = toggleMenu;
  window.toggleFollow             = toggleFollow;
  window.openContact              = openContact;
  window.closeContact             = closeContact;
  window.sendMsg                  = sendMsg;
  window.openEditModal            = openEditModal;
  window.closeEdit                = closeEdit;
  window.saveEdit                 = saveEdit;
  window._applyCompanyLocalUpdate = _applyCompanyLocalUpdate;
  window.setCover                 = setCover;
  window.uploadCover              = uploadCover;
  window.uploadLogo               = uploadLogo;
  window.openReportModal          = openReportModal;
  window.closeReportModal         = closeReportModal;
  window.submitReport             = submitReport;
  window.initCompanyProfile       = initCompanyProfile;

  // Expose _branchesLoaded read/write for testability and cross-module access
  Object.defineProperty(window, '_branchesLoaded', {
    get: function () { return _branchesLoaded; },
    set: function (v) { _branchesLoaded = v; },
    configurable: true,
  });

  // ── Event bindings (commit #2 — replaces all inline onclick/onchange) ──
  function _bindMainEvents() {
    var q = function (id) { return document.getElementById(id); };

    // Profile section buttons
    var postJobBtn    = q('postJobBtn');    if (postJobBtn)    postJobBtn.addEventListener('click', openPostJob);
    var editInfoBtn   = q('editInfoBtn');   if (editInfoBtn)   editInfoBtn.addEventListener('click', openEditModal);
    var ctaPostJobBtn = q('ctaPostJobBtn'); if (ctaPostJobBtn) ctaPostJobBtn.addEventListener('click', openPostJob);

    // Shared header — menu + logout
    var coMenuBtn   = q('coMenuBtn');   if (coMenuBtn)   coMenuBtn.addEventListener('click', toggleMenu);
    var coLogoutBtn = q('coLogoutBtn'); if (coLogoutBtn) coLogoutBtn.addEventListener('click', doLogout);

    // Cover photo upload
    var coverFileInput = q('coverFileInput');
    if (coverFileInput) coverFileInput.addEventListener('change', function () { uploadCover(this); });

    // Logo photo upload — analogous to Profile V2 av-cam-btn flow
    var coLogoCamBtn    = q('coLogoCamBtn');
    var coLogoFileInput = q('coLogoFileInput');
    if (coLogoCamBtn && coLogoFileInput) {
      coLogoCamBtn.addEventListener('click', function () { coLogoFileInput.click(); });
      coLogoFileInput.addEventListener('change', function () { uploadLogo(this); });
    }

    // Follow + Contact
    var followBtn  = q('followBtn');  if (followBtn)  followBtn.addEventListener('click', toggleFollow);
    var contactBtn = q('contactBtn'); if (contactBtn) contactBtn.addEventListener('click', openContact);

    // Tabs
    document.querySelectorAll('.sc-tab[data-tab]').forEach(function (tab) {
      tab.addEventListener('click', function () { switchTab(this.dataset.tab, this); });
    });

    // Edit modal
    var editOverlay   = q('editOverlay');   if (editOverlay)   editOverlay.addEventListener('click', closeEdit);
    var editSaveBtn   = q('editSaveBtn');   if (editSaveBtn)   editSaveBtn.addEventListener('click', saveEdit);
    var editCancelBtn = q('editCancelBtn');
    if (editCancelBtn) editCancelBtn.addEventListener('click', function () {
      var ov = q('editOverlay'); if (ov) ov.classList.remove('show');
    });

    // Country dropdown → reload city list
    var eCountry = q('e-country');
    if (eCountry) eCountry.addEventListener('change', function () { _coLoadCities(this.value, ''); });

    // Add branch row
    var addBranchBtn = q('addBranchBtn');
    if (addBranchBtn) addBranchBtn.addEventListener('click', function () { _addBranchRow({}); });

    // Contact modal
    var contactOverlay   = q('contactOverlay');   if (contactOverlay)   contactOverlay.addEventListener('click', closeContact);
    var contactSendBtn   = q('contactSendBtn');   if (contactSendBtn)   contactSendBtn.addEventListener('click', sendMsg);
    var contactCancelBtn = q('contactCancelBtn');
    if (contactCancelBtn) contactCancelBtn.addEventListener('click', function () {
      var ov = q('contactOverlay'); if (ov) ov.classList.remove('show');
    });

    // Report modal
    var reportSubmitBtn = q('reportSubmitBtn'); if (reportSubmitBtn) reportSubmitBtn.addEventListener('click', submitReport);
    var reportCancelBtn = q('reportCancelBtn'); if (reportCancelBtn) reportCancelBtn.addEventListener('click', closeReportModal);
  }

  // ── Auth-sync: cross-tab session invalidation ──
  // Wires TwAuthSync (static/shared/auth-sync.js) into Company Profile.
  // On JWT change: immediately strips owner mode, closes edit modal,
  // then background-reloads to get authoritative viewer_type from server.
  (function () {
    if (!window.TwAuthSync) return;
    TwAuthSync.onSessionChange(function () {
      // Immediately revoke owner UI
      if (window.companyState && companyState.viewMode === 'owner') {
        companyState.viewMode = 'guest';
        if (window._applyViewMode) _applyViewMode();
        // Close edit modal if open
        var ov = document.getElementById('editOverlay');
        if (ov) ov.classList.remove('show');
        // Disable save button defensively
        var saveBtn = document.getElementById('editSaveBtn');
        if (saveBtn) saveBtn.disabled = true;
      }
      // Background re-verify — gets fresh viewer_type from server
      if (window.loadData) loadData({ silent: true });
    });
  }());

  // ── DOMContentLoaded ───────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    if (window.lucide) lucide.createIcons();
    if (window.initScrollProg)      initScrollProg();
    if (window.initCompanyProfile)  initCompanyProfile();
    _bindMainEvents();
  });

  // ── Pull-to-refresh ────────────────────────────────────────────
  var _ptr2Start = 0, _ptr2Active = false;
  document.addEventListener('touchstart', function (e) {
    if (window.scrollY === 0) _ptr2Start = e.touches[0].clientY;
  }, { passive: true });
  document.addEventListener('touchend', function () {
    if (_ptr2Active) { _ptr2Active = false; if (window.loadData) loadData(); }
  }, { passive: true });
  document.addEventListener('touchmove', function (e) {
    if (window.scrollY === 0 && _ptr2Start > 0) {
      var diff = e.touches[0].clientY - _ptr2Start;
      if (diff > 70 && !_ptr2Active) {
        _ptr2Active = true;
        if (window.showToast) showToast('جاري التحديث...', 'info', 1500);
      }
    }
  }, { passive: true });
}());

// ── Company Followers Modal ────────────────────────────────────────
(function () {
  'use strict';

  var _overlay  = document.getElementById('coFollowListModal');
  if (!_overlay) return;

  var _list     = document.getElementById('coFlList');
  var _loadWrap = document.getElementById('coFlLoad');
  var _loadBtn  = document.getElementById('coFlLoadMore');
  var _filtersEl= document.getElementById('coFlFilters');

  var _loading  = false;
  var _filter   = 'all';
  var _offset   = 0;
  var _limit    = 20;
  var _hasMore  = false;

  var _TYPE_LABELS = { all: 'الكل', emp: 'موظفون', co: 'شركات', edu: 'مؤسسات' };
  var _TYPE_ORDER  = ['all', 'emp', 'co', 'edu'];

  function _getCompanyId() {
    return window.companyState && companyState.profile ? companyState.profile.id : null;
  }

  function _open() {
    _filter = 'all';
    _offset = 0;
    _list.innerHTML = '';
    _loadWrap.style.display = 'none';
    _overlay.style.display  = 'flex';
    document.body.style.overflow = 'hidden';
    _fetchPage(true);
  }

  function _close() {
    _overlay.style.display = 'none';
    document.body.style.overflow = '';
  }

  function _renderChips(counts) {
    if (!_filtersEl) return;
    var html = '';
    _TYPE_ORDER.forEach(function (t) {
      var n = t === 'all' ? (counts.all || 0) : (counts[t] || 0);
      if (t !== 'all' && n === 0) return;
      var active = _filter === t ? ' active' : '';
      html += '<button class="co-fl-chip' + active + '" data-type="' + t + '">' +
        _TYPE_LABELS[t] + (t !== 'all' ? ' (' + n + ')' : '') + '</button>';
    });
    _filtersEl.innerHTML = html;
    _filtersEl.querySelectorAll('.co-fl-chip').forEach(function (btn) {
      btn.addEventListener('click', function () {
        _filter = this.dataset.type;
        _offset = 0;
        _list.innerHTML = '';
        _filtersEl.querySelectorAll('.co-fl-chip').forEach(function (b) { b.classList.remove('active'); });
        this.classList.add('active');
        _fetchPage(true);
      });
    });
  }

  function _esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function _renderItems(items) {
    items.forEach(function (item) {
      var div = document.createElement('div');
      div.className = 'co-fl-item';

      // Avatar
      var avaDiv = document.createElement('div');
      avaDiv.className = 'co-fl-ava';
      if (item.avatar_url) {
        var img = document.createElement('img');
        img.src = item.avatar_url;
        img.alt = item.display_name || '';
        avaDiv.appendChild(img);
      } else {
        avaDiv.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>';
      }

      // Info
      var infoDiv = document.createElement('div');
      infoDiv.className = 'co-fl-info';

      var nameEl = document.createElement('div');
      nameEl.className = 'co-fl-name';
      nameEl.textContent = item.display_name || '—';

      var metaEl = document.createElement('div');
      metaEl.className = 'co-fl-meta';
      var typeLabel  = { emp: 'موظف', co: 'شركة', edu: 'تعليمية' }[item.user_type] || '';
      var profLabel  = item.profession && item.profession.name_ar ? item.profession.name_ar : '';
      metaEl.textContent = [profLabel, typeLabel].filter(Boolean).join(' · ');

      infoDiv.appendChild(nameEl);
      infoDiv.appendChild(metaEl);

      // Follow button (if allowed)
      var followBtnEl = null;
      if (item.can_follow) {
        followBtnEl = document.createElement('button');
        followBtnEl.className = 'co-fl-follow-btn' + (item.is_following ? ' following' : '');
        followBtnEl.textContent = item.is_following ? 'متابَع' : 'تابع';
        (function (it, btn) {
          btn.addEventListener('click', function () {
            var jwt = window._jwt ? window._jwt() : '';
            if (!jwt) { if (window.showToast) showToast('سجّل الدخول أولاً'); return; }
            var isF = btn.classList.contains('following');
            var method = isF ? 'DELETE' : 'POST';
            btn.disabled = true;
            fetch('/profile/' + it.id + '/follow', {
              method: method,
              headers: { 'Authorization': 'Bearer ' + jwt }
            }).then(function (r) { return r.json(); })
              .then(function (d) {
                if (d.status === 'success' || d.is_following != null) {
                  var nowF = !isF;
                  btn.classList.toggle('following', nowF);
                  btn.textContent = nowF ? 'متابَع' : 'تابع';
                }
              }).catch(function () {})
              .finally(function () { btn.disabled = false; });
          });
        }(item, followBtnEl));
      }

      div.appendChild(avaDiv);
      div.appendChild(infoDiv);
      if (followBtnEl) div.appendChild(followBtnEl);
      _list.appendChild(div);
    });
  }

  function _fetchPage(replace) {
    var coId = _getCompanyId();
    if (_loading || !coId) return;
    _loading = true;
    if (replace) _list.innerHTML = '<div class="co-fl-spin">جاري التحميل...</div>';
    window.getCompanyFollowersList(coId, _limit, _offset, _filter)
      .then(function (res) {
        _loading = false;
        if (!res || !res.ok || !res.data) {
          if (replace) _list.innerHTML = '<div class="co-fl-empty">تعذّر تحميل القائمة</div>';
          return;
        }
        var d = res.data;
        if (replace) {
          _list.innerHTML = '';
          _renderChips(d.counts || {});
        }
        if (!d.items || d.items.length === 0) {
          if (replace) _list.innerHTML = '<div class="co-fl-empty">لا يوجد متابعون حتى الآن</div>';
          _loadWrap.style.display = 'none';
          return;
        }
        _renderItems(d.items);
        _offset += d.items.length;
        _hasMore = d.pagination && d.pagination.has_more;
        _loadWrap.style.display = _hasMore ? '' : 'none';
        if (window.lucide && lucide.createIcons) lucide.createIcons();
      })
      .catch(function () {
        _loading = false;
        if (replace) _list.innerHTML = '<div class="co-fl-empty">حدث خطأ، حاول مرة أخرى</div>';
      });
  }

  // Wire close button
  document.getElementById('coFlClose').addEventListener('click', _close);
  _overlay.addEventListener('click', function (e) { if (e.target === _overlay) _close(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') _close(); });
  if (_loadBtn) _loadBtn.addEventListener('click', function () { _fetchPage(false); });

  // Wire followers tile click — fires after data loads (tile may not exist yet on DOMContentLoaded)
  document.addEventListener('DOMContentLoaded', function () {
    var tile = document.getElementById('coStatFollowersTile');
    if (tile) tile.addEventListener('click', _open);
  });

  window._coFlOpen = _open;
}());

// ── Soft refresh: followers count every 30s while page is visible ─
(function () {
  var _interval = null;
  function _start() {
    if (_interval) return;
    _interval = setInterval(function () {
      if (window.loadData) loadData({ silent: true });
    }, 30000);
  }
  function _stop() { clearInterval(_interval); _interval = null; }
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) _stop(); else _start();
  });
  document.addEventListener('DOMContentLoaded', _start);
}());
