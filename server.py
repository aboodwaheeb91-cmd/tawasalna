"""
تواصلنا - Arabic Employment Platform
"""

# ── Imports ──
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import secrets
import json
import os

from auth import (
    init_db, get_conn,
    create_user, authenticate_user, get_user_by_id,
    get_public_profile, get_full_profile, update_profile,
    add_experience, add_education, add_course, create_verify_request
)

# ── App ──
app = FastAPI(title="تواصلنا API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ── Admin Session ──
admin_sessions: set = set()
ADMIN_PASSWORD = "tw@admin2025"
ADMIN_URL_TOKEN = "kPuOWhpIYjdLQXmh"

# ── Startup ──
@app.on_event("startup")
def on_startup():
    try:
        init_db()
        print("✅ DB initialized")
    except Exception as e:
        print(f"⚠️ DB init failed: {e}")

# ── HTML Helper ──
def read_html(name: str) -> str:
    try:
        with open(name, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"<h1>الصفحة غير موجودة: {name}</h1>"

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

@app.get("/job-detail", response_class=HTMLResponse)
def job_detail(): return read_html("job-detail.html")

@app.get("/job-detail.html", response_class=HTMLResponse)
def job_detail_html(): return read_html("job-detail.html")

@app.get("/settings", response_class=HTMLResponse)
def settings(): return read_html("settings.html")

@app.get("/settings.html", response_class=HTMLResponse)
def settings_html(): return read_html("settings.html")

# ── Admin Pages ──
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

class CourseInput(BaseModel):
    title: str
    provider: Optional[str] = None
    completion_date: Optional[str] = None
    certificate_url: Optional[str] = None
    description: Optional[str] = None

class VerifyRequestInput(BaseModel):
    user_id: int
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
def register(data: RegisterInput):
    if not data.full_name.strip():
        raise HTTPException(400, detail="الاسم الكامل مطلوب")
    if not data.email.strip():
        raise HTTPException(400, detail="البريد الإلكتروني مطلوب")
    if len(data.password) < 6:
        raise HTTPException(400, detail="كلمة المرور يجب أن تكون 6 أحرف على الأقل")
    if data.user_type not in ("emp", "co", "edu"):
        raise HTTPException(400, detail="نوع الحساب غير صحيح")
    try:
        user = create_user(data.full_name, data.email, data.password, data.user_type)
        return {"status": "success", "message": "تم إنشاء الحساب بنجاح", "user": user}
    except ValueError as e:
        raise HTTPException(409, detail=str(e))
    except Exception as e:
        print(f"Register error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم، حاول لاحقاً")

@app.post("/auth/login")
def login(data: LoginInput):
    if not data.email.strip() or not data.password:
        raise HTTPException(400, detail="البريد وكلمة المرور مطلوبان")
    user = authenticate_user(data.email, data.password)
    if not user:
        raise HTTPException(401, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة")
    return {"status": "success", "message": "تم تسجيل الدخول بنجاح", "user": user}

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
def public_profile(user_id: int):
    profile = get_public_profile(user_id)
    if not profile:
        raise HTTPException(404, detail="الملف الشخصي غير موجود")
    return {"status": "success", "profile": profile}

@app.get("/profile/{user_id}/full")
def full_profile(user_id: int):
    profile = get_full_profile(user_id)
    if not profile:
        raise HTTPException(404, detail="الملف الشخصي غير موجود")
    return {"status": "success", "profile": profile}

@app.put("/profile/{user_id}")
def update_user_profile(user_id: int, data: ProfileUpdateInput):
    try:
        profile = update_profile(user_id, data.dict())
        return {"status": "success", "message": "تم تحديث الملف الشخصي", "profile": profile}
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
JOBS = [
    {"id":1,"title":"محاسب","company":"شركة المال والأعمال","location":"عمان","text":"نبحث عن محاسب لديه خبرة في Excel والمالية والضرائب"},
    {"id":2,"title":"مطور ويب","company":"تك ستارت","location":"الرياض","text":"مطلوب مطور React و FastAPI خبرة 3 سنوات على الأقل"},
    {"id":3,"title":"فني تكييف","company":"برودة للتكييف","location":"دبي","text":"خبرة في صيانة أجهزة التكييف والتبريد وإصلاح الأعطال"},
    {"id":4,"title":"مدير مبيعات","company":"نجوم التجارة","location":"القاهرة","text":"خبرة في المبيعات وإدارة فريق العمل وتحقيق الأهداف"},
    {"id":5,"title":"مصمم جرافيك","company":"إبداع ستوديو","location":"بيروت","text":"إتقان Photoshop وIllustrator وخبرة في الهوية البصرية"},
    {"id":6,"title":"ممرض/ة","company":"مستشفى الشفاء","location":"عمان","text":"شهادة تمريض خبرة في الرعاية الصحية والتعامل مع المرضى"},
    {"id":7,"title":"معلم رياضيات","company":"مدارس المستقبل","location":"دبي","text":"شهادة تعليم خبرة في تدريس الرياضيات للمرحلة الثانوية"},
]

@app.get("/jobs")
def list_jobs():
    return {"jobs": JOBS, "count": len(JOBS)}

@app.post("/match")
def match_cv(cv: CVInput):
    if not cv.cv_text.strip():
        raise HTTPException(400, detail="cv_text لا يمكن أن يكون فارغاً")
    query = cv.cv_text.lower()
    results = []
    for job in JOBS:
        score = sum(1 for word in query.split() if word in job["text"].lower())
        results.append({
            "job_id": job["id"], "title": job["title"],
            "company": job["company"], "location": job["location"],
            "score": score, "match_percent": min(score * 10, 100)
        })
    results = sorted(results, key=lambda x: x["score"], reverse=True)[:cv.top_k or 5]
    return {"status": "success", "matches": results}

@app.post("/feedback")
def log_feedback(data: FeedbackInput):
    return {"status": "logged"}

@app.get("/stats")
def stats():
    return {"jobs_count": len(JOBS)}

# ══════════════════════════════════════════
# Admin Auth
# ══════════════════════════════════════════
def check_admin(request: Request):
    token = request.cookies.get("tw_adm")
    if not token or token not in admin_sessions:
        raise HTTPException(status_code=403, detail="Forbidden")

@app.post("/tw-ctrl-login")
def admin_login(data: AdminLoginInput, response: Response):
    if data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = secrets.token_urlsafe(32)
    admin_sessions.add(token)
    response.set_cookie(
        key="tw_adm",
        value=token,
        httponly=True,
        max_age=86400,
        samesite="lax"
    )
    return {"success": True}

@app.post("/tw-ctrl-logout")
def admin_logout(request: Request, response: Response):
    token = request.cookies.get("tw_adm")
    admin_sessions.discard(token)
    response.delete_cookie("tw_adm")
    return {"success": True}

# ══════════════════════════════════════════
# Admin API
# ══════════════════════════════════════════
@app.get("/auth/users")
def get_all_users(request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, full_name, email, user_type, created_at FROM users ORDER BY created_at DESC"
        )
        cols = [d[0] for d in conn.columns]
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
                   vr.notes, vr.status, vr.created_at
            FROM verify_requests vr
            JOIN users u ON u.id = vr.user_id
            ORDER BY vr.created_at DESC
        """)
        cols = [d[0] for d in conn.columns]
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
        return profile or {"error": "لا يوجد ملف"}
    except Exception as e:
        print(f"admin_get_profile error: {e}")
        raise HTTPException(500, detail=str(e))

@app.post("/admin/message")
def admin_send_message(data: AdminMessageInput, request: Request):
    check_admin(request)
    print(f"[ADMIN MSG] To:{data.user_id} | {data.subject}: {data.message}")
    return {"success": True}
