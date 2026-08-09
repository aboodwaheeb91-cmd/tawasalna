// test_job_chip_pop_runtime.js — Runtime tests for job chip popover (company.main.js)
// Uses Node.js vm module to run REAL production code from company.main.js
// via @vm-extract-begin/end: co-job-chip-pop markers.
// Uses jsdom for DOM simulation (innerHTML/querySelector/events require real DOM).
//
// Run: node test_job_chip_pop_runtime.js
'use strict';

const fs   = require('fs');
const vm   = require('vm');
const { JSDOM } = require('jsdom');

// ── Source extraction ─────────────────────────────────────────────────────────
const src = fs.readFileSync('./static/company/company.main.js', 'utf8');

function extractSection(src, key) {
  var begin = '// @vm-extract-begin: ' + key;
  var end   = '// @vm-extract-end: '   + key;
  var si = src.indexOf(begin);
  var ei = src.indexOf(end, si + begin.length);
  if (si === -1) throw new Error('Missing @vm-extract-begin: ' + key);
  if (ei === -1) throw new Error('Missing @vm-extract-end: '   + key);
  return src.slice(si, ei + end.length);
}

var POP_CODE = extractSection(src, 'co-job-chip-pop');

// ── Test harness ──────────────────────────────────────────────────────────────
var _passed = 0, _failed = 0;

function assert(label, condition) {
  if (condition) { console.log('  ✅ PASS:', label); _passed++; }
  else { console.error('  ❌ FAIL:', label); _failed++; }
}

// ── Context factory — fresh DOM + fresh vm context per scenario ───────────────
// 'nextApptId' param lets callers set chip's data-next-appt-id for scenario 3.
function makeScenarioCtx(nextApptId) {
  nextApptId = nextApptId || '';

  // Fresh jsdom with the minimal DOM the popover code needs
  var dom = new JSDOM(`<!DOCTYPE html>
<html dir="rtl">
<body>
  <div id="coNotesModal" style="display:none"></div>
  <div id="coApptModal"  style="display:none"></div>
  <div class="co-cand-saved-card" id="testCard" data-cid="42" data-name="أحمد محمد">
    <div id="testChip" class="co-cjp-chip"
         data-title="مطوّر ويب"
         data-apply-date="2026-01-01"
         data-cand-status="saved"
         data-pe-id="10"
         data-app-id="20"
         data-notes-count="3"
         data-next-appt-id="${nextApptId}"
         data-jid="5">
    </div>
  </div>
</body>
</html>`, { url: 'http://localhost/' });

  // Calls recorder and modal stub functions
  var calls = { openNotesPanel: [], openApptModal: [] };
  var state = { navTarget: null };

  // Proxy window.location so href assignments are intercepted without jsdom navigation
  var locProxy = new Proxy(dom.window.location, {
    set: function(target, key, val) {
      if (key === 'href') { state.navTarget = String(val); return true; }
      return Reflect.set(target, key, val);
    }
  });

  // Proxy window so window.location → our spy; everything else → real dom.window
  var winProxy = new Proxy(dom.window, {
    get: function(target, prop) {
      if (prop === 'location') return locProxy;
      var v = Reflect.get(target, prop);
      if (typeof v === 'function') return Function.prototype.bind.call(v, target);
      return v;
    }
  });

  // vm context: jsdom document + proxy window + IIFE-local stubs
  // _STATUS_LABELS verbatim from company.main.js:2644
  // _esc verbatim from company.main.js:2727
  var ctx = vm.createContext({
    document:           dom.window.document,
    window:             winProxy,
    encodeURIComponent: encodeURIComponent,
    parseInt:           parseInt,
    // setTimeout is synchronous here so the capture listener registers
    // before the test dispatches any events (no async gap).
    setTimeout: function(fn) { fn(); },

    // IIFE-local variables (declared outside the extracted section)
    _jobPopTarget: null,
    _appJobId:     null,

    // IIFE-local helper stubs
    _STATUS_LABELS: {
      saved: 'محفوظ', shortlisted: 'مرشح قوي',
      contacted: 'تم التواصل',
      interview: 'مقابلة',
      hired: 'تم التوظيف', rejected: 'غير مناسب'
    },
    _esc: function(s) {
      if (s == null) return '';
      return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    },
    _openNotesPanel: function(entryId) {
      calls.openNotesPanel.push(entryId);
      var el = dom.window.document.getElementById('coNotesModal');
      if (el) el.style.display = 'flex';
    },
    _openApptModal: function(appId, applName, jobTitle, entryId, candidateId) {
      calls.openApptModal.push({ appId: appId, applName: applName, jobTitle: jobTitle,
                                  entryId: entryId, candidateId: candidateId });
      var el = dom.window.document.getElementById('coApptModal');
      if (el) el.style.display = 'flex';
    },
  });

  // Run REAL extracted code in this context: registers _showJobChipPop,
  // _jobPopPositionFromChip, _closeJobPop as properties on ctx.
  vm.runInContext(POP_CODE, ctx);

  return { dom: dom, ctx: ctx, calls: calls, state: state };
}

