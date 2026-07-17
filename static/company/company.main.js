// company.main.js — bootstrap, navigation, modals, follow, cover, report
// Load order: 7th (last — depends on all other modules)
(function () {
  'use strict';

  // ── Navigation ─────────────────────────────────────────────────
  function switchTab(name, el) {
    document.querySelectorAll('.sc-tab').forEach(function (t) { t.classList.remove('active'); });
    el.classList.add('active');
    ['jobs', 'posts', 'about'].forEach(function (t) {
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

  // ── Shared: resolve numeric company id (works on /u/C0... and ?id= routes) ─
  function _resolveCoId() {
    if (window.companyState && companyState.profile && companyState.profile.id)
      return companyState.profile.id;
    if (window._companyProfileIdFromRoute != null)
      return parseInt(window._companyProfileIdFromRoute) || null;
    var qId = new URLSearchParams(location.search).get('id');
    return qId ? (parseInt(qId) || null) : null;
  }

  // ── Follow ─────────────────────────────────────────────────────
  var isFollowLoading = false;

  function toggleFollow() {
    if (!window._jwt || !_jwt()) { window.location.href = '/'; return; }
    if (!window.companyState || !companyState.permissions.can_follow) return;
    if (isFollowLoading) return;

    var companyId = _resolveCoId();
    if (!companyId) { if (window.showToast) showToast('تعذّر تحديد الشركة', 'error'); return; }

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
    if (window.history && !_contactHistoryPushed) {
      history.pushState({ modal: 'contact' }, '', location.href);
      _contactHistoryPushed = true;
    }
  }
  function closeContact(e) {
    var el = document.getElementById('contactOverlay');
    if (!e || e.target === el) {
      if (el) el.classList.remove('show');
      if (_contactHistoryPushed) {
        _contactHistoryPushed = false;
        if (window.history) history.back();
      }
    }
  }
  var isSendingMsg = false;
  function sendMsg() {
    var subjectEl = document.getElementById('msg-subject');
    var bodyEl    = document.getElementById('msg-body');
    var subject   = (subjectEl ? subjectEl.value : '').trim();
    var body      = (bodyEl    ? bodyEl.value    : '').trim();
    if (!body) { if (window.showToast) showToast('أدخل الرسالة', 'error'); return; }

    if (!window._jwt || !_jwt()) { window.location.href = '/login'; return; }

    var coId = _resolveCoId();
    if (!coId) { if (window.showToast) showToast('تعذّر تحديد الشركة', 'error'); return; }

    if (isSendingMsg) return;
    isSendingMsg = true;
    var sendBtn = document.getElementById('contactSendBtn');
    if (sendBtn) sendBtn.disabled = true;

    var content = subject ? (subject + '\n' + body) : body;

    fetch('/messages/send', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _jwt() },
      body:    JSON.stringify({ receiver_id: coId, content: content }),
    })
    .then(function (r) {
      if (!r.ok) return r.json().then(function (e) { throw new Error(e.detail || String(r.status)); });
      return r.json();
    })
    .then(function () {
      if (subjectEl) subjectEl.value = '';
      if (bodyEl)    bodyEl.value    = '';
      closeContact();
      if (window.showToast) showToast('تم إرسال رسالتك ✓');
    })
    .catch(function () {
      if (window.showToast) showToast('تعذّر إرسال الرسالة، حاول مجدداً', 'error');
    })
    .finally(function () {
      isSendingMsg = false;
      if (sendBtn) sendBtn.disabled = false;
    });
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
    if (window.history && !_editHistoryPushed) {
      history.pushState({ modal: 'edit' }, '', location.href);
      _editHistoryPushed = true;
    }

    // Apply custom dropdown to all ep-select elements inside the modal
    if (window.scSelectInit) scSelectInit();
  }
  function closeEdit(e) {
    var el = document.getElementById('editOverlay');
    if (!e || e.target === el) {
      if (el) el.classList.remove('show');
      if (_editHistoryPushed) {
        _editHistoryPushed = false;
        if (window.history) history.back();
      }
    }
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

  // ── Cover photo — crop via shared cropper, then upload ──
  function setCover(src) {
    var img = document.getElementById('coverImg');
    if (!img) return;
    img.src = src; img.style.display = 'block';
    setTimeout(function () { img.style.opacity = '1'; }, 50);
  }

  var _coverCropper = null;
  function _getCoverCropper() {
    if (!_coverCropper) {
      var canvas = document.getElementById('coCoverCropCanvas');
      if (!canvas) return null;
      _coverCropper = TW.createCropper({
        canvas:  canvas,
        ratio:   4 / 1,
        shape:   'rect',
        outputW: 800,
        outputH: 200,
        quality: 0.88
      });
    }
    return _coverCropper;
  }

  function uploadCover(input) {
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

    var reader = new FileReader();
    reader.onload = function (e) { openCoverCrop(e.target.result); };
    reader.readAsDataURL(file);
  }

  function openCoverCrop(src) {
    var overlay = document.getElementById('coCoverCropOverlay');
    var slider  = document.getElementById('coCoverZoomSlider');
    if (!overlay) return;
    overlay.classList.add('open');
    if (slider) { slider.min = 100; slider.max = 300; slider.value = 100; }
    requestAnimationFrame(function () {
      var cropper = _getCoverCropper();
      if (cropper) cropper.load(src);
    });
  }

  function closeCoverCrop() {
    var overlay = document.getElementById('coCoverCropOverlay');
    if (overlay) overlay.classList.remove('open');
    var cropper = _getCoverCropper();
    if (cropper) cropper.reset();
  }

  var isUploadingCover = false;
  function _doUploadCover() {
    var cropper = _getCoverCropper();
    if (!cropper) return;
    if (isUploadingCover) return;

    var userId = window.companyState && companyState.profile && companyState.profile.id;
    if (!userId) return;
    var jwt = window._jwt ? _jwt() : '';
    if (!jwt) { window.location.href = '/login'; return; }

    isUploadingCover = true;
    var saveBtn   = document.getElementById('coCoverCropSaveBtn');
    var uploadBtn = document.getElementById('coverUploadBtn');
    if (saveBtn)   { saveBtn.disabled = true; saveBtn.textContent = 'جاري الرفع…'; }
    if (uploadBtn) uploadBtn.style.pointerEvents = 'none';

    var dataUrl = cropper.export();

    TW.uploadImage({ userId: userId, bucket: 'avatars', filename: 'cover', dataUrl: dataUrl, jwt: jwt })
    .then(function (res) {
      if (!res.ok || !res.data || !res.data.url) throw new Error('no_url');
      var url = res.data.url;
      return fetch('/company/cover/' + userId, {
        method:  'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + jwt },
        body:    JSON.stringify({ cover_url: url }),
      })
      .then(function (r2) {
        if (!r2.ok) throw new Error('save_fail');
        return url;
      });
    })
    .then(function (url) {
      if (window.companyState && companyState.company) {
        companyState.company.cover_url = url;
      }
      setCover(url);
      if (window.showToast) showToast('تم حفظ صورة الغلاف ✓');
      closeCoverCrop();
    })
    .catch(function () {
      if (window.showToast) showToast('تعذّر رفع الغلاف، حاول مرة أخرى', 'error');
    })
    .finally(function () {
      isUploadingCover = false;
      if (saveBtn)   { saveBtn.disabled = false; saveBtn.textContent = 'حفظ الغلاف'; }
      if (uploadBtn) uploadBtn.style.pointerEvents = '';
    });
  }

  // ── Logo photo — crop via shared cropper, then upload ──
  var _logoCropper = null;
  function _getLogoCropper() {
    if (!_logoCropper) {
      var canvas = document.getElementById('coLogoCropCanvas');
      if (!canvas) return null;
      _logoCropper = TW.createCropper({
        canvas:  canvas,
        ratio:   1 / 1,
        shape:   'circle',
        outputW: 300,
        outputH: 300,
        quality: 0.85
      });
    }
    return _logoCropper;
  }

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

    var reader = new FileReader();
    reader.onload = function (e) { openLogoCrop(e.target.result); };
    reader.readAsDataURL(file);
  }

  function openLogoCrop(src) {
    var overlay = document.getElementById('coLogoCropOverlay');
    var slider  = document.getElementById('coLogoZoomSlider');
    if (!overlay) return;
    overlay.classList.add('open');
    if (slider) { slider.min = 100; slider.max = 300; slider.value = 100; }
    requestAnimationFrame(function () {
      var cropper = _getLogoCropper();
      if (cropper) cropper.load(src);
    });
  }

  function closeLogoCrop() {
    var overlay = document.getElementById('coLogoCropOverlay');
    if (overlay) overlay.classList.remove('open');
    var cropper = _getLogoCropper();
    if (cropper) cropper.reset();
  }

  function _doUploadLogo() {
    var cropper = _getLogoCropper();
    if (!cropper) return;

    var userId = window.companyState && companyState.profile && companyState.profile.id;
    if (!userId) return;
    var jwt = window._jwt ? _jwt() : '';
    if (!jwt) { window.location.href = '/login'; return; }

    var saveBtn = document.getElementById('coLogoCropSaveBtn');
    var camBtn  = document.getElementById('coLogoCamBtn');
    var logoEl  = document.getElementById('coLogo');

    var dataUrl = cropper.export();

    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'جاري الرفع…'; }
    if (camBtn)  camBtn.disabled = true;
    if (logoEl)  logoEl.style.opacity = '0.5';

    TW.uploadImage({ userId: userId, bucket: 'avatars', filename: 'logo', dataUrl: dataUrl, jwt: jwt })
    .then(function (res) {
      if (!res.ok) throw new Error('upload_fail');
      var url = (res.data && res.data.url) ? res.data.url : dataUrl;
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
      closeLogoCrop();
    })
    .catch(function () {
      if (window.showToast) showToast('تعذر رفع الصورة، حاول مرة أخرى', 'error');
    })
    .finally(function () {
      if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'حفظ الشعار'; }
      if (camBtn)  camBtn.disabled = false;
      if (logoEl)  logoEl.style.opacity = '';
    });
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

  // ── Applicants Modal — owner-only, per-job ────────────────────
  var _appJobId               = null;
  var _appLoading             = false;
  var _appModalHistoryPushed  = false; // true after pushState for applicants modal
  var _contactHistoryPushed   = false; // true after pushState for contact modal
  var _editHistoryPushed      = false; // true after pushState for edit modal
  var _astFloat               = null;   // singleton classify dropdown (body-level)
  var _astFloatTrigger        = null;   // classify btn that opened it
  var _cardListenerBound      = false;  // delegation guard for #coAppList
  var _icFloat                = null;   // interview choice mini-portal (body-level)
  var _icFloatTrigger         = null;   // classify btn that opened it
  var _icFloatAppId           = null;   // appId awaiting interview choice
  var _icPrevStatus           = null;   // prev status for rollback if classify fails
  // ── Appointment scheduling — per accepted applicant ────────────
  var _apptByAppId         = {};    // { "appId": { id, status } } from GET /api/appointments
  var _apptByEntryId       = {};    // { "entryId": { id, status } } — pipeline Path B
  var _apptIndexLoaded     = false; // true after first successful index load
  var _apptInFlight        = false; // true while create+send is in progress
  var _apptCurrentAppId    = null;  // appId for Path A (application-based)
  var _apptCurrentEntryId  = null;  // pipeline_entry_id for Path B
  var _apptCurrentCandidateId = null; // candidate user_id for Path B
  var _apptModalInited     = false; // one-time listener guard
  var _apptMode            = 'online';
  // ── Pipeline Notes panel ────────────────────────────────────────
  var _notesCurrentEntryId = null;  // entry_id whose notes are open
  var _notesInFlight       = false; // create-note in-flight guard
  var _notesModalInited    = false; // one-time listener guard
  var _APP_STATUS_LABEL = {
    pending:   'محفوظ',
    viewed:    'للمراجعة',
    accepted:  'مرشح قوي',
    contacted: 'تم التواصل',
    interview: 'مقابلة',
    hired:     'تم التوظيف',
    rejected:  'غير مناسب'
  };

  function _escApp(s) {
    return String(s || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function _appFmtDate(iso) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleDateString('ar-EG',
        { year: 'numeric', month: 'short', day: 'numeric' });
    } catch (e) { return ''; }
  }

  function openApplicantsModal(jobId) {
    _appJobId   = jobId;
    _appLoading = false;
    var el = document.getElementById('coApplicantsModal');
    if (el) el.style.display = 'flex';
    var title = document.getElementById('coAppModalTitle');
    var job = window.companyState && companyState.jobs
      ? companyState.jobs.find(function (j) { return j.id == jobId; })
      : null;
    if (title) title.textContent = 'المتقدمون' + (job ? ' — ' + job.title : '');
    if (window.history && !_appModalHistoryPushed) {
      history.pushState({ modal: 'applicants' }, '', location.href);
      _appModalHistoryPushed = true;
    }
    _loadApplicants(jobId);
  }

  function closeApplicantsModal() {
    _closeClassifyFloat();
    _closeInterviewChoice();
    var el = document.getElementById('coApplicantsModal');
    if (el) el.style.display = 'none';
    _appJobId = null;
    if (_appModalHistoryPushed) {
      _appModalHistoryPushed = false;
      if (window.history) history.back();
    }
  }

  function _loadApplicants(jobId) {
    if (_appLoading) return;
    _appLoading = true;
    var list = document.getElementById('coAppList');
    if (list) list.innerHTML = '<div class="co-app-spin">جارٍ التحميل…</div>';
    var jwt = window._jwt ? _jwt() : '';
    if (!jwt) {
      if (list) list.innerHTML = '<div class="co-app-empty">يجب تسجيل الدخول أولاً</div>';
      _appLoading = false;
      return;
    }
    fetch('/jobs/' + parseInt(jobId, 10) + '/applicants', {
      headers: { 'Authorization': 'Bearer ' + jwt }
    })
    .then(function (r) {
      if (!r.ok) { var err = new Error('HTTP ' + r.status); err.status = r.status; throw err; }
      return r.json();
    })
    .then(function (data) {
      _appLoading = false;
      var apps = (data && Array.isArray(data.applicants)) ? data.applicants : [];
      _renderApplicants(apps);
    })
    .catch(function (err) {
      _appLoading = false;
      var list2 = document.getElementById('coAppList');
      var msg = (err && (err.status === 401 || err.status === 403))
        ? 'انتهت الجلسة أو لا تملك صلاحية عرض المتقدمين'
        : 'تعذّر تحميل المتقدمين، حاول مجدداً';
      if (list2) list2.innerHTML = '<div class="co-app-empty">' + msg + '</div>';
    });
  }

  function _renderApplicants(apps) {
    var list = document.getElementById('coAppList');
    if (!list) return;
    if (!apps.length) {
      list.innerHTML = '<div class="co-app-empty">لا يوجد متقدمون لهذه الوظيفة</div>';
      return;
    }
    var html = '';
    apps.forEach(function (a) {
      var initial        = (a.full_name || '؟').charAt(0);
      var statusKey      = a.status || 'pending';
      var statusLbl      = _APP_STATUS_LABEL[statusKey] || statusKey;
      var dateStr        = _appFmtDate(a.applied_at);
      var appId          = parseInt(a.id, 10);
      var uid            = parseInt(a.user_id, 10);
      var twId           = a.tw_id || '';
      var isSaved        = !!a.is_saved;
      var otherJobTitles = Array.isArray(a.other_job_titles) ? a.other_job_titles : [];
      var entryId        = a.pipeline_entry_id ? parseInt(a.pipeline_entry_id, 10) : 0;
      var stage          = a.stage || '';
      var notesCount     = parseInt(a.pipeline_notes_count || 0, 10);
      var nextAppt       = a.next_appointment || null;

      var isRejected   = statusKey === 'rejected';
      var isHired      = statusKey === 'hired';
      var isClassified = statusKey !== 'pending';

      var avatarHtml = a.avatar_url
        ? '<img src="' + _escApp(a.avatar_url) + '" alt="" loading="lazy"'
          + ' onerror="this.style.display=\'none\';this.parentNode.dataset.fb=\'1\'">'
          + '<span class="co-app-ava-fb">' + _escApp(initial) + '</span>'
        : _escApp(initial);

      var statusBadge = isClassified
        ? '<span class="co-app-status co-app-status--' + _escApp(statusKey) + '">' + _escApp(statusLbl) + '</span>'
        : '';

      var stageHtml = (entryId && stage)
        ? '<div class="co-app-meta-line co-app-stage">المرحلة: ' + _escApp(stage) + '</div>'
        : '';

      var nextApptHtml = '';
      if (nextAppt && nextAppt.scheduled_at) {
        var apptTypeLbl = nextAppt.appointment_type || 'مقابلة';
        nextApptHtml = '<div class="co-app-next-appt">'
          + _escApp(apptTypeLbl) + ' · ' + _escApp(_appFmtDate(nextAppt.scheduled_at))
          + '</div>';
      }

      var viewBtn = twId
        ? '<a class="co-app-view-btn co-app-act" href="/u/' + _escApp(twId) + '" target="_blank" rel="noopener">عرض الملف الكامل</a>'
        : '';

      var classifyLbl = !isClassified ? 'ترشيح للوظيفة ▾'
        : isRejected                  ? 'إعادة التصنيف ▾'
        : 'تعديل التصنيف ▾';

      var classifyBtn = '<button type="button" class="co-classify-btn co-app-act'
        + (isRejected ? ' co-classify-btn--reclassify' : '')
        + '" data-app-id="' + appId + '" data-status="' + _escApp(statusKey) + '"'
        + ' data-uid="' + uid + '"'
        + (isHired ? ' data-hired="1"' : '')
        + '>' + classifyLbl + '</button>';

      var tbLbl = isSaved ? 'محفوظ في بنك المواهب ✓' : 'حفظ في بنك المواهب';
      var talentBankBtn = '<button type="button" class="co-talentbank-btn co-app-act'
        + (isSaved ? ' co-talentbank-btn--saved' : '')
        + '" data-uid="' + uid + '" data-saved="' + (isSaved ? '1' : '0') + '"'
        + (isSaved ? ' disabled' : '')
        + '>' + tbLbl + '</button>';

      // "ملاحظات الوظيفة" — only when pipeline entry exists
      var notesCountBadge = notesCount > 0 ? ' (' + notesCount + ')' : '';
      var notesBtn = entryId
        ? '<button type="button" class="co-notes-btn co-app-act" data-entry-id="' + entryId + '"'
          + '>ملاحظات الوظيفة' + notesCountBadge + '</button>'
        : '';

      // "تحديد موعد" — for ALL pipeline candidates (not limited to interview status)
      var schedBtn = entryId
        ? '<button type="button" class="co-app-sched-btn co-app-act"'
          + ' data-app-id="' + appId + '"'
          + ' data-entry-id="' + entryId + '"'
          + ' data-uid="' + uid + '"'
          + '>تحديد موعد</button>'
        : '';

      var savedCtx = isSaved && otherJobTitles.length > 0
        ? '<div class="co-app-saved-ctx">محفوظ · أيضاً في: '
          + otherJobTitles.slice(0, 2).map(function (t) { return _escApp(t); }).join(' · ')
          + (otherJobTitles.length > 2 ? ' · +' + (otherJobTitles.length - 2) : '')
          + '</div>'
        : '';

      html += '<div class="co-app-card' + (isRejected ? ' co-app-card--rejected' : '') + '"'
        + ' data-app-id="' + appId + '" data-name="' + _escApp(a.full_name || '') + '"'
        + ' data-uid="' + uid + '" data-tw-id="' + _escApp(twId) + '"'
        + (entryId ? ' data-entry-id="' + entryId + '"' : '')
        + '>'
        + '<div class="co-app-card-head">'
        +   '<div class="co-app-ava">' + avatarHtml + '</div>'
        +   '<div class="co-app-info">'
        +     '<div class="co-app-name">' + _escApp(a.full_name || '—') + '</div>'
        +     (dateStr ? '<div class="co-app-meta-line">تقدّم: ' + _escApp(dateStr) + '</div>' : '')
        +     stageHtml
        +   '</div>'
        +   statusBadge
        + '</div>'
        + nextApptHtml
        + savedCtx
        + '<div class="co-app-card-foot">'
        + viewBtn
        + classifyBtn
        + talentBankBtn
        + notesBtn
        + schedBtn
        + '</div>'
        + '</div>';
    });
    list.innerHTML = html;
    _wireApplicantCards(list);
    _loadApptIndex(function () { _applyApptIndexToCards(); });
  }

  function _wireApplicantCards(list) {
    if (_cardListenerBound) return;
    _cardListenerBound = true;
    list.addEventListener('click', function (e) {
      var classifyBtn = e.target.closest('.co-classify-btn');
      if (classifyBtn && !classifyBtn.disabled) { _openClassifyFloat(classifyBtn); return; }
      var tbBtn = e.target.closest('.co-talentbank-btn');
      if (tbBtn && !tbBtn.disabled) { _onSaveToTalentBank(tbBtn); return; }
      var schedBtn = e.target.closest('.co-app-sched-btn');
      if (schedBtn && !schedBtn.disabled) { _onSchedBtn(schedBtn); return; }
      var notesBtn = e.target.closest('.co-notes-btn');
      if (notesBtn && !notesBtn.disabled) { _onNotesBtn(notesBtn); return; }
    });
  }

  function _onPromote(btn) {
    var appId = parseInt(btn.getAttribute('data-app-id'), 10);
    if (!appId || btn.disabled) return;
    var card = document.querySelector('#coAppList .co-app-card[data-app-id="' + appId + '"]');
    _execPromote(appId, card, btn);
  }

  function _execPromote(appId, card, promoteBtn) {
    if (promoteBtn) {
      promoteBtn.disabled    = true;
      promoteBtn.textContent = 'جارٍ الترقية…';
    }
    var jwt = window._jwt ? _jwt() : '';
    fetch('/jobs/applications/' + appId + '/promote', {
      method:  'POST',
      headers: { 'Authorization': 'Bearer ' + jwt }
    })
    .then(function (r) {
      if (!r.ok) { var e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
      return r.json();
    })
    .then(function (data) {
      if (card) {
        _reRenderCardFoot(card, 'accepted');
      }
      if (promoteBtn) { promoteBtn.disabled = false; }
      // Dispatch cross-IIFE event so Saved Candidates screen syncs without refresh
      if (data && data.candidate_id && data.job_id) {
        document.dispatchEvent(new CustomEvent('tw:candidate-job-classification-updated', { detail: {
          candidateId:       data.candidate_id,
          jobId:             data.job_id,
          applicationStatus: data.application_status || 'accepted',
          candidateStatus:   data.candidate_status   || 'shortlisted',
          generalStatus:     data.general_status      || null
        }}));
      }
      if (window._loadCandidatesBadge) window._loadCandidatesBadge();
      if (window.showToast) showToast('تم تصنيف المرشح بنجاح ✓');
    })
    .catch(function (err) {
      if (promoteBtn) {
        promoteBtn.disabled    = false;
        promoteBtn.textContent = promoteBtn.dataset.origText || 'ترشيح للوظيفة ▾';
      }
      var status = err && err.status;
      var msg;
      if (status === 403) msg = 'انتهت الجلسة أو لا تملك صلاحية الترقية';
      else if (status === 404) msg = 'الطلب غير موجود';
      else if (status === 401) msg = 'انتهت الجلسة — سجّل دخولك مجدداً';
      else                     msg = 'تعذّرت الترقية، حاول مجدداً';
      if (window.showToast) showToast(msg, 'error');
    });
  }

  function _onSaveApplicant(btn) {
    var uid = parseInt(btn.getAttribute('data-uid'), 10);
    if (!uid || btn.disabled) return;
    btn.disabled    = true;
    btn.textContent = 'جارٍ الحفظ…';
    var jwt     = window._jwt ? _jwt() : '';
    var jobSufx = (_appJobId ? '?job_id=' + parseInt(_appJobId, 10) : '');
    fetch('/company/saved-candidates/' + uid + jobSufx, {
      method:  'POST',
      headers: { 'Authorization': 'Bearer ' + jwt }
    })
    .then(function (r) {
      if (!r.ok) return r.json().then(function (d) { throw new Error(d.detail || 'error'); });
      return r.json();
    })
    .then(function () {
      btn.textContent = 'تم الحفظ ✓';
      btn.classList.add('saved');
      btn.disabled = true;
      if (window._loadCandidatesBadge) window._loadCandidatesBadge();
    })
    .catch(function (err) {
      btn.disabled    = false;
      btn.textContent = '+ حفظ المرشح';
      if (window.showToast) showToast((err && err.message) || 'تعذّر حفظ المرشح', 'error');
    });
  }

  // ── Save applicant to Talent Bank ──────────────────────────────
  function _onSaveToTalentBank(btn) {
    var uid = parseInt(btn.getAttribute('data-uid'), 10);
    if (!uid || btn.disabled || btn.getAttribute('data-saved') === '1') return;
    btn.disabled    = true;
    btn.textContent = 'جارٍ الحفظ…';
    var jwt     = window._jwt ? _jwt() : '';
    var jobSufx = (_appJobId ? '?job_id=' + parseInt(_appJobId, 10) : '');
    fetch('/company/saved-candidates/' + uid + jobSufx, {
      method:  'POST',
      headers: { 'Authorization': 'Bearer ' + jwt }
    })
    .then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, status: r.status, data: d }; });
    })
    .then(function (res) {
      if (res.status === 409 && res.data && res.data.code === 'talent_bank_limit_reached') {
        btn.disabled    = false;
        btn.textContent = 'حفظ في بنك المواهب';
        var body = res.data;
        if (window.showToast) showToast(
          'وصلت للحد المجاني لبنك المواهب: ' + body.used + ' من ' + body.limit
          + '. احذف موهبة محفوظة أو قم بترقية الخطة لإضافة شخص جديد.',
          'error');
        return;
      }
      if (!res.ok) {
        btn.disabled    = false;
        btn.textContent = 'حفظ في بنك المواهب';
        var status = res.status;
        var msg = (status === 401 || status === 403)
          ? 'انتهت الجلسة أو لا تملك صلاحية الحفظ'
          : 'تعذّر الحفظ في بنك المواهب، حاول مجدداً';
        if (window.showToast) showToast(msg, 'error');
        return;
      }
      btn.textContent = 'محفوظ في بنك المواهب ✓';
      btn.setAttribute('data-saved', '1');
      btn.classList.add('co-talentbank-btn--saved');
      btn.disabled = true;
      if (window.showToast) showToast('تم الحفظ في بنك المواهب ✓');
      if (window._loadCandidatesBadge) window._loadCandidatesBadge();
    })
    .catch(function () {
      btn.disabled    = false;
      btn.textContent = 'حفظ في بنك المواهب';
      if (window.showToast) showToast('تعذّر الحفظ في بنك المواهب، حاول مجدداً', 'error');
    });
  }

  // ── Appointment scheduling — index, modal, submit ──────────────

  function _isApptActive(status) {
    return ['cancelled', 'expired', 'missed', 'closed'].indexOf(status) === -1;
  }

  function _isApptDraft(status) { return status === 'draft'; }

  function _loadApptIndex(cb) {
    var jwt = window._jwt ? _jwt() : '';
    if (!jwt) { if (cb) cb(); return; }
    fetch('/api/appointments', {
      headers: { 'Authorization': 'Bearer ' + jwt }
    })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      var items = Array.isArray(d) ? d : (d.data || d.appointments || []);
      _apptByAppId   = {};
      _apptByEntryId = {};
      items.forEach(function (a) {
        var info = { id: a.id, status: a.computed_status || a.status };
        if (a.application_id != null) {
          _apptByAppId[String(a.application_id)] = info;
        }
        if (a.pipeline_entry_id != null) {
          _apptByEntryId[String(a.pipeline_entry_id)] = info;
        }
      });
      _apptIndexLoaded = true;
      if (cb) cb();
    })
    .catch(function () { if (cb) cb(); });
  }

  function _applyApptIndexToCards() {
    var cards = document.querySelectorAll('#coAppList .co-app-card');
    cards.forEach(function (card) {
      var appId   = card.getAttribute('data-app-id');
      var entryId = card.getAttribute('data-entry-id');
      // Prefer entry-id lookup (more specific), fall back to app-id
      var entry   = (entryId && _apptByEntryId[entryId])
                    || (appId && _apptByAppId[appId]);
      if (!entry || !_isApptActive(entry.status) || _isApptDraft(entry.status)) return;
      var foot = card.querySelector('.co-app-card-foot');
      if (!foot) return;
      var btn = foot.querySelector('.co-app-sched-btn');
      if (!btn) return;
      var link = document.createElement('a');
      link.href      = '/appointment-room?id=' + entry.id;
      link.className = 'co-app-open-appt-btn co-app-act';
      link.textContent = 'فتح الموعد';
      link.target    = '_blank';
      link.rel       = 'noopener';
      foot.replaceChild(link, btn);
    });
  }

  function _onSchedBtn(btn) {
    if (btn.disabled) return;
    var appId   = parseInt(btn.getAttribute('data-app-id'), 10) || 0;
    var entryId = parseInt(btn.getAttribute('data-entry-id'), 10) || 0;
    var uid     = parseInt(btn.getAttribute('data-uid'), 10) || 0;

    var card = appId
      ? document.querySelector('#coAppList .co-app-card[data-app-id="' + appId + '"]')
      : document.querySelector('#coAppList .co-app-card[data-entry-id="' + entryId + '"]');
    var applName = card ? card.getAttribute('data-name') : '';
    var job = window.companyState && companyState.jobs
      ? companyState.jobs.find(function (j) { return j.id == _appJobId; })
      : null;
    var jobTitle = job ? job.title : '';

    if (_apptIndexLoaded) {
      var entry = (entryId && _apptByEntryId[String(entryId)])
                  || (appId && _apptByAppId[String(appId)]);
      if (entry && _isApptActive(entry.status)) {
        if (_isApptDraft(entry.status)) {
          _openApptModal(appId || null, applName, jobTitle, entryId || null, uid || null);
          return;
        }
        window.open('/appointment-room?id=' + entry.id, '_blank');
        return;
      }
    }
    _openApptModal(appId || null, applName, jobTitle, entryId || null, uid || null);
  }

  function _openApptModal(appId, applName, jobTitle, entryId, candidateId) {
    _apptCurrentAppId       = appId       || null;
    _apptCurrentEntryId     = entryId     || null;
    _apptCurrentCandidateId = candidateId || null;
    var el = document.getElementById('coApptModal');
    if (!el) return;
    // Fill static info
    var nameEl = document.getElementById('coApptApplName');
    var jobEl  = document.getElementById('coApptJobName');
    if (nameEl) nameEl.textContent = applName || '—';
    if (jobEl)  jobEl.textContent  = jobTitle  || '—';
    // Show retry hint if an orphaned draft exists (check both indexes)
    var existEntry = (_apptCurrentEntryId && _apptByEntryId[String(_apptCurrentEntryId)])
                     || (_apptCurrentAppId && _apptByAppId[String(_apptCurrentAppId)]);
    var isDraftRetry = !!(existEntry && _isApptDraft(existEntry.status));
    var retryHint = document.getElementById('coApptRetryHint');
    if (retryHint) retryHint.style.display = isDraftRetry ? '' : 'none';
    // Reset all form fields
    var fields = ['coApptDate','coApptTime','coApptUrl','coApptLoc','coApptNotes','coApptRep'];
    fields.forEach(function (id) {
      var inp = document.getElementById(id);
      if (inp) inp.value = (id === 'coApptTime') ? '10:00' : '';
    });
    var deadlineEl = document.getElementById('coApptDeadline');
    if (deadlineEl) deadlineEl.value = '48';
    _apptMode = 'online';
    _setApptMode('online');
    var submitBtn = document.getElementById('coApptSubmit');
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = isDraftRetry ? 'إعادة الإرسال' : 'إرسال الدعوة'; }
    _apptInFlight = false;
    _initApptModalListeners();
    el.style.display = 'flex';
  }

  function _closeApptModal() {
    var el = document.getElementById('coApptModal');
    if (el) el.style.display = 'none';
    _apptCurrentAppId       = null;
    _apptCurrentEntryId     = null;
    _apptCurrentCandidateId = null;
    _apptInFlight = false;
  }

  function _setApptMode(mode) {
    _apptMode = mode;
    var onlineBtn = document.getElementById('coApptModeOnline');
    var onsiteBtn = document.getElementById('coApptModeOnsite');
    var urlRow    = document.getElementById('coApptUrlRow');
    var locRow    = document.getElementById('coApptLocRow');
    if (onlineBtn) onlineBtn.classList.toggle('active', mode === 'online');
    if (onsiteBtn) onsiteBtn.classList.toggle('active', mode === 'onsite');
    if (urlRow)    urlRow.style.display = (mode === 'online') ? '' : 'none';
    if (locRow)    locRow.style.display = (mode === 'onsite') ? '' : 'none';
  }

  function _initApptModalListeners() {
    if (_apptModalInited) return;
    _apptModalInited = true;
    var el = document.getElementById('coApptModal');
    if (!el) return;
    el.addEventListener('click', function (e) {
      if (e.target === el) _closeApptModal();
    });
    var closeBtn = el.querySelector('.co-fl-close');
    if (closeBtn) closeBtn.addEventListener('click', _closeApptModal);
    var onlineBtn = document.getElementById('coApptModeOnline');
    var onsiteBtn = document.getElementById('coApptModeOnsite');
    if (onlineBtn) onlineBtn.addEventListener('click', function () { _setApptMode('online'); });
    if (onsiteBtn) onsiteBtn.addEventListener('click', function () { _setApptMode('onsite'); });
    var submitBtn = document.getElementById('coApptSubmit');
    if (submitBtn) submitBtn.addEventListener('click', _submitApptForm);
  }

  function _submitApptForm() {
    if (_apptInFlight) return;
    var appId   = _apptCurrentAppId;
    var entryId = _apptCurrentEntryId;
    var uid     = _apptCurrentCandidateId;
    // Must have either application_id (Path A) or candidate_id + job_id (Path B)
    if (!appId && !(uid && _appJobId)) {
      if (window.showToast) showToast('بيانات الموعد غير مكتملة', 'error');
      return;
    }

    var g = function (id) { return (document.getElementById(id) || {}).value || ''; };
    var dateVal     = g('coApptDate');
    var timeVal     = g('coApptTime') || '09:00';
    var urlVal      = g('coApptUrl');
    var locVal      = g('coApptLoc');
    var notesVal    = g('coApptNotes');
    var deadlineVal = parseInt(g('coApptDeadline') || '48', 10) || 48;
    var repVal      = g('coApptRep');

    if (!dateVal) {
      if (window.showToast) showToast('يرجى تحديد تاريخ المقابلة', 'error');
      return;
    }

    if (_apptMode === 'online' && !urlVal) {
      if (window.showToast) showToast('يرجى إدخال رابط المقابلة الأونلاين', 'error');
      return;
    }
    if (_apptMode === 'onsite' && !locVal) {
      if (window.showToast) showToast('يرجى إدخال موقع المقابلة', 'error');
      return;
    }

    // Convert user's local datetime to UTC ISO (Z-suffix) — backend rejects naive ISO
    var localScheduled = new Date(dateVal + 'T' + timeVal + ':00');
    if (!Number.isFinite(localScheduled.getTime())) {
      if (window.showToast) showToast('تاريخ أو وقت غير صالح', 'error');
      return;
    }
    var scheduledAt = localScheduled.toISOString(); // always Z-suffix

    var scheduledMs = localScheduled.getTime();
    var deadlineMs  = deadlineVal * 60 * 60 * 1000;
    if (scheduledMs - Date.now() <= deadlineMs) {
      if (window.showToast) showToast('مهلة الرد تنتهي بعد وقت الموعد — اختر موعداً أبعد أو مهلة أقصر', 'error');
      return;
    }
    _apptInFlight = true;
    var submitBtn = document.getElementById('coApptSubmit');
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'جارٍ الإرسال…'; }

    var jwt = window._jwt ? _jwt() : '';

    // If an orphaned draft exists, skip create and retry send directly
    var existingEntry = (entryId && _apptByEntryId[String(entryId)])
                        || (appId && _apptByAppId[String(appId)]);
    if (existingEntry && _isApptDraft(existingEntry.status)) {
      _execSendStep(existingEntry.id, appId, jwt, scheduledAt, deadlineVal, urlVal, locVal, notesVal, repVal, submitBtn);
      return;
    }

    // Build create body: Path A (application_id) or Path B (candidate_id + job_id)
    var createBody;
    if (appId) {
      // Path A
      createBody = {
        application_id:      appId,
        mode:                _apptMode,
        notes:               notesVal  || null,
        online_url:          urlVal    || null,
        location_text:       locVal    || null,
        representative_name: repVal    || null
      };
    } else {
      // Path B — pipeline
      createBody = {
        candidate_id:        uid,
        job_id:              parseInt(_appJobId, 10),
        appointment_type:    'interview',
        mode:                _apptMode,
        notes:               notesVal  || null,
        online_url:          urlVal    || null,
        location_text:       locVal    || null,
        representative_name: repVal    || null
      };
    }

    fetch('/api/appointments', {
      method:  'POST',
      headers: { 'Authorization': 'Bearer ' + jwt, 'Content-Type': 'application/json' },
      body:    JSON.stringify(createBody)
    })
    .then(function (r) {
      if (!r.ok) {
        return r.json().then(function (d) {
          var e = new Error('HTTP ' + r.status); e.status = r.status; e.detail = d.detail || d.message; throw e;
        });
      }
      return r.json();
    })
    .then(function (d) {
      var apptId = d.data && d.data.id;
      if (!apptId) throw new Error('missing appointment id');
      // Store draft in index — if send fails, next retry reuses this id
      var info = { id: apptId, status: 'draft' };
      if (appId)   _apptByAppId[String(appId)]     = info;
      if (entryId) _apptByEntryId[String(entryId)] = info;
      _execSendStep(apptId, appId, jwt, scheduledAt, deadlineVal, urlVal, locVal, notesVal, repVal, submitBtn);
    })
    .catch(function (err) {
      _apptInFlight = false;
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'إرسال الدعوة'; }
      var status = err && err.status;
      var detail = (err && err.detail) || '';
      var msg;
      if (detail.indexOf('يوجد موعد نشط') !== -1) {
        _loadApptIndex(function () { _applyApptIndexToCards(); });
        msg = 'يوجد موعد نشط — تحقق من صفحة المواعيد';
      } else if (status === 409) {
        msg = detail || 'لا يمكن إنشاء الموعد — تحقق من البيانات';
      } else if (status === 403) {
        msg = 'انتهت الجلسة أو لا تملك صلاحية إنشاء المواعيد';
      } else if (status === 401) {
        msg = 'انتهت الجلسة — سجّل دخولك مجدداً';
      } else {
        msg = detail || 'تعذّر إنشاء الموعد، حاول مجدداً';
      }
      if (window.showToast) showToast(msg, 'error');
    });
  }

  // Handles the /send step independently — draft is preserved in _apptByAppId on failure,
  // so _submitApptForm will skip create and call _execSendStep directly on the next attempt.
  function _execSendStep(apptId, appId, jwt, scheduledAt, deadlineVal, urlVal, locVal, notesVal, repVal, submitBtn) {
    var sendBody = {
      scheduled_at:        scheduledAt,
      deadline_hours:      deadlineVal,
      online_url:          urlVal   || null,
      location_text:       locVal   || null,
      notes:               notesVal || null,
      representative_name: repVal   || null
    };
    fetch('/api/appointments/' + apptId + '/send', {
      method:  'POST',
      headers: { 'Authorization': 'Bearer ' + jwt, 'Content-Type': 'application/json' },
      body:    JSON.stringify(sendBody)
    })
    .then(function (r) {
      if (!r.ok) {
        return r.json().then(function (d) {
          var e = new Error('HTTP ' + r.status); e.status = r.status; e.detail = d.detail; throw e;
        });
      }
      return r.json();
    })
    .then(function () {
      // Update both indexes to sent state
      var sentInfo = { id: apptId, status: 'pending_response' };
      if (appId) _apptByAppId[String(appId)] = sentInfo;
      if (_apptCurrentEntryId) _apptByEntryId[String(_apptCurrentEntryId)] = sentInfo;
      var card = appId
        ? document.querySelector('#coAppList .co-app-card[data-app-id="' + appId + '"]')
        : (_apptCurrentEntryId
            ? document.querySelector('#coAppList .co-app-card[data-entry-id="' + _apptCurrentEntryId + '"]')
            : null);
      if (card) {
        var foot = card.querySelector('.co-app-card-foot');
        var oldBtn = foot ? (foot.querySelector('.co-app-sched-btn') || foot.querySelector('.co-app-open-appt-btn')) : null;
        if (oldBtn && foot) {
          var link = document.createElement('a');
          link.href      = '/appointment-room?id=' + apptId;
          link.className = 'co-app-open-appt-btn co-app-act';
          link.textContent = 'فتح الموعد';
          link.target    = '_blank';
          link.rel       = 'noopener';
          foot.replaceChild(link, oldBtn);
        }
      }
      _closeApptModal();
      if (window.showToast) showToast('تم إرسال دعوة المقابلة بنجاح ✓');
      location.href = '/appointment-room?id=' + apptId;
    })
    .catch(function (err) {
      // Draft entry stays in _apptByAppId — next open of the modal shows retry UI
      _apptInFlight = false;
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'إعادة الإرسال'; }
      var status = err && err.status;
      var detail = (err && err.detail) || '';
      var msg;
      if (status === 403) {
        msg = 'انتهت الجلسة أو لا تملك صلاحية إرسال الدعوة';
      } else if (status === 401) {
        msg = 'انتهت الجلسة — سجّل دخولك مجدداً';
      } else if (detail) {
        msg = detail;
      } else {
        msg = 'أُنشئ الموعد لكن تعذّر الإرسال — اضغط "إعادة الإرسال"';
      }
      if (window.showToast) showToast(msg, 'error');
    });
  }

  // ── Pipeline Notes Panel ────────────────────────────────────────
  function _onNotesBtn(btn) {
    var entryId = parseInt(btn.getAttribute('data-entry-id'), 10);
    if (!entryId) return;
    _openNotesPanel(entryId);
  }

  function _openNotesPanel(entryId) {
    _notesCurrentEntryId = entryId;
    var el = document.getElementById('coNotesModal');
    if (!el) return;
    var listEl = document.getElementById('coNotesList');
    if (listEl) listEl.innerHTML = '<div class="co-app-spin">جارٍ التحميل…</div>';
    var inp = document.getElementById('coNotesInput');
    if (inp) inp.value = '';
    _notesInFlight = false;
    _initNotesModalListeners();
    el.style.display = 'flex';
    _loadPanelNotes(entryId);
  }

  function _closeNotesPanel() {
    var el = document.getElementById('coNotesModal');
    if (el) el.style.display = 'none';
    _notesCurrentEntryId = null;
    _notesInFlight = false;
  }

  function _initNotesModalListeners() {
    if (_notesModalInited) return;
    _notesModalInited = true;
    var el = document.getElementById('coNotesModal');
    if (!el) return;
    el.addEventListener('click', function (e) {
      if (e.target === el) _closeNotesPanel();
    });
    var closeBtn = document.getElementById('coNotesClose');
    if (closeBtn) closeBtn.addEventListener('click', _closeNotesPanel);
    var submitBtn = document.getElementById('coNotesSubmit');
    if (submitBtn) submitBtn.addEventListener('click', _submitNote);
    var listEl = document.getElementById('coNotesList');
    if (listEl) listEl.addEventListener('click', function (e) {
      var delBtn = e.target.closest('.co-note-del');
      if (delBtn && !delBtn.disabled) _deleteNote(delBtn);
    });
  }

  function _loadPanelNotes(entryId) {
    var listEl = document.getElementById('coNotesList');
    if (!listEl) return;
    var jwt = window._jwt ? _jwt() : '';
    if (!jwt) {
      listEl.innerHTML = '<div class="co-app-empty">يجب تسجيل الدخول أولاً</div>';
      return;
    }
    fetch('/company/pipeline/' + entryId + '/notes', {
      headers: { 'Authorization': 'Bearer ' + jwt }
    })
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (d) {
      var notes = (d && d.data && Array.isArray(d.data.notes)) ? d.data.notes : [];
      _renderPanelNotes(notes, listEl);
    })
    .catch(function () {
      if (listEl) listEl.innerHTML = '<div class="co-app-empty">تعذّر تحميل الملاحظات</div>';
    });
  }

  function _renderPanelNotes(notes, listEl) {
    if (!listEl) return;
    if (!notes.length) {
      listEl.innerHTML = '<div class="co-app-empty">لا توجد ملاحظات بعد</div>';
      return;
    }
    var html = '';
    notes.forEach(function (n) {
      var noteId = parseInt(n.id, 10);
      html += '<div class="co-note-item" data-note-id="' + noteId + '">'
        + '<div class="co-note-body"></div>'
        + '<button type="button" class="co-note-del" data-note-id="' + noteId + '">×</button>'
        + '</div>';
    });
    listEl.innerHTML = html;
    // Set body text safely (XSS: textContent only)
    var items = listEl.querySelectorAll('.co-note-item');
    notes.forEach(function (n, i) {
      var bodyEl = items[i] && items[i].querySelector('.co-note-body');
      if (bodyEl) bodyEl.textContent = n.body || '';
    });
  }

  function _submitNote() {
    if (_notesInFlight) return;
    var entryId = _notesCurrentEntryId;
    if (!entryId) return;
    var inp = document.getElementById('coNotesInput');
    var body = inp ? inp.value.trim() : '';
    if (!body) {
      if (window.showToast) showToast('أدخل نص الملاحظة', 'error');
      return;
    }
    _notesInFlight = true;
    var submitBtn = document.getElementById('coNotesSubmit');
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'جارٍ الحفظ…'; }
    var jwt = window._jwt ? _jwt() : '';
    fetch('/company/pipeline/' + entryId + '/notes', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + jwt, 'Content-Type': 'application/json' },
      body: JSON.stringify({ body: body })
    })
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function () {
      if (inp) inp.value = '';
      _notesInFlight = false;
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'إضافة'; }
      _loadPanelNotes(entryId);
      // Refresh notes count on the card
      _refreshCardNotesCount(entryId);
    })
    .catch(function () {
      _notesInFlight = false;
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'إضافة'; }
      if (window.showToast) showToast('تعذّر حفظ الملاحظة', 'error');
    });
  }

  function _deleteNote(delBtn) {
    var noteId = parseInt(delBtn.getAttribute('data-note-id'), 10);
    if (!noteId) return;
    var entryId = _notesCurrentEntryId;
    delBtn.disabled = true;
    var jwt = window._jwt ? _jwt() : '';
    fetch('/company/pipeline/notes/' + noteId, {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer ' + jwt }
    })
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function () {
      _loadPanelNotes(entryId);
      _refreshCardNotesCount(entryId);
    })
    .catch(function () {
      delBtn.disabled = false;
      if (window.showToast) showToast('تعذّر حذف الملاحظة', 'error');
    });
  }

  function _refreshCardNotesCount(entryId) {
    // Reload applicants to get updated count — lightweight approach
    if (_appJobId) _loadApplicants(_appJobId);
  }

  // ── Classify dropdown — 7-option save/classify portal ─────────
  function _initClassifyFloat() {
    if (_astFloat) return;
    _astFloat = document.createElement('div');
    _astFloat.className     = 'co-ast-float';
    _astFloat.style.display = 'none';
    _astFloat.innerHTML =
      '<button class="co-ast-opt" data-val="pending">محفوظ</button>'
      + '<button class="co-ast-opt" data-val="viewed">للمراجعة</button>'
      + '<button class="co-ast-opt" data-val="accepted">مرشح قوي</button>'
      + '<button class="co-ast-opt" data-val="contacted">تم التواصل</button>'
      + '<button class="co-ast-opt" data-val="interview">مقابلة</button>'
      + '<button class="co-ast-opt" data-val="hired">تم التوظيف</button>'
      + '<button class="co-ast-opt co-ast-opt--reject" data-val="rejected">غير مناسب</button>';
    document.body.appendChild(_astFloat);

    _astFloat.addEventListener('click', function (e) {
      var opt = e.target.closest('.co-ast-opt');
      if (!opt || !_astFloatTrigger) { _closeClassifyFloat(); return; }
      var newStatus  = opt.getAttribute('data-val');
      var trigger    = _astFloatTrigger;
      var appId      = parseInt(trigger.getAttribute('data-app-id'), 10);
      var prevStatus = trigger.getAttribute('data-status');
      var isSaved    = trigger.getAttribute('data-saved') === '1';
      var card       = document.querySelector('#coAppList .co-app-card[data-app-id="' + appId + '"]');
      _closeClassifyFloat();
      if (newStatus === prevStatus && isSaved) return;
      if (newStatus === 'interview') {
        // Stop propagation: without this, the document outside-click handler
        // immediately closes _icFloat on the same click event that opened it.
        e.stopPropagation();
        _showInterviewChoice(trigger, appId, prevStatus, isSaved, card);
        return;
      }
      _execClassify(appId, newStatus, card, trigger, prevStatus, isSaved, null);
    });

    document.addEventListener('click', function (e) {
      if (_astFloat && _astFloat.style.display !== 'none') {
        if (!_astFloat.contains(e.target) &&
            (!_astFloatTrigger || !_astFloatTrigger.contains(e.target))) {
          _closeClassifyFloat();
        }
      }
      if (_icFloat && _icFloat.style.display !== 'none') {
        if (!_icFloat.contains(e.target) &&
            (!_icFloatTrigger || !_icFloatTrigger.contains(e.target))) {
          _closeInterviewChoice();
        }
      }
    });

    var appList = document.getElementById('coAppList');
    if (appList) { appList.addEventListener('scroll', _closeClassifyFloat, { passive: true }); }
  }

  function _openClassifyFloat(triggerBtn) {
    _initClassifyFloat();
    var isSame = _astFloatTrigger === triggerBtn && _astFloat.style.display !== 'none';
    _closeClassifyFloat();
    if (isSame) return;
    _astFloatTrigger = triggerBtn;

    var currentStatus = triggerBtn.getAttribute('data-status') || '';
    var isHired       = triggerBtn.getAttribute('data-hired') === '1';
    var rejectOpt     = _astFloat.querySelector('.co-ast-opt--reject');
    if (rejectOpt) rejectOpt.style.display = isHired ? 'none' : '';

    _astFloat.style.display = 'block';
    var rect  = triggerBtn.getBoundingClientRect();
    var menuW = _astFloat.offsetWidth  || 180;
    var menuH = _astFloat.offsetHeight || 220;
    var vpW   = window.innerWidth;
    var vpH   = window.innerHeight;
    var left  = rect.right - menuW;
    if (left < 8) left = 8;
    if (left + menuW > vpW - 8) left = vpW - menuW - 8;
    var top;
    if (vpH - rect.bottom >= menuH + 8) {
      top = rect.bottom + 4;
    } else {
      top = rect.top - menuH - 4;
      if (top < 8) top = rect.bottom + 4;
    }
    _astFloat.style.left = left + 'px';
    _astFloat.style.top  = top  + 'px';

    _astFloat.querySelectorAll('.co-ast-opt').forEach(function (o) {
      o.classList.toggle('co-ast-current', o.getAttribute('data-val') === currentStatus);
    });
  }

  function _closeClassifyFloat() {
    if (_astFloat) _astFloat.style.display = 'none';
    _astFloatTrigger = null;
  }

  // ── Interview choice mini-portal (الآن / لاحقاً) ───────────────
  function _showInterviewChoice(classifyBtn, appId, prevStatus, isSaved, card) {
    if (!_icFloat) {
      _icFloat = document.createElement('div');
      _icFloat.className     = 'co-ic-float';
      _icFloat.style.display = 'none';
      _icFloat.innerHTML =
        '<div class="co-ic-prompt">تحديد موعد المقابلة؟</div>'
        + '<div class="co-ic-btns">'
        +   '<button class="co-ic-btn co-ic-btn--now">الآن</button>'
        +   '<button class="co-ic-btn co-ic-btn--later">لاحقاً</button>'
        + '</div>';
      document.body.appendChild(_icFloat);
    }
    _icFloatTrigger = classifyBtn;
    _icFloatAppId   = appId;
    _icPrevStatus   = prevStatus;

    _icFloat.style.display = 'block';
    var rect  = classifyBtn.getBoundingClientRect();
    var menuW = _icFloat.offsetWidth  || 170;
    var menuH = _icFloat.offsetHeight || 80;
    var vpW   = window.innerWidth;
    var vpH   = window.innerHeight;
    var left  = rect.right - menuW;
    if (left < 8) left = 8;
    if (left + menuW > vpW - 8) left = vpW - menuW - 8;
    var top = (vpH - rect.bottom >= menuH + 8) ? rect.bottom + 4 : rect.top - menuH - 4;
    if (top < 8) top = rect.bottom + 4;
    _icFloat.style.left = left + 'px';
    _icFloat.style.top  = top  + 'px';

    var nowBtn   = _icFloat.querySelector('.co-ic-btn--now');
    var laterBtn = _icFloat.querySelector('.co-ic-btn--later');

    if (nowBtn) nowBtn.onclick = function () {
      var aId = _icFloatAppId, prv = _icPrevStatus, sv = isSaved;
      var c = card, cBtn = _icFloatTrigger;
      _closeInterviewChoice();
      _execClassify(aId, 'interview', c, cBtn, prv, sv, function () {
        var name = c ? c.getAttribute('data-name') : '';
        var job  = window.companyState && companyState.jobs
          ? companyState.jobs.find(function (j) { return j.id == _appJobId; })
          : null;
        _openApptModal(aId, name, job ? job.title : '');
      });
    };

    if (laterBtn) laterBtn.onclick = function () {
      var aId = _icFloatAppId, prv = _icPrevStatus, sv = isSaved;
      var c = card, cBtn = _icFloatTrigger;
      _closeInterviewChoice();
      _execClassify(aId, 'interview', c, cBtn, prv, sv, null);
    };
  }

  function _closeInterviewChoice() {
    if (_icFloat) _icFloat.style.display = 'none';
    _icFloatTrigger = null;
    _icFloatAppId   = null;
    _icPrevStatus   = null;
  }

  // ── Classify: save candidate + set application status ──────────
  function _execClassify(appId, newStatus, card, classifyBtn, prevStatus, wasSaved, onSuccess) {
    var jwt = window._jwt ? _jwt() : '';

    // "مرشح قوي" uses the promote endpoint (atomic save + accept)
    if (newStatus === 'accepted') {
      if (classifyBtn) {
        classifyBtn.dataset.origText = classifyBtn.textContent;
        classifyBtn.disabled    = true;
        classifyBtn.textContent = 'جارٍ التصنيف…';
      }
      _execPromote(appId, card, classifyBtn);
      return;
    }

    // Optimistic badge update
    if (card) _applyClassifyBadge(card, newStatus);
    if (classifyBtn) {
      classifyBtn.disabled    = true;
      classifyBtn.textContent = 'جارٍ التصنيف…';
    }

    // Single atomic request — backend writes job_applications.status AND
    // company_candidate_job_refs.candidate_status in one transaction (pipeline dual-write).
    // Does NOT write to company_saved_candidates (Talent Bank independence — PR-3).
    fetch('/jobs/applications/' + appId + '/status', {
      method:  'PUT',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + jwt },
      body:    JSON.stringify({ status: newStatus })
    })
      .then(function (r) {
        if (!r.ok) { var e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
        return r.json();
      })
      .then(function (data) {
        if (card) {
          _reRenderCardFoot(card, newStatus);
          if (_apptIndexLoaded) _applyApptIndexToCards();
        }
        // Dispatch cross-IIFE event so Saved Candidates screen syncs without refresh.
        // Event is only dispatched on success — never on error.
        if (data && data.candidate_id && data.job_id) {
          document.dispatchEvent(new CustomEvent('tw:candidate-job-classification-updated', { detail: {
            candidateId:       data.candidate_id,
            jobId:             data.job_id,
            applicationStatus: data.application_status || newStatus,
            candidateStatus:   data.candidate_status   !== undefined ? data.candidate_status : null,
            generalStatus:     data.general_status      || null
          }}));
        }
        if (window._loadCandidatesBadge) window._loadCandidatesBadge();
        if (window.showToast) showToast('تم التصنيف بنجاح ✓');
        if (onSuccess) onSuccess();
      })
      .catch(function (err) {
        var msg = (err && (err.status === 401 || err.status === 403))
          ? 'انتهت الجلسة أو لا تملك صلاحية التصنيف'
          : 'تعذّر التصنيف، حاول مجدداً';
        if (window.showToast) showToast(msg, 'error');
        if (_appJobId) {
          _loadApplicants(_appJobId);
        } else {
          if (card) _applyClassifyBadge(card, prevStatus);
          if (classifyBtn) {
            classifyBtn.disabled    = false;
            var wasFresh = !wasSaved && (!prevStatus || prevStatus === 'pending');
            classifyBtn.textContent = wasFresh ? 'ترشيح للوظيفة ▾' : 'تعديل التصنيف ▾';
          }
        }
      });
  }

  function _applyClassifyBadge(card, statusKey) {
    if (!statusKey) return;
    var badge = card.querySelector('.co-app-status');
    if (badge) {
      badge.textContent = _APP_STATUS_LABEL[statusKey] || statusKey;
      badge.className   = 'co-app-status co-app-status--' + statusKey;
    }
  }

  function _reRenderCardFoot(card, statusKey) {
    var appId       = parseInt(card.getAttribute('data-app-id'), 10);
    var uid         = parseInt(card.getAttribute('data-uid'), 10);
    var twId        = card.getAttribute('data-tw-id') || '';
    var isRejected  = statusKey === 'rejected';
    var isHired     = statusKey === 'hired';
    var isInterview = statusKey === 'interview';

    // Update or create status badge
    var statusLbl = _APP_STATUS_LABEL[statusKey] || statusKey;
    var badge = card.querySelector('.co-app-status');
    if (badge) {
      badge.textContent = statusLbl;
      badge.className   = 'co-app-status co-app-status--' + statusKey;
    } else {
      var head = card.querySelector('.co-app-card-head');
      if (head) {
        var nb = document.createElement('span');
        nb.className   = 'co-app-status co-app-status--' + statusKey;
        nb.textContent = statusLbl;
        head.appendChild(nb);
      }
    }

    if (isRejected) {
      card.classList.add('co-app-card--rejected');
    } else {
      card.classList.remove('co-app-card--rejected');
    }

    var viewHtml = twId
      ? '<a class="co-app-view-btn co-app-act" href="/u/' + _escApp(twId) + '" target="_blank" rel="noopener">عرض الملف الكامل</a>'
      : '';

    var classifyLbl  = isRejected ? 'إعادة التصنيف ▾' : 'تعديل التصنيف ▾';
    var classifyHtml = '<button type="button" class="co-classify-btn co-app-act'
      + (isRejected ? ' co-classify-btn--reclassify' : '')
      + '" data-app-id="' + appId + '" data-status="' + _escApp(statusKey) + '"'
      + ' data-uid="' + uid + '"'
      + (isHired ? ' data-hired="1"' : '')
      + '>' + classifyLbl + '</button>';

    // Preserve talent bank saved state from the existing DOM
    var existingTb   = card.querySelector('.co-talentbank-btn');
    var tbAlreadySaved = existingTb ? existingTb.getAttribute('data-saved') === '1' : false;
    var tbLbl        = tbAlreadySaved ? 'محفوظ في بنك المواهب ✓' : 'حفظ في بنك المواهب';
    var talentHtml   = '<button type="button" class="co-talentbank-btn co-app-act'
      + (tbAlreadySaved ? ' co-talentbank-btn--saved' : '')
      + '" data-uid="' + uid + '" data-saved="' + (tbAlreadySaved ? '1' : '0') + '"'
      + (tbAlreadySaved ? ' disabled' : '')
      + '>' + tbLbl + '</button>';

    var schedHtml = isInterview
      ? '<button type="button" class="co-app-sched-btn co-app-act" data-app-id="' + appId + '">تحديد موعد</button>'
      : '';

    var foot = card.querySelector('.co-app-card-foot');
    if (foot) foot.innerHTML = viewHtml + classifyHtml + talentHtml + schedHtml;
  }

  // Back button: close the topmost open modal on popstate.
  // Always clear the flag BEFORE calling close so the close fn does not re-fire history.back().
  window.addEventListener('popstate', function () {
    // edit modal (highest z-order — check first)
    var editEl = document.getElementById('editOverlay');
    if (editEl && editEl.classList.contains('show')) {
      _editHistoryPushed = false;
      closeEdit();
      return;
    }
    // contact modal
    var contactEl = document.getElementById('contactOverlay');
    if (contactEl && contactEl.classList.contains('show')) {
      _contactHistoryPushed = false;
      closeContact();
      return;
    }
    // postJob / editJob modal (handled by company.jobs.js via _closePostJobOverlay)
    var postJobEl = document.getElementById('postJobOverlay');
    if (postJobEl && postJobEl.classList.contains('show')) {
      if (window._closePostJobOverlay) window._closePostJobOverlay(true);
      return;
    }
    // post (create post) modal (handled by company.posts.js via _closePostOverlay)
    var postEl = document.getElementById('postOverlay');
    if (postEl && postEl.classList.contains('show')) {
      if (window._closePostOverlay) window._closePostOverlay(true);
      return;
    }
    // applicants modal
    var modal = document.getElementById('coApplicantsModal');
    if (modal && modal.style.display !== 'none') {
      _appModalHistoryPushed = false;
      closeApplicantsModal();
    }
  });

  // ── Bootstrap (Rule #10 — idempotent) ──────────────────────────
  function initCompanyProfile() {
    if (window.__companyBooted) return;
    window.__companyBooted = true;
    // Rule #17: stamp the base history entry once so popstate always has a baseline.
    if (window.history) history.replaceState({ modal: null }, '', location.href);
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
  window.openCoverCrop            = openCoverCrop;
  window.closeCoverCrop           = closeCoverCrop;
  window.uploadLogo               = uploadLogo;
  window.openLogoCrop             = openLogoCrop;
  window.closeLogoCrop            = closeLogoCrop;
  window.openReportModal          = openReportModal;
  window.closeReportModal         = closeReportModal;
  window.submitReport             = submitReport;
  window.openApplicantsModal      = openApplicantsModal;
  window.closeApplicantsModal     = closeApplicantsModal;
  window._onSaveApplicant         = _onSaveApplicant;
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

    // Cover photo upload → crop overlay → upload
    var coverFileInput = q('coverFileInput');
    if (coverFileInput) coverFileInput.addEventListener('change', function () { uploadCover(this); });

    // Cover crop overlay controls
    var coCoverCropSaveBtn   = q('coCoverCropSaveBtn');
    var coCoverCropCancelBtn = q('coCoverCropCancelBtn');
    var coCoverZoomSlider    = q('coCoverZoomSlider');
    var coCoverCropOverlay   = q('coCoverCropOverlay');
    if (coCoverCropSaveBtn)   coCoverCropSaveBtn.addEventListener('click', _doUploadCover);
    if (coCoverCropCancelBtn) coCoverCropCancelBtn.addEventListener('click', closeCoverCrop);
    if (coCoverZoomSlider)    coCoverZoomSlider.addEventListener('input', function () {
      var c = _getCoverCropper();
      if (c) c.setZoom(parseInt(this.value, 10) / 100);
    });
    if (coCoverCropOverlay)   coCoverCropOverlay.addEventListener('click', function (e) {
      if (e.target === coCoverCropOverlay) closeCoverCrop();
    });

    // Logo photo upload → crop overlay → upload
    var coLogoCamBtn    = q('coLogoCamBtn');
    var coLogoFileInput = q('coLogoFileInput');
    if (coLogoCamBtn && coLogoFileInput) {
      coLogoCamBtn.addEventListener('click', function () { coLogoFileInput.click(); });
      coLogoFileInput.addEventListener('change', function () { uploadLogo(this); });
    }

    // Logo crop overlay controls
    var coLogoCropSaveBtn   = q('coLogoCropSaveBtn');
    var coLogoCropCancelBtn = q('coLogoCropCancelBtn');
    var coLogoZoomSlider    = q('coLogoZoomSlider');
    var coLogoCropOverlay   = q('coLogoCropOverlay');
    if (coLogoCropSaveBtn)   coLogoCropSaveBtn.addEventListener('click', _doUploadLogo);
    if (coLogoCropCancelBtn) coLogoCropCancelBtn.addEventListener('click', closeLogoCrop);
    if (coLogoZoomSlider)    coLogoZoomSlider.addEventListener('input', function () {
      var c = _getLogoCropper();
      if (c) c.setZoom(parseInt(this.value, 10) / 100);
    });
    if (coLogoCropOverlay)   coLogoCropOverlay.addEventListener('click', function (e) {
      if (e.target === coLogoCropOverlay) closeLogoCrop();
    });

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
    if (editCancelBtn) editCancelBtn.addEventListener('click', function () { closeEdit(); });

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
    if (contactCancelBtn) contactCancelBtn.addEventListener('click', function () { closeContact(); });

    // Report modal
    var reportSubmitBtn = q('reportSubmitBtn'); if (reportSubmitBtn) reportSubmitBtn.addEventListener('click', submitReport);
    var reportCancelBtn = q('reportCancelBtn'); if (reportCancelBtn) reportCancelBtn.addEventListener('click', closeReportModal);

    // Inline handlers migrated from HTML (refactor/company-profile-remove-inline-handlers)
    // Edit modal X button — calls closeEdit() without args; !e path closes unconditionally
    var editCloseX = document.querySelector('#editOverlay .modal-head-close');
    if (editCloseX) editCloseX.addEventListener('click', function () { window.closeEdit && window.closeEdit(); });
    // Job modal — checkboxes and selects
    var jAccAll  = q('j-acc-all');  if (jAccAll)  jAccAll.addEventListener('change',  function () { window._onAccAllChange      && window._onAccAllChange(); });
    var jWmode   = q('j-wmode');    if (jWmode)   jWmode.addEventListener('change',   function () { window._onWmodeChange       && window._onWmodeChange(); });
    var jLocMode = q('j-loc-mode'); if (jLocMode) jLocMode.addEventListener('change', function () { window._onJobLocModeChange  && window._onJobLocModeChange(); });
    var jSalShow = q('j-sal-show'); if (jSalShow) jSalShow.addEventListener('change', function () { window._onSalShowChange     && window._onSalShowChange(); });
    // Job modal — click-to-focus on skill/profession chip boxes
    var jAccProfBox = q('j-acc-prof-box'); if (jAccProfBox) jAccProfBox.addEventListener('click', function () { var inp = q('j-acc-prof-inp'); if (inp) inp.focus(); });
    var jSkillBox   = q('j-skill-box');    if (jSkillBox)   jSkillBox.addEventListener('click',   function () { var inp = q('j-skill-inp');      if (inp) inp.focus(); });
    // All Branches bottom sheet — overlay backdrop + close button
    var brOverlay = q('allBranchesOverlay');
    if (brOverlay) brOverlay.addEventListener('click', function (e) { if (e.target === brOverlay && window.closeAllBranchesModal) window.closeAllBranchesModal(); });
    var brClose = document.querySelector('#allBranchesOverlay .co-branches-sheet-close');
    if (brClose) brClose.addEventListener('click', function () { window.closeAllBranchesModal && window.closeAllBranchesModal(); });
    // Applicants modal — overlay backdrop + close button
    var appOverlay = q('coApplicantsModal');
    if (appOverlay) appOverlay.addEventListener('click', function (e) { if (e.target === appOverlay && window.closeApplicantsModal) window.closeApplicantsModal(); });
    var appClose = document.querySelector('#coApplicantsModal .co-fl-close');
    if (appClose) appClose.addEventListener('click', function () { window.closeApplicantsModal && window.closeApplicantsModal(); });
  }

  // ── Auth-sync: cross-tab session invalidation ──
  // Wires TwAuthSync (static/shared/auth-sync.js) into Company Profile.
  // On JWT change: immediately strips owner mode, closes edit modal,
  // then background-reloads to get authoritative viewer_type from server.
  //
  // bfcache case (reason === 'pageshow', jwt present):
  //   auth-sync fires with force:true even when JWT is unchanged — this previously
  //   caused a mixed UI state (visitor header + owner job cards) because owner mode
  //   was stripped immediately while the DOM was still showing owner card HTML from
  //   bfcache. Fix: skip the strip when JWT is still valid; just background-verify.
  (function () {
    if (!window.TwAuthSync) return;
    TwAuthSync.onSessionChange(function (e) {
      var reason = e && e.reason;
      var jwt    = (e && e.jwt) || '';

      // bfcache restore with a valid JWT — page state is still correct.
      // Background-verify only; do NOT strip owner mode prematurely.
      if (reason === 'pageshow' && jwt) {
        if (window.loadData) loadData({ silent: true });
        return;
      }

      // JWT is missing or changed (logout / account switch in another tab).
      // Immediately revoke owner UI for security.
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
    if (_ptr2Active) {
      _ptr2Active = false;
      if (window.showToast) showToast('جاري التحديث...', 'info', 1200);
      if (window.loadData) loadData();
    }
  }, { passive: true });
  document.addEventListener('touchmove', function (e) {
    if (window.scrollY === 0 && _ptr2Start > 0) {
      var diff = e.touches[0].clientY - _ptr2Start;
      if (diff > 120 && !_ptr2Active) { _ptr2Active = true; }
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

// ── Rating Modal ──────────────────────────────────────────────────
(function () {
  'use strict';

  var _overlay = document.getElementById('coRatingModal');
  var _body    = document.getElementById('coRatBody');

  function _open() {
    if (!_overlay) return;
    _overlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    _fetch();
  }

  function _close() {
    if (!_overlay) return;
    _overlay.style.display = 'none';
    document.body.style.overflow = '';
  }

  function _esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function _stars(n) {
    var s = '';
    for (var i = 1; i <= 5; i++) s += (i <= n ? '★' : '☆');
    return s;
  }

  function _fetch() {
    if (!_body) return;
    _body.innerHTML = '<div class="co-fl-spin">جارٍ التحميل…</div>';
    var coId = (window._companyProfileIdFromRoute != null)
      ? String(window._companyProfileIdFromRoute)
      : new URLSearchParams(window.location.search).get('id');
    if (!coId && window.companyState && companyState.profile)
      coId = String(companyState.profile.id);
    if (!coId) { _body.innerHTML = '<div class="co-fl-empty">تعذّر تحميل التقييمات.</div>'; return; }

    window.getCompanyRatingsDetail(coId, 5)
      .then(function (res) {
        if (!res.ok) throw new Error('fail');
        _render(res.data);
      })
      .catch(function () {
        if (_body) _body.innerHTML = '<div class="co-fl-empty">تعذّر تحميل التقييمات.</div>';
      });
  }

  function _render(d) {
    if (!_body) return;
    var html = '';

    // ── Summary ──
    if (!d.rating_count || d.rating_count === 0) {
      html += '<div class="co-fl-empty">لا توجد تقييمات بعد.</div>';
      html += _rateSection(d);
      _body.innerHTML = html;
      _wireRateBtn(d);
      return;
    }

    var avg = d.rating_avg ? parseFloat(d.rating_avg).toFixed(1) : '—';
    html += '<div class="co-rat-summary">';
    html += '<div class="co-rat-avg">' + _esc(avg) + '</div>';
    html += '<div class="co-rat-stars">' + _stars(Math.round(d.rating_avg || 0)) + '</div>';
    html += '<div class="co-rat-count">من ' + _esc(d.rating_count) + ' تقييم</div>';
    html += '</div>';

    // ── Distribution ──
    if (d.distribution) {
      html += '<div class="co-rat-dist">';
      var total = d.rating_count || 1;
      for (var s = 5; s >= 1; s--) {
        var cnt = d.distribution[String(s)] || 0;
        var pct = Math.round((cnt / total) * 100);
        html += '<div class="co-rat-dist-row">';
        html += '<span class="co-rat-dist-lbl">' + s + '★</span>';
        html += '<div class="co-rat-dist-bar"><div class="co-rat-dist-fill" style="width:' + pct + '%"></div></div>';
        html += '<span class="co-rat-dist-pct">' + pct + '%</span>';
        html += '</div>';
      }
      html += '</div>';
    }

    // ── Recent comments ──
    if (d.recent_comments && d.recent_comments.length) {
      html += '<div class="co-rat-comments-head">أحدث التعليقات</div>';
      html += '<div class="co-rat-comments">';
      d.recent_comments.forEach(function (c) {
        html += '<div class="co-rat-comment">';
        html += '<span class="co-rat-comment-stars">' + _stars(c.score) + '</span>';
        html += '<p class="co-rat-comment-text">' + _esc(c.comment) + '</p>';
        html += '</div>';
      });
      html += '</div>';
    }

    // ── My rating / rate CTA ──
    html += _rateSection(d);
    _body.innerHTML = html;
    _wireRateBtn(d);
  }

  function _rateSection(d) {
    var s = window.companyState;
    if (!s || !s.permissions || !s.permissions.can_rate) return '';
    var html = '<div class="co-rat-my" id="coRatMySection">';
    if (d.my_rating) {
      html += '<div class="co-rat-my-label">تقييمك الحالي: <span class="co-rat-my-stars">' + _stars(d.my_rating) + '</span></div>';
      html += '<button class="co-rat-my-btn" id="coRatEditBtn">تعديل التقييم</button>';
    } else {
      html += '<button class="co-rat-my-btn" id="coRatEditBtn">قيّم الشركة</button>';
    }
    html += '<div class="co-rat-picker" id="coRatPicker" style="display:none">';
    for (var i = 1; i <= 5; i++) {
      html += '<span class="co-rat-star" data-score="' + i + '">★</span>';
    }
    html += '</div>';
    html += '</div>';
    return html;
  }

  function _wireRateBtn(d) {
    var editBtn = document.getElementById('coRatEditBtn');
    var picker  = document.getElementById('coRatPicker');
    if (!editBtn || !picker) return;
    editBtn.addEventListener('click', function () {
      picker.style.display = picker.style.display === 'none' ? 'flex' : 'none';
    });
    var stars = picker.querySelectorAll('.co-rat-star');
    stars.forEach(function (star) {
      star.addEventListener('mouseenter', function () {
        var n = parseInt(this.dataset.score);
        stars.forEach(function (st, idx) { st.classList.toggle('active', idx < n); });
      });
      star.addEventListener('mouseleave', function () {
        stars.forEach(function (st) { st.classList.remove('active'); });
      });
      star.addEventListener('click', function () {
        var score = parseInt(this.dataset.score);
        _submitRating(score);
      });
    });
  }

  function _submitRating(score) {
    var s = window.companyState;
    if (!s || !s.profile) return;
    var coId = String(s.profile.id);
    var jwt  = window._jwt ? window._jwt() : '';
    if (!jwt) return;
    fetch('/company/rate/' + coId, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + jwt },
      body: JSON.stringify({ score: score })
    })
    .then(function (r) { return r.json(); })
    .then(function (res) {
      if (res.status === 'success') {
        if (window.companyState) {
          companyState.stats.rating_avg   = res.rating_avg;
          companyState.stats.rating_count = res.rating_count;
          if (window.renderStats) renderStats();
        }
        _fetch();
      }
    })
    .catch(function () {});
  }

  // Wire
  document.addEventListener('DOMContentLoaded', function () {
    var tile = document.getElementById('coStatRatingTile');
    if (tile) tile.addEventListener('click', _open);
    var closeBtn = document.getElementById('coRatClose');
    if (closeBtn) closeBtn.addEventListener('click', _close);
    if (_overlay) _overlay.addEventListener('click', function (e) { if (e.target === _overlay) _close(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && _overlay && _overlay.style.display !== 'none') _close(); });
  });

  window._coRatOpen = _open;
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

// ── Candidates Modal (Phase 4 + Phase 5B + Phase 6B — owner-only) ──
(function () {
  'use strict';

  var _overlay  = document.getElementById('coCandidatesModal');
  var _body     = document.getElementById('coCandBody');
  var _badge    = document.getElementById('candidatesBadge');
  var _openBtn  = document.getElementById('candidatesBtn');
  var _closeBtn = document.getElementById('coCandClose');

  if (!_overlay || !_body) return;

  // Tab state
  var _activeTab    = 'saved';
  var _suggOffset   = 0;
  var _suggLoading  = false;

  // Saved tab filter/search/sort/pagination state (Phase 7B)
  var _savedOffset   = 0;
  var _savedLoading  = false;
  var _savedFilter   = null;   // null=all, status string, or '_unlinked'
  var _savedSearch   = '';
  var _savedSort     = 'updated_desc';
  var _savedStats    = null;
  var _savedDebTimer = null;

  // Talent Bank V2 advanced filter state (PR-4)
  var _savedPriority         = '';   // ''=all, 'low'/'medium'/'high'
  var _savedMinRating        = '';   // ''=all, '1'-'5'
  var _savedTag              = '';   // ''=all, tag string
  var _savedSaveSource       = '';   // ''=all, 'manual'/'applicant'/'suggestion'
  var _quotaUsed             = null;
  var _quotaLimit            = 25;

  // ── Pipeline status labels & order ───────────────────────────
  var _STATUS_LABELS = {
    'saved':       'محفوظ',
    'shortlisted': 'مرشح قوي',
    'contacted':   'تم التواصل',
    'interview':   'مقابلة',
    'hired':       'تم التوظيف',
    'rejected':    'غير مناسب'
  };
  var _STATUS_ORDER = ['saved','shortlisted','contacted','interview','hired','rejected'];

  // Job application status labels (for chip popover)
  var _APP_STATUS_LABELS = {
    'pending':   'قيد المراجعة',
    'viewed':    'تمت المشاهدة',
    'accepted':  'مقبول',
    'contacted': 'تم التواصل',
    'interview': 'مقابلة',
    'hired':     'تم التوظيف',
    'rejected':  'مرفوض',
  };

  // Pending manage panel open after tab switch (Reqs 5 & 6)
  var _pendingManageOpen      = null;   // candidate_id to auto-open after saved tab loads
  var _pendingManageOpenNotes = false;  // also focus notes textarea

  // Deep-link from ?cand=<id>[&notes=1] in URL — set at init, consumed in _loadBadge
  var _urlDeepLinkPending = false;
  (function () {
    var sp = new URLSearchParams(location.search);
    var cand = sp.get('cand');
    if (cand) {
      _pendingManageOpen      = cand;
      _pendingManageOpenNotes = sp.get('notes') === '1';
      _urlDeepLinkPending     = true;
    }
  }());

  // DOM-independent per-job status PATCH lock.
  // Keyed by String(candidateId). Survives list rebuilds (filter/search/tab switch/pagination).
  // A candidate's entry is present while a PATCH is in-flight; absent otherwise.
  // _savedCardHTML and _renderCandidateJobLinksUI check this registry (not only data-job-status-saving)
  // so newly built cards for a candidate mid-flight start with pickers already disabled.
  var _jobStatusInFlight = Object.create(null);

  // Job chip popover state
  var _jobPopTarget = null;

  function _statusLabel(s) { return _STATUS_LABELS[s] || _STATUS_LABELS['saved']; }
  function _statusKey(s)   { return _STATUS_LABELS[s] ? s : 'saved'; }

  // ── Owner guard ────────────────────────────────────────────────
  function _isOwner() {
    return window.companyState &&
           companyState.permissions &&
           companyState.permissions.can_edit;
  }

  // ── Badge ──────────────────────────────────────────────────────
  function _setBadge(count) {
    if (!_badge) return;
    if (count > 0) {
      _badge.textContent = count > 99 ? '99+' : String(count);
      _badge.style.display = 'inline-flex';
    } else {
      _badge.style.display = 'none';
    }
  }

  function _loadBadge() {
    if (!_isOwner()) return;
    _loadSavedStats(null);
    if (_urlDeepLinkPending) {
      _urlDeepLinkPending = false;
      setTimeout(_open, 0);
    }
  }

  // ── Text escape helper ─────────────────────────────────────────
  function _esc(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Avatar SVG fallback ────────────────────────────────────────
  var _avatarSvg =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">' +
    '<circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>';

  // ── Custom dark picker helpers (Phase UI-Polish) ───────────────
  var _S = 'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"';
  function _chevronSvg() {
    return '<svg class="co-dp-chev" viewBox="0 0 24 24" fill="none" ' + _S + '>'
         + '<polyline points="6 9 12 15 18 9"/></svg>';
  }
  function _checkSvg() {
    return '<svg class="co-dp-chk" viewBox="0 0 24 24" fill="none" ' + _S + '>'
         + '<polyline points="20 6 9 17 4 12"/></svg>';
  }
  // Filter chip icons (Lucide-style inline SVG)
  var _FILTER_ICONS = {
    'null':        '<svg viewBox="0 0 24 24" fill="none" ' + _S + '><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>',
    'saved':       '<svg viewBox="0 0 24 24" fill="none" ' + _S + '><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>',
    'shortlisted': '<svg viewBox="0 0 24 24" fill="none" ' + _S + '><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    'contacted':   '<svg viewBox="0 0 24 24" fill="none" ' + _S + '><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    'interview':   '<svg viewBox="0 0 24 24" fill="none" ' + _S + '><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    'hired':       '<svg viewBox="0 0 24 24" fill="none" ' + _S + '><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    'rejected':    '<svg viewBox="0 0 24 24" fill="none" ' + _S + '><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    '_unlinked':   '<svg viewBox="0 0 24 24" fill="none" ' + _S + '><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="17" y1="11" x2="23" y2="11"/></svg>'
  };
  // Build a custom dark picker (wrapClass + options array + current value).
  // meta (optional 4th arg): { cid, jid, locked } — adds data-cid/data-jid to wrap,
  // disables .co-dp-btn when locked. Backward-compatible (existing 3-arg callers unaffected).
  function _dpHTML(wrapClass, opts, current, meta) {
    meta = meta || {};
    var curLabel = '';
    for (var i = 0; i < opts.length; i++) {
      if (opts[i].value === current) { curLabel = opts[i].label; break; }
    }
    var listHtml = opts.map(function (o) {
      var cls = 'co-dp-opt' + (o.value === current ? ' selected' : '') + (o.disabled ? ' co-dp-opt--disabled' : '');
      return '<button class="' + cls + '"'
           + ' data-value="' + _esc(o.value) + '" type="button"'
           + (o.disabled ? ' data-linked="1"' : '') + '>'
           + _checkSvg()
           + '<span>' + _esc(o.label) + '</span></button>';
    }).join('');
    var extraAttrs = '';
    if (meta.cid != null) extraAttrs += ' data-cid="' + _esc(String(meta.cid)) + '"';
    if (meta.jid != null) extraAttrs += ' data-jid="' + _esc(String(meta.jid)) + '"';
    return '<div class="co-dp-wrap ' + _esc(wrapClass) + '" data-selected="' + _esc(current) + '"' + extraAttrs + '>'
      + '<button class="co-dp-btn" type="button"' + (meta.locked ? ' disabled' : '') + '>'
      + '<span class="co-dp-val">' + _esc(curLabel) + '</span>'
      + _chevronSvg()
      + '</button>'
      + '<div class="co-dp-list" style="display:none">' + listHtml + '</div>'
      + '</div>';
  }
  function _closeAllDp() {
    _body.querySelectorAll('.co-dp-list').forEach(function (l) { l.style.display = 'none'; });
  }
  function _toggleDpOf(btn) {
    if (btn.disabled) return;  // respect card-level lock
    var wrap = btn.closest('.co-dp-wrap');
    if (!wrap) return;
    var list = wrap.querySelector('.co-dp-list');
    if (!list) return;
    var wasOpen = list.style.display !== 'none';
    _closeAllDp();
    if (!wasOpen) list.style.display = 'block';
  }
  function _handleDpOptClick(opt) {
    if (opt.getAttribute('data-linked') === '1') return;
    var wrap = opt.closest('.co-dp-wrap');
    if (!wrap) return;
    // Per-job candidate status picker — PATCH auto-save with card-level lock
    if (wrap.classList.contains('co-cand-job-status-dp')) {
      _handleJobStatusDpSelect(opt, wrap);
      return;
    }
    var val  = opt.getAttribute('data-value');
    var span = opt.querySelector('span');
    var lbl  = span ? span.textContent : val;
    wrap.setAttribute('data-selected', val != null ? val : '');
    var valEl = wrap.querySelector('.co-dp-val');
    if (valEl) valEl.textContent = lbl;
    wrap.querySelectorAll('.co-dp-opt').forEach(function (o) {
      o.classList.toggle('selected', o === opt);
    });
    var list = wrap.querySelector('.co-dp-list');
    if (list) list.style.display = 'none';
    // Sort picker action
    if (wrap.classList.contains('co-cand-sort-dp')) {
      _savedSort   = val;
      _savedOffset = 0;
      _doFetchSavedPage(true);
      return;
    }
    // Advanced filter pickers
    if (wrap.classList.contains('co-cand-priority-dp') ||
        wrap.classList.contains('co-cand-rating-dp')   ||
        wrap.classList.contains('co-cand-source-dp')) {
      _handleAdvDpSelect(wrap, val || '');
    }
  }

  // Find the live card for a candidate from the current DOM.
  // Must not use a stale reference captured before a list rebuild.
  function _findLiveSavedCandidateCard(candidateId) {
    return _body
      ? _body.querySelector('.co-cand-saved-card[data-cid="' + String(candidateId) + '"]')
      : null;
  }

  // Auto-save per-job candidate status via PATCH when user selects from co-cand-job-status-dp.
  // Uses _jobStatusInFlight registry (keyed by candidateId) — independent of DOM card references.
  // Registry-based lock survives list rebuilds (filter/search/tab switch/pagination).
  // data-job-links on card is the single client-side truth; all DOM rebuilds come from it.
  function _handleJobStatusDpSelect(opt, wrap) {
    var cidStr = wrap.getAttribute('data-cid') || '';
    var cidInt = parseInt(cidStr, 10);
    var jid    = parseInt(wrap.getAttribute('data-jid'), 10);
    if (!cidInt || !jid) return;
    if (!window.updateCandidateJobStatus) return;

    // Registry-based lock: one in-flight PATCH per candidate, not per card.
    if (_jobStatusInFlight[cidStr]) return;

    var cs = opt.getAttribute('data-value') || null;   // '' → null  (clears classification)

    // No-op guard: if selected value already matches current data-job-links, close picker and skip PATCH.
    var liveCard0 = _findLiveSavedCandidateCard(cidInt);
    var currentLinks = [];
    if (liveCard0) {
      try { currentLinks = JSON.parse(liveCard0.getAttribute('data-job-links') || '[]'); } catch (e) {}
    }
    var existingEntry = null;
    for (var _i = 0; _i < currentLinks.length; _i++) {
      if (String(currentLinks[_i].job_id) === String(jid)) { existingEntry = currentLinks[_i]; break; }
    }
    if (existingEntry !== null) {
      var currentCs = existingEntry.candidate_status || null;
      if ((cs || null) === currentCs) {
        // Same value — just close the open picker list, no PATCH
        var dpList = wrap.querySelector('.co-dp-list');
        if (dpList) dpList.style.display = 'none';
        return;
      }
    }

    // Mark in-flight in registry; apply visual lock on live card
    _jobStatusInFlight[cidStr] = true;
    var liveCard = _findLiveSavedCandidateCard(cidInt);
    if (liveCard) {
      liveCard.setAttribute('data-job-status-saving', '1');
      liveCard.querySelectorAll('.co-cand-job-status-dp .co-dp-list').forEach(function (l) { l.style.display = 'none'; });
      liveCard.querySelectorAll('.co-cand-job-status-dp .co-dp-btn').forEach(function (b) { b.disabled = true; });
    }

    window.updateCandidateJobStatus(cidInt, jid, cs)
      .then(function (res) {
        var card = _findLiveSavedCandidateCard(cidInt);
        if (!res || !res.ok) {
          var detail = (res && res.data && res.data.detail) || '';
          if (card && card.parentNode) {
            var rollLinks = [];
            try { rollLinks = JSON.parse(card.getAttribute('data-job-links') || '[]'); } catch (err) {}
            _renderCandidateJobLinksUI(card, rollLinks);
          }
          if (window.showToast) showToast(detail || 'تعذّر حفظ التصنيف', 'error');
          return;
        }
        if (card && card.parentNode) {
          var links = [];
          try { links = JSON.parse(card.getAttribute('data-job-links') || '[]'); } catch (err) {}
          links = links.map(function (jl) {
            return String(jl.job_id) === String(jid)
              ? Object.assign({}, jl, { candidate_status: cs || null })
              : jl;
          });
          _renderCandidateJobLinksUI(card, links);
        }
        if (window.showToast) showToast('تم حفظ التصنيف ✓');
      })
      .catch(function () {
        var card = _findLiveSavedCandidateCard(cidInt);
        if (card && card.parentNode) {
          var rollLinks = [];
          try { rollLinks = JSON.parse(card.getAttribute('data-job-links') || '[]'); } catch (err) {}
          _renderCandidateJobLinksUI(card, rollLinks);
        }
        if (window.showToast) showToast('تعذّر حفظ التصنيف', 'error');
      })
      .finally(function () {
        delete _jobStatusInFlight[cidStr];
        var card = _findLiveSavedCandidateCard(cidInt);
        if (card) {
          card.removeAttribute('data-job-status-saving');
          // Re-enable buttons on the freshly rebuilt DOM (_renderCandidateJobLinksUI rebuilt them)
          card.querySelectorAll('.co-cand-job-status-dp .co-dp-btn').forEach(function (b) { b.disabled = false; });
        }
      });
  }

  // ── Open / Close ───────────────────────────────────────────────
  function _open() {
    if (!_isOwner()) return;
    _overlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    _switchTab('saved');
  }

  function _close() {
    _overlay.style.display = 'none';
    document.body.style.overflow = '';
  }

  // ── Tab switching ──────────────────────────────────────────────
  function _switchTab(tab) {
    _activeTab = tab;
    var tabs = _overlay.querySelectorAll('.co-cand-tab');
    tabs.forEach(function (t) {
      if (t.getAttribute('data-tab') === tab) t.classList.add('active');
      else t.classList.remove('active');
    });
    if (tab === 'saved') {
      _fetchSaved();
    } else {
      _suggOffset  = 0;
      _suggLoading = false;
      _fetchSuggestions(0);
    }
  }

  // ────────────────────────────────────────────────────────────────
  // TAB 1 — Saved candidates (Phase 6B enhanced)
  // ────────────────────────────────────────────────────────────────

  // ── Phase 7B: filter bar shell ──────────────────────────────────

  function _savedShellHTML() {
    var sortOpts = [
      {value:'updated_desc',  label:'الأحدث تعديلاً'},
      {value:'updated_asc',   label:'الأقدم تعديلاً'},
      {value:'created_desc',  label:'الأحدث حفظاً'},
      {value:'created_asc',   label:'الأقدم حفظاً'},
      {value:'name_asc',      label:'الاسم أ-ي'},
      {value:'status_asc',    label:'الحالة'},
      {value:'rating_desc',   label:'التقييم الأعلى'},
      {value:'priority_asc',  label:'الأولوية'}
    ];
    var priorityOpts = [
      {value:'',       label:'كل الأولويات'},
      {value:'high',   label:'عالية'},
      {value:'medium', label:'متوسطة'},
      {value:'low',    label:'منخفضة'}
    ];
    var ratingOpts = [
      {value:'',  label:'كل التقييمات'},
      {value:'5', label:'★★★★★ فقط'},
      {value:'4', label:'★★★★ فأعلى'},
      {value:'3', label:'★★★ فأعلى'},
      {value:'2', label:'★★ فأعلى'},
      {value:'1', label:'★ فأعلى'}
    ];
    var sourceOpts = [
      {value:'',           label:'كل المصادر'},
      {value:'manual',     label:'حفظ يدوي'},
      {value:'applicant',  label:'من المتقدمين'},
      {value:'suggestion', label:'من الاقتراحات'}
    ];
    var quotaStr = (_quotaUsed !== null)
      ? ('بنك المواهب: ' + _quotaUsed + ' من ' + _quotaLimit)
      : 'بنك المواهب';
    return '<div id="coCandSavedShell">'
      + '<div class="co-tb-quota-bar" id="coTbQuotaBar">'
      + '<span class="co-tb-quota-lbl" id="coTbQuotaLbl">' + _esc(quotaStr) + '</span>'
      + '</div>'
      + '<div class="co-cand-filter-bar">'
      + '<div id="coCandChips" class="co-cand-chips"></div>'
      + '<div class="co-cand-search-row">'
      + '<input id="coCandSearch" type="text" class="co-cand-search"'
      + ' placeholder="بحث عن مرشح…" dir="rtl" value="' + _esc(_savedSearch) + '">'
      + _dpHTML('co-cand-sort-dp', sortOpts, _savedSort)
      + '</div>'
      + '<div class="co-cand-adv-filters">'
      + _dpHTML('co-cand-priority-dp', priorityOpts, _savedPriority)
      + _dpHTML('co-cand-rating-dp',   ratingOpts,   _savedMinRating)
      + _dpHTML('co-cand-source-dp',   sourceOpts,   _savedSaveSource)
      + '<input id="coCandTagFilter" type="text" class="co-cand-tag-input"'
      + ' placeholder="فلترة بـ tag…" dir="rtl" value="' + _esc(_savedTag) + '">'
      + '</div>'
      + '</div>'
      + '<div id="coCandSavedList"></div>'
      + '</div>';
  }

  function _renderChips() {
    var el = document.getElementById('coCandChips');
    if (!el) return;
    var stats    = _savedStats || {};
    var byStatus = stats.by_status || {};
    var chips = [
      [null,          'الكل',             stats.total        || 0],
      ['saved',       _STATUS_LABELS['saved'],       byStatus.saved       || 0],
      ['shortlisted', _STATUS_LABELS['shortlisted'],  byStatus.shortlisted || 0],
      ['contacted',   _STATUS_LABELS['contacted'],    byStatus.contacted   || 0],
      ['interview',   _STATUS_LABELS['interview'],    byStatus.interview   || 0],
      ['hired',       _STATUS_LABELS['hired'],        byStatus.hired       || 0],
      ['rejected',    _STATUS_LABELS['rejected'],     byStatus.rejected    || 0],
      ['_unlinked',   'بدون وظيفة',       stats.unlinked       || 0]
    ];
    var html = '';
    chips.forEach(function (c) {
      var fval  = c[0], label = c[1], count = c[2];
      var fkey  = fval == null ? 'null' : fval;
      var dataf = fval == null ? '' : _esc(fval);
      var active = (fval === _savedFilter);
      var icon   = _FILTER_ICONS[fkey] || _FILTER_ICONS['null'];
      html += '<button class="co-cand-chip chip-f-' + fkey + (active ? ' active' : '') + '"'
            + ' data-filter="' + dataf + '">'
            + '<span class="co-cand-chip-main">'
            +   '<span class="co-cand-chip-ico">' + icon + '</span>'
            +   '<span class="co-cand-chip-lbl">' + _esc(label) + '</span>'
            + '</span>'
            + '<span class="co-cand-chip-cnt">' + count + '</span>'
            + '</button>';
    });
    el.innerHTML = html;
    el.querySelectorAll('.co-cand-chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        var val = chip.getAttribute('data-filter');
        _savedFilter = (val === '') ? null : val;
        _savedSearch = '';
        var searchEl = document.getElementById('coCandSearch');
        if (searchEl) searchEl.value = '';
        _savedOffset = 0;
        _renderChips();
        _doFetchSavedPage(true);
      });
    });
  }

  function _loadSavedStats(cb) {
    if (!window.getSavedCandidatesStats) { if (cb) cb(); return; }
    window.getSavedCandidatesStats()
      .then(function (res) {
        if (res && res.ok && res.data) {
          _savedStats = res.data;
          _setBadge(_savedStats.total || 0);
          _renderChips();
        }
        if (cb) cb();
      })
      .catch(function () { if (cb) cb(); });
  }

  function _wireSavedFilterBar() {
    _renderChips();
    var searchEl = document.getElementById('coCandSearch');
    if (searchEl) {
      searchEl.addEventListener('input', function () {
        clearTimeout(_savedDebTimer);
        var val = searchEl.value.slice(0, 80).trim();
        _savedDebTimer = setTimeout(function () {
          _savedSearch = val;
          _savedOffset = 0;
          _doFetchSavedPage(true);
        }, 300);
      });
    }
    // Tag filter input
    var tagEl = document.getElementById('coCandTagFilter');
    if (tagEl) {
      tagEl.addEventListener('input', function () {
        clearTimeout(_savedDebTimer);
        var val = tagEl.value.slice(0, 30).trim();
        _savedDebTimer = setTimeout(function () {
          _savedTag = val;
          _savedOffset = 0;
          _doFetchSavedPage(true);
        }, 400);
      });
    }
    // Advanced filter pickers handled via _onSavedClick delegation (_handleAdvDpSelect)
  }

  // Called when an advanced filter picker option is selected
  function _handleAdvDpSelect(dpEl, val) {
    var cls = dpEl.className;
    if (cls.indexOf('co-cand-priority-dp') >= 0) {
      _savedPriority = val;
    } else if (cls.indexOf('co-cand-rating-dp') >= 0) {
      _savedMinRating = val;
    } else if (cls.indexOf('co-cand-source-dp') >= 0) {
      _savedSaveSource = val;
    } else {
      return; // not an advanced filter
    }
    _savedOffset = 0;
    _doFetchSavedPage(true);
  }

  // Load talent bank quota from server
  function _loadTalentBankQuota() {
    var jwt = window._jwt ? window._jwt() : '';
    if (!jwt) return;
    fetch('/company/saved-candidates/quota', {
      headers: { 'Authorization': 'Bearer ' + jwt }
    })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d && d.used !== undefined) {
        _quotaUsed  = d.used;
        _quotaLimit = d.limit || 25;
        var lbl = document.getElementById('coTbQuotaLbl');
        if (lbl) lbl.textContent = 'بنك المواهب: ' + _quotaUsed + ' من ' + _quotaLimit;
      }
    })
    .catch(function () {});
  }

  function _fetchSaved() {
    _savedOffset  = 0;
    _savedLoading = false;
    _body.innerHTML = _savedShellHTML();
    _wireSavedFilterBar();
    _loadSavedStats(null);
    _loadTalentBankQuota();
    _doFetchSavedPage(true);
  }

  function _doFetchSavedPage(first) {
    if (_savedLoading) return;
    _savedLoading = true;
    var list = document.getElementById('coCandSavedList');
    if (first && list) list.innerHTML = '<div class="co-fl-spin">جارٍ التحميل…</div>';
    var oldBtn = document.getElementById('coCandSavedLoadMore');
    if (oldBtn && oldBtn.parentNode) oldBtn.parentNode.removeChild(oldBtn);

    var filters = {};
    if (_savedFilter === '_unlinked')  { filters.unlinked = true; }
    else if (_savedFilter)             { filters.status = _savedFilter; }
    if (_savedSearch)         filters.q                  = _savedSearch;
    if (_savedPriority)       filters.priority           = _savedPriority;
    if (_savedMinRating)      filters.min_rating         = _savedMinRating;
    if (_savedTag)            filters.tag                = _savedTag;
    if (_savedSaveSource)     filters.save_source_filter = _savedSaveSource;
    filters.sort = _savedSort;

    if (!window.getSavedCandidates) { _savedLoading = false; return; }
    window.getSavedCandidates(20, _savedOffset, filters)
      .then(function (res) {
        var list = document.getElementById('coCandSavedList');
        if (!list) return;
        if (!res || !res.ok) {
          if (first) {
            var code = res && res.status;
            list.innerHTML = (code === 401 || code === 403)
              ? '<div class="co-fl-empty">غير مصرح بالوصول</div>'
              : '<div class="co-fl-empty">تعذّر تحميل القائمة</div>';
          }
          return;
        }
        var items = (res.data && res.data.items) || [];
        var pg    = (res.data && res.data.pagination) || {};
        if (first) {
          if (!items.length) {
            list.innerHTML = _savedEmptyHTML(_savedFilter, _savedSearch);
            return;
          }
          var html = '';
          items.forEach(function (i) { html += _savedCardHTML(i); });
          list.innerHTML = html;
          _wireSavedCards();
        } else {
          var tmp = document.createElement('div');
          items.forEach(function (i) {
            tmp.innerHTML = _savedCardHTML(i);
            while (tmp.firstChild) list.appendChild(tmp.firstChild);
          });
          _wireSavedCards();
        }
        _savedOffset = (pg.offset || 0) + items.length;
        var shell = document.getElementById('coCandSavedShell');
        if (pg.has_more && shell) {
          var loadBtn = document.createElement('button');
          loadBtn.className = 'co-cand-load-more';
          loadBtn.id        = 'coCandSavedLoadMore';
          loadBtn.textContent = 'عرض المزيد';
          shell.appendChild(loadBtn);
          loadBtn.addEventListener('click', function () {
            loadBtn.disabled    = true;
            loadBtn.textContent = 'جارٍ التحميل…';
            _doFetchSavedPage(false);
          });
        }
      })
      .catch(function () {
        var list = document.getElementById('coCandSavedList');
        if (list && first) list.innerHTML = '<div class="co-fl-empty">تعذّر تحميل القائمة</div>';
      })
      .finally(function () { _savedLoading = false; });
  }

  function _savedEmptyHTML(filter, q) {
    if (q) return '<div class="co-cand-empty">'
      + '<div class="co-cand-empty-title">لا نتائج للبحث عن "' + _esc(q) + '"</div>'
      + '<div class="co-cand-empty-sub">جرّب كلمات بحث مختلفة.</div></div>';
    var msgs = {
      'null':        ['لا يوجد مرشحون محفوظون بعد',          'عند حفظ مرشح سيظهر هنا لإدارته لاحقاً.'],
      'saved':       ['لا يوجد مرشحون بحالة "محفوظ"',        'يمكنك تغيير حالة المرشح من لوحة الإدارة.'],
      'shortlisted': ['لا يوجد مرشحون مرشحون قوياً',         ''],
      'contacted':   ['لا يوجد مرشحون تم التواصل معهم',      ''],
      'interview':   ['لا يوجد مرشحون في مرحلة المقابلة',    ''],
      'hired':       ['لا يوجد مرشحون تم توظيفهم',           ''],
      'rejected':    ['لا يوجد مرشحون بحالة "غير مناسب"',    ''],
      '_unlinked':   ['لا يوجد مرشحون بدون وظيفة',           'جميع المرشحين مرتبطون بوظيفة حالياً.']
    };
    var key = filter == null ? 'null' : String(filter);
    var m = msgs[key] || msgs['null'];
    return '<div class="co-cand-empty">'
      + '<div class="co-cand-empty-title">' + _esc(m[0]) + '</div>'
      + (m[1] ? '<div class="co-cand-empty-sub">' + _esc(m[1]) + '</div>' : '')
      + '</div>';
  }

  function _fmtDate(iso) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleDateString('ar-SA', { year:'numeric', month:'short', day:'numeric' });
    } catch (e) { return ''; }
  }

  // Rating stars HTML (display-only, 1-5)
  function _starsHTML(rating) {
    if (!rating) return '';
    var s = '';
    for (var i = 1; i <= 5; i++) {
      s += '<span class="co-cand-star' + (i <= rating ? ' co-cand-star--on' : '') + '">★</span>';
    }
    return '<span class="co-cand-stars">' + s + '</span>';
  }

  // Priority badge HTML
  var _PRIORITY_LABELS = { high: 'عالية', medium: 'متوسطة', low: 'منخفضة' };
  function _priorityBadgeHTML(priority) {
    if (!priority) return '';
    return '<span class="co-cand-priority co-cand-priority--' + _esc(priority) + '">'
      + _esc(_PRIORITY_LABELS[priority] || priority) + '</span>';
  }

  // Save source Arabic labels
  var _SOURCE_LABELS = {
    manual:         'حفظ يدوي',
    applicant:      'من المتقدمين',
    suggestion:     'من الاقتراحات',
    legacy_unknown: 'قديم'
  };

  // Follow-up status labels
  var _FU_STATUS_LABELS = { pending: 'قيد المتابعة', done: 'تمت المتابعة', none: '' };

  // Build a single saved card with embedded manage panel (V2)
  function _savedCardHTML(item) {
    var status       = item.status        || 'saved';
    var notes        = item.notes         || '';
    var jobId        = item.job_id  != null ? String(item.job_id) : '';
    var rating       = item.rating        || null;
    var priority     = item.priority      || null;
    var tags         = Array.isArray(item.tags) ? item.tags : [];
    var followUpAt   = item.follow_up_at  || null;
    var followUpSt   = item.follow_up_status || null;
    var saveSource   = item.save_source   || null;
    var meta         = [item.profession, item.city, item.country].filter(Boolean).join(' · ');
    var date         = _fmtDate(item.created_at);
    var cid          = _esc(item.candidate_id);
    var jobLinks     = Array.isArray(item.job_links) ? item.job_links : [];
    var linkedIds    = jobLinks.map(function(jl) { return String(jl.job_id); });

    var html = '<div class="co-cand-saved-card"'
      + ' data-cid="' + cid + '"'
      + ' data-name="' + _esc(item.full_name || '') + '"'
      + ' data-status="' + _esc(status) + '"'
      + ' data-notes="' + _esc(notes) + '"'
      + ' data-jobid="' + _esc(jobId) + '"'
      + ' data-rating="' + (rating || '') + '"'
      + ' data-priority="' + _esc(priority || '') + '"'
      + ' data-tags="' + _esc(JSON.stringify(tags)) + '"'
      + ' data-follow-up-at="' + _esc(followUpAt || '') + '"'
      + ' data-follow-up-status="' + _esc(followUpSt || '') + '"'
      + ' data-save-source="' + _esc(saveSource || '') + '"'
      + ' data-job-links="' + _esc(JSON.stringify(jobLinks)) + '">';

    // ── Top row (avatar + info + actions) ────────────────────────
    html += '<div class="co-cand-top">';

    html += '<div class="co-cand-ava">'
      + (item.avatar_url
          ? '<img src="' + _esc(item.avatar_url) + '" alt="" loading="lazy">'
          : _avatarSvg)
      + '</div>';

    html += '<div class="co-cand-info">';
    html += '<div class="co-cand-name-row">';
    html += '<span class="co-cand-name">' + _esc(item.full_name) + '</span>';
    if (priority) html += _priorityBadgeHTML(priority);
    html += '</div>';
    if (meta) html += '<div class="co-cand-meta">' + _esc(meta) + '</div>';

    // Rating stars + status badge row
    html += '<div class="co-cand-row2">';
    if (rating) html += _starsHTML(rating);
    if (date) html += '<span class="co-cand-date">حُفظ ' + _esc(date) + '</span>';
    html += '<span class="co-cand-status co-cand-status--' + _esc(_statusKey(status)) + '">'
          + _esc(_statusLabel(status)) + '</span>';
    html += '</div>';

    // Tags (top 3)
    if (tags.length) {
      html += '<div class="co-cand-tags-row">';
      var displayTags = tags.slice(0, 3);
      displayTags.forEach(function (t) {
        html += '<span class="co-cand-tag-chip">' + _esc(t) + '</span>';
      });
      if (tags.length > 3) {
        html += '<span class="co-cand-tag-chip co-cand-tag-more">+' + (tags.length - 3) + '</span>';
      }
      html += '</div>';
    }

    // Follow-up indicator
    if (followUpAt && followUpSt && followUpSt !== 'none') {
      html += '<div class="co-cand-followup-strip co-cand-followup--' + _esc(followUpSt) + '">'
        + '<span class="co-cand-followup-lbl">' + _esc(_FU_STATUS_LABELS[followUpSt] || followUpSt) + '</span>'
        + '<span class="co-cand-followup-date">' + _esc(_fmtDate(followUpAt)) + '</span>'
        + '</div>';
    }

    // Save source label
    if (saveSource && saveSource !== 'manual') {
      html += '<div class="co-cand-source-lbl">'
        + _esc(_SOURCE_LABELS[saveSource] || saveSource)
        + '</div>';
    }

    // Notes preview (truncated)
    if (notes) html += '<div class="co-cand-notes-pre">' + _esc(notes) + '</div>';

    // Job chips
    if (jobLinks.length) {
      html += '<div class="co-cand-job-chips">';
      jobLinks.forEach(function (jl, idx) {
        var applyDate   = jl.apply_date ? _fmtDate(jl.apply_date) : '';
        var hiddenCls   = idx >= 3 ? ' co-cand-job-chip--hidden' : '';
        var peId        = jl.pipeline_entry_id != null ? String(jl.pipeline_entry_id) : '';
        var appId       = jl.application_id    != null ? String(jl.application_id)    : '';
        var notesCount  = jl.pipeline_notes_count != null ? String(jl.pipeline_notes_count) : '0';
        var nextApptId  = (jl.next_appointment && jl.next_appointment.id) ? String(jl.next_appointment.id) : '';
        var nextApptSt  = (jl.next_appointment && jl.next_appointment.status) ? jl.next_appointment.status : '';
        html += '<button class="co-cand-job-chip' + hiddenCls + '" type="button"'
              + ' data-jid="' + _esc(String(jl.job_id)) + '"'
              + ' data-title="' + _esc(jl.title || '') + '"'
              + ' data-apply-date="' + _esc(applyDate) + '"'
              + ' data-app-status="' + _esc(jl.application_status || '') + '"'
              + ' data-cand-status="' + _esc(jl.candidate_status || '') + '"'
              + ' data-pe-id="' + _esc(peId) + '"'
              + ' data-app-id="' + _esc(appId) + '"'
              + ' data-notes-count="' + _esc(notesCount) + '"'
              + ' data-next-appt-id="' + _esc(nextApptId) + '"'
              + ' data-next-appt-status="' + _esc(nextApptSt) + '">'
              + _esc(jl.title || ('وظيفة #' + jl.job_id)) + '</button>';
      });
      if (jobLinks.length > 3) {
        html += '<button class="co-cand-chip-more-btn" type="button" aria-label="عرض المزيد من الوظائف">+'
              + (jobLinks.length - 3) + '</button>';
      }
      html += '</div>';
    }
    html += '</div>'; // .co-cand-info

    html += '<div class="co-cand-actions">';
    html += '<a class="co-cand-view-btn" href="/u/' + _esc(item.tw_id) + '" target="_blank" rel="noopener">عرض الملف العام</a>';
    html += '<button class="co-cand-manage-btn" data-cid="' + cid + '">إدارة الموهبة</button>';
    html += '</div>'; // .co-cand-actions

    html += '</div>'; // .co-cand-top

    // ── Manage panel (hidden by default) — V2 ────────────────────
    // Sections: Rating · Priority · Tags · Notes · Follow-up · Save source (read-only)
    // Pipeline status and Job link are NOT in this panel (managed separately).
    var fuStatusOpts = [
      {value: 'none',    label: 'لا متابعة'},
      {value: 'pending', label: 'قيد المتابعة'},
      {value: 'done',    label: 'تمت المتابعة'}
    ];
    html += '<div class="co-cand-manage-panel">';

    // Row 1: Rating (clearable 1-5 stars)
    html += '<div class="co-panel-section">';
    html += '<label class="co-cand-panel-label">التقييم</label>';
    html += '<div class="co-panel-stars" data-rating="' + (rating || 0) + '">';
    for (var si = 1; si <= 5; si++) {
      html += '<button type="button" class="co-panel-star' + (rating && si <= rating ? ' on' : '') + '"'
            + ' data-val="' + si + '">' + '★' + '</button>';
    }
    html += '<button type="button" class="co-panel-star-clear" title="مسح التقييم">✕</button>';
    html += '</div>';
    html += '</div>';

    // Row 2: Priority
    var priorityOpts2 = [
      {value: '',       label: '— بدون أولوية —'},
      {value: 'high',   label: 'عالية'},
      {value: 'medium', label: 'متوسطة'},
      {value: 'low',    label: 'منخفضة'}
    ];
    html += '<div class="co-panel-section">';
    html += '<label class="co-cand-panel-label">الأولوية</label>';
    html += _dpHTML('co-cand-dp-priority', priorityOpts2, priority || '');
    html += '</div>';

    // Row 3: Tags
    html += '<div class="co-panel-section">';
    html += '<label class="co-cand-panel-label">التصنيفات (tags)</label>';
    html += '<div class="co-panel-tags-wrap" id="coPanelTags_' + cid + '">';
    tags.forEach(function (t) {
      html += '<span class="co-panel-tag">'
            + '<span class="co-panel-tag-txt">' + _esc(t) + '</span>'
            + '<button type="button" class="co-panel-tag-del" data-tag="' + _esc(t) + '">✕</button>'
            + '</span>';
    });
    html += '</div>';
    html += '<div class="co-panel-tag-add-row">';
    html += '<input type="text" class="co-panel-tag-input" placeholder="أضف tag…" dir="rtl" maxlength="30">';
    html += '<button type="button" class="co-panel-tag-add-btn">+</button>';
    html += '</div>';
    html += '</div>';

    // Row 4: General notes
    html += '<div class="co-panel-section">';
    html += '<label class="co-cand-panel-label">ملاحظات عامة</label>';
    html += '<div class="co-cand-panel-ta-wrap">';
    html += '<textarea class="co-cand-panel-ta" maxlength="500"'
          + ' placeholder="أضف ملاحظة عن هذا المرشح…" dir="rtl">'
          + _esc(notes) + '</textarea>';
    html += '<span class="co-cand-panel-counter">' + notes.length + ' / 500</span>';
    html += '</div>';
    html += '</div>';

    // Row 5: Follow-up date + status
    html += '<div class="co-panel-section">';
    html += '<label class="co-cand-panel-label">المتابعة</label>';
    html += '<div class="co-panel-followup-row">';
    html += '<input type="date" class="co-panel-followup-date" value="' + _esc(followUpAt ? followUpAt.slice(0, 10) : '') + '">';
    html += _dpHTML('co-cand-dp-fu-status', fuStatusOpts, followUpSt || 'none');
    html += '</div>';
    html += '</div>';

    // Row 6: Save source (read-only)
    if (saveSource) {
      html += '<div class="co-panel-section co-panel-section--readonly">';
      html += '<label class="co-cand-panel-label">مصدر الحفظ</label>';
      html += '<span class="co-panel-source-val">' + _esc(_SOURCE_LABELS[saveSource] || saveSource) + '</span>';
      html += '</div>';
    }

    // Panel actions: Save + Cancel + Remove
    html += '<div class="co-cand-panel-acts">';
    html += '<button class="co-cand-panel-save" data-cid="' + cid + '">حفظ التعديل</button>';
    html += '<button class="co-cand-panel-cancel" data-cid="' + cid + '">إلغاء</button>';
    html += '<button class="co-cand-panel-remove" data-cid="' + cid + '">إزالة من بنك المواهب</button>';
    html += '</div>';
    html += '</div>'; // .co-cand-manage-panel

    html += '</div>'; // .co-cand-saved-card
    return html;
  }

  // Wire textarea character counters
  function _wireTextareaCounters() {
    _body.querySelectorAll('.co-cand-panel-ta').forEach(function (ta) {
      var counter = ta.parentNode.querySelector('.co-cand-panel-counter');
      ta.addEventListener('input', function () {
        if (counter) counter.textContent = ta.value.length + ' / 500';
      });
    });
  }

  // Unified event delegation for saved tab — remove + manage + panel save/cancel
  function _wireSavedCards() {
    _wireTextareaCounters();
    _body.removeEventListener('click', _onSavedClick);
    _body.addEventListener('click', _onSavedClick);

    // Req 5 & 6: auto-open manage panel after switching from suggestions tab
    if (_pendingManageOpen != null) {
      var pendCid   = _pendingManageOpen;
      var focusNotes = _pendingManageOpenNotes;
      _pendingManageOpen      = null;
      _pendingManageOpenNotes = false;
      var targetCard = _body.querySelector('.co-cand-saved-card[data-cid="' + pendCid + '"]');
      if (targetCard) {
        var manBtn = targetCard.querySelector('.co-cand-manage-btn');
        if (manBtn) {
          _togglePanel(manBtn);
          if (focusNotes) {
            var ta = targetCard.querySelector('.co-cand-panel-ta');
            if (ta) setTimeout(function () { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); }, 50);
          }
        }
      }
    }
  }

  function _onSavedClick(e) {
    // +N expand button — reveal hidden job chips in this card
    var moreBtn = e.target.closest('.co-cand-chip-more-btn');
    if (moreBtn) {
      var chipsRow = moreBtn.closest('.co-cand-job-chips');
      if (chipsRow) {
        chipsRow.querySelectorAll('.co-cand-job-chip--hidden').forEach(function (c) {
          c.classList.remove('co-cand-job-chip--hidden');
        });
      }
      moreBtn.remove();
      return;
    }

    // Pipeline notes button inside job chip popover
    var notesPopBtn = e.target.closest('.co-cjp-btn--notes');
    if (notesPopBtn) {
      var notesEntryId = notesPopBtn.getAttribute('data-pe-id');
      if (notesEntryId && typeof _openNotesPanel === 'function') {
        _closeJobPop();
        _openNotesPanel(parseInt(notesEntryId, 10));
      }
      return;
    }

    // Appointment button inside job chip popover (Path B: candidate_id + job_id)
    var apptPopBtn = e.target.closest('.co-cjp-btn--appt');
    if (apptPopBtn) {
      var apptEntryId  = apptPopBtn.getAttribute('data-pe-id')       || null;
      var apptAppId    = apptPopBtn.getAttribute('data-app-id')       || null;
      var apptCandId   = apptPopBtn.getAttribute('data-cand-id')      || null;
      var apptCandName = apptPopBtn.getAttribute('data-cand-name')    || '';
      var apptJobTitle = apptPopBtn.getAttribute('data-job-title')    || '';
      var apptJobId    = apptPopBtn.getAttribute('data-job-id')       || null;
      if (apptEntryId && typeof _openApptModal === 'function') {
        _closeJobPop();
        // Path B: set _appJobId before opening modal so the endpoint uses candidate_id + job_id
        if (typeof _appJobId !== 'undefined' && apptJobId) {
          _appJobId = parseInt(apptJobId, 10);
        }
        _openApptModal(
          apptAppId  ? parseInt(apptAppId, 10)  : null,
          apptCandName,
          apptJobTitle,
          parseInt(apptEntryId, 10),
          apptCandId ? parseInt(apptCandId, 10) : null
        );
      }
      return;
    }

    // Job chip popover
    var chipBtn = e.target.closest('.co-cand-job-chip');
    if (chipBtn && !chipBtn.classList.contains('co-cand-job-chip--hidden')) {
      _showJobChipPop(chipBtn, e);
      return;
    }

    // Custom dark picker — option selected
    var dpOpt = e.target.closest('.co-dp-opt');
    if (dpOpt) { _handleDpOptClick(dpOpt); return; }

    // Custom dark picker — toggle open/close
    var dpBtn = e.target.closest('.co-dp-btn');
    if (dpBtn) { _toggleDpOf(dpBtn); return; }

    // Click outside any picker → close all
    if (!e.target.closest('.co-dp-wrap')) _closeAllDp();

    var removeBtn = e.target.closest('.co-cand-remove-btn');
    if (removeBtn) { _handleRemove(removeBtn); return; }

    var panelRemoveBtn = e.target.closest('.co-cand-panel-remove');
    if (panelRemoveBtn) { _handlePanelRemove(panelRemoveBtn); return; }

    var manageBtn = e.target.closest('.co-cand-manage-btn');
    if (manageBtn) { _togglePanel(manageBtn); return; }

    var saveBtn = e.target.closest('.co-cand-panel-save');
    if (saveBtn) { _handlePanelSave(saveBtn); return; }

    var cancelBtn = e.target.closest('.co-cand-panel-cancel');
    if (cancelBtn) { _closePanelOf(cancelBtn); return; }

    // Star button click — update .co-panel-stars data-rating
    var starBtn = e.target.closest('.co-panel-star');
    if (starBtn) {
      var starsWrap2 = starBtn.closest('.co-panel-stars');
      if (starsWrap2) {
        var newR = parseInt(starBtn.getAttribute('data-val') || '0');
        var curR = parseInt(starsWrap2.getAttribute('data-rating') || '0');
        // Click same star = clear (toggle off)
        newR = (newR === curR) ? 0 : newR;
        starsWrap2.setAttribute('data-rating', newR);
        starsWrap2.querySelectorAll('.co-panel-star').forEach(function (sb) {
          sb.classList.toggle('on', parseInt(sb.getAttribute('data-val')) <= newR && newR > 0);
        });
      }
      return;
    }

    // Clear star button
    var starClear = e.target.closest('.co-panel-star-clear');
    if (starClear) {
      var starsWrap3 = starClear.closest('.co-panel-stars');
      if (starsWrap3) {
        starsWrap3.setAttribute('data-rating', '0');
        starsWrap3.querySelectorAll('.co-panel-star').forEach(function (sb) { sb.classList.remove('on'); });
      }
      return;
    }

    // Tag delete button
    var tagDelBtn = e.target.closest('.co-panel-tag-del');
    if (tagDelBtn) {
      var tagEl2 = tagDelBtn.closest('.co-panel-tag');
      if (tagEl2) tagEl2.parentNode.removeChild(tagEl2);
      return;
    }

    // Tag add button
    var tagAddBtn = e.target.closest('.co-panel-tag-add-btn');
    if (tagAddBtn) {
      var addRow = tagAddBtn.closest('.co-panel-tag-add-row');
      if (addRow) {
        var tagInput = addRow.querySelector('.co-panel-tag-input');
        if (tagInput) {
          var tagVal = tagInput.value.trim().slice(0, 30);
          if (!tagVal) return;
          var panelWrap = tagInput.closest('.co-cand-manage-panel');
          var tw = panelWrap && panelWrap.querySelector('.co-panel-tags-wrap');
          if (tw) {
            // Dedup check
            var existingTags = tw.querySelectorAll('.co-panel-tag-txt');
            var isDup = false;
            existingTags.forEach(function (el) {
              if (el.textContent.trim().toLowerCase() === tagVal.toLowerCase()) isDup = true;
            });
            if (isDup) return;
            if (existingTags.length >= 20) {
              if (window.showToast) showToast('الحد الأقصى 20 tag', 'error');
              return;
            }
            var tagSpan = document.createElement('span');
            tagSpan.className = 'co-panel-tag';
            tagSpan.innerHTML = '<span class="co-panel-tag-txt">' + _esc(tagVal) + '</span>'
              + '<button type="button" class="co-panel-tag-del" data-tag="' + _esc(tagVal) + '">✕</button>';
            tw.appendChild(tagSpan);
            tagInput.value = '';
          }
        }
      }
      return;
    }
  }

  // ── Job chip popover ────────────────────────────────────────────
  // Row 1: per-job candidate classification (company_candidate_job_refs.candidate_status)
  // Row 2: apply_date — shown only when the candidate actually applied (not null)
  // Row 3 (pipeline only): ملاحظات الوظيفة + تحديد موعد / فتح الموعد buttons
  function _showJobChipPop(chip) {
    var title         = chip.getAttribute('data-title') || '';
    var applyDate     = chip.getAttribute('data-apply-date') || '';
    var candJobSt     = chip.getAttribute('data-cand-status') || '';
    var candJobLbl    = candJobSt ? (_STATUS_LABELS[candJobSt] || candJobSt) : 'غير مصنف';
    var candJobCls    = candJobSt ? 'co-cjp-cand-job-st' : 'co-cjp-no-app';
    var peId          = chip.getAttribute('data-pe-id') || '';
    var appId         = chip.getAttribute('data-app-id') || '';
    var notesCount    = parseInt(chip.getAttribute('data-notes-count') || '0', 10) || 0;
    var nextApptId    = chip.getAttribute('data-next-appt-id') || '';
    var nextApptSt    = chip.getAttribute('data-next-appt-status') || '';
    var jobId         = chip.getAttribute('data-jid') || '';

    // Candidate name from parent card
    var card          = chip.closest('.co-cand-saved-card');
    var candId        = card ? (card.getAttribute('data-cid') || '') : '';
    var candName      = card ? (card.getAttribute('data-name') || '') : '';

    var pop = document.getElementById('co-cand-job-pop');
    if (!pop) {
      pop = document.createElement('div');
      pop.id = 'co-cand-job-pop';
      pop.className = 'co-cand-job-pop';
      document.body.appendChild(pop);
    }

    var html = '<div class="co-cjp-title">' + _esc(title) + '</div>';
    html += '<div class="co-cjp-row"><span>حالة المرشح في هذه الوظيفة</span><span class="' + candJobCls + '">' + _esc(candJobLbl) + '</span></div>';
    if (applyDate) {
      html += '<div class="co-cjp-row co-cjp-row--date"><span>تاريخ التقدم</span><span>' + _esc(applyDate) + '</span></div>';
    }
    // Pipeline action buttons — only when this chip has a real pipeline entry
    if (peId) {
      var notesLbl  = notesCount > 0 ? ('ملاحظات الوظيفة (' + notesCount + ')') : 'ملاحظات الوظيفة';
      var apptLabel = nextApptId ? 'فتح الموعد' : 'تحديد موعد';
      html += '<div class="co-cjp-actions">'
            + '<button type="button" class="co-cjp-btn co-cjp-btn--notes"'
            + ' data-pe-id="' + _esc(peId) + '">' + _esc(notesLbl) + '</button>'
            + '<button type="button" class="co-cjp-btn co-cjp-btn--appt"'
            + ' data-pe-id="' + _esc(peId) + '"'
            + ' data-app-id="' + _esc(appId) + '"'
            + ' data-cand-id="' + _esc(candId) + '"'
            + ' data-cand-name="' + _esc(candName) + '"'
            + ' data-job-title="' + _esc(title) + '"'
            + ' data-job-id="' + _esc(jobId) + '"'
            + ' data-next-appt-id="' + _esc(nextApptId) + '">'
            + _esc(apptLabel) + '</button>'
            + '</div>';
    }
    pop.innerHTML = html;
    pop.style.display = 'block';

    _jobPopPositionFromChip(chip, pop);
    _jobPopTarget = chip;

    // Close on outside click — _closeJobPop is named so it can be removed in _closeJobPop()
    setTimeout(function () {
      document.addEventListener('click', _closeJobPop, { capture: true });
    }, 0);
    window.addEventListener('scroll', _closeJobPop, { once: true, passive: true });
    window.addEventListener('resize', _closeJobPop, { once: true });
  }

  // Position popover below chip; flip above when not enough room below
  function _jobPopPositionFromChip(chip, pop) {
    var rect  = chip.getBoundingClientRect();
    var popH  = pop.offsetHeight;
    var popW  = pop.offsetWidth;
    var winH  = window.innerHeight;
    var winW  = window.innerWidth;

    // Prefer below; flip above if insufficient space and above has room
    var top = (rect.bottom + popH + 6 > winH - 8 && rect.top > popH + 6)
      ? rect.top - popH - 6
      : rect.bottom + 6;

    // Clamp horizontally within viewport
    var left = rect.left;
    if (left + popW > winW - 8) left = winW - popW - 8;
    if (left < 8) left = 8;

    // Full vertical clamp: 8 <= top <= innerHeight - popH - 8
    var maxTop = winH - popH - 8;
    pop.style.top  = Math.min(Math.max(8, top), maxTop) + 'px';
    pop.style.left = left + 'px';
  }

  function _closeJobPop() {
    var pop = document.getElementById('co-cand-job-pop');
    if (pop) pop.style.display = 'none';
    document.removeEventListener('click', _closeJobPop, { capture: true });
    window.removeEventListener('scroll', _closeJobPop);
    window.removeEventListener('resize', _closeJobPop);
    _jobPopTarget = null;
  }

  // Unified helper: syncs all job-link UI on a card from a canonical links array.
  // Responsibilities:
  //   1. Updates data-job-links (single client-side source of truth)
  //   2. Rebuilds job chip strip (preserves candidate_status per chip)
  //   3. Rebuilds "تصنيف المرشح لكل وظيفة" section (custom pickers, not native selects)
  //   4. Updates job picker disabled/linked states
  //   5. Adds or removes the status section when links appear / disappear
  //   6. Renders picker buttons as disabled when card has data-job-status-saving lock
  function _renderCandidateJobLinksUI(card, links) {
    // Registry-based lock check: a candidate in _jobStatusInFlight gets pickers rebuilt
    // as disabled even when the card DOM was replaced by a list rebuild mid-flight.
    // data-job-status-saving is kept as a secondary visual signal only.
    var cidStr   = card.getAttribute('data-cid') || '';
    var isLocked = !!(cidStr && _jobStatusInFlight[cidStr]) || !!card.getAttribute('data-job-status-saving');

    // 1. Canonical store
    card.setAttribute('data-job-links', JSON.stringify(links));

    // 2. Chip strip
    var chipsHtml = links.map(function (jl, idx) {
      var applyDate  = jl.apply_date ? _fmtDate(jl.apply_date) : '';
      var hiddenCls  = idx >= 3 ? ' co-cand-job-chip--hidden' : '';
      var peId       = jl.pipeline_entry_id != null ? String(jl.pipeline_entry_id) : '';
      var appId      = jl.application_id    != null ? String(jl.application_id)    : '';
      var notesCount = jl.pipeline_notes_count != null ? String(jl.pipeline_notes_count) : '0';
      var nextApptId = (jl.next_appointment && jl.next_appointment.id) ? String(jl.next_appointment.id) : '';
      var nextApptSt = (jl.next_appointment && jl.next_appointment.status) ? jl.next_appointment.status : '';
      return '<button class="co-cand-job-chip' + hiddenCls + '" type="button"'
           + ' data-jid="' + _esc(String(jl.job_id)) + '"'
           + ' data-title="' + _esc(jl.title || '') + '"'
           + ' data-apply-date="' + _esc(applyDate) + '"'
           + ' data-app-status="' + _esc(jl.application_status || '') + '"'
           + ' data-cand-status="' + _esc(jl.candidate_status || '') + '"'
           + ' data-pe-id="' + _esc(peId) + '"'
           + ' data-app-id="' + _esc(appId) + '"'
           + ' data-notes-count="' + _esc(notesCount) + '"'
           + ' data-next-appt-id="' + _esc(nextApptId) + '"'
           + ' data-next-appt-status="' + _esc(nextApptSt) + '">'
           + _esc(jl.title || ('وظيفة #' + jl.job_id)) + '</button>';
    }).join('');
    if (links.length > 3) {
      chipsHtml += '<button class="co-cand-chip-more-btn" type="button" aria-label="عرض المزيد من الوظائف">+'
                 + (links.length - 3) + '</button>';
    }
    var chipsWrap = card.querySelector('.co-cand-job-chips');
    if (chipsWrap) {
      chipsWrap.innerHTML = chipsHtml;
    } else if (chipsHtml) {
      var wrap = document.createElement('div');
      wrap.className = 'co-cand-job-chips';
      wrap.innerHTML = chipsHtml;
      var infoDiv = card.querySelector('.co-cand-info');
      if (infoDiv) infoDiv.appendChild(wrap);
    }

  }

  // Thin wrapper kept for any external callers — delegates to unified helper
  function _updateChips(card, links) {
    _renderCandidateJobLinksUI(card, links);
  }

  function _handleRemove(btn) {
    var cid = parseInt(btn.getAttribute('data-cid'));
    if (!cid) return;
    btn.disabled = true;
    if (!window.deleteSavedCandidate) return;
    window.deleteSavedCandidate(cid)
      .then(function (res) {
        if (res && res.ok) {
          var card = btn.closest('.co-cand-saved-card');
          if (card) {
            card.style.transition = 'opacity .2s';
            card.style.opacity = '0';
            setTimeout(function () {
              if (card.parentNode) card.parentNode.removeChild(card);
              var list = document.getElementById('coCandSavedList');
              if (list && !list.querySelector('.co-cand-saved-card')) {
                list.innerHTML = _savedEmptyHTML(_savedFilter, _savedSearch);
              }
            }, 220);
          }
          _loadSavedStats(null);
          if (window.showToast) showToast('تمت إزالة المرشح');
        } else {
          btn.disabled = false;
          if (window.showToast) showToast('تعذّر الإزالة', 'error');
        }
      })
      .catch(function () {
        btn.disabled = false;
        if (window.showToast) showToast('تعذّر الإزالة', 'error');
      });
  }

  // Panel remove button — confirm before deleting
  function _handlePanelRemove(btn) {
    var cid = parseInt(btn.getAttribute('data-cid'));
    if (!cid) return;
    if (!window.confirm('هل تريد إزالة هذا المرشح من بنك المواهب نهائياً؟')) return;
    btn.disabled    = true;
    btn.textContent = 'جارٍ الإزالة…';
    if (!window.deleteSavedCandidate) return;
    window.deleteSavedCandidate(cid)
      .then(function (res) {
        if (res && res.ok) {
          var card = btn.closest('.co-cand-saved-card');
          if (card) {
            card.style.transition = 'opacity .2s';
            card.style.opacity = '0';
            setTimeout(function () {
              if (card.parentNode) card.parentNode.removeChild(card);
              var list = document.getElementById('coCandSavedList');
              if (list && !list.querySelector('.co-cand-saved-card')) {
                list.innerHTML = _savedEmptyHTML(_savedFilter, _savedSearch);
              }
            }, 220);
          }
          _loadSavedStats(null);
          _loadTalentBankQuota();
          if (window.showToast) showToast('تمت إزالة المرشح من بنك المواهب');
        } else {
          btn.disabled    = false;
          btn.textContent = 'إزالة من بنك المواهب';
          if (window.showToast) showToast('تعذّر الإزالة', 'error');
        }
      })
      .catch(function () {
        btn.disabled    = false;
        btn.textContent = 'إزالة من بنك المواهب';
        if (window.showToast) showToast('تعذّر الإزالة', 'error');
      });
  }

  function _togglePanel(btn) {
    var card  = btn.closest('.co-cand-saved-card');
    var panel = card ? card.querySelector('.co-cand-manage-panel') : null;
    if (!panel) return;

    // Close other open panels first
    _body.querySelectorAll('.co-cand-manage-panel.open').forEach(function (p) {
      if (p !== panel) {
        p.classList.remove('open');
        var otherCard = p.closest('.co-cand-saved-card');
        if (otherCard) {
          var otherBtn = otherCard.querySelector('.co-cand-manage-btn');
          if (otherBtn) otherBtn.classList.remove('active');
        }
      }
    });

    var isOpen = panel.classList.contains('open');
    panel.classList.toggle('open', !isOpen);
    btn.classList.toggle('active', !isOpen);
  }

  function _closePanelOf(btn) {
    var card  = btn.closest('.co-cand-saved-card');
    var panel = card ? card.querySelector('.co-cand-manage-panel') : null;
    if (!panel) return;
    panel.classList.remove('open');
    var manBtn = card.querySelector('.co-cand-manage-btn');
    if (manBtn) manBtn.classList.remove('active');
  }

  // Talent Bank manage panel save — sends ONLY talent management fields.
  // Pipeline status (status) and Job link (job_id) are NEVER sent from this panel.
  function _handlePanelSave(btn) {
    var cid = parseInt(btn.getAttribute('data-cid'));
    if (!cid) return;
    var card  = btn.closest('.co-cand-saved-card');
    var panel = card ? card.querySelector('.co-cand-manage-panel') : null;
    if (!panel) return;

    var ta         = panel.querySelector('.co-cand-panel-ta');
    var dpPriority = panel.querySelector('.co-cand-dp-priority');
    var starsWrap  = panel.querySelector('.co-panel-stars');
    var dpFuStatus = panel.querySelector('.co-cand-dp-fu-status');
    var fuDateEl   = panel.querySelector('.co-panel-followup-date');
    var tagsWrap   = panel.querySelector('.co-panel-tags-wrap');

    // Build payload — talent fields only; status and job_id are explicitly excluded.
    var payload = {};
    if (ta) payload.notes = ta.value;
    if (dpPriority) {
      var pval = dpPriority.getAttribute('data-selected') || '';
      payload.priority = pval || null;
    }
    if (starsWrap) {
      var rval = parseInt(starsWrap.getAttribute('data-rating') || '0');
      payload.rating = rval > 0 ? rval : null;
    }
    if (dpFuStatus) {
      var fsval = dpFuStatus.getAttribute('data-selected') || 'none';
      payload.follow_up_status = fsval || 'none';
    }
    if (fuDateEl) {
      payload.follow_up_at = fuDateEl.value || null;
    }
    if (tagsWrap) {
      var tagEls = tagsWrap.querySelectorAll('.co-panel-tag-txt');
      var collectedTags = [];
      tagEls.forEach(function (el) {
        var t = el.textContent.trim();
        if (t) collectedTags.push(t);
      });
      payload.tags = collectedTags.length ? collectedTags : null;
    }

    if (!window.updateSavedCandidate) return;
    btn.disabled    = true;
    btn.textContent = 'جارٍ الحفظ…';

    window.updateSavedCandidate(cid, payload)
      .then(function (res) {
        if (!res || !res.ok || !res.data || !res.data.item) {
          if (window.showToast) showToast('تعذّر الحفظ', 'error');
          return;
        }
        var updated = res.data.item;
        _applyCardUpdate(card, updated);
        _closePanelOf(btn);
        _loadSavedStats(null);

        if (window.showToast) showToast('تم تحديث المرشح');
      })
      .catch(function () {
        if (window.showToast) showToast('تعذّر الحفظ', 'error');
      })
      .finally(function () {
        btn.disabled    = false;
        btn.textContent = 'حفظ التعديل';
      });
  }

  // Update card in-place after successful PATCH — no full re-render
  function _applyCardUpdate(card, data) {
    if (!card || !data) return;
    var newStatus      = data.status          || 'saved';
    var newNotes       = data.notes           || '';
    var newJobId       = data.job_id  != null ? String(data.job_id) : '';
    var newRating      = data.rating  != null ? data.rating  : null;
    var newPriority    = data.priority        || null;
    var newTags        = Array.isArray(data.tags) ? data.tags : [];
    var newFuAt        = data.follow_up_at    || null;
    var newFuStatus    = data.follow_up_status || null;

    // Update data attributes (source of truth for next panel open)
    card.setAttribute('data-status',          newStatus);
    card.setAttribute('data-notes',           newNotes);
    card.setAttribute('data-jobid',           newJobId);
    card.setAttribute('data-rating',          newRating || '');
    card.setAttribute('data-priority',        newPriority || '');
    card.setAttribute('data-tags',            JSON.stringify(newTags));
    card.setAttribute('data-follow-up-at',    newFuAt || '');
    card.setAttribute('data-follow-up-status', newFuStatus || '');

    // Update status badge class + text
    var badge = card.querySelector('.co-cand-status');
    if (badge) {
      _STATUS_ORDER.forEach(function (s) { badge.classList.remove('co-cand-status--' + s); });
      badge.classList.add('co-cand-status--' + _statusKey(newStatus));
      badge.textContent = _statusLabel(newStatus);
    }

    // Update notes preview
    var notesPre = card.querySelector('.co-cand-notes-pre');
    if (newNotes) {
      if (notesPre) {
        notesPre.textContent = newNotes;
      } else {
        var row2 = card.querySelector('.co-cand-row2');
        if (row2) {
          var nd = document.createElement('div');
          nd.className   = 'co-cand-notes-pre';
          nd.textContent = newNotes;
          row2.parentNode.insertBefore(nd, row2.nextSibling);
        }
      }
    } else if (notesPre) {
      notesPre.parentNode.removeChild(notesPre);
    }

    // Remove legacy raw ID display if present
    var jobRef = card.querySelector('.co-cand-job-ref');
    if (jobRef) jobRef.parentNode.removeChild(jobRef);

    // Update stars display on card
    var starsDisplay = card.querySelector('.co-cand-stars');
    if (starsDisplay) {
      starsDisplay.innerHTML = '';
      for (var _si = 1; _si <= 5; _si++) {
        var s = document.createElement('span');
        s.className = 'co-cand-star' + (_si <= newRating ? ' co-cand-star--on' : '');
        s.textContent = '★';
        starsDisplay.appendChild(s);
      }
    } else if (newRating) {
      var row2b = card.querySelector('.co-cand-row2');
      if (row2b) {
        var sd = document.createElement('span');
        sd.className = 'co-cand-stars';
        sd.innerHTML = _starsHTML(newRating).replace(/<span class="co-cand-stars">|<\/span>$/g, '');
        row2b.insertBefore(sd, row2b.firstChild);
      }
    }

    // Update priority badge on card
    var nameRow = card.querySelector('.co-cand-name-row');
    var oldBadge = nameRow && nameRow.querySelector('.co-cand-priority');
    if (oldBadge) oldBadge.parentNode.removeChild(oldBadge);
    if (newPriority && nameRow) {
      var tmp = document.createElement('div');
      tmp.innerHTML = _priorityBadgeHTML(newPriority);
      if (tmp.firstChild) nameRow.appendChild(tmp.firstChild);
    }

    // Update tags display on card
    var oldTagsRow = card.querySelector('.co-cand-tags-row');
    if (oldTagsRow) oldTagsRow.parentNode.removeChild(oldTagsRow);
    if (newTags.length) {
      var tagsRowEl = document.createElement('div');
      tagsRowEl.className = 'co-cand-tags-row';
      newTags.slice(0, 3).forEach(function (t) {
        var tc = document.createElement('span');
        tc.className = 'co-cand-tag-chip';
        tc.textContent = t;
        tagsRowEl.appendChild(tc);
      });
      if (newTags.length > 3) {
        var moreChip = document.createElement('span');
        moreChip.className = 'co-cand-tag-chip co-cand-tag-more';
        moreChip.textContent = '+' + (newTags.length - 3);
        tagsRowEl.appendChild(moreChip);
      }
      var notesPre2 = card.querySelector('.co-cand-notes-pre');
      var insertAfter = notesPre2 || card.querySelector('.co-cand-followup-strip') || card.querySelector('.co-cand-row2');
      if (insertAfter && insertAfter.parentNode) {
        insertAfter.parentNode.insertBefore(tagsRowEl, insertAfter.nextSibling);
      }
    }

    // Sync panel stars widget data-rating
    var panelStars = card.querySelector('.co-panel-stars');
    if (panelStars) {
      panelStars.setAttribute('data-rating', newRating || 0);
      panelStars.querySelectorAll('.co-panel-star').forEach(function (sb) {
        var sv = parseInt(sb.getAttribute('data-val') || '0');
        sb.classList.toggle('on', sv <= newRating);
      });
    }
  }

  // ────────────────────────────────────────────────────────────────
  // TAB 2 — Suggestions (Phase 5B — unchanged)
  // ────────────────────────────────────────────────────────────────

  function _fetchSuggestions(offset) {
    if (_suggLoading) return;
    _suggLoading = true;
    if (offset === 0) _body.innerHTML = '<div class="co-fl-spin">جارٍ التحميل…</div>';
    if (!window.getCandidateSuggestions) { _suggLoading = false; return; }
    window.getCandidateSuggestions(20, offset)
      .then(function (res) {
        if (!res || !res.ok) {
          var code = res && res.status;
          if (offset === 0) {
            _body.innerHTML = (code === 401 || code === 403)
              ? '<div class="co-fl-empty">غير مصرح بالوصول للاقتراحات</div>'
              : '<div class="co-fl-empty">تعذّر تحميل الاقتراحات</div>';
          }
          return;
        }
        var data  = res.data || {};
        var items = data.items || [];
        var pg    = data.pagination || {};

        if (data.status === 'no_jobs') {
          if (offset === 0) _body.innerHTML = _suggNoJobsHTML();
          return;
        }

        if (offset === 0) {
          if (items.length === 0) { _body.innerHTML = _suggEmptyHTML(); return; }
          _renderSuggestions(items, pg);
        } else {
          _appendSuggestions(items, pg);
        }
      })
      .catch(function () {
        if (offset === 0) _body.innerHTML = '<div class="co-fl-empty">تعذّر تحميل الاقتراحات</div>';
      })
      .finally(function () { _suggLoading = false; });
  }

  function _suggNoJobsHTML() {
    return '<div class="co-cand-empty">' +
      '<div class="co-cand-empty-title">لا توجد اقتراحات بعد</div>' +
      '<div class="co-cand-empty-sub">انشر وظيفة أولاً لتحسين الاقتراحات.</div>' +
      '</div>';
  }

  function _suggEmptyHTML() {
    return '<div class="co-cand-empty">' +
      '<div class="co-cand-empty-title">لا توجد اقتراحات إضافية حالياً</div>' +
      '<div class="co-cand-empty-sub">سنقترح مرشحين عند توفر تطابق أفضل.</div>' +
      '</div>';
  }

  function _suggItemHTML(item) {
    var meta    = [item.profession, item.city, item.country].filter(Boolean).join(' · ');
    var score   = item.match_score || 0;
    var reasons = item.match_reasons || [];
    var html = '<div class="co-cand-item co-sugg-item" data-cid="' + _esc(item.candidate_id) + '">';
    html += '<div class="co-cand-ava">' + (item.avatar_url ? '<img src="' + _esc(item.avatar_url) + '" alt="" loading="lazy">' : _avatarSvg) + '</div>';
    html += '<div class="co-cand-info">';
    html += '<div class="co-sugg-name-row">';
    html += '<div class="co-cand-name">' + _esc(item.full_name) + '</div>';
    html += '<span class="co-sugg-score">' + score + '%</span>';
    html += '</div>';
    if (meta) html += '<div class="co-cand-meta">' + _esc(meta) + '</div>';
    if (reasons.length) {
      html += '<div class="co-sugg-reasons">';
      reasons.forEach(function (r) { html += '<span class="co-sugg-chip">' + _esc(r) + '</span>'; });
      html += '</div>';
    }
    html += '</div>';
    html += '<div class="co-cand-actions">';
    html += '<a class="co-cand-view-btn" href="/u/' + _esc(item.tw_id) + '" target="_blank" rel="noopener">فتح البروفايل</a>';
    html += '<button class="co-sugg-save-btn" data-cid="' + _esc(item.candidate_id) + '">حفظ كمرشح</button>';
    html += '</div></div>';
    return html;
  }

  function _renderSuggestions(items, pg) {
    var html = '<div id="coCandSuggList">';
    items.forEach(function (item) { html += _suggItemHTML(item); });
    html += '</div>';
    if (pg && pg.has_more) html += '<button class="co-sugg-load-more" id="coCandLoadMore">عرض المزيد</button>';
    _body.innerHTML = html;
    _wireSaveButtons();
    _wireLoadMore(pg);
  }

  function _appendSuggestions(items, pg) {
    var oldMore = document.getElementById('coCandLoadMore');
    if (oldMore && oldMore.parentNode) oldMore.parentNode.removeChild(oldMore);
    var list = _body.querySelector('#coCandSuggList');
    if (!list) return;
    items.forEach(function (item) {
      var tmp = document.createElement('div');
      tmp.innerHTML = _suggItemHTML(item);
      while (tmp.firstChild) list.appendChild(tmp.firstChild);
    });
    if (pg && pg.has_more) {
      var btn = document.createElement('button');
      btn.className = 'co-sugg-load-more'; btn.id = 'coCandLoadMore'; btn.textContent = 'عرض المزيد';
      _body.appendChild(btn);
      _wireLoadMore(pg);
    }
    _wireSaveButtons();
  }

  function _wireLoadMore(pg) {
    var btn = document.getElementById('coCandLoadMore');
    if (!btn || !pg || !pg.has_more) return;
    btn.addEventListener('click', function () {
      _suggOffset = (pg.offset || 0) + (pg.limit || 20);
      btn.disabled = true;
      btn.textContent = 'جارٍ التحميل…';
      _fetchSuggestions(_suggOffset);
    });
  }

  function _wireSaveButtons() {
    _body.querySelectorAll('.co-sugg-save-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var cid = parseInt(btn.getAttribute('data-cid'));
        if (!cid) return;
        btn.disabled = true;
        btn.textContent = 'جارٍ الحفظ…';
        if (!window.saveSuggestedCandidate) { btn.disabled = false; return; }
        window.saveSuggestedCandidate(cid)
          .then(function (res) {
            if (res && res.ok) {
              _loadSavedStats(null);
              var row = btn.closest('.co-cand-item');
              // Req 5: swap save btn for manage btn (clone removes old listener)
              var newBtn = document.createElement('button');
              newBtn.className = 'co-sugg-save-btn co-sugg-manage-mode';
              newBtn.type      = 'button';
              newBtn.textContent = 'إدارة المرشح';
              newBtn.addEventListener('click', function () {
                _pendingManageOpen      = cid;
                _pendingManageOpenNotes = false;
                _switchTab('saved');
              });
              if (btn.parentNode) btn.parentNode.replaceChild(newBtn, btn);
              // Req 6: show inline confirmation card
              if (row) {
                var existing = row.querySelector('.co-sugg-confirm');
                if (!existing) {
                  var conf = document.createElement('div');
                  conf.className = 'co-sugg-confirm';
                  conf.innerHTML = '<span class="co-sugg-conf-msg">✓ تم حفظ المرشح</span>'
                    + '<button class="co-sugg-conf-notes" type="button">إضافة ملاحظة</button>'
                    + '<button class="co-sugg-conf-later" type="button">ليس الآن</button>';
                  conf.querySelector('.co-sugg-conf-notes').addEventListener('click', function () {
                    _pendingManageOpen      = cid;
                    _pendingManageOpenNotes = true;
                    _switchTab('saved');
                  });
                  conf.querySelector('.co-sugg-conf-later').addEventListener('click', function () {
                    conf.parentNode && conf.parentNode.removeChild(conf);
                  });
                  row.appendChild(conf);
                }
              }
            } else {
              btn.disabled = false;
              btn.textContent = 'حفظ كمرشح';
              if (res && res.status === 409 && res.data && res.data.code === 'talent_bank_limit_reached') {
                var body = res.data;
                if (window.showToast) showToast(
                  'وصلت للحد المجاني لبنك المواهب: ' + body.used + ' من ' + body.limit
                  + '. احذف موهبة محفوظة أو قم بترقية الخطة لإضافة شخص جديد.',
                  'error');
              } else {
                if (window.showToast) showToast('تعذّر الحفظ', 'error');
              }
            }
          })
          .catch(function () {
            btn.disabled = false;
            btn.textContent = 'حفظ كمرشح';
            if (window.showToast) showToast('تعذّر الحفظ', 'error');
          });
      });
    });
  }

  // ── Wire events ────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    if (_openBtn) _openBtn.addEventListener('click', _open);
    if (_closeBtn) _closeBtn.addEventListener('click', _close);
    if (_overlay) _overlay.addEventListener('click', function (e) {
      if (e.target === _overlay) _close();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && _overlay && _overlay.style.display !== 'none') _close();
    });

    // Tab clicks
    var tabsEl = document.getElementById('coCandTabs');
    if (tabsEl) {
      tabsEl.addEventListener('click', function (e) {
        var t = e.target.closest('.co-cand-tab');
        if (!t || !_isOwner()) return;
        var tab = t.getAttribute('data-tab');
        if (tab && tab !== _activeTab) _switchTab(tab);
      });
    }
  });

  // ── Expose for loadData hook ───────────────────────────────────
  window._loadCandidatesBadge = _loadBadge;
  window._coCandOpen          = _open;

  // Listen for applicant classification events → sync live saved-candidate cards immediately.
  // Dispatched by _execClassify and _execPromote in the Applicants IIFE on success only.
  document.addEventListener('tw:candidate-job-classification-updated', function (evt) {
    var d = evt && evt.detail;
    if (!d || !d.candidateId || !d.jobId) return;
    var card = _findLiveSavedCandidateCard(d.candidateId);
    if (!card) return;
    var links = [];
    try { links = JSON.parse(card.getAttribute('data-job-links') || '[]'); } catch (e) {}
    var matched = false;
    links = links.map(function (jl) {
      if (String(jl.job_id) === String(d.jobId)) {
        matched = true;
        return Object.assign({}, jl, {
          application_status: d.applicationStatus != null ? d.applicationStatus : jl.application_status,
          status:             d.applicationStatus != null ? d.applicationStatus : jl.status,
          candidate_status:   d.candidateStatus   !== undefined ? d.candidateStatus : jl.candidate_status
        });
      }
      return jl;
    });
    if (matched) _renderCandidateJobLinksUI(card, links);
  });
}());

