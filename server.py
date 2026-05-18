"""
تواصلنا - Arabic Employment Platform
"""

import os
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import base64, mimetypes
from typing import List, Optional
from datetime import datetime
import hashlib, secrets, json, os

import urllib.request

# ── IP to country code ──
IP_TO_COUNTRY_CACHE = {}

def get_country_from_ip(ip: str) -> str:
    if not ip or ip in ('127.0.0.1', '::1', 'localhost'):
        return 'DEFAULT'
    if ip in IP_TO_COUNTRY_CACHE:
        return IP_TO_COUNTRY_CACHE[ip]
    COUNTRY_MAP = {
        'JO':'JO','SA':'SA','AE':'AE','KW':'KW','QA':'QA',
        'BH':'BH','OM':'OM','EG':'EG','IQ':'IQ','SY':'SY',
        'LB':'LB','PS':'PS','YE':'YE','MA':'MA','DZ':'DZ',
        'TN':'TN','LY':'LY','SD':'SD',
    }
    try:
        url = f'http://ip-api.com/json/{ip}?fields=countryCode'
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read())
        code = data.get('countryCode','DEFAULT')
        result = COUNTRY_MAP.get(code,'DEFAULT')
        IP_TO_COUNTRY_CACHE[ip] = result
        return result
    except Exception:
        return 'DEFAULT'

def get_client_ip(request) -> str:
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else '127.0.0.1'


from auth import (
    init_db, get_conn,
    create_user, authenticate_user, get_user_by_id,
    get_public_profile, get_full_profile, update_profile,
    get_profile_by_tw_id, get_full_profile_by_tw_id, get_user_id_by_tw_id,
    add_experience, add_education, add_course, create_verify_request,
    add_job, get_jobs, get_job, apply_job,
    start_kyc, send_email_code, verify_email_code,
    send_phone_code, verify_phone_code, upload_kyc_docs,
    get_kyc_status, admin_approve_kyc, admin_reject_kyc, get_all_kyc_submissions,
    get_job_applicants, get_user_applications,
    update_application_status, delete_job
)

# ── Config ──
ADMIN_PASSWORD = "tw@admin2025"
ADMIN_URL_TOKEN = "kPuOWhpIYjdLQXmh"
# Stable token derived from password - no server storage needed
ADMIN_TOKEN = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()

# ── App ──
app = FastAPI(title="تواصلنا API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,  # Must be False with allow_origins=["*"]
)

# ── Startup ──
@app.on_event("startup")
def on_startup():
    try:
        init_db()
        print("✅ DB initialized")
    except Exception as e:
        print(f"⚠️ DB init failed: {e}")

