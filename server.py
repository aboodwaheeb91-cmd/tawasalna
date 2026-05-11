"""
تواصلنا - Arabic Job Matching Engine
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import json
import os
from datetime import datetime
from typing import List, Optional
from auth import (
    init_db, create_user, authenticate_user, get_user_by_id,
    get_public_profile, get_full_profile, update_profile,
    add_experience, add_education, add_course, create_verify_request
)

# ─────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────
app = FastAPI(title="تواصلنا API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    try:
        init_db()
    except Exception as e:
        print(f"⚠️ DB init failed: {e}")

# ─────────────────────────────────────────
# Jobs Database
# ─────────────────────────────────────────
JOBS_FILE = "jobs.json"

def load_jobs():
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return [
        {"id": 1, "title": "محاسب", "company": "شركة المال والأعمال", "location": "عمان", "text": "نبحث عن محاسب لديه خبرة في Excel والمالية والضرائب"},
        {"id": 2, "title": "مطور ويب", "company": "تك ستارت", "location": "الرياض", "text": "مطلوب مطور React و FastAPI خبرة 3 سنوات على الأقل"},
        {"id": 3, "title": "فني تكييف", "company": "برودة للتكييف", "location": "دبي", "text": "خبرة في صيانة أجهزة التكييف والتبريد وإصلاح الأعطال"},
        {"id": 4, "title": "مدير مبيعات", "company": "نجوم التجارة", "location": "القاهرة", "text": "خبرة في المبيعات وإدارة فريق العمل وتحقيق الأهداف"},
        {"id": 5, "title": "مصمم جرافيك", "company": "إبداع ستوديو", "location": "بيروت", "text": "إتقان Photoshop وIllustrator وخبرة في الهوية البصرية"},
        {"id": 6, "title": "ممرض/ة", "company": "مستشفى الشفاء", "location": "عمان", "text": "شهادة تمريض خبرة في الرعاية الصحية والتعامل مع المرضى"},
        {"id": 7, "title": "سائق توصيل", "company": "سريع للتوصيل", "location": "الرياض", "text": "رخصة قيادة سارية خبرة في التوصيل ومعرفة بشوارع المدينة"},
        {"id": 8, "title": "معلم رياضيات", "company": "مدارس المستقبل", "location": "دبي", "text": "شهادة تعليم خبرة في تدريس الرياضيات للمرحلة الثانوية"},
    ]

jobs = load_jobs()

# ─────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────
class CVInput(BaseModel):
    cv_text: str
    user_id: Optional[str] = None
    top_k: Optional[int] = 5

class JobInput(BaseModel):
    title: str
    company: str
    location: str
    text: str

class FeedbackInput(BaseModel):
    cv_text: str
    job_id: int
    score: float
    action: str
    user_id: Optional[str] = None

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

# ─────────────────────────────────────────
# Logging
# ─────────────────────────────────────────
def log_event(filename: str, data: dict):
    os.makedirs("logs", exist_ok=True)
    with open(f"logs/{filename}", "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

# ─────────────────────────────────────────
# Routes
# ─────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/health")
def health():
    return {"status": "ok", "jobs_count": len(jobs)}

# ─────────────────────────────────────────
# Auth Routes
# ─────────────────────────────────────────

@app.post("/auth/register")
def register(data: RegisterInput):
    if not data.full_name.strip():
        raise HTTPException(status_code=400, detail="الاسم الكامل مطلوب")
    if not data.email.strip():
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مطلوب")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تكون 6 أحرف على الأقل")
    if data.user_type not in ("emp", "co", "edu"):
        raise HTTPException(status_code=400, detail="نوع الحساب غير صحيح")
    try:
        user = create_user(data.full_name, data.email, data.password, data.user_type)
        return {"status": "success", "message": "تم إنشاء الحساب بنجاح", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="خطأ في الخادم، حاول لاحقاً")

@app.post("/auth/login")
def login(data: LoginInput):
    if not data.email.strip() or not data.password:
        raise HTTPException(status_code=400, detail="البريد وكلمة المرور مطلوبان")
    user = authenticate_user(data.email, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة")
    return {"status": "success", "message": "تم تسجيل الدخول بنجاح", "user": user}

@app.get("/auth/user/{user_id}")
def get_user(user_id: int):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    return {"user": user}

# ─────────────────────────────────────────
# Profile Routes
# ─────────────────────────────────────────

@app.get("/profile/{user_id}")
def public_profile(user_id: int):
    profile = get_public_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="الملف الشخصي غير موجود")
    return {"status": "success", "profile": profile}

@app.get("/profile/{user_id}/full")
def full_profile(user_id: int):
    profile = get_full_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="الملف الشخصي غير موجود")
    return {"status": "success", "profile": profile}

@app.put("/profile/{user_id}")
def update_user_profile(user_id: int, data: ProfileUpdateInput):
    try:
        profile = update_profile(user_id, data.dict())
        return {"status": "success", "message": "تم تحديث الملف الشخصي", "profile": profile}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="خطأ في الخادم، حاول لاحقاً")

# ─────────────────────────────────────────
# Experience / Education / Course Routes
# ─────────────────────────────────────────

@app.post("/experience/{user_id}")
def add_user_experience(user_id: int, data: ExperienceInput):
    if not data.title.strip() or not data.company.strip():
        raise HTTPException(status_code=400, detail="المسمى الوظيفي وجهة العمل مطلوبان")
    try:
        entry = add_experience(user_id, data.dict())
        return {"status": "success", "message": "تمت إضافة الخبرة", "experience": entry}
    except Exception as e:
        raise HTTPException(status_code=500, detail="خطأ في الخادم، حاول لاحقاً")

@app.post("/education/{user_id}")
def add_user_education(user_id: int, data: EducationInput):
    if not data.institution.strip():
        raise HTTPException(status_code=400, detail="اسم المؤسسة التعليمية مطلوب")
    try:
        entry = add_education(user_id, data.dict())
        return {"status": "success", "message": "تمت إضافة التعليم", "education": entry}
    except Exception as e:
        raise HTTPException(status_code=500, detail="خطأ في الخادم، حاول لاحقاً")

@app.post("/course/{user_id}")
def add_user_course(user_id: int, data: CourseInput):
    if not data.title.strip():
        raise HTTPException(status_code=400, detail="اسم الدورة مطلوب")
    try:
        entry = add_course(user_id, data.dict())
        return {"status": "success", "message": "تمت إضافة الدورة", "course": entry}
    except Exception as e:
        raise HTTPException(status_code=500, detail="خطأ في الخادم، حاول لاحقاً")

# ─────────────────────────────────────────
# Verification Route
# ─────────────────────────────────────────

@app.post("/verify-request")
def request_verification(data: VerifyRequestInput):
    try:
        req = create_verify_request(data.user_id, data.dict())
        return {"status": "success", "message": "تم إرسال طلب التحقق بنجاح", "request": req}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="خطأ في الخادم، حاول لاحقاً")

# ─────────────────────────────────────────
# Match Route
# ─────────────────────────────────────────

@app.post("/match")
def match_cv(cv: CVInput):
    if not cv.cv_text.strip():
        raise HTTPException(status_code=400, detail="cv_text لا يمكن أن يكون فارغاً")
    query = cv.cv_text.lower()
    results = []
    for job in jobs:
        score = sum(1 for word in query.split() if word in job["text"].lower())
        results.append({
            "job_id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "score": score,
            "match_percent": min(score * 10, 100)
        })
    results = sorted(results, key=lambda x: x["score"], reverse=True)[:cv.top_k or 5]
    log_event("matches.jsonl", {
        "timestamp": datetime.now().isoformat(),
        "user_id": cv.user_id,
        "cv_text": cv.cv_text,
        "results": results
    })
    return {"status": "success", "matches": results}

@app.post("/feedback")
def log_feedback(data: FeedbackInput):
    signal = {
        "timestamp": datetime.now().isoformat(),
        "user_id": data.user_id,
        "cv_text": data.cv_text,
        "job_id": data.job_id,
        "score": data.score,
        "action": data.action,
        "label": 1 if data.action in ["applied", "hired"] else 0
    }
    log_event("training_signals.jsonl", signal)
    return {"status": "logged", "signal_type": "positive" if signal["label"] == 1 else "negative"}

@app.get("/jobs")
def list_jobs():
    return {"jobs": jobs, "count": len(jobs)}

@app.get("/stats")
def stats():
    def count_lines(filename):
        path = f"logs/{filename}"
        if not os.path.exists(path):
            return 0
        with open(path, encoding="utf-8") as f:
            return sum(1 for _ in f)
    return {
        "total_matches": count_lines("matches.jsonl"),
        "total_feedback_signals": count_lines("training_signals.jsonl"),
        "jobs_count": len(jobs)
    }
