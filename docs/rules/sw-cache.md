# Service Worker Cache — كاش الـ Service Worker

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Service Worker Cache Rules (mandatory for all AI sessions)

1. **`sw.js` caches by allowlist only** (`isCacheableRequest()`): same-origin + GET + no `Authorization` + destination style/script/font/image/manifest + path `/static/*` · `/manifest.json` · `/icon-*.png`. API/JSON and HTML navigations are never cached.
2. **Any new endpoint needs NO change to `sw.js`** — the API is not cached by default. Do not reintroduce a `NO_CACHE` blocklist.
3. **Session-end cache wipe = `twClearAppCaches()` in `tw_shared.js` only**, called from `TwAuthSync.invalidateSession()` and the `twLogout()` fallback. Best-effort, never delays redirect. Do not write a second helper.
4. **Bump `BUILD_TIME` in `sw.js` on every change to `sw.js`.**
4b. **Offline fallback precache (Phase C — landing):** `STATIC_ASSETS` = `/landing.html` + `/manifest.json` + every shared CSS/JS of the Page Shell partials + `/static/shared/tw-icons.js` + `/static/app-header.css` (unified guest header — PR 4.1) + the page logo `/static/33333.svg`, stored without `?v=` and matched offline with `ignoreSearch` (exact URL first). A new asset in `partials/shell-*.html` or a new script / `<img>` on `landing.html` → add it here + bump `BUILD_TIME` in the same PR (test: `python tests/test_landing_shell.py`).
5. Full spec: `ARCHITECTURE.md §71` · `docs/SYSTEMS_INDEX.md §32`.
