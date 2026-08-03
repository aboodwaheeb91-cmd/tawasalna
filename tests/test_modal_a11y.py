"""
Static DOM Structural Tests — Profile V2 Modal Accessibility (Phase 6)
Uses Python html.parser.HTMLParser for real DOM structural analysis.
JS source files checked via targeted string scan + node --check.

Tests:
  html-01  No duplicate IDs in profile-showcase.html
  html-02  7 modals have role="dialog"
  html-03  7 modals have aria-labelledby
  html-04  Each aria-labelledby target ID exists in the DOM
  html-05  Each aria-labelledby target is non-interactive (not <input>)
  html-06  7 close buttons have an accessible name
  html-07  6 modified close buttons have type="button"
  html-08  25 label[for] controls each point to an existing element
  html-09  exCurrent / eduCurrent use wrapping <label> (not for= association)
  html-10  12 custom selects have a label[for] association
  js-01   node --check profile-v2.edu.js passes (no syntax errors)
  js-02   node --check profile-v2.courses.js passes (no syntax errors)
  js-03   edu.js does not call sv('eduMTitle', ...)
  js-04   courses.js does not call sv('courseMTitle', ...)
  js-05   edu.js uses textContent in _setModalTitle (not innerHTML)
  js-06   courses.js uses textContent in _setCourseTitle (not innerHTML)
  js-07   edu.js contains _setModalTitle('إضافة شهادة')
  js-08   edu.js contains _setModalTitle('تعديل الشهادة')
  js-09   courses.js contains _setCourseTitle('إضافة دورة')
  js-10   courses.js contains _setCourseTitle('تعديل الدورة')

  Exit code: 0 on all pass, 1 on any failure.
"""

import sys
import os
import subprocess
from html.parser import HTMLParser

PASS, FAIL = '✅ PASS', '❌ FAIL'
results = []


def check(name, condition, detail=None):
    status = PASS if condition else FAIL
    results.append((name, status, detail))
    marker = '✅' if condition else '❌'
    suffix = f'  [{detail}]' if detail and not condition else ''
    print(f'{marker}  {name}{suffix}')


# ── Void elements (self-closing, no end tag) ──────────────────────────────────
_VOID = frozenset({
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
    'link', 'meta', 'param', 'source', 'track', 'wbr',
})

# ── DOM Collector ─────────────────────────────────────────────────────────────
class DOMCollector(HTMLParser):
    """SAX-style collector that tracks IDs, labels, and structural nesting."""

    def __init__(self):
        super().__init__()
        self.ids = {}               # id → {'tag', 'attrs'}
        self.duplicate_ids = set()  # IDs appearing more than once
        self.label_fors = []        # all label[for] values in document order
        self.elements = []          # all elements in document order
        self._stack = []            # open non-void element stack
        self.inputs_in_label = set()  # IDs of inputs wrapped by a <label>

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        adict = {k.lower(): v or '' for k, v in attrs}
        el = {'tag': tag, 'attrs': adict}
        self.elements.append(el)

        el_id = adict.get('id', '').strip()
        if el_id:
            if el_id in self.ids:
                self.duplicate_ids.add(el_id)
            else:
                self.ids[el_id] = el

        if tag == 'label' and 'for' in adict:
            self.label_fors.append(adict['for'].strip())

        # Wrapping-label detection: <input> is void so check stack BEFORE push.
        # When handle_starttag fires for <input id="exCurrent">, the enclosing
        # <label> is already on the stack.
        if tag in ('input', 'select', 'textarea') and el_id:
            if any(p['tag'] == 'label' for p in self._stack):
                self.inputs_in_label.add(el_id)

        if tag not in _VOID:
            self._stack.append(el)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _VOID:
            return
        # Pop the most recent matching open tag
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]['tag'] == tag:
                self._stack.pop(i)
                return


# ── File paths ────────────────────────────────────────────────────────────────
BASE = os.path.join(os.path.dirname(__file__), '..')
HTML_FILE = os.path.join(BASE, 'profile-showcase.html')
EDU_FILE  = os.path.join(BASE, 'profile-v2.edu.js')
CRS_FILE  = os.path.join(BASE, 'profile-v2.courses.js')


