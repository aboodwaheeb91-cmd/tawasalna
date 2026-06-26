# CLAUDE.md — تواصلنا (Tawasalna)

> Arabic Employment Platform & Credential Verification System

---

## Project Overview

**تواصلنا** ("Our Connection") is a full-stack Arabic employment platform serving three user types: employees, companies, and educational institutions. It provides job matching, credential verification, profile management, and direct messaging.

**Key characteristics:**
- Arabic-first, RTL UI design
- Multi-tenant: employees / companies / educational institutions
- Backend: FastAPI + PostgreSQL (Supabase)
- Frontend: Vanilla HTML/CSS/JS (no framework)
- Heroku-ready deployment via Procfile

---

## Repository Structure

```
tawasalna/
├── server.py              # Main FastAPI application — ALL backend logic lives here
├── auth.py                # Authentication helpers (bcrypt, tw_id generation, admin token)
├── auto_sync.py           # File watcher that auto-commits changes to GitHub
├── test.py                # Basic API integration tests
├── requirements.txt       # Python dependencies
├── Procfile               # Deployment: uvicorn server:app --host 0.0.0.0 --port $PORT
├── README.md              # Quick-start guide
│
├── index.html             # Auth Gateway — HTML structure only (login + register)
├── index.css              # Auth page styles — login/register only, NOT shared
├── index.auth.js          # Auth logic: redirect(), doLogin(), doRegister(), on-load check
├── index.ui.js            # UI logic: selectType(), form switching, toast, utilities
├── landing.html           # Public marketing page
├── home.html              # Employee feed (jobs, courses, news)
├── profile.html           # Employee profile editor (largest page ~147KB)
├── company.html           # Company: candidate search
├── company-profile.html   # Company: profile & job posting
├── edu.html               # Education institution: course dashboard
├── edu-profile.html       # Education institution: profile
├── job-detail.html        # Single job posting view
├── messages.html          # Direct messaging
├── notifications.html     # User notifications
├── employees-group.html   # Company: team member management
├── settings.html          # Account settings
├── admin.html             # Admin control panel
└── admin-view.html        # Admin analytics dashboard
```

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
| Deployment | Heroku / any $PORT platform | — |

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `SUPABASE_DB_URL` | **Yes** | PostgreSQL connection string |
| `PORT` | Yes (auto on Heroku) | Server port |
| `GITHUB_TOKEN` | Optional | Used by auto_sync.py for auto-commit |

---

## Running Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set the database URL
export SUPABASE_DB_URL="postgres://..."

# 3. Start the server (with auto-reload for development)
uvicorn server:app --reload

# 4. Run tests
python test.py
```

Server starts at `http://localhost:8000`.

---

## Authentication System (`auth.py`)

### Password Handling
- Hashed with **bcrypt** (salted)
- Minimum 6 characters enforced
- `hash_password(plain)` / `verify_password(plain, hashed)`

### User ID Format (tw_id)
Every user gets a unique platform ID:
```
{PREFIX}{COUNTRY_CODE}{10_RANDOM_HEX_CHARS}

Examples:
  U9620ec95e9c5ca  →  Jordanian employee
  C9660a1b2c3d4e5  →  Saudi company
  T9710f0e1d2c3b4  →  UAE educational institution
```

Prefixes: `U` = Employee, `C` = Company, `T` = Training/Education  
Country codes: JO=9620, SA=9660, AE=9710, EG=2000, IQ=9640, SY=9630 …

### Session Management
Sessions are stored in **localStorage** (client-side only) as JSON:
```json
{
  "id": 42,
  "tw_id": "U9620...",
  "full_name": "أحمد",
  "email": "ahmed@example.com",
  "user_type": "emp",
  "country_code": "9620",
  "created_at": "2025-01-01T00:00:00"
}
```

### Admin Authentication
- Password: `tw@admin2025`
- All admin API endpoints require the header: `X-Admin-Token: <sha256_of_password>`
- Admin panel URL: `/tw-ctrl-kPuOWhpIYjdLQXmh`

---

## Database Schema

Tables are auto-created on startup (with migrations for legacy data):

