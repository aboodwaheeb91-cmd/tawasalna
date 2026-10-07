# CLAUDE.md — تواصلنا (Tawasalna)

## بروتوكول المهام (إلزامي لكل جلسة ولكل مهمة)
1. القراءة: اقرأ "فهرس القواعد" بأول ARCHITECTURE_FOUNDATION.md، ثم docs/SYSTEMS_INDEX.md كفهرس، ثم فقط نص القواعد والأنظمة المرتبطة بالمهمة. ممنوع قراءة ملفات توثيق كاملة بلا حاجة.
2. النظام أولاً: كل عنصر يُنفَّذ حسب نظامه الموثّق. لا يوجد نظام أو التغطية ناقصة → STOP واشرح (F30).
3. اقتراح قبل التنفيذ: إذا عندك حل أفضل أو أضمن معمارياً، أو اقتراح جميل وذكي → وقف واشرحه قبل التنفيذ. غير هيك نفّذ مباشرة.
4. النطاق: نفّذ المطلوب فقط. لا refactor ولا cleanup ولا redesign خارج المهمة.
5. السبب الجذري: حدّد السبب الجذري قبل الإصلاح، وصحّحه وليس العَرَض.
6. نقص بالنظام: إذا الخطأ كشف نقص بنظام → صحّح الكود والتوثيق بنفس الـ PR. إذا المشكلة تطبيق فقط → لا تعدّل التوثيق.
7. التوثيق: أي نظام أو قاعدة أو عقد جديد → SYSTEMS_INDEX + الملف التفصيلي بنفس الـ PR. حذف أي شي → يُحذف من الكود والتوثيق معاً.
8. GitHub: Pre-push GitHub State Check قبل أي رفع. PR مدموج → branch جديد من آخر main.
9. الدمج: ممنوع الدمج أو auto-merge. زعتر يدمج يدوياً.
10. الرصيد: اختبار واحد مركّز. بدون screenshots، بدون بحث بكل الريبو، بدون تشغيل كل الاختبارات. فشل الاختبار مرتين → وقف وبلّغ.
11. التقرير النهائي: رقم PR، آخر commit، الملفات، السبب الجذري، الاختبار ونتيجته، ما لم يُختبر، أي تغيير سلوك لازم زعتر يعرفه.
12. الجلسات: مهمة جديدة = جلسة جديدة. تصحيحات نفس الـ PR بنفس الجلسة.
13. سجل التحديثات: تاريخ التعديلات يُكتب كبند جديد بـ `docs/CHANGELOG.md` فقط (الأحدث فوق) — ممنوع تطويل سطر "Last updated" بأي ملف؛ كل ملف يحتفظ بسطر واحد قصير: آخر تاريخ + آخر PR + رابط `docs/CHANGELOG.md`.

---

> Arabic Employment Platform & Credential Verification System

---

## Project Overview

**تواصلنا** ("Our Connection") is a full-stack Arabic employment platform serving three user types: employees, companies, and educational institutions. It provides job matching, credential verification, profile management, and direct messaging.

**Key characteristics:**
- Arabic-first, RTL UI design
- Multi-tenant: employees / companies / educational institutions
- Backend: FastAPI + PostgreSQL (Supabase)
- Frontend: Vanilla HTML/CSS/JS (no framework)
- Railway deployment via Procfile (any `$PORT` platform works)

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend framework | FastAPI | 0.111.0 |
| ASGI server | Uvicorn | 0.30.1 |
| Database | PostgreSQL via Supabase (pg8000) | pg8000 1.31.2 |
| Password hashing | bcrypt | 4.1.3 |
| Frontend | Vanilla HTML/CSS/JS | — |
| Font | Google Cairo | — |
| Deployment | Railway (Procfile, `$PORT`) | — |

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
Source: `os.environ.get(...)` calls in `server.py` / `auth.py`. All secrets are set as Railway Variables — never in source.

