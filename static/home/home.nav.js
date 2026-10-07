/* home.nav.js — sidebar + banner per user type for Home V2.
 * The bottom nav is the unified one (tw_shared.js _TW_BOTTOM_NAV — HEADER-NAV.md HNAV-06). */
(function () {
  'use strict';
  window.Home = window.Home || {};

  function _banner(ico, title, sub, stats) {
    var bannerEl = document.getElementById('hwBanner');
    if (!bannerEl) return;
    bannerEl.classList.remove('hidden');
    document.getElementById('hwBIco').setAttribute('data-lucide', ico);
    document.getElementById('hwBTitle').textContent = title;
    document.getElementById('hwBSub').textContent   = sub;
    var statsEl = document.getElementById('hwBStats');
    statsEl.innerHTML = '';
    stats.forEach(function (s) {
      var d      = document.createElement('div');
      d.className = 'hw-bstat';
      var strong = document.createElement('strong');
      strong.textContent = s.v;
      var span   = document.createElement('span');
      span.textContent   = s.l;
      d.appendChild(strong);
      d.appendChild(span);
      statsEl.appendChild(d);
    });
    window.Home.utils.icons();
  }

  function _sbLinks(links) {
    var c = document.getElementById('sbLinks');
    if (!c) return;
    c.innerHTML = '';
    links.forEach(function (l) {
      var a   = document.createElement('a');
      a.className  = 'hw-sb-lnk';
      a.href       = l.href;
      var ico  = document.createElement('i');
      ico.setAttribute('data-lucide', l.icon);
      ico.setAttribute('width',  '15');
      ico.setAttribute('height', '15');
      var span = document.createElement('span');
      span.textContent = l.label;
      a.appendChild(ico);
      a.appendChild(span);
      c.appendChild(a);
    });
    window.Home.utils.icons();
  }

  window.Home.nav = {
    init: function (user) {
      var type       = user.user_type || 'emp';
      var profileUrl = user.tw_id ? '/u/' + user.tw_id : '/profile';

      if (type === 'emp') {
        document.getElementById('sbComplLink').href  = profileUrl;
        _sbLinks([
          { icon: 'user',      label: 'ملفي الشخصي', href: profileUrl   },
          { icon: 'briefcase', label: 'تصفح الفرص',   href: '/home'      },
          { icon: 'newspaper', label: 'الأخبار',       href: '/home'      },
          { icon: 'settings',  label: 'الإعدادات',     href: '/settings'  },
        ]);

      } else if (type === 'co') {
        var _coUrl = user.tw_id ? '/u/' + user.tw_id : '/company-profile';
        document.getElementById('sbComplLink').href         = _coUrl;
        _banner('briefcase', 'فرص شركتك', 'تابع الفرص المنشورة والمتقدمين', [
          { v: '—', l: 'فرصة نشطة' }, { v: '—', l: 'متقدم جديد' }
        ]);
        _sbLinks([
          { icon: 'layout-dashboard', label: 'لوحة التحكم', href: _coUrl          },
          { icon: 'users',            label: 'بنك المواهب',  href: twTalentBankHref(user) },
          { icon: 'plus-circle',      label: 'نشر فرصة',    href: _coUrl          },
          { icon: 'settings',         label: 'الإعدادات',    href: '/settings'     },
        ]);

      } else if (type === 'edu') {
        document.getElementById('sbComplLink').href         = '/edu-profile';
        _banner('graduation-cap', 'دورات مؤسستك', 'تابع الدورات المنشورة وطلبات التوثيق', [
          { v: '—', l: 'دورة نشطة' }, { v: '—', l: 'طلب توثيق' }
        ]);
        _sbLinks([
          { icon: 'layout-dashboard', label: 'لوحة التحكم',    href: '/edu-profile' },
          { icon: 'book-open',        label: 'الدورات',          href: '/edu-profile' },
          { icon: 'shield-check',     label: 'طلبات التوثيق',  href: '/edu-profile' },
          { icon: 'settings',         label: 'الإعدادات',        href: '/settings'    },
        ]);
      }
    }
  };
}());
