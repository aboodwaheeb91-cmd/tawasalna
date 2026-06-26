// profile-v2.skills.js — Skills: Catalog Autocomplete + Vertical Cards + Lucide Icons + Notes (Phase 2)
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

  // ── Icon helpers (Phase 1: Lucide only) ──
  var _CUSTOM_FALLBACK_ICON = 'circle-check';
  function _skillIconHtml(iconName){
    return '<i data-lucide="'+(iconName||_CUSTOM_FALLBACK_ICON)+'" class="sk-ic"></i>';
  }

  // ── Level → CSS slug ──
  // Rank used for sorting — higher number = shown first
  var LEVEL_RANK = {
    'محترف': 5,
    'متقدم': 4,
    'جيد':   3,
    'متوسط': 2,
    'مبتدئ': 1,
  };

  var LEVEL_CSS = {
    'مبتدئ': 'lv-beginner',
    'متوسط': 'lv-mid',
    'جيد':   'lv-good',
    'متقدم': 'lv-advanced',
    'محترف': 'lv-pro',
  };

  // ── Catalog helpers delegate to TW (tw-skills.js) ──────────────
  // tw-skills.js loads from /skills/catalog (DB) with TW.SKILL_CATALOG fallback.

  // Level color map
  var LEVEL_COLORS = {
    'مبتدئ': {color:'#9ca3af', bg:'rgba(156,163,175,.15)'},
    'متوسط': {color:'#60a5fa', bg:'rgba(96,165,250,.15)'},
    'جيد':   {color:'#a78bfa', bg:'rgba(167,139,250,.15)'},
    'متقدم': {color:'#00c896', bg:'rgba(0,200,150,.15)'},
    'محترف': {color:'#fbbf24', bg:'rgba(251,191,36,.15)'},
  };

  // Words indicating merged skill+level (caught in validation)
  var LEVEL_WORDS = ['مبتدئ','متوسط','جيد','متقدم','محترف','متخصص','خبير',
                     'beginner','intermediate','advanced','expert','junior','senior','mid-level'];

  // ── Catalog helpers — delegate to TW (tw-skills.js) ──
  function _search(q)           { return (window.TW && TW.searchSkills)   ? TW.searchSkills(q, 8)    : []; }
  function _normalize(raw)      { return (window.TW && TW.normalizeSkill) ? TW.normalizeSkill(raw)   : (raw||'').trim(); }
  function _isOfficial(name)    { return (window.TW && TW._isOfficialSkill) ? TW._isOfficialSkill(name) : false; }
  function _getCatalogEntry(n)  { return (window.TW && TW._getSkillEntry)   ? TW._getSkillEntry(n)      : null; }

  // ── Validation ──
  function _validate(skill){
    if(!skill) return 'اسم المهارة مطلوب';
    if(skill.length < 2) return 'اسم المهارة قصير جداً (حرفان على الأقل)';
    var _pcErr = window._scCheckProfessional && window._scCheckProfessional(skill);
    if(_pcErr) return _pcErr;
    if(!/[a-zA-Z؀-ۿ]/.test(skill)) return 'اسم المهارة غير صالح — يجب أن يحتوي على حروف';
    var sl = skill.toLowerCase();
    for(var i=0; i<LEVEL_WORDS.length; i++){
      if(sl.indexOf(LEVEL_WORDS[i]) !== -1){
        return 'اكتب اسم المهارة فقط — واختر المستوى من القائمة أدناه';
      }
    }
    return null;
  }

  function _validateNote(note){
    if(!note) return null;
    if(note.length > 160) return 'الملاحظة طويلة جداً — الحد الأقصى 160 حرف';
    var _pcErr = window._scCheckProfessional && window._scCheckProfessional(note);
    if(_pcErr) return _pcErr;
    return null;
  }

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
        + _skillIconHtml(s.icon || _CUSTOM_FALLBACK_ICON)
        + '<span class="sk-ac-en">'+esc(s.en)+'</span>'
        + (s.ar !== s.en ? '<span class="sk-ac-ar">'+esc(s.ar)+'</span>' : '')
        + '</div>';
    }
    drop.innerHTML = html;
    drop.style.display = 'block';
    if(window.lucide && lucide.createIcons) lucide.createIcons();

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
    inp.addEventListener('input', function(){ _showDrop(_search(inp.value)); });
    inp.addEventListener('keydown', function(e){
      var drop = _getDrop();
      var open = drop && drop.style.display !== 'none';
      if(e.key === 'ArrowDown')  { e.preventDefault(); if(open) _moveActive(1);       }
      else if(e.key === 'ArrowUp')  { e.preventDefault(); if(open) _moveActive(-1);      }
      else if(e.key === 'Enter')    { if(open && _selectActive()) e.preventDefault();     }
      else if(e.key === 'Escape')   { _hideDrop();                                        }
    });
    inp.addEventListener('blur', function(){ setTimeout(_hideDrop, 160); });
  }

  function _initNoteCounter(){
    var ta = f('skillNote');
    var cnt = f('skillNoteCount');
    if(!ta || !cnt) return;
    ta.addEventListener('input', function(){
      cnt.textContent = ta.value.length + ' / 160';
    });
  }

  // ── Modal ──
  function openModal(){
    sv('skillName','');
    sv('skillLevel','');
    sv('skillNote','');
    var cnt = f('skillNoteCount');
    if(cnt) cnt.textContent = '0 / 160';
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
  _initNoteCounter();

  // ── Save ──
  saveBtn.onclick = function(){
    var raw   = fv('skillName');
    var skill = _normalize(raw);
    var level = fv('skillLevel') || null;
    var rawNote = fv('skillNote');
    var note  = rawNote.length > 0 ? rawNote : null;

    var err = _validate(skill);
    if(err){ toast(err); return; }

    var noteErr = _validateNote(note);
    if(noteErr){ toast(noteErr); return; }

    if(_isDuplicate(skill)){
      toast('هذه المهارة موجودة مسبقاً في ملفك الشخصي');
      return;
    }

    saveBtn.disabled    = true;
    saveBtn.textContent = 'جاري الحفظ…';

    addSkill(_scUserId, {skill:skill, level:level, note:note}).then(function(res){
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
      if(window._updateCompletion) window._updateCompletion();
      _reRenderSkills();
      if(window._bgRefetch) window._bgRefetch();
    }).catch(function(){
      toast('خطأ في الاتصال بالخادم');
    }).finally(function(){
      saveBtn.disabled    = false;
      saveBtn.textContent = 'حفظ';
    });
  };

  // ── Build Skills HTML (vertical cards) ──
  // Legend order matches card display order: highest level first
  var _LEGEND_HTML = '<div class="sc-skill-legend">'
    + '<span class="sc-legend-item"><span class="sc-legend-dot sc-legend-pro"></span>محترف</span>'
    + '<span class="sc-legend-item"><span class="sc-legend-dot sc-legend-advanced"></span>متقدم</span>'
    + '<span class="sc-legend-item"><span class="sc-legend-dot sc-legend-good"></span>جيد</span>'
    + '<span class="sc-legend-item"><span class="sc-legend-dot sc-legend-mid"></span>متوسط</span>'
    + '<span class="sc-legend-item"><span class="sc-legend-dot sc-legend-beginner"></span>مبتدئ</span>'
    + '</div>';

  window._buildSkillsHTML = function(skills, isOwner){
    var addBtn = isOwner
      ? '<button class="sc-section-add owner-only" onclick="window._skillOpenAdd()">'
        + '<svg class="ico-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        + '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'
        + ' إضافة مهارة</button>'
      : '';

    var header = '<div class="sc-skill-header">' + addBtn + _LEGEND_HTML + '</div>';

    if(!skills || !skills.length)
      return header + '<div class="sc-empty">لا توجد مهارات بعد</div>';

    // Sort: by level rank descending (محترف first), then alphabetically within same level
    var sorted = skills.slice().sort(function(a, b){
      var ra = LEVEL_RANK[a.level] || 0;
      var rb = LEVEL_RANK[b.level] || 0;
      if(rb !== ra) return rb - ra;
      return (a.skill || '').localeCompare(b.skill || '', 'ar');
    });

    var cards = '<div class="sc-skill-list">';
    for(var i=0; i<sorted.length; i++){
      var s     = sorted[i];
      var name  = esc(s.skill || '');
      var level = s.level ? esc(s.level) : '';
      var note  = (s.note || '').trim();
      var lv    = LEVEL_COLORS[s.level] || {color:'#9ca3af', bg:'rgba(156,163,175,.15)'};
      var lvSlug = LEVEL_CSS[s.level] || '';

      var badge = level
        ? '<span class="sc-skill-badge" style="color:'+lv.color+';background:'+lv.bg+'">'+level+'</span>'
        : '';

      var isOff    = _isOfficial(s.skill || '');
      var cstBadge = !isOff
        ? '<span class="sc-skill-badge sc-skill-custom-badge">مخصصة</span>'
        : '';

      var del = isOwner
        ? '<button class="sc-skill-del owner-only" data-skill-id="'+s.id+'"'
          + ' onclick="window._skillConfirmDelete(this.dataset.skillId)"'
          + ' title="حذف" aria-label="حذف المهارة">×</button>'
        : '';

      var entry  = _getCatalogEntry(s.skill || '');
      var icon   = (entry && entry.icon) ? entry.icon : _CUSTOM_FALLBACK_ICON;
      var noteHtml = note ? '<p class="sc-skill-note">'+esc(note)+'</p>' : '';
      var cardClass = 'sc-skill-card' + (lvSlug ? ' sc-skill-card--'+lvSlug : '');

      cards += '<div class="'+cardClass+'">'
        + '<div class="sc-skill-card-top">'
        + '<span class="sc-sk-info">'
        + _skillIconHtml(icon)
        + '<span class="sc-skill-name" dir="auto">'+name+'</span>'
        + cstBadge
        + '</span>'
        + '<span class="sc-sk-meta">'
        + badge
        + del
        + '</span>'
        + '</div>'
        + noteHtml
        + '</div>';
    }
    cards += '</div>';
    return header + cards;
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

  // Expose icon lookup for About tab summary cards — delegates to TW
  window._getSkillIcon = function(skillName){
    return (window.TW && TW.getSkillIcon) ? TW.getSkillIcon(skillName) : _CUSTOM_FALLBACK_ICON;
  };

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
        if(window._updateCompletion) window._updateCompletion();
        if(window._bgRefetch) window._bgRefetch();
      }).catch(function(){ toast('خطأ في الاتصال بالخادم'); });
    });
  };

})();
