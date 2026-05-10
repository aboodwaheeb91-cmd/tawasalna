"""
تواصلنا - Arabic Job Matching Engine
MVP Backend - FastAPI + Multilingual E5 Embeddings
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import json
import os
from datetime import datetime
from typing import List, Optional

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
# Model (أقوى embedding للعربي عملياً)
# ─────────────────────────────────────────
model = None

def get_model():
    global model
    if model is None:
        print("⏳ Loading embedding model...")
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        print("✅ Model loaded.")
    return model
# ─────────────────────────────────────────
# Jobs Database (استبدلها بـ PostgreSQL لاحقاً)
# ─────────────────────────────────────────
JOBS_FILE = "jobs.json"

def load_jobs():
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Default jobs إذا ما في ملف
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
# Precompute Job Embeddings (مرة واحدة بس)
# ─────────────────────────────────────────
EMBEDDINGS_FILE = "job_embeddings.npy"

def get_job_embeddings():
    job_texts = [f"passage: {j['title']} {j['text']}" for j in jobs]
    
    if os.path.exists(EMBEDDINGS_FILE):
        print("✅ Loading cached embeddings...")
        return np.load(EMBEDDINGS_FILE)
    
    print("⏳ Computing job embeddings...")
    embeddings = model.encode(job_texts, normalize_embeddings=True)
    np.save(EMBEDDINGS_FILE, embeddings)
    print("✅ Embeddings saved.")
    return embeddings

job_embeddings = get_job_embeddings()

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
    action: str  # "clicked" | "applied" | "rejected" | "hired"
    user_id: Optional[str] = None

# ─────────────────────────────────────────
# Logging (Data Flywheel 🔥)
# ─────────────────────────────────────────
def log_event(filename: str, data: dict):
    os.makedirs("logs", exist_ok=True)
    with open(f"logs/{filename}", "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

# ─────────────────────────────────────────
# Routes
# ─────────────────────────────────────────

from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
@app.get("/", response_class=HTMLResponse)
def root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()
@app.get("/health")
def health():
    return {"status": "ok", "jobs_count": len(jobs), "model": "multilingual-e5-base"}


@app.post("/match")
def match_cv(cv: CVInput):
    """
    المطابقة الرئيسية: CV → أفضل وظائف
    """
    if not cv.cv_text.strip():
        raise HTTPException(status_code=400, detail="cv_text لا يمكن أن يكون فارغاً")

    # E5 format: query prefix
    query = f"query: {cv.cv_text}"
    cv_embedding = model.encode([query], normalize_embeddings=True)

    scores = cosine_similarity(cv_embedding, job_embeddings)[0]

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

    # 🔥 Log كل request = داتا مجانية
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
    """
    تسجيل تفاعل المستخدم - هاد هو الذهب الحقيقي
    applied / hired = positive signal قوي
    rejected = negative signal
    """
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
    """
    إضافة وظيفة جديدة وتحديث الـ embeddings
    """
    global jobs, job_embeddings

    new_id = max(j["id"] for j in jobs) + 1
    new_job = {"id": new_id, **job.dict()}
    jobs.append(new_job)

    # حفظ الوظائف
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    # تحديث الـ embeddings
    job_texts = [f"passage: {j['title']} {j['text']}" for j in jobs]
    job_embeddings = model.encode(job_texts, normalize_embeddings=True)
    np.save(EMBEDDINGS_FILE, job_embeddings)

    return {"status": "added", "job_id": new_id}


@app.get("/jobs")
def list_jobs():
    return {"jobs": jobs, "count": len(jobs)}


@app.get("/stats")
def stats():
    """
    إحصائيات الـ logs (مفيدة لمتابعة الـ data flywheel)
    """
    def count_lines(filename):
        path = f"logs/{filename}"
        if not os.path.exists(path):
            return 0
        with open(path, encoding="utf-8") as f:
            return sum(1 for _ in f)

    matches = count_lines("matches.jsonl")
    signals = count_lines("training_signals.jsonl")

    return {
        "total_matches": matches,
        "total_feedback_signals": signals,
        "jobs_count": len(jobs)
    }
