// test_modal_a11y.js — Static regression tests for Phase 6 (modal-a11y-v1)
// Verifies: role="dialog" + aria-labelledby on 6 modals,
//           <span> title elements (not <input readonly>),
//           type="button" + aria-label="إغلاق" on 6 close buttons,
//           for/id label associations on 25 fields.
//
// Run: node tests/test_modal_a11y.js

'use strict';

const fs   = require('fs');
const path = require('path');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'profile-showcase.html'), 'utf8');
const EDU  = fs.readFileSync(path.join(__dirname, '..', 'profile-v2.edu.js'),     'utf8');
const CRS  = fs.readFileSync(path.join(__dirname, '..', 'profile-v2.courses.js'), 'utf8');

let passed = 0, failed = 0;

function assert(name, condition) {
  if (condition) {
    console.log('  ✓', name);
    passed++;
  } else {
    console.error('  ✗', name);
    failed++;
  }
}

// ── 1. role="dialog" on 6 modals ──────────────────────────────────────────
console.log('\n[1] role="dialog" + aria-labelledby on 6 modals');

assert('exOverlay has role="dialog"',
  /id="exOverlay"[^>]*role="dialog"/.test(HTML) || /role="dialog"[^>]*id="exOverlay"/.test(HTML));
assert('exOverlay has aria-labelledby="exModalTitle"',
  /id="exOverlay"[^>]*aria-labelledby="exModalTitle"/.test(HTML) ||
  /aria-labelledby="exModalTitle"[^>]*id="exOverlay"/.test(HTML));

assert('eduOverlay has role="dialog"',
  /id="eduOverlay"[^>]*role="dialog"/.test(HTML) || /role="dialog"[^>]*id="eduOverlay"/.test(HTML));
assert('eduOverlay has aria-labelledby="eduMTitle"',
  /id="eduOverlay"[^>]*aria-labelledby="eduMTitle"/.test(HTML) ||
  /aria-labelledby="eduMTitle"[^>]*id="eduOverlay"/.test(HTML));

assert('courseOverlay has role="dialog"',
  /id="courseOverlay"[^>]*role="dialog"/.test(HTML) || /role="dialog"[^>]*id="courseOverlay"/.test(HTML));
assert('courseOverlay has aria-labelledby="courseMTitle"',
  /id="courseOverlay"[^>]*aria-labelledby="courseMTitle"/.test(HTML) ||
  /aria-labelledby="courseMTitle"[^>]*id="courseOverlay"/.test(HTML));

assert('skillOverlay has role="dialog"',
  /id="skillOverlay"[^>]*role="dialog"/.test(HTML) || /role="dialog"[^>]*id="skillOverlay"/.test(HTML));
assert('skillOverlay has aria-labelledby="skillModalTitle"',
  /id="skillOverlay"[^>]*aria-labelledby="skillModalTitle"/.test(HTML) ||
  /aria-labelledby="skillModalTitle"[^>]*id="skillOverlay"/.test(HTML));

assert('langOverlay has role="dialog"',
  /id="langOverlay"[^>]*role="dialog"/.test(HTML) || /role="dialog"[^>]*id="langOverlay"/.test(HTML));
assert('langOverlay has aria-labelledby="langModalTitle"',
  /id="langOverlay"[^>]*aria-labelledby="langModalTitle"/.test(HTML) ||
  /aria-labelledby="langModalTitle"[^>]*id="langOverlay"/.test(HTML));

assert('linkOverlay has role="dialog"',
  /id="linkOverlay"[^>]*role="dialog"/.test(HTML) || /role="dialog"[^>]*id="linkOverlay"/.test(HTML));
assert('linkOverlay has aria-labelledby="linkModalTitle"',
  /id="linkOverlay"[^>]*aria-labelledby="linkModalTitle"/.test(HTML) ||
  /aria-labelledby="linkModalTitle"[^>]*id="linkOverlay"/.test(HTML));

// ── 2. Title elements: <span> not <input readonly> ──────────────────────
console.log('\n[2] Title elements are <span> (not <input readonly>)');

assert('eduMTitle is a <span> (not input)',
  /<span[^>]*id="eduMTitle"/.test(HTML));
assert('eduMTitle is NOT an <input>',
  !/<input[^>]*id="eduMTitle"/.test(HTML));

assert('courseMTitle is a <span> (not input)',
  /<span[^>]*id="courseMTitle"/.test(HTML));
assert('courseMTitle is NOT an <input>',
  !/<input[^>]*id="courseMTitle"/.test(HTML));

assert('skillModalTitle id exists on a <span>',
  /<span[^>]*id="skillModalTitle"/.test(HTML));
assert('langModalTitle id exists on a <span>',
  /<span[^>]*id="langModalTitle"/.test(HTML));
assert('linkModalTitle id exists on a <span>',
  /<span[^>]*id="linkModalTitle"/.test(HTML));