| Table | Key Columns |
|-------|-------------|
| `users` | id, tw_id (UNIQUE), full_name, email (UNIQUE), password_hash, user_type ('emp'/'co'/'edu'), country_code |
| `profiles` | user_id (UNIQUE FK), headline, bio, location, skills[], avatar_url, website, is_verified |
| `experience` | user_id FK, title, company, location, start_date, end_date, is_current, description |
| `education` | user_id FK, institution, degree, field, start_year, end_year, description |
| `user_skills` | user_id FK, skill, level |
| `user_langs` | user_id FK, language, level |
| `user_links` | user_id FK, link_type, url |
| `courses` | user_id FK, title, provider, completion_date, certificate_url, description |
| `jobs` | company_id FK, title, description, location, job_type, salary_min/max, skills[], status, views |
| `job_applications` | job_id FK, user_id FK, status ('pending'), cover_letter — UNIQUE(job_id, user_id) |
| `verify_requests` | user_id FK, item_type, item_id, item_title, document_url, status ('pending') |

---

## API Endpoints

### Authentication
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create account (emp / co / edu) |
| POST | `/auth/login` | Login, returns user object |
| GET | `/auth/user/{user_id}` | Get user info |
| PUT | `/auth/user/{user_id}/name` | Update display name |

### Profile
| Method | Path | Description |
|--------|------|-------------|
| GET | `/profile/{user_id}` | Public profile |
| GET | `/profile/{user_id}/full` | Full profile with credentials |
| PUT | `/profile/{user_id}` | Update profile |
| POST | `/experience/{user_id}` | Add work experience |
| POST | `/education/{user_id}` | Add education entry |
| POST | `/course/{user_id}` | Add completed course |
| POST | `/verify-request` | Submit credential verification request |

### Jobs & Matching
| Method | Path | Description |
|--------|------|-------------|
| GET | `/jobs` | List all jobs |
| POST | `/match` | Match CV text to jobs (returns top_k) |
| POST | `/feedback` | Log user feedback on a match |
| GET | `/stats` | Platform-wide statistics |

### Admin (require `X-Admin-Token` header)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/users` | List all users |
| GET | `/admin/verify-requests` | List pending verifications |
| PUT | `/admin/verify/{req_id}` | Approve / reject verification |
| GET | `/admin/profile/{user_id}` | View any user's full profile |
| DELETE | `/admin/user/{user_id}` | Delete user account |
| PUT | `/admin/user/{user_id}/type` | Change user type |
| PUT | `/admin/user/{user_id}/verify` | Set verified badge |
| PUT | `/admin/user/{user_id}/password` | Reset password |
| DELETE | `/admin/experience/{exp_id}` | Delete experience entry |
| DELETE | `/admin/education/{edu_id}` | Delete education entry |
| DELETE | `/admin/course/{course_id}` | Delete course entry |
| POST | `/admin/message` | Send message to user |

### HTML Pages (served by FastAPI)
| Path | File | Audience |
|------|------|---------|
| `/` | landing.html | Public |
| `/login` | index.html | All |
| `/home` | home.html | Employees |
| `/profile` | profile.html | Employees |
| `/company` | company.html | Companies |
| `/company-profile` | company-profile.html | Companies |
| `/edu` | edu.html | Education |
| `/edu-profile` | edu-profile.html | Education |
| `/job-detail` | job-detail.html | All |
| `/messages` | messages.html | All |
| `/notifications` | notifications.html | All |
| `/settings` | settings.html | All |
| `/tw-ctrl-kPuOWhpIYjdLQXmh` | admin.html | Admin only |

---

## CV Matching Algorithm

The matching engine in `server.py` uses **keyword overlap scoring**:

```python
score = count_of_matching_words(cv_text, job_description)
match_percent = min(score * 10, 100)
```

Returns `top_k` best-matching jobs (default 5). This is intentionally simple — see README for the roadmap toward RLHF-based ranking.

---

## Frontend Conventions

### Design System
| Token | Value |
|-------|-------|
| Primary (green) | `#00c896` |
| Secondary (blue) | `#2563ff` |
| Accent (purple) | `#8b5cf6` |
| Background | `#070b18` |
| Card surface | `rgba(255,255,255,.03)` |
| Font | Cairo (Google Fonts) |

### Patterns
- All pages are **RTL** (`dir="rtl"`, `font-family: 'Cairo'`)
- Sessions read/written via `localStorage` as JSON
- API calls use native `fetch()` — no axios or jQuery
- No bundler or build step — edit HTML files directly
- Glassmorphism cards: `backdrop-filter: blur(...)` + semi-transparent backgrounds
- Bottom navigation bar for mobile; sidebar for desktop

