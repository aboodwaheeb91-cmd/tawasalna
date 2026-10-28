/* home.posts.js — company posts in the feed (task 8.6b-2 · DS-CARD §61 · comments §22c)
 *
 * One controller per page: TwPostCard.create (appreciate · save · views · share · comments panel)
 * + TwPostComments.create (the comments inside the feed). The cards come from
 * Home.cards.renderPostCard (TwPostCard.html). Nothing here navigates — every card button and
 * the comments panel stay on /home; only the author name / avatar link to /u/{tw_id}.
 *   bind(feedEl)          → click delegation on the feed list, once
 *   remember(items)       → the posts of this render (author for mention suggestions / share)
 *   afterRender(feedEl)   → 3-line clamp + view tracking, after every render
 */
(function () {
  'use strict';
  window.Home = window.Home || {};

  var _posts = {};   // post id → feed item of the current render

  /* The page's session (TwAuthSync snapshot — /home is protected by twRequireAuth) */
  function signedIn() {
    var snap = window.TwAuthSync && TwAuthSync.getSessionSnapshot();
    return !!(snap && snap.isAuthenticated);
  }

  function postPath(id, action) {
    return '/company/posts/' + encodeURIComponent(id) + '/' + action;
  }

  var comments = TwPostComments.create({
    signedIn: signedIn,
    postOwner: function (id) {   // the post's company joins the @mention suggestions
      var it = _posts[String(id)];
      return it ? { full_name: it.author_name, tw_id: it.author_tw_id, avatar_url: it.author_avatar } : null;
    }
  });

  var card = TwPostCard.create({
    signedIn: signedIn,
    paths: {
      appreciation: function (id) { return postPath(id, 'appreciation'); },
      save:         function (id) { return postPath(id, 'save'); },
      view:         function (id) { return postPath(id, 'view'); }
    },
    visitorKeyName: 'cp_vk',
    shareInfo: function (id) {   // same text as the company page: company name + its /u/{tw_id}
      var it = _posts[String(id)] || {};
      var url = it.author_tw_id ? (location.origin || '') + twAccountHref({ tw_id: it.author_tw_id }) : location.href;
      return { name: it.author_name || '', url: url };
    },
    comments: { build: comments.build, load: comments.load }
  });

  var _bound = false;

  window.Home.posts = {
    bind: function (feedEl) {
      if (_bound || !feedEl) return;
      _bound = true;
      card.bind(feedEl);
    },

    remember: function (items) {
      _posts = {};
      (items || []).forEach(function (it) {
        if (it && it.type === 'post') _posts[String(it.id)] = it;
      });
    },

    /* Two rAFs (as the company page): layout first, then fonts are measured */
    afterRender: function (feedEl) {
      if (!feedEl.querySelector('.post-card')) return;
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          TwPostCard.initClamps(feedEl);
          card.trackViews(feedEl);
        });
      });
    }
  };
}());