// ── 3. Close buttons: type="button" + aria-label="إغلاق" ────────────────
console.log('\n[3] Close buttons have type="button" and aria-label="إغلاق"');

const CLOSE_IDS = ['exClose', 'eduClose', 'courseClose', 'skillClose', 'langClose', 'linkClose'];
CLOSE_IDS.forEach(function(id) {
  const re = new RegExp('id="' + id + '"[^>]*(type="button"[^>]*aria-label="[^"]*إغلاق[^"]*"|aria-label="[^"]*إغلاق[^"]*"[^>]*type="button")');
  const re2 = new RegExp('(type="button"[^>]*id="' + id + '"[^>]*aria-label="[^"]*إغلاق[^"]*"|aria-label="[^"]*إغلاق[^"]*"[^>]*id="' + id + '"[^>]*type="button")');
  // Also allow any order — just check both attributes present within the same tag
  const tagRe = new RegExp('<button[^>]*id="' + id + '"[^>]*>');
  const match = HTML.match(tagRe);
  if (match) {
    const tag = match[0];
    assert(id + ' has type="button"', /type="button"/.test(tag));
    assert(id + ' has aria-label="إغلاق"', /aria-label="إغلاق"/.test(tag));
  } else {
    assert(id + ' button tag found', false);
    assert(id + ' has aria-label="إغلاق"', false);
  }
});

// ── 4. Label for= associations — 25 fields ──────────────────────────────
console.log('\n[4] Label for= associations (25 fields)');

const LABEL_FOR = [
  // Experience modal (7)
  'exTitle', 'exCompany', 'exStart', 'exEnd', 'exCountry', 'exCity', 'exDesc',
  // Education modal (6)
  'eduInst', 'eduDeg', 'eduField', 'eduSY', 'eduEY', 'eduDesc',
  // Courses modal (5)
  'courseTitle', 'courseProv', 'courseCD', 'courseCurl', 'courseDesc',
  // Skills modal (3)
  'skillName', 'skillLevel', 'skillNote',
  // Languages modal (2)
  'langName', 'langLevel',
  // Links modal (2)
  'linkType', 'linkUrl',
];

LABEL_FOR.forEach(function(fieldId) {
  assert('label for="' + fieldId + '" exists',
    new RegExp('for="' + fieldId + '"').test(HTML));
});

// ── 5. JS: sv('eduMTitle') / sv('courseMTitle') no longer used ──────────
console.log('\n[5] JS: sv() no longer called for title elements');

assert('edu.js does not call sv(\'eduMTitle\')',
  !EDU.includes("sv('eduMTitle'"));
assert('courses.js does not call sv(\'courseMTitle\')',
  !CRS.includes("sv('courseMTitle'"));

assert('edu.js has _setModalTitle helper',
  EDU.includes('_setModalTitle'));
assert('courses.js has _setCourseTitle helper',
  CRS.includes('_setCourseTitle'));

assert('edu.js calls _setModalTitle(\'إضافة شهادة\')',
  EDU.includes("_setModalTitle('إضافة شهادة')"));
assert('edu.js calls _setModalTitle(\'تعديل الشهادة\')',
  EDU.includes("_setModalTitle('تعديل الشهادة')"));
assert('courses.js calls _setCourseTitle(\'إضافة دورة\')',
  CRS.includes("_setCourseTitle('إضافة دورة')"));
assert('courses.js calls _setCourseTitle(\'تعديل الدورة\')',
  CRS.includes("_setCourseTitle('تعديل الدورة')"));

// ── 6. Cache version ─────────────────────────────────────────────────────
console.log('\n[6] Cache bust versions updated to modal-a11y-v1');

assert('edu.js script tag has ?v=modal-a11y-v1',
  HTML.includes('profile-v2.edu.js?v=modal-a11y-v1'));
assert('courses.js script tag has ?v=modal-a11y-v1',
  HTML.includes('profile-v2.courses.js?v=modal-a11y-v1'));

// ── 7. epOverlay untouched ────────────────────────────────────────────────
console.log('\n[7] epOverlay unchanged (already compliant — must not be modified)');

assert('epOverlay still has role="dialog" aria-labelledby="epTitle"',
  /id="epOverlay"[^>]*role="dialog"[^>]*aria-labelledby="epTitle"/.test(HTML) ||
  /role="dialog"[^>]*id="epOverlay"[^>]*aria-labelledby="epTitle"/.test(HTML) ||
  /aria-labelledby="epTitle"[^>]*role="dialog"[^>]*id="epOverlay"/.test(HTML) ||
  HTML.includes('id="epOverlay" role="dialog" aria-labelledby="epTitle"'));

// ── Summary ───────────────────────────────────────────────────────────────
console.log('\n─────────────────────────────────────');
console.log('  Passed:', passed, '  Failed:', failed);
if (failed > 0) {
  console.error('  FAIL — fix the issues above before pushing.');
  process.exit(1);
} else {
  console.log('  PASS — all a11y adoption checks green.');
}
