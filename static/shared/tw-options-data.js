// static/shared/tw-options-data.js
// Single source of truth for all repeated dropdown data across the platform.
// Namespace: window.TW
// Country/city VALUES for companies are Arabic names — never ISO codes — matching DB contract.
// For Profile V2 (employees), country VALUES are ISO-2 codes (JO, SA, …) — legacy DB contract.
// Do NOT duplicate this data inside page-specific files.

(function () {
  'use strict';

  window.TW = window.TW || {};

  // ── Country map — single source for code, Arabic name, flag ──
  // Ordered to match TW.COUNTRIES (backward compat)
  TW.COUNTRY_MAP = [
    { code:'JO', name_ar:'الأردن',    flagPath:'/static/shared/flags/jo.svg' },
    { code:'SA', name_ar:'السعودية',  flagPath:'/static/shared/flags/sa.svg' },
    { code:'AE', name_ar:'الإمارات', flagPath:'/static/shared/flags/ae.svg' },
    { code:'KW', name_ar:'الكويت',   flagPath:'/static/shared/flags/kw.svg' },
    { code:'QA', name_ar:'قطر',      flagPath:'/static/shared/flags/qa.svg' },
    { code:'BH', name_ar:'البحرين',  flagPath:'/static/shared/flags/bh.svg' },
    { code:'OM', name_ar:'عُمان',    flagPath:'/static/shared/flags/om.svg' },
    { code:'EG', name_ar:'مصر',      flagPath:'/static/shared/flags/eg.svg' },
    { code:'IQ', name_ar:'العراق',   flagPath:'/static/shared/flags/iq.svg' },
    { code:'SY', name_ar:'سوريا',    flagPath:'/static/shared/flags/sy.svg' },
    { code:'LB', name_ar:'لبنان',    flagPath:'/static/shared/flags/lb.svg' },
    { code:'PS', name_ar:'فلسطين',   flagPath:'/static/shared/flags/ps.svg' },
    { code:'YE', name_ar:'اليمن',    flagPath:'/static/shared/flags/ye.svg' },
    { code:'LY', name_ar:'ليبيا',    flagPath:'/static/shared/flags/ly.svg' },
    { code:'TN', name_ar:'تونس',     flagPath:'/static/shared/flags/tn.svg' },
    { code:'DZ', name_ar:'الجزائر',  flagPath:'/static/shared/flags/dz.svg' },
    { code:'MA', name_ar:'المغرب',   flagPath:'/static/shared/flags/ma.svg' },
    { code:'SD', name_ar:'السودان',  flagPath:'/static/shared/flags/sd.svg' }
  ];

  // ── Internal lookup maps (built once) ───────────────────────
  var _byCode   = {};
  var _byNameAr = {};
  TW.COUNTRY_MAP.forEach(function (e) {
    _byCode[e.code.toUpperCase()] = e;
    _byNameAr[e.name_ar]          = e;
  });

  // ── Arab countries — derived from COUNTRY_MAP for backward compat ──
  TW.COUNTRIES = TW.COUNTRY_MAP.map(function (e) { return e.name_ar; });

  // ── Lookup by ISO code OR Arabic name ────────────────────────
  TW.countryEntry = function (value) {
    if (!value) return null;
    var v = String(value).trim();
    return _byCode[v.toUpperCase()] || _byNameAr[v] || null;
  };

  // ── Return Arabic display name (accepts ISO or Arabic) ───────
  TW.countryName = function (value) {
    var e = TW.countryEntry(value);
    return e ? e.name_ar : (value || '');
  };

  // ── Return ISO-2 code (accepts ISO or Arabic) ─────────────
  TW.countryCode = function (value) {
    var e = TW.countryEntry(value);
    return e ? e.code : null;
  };

  // ── Build circular flag <img> element (returns null if unknown) ─
  TW.countryFlagEl = function (value, extraClass) {
    var e = TW.countryEntry(value);
    if (!e) return null;
    var img = document.createElement('img');
    img.src       = e.flagPath;
    img.alt       = e.name_ar;
    img.className = 'tw-flag' + (extraClass ? ' ' + extraClass : '');
    img.width     = 18;
    img.height    = 18;
    return img;
  };

  // ── Compare two country values — handles mixed ISO / Arabic ──
  // TW.sameCountry('JO', 'الأردن') → true
  TW.sameCountry = function (a, b) {
    if (!a || !b) return false;
    if (a === b) return true;
    var ea = TW.countryEntry(a);
    var eb = TW.countryEntry(b);
    if (!ea || !eb) return false;
    return ea.code === eb.code;
  };

  // ── Cities keyed by Arabic country name ───────────────────────
  TW.CITIES = {
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

  // ── Company types ─────────────────────────────────────────────
  TW.COMPANY_TYPES = [
    'شركة خاصة','مصنع','مؤسسة تجارية','بنك / مؤسسة مالية',
    'جامعة / كلية','مدرسة','معهد','مركز تدريب','مستشفى','مطعم',
    'جهة حكومية','أخرى'
  ];

  // ── Company sizes ─────────────────────────────────────────────
  TW.COMPANY_SIZES = [
    '1-10 موظفين','11-50 موظف','51-200 موظف','201-500 موظف','+500 موظف'
  ];

  // ── Job categories ────────────────────────────────────────────
  TW.JOB_CATEGORIES = [
    'تقنية وبرمجة','محاسبة ومالية','مبيعات وتسويق',
    'مطاعم وضيافة','تعليم وتدريب','سائقون وتوصيل',
    'أمن وحماية','إداري ومكتبي','حرف ومهن',
    'طب وتمريض','هندسة','موارد بشرية','أخرى'
  ];

  // ── Job types (employment type) ────────────────────────────────
  TW.JOB_TYPES = [
    'دوام كامل','دوام جزئي','مؤقت','عقد','تدريب','حر / Freelance'
  ];

  // ── Work modes ─────────────────────────────────────────────────
  TW.JOB_WORK_MODES = [
    'في الموقع','عن بُعد','هجين'
  ];

  // ── Experience levels ──────────────────────────────────────────
  TW.EXPERIENCE_LEVELS = [
    'لا يشترط خبرة','أقل من سنة','1–3 سنوات','3–5 سنوات','أكثر من 5 سنوات'
  ];

  // ── DOM helper: fill a <select> from a string array ──────────
  TW.fillSelect = function (selEl, items, placeholder) {
    if (!selEl) return;
    selEl.innerHTML = '<option value="">' + (placeholder || '— اختر —') + '</option>';
    items.forEach(function (v) {
      var o = document.createElement('option');
      o.value = v; o.textContent = v;
      selEl.appendChild(o);
    });
  };

  // ── Fill countries into a <select> ────────────────────────────
  // opts = { valueMode: 'name_ar' | 'code', withFlags: boolean }
  // Backward compat: no opts → valueMode:'name_ar', withFlags:false
  TW.fillCountries = function (selEl, placeholder, opts) {
    if (!selEl) return;
    opts = opts || {};
    var valueMode = opts.valueMode || 'name_ar';
    var withFlags = !!opts.withFlags;
    var modeKey   = valueMode + ':' + (withFlags ? '1' : '0');

    // Idempotency: skip if already populated with same mode and options
    if (selEl.options.length > 1 && selEl.getAttribute('data-tw-mode') === modeKey && !opts.force) return;

    selEl.setAttribute('data-tw-mode', modeKey);
    selEl.innerHTML = '<option value="">' + (placeholder || '— اختر الدولة —') + '</option>';
    TW.COUNTRY_MAP.forEach(function (e) {
      var o = document.createElement('option');
      o.value       = valueMode === 'code' ? e.code : e.name_ar;
      o.textContent = e.name_ar;
      if (withFlags) o.setAttribute('data-img', e.flagPath);
      selEl.appendChild(o);
    });
  };

  // ── Fill cities for a country (clears previous options) ───────
  // Accepts both ISO code and Arabic name for the country parameter.
  TW.fillCities = function (selEl, country, selectedCity) {
    if (!selEl) return;
    selEl.innerHTML = '<option value="">— اختر المدينة —</option>';
    var name = TW.countryName(country) || country;
    (TW.CITIES[name] || []).forEach(function (c) {
      var o = document.createElement('option');
      o.value = c; o.textContent = c;
      if (c === selectedCity) o.selected = true;
      selEl.appendChild(o);
    });
  };

  // ── Fill founded-year dropdown (current year → 1900, idempotent) ─
  TW.fillFoundedYears = function (selEl) {
    if (!selEl || selEl.options.length > 1) return;
    var cur = new Date().getFullYear();
    for (var y = cur; y >= 1900; y--) {
      var o = document.createElement('option');
      o.value = String(y); o.textContent = String(y);
      selEl.appendChild(o);
    }
  };
}());
