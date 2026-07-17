"""
Talent Bank Polish (fix/talent-bank-polish) — Static Verification Tests

Tests cover all 11 hotfix sections via:
  - Static source analysis (no server/DB required)
  - Backend auth.py function logic tests
  - JS/HTML content pattern checks

Groups:
  A (01-04): Button rename + badge quota format
  B (05-07): Pipeline status filters removed
  C (08-11): Tag prefix search (ILIKE + escaping + server validation)
  D (12-14): Card layout new classes present
  E (15-17): Save source labels including manual
  F (18-20): Job sections split (applied vs pipeline-only)
  G (21-23): Job chip popover label + date gate
  H (24-26): Manage panel notes counter + follow-up labels
  I (27-29): Forbidden side-effects absent
  J (30-32): PR-5 popover buttons still wired

Requires: Python 3.8+, no DB, no server
"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))

def _read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()

HTML   = _read("company-profile.html")
JS     = _read("static/company/company.main.js")
CSS    = _read("static/company/company.css")
AUTH   = _read("auth.py")
SERVER = _read("server.py")


# ══════════════════════════════════════════════════════════════════
# Group A — Button rename + badge quota format
# ══════════════════════════════════════════════════════════════════
class A_ButtonRename(unittest.TestCase):

    def test_01_button_label_is_talent_bank(self):
        """HTML: candidatesBtn shows 'بنك المواهب' not 'المرشحون'"""
        self.assertIn("بنك المواهب", HTML)
        self.assertNotIn(">المرشحون<", HTML)

    def test_02_button_uses_gem_icon(self):
        """HTML: candidatesBtn uses data-lucide='gem'"""
        # check gem appears near candidatesBtn
        btn_block = re.search(
            r'id="candidatesBtn".*?</button>', HTML, re.S
        )
        self.assertIsNotNone(btn_block, "candidatesBtn not found")
        self.assertIn('data-lucide="gem"', btn_block.group())

    def test_03_badge_quota_format_in_setBadge(self):
        """JS: _setBadge shows 'used / limit' from _quotaUsed/_quotaLimit"""
        self.assertIn("_quotaUsed + ' / ' + _quotaLimit", JS)

    def test_04_nb_talent_bank_css_class_exists(self):
        """CSS: .nb-talent-bank rule is defined"""
        self.assertIn(".nb-talent-bank", CSS)
        # Must NOT reuse teal color from nb-owner-action
        # It must use indigo/purple spectrum
        tb_block = re.search(
            r'\.nb-talent-bank\s*\{[^}]+\}', CSS
        )
        self.assertIsNotNone(tb_block)
        self.assertIn("rgba(99,102,241", tb_block.group())


# ══════════════════════════════════════════════════════════════════
# Group B — Pipeline status filters removed from Talent Bank
# ══════════════════════════════════════════════════════════════════
class B_FiltersRemoved(unittest.TestCase):

    def test_05_no_saved_filter_chip_in_renderChips(self):
        """JS: _renderChips only has 'الكل' — pipeline status values removed"""
        # Extract the chips array literal inside _renderChips
        chips_block = re.search(
            r'_renderChips.*?var chips\s*=\s*\[(.*?)\];', JS, re.S
        )
        self.assertIsNotNone(chips_block, "_renderChips chips array not found")
        arr = chips_block.group(1)
        self.assertNotIn("'saved'", arr)
        self.assertNotIn("'shortlisted'", arr)
        self.assertNotIn("'hired'", arr)
        self.assertNotIn("'rejected'", arr)

    def test_06_savedFilter_not_sent_to_backend(self):
        """JS: _savedFilter value is not included in fetch params"""
        # The old code sent filters.status = _savedFilter; that must be gone
        # Check inside _doFetchSavedPage
        fetch_block = re.search(
            r'_doFetchSavedPage.*?function _', JS, re.S
        )
        if not fetch_block:
            # fallback: just grep
            self.assertNotIn("filters.status = _savedFilter", JS)
        else:
            self.assertNotIn("filters.status = _savedFilter", fetch_block.group())

    def test_07_pipeline_status_badge_not_in_card_html(self):
        """JS: _savedCardHTML does not emit co-cand-status--saved/shortlisted badge in meta strip"""
        # The strip should show priority + rating but NOT pipeline status badge classes
        # We check the _savedCardHTML function body
        card_fn = re.search(
            r'function _savedCardHTML\(.*?\n  \}', JS, re.S
        )
        if card_fn:
            body = card_fn.group()
            # These are the old pipeline status badge CSS classes — must be gone
            self.assertNotIn("co-cand-status--saved", body)
            self.assertNotIn("co-cand-status--shortlisted", body)
        else:
            # Looser check
            # If those classes appear in cards section, fail
            # They may appear in CSS but not in _savedCardHTML JS
            self.assertNotIn(
                "co-cand-status--saved' + pipeSt",  # the old pattern
                JS
            )


# ══════════════════════════════════════════════════════════════════
# Group C — Tag prefix search (ILIKE + escaping + server validation)
# ══════════════════════════════════════════════════════════════════
class C_TagSearch(unittest.TestCase):

    def test_08_tag_ilike_prefix_in_auth(self):
        """auth.py: tag filter uses ILIKE prefix (not exact = ANY)"""
        # New code must use ILIKE with _tag_esc + '%'
        self.assertIn("ILIKE :tag_prefix", AUTH)

    def test_09_tag_escape_percent_in_auth(self):
        """auth.py: LIKE special chars escaped (%, _, \\)"""
        self.assertIn('.replace("%", "\\\\%")', AUTH)
        self.assertIn('.replace("_", "\\\\_")', AUTH)

    def test_10_tag_server_validation_max50(self):
        """server.py: tag param stripped and max 50 chars enforced"""
        self.assertIn("tag = tag.strip()", SERVER)
        self.assertIn("len(tag) > 50", SERVER)

    def test_11_tag_placeholder_updated(self):
        """JS: tag filter placeholder says 'بحث بالوسم…'"""
        self.assertIn("بحث بالوسم", JS)


# ══════════════════════════════════════════════════════════════════
# Group D — Card layout new CSS classes
# ══════════════════════════════════════════════════════════════════
class D_CardLayout(unittest.TestCase):

    def test_12_co_cand_info_head_exists_in_css(self):
        """CSS: .co-cand-info-head is defined"""
        self.assertIn(".co-cand-info-head", CSS)

    def test_13_co_cand_strip_exists_in_css(self):
        """CSS: .co-cand-strip is defined for the meta strip"""
        self.assertIn(".co-cand-strip", CSS)

    def test_14_co_cand_actions_column_in_css(self):
        """CSS: .co-cand-actions defined with flex-direction:column"""
        block = re.search(r'\.co-cand-actions\s*\{[^}]+\}', CSS)
        self.assertIsNotNone(block, ".co-cand-actions rule missing")
        self.assertIn("flex-direction:column", block.group())


# ══════════════════════════════════════════════════════════════════
# Group E — Save source labels
# ══════════════════════════════════════════════════════════════════
class E_SourceLabels(unittest.TestCase):

    def test_15_manual_label_is_correct(self):
        """JS: _SOURCE_LABELS['manual'] = 'حفظ يدوي'"""
        self.assertIn("manual:         'حفظ يدوي'", JS)

    def test_16_applicant_label_is_correct(self):
        """JS: _SOURCE_LABELS['applicant'] = 'متقدم لوظيفة'"""
        self.assertIn("applicant:      'متقدم لوظيفة'", JS)

    def test_17_legacy_unknown_label_present(self):
        """JS: _SOURCE_LABELS['legacy_unknown'] = 'بيانات سابقة'"""
        self.assertIn("legacy_unknown: 'بيانات سابقة'", JS)


# ══════════════════════════════════════════════════════════════════
# Group F — Job sections split
# ══════════════════════════════════════════════════════════════════
class F_JobSections(unittest.TestCase):

    def test_18_applied_section_title(self):
        """JS: 'تقدّم إلى:' section title present"""
        self.assertIn("تقدّم إلى:", JS)

    def test_19_linked_only_section_title(self):
        """JS: 'مرتبط بوظيفة:' section title present"""
        self.assertIn("مرتبط بوظيفة:", JS)

    def test_20_applied_chip_class_distinct(self):
        """CSS: .co-cand-job-chip--applied defined with different styling"""
        self.assertIn(".co-cand-job-chip--applied", CSS)
        block = re.search(r'\.co-cand-job-chip--applied\s*\{[^}]+\}', CSS)
        self.assertIsNotNone(block)
        # Must differ from default blue chip — check for teal/green color
        self.assertIn("34d399", block.group())  # green tint for applied


# ══════════════════════════════════════════════════════════════════
# Group G — Job chip popover label + date gate
# ══════════════════════════════════════════════════════════════════
class G_Popover(unittest.TestCase):

    def test_21_no_classification_label_updated(self):
        """JS: 'غير مصنف' replaced by 'لم يتم ترشيحه بعد'"""
        self.assertNotIn("'غير مصنف'", JS)
        self.assertIn("'لم يتم ترشيحه بعد'", JS)

    def test_22_apply_date_gated_on_appId(self):
        """JS: apply-date row in popover requires both appId AND applyDate"""
        # Find the popover apply-date condition
        match = re.search(
            r'if\s*\((\w+)\s*&&\s*(\w+)\)\s*\{[^}]*تاريخ التقدم', JS, re.S
        )
        self.assertIsNotNone(
            match,
            "apply-date row must be gated on appId AND applyDate"
        )
        vars_used = {match.group(1), match.group(2)}
        self.assertIn("appId", vars_used)
        self.assertIn("applyDate", vars_used)

    def test_23_popover_co_cjp_no_app_class_still_present(self):
        """JS: candJobCls 'co-cjp-no-app' still used for unclassified state"""
        self.assertIn("co-cjp-no-app", JS)


# ══════════════════════════════════════════════════════════════════
# Group H — Manage panel: notes counter + follow-up labels
# ══════════════════════════════════════════════════════════════════
class H_ManagePanel(unittest.TestCase):

    def test_24_notes_counter_has_ltr(self):
        """JS: notes counter span has dir='ltr' so N/M reads left-to-right"""
        self.assertIn('class="co-cand-panel-counter" dir="ltr"', JS)

    def test_25_followup_date_label(self):
        """JS: 'تاريخ المتابعة' label above date input"""
        self.assertIn("تاريخ المتابعة", JS)

    def test_26_followup_status_label(self):
        """JS: 'حالة المتابعة' label above status dropdown"""
        self.assertIn("حالة المتابعة", JS)


# ══════════════════════════════════════════════════════════════════
# Group I — Forbidden side-effects absent
# ══════════════════════════════════════════════════════════════════
class I_ForbiddenSideEffects(unittest.TestCase):

    def test_27_no_silent_application_creation_in_display(self):
        """JS: _savedCardHTML does not call createApplication or job_applications insert"""
        # This is a display function — it must not trigger API writes
        card_fn = re.search(r'function _savedCardHTML\(', JS)
        self.assertIsNotNone(card_fn)
        # Everything after the function start until the next top-level function
        snippet = JS[card_fn.start():card_fn.start() + 6000]
        self.assertNotIn("createApplication", snippet)
        self.assertNotIn("job_applications", snippet)

    def test_28_quota_limit_constant_unchanged(self):
        """auth.py: TALENT_BANK_FREE_LIMIT = 25 (quota not changed)"""
        self.assertIn("TALENT_BANK_FREE_LIMIT = 25", AUTH)

    def test_29_pipeline_stages_not_modified(self):
        """auth.py: VALID_CANDIDATE_STATUSES still contains the original 6 stages"""
        self.assertIn("'saved'", AUTH)
        self.assertIn("'shortlisted'", AUTH)
        self.assertIn("'interview'", AUTH)
        self.assertIn("'hired'", AUTH)
        self.assertIn("'rejected'", AUTH)


# ══════════════════════════════════════════════════════════════════
# Group J — PR-5 popover buttons still wired (regression guard)
# ══════════════════════════════════════════════════════════════════
class J_PR5Regression(unittest.TestCase):

    def test_30_notes_modal_button_class_present(self):
        """JS: .co-cjp-btn--notes button still exists in _showJobChipPop"""
        self.assertIn("co-cjp-btn--notes", JS)

    def test_31_appt_modal_button_class_present(self):
        """JS: .co-cjp-btn--appt button still exists in _showJobChipPop"""
        self.assertIn("co-cjp-btn--appt", JS)

    def test_32_close_popover_guard_contains_check(self):
        """JS: _closeJobPop guards against closing when click is inside popover"""
        self.assertIn("pop.contains(e.target)", JS)


# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    loader = unittest.TestLoader()
    loader.sortTestMethodsUsing = None   # preserve definition order
    suite = unittest.TestSuite()
    for cls in [
        A_ButtonRename, B_FiltersRemoved, C_TagSearch,
        D_CardLayout, E_SourceLabels, F_JobSections,
        G_Popover, H_ManagePanel, I_ForbiddenSideEffects,
        J_PR5Regression,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
