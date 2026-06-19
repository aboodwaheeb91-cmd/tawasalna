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
├── index.html             # Login & registration (entry point)
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

**Any PR that includes a new feature, system, or architectural change MUST update `ARCHITECTURE.md` in the same PR.**

A PR is not considered complete if it introduces architectural changes without documentation.

Rules:
- New DB tables → document schema + constraints in ARCHITECTURE.md
- New API endpoints → document endpoint, auth requirements, request/response
- New Frontend systems → document components, state, behavior rules
- New Backend modules → document functions, mapping tables, rules
- Forbidden patterns → document what must NOT be done (ممنوعات)
- Implementation status → document what is done vs. pending

If `CLAUDE.md` contains AI behavior rules relevant to the new feature, add a summary there too.

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

2. **`/login` (index.html) is the Auth Gateway only.** It contains the login form and registration form. It is not a full Landing Page and must not be redesigned as one without an explicit request.

3. **Post-login redirect is role-based from the API response, not from inbox or messages.** The `redirect(u)` function in `index.html` is the single authority. Rules:
   - `emp` → `/u/{tw_id}` (canonical employee public profile)
   - `co` → `/company-profile`
   - `edu` → `/edu-profile`
   - `admin` → `/admin` (defensive; admin auth uses separate flow)

4. **`profile.html?id=` is a forbidden redirect target for new code.** Use `/u/{tw_id}` for employees. The legacy URL `profile.html?id=` must not appear in any new redirect, link, or button.

5. **`company-profile.html?id=` and `edu-profile.html?id=` are forbidden as new redirect targets.** Use `/company-profile` and `/edu-profile` (modern routes without query params).

6. **localStorage is a session cache, not the authority for roles.** `localStorage.tw_user` is populated by the API after login and used as a convenience cache. Never gate security-sensitive behaviour on it. TODO (P1): validate the session with `POST /auth/verify-token` before trusting localStorage data.

7. **Exactly one on-load redirect check in index.html.** Three duplicate blocks existed previously and were removed. Do not re-add more than one `try { redirect(_cached) }` block.

8. **Do NOT redirect to `/messages` or `/notifications` as the post-login landing destination.** These are secondary destinations reachable from the dashboard, not entry points after login.
