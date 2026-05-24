# 🏗️ تواصلنا - Master Architecture Document
> **ملف مرجعي أساسي** - آخر تحديث: مايو 2026
> Architecture: Hybrid (تدريجي - لا يعيد بناء المشروع)

---

## 📋 قواعد التطوير (يُقرأ أولاً)

```
قبل أي تعديل:
1. افحص هذا الملف
2. عدّل فقط القسم المطلوب - لا الصفحة كاملة
3. افحص تأثير التعديل على الأقسام الأخرى
4. حافظ على نفس الستايل والألوان
5. لا تعدّل DB بدون migration plan
6. وثّق التغيير هنا
```

---

## 1. هيكلة المشروع (Project Structure)

```
tawasalna/
├── 📄 server.py          # FastAPI backend (114 endpoints)
├── 📄 auth.py            # DB functions + connection pool (16 tables)
├── 📄 tw_shared.js       # Shared JS (toast, logo, auth headers, error tracking)
├── 📄 requirements.txt   # Python dependencies
├── 📄 sw.js              # Service Worker (PWA)
├── 📄 manifest.json      # PWA manifest
├── 📄 ARCHITECTURE.md    # هذا الملف
│
├── 🌐 Pages/
│   ├── landing.html      # صفحة الهبوط (public) [31KB]
│   ├── index.html        # تسجيل الدخول/التسجيل (public) [23KB]
│   ├── home.html         # الرئيسية (protected) [37KB]
│   ├── profile.html      # البروفايل (protected+public) [181KB]
│   ├── settings.html     # الإعدادات + KYC (protected) [42KB]
│   ├── jobs.html         # قائمة الوظائف (public) [20KB]
│   ├── job-detail.html   # تفاصيل وظيفة (public) [29KB]
│   ├── company.html      # لوحة الشركة (co only) [37KB]
│   ├── company-profile.html # بروفايل شركة (public) [50KB]
│   ├── edu.html          # لوحة تعليمية (edu only) [44KB]
│   ├── edu-profile.html  # بروفايل مؤسسة (public) [37KB]
│   ├── messages.html     # الرسائل (protected) [31KB]
│   ├── notifications.html # الإشعارات (protected) [24KB]
│   ├── admin.html        # لوحة الإدارة (admin only) [38KB]
│   └── admin-view.html   # تفاصيل مستخدم (admin only) [41KB]
│
└── ☁️ Storage (Supabase)/
    ├── avatars/          # صور المستخدمين (public)
    ├── kyc-docs/         # وثائق التوثيق (private)
    └── site/             # ملفات الموقع - شعار (public)
```

---

## 2. الملفات المشتركة (Shared Files)

| الملف | الوظيفة | تُستخدم في |
|-------|---------|-----------|
| `tw_shared.js` | Toast, Logo, getAuthHeaders(), Error Tracking | كل الصفحات |
| `server.py` | كل الـ API endpoints | Backend |
| `auth.py` | DB queries + connection pool | server.py فقط |
| `sw.js` | PWA Service Worker | كل الصفحات |
| `manifest.json` | PWA config | كل الصفحات |

---

## 3. توثيق Routes (Endpoints)

### 🔐 Auth (10)
```
POST  /auth/register
POST  /auth/login
GET   /auth/user/{id}
PUT   /auth/user/{id}/name
DELETE /auth/user/{id}/delete
GET   /auth/users (admin)
POST  /tw-ctrl-login (admin)
```

### 👤 Profile (7)
```
GET   /profile/{id}
GET   /profile/{id}/full
PUT   /profile/{id}
GET   /profile/{id}/score
POST  /profile/experience
POST  /profile/education
POST  /profile/course
```

### 💼 Jobs (15)
```
GET   /jobs
GET   /jobs/{id}
POST  /company/jobs
PUT   /company/jobs/{id}
DELETE /company/jobs/{id}
POST  /jobs/{id}/apply
GET   /jobs/{id}/applicants
GET   /my/applications
```

