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

  // ── Experience levels with integer DB values ───────────────────
  // Used by job post modal (j-exp select) and job-detail display mapping.
  // Values match experience_years INTEGER column: 0=none, 1=<1yr, 2=1-2yr, 3=3-5yr, 6=>5yr
  TW.EXP_LEVELS = [
    {value: 0, label: 'بدون خبرة'},
    {value: 1, label: 'أقل من سنة'},
    {value: 2, label: '1-2 سنة'},
    {value: 3, label: '3-5 سنوات'},
    {value: 6, label: 'أكثر من 5 سنوات'},
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

  // ── Skill catalog — FALLBACK ONLY ────────────────────────────────
  // الـ source الرسمي هو GET /skills/catalog (يُحمَّل من DB).
  // هذه القائمة تُستخدم فقط عند فشل التحميل من API أو قبل اكتمال PR 2.
  // لا تضف مهارات هنا — أضفها في جدول skill_catalog عبر auth.py seed.
  TW.SKILL_CATALOG = [
    // tech
    {slug:'python',      name_ar:'Python',         icon:'code',            group:'tech'},
    {slug:'javascript',  name_ar:'JavaScript',     icon:'code',            group:'tech'},
    {slug:'typescript',  name_ar:'TypeScript',     icon:'code',            group:'tech'},
    {slug:'java',        name_ar:'Java',            icon:'coffee',          group:'tech'},
    {slug:'csharp',      name_ar:'C#',              icon:'code',            group:'tech'},
    {slug:'cpp',         name_ar:'C++',             icon:'cpu',             group:'tech'},
    {slug:'php',         name_ar:'PHP',             icon:'code',            group:'tech'},
    {slug:'go',          name_ar:'Go',              icon:'zap',             group:'tech'},
    {slug:'ruby',        name_ar:'Ruby',            icon:'gem',             group:'tech'},
    {slug:'swift',       name_ar:'Swift',           icon:'zap',             group:'tech'},
    {slug:'kotlin',      name_ar:'Kotlin',          icon:'code',            group:'tech'},
    {slug:'rust',        name_ar:'Rust',            icon:'shield',          group:'tech'},
    {slug:'react',       name_ar:'React',           icon:'atom',            group:'tech'},
    {slug:'vue',         name_ar:'Vue.js',          icon:'layers',          group:'tech'},
    {slug:'angular',     name_ar:'Angular',         icon:'layers',          group:'tech'},
    {slug:'nextjs',      name_ar:'Next.js',         icon:'triangle',        group:'tech'},
    {slug:'nodejs',      name_ar:'Node.js',         icon:'server',          group:'tech'},
    {slug:'django',      name_ar:'Django',          icon:'server',          group:'tech'},
    {slug:'fastapi',     name_ar:'FastAPI',         icon:'zap',             group:'tech'},
    {slug:'spring',      name_ar:'Spring Boot',     icon:'server',          group:'tech'},
    {slug:'laravel',     name_ar:'Laravel',         icon:'server',          group:'tech'},
    {slug:'react_native',name_ar:'React Native',   icon:'smartphone',      group:'tech'},
    {slug:'flutter',     name_ar:'Flutter',         icon:'smartphone',      group:'tech'},
    {slug:'android',     name_ar:'Android',         icon:'smartphone',      group:'tech'},
    {slug:'ios',         name_ar:'iOS',             icon:'smartphone',      group:'tech'},
    {slug:'postgresql',  name_ar:'PostgreSQL',      icon:'database',        group:'tech'},
    {slug:'mysql',       name_ar:'MySQL',           icon:'database',        group:'tech'},
    {slug:'mongodb',     name_ar:'MongoDB',         icon:'database',        group:'tech'},
    {slug:'redis',       name_ar:'Redis',           icon:'database',        group:'tech'},
    {slug:'aws',         name_ar:'AWS',             icon:'cloud',           group:'tech'},
    {slug:'gcp',         name_ar:'Google Cloud',   icon:'cloud',           group:'tech'},
    {slug:'azure',       name_ar:'Microsoft Azure', icon:'cloud',           group:'tech'},
    {slug:'docker',      name_ar:'Docker',          icon:'package',         group:'tech'},
    {slug:'kubernetes',  name_ar:'Kubernetes',      icon:'layers',          group:'tech'},
    {slug:'git',         name_ar:'Git',             icon:'git-branch',      group:'tech'},
    {slug:'linux',       name_ar:'Linux',           icon:'terminal',        group:'tech'},
    {slug:'networking',  name_ar:'شبكات',           icon:'network',         group:'tech'},
    {slug:'ml',          name_ar:'تعلم الآلة',      icon:'brain',           group:'tech'},
    {slug:'data_analysis',name_ar:'تحليل البيانات', icon:'bar-chart-2',     group:'tech'},
    // security
    {slug:'cybersecurity',name_ar:'أمن المعلومات',  icon:'shield',          group:'security'},
    {slug:'penetration_testing',name_ar:'اختبار الاختراق',icon:'shield-off',group:'security'},
    {slug:'network_security',name_ar:'أمن الشبكات', icon:'shield',          group:'security'},
    // design
    {slug:'figma',       name_ar:'Figma',           icon:'figma',           group:'design'},
    {slug:'ui_design',   name_ar:'تصميم UI',        icon:'layout',          group:'design'},
    {slug:'ux_design',   name_ar:'تصميم UX',        icon:'users',           group:'design'},
    {slug:'photoshop',   name_ar:'Photoshop',       icon:'image',           group:'design'},
    {slug:'illustrator', name_ar:'Illustrator',     icon:'pen-tool',        group:'design'},
    {slug:'after_effects',name_ar:'After Effects',  icon:'film',            group:'design'},
    {slug:'video_editing',name_ar:'مونتاج الفيديو', icon:'video',           group:'design'},
    // management
    {slug:'project_management',name_ar:'إدارة المشاريع',icon:'briefcase',   group:'management'},
    {slug:'scrum',       name_ar:'Scrum / Agile',   icon:'refresh-cw',      group:'management'},
    {slug:'leadership',  name_ar:'القيادة',          icon:'users',           group:'management'},
    {slug:'communication',name_ar:'التواصل',         icon:'message-circle',  group:'management'},
    {slug:'problem_solving',name_ar:'حل المشكلات',  icon:'zap',             group:'management'},
    {slug:'teamwork',    name_ar:'العمل الجماعي',   icon:'users',           group:'management'},
    {slug:'time_management',name_ar:'إدارة الوقت',  icon:'clock',           group:'management'},
    {slug:'negotiation', name_ar:'التفاوض',          icon:'handshake',       group:'management'},
    // marketing
    {slug:'digital_marketing',name_ar:'التسويق الرقمي',icon:'trending-up',  group:'marketing'},
    {slug:'social_media',name_ar:'وسائل التواصل',   icon:'share-2',         group:'marketing'},
    {slug:'seo',         name_ar:'SEO',             icon:'search',          group:'marketing'},
    {slug:'content_writing',name_ar:'كتابة المحتوى',icon:'edit-3',          group:'marketing'},
    {slug:'sales',       name_ar:'المبيعات',         icon:'trending-up',     group:'marketing'},
    {slug:'crm',         name_ar:'CRM',             icon:'users',           group:'marketing'},
    // finance
    {slug:'accounting',  name_ar:'المحاسبة',         icon:'calculator',      group:'finance'},
    {slug:'financial_analysis',name_ar:'التحليل المالي',icon:'bar-chart-2',  group:'finance'},
    {slug:'excel',       name_ar:'Excel',           icon:'table',           group:'finance'},
    {slug:'quickbooks',  name_ar:'QuickBooks',      icon:'book',            group:'finance'},
    {slug:'auditing',    name_ar:'التدقيق المالي',  icon:'check-square',    group:'finance'},
    {slug:'tax',         name_ar:'الضرائب',          icon:'file-text',       group:'finance'},
    // hr
    {slug:'recruitment', name_ar:'التوظيف',          icon:'user-plus',       group:'hr'},
    {slug:'hr_management',name_ar:'إدارة الموارد البشرية',icon:'users',      group:'hr'},
    {slug:'training',    name_ar:'التدريب',          icon:'book-open',       group:'hr'},
    {slug:'payroll',     name_ar:'الرواتب',          icon:'dollar-sign',     group:'hr'},
    // education
    {slug:'teaching',    name_ar:'التدريس',          icon:'book-open',       group:'education'},
    {slug:'curriculum_design',name_ar:'تصميم المناهج',icon:'layout',        group:'education'},
    {slug:'e_learning',  name_ar:'التعليم الإلكتروني',icon:'monitor',        group:'education'},
    // engineering
    {slug:'autocad',     name_ar:'AutoCAD',         icon:'pen-tool',        group:'engineering'},
    {slug:'civil_engineering',name_ar:'الهندسة المدنية',icon:'building',    group:'engineering'},
    {slug:'electrical_engineering',name_ar:'الهندسة الكهربائية',icon:'zap', group:'engineering'},
    {slug:'mechanical_engineering',name_ar:'الهندسة الميكانيكية',icon:'settings',group:'engineering'},
    // health
    {slug:'patient_care',name_ar:'رعاية المرضى',   icon:'heart',           group:'health'},
    {slug:'first_aid',   name_ar:'الإسعافات الأولية',icon:'activity',       group:'health'},
    {slug:'pharmacology',name_ar:'الصيدلة',         icon:'pill',            group:'health'},
    // trades
    {slug:'plumbing',    name_ar:'السباكة',          icon:'tool',            group:'trades'},
    {slug:'electrical_work',name_ar:'الكهرباء',     icon:'zap',             group:'trades'},
    {slug:'carpentry',   name_ar:'النجارة',          icon:'tool',            group:'trades'},
    {slug:'welding',     name_ar:'اللحام',           icon:'tool',            group:'trades'},
    // hospitality
    {slug:'cooking',     name_ar:'الطبخ',            icon:'utensils',        group:'hospitality'},
    {slug:'customer_service',name_ar:'خدمة العملاء', icon:'headphones',      group:'customer_service'},
    // logistics
    {slug:'logistics',   name_ar:'اللوجستيات',       icon:'truck',           group:'logistics'},
    {slug:'supply_chain',name_ar:'سلسلة التوريد',   icon:'package',         group:'logistics'},
    {slug:'warehousing', name_ar:'المستودعات',       icon:'archive',         group:'logistics'},
    // languages
    {slug:'arabic',      name_ar:'اللغة العربية',    icon:'type',            group:'languages'},
    {slug:'english',     name_ar:'اللغة الإنجليزية', icon:'type',            group:'languages'},
    {slug:'french',      name_ar:'اللغة الفرنسية',  icon:'type',            group:'languages'},
    {slug:'german',      name_ar:'اللغة الألمانية',  icon:'type',            group:'languages'},
    {slug:'spanish',     name_ar:'اللغة الإسبانية',  icon:'type',            group:'languages'},
    {slug:'chinese',     name_ar:'اللغة الصينية',   icon:'type',            group:'languages'},
  ];

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