### Auth Guard Pattern (used in every page)
```js
const _u = JSON.parse(localStorage.getItem('tawasalna_user') || 'null');
if (!_u) { location.href = '/login'; }
```

---

## User Types & Access Control

| user_type | Arabic | What they can do |
|-----------|--------|-----------------|
| `emp` | موظف | Build profile, apply to jobs, request verifications |
| `co` | شركة | Post jobs, search candidates, send messages |
| `edu` | جهة تعليمية | Publish courses, verify student credentials |
| `admin` | مدير | Manage all users, approve verifications, analytics |

---

## Key Workflows

### 1. Registration Flow
1. `POST /auth/register` with `{ full_name, email, password, user_type, country_code }`
2. Server hashes password, generates `tw_id`, inserts into `users` + creates empty `profiles` row
3. Returns user object — client stores in localStorage

### 2. Credential Verification Flow
1. Employee submits `POST /verify-request` with document URL
2. Admin reviews at `/tw-ctrl-kPuOWhpIYjdLQXmh`
3. Admin calls `PUT /admin/verify/{req_id}` with `{ status: "approved" | "rejected" }`
4. Approved credentials show a verified badge on the employee's public profile

### 3. Job Matching Flow
1. Employee CV text sent to `POST /match`
2. Server scores each job by keyword overlap
3. Returns ranked list with match percentages
4. Employee's click tracked via `POST /feedback`

---

## auto_sync.py

Watches all project files and auto-commits to GitHub on save:
- Polls every **3 seconds**, waits **5 seconds** of inactivity before committing
- Watches extensions: `.py .html .txt .json .md .sh .toml .cfg .ini .yaml .yml`
- Requires `GITHUB_TOKEN` env var

Run in the background during development if you want auto-commits:
```bash
python auto_sync.py &
```

---

## Testing

```bash
python test.py
```

Tests: CV matching endpoint, feedback logging, stats endpoint. Tests are minimal — expand as features grow.

---

## Development Guidelines for AI Assistants

1. **All business logic lives in `server.py`** — this is the single source of truth for the backend. There is no separate routes/models/services split.

2. **Frontend pages are self-contained** — each HTML file includes its own `<style>` and `<script>` blocks. Do not introduce a build system unless explicitly requested.

3. **Database migrations are handled inline** — `server.py` runs `ALTER TABLE` / `CREATE TABLE IF NOT EXISTS` on startup. Add new migrations there.

4. **Respect RTL** — all UI text is Arabic. Use `dir="rtl"` and the Cairo font. Avoid left-to-right assumptions in CSS (use `margin-inline-start` instead of `margin-left` when adding new styles).

5. **Security notes:**
   - Admin token is hardcoded as a SHA256 hash in `auth.py` — do not log it or expose it
   - The admin URL token `kPuOWhpIYjdLQXmh` is security-through-obscurity; treat it as a secret
   - Passwords are never returned from any endpoint

6. **No real-time layer yet** — messages and notifications use polling (`fetch` on interval). Do not add WebSocket code without being asked.

7. **Supabase is the only database** — `SUPABASE_DB_URL` must be set. There is no local SQLite fallback.

8. **No front-end framework** — keep it vanilla JS. Adding React/Vue requires an explicit request and build tooling setup.

9. **IP geolocation** — `ip-api.com` is used to detect user country. Results are cached in `IP_TO_COUNTRY_CACHE` dict (in-memory, resets on restart).

---

## Deployment

```bash
# Heroku (or any platform supporting Procfile)
git push heroku main
# Set env vars:
heroku config:set SUPABASE_DB_URL="postgres://..."
```

The `Procfile` binds to `$PORT` automatically:
```
web: uvicorn server:app --host 0.0.0.0 --port $PORT
```

---

## Git Workflow Rules (mandatory for all AI sessions)

1. **بعد كل `git push` — افتح PR فوراً** بدون انتظار طلب من المستخدم.
2. **بعد كل PR يُدمج — تحقق من الـ branch** هل في commits لم تُدمج، وافتح PR جديد إذا في.
3. **لا تنتظر "افحص الpr" أو "افتح pr"** — افعلها تلقائياً.

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

---

## Auth Gateway Rules (mandatory for all AI sessions)

1. **`/` is the Landing Page.** `GET /` serves `landing.html`. Do not replace it with a login form or a dashboard redirect.

2. **`/login` (index.html) is the Auth Gateway only.** It contains the login form and registration form. It is not a full Landing Page. The page is split into three files: `index.html` (HTML), `index.auth.js` (auth logic), `index.ui.js` (UI effects). Do not merge them back.