# ── Parse HTML ────────────────────────────────────────────────────────────────
with open(HTML_FILE, encoding='utf-8') as fh:
    HTML = fh.read()

dom = DOMCollector()
dom.feed(HTML)


# ── Constants ─────────────────────────────────────────────────────────────────
MODALS = {
    'epOverlay':     'epTitle',
    'exOverlay':     'exModalTitle',
    'eduOverlay':    'eduMTitle',
    'courseOverlay': 'courseMTitle',
    'skillOverlay':  'skillModalTitle',
    'langOverlay':   'langModalTitle',
    'linkOverlay':   'linkModalTitle',
}

ALL_CLOSE      = ['epClose', 'exClose', 'eduClose', 'courseClose',
                  'skillClose', 'langClose', 'linkClose']
MODIFIED_CLOSE = ['exClose', 'eduClose', 'courseClose',
                  'skillClose', 'langClose', 'linkClose']

LABEL_FORS_EXPECTED = [
    # Experience modal (7)
    'exTitle', 'exCompany', 'exStart', 'exEnd', 'exCountry', 'exCity', 'exDesc',
    # Education modal (6)
    'eduInst', 'eduDeg', 'eduField', 'eduSY', 'eduEY', 'eduDesc',
    # Courses modal (5)
    'courseTitle', 'courseProv', 'courseCD', 'courseCurl', 'courseDesc',
    # Skills modal (3)
    'skillName', 'skillLevel', 'skillNote',
    # Languages modal (2)
    'langName', 'langLevel',
    # Links modal (2)
    'linkType', 'linkUrl',
]  # 25 total

CUSTOM_SELECTS = [
    # Experience
    'exStart', 'exEnd', 'exCountry', 'exCity',
    # Education
    'eduDeg', 'eduSY', 'eduEY',
    # Courses
    'courseCD',
    # Skills
    'skillLevel',
    # Languages
    'langName', 'langLevel',
    # Links
    'linkType',
]  # 12 total

WRAPPING_CHECKBOXES = ['exCurrent', 'eduCurrent']


# ─────────────────────────────────────────────────────────────────────────────
# HTML structural checks
# ─────────────────────────────────────────────────────────────────────────────

print('\n[html-01] No duplicate IDs in profile-showcase.html')
check('no duplicate IDs in page',
      len(dom.duplicate_ids) == 0,
      f'duplicates: {sorted(dom.duplicate_ids)}' if dom.duplicate_ids else None)

print('\n[html-02] 7 modals have role="dialog"')
for modal_id in MODALS:
    el = dom.ids.get(modal_id)
    has_role = el is not None and el['attrs'].get('role') == 'dialog'
    check(f'{modal_id} role="dialog"', has_role,
          f'element not found' if el is None else f'role="{el["attrs"].get("role","(missing)")}"')

print('\n[html-03] 7 modals have aria-labelledby')
for modal_id in MODALS:
    el = dom.ids.get(modal_id)
    has_attr = el is not None and 'aria-labelledby' in el['attrs']
    check(f'{modal_id} has aria-labelledby', has_attr)

print('\n[html-04] aria-labelledby targets exist in DOM')
for modal_id, target_id in MODALS.items():
    target_exists = target_id in dom.ids
    modal_el = dom.ids.get(modal_id)
    actual_target = modal_el['attrs'].get('aria-labelledby', '') if modal_el else ''
    points_correctly = actual_target == target_id
    check(f'{modal_id} aria-labelledby="{target_id}" — target exists',
          target_exists and points_correctly,
          f'aria-labelledby="{actual_target}", target in DOM: {target_exists}')

print('\n[html-05] aria-labelledby targets are non-interactive elements (not <input>)')
for modal_id, target_id in MODALS.items():
    el = dom.ids.get(target_id)
    is_non_input = el is not None and el['tag'] != 'input'
    check(f'{target_id} is not an <input>',
          is_non_input,
          f'tag=<{el["tag"]}>' if el else 'element not found')

print('\n[html-06] 7 close buttons have an accessible name (aria-label)')
for btn_id in ALL_CLOSE:
    el = dom.ids.get(btn_id)
    has_label = (el is not None and
                 el['attrs'].get('aria-label', '').strip() != '')
    check(f'{btn_id} has aria-label',
          has_label,
          f'aria-label="{el["attrs"].get("aria-label","(missing)")}"' if el else 'element not found')

