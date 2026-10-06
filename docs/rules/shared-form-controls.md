# Shared Form Controls — عناصر النماذج المشتركة

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Shared Form Controls Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions:

1. **`static/shared/` is the canonical location** for all shared dropdown/picker UI and data. Files: `tw-select.js`, `tw-select.css`, `tw-options-data.js`, `flags/*.svg`. Never duplicate their logic inside a page file.

2. **Any new dropdown, year picker, or date picker must use the shared system.** Adding a new `<select>` with repeated data (countries, years, company types, sizes) without routing it through `TW.*` helpers in `tw-options-data.js` is forbidden.

3. **Forbidden — duplicating dropdown data per page.** Country names, year ranges, company types, company sizes, and city lists must live only in `tw-options-data.js`. Never copy-paste these arrays or objects into an HTML file, a page JS module, or inline `<script>`.

4. **Forbidden — native `<select>` for unified-experience pages.** Any page that uses the `ep-select` class must initialize the custom dropdown via `scSelectInit()` from `tw-select.js`. Do NOT leave a bare native select on a page that is supposed to match the Profile V2 / Company Profile design.

5. **Visual changes to dropdowns go in `static/shared/tw-select.css` only.** Do NOT add `.sc-sel-*` or `.tw-flag` overrides in page CSS files.

6. **`TW.fillSelect()`, `TW.fillCountries()`, `TW.fillCities()`, `TW.fillFoundedYears()` are the only approved fill helpers.** `TW.fillCountries(el, ph, opts)` accepts optional `opts = { valueMode: 'name_ar'|'code', withFlags: boolean }`. Do not write ad-hoc `for` loops to populate `<select>` options for data that already exists in `tw-options-data.js`.

7. **`scSelectInit()` must be called after dynamic option population.** Any time you populate a select's options at runtime (modal open, country-change, row insertion), call `if (window.scSelectInit) scSelectInit();` immediately after.

8. **`tw-options-data.js` must load before any page module that calls `TW.*`.** Load order: `tw-options-data.js` → `tw-select.js` → page state module → other modules.

9. **Profile V2 `epCountry` uses ISO codes (JO, SA, …) — not Arabic names.** This is a legacy DB contract (`profiles.country` for employees). `TW.fillCountries(el, ph, { valueMode:'code', withFlags:true })` is the correct call. `TW.countryEntry(isoCode)` bridges ISO → `TW.CITIES[name_ar]`. Do NOT change this storage without a DB migration.

10. **`TW.COUNTRY_MAP` is the single source of truth for country data.** `TW.COUNTRIES` (string array) is derived from it for backward compat. `TW.countryEntry(value)` accepts either ISO code or Arabic name. `TW.sameCountry(a, b)` handles mixed comparison (`'JO' == 'الأردن'` → `true`).

11. **Flag images come from `static/shared/flags/*.svg` only.** Never hard-code flag paths inside page JS. Always use `TW.countryFlagEl(value)` or `TW.COUNTRY_MAP[i].flagPath`. Never use CDN or emoji flags. License: MIT (HatScripts/circle-flags) — see `THIRD_PARTY_NOTICES.md`.

12. **No merge without user approval.** No PR touching shared form controls is to be merged automatically. Every merge requires explicit user instruction.