3. **`redirect(u)` in `index.auth.js` is the single authority for post-login routing.** Rules:
   - `emp` → `/u/{tw_id}` (canonical employee public profile)
   - `co` → `/company-profile`
   - `edu` → `/edu-profile`
   - `admin` → `/admin` (defensive; admin auth uses separate flow)

4. **`profile.html?id=` is a forbidden redirect target for new code.** Use `/u/{tw_id}` for employees. The legacy URL `profile.html?id=` must not appear in any new redirect, link, or button.

5. **`company-profile.html?id=` and `edu-profile.html?id=` are forbidden as new redirect targets.** Use `/company-profile` and `/edu-profile` (modern routes without query params).

6. **localStorage is a session cache, not the authority for roles.** `localStorage.tw_user` is populated by the API after login and used as a convenience cache. Never gate security-sensitive behaviour on it. TODO (P1 next): validate the session with `POST /auth/verify-token` before trusting localStorage data.

7. **Exactly one on-load redirect check — in `index.auth.js`.** One IIFE only. Do not re-add redirect checks in `index.ui.js` or inline in `index.html`.

8. **Do NOT redirect to `/messages` or `/notifications` as the post-login landing destination.** These are secondary destinations reachable from the dashboard, not entry points after login.

9. **Role selector is register-only.** The three role cards (`#empBtn`, `#coBtn`, `#eduBtn`) are inside `#typeRow` which is hidden by default. `showRegister()` unhides it; `showLogin()` hides it. Do NOT show the role selector on the login form.

10. **`index.auth.js` must not contain DOM/appearance code.** UI side-effects (show/hide forms, button states, toast) belong in `index.ui.js`. The separation is mandatory — auth logic must remain testable in isolation.

11. **`index.css` is scoped to the auth page.** Do not import it from any other page. Do not put shared/global styles in it.

---

## Home V2 Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions:

1. **`/home` serves `home-v2.html`** — `home.html` (القديم) لم يعد production route. لا تعيده لـ `/home`.

2. **Feed-first is mandatory.** أي تعديل على Home V2 يجب أن يبدأ بـ filter tabs ثم feed. ممنوع إعادة Dashboard-first (بطاقة مستخدم ضخمة أول الصفحة).

3. **Files are split — keep them split (modular structure):**
   - `home-v2.html` — HTML هيكل فقط
   - `static/app-header.css` — CSS vars + `.sc-header` / `.sc-*` shared header classes
   - `static/app-header.js` — `initAppHeader(user)` — reserved, not used on Home currently
   - `static/home-v2.css` — أنماط الصفحة (`.hw-*` namespace)
   - `static/home-v2.js` — **DEPRECATED** — placeholder فقط، لا تضيف code هنا
   - `static/home/home.utils.js` — constants + DOM helpers
   - `static/home/home.state.js` — shared state (`window.Home.state`)
   - `static/home/home.api.js` — feed fetch (`Home.api.loadFeed`)
   - `static/home/home.cards.js` — card renderers (opportunity / post / news)
   - `static/home/home.render.js` — feed UI states (skeleton / empty / error / feed)
   - `static/home/home.filters.js` — filter tab wiring + orchestration
   - `static/home/home.header.js` — header buttons (home, menu, logout)
   - `static/home/home.nav.js` — bottom nav + sidebar + per-user-type setup
   - `static/home/home.main.js` — bootstrap only (auth guard + init + load)
   - ممنوع دمج CSS/JS الكبير داخل HTML
   - **ممنوع** إضافة logic في `static/home-v2.js`
   - **ممنوع** إضافة feature جديدة قبل تحديد module المناسب لها

4. **`/preview/home-v2` is deleted.** لا تعيد إضافته. Route المعاينة المؤقت أُزيل عند shipping Home V2.

5. **`GET /home/feed` is the feed API.** Auth: `Depends(verify_token)` — `user_id` من JWT فقط، ليس من query param. `filter` مُقيَّد server-side بـ allowlist: `{"all","opportunities","posts","news"}`.

6. **Rendering is always safe:** كل بيانات API تُعرض عبر `createElement` + `textContent`. لا `innerHTML = apiData`. السماح بـ `innerHTML` للـ skeleton الثابت فقط (لا يحتوي بيانات API).

