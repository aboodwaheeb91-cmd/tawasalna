// Frozen copy of the pre-U.2 company post card (company.render.js @ e358a12) — golden for
// tests/test_post_card_runtime.js. Do not edit: TwPostCard.html must match it byte for byte.
  function _relativeTime(iso) {
    if (!iso) return '';
    var then = new Date(iso).getTime();
    if (isNaN(then)) return '';
    var diff = Math.floor((Date.now() - then) / 1000);
    if (diff < 60)      return 'الآن';
    if (diff < 3600)    return 'منذ ' + Math.floor(diff / 60) + ' دقيقة';
    if (diff < 86400)   return 'منذ ' + Math.floor(diff / 3600) + ' ساعة';
    if (diff < 604800)  return 'منذ ' + Math.floor(diff / 86400) + ' يوم';
    if (diff < 2592000) return 'منذ ' + Math.floor(diff / 604800) + ' أسبوع';
    return new Date(iso).toLocaleDateString('ar');
  }

  function _fmtViews(n) {
    n = Number(n) || 0;
    if (n >= 1000) { var k = n / 1000; return (k % 1 === 0 ? k : k.toFixed(1)) + 'K مشاهدة'; }
    return n + ' مشاهدة';
  }

  function _postCardHtml(post) {
    var coName    = (window.companyState && companyState.profile)
      ? (companyState.profile.full_name || 'الشركة') : 'الشركة';
    var avatarUrl = twSafeImageUrl((window.companyState && companyState.profile)
      ? companyState.profile.avatar_url : '');

    // Resolve theme color — null/unknown → teal
    var colorKey = (post.theme_color && window.TW && TW.POST_THEME_COLORS && TW.POST_THEME_COLORS[post.theme_color])
      ? post.theme_color : 'teal';
    var clr = (window.TW && TW.POST_THEME_COLORS && TW.POST_THEME_COLORS[colorKey])
      || { accent: 'var(--color-categorical-teal)', soft: 'rgba(var(--color-categorical-teal-rgb),.12)', glow: 'rgba(var(--color-categorical-teal-rgb),.18)' };
    var cardStyle = '--pa:' + clr.accent + '; --pa-s:' + clr.soft + '; --pa-g:' + clr.glow;

    // Avatar: real logo or initial letter
    var avaContent = avatarUrl
      ? '<img src="' + _escAttr(avatarUrl) + '" alt="">'
      : '<span class="post-ava--init">' + _esc((coName || '?').charAt(0)) + '</span>';

    // Tags — use themed class so they inherit --pa from the card
    var tagsHtml = '';
    if (post.tags && post.tags.length) {
      tagsHtml = '<div class="job-tags">' + post.tags.map(function (t) {
        return '<span class="jtag jtag-themed">' + _esc(t) + '</span>';
      }).join('') + '</div>';
    }

    // 3-dot owner menu
    var canEdit = window.companyState &&
      companyState.permissions && companyState.permissions.can_edit;
    var pid = _escAttr(String(post.id));
    var icoEdit   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';
    var icoTrash  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>';
    var dotsHtml = canEdit
      ? '<div class="pc-dots">'
          + '<button class="pc-dots-btn" data-post-id="' + pid + '" aria-label="خيارات">&#8943;</button>'
          + '<div class="pc-dots-menu" id="pc-dm-' + pid + '">'
            + '<button class="pc-dots-edit" data-post-id="' + pid + '">' + icoEdit + 'تعديل</button>'
            + '<button class="pc-dots-delete" data-post-id="' + pid + '">' + icoTrash + 'حذف</button>'
          + '</div>'
        + '</div>'
      : '';

    // Inline SVGs
    var icoEye         = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
    var icoClock       = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
    var icoShare       = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>';
    var icoHeartOutline = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';
    var icoHeartFilled  = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';
    var icoComment     = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
    var icoBookmark       = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>';
    var icoBookmarkCheck  = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/><path d="M8.5 10l2.5 2.5 5-5" fill="none" stroke="var(--color-surface-page)" stroke-width="2"/></svg>';

    return '<div class="post-card" data-post-id="' + pid + '" style="' + cardStyle + '">'
      + '<div class="post-head">'
        + '<div class="post-ava">' + avaContent + '</div>'
        + '<div class="post-head-info">'
          + '<div class="post-nm">' + _esc(coName) + '</div>'
          + '<div class="post-meta-row">'
            + '<span class="post-date">' + icoClock + _relativeTime(post.created_at) + '</span>'
            + '<span class="post-views" data-views-count="' + (Number(post.views_count) || 0) + '">' + icoEye + _fmtViews(post.views_count) + '</span>'
          + '</div>'
        + '</div>'
        + dotsHtml
      + '</div>'
      + '<div class="post-body-wrap">'
        + '<div class="post-body">'
          + '<span class="post-body-text">' + _esc(post.body) + '</span>'
          + '<button type="button" class="post-more-inline" aria-label="عرض المزيد">'
            + '<span class="post-more-ellipsis">…</span>'
            + '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 8v8"/><path d="m8 12 4 4 4-4"/></svg>'
          + '</button>'
        + '</div>'
        + '<button type="button" class="post-less-btn" aria-label="عرض أقل">'
          + '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="m16 12-4-4-4 4"/><path d="M12 16V8"/></svg>'
        + '</button>'
      + '</div>'
      + tagsHtml
      + (function () {
          var appCount = Number(post.appreciations_count) || 0;
          var appActive = post.viewer_appreciated === true || post.viewer_appreciated === 'true' || post.viewer_appreciated === 1;
          var apprCls = 'pc-btn pc-btn--appr' + (appActive ? ' appr-active' : '');
          var apprIco = appActive ? icoHeartFilled : icoHeartOutline;
          var apprLabel = appCount > 0 ? ('أقدّر · ' + appCount) : 'أقدّر';
          return '<div class="pc-actions">'
            + '<button class="' + apprCls + '" data-post-id="' + pid + '" data-appr-count="' + appCount + '">' + apprIco + apprLabel + '</button>'
            + (post.comments_enabled !== false ? (function() {
                var cmtCount = Number(post.comments_count) || 0;
                var cmtLabel = cmtCount > 0 ? ('تعليق · ' + cmtCount) : 'تعليق';
                return '<button class="pc-btn pc-btn--cmt" data-post-id="' + pid + '" data-cmt-count="' + cmtCount + '">' + icoComment + cmtLabel + '</button>';
              })() : '')
            + '<button class="pc-btn pc-btn--share" data-post-id="' + pid + '">' + icoShare    + 'مشاركة</button>'
            + (function () {
                var saveActive = post.viewer_saved === true || post.viewer_saved === 'true' || post.viewer_saved === 1;
                var saveCls  = 'pc-btn pc-btn--save' + (saveActive ? ' save-active' : '');
                var saveIco  = saveActive ? icoBookmarkCheck : icoBookmark;
                return '<button class="' + saveCls + '" data-post-id="' + pid + '" data-saved="' + (saveActive ? '1' : '0') + '">' + saveIco + (saveActive ? 'محفوظ' : 'حفظ') + '</button>';
              })()
            + '</div>';
        })()
      + (post.comments_enabled !== false ? '<div class="pc-cmts-panel" id="pc-cmt-panel-' + pid + '" data-post-id="' + pid + '" style="display:none"></div>' : '')
    + '</div>';
  }


// pre-U.2 company.posts.js button re-render (D2 / D3)
  var _ICO_BOOKMARK_OUTLINE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>';
  var _ICO_BOOKMARK_CHECK   = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/><path d="M8.5 10l2.5 2.5 5-5" fill="none" stroke="var(--color-surface-page)" stroke-width="2"/></svg>';

  function _renderSaveButton(btn, active) {
    btn.innerHTML = (active ? _ICO_BOOKMARK_CHECK : _ICO_BOOKMARK_OUTLINE) + (active ? 'محفوظ' : 'حفظ');
    if (active) { btn.classList.add('save-active');    }
    else        { btn.classList.remove('save-active'); }
    btn.dataset.saved = active ? '1' : '0';
  }

  var _ICO_HEART_OUTLINE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';
  var _ICO_HEART_FILLED  = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';

  function _renderAppreciationButton(btn, active, count) {
    var ico   = active ? _ICO_HEART_FILLED : _ICO_HEART_OUTLINE;
    var label = count > 0 ? ('أقدّر · ' + count) : 'أقدّر';
    if (active) { btn.classList.add('appr-active');    }
    else        { btn.classList.remove('appr-active'); }
    btn.dataset.apprCount = count;
    btn.innerHTML = ico + label;
  }

