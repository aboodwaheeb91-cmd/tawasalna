// profile-v2.select.js — Custom Select Component for Profile V2
// Replaces native <select> with a styled dropdown while preserving all values and events.
//
// Architecture:
//   - Hides native <select>, inserts .sc-sel trigger wrapper before it
//   - Dropdown portal: appended to document.body with position:fixed (escape overflow:hidden/auto)
//   - MutationObserver per select: auto-syncs trigger label when options change (cities, years, professions)
//   - Modal open observer: re-syncs all triggers 80ms after any .ep-overlay opens (catches programmatic prefill)
//   - Closes on: outside mousedown, scroll (capture:true), Escape key

(function(){
  'use strict';

  function _esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  // ── Currently open dropdown ──
  var _cur = null;

  // ── Close open dropdown ──
  function _close(){
    if(!_cur) return;
    var d = _cur.drop;
    d.classList.remove('sc-sel-drop-open');
    _cur.wrap.classList.remove('sc-sel-open');
    _cur.trg.setAttribute('aria-expanded','false');
    _cur = null;
    setTimeout(function(){ if(d.parentNode) d.parentNode.removeChild(d); }, 130);
    if(window._scHistoryReset) window._scHistoryReset();
  }

  // ── Global close triggers ──
  // capture:true catches all scrolls — skip if scroll is inside the open dropdown itself
  window.addEventListener('scroll', function(e){
    if(_cur && _cur.drop.contains(e.target)) return;
    _close();
  }, true);
  document.addEventListener('mousedown', function(e){
    if(_cur && !_cur.wrap.contains(e.target) && !_cur.drop.contains(e.target)) _close();
  });
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape'){ _close(); return; }
    if(!_cur) return;
    var items = _cur.drop.querySelectorAll('.sc-sel-item:not(.sc-sel-item-dis)');
    var focused = _cur.drop.querySelector('.sc-sel-item-kb');
    var idx = focused ? Array.prototype.indexOf.call(items, focused) : -1;
    if(e.key === 'ArrowDown'){
      e.preventDefault();
      if(idx < items.length - 1){
        if(focused) focused.classList.remove('sc-sel-item-kb');
        items[idx+1].classList.add('sc-sel-item-kb');
        items[idx+1].scrollIntoView({block:'nearest'});
      }
    } else if(e.key === 'ArrowUp'){
      e.preventDefault();
      if(idx > 0){
        if(focused) focused.classList.remove('sc-sel-item-kb');
        items[idx-1].classList.add('sc-sel-item-kb');
        items[idx-1].scrollIntoView({block:'nearest'});
      }
    } else if(e.key === 'Enter' && focused){
      e.preventDefault();
      focused.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));
    }
  });

  // ── Build a single dropdown item from an <option> element ──
  function _buildItem(opt, native, wrap){
    var val  = opt.value;
    var text = (opt.textContent || '').trim();
    var icon = opt.getAttribute('data-icon') || '';
    var img  = opt.getAttribute('data-img')  || '';
    var isPlaceholder = (val === '');
    var isDis = opt.disabled || isPlaceholder;
    var isSel = (!isPlaceholder && val === native.value);

    var item = document.createElement('div');
    item.className = 'sc-sel-item'
      + (isDis ? ' sc-sel-item-dis' : '')
      + (isSel ? ' sc-sel-item-sel' : '');
    item.setAttribute('role','option');
    item.setAttribute('aria-selected', isSel ? 'true' : 'false');
    item.dataset.val = val;

    if(icon){
      item.innerHTML = '<i data-lucide="' + _esc(icon) + '" class="ico-sm sc-sel-ico"></i><span>' + _esc(text) + '</span>';
    } else if(img){
      var imgEl = document.createElement('img');
      imgEl.src       = img;
      imgEl.alt       = '';
      imgEl.className = 'tw-flag sc-sel-ico';
      imgEl.width     = 18;
      imgEl.height    = 18;
      var txtSpan = document.createElement('span');
      txtSpan.textContent = text;
      item.appendChild(imgEl);
      item.appendChild(txtSpan);
    } else {
      item.textContent = text;
    }

    if(!isDis){
      (function(v){
        item.addEventListener('mousedown', function(e){
          e.preventDefault();
          native.value = v;
          native.dispatchEvent(new Event('change',{bubbles:true}));
          _syncTrigger(wrap, native);
          _close();
        });
      })(val);
    }
    return item;
  }

  // ── Recursively render options/optgroups into the dropdown container ──
  function _buildChildren(container, children, native, wrap){
    var first = true;
    for(var i=0; i<children.length; i++){
      var child = children[i];
      var tag = child.tagName ? child.tagName.toLowerCase() : '';
      if(tag === 'optgroup'){
        var hdr = document.createElement('div');
        hdr.className = 'sc-sel-grp' + (first ? ' sc-sel-grp-first' : '');
        hdr.textContent = child.getAttribute('label') || '';
        container.appendChild(hdr);
        _buildChildren(container, child.children, native, wrap);
        first = false;
      } else if(tag === 'option'){
        container.appendChild(_buildItem(child, native, wrap));
        first = false;
      }
    }
  }

  // ── Update trigger button label from current native select value ──
  function _syncTrigger(wrap, native){
    var txt = wrap ? wrap.querySelector('.sc-sel-txt') : null;
    if(!txt) return;
    var idx = native.selectedIndex;
    var opt = (idx >= 0) ? native.options[idx] : null;

    if(!opt || opt.value === ''){
      // Show placeholder
      var ph = native.options[0];
      txt.innerHTML = _esc(ph ? (ph.textContent||'').trim() : '— اختر —');
      txt.classList.add('sc-sel-ph');
    } else {
      var text = (opt.textContent||'').trim();
      var icon = opt.getAttribute('data-icon') || '';
      var img  = opt.getAttribute('data-img')  || '';
      txt.classList.remove('sc-sel-ph');
      if(icon){
        txt.innerHTML = '<i data-lucide="' + _esc(icon) + '" class="ico-sm sc-sel-ico" style="margin-left:5px"></i>' + _esc(text);
        if(window.lucide && lucide.createIcons) lucide.createIcons({nodes:[txt]});
      } else if(img){
        txt.innerHTML = '';
        var imgEl = document.createElement('img');
        imgEl.src       = img;
        imgEl.alt       = '';
        imgEl.className = 'tw-flag';
        imgEl.style.marginLeft = '5px';
        imgEl.width  = 18;
        imgEl.height = 18;
        txt.appendChild(imgEl);
        txt.appendChild(document.createTextNode(text));
      } else {
        txt.innerHTML = _esc(text);
      }
    }
  }

  // ── Open the dropdown for a given select ──
  function _openFor(wrap, native, trg){
    _close();

    var drop = document.createElement('div');
    drop.className = 'sc-sel-drop';
    drop.setAttribute('role','listbox');
    drop.setAttribute('dir','rtl');
    _buildChildren(drop, native.children, native, wrap);
    document.body.appendChild(drop);

    // Position: fixed relative to trigger
    var rect = trg.getBoundingClientRect();
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    var w  = rect.width;
    var maxH = 240;
    var spaceBelow = vh - rect.bottom;
    var leftPos = Math.max(4, Math.min(rect.left, vw - w - 4));

    drop.style.width  = w + 'px';
    drop.style.left   = leftPos + 'px';
    drop.style.right  = 'auto';
    drop.style.zIndex = getComputedStyle(document.documentElement).getPropertyValue('--tw-drop-z').trim() || '9500';

    if(spaceBelow >= maxH + 6 || spaceBelow >= vh - rect.top){
      drop.style.top    = (rect.bottom + 3) + 'px';
      drop.style.bottom = 'auto';
      drop.style.maxHeight = Math.min(spaceBelow - 6, maxH) + 'px';
    } else {
      drop.style.top    = 'auto';
      drop.style.bottom = (vh - rect.top + 3) + 'px';
      drop.style.maxHeight = Math.min(rect.top - 6, maxH) + 'px';
    }

    if(window.lucide && lucide.createIcons) lucide.createIcons({nodes:[drop]});

    requestAnimationFrame(function(){ drop.classList.add('sc-sel-drop-open'); });

    // Scroll selected item into view after paint
    setTimeout(function(){
      var sel = drop.querySelector('.sc-sel-item-sel');
      if(sel) sel.scrollIntoView({block:'nearest'});
    }, 0);

    trg.setAttribute('aria-expanded','true');
    wrap.classList.add('sc-sel-open');
    _cur = { wrap:wrap, native:native, trg:trg, drop:drop };
    if(window._scPushHistory) window._scPushHistory('select');
  }

  // ── Sync all initialized triggers (called on modal open) ──
  function _syncAll(){
    var all = document.querySelectorAll('select[data-sc-sel]');
    for(var i=0; i<all.length; i++){
      var nat  = all[i];
      var wrap = nat.closest('.sc-sel');
      if(wrap) _syncTrigger(wrap, nat);
    }
  }

  // ── Initialize one native <select> ──
  function _init(native){
    if(!native || native.hasAttribute('data-sc-sel')) return;
    native.setAttribute('data-sc-sel','1');
    native.style.display = 'none';

    // Wrapper (position:relative so dropdown anchor is predictable)
    var wrap = document.createElement('div');
    wrap.className = 'sc-sel';
    native.parentNode.insertBefore(wrap, native);
    wrap.appendChild(native);

    // Trigger button
    var trg = document.createElement('button');
    trg.type = 'button';
    trg.className = 'sc-sel-trg';
    trg.setAttribute('aria-haspopup','listbox');
    trg.setAttribute('aria-expanded','false');
    trg.setAttribute('dir','rtl');

    var txt = document.createElement('span');
    txt.className = 'sc-sel-txt sc-sel-ph';
    trg.appendChild(txt);

    var arr = document.createElement('span');
    arr.className = 'sc-sel-arr';
    arr.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12"><polyline points="6 9 12 15 18 9"/></svg>';
    trg.appendChild(arr);

    wrap.insertBefore(trg, native);
    _syncTrigger(wrap, native);

    // Toggle on click
    trg.addEventListener('click', function(e){
      e.stopPropagation();
      if(_cur && _cur.native === native) _close();
      else _openFor(wrap, native, trg);
    });

    // MutationObserver: rebuild trigger label when options change (cities, years, professions)
    new MutationObserver(function(){
      _syncTrigger(wrap, native);
      // If this dropdown is currently open, close and re-open with fresh options
      if(_cur && _cur.native === native){
        var savedWrap = wrap; var savedTrg = trg;
        _close();
        setTimeout(function(){
          if(document.body.contains(native)) _openFor(savedWrap, native, savedTrg);
        }, 20);
      }
    }).observe(native, {childList:true, subtree:true});

    // Sync trigger on native change (e.g. programmatic native.value = x followed by change event)
    native.addEventListener('change', function(){ _syncTrigger(wrap, native); });
  }

  // ── Watch modal opens to re-sync prefilled values ──
  // Programmatic `select.value = x` doesn't fire a change event, so we sync on modal open.
  (function(){
    var overlays = document.querySelectorAll('.ep-overlay, .sc-modal-overlay');
    for(var i=0; i<overlays.length; i++){
      (function(ov){
        new MutationObserver(function(muts){
          for(var j=0; j<muts.length; j++){
            if(muts[j].attributeName === 'class' && ov.classList.contains('open')){
              setTimeout(_syncAll, 80);
              break;
            }
          }
        }).observe(ov, {attributes:true, attributeFilter:['class']});
      })(overlays[i]);
    }
  })();

  // ── Initialize all .ep-select elements, then sync all trigger labels ──
  // Calling scSelectInit() is safe at any time: _init() skips already-wrapped selects,
  // and _syncAll() re-reads native.value for every initialized trigger (no side-effects).
  window.scSelectInit = function(){
    var sels = document.querySelectorAll('.ep-select:not([data-sc-sel])');
    for(var i=0; i<sels.length; i++) _init(sels[i]);
    _syncAll();
  };

  // Expose close for history.js back-button handler
  window.scSelectClose = _close;

  // Run at script load (all preceding scripts have already populated options)
  window.scSelectInit();
})();