7. **Home feed filters are final: `all / opportunities / posts / news`.**
   - `opportunities` — يعرض `jobs` حالياً (مع `opp_type="job"`). مستقبلاً يدعم training/scholarship/overseas.
   - `news` — أخبار رسمية من `news_posts` table، يُنشر من الأدمن فقط.
   - **ممنوع** إعادة `companies` كـ filter — مكانها صفحة استكشاف/بحث مستقلة في PR منفصل.
   - **ممنوع** إضافة `questions` أو `courses` أو أي filter آخر قبل بناء جدوله وendpoint حقيقي.
   - فلتر `news` فارغ بسبب غياب بيانات = **مقبول**. فلتر بدون جدول/API = **ممنوع**.

8. **`tw_jwt` is the auth token.** `localStorage.getItem('tw_jwt')` يُرسل كـ `Authorization: Bearer` في كل API call من Home V2.

9. **CSS offset is single-source:** `body { padding-top: var(--flt) }` — `.sc-header` هو `position:sticky` (في التدفق الطبيعي)، لا يحتاج padding. `.hw-fbar` هو `position:fixed` على `top:var(--ah-h,56px)`. ممنوع إضافة `margin-block-start` على `.hw-page`.

10. **`home.html` is legacy.** يمكن الاحتفاظ به كملف احتياطي لكنه ليس route. ممنوع حذفه أو تعديله دون سبب واضح.

11. **App Header is unified.** `static/app-header.css` هو المرجع الرسمي لـ CSS vars وshared header classes (`.sc-header`, `.sc-hicon`, `.sc-home-btn`, `.sc-menu-*`). ممنوع إنشاء header styles منفصلة لصفحة جديدة — يجب استخدام CSS vars من `app-header.css`. أي تعديل على شكل الهيدر يجب أن يكون في `app-header.css` فقط.

12. **Home مصمم لملايين المستخدمين — لا ديون تقنية.** قواعد إلزامية:
    - **ممنوع** إضافة feature جديدة فوق ملف واحد كبير — كل feature تذهب لـ module مناسب
    - **ممنوع** حلول مؤقتة أو TODO داخل production code
    - **ممنوع** `ORDER BY RANDOM()` في أي query على `/home/feed`
    - **ممنوع** table scan بدون index على columns مستخدمة في WHERE/ORDER — راجع `_migrate_feed_indexes()`
    - **مطلوب** اتباع `window.Home` namespace لأي module جديد
    - **مطلوب** تحديد module المناسب قبل إضافة أي سلوك جديد على Home

---

## Company Profile Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions:

1. **`static/company/` is the canonical location** for all Company Profile JS and CSS. Never add inline `<style>` or `<script>` blocks to `company-profile.html`.

2. **`company-profile.html` is HTML structure only.** It loads 7 module scripts and 1 CSS file. No logic lives inside it.

3. **Module load order is mandatory:**
   `company.state.js` → `company.api.js` → `company.permissions.js` → `company.render.js` → `company.jobs.js` → `company.posts.js` → `company.main.js`

4. **`company-profile.js` (root file) is superseded.** It must not be loaded from `company-profile.html`. The `/company-profile.js` server route remains in `server.py` but is unused.

5. **New features for Company Profile go into the appropriate module** — never a new root-level JS file, never inline in HTML.

6. **Security rules from PR #223 are permanent:**
   - All fetch calls use `Authorization: Bearer {jwt}` only — X-User-Id is forbidden
   - `_jwt()` from `company.state.js` is the only token source
   - Ownership checks stay server-side (DB query in server.py)

7. **`companyState` is the Single Source of Truth.** No other variable may serve as state for company profile data. `localStorage` is never used as an authority for company data.

8. **`window.X` namespace only.** No ES modules, no bundler. All cross-module calls go through `window.X` exposed at the bottom of each IIFE.

