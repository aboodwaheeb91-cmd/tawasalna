# Profile Completion Card — بطاقة اكتمال البروفايل

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Profile Completion Card Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions:

1. **The completion strip is owner-only.** It must never be visible to visitors, guests, or in preview mode. Three independent layers enforce this:
   - `style="display:none"` on `#scComplCard` in HTML (default hidden)
   - `renderProfile` in `profile-v2.render.js` shows it **only** when `_vt === 'owner'`; the `else` branch explicitly hides it and clears `#scComplList`
   - `_isOwnerActive()` inside `profile-v2.completion.js` checks `window._scViewerType === 'owner'` AND body has no `preview-public-user` / `preview-guest` class; `_render`, `_doAction`, and all click handlers bail immediately if this returns `false`

2. **`window._scProfile` is the only data source.** No localStorage reads, no separate API calls, no hardcoded data.

3. **Weights must always sum to 100.** Adding or removing a checklist item requires rebalancing all weights so the total remains exactly 100.

4. **`window._scViewerType`** is set by `renderProfile` in `profile-v2.render.js` (`= _vt`). It is the authoritative viewer-type signal for all IIFE modules including `completion.js`. Do not read it before `renderProfile` runs.

5. **`window._updateCompletion()`** must be called after every successful add/edit/delete in all section save handlers (`exp`, `edu`, `courses`, `skills`, `langs`, `links`, `avatar`, `edit`). Do not add a new section save handler without this call.

6. **Do NOT invent a separate completion API endpoint.** The card derives its state entirely from the already-loaded `window._scProfile`.

7. **The strip is positioned inside `.sc-main-card`, between `.sc-actions` and `.sc-stats`.** Do not move it outside the main card or below the tabs.

8. **Dismiss state uses a module-level `_dismissed` variable only** (resets on page reload). Do NOT persist dismiss state to localStorage or sessionStorage.

9. **At 100% completion the strip switches to Growth Mode.** It shows one rule-based suggestion at a time from `_buildGrowthSuggestions()`. Button layout (RTL, left to right): "تفاصيل" (expand detail panel) | "↻" (cycle suggestion) | "✕" (dismiss session). Buttons are **solid-filled, not glassmorphic** — styled per ID: `#scGrowthDet` teal, `#scGrowthNext` neutral gray, `#scGrowthHide` red. The `_growthIdx` IIFE variable tracks the current suggestion index (never persisted). Do NOT show a "تم" dismiss button at 100% — growth mode replaces it. Clicking the suggestion **text** shows a **short 1-sentence actionable toast** (`#scGrowthToast`, 4 s) — not the full explanation. The **full explanation** (reason + benefit) is shown **only in the "تفاصيل" panel**. `_toastTimer` holds the active handle and is cleared on ↻ click or new toast.

10. **`_buildGrowthSuggestions()` rules must check that the suggested item is not already in the profile.** Each rule's `cond` must evaluate to `false` if the skill/course/link already exists. When the user adds the suggested item, `_updateCompletion()` is called, `_render()` re-runs `_buildGrowthSuggestions()`, and the satisfied rule drops out automatically. `_growthIdx` is clamped with `% suggs.length`.

11. **Growth mode and completion mode share the same `#scComplCard` container** but use separate row and panel elements (`#scComplRow`/`#scComplPanel` for completion, `#scGrowthRow`/`#scGrowthPanel` for growth). `_render()` shows exactly one mode and hides the other.

12. **All growth suggestion `text` values must follow the "learn/earn first, then document" ethical framing.** Never write text that implies adding a skill or course the user hasn't actually completed. Pattern: "تعلّم X ثم وثّقه" / "احصل على دورة X ثم أضفها". Do NOT write suggestions that could be read as "fake it till you make it".
