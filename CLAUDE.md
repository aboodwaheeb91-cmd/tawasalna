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

6. **Real-time transport is WebSocket for messages, polling for notifications.**
   - Messaging: WebSocket IS implemented — `/ws/{user_id}` in `server.py` + `messages.ws.js` client. ⚠️ P0 Security Debt: the route accepts any `user_id` without JWT verification (hardening deferred). Do not build new features on top of the WebSocket until the auth debt is resolved.
   - Notifications: HTTP polling only — `fetch('/notifications/{user_id}')`. No WebSocket for notifications.
   - Do not add a second WebSocket route for messages or notifications.

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
   - `/company-profile` (no params): serves a minimal redirect HTML that checks `tw_user.user_type === "co"` → redirects to `/u/{tw_id}`; non-co users → `/home`; no JWT → `/login`.
   - `/company-profile?id=123`: server-side 302 → `/u/{that_company_tw_id}`.
   - `/company-profile.html`: same as above.
   - **Owner mode is determined by `viewer_type` from the server via JWT** — never by which URL the user arrived at.

8. **Backward-compatible routes are permanent:** `/company-profile?id=`, `/edu-profile?id=`, `/profile-showcase` must continue to work — but they now do so via redirect to `/u/{tw_id}`, not by serving the page directly.

8. **Numeric id stays internal.** Never put `id` (integer) in a public share URL. Use `tw_id` only.

9. **Future entity public IDs** (J/P/A/V/D/E/L/Q/S) must use one shared generator in `auth.py` with **entity prefix only + random unique code — no country code, no ISO code, no dial code inside the public_id**. Signature: `generate_public_id(prefix)` — NOT `generate_public_id(prefix, country_code)`. Country data lives in the DB on the entity/user record; it must never be baked into the ID. Do NOT create a separate generator per entity type.

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

---

## Pre-PR System Registry Check (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

**Before implementing any new feature or opening a PR, you MUST:**

1. Read `docs/SYSTEMS_INDEX.md` — the authoritative index of all 33 documented systems.
2. Find the relevant system entry and note the "Source of Truth" and "Details" pointer.
3. Read the linked section in ARCHITECTURE.md or CLAUDE.md.
4. Read any shared files the system depends on.

Then decide:
- **Use** the existing system if it already covers the need.
- **Extend** the existing system if the need is a natural addition.
- **Document as missing** — add to `docs/SYSTEMS_INDEX.md → Systems Needing Documentation` before building anything new.

### Forbidden without checking the index first

```
❌ Building a system that duplicates an existing one
❌ Creating a DB table when an official table exists for the same purpose
❌ Using localStorage as permanent storage when a backend system exists or is planned
❌ Creating a per-page helper/catalog/mapping that already exists in a shared module
❌ Adding a new public profile route outside Smart Router
❌ Implementing skill icons or category lists outside tw-skills.js / tw-options-data.js
❌ Copying logic from one system into another instead of using the shared helper
```

### Index location

`docs/SYSTEMS_INDEX.md` — 33 systems, 9 categories. Read it before every PR.

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

---

## Rule Index First (mandatory for all AI sessions)

This rule is permanent and applies to all future AI sessions.

**Before implementing any new feature, fix, or opening a PR:**

1. Read `docs/SYSTEMS_INDEX.md` — the authoritative index of all documented systems.
2. Locate the system that matches your change. Note its "Source of Truth" and "Details" pointers.
3. Follow the documented system; do not rebuild it from scratch.

This rule is a shortcut to the full checklist in `CLAUDE.md → Pre-PR System Registry Check`. Both are mandatory — this one is the quick reminder, the other is the full procedure.

### Forbidden without reading the index first

```
❌ Building a system that duplicates an existing one
❌ Creating a DB table when an official table exists for the same purpose
❌ Adding a new endpoint that overlaps with a documented API contract
❌ Using localStorage as permanent storage when a backend system exists
❌ Creating a per-page helper/catalog/mapping that already exists in a shared module
```

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