9. **Location field mapping is permanent (PR #248):**
   - `profiles.country` → stores Arabic country name (e.g. "الأردن") — edit field `e-country`
   - `profiles.city` → stores Arabic city name (e.g. "عمان") — edit field `e-city-sel`
   - `profiles.location` → stores street/district free text — edit field `e-district`
   - Display order: `country + '، ' + city`; if both empty → fall back to `p.location`
   - **Never** use `p.location` as the country; **never** swap city/country display order

10. **`ep-select` in company profile uses the shared custom dropdown.** Company profile loads `static/shared/tw-select.js` and `static/shared/tw-select.css`. The `.ep-select` class triggers the custom dropdown component — do NOT add `profile-v2.select.js` directly; use `tw-select.js` instead. The CSS-only fallback in `company.css` is kept for no-JS degradation only.

11. **Branches are saved to DB via `company_branches` table (PR feat/company-branches).** `_addBranchRow(data)` creates a branch card with 4 fields: branch_name input (`.b-name`) + country select (`.b-country`) + city select (`.b-city`) + district input (`.b-district`). On save, `saveEdit()` collects all `.branch-row` data and sends `PUT /company/branches/{id}` (snapshot replace, atomic). Opening the modal fetches `GET /company/branches/{id}` to pre-populate existing branches. Public profile loads branches via `loadBranches()` → `renderBranches()`. **Permanent constraints:** never use localStorage for branches; never use X-User-Id; never show branches in public profile without a real DB load; max 10 branches enforced server-side.

12. **Three fields are permanently removed from the edit form — DB columns untouched:**
    - `e-web` → `profiles.website` (still in DB; displayable in About tab)
    - `e-email` → `company_profiles.contact_email` (still in DB)
    - `e-hq` → `company_profiles.headquarters` (still in DB)

13. **`e-founded` is a `<select>` dropdown (not `<input type="number">`).** Options are generated by `_populateFoundedYears()` in JS (current year down to 1900). The function is idempotent — it checks `options.length > 1` before populating.

14. **District / area (`e-district`) is an `<input>` — not a dropdown.** No official source for Arabic neighborhood/district data exists. Do NOT invent a dropdown with made-up district names. If an official dataset is added later, convert then.

15. **`ep-select` visual is driven by `tw-select.js` + `tw-select.css`.** The CSS-only chevron in `company.css` is a no-JS fallback only. Do NOT use it as the primary styling mechanism. Any visual change to dropdowns goes in `static/shared/tw-select.css` — not in page CSS.

16. **No merge without user approval.** No PR is to be merged automatically. Every merge requires explicit user instruction.

---

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

## AI Usage Budget — Minimal Execution (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions. The goal is to preserve token budget and deliver changes efficiently.

### Work pattern (every task)

1. Understand the request.
2. Read only the necessary files.
3. Make the change in the fewest files possible.
4. Run one or two targeted tests — no more.
5. If tests pass → open PR and send the report.
6. If tests fail twice → **stop**, report the reason, do not continue diagnosing.

### Test scope by change type

| نوع التعديل | الاختبار المطلوب |
|------------|----------------|
| تعديل CSS بسيط | فحص بصري مختصر أو اختبار واحد |
| تعديل JS بسيط | اختبار واحد مركز على السلوك المطلوب |
| تعديل حفظ / API frontend | اختبارات محددة للنجاح والفشل فقط |
| تعديل docs فقط | لا يحتاج tests |
| تعديل backend أو DB | توقف واشرح السبب قبل توسيع الفحص |

### Forbidden without prior report

Before doing any of the following, stop and send a short report:

- أكثر من 3 اختبارات لتعديل واحد
- إنشاء diagnostic script جديد
- تعديل test file فقط حتى ينجح (بدون إصلاح الكود الحقيقي)
- تشغيل suite كامل أكثر من مرة
- Screenshots متعددة
- بحث طويل داخل ملفات كثيرة
- خطوات إضافية خارج نطاق المطلوب

The report must answer:
- ما المشكلة؟
- لماذا تحتاج توسع؟
- كم ملف ستلمس؟
- هل التوسع ضروري فعلاً؟
- هل يوجد حل أبسط؟

### Merge / Deploy rules

- **لا تدمج** إلا إذا قال المستخدم صراحةً "ادمج الآن".
- **لا تعمل deploy** إلا إذا طُلب صراحةً.
- افتح PR نظيف واترك الدمج للمستخدم.

### End-of-task report (mandatory)

Every completed task must end with:

- ماذا تم؟
- الملفات المعدلة.
- هل التعديل ضمن النطاق؟
- ما الاختبار الذي شغلته؟ وهل نجح؟
- هل يوجد شيء لم يُختبر؟
- هل PR جاهز للدمج؟

### Screenshots

لا تلتقط screenshots إلا إذا:
- طلب المستخدم صراحةً، أو
- الخطأ بصري ولا يمكن فهمه بدون صورة.

### The golden rule

> اشتغل بذكاء، مش بكثرة خطوات.
> إذا المشكلة تحتاج تشخيص طويل، توقف واسأل قبل ما تستهلك الرصيد.
