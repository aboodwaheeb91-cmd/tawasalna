"""
تواصلنا - Arabic Job Matching Engine
MVP Backend - FastAPI + Multilingual E5 Embeddings + Auth
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import json
import os
from datetime import datetime
from typing import List, Optional
from auth import init_db, create_user, authenticate_user, get_user_by_id

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

# ─────────────────────────────────────────
# DB Init on startup
# ─────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    try:
        init_db()
    except Exception as e:
        print(f"⚠️ DB init failed: {e}")

# ─────────────────────────────────────────
# Lazy Model Loading
# ─────────────────────────────────────────
_model = None
_job_embeddings = None

def get_model():
    global _model
    if _model is None:
        print("⏳ Loading embedding model...")
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        print("✅ Model loaded.")
    return _model

def get_job_embeddings():
    global _job_embeddings
    if _job_embeddings is not None:
        return _job_embeddings

    EMBEDDINGS_FILE = "job_embeddings.npy"
    job_texts = [f"passage: {j['title']} {j['text']}" for j in jobs]

    if os.path.exists(EMBEDDINGS_FILE):
        print("✅ Loading cached embeddings...")
        _job_embeddings = np.load(EMBEDDINGS_FILE)
        return _job_embeddings

    print("⏳ Computing job embeddings...")
    _job_embeddings = get_model().encode(job_texts, normalize_embeddings=True)
    np.save(EMBEDDINGS_FILE, _job_embeddings)
    print("✅ Embeddings saved.")
    return _job_embeddings

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
    return {"status": "ok", "jobs_count": len(jobs), "model": "MiniLM-L12-v2"}

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

@app.post("/match")
def match_cv(cv: CVInput):
    if not cv.cv_text.strip():
        raise HTTPException(status_code=400, detail="cv_text لا يمكن أن يكون فارغاً")

    query = f"query: {cv.cv_text}"
    cv_embedding = get_model().encode([query], normalize_embeddings=True)
    scores = cosine_similarity(cv_embedding, get_job_embeddings())[0]

    top_k = min(cv.top_k or 5, len(jobs))
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = [
        {
            "job_id": jobs[i]["id"],
            "title": jobs[i]["title"],
            "company": jobs[i]["company"],
            "location": jobs[i]["location"],
            "score": round(float(scores[i]), 4),
            "match_percent": round(float(scores[i]) * 100, 1)
        }
        for i in top_indices
    ]

    log_event("matches.jsonl", {
        "timestamp": datetime.now().isoformat(),
        "user_id": cv.user_id,
        "cv_text": cv.cv_text,
        "results": results
    })

    return {
        "status": "success",
        "cv_preview": cv.cv_text[:100] + "..." if len(cv.cv_text) > 100 else cv.cv_text,
        "matches": results
    }

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

@app.post("/jobs/add")
def add_job(job: JobInput):
    global jobs, _job_embeddings

    new_id = max(j["id"] for j in jobs) + 1
    new_job = {"id": new_id, **job.dict()}
    jobs.append(new_job)

    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    job_texts = [f"passage: {j['title']} {j['text']}" for j in jobs]
    _job_embeddings = get_model().encode(job_texts, normalize_embeddings=True)
    np.save("job_embeddings.npy", _job_embeddings)

    return {"status": "added", "job_id": new_id}

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