## Post Appreciation System Rules — أقدّر (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

1. **Button label is frozen: "أقدّر".** Do not rename it, translate it, or change it to "أعجبني", "تقدير", or any other word. The word "أقدّر" was chosen deliberately and is permanent.

2. **Use the idempotent `PUT` endpoint.** `PUT /company/posts/{post_id}/appreciation` with `{"appreciated": bool}` is the canonical endpoint. The legacy `POST /appreciate` toggle remains in server.py for backward compatibility only — do not use it in new code.

3. **`INSERT ... ON CONFLICT DO NOTHING` is mandatory.** The DB operation must be idempotent. Never use a simple `INSERT` that can throw a unique-constraint error on rapid clicks.

4. **Rate limiter: 10 requests per 10 seconds per (user, post) pair.** The `_check_appr_rate` function in `server.py` enforces this. Do not remove it or relax the limits without an explicit security review.

5. **Desired State Queue is mandatory (no-flicker architecture).** The three module-level variables in `company.posts.js` are the core of the fast-click safety:
   - `_apprDesired[postId]` — the user's last-intended state
   - `_apprInFlight[postId]` — `true` while a request is in flight
   - `_apprOrigState[postId]` — the known-good state before the first in-flight request
   Do not simplify this to a plain toggle. Do not remove any of the three variables.

6. **No-flicker rule: check desired BEFORE rendering server response.** In `_dispatchAppreciation`, always check `desired !== undefined && desired !== srvActive` BEFORE calling `_renderAppreciationButton`. If stale, update `_apprOrigState`, dispatch follow-up, and `return` without rendering. Only render when server state matches desired.

7. **Self-appreciation is forbidden server-side.** The endpoint checks `owner_id === user_id` and returns HTTP 403. Do not add client-side bypasses.

8. **`company_post_appreciations` is the only table for post appreciations.** Do not create a second table for the same purpose.

9. **`_renderAppreciationButton(btn, active, count)` is the only DOM update point** for appreciation state. Do not update `.appr-active` class or `data-appr-count` anywhere else in `company.posts.js`.

---

## Post Save System Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.
Full technical specification: `ARCHITECTURE.md §64`.

1. **`company_post_saves` is the only table for post saves.** Schema: `id, post_id FK (ON DELETE CASCADE), user_id FK (ON DELETE CASCADE), created_at` with `UNIQUE(post_id, user_id)`. Do not create a second table for the same purpose.

2. **Use the idempotent `PUT` endpoint.** `PUT /company/posts/{post_id}/save` with `{"saved": bool}` is the canonical endpoint. `INSERT ... ON CONFLICT DO NOTHING` for save=true; plain `DELETE` (no-op if absent) for save=false.

3. **`viewer_saved` is the only source of truth for save state.** It is returned per-post from `GET /company/posts/{company_id}` when a JWT is present. Do not use localStorage as the save source.

4. **Save count is private.** Do not expose how many users saved a post publicly. There is no public save counter on the card.

5. **Owner can save their own post.** Unlike appreciation, there is no self-save restriction. The endpoint has no 403 for the post owner.

6. **Desired State Queue is mandatory.** The three module-level variables in `company.posts.js` mirror the appreciation queue pattern: `_saveDesired`, `_saveInFlight`, `_saveOrigState`. Do not simplify to a plain toggle.

7. **No-flicker rule applies to saves.** In `_dispatchSave`, check `desired !== undefined && desired !== srvActive` BEFORE calling `_renderSaveButton`. If stale, update `_saveOrigState`, dispatch follow-up, and `return` without rendering.

8. **`_renderSaveButton(btn, active)` is the only DOM update point** for save state. Do not update `.save-active` class, `data-saved`, or the button's icon/text anywhere else in `company.posts.js`. Button states are a permanent contract:
   - `active=true` → icon: `_ICO_BOOKMARK_CHECK` (filled bookmark + dark checkmark ✓), text: `'محفوظ'`, class: `save-active` (yellow `#fbbf24`)
   - `active=false` → icon: `_ICO_BOOKMARK_OUTLINE` (outline bookmark), text: `'حفظ'`, class: none (gray)

   `company.render.js` initial render must produce the same states using `icoBookmarkCheck` / `icoBookmark`. Any icon/text change must update both files in the same PR.