print('\n[html-07] 6 modified close buttons have type="button"')
for btn_id in MODIFIED_CLOSE:
    el = dom.ids.get(btn_id)
    has_type = el is not None and el['attrs'].get('type') == 'button'
    check(f'{btn_id} type="button"',
          has_type,
          f'type="{el["attrs"].get("type","(missing)")}"' if el else 'element not found')

print('\n[html-08] 25 label[for] controls each point to an existing element')
label_fors_set = set(dom.label_fors)
for field_id in LABEL_FORS_EXPECTED:
    has_label = field_id in label_fors_set
    target_exists = field_id in dom.ids
    check(f'label[for="{field_id}"] and target exists',
          has_label and target_exists,
          f'label present: {has_label}, target in DOM: {target_exists}')

print('\n[html-09] exCurrent / eduCurrent use wrapping <label> (not for= association)')
for cb_id in WRAPPING_CHECKBOXES:
    in_label = cb_id in dom.inputs_in_label
    has_for  = cb_id in label_fors_set
    check(f'{cb_id} is wrapped by <label> (not for= association)',
          in_label and not has_for,
          f'wrapped={in_label}, for= present={has_for}')

print('\n[html-10] 12 custom selects have a label[for] association')
for sel_id in CUSTOM_SELECTS:
    has_label = sel_id in label_fors_set
    check(f'label[for="{sel_id}"] exists',
          has_label)


# ─────────────────────────────────────────────────────────────────────────────
# JS syntax checks via node --check
# ─────────────────────────────────────────────────────────────────────────────

print('\n[js-01/02] JS syntax checks (node --check)')
for js_label, js_path in [('profile-v2.edu.js', EDU_FILE),
                            ('profile-v2.courses.js', CRS_FILE)]:
    result = subprocess.run(
        ['node', '--check', js_path],
        capture_output=True, text=True
    )
    check(f'node --check {js_label}',
          result.returncode == 0,
          result.stderr.strip() if result.returncode != 0 else None)


# ─────────────────────────────────────────────────────────────────────────────
# JS source checks (targeted string scan — not a substitute for HTML parsing)
# ─────────────────────────────────────────────────────────────────────────────

with open(EDU_FILE, encoding='utf-8') as fh:
    EDU = fh.read()
with open(CRS_FILE, encoding='utf-8') as fh:
    CRS = fh.read()

print('\n[js-03–06] sv() no longer used for title elements; textContent used instead')
check("edu.js does not call sv('eduMTitle'",
      "sv('eduMTitle'" not in EDU)
check("courses.js does not call sv('courseMTitle'",
      "sv('courseMTitle'" not in CRS)
check('edu.js _setModalTitle uses textContent (not innerHTML)',
      'el.textContent' in EDU and 'el.innerHTML' not in EDU.split('_setModalTitle')[1].split('}')[0])
check('courses.js _setCourseTitle uses textContent (not innerHTML)',
      'el.textContent' in CRS and 'el.innerHTML' not in CRS.split('_setCourseTitle')[1].split('}')[0])

print("\n[js-07–10] Title strings present in JS files")
check("edu.js calls _setModalTitle('إضافة شهادة')",
      "_setModalTitle('إضافة شهادة')" in EDU)
check("edu.js calls _setModalTitle('تعديل الشهادة')",
      "_setModalTitle('تعديل الشهادة')" in EDU)
check("courses.js calls _setCourseTitle('إضافة دورة')",
      "_setCourseTitle('إضافة دورة')" in CRS)
check("courses.js calls _setCourseTitle('تعديل الدورة')",
      "_setCourseTitle('تعديل الدورة')" in CRS)


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

passed  = sum(1 for _, s, _ in results if s == PASS)
failed  = sum(1 for _, s, _ in results if s == FAIL)
total   = len(results)

print(f'\n{"─" * 50}')
print(f'  Passed: {passed}   Failed: {failed}   Total: {total}')

if failed > 0:
    print('  FAIL — fix the issues above before pushing.')
    sys.exit(1)
else:
    print('  PASS — all accessibility adoption checks green.')