// ─────────────────────────────────────────────────────────────────────────────
// SCENARIO 1: .co-cjp-btn--notes → _openNotesPanel → #coNotesModal visible
// ─────────────────────────────────────────────────────────────────────────────
console.log('\nScenario 1: .co-cjp-btn--notes opens #coNotesModal');
(function () {
  var S = makeScenarioCtx('');
  var doc  = S.dom.window.document;
  var chip = doc.getElementById('testChip');

  S.ctx._showJobChipPop(chip);

  var pop = doc.getElementById('co-cand-job-pop');
  assert('S1-1: popover created on document.body',   !!(pop));
  assert('S1-2: popover initially visible (display=block)', pop && pop.style.display === 'block');

  var notesBtn = pop && pop.querySelector('.co-cjp-btn--notes');
  assert('S1-3: .co-cjp-btn--notes exists inside popover',  !!(notesBtn));
  assert('S1-4: notes button label contains "ملاحظات الوظيفة"',
    notesBtn && notesBtn.textContent.includes('ملاحظات الوظيفة'));
  assert('S1-5: notes button data-pe-id="10"',
    notesBtn && notesBtn.getAttribute('data-pe-id') === '10');

  // Dispatch click — bubbling so document capture listener also fires
  notesBtn.dispatchEvent(new S.dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));

  assert('S1-6: _openNotesPanel called exactly once',   S.calls.openNotesPanel.length === 1);
  assert('S1-7: _openNotesPanel called with pe-id=10',  S.calls.openNotesPanel[0] === 10);
  assert('S1-8: _openApptModal NOT called',             S.calls.openApptModal.length === 0);

  var notesModal = doc.getElementById('coNotesModal');
  assert('S1-9: #coNotesModal is now display=flex',     notesModal && notesModal.style.display === 'flex');
  assert('S1-10: popover closed after notes click',     pop && pop.style.display === 'none');
}());

