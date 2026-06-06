// profile-v2.edit.js — Edit Profile Modal (Phase 2: name, dob, country/city, avail, profession, bio)
// Depends on: profile-v2.state.js (_jwt, _scUserId, _scProfileKey, _scProfile)
//             profile-v2.api.js (getProfessions, updateProfile, getProfile)
//             profile-v2.render.js (window.renderProfile)
//             profile-v2.utils.js (window.toast)

(function(){
  var overlay   = document.getElementById('epOverlay');
  var closeBtn  = document.getElementById('epClose');
  var cancelBtn = document.getElementById('epCancelBtn');
  var saveBtn   = document.getElementById('epSaveBtn');
  var editBtn   = document.getElementById('scEditProfileBtn');
  var errEl     = document.getElementById('epErr');

  if(!overlay || !editBtn) return;

  // ── Cities data ──
  var EP_CITIES = {
    JO:['عمان','إربد','الزرقاء','العقبة','السلط','مادبا','الكرك','معان','جرش','عجلون','الطفيلة'],
    SA:['الرياض','جدة','مكة المكرمة','المدينة المنورة','الدمام','الخبر','الطائف','أبها','تبوك','القطيف','بريدة'],
    AE:['دبي','أبوظبي','الشارقة','عجمان','رأس الخيمة','الفجيرة','أم القيوين','العين'],
    KW:['مدينة الكويت','حولي','الفروانية','الأحمدي','الجهراء','مبارك الكبير'],
    QA:['الدوحة','الريان','الوكرة','أم صلال','الخور','الشمال'],
    BH:['المنامة','المحرق','الرفاع','مدينة عيسى','مدينة حمد'],
    OM:['مسقط','صلالة','نزوى','صحار','السيب','مطرح','البريمي'],
    EG:['القاهرة','الإسكندرية','الجيزة','شرم الشيخ','الأقصر','أسوان','طنطا','المنصورة','الفيوم','بورسعيد'],
    IQ:['بغداد','البصرة','الموصل','أربيل','كربلاء','النجف','السليمانية','كركوك'],
    SY:['دمشق','حلب','حمص','اللاذقية','حماة','دير الزور','الرقة','درعا'],
    LB:['بيروت','طرابلس','صيدا','صور','جونية','زحلة'],
    PS:['رام الله','القدس','غزة','نابلس','الخليل','جنين','أريحا','بيت لحم'],
    YE:['صنعاء','عدن','تعز','الحديدة','إب','ذمار','مأرب'],
    LY:['طرابلس','بنغازي','مصراتة','الزاوية','البيضاء','سبها'],
    TN:['تونس','صفاقس','سوسة','بنزرت','قابس','القيروان'],
    DZ:['الجزائر','وهران','قسنطينة','عنابة','سطيف','تلمسان'],
    MA:['الرباط','الدار البيضاء','فاس','مراكش','مكناس','أكادير','طنجة'],
    SD:['الخرطوم','أم درمان','بورتسودان','كسلا','الأبيض']
  };

  // ── Populate DOB day options ──
  (function(){
    var d = document.getElementById('epDobD');
    if(!d) return;
    for(var i=1; i<=31; i++){
      var o = document.createElement('option');
      o.value = String(i).padStart(2,'0');
      o.text  = i;
      d.appendChild(o);
    }
  })();

  // ── Populate DOB year options ──
  (function(){
    var y = document.getElementById('epDobY');
    if(!y) return;
    var cur = new Date().getFullYear();
    for(var i=cur-15; i>=1940; i--){
      var o = document.createElement('option');
      o.value = i;
      o.text  = i;
      y.appendChild(o);
    }
  })();

  // ── City loader — global so onchange="epLoadCities()" works ──
  window.epLoadCities = function(selectedCity){
    var cc       = (document.getElementById('epCountry') || {}).value || '';
    var cityWrap = document.getElementById('epCityWrap');
    var cityEl   = document.getElementById('epCity');
    if(!cityEl) return;
    var cities = EP_CITIES[cc] || [];
    if(!cities.length){
      if(cityWrap) cityWrap.style.display = 'none';
      cityEl.innerHTML = '<option value="">— اختر المدينة —</option>';
      return;
    }
    cityEl.innerHTML = '<option value="">— اختر المدينة —</option>';
    cities.forEach(function(c){
      var o = document.createElement('option');
      o.value = c; o.text = c;
      if(selectedCity && c === selectedCity) o.selected = true;
      cityEl.appendChild(o);
    });
    if(cityWrap) cityWrap.style.display = 'block';
  };

  // ── Open Modal — prefill all fields ──
  function openModal(){
    var p = window._scProfile || {};

    // Name: split full_name into first / mid / last
    var parts = (p.full_name || '').trim().split(/\s+/).filter(Boolean);
    var fn = document.getElementById('epFirstName');
    var mn = document.getElementById('epMidName');
    var ln = document.getElementById('epLastName');
    if(fn) fn.value = parts[0] || '';
    if(ln) ln.value = parts.length > 1 ? parts[parts.length-1] : '';
    if(mn) mn.value = parts.length > 2 ? parts.slice(1,-1).join(' ') : '';

    // DOB: parse YYYY-MM-DD
    var dob = p.dob || '';
    if(dob && dob.length === 10){
      var dp = dob.split('-');
      var dy = document.getElementById('epDobY'); if(dy) dy.value = dp[0];
      var dm = document.getElementById('epDobM'); if(dm) dm.value = dp[1];
      var dd = document.getElementById('epDobD'); if(dd) dd.value = dp[2];
    }

    // Country + City
    var countryEl = document.getElementById('epCountry');
    if(countryEl) countryEl.value = p.country || '';
    epLoadCities(p.city || '');

    // Availability
    var avEl = document.getElementById('epAvail');
    if(avEl) avEl.value = p.avail || '';

    // Profession
    var profEl = document.getElementById('epProfession');
    if(profEl){
      profEl.innerHTML = '<option value="">جاري التحميل…</option>';
      getProfessions()
        .then(function(list){
          var groups = {};
          list.forEach(function(pr){
            var g = pr.category_group || 'أخرى';
            if(!groups[g]) groups[g] = [];
            groups[g].push(pr);
          });
          var html = '<option value="">— اختر التخصص —</option>';
          Object.keys(groups).forEach(function(g){
            html += '<optgroup label="' + g + '">';
            groups[g].forEach(function(pr){
              var sel = (p.profession && p.profession.id === pr.id) ? ' selected' : '';
              html += '<option value="' + pr.id + '"' + sel + '>' + pr.name_ar + '</option>';
            });
            html += '</optgroup>';
          });
          profEl.innerHTML = html;
          if(window.lucide && lucide.createIcons) lucide.createIcons();
        })
        .catch(function(){ profEl.innerHTML = '<option value="">تعذّر تحميل التخصصات</option>'; });
    }

    // Bio
    var bioEl = document.getElementById('epBio');
    if(bioEl) bioEl.value = p.bio || '';

    if(errEl) errEl.style.display = 'none';
    overlay.classList.add('open');
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  }

  function closeModal(){
    overlay.classList.remove('open');
  }

  editBtn.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', function(e){ if(e.target === overlay) closeModal(); });

  // ── Save ──
  saveBtn.addEventListener('click', function(){
    var uid = window._scUserId;
    if(!uid){
      if(errEl){ errEl.textContent = 'خطأ: لم يتم التعرف على المستخدم'; errEl.style.display = 'block'; }
      return;
    }

    var first = ((document.getElementById('epFirstName')||{}).value||'').trim();
    var mid   = ((document.getElementById('epMidName')  ||{}).value||'').trim();
    var last  = ((document.getElementById('epLastName') ||{}).value||'').trim();
    var fullName = [first, mid, last].filter(Boolean).join(' ');

    var dobY  = ((document.getElementById('epDobY')||{}).value||'').trim();
    var dobM  = ((document.getElementById('epDobM')||{}).value||'').trim();
    var dobD  = ((document.getElementById('epDobD')||{}).value||'').trim();
    var dob   = (dobY && dobM && dobD) ? (dobY + '-' + dobM + '-' + dobD) : '';

    var country = ((document.getElementById('epCountry')||{}).value||'').trim();
    var city    = ((document.getElementById('epCity')   ||{}).value||'').trim();
    var avail   = ((document.getElementById('epAvail')  ||{}).value||'').trim();
    var profVal = ((document.getElementById('epProfession')||{}).value||'').trim();
    var bioVal  = ((document.getElementById('epBio')    ||{}).value||'').trim();

    var payload = { bio: bioVal };
    if(fullName) payload.full_name     = fullName;
    if(dob)      payload.dob           = dob;
    if(country)  payload.country       = country;
    if(city)     payload.city          = city;
    if(avail)    payload.avail         = avail;
    if(profVal)  payload.profession_id = parseInt(profVal, 10);

    if(errEl) errEl.style.display = 'none';
    saveBtn.disabled = true;
    saveBtn.textContent = 'جاري الحفظ…';

    updateProfile(uid, payload)
      .then(function(res){
        if(!res.ok){
          var msg = (res.data && res.data.detail) ? res.data.detail : 'حدث خطأ أثناء الحفظ';
          if(errEl){ errEl.textContent = msg; errEl.style.display = 'block'; }
          return;
        }
        closeModal();
        if(window.toast) window.toast('تم حفظ التغييرات بنجاح');
        getProfile(_scProfileKey)
          .then(function(freshRes){
            if(freshRes && window.renderProfile) window.renderProfile(freshRes);
            if(window.lucide && lucide.createIcons) lucide.createIcons();
          })
          .catch(function(){ /* silent — user can refresh */ });
      })
      .catch(function(){
        if(errEl){ errEl.textContent = 'خطأ في الاتصال بالخادم'; errEl.style.display = 'block'; }
      })
      .finally(function(){
        saveBtn.disabled = false;
        saveBtn.textContent = 'حفظ التغييرات';
      });
  });
})();
