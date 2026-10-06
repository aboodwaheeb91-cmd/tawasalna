# Profile V2 — بروفايل الموظف

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Employee Name Fields Contract (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

1. **`first_name` + `middle_name` + `last_name` are the ONLY channels** for mutating an employee's displayed name. The `full_name` column in `users` is auto-built by `_norm_name()` — never written directly by the frontend or via a direct `full_name` field in the payload.

2. **`emp_name_mutation_forbidden` is a permanent server error code (HTTP 422).** It fires in `update_profile()` when a payload includes `full_name` while `user_type === 'emp'`. Frontend must never send `full_name` in any employee profile save call.

3. **Atomic Name Group Rule:** `first_name`, `middle_name`, `last_name` must be sent together or omitted entirely (DS-FRM Tri-state Delta). Sending only `middle_name` without `first_name` + `last_name` is rejected server-side.

4. **`update_profile()` in `auth.py` enforces this via the `user_type` parameter** — passed from JWT by the endpoint. Do NOT bypass the user_type check or add logic that allows emp accounts to write `full_name` directly.

5. **Frontend `_routeFieldError()` in `profile-v2.edit.js`** routes `emp_name_mutation_forbidden` to `#epNameErr` — the same element as `first_name_required`. This is intentional: the error surfaces near the name inputs.

---

## Employment / Availability Status Rules (mandatory)

These rules are permanent and apply to all future AI sessions:

1. **`profiles.avail` is the single source of truth** for employment/availability status. No second field may serve the same purpose.

2. **`availability_status` is deprecated and hardened-out.** The DB column exists but must not appear in:
   - `ProfileUpdateInput` fields
   - `update_profile` `allowed` or `_clearable` lists
   - Any SELECT query in `auth.py`
   - Any frontend variable or API call

3. **The availability dot on the profile avatar is a visual shortcut to `avail`.** Saving from the dot writes to `avail`; saving from the edit modal writes to `avail`; both surfaces must always be in sync.

4. **Public profile share URL must always be `/u/{tw_id}`**, not `/profile?id=`. The `/u/{tw_id}` route is served by `server.py` and is the canonical public URL for Profile V2.

---

## Profile V2 Action Buttons Rule (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

The three action buttons inside `.sc-actions` in `profile-showcase.html` — `#scFollowBtn`, `#scContactBtn`, `#scFullBtn` — have frozen dimensions defined in `profile-v2.css` lines 248–262. These values were inspected on 2026-06-29 and must not change without a dedicated, explicitly-scoped PR.

### Frozen values (source: `profile-v2.css`)

**Container — `.sc-actions` (line 248):**
- `display: flex; flex-direction: row; align-items: center; justify-content: center`
- `flex-wrap: nowrap`
- `gap: 10px` — gap between buttons
- `padding: 6px 20px 13px`

**Button base — `.sc-btn` (line 252):**
- `height: 27px`
- `border-radius: 9px`
- `font-size: 11px`
- `font-weight: 700`
- `gap: 5px` — gap between icon and text
- `display: inline-flex; align-items: center; justify-content: center`
- `flex-shrink: 0`

**Variants — `.sc-btn-primary` / `.sc-btn-ghost` (lines 259–260):**
- `padding: 0 18px` (both variants — identical horizontal padding)

**Icon — `.sc-btn .ico-sm` (line 262):**
- `width: 14px; height: 14px`
- `stroke-width: 1.8`
- `flex-shrink: 0`

**Responsive:** No media queries resize these buttons. Dimensions are identical on all screen sizes.

### Forbidden without a dedicated PR

```
❌ Changing .sc-btn height from 27px
❌ Changing .sc-btn padding from 0 18px
❌ Changing .sc-btn font-size from 11px
❌ Changing .sc-btn gap (icon ↔ text) from 5px
❌ Changing .sc-actions gap (between buttons) from 10px
❌ Changing .sc-actions padding from 6px 20px 13px
❌ Changing icon size from 14×14px or stroke-width from 1.8
❌ Changing border-radius from 9px
❌ Adding a media query that resizes buttons on mobile/desktop
❌ Splitting .sc-btn-primary and .sc-btn-ghost to different heights
❌ Restyling these buttons as part of an unrelated PR
```

Any AI session that needs to change button dimensions must open a **standalone PR with an explicit title** (e.g. `design: resize Profile V2 action buttons`) and must not bundle the change with unrelated work.
