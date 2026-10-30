/* home.posts.js — company posts in the feed (task 8.6b-2 · DS-CARD §61 · comments §22c)
 *
 * One controller per page: TwPostCard.create (appreciate · save · views · share · comments panel)
 * + TwPostComments.create (the comments inside the feed). The cards come from
 * Home.cards.renderPostCard (TwPostCard.html). Nothing here navigates — every card button and
 * the comments panel stay on /home; only the author name / avatar link to /u/{tw_id}.
 *   bind(feedEl)          → click delegation on the feed list, once
 *   remember(items, append) → the posts on screen (author for mention suggestions / share) —
 *                           append («عرض المزيد») adds to them, otherwise they start over
 *   afterRender(feedEl, cards) → 3-line clamp of the new cards only + view tracking, after every render
 */
(function () {
  'use strict';
  window.Home = window.Home || {};

  var _posts = {};   // post id → feed item of the cards on screen

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

    remember: function (items, append) {
      if (!append) _posts = {};
      (items || []).forEach(function (it) {
        if (it && it.type === 'post') _posts[String(it.id)] = it;
      });
    },

    /* Two rAFs (as the company page): layout first, then fonts are measured.
     * Clamp runs on the new cards only (a second pass would re-cut an opened post); trackViews
     * replaces its one observer over every post card — a post already counted is never sent again. */
    afterRender: function (feedEl, cards) {
      var fresh = (cards || []).filter(function (c) { return c.classList.contains('post-card'); });
      if (!fresh.length) return;
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          fresh.forEach(function (c) { TwPostCard.initClamps(c); });
          card.trackViews(feedEl);
        });
      });
    }
  };
}());