# ── Helpers ──
def read_html(name: str) -> str:
    try:
        with open(name, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"<h1>الصفحة غير موجودة: {name}</h1>"

def check_admin(request: Request):
    """Check admin token from header X-Admin-Token"""
    token = request.headers.get("X-Admin-Token", "")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

# ══════════════════════════════════════════
# HTML Pages
# ══════════════════════════════════════════
@app.get("/", response_class=HTMLResponse)
def root(): return read_html("landing.html")

@app.get("/login", response_class=HTMLResponse)
def login_page(): return read_html("index.html")

@app.get("/login.html", response_class=HTMLResponse)
def login_html(): return read_html("index.html")

@app.get("/home", response_class=HTMLResponse)
def home(): return read_html("home.html")

@app.get("/home.html", response_class=HTMLResponse)
def home_html(): return read_html("home.html")

@app.get("/profile", response_class=HTMLResponse)
def profile(): return read_html("profile.html")

@app.get("/profile.html", response_class=HTMLResponse)
def profile_html(): return read_html("profile.html")

@app.get("/company", response_class=HTMLResponse)
def company(): return read_html("company.html")

@app.get("/company.html", response_class=HTMLResponse)
def company_html(): return read_html("company.html")

@app.get("/company-profile", response_class=HTMLResponse)
def company_profile(): return read_html("company-profile.html")

@app.get("/company-profile.html", response_class=HTMLResponse)
def company_profile_html(): return read_html("company-profile.html")

@app.get("/edu", response_class=HTMLResponse)
def edu(): return read_html("edu.html")

@app.get("/edu.html", response_class=HTMLResponse)
def edu_html(): return read_html("edu.html")

@app.get("/edu-profile", response_class=HTMLResponse)
def edu_profile(): return read_html("edu-profile.html")

@app.get("/edu-profile.html", response_class=HTMLResponse)
def edu_profile_html(): return read_html("edu-profile.html")

@app.get("/notifications", response_class=HTMLResponse)
def notifications(): return read_html("notifications.html")

@app.get("/notifications.html", response_class=HTMLResponse)
def notifications_html(): return read_html("notifications.html")

@app.get("/messages", response_class=HTMLResponse)
def messages(): return read_html("messages.html")

@app.get("/messages.html", response_class=HTMLResponse)
def messages_html(): return read_html("messages.html")

@app.get("/employees-group", response_class=HTMLResponse)
def employees_group(): return read_html("employees-group.html")

@app.get("/employees-group.html", response_class=HTMLResponse)
def employees_group_html(): return read_html("employees-group.html")

@app.get("/jobs.html", response_class=HTMLResponse)
def jobs_page(): return read_html("jobs.html")

@app.get("/job-detail", response_class=HTMLResponse)
def job_detail(): return read_html("job-detail.html")

@app.get("/job-detail.html", response_class=HTMLResponse)
def job_detail_html(): return read_html("job-detail.html")

@app.get("/admin-view", response_class=HTMLResponse)
@app.get("/admin-view.html", response_class=HTMLResponse)
def admin_view(): return read_html("admin-view.html")

@app.get("/settings", response_class=HTMLResponse)
def settings(): return read_html("settings.html")

@app.get("/settings.html", response_class=HTMLResponse)
def settings_html(): return read_html("settings.html")

@app.get("/admin.html", response_class=HTMLResponse)
def admin_html(): return read_html("admin.html")

@app.get("/tw-ctrl-" + ADMIN_URL_TOKEN, response_class=HTMLResponse)
def admin_page(): return read_html("admin.html")

# ══════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════
class RegisterInput(BaseModel):
    full_name: str
    email: str
    password: str
    user_type: Optional[str] = "emp"

class LoginInput(BaseModel):
    email: str
    password: str

class ProfileUpdateInput(BaseModel):
    headline: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    skills: Optional[List[str]] = None
    avatar_url: Optional[str] = None
    website: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    sections_order: Optional[str] = None
    custom_sections: Optional[str] = None
    dob: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    avail: Optional[str] = None

class ExperienceInput(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: Optional[bool] = False
    description: Optional[str] = None

class EducationInput(BaseModel):
    institution: str
    degree: Optional[str] = None
    field: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    description: Optional[str] = None

class ImageUploadInput(BaseModel):
    user_id: int
    bucket: str
    filename: str
    data_url: str

class KYCEmailInput(BaseModel):
    user_id: int
    email: str

class KYCCodeInput(BaseModel):
    user_id: int
    code: str

class KYCPhoneInput(BaseModel):
    user_id: int
    phone: str

class KYCDocsInput(BaseModel):
    user_id: int
    id_front_url: str
    selfie_url: Optional[str] = None

class KYCAdminInput(BaseModel):
    note: Optional[str] = ""

class JobInput(BaseModel):
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = "full_time"
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: Optional[str] = "USD"
    experience_years: Optional[int] = 0
    skills: Optional[List[str]] = None

class JobApplyInput(BaseModel):
    user_id: int
    cover_letter: Optional[str] = ""

class AppStatusInput(BaseModel):
    status: str  # pending, viewed, accepted, rejected

class SkillInput(BaseModel):
    skill: str
    level: Optional[str] = None

class LangInput(BaseModel):
    language: str
    level: Optional[str] = None

class LinkInput(BaseModel):
    link_type: Optional[str] = None
    url: str

class CourseInput(BaseModel):
    title: str
    provider: Optional[str] = None
    completion_date: Optional[str] = None
    certificate_url: Optional[str] = None
    description: Optional[str] = None

class VerifyRequestInput(BaseModel):
    user_id: int
    item_type: Optional[str] = None   # exp / edu / course
    item_id: Optional[int] = None
    item_title: Optional[str] = None
    item_company: Optional[str] = None
    document_url: Optional[str] = None
    notes: Optional[str] = None

class CVInput(BaseModel):
    cv_text: str
    user_id: Optional[str] = None
    top_k: Optional[int] = 5

class FeedbackInput(BaseModel):
    cv_text: str
    job_id: int
    score: float
    action: str
    user_id: Optional[str] = None

class AdminLoginInput(BaseModel):
    password: str

class VerifyUpdateInput(BaseModel):
    status: str

class AdminMessageInput(BaseModel):
    user_id: int
    subject: str
    message: str

# ══════════════════════════════════════════
# Health
# ══════════════════════════════════════════
@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# ══════════════════════════════════════════
# Auth
# ══════════════════════════════════════════
@app.post("/auth/register")
def register(data: RegisterInput, request: Request):
    if not data.full_name.strip():
        raise HTTPException(400, detail="الاسم الكامل مطلوب")
    if not data.email.strip():
        raise HTTPException(400, detail="البريد الإلكتروني مطلوب")
    if len(data.password) < 6:
        raise HTTPException(400, detail="كلمة المرور يجب أن تكون 6 أحرف على الأقل")
    if data.user_type not in ("emp", "co", "edu"):
        raise HTTPException(400, detail="نوع الحساب غير صحيح")
    try:
        client_ip = get_client_ip(request)
        country_code = get_country_from_ip(client_ip)
        user = create_user(data.full_name, data.email, data.password, data.user_type, country_code)
        return {"status": "success", "user": user}
    except ValueError as e:
        raise HTTPException(409, detail=str(e))
    except Exception as e:
        print(f"Register error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

@app.post("/auth/login")
def login(data: LoginInput):
    if not data.email.strip() or not data.password:
        raise HTTPException(400, detail="البريد وكلمة المرور مطلوبان")
    user = authenticate_user(data.email, data.password)
    if not user:
        raise HTTPException(401, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة")
    return {"status": "success", "user": user}

@app.put("/auth/user/{user_id}/name")
async def update_user_name(user_id: int, request: Request):
    try:
        data = await request.json()
        full_name = data.get("full_name","").strip()
        if not full_name:
            raise HTTPException(400, "الاسم مطلوب")
        conn = auth.get_conn()
        try:
            conn.run("UPDATE users SET full_name=:name WHERE id=:uid",
                     name=full_name, uid=user_id)
        finally:
            conn.close()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/auth/user/{user_id}")
def get_user(user_id: int):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, detail="المستخدم غير موجود")
    return {"user": user}

# ══════════════════════════════════════════
# Profile
# ══════════════════════════════════════════
@app.get("/profile/{user_id}")
def public_profile(user_id: str):
    try:
        uid = int(user_id)
        profile = get_public_profile(uid)
    except ValueError:
        profile = get_profile_by_tw_id(user_id)
    if not profile:
        raise HTTPException(404, detail="الملف الشخصي غير موجود")
    return {"status": "success", "profile": profile}

@app.get("/profile/{user_id}/full")
def full_profile(user_id: str):
    try:
        uid = int(user_id)
        profile = get_full_profile(uid)
    except ValueError:
        profile = get_full_profile_by_tw_id(user_id)
    if not profile:
        raise HTTPException(404, detail="الملف الشخصي غير موجود")
    return {"status": "success", "profile": profile}

@app.put("/profile/{user_id}")
def update_user_profile(user_id: int, data: ProfileUpdateInput):
    try:
        profile = update_profile(user_id, data.dict())
        return {"status": "success", "profile": profile}
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except Exception as e:
        print(f"Profile update error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

@app.post("/experience/{user_id}")
def add_user_experience(user_id: int, data: ExperienceInput):
    if not data.title.strip() or not data.company.strip():
        raise HTTPException(400, detail="المسمى الوظيفي وجهة العمل مطلوبان")
    try:
        return {"status": "success", "experience": add_experience(user_id, data.dict())}
    except Exception as e:
        print(f"Experience error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

@app.post("/education/{user_id}")
def add_user_education(user_id: int, data: EducationInput):
    if not data.institution.strip():
        raise HTTPException(400, detail="اسم المؤسسة التعليمية مطلوب")
    try:
        return {"status": "success", "education": add_education(user_id, data.dict())}
    except Exception as e:
        print(f"Education error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

@app.post("/course/{user_id}")
def add_user_course(user_id: int, data: CourseInput):
    if not data.title.strip():
        raise HTTPException(400, detail="اسم الدورة مطلوب")
    try:
        return {"status": "success", "course": add_course(user_id, data.dict())}
    except Exception as e:
        print(f"Course error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

@app.post("/skills/{user_id}")
def add_user_skill(user_id: int, data: SkillInput):
    try:
        conn = get_conn()
        try:
            rows = conn.run(
                "INSERT INTO user_skills (user_id, skill, level) VALUES (:uid, :skill, :level) RETURNING id, user_id, skill, level",
                uid=user_id, skill=data.skill, level=data.level
            )
            cols = [d["name"] if isinstance(d, dict) else d[0] for d in conn.columns]
            return {"status": "success", "skill": dict(zip(cols, rows[0]))}
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(500, str(e))

@app.delete("/skills/{skill_id}")
def delete_user_skill(skill_id: int):
    try:
        conn = get_conn()
        try:
            conn.run("DELETE FROM user_skills WHERE id = :id", id=skill_id)
            return {"success": True}
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/langs/{user_id}")
def add_user_lang(user_id: int, data: LangInput):
    try:
        conn = get_conn()
        try:
            rows = conn.run(
                "INSERT INTO user_langs (user_id, language, level) VALUES (:uid, :lang, :level) RETURNING id, user_id, language, level",
                uid=user_id, lang=data.language, level=data.level
            )
            cols = [d["name"] if isinstance(d, dict) else d[0] for d in conn.columns]
            return {"status": "success", "lang": dict(zip(cols, rows[0]))}
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(500, str(e))

@app.delete("/langs/{lang_id}")
def delete_user_lang(lang_id: int):
    try:
        conn = get_conn()
        try:
            conn.run("DELETE FROM user_langs WHERE id = :id", id=lang_id)
            return {"success": True}
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/links/{user_id}")
def add_user_link(user_id: int, data: LinkInput):
    try:
        conn = get_conn()
        try:
            rows = conn.run(
                "INSERT INTO user_links (user_id, link_type, url) VALUES (:uid, :ltype, :url) RETURNING id, user_id, link_type, url",
                uid=user_id, ltype=data.link_type, url=data.url
            )
            cols = [d["name"] if isinstance(d, dict) else d[0] for d in conn.columns]
            return {"status": "success", "link": dict(zip(cols, rows[0]))}
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(500, str(e))

@app.delete("/links/{link_id}")
def delete_user_link(link_id: int):
    try:
        conn = get_conn()
        try:
            conn.run("DELETE FROM user_links WHERE id = :id", id=link_id)
            return {"success": True}
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(500, str(e))

# ══ Storage Upload ══

@app.post("/upload/image")
async def upload_image(data: ImageUploadInput):
    """Upload image to Supabase Storage and return public URL"""
    import httpx
    try:
        # Parse data URL: "data:image/jpeg;base64,/9j/4AAQ..."
        if ',' not in data.data_url:
            raise HTTPException(400, "Invalid data URL")

        header, b64data = data.data_url.split(',', 1)
        # Get mime type: "data:image/jpeg;base64"
        mime = header.split(':')[1].split(';')[0]
        ext = mimetypes.guess_extension(mime) or '.jpg'
        if ext == '.jpe': ext = '.jpg'

        file_bytes = base64.b64decode(b64data)

        # Check size - max 5MB
        if len(file_bytes) > 5 * 1024 * 1024:
            raise HTTPException(400, "الصورة كبيرة جداً - الحد الأقصى 5MB")

        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            # Fallback: return data URL as-is (dev mode)
            return {"status": "success", "url": data.data_url, "dev_mode": True}

        bucket = data.bucket
        filename = f"{data.user_id}_{data.filename}{ext}"
        storage_url = f"{supabase_url}/storage/v1/object/{bucket}/{filename}"

        async with httpx.AsyncClient() as client:
            r = await client.post(
                storage_url,
                content=file_bytes,
                headers={
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": mime,
                    "x-upsert": "true"
                }
            )
            if r.status_code not in (200, 201):
                # Fallback to data URL
                return {"status": "success", "url": data.data_url, "dev_mode": True}

        public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{filename}"
        return {"status": "success", "url": public_url}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload error: {e}")
        # Fallback: return data URL
        return {"status": "success", "url": data.data_url, "dev_mode": True}

# ══ KYC Endpoints ══

@app.post("/kyc/start")
def kyc_start(user_id: int):
    try:
        result = start_kyc(user_id)
        return {"status": "success", "kyc": result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/kyc/status/{user_id}")
def kyc_status(user_id: int):
    try:
        result = get_kyc_status(user_id)
        return {"status": "success", "kyc": result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/kyc/email/send")
def kyc_send_email(data: KYCEmailInput):
    try:
        start_kyc(data.user_id)
        code = send_email_code(data.user_id, data.email)
        print(f"[KYC] Email code for user {data.user_id}: {code}")  # In prod: send via email
        return {"status": "success", "message": "تم إرسال الرمز على بريدك الإلكتروني", "dev_code": code}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/kyc/email/verify")
def kyc_verify_email(data: KYCCodeInput):
    try:
        ok = verify_email_code(data.user_id, data.code)
        if not ok:
            raise HTTPException(400, "الرمز غير صحيح أو منتهي الصلاحية")
        return {"status": "success", "message": "تم تأكيد البريد الإلكتروني ✅"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/kyc/phone/send")
def kyc_send_phone(data: KYCPhoneInput):
    try:
        code = send_phone_code(data.user_id, data.phone)
        print(f"[KYC] Phone code for user {data.user_id}: {code}")  # In prod: send via SMS
        return {"status": "success", "message": "تم إرسال الرمز على هاتفك", "dev_code": code}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/kyc/phone/verify")
def kyc_verify_phone(data: KYCCodeInput):
    try:
        ok = verify_phone_code(data.user_id, data.code)
        if not ok:
            raise HTTPException(400, "الرمز غير صحيح")
        return {"status": "success", "message": "تم تأكيد رقم الهاتف ✅"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/kyc/docs")
def kyc_upload_docs(data: KYCDocsInput):
    try:
        result = upload_kyc_docs(data.user_id, data.id_front_url, data.selfie_url)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/admin/kyc")
def admin_get_kyc(request: Request):
    check_admin(request)
    try:
        submissions = get_all_kyc_submissions()
        return {"status": "success", "submissions": submissions, "count": len(submissions)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.put("/admin/kyc/{user_id}/approve")
def admin_kyc_approve(user_id: int, data: KYCAdminInput, request: Request):
    check_admin(request)
    try:
        result = admin_approve_kyc(user_id, data.note)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.put("/admin/kyc/{user_id}/reject")
def admin_kyc_reject(user_id: int, data: KYCAdminInput, request: Request):
    check_admin(request)
    try:
        result = admin_reject_kyc(user_id, data.note)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/verify-request")
def request_verification(data: VerifyRequestInput):
    try:
        req = create_verify_request(data.user_id, data.dict())
        return {"status": "success", "request": req}
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except Exception as e:
        print(f"Verify request error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

# ══════════════════════════════════════════
# Jobs & Match
# ══════════════════════════════════════════

@app.get("/jobs")
def list_jobs(search: str = None, location: str = None,
               job_type: str = None, company_id: int = None):
    filters = {"search":search,"location":location,"job_type":job_type,"company_id":company_id}
    jobs = get_jobs({k:v for k,v in filters.items() if v})
    return {"jobs": jobs, "count": len(jobs)}

@app.get("/jobs/{job_id}")
def get_job_detail(job_id: int):
    job = get_job(job_id)
    if not job: raise HTTPException(404, "الوظيفة غير موجودة")
    return {"status": "success", "job": job}

@app.post("/company/jobs")
def post_job(data: JobInput, request: Request):
    user_id = int(request.headers.get("X-User-Id", 0))
    if not user_id: raise HTTPException(401, "غير مصرح")
    job = add_job(user_id, data.dict())
    return {"status": "success", "job": job}

@app.put("/company/jobs/{job_id}")
def update_job_endpoint(job_id: int, data: JobInput, request: Request):
    user_id = int(request.headers.get("X-User-Id", 0))
    if not user_id: raise HTTPException(401, "غير مصرح")
    conn = get_conn()
    try:
        fields = {k:v for k,v in data.dict().items() if v is not None}
        if fields:
            set_clause = ", ".join(f"{k}=:{k}" for k in fields)
            conn.run(f"UPDATE jobs SET {set_clause} WHERE id=:id AND company_id=:cid",
                     id=job_id, cid=user_id, **fields)
        return {"status": "success"}
    finally:
        conn.close()

@app.delete("/company/jobs/{job_id}")
def remove_job(job_id: int, request: Request):
    user_id = int(request.headers.get("X-User-Id", 0))
    if not user_id: raise HTTPException(401, "غير مصرح")
    delete_job(job_id, user_id)
    return {"success": True}

@app.get("/company/jobs")
def get_company_jobs(request: Request):
    user_id = int(request.headers.get("X-User-Id", 0))
    if not user_id: raise HTTPException(401, "غير مصرح")
    jobs = get_jobs({"company_id": user_id})
    return {"jobs": jobs, "count": len(jobs)}

@app.post("/jobs/{job_id}/apply")
def apply_to_job(job_id: int, data: JobApplyInput):
    result = apply_job(job_id, data.user_id, data.cover_letter or "")
    return {"status": "success", **result}

@app.get("/jobs/{job_id}/applicants")
def job_applicants(job_id: int, request: Request):
    user_id = int(request.headers.get("X-User-Id", 0))
    if not user_id: raise HTTPException(401, "غير مصرح")
    applicants = get_job_applicants(job_id)
    return {"applicants": applicants, "count": len(applicants)}

@app.get("/my/applications")
def my_applications(request: Request):
    user_id = int(request.headers.get("X-User-Id", 0))
    if not user_id: raise HTTPException(401, "غير مصرح")
    apps = get_user_applications(user_id)
    return {"applications": apps, "count": len(apps)}

@app.put("/jobs/applications/{app_id}/status")
def update_app_status(app_id: int, data: AppStatusInput, request: Request):
    user_id = int(request.headers.get("X-User-Id", 0))
    if not user_id: raise HTTPException(401, "غير مصرح")
    result = update_application_status(app_id, data.status)
    return result

@app.get("/admin/jobs")
def admin_list_jobs(request: Request):
    check_admin(request)
    jobs = get_jobs({})
    return {"jobs": jobs, "count": len(jobs)}

@app.delete("/admin/jobs/{job_id}")
def admin_delete_job(job_id: int, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        conn.run("DELETE FROM jobs WHERE id=:id", id=job_id)
        return {"success": True}
    finally:
        conn.close()

@app.post("/match")
def match_cv(cv: CVInput):
    if not cv.cv_text.strip():
        raise HTTPException(400, detail="cv_text لا يمكن أن يكون فارغاً")
    query = cv.cv_text.lower()
    results = sorted([
        {"job_id": j["id"], "title": j["title"], "company": j["company"],
         "location": j["location"],
         "score": sum(1 for w in query.split() if w in j["text"].lower()),
         "match_percent": min(sum(1 for w in query.split() if w in j["text"].lower()) * 10, 100)}
        for j in JOBS
    ], key=lambda x: x["score"], reverse=True)[:cv.top_k or 5]
    return {"status": "success", "matches": results}

@app.post("/feedback")
def log_feedback(data: FeedbackInput):
    return {"status": "logged"}

@app.get("/stats")
def stats():
    conn = get_conn()
    try:
        users_count = conn.run("SELECT COUNT(*) FROM users")[0][0]
        emp_count = conn.run("SELECT COUNT(*) FROM users WHERE user_type='emp'")[0][0]
        co_count = conn.run("SELECT COUNT(*) FROM users WHERE user_type='co'")[0][0]
        edu_count = conn.run("SELECT COUNT(*) FROM users WHERE user_type='edu'")[0][0]
        return {
            "users_count": users_count,
            "emp_count": emp_count,
            "co_count": co_count,
            "edu_count": edu_count,
            "jobs_count": len(JOBS)
        }
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()

# ══════════════════════════════════════════
# Admin Login - returns token
# ══════════════════════════════════════════
@app.post("/tw-ctrl-login")
def admin_login(data: AdminLoginInput):
    if data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # Return stable token (derived from password - no server storage)
    return {"success": True, "token": ADMIN_TOKEN}

# ══════════════════════════════════════════
# Admin API - all require X-Admin-Token header
# ══════════════════════════════════════════
@app.get("/auth/users")
def get_all_users(request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, full_name, email, user_type, created_at FROM users ORDER BY created_at DESC"
        )
        cols = [d["name"] if isinstance(d, dict) else d[0] for d in conn.columns]
        users = [dict(zip(cols, r)) for r in rows]
        for u in users:
            if u.get("created_at"):
                u["created_at"] = str(u["created_at"])[:10]
        return {"users": users, "total": len(users)}
    except Exception as e:
        print(f"get_all_users error: {e}")
        raise HTTPException(500, detail=str(e))
    finally:
        conn.close()

@app.get("/admin/verify-requests")
def admin_verify_requests(request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        rows = conn.run("""
            SELECT vr.id, vr.user_id, u.full_name AS user_name,
                   vr.item_type, vr.item_id, vr.item_title, vr.item_company,
                   vr.notes, vr.status, vr.created_at
            FROM verify_requests vr
            JOIN users u ON u.id = vr.user_id
            ORDER BY vr.created_at DESC
        """)
        cols = [d["name"] if isinstance(d, dict) else d[0] for d in conn.columns]
        reqs = [dict(zip(cols, r)) for r in rows]
        for r in reqs:
            if r.get("created_at"):
                r["created_at"] = str(r["created_at"])[:10]
        return {"requests": reqs, "total": len(reqs)}
    except Exception as e:
        print(f"verify_requests error: {e}")
        raise HTTPException(500, detail=str(e))
    finally:
        conn.close()

@app.put("/admin/verify/{req_id}")
def admin_update_verify(req_id: int, data: VerifyUpdateInput, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        conn.run(
            "UPDATE verify_requests SET status = :s WHERE id = :id",
            s=data.status, id=req_id
        )
        return {"success": True}
    except Exception as e:
        print(f"update_verify error: {e}")
        raise HTTPException(500, detail=str(e))
    finally:
        conn.close()

@app.get("/admin/profile/{user_id}")
def admin_get_profile(user_id: int, request: Request):
    check_admin(request)
    try:
        profile = get_full_profile(user_id)
        if not profile:
            raise HTTPException(404, "المستخدم غير موجود")
        return {"status": "success", "profile": profile}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f"admin_get_profile error: {err}")
        raise HTTPException(500, detail=f"خطأ: {str(e)}")

@app.delete("/auth/user/{user_id}/delete")
def delete_own_account(user_id: int, request: Request):
    """User deletes their own account"""
    conn = get_conn()
    try:
        conn.run("DELETE FROM users WHERE id = :uid", uid=user_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.delete("/admin/user/{user_id}")
def delete_user(user_id: int, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        rows = conn.run("SELECT id FROM users WHERE id = :uid", uid=user_id)
        if not rows:
            raise HTTPException(404, "المستخدم غير موجود")
        conn.run("DELETE FROM users WHERE id = :uid", uid=user_id)
        return {"success": True, "message": "تم حذف الحساب"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.put("/admin/user/{user_id}/type")
async def change_user_type(user_id: int, request: Request):
    check_admin(request)
    data = await request.json()
    new_type = data.get("user_type","emp")
    if new_type not in ("emp","co","edu"):
        raise HTTPException(400, "نوع حساب غير صحيح")
    conn = get_conn()
    try:
        conn.run("UPDATE users SET user_type = :utype WHERE id = :uid", utype=new_type, uid=user_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.put("/admin/user/{user_id}/verify")
async def verify_user(user_id: int, request: Request):
    check_admin(request)
    data = await request.json()
    is_v = data.get("is_verified", True)
    conn = get_conn()
    try:
        rows = conn.run("SELECT id FROM profiles WHERE user_id = :uid", uid=user_id)
        if rows:
            conn.run("UPDATE profiles SET is_verified = :v WHERE user_id = :uid", v=is_v, uid=user_id)
        else:
            conn.run("INSERT INTO profiles (user_id, is_verified) VALUES (:uid, :v)", uid=user_id, v=is_v)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.put("/admin/user/{user_id}/password")
async def admin_reset_password(user_id: int, request: Request):
    check_admin(request)
    data = await request.json()
    pw = data.get("password","").strip()
    if not pw or len(pw) < 6:
        raise HTTPException(400, "كلمة المرور قصيرة جداً")
    from auth import hash_password
    conn = get_conn()
    try:
        conn.run("UPDATE users SET password_hash = :pw WHERE id = :uid",
                 pw=hash_password(pw), uid=user_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.delete("/admin/experience/{exp_id}")
def admin_delete_exp(exp_id: int, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        conn.run("DELETE FROM experience WHERE id = :id", id=exp_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.delete("/admin/education/{edu_id}")
def admin_delete_edu(edu_id: int, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        conn.run("DELETE FROM education WHERE id = :id", id=edu_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.delete("/admin/course/{course_id}")
def admin_delete_course(course_id: int, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        conn.run("DELETE FROM courses WHERE id = :id", id=course_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.post("/admin/message")
def admin_send_message(data: AdminMessageInput, request: Request):
    check_admin(request)
    print(f"[ADMIN MSG] To:{data.user_id} | {data.subject}: {data.message}")
    return {"success": True}
