/* home.render.js — feed UI states for Home V2 (skeleton / empty / error / feed / «عرض المزيد») */
(function () {
  'use strict';
  window.Home = window.Home || {};

  var feedEl  = document.getElementById('hwFeed');
  var emptyEl = document.getElementById('hwEmpty');
  var errorEl = document.getElementById('hwError');
  var moreEl  = document.getElementById('hwMore');
  var moreBtn = document.getElementById('hwMoreBtn');
  var moreErr = document.getElementById('hwMoreErr');

  function _hideMore() { moreEl.classList.add('hidden'); }

  /* «عرض المزيد» button state: idle / loading (disabled) / error (message + retry) */
  function _setMore(mode) {
    moreBtn.disabled = mode === 'loading';
    moreBtn.textContent = twT(mode === 'loading' ? 'common.loading' : mode === 'error' ? 'home.retry' : 'home.more.load');
    moreErr.classList.toggle('hidden', mode !== 'error');
  }

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
      _hideMore();
      emptyEl.classList.add('hidden');
      errorEl.classList.add('hidden');
    },

    showEmpty: function (filter) {
      var L = window.Home.utils.emptyLabels(filter);
      feedEl.innerHTML = '';
      feedEl.classList.add('hidden');
      _hideMore();
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
      _hideMore();
      emptyEl.classList.add('hidden');
      errorEl.classList.remove('hidden');
      var btn = errorEl.querySelector('.hw-retry');
      if (btn) btn.onclick = retryFn;
    },

    /* append = true («عرض المزيد») adds the page under the cards on screen; otherwise the feed starts over.
     * An item already on screen (same type + id) is skipped — a guard only, the server cursor has no repeats. */
    renderFeed: function (items, filter, append) {
      var state = window.Home.state;
      if (!append) { feedEl.innerHTML = ''; state.seen = {}; }
      var fresh = (items || []).filter(function (it) {
        var key = it && (it.type + ':' + it.id);
        if (!key || state.seen[key]) return false;
        state.seen[key] = true;
        return true;
      });
      if (!append && !fresh.length) { this.showEmpty(filter); return; }
      window.Home.posts.remember(fresh, append);   // post authors for mentions / share (home.posts.js)
      var frag = document.createDocumentFragment();
      var cards = [];
      fresh.forEach(function (item) {
        var card = window.Home.cards.renderCard(item);
        if (card) { frag.appendChild(card); cards.push(card); }
      });
      feedEl.appendChild(frag);
      feedEl.classList.remove('hidden');
      emptyEl.classList.add('hidden');
      errorEl.classList.add('hidden');
      window.Home.posts.afterRender(feedEl, cards);   // clamp the new cards + view tracking
      this.updateMore();
    },

    /* The button shows only while the server has a next page (next_cursor) */
    updateMore: function () {
      if (!window.Home.state.nextCursor) { _hideMore(); return; }
      _setMore('idle');
      moreEl.classList.remove('hidden');
    },

    moreLoading: function () { _setMore('loading'); },

    /* A failed page keeps the cards on screen — small message + the same button retries */
    moreError: function () { _setMore('error'); }
  };
}());