| Variable | Required | Purpose |
|----------|----------|---------|
| `SUPABASE_DB_URL` | **Yes** | PostgreSQL connection string (`server.py` + `auth.py`) |
| `JWT_SECRET` | **Yes** | HS256 signing secret for user JWTs — independent of `ADMIN_TOKEN` |
| `ADMIN_TOKEN` | **Yes** (admin) | Admin login password + `X-Admin-Token` header value |
| `ADMIN_URL_TOKEN` | **Yes** (admin) | Slug for the admin panel path `/tw-ctrl-{ADMIN_URL_TOKEN}` |
| `SCHEDULER_SECRET` | Yes (scheduler) | `X-Scheduler-Secret` value for internal scheduler endpoints (503 when unset) |
| `SUPABASE_URL` | Yes (uploads) | Supabase project URL for Storage — must be `https://<project>.supabase.co` (cleaned of spaces / hidden chars / quotes; anything else = not configured) |
| `SUPABASE_SERVICE_KEY` | Yes (uploads) | Storage service key: new `sb_secret_…` (sent as `apikey` only) **or** legacy `service_role` JWT (deprecated by Supabase end of 2026). anon / publishable keys are rejected. Status logged at startup (never the value) — SYSTEMS_INDEX §29a |
| `REDIS_URL` | Optional | Redis cache; in-memory cache fallback when unset |
| `WS_ALLOWED_ORIGINS` | Optional | Comma-separated WebSocket origin allowlist; unset = production defaults; `*` raises at startup |
| `APP_ENV` | Optional | Default `production`; `development` adds localhost WS origins |
| `DEV_OTP_LOG` | Optional (dev) | Logs OTP events (never the code) |
| `CLIENT_IP_SOURCE` | Optional | `xff_left` (default) / `xff_right` / `x_real_ip` / `peer` — how `get_client_ip()` reads the client IP (ARCHITECTURE §52 → Client IP Resolution) |
| `TRUSTED_PROXY_HOPS` | Optional | With `xff_right`: position from the right of `X-Forwarded-For` (default 1) |
| `LOG_CLIENT_IP` | Optional (measure) | `1` → one `[client-ip]` line per `/auth/login` (headers + chosen IP, never credentials). Off by default |
| `TW_DEV_UPLOAD` | Optional (dev) | `1` + missing Supabase keys → `/upload/image` returns the data URL (`dev_mode`). Never set in production (PR-7a) |
| `PORT` | Yes (auto on Railway) | Server port |

---

## Running Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set the required environment variables (see table above)
export SUPABASE_DB_URL="postgres://..."
export JWT_SECRET="<random hex>"
export APP_ENV=development

# 3. Start the server (with auto-reload for development)
uvicorn server:app --reload

# 4. Run a focused test (one file — see docs/rules/project-reference.md → Testing)
python -m pytest test_post_comments.py -q
```

Server starts at `http://localhost:8000`.

---

## User Types & Access Control

| user_type | Arabic | What they can do |
|-----------|--------|-----------------|
| `emp` | موظف | Build profile, apply to jobs, request verifications |
| `co` | شركة | Post jobs, search candidates, send messages |
| `edu` | جهة تعليمية | Publish courses, verify student credentials |
| `admin` | مدير | Manage all users, approve verifications, analytics |

---

## Architecture Foundation (mandatory for all AI sessions)

**قبل أي تعديل أو ميزة جديدة، اقرأ "فهرس القواعد" بأول [`ARCHITECTURE_FOUNDATION.md`](ARCHITECTURE_FOUNDATION.md)، ثم فقط نص القواعد المرتبطة بالمهمة (بروتوكول المهام — البند 1).**

هذا الملف هو الدستور المعماري للمشروع. له أولوية على جميع التوثيقات التفصيلية.
إذا تعارض أي توثيق مع `ARCHITECTURE_FOUNDATION.md` — يُعتمد `ARCHITECTURE_FOUNDATION.md`.

القواعد العليا (F1–F39) غير قابلة للكسر إلا بموافقة معمارية صريحة موثَّقة في `ARCHITECTURE.md §C`.

---

## Git Workflow Rules (mandatory for all AI sessions)

1. **بعد كل `git push` — افتح PR فوراً** بدون انتظار طلب من المستخدم.
2. **بعد كل PR يُدمج — تحقق من الـ branch** هل في commits لم تُدمج، وافتح PR جديد إذا في.
3. **لا تنتظر "افحص الpr" أو "افتح pr"** — افعلها تلقائياً.

---

## Pre-push GitHub State Check (mandatory for all AI sessions)

هذه القاعدة إلزامية قبل **أي** commit / push / PR / إضافة على PR موجود — بدون استثناء.

### الفحص المطلوب

قبل أي رفع، قم بالتحقق من الحالة الفعلية على GitHub (عبر `mcp__github__pull_request_read`) وأجب على هذه النقاط في تقريرك:

