// static/shared/tw-options-data.js
// Single source of truth for all repeated dropdown data across the platform.
// Namespace: window.TW
// Country/city VALUES are Arabic names — never ISO codes — matching DB contract.
// Do NOT duplicate this data inside page-specific files.

(function () {
  'use strict';

  window.TW = window.TW || {};

  // ── Arab countries (Arabic name = stored value in DB) ─────────
  TW.COUNTRIES = [
    'الأردن','السعودية','الإمارات','الكويت','قطر','البحرين','عُمان',
    'مصر','العراق','سوريا','لبنان','فلسطين','اليمن','ليبيا','تونس','الجزائر','المغرب','السودان'
  ];

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

  // ── Fill countries into a <select> (idempotent) ───────────────
  TW.fillCountries = function (selEl, placeholder) {
    if (!selEl || selEl.options.length > 1) return;
    TW.fillSelect(selEl, TW.COUNTRIES, placeholder || '— اختر الدولة —');
  };

  // ── Fill cities for a country (clears previous options) ───────
  TW.fillCities = function (selEl, country, selectedCity) {
    if (!selEl) return;
    selEl.innerHTML = '<option value="">— اختر المدينة —</option>';
    (TW.CITIES[country] || []).forEach(function (c) {
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
