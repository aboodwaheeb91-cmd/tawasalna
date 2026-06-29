/* home.cards.js — feed card renderers for Home V2
 *
 * ALL rendering uses createElement + textContent.
 * innerHTML is FORBIDDEN for any API-supplied field.
 * The only innerHTML usage is in home.render.js for static skeleton markup.
 */
(function () {
  'use strict';
  window.Home = window.Home || {};

  var U = window.Home.utils;

  function _lucideIcon(name, size) {
    var i = U.el('i');
    i.setAttribute('data-lucide', name);
    i.setAttribute('width',  size || '16');
    i.setAttribute('height', size || '16');
    return i;
  }

  window.Home.cards = {

    renderOpportunityCard: function (item) {
      var art  = U.el('article', 'hw-card');
      var head = U.el('div', 'hw-jhead');

      var logo = U.el('div', 'hw-jlogo');
      if (item.company_logo) {
        var img = U.el('img');
        img.alt = '';
        img.setAttribute('loading', 'lazy');
        img.src = item.company_logo;
        logo.appendChild(img);
      } else {
        logo.appendChild(_lucideIcon('building-2', '20'));
      }
      head.appendChild(logo);

      var info = U.el('div', 'hw-jinfo');
      info.appendChild(U.txt('div', 'hw-jtitle', item.title || ''));
      info.appendChild(U.txt('div', 'hw-jco',    item.company_name || ''));
      head.appendChild(info);
      art.appendChild(head);

      var meta = U.el('div', 'hw-jmeta');
      if (item.profession_name_ar) {
        var pchip = U.el('span', 'hw-chip hw-chip--prof');
        pchip.appendChild(_lucideIcon(item.profession_icon || 'briefcase', '11'));
        pchip.appendChild(document.createTextNode(' ' + item.profession_name_ar));
        meta.appendChild(pchip);
      }
      if (item.accepts_all_professions) {
        var apchip = U.el('span', 'hw-chip hw-chip--open');
        apchip.appendChild(_lucideIcon('users', '11'));
        apchip.appendChild(document.createTextNode(' جميع التخصصات'));
        meta.appendChild(apchip);
      } else if (item.accepted_professions && item.accepted_professions.length) {
        var apchip = U.el('span', 'hw-chip');
        apchip.appendChild(_lucideIcon('users', '11'));
        apchip.appendChild(document.createTextNode(' +' + item.accepted_professions.length + ' تخصص'));
        meta.appendChild(apchip);
      }
      if (item.location)   meta.appendChild(U.txt('span', 'hw-chip',   item.location));
      if (item.job_type)   meta.appendChild(U.txt('span', 'hw-chip',   U.JOB_TYPES[item.job_type] || item.job_type));
      if (item.salary_min) {
        meta.appendChild(U.txt('span', 'hw-chip g',
          item.salary_min + (item.salary_max ? '–' + item.salary_max : '+') + ' ' + (item.currency || '')));
      }
      if (item.opp_type && item.opp_type !== 'job') {
        meta.appendChild(U.txt('span', 'hw-chip', item.opp_type));
      }
      art.appendChild(meta);

      var foot = U.el('div', 'hw-jfoot');
      foot.appendChild(U.txt('span', 'hw-ts', U.timeAgo(item.created_at)));
      var link = U.el('a', 'hw-btn g');
      link.textContent = 'عرض الفرصة';
      link.href = '/job-detail?id=' + U.safeInt(item.id);
      foot.appendChild(link);
      art.appendChild(foot);

      return art;
    },

    renderPostCard: function (item) {
      var art  = U.el('article', 'hw-card');
      var head = U.el('div', 'hw-phead');
      head.appendChild(U.makeAvatar('hw-pav', item.author_name, item.author_avatar));
      var meta = U.el('div');
      meta.appendChild(U.txt('div', 'hw-pname', item.author_name || ''));
      meta.appendChild(U.txt('div', 'hw-psub',  U.timeAgo(item.created_at)));
      head.appendChild(meta);
      art.appendChild(head);

      art.appendChild(U.txt('div', 'hw-pbody', item.body || ''));

      var foot     = U.el('div', 'hw-pfoot');
      var shareAct = U.el('span', 'hw-pact');
      shareAct.appendChild(_lucideIcon('share-2', '13'));
      shareAct.appendChild(document.createTextNode(' مشاركة'));
      foot.appendChild(shareAct);
      art.appendChild(foot);

      if (item.author_tw_id) {
        art.style.cursor = 'pointer';
        art.addEventListener('click', function (ev) {
          if (ev.target.closest('a,button')) return;
          location.href = '/u/' + item.author_tw_id;
        });
      }

      return art;
    },

    renderNewsCard: function (item) {
      var art  = U.el('article', 'hw-card');
      var head = U.el('div', 'hw-nhead');
      var nico = U.el('div', 'hw-nico');
      nico.appendChild(_lucideIcon('newspaper', '16'));
      head.appendChild(nico);

      var ninfo = U.el('div', 'hw-ninfo');
      ninfo.appendChild(U.txt('div', 'hw-ntitle', item.title || ''));
      var nmeta = U.el('div', 'hw-nmeta');
      if (item.category) nmeta.appendChild(U.txt('span', 'hw-ncat',     U.NEWS_CATS[item.category] || item.category));
      if (item.country)  nmeta.appendChild(U.txt('span', 'hw-ncountry', item.country));
      ninfo.appendChild(nmeta);
      head.appendChild(ninfo);
      art.appendChild(head);

      if (item.summary) art.appendChild(U.txt('p', 'hw-nsummary', item.summary));

      var bodyEl = null;
      if (item.body && item.body.trim()) {
        bodyEl = U.txt('div', 'hw-nbody', item.body);
        art.appendChild(bodyEl);
      }

      var foot = U.el('div', 'hw-nfoot');
      foot.appendChild(U.txt('span', 'hw-ts', U.timeAgo(item.created_at)));

      if (bodyEl) {
        var expandBtn = U.el('button', 'hw-nbtn');
        expandBtn.textContent = 'قراءة المزيد';
        expandBtn.addEventListener('click', function () {
          var open = bodyEl.classList.toggle('open');
          expandBtn.textContent = open ? 'إخفاء' : 'قراءة المزيد';
        });
        foot.appendChild(expandBtn);
      }

      if (item.source_url && /^https?:\/\//i.test(item.source_url)) {
        var srcLink = U.el('a', 'hw-nbtn src');
        srcLink.textContent = 'المصدر الرسمي';
        srcLink.href        = item.source_url;
        srcLink.target      = '_blank';
        srcLink.rel         = 'noopener noreferrer';
        foot.appendChild(srcLink);
      }

      art.appendChild(foot);
      return art;
    },

    renderCard: function (item) {
      if (item.type === 'opportunity') return this.renderOpportunityCard(item);
      if (item.type === 'post')        return this.renderPostCard(item);
      if (item.type === 'news')        return this.renderNewsCard(item);
      return null;
    }
  };
}());