```
Pre-push GitHub State Check:
- PR number:        [رقم الـ PR إن وجد]
- PR state:         open | closed
- merged:           true | false
- current branch:   [اسم الـ branch الحالي]
- base branch:      main | other
- latest main:      [آخر commit SHA على main]
- هل هذا PR مفتوح أم مدموج؟
- هل التعديل لازم يكون على نفس PR أم PR جديد؟
- القرار:           [push على branch حالي / branch جديد / PR جديد]
```

### قواعد القرار

- **اسم الـ branch لا يكفي** — تحقق من حالة الـ PR فعلياً على GitHub.
- **إذا PR مدموج (`merged: true`)** → أنشئ branch جديد من آخر main + PR جديد.
- **إذا PR مفتوح (`state: open`)** → يمكن الإضافة على نفس الـ branch.
- **لا تضيف commits على branch قديم** إذا كان الـ PR المرتبط به مدموجاً.
- **إذا نسيت هذا الفحص** → التقرير ناقص حتى لو الكود صحيح.

### مثال على خطأ يجب تجنبه

```
❌ إضافة commit على feat/company-followers-modal
   بعد دمج PR #295 — لأن اسم الـ branch موجود ≠ PR مفتوح
✅ الصح: fetch origin/main → branch جديد → PR جديد
```

---

## Documentation Rule (mandatory for all AI sessions)

**Every PR must include documentation updates in the same PR — PR description is NOT a substitute for `.md` files.**

### What to update per change type

| نوع التغيير | الملف المطلوب |
|------------|--------------|
| تغيير معماري / routes / صلاحيات / DB schema | `ARCHITECTURE.md` |
| مكتبة vendor جديدة / CDN → local / اعتمادية build | `ARCHITECTURE.md` قسم Vendor Assets + `README.md` إذا يؤثر على setup |
| سلوك صفحة أو flow مهم | `ARCHITECTURE.md` في قسم الصفحة المعنية |
| قاعدة جديدة يجب على AI الالتزام بها | `CLAUDE.md` |
| تغيير صغير لا أثر معماري له | اكتب في وصف PR: `Docs: not needed — [سبب واضح]` |

### Detailed rules

- New DB tables → document schema + constraints in ARCHITECTURE.md
- New API endpoints → document endpoint, auth requirements, request/response
- New Frontend systems → document components, state, behavior rules
- New Backend modules → document functions, mapping tables, rules
- Forbidden patterns → document what must NOT be done (ممنوعات)
- Vendor assets → add to Vendor Assets table in ARCHITECTURE.md with version + license

### PR Checklist (mandatory — add to every PR body)

```
- [ ] Code updated
- [ ] Docs updated (ARCHITECTURE.md / CLAUDE.md / README.md)
- [ ] Architecture impact checked
- [ ] No old routes/contracts broken
```

If docs are genuinely not needed, replace the "Docs updated" line with:
`- [x] Docs: not needed — [reason]`

---

## Smart Public Profile Router Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

1. **`/u/{tw_id}` is the unified public URL** for ALL account types (emp, co, edu). Do NOT create separate public routes like `/company-public/{tw_id}` or `/edu-public/{tw_id}`.

2. **`users.user_type` is the source of truth** for routing decisions. The tw_id prefix (U/C/T) is a hint only. The server MUST query the DB before serving any page.

3. **Helper `get_user_info_by_tw_id(tw_id)` in `auth.py`** is the only approved lookup for Smart Router. It returns `{ id, tw_id, user_type }`. Do NOT add routing logic that bypasses it.

4. **Injection pattern (mandatory):**
   - `emp` → inject `window._scProfileIdFromRoute = {int(uid)}` into `profile-showcase.html`
   - `co` → inject `window._companyProfileIdFromRoute = {int(uid)}` + `window._companyTwIdFromRoute = {json.dumps(tw_id)}` into `company-profile.html`
   - `edu` → inject `window._eduProfileIdFromRoute = {int(uid)}` + `window._eduTwIdFromRoute = {json.dumps(tw_id)}` into `edu-profile.html`

5. **Frontend load priority for company (`company.api.js`):**
   1. `window._companyProfileIdFromRoute` (Smart Router)
   2. `?id=` query param
   3. session owner fallback (only when both above are absent)

6. **Empty URL must return 404.** `/u` and `/u/` must never open a blank page. A dedicated `GET /u` route returns HTTP 404.

