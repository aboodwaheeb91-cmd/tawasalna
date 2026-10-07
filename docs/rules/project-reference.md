# Project Reference — مرجع المشروع العام

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Repository Structure

```
tawasalna/
├── server.py              # FastAPI app — routes, JWT, WebSocket, middleware, migrations
├── auth.py                # DB data layer + business logic (users, profiles, jobs, comments, pipeline, bcrypt, tw_id)
├── requirements.txt       # Python dependencies
├── Procfile               # Deployment: uvicorn server:app --host 0.0.0.0 --port $PORT
├── README.md              # Quick-start guide
│
├── index.html             # Auth Gateway — HTML structure only (login + register)
├── index.css              # Auth page styles — login/register only, NOT shared
├── index.auth.js          # Auth logic: redirect(), doLogin(), doRegister(), on-load check
├── index.ui.js            # UI logic: selectType(), form switching, toast, utilities
├── landing.html           # Public marketing page
├── home-v2.html           # Home V2 feed (/home) — per-account-type view
├── profile-showcase.html  # Employee profile (served by /u/{tw_id})
├── company-profile.html   # Company: profile, jobs, Talent Bank (served by /u/{tw_id})
├── edu-profile.html       # Education institution: profile
├── job-detail.html        # Single job posting view
├── messages.html          # Direct messaging
├── notifications.html     # User notifications
├── settings.html          # Account settings
├── admin.html             # Admin control panel
└── admin-view.html        # Admin analytics dashboard
```

---

## API Endpoints

### Authentication
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create account (emp / co / edu) |
| POST | `/auth/login` | Login, returns user object |
| GET | `/auth/user/{user_id}` | Get user info |
| PUT | `/auth/user/{user_id}/name` | Update display name — co / edu only (`_norm_name`, ≤ 100, `validate_professional_text`); emp → 422 `emp_name_mutation_forbidden` (PR 2A) |

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

### Jobs
| Method | Path | Description |
|--------|------|-------------|
| GET | `/jobs` | List all jobs |
| GET | `/stats` | Platform-wide statistics |

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

> **DS-COLOR:** النظام الرسمي لكل color tokens موثَّق في `docs/design-system/COLOR-SYSTEM.md`.
> قبل تعريف لون جديد أو ترحيل hex value → اقرأ CLR-00 أولاً. لا تعدّل `--ac / --bg / --t1` إلخ بدون PR DS-COLOR معلن.

### Patterns
- All pages are **RTL** (`dir="rtl"`, `font-family: 'Cairo'`)
- Sessions read/written via `localStorage` as JSON
- API calls use native `fetch()` — no axios or jQuery
- No bundler or build step — edit HTML files directly
- Glassmorphism cards: `backdrop-filter: blur(...)` + semi-transparent backgrounds
- Bottom navigation bar for mobile; sidebar for desktop

### Auth Guard Pattern
Session state comes from `TwAuthSync.getSessionSnapshot()` (`static/shared/auth-sync.js`, loaded after `tw_shared.js`). `localStorage` keys are `tw_user` / `tw_jwt` — a cache only, never the authority (see Auth Gateway Rules §6).
```js
var snap = (window.TwAuthSync && TwAuthSync.getSessionSnapshot) ? TwAuthSync.getSessionSnapshot() : null;
if (!snap || !snap.isAuthenticated) { location.replace('/login'); return; }
var jwt = localStorage.getItem('tw_jwt');   // snapshot has no jwt field — never snap.jwt
```

---

## Key Workflows

### 1. Registration Flow
1. `POST /auth/register` with `{ full_name, email, password, user_type, country_code }`
2. Server hashes password, generates `tw_id`, inserts into `users` + creates empty `profiles` row
3. Returns user object — client stores in localStorage

### 2. Credential Verification Flow
1. Employee submits `POST /verify-request` with document URL
2. Admin reviews at `/tw-ctrl-{ADMIN_URL_TOKEN}`
3. Admin calls `PUT /admin/verify/{req_id}` with `{ status: "approved" | "rejected" }`
4. Approved credentials show a verified badge on the employee's public profile

---

## Testing

Focused tests live at the repo root (`test_*.py`, `test_*_runtime.js`) and in `tests/`. Run only the one relevant to your change, e.g.:

```bash
python -m pytest test_post_comments.py -q
node test_stale_session_entry_runtime.js
```

---

## Deployment

```bash
# Railway — deploys from GitHub main (Procfile)
# Set env vars in Railway → Variables (see Environment Variables table)
```

The `Procfile` binds to `$PORT` automatically:
```
web: uvicorn server:app --host 0.0.0.0 --port $PORT
```
