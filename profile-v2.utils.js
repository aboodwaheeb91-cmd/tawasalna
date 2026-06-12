// profile-v2.utils.js — helpers: esc, setText, toast, renderIcons, fitName, toggleBio, scTab, hasEmoji

// Emoji guard — blocks pictographic symbols in professional text fields.
// Shared by all V2 edit panels. Backend enforces the same rule via validate_no_emoji().
window.hasEmoji = (function(){
  var _re = /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FAFF}\u{2702}-\u{27B0}\u{2600}-\u{26FF}\u{1F1E0}-\u{1F1FF}️‍]/u;
  return function(str){ return str != null && _re.test(String(str)); };
})();

function esc(s){ var d=document.createElement('div'); d.textContent=s==null?'':String(s); return d.innerHTML; }
function setText(id,v){ var el=document.getElementById(id); if(el) el.textContent=v==null?'':v; }

function renderIcons(){
  if(window.lucide && lucide.createIcons){ lucide.createIcons(); return true; }
  return false;
}
window._renderIcons = function(){ if(window.lucide && lucide.createIcons) lucide.createIcons(); };

function toast(msg){
  var t=document.getElementById('scToast'); if(!t) return;
  t.textContent=msg; t.classList.add('show');
  setTimeout(function(){ t.classList.remove('show'); },2200);
}
window.toast = toast;

// Auto-fit name to one line — shrink font before resorting to ellipsis.
function fitName(){
  var nameEl=document.getElementById('scName');
  var row=document.querySelector('.sc-name-row');
  if(!nameEl || !row) return;
  var MAX=20, MIN=13;
  var boxW=row.clientWidth;
  if(boxW<=0) return;
  var badge=document.getElementById('scVerified');
  var badgeVisible = badge && badge.style.display!=='none';
  nameEl.style.textOverflow='clip';
  var size=MAX;
  nameEl.style.fontSize=size+'px';
  function reserve(){ return badgeVisible ? (size*1.1 + size*0.3 + 4) : 0; }
  while(size>MIN && nameEl.scrollWidth > (boxW - reserve())){
    size-=1; nameEl.style.fontSize=size+'px';
  }
  // ellipsis only as last resort — when still doesn't fit at MIN
  nameEl.style.textOverflow = (nameEl.scrollWidth > (boxW - reserve())) ? 'ellipsis' : 'clip';
}
window._fitName = fitName;

// Re-run after Cairo font loads (avoids wrong measurement with fallback font)
if(document.fonts && document.fonts.ready){
  document.fonts.ready.then(function(){ fitName(); });
}

window.toggleBio = function(){
  var bio=document.getElementById('scBio');
  var btn=document.getElementById('scBioMore');
  if(!bio || !btn) return;
  var expanded = bio.classList.toggle('expanded');
  btn.textContent = expanded ? 'عرض أقل ▴' : 'عرض المزيد ▾';
};

window.scTab = function(name, el){
  var tabs=document.querySelectorAll('.sc-tab');
  for(var i=0;i<tabs.length;i++) tabs[i].classList.remove('active');
  if(el) el.classList.add('active');
  var panes=document.querySelectorAll('.sc-pane');
  for(var j=0;j<panes.length;j++) panes[j].classList.remove('active');
  var pane=document.getElementById('pane-'+name);
  if(pane) pane.classList.add('active');
  if(el) el.scrollIntoView({behavior:'smooth',inline:'center',block:'nearest'});
  if(window.lucide && lucide.createIcons) lucide.createIcons();
};

window.addEventListener('resize', function(){ if(window._fitName) fitName(); });

