# تواصلنا - Arabic Job Matching Engine 🚀

## تشغيل سريع

```bash
# 1. تثبيت
pip install -r requirements.txt

# 2. تشغيل السيرفر
uvicorn server:app --reload

# 3. اختبار
python test.py
```

## API Endpoints

| Method | Endpoint | الوظيفة |
|--------|----------|---------|
| POST | `/match` | مطابقة CV مع وظائف |
| POST | `/feedback` | تسجيل تفاعل المستخدم |
| POST | `/jobs/add` | إضافة وظيفة جديدة |
| GET | `/jobs` | عرض كل الوظائف |
| GET | `/stats` | إحصائيات الـ logs |

## مثال

```bash
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{"cv_text": "اشتغلت فني تكييف 3 سنوات", "top_k": 5}'
```

## البنية

```
server.py          # الـ API الرئيسي
requirements.txt   # المكتبات
test.py            # اختبارات
jobs.json          # يتولد تلقائياً
job_embeddings.npy # يتولد تلقائياً (cache)
logs/
  matches.jsonl          # كل request
  training_signals.jsonl # feedback من المستخدمين
```

## الخطوة التالية

بعد ما تجمع 500+ signal من `training_signals.jsonl`:
- تدرّب Ranking Layer فوق الـ embeddings
- Logistic Regression بسيطة تبدأ فيها
- بعدها RLHF حقيقي