// ─────────────────────────────────────────────────────────────────────────────
// SCENARIO 2: .co-cjp-btn--appt (no data-next-appt-id) → _openApptModal
// ─────────────────────────────────────────────────────────────────────────────
console.log('\nScenario 2: .co-cjp-btn--appt (empty appt-id) opens #coApptModal');
(function () {
  var S = makeScenarioCtx('');   // data-next-appt-id=""
  var doc  = S.dom.window.document;
  var chip = doc.getElementById('testChip');

  S.ctx._showJobChipPop(chip);

  var pop     = doc.getElementById('co-cand-job-pop');
  var apptBtn = pop && pop.querySelector('.co-cjp-btn--appt');
  assert('S2-1: .co-cjp-btn--appt exists', !!(apptBtn));
  assert('S2-2: label is "تحديد موعد" when no appt-id',
    apptBtn && apptBtn.textContent.trim() === 'تحديد موعد');
  assert('S2-3: data-next-appt-id is empty string',
    apptBtn && apptBtn.getAttribute('data-next-appt-id') === '');
  assert('S2-4: data-app-id="20"',  apptBtn && apptBtn.getAttribute('data-app-id')   === '20');
  assert('S2-5: data-pe-id="10"',   apptBtn && apptBtn.getAttribute('data-pe-id')    === '10');
  assert('S2-6: data-cand-id="42"', apptBtn && apptBtn.getAttribute('data-cand-id')  === '42');
  assert('S2-7: data-cand-name set', apptBtn && apptBtn.getAttribute('data-cand-name') !== '');

  apptBtn.dispatchEvent(new S.dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));

  assert('S2-8: _openApptModal called exactly once',  S.calls.openApptModal.length === 1);
  var c = S.calls.openApptModal[0];
  assert('S2-9:  appId = 20',            c && c.appId        === 20);
  assert('S2-10: entryId = 10',          c && c.entryId      === 10);
  assert('S2-11: candidateId = 42',      c && c.candidateId  === 42);
  assert('S2-12: applName = أحمد محمد',
    c && c.applName === 'أحمد محمد');
  assert('S2-13: jobTitle = مطور ويب',
    c && c.jobTitle === 'مطوّر ويب');

  var apptModal = doc.getElementById('coApptModal');
  assert('S2-14: #coApptModal is visible',              apptModal && apptModal.style.display === 'flex');
  assert('S2-15: _openNotesPanel NOT called',           S.calls.openNotesPanel.length === 0);
  assert('S2-16: popover closed after appt click',      pop && pop.style.display === 'none');
  assert('S2-17: no navigation (no nextId)',            !S.state.navTarget);
}());

// ─────────────────────────────────────────────────────────────────────────────
// SCENARIO 3: .co-cjp-btn--appt (data-next-appt-id="99") → navigate
// ─────────────────────────────────────────────────────────────────────────────
console.log('\nScenario 3: .co-cjp-btn--appt (appt-id="99") navigates to /appointment-room');
(function () {
  var S = makeScenarioCtx('99');   // data-next-appt-id="99"
  var doc  = S.dom.window.document;
  var chip = doc.getElementById('testChip');

  S.ctx._showJobChipPop(chip);

  var pop     = doc.getElementById('co-cand-job-pop');
  var apptBtn = pop && pop.querySelector('.co-cjp-btn--appt');
  assert('S3-1: .co-cjp-btn--appt exists', !!(apptBtn));
  assert('S3-2: label is "فتح الموعد" when appt-id present',
    apptBtn && apptBtn.textContent.trim() === 'فتح الموعد');
  assert('S3-3: data-next-appt-id="99" on button',
    apptBtn && apptBtn.getAttribute('data-next-appt-id') === '99');

  apptBtn.dispatchEvent(new S.dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));

  assert('S3-4: window.location.href assigned (navTarget set)',  !!(S.state.navTarget));
  assert('S3-5: URL contains /appointment-room?id=',
    S.state.navTarget && S.state.navTarget.includes('/appointment-room?id='));
  assert('S3-6: URL contains encoded id "99"',
    S.state.navTarget && S.state.navTarget.includes('99'));
  assert('S3-7: _openApptModal NOT called (navigation takes over)',
    S.calls.openApptModal.length === 0);
  assert('S3-8: _openNotesPanel NOT called',
    S.calls.openNotesPanel.length === 0);
  assert('S3-9: popover closed before navigation',
    pop && pop.style.display === 'none');
}());

