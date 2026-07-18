"""
Talent Bank V3 — Compact Expandable Cards structural tests.
Verifies JS and CSS sources contain the expected patterns.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parent
JS_SRC  = (ROOT / "static" / "company" / "company.main.js").read_text()
CSS_SRC = (ROOT / "static" / "company" / "company.css").read_text()


class TestStatusChipsRemoved(unittest.TestCase):
    """Status filter chips row must be gone from _savedShellHTML."""

    def _shell_fn(self):
        m = re.search(
            r"function _savedShellHTML\(\)(.*?)(?=\n  function |\n  var |\Z)",
            JS_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "_savedShellHTML function not found")
        return m.group(1)

    def test_no_coCandChips_in_shell(self):
        body = self._shell_fn()
        self.assertNotIn('id="coCandChips"', body,
            "coCandChips div must be removed from _savedShellHTML")

    def test_quota_label_has_rtl_dir(self):
        body = self._shell_fn()
        self.assertIn('dir="rtl"', body,
            "Quota label must have dir=rtl for correct Arabic display")


class TestCompactCardStructure(unittest.TestCase):
    """_savedCardHTML must emit the V3 compact expandable structure."""

    def _card_fn(self):
        m = re.search(
            r"function _savedCardHTML\(item\)(.*?)(?=\n  function |\n  var |\Z)",
            JS_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "_savedCardHTML function not found")
        return m.group(1)

    def test_data_rating_attribute_on_card(self):
        body = self._card_fn()
        self.assertIn('data-rating=', body,
            "Card must have data-rating attribute for CSS border/glow")

    def test_data_expanded_attribute_on_card(self):
        body = self._card_fn()
        self.assertIn('data-expanded="false"', body,
            "Card must start collapsed (data-expanded=false)")

    def test_compact_header_class(self):
        body = self._card_fn()
        self.assertIn('co-csc-header', body,
            "Compact header .co-csc-header must exist")

    def test_avatar_class(self):
        body = self._card_fn()
        self.assertIn('co-csc-ava', body,
            "Avatar element .co-csc-ava must exist in header")

    def test_name_and_profession_in_header(self):
        body = self._card_fn()
        self.assertIn('co-csc-name', body)
        self.assertIn('co-csc-profession', body)

    def test_stars_in_header(self):
        body = self._card_fn()
        self.assertIn('co-csc-stars', body,
            "Star rating must appear inside compact header")

    def test_toggle_button_exists(self):
        body = self._card_fn()
        self.assertIn('co-csc-toggle', body,
            "Toggle button .co-csc-toggle must exist")

    def test_toggle_aria_expanded(self):
        body = self._card_fn()
        self.assertIn('aria-expanded="false"', body,
            "Toggle button must start with aria-expanded=false")

    def test_chevron_svg_exists(self):
        body = self._card_fn()
        self.assertIn('co-csc-chevron', body,
            "Chevron SVG .co-csc-chevron must exist inside toggle")

    def test_body_is_hidden_by_default(self):
        body = self._card_fn()
        self.assertIn('co-csc-body" hidden', body,
            "Expandable body must have hidden attribute by default")

    def test_source_row_always_present(self):
        body = self._card_fn()
        self.assertIn('co-csc-source-row', body,
            "مصدر الحفظ row must always be present")

    def test_action_buttons_inside_body(self):
        body = self._card_fn()
        self.assertIn('co-csc-actions', body,
            "Action buttons section must exist inside expandable body")
        self.assertIn('co-csc-btn--view', body,
            "View profile button must exist")
        self.assertIn('co-csc-btn--manage', body,
            "Manage button must exist")

    def test_view_btn_links_to_public_profile(self):
        body = self._card_fn()
        self.assertIn('/u/', body,
            "View button must link to /u/{tw_id} (not /profile?id=)")

    def test_no_left_right_column_split(self):
        body = self._card_fn()
        # Old V2 split used .co-cand-top (header) + .co-cand-actions columns
        self.assertNotIn('co-cand-actions', body,
            "Old .co-cand-actions column must be removed (no left/right split)")
        self.assertNotIn('co-cand-top', body,
            "Old .co-cand-top wrapper must be removed")

    def test_manage_panel_inside_body(self):
        body = self._card_fn()
        # manage panel HTML should appear after co-csc-body opening
        body_idx  = body.find('co-csc-body')
        panel_idx = body.find('co-cand-manage-panel')
        self.assertGreater(panel_idx, body_idx,
            "Manage panel must be inside .co-csc-body (collapsed with card)")


class TestToggleCardFunction(unittest.TestCase):
    """_toggleCard must implement accordion + aria pattern."""

    def _toggle_fn(self):
        m = re.search(
            r"function _toggleCard\(btn\)(.*?)(?=\n  function |\n  var |\Z)",
            JS_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "_toggleCard function not found")
        return m.group(1)

    def test_closes_other_open_cards(self):
        body = self._toggle_fn()
        self.assertIn('data-expanded="true"', body,
            "_toggleCard must query and close other open cards")

    def test_sets_data_expanded(self):
        body = self._toggle_fn()
        self.assertIn("setAttribute('data-expanded'", body,
            "_toggleCard must set data-expanded attribute")

    def test_sets_hidden_on_body(self):
        body = self._toggle_fn()
        self.assertIn('.hidden', body) if '.hidden' in body else \
        self.assertIn('hidden', body,
            "_toggleCard must toggle hidden attribute on .co-csc-body")

    def test_sets_aria_expanded(self):
        body = self._toggle_fn()
        self.assertIn("setAttribute('aria-expanded'", body,
            "_toggleCard must update aria-expanded on toggle button")

    def test_sets_aria_label(self):
        body = self._toggle_fn()
        self.assertIn("setAttribute('aria-label'", body,
            "_toggleCard must update aria-label for accessibility")

    def test_close_closes_manage_panel(self):
        body = self._toggle_fn()
        self.assertIn('co-cand-manage-panel', body,
            "_toggleCard must close manage panel when collapsing")


class TestOnSavedClickHandler(unittest.TestCase):
    """_onSavedClick must route toggle clicks first."""

    def _handler_fn(self):
        m = re.search(
            r"function _onSavedClick\(e\)(.*?)(?=\n  function |\n  var |\Z)",
            JS_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "_onSavedClick function not found")
        return m.group(1)

    def test_toggle_handled_first(self):
        body = self._handler_fn()
        toggle_idx = body.find('co-csc-toggle')
        manage_idx = body.find('co-cand-manage-btn')
        self.assertLess(toggle_idx, manage_idx,
            "Toggle button must be handled before manage button in _onSavedClick")


class TestApplyCardUpdateFunction(unittest.TestCase):
    """_applyCardUpdate must update new V3 DOM selectors."""

    def _update_fn(self):
        m = re.search(
            r"function _applyCardUpdate\(card, data\)(.*?)(?=\n  function |\n  var |\Z)",
            JS_SRC, re.DOTALL
        )
        self.assertIsNotNone(m, "_applyCardUpdate function not found")
        return m.group(1)

    def test_updates_data_rating(self):
        body = self._update_fn()
        self.assertIn("setAttribute('data-rating'", body,
            "_applyCardUpdate must update data-rating for live border/glow")

    def test_updates_stars_selector(self):
        body = self._update_fn()
        self.assertIn('co-csc-stars', body,
            "_applyCardUpdate must target .co-csc-stars for rating display")

    def test_updates_name_row(self):
        body = self._update_fn()
        self.assertIn('co-csc-name-row', body,
            "_applyCardUpdate must target .co-csc-name-row for priority badge")

    def test_updates_notes(self):
        body = self._update_fn()
        self.assertIn('co-csc-notes', body,
            "_applyCardUpdate must target .co-csc-notes for notes update")

    def test_updates_fu_row(self):
        body = self._update_fn()
        self.assertIn('co-csc-fu-row', body,
            "_applyCardUpdate must target .co-csc-fu-row for follow-up update")


class TestCSSCompactCards(unittest.TestCase):
    """company.css must contain the V3 compact card styles."""

    def test_coCandSavedList_flex_column(self):
        self.assertIn('#coCandSavedList', CSS_SRC,
            "#coCandSavedList list container must be styled")
        self.assertIn('flex-direction:column', CSS_SRC)

    def test_card_standalone_box(self):
        m = re.search(
            r"\.co-cand-saved-card\s*\{[^}]*border-radius:\s*10px",
            CSS_SRC
        )
        self.assertIsNotNone(m,
            ".co-cand-saved-card must have border-radius (standalone box)")

    def test_no_border_bottom_separator(self):
        m = re.search(
            r"\.co-cand-saved-card\s*\{[^}]*border-bottom:[^}]*\}",
            CSS_SRC
        )
        self.assertIsNone(m,
            ".co-cand-saved-card must NOT have border-bottom (old separator style)")

    def test_rating_glow_rules(self):
        for r in ['5', '4', '3', '2', '1']:
            self.assertIn(f'[data-rating="{r}"]', CSS_SRC,
                f"Rating {r} border/glow rule must exist")

    def test_csc_header_rule(self):
        self.assertIn('.co-csc-header', CSS_SRC)

    def test_csc_toggle_rule(self):
        self.assertIn('.co-csc-toggle', CSS_SRC)

    def test_csc_chevron_rotation(self):
        self.assertIn('co-csc-chevron', CSS_SRC)
        self.assertIn('rotate(180deg)', CSS_SRC,
            "Chevron must rotate 180deg when card is open")

    def test_csc_body_hidden_pattern(self):
        self.assertIn('.co-csc-body:not([hidden])', CSS_SRC,
            "Body must use :not([hidden]) selector for flex layout when visible")

    def test_csc_btn_rules(self):
        self.assertIn('.co-csc-btn--view', CSS_SRC)
        self.assertIn('.co-csc-btn--manage', CSS_SRC)

    def test_csc_notes_line_clamp(self):
        self.assertIn('.co-csc-notes', CSS_SRC)
        self.assertIn('-webkit-line-clamp', CSS_SRC)

    def test_followup_color_rules(self):
        self.assertIn('.co-csc-followup--pending', CSS_SRC)
        self.assertIn('.co-csc-followup--done', CSS_SRC)


if __name__ == "__main__":
    unittest.main(verbosity=2)
