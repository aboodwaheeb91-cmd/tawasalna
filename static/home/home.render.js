/* home.render.js — feed UI states for Home V2 (skeleton / empty / error / feed) */
(function () {
  'use strict';
  window.Home = window.Home || {};

  var feedEl  = document.getElementById('hwFeed');
  var emptyEl = document.getElementById('hwEmpty');
  var errorEl = document.getElementById('hwError');

  /* Skeleton markup is static (no API data) — innerHTML is safe here */
  function _buildSkeletons() {
    var frag = document.createDocumentFragment();
    var SKELS = [
      '<div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:12px"><div class="hw-skr" style="width:44px;height:44px;flex-shrink:0"></div><div style="flex:1;display:flex;flex-direction:column;gap:7px"><div class="hw-skl" style="height:14px;width:62%"></div><div class="hw-skl" style="height:11px;width:38%"></div></div></div><div style="display:flex;gap:7px;margin-bottom:14px"><div class="hw-skl" style="height:22px;width:68px;border-radius:12px"></div><div class="hw-skl" style="height:22px;width:52px;border-radius:12px"></div></div><div style="display:flex;justify-content:space-between;align-items:center"><div class="hw-skl" style="height:10px;width:76px"></div><div class="hw-skl" style="height:30px;width:82px;border-radius:20px"></div></div>',
      '<div style="display:flex;gap:10px;align-items:center;margin-bottom:12px"><div class="hw-skc" style="width:38px;height:38px;flex-shrink:0"></div><div style="flex:1;display:flex;flex-direction:column;gap:6px"><div class="hw-skl" style="height:13px;width:42%"></div><div class="hw-skl" style="height:10px;width:26%"></div></div></div><div style="display:flex;flex-direction:column;gap:6px"><div class="hw-skl" style="height:12px;width:100%"></div><div class="hw-skl" style="height:12px;width:88%"></div><div class="hw-skl" style="height:12px;width:72%"></div></div>',
      '<div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:10px"><div class="hw-skr" style="width:36px;height:36px;flex-shrink:0;border-radius:9px"></div><div style="flex:1;display:flex;flex-direction:column;gap:7px"><div class="hw-skl" style="height:14px;width:70%"></div><div class="hw-skl" style="height:10px;width:30%;border-radius:12px"></div></div></div><div class="hw-skl" style="height:12px;width:100%;margin-bottom:6px"></div><div class="hw-skl" style="height:12px;width:80%"></div>'
    ];
    SKELS.forEach(function (inner) {
      var c = document.createElement('div');
      c.className = 'hw-card';
      c.innerHTML = inner;
      frag.appendChild(c);
    });
    return frag;
  }

  window.Home.render = {
    showSkeleton: function () {
      feedEl.innerHTML = '';
      feedEl.appendChild(_buildSkeletons());
      feedEl.classList.remove('hidden');
      emptyEl.classList.add('hidden');
      errorEl.classList.add('hidden');
      window.Home.utils.icons();
    },

    showEmpty: function (filter) {
      var L = window.Home.utils.EMPTY_LABELS[filter]
            || { h: 'لا يوجد محتوى', p: 'ارجع لاحقاً أو جرّب فلتراً آخر' };
      feedEl.innerHTML = '';
      feedEl.classList.add('hidden');
      var h3 = emptyEl.querySelector('h3');
      var p  = emptyEl.querySelector('p');
      if (h3) h3.textContent = L.h;
      if (p)  p.textContent  = L.p;
      emptyEl.classList.remove('hidden');
      errorEl.classList.add('hidden');
    },

    showError: function (retryFn) {
      feedEl.innerHTML = '';
      feedEl.classList.add('hidden');
      emptyEl.classList.add('hidden');
      errorEl.classList.remove('hidden');
      var btn = errorEl.querySelector('.hw-retry');
      if (btn) btn.onclick = retryFn;
    },

    renderFeed: function (items, filter) {
      feedEl.innerHTML = '';
      if (!items || !items.length) { this.showEmpty(filter); return; }
      var frag = document.createDocumentFragment();
      items.forEach(function (item) {
        var card = window.Home.cards.renderCard(item);
        if (card) frag.appendChild(card);
      });
      feedEl.appendChild(frag);
      feedEl.classList.remove('hidden');
      emptyEl.classList.add('hidden');
      errorEl.classList.add('hidden');
      window.Home.utils.icons();
    }
  };
}());
