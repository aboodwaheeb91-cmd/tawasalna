// profile-v2.courses.js — Courses Add / Edit / Delete
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.utils.js

(function(){
  var overlay   = document.getElementById('courseOverlay');
  var saveBtn   = document.getElementById('courseSaveBtn');
  var cancelBtn = document.getElementById('courseCancelBtn');
  var closeBtn  = document.getElementById('courseClose');
  if(!overlay || !saveBtn) return;

  function f(id){ return document.getElementById(id); }
  function fv(id){ return ((f(id)||{}).value||'').trim(); }
  function sv(id,v){ var el=f(id); if(el) el.value=(v==null?'':v); }

  var _editId = null;

  // Populate year select once — runs at module init
  (function _populateCourseYears(){
    var sel = f('courseCD');
    if(!sel || sel.options.length > 1) return;
    var now = new Date().getFullYear();
    var opts = '<option value="">— اختر السنة —</option>';
    for(var y = now; y >= 1990; y--) opts += '<option value="'+y+'">'+y+'</option>';
    sel.innerHTML = opts;
  })();

  function openAdd(){
    _editId = null;
    sv('courseMTitle','إضافة دورة');
    sv('courseTitle',''); sv('courseProv',''); sv('courseCD','');
    sv('courseCurl',''); sv('courseDesc','');
    overlay.classList.add('open');
    var inp=f('courseTitle'); if(inp) setTimeout(function(){ inp.focus(); },120);
  }

  function openEdit(entry){
    _editId = entry.id;
    sv('courseMTitle','تعديل الدورة');
    sv('courseTitle', entry.title           || '');
    sv('courseProv',  entry.provider        || '');
    // completion_date may be stored as "YYYY-MM-DD" or "YYYY" — extract year only
    var cdYear = (entry.completion_date || '').split('-')[0] || '';
    sv('courseCD', cdYear);
    sv('courseCurl',  entry.certificate_url || '');
    sv('courseDesc',  entry.description     || '');
    overlay.classList.add('open');
    var inp=f('courseTitle'); if(inp) setTimeout(function(){ inp.focus(); },120);
  }

  function closeModal(){ overlay.classList.remove('open'); _editId=null; }

  if(closeBtn)  closeBtn.onclick  = closeModal;
  if(cancelBtn) cancelBtn.onclick = closeModal;
  overlay.addEventListener('click', function(e){ if(e.target===overlay) closeModal(); });

  if(saveBtn) saveBtn.onclick = function(){
    var title = fv('courseTitle');
    if(!title){ toast('اسم الدورة مطلوب'); return; }
    var _emojiFields = [title, fv('courseProv'), fv('courseDesc')];
    for(var _i=0; _i<_emojiFields.length; _i++){
      if(_emojiFields[_i] && typeof hasEmoji==='function' && hasEmoji(_emojiFields[_i])){ toast('لا يسمح باستخدام الرموز التعبيرية'); return; }
    }
    var payload = {
      title:            title,
      provider:         fv('courseProv')  || null,
      completion_date:  fv('courseCD')    || null,
      certificate_url:  fv('courseCurl')  || null,
      description:      fv('courseDesc')  || null
    };
    saveBtn.disabled    = true;
    saveBtn.textContent = 'جاري الحفظ…';

    var isEdit = !!_editId;
    var promise = isEdit
      ? updateCourse(_editId, payload)
      : addCourse(_scUserId, payload);

    promise.then(function(res){
      if(!res.ok){
        var _det = res.data && res.data.detail;
        var _msg = (_det && typeof _det === 'object' && _det.message) ? _det.message : (typeof _det === 'string' ? _det : 'حدث خطأ');
        toast(_msg);
        return;
      }
      var entry = res.data.course;
      var cache = window._scProfile;
      if(cache){
        if(isEdit){
          cache.courses = (cache.courses||[]).map(function(c){ return c.id===entry.id ? entry : c; });
        } else {
          cache.courses = [entry].concat(cache.courses||[]);
        }
      }
      closeModal();
      toast(isEdit ? 'تم التحديث' : 'تمت الإضافة');
      _reRenderCourses();
      if(window._bgRefetch) window._bgRefetch();
    }).catch(function(){
      toast('خطأ في الاتصال بالخادم');
    }).finally(function(){
      saveBtn.disabled    = false;
      saveBtn.textContent = 'حفظ';
    });
  };

  // ── Build Courses HTML ──
  window._buildCoursesHTML = function(courses, isOwner){
    var addBtn = isOwner
      ? '<button class="sc-section-add owner-only" onclick="window._courseOpenAdd()">'
        + '<svg class="ico-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'
        + ' إضافة دورة</button>'
      : '';
    if(!courses || !courses.length) return addBtn + '<div class="sc-empty">لا توجد دورات بعد</div>';

    var rows = '<div class="sc-exp-list">' + courses.map(function(c){
      var title  = esc(c.title    || '');
      var prov   = c.provider         ? esc(c.provider)         : '';
      var cd     = c.completion_date  ? esc(c.completion_date)  : '';
      var curl   = c.certificate_url  ? esc(c.certificate_url)  : '';
      var desc   = c.description      ? esc(c.description)      : '';
      var actions = isOwner
        ? '<div class="sc-exp-menu-wrap owner-only">'
          +'<button class="sc-exp-menu-btn" onclick="window._expMenuToggle(this)" title="خيارات">'
          +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/></svg>'
          +'</button>'
          +'<div class="sc-exp-menu">'
          +'<button class="sc-exp-menu-item" data-course-id="'+c.id+'" onclick="window._courseOpenEdit(this.dataset.courseId);window._expMenuClose()">'
          +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>'
          +' تعديل</button>'
          +'<button class="sc-exp-menu-item sc-exp-menu-del" data-course-id="'+c.id+'" onclick="window._courseConfirmDelete(this.dataset.courseId);window._expMenuClose()">'
          +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>'
          +' حذف</button>'
          +'</div>'
          +'</div>'
        : '';

      return '<div class="sc-exp-card">'
        + '<div class="sc-exp-head">'
        + '<div class="sc-exp-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="20" height="20"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg></div>'
        + '<div class="sc-exp-body">'
        + '<div class="sc-exp-title">' + title + '</div>'
        + (prov ? '<div class="sc-exp-company">' + prov + '</div>' : '')
        + (cd   ? '<div class="sc-exp-period">' + cd + '</div>' : '')
        + (desc ? '<div class="sc-exp-desc">'   + desc + '</div>' : '')
        + (curl ? '<a href="' + curl + '" target="_blank" rel="noopener" class="sc-cert-link"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg> عرض الشهادة</a>' : '')
        + '</div>'
        + actions
        + '</div>'
        + '</div>';
    }).join('') + '</div>';

    return addBtn + rows;
  };

  function _reRenderCourses(){
    var el = document.getElementById('scCoursesPane');
    if(!el) return;
    var cache   = window._scProfile;
    var courses = cache ? (cache.courses || []) : [];
    var isOwner = (window._scViewerType === 'owner');
    el.innerHTML = window._buildCoursesHTML(courses, isOwner);
  }
  window._reRenderCourses = _reRenderCourses;

  window._courseOpenAdd  = function(){ openAdd(); };
  window._courseOpenEdit = function(courseId){
    var id   = parseInt(courseId, 10);
    var list = (window._scProfile && Array.isArray(window._scProfile.courses))
      ? window._scProfile.courses : [];
    var entry = null;
    for(var i = 0; i < list.length; i++){
      if(list[i].id === id){ entry = list[i]; break; }
    }
    if(!entry){ toast('لم يتم العثور على الدورة'); return; }
    openEdit(entry);
  };
  window._courseConfirmDelete = function(id){
    id = parseInt(id);
    scConfirm('هل أنت متأكد من حذف هذه الدورة؟', function(){
      deleteCourse(id).then(function(res){
        if(!res.ok){ toast('حدث خطأ أثناء الحذف'); return; }
        var cache = window._scProfile;
        if(cache) cache.courses = (cache.courses||[]).filter(function(c){ return c.id!==id; });
        _reRenderCourses();
        toast('تم حذف الدورة');
        if(window._bgRefetch) window._bgRefetch();
      }).catch(function(){ toast('خطأ في الاتصال بالخادم'); });
    });
  };

})();