// Professional content guard — checks emoji AND prohibited language.
// Returns error message string if found, null if clean.
// Mirrors backend validate_professional_text() in auth.py.
window._scCheckProfessional = (function(){
  var _BAD = [
    // English: short — word-level only (len < 5)
    'ass','anus','anal','cock','cum','dick','rape','sex','tit','tits',
    'nude','pimp','smut','perv','wank','twat','pedo',
    // English: medium/long — also substring match (len >= 5)
    'pussy','penis','boobs','naked','horny','boner','nudes','vulva',
    'rapist','orgasm','vagina','erotic','incest','sexting','camgirl','wanker',
    'creampie','gangbang','onlyfans','ejaculat','pedophil','necrophil','bestiality',
    // English: original list
    'fuck','fucking','fucked','fucker','fucks','motherfucker','motherfucking',
    'shit','bullshit','shitting','cunt','cunts','bitch','bitches',
    'asshole','assholes','whore','whores','slut','sluts','bastard',
    'porn','porno','pornography','pornographic',
    'blowjob','handjob','rimjob','cumshot','dildo','masturbate','masturbation',
    // Arabic: short — word-level only
    'زب','طيز','كس','ير','خول','زناء','لواط',
    'زنا','زنى','عاهر','مومس','بزاز','نهود','فحش','جماع','عرص','عري','تعري',
    // Arabic: medium/long — also substring match
    'إباحي','إباحية','زانية','عاهرة','دعارة','ماخور','استمناء','فاحشة',
    // Arabic: original list
    'نيك','ينيك','ينكح','بنيك',
    'شرموطة','شراميط','قحبة','قحاب',
    'خرا','خرة','منيوك','منيوكة',
    'كسمك','كسمه','كسها','كسك','كسمها','كسمهم',
    'متناك','متناكة','سكس','سيكس','بورن','بورنو'
  ];

  function _norm(t){
    t = (t||'').toLowerCase();
    // Arabic: strip diacritics (tashkeel) and tatweel
    t = t.replace(/[ً-ٰٟـ]/g,'');
    // Arabic: normalize hamza forms → plain alef
    t = t.replace(/[آأإٱ]/g,'ا');
    // Arabic: alef maqsura → ya; teh marbuta → ha
    t = t.replace(/ى/g,'ي').replace(/ة/g,'ه');
    // Leet-speak substitutions
    t = t.replace(/@/g,'a').replace(/0/g,'o').replace(/1/g,'i')
         .replace(/3/g,'e').replace(/\$/g,'s').replace(/5/g,'s');
    // Remove invisible / zero-width chars
    t = t.replace(/[​-‏‪-‮﻿͏­]/g,'');
    // Collapse excessive repeats
    t = t.replace(/(.)\1{2,}/g,'$1$1');
    return t;
  }

  // Pre-normalize bad words so comparisons are always apples-to-apples.
  // Handles Arabic words with ة/أ/إ stored in normalized form.
  var _BAD_NORM = [];
  for(var _i=0; _i<_BAD.length; _i++){ _BAD_NORM.push(_norm(_BAD[_i])); }

  var _MSG = 'لا يسمح باستخدام كلمات غير لائقة أو غير مهنية داخل هذا الحقل';

  return function(text){
    if(!text) return null;
    if(typeof hasEmoji === 'function' && hasEmoji(text))
      return 'لا يسمح باستخدام الرموز التعبيرية داخل هذا الحقل';
    var n = _norm(String(text));
    // Split on whitespace/structural separators only (NOT . ! - * etc.),
    // then strip remaining non-alphanumeric from each token to defeat
    // obfuscation like f.u.c.k, sh!t, f*ck written as consonants, etc.
    var rawToks = n.split(/[\s,،;:'"()\[\]{}]+/);
    var ws = {};
    for(var i=0; i<rawToks.length; i++){
      var clean = rawToks[i].replace(/[^a-z0-9؀-ۿ]/g,'');
      if(clean) ws[clean] = 1;
    }
    for(var j=0; j<_BAD_NORM.length; j++){
      var bad = _BAD_NORM[j];
      if(ws[bad]) return _MSG;
      if(bad.length >= 5 && n.indexOf(bad) !== -1) return _MSG;
    }
    return null;
  };
})();

// Tab edge fade — shows gradient when tabs overflow horizontally
(function(){
  function _initTabFade(){
    var wrap = document.querySelector('.sc-tabs-wrap');
    var cont = document.querySelector('.sc-tabs');
    if(!wrap || !cont) return;
    function _upd(){
      var btns = cont.querySelectorAll('.sc-tab');
      if(!btns.length || cont.scrollWidth <= cont.clientWidth + 2){
        wrap.classList.remove('fade-left','fade-right'); return;
      }
      var cr = cont.getBoundingClientRect();
      // In RTL: first button is rightmost, last button is leftmost
      var fr = btns[0].getBoundingClientRect();
      var lr = btns[btns.length-1].getBoundingClientRect();
      wrap.classList.toggle('fade-right', fr.right > cr.right + 2);
      wrap.classList.toggle('fade-left',  lr.left  < cr.left  - 2);
    }
    cont.addEventListener('scroll', _upd, {passive:true});
    window.addEventListener('resize', _upd, {passive:true});
    _upd();
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _initTabFade);
  else _initTabFade();
})();
