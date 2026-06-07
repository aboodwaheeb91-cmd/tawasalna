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
