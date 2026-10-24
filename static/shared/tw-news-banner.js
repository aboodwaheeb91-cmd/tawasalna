// static/shared/tw-news-banner.js — News Banner (phase 5b · docs/rules/content-admin.md · SYSTEMS_INDEX §25h)
// One announcement strip for guests and signed-in users, on top of the landing page (/) and the feed (/home).
//   Host: <div data-tw-news-banner hidden></div> → filled on load from GET /news/banner (public, twApi auth:false)
//   data null · request failed · this news id closed before → nothing shown, nothing logged
//   title + summary + optional link — every text via textContent (never innerHTML) · link only through
//   twSafeLinkUrl (target=_blank, rel="noopener noreferrer") · close → the news id in localStorage
//   (try/catch — storage blocked = closed for this page only) · text: twT (news.banner.*) · colors: --color-* tokens
(function () {
  'use strict';
  var KEY = 'tw_news_banner_closed';

  function closedId() {
    try { return String(window.localStorage.getItem(KEY) || ''); } catch (e) { return ''; }
  }
  function remember(id) {
    try { window.localStorage.setItem(KEY, String(id)); } catch (e) { /* storage blocked — closed for this view only */ }
  }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = String(text);
    return n;
  }

  function render(host, n) {
    host.textContent = '';
    host.className = (host.className ? host.className + ' ' : '') + 'tw-news-banner';
    host.setAttribute('role', 'region');
    host.setAttribute('aria-label', twT('news.banner.label'));
    host.setAttribute('data-news-id', String(n.id));
    var body = el('div', 'tw-news-banner-body');
    body.appendChild(el('strong', 'tw-news-banner-title', n.title || ''));
    if (n.summary) body.appendChild(el('p', 'tw-news-banner-summary', n.summary));
    var safe = typeof window.twSafeLinkUrl === 'function' ? twSafeLinkUrl(n.source_url || '') : '';
    if (safe) {
      var a = el('a', 'tw-news-banner-link', twT('news.banner.link'));
      a.href = safe;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      body.appendChild(a);
    }
    host.appendChild(body);
    var close = el('button', 'tw-news-banner-close');
    close.type = 'button';
    close.setAttribute('aria-label', twT('news.banner.close'));
    close.setAttribute('title', twT('news.banner.close'));
    if (typeof window.twIcon === 'function') close.innerHTML = twIcon('close', { size: 'sm' });   // registry SVG only
    else close.textContent = '×';
    close.addEventListener('click', function () {
      remember(n.id);
      host.hidden = true;
      host.textContent = '';
    });
    host.appendChild(close);
    host.hidden = false;
  }

  // → Promise<news | null> (null = nothing shown)
  function twNewsBanner(host) {
    if (!host || typeof window.twApi !== 'function') return Promise.resolve(null);
    host.hidden = true;
    return twApi('/news/banner', { auth: false }).then(function (res) {
      var n = res && res.ok ? res.data : null;
      if (!n || typeof n !== 'object' || n.id == null || !n.title) return null;
      if (closedId() === String(n.id)) return null;
      render(host, n);
      return n;
    }, function () { return null; });
  }

  function mountAll() {
    var hosts = document.querySelectorAll('[data-tw-news-banner]');
    for (var i = 0; i < hosts.length; i++) twNewsBanner(hosts[i]);
  }

  window.twNewsBanner = twNewsBanner;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountAll);
  else mountAll();
})();
