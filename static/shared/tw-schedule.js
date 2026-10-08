// static/shared/tw-schedule.js — Schedule Interview System (PR 3.10 · SYSTEMS_INDEX §23b)
//
// One button + one dialog for every place a company schedules an interview.
//
// Usage:
//   twScheduleInterview({ candidateId?, candidateName?, jobId?, jobTitle?, applicationId?,
//                         entryId?, navigate? }) → Promise<appointment | null>
//     The dialog (DS-OVL twModal): person (search when candidateId is missing) · job (picker
//     of the company's active jobs when jobId is missing) · date + time (DS-DATE DateTime:
//     day / month / year + hour / minute / ص-م dropdowns, DS-SEL engine) · type (أونلاين +
//     link through twSafeLinkUrl / حضوري + place) · reply deadline · company rep · notes.
//     Submit: POST /api/appointments {candidate_id, job_id} (server adds the person to the
//     job's pipeline when needed — never sends application_id) → POST /{id}/send.
//     applicationId / entryId are context hints only — the server resolves the link.
//     Success → toast + 'tw:appointment-scheduled' event + room page (navigate:false = stay).
//   twScheduleButton({ candidateId, candidateName?, candidateType?, jobId?, jobTitle?,
//                      className?, navigate? }) → HTMLButtonElement | null
//     null unless the viewer is a company (TwAuthSync snapshot) looking at an emp account
//     that is not itself. An open appointment with this person (GET /api/schedule/open —
//     batched, jobId narrows it) turns it into «فتح الموعد» → the room. A draft (create
//     succeeded, send failed) keeps «تحديد موعد» and the dialog re-sends that draft.
//   twScheduleMount(root) → replaces every <span data-tw-schedule-slot data-candidate-id
//     data-candidate-name data-candidate-type data-job-id data-job-title data-class> under
//     root with twScheduleButton(...) — for pages that render cards as HTML strings.
//
// Rules: every request through twApi · text via twApiMessage · DS-COLOR / DS-SIZE tokens only ·
// loaded as a page asset after tw-overlay.js (never in the Page Shell).
// Time zone (DATE-13/14 Feature Contract): the picked date + time is the company's local
// time on its device; sent as UTC ISO (toISOString) — each side sees it in its own time.
(function () {
  'use strict';

  var STYLE_ID = 'tw-sch-style';
  var CSS = ''
    + '.tw-sch-btn{display:inline-flex;align-items:center;justify-content:center;gap:var(--space-2);'
    + 'min-height:var(--size-control-sm);padding:0 var(--space-6);border-radius:var(--radius-control);'
    + 'border:1px solid var(--color-border-strong);background:transparent;color:var(--color-brand-primary);'
    + 'font:inherit;font-size:var(--size-font-sm);font-weight:700;cursor:pointer;white-space:nowrap}'
    + '.tw-sch-btn:hover{border-color:var(--color-brand-primary)}'
    + '.tw-sch-btn:focus-visible{outline:2px solid var(--color-border-focus);outline-offset:2px}'
    // own row under a page's action buttons (employee profile — frozen .sc-actions untouched)
    + '.tw-sch-bar{display:flex;justify-content:center;padding:0 var(--space-10) var(--space-6)}'
    + '.tw-sch-form{display:flex;flex-direction:column;gap:var(--space-6);padding-bottom:var(--space-2)}'
    + '.tw-sch-f{display:flex;flex-direction:column;gap:var(--space-2)}'
    + '.tw-sch-lbl{font-size:var(--size-font-xs);font-weight:700;color:var(--color-text-secondary)}'
    + '.tw-sch-val{font-size:var(--size-font-md);color:var(--color-text-primary);font-weight:700}'
    + '.tw-sch-row{display:flex;gap:var(--space-3)}'
    + '.tw-sch-row>*{flex:1;min-width:0}'
    + '.tw-sch-in{width:100%;box-sizing:border-box;min-height:var(--size-control-md);padding:0 var(--space-5);'
    + 'border-radius:var(--radius-control);border:1px solid var(--color-border-default);'
    + 'background:var(--color-surface-input);color:var(--color-text-primary);font:inherit;font-size:var(--size-font-md)}'
    + 'textarea.tw-sch-in{min-height:72px;padding:var(--space-4) var(--space-5);resize:vertical}'
    + '.tw-sch-in:focus{outline:none;border-color:var(--color-border-focus)}'
    + '.tw-sch-in::placeholder{color:var(--color-text-placeholder)}'
    + '.tw-sch-seg{display:flex;gap:var(--space-3)}'
    + '.tw-sch-seg button{flex:1;min-height:var(--size-control-md);border-radius:var(--radius-control);'
    + 'border:1px solid var(--color-border-default);background:transparent;color:var(--color-text-secondary);'
    + 'font:inherit;font-size:var(--size-font-md);font-weight:700;cursor:pointer}'
    + '.tw-sch-seg button[aria-pressed="true"]{border-color:var(--color-brand-primary);color:var(--color-brand-primary)}'
    + '.tw-sch-res{display:flex;flex-direction:column;gap:var(--space-1);max-height:180px;overflow-y:auto}'
    + '.tw-sch-res button{display:flex;align-items:center;gap:var(--space-4);padding:var(--space-3) var(--space-4);'
    + 'border:none;border-radius:var(--radius-sm);background:transparent;color:var(--color-text-primary);'
    + 'font:inherit;font-size:var(--size-font-md);text-align:start;cursor:pointer}'
    + '.tw-sch-res button:hover,.tw-sch-res button:focus-visible{background:var(--color-surface-input);outline:none}'
    + '.tw-sch-hint{font-size:var(--size-font-xs);color:var(--color-text-muted)}'
    + '.tw-sch-pick{display:flex;align-items:center;gap:var(--space-4)}'
    + '.tw-sch-pick .tw-sch-val{flex:1}'
    + '.tw-sch-link{border:none;background:none;padding:0;color:var(--color-brand-primary);font:inherit;'
    + 'font-size:var(--size-font-sm);font-weight:700;cursor:pointer}'
    + '.tw-sch-err{font-size:var(--size-font-sm);color:var(--color-status-danger);min-height:0}'
    + '.tw-sch-err:empty{display:none}';

  var DEADLINES = [24, 48, 72, 168];          // = _APPT_DEADLINE_HOURS_ALLOWED (auth.py)
  var MINUTE_STEP = 15;                         // DATE-12 Field Contract: «موعد عام»
  var BATCH_MAX = 50;                           // = GET /api/schedule/open limit

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var s = document.createElement('style');
    s.id = STYLE_ID;
    s.textContent = CSS;
    (document.head || document.documentElement).appendChild(s);
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = String(text);
    return n;
  }

  function toast(msg, type) { if (typeof window.showToast === 'function') window.showToast(msg, type); }

  // Viewer from the TwAuthSync snapshot only (never tw_user — VM-10 / SHELL-09).
  function viewer() {
    if (!window.TwAuthSync || typeof TwAuthSync.getSessionSnapshot !== 'function') return null;
    var s = TwAuthSync.getSessionSnapshot();
    if (!s || !s.isAuthenticated) return null;
    return { type: s.userType, id: parseInt(s.userId, 10) || 0 };
  }

  // Who sees «تحديد موعد» = the Actions Registry entry `schedule` only (tw_actions.json —
  // BUTTONS.md BTN-19): company viewer · emp target · not the viewer itself (owner).
  // No inline copy of the rule (PR 3.9b): without tw_shared.js → no button (fail-closed).
  function canSchedule(candidateId, candidateType) {
    var cid = parseInt(candidateId, 10) || 0;
    if (cid <= 0 || typeof window.twActionState !== 'function') return false;
    return twActionState('schedule', { ownerId: cid, targetType: candidateType || 'emp' }) === 'enabled';
  }

  function roomHref(id) { return '/appointment-room?id=' + encodeURIComponent(id); }

  // ── Open-appointment lookup — one request per job group per tick ──────────
  var _queue = {};   // jobKey → { ids: {id: [resolve…]} }
  var _flushT = null;

  function lookupOpen(candidateId, jobId) {
    var key = jobId ? String(parseInt(jobId, 10)) : '';
    return new Promise(function (resolve) {
      var g = _queue[key] || (_queue[key] = { ids: {} });
      (g.ids[candidateId] || (g.ids[candidateId] = [])).push(resolve);
      if (!_flushT) _flushT = setTimeout(flush, 0);
    });
  }

  function flush() {
    _flushT = null;
    var q = _queue;
    _queue = {};
    Object.keys(q).forEach(function (key) {
      var ids = Object.keys(q[key].ids);
      for (var i = 0; i < ids.length; i += BATCH_MAX) {
        (function (chunk) {
          var url = '/api/schedule/open?candidate_ids=' + chunk.join(',')
            + (key ? '&job_id=' + key : '');
          twApi(url).then(function (res) {
            var data = (res.ok && res.data) || {};
            chunk.forEach(function (id) {
              q[key].ids[id].forEach(function (r) { r(data[id] || null); });
            });
          });
        })(ids.slice(i, i + BATCH_MAX));
      }
    });
  }

  // ── Button ─────────────────────────────────────────────────────────────────
  function twScheduleButton(opts) {
    opts = opts || {};
    if (!canSchedule(opts.candidateId, opts.candidateType)) return null;
    injectStyle();
    var cid = parseInt(opts.candidateId, 10);
    var btn = twAction('schedule', { ownerId: cid, targetType: opts.candidateType || 'emp', className: opts.className });
    if (!btn) return null;
    btn.type = 'button';
    btn.setAttribute('data-tw-schedule', 'new');
    var open = null;
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (open && open.status !== 'draft') { location.href = roomHref(open.id); return; }
      var o = {};
      for (var k in opts) o[k] = opts[k];
      o.draft = open;
      twScheduleInterview(o).then(function (appt) {
        if (appt) setOpen(appt);
      });
    });
    function setOpen(appt) {
      open = appt;
      if (appt && appt.status !== 'draft') {
        btn.textContent = 'فتح الموعد';
        btn.setAttribute('data-tw-schedule', 'open');
      }
    }
    lookupOpen(cid, opts.jobId).then(setOpen);
    return btn;
  }

  function twScheduleMount(root) {
    if (!root || !root.querySelectorAll) return;
    var slots = root.querySelectorAll('[data-tw-schedule-slot]');
    for (var i = 0; i < slots.length; i++) {
      var s = slots[i];
      var b = twScheduleButton({
        candidateId:   s.getAttribute('data-candidate-id'),
        candidateName: s.getAttribute('data-candidate-name') || '',
        candidateType: s.getAttribute('data-candidate-type') || 'emp',
        jobId:         parseInt(s.getAttribute('data-job-id'), 10) || null,
        jobTitle:      s.getAttribute('data-job-title') || '',
        className:     s.getAttribute('data-class') || '',
      });
      if (b) s.parentNode.replaceChild(b, s);
      else s.parentNode.removeChild(s);
    }
  }

  // ── DS-DATE DateTime group (Date: day/month/year · Time: hour/minute/ص-م) ─────
  function sel(cls, placeholder, items) {
    var s = el('select', 'tw-sch-in ep-select ' + cls);
    var ph = el('option', null, placeholder);
    ph.value = '';
    s.appendChild(ph);
    (items || []).forEach(function (it) {
      var o = el('option', null, it.label);
      o.value = String(it.value);
      s.appendChild(o);
    });
    return s;
  }

  function daysInMonth(y, m) { return new Date(y, m, 0).getDate(); }   // m = 1..12

  function monthName(m) {
    try { return new Intl.DateTimeFormat('ar-JO', { month: 'long' }).format(new Date(2000, m - 1, 1)); }
    catch (e) { return String(m); }
  }

  function buildDateTime() {
    var now = new Date();
    var y0 = now.getFullYear();
    var months = [];
    for (var m = 1; m <= 12; m++) months.push({ value: m, label: monthName(m) });
    var hours = [];
    for (var h = 1; h <= 12; h++) hours.push({ value: h, label: String(h) });
    var mins = [];
    for (var mi = 0; mi < 60; mi += MINUTE_STEP) mins.push({ value: mi, label: (mi < 10 ? '0' : '') + mi });
    // Year range (DATE-06 domain contract): this year + next year — an interview is near.
    var day = sel('tw-sch-day', 'اليوم', []);
    var mon = sel('tw-sch-mon', 'الشهر', months);
    var yr  = sel('tw-sch-yr', 'السنة', [{ value: y0, label: y0 }, { value: y0 + 1, label: y0 + 1 }]);
    var hr  = sel('tw-sch-hr', 'الساعة', hours);
    var mn  = sel('tw-sch-min', 'الدقيقة', mins);
    var ap  = sel('tw-sch-ap', 'ص / م', [{ value: 'am', label: 'صباحاً' }, { value: 'pm', label: 'مساءً' }]);

    function fillDays() {
      var y = parseInt(yr.value, 10), m = parseInt(mon.value, 10);
      var max = (y && m) ? daysInMonth(y, m) : 31;
      var keep = parseInt(day.value, 10);
      while (day.options.length > 1) day.remove(1);
      for (var d = 1; d <= max; d++) {
        var o = el('option', null, String(d));
        o.value = String(d);
        day.appendChild(o);
      }
      day.value = (keep && keep <= max) ? String(keep) : '';   // DATE-09: invalid day → empty
    }
    fillDays();
    mon.addEventListener('change', function () { day.value = ''; fillDays(); });   // DATE-09 cascade
    yr.addEventListener('change', fillDays);

    var dateRow = el('div', 'tw-sch-row');
    dateRow.appendChild(day); dateRow.appendChild(mon); dateRow.appendChild(yr);
    var timeRow = el('div', 'tw-sch-row');
    timeRow.appendChild(hr); timeRow.appendChild(mn); timeRow.appendChild(ap);

    return {
      dateRow: dateRow, timeRow: timeRow,
      // → Date (local) or null when a part is missing (DATE-18: never guessed)
      value: function () {
        var y = parseInt(yr.value, 10), m = parseInt(mon.value, 10), d = parseInt(day.value, 10);
        var h12 = parseInt(hr.value, 10), mm = parseInt(mn.value, 10);
        if (!y || !m || !d || !h12 || isNaN(mm) || !ap.value) return null;
        var h = (h12 % 12) + (ap.value === 'pm' ? 12 : 0);
        return new Date(y, m - 1, d, h, mm, 0, 0);
      },
    };
  }

  // ── Dialog ─────────────────────────────────────────────────────────────────
  function field(label, control) {
    var f = el('div', 'tw-sch-f');
    var l = el('label', 'tw-sch-lbl', label);
    f.appendChild(l);
    if (control) f.appendChild(control);
    return f;
  }

  function twScheduleInterview(opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      var v = viewer();
      if (!v || v.type !== 'co') { resolve(null); return; }
      if (typeof window.twModal !== 'function') {
        console.error('[tw-schedule] tw-overlay.js is not loaded');
        resolve(null);
        return;
      }
      injectStyle();

      var draft = opts.draft && opts.draft.status === 'draft' ? opts.draft : null;
      var st = {
        cand: opts.candidateId ? { id: parseInt(opts.candidateId, 10), name: opts.candidateName || '' } : null,
        jobId: draft ? draft.job_id : (parseInt(opts.jobId, 10) || null),
        jobTitle: draft ? (draft.job_title || '') : (opts.jobTitle || ''),
        draftId: draft ? draft.id : null,
        mode: 'online',
        result: null,
      };

      var form = el('div', 'tw-sch-form');
      var err = el('div', 'tw-sch-err');
      err.setAttribute('role', 'alert');

      // Person
      var personBox = el('div', 'tw-sch-f');
      function renderPerson() {
        personBox.innerHTML = '';
        personBox.appendChild(el('span', 'tw-sch-lbl', 'الشخص'));
        if (st.cand) {
          var pick = el('div', 'tw-sch-pick');
          pick.appendChild(el('span', 'tw-sch-val', st.cand.name || '—'));
          if (!opts.candidateId) {
            var chg = el('button', 'tw-sch-link', 'تغيير');
            chg.type = 'button';
            chg.addEventListener('click', function () { st.cand = null; renderPerson(); });
            pick.appendChild(chg);
          }
          personBox.appendChild(pick);
          return;
        }
        var q = el('input', 'tw-sch-in');
        q.type = 'search';
        q.placeholder = 'ابحث بالاسم بين المتقدمين والمرشحين والمحفوظين…';
        q.setAttribute('aria-label', 'ابحث عن الشخص بالاسم');
        var res = el('div', 'tw-sch-res');
        var hint = el('div', 'tw-sch-hint');
        personBox.appendChild(q); personBox.appendChild(res); personBox.appendChild(hint);
        var t = null, seq = 0;
        function search() {
          var my = ++seq;
          hint.textContent = 'جارٍ البحث…';
          twApi('/api/schedule/people?q=' + encodeURIComponent(q.value.trim())).then(function (r) {
            if (my !== seq) return;
            res.innerHTML = '';
            if (!r.ok) { hint.textContent = twApiMessage(r, 'تعذّر البحث، حاول مجدداً'); return; }
            var list = Array.isArray(r.data) ? r.data : [];
            hint.textContent = list.length ? '' : 'لا يوجد أشخاص بهذا الاسم بين المتقدمين والمرشحين والمحفوظين';
            list.forEach(function (p) {
              var b = el('button');
              b.type = 'button';
              if (typeof window.twAvatarEl === 'function') b.appendChild(twAvatarEl({ full_name: p.full_name, avatar_url: p.avatar_url, user_type: 'emp' }, 'md'));
              b.appendChild(el('span', null, p.full_name || '—'));
              b.addEventListener('click', function () { st.cand = { id: p.id, name: p.full_name }; renderPerson(); });
              res.appendChild(b);
            });
          });
        }
        q.addEventListener('input', function () { clearTimeout(t); t = setTimeout(search, 250); });
        search();
      }
      renderPerson();
      form.appendChild(personBox);

      // Job
      var jobBox = el('div', 'tw-sch-f');
      jobBox.appendChild(el('span', 'tw-sch-lbl', 'الوظيفة'));
      var jobSel = null;
      if (st.jobId) {
        jobBox.appendChild(el('span', 'tw-sch-val', st.jobTitle || 'الوظيفة المحددة'));
      } else {
        jobSel = sel('tw-sch-job', 'جارٍ تحميل الوظائف…', []);
        jobSel.setAttribute('aria-label', 'الوظيفة');
        jobBox.appendChild(jobSel);
        twApi('/api/schedule/jobs').then(function (r) {
          var jobs = (r.ok && Array.isArray(r.data)) ? r.data : [];
          jobSel.options[0].textContent = !r.ok ? twApiMessage(r, 'تعذّر تحميل الوظائف')
            : jobs.length ? 'اختر الوظيفة' : 'لا توجد وظائف فعّالة — انشر وظيفة أولاً';
          jobs.forEach(function (j) {
            var o = el('option', null, j.title || ('وظيفة #' + j.id));
            o.value = String(j.id);
            jobSel.appendChild(o);
          });
          if (window.scSelectInit) scSelectInit();
        });
      }
      form.appendChild(jobBox);

      // Date + time
      var dt = buildDateTime();
      form.appendChild(field('التاريخ', dt.dateRow));
      form.appendChild(field('الوقت', dt.timeRow));

      // Type
      var seg = el('div', 'tw-sch-seg');
      var bOn = el('button', null, 'أونلاين'); bOn.type = 'button';
      var bOff = el('button', null, 'حضوري'); bOff.type = 'button';
      seg.appendChild(bOn); seg.appendChild(bOff);
      form.appendChild(field('نوع المقابلة', seg));
      var url = el('input', 'tw-sch-in');
      url.type = 'url'; url.dir = 'ltr'; url.placeholder = 'https://meet.google.com/…';
      var urlF = field('رابط الاجتماع', url);
      var loc = el('input', 'tw-sch-in');
      loc.type = 'text'; loc.maxLength = 500; loc.placeholder = 'مبنى الشركة، الطابق الثاني…';
      var locF = field('مكان المقابلة', loc);
      form.appendChild(urlF); form.appendChild(locF);
      function setMode(m) {
        st.mode = m;
        bOn.setAttribute('aria-pressed', m === 'online' ? 'true' : 'false');
        bOff.setAttribute('aria-pressed', m === 'onsite' ? 'true' : 'false');
        urlF.hidden = m !== 'online';
        locF.hidden = m !== 'onsite';
      }
      bOn.addEventListener('click', function () { setMode('online'); });
      bOff.addEventListener('click', function () { setMode('onsite'); });
      setMode('online');

      var dl = sel('tw-sch-dl', 'مهلة الرد', DEADLINES.map(function (h) {
        return { value: h, label: h === 168 ? 'أسبوع' : h + ' ساعة' };
      }));
      dl.value = '48';   // Feature Contract default (not a date field)
      form.appendChild(field('مهلة رد المرشح', dl));
      var rep = el('input', 'tw-sch-in');
      rep.type = 'text'; rep.maxLength = 200; rep.placeholder = 'اسم مسؤول المقابلة (اختياري)';
      form.appendChild(field('ممثل الشركة', rep));
      var notes = el('textarea', 'tw-sch-in');
      notes.maxLength = 1000; notes.rows = 2; notes.placeholder = 'أي تفاصيل أو تعليمات إضافية…';
      form.appendChild(field('ملاحظات', notes));
      form.appendChild(err);

      function fail(msg) { err.textContent = msg; return false; }

      function submit() {
        err.textContent = '';
        if (!st.cand) return fail('اختر الشخص الذي تريد تحديد موعد معه');
        var jobId = st.jobId || (jobSel && parseInt(jobSel.value, 10)) || null;
        if (!jobId) return fail('اختر الوظيفة التي يرتبط بها الموعد');
        var when = dt.value();
        if (!when) return fail('اختر التاريخ والوقت كاملين');
        if (when.getTime() <= Date.now()) return fail('وقت الموعد يجب أن يكون في المستقبل');
        var hours = parseInt(dl.value, 10);
        if (DEADLINES.indexOf(hours) === -1) return fail('اختر مهلة الرد');
        if (when.getTime() - Date.now() <= hours * 3600000)
          return fail('مهلة الرد تنتهي بعد وقت الموعد — اختر موعداً أبعد أو مهلة أقصر');
        var link = null, place = null;
        if (st.mode === 'online') {
          link = twSafeLinkUrl(url.value.trim());
          if (!link || link.indexOf('https://') !== 0) return fail('أدخل رابط اجتماع صالحاً يبدأ بـ https://');
        } else {
          place = loc.value.trim();
          if (!place) return fail('أدخل مكان المقابلة');
        }
        var extra = {
          notes: notes.value.trim() || null,
          representative_name: rep.value.trim() || null,
        };
        var createP = st.draftId
          ? Promise.resolve({ ok: true, data: { id: st.draftId } })
          : twApi('/api/appointments', { method: 'POST', body: {
              candidate_id: st.cand.id, job_id: jobId, appointment_type: 'interview',
              mode: st.mode, online_url: link, location_text: place,
              notes: extra.notes, representative_name: extra.representative_name,
            } });
        return createP.then(function (c) {
          if (!c.ok || !c.data || !c.data.id) {
            var code = c.error && c.error.generalError && c.error.generalError.code;
            if (code === 'appointment_exists') {
              return lookupOpen(st.cand.id, jobId).then(function (a) {
                if (a && a.status === 'draft') { st.draftId = a.id; return submit(); }
                return fail(twApiMessage(c, 'يوجد موعد نشط مع هذا الشخص على هذه الوظيفة')
                  + (a ? ' — افتحه من «فتح الموعد»' : ''));
              });
            }
            return fail(twApiMessage(c, 'تعذّر إنشاء الموعد، حاول مجدداً'));
          }
          st.draftId = c.data.id;   // a failed send below keeps the draft → retry sends it
          return twApi('/api/appointments/' + encodeURIComponent(c.data.id) + '/send', {
            method: 'POST', body: {
              scheduled_at: when.toISOString(), deadline_hours: hours,
              online_url: link, location_text: place,
              notes: extra.notes, representative_name: extra.representative_name,
            } }).then(function (s) {
            if (!s.ok) return fail(twApiMessage(s, 'أُنشئ الموعد لكن تعذّر إرسال الدعوة — اضغط «إرسال الدعوة» مجدداً'));
            st.result = { id: st.draftId, status: 'pending_response', job_id: jobId };
            return true;
          });
        });
      }

      twModal({
        title: 'تحديد موعد مقابلة',
        content: form,
        actions: [
          { text: 'إلغاء', variant: 'secondary' },
          { text: 'إرسال الدعوة', variant: 'primary', onClick: submit },
        ],
        onClose: function () {
          var r = st.result;
          if (r) {
            toast('تم إرسال دعوة المقابلة ✓');
            try {
              document.dispatchEvent(new CustomEvent('tw:appointment-scheduled', { detail: {
                appointmentId: r.id, candidateId: st.cand.id, jobId: r.job_id } }));
            } catch (e) { console.warn('[tw-schedule] event failed', e); }
            if (opts.navigate !== false) location.href = roomHref(r.id);
          }
          resolve(r);
        },
      });
      if (window.scSelectInit) scSelectInit();   // DS-SEL engine for the date/time/job dropdowns
    });
  }

  window.twScheduleInterview = twScheduleInterview;
  window.twScheduleButton = twScheduleButton;
  window.twScheduleMount = twScheduleMount;
})();
