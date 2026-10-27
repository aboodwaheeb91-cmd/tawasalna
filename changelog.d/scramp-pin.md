## PR scramp-pin — تثبيت scramp==1.4.18 — 2026-10-27

- `requirements.txt`: `scramp==1.4.18` تحت `pg8000`. scramp كان بينزل مع pg8000 بدون تثبيت، وإصدار 1.5.0 شال `make_channel_binding` اللي pg8000 1.31.5 بيناديها بكل اتصال SSL → كل اتصال بالقاعدة كان بيفشل (CI: «PostgreSQL not reachable») وأي build جديد على Railway.