// ─────────────────────────────────────────────────────────────────────────────
// SCENARIO 4: _closeJobPop guard — inside click keeps pop open; outside closes
// ─────────────────────────────────────────────────────────────────────────────
console.log('\nScenario 4: _closeJobPop guard — inside click keeps; outside click closes');
(function () {
  var S = makeScenarioCtx('');
  var doc  = S.dom.window.document;
  var chip = doc.getElementById('testChip');

  S.ctx._showJobChipPop(chip);

  var pop = doc.getElementById('co-cand-job-pop');
  assert('S4-1: popover visible after open', pop && pop.style.display === 'block');

  // Sub-test A: direct call to _closeJobPop with an event whose target IS inside the pop
  var notesBtn = pop && pop.querySelector('.co-cjp-btn--notes');
  assert('S4-2: notes button is a child of pop (pop.contains)', notesBtn && pop.contains(notesBtn));

  S.ctx._closeJobPop({ target: notesBtn });
  assert('S4-3: popover stays open when click target is inside pop', pop.style.display === 'block');

  // Sub-test B: dispatch a real document-level click on an element OUTSIDE the pop.
  // The capture listener (registered by _showJobChipPop via setTimeout) fires _closeJobPop.
  var testCard = doc.getElementById('testCard');
  assert('S4-4: testCard is NOT inside pop (outside element)', !pop.contains(testCard));

  testCard.dispatchEvent(new S.dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
  assert('S4-5: popover hidden after outside click',  pop.style.display === 'none');
  assert('S4-6: _jobPopTarget cleared to null',       S.ctx._jobPopTarget === null);

  // Sub-test C: _closeJobPop with no event arg always closes (no-guard path)
  // Re-open the popover first
  S.ctx._showJobChipPop(chip);
  var pop2 = doc.getElementById('co-cand-job-pop');
  S.ctx._closeJobPop();   // called without event (same as from button handlers)
  assert('S4-7: calling _closeJobPop() with no arg closes pop', pop2.style.display === 'none');
}());

// ─────────────────────────────────────────────────────────────────────────────
// SCENARIO 5: chip without peId — no action buttons rendered
// ─────────────────────────────────────────────────────────────────────────────
console.log('\nScenario 5: chip with empty data-pe-id renders no action buttons');
(function () {
  var S = makeScenarioCtx('');
  var doc  = S.dom.window.document;
  var chip = doc.getElementById('testChip');

  // Remove pe-id so pipeline buttons are suppressed
  chip.setAttribute('data-pe-id', '');

  S.ctx._showJobChipPop(chip);

  var pop = doc.getElementById('co-cand-job-pop');
  assert('S5-1: popover created',             !!(pop));

  var notesBtn = pop && pop.querySelector('.co-cjp-btn--notes');
  var apptBtn  = pop && pop.querySelector('.co-cjp-btn--appt');
  assert('S5-2: no notes button when pe-id empty', !notesBtn);
  assert('S5-3: no appt button when pe-id empty',  !apptBtn);
}());

// ─────────────────────────────────────────────────────────────────────────────
// SCENARIO 6: notes count shown in label when > 0
// ─────────────────────────────────────────────────────────────────────────────
console.log('\nScenario 6: notes button label shows count when notes-count > 0');
(function () {
  var S = makeScenarioCtx('');
  var doc  = S.dom.window.document;
  var chip = doc.getElementById('testChip');
  // chip already has data-notes-count="3"

  S.ctx._showJobChipPop(chip);

  var pop      = doc.getElementById('co-cand-job-pop');
  var notesBtn = pop && pop.querySelector('.co-cjp-btn--notes');
  // Expected label: "ملاحظات الوظيفة (3)"
  assert('S6-1: label includes count (3)',
    notesBtn && notesBtn.textContent.includes('(3)'));

  // Re-open with count=0
  pop.style.display = 'none';
  chip.setAttribute('data-notes-count', '0');
  S.ctx._showJobChipPop(chip);
  var pop2      = doc.getElementById('co-cand-job-pop');
  var notesBtn2 = pop2 && pop2.querySelector('.co-cjp-btn--notes');
  // Expected label: "ملاحظات الوظيفة" (no count)
  assert('S6-2: label has no count when notes-count=0',
    notesBtn2 && !notesBtn2.textContent.includes('('));
}());

// ─────────────────────────────────────────────────────────────────────────────
// Summary
// ─────────────────────────────────────────────────────────────────────────────
console.log('\n' + '─'.repeat(60));
console.log('Results: ' + _passed + ' passed, ' + _failed + ' failed');
if (_failed > 0) {
  console.error('\nSome tests FAILED. Do not merge.');
  process.exit(1);
} else {
  console.log('All tests passed. ✓');
}
