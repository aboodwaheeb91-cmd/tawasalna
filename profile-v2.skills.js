// profile-v2.skills.js — Skills with Catalog Autocomplete (Phase 1)
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.utils.js

(function(){
  var overlay   = document.getElementById('skillOverlay');
  var saveBtn   = document.getElementById('skillSaveBtn');
  var cancelBtn = document.getElementById('skillCancelBtn');
  var closeBtn  = document.getElementById('skillClose');
  if(!overlay || !saveBtn) return;

  function f(id){ return document.getElementById(id); }
  function fv(id){ return ((f(id)||{}).value||'').trim(); }
  function sv(id,v){ var el=f(id); if(el) el.value=(v==null?'':v); }

  // ── Skill Catalog (Phase 1 — embedded, Phase 2 moves to DB) ──
  var CATALOG = [
    // Programming Languages
    {slug:'javascript',en:'JavaScript',ar:'جافا سكريبت',kw:'js جافاسكريبت web'},
    {slug:'python',en:'Python',ar:'بايثون',kw:'بايثون py'},
    {slug:'java',en:'Java',ar:'جافا',kw:'جافا oop'},
    {slug:'typescript',en:'TypeScript',ar:'تايب سكريبت',kw:'ts'},
    {slug:'cpp',en:'C++',ar:'سي بلس بلس',kw:'cpp سي بلس'},
    {slug:'csharp',en:'C#',ar:'سي شارب',kw:'dotnet سي شارب'},
    {slug:'php',en:'PHP',ar:'PHP',kw:'لارافيل'},
    {slug:'swift',en:'Swift',ar:'سويفت',kw:'ios apple'},
    {slug:'kotlin',en:'Kotlin',ar:'كوتلن',kw:'android'},
    {slug:'go',en:'Go',ar:'Go',kw:'golang'},
    {slug:'ruby',en:'Ruby',ar:'روبي',kw:'rails'},
    {slug:'r_lang',en:'R',ar:'R',kw:'r language احصاء statistics ستاتستك'},
    {slug:'dart',en:'Dart',ar:'دارت',kw:'flutter'},
    {slug:'scala',en:'Scala',ar:'سكالا',kw:''},
    {slug:'rust',en:'Rust',ar:'رست',kw:''},
    {slug:'matlab',en:'MATLAB',ar:'ماتلاب',kw:'simulation محاكاة'},
    {slug:'vba',en:'VBA',ar:'VBA',kw:'excel macro اكسل ماكرو'},
    // Web Frontend
    {slug:'html',en:'HTML',ar:'HTML',kw:'html5 markup'},
    {slug:'css',en:'CSS',ar:'CSS',kw:'css3 styling'},
    {slug:'react',en:'React',ar:'رياكت',kw:'reactjs'},
    {slug:'vuejs',en:'Vue.js',ar:'فيو',kw:'vue vuejs'},
    {slug:'angular',en:'Angular',ar:'أنغولار',kw:'angularjs'},
    {slug:'nextjs',en:'Next.js',ar:'نكست',kw:'nextjs'},
    {slug:'nuxtjs',en:'Nuxt.js',ar:'نكست فيو',kw:'nuxt'},
    {slug:'bootstrap',en:'Bootstrap',ar:'بوتستراب',kw:'css framework'},
    {slug:'tailwind',en:'Tailwind CSS',ar:'تيلويند',kw:'tailwindcss'},
    {slug:'jquery',en:'jQuery',ar:'jQuery',kw:'js library'},
    {slug:'svelte',en:'Svelte',ar:'سفيلت',kw:'svelte frontend'},
    // Backend Frameworks
    {slug:'nodejs',en:'Node.js',ar:'نود',kw:'nodejs node express'},
    {slug:'django',en:'Django',ar:'دجانغو',kw:'python framework'},
    {slug:'flask',en:'Flask',ar:'فلاسك',kw:'python flask'},
    {slug:'fastapi',en:'FastAPI',ar:'FastAPI',kw:'python api'},
    {slug:'laravel',en:'Laravel',ar:'لارافيل',kw:'php'},
    {slug:'springboot',en:'Spring Boot',ar:'سبرينغ',kw:'spring java framework'},
    {slug:'aspnet',en:'ASP.NET',ar:'ASP.NET',kw:'dotnet csharp'},
    {slug:'expressjs',en:'Express.js',ar:'إكسبريس',kw:'nodejs express'},
    // Mobile
    {slug:'react_native',en:'React Native',ar:'ريأكت نيتف',kw:'mobile cross platform'},
    {slug:'flutter',en:'Flutter',ar:'فلاتر',kw:'dart mobile'},
    {slug:'android_dev',en:'Android Development',ar:'تطوير أندرويد',kw:'android kotlin java mobile'},
    {slug:'ios_dev',en:'iOS Development',ar:'تطوير iOS',kw:'ios swift apple'},
    // Data / AI
    {slug:'machine_learning',en:'Machine Learning',ar:'تعلم الآلة',kw:'ml ai ذكاء اصطناعي'},
    {slug:'deep_learning',en:'Deep Learning',ar:'التعلم العميق',kw:'dl neural network شبكات عصبية'},
    {slug:'data_analysis',en:'Data Analysis',ar:'تحليل البيانات',kw:'data analyst تحليل بيانات'},
    {slug:'data_science',en:'Data Science',ar:'علم البيانات',kw:'datascience علم البيانات'},
    {slug:'tensorflow',en:'TensorFlow',ar:'تنسرفلو',kw:'google ai tensorflow'},
    {slug:'pytorch',en:'PyTorch',ar:'بايتورش',kw:'pytorch deep learning'},
    {slug:'pandas',en:'Pandas',ar:'باندا',kw:'python data pandas'},
    {slug:'numpy',en:'NumPy',ar:'نمباي',kw:'python math numpy'},
    {slug:'powerbi',en:'Power BI',ar:'باور بي آي',kw:'powerbi microsoft bi تحليل'},
    {slug:'tableau',en:'Tableau',ar:'تابلو',kw:'data visualization tableau'},
    {slug:'nlp',en:'NLP',ar:'معالجة اللغة الطبيعية',kw:'natural language processing nlp'},
    // Databases
    {slug:'sql',en:'SQL',ar:'إس كيو إل',kw:'قواعد بيانات database استعلامات'},
    {slug:'mysql',en:'MySQL',ar:'ماي إس كيو إل',kw:'mysql database'},
    {slug:'postgresql',en:'PostgreSQL',ar:'بوستغريس',kw:'postgres postgresql'},
    {slug:'mongodb',en:'MongoDB',ar:'مونغو',kw:'nosql mongodb'},
    {slug:'oracle_db',en:'Oracle Database',ar:'أوراكل',kw:'oracle plsql'},
    {slug:'redis',en:'Redis',ar:'ريديس',kw:'redis cache'},
    {slug:'firebase',en:'Firebase',ar:'فايربيز',kw:'firebase google'},
    {slug:'sqlite',en:'SQLite',ar:'إس كيو لايت',kw:'sqlite local'},
    {slug:'elasticsearch',en:'Elasticsearch',ar:'إلاستيك سيرش',kw:'elastic search'},
    // Cloud / DevOps
    {slug:'docker',en:'Docker',ar:'دوكر',kw:'docker containers'},
    {slug:'kubernetes',en:'Kubernetes',ar:'كوبيرنيتس',kw:'k8s orchestration'},
    {slug:'aws',en:'AWS',ar:'أمازون كلاود',kw:'amazon aws cloud'},
    {slug:'azure',en:'Microsoft Azure',ar:'أزور',kw:'azure microsoft cloud'},
    {slug:'gcp',en:'Google Cloud',ar:'جوجل كلاود',kw:'gcp google cloud'},
    {slug:'git',en:'Git',ar:'جيت',kw:'git github gitlab version control'},
    {slug:'linux',en:'Linux',ar:'لينكس',kw:'linux ubuntu bash terminal'},
    {slug:'cicd',en:'CI/CD',ar:'CI/CD',kw:'devops cicd jenkins github actions'},
    {slug:'terraform',en:'Terraform',ar:'تيرافورم',kw:'terraform iac infrastructure'},
    {slug:'nginx',en:'Nginx',ar:'إنجينكس',kw:'nginx web server'},
    // Design
    {slug:'photoshop',en:'Adobe Photoshop',ar:'فوتوشوب',kw:'photoshop ps تصميم'},
    {slug:'illustrator',en:'Adobe Illustrator',ar:'إليستريتور',kw:'illustrator ai vector'},
    {slug:'figma',en:'Figma',ar:'فيغما',kw:'figma ui prototype تصميم'},
    {slug:'xd',en:'Adobe XD',ar:'أدوبي XD',kw:'xd ux wireframe'},
    {slug:'premiere',en:'Adobe Premiere',ar:'بريمير',kw:'premiere video editing تحرير فيديو'},
    {slug:'aftereffects',en:'Adobe After Effects',ar:'أفتر إفيكتس',kw:'after effects motion animation'},
    {slug:'ui_design',en:'UI Design',ar:'تصميم الواجهات',kw:'ui user interface تصميم'},
    {slug:'ux_design',en:'UX Design',ar:'تجربة المستخدم',kw:'ux user experience usability'},
    {slug:'graphic_design',en:'Graphic Design',ar:'تصميم جرافيك',kw:'graphic جرافيك design'},
    {slug:'autocad',en:'AutoCAD',ar:'أوتوكاد',kw:'autocad cad هندسة'},
    {slug:'three_d',en:'3D Modeling',ar:'نمذجة ثلاثية الأبعاد',kw:'3d blender modeling'},
    // Office / Productivity
    {slug:'excel',en:'Microsoft Excel',ar:'إكسل',kw:'excel spreadsheet جداول بيانات'},
    {slug:'word',en:'Microsoft Word',ar:'وورد',kw:'word document وورد'},
    {slug:'powerpoint',en:'Microsoft PowerPoint',ar:'باوربوينت',kw:'powerpoint presentation عروض'},
    {slug:'access',en:'Microsoft Access',ar:'أكسس',kw:'access microsoft'},
    {slug:'ms_office',en:'Microsoft Office',ar:'مايكروسوفت أوفيس',kw:'office أوفيس'},
    {slug:'google_sheets',en:'Google Sheets',ar:'جوجل شيتس',kw:'sheets google docs'},
    {slug:'google_workspace',en:'Google Workspace',ar:'جوجل ورك سبيس',kw:'google drive gmail docs'},
    {slug:'data_entry',en:'Data Entry',ar:'إدخال البيانات',kw:'data entry إدخال بيانات typing'},
    // Management / Soft Skills
    {slug:'project_management',en:'Project Management',ar:'إدارة المشاريع',kw:'pm pmp إدارة مشاريع'},
    {slug:'agile',en:'Agile / Scrum',ar:'أجايل / سكرام',kw:'agile scrum sprint kanban'},
    {slug:'team_leadership',en:'Team Leadership',ar:'قيادة الفريق',kw:'leadership قيادة فريق'},
    {slug:'communication',en:'Communication Skills',ar:'مهارات التواصل',kw:'communication تواصل presentation'},
    {slug:'problem_solving',en:'Problem Solving',ar:'حل المشكلات',kw:'problem solving analytical تحليل'},
    {slug:'time_management',en:'Time Management',ar:'إدارة الوقت',kw:'time management productivity وقت'},
    {slug:'critical_thinking',en:'Critical Thinking',ar:'التفكير النقدي',kw:'critical thinking تفكير نقدي'},
    // Business / Marketing
    {slug:'accounting',en:'Accounting',ar:'محاسبة',kw:'accounting محاسبة ميزانية'},
    {slug:'financial_analysis',en:'Financial Analysis',ar:'تحليل مالي',kw:'finance financial مالي'},
    {slug:'marketing',en:'Marketing',ar:'تسويق',kw:'marketing digital تسويق رقمي'},
    {slug:'seo',en:'SEO',ar:'تحسين محركات البحث',kw:'seo search engine تحسين'},
    {slug:'social_media',en:'Social Media Marketing',ar:'تسويق التواصل الاجتماعي',kw:'social media instagram twitter تواصل'},
    {slug:'content_writing',en:'Content Writing',ar:'كتابة المحتوى',kw:'content copywriting كتابة محتوى'},
    {slug:'customer_service',en:'Customer Service',ar:'خدمة العملاء',kw:'customer service support خدمة عملاء'},
    {slug:'sales',en:'Sales',ar:'المبيعات',kw:'sales selling مبيعات'},
    {slug:'hr',en:'Human Resources',ar:'الموارد البشرية',kw:'hr human resources موارد بشرية'},
    // Network / Security
    {slug:'networking',en:'Networking',ar:'شبكات',kw:'network ccna tcp/ip شبكات'},
    {slug:'cybersecurity',en:'Cybersecurity',ar:'الأمن السيبراني',kw:'security cyber أمن سيبراني'},
    // Languages / Other
    {slug:'arabic_typing',en:'Arabic Typing',ar:'طباعة عربية',kw:'arabic typing طباعة عربية'},
    {slug:'translation',en:'Translation',ar:'ترجمة',kw:'translation ترجمة english arabic'},
    {slug:'technical_writing',en:'Technical Writing',ar:'الكتابة التقنية',kw:'technical writing documentation توثيق'},
  ];

  // Level color map — displayed as a badge separate from skill name
  var LEVEL_COLORS = {
    'مبتدئ': {color:'#9ca3af', bg:'rgba(156,163,175,.15)'},
    'متوسط': {color:'#60a5fa', bg:'rgba(96,165,250,.15)'},
    'جيد':   {color:'#a78bfa', bg:'rgba(167,139,250,.15)'},
    'متقدم': {color:'#00c896', bg:'rgba(0,200,150,.15)'},
    'محترف': {color:'#fbbf24', bg:'rgba(251,191,36,.15)'},
  };

  // Words that indicate user merged skill + level (caught in validation)
  var LEVEL_WORDS = ['مبتدئ','متوسط','جيد','متقدم','محترف','متخصص','خبير',
                     'beginner','intermediate','advanced','expert','junior','senior','mid-level'];

  // ── Catalog search (returns up to 8 matches) ──
  function _search(q){
    if(!q || q.length < 1) return [];
    var ql = q.toLowerCase();
    var results = [];
    for(var i=0; i<CATALOG.length; i++){
      var s = CATALOG[i];
      if(s.en.toLowerCase().indexOf(ql) !== -1
      || s.ar.indexOf(q) !== -1
      || s.slug.indexOf(ql) !== -1
      || s.kw.toLowerCase().indexOf(ql) !== -1){
        results.push(s);
        if(results.length >= 8) break;
      }
    }
    return results;
  }

  // ── Normalize: map input to canonical name_en if it matches catalog ──
  function _normalize(raw){
    var cleaned = raw.trim();
    var ql = cleaned.toLowerCase();
    for(var i=0; i<CATALOG.length; i++){
      var s = CATALOG[i];
      if(s.slug === ql || s.en.toLowerCase() === ql || s.ar === cleaned){
        return s.en;
      }
      var kws = s.kw.split(' ');
      for(var j=0; j<kws.length; j++){
        if(kws[j] && kws[j].toLowerCase() === ql) return s.en;
      }
    }
    return cleaned;
  }

  // ── Validation — returns error string or null ──
  function _validate(skill){
    if(!skill) return 'اسم المهارة مطلوب';
    if(skill.length < 2) return 'اسم المهارة قصير جداً (حرفان على الأقل)';
    if(typeof hasEmoji === 'function' && hasEmoji(skill)) return 'لا يسمح باستخدام الرموز التعبيرية';
    // Must contain at least one Arabic or Latin letter
    if(!/[a-zA-Z؀-ۿ]/.test(skill)) return 'اسم المهارة غير صالح — يجب أن يحتوي على حروف';
    // Detect merged "skill + level" pattern
    var sl = skill.toLowerCase();
    for(var i=0; i<LEVEL_WORDS.length; i++){
      if(sl.indexOf(LEVEL_WORDS[i]) !== -1){
        return 'اكتب اسم المهارة فقط — واختر المستوى من القائمة أدناه';
      }
    }
    return null;
  }

  // ── Case-insensitive duplicate check against current profile ──
  function _isDuplicate(skill){
    var sl = skill.toLowerCase();
    var existing = (window._scProfile && window._scProfile.skills) || [];
    for(var i=0; i<existing.length; i++){
      if((existing[i].skill || '').toLowerCase() === sl) return true;
    }
    return false;
  }

  // ── Autocomplete ──
  var _dropResults = [];
  var _activeIdx   = -1;

  function _getDrop(){ return f('skillDrop'); }

  function _showDrop(results){
    var drop = _getDrop();
    if(!drop) return;
    _dropResults = results;
    _activeIdx   = -1;
    if(!results.length){ _hideDrop(); return; }

    var html = '';
    for(var i=0; i<results.length; i++){
      var s = results[i];
      html += '<div class="sk-ac-item" data-idx="'+i+'">'
        + '<span class="sk-ac-en">'+esc(s.en)+'</span>'
        + (s.ar !== s.en ? '<span class="sk-ac-ar">'+esc(s.ar)+'</span>' : '')
        + '</div>';
    }
    drop.innerHTML = html;
    drop.style.display = 'block';

    var items = drop.querySelectorAll('.sk-ac-item');
    for(var j=0; j<items.length; j++){
      (function(item, res){
        item.onclick = function(){ _pickResult(res.en); };
      })(items[j], results[j]);
    }
  }

  function _hideDrop(){
    var drop = _getDrop();
    if(drop){ drop.style.display='none'; drop.innerHTML=''; }
    _dropResults = [];
    _activeIdx   = -1;
  }

  function _pickResult(name){
    var inp = f('skillName');
    if(inp) inp.value = name;
    _hideDrop();
    if(inp) inp.focus();
  }

  function _moveActive(dir){
    var drop = _getDrop();
    if(!drop || drop.style.display==='none' || !_dropResults.length) return;
    var items = drop.querySelectorAll('.sk-ac-item');
    if(!items.length) return;
    if(_activeIdx >= 0) items[_activeIdx].classList.remove('sk-ac-active');
    _activeIdx = (_activeIdx + dir + _dropResults.length) % _dropResults.length;
    items[_activeIdx].classList.add('sk-ac-active');
    items[_activeIdx].scrollIntoView({block:'nearest'});
  }

  function _selectActive(){
    if(_activeIdx < 0 || !_dropResults[_activeIdx]) return false;
    _pickResult(_dropResults[_activeIdx].en);
    return true;
  }

  function _initAC(){
    var inp = f('skillName');
    if(!inp) return;

    inp.addEventListener('input', function(){
      _showDrop(_search(inp.value));
    });

    inp.addEventListener('keydown', function(e){
      var drop = _getDrop();
      var open = drop && drop.style.display !== 'none';
      if(e.key === 'ArrowDown')  { e.preventDefault(); if(open) _moveActive(1);        }
      else if(e.key === 'ArrowUp')    { e.preventDefault(); if(open) _moveActive(-1);       }
      else if(e.key === 'Enter')      { if(open && _selectActive()) e.preventDefault();      }
      else if(e.key === 'Escape')     { _hideDrop();                                         }
    });

    inp.addEventListener('blur', function(){
      setTimeout(_hideDrop, 160);
    });
  }

  // ── Modal ──
  function openModal(){
    sv('skillName','');
    sv('skillLevel','');
    _hideDrop();
    overlay.classList.add('open');
    if(window._scPushHistory) window._scPushHistory('skill');
    setTimeout(function(){ var inp=f('skillName'); if(inp) inp.focus(); }, 120);
  }
  function closeModal(){
    _hideDrop();
    overlay.classList.remove('open');
    if(window._scHistoryReset) window._scHistoryReset();
  }

  if(closeBtn)  closeBtn.onclick  = closeModal;
  if(cancelBtn) cancelBtn.onclick = closeModal;
  overlay.addEventListener('click', function(e){ if(e.target===overlay) closeModal(); });

  _initAC();

  // ── Save ──
  saveBtn.onclick = function(){
    var raw   = fv('skillName');
    var skill = _normalize(raw);
    var level = fv('skillLevel') || null;

    var err = _validate(skill);
    if(err){ toast(err); return; }

    if(_isDuplicate(skill)){
      toast('هذه المهارة موجودة مسبقاً في ملفك الشخصي');
      return;
    }

    saveBtn.disabled    = true;
    saveBtn.textContent = 'جاري الحفظ…';

    addSkill(_scUserId, {skill:skill, level:level}).then(function(res){
      if(!res.ok){
        var _det = res.data && res.data.detail;
        var _msg = (_det && typeof _det==='object' && _det.message) ? _det.message
                 : (typeof _det==='string' ? _det : 'حدث خطأ');
        toast(_msg);
        return;
      }
      var entry = res.data.skill;
      var cache = window._scProfile;
      if(cache){
        var found = false;
        var skills = cache.skills || [];
        for(var i=0; i<skills.length; i++){
          if((skills[i].skill||'').toLowerCase() === (entry.skill||'').toLowerCase()){
            skills[i] = entry; found = true; break;
          }
        }
        if(!found) cache.skills = [entry].concat(skills);
        else cache.skills = skills;
      }
      closeModal();
      toast('تمت إضافة المهارة');
      _reRenderSkills();
      if(window._bgRefetch) window._bgRefetch();
    }).catch(function(){
      toast('خطأ في الاتصال بالخادم');
    }).finally(function(){
      saveBtn.disabled    = false;
      saveBtn.textContent = 'حفظ';
    });
  };

  // ── Build Skills HTML ──
  window._buildSkillsHTML = function(skills, isOwner){
    var addBtn = isOwner
      ? '<button class="sc-section-add owner-only" onclick="window._skillOpenAdd()">'
        + '<svg class="ico-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        + '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'
        + ' إضافة مهارة</button>'
      : '';
    if(!skills || !skills.length)
      return addBtn + '<div class="sc-empty">لا توجد مهارات بعد</div>';

    var chips = '<div class="sc-skills-wrap">';
    for(var i=0; i<skills.length; i++){
      var s     = skills[i];
      var name  = esc(s.skill || '');
      var level = s.level ? esc(s.level) : '';
      var lv    = LEVEL_COLORS[s.level] || {color:'#9ca3af', bg:'rgba(156,163,175,.15)'};
      var badge = level
        ? '<span class="sc-skill-badge" style="color:'+lv.color+';background:'+lv.bg+'">'+level+'</span>'
        : '';
      var del = isOwner
        ? '<button class="sc-skill-del owner-only" data-skill-id="'+s.id+'"'
          + ' onclick="window._skillConfirmDelete(this.dataset.skillId)"'
          + ' title="حذف" aria-label="حذف المهارة">×</button>'
        : '';
      chips += '<span class="sc-skill-chip">'
        + '<span class="sc-skill-name">'+name+'</span>'
        + badge
        + del
        + '</span>';
    }
    chips += '</div>';
    return addBtn + chips;
  };

  function _reRenderSkills(){
    var el = document.getElementById('scSkillsPane');
    if(!el) return;
    var cache   = window._scProfile;
    var skills  = cache ? (cache.skills || []) : [];
    var isOwner = (window._scViewerType === 'owner');
    el.innerHTML = window._buildSkillsHTML(skills, isOwner);
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  }
  window._reRenderSkills = _reRenderSkills;

  window._skillOpenAdd = function(){ openModal(); };

  window._skillConfirmDelete = function(id){
    id = parseInt(id, 10);
    scConfirm('هل أنت متأكد من حذف هذه المهارة؟', function(){
      deleteSkill(id).then(function(res){
        if(!res.ok){ toast('حدث خطأ أثناء الحذف'); return; }
        var cache = window._scProfile;
        if(cache) cache.skills = (cache.skills||[]).filter(function(s){ return s.id!==id; });
        _reRenderSkills();
        toast('تم حذف المهارة');
        if(window._bgRefetch) window._bgRefetch();
      }).catch(function(){ toast('خطأ في الاتصال بالخادم'); });
    });
  };

})();