// ── Communication Hub (owner-only entry point) ─────────────────────────────
(function () {
  'use strict';
  var _activeTab   = 'messages';
  var _apptsLoaded = false;

  function _open() {
    var ov = document.getElementById('coHubOverlay');
    if (!ov) return;
    ov.style.display = 'flex';
    document.body.classList.add('co-hub-open');
  }

  function _close() {
    var ov = document.getElementById('coHubOverlay');
    if (!ov) return;
    ov.style.display = 'none';
    document.body.classList.remove('co-hub-open');
  }

  function _switchHubTab(tab) {
    if (!tab) return;
    _activeTab = tab;
    document.querySelectorAll('.co-hub-tab').forEach(function (t) {
      t.classList.toggle('active', t.getAttribute('data-hub-tab') === tab);
    });
    var msg  = document.getElementById('coHubMsgPanel');
    var appt = document.getElementById('coHubApptPanel');
    if (msg)  msg.style.display  = (tab === 'messages')      ? '' : 'none';
    if (appt) appt.style.display = (tab === 'appointments') ? '' : 'none';
    if (tab === 'appointments' && !_apptsLoaded) _loadAppts();
  }

  function _fmtDate(iso) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleDateString('ar-EG',
        { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch (e) { return ''; }
  }

  function _loadAppts() {
    var list = document.getElementById('coHubApptList');
    if (!list) return;
    if (!window.loadCompanyAppointments) {
      list.innerHTML = '';
      var msg = document.createElement('div');
      msg.className = 'co-hub-appt-empty';
      msg.textContent = 'اذهب إلى صفحة المواعيد لإدارة مقابلاتك';
      list.appendChild(msg);
      return;
    }
    window.loadCompanyAppointments(function (appts) {
      _apptsLoaded = true;
      list.innerHTML = '';
      var upcoming = appts.filter(function (a) {
        return a.status === 'confirmed' || a.status === 'pending_response';
      }).slice(0, 5);
      if (!upcoming.length) {
        var empty = document.createElement('div');
        empty.className = 'co-hub-appt-empty';
        empty.textContent = 'لا مواعيد قادمة حالياً';
        list.appendChild(empty);
        return;
      }
      upcoming.forEach(function (a) {
        var item    = document.createElement('div');
        item.className = 'co-hub-appt-item';
        var nameEl  = document.createElement('div');
        nameEl.className = 'co-hub-appt-name';
        nameEl.textContent = a.title || a.other_party_name || 'موعد';
        var dateEl  = document.createElement('div');
        dateEl.className = 'co-hub-appt-date';
        dateEl.textContent = _fmtDate(a.scheduled_at);
        var link    = document.createElement('a');
        link.href   = '/appointment-room?id=' + encodeURIComponent(a.id);
        link.className = 'co-hub-appt-link';
        link.textContent = 'عرض التفاصيل';
        item.appendChild(nameEl);
        item.appendChild(dateEl);
        item.appendChild(link);
        list.appendChild(item);
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var openBtn  = document.getElementById('coHubBtn');
    var closeBtn = document.getElementById('coHubCloseBtn');
    var ov       = document.getElementById('coHubOverlay');

    if (openBtn)  openBtn.addEventListener('click', _open);
    if (closeBtn) closeBtn.addEventListener('click', _close);
    if (ov) {
      ov.addEventListener('click', function (e) {
        if (e.target === ov) _close();
      });
      ov.addEventListener('click', function (e) {
        var t = e.target.closest('.co-hub-tab');
        if (t) _switchHubTab(t.getAttribute('data-hub-tab'));
      });
    }
    document.addEventListener('keydown', function (e) {
      var ov2 = document.getElementById('coHubOverlay');
      if (e.key === 'Escape' && ov2 && ov2.style.display === 'flex') _close();
    });
    window.addEventListener('popstate', _close);
  });

  window._coHubOpen  = _open;
  window._coHubClose = _close;
}());
