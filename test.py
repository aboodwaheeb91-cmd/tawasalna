"""
اختبار الـ Matching Engine
شغّل السيرفر أولاً: uvicorn server:app --reload
"""

import requests
import json

BASE = "http://localhost:8000"

def test_match(cv_text, label=""):
    print(f"\n{'─'*50}")
    print(f"🧪 {label}")
    print(f"CV: {cv_text}")
    
    res = requests.post(f"{BASE}/match", json={
        "cv_text": cv_text,
        "top_k": 3
    })
    
    data = res.json()
    print("\n📊 أفضل وظائف:")
    for m in data["matches"]:
        bar = "█" * int(m["match_percent"] / 10)
        print(f"  {m['match_percent']:5.1f}% {bar:<10} {m['title']} - {m['company']}")

def test_feedback():
    print(f"\n{'─'*50}")
    print("📝 اختبار تسجيل الـ Feedback")
    
    res = requests.post(f"{BASE}/feedback", json={
        "cv_text": "اشتغلت فني تكييف 3 سنوات",
        "job_id": 3,
        "score": 0.87,
        "action": "applied"
    })
    print(f"✅ {res.json()}")

def test_stats():
    print(f"\n{'─'*50}")
    res = requests.get(f"{BASE}/stats")
    print(f"📈 Stats: {json.dumps(res.json(), ensure_ascii=False, indent=2)}")

if __name__ == "__main__":
    # اختبار حالات مختلفة
    test_match("اشتغلت فني تكييف 3 سنوات وبعرف صيانة أجهزة التبريد", "فني تكييف")
    test_match("عندي خبرة بالمحاسبة والـ Excel وإعداد التقارير المالية", "محاسب")
    test_match("مطور React و Python خبرة 4 سنوات", "مطور")
    test_match("ممرضة شهادة تمريض 5 سنوات خبرة بالمستشفيات", "ممرضة")
    
    test_feedback()
    test_stats()
    
    print(f"\n{'═'*50}")
    print("✅ كل الاختبارات اشتغلت!")
