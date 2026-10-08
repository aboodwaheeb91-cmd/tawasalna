/* home.nav.js — sidebar + banner per user type for Home V2.
 * The bottom nav is the unified one (tw_shared.js _TW_BOTTOM_NAV — HEADER-NAV.md HNAV-06).
 * Links: the account page is twAccountHref(user) (/u/{tw_id}) — never a legacy route.
 * Numbers come from the API only; a number with no API is not shown. */
(function () {
  'use strict';
  window.Home = window.Home || {};

  function _banner(icon, titleKey, subKey) {
    var bannerEl = document.getElementById('hwBanner');
    if (!bannerEl) return;
    var ico = document.getElementById('hwBIco');
    ico.textContent = '';
    ico.appendChild(window.Home.utils.icon(icon, 'lg'));
    document.getElementById('hwBTitle').textContent = twT(titleKey);
    document.getElementById('hwBSub').textContent   = twT(subKey);
    bannerEl.classList.remove('hidden');
  }

  function _bannerStat(value, labelKey) {
    var statsEl = document.getElementById('hwBStats');
    if (!statsEl) return;
    var d      = document.createElement('div');
    d.className = 'hw-bstat';
    var strong = document.createElement('strong');
    strong.textContent = String(value);
    var span   = document.createElement('span');
    span.textContent   = twT(labelKey);
    d.appendChild(strong);
    d.appendChild(span);
    statsEl.appendChild(d);
    statsEl.classList.remove('hidden');
  }

  function _sbLinks(links) {
    var c = document.getElementById('sbLinks');
    if (!c) return;
    c.textContent = '';
    links.forEach(function (l) {
      var a   = document.createElement('a');
      a.className  = 'hw-sb-lnk';
      a.href       = l.href;
      a.appendChild(window.Home.utils.icon(l.icon, 'sm'));
      var span = document.createElement('span');
      span.textContent = twT(l.labelKey);
      a.appendChild(span);
      c.appendChild(a);
    });
  }

  /* Completion box (emp) — score from GET /profile/{id}/score; hidden until it loads / on failure */
  function _completion(user, accountUrl) {
    window.Home.api.loadScore(user.id).then(function (sc) {
      if (!sc) return;
      var pct = Math.max(0, Math.min(100, Math.round(sc.score)));
      document.getElementById('sbFill').style.width = pct + '%';
      document.getElementById('sbPct').textContent  = twT('home.completion.pct', { n: pct });
      document.getElementById('sbComplLink').href   = accountUrl;
      document.getElementById('sbComplBox').classList.remove('hidden');
    });
  }

  window.Home.nav = {
    init: function (user) {
      var type       = user.user_type;
      var accountUrl = twAccountHref(user);

      if (type === 'emp') {
        _completion(user, accountUrl);
        _sbLinks([
          { icon: 'user',      labelKey: 'home.link.my_profile', href: accountUrl  },
          { icon: 'briefcase', labelKey: 'home.link.browse_jobs', href: '/home'    },
          { icon: 'newspaper', labelKey: 'home.filter.news',     href: '/home'     },
          { icon: 'settings',  labelKey: 'menu.settings',        href: '/settings' }
        ]);

      } else if (type === 'co') {
        _banner('briefcase', 'home.banner.co_title', 'home.banner.co_sub');
        window.Home.api.loadActiveJobsCount().then(function (n) {
          if (n !== null) _bannerStat(n, 'home.banner.active_jobs');
        });
        _sbLinks([
          { icon: 'layout-dashboard', labelKey: 'home.link.dashboard',  href: accountUrl             },
          { icon: 'users',            labelKey: 'people.talent_bank',   href: twTalentBankHref(user) },
          { icon: 'plus-circle',      labelKey: 'jobs.post',            href: accountUrl             },
          { icon: 'settings',         labelKey: 'menu.settings',        href: '/settings'            }
        ]);

      } else if (type === 'edu') {
        _banner('graduation-cap', 'home.banner.edu_title', 'home.banner.edu_sub');
        _sbLinks([
          { icon: 'layout-dashboard', labelKey: 'home.link.dashboard',  href: accountUrl  },
          { icon: 'book-open',        labelKey: 'home.link.courses',    href: accountUrl  },
          { icon: 'shield-check',     labelKey: 'home.link.verify_req', href: accountUrl  },
          { icon: 'settings',         labelKey: 'menu.settings',        href: '/settings' }
        ]);
      }
    }
  };
}());
