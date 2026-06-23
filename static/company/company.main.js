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
  var _menuOpen = false;
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

  // ── Country / city data ────────────────────────────────────────
  var _CO_COUNTRIES = [
    'الأردن','السعودية','الإمارات','الكويت','قطر','البحرين','عُمان',
    'مصر','العراق','سوريا','لبنان','فلسطين','اليمن','ليبيا','تونس','الجزائر','المغرب','السودان'
  ];
  var _CO_CITIES = {
    'الأردن':   ['عمان','إربد','الزرقاء','العقبة','السلط','مادبا','الكرك','معان','جرش','عجلون','الطفيلة'],
    'السعودية': ['الرياض','جدة','مكة المكرمة','المدينة المنورة','الدمام','الخبر','الطائف','أبها','تبوك','القطيف','بريدة'],
    'الإمارات': ['دبي','أبوظبي','الشارقة','عجمان','رأس الخيمة','الفجيرة','أم القيوين','العين'],
    'الكويت':   ['مدينة الكويت','حولي','الفروانية','الأحمدي','الجهراء','مبارك الكبير'],
    'قطر':      ['الدوحة','الريان','الوكرة','أم صلال','الخور','الشمال'],
    'البحرين':  ['المنامة','المحرق','الرفاع','مدينة عيسى','مدينة حمد'],
    'عُمان':    ['مسقط','صلالة','نزوى','صحار','السيب','مطرح','البريمي'],
    'مصر':      ['القاهرة','الإسكندرية','الجيزة','شرم الشيخ','الأقصر','أسوان','طنطا','المنصورة','الفيوم','بورسعيد'],
    'العراق':   ['بغداد','البصرة','الموصل','أربيل','كربلاء','النجف','السليمانية','كركوك'],
    'سوريا':    ['دمشق','حلب','حمص','اللاذقية','حماة','دير الزور','الرقة','درعا'],
    'لبنان':    ['بيروت','طرابلس','صيدا','صور','جونية','زحلة'],
    'فلسطين':   ['رام الله','القدس','غزة','نابلس','الخليل','جنين','أريحا','بيت لحم'],
    'اليمن':    ['صنعاء','عدن','تعز','الحديدة','إب','ذمار','مأرب'],
    'ليبيا':    ['طرابلس','بنغازي','مصراتة','الزاوية','البيضاء','سبها'],
    'تونس':     ['تونس','صفاقس','سوسة','بنزرت','قابس','القيروان'],
    'الجزائر':  ['الجزائر','وهران','قسنطينة','عنابة','سطيف','تلمسان'],
    'المغرب':   ['الرباط','الدار البيضاء','فاس','مراكش','مكناس','أكادير','طنجة'],
    'السودان':  ['الخرطوم','أم درمان','بورتسودان','كسلا','الأبيض']
  };

  // ── Country/city helpers (shared between main form and branch rows) ────────
  function _fillCountrySel(sel) {
    if (!sel || sel.options.length > 1) return;
    _CO_COUNTRIES.forEach(function (c) {
      var opt = document.createElement('option');
      opt.value = c; opt.textContent = c;
      sel.appendChild(opt);
    });
  }

  function _fillCitySel(sel, country, selectedCity) {
    if (!sel) return;
    sel.innerHTML = '<option value="">— اختر المدينة —</option>';
    (_CO_CITIES[country] || []).forEach(function (c) {
      var opt = document.createElement('option');
      opt.value = c; opt.textContent = c;
      if (c === selectedCity) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  function _coPopulateCountries() { _fillCountrySel(document.getElementById('e-country')); }

  function _coLoadCities(country, selectedCity) {
    _fillCitySel(document.getElementById('e-city-sel'), country, selectedCity);
  }

  // ── Founded year dropdown ──────────────────────────────────────
  function _populateFoundedYears() {
    var sel = document.getElementById('e-founded');
    if (!sel || sel.options.length > 1) return;
    var curYear = new Date().getFullYear();
    for (var y = curYear; y >= 1900; y--) {
      var opt = document.createElement('option');
      opt.value = String(y); opt.textContent = String(y);
      sel.appendChild(opt);
    }
  }

  // ── Branches (UI-only — no DB save until company_branches table is added) ──
  function _makeMf(labelText, child, extraClass) {
    var mf = document.createElement('div');
    mf.className = 'mf' + (extraClass ? ' ' + extraClass : '');
    var lbl = document.createElement('label');
    lbl.textContent = labelText;
    mf.appendChild(lbl);
    mf.appendChild(child);
    return mf;
  }

  function _addBranchRow() {
    var list = document.getElementById('branchesList');
    if (!list) return;

    var idx   = list.children.length + 1;
    var row   = document.createElement('div');
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

    // Fields grid
    var fields = document.createElement('div');
    fields.className = 'branch-fields';

    // Country select
    var selCountry = document.createElement('select');
    selCountry.className = 'ep-select';
    selCountry.innerHTML = '<option value="">— الدولة —</option>';
    _fillCountrySel(selCountry);

    // City select (loaded on country change)
    var selCity = document.createElement('select');
    selCity.className = 'ep-select';
    selCity.innerHTML = '<option value="">— المدينة —</option>';
    selCountry.addEventListener('change', function () { _fillCitySel(selCity, this.value, ''); });

    // District input (no official source — input temporary)
    var inpDistrict = document.createElement('input');
    inpDistrict.type        = 'text';
    inpDistrict.placeholder = 'مثال: حي العليا، شارع...';

    fields.appendChild(_makeMf('الدولة',                     selCountry));
    fields.appendChild(_makeMf('المحافظة / المدينة',         selCity));
    fields.appendChild(_makeMf('المنطقة / الحي (اختياري)',   inpDistrict, 'branch-field-full'));

    row.appendChild(hdr);
    row.appendChild(fields);
    list.appendChild(row);
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
    setVal('e-type',     c.industry || c.company_type || '');
    setVal('e-size',     c.company_size || '');
    setVal('e-district', p.location || '');

    // Founded year dropdown
    _populateFoundedYears();
    setVal('e-founded', c.founded_year ? String(c.founded_year) : '');

    // Country & city dropdowns
    _coPopulateCountries();
    var savedCountry = p.country || '';
    setVal('e-country', savedCountry);
    _coLoadCities(savedCountry, p.city || '');

    // Clear branches list (UI-only state, no persistence)
    var bList = document.getElementById('branchesList');
    if (bList) bList.innerHTML = '';

    var ov = document.getElementById('editOverlay');
    if (ov) ov.classList.add('show');
    if (window.history) history.pushState({ modal: 'edit' }, '', location.href);
  }
  function closeEdit(e) {
    var el = document.getElementById('editOverlay');
    if (!e || e.target === el) el && el.classList.remove('show');
  }
  function _parseOk(r) {
    if (!r.ok) return r.json().then(function (d) { throw new Error(d.detail || ('HTTP ' + r.status)); });
    return r.json();
  }

  function saveEdit() {
    if (!window.companyState || !companyState.permissions.can_edit) return;
    var val  = function (id) { return (document.getElementById(id) || {}).value || ''; };
    var name = val('e-name').trim();
    if (!name) { if (window.showToast) showToast('أدخل اسم الشركة', 'error'); return; }
    var coType = val('e-type');
    if (!coType) { if (window.showToast) showToast('يجب تحديد تصنيف الجهة', 'error'); return; }
    var coId = (companyState.profile || {}).id;
    var jwt  = _jwt();
    var hdrs = { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + jwt };
    var ov   = document.getElementById('editOverlay');
    if (ov) ov.classList.remove('show');

    // ── 1. Update base profile (profiles table) ──────────────────
    var p1 = fetch('/profile/' + coId, {
      method: 'PUT', headers: hdrs,
      body: JSON.stringify({
        full_name: name,
        bio:       val('e-desc'),
        country:   val('e-country'),
        city:      val('e-city-sel'),
        location:  val('e-district'),
      }),
    }).then(_parseOk);

    // ── 2. Update company_profiles table ─────────────────────────
    var founderVal = parseInt(val('e-founded'), 10);
    var coPayload  = { industry: coType, company_type: coType };
    if (!isNaN(founderVal) && founderVal > 1800) coPayload.founded_year = founderVal;
    if (val('e-size')) coPayload.company_size = val('e-size');

    var p2 = fetch('/company/profile/' + coId, {
      method: 'PUT', headers: hdrs,
      body: JSON.stringify(coPayload),
    }).then(_parseOk);

    Promise.all([p1, p2])
      .then(function () {
        if (window.showToast) showToast('تم الحفظ ✓');
        if (window.loadData) loadData();
      })
      .catch(function (err) {
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

  // ── Logo photo (same local-preview pattern as uploadCover) ─────
  function uploadLogo(input) {
    var file = input.files && input.files[0];
    input.value = '';
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function (e) {
      var logoEl = document.getElementById('coLogo');
      if (!logoEl) return;
      logoEl.innerHTML = '';
      var img = document.createElement('img');
      img.src       = e.target.result;
      img.className = 'co-logo-img';
      img.alt       = (window.companyState && companyState.profile && companyState.profile.full_name) || '';
      logoEl.appendChild(img);
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
  window.switchTab         = switchTab;
  window.doLogout          = doLogout;
  window.toggleMenu        = toggleMenu;
  window.toggleFollow      = toggleFollow;
  window.openContact       = openContact;
  window.closeContact      = closeContact;
  window.sendMsg           = sendMsg;
  window.openEditModal     = openEditModal;
  window.closeEdit         = closeEdit;
  window.saveEdit          = saveEdit;
  window.setCover          = setCover;
  window.uploadCover       = uploadCover;
  window.uploadLogo        = uploadLogo;
  window.openReportModal   = openReportModal;
  window.closeReportModal  = closeReportModal;
  window.submitReport      = submitReport;
  window.initCompanyProfile = initCompanyProfile;

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
    if (addBranchBtn) addBranchBtn.addEventListener('click', function () { _addBranchRow(''); });

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