9. **Guest toast message is fixed:** `'سجّل دخولك لحفظ المنشور'`. Do not change this wording.

---

## Post Comments System Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.
Full technical specification: `ARCHITECTURE.md §65`.

1. **`company_post_comments` is the only table for post comments.** Do not create a second table for the same purpose.

2. **V1 is flat comments only.** No nested replies, mentions, or reactions on comments in V1. Do not implement reply threading without an explicit PR for that feature.

3. **`comments_enabled` is enforced server-side.** When `comments_enabled=false`, `create_company_post_comment()` raises `PermissionError` → HTTP 403. Do not rely on hiding the button alone.

4. **Permissions are server-side only:**
   - Edit: comment author only (`owner_id == user_id`)
   - Delete: comment author OR company page owner (`company_id == user_id`)
   - `viewer_can_edit` / `viewer_can_delete` flags are returned per-comment from `GET /company/posts/{post_id}/comments`
   - Never gate permissions on frontend state alone

5. **`comments_count` is the only source of truth for the count.** It comes from `get_company_posts()` LEFT JOIN. Do not count comments client-side or cache a count in localStorage.

6. **Soft delete is mandatory.** `delete_company_post_comment()` sets `status='deleted'` and `deleted_at=NOW()`. Hard delete is forbidden. `get_company_post_comments()` filters `status='active'` only.

7. **XSS protection is mandatory.** Comment `body` must only be rendered via `textContent` — never `innerHTML`. The `_cmtBuildItem()` function enforces this. Do not introduce `innerHTML` rendering of any API text in the comments panel.

8. **No localStorage for comments.** Comment data, counts, and state come from the API only. Do not cache comments or counts in `localStorage` or `sessionStorage`.

9. **`_toggleCommentPanel(postId)` is the single entry point** for opening/closing the comments panel. Do not add a second trigger or duplicate panel-open logic.

10. **No notifications in this PR.** The `comment_created` event is a future hook for Phase 3 (Notifications). Do not create a `notifications` table or send notifications in the comments PR.

11. **Do not change the appreciation system or save system.** The comments implementation must not modify `company_post_appreciations`, `company_post_saves`, their endpoints, or their frontend queue variables.

12. **Rate limits are permanent:** 10 create / 60s per (user, post), 10 edits / 60s per (user, comment). Do not remove or relax without a documented security review.

13. **Comment edit flow is a permanent contract (fix/comment-edit-ux):**
   - **Insert-first rule:** `editWrap` must be inserted into `.pc-cmt-content` BEFORE `bodyEl.style.display = 'none'`. Never hide the body before the editor is in the DOM.
   - **Correct parent:** `content.insertBefore(editWrap, acts)` where `content = item.querySelector('.pc-cmt-content')`. Do NOT use `item.insertBefore(editWrap, acts)` — `acts` is not a direct child of `item`.
   - **In-flight guard:** `_cmtEditInFlight[commentId]` prevents concurrent PATCH requests on the same comment. Check it at the top of `_cmtHandleEdit` AND inside the save handler.
   - **Optimistic UI:** `bodyEl.textContent = newBody` (XSS-safe) BEFORE the fetch call. On PATCH failure, rollback: `bodyEl.textContent = originalText`.
   - **XSS contract:** ALL text assignments in the edit flow use `textContent` — never `innerHTML`. This applies to `newBody`, `originalText`, and `res.data.comment.body`.
   - **Cancel:** restores body instantly, no request. `bodyEl.style.display = ''` + `editWrap.remove()`.
   - **"تم التعديل" badge** added to `.pc-cmt-header` on success (idempotent — only if not already present).