### 💬 Messages & Notifications
```
POST  /messages/send
GET   /messages/conversations/{id}
GET   /messages/{uid}/{oid}
GET   /notifications/{id}
PUT   /notifications/{id}/read
WS    /ws/{user_id}
```

### 🪪 KYC
```
POST  /kyc/start
GET   /kyc/status/{id}
POST  /kyc/email/send
POST  /kyc/email/verify
POST  /kyc/phone/send
POST  /kyc/phone/verify
POST  /kyc/docs
```

### 🚨 Reports
```
POST  /reports/submit
GET   /admin/reports
PUT   /admin/reports/{id}/resolve
```

### ⚙️ Admin (26)
```
GET   /admin/jobs
DELETE /admin/jobs/{id}
GET   /admin/verify-requests
PUT   /admin/verify/{id}
GET   /admin/user/{id}
DELETE /admin/user/{id}
GET   /admin/kyc
PUT   /admin/kyc/{id}/approve
PUT   /admin/kyc/{id}/reject
POST  /admin/message
POST  /admin/logo
GET   /admin/logo
```

### 🔧 System
```
GET,HEAD /health
GET,HEAD /ping
GET   /static/{filename}  (المرحلة 3)
POST  /log/error
POST  /upload/image
GET   /sitemap.xml
GET   /robots.txt
```

---

## 4. قاعدة البيانات (16 جداول)

```sql
users, profiles, experience, education,
user_skills, user_langs, user_links,
courses, jobs, job_applications,
kyc_submissions, messages, notifications,
verify_requests, site_settings, reports
```

---

## 5. نظام الصلاحيات

| النوع | user_type | الصلاحيات |
|-------|-----------|-----------|
| موظف | `emp` | بروفايل، وظائف، رسائل، KYC |
| شركة | `co` | + نشر وظائف، مراجعة طلبات |
| تعليمية | `edu` | + دورات، توثيق شهادات |
| أدمن | token | كل شيء |

---

## 6. قواعد التصميم

```css
/* الألوان الأساسية */
--ac:  #00c896   /* أخضر رئيسي */
--ac2: #2563ff   /* أزرق */
--bg:  #070b18   /* خلفية داكنة */
--bdr: rgba(255,255,255,.08)  /* حدود */
--t2:  rgba(255,255,255,.7)   /* نص ثانوي */
--t3:  rgba(255,255,255,.4)   /* نص خافت */

/* الخط */
font-family: Cairo, sans-serif;

/* البطاقات */
border-radius: 12px - 16px;
background: rgba(255,255,255,.04);
border: 1px solid rgba(255,255,255,.08);
```

---

## 7. نظام التسمية (Naming Convention)

```
✅ صحيح:
USR_000001_PROFILE.jpg
CMP_000045_LOGO.png
logo_wide.svg

❌ ممنوع:
image1.png / final.jpg / new2.png
```

---

## 8. Dependencies مهمة

```python
# server.py
fastapi, uvicorn, pg8000, httpx, bcrypt

# Frontend
qrcode.js    → QR generation (profile.html)
Cairo font   → Google Fonts
tw_shared.js → Shared utilities
```

---

## 9. النشر (Deployment)

```
Backend:   Railway (Hobby $5/شهر)
DB:        Supabase PostgreSQL
Storage:   Supabase Storage
Domain:    tawasolna.com

Railway Variables:
- SUPABASE_DB_URL
- SUPABASE_URL
- SUPABASE_SERVICE_KEY
- ADMIN_PASSWORD
```

---

## 10. سجل التغييرات (Change Log)

| التاريخ | الملف | التغيير |
|---------|-------|---------|
| 2026-05 | كل الصفحات | إضافة تعليقات Sections (المرحلة 1) |
| 2026-05 | ARCHITECTURE.md | توثيق شامل (المرحلة 2) |
| 2026-05 | server.py | إضافة /static/ route (المرحلة 3) |
| 2026-05 | tw_shared.css | فصل CSS المشترك (المرحلة 4) |

---

*Hybrid Architecture - تنظيم تدريجي آمن*
