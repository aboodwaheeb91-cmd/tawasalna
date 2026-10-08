/* home.cards.js — feed card renderers for Home V2
 *
 * ALL rendering uses createElement + textContent · texts = twT keys (home.*) ·
 * icons = DS-ICON (twIconEl) · logo / avatar = DS-IMAGE (twAvatarEl — URL via twSafeImageUrl).
 * innerHTML is FORBIDDEN for any API-supplied field.
 * The only innerHTML usage is in home.render.js for static skeleton markup.
 */
(function () {
  'use strict';
  window.Home = window.Home || {};

  var U = window.Home.utils;

  window.Home.cards = {

    renderOpportunityCard: function (item) {
      var art  = U.el('article', 'hw-card');
      var head = U.el('div', 'hw-jhead');

      head.appendChild(twAvatarEl({ full_name: item.company_name, avatar_url: item.company_logo, user_type: 'co' }, 'md'));

      var info = U.el('div', 'hw-jinfo');
      info.appendChild(U.txt('div', 'hw-jtitle', item.title || ''));
      info.appendChild(U.txt('div', 'hw-jco',    item.company_name || ''));
      head.appendChild(info);
      art.appendChild(head);

      var meta = U.el('div', 'hw-jmeta');
      if (item.profession_name_ar) {
        var pchip = U.el('span', 'hw-chip hw-chip--prof');
        pchip.appendChild(U.icon(item.profession_icon || 'briefcase', 'xs'));
        pchip.appendChild(document.createTextNode(' ' + item.profession_name_ar));
        meta.appendChild(pchip);
      }
      if (item.accepts_all_professions) {
        var apchip = U.el('span', 'hw-chip hw-chip--open');
        apchip.appendChild(U.icon('users', 'xs'));
        apchip.appendChild(document.createTextNode(' ' + twT('home.card.all_professions')));
        meta.appendChild(apchip);
      } else if (item.accepted_professions && item.accepted_professions.length) {
        var apchip = U.el('span', 'hw-chip');
        apchip.appendChild(U.icon('users', 'xs'));
        apchip.appendChild(document.createTextNode(' ' + twT('home.card.more_professions', { n: item.accepted_professions.length })));
        meta.appendChild(apchip);
      }
      if (item.location)   meta.appendChild(U.txt('span', 'hw-chip',   item.location));
      if (item.job_type)   meta.appendChild(U.txt('span', 'hw-chip',   U.jobType(item.job_type)));
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
      link.textContent = twT('home.card.view_job');
      link.href = '/job-detail?id=' + U.safeInt(item.id);
      foot.appendChild(link);
      art.appendChild(foot);

      return art;
    },

    renderPostCard: function (item) {
      var art  = U.el('article', 'hw-card');
      var head = U.el('div', 'hw-phead');
      head.appendChild(twAvatarEl({ full_name: item.author_name, avatar_url: item.author_avatar }, 'md'));
      var meta = U.el('div');
      meta.appendChild(U.txt('div', 'hw-pname', item.author_name || ''));
      meta.appendChild(U.txt('div', 'hw-psub',  U.timeAgo(item.created_at)));
      head.appendChild(meta);
      art.appendChild(head);

      art.appendChild(U.txt('div', 'hw-pbody', item.body || ''));

      var foot     = U.el('div', 'hw-pfoot');
      var shareAct = U.el('span', 'hw-pact');
      shareAct.appendChild(U.icon('share', 'xs'));
      shareAct.appendChild(document.createTextNode(' ' + twT('home.card.share')));
      foot.appendChild(shareAct);
      art.appendChild(foot);

      if (item.author_tw_id) {
        art.style.cursor = 'pointer';
        art.addEventListener('click', function (ev) {
          if (ev.target.closest('a,button')) return;
          location.href = twAccountHref({ tw_id: item.author_tw_id });
        });
      }

      return art;
    },

    renderNewsCard: function (item) {
      var art  = U.el('article', 'hw-card');
      var head = U.el('div', 'hw-nhead');
      var nico = U.el('div', 'hw-nico');
      nico.appendChild(U.icon('newspaper', 'sm'));
      head.appendChild(nico);

      var ninfo = U.el('div', 'hw-ninfo');
      ninfo.appendChild(U.txt('div', 'hw-ntitle', item.title || ''));
      var nmeta = U.el('div', 'hw-nmeta');
      if (item.category) nmeta.appendChild(U.txt('span', 'hw-ncat',     U.newsCat(item.category)));
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
        expandBtn.textContent = twT('home.card.read_more');
        expandBtn.addEventListener('click', function () {
          var open = bodyEl.classList.toggle('open');
          expandBtn.textContent = twT(open ? 'home.card.read_less' : 'home.card.read_more');
        });
        foot.appendChild(expandBtn);
      }

      var _srcUrl = twSafeLinkUrl(item.source_url || '');   // §54 rule 4b
      if (_srcUrl) {
        var srcLink = U.el('a', 'hw-nbtn src');
        srcLink.textContent = twT('home.card.source');
        srcLink.href        = _srcUrl;
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
