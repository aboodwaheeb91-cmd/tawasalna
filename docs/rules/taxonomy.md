# Unified Professional Taxonomy — التصنيف المهني الموحّد

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Unified Professional Taxonomy Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

1. **`skill_catalog` DB table is the official source for all skills.** Do NOT maintain hardcoded skill lists inside page JS files, HTML, or any file other than `auth.py` (`_SKILL_SEED` inside `_migrate_taxonomy_foundation()`).

2. **`TW.SKILL_CATALOG` in `tw-options-data.js` is fallback-only.** It is used internally by `tw-skills.js` as the initial synchronous catalog before the DB fetch completes. Never use it directly from page modules — always go through `TW.searchSkills / TW.normalizeSkill / TW.getSkillIcon`.

3. **`profession_categories` DB table is the official source for all professional specializations.** The `GET /professions` endpoint is the only approved way to load them on the frontend.

4. **`jobs.profession_id` is the canonical job specialization field.** `jobs.category` (legacy text) remains in DB but is NOT a primary UI source. Do NOT use `jobs.category` to drive UI or matching in new features.

5. **`GET /skills/catalog` is public (no auth required).** It has a 1-hour in-memory cache (`_skill_catalog_cache` in `server.py`). Do NOT add auth to it or change the cache TTL without a documented reason.

6. **Never duplicate skill data across files.** Any skill addition goes into `_SKILL_SEED` in `auth.py` only. The DB → `GET /skills/catalog` → `TW.SKILL_CATALOG` (fallback) flow is the only approved pipeline.

7. **`static/shared/tw-skills.js` is the only approved access point for skill catalog on the frontend.** All skill search, normalization, and icon lookup must go through `TW.searchSkills`, `TW.normalizeSkill`, `TW.getSkillIcon`, `TW._getSkillEntry`, `TW._isOfficialSkill`. Load order: `tw-options-data.js` → `tw-skills.js` → page skill module.

8. **Forbidden patterns (permanent — all 5 PRs complete):**
   ```
   ❌ Hardcoded skill arrays inside page JS files
   ❌ Hardcoded profession/category lists outside profession_categories DB table
   ❌ TW.SKILL_CATALOG used directly from page modules (it is fallback-only inside tw-skills.js)
   ❌ TW.JOB_CATEGORIES — DELETED in PR 5; do NOT re-add
   ❌ fetch('/skills/catalog') called directly from page modules (use tw-skills.js)
   ❌ jobs.category used as primary UI or matching source in new features
   ❌ Direct DB writes to skill_catalog outside auth.py migrations
   ❌ New j-cat or category select in Job Modal — replaced by j-prof (profession picker)
   ```

9. **All 5 PRs of the Unified Taxonomy System are complete.** No further taxonomy PRs are planned. Do NOT re-open or re-introduce any removed pattern.
