/* home-v2.js — Feed-first home page logic */
(function () {
  'use strict';

  /* ── Auth guard ── */
  var _u = null, _jwt = '';
  try {
    _u   = JSON.parse(localStorage.getItem('tw_user') || 'null');
    _jwt = localStorage.getItem('tw_jwt') || '';
  } catch (e) {}
  if (!_u || !_u.id) { location.replace('/login'); return; }

  var type     = _u.user_type || 'emp';
  var fullName = _u.full_name || _u.name || _u.email || 'مستخدم';
  var initial  = fullName.charAt(0).toUpperCase();

  function getProfileUrl(u) {
    return u.tw_id ? '/u/' + u.tw_id : '/profile';
  }

  /* ── Helpers ── */
  var JOB_TYPES = {
    full_time: 'دوام كامل', part_time: 'دوام جزئي',
    remote: 'عن بُعد', contract: 'عقد', internship: 'تدريب'
  };

  function timeAgo(iso) {
    if (!iso) return '';
    var diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60)      return 'الآن';
    if (diff < 3600)    return Math.floor(diff / 60) + ' د';
    if (diff < 86400)   return Math.floor(diff / 3600) + ' س';
    if (diff < 2592000) return Math.floor(diff / 86400) + ' ي';
    if (diff < 31536000)return Math.floor(diff / 2592000) + ' ش';
    return Math.floor(diff / 31536000) + ' سنة';
  }

  function el(tag, cls) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    return e;
  }

  function txt(tag, cls, content) {
    var e = el(tag, cls);
    e.textContent = content;
    return e;
  }

  /* safe avatar: if url exists use img, else initials div */
  function makeAvatar(cls, name, avatarUrl) {
    var wrap = el('div', cls);
    if (avatarUrl) {
      var img = el('img');
      img.alt = '';
      img.setAttribute('loading', 'lazy');
      /* only absolute URLs from our own API are allowed */
      img.src = avatarUrl;
      wrap.appendChild(img);
    } else {
      wrap.textContent = (name || '?').charAt(0).toUpperCase();
    }
    return wrap;
  }

  /* ── Card renderers (all use createElement + textContent, NO innerHTML from API) ── */

  function renderJobCard(item) {
    var art = el('article', 'hw-card');

    var head = el('div', 'hw-jhead');
    var logo = el('div', 'hw-jlogo');
    if (item.company_logo) {
      var img = el('img');
      img.alt = '';
      img.setAttribute('loading', 'lazy');
      img.src = item.company_logo;
      logo.appendChild(img);
    } else {
      var icoEl = el('i');
      icoEl.setAttribute('data-lucide', 'building-2');
      icoEl.setAttribute('width', '20');
      icoEl.setAttribute('height', '20');
      logo.appendChild(icoEl);
    }
    head.appendChild(logo);

    var info = el('div', 'hw-jinfo');
    info.appendChild(txt('div', 'hw-jtitle', item.title || ''));
    info.appendChild(txt('div', 'hw-jco', item.company_name || ''));
    head.appendChild(info);
    art.appendChild(head);

    var meta = el('div', 'hw-jmeta');
    if (item.location) meta.appendChild(txt('span', 'hw-chip', item.location));
    if (item.job_type) meta.appendChild(txt('span', 'hw-chip', JOB_TYPES[item.job_type] || item.job_type));
    if (item.salary_min) {
      meta.appendChild(txt('span', 'hw-chip g', item.salary_min + (item.salary_max ? '–' + item.salary_max : '+') + ' ' + (item.currency || '')));
    }
    art.appendChild(meta);

    var foot = el('div', 'hw-jfoot');
    foot.appendChild(txt('span', 'hw-ts', timeAgo(item.created_at)));
    var applyLink = el('a', 'hw-btn g');
    applyLink.textContent = 'عرض الوظيفة';
    applyLink.href = '/job-detail?id=' + parseInt(item.id, 10);
    foot.appendChild(applyLink);
    art.appendChild(foot);

    return art;
  }

  function renderPostCard(item) {
    var art = el('article', 'hw-card');

    var head = el('div', 'hw-phead');
    head.appendChild(makeAvatar('hw-pav', item.author_name, item.author_avatar));
    var meta = el('div');
    meta.appendChild(txt('div', 'hw-pname', item.author_name || ''));
    meta.appendChild(txt('div', 'hw-psub', timeAgo(item.created_at)));
    head.appendChild(meta);
    art.appendChild(head);

    art.appendChild(txt('div', 'hw-pbody', item.body || ''));

    var foot = el('div', 'hw-pfoot');
    var shareAct = el('span', 'hw-pact');
    var shareIco = el('i');
    shareIco.setAttribute('data-lucide', 'share-2');
    shareIco.setAttribute('width', '13');
    shareIco.setAttribute('height', '13');
    shareAct.appendChild(shareIco);
    shareAct.appendChild(document.createTextNode(' مشاركة'));
    foot.appendChild(shareAct);
    art.appendChild(foot);

    /* link the card to the company profile */
    if (item.author_tw_id) {
      art.style.cursor = 'pointer';
      art.addEventListener('click', function (ev) {
        if (ev.target.closest('a,button')) return;
        location.href = '/u/' + item.author_tw_id;
      });
    }

    return art;
  }

  function renderSuggestedCard(item) {
    var art = el('article', 'hw-card');
    var wrap = el('div', 'hw-scard');
    wrap.appendChild(makeAvatar('hw-sav', item.name, item.avatar_url));
    var info = el('div', 'hw-sinfo');
    info.appendChild(txt('div', 'hw-sname', item.name || ''));
    info.appendChild(txt('div', 'hw-ssub', item.headline || (item.user_type === 'edu' ? 'مؤسسة تعليمية' : 'شركة')));
    wrap.appendChild(info);
    if (item.tw_id) {
      var viewLink = el('a', 'hw-btn out');
      viewLink.textContent = 'عرض';
      viewLink.href = '/u/' + item.tw_id;
      wrap.appendChild(viewLink);
    }
    art.appendChild(wrap);
    return art;
  }

  function renderCard(item) {
    if (item.type === 'job')     return renderJobCard(item);
    if (item.type === 'post')    return renderPostCard(item);
    if (item.type === 'company') return renderSuggestedCard(item);
    return null;
  }

  /* ── Skeleton HTML (static, no API data) ── */
  function renderSkeletons() {
    var frag = document.createDocumentFragment();

    function skCard(inner) {
      var c = el('div', 'hw-card');
      c.innerHTML = inner; /* safe: no API data, purely static markup */
      frag.appendChild(c);
    }

    skCard('<div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:12px"><div class="hw-skr" style="width:44px;height:44px;flex-shrink:0"></div><div style="flex:1;display:flex;flex-direction:column;gap:7px"><div class="hw-skl" style="height:14px;width:62%"></div><div class="hw-skl" style="height:11px;width:38%"></div></div></div><div style="display:flex;gap:7px;margin-bottom:14px"><div class="hw-skl" style="height:22px;width:68px;border-radius:12px"></div><div class="hw-skl" style="height:22px;width:52px;border-radius:12px"></div></div><div style="display:flex;justify-content:space-between;align-items:center"><div class="hw-skl" style="height:10px;width:76px"></div><div class="hw-skl" style="height:30px;width:82px;border-radius:20px"></div></div>');
    skCard('<div style="display:flex;gap:10px;align-items:center;margin-bottom:12px"><div class="hw-skc" style="width:38px;height:38px;flex-shrink:0"></div><div style="flex:1;display:flex;flex-direction:column;gap:6px"><div class="hw-skl" style="height:13px;width:42%"></div><div class="hw-skl" style="height:10px;width:26%"></div></div></div><div style="display:flex;flex-direction:column;gap:6px"><div class="hw-skl" style="height:12px;width:100%"></div><div class="hw-skl" style="height:12px;width:88%"></div><div class="hw-skl" style="height:12px;width:72%"></div></div>');
    skCard('<div style="display:flex;align-items:center;gap:12px"><div class="hw-skc" style="width:46px;height:46px;flex-shrink:0"></div><div style="flex:1;display:flex;flex-direction:column;gap:7px"><div class="hw-skl" style="height:13px;width:55%"></div><div class="hw-skl" style="height:10px;width:38%"></div></div><div class="hw-skl" style="height:30px;width:74px;border-radius:20px;flex-shrink:0"></div></div>');

    return frag;
  }

  /* ── Feed state machine ── */
  var feedEl    = document.getElementById('hwFeed');
  var emptyEl   = document.getElementById('hwEmpty');
  var errorEl   = document.getElementById('hwError');
  var currentFilter = 'all';
  var _abortCtrl = null;

  function showSkeleton() {
    feedEl.innerHTML = '';
    feedEl.appendChild(renderSkeletons());
    feedEl.classList.remove('hidden');
    emptyEl.classList.add('hidden');
    errorEl.classList.add('hidden');
    if (window.lucide) lucide.createIcons();
  }

  function showEmpty(filter) {
    var LABELS = {
      all:'لا يوجد محتوى بعد', jobs:'لا توجد وظائف حالياً',
      posts:'لا توجد منشورات بعد', companies:'لا توجد شركات بعد'
    };
    feedEl.innerHTML = '';
    feedEl.classList.add('hidden');
    var h3 = emptyEl.querySelector('h3');
    var p  = emptyEl.querySelector('p');
    if (h3) h3.textContent = LABELS[filter] || 'لا يوجد محتوى';
    if (p)  p.textContent  = 'ارجع لاحقاً أو جرّب فلتراً آخر';
    emptyEl.classList.remove('hidden');
    errorEl.classList.add('hidden');
  }

  function showError(retryFn) {
    feedEl.innerHTML = '';
    feedEl.classList.add('hidden');
    emptyEl.classList.add('hidden');
    errorEl.classList.remove('hidden');
    var btn = errorEl.querySelector('.hw-retry');
    if (btn) btn.onclick = retryFn;
  }

  function renderFeed(items, filter) {
    feedEl.innerHTML = '';
    if (!items || !items.length) { showEmpty(filter); return; }

    var frag = document.createDocumentFragment();
    items.forEach(function (item) {
      var card = renderCard(item);
      if (card) frag.appendChild(card);
    });
    feedEl.appendChild(frag);
    feedEl.classList.remove('hidden');
    emptyEl.classList.add('hidden');
    errorEl.classList.add('hidden');
    if (window.lucide) lucide.createIcons();
  }

  function fetchFeed(filter) {
    if (_abortCtrl) _abortCtrl.abort();
    _abortCtrl = new AbortController();
    currentFilter = filter;
    showSkeleton();

    var headers = { 'Content-Type': 'application/json' };
    if (_jwt) headers['Authorization'] = 'Bearer ' + _jwt;

    fetch('/home/feed?filter=' + encodeURIComponent(filter) + '&limit=30', {
      headers: headers,
      signal: _abortCtrl.signal
    })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        renderFeed(data.items || [], filter);
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') return;
        showError(function () { fetchFeed(filter); });
      });
  }

  /* ── Nav setup ── */
  var navAv = document.getElementById('navAv');
  if (navAv) {
    navAv.textContent = initial;
    navAv.title = fullName;
    if (type === 'emp')      navAv.href = getProfileUrl(_u);
    else if (type === 'co')  navAv.href = '/company-profile';
    else if (type === 'edu') navAv.href = '/edu-profile';
  }

  document.getElementById('btnLogout').addEventListener('click', function () {
    Object.keys(localStorage)
      .filter(function (k) { return k.startsWith('tw_'); })
      .forEach(function (k) { localStorage.removeItem(k); });
    location.replace('/login');
  });

  /* ── Filter tabs ── */
  document.querySelectorAll('.hw-ft').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var filter = btn.getAttribute('data-filter') || 'all';
      if (filter === currentFilter) return;
      document.querySelectorAll('.hw-ft').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      fetchFeed(filter);
    });
  });

  /* ── Per-type setup ── */
  var profileUrl = getProfileUrl(_u);

  if (type === 'emp') {
    document.getElementById('bnProfile').href = profileUrl;
    document.getElementById('sbComplLink').href = profileUrl;
    _sbLinks([
      { icon: 'user',      label: 'ملفي الشخصي',  href: profileUrl },
      { icon: 'briefcase', label: 'تصفح الوظائف', href: '/home' },
      { icon: 'book-open', label: 'الدورات',       href: '/home' },
      { icon: 'settings',  label: 'الإعدادات',     href: '/settings' },
    ]);

  } else if (type === 'co') {
    document.getElementById('bnProfile').href = '/company-profile';
    document.getElementById('bnProfileLbl').textContent = 'شركتي';
    document.getElementById('bnJobs').href = '/company-profile';
    document.getElementById('bnJobsLbl').textContent = 'وظائفي';
    document.getElementById('sbComplLink').href = '/company-profile';
    _banner('briefcase', 'وظائف شركتك', 'تابع وظائفك المنشورة والمتقدمين', [
      { v: '—', l: 'وظيفة نشطة' }, { v: '—', l: 'متقدم جديد' },
    ]);
    _sbLinks([
      { icon: 'layout-dashboard', label: 'لوحة التحكم', href: '/company-profile' },
      { icon: 'users',            label: 'المرشحون',     href: '/company' },
      { icon: 'plus-circle',      label: 'نشر وظيفة',   href: '/company-profile' },
      { icon: 'settings',         label: 'الإعدادات',   href: '/settings' },
    ]);

  } else if (type === 'edu') {
    document.getElementById('bnProfile').href = '/edu-profile';
    document.getElementById('bnProfileLbl').textContent = 'مؤسستي';
    document.getElementById('bnJobsIco').setAttribute('data-lucide', 'book-open');
    document.getElementById('bnJobs').href = '/edu-profile';
    document.getElementById('bnJobsLbl').textContent = 'دوراتي';
    document.getElementById('sbComplLink').href = '/edu-profile';
    _banner('graduation-cap', 'دورات مؤسستك', 'تابع الدورات المنشورة وطلبات التوثيق', [
      { v: '—', l: 'دورة نشطة' }, { v: '—', l: 'طلب توثيق' },
    ]);
    _sbLinks([
      { icon: 'layout-dashboard', label: 'لوحة التحكم',   href: '/edu-profile' },
      { icon: 'book-open',        label: 'الدورات',         href: '/edu' },
      { icon: 'shield-check',     label: 'طلبات التوثيق', href: '/edu-profile' },
      { icon: 'settings',         label: 'الإعدادات',       href: '/settings' },
    ]);
  }

  /* ── Initial load ── */
  if (window.lucide) lucide.createIcons();
  fetchFeed('all');

  /* ── Helpers ── */
  function _banner(ico, title, sub, stats) {
    var el2 = document.getElementById('hwBanner');
    if (!el2) return;
    el2.classList.remove('hidden');
    document.getElementById('hwBIco').setAttribute('data-lucide', ico);
    document.getElementById('hwBTitle').textContent = title;
    document.getElementById('hwBSub').textContent = sub;
    var statsEl = document.getElementById('hwBStats');
    statsEl.innerHTML = '';
    stats.forEach(function (s) {
      var d = document.createElement('div');
      d.className = 'hw-bstat';
      var strong = document.createElement('strong');
      strong.textContent = s.v;
      var span = document.createElement('span');
      span.textContent = s.l;
      d.appendChild(strong);
      d.appendChild(span);
      statsEl.appendChild(d);
    });
    if (window.lucide) lucide.createIcons();
  }

  function _sbLinks(links) {
    var c = document.getElementById('sbLinks');
    if (!c) return;
    c.innerHTML = '';
    links.forEach(function (l) {
      var a = document.createElement('a');
      a.className = 'hw-sb-lnk';
      a.href = l.href;
      var ico = document.createElement('i');
      ico.setAttribute('data-lucide', l.icon);
      ico.setAttribute('width', '15');
      ico.setAttribute('height', '15');
      var span = document.createElement('span');
      span.textContent = l.label;
      a.appendChild(ico);
      a.appendChild(span);
      c.appendChild(a);
    });
    if (window.lucide) lucide.createIcons();
  }

})();
