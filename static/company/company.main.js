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

  // ── Cover photo ────────────────────────────────────────────────
  function setCover(src) {
    var img = document.getElementById('coverImg');
    if (!img) return;
    img.src = src; img.style.display = 'block';
    setTimeout(function () { img.style.opacity = '1'; }, 50);
  }
  var isUploadingCover = false;
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

    var userId = window.companyState && companyState.profile && companyState.profile.id;
    if (!userId) return;
    var jwt = window._jwt ? _jwt() : '';
    if (!jwt) { window.location.href = '/login'; return; }

    if (isUploadingCover) return;
    isUploadingCover = true;
    var uploadBtn = document.getElementById('coverUploadBtn');
    if (uploadBtn) uploadBtn.style.pointerEvents = 'none';

    var reader = new FileReader();
    reader.onload = function (e) {
      var dataUrl = e.target.result;

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
      })
      .catch(function () {
        if (window.showToast) showToast('تعذّر رفع الغلاف، حاول مرة أخرى', 'error');
      })
      .finally(function () {
        isUploadingCover = false;
        if (uploadBtn) uploadBtn.style.pointerEvents = '';
      });
    };
    reader.readAsDataURL(file);
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

  // ── Applicants Modal — owner-only, per-job ────────────────────
  var _appJobId               = null;
  var _appLoading             = false;
  var _appModalHistoryPushed  = false; // true after pushState for applicants modal
  var _contactHistoryPushed   = false; // true after pushState for contact modal
  var _editHistoryPushed      = false; // true after pushState for edit modal
  var _astFloat               = null;   // singleton floating status dropdown (body-level)
  var _astFloatTrigger        = null;   // trigger button that opened the float
  var _cardListenerBound      = false;  // delegation guard for #coAppList
  var _APP_STATUS_LABEL = {
    pending:  'بانتظار المراجعة',
    viewed:   'تمت المراجعة',
    accepted: 'مقبول',
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
    _closeAstFloat();
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
      var initial   = (a.full_name || '؟').charAt(0);
      var statusKey = a.status || 'pending';
      var statusLbl = _APP_STATUS_LABEL[statusKey] || statusKey;
      var dateStr   = _appFmtDate(a.applied_at);
      var appId      = parseInt(a.id, 10);
      var isSaved    = !!a.is_saved;
      var isAccepted = statusKey === 'accepted';
      var isRejected = statusKey === 'rejected';
      var avatarHtml = a.avatar_url
        ? '<img src="' + _escApp(a.avatar_url) + '" alt="" loading="lazy"'
          + ' onerror="this.style.display=\'none\';this.parentNode.dataset.fb=\'1\'">'
          + '<span class="co-app-ava-fb">' + _escApp(initial) + '</span>'
        : _escApp(initial);
      html += '<div class="co-app-card" data-app-id="' + appId + '">'
        + '<div class="co-app-card-head">'
        +   '<div class="co-app-ava">' + avatarHtml + '</div>'
        +   '<div class="co-app-info">'
        +     '<div class="co-app-name">' + _escApp(a.full_name || '—') + '</div>'
        +     (dateStr ? '<div class="co-app-date">تقدّم: ' + _escApp(dateStr) + '</div>' : '')
        +   '</div>'
        +   '<span class="co-app-status co-app-status--' + _escApp(statusKey) + '">' + _escApp(statusLbl) + '</span>'
        + '</div>'
        + '<div class="co-app-card-foot">'
        +   '<button type="button" class="co-app-accept-btn co-app-act' + (isAccepted ? ' co-app-qact--on' : '') + '" data-app-id="' + appId + '" data-cur-status="' + _escApp(statusKey) + '">قبول مبدئي</button>'
        +   '<button type="button" class="co-app-reject-btn co-app-act' + (isRejected ? ' co-app-qact--on' : '') + '" data-app-id="' + appId + '" data-cur-status="' + _escApp(statusKey) + '">رفض</button>'
        +   (a.tw_id
              ? '<a class="co-app-view-btn co-app-act" href="/u/' + _escApp(a.tw_id) + '" target="_blank" rel="noopener">عرض الملف الكامل</a>'
              : '')
        +   '<button type="button" class="co-app-save-btn co-app-act' + (isSaved ? ' saved' : '') + '" data-uid="' + parseInt(a.user_id, 10) + '"' + (isSaved ? ' disabled' : '') + '>'
        +     (isSaved ? 'تم الحفظ ✓' : '+ حفظ المرشح')
        +   '</button>'
        + '</div>'
        + '</div>';
    });
    list.innerHTML = html;
    _wireApplicantCards(list);
  }

  function _wireApplicantCards(list) {
    if (_cardListenerBound) return;
    _cardListenerBound = true;
    list.addEventListener('click', function (e) {
      var trigger = e.target.closest('.co-ast-trigger');
      if (trigger) { _openAstFloat(trigger); return; }
      var acceptBtn = e.target.closest('.co-app-accept-btn');
      if (acceptBtn && !acceptBtn.disabled) { _onQuickStatus(acceptBtn, 'accepted'); return; }
      var rejectBtn = e.target.closest('.co-app-reject-btn');
      if (rejectBtn && !rejectBtn.disabled) { _onQuickStatus(rejectBtn, 'rejected'); return; }
      var saveBtn = e.target.closest('.co-app-save-btn');
      if (saveBtn && !saveBtn.disabled) { _onSaveApplicant(saveBtn); return; }
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

  // ── Quick accept / reject actions ─────────────────────────────
  function _updateQuickBtnStates(card, status) {
    if (!card) return;
    var a = card.querySelector('.co-app-accept-btn');
    var r = card.querySelector('.co-app-reject-btn');
    if (a) a.classList.toggle('co-app-qact--on', status === 'accepted');
    if (r) r.classList.toggle('co-app-qact--on', status === 'rejected');
  }

  function _onQuickStatus(btn, newStatus) {
    var appId      = parseInt(btn.getAttribute('data-app-id'), 10);
    var prevStatus = btn.getAttribute('data-cur-status') || 'pending';
    if (newStatus === prevStatus) return;
    var card      = document.querySelector('#coAppList .co-app-card[data-app-id="' + appId + '"]');
    var badge     = card ? card.querySelector('.co-app-status')     : null;
    var acceptBtn = card ? card.querySelector('.co-app-accept-btn') : null;
    var rejectBtn = card ? card.querySelector('.co-app-reject-btn') : null;

    // Optimistic UI update
    if (badge) {
      badge.textContent = _APP_STATUS_LABEL[newStatus] || newStatus;
      badge.className   = 'co-app-status co-app-status--' + newStatus;
    }
    _updateQuickBtnStates(card, newStatus);
    if (acceptBtn) { acceptBtn.setAttribute('data-cur-status', newStatus); acceptBtn.disabled = true; }
    if (rejectBtn) { rejectBtn.setAttribute('data-cur-status', newStatus); rejectBtn.disabled = true; }

    var jwt = window._jwt ? _jwt() : '';
    fetch('/jobs/applications/' + appId + '/status', {
      method:  'PUT',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + jwt },
      body:    JSON.stringify({ status: newStatus })
    })
    .then(function (r) {
      if (!r.ok) { var e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
      return r.json();
    })
    .then(function () {
      if (window.showToast) showToast('تم تحديث حالة الطلب ✓');
    })
    .catch(function (err) {
      // Revert optimistic update on failure
      if (badge) {
        badge.textContent = _APP_STATUS_LABEL[prevStatus] || prevStatus;
        badge.className   = 'co-app-status co-app-status--' + prevStatus;
      }
      _updateQuickBtnStates(card, prevStatus);
      if (acceptBtn) acceptBtn.setAttribute('data-cur-status', prevStatus);
      if (rejectBtn) rejectBtn.setAttribute('data-cur-status', prevStatus);
      var msg = (err && (err.status === 401 || err.status === 403))
        ? 'انتهت الجلسة أو لا تملك صلاحية تعديل حالة الطلب'
        : 'تعذّر تحديث حالة الطلب، حاول مجدداً';
      if (window.showToast) showToast(msg, 'error');
    })
    .finally(function () {
      if (acceptBtn) acceptBtn.disabled = false;
      if (rejectBtn) rejectBtn.disabled = false;
    });
  }

  // ── Application status — floating dropdown ─────────────────────
  function _initAstFloat() {
    if (_astFloat) return;
    _astFloat = document.createElement('div');
    _astFloat.className    = 'co-ast-float';
    _astFloat.style.display = 'none';
    _astFloat.innerHTML =
      '<button class="co-ast-opt" data-val="pending">بانتظار المراجعة</button>'
      + '<button class="co-ast-opt" data-val="viewed">تمت المراجعة</button>'
      + '<button class="co-ast-opt" data-val="accepted">مقبول</button>'
      + '<button class="co-ast-opt" data-val="rejected">غير مناسب</button>';
    document.body.appendChild(_astFloat);

    _astFloat.addEventListener('click', function (e) {
      var opt = e.target.closest('.co-ast-opt');
      if (!opt || !_astFloatTrigger) { _closeAstFloat(); return; }
      var newStatus  = opt.getAttribute('data-val');
      var trigger    = _astFloatTrigger;
      var appId      = parseInt(trigger.getAttribute('data-app-id'), 10);
      var prevStatus = trigger.getAttribute('data-status');
      _closeAstFloat();
      if (newStatus === prevStatus) return;
      var card  = document.querySelector('#coAppList .co-app-card[data-app-id="' + appId + '"]');
      var badge = card ? card.querySelector('.co-app-status') : null;
      if (badge) {
        badge.textContent = _APP_STATUS_LABEL[newStatus] || newStatus;
        badge.className   = 'co-app-status co-app-status--' + newStatus;
      }
      trigger.setAttribute('data-status', newStatus);
      _updateAppStatus(appId, newStatus, badge, trigger, prevStatus);
    });

    document.addEventListener('click', function (e) {
      if (_astFloat && _astFloat.style.display !== 'none') {
        if (!_astFloat.contains(e.target) &&
            (!_astFloatTrigger || !_astFloatTrigger.contains(e.target))) {
          _closeAstFloat();
        }
      }
    });

    var appList = document.getElementById('coAppList');
    if (appList) { appList.addEventListener('scroll', _closeAstFloat, { passive: true }); }
  }

  function _openAstFloat(triggerBtn) {
    _initAstFloat();
    var isSame = _astFloatTrigger === triggerBtn && _astFloat.style.display !== 'none';
    _closeAstFloat();
    if (isSame) return;
    _astFloatTrigger        = triggerBtn;
    _astFloat.style.display = 'block';
    var rect  = triggerBtn.getBoundingClientRect();
    var menuW = _astFloat.offsetWidth  || 175;
    var menuH = _astFloat.offsetHeight || 148;
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

    // Mark current status option
    var currentStatus = triggerBtn.getAttribute('data-status') || '';
    _astFloat.querySelectorAll('.co-ast-opt').forEach(function (o) {
      o.classList.toggle('co-ast-current', o.getAttribute('data-val') === currentStatus);
    });
  }

  function _closeAstFloat() {
    if (_astFloat) _astFloat.style.display = 'none';
    _astFloatTrigger = null;
  }

  function _updateAppStatus(appId, newStatus, badge, triggerBtn, prevStatus) {
    var jwt = window._jwt ? _jwt() : '';
    fetch('/jobs/applications/' + appId + '/status', {
      method:  'PUT',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + jwt },
      body:    JSON.stringify({ status: newStatus })
    })
    .then(function (r) {
      if (!r.ok) { var e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
      return r.json();
    })
    .then(function () {
      if (window.showToast) showToast('تم تحديث الحالة ✓');
    })
    .catch(function (err) {
      if (badge) {
        badge.textContent = _APP_STATUS_LABEL[prevStatus] || prevStatus;
        badge.className   = 'co-app-status co-app-status--' + prevStatus;
      }
      if (triggerBtn) triggerBtn.setAttribute('data-status', prevStatus);
      var msg = (err && (err.status === 401 || err.status === 403))
        ? 'انتهت الجلسة أو لا تملك صلاحية تعديل حالة الطلب'
        : 'تعذّر تحديث حالة الطلب، حاول مجدداً';
      if (window.showToast) showToast(msg, 'error');
    });
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
  window.uploadLogo               = uploadLogo;
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
  // Build a custom dark picker (wrapClass + options array + current value)
  function _dpHTML(wrapClass, opts, current) {
    var curLabel = '';
    for (var i = 0; i < opts.length; i++) {
      if (opts[i].value === current) { curLabel = opts[i].label; break; }
    }
    var listHtml = opts.map(function (o) {
      return '<button class="co-dp-opt' + (o.value === current ? ' selected' : '') + '"'
           + ' data-value="' + _esc(o.value) + '" type="button">'
           + _checkSvg()
           + '<span>' + _esc(o.label) + '</span></button>';
    }).join('');
    return '<div class="co-dp-wrap ' + _esc(wrapClass) + '" data-selected="' + _esc(current) + '">'
      + '<button class="co-dp-btn" type="button">'
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
    var wrap = btn.closest('.co-dp-wrap');
    if (!wrap) return;
    var list = wrap.querySelector('.co-dp-list');
    if (!list) return;
    var wasOpen = list.style.display !== 'none';
    _closeAllDp();
    if (!wasOpen) list.style.display = 'block';
  }
  function _handleDpOptClick(opt) {
    var wrap = opt.closest('.co-dp-wrap');
    if (!wrap) return;
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
    }
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
      {value:'updated_desc', label:'الأحدث تعديلاً'},
      {value:'updated_asc',  label:'الأقدم تعديلاً'},
      {value:'created_desc', label:'الأحدث حفظاً'},
      {value:'created_asc',  label:'الأقدم حفظاً'},
      {value:'name_asc',     label:'الاسم أ-ي'},
      {value:'status_asc',   label:'الحالة'}
    ];
    return '<div id="coCandSavedShell">'
      + '<div class="co-cand-filter-bar">'
      + '<div id="coCandChips" class="co-cand-chips"></div>'
      + '<div class="co-cand-search-row">'
      + '<input id="coCandSearch" type="text" class="co-cand-search"'
      + ' placeholder="بحث عن مرشح…" dir="rtl" value="' + _esc(_savedSearch) + '">'
      + _dpHTML('co-cand-sort-dp', sortOpts, _savedSort)
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
    // Sort picker is handled via _onSavedClick delegation (_handleDpOptClick)
  }

  function _fetchSaved() {
    _savedOffset  = 0;
    _savedLoading = false;
    _body.innerHTML = _savedShellHTML();
    _wireSavedFilterBar();
    _loadSavedStats(null);
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
    if (_savedSearch) filters.q = _savedSearch;
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

  // Build status <option> list
  // Build custom job picker from companyState.jobs (active/paused jobs + legacy 'open')
  function _jobDpHTML(currentJobId) {
    var jobs = (window.companyState && companyState.jobs)
      ? companyState.jobs.filter(function (j) {
          var eff = j.effective_status || j.status;
          return eff === 'active' || eff === 'paused' || j.status === 'open';
        })
      : [];
    if (!jobs.length) return '';
    var opts = [{value: '', label: '— بدون وظيفة محددة —'}];
    jobs.forEach(function (j) {
      opts.push({value: String(j.id), label: j.title || ('وظيفة #' + j.id)});
    });
    return '<label class="co-cand-panel-label">ربط بوظيفة (اختياري)</label>'
         + _dpHTML('co-cand-dp-job', opts, currentJobId || '');
  }

  // Build a single saved card with embedded manage panel
  function _savedCardHTML(item) {
    var status = item.status || 'saved';
    var notes  = item.notes  || '';
    var jobId  = item.job_id  != null ? String(item.job_id) : '';
    var meta   = [item.profession, item.city, item.country].filter(Boolean).join(' · ');
    var date   = _fmtDate(item.created_at);
    var cid    = _esc(item.candidate_id);

    var html = '<div class="co-cand-saved-card"'
      + ' data-cid="' + cid + '"'
      + ' data-status="' + _esc(status) + '"'
      + ' data-notes="' + _esc(notes) + '"'
      + ' data-jobid="' + _esc(jobId) + '">';

    // ── Top row (avatar + info + actions) ────────────────────────
    html += '<div class="co-cand-top">';

    html += '<div class="co-cand-ava">'
      + (item.avatar_url
          ? '<img src="' + _esc(item.avatar_url) + '" alt="" loading="lazy">'
          : _avatarSvg)
      + '</div>';

    html += '<div class="co-cand-info">';
    html += '<div class="co-cand-name">' + _esc(item.full_name) + '</div>';
    if (meta) html += '<div class="co-cand-meta">' + _esc(meta) + '</div>';
    // Date + status badge
    html += '<div class="co-cand-row2">';
    if (date) html += '<span class="co-cand-date">حُفظ ' + _esc(date) + '</span>';
    html += '<span class="co-cand-status co-cand-status--' + _esc(_statusKey(status)) + '">'
          + _esc(_statusLabel(status)) + '</span>';
    html += '</div>';
    // Notes preview
    if (notes) html += '<div class="co-cand-notes-pre">' + _esc(notes) + '</div>';
    // Job reference
    if (jobId) html += '<div class="co-cand-job-ref">مرتبط بوظيفة #' + _esc(jobId) + '</div>';
    html += '</div>'; // .co-cand-info

    html += '<div class="co-cand-actions">';
    html += '<a class="co-cand-view-btn" href="/u/' + _esc(item.tw_id) + '" target="_blank" rel="noopener">فتح البروفايل</a>';
    html += '<button class="co-cand-manage-btn" data-cid="' + cid + '">إدارة</button>';
    html += '<button class="co-cand-remove-btn" data-cid="' + cid + '">إزالة</button>';
    html += '</div>'; // .co-cand-actions

    html += '</div>'; // .co-cand-top

    // ── Manage panel (hidden by default) ─────────────────────────
    var statusOpts = _STATUS_ORDER.map(function (s) { return {value: s, label: _STATUS_LABELS[s]}; });
    html += '<div class="co-cand-manage-panel">';
    html += '<label class="co-cand-panel-label">الحالة في Pipeline</label>';
    html += _dpHTML('co-cand-dp-status', statusOpts, status);
    html += '<label class="co-cand-panel-label">ملاحظات</label>';
    html += '<div class="co-cand-panel-ta-wrap">';
    html += '<textarea class="co-cand-panel-ta" maxlength="500"'
          + ' placeholder="أضف ملاحظة عن هذا المرشح…" dir="rtl">'
          + _esc(notes) + '</textarea>';
    html += '<span class="co-cand-panel-counter">' + notes.length + ' / 500</span>';
    html += '</div>';
    html += _jobDpHTML(jobId);
    html += '<div class="co-cand-panel-acts">';
    html += '<button class="co-cand-panel-save" data-cid="' + cid + '">حفظ التعديل</button>';
    html += '<button class="co-cand-panel-cancel" data-cid="' + cid + '">إلغاء</button>';
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
  }

  function _onSavedClick(e) {
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

    var manageBtn = e.target.closest('.co-cand-manage-btn');
    if (manageBtn) { _togglePanel(manageBtn); return; }

    var saveBtn = e.target.closest('.co-cand-panel-save');
    if (saveBtn) { _handlePanelSave(saveBtn); return; }

    var cancelBtn = e.target.closest('.co-cand-panel-cancel');
    if (cancelBtn) { _closePanelOf(cancelBtn); return; }
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

  function _handlePanelSave(btn) {
    var cid  = parseInt(btn.getAttribute('data-cid'));
    if (!cid) return;
    var card  = btn.closest('.co-cand-saved-card');
    var panel = card ? card.querySelector('.co-cand-manage-panel') : null;
    if (!panel) return;

    var dpStatus = panel.querySelector('.co-cand-dp-status');
    var ta       = panel.querySelector('.co-cand-panel-ta');
    var dpJob    = panel.querySelector('.co-cand-dp-job');

    var payload = {};
    if (dpStatus) payload.status = dpStatus.getAttribute('data-selected') || 'saved';
    if (ta)       payload.notes  = ta.value;
    if (dpJob) {
      var jval = dpJob.getAttribute('data-selected');
      payload.job_id = jval ? parseInt(jval) : null;
    }

    if (!window.updateSavedCandidate) return;
    btn.disabled    = true;
    btn.textContent = 'جارٍ الحفظ…';

    window.updateSavedCandidate(cid, payload)
      .then(function (res) {
        if (res && res.ok && res.data && res.data.item) {
          var updated = res.data.item;
          _applyCardUpdate(card, updated);
          _closePanelOf(btn);
          _loadSavedStats(null);
          // Hide card if it no longer matches the active filter
          var shouldHide = (_savedFilter && _savedFilter !== '_unlinked' && updated.status !== _savedFilter)
            || (_savedFilter === '_unlinked' && updated.job_id != null);
          if (shouldHide) {
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
          if (window.showToast) showToast('تم تحديث المرشح');
        } else {
          if (window.showToast) showToast('تعذّر الحفظ', 'error');
        }
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
    var newStatus = data.status  || 'saved';
    var newNotes  = data.notes   || '';
    var newJobId  = data.job_id  != null ? String(data.job_id) : '';

    // Update data attributes (source of truth for next panel open)
    card.setAttribute('data-status', newStatus);
    card.setAttribute('data-notes',  newNotes);
    card.setAttribute('data-jobid',  newJobId);

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

    // Update job reference
    var jobRef = card.querySelector('.co-cand-job-ref');
    if (newJobId) {
      if (jobRef) {
        jobRef.textContent = 'مرتبط بوظيفة #' + newJobId;
      } else {
        var info = card.querySelector('.co-cand-info');
        if (info) {
          var jd = document.createElement('div');
          jd.className   = 'co-cand-job-ref';
          jd.textContent = 'مرتبط بوظيفة #' + newJobId;
          info.appendChild(jd);
        }
      }
    } else if (jobRef) {
      jobRef.parentNode.removeChild(jobRef);
    }

    // Sync custom status picker display for next panel open
    var dpStatus = card.querySelector('.co-cand-dp-status');
    if (dpStatus) {
      dpStatus.setAttribute('data-selected', newStatus);
      var dpSVal = dpStatus.querySelector('.co-dp-val');
      if (dpSVal) dpSVal.textContent = _statusLabel(newStatus);
      dpStatus.querySelectorAll('.co-dp-opt').forEach(function (o) {
        o.classList.toggle('selected', o.getAttribute('data-value') === newStatus);
      });
    }

    // Sync custom job picker display
    var dpJob = card.querySelector('.co-cand-dp-job');
    if (dpJob) {
      dpJob.setAttribute('data-selected', newJobId);
      var dpJVal = dpJob.querySelector('.co-dp-val');
      if (dpJVal) dpJVal.textContent = newJobId ? ('وظيفة #' + newJobId) : '— بدون وظيفة محددة —';
      dpJob.querySelectorAll('.co-dp-opt').forEach(function (o) {
        o.classList.toggle('selected', o.getAttribute('data-value') === newJobId);
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
              if (row) {
                row.style.transition = 'opacity .2s';
                row.style.opacity = '0';
                setTimeout(function () {
                  if (row.parentNode) row.parentNode.removeChild(row);
                  var list = _body.querySelector('#coCandSuggList');
                  if (list && !list.querySelector('.co-cand-item')) {
                    _body.innerHTML = _suggEmptyHTML();
                  }
                }, 220);
              }
              if (window.showToast) showToast('تم حفظ المرشح');
            } else {
              btn.disabled = false;
              btn.textContent = 'حفظ كمرشح';
              if (window.showToast) showToast('تعذّر الحفظ', 'error');
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
}());
