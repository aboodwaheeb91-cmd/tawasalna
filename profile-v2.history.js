// profile-v2.history.js — Android Hardware Back Button Handler
// Depends on: all other profile-v2 modules (must load LAST)
//
// Strategy:
//   - replaceState at load → base state marker
//   - pushState when any UI layer opens → back button pops this entry
//   - popstate handler → close topmost layer, re-push if more layers remain
//   - MutationObserver on every static overlay to auto-push on open
//   - Three-dot menus and custom select push via explicit calls from exp.js / select.js

(function(){
  'use strict';

  var _pushed = false;

  // ── Ordered list of layers (highest priority first) ──
  // Each entry: { test: fn → bool, close: fn }
  function _layers(){
    return [
      {
        // Three-dot action menus (dynamic cards)
        test:  function(){ return !!document.querySelector('.sc-exp-menu.open'); },
        close: function(){ if(window._expMenuClose) window._expMenuClose(); }
      },
      {
        // Custom select dropdown portal
        test:  function(){ return !!document.querySelector('.sc-sel-drop-open'); },
        close: function(){ if(window.scSelectClose) window.scSelectClose(); }
      },
      {
        // Avatar crop overlay
        test:  function(){ var el=document.getElementById('avCropOverlay'); return !!(el && el.classList.contains('open')); },
        close: function(){
          var btn=document.getElementById('avCropCancelBtn');
          if(btn) btn.click();
          else { var el=document.getElementById('avCropOverlay'); if(el) el.classList.remove('open'); }
        }
      },
      {
        // Cover crop overlay
        test:  function(){ var el=document.getElementById('cvCropOverlay'); return !!(el && el.classList.contains('open')); },
        close: function(){
          var btn=document.getElementById('cvCropCancelBtn');
          if(btn) btn.click();
          else { var el=document.getElementById('cvCropOverlay'); if(el) el.classList.remove('open'); }
        }
      },
      {
        // Experience modal (ep-overlay)
        test:  function(){ var el=document.getElementById('exOverlay'); return !!(el && el.classList.contains('open')); },
        close: function(){
          var btn=document.getElementById('exClose');
          if(btn) btn.click();
          else { var el=document.getElementById('exOverlay'); if(el) el.classList.remove('open'); }
        }
      },
      {
        // Edit Profile modal (ep-overlay)
        test:  function(){ var el=document.getElementById('epOverlay'); return !!(el && el.classList.contains('open')); },
        close: function(){
          var btn=document.getElementById('epClose');
          if(btn) btn.click();
          else { var el=document.getElementById('epOverlay'); if(el) el.classList.remove('open'); }
        }
      },
      {
        // Education modal
        test:  function(){ var el=document.getElementById('eduOverlay'); return !!(el && el.classList.contains('open')); },
        close: function(){
          var btn=document.getElementById('eduClose');
          if(btn) btn.click();
          else { var el=document.getElementById('eduOverlay'); if(el) el.classList.remove('open'); }
        }
      },
      {
        // Courses modal
        test:  function(){ var el=document.getElementById('courseOverlay'); return !!(el && el.classList.contains('open')); },
        close: function(){
          var btn=document.getElementById('courseClose');
          if(btn) btn.click();
          else { var el=document.getElementById('courseOverlay'); if(el) el.classList.remove('open'); }
        }
      },
      {
        // Skills modal
        test:  function(){ var el=document.getElementById('skillOverlay'); return !!(el && el.classList.contains('open')); },
        close: function(){
          var btn=document.getElementById('skillClose');
          if(btn) btn.click();
          else { var el=document.getElementById('skillOverlay'); if(el) el.classList.remove('open'); }
        }
      },
      {
        // Languages modal
        test:  function(){ var el=document.getElementById('langOverlay'); return !!(el && el.classList.contains('open')); },
        close: function(){
          var btn=document.getElementById('langClose');
          if(btn) btn.click();
          else { var el=document.getElementById('langOverlay'); if(el) el.classList.remove('open'); }
        }
      },
      {
        // Links modal
        test:  function(){ var el=document.getElementById('linkOverlay'); return !!(el && el.classList.contains('open')); },
        close: function(){
          var btn=document.getElementById('linkClose');
          if(btn) btn.click();
          else { var el=document.getElementById('linkOverlay'); if(el) el.classList.remove('open'); }
        }
      }
    ];
  }

  function _hasOpenLayer(){
    var list = _layers();
    for(var i=0; i<list.length; i++){
      if(list[i].test()) return true;
    }
    return false;
  }

  function _closeTopmost(){
    var list = _layers();
    for(var i=0; i<list.length; i++){
      if(list[i].test()){
        list[i].close();
        return true;
      }
    }
    return false;
  }

  // ── Called by any module when it opens a layer ──
  window._scPushHistory = function(label){
    if(_pushed) return;
    _pushed = true;
    history.pushState({ scLayer: label || 'layer' }, '');
  };

  // ── popstate = Android/browser back button ──
  window.addEventListener('popstate', function(){
    _pushed = false;
    var closed = _closeTopmost();
    if(closed){
      // Re-push only if another layer is still open
      setTimeout(function(){
        if(_hasOpenLayer()){
          window._scPushHistory('layer');
        }
      }, 50);
    }
    // If nothing was open, natural back navigation proceeds normally
  });

  // ── Watch every static overlay: push history when it opens ──
  var _staticOverlays = [
    'avCropOverlay','cvCropOverlay',
    'exOverlay','epOverlay',
    'eduOverlay','courseOverlay','skillOverlay','langOverlay','linkOverlay'
  ];

  function _watchOverlay(id){
    var el = document.getElementById(id);
    if(!el) return;
    new MutationObserver(function(muts){
      for(var i=0; i<muts.length; i++){
        if(muts[i].attributeName === 'class'){
          if(el.classList.contains('open')){
            window._scPushHistory(id);
          } else {
            if(!_hasOpenLayer()) _pushed = false;
          }
          break;
        }
      }
    }).observe(el, { attributes: true, attributeFilter: ['class'] });
  }

  for(var _i=0; _i<_staticOverlays.length; _i++) _watchOverlay(_staticOverlays[_i]);

  // ── Set base state on load ──
  history.replaceState({ scLayer: 'profile-base' }, '');

})();