7. **`/company-profile` is a legacy redirect only (PR #386).** It is NOT a canonical URL and must not appear as a final link in share buttons, "شركتي" buttons, "إدارة الصفحة" buttons, or copy-link flows.
   - `/company-profile` (no params): serves the shared legacy redirect page (`_LEGACY_REDIRECT_HTML` in `server.py`) — see rule 10 below.
   - `/company-profile?id=123`: server-side 302 → `/u/{tw_id}` of account 123 (any type) — see rule 10.
   - `/company-profile.html`: same as above.
   - **Owner mode is determined by `viewer_type` from the server via JWT** — never by which URL the user arrived at.

8. **Backward-compatible routes are permanent:** `/company-profile?id=`, `/edu-profile?id=`, `/profile-showcase` must continue to work — but they now do so via redirect to `/u/{tw_id}`, not by serving the page directly.

8. **Numeric id stays internal.** Never put `id` (integer) in a public share URL. Use `tw_id` only.

9. **Future entity public IDs** (J/P/A/V/D/E/L/Q/S) must use one shared generator in `auth.py` with **entity prefix only + random unique code — no country code, no ISO code, no dial code inside the public_id**. Signature: `generate_public_id(prefix)` — NOT `generate_public_id(prefix, country_code)`. Country data lives in the DB on the entity/user record; it must never be baked into the ID. Do NOT create a separate generator per entity type.

10. **One legacy redirect page for every retired page URL (PR-4).** `_LEGACY_REDIRECT_HTML` in `server.py` is the single source for `/profile`, `/profile.html`, `/company`, `/company.html`, `/edu`, `/edu.html`, `/home.html`, `/jobs.html`, `/company-profile`, `/company-profile.html`.
   - `?id=N` (numeric, existing account of any type) → server-side **302 → `/u/{tw_id}`** via `_tw_id_for_user_id()` — the only id → tw_id lookup for legacy routes (F7 / F14).
   - No `?id=`, id that is not 1–18 ASCII digits (`id.isascii() and id.isdigit() and len(id) <= 18`), or unknown id → the redirect page (no 302, no lookup for invalid ids). It loads `tw_shared.js` → `auth-sync.js` and decides via `twEntryDestination()` (TwAuthSync snapshot only): authenticated → `twAccountHref(u)` = `/u/{tw_id}`; guest / expired / stale / invalid → `/login` (stale session invalidated first).
   - ❌ Re-creating a page file or a per-route redirect for any of these URLs.
   - ❌ Deciding the redirect from `tw_user` alone.
   - ❌ A second id → tw_id lookup for legacy routes.
   - Test: `python test_legacy_routes_cleanup.py`.

---

## Auth Gateway Rules (mandatory for all AI sessions)

1. **`/` is the Landing Page.** `GET /` serves `landing.html`. Do not replace it with a login form or a dashboard redirect.

2. **`/login` (index.html) is the Auth Gateway only.** It contains the login form and registration form. It is not a full Landing Page. The page is split into three files: `index.html` (HTML), `index.auth.js` (auth logic), `index.ui.js` (UI effects). Do not merge them back.

3. **`redirect(u)` in `index.auth.js` is the single authority for post-login routing.** It delegates the destination to **`twAccountHref(u)` in `tw_shared.js`** — the ONLY "my account" destination function (also used by `landing.html` via `twEntryDestination()`):
   - account with `tw_id` (emp / co / edu) → `/u/{tw_id}` (Smart Router decides the page by `users.user_type`)
   - no `tw_id` → `/login`
   - Do NOT re-add per-type branches (`/company-profile`, `/edu-profile`, `/admin`, `/profile-showcase`) in `redirect()` or `landing.html`.
   - `twHomeHref()` is a different concept — the **feed/dashboard** (`/home` for every account type; Home V2 renders a per-type view) used by header home buttons. Never use it as the post-login destination, and never merge it with `twAccountHref()`.

4. **`/profile` / `profile.html?id=` are retired (file deleted in PR-4) — redirect-only.** Use `/u/{tw_id}` for employees. They must not appear in any new redirect, link, or button.

5. **`company-profile.html?id=` and `edu-profile.html?id=` are forbidden as new redirect targets.** Use `/company-profile` and `/edu-profile` (modern routes without query params).

6. **localStorage is a session cache, not the authority for roles.** `localStorage.tw_user` is populated by the API after login and used as a convenience cache. Never gate security-sensitive behaviour on it. TODO (P1 next): validate the session with `POST /auth/verify-token` before trusting localStorage data.
   - **Entry pages decide from `TwAuthSync.getSessionSnapshot()` only (fix/stale-session-entry-redirect).** `landing.html` and the Auth Gateway (`index.auth.js` on-load + bfcache) call `twEntryDestination()` in `tw_shared.js`: redirect **only** when `isAuthenticated === true`; `expired` / `stale` / `invalid` → `TwAuthSync.invalidateSession('stale_entry')` with **no redirect**; `guest` or TwAuthSync missing → no redirect (fail-closed).
   - Both entry pages load `tw_shared.js` → `static/shared/auth-sync.js` before their entry check.
   - bfcache re-check in `index.auth.js` goes through `TwAuthSync.onSessionChange` (`reason === 'pageshow'`) — no direct `pageshow` listener.
   - ❌ Redirecting from an entry page because `tw_user` exists (this caused the expired-JWT login ↔ profile loop).
   - Test: `node test_stale_session_entry_runtime.js` (vm, real code).

7. **Exactly one on-load redirect check — in `index.auth.js`.** One IIFE only. Do not re-add redirect checks in `index.ui.js` or inline in `index.html`.

8. **Do NOT redirect to `/messages` or `/notifications` as the post-login landing destination.** These are secondary destinations reachable from the dashboard, not entry points after login.

9. **Role selector is register-only.** The three role cards (`#empBtn`, `#coBtn`, `#eduBtn`) are inside `#typeRow` which is hidden by default. `showRegister()` unhides it; `showLogin()` hides it. Do NOT show the role selector on the login form.

10. **`index.auth.js` must not contain DOM/appearance code.** UI side-effects (show/hide forms, button states, toast) belong in `index.ui.js`. The separation is mandatory — auth logic must remain testable in isolation.

11. **`index.css` is scoped to the auth page.** Do not import it from any other page. Do not put shared/global styles in it.

12. **`/login#register` opens the registration form directly.** `index.ui.js` contains a hash router that handles `#register`, `#register-emp`, `#register-co`, `#register-edu`. The global header menu's "إنشاء حساب" item must link to `/login#register` — NOT `/login` (which defaults to the login form). Login and Register menu items MUST have different hrefs.

13. **Auth Return Destination — `?next=` (PR #558 · `docs/design-system/NAVIGATION.md` NAV-07).** A page that sends a guest to login uses **`twLoginHref(next)` in `tw_shared.js`** → `/login?next=<encoded>`. **`twSafeNext(next)`** is the only validator: internal path only — one leading `/` (not `//`, not `/\`), no backslash / whitespace / control char, ≤ 512 chars, not `/login` itself; anything else (`https://…`, `//host`, `javascript:` …) is ignored. In `index.auth.js` a safe `?next=` wins over `twAccountHref(u)` in `redirect(u)` and over `twEntryDestination()` in the on-load check (authenticated only — guests stay on the form).
   - ❌ Hand-built `'/login?next=' + …` · ❌ a second next validator · ❌ reading `?next=` outside `index.auth.js`.
   - Test: `node test_auth_next_icon_hydrate_runtime.js`.

14. **Protected Page Guard — `twRequireAuth(opts)` in `tw_shared.js` (`docs/design-system/PAGE-SHELL.md` SHELL-09).** The ONLY way a page that needs a session sends a visitor away. The page declares `<meta name="tw-page" content="auth">` and calls `twRequireAuth()` once, first thing in its script, before any `fetch` (`if (!snap) return;`).
   - Decides from `TwAuthSync.getSessionSnapshot()` only: guest / expired / stale / invalid / no TwAuthSync → `location.replace(twLoginHref(pathname + search))`; authenticated + `opts.userTypes` without this type → `location.replace(twAccountHref(u))` (not `/login`); authenticated → returns the snapshot.
   - Registers once on `TwAuthSync.onSessionChange` (VM-01 — no own `pageshow` / `storage` listener): logout / expiry in another tab → same redirect; a different account signed in → `location.reload()`.
   - First consumers: `appointments.html` · `appointment-room.html`. Entry pages (`/`, `/login`) never use it — they use `twEntryDestination()`.
   - ❌ Reading `tw_user` / `tw_jwt` directly to gate a page · ❌ hand-built `location.href = '/login'` · ❌ a second page-local guard.
   - Test: `node test_appointments_guard_runtime.js`.

---

## Shared System First — Architecture Pattern Check (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

**Before implementing any new feature or change, always check:**

1. **Does a shared system already exist for this?** Look for existing helpers, components, CSS classes, data sources, or patterns in `static/shared/`, `ARCHITECTURE.md`, and this file before writing any new code.
2. **Is there a helper, component, CSS class, or data source already in the project that covers this need?** If yes — use it. Do NOT create a parallel implementation.
3. **Is this documented in `CLAUDE.md` or `ARCHITECTURE.md`?** If a rule or pattern is documented, follow it exactly. If it conflicts with a new requirement, stop and propose updating the docs first.
4. **Must this change use the existing shared system instead of a page-specific solution?** Any dropdown, flag, country data, formatter, or UI pattern that already exists in `static/shared/` must be sourced from there — not re-implemented per page.
5. **If no shared system exists: is it better to build a small clean shared system rather than a one-off solution?** If the same code or data would appear in 2+ pages, it belongs in a shared module — not duplicated. Build the shared module first, then use it.
6. **If you add a new shared system or pattern: document it in `CLAUDE.md` and/or `ARCHITECTURE.md` in the same PR.** New shared patterns are invisible to future AI sessions until documented.

### Forbidden patterns (ممنوعات ثابتة)

```
❌ Dropdown with hardcoded country/city data inside a page JS file
❌ A new modal pattern that doesn't follow the established modal behavior
❌ A new save flow that diverges from the documented save pattern
❌ A CSS chip/button/card class unique to one page when a shared class exists
❌ A formatter function repeated across two modules
❌ Hardcoded data (company types, sizes, year ranges) outside tw-options-data.js
❌ A temporary/quick fix when a shared architectural solution exists
```

### The Golden Rule

> أي شيء ممكن يتكرر في صفحتين أو أكثر، لا تعمله كحل خاص لصفحة واحدة.
> اعمله أو اربطه بـ shared system.

### Mandatory "Shared System Check" in every plan/report

Every implementation plan or execution report must include a section named **"Shared System Check"** that answers:

| السؤال | الجواب |
|--------|--------|
| هل تم فحص النظام الموجود؟ | نعم / لا + تفاصيل |
| هل استخدمنا shared system موجود؟ | نعم / لا + اسم الـ system |
| هل أضفنا helper/component/pattern مشترك جديد؟ | نعم / لا + الملف |
| هل قللنا التكرار أم زدناه؟ | قللنا / زدنا + التوضيح |
| هل يحتاج التعديل توثيق في CLAUDE.md أو ARCHITECTURE.md؟ | نعم / لا |
| إذا لا يحتاج توثيق — السبب؟ | [سبب واضح] |

### Examples of correct application

- بيانات الدول والمدن → `TW.COUNTRY_MAP` في `tw-options-data.js` (ليس داخل ملف صفحة)
- الأعلام → `TW.countryFlagEl()` من `tw-options-data.js` + `flags/*.svg` (ليس CDN أو emoji)
- القوائم المنسدلة → `tw-select.js` + `.ep-select` class (ليس native select جديد)
- formatter لعرض الفروع → `_formatBranchLabel()` مشترك بين chips والـ modal (ليس منطقان منفصلان)
- نمط الحفظ → `applyLocalUpdate()` pattern الموثق (ليس كل modal بطريقة مختلفة)
- أي بيانات متكررة → `tw-options-data.js` (ليس نسخ لصفحة واحدة)

---

## Safe Rendering / Output Escaping Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

1. **`twEscAttr(v)` in `tw_shared.js` is the canonical escaping implementation** (escapes `& < > " '`). `twEscHtml(v)` is an alias (safe superset). The old `sanitize()` alias was deleted (PR-4) — do NOT re-add it. Do NOT write a new escaping function in any page or module. One implementation only (§54).

2. **All API data inserted into `innerHTML` via template literals MUST be wrapped in `twEscHtml()`.** Raw `${u.full_name}` in innerHTML is a permanent violation.

3. **All API data inserted into HTML attribute values MUST be wrapped in `twEscAttr()`.** Raw `${u.email}` in `href`, `data-*`, or other attributes is a permanent violation.

4. **Image/URL src attributes must be validated before use — via `twSafeImageUrl(url)` in `tw_shared.js` (PR-7b, the only check).** Accepts only `https://` or a `/`-relative path (not `//` and not `/\`); everything else (javascript:, data:, vbscript:, http:, …) → `''`. CSS `background-image` only via `twCssUrl(url)` (validated + CSS-escaped). HTML string → `twEscAttr(twSafeImageUrl(url))`; DOM → `img.src = twSafeImageUrl(url)` (never `esc(url)`). The old inline regex `/^(https?:\/\/|\/(?!\/))/` is legacy — do not add new copies. Known debt: 7 local escaping functions on image paths (messages / company) — removed in DS-IMAGE phase C (`docs/design-system/IMAGE-SYSTEM.md` IMG-12). `profile-v2.utils.js → esc()` is now an alias of `twEscHtml` (PR 1.1) — not a separate implementation.

4b. **User-entered external links in `href` go through `twSafeLinkUrl(url)` in `tw_shared.js` (PR 1.1, the only check).** Accepts only `http://` / `https://` + a host char (not `https:///x`, not `https:\x`), no whitespace / control char anywhere, ≤ 2048; everything else (javascript:, data:, vbscript:, leading space, `//x`, `/path`, `www.x`) → `''` → the URL is rendered as **plain text, no `<a>` / no `href`**. Use `href="' + twEscAttr(safe) + '"` (HTML string) or `a.href = safe` (DOM), always with `rel="noopener noreferrer"`. Save forms check with the same helper before sending. Consumers: profile-v2 links (`sc-link-url`) + course certificate (`sc-cert-link`) · edu-profile website (`#aboutWeb` / `#aWeb`) · home news source (`hw-nbtn src`) · appointment-room `online_url`.
   - **Backend twin: `_validate_external_url(url, field, label, required=False)` in `server.py`** — same rule after `strip()`; empty → `None` (or 422 `"{label} مطلوب"` when required); bad → `ExternalUrlError` → 422 `{ok:false, error, errors:[{field, code:"invalid_url", message}], detail:{status, message, field}}` (Arabic message). Applied to `POST /links` (`url`, required) · `POST /course/{uid}` + `PUT /course/{id}` (`certificate_url`) · `PUT /profile/{uid}` (`website`) · `POST/PUT /admin/news` (`source_url`).
   - ❌ A new inline `/^https?:\/\//` check for a link · ❌ `href` from user data via `esc()` / `twEscAttr()` alone (escaping ≠ scheme check) · ❌ a second link validator in Python or JS.
   - Test: `python -m pytest test_safe_link_url.py -q`.

5. **Inline `onclick` with string interpolation of non-numeric user data is permanently forbidden.** Use `data-*` attributes + event delegation instead.

6. **`GET /admin.html` route is permanently deleted.** The admin panel is served only via `/tw-ctrl-{ADMIN_URL_TOKEN}`.

7. **`/tw-ctrl-login` is in the rate_limit_middleware list.** Do not remove it.

8. **`get_client_ip(request)` in `server.py` is the ONLY source of the client IP (PR 1.4).** Rate limiter, registration country, logs — all call it. Never read `X-Forwarded-For` / `X-Real-IP` anywhere else. Source chosen by `CLIENT_IP_SOURCE` (measured, not guessed — `ARCHITECTURE.md §52 → Client IP Resolution`). KYC OTP logic lives only in `auth._otp_issue` / `auth._otp_verify` (SYSTEMS_INDEX §54c).

---

## Documentation Completion Rule (mandatory for all AI sessions)

This rule is permanent and applies to all future AI sessions.

**A task is not "done" until all new rules and contracts are indexed.**

Any PR that introduces a new system, rule, contract, or permanent constraint MUST:

1. Add or update an entry in `docs/SYSTEMS_INDEX.md` — following the existing entry format (`**Purpose:**`, `**Source of Truth:**`, `**Details:**`, `**Do not recreate:**`).
2. Add the rule text in `CLAUDE.md` (for AI-facing rules) and/or `ARCHITECTURE.md` (for technical specs).
3. Include both documentation files in the same PR as the code change.

### What triggers documentation

| التغيير | الإجراء المطلوب |
|---------|----------------|
| نظام جديد (جدول DB + endpoint + frontend) | إدخال جديد في SYSTEMS_INDEX.md + قسم في ARCHITECTURE.md |
| قاعدة دائمة جديدة للـ AI sessions | قسم في CLAUDE.md + إدخال في SYSTEMS_INDEX.md إذا كان نظاماً |
| تغيير في contract موجود (endpoint/schema/behavior) | تحديث الإدخال الموجود في SYSTEMS_INDEX.md + ARCHITECTURE.md |
| تغيير صغير لا أثر معماري | اكتب في PR: `Docs: not needed — [سبب واضح]` |

### Forbidden

```
❌ Closing a PR with new rules documented only in the PR description
❌ Adding a new system without an SYSTEMS_INDEX.md entry
❌ Skipping CLAUDE.md updates for mandatory AI rules "to save time"
❌ Saying "docs will be added in a follow-up PR" for same-session work
```

---

## قوانين الأنظمة (System Rules Index — PR-3b)

قوانين كل نظام خاص منقولة **حرفياً** إلى `docs/rules/<system>.md`. هي **إلزامية بنفس قوة هذا الملف**: قبل أي تعديل يلمس نظاماً، افتح ملفه من الجدول (بروتوكول المهام — البند 1). أي إشارة قديمة بصيغة `CLAUDE.md → <قسم>` تُحلّ عبر هذا الجدول. نظام أو قاعدة خاصة جديدة → ملف في `docs/rules/` + سطر هنا + Details في `docs/SYSTEMS_INDEX.md` بنفس الـ PR.

| النظام / القسم القديم في CLAUDE.md | الملف |
|-----------------------------------|-------|
| Employee Name Fields Contract · Employment / Availability Status Rules · Profile V2 Action Buttons Rule | `docs/rules/profile-v2.md` |
| Profile Completion Card Rules | `docs/rules/profile-completion.md` |
| Home V2 Rules | `docs/rules/home-v2.md` |
| Company Profile Rules | `docs/rules/company-profile.md` |
| Saved Candidates — Three Sources of Truth | `docs/rules/saved-candidates.md` |
| Shared Form Controls Rules | `docs/rules/shared-form-controls.md` |
| Unified Professional Taxonomy Rules | `docs/rules/taxonomy.md` |
| Global Session UI Visibility System Rules — VM-10 | `docs/rules/vm10-header.md` |
| VM-01 bfcache Session Revalidation Rules | `docs/rules/vm01-bfcache.md` |
| Messenger Session Lifecycle Rules | `docs/rules/messenger.md` |
| Post Appreciation System Rules — أقدّر | `docs/rules/post-appreciation.md` |
| Post Save System Rules | `docs/rules/post-save.md` |
| Post Comments System Rules · Post Comments — Mention Atomicity Rules | `docs/rules/post-comments.md` |
| Color System V1 (DS-COLOR) Rules | `docs/rules/ds-color.md` |
| Size System V1 (DS-SIZE) Rules | `docs/rules/ds-size.md` |
| Icon System V1 (DS-ICON) Rules | `docs/rules/ds-icon.md` |
| Image Display System V1 (DS-IMAGE) Rules — أفاتار / لوغو / رابط صورة | `docs/rules/ds-image.md` |
| Page Shell V1 (DS-SHELL) Rules — `<head>` + سكربتات مشتركة لكل صفحة (markers `<!--tw:shell-*-->`) | `docs/rules/page-shell.md` |
| Shared Upload Client Rules | `docs/rules/upload.md` |
| Image Cropper System Rules | `docs/rules/image-cropper.md` |
| Service Worker Cache Rules | `docs/rules/sw-cache.md` |
| Authentication System (Password · tw_id / User ID Format · Session Management · Admin Authentication) | `docs/rules/auth-identity.md` |
| Development Guidelines for AI Assistants (incl. WebSocket / real-time contract) | `docs/rules/dev-guidelines.md` |
| Pre-PR System Registry Check · Rule Index First | `docs/rules/system-registry.md` |
| AI Usage Budget — Minimal Execution | `docs/rules/ai-usage-budget.md` |
| Repository Structure · API Endpoints (Authentication / Profile / Jobs) · Frontend Conventions (Design System · Patterns · Auth Guard Pattern) · Key Workflows (Registration · Credential Verification) · Testing · Deployment | `docs/rules/project-reference.md` |

### الجداول المرجعية (محذوفة من هنا — مكانها الصحيح)

| الجدول القديم | المرجع |
|--------------|--------|
| API Endpoints → Admin | `ARCHITECTURE.md §57 → Admin Endpoints` |
| API Endpoints → HTML Pages | `ARCHITECTURE.md → Routing & Navigation Rules (Global) → HTML Page Routes` |
| Database Schema | `ARCHITECTURE.md §72 — Core Schema` |
