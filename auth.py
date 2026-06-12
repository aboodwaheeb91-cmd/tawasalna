"""
Authentication module - Supabase PostgreSQL
تواصلنا - نظام المصادقة وقاعدة البيانات
"""

import os
import re
import uuid
import bcrypt
import pg8000.native
from datetime import datetime
from typing import Optional

# ══ Emoji / symbol prevention ══
_EMOJI_RE = re.compile(
    "[\U0001F600-\U0001F64F"   # emoticons
    "\U0001F300-\U0001F5FF"    # misc symbols & pictographs
    "\U0001F680-\U0001F6FF"    # transport & map
    "\U0001F900-\U0001F9FF"    # supplemental symbols
    "\U0001FA00-\U0001FAFF"    # extended-A
    "\U00002702-\U000027B0"    # dingbats
    "\U00002600-\U000026FF"    # misc symbols
    "\U0001F1E0-\U0001F1FF"    # flags
    "\U0000FE0F"               # variation selector-16
    "\U0000200D"               # zero-width joiner
    "]+",
    re.UNICODE
)


class ContentValidationError(ValueError):
    """Base class for professional content validation errors."""
    def __init__(self, field: str, message: str):
        super().__init__(field)
        self.field = field
        self.message = message


class EmojiError(ContentValidationError):
    """Raised when a text field contains emoji / pictographic symbols."""
    def __init__(self, field: str):
        super().__init__(field, "لا يسمح باستخدام الرموز التعبيرية داخل هذا الحقل")


class ProfanityError(ContentValidationError):
    """Raised when a text field contains prohibited / unprofessional language."""
    def __init__(self, field: str):
        super().__init__(field, "لا يسمح باستخدام كلمات غير لائقة أو غير مهنية داخل هذا الحقل")


def validate_no_emoji(value, field: str = "هذا الحقل") -> None:
    """Raise EmojiError if value contains emoji. Reusable across all text fields."""
    if value and _EMOJI_RE.search(str(value)):
        raise EmojiError(field)


# ══ Profanity / Professional Content Filter ══
_PROFANITY = frozenset([
    # ─── English: short — word-level only (len < 5) ──────────────────────────
    'ass', 'anus', 'anal', 'cock', 'cum', 'dick', 'rape', 'sex', 'tit', 'tits',
    'nude', 'pimp', 'smut', 'perv', 'wank', 'twat', 'pedo',
    # ─── English: medium/long — also substring match (len >= 5) ─────────────
    'pussy', 'penis', 'boobs', 'naked', 'horny', 'boner', 'nudes', 'vulva',
    'rapist', 'orgasm', 'vagina', 'erotic', 'incest', 'sexting', 'camgirl', 'wanker',
    'creampie', 'gangbang', 'onlyfans', 'ejaculat', 'pedophil', 'necrophil', 'bestiality',
    # ─── English: original list ──────────────────────────────────────────────
    'fuck', 'fucking', 'fucked', 'fucker', 'fucks', 'motherfucker', 'motherfucking',
    'shit', 'bullshit', 'shitting',
    'cunt', 'cunts', 'bitch', 'bitches',
    'asshole', 'assholes', 'whore', 'whores', 'slut', 'sluts', 'bastard',
    'porn', 'porno', 'pornography', 'pornographic',
    'blowjob', 'handjob', 'rimjob', 'cumshot', 'dildo', 'masturbate', 'masturbation',
    # ─── Arabic: short — word-level only ─────────────────────────────────────
    'زب', 'طيز', 'كس', 'ير', 'خول', 'زناء', 'لواط',
    'زنا', 'زنى', 'عاهر', 'مومس', 'بزاز', 'نهود', 'فحش', 'جماع', 'عرص', 'عري', 'تعري',
    # ─── Arabic: medium/long — also substring match ───────────────────────────
    'إباحي', 'إباحية', 'زانية', 'عاهرة', 'دعارة', 'ماخور', 'استمناء', 'فاحشة',
    # ─── Arabic: original list ───────────────────────────────────────────────
    'نيك', 'ينيك', 'ينكح', 'بنيك',
    'شرموطة', 'شراميط', 'قحبة', 'قحاب',
    'خرا', 'خرة', 'منيوك', 'منيوكة',
    'كسمك', 'كسمه', 'كسها', 'كسك', 'كسمها', 'كسمهم',
    'متناك', 'متناكة', 'سكس', 'سيكس', 'بورن', 'بورنو',
])


def _normalize_for_profanity(text: str) -> str:
    """Normalize text before profanity matching.

    Handles: Arabic tashkeel/tatweel, hamza variants, alef maqsura,
    teh marbuta, leet-speak substitutions, invisible chars, repeat collapse.
    """
    t = text.lower()
    # Arabic: strip diacritics (tashkeel U+064B–U+065F, superscript alef U+0670) and tatweel U+0640
    t = re.sub(r'[ً-ٰٟـ]', '', t)
    # Arabic: normalize all hamza forms → plain alef (U+0627)
    t = re.sub(r'[آأإٱ]', 'ا', t)
    # Arabic: alef maqsura → ya; teh marbuta → ha
    t = t.replace('ى', 'ي').replace('ة', 'ه')
    # Leet-speak digit/symbol substitutions
    t = (t.replace('@', 'a').replace('0', 'o').replace('1', 'i')
          .replace('3', 'e').replace('$', 's').replace('5', 's'))
    # Remove invisible / zero-width Unicode
    t = re.sub(r'[​-‏‪-‮﻿͏­]', '', t)
    # Collapse excessive repeated chars ("fuuuck" → "fuuck")
    t = re.sub(r'(.)\1{2,}', r'\1\1', t)
    return t


# Pre-normalize the bad word list so every comparison is apples-to-apples.
# This means Arabic words with ة/أ/إ in the list are stored normalized,
# and input is normalized identically before checking.
_PROFANITY_NORMALIZED = frozenset(_normalize_for_profanity(w) for w in _PROFANITY)


def validate_professional_text(value, field: str = "هذا الحقل") -> None:
    """Raise ContentValidationError if value contains emoji or prohibited language."""
    if not value:
        return
    s = str(value)
    validate_no_emoji(s, field)
    normalized = _normalize_for_profanity(s)
    # Split on whitespace and structural separators only (NOT on . ! - * etc.).
    # Then strip remaining non-alphanumeric from each token — this defeats
    # obfuscation like f.u.c.k, sh!t, f*ck written as f-c-k, etc.
    word_set: set = set()
    for tok in re.split(r'[\s,،;:\'"()\[\]{}]+', normalized):
        clean = re.sub(r'[^a-z0-9؀-ۿ]', '', tok)
        if clean:
            word_set.add(clean)
    for bad in _PROFANITY_NORMALIZED:
        if bad in word_set:
            raise ProfanityError(field)
        if len(bad) >= 5 and bad in normalized:
            raise ProfanityError(field)


# ══ نظام الـ IDs ══
# الشكل: {PREFIX}{COUNTRY_CODE}{UUID_10_CHARS}
# مثال: U96204a8f3c9b2e (موظف أردني)

TYPE_PREFIX = {
    'emp': 'U',   # User (موظف)
    'co':  'C',   # Company (شركة)
    'edu': 'T',   # Training/Education (مؤسسة تعليمية)
}

COUNTRY_CODES = {
    'JO': '9620', 'SA': '9660', 'AE': '9710', 'KW': '9650',
    'QA': '9740', 'BH': '9730', 'OM': '9680', 'EG': '2000',
    'IQ': '9640', 'SY': '9630', 'LB': '9610', 'PS': '9720',
    'YE': '9670', 'MA': '2120', 'DZ': '2130', 'TN': '2160',
    'LY': '2180', 'SD': '2490', 'DEFAULT': '0000',
}


def generate_tw_id(user_type: str, country_code: str = 'DEFAULT') -> str:
    """
    يولّد معرف احترافي فريد للحساب.
    الشكل: {U/C/T}{كود_الدولة}{10_أحرف_عشوائية}
    مثال: U9620ec95e9c5ca
    """
    prefix = TYPE_PREFIX.get(user_type, 'U')
    cc = COUNTRY_CODES.get(country_code, COUNTRY_CODES['DEFAULT'])
    rand = uuid.uuid4().hex[:10]
    return f"{prefix}{cc}{rand}"


# ══ الاتصال بقاعدة البيانات ══
# ── Connection Pool ──
_pool = []
import threading as _threading
_pool_lock = _threading.Lock()
_MAX_POOL = 5
_db_params = {}

def _parse_db_url():
    global _db_params
    if _db_params: return
    url = os.environ.get("SUPABASE_DB_URL","").strip().replace(" ","")
    if not url: raise RuntimeError("SUPABASE_DB_URL is not set")
    without_scheme = url.split("://",1)[1]
    userinfo, hostinfo = without_scheme.split("@",1)
    username, password = userinfo.split(":",1)
    host_port, dbname = hostinfo.split("/",1)
    dbname = dbname.split("?")[0]
    host, port = (host_port.rsplit(":",1) if ":" in host_port else (host_port, "5432"))
    _db_params = dict(host=host, port=int(port), user=username, password=password, database=dbname, ssl_context=True)


# ── Query Cache (Redis-ready) ──
import time as _time_mod, json as _json_mod
_query_cache = {}
_CACHE_TTL = 60  # Reduced from 300s for cross-device consistency  # seconds (5 min)

def _cache_get(key):
    # Try Redis first
    try:
        from server import _redis_client
        if _redis_client:
            val = _redis_client.get(key)
            return _json_mod.loads(val) if val else None
    except: pass
    # Fallback: in-memory
    if key in _query_cache:
        val, ts = _query_cache[key]
        if _time_mod.time() - ts < _CACHE_TTL:
            return val
        del _query_cache[key]
    return None

def _cache_set(key, val):
    # Try Redis first
    try:
        from server import _redis_client
        if _redis_client:
            _redis_client.setex(key, _CACHE_TTL, _json_mod.dumps(val, default=str))
            return
    except: pass
    # Fallback: in-memory
    _query_cache[key] = (val, _time_mod.time())

def _cache_del(prefix):
    # Try Redis first
    try:
        from server import _redis_client
        if _redis_client:
            keys = _redis_client.keys(prefix + '*')
            if keys: _redis_client.delete(*keys)
            return
    except: pass
    # Fallback: in-memory
    for k in list(_query_cache.keys()):
        if k.startswith(prefix):
            del _query_cache[k]

def get_conn():
    _parse_db_url()
    global _pool
    with _pool_lock:
        if _pool:
            try:
                conn = _pool.pop()
                conn.run("SELECT 1")
                return conn
            except Exception:
                pass
    return pg8000.native.Connection(**_db_params)

def release_conn(conn):
    global _pool
    with _pool_lock:
        if len(_pool) < _MAX_POOL:
            try:
                _pool.append(conn)
                return
            except Exception:
                pass
    try: conn.close()
    except: pass


# ══ مساعدات ══
def _row_to_dict(columns, row):
    return dict(zip(columns, row))


def _serialize(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ══ تهيئة قاعدة البيانات ══
def init_db():
    conn = get_conn()
    try:
        conn.run("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                tw_id TEXT UNIQUE,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                user_type TEXT NOT NULL DEFAULT 'emp',
                country_code TEXT DEFAULT 'DEFAULT',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Migration: أضف الأعمدة الجديدة لو ما موجودة
        for col_sql in [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS tw_id TEXT UNIQUE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS country_code TEXT DEFAULT 'DEFAULT'",
        ]:
            try:
                conn.run(col_sql)
            except Exception:
                pass

        # Migration: ولّد tw_id للحسابات القديمة
        try:
            old_users = conn.run(
                "SELECT id, user_type, country_code FROM users WHERE tw_id IS NULL"
            )
            for row in (old_users or []):
                uid, utype, cc = row[0], row[1] or 'emp', row[2] or 'DEFAULT'
                tw_id = _unique_tw_id(conn, utype, cc)
                conn.run(
                    "UPDATE users SET tw_id = :tw_id WHERE id = :uid",
                    tw_id=tw_id, uid=uid
                )
        except Exception as e:
            print(f"Migration note: {e}")

        conn.run("""
            CREATE TABLE IF NOT EXISTS profiles (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                headline TEXT, bio TEXT, location TEXT,
                skills TEXT[], avatar_url TEXT, website TEXT,
                is_verified BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Migration: add missing columns to profiles
        for col_sql in [
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS dob TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS phone TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS country TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS city TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS avail TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS title TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS sections_order TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS custom_sections TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS profile_color TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS profile_style TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS first_name TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS middle_name TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS last_name TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS cover_url TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS short_bio TEXT",
        ]:
            try: conn.run(col_sql)
            except Exception: pass
        # Migration: sort_order for experience
        try: conn.run("ALTER TABLE experience ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0")
        except Exception: pass

        # ── Profile Follows ──
        try:
            conn.run("""
                CREATE TABLE IF NOT EXISTS profile_follows (
                    id          SERIAL PRIMARY KEY,
                    follower_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    followed_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at  TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT uq_profile_follow UNIQUE (follower_id, followed_id),
                    CONSTRAINT no_self_follow    CHECK  (follower_id != followed_id)
                )
            """)
            conn.run("CREATE INDEX IF NOT EXISTS idx_pf_followed ON profile_follows(followed_id)")
            conn.run("CREATE INDEX IF NOT EXISTS idx_pf_follower ON profile_follows(follower_id)")
        except Exception as _pfe:
            print(f"[init_db] profile_follows setup note: {_pfe}")

        # ── Profile Views ──
        try:
            conn.run("""
                CREATE TABLE IF NOT EXISTS profile_views (
                    id              SERIAL PRIMARY KEY,
                    viewed_user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    viewer_user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    viewed_at       TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Migration: drop old UNIQUE/CHECK constraints from prior version (event-log redesign)
            try: conn.run("ALTER TABLE profile_views DROP CONSTRAINT IF EXISTS uq_profile_view")
            except Exception: pass
            try: conn.run("ALTER TABLE profile_views DROP CONSTRAINT IF EXISTS no_self_profile_view")
            except Exception: pass
            # Composite index for "last view" lookup (24h check query)
            conn.run("CREATE INDEX IF NOT EXISTS idx_pv_pair_time ON profile_views(viewed_user_id, viewer_user_id, viewed_at DESC)")
            # Index for COUNT(*) per profile
            conn.run("CREATE INDEX IF NOT EXISTS idx_pv_viewed ON profile_views(viewed_user_id)")
        except Exception as _pve:
            print(f"[init_db] profile_views setup note: {_pve}")

        # ── Profession Categories System ──
        conn.run("""
            CREATE TABLE IF NOT EXISTS profession_categories (
                id             SERIAL PRIMARY KEY,
                name_ar        VARCHAR(100) NOT NULL,
                name_en        VARCHAR(100) NOT NULL,
                slug           VARCHAR(100) NOT NULL UNIQUE,
                icon           VARCHAR(60)  NOT NULL DEFAULT 'user-round',
                category_group VARCHAR(60),
                is_active      BOOLEAN DEFAULT TRUE,
                sort_order     SMALLINT DEFAULT 0,
                created_at     TIMESTAMPTZ DEFAULT NOW(),
                updated_at     TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        try:
            conn.run("CREATE INDEX IF NOT EXISTS idx_prof_slug  ON profession_categories(slug)")
            conn.run("CREATE INDEX IF NOT EXISTS idx_prof_group ON profession_categories(category_group)")
        except Exception: pass
        try:
            conn.run("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS profession_id INTEGER REFERENCES profession_categories(id) ON DELETE SET NULL")
        except Exception: pass
        try:
            conn.run("""
                CREATE TABLE IF NOT EXISTS profession_suggestions (
                    id               SERIAL PRIMARY KEY,
                    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    suggested_name_ar TEXT NOT NULL,
                    suggested_name_en TEXT,
                    normalized_name   TEXT,
                    status           VARCHAR(20) DEFAULT 'pending',
                    reviewed_by      INTEGER REFERENCES users(id),
                    reviewed_at      TIMESTAMPTZ,
                    review_note      TEXT,
                    created_at       TIMESTAMPTZ DEFAULT NOW(),
                    updated_at       TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        except Exception: pass
        try:
            conn.run("CREATE INDEX IF NOT EXISTS idx_prof_sugg_user ON profession_suggestions(user_id)")
        except Exception: pass
        try:
            conn.run("CREATE INDEX IF NOT EXISTS idx_prof_sugg_status ON profession_suggestions(status)")
        except Exception: pass
        try:
            conn.run("""
                INSERT INTO profession_categories (name_ar,name_en,slug,icon,category_group,sort_order) VALUES
                ('مطور برمجيات','Software Developer','software-developer','code-2','tech',10),
                ('مطور ويب','Web Developer','web-developer','globe','tech',11),
                ('مطور تطبيقات','Mobile Developer','mobile-developer','smartphone','tech',12),
                ('مهندس بيانات','Data Engineer','data-engineer','database','tech',13),
                ('عالم بيانات','Data Scientist','data-scientist','brain-circuit','tech',14),
                ('مهندس DevOps','DevOps Engineer','devops-engineer','server','tech',15),
                ('مصمم UI/UX','UI/UX Designer','ui-ux-designer','layout-dashboard','tech',16),
                ('محلل أنظمة','Systems Analyst','systems-analyst','monitor','tech',17),
                ('أمن المعلومات','Cybersecurity Specialist','cybersecurity','shield-check','tech',18),
                ('مدير تقنية','Tech Lead / CTO','tech-lead','cpu','tech',19),
                ('معلم','Teacher','teacher','book-open','education',20),
                ('أستاذ جامعي','University Professor','professor','graduation-cap','education',21),
                ('مدرب','Trainer','trainer','presentation','education',22),
                ('مستشار تعليمي','Education Consultant','education-consultant','lightbulb','education',23),
                ('طبيب','Doctor','doctor','stethoscope','health',30),
                ('ممرض','Nurse','nurse','heart-pulse','health',31),
                ('صيدلاني','Pharmacist','pharmacist','pill','health',32),
                ('معالج نفسي','Therapist','therapist','brain','health',33),
                ('طبيب أسنان','Dentist','dentist','smile','health',34),
                ('مهندس مدني','Civil Engineer','civil-engineer','hard-hat','engineering',40),
                ('مهندس كهربائي','Electrical Engineer','electrical-engineer','zap','engineering',41),
                ('مهندس ميكانيكي','Mechanical Engineer','mechanical-engineer','settings','engineering',42),
                ('مهندس معماري','Architect','architect','pencil-ruler','engineering',43),
                ('مهندس كيميائي','Chemical Engineer','chemical-engineer','flask-conical','engineering',44),
                ('محاسب','Accountant','accountant','calculator','finance',50),
                ('محلل مالي','Financial Analyst','financial-analyst','bar-chart-2','finance',51),
                ('مدقق حسابات','Auditor','auditor','scan-search','finance',52),
                ('مستشار مالي','Financial Advisor','financial-advisor','trending-up','finance',53),
                ('مصمم جرافيك','Graphic Designer','graphic-designer','palette','design',60),
                ('مصمم داخلي','Interior Designer','interior-designer','home','design',61),
                ('مصمم أزياء','Fashion Designer','fashion-designer','shirt','design',62),
                ('مسوّق رقمي','Digital Marketer','digital-marketer','megaphone','marketing',70),
                ('مندوب مبيعات','Sales Representative','sales-rep','handshake','marketing',71),
                ('مدير تسويق','Marketing Manager','marketing-manager','target','marketing',72),
                ('متخصص SEO','SEO Specialist','seo-specialist','search','marketing',73),
                ('منشئ محتوى','Content Creator','content-creator','pen-tool','marketing',74),
                ('محامي','Lawyer','lawyer','scale','legal',80),
                ('مستشار قانوني','Legal Consultant','legal-consultant','file-text','legal',81),
                ('كهربائي','Electrician','electrician','plug','trades',90),
                ('سباك','Plumber','plumber','wrench','trades',91),
                ('نجار','Carpenter','carpenter','hammer','trades',92),
                ('ميكانيكي سيارات','Car Mechanic','car-mechanic','wrench','trades',93),
                ('سائق','Driver','driver','car','transport',100),
                ('طيار','Pilot','pilot','plane','transport',101),
                ('سائق شاحنة','Truck Driver','truck-driver','truck','transport',102),
                ('طباخ / شيف','Chef','chef','chef-hat','hospitality',110),
                ('نادل','Waiter','waiter','utensils','hospitality',111),
                ('مدير فندق','Hotel Manager','hotel-manager','hotel','hospitality',112),
                ('مدير عام','General Manager / CEO','ceo','briefcase','management',120),
                ('مدير موارد بشرية','HR Manager','hr-manager','users','management',121),
                ('مدير مشاريع','Project Manager','project-manager','clipboard-list','management',122),
                ('مدير تشغيل','Operations Manager','operations-manager','settings-2','management',123),
                ('حارس أمن','Security Guard','security-guard','shield','security',130),
                ('مصور','Photographer','photographer','camera','media',140),
                ('صحفي','Journalist','journalist','newspaper','media',141),
                ('منتج فيديو','Video Producer','video-producer','video','media',142),
                ('مذيع','Presenter / Broadcaster','presenter','mic','media',143),
                ('مؤثر / يوتيوبر','Influencer / YouTuber','influencer','star','media',144)
                ON CONFLICT (slug) DO NOTHING
            """)
        except Exception as e:
            print(f"[Seed professions] {e}")

        conn.run("""
            CREATE TABLE IF NOT EXISTS experience (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL, company TEXT NOT NULL,
                location TEXT, start_date TEXT, end_date TEXT,
                is_current BOOLEAN DEFAULT FALSE, description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS education (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                institution TEXT NOT NULL, degree TEXT, field TEXT,
                start_year INTEGER, end_year INTEGER, description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS user_skills (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                skill TEXT NOT NULL,
                level TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        try:
            conn.run("ALTER TABLE user_skills ADD CONSTRAINT IF NOT EXISTS user_skills_uid_skill_uq UNIQUE (user_id, skill)")
        except Exception: pass
        try:
            conn.run("ALTER TABLE user_skills ADD COLUMN IF NOT EXISTS note TEXT")
        except Exception: pass
        conn.run("""
            CREATE TABLE IF NOT EXISTS user_langs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                language TEXT NOT NULL,
                level TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        try:
            conn.run("ALTER TABLE user_langs ADD CONSTRAINT IF NOT EXISTS user_langs_uid_lang_uq UNIQUE (user_id, language)")
        except Exception: pass
        conn.run("""
            CREATE TABLE IF NOT EXISTS user_links (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                link_type TEXT,
                url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        try:
            conn.run("ALTER TABLE user_links ADD CONSTRAINT IF NOT EXISTS user_links_uid_link_uq UNIQUE (user_id, link_type)")
        except Exception: pass
        conn.run("""
            CREATE TABLE IF NOT EXISTS courses (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL, provider TEXT,
                completion_date TEXT, certificate_url TEXT, description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        try:
            conn.run("ALTER TABLE courses ALTER COLUMN name DROP NOT NULL")
        except Exception: pass
        try:
            conn.run("ALTER TABLE courses ADD COLUMN IF NOT EXISTS title TEXT")
        except Exception: pass
        conn.run("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                company_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT,
                location TEXT,
                job_type TEXT DEFAULT 'full_time',
                salary_min INTEGER,
                salary_max INTEGER,
                currency TEXT DEFAULT 'USD',
                experience_years INTEGER DEFAULT 0,
                skills TEXT[],
                status TEXT DEFAULT 'active',
                views INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS job_applications (
                id SERIAL PRIMARY KEY,
                job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                status TEXT DEFAULT 'pending',
                cover_letter TEXT,
                applied_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(job_id, user_id)
            )
        """)
        # KYC table
        conn.run("""
            CREATE TABLE IF NOT EXISTS kyc_submissions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                step TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                email_code TEXT,
                email_verified BOOLEAN DEFAULT FALSE,
                phone TEXT,
                phone_code TEXT,
                phone_verified BOOLEAN DEFAULT FALSE,
                id_front_url TEXT,
                selfie_url TEXT,
                admin_note TEXT,
                submitted_at TIMESTAMP DEFAULT NOW(),
                reviewed_at TIMESTAMP,
                UNIQUE(user_id)
            )
        """)
        # Add KYC fields to users if not exist
        for col in [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS kyc_step TEXT DEFAULT 'none'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE",
        ]:
            try: conn.run(col)
            except: pass

        # Messages table
        conn.run("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Notifications table
        conn.run("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                type TEXT NOT NULL,
                title TEXT,
                body TEXT,
                link TEXT,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS verify_requests (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                item_type TEXT,
                item_id INTEGER,
                item_title TEXT,
                item_company TEXT,
                document_url TEXT, notes TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Migration: add new columns if not exist
        for col in [
            "ALTER TABLE verify_requests ADD COLUMN IF NOT EXISTS item_type TEXT",
            "ALTER TABLE verify_requests ADD COLUMN IF NOT EXISTS item_id INTEGER",
            "ALTER TABLE verify_requests ADD COLUMN IF NOT EXISTS item_title TEXT",
            "ALTER TABLE verify_requests ADD COLUMN IF NOT EXISTS item_company TEXT",
        ]:
            try: conn.run(col)
            except: pass
        print("✅ Database ready.")
    finally:
        
        # ── Comprehensive column migrations (idempotent) ──
        _migrations = [
            # experience
            "ALTER TABLE experience ADD COLUMN IF NOT EXISTS company TEXT",
            "ALTER TABLE experience ADD COLUMN IF NOT EXISTS location TEXT",
            "ALTER TABLE experience ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT FALSE",
            "ALTER TABLE experience ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE experience ADD COLUMN IF NOT EXISTS start_date TEXT",
            "ALTER TABLE experience ADD COLUMN IF NOT EXISTS end_date TEXT",
            # education
            "ALTER TABLE education ADD COLUMN IF NOT EXISTS degree TEXT",
            "ALTER TABLE education ADD COLUMN IF NOT EXISTS field TEXT",
            "ALTER TABLE education ADD COLUMN IF NOT EXISTS start_year INTEGER",
            "ALTER TABLE education ADD COLUMN IF NOT EXISTS end_year INTEGER",
            "ALTER TABLE education ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE education ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT FALSE",
            # courses
            "ALTER TABLE courses ADD COLUMN IF NOT EXISTS title TEXT",
            "ALTER TABLE courses ADD COLUMN IF NOT EXISTS provider TEXT",
            "ALTER TABLE courses ADD COLUMN IF NOT EXISTS completion_date TEXT",
            "ALTER TABLE courses ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE courses ADD COLUMN IF NOT EXISTS certificate_url TEXT",
            # profiles
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS dob TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS phone TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS country TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS city TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS avail TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS title TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS sections_order TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS custom_sections TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS profile_color TEXT",
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS profile_style TEXT",
        ]
        for _m in _migrations:
            try: conn.run(_m)
            except Exception: pass
        # courses: make name nullable (old schema compat)
        try: conn.run("ALTER TABLE courses ALTER COLUMN name DROP NOT NULL")
        except Exception: pass
        # Add UNIQUE constraints (using DO $$ for idempotency)
        _constraints = [
            ("user_langs", "user_id, language"),
            ("user_skills", "user_id, skill"),
            ("user_links", "user_id, link_type"),
        ]
        for _tbl, _cols in _constraints:
            try:
                conn.run(f"ALTER TABLE {_tbl} ADD CONSTRAINT {_tbl}_unique_uq UNIQUE ({_cols})")
            except Exception: pass  # already exists
        release_conn(conn)
    # Phase 2: company tables
    ensure_company_tables()


def _unique_tw_id(conn, user_type: str, country_code: str) -> str:
    """يولّد tw_id فريد مع التحقق من عدم التكرار."""
    while True:
        tw_id = generate_tw_id(user_type, country_code)
        existing = conn.run(
            "SELECT id FROM users WHERE tw_id = :tw_id", tw_id=tw_id
        )
        if not existing:
            return tw_id


# ══ المستخدمون ══
def create_user(
    full_name: str, email: str, password: str,
    user_type: str, country_code: str = 'DEFAULT'
) -> dict:
    conn = get_conn()
    try:
        tw_id = _unique_tw_id(conn, user_type, country_code)
        rows = conn.run(
            "INSERT INTO users (tw_id, full_name, email, password_hash, user_type, country_code) "
            "VALUES (:tw_id, :name, :email, :pw, :utype, :cc) "
            "RETURNING id, tw_id, full_name, email, user_type, created_at",
            tw_id=tw_id, name=full_name,
            email=email.lower().strip(),
            pw=hash_password(password),
            utype=user_type, cc=country_code
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise ValueError("البريد الإلكتروني مسجل مسبقاً")
        raise
    finally:
        release_conn(conn)


def authenticate_user(email: str, password: str) -> Optional[dict]:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, tw_id, full_name, email, password_hash, user_type, country_code, created_at "
            "FROM users WHERE email = :email",
            email=email.lower().strip()
        )
        if not rows:
            return None
        cols = [c["name"] for c in conn.columns]
        user = _row_to_dict(cols, rows[0])
        if not verify_password(password, user["password_hash"]):
            return None
        user.pop("password_hash")
        # ولّد tw_id لو ما عنده (حسابات قديمة)
        if not user.get("tw_id"):
            tw_id = _unique_tw_id(conn, user.get("user_type", "emp"), user.get("country_code", "DEFAULT"))
            conn.run("UPDATE users SET tw_id = :tw_id WHERE id = :uid", tw_id=tw_id, uid=user["id"])
            user["tw_id"] = tw_id
        return _serialize(user)
    finally:
        release_conn(conn)


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, tw_id, full_name, email, user_type, created_at FROM users WHERE id = :uid",
            uid=user_id
        )
        if not rows:
            return None
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)


# ══ الملفات الشخصية ══
def _safe_query(conn, sql, uid):
    """
    EMPTY RESULT vs QUERY FAILURE — explicit separation.

    EMPTY RESULT  → rows=[] → returns [] → UI shows empty section (correct)
    QUERY FAILURE → exception → logs [SCHEMA_ERROR] + tries fallback
                  → fallback returns row count so UI does NOT hide real data
                  → logs [SCHEMA_FALLBACK] "run migrations!" for operator

    Prevents SQL schema exceptions from becoming hidden UI sections.
    """
    try:
        rows = conn.run(sql, uid=uid)
        cols = [c["name"] for c in conn.columns]
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    except Exception as e:
        err = str(e)
        import re as _re
        tbl_m = _re.search("FROM ([a-z_]+)", sql)
        tbl = tbl_m.group(1) if tbl_m else "unknown"
        print("[SCHEMA_ERROR] table=%s error=%s" % (tbl, err[:100]))
        # Schema mismatch (column missing) — retry with minimal columns
        if any(k in err for k in ("UndefinedColumn", "column", "does not exist")):
            try:
                rows2 = conn.run(
                    "SELECT id, user_id FROM " + tbl + " WHERE user_id = :uid ORDER BY id DESC",
                    uid=uid
                )
                cols2 = [c["name"] for c in conn.columns]
                result = [_serialize(_row_to_dict(cols2, r)) for r in rows2]
                print("[SCHEMA_FALLBACK] %s: returned %d rows — run migrations!" % (tbl, len(result)))
                return result
            except Exception as e2:
                print("[SCHEMA_FALLBACK_FAIL] %s: %s" % (tbl, str(e2)))
        print("[QUERY_FAILURE] %s: returning [] — data may be hidden! Check migrations." % tbl)
        return []


def _get_extras(conn, user_id: int) -> dict:
    return {
        "experience": _safe_query(conn,
            "SELECT id, title, company, location, start_date, end_date, "
            "is_current, description, created_at, sort_order "
            "FROM experience WHERE user_id = :uid ORDER BY sort_order ASC, id DESC", user_id),
        "education": _safe_query(conn,
            "SELECT id, institution, degree, field, start_year, end_year, "
            "is_current, description, created_at "
            "FROM education WHERE user_id = :uid ORDER BY id DESC", user_id),
        "courses": _safe_query(conn,
            "SELECT id, title, provider, completion_date, certificate_url, "
            "description, created_at "
            "FROM courses WHERE user_id = :uid ORDER BY id DESC", user_id),
        "skills": _safe_query(conn,
            "SELECT id, skill, level, note FROM user_skills "
            "WHERE user_id = :uid ORDER BY id", user_id),
        "langs": _safe_query(conn,
            "SELECT id, language, level FROM user_langs "
            "WHERE user_id = :uid ORDER BY id", user_id),
        "links": _safe_query(conn,
            "SELECT id, link_type, url FROM user_links "
            "WHERE user_id = :uid ORDER BY id", user_id),
    }


def get_public_profile(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, tw_id, full_name, user_type, created_at FROM users WHERE id = :uid",
            uid=user_id
        )
        if not rows:
            return None
        cols = [c["name"] for c in conn.columns]
        user = _serialize(_row_to_dict(cols, rows[0]))

        try:
            rows = conn.run(
                "SELECT p.headline, p.bio, p.short_bio, p.location, p.skills, p.avatar_url, p.website, p.is_verified, "
                "p.dob, p.phone, p.country, p.city, p.avail, p.title, p.sections_order, p.custom_sections, "
                "p.profile_color, p.profile_style, p.profession_id, p.cover_url, "
                "p.first_name, p.middle_name, p.last_name, "
                "pc.id AS pc_id, pc.name_ar AS pc_name_ar, pc.name_en AS pc_name_en, "
                "pc.slug AS pc_slug, pc.icon AS pc_icon, pc.category_group AS pc_category_group "
                "FROM profiles p LEFT JOIN profession_categories pc ON p.profession_id = pc.id "
                "WHERE p.user_id = :uid", uid=user_id
            )
        except Exception as _e:
            print(f"[get_public_profile] LEFT JOIN failed: {_e} — adding column and retrying")
            try:
                conn.run("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS profession_id INTEGER")
            except Exception: pass
            try:
                conn.run("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS cover_url TEXT")
            except Exception: pass
            try:
                conn.run("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS short_bio TEXT")
            except Exception: pass
            try:
                rows = conn.run(
                    "SELECT p.headline, p.bio, p.short_bio, p.location, p.skills, p.avatar_url, p.website, p.is_verified, "
                    "p.dob, p.phone, p.country, p.city, p.avail, p.title, p.sections_order, p.custom_sections, "
                    "p.profile_color, p.profile_style, p.profession_id, p.cover_url, "
                    "p.first_name, p.middle_name, p.last_name, "
                    "pc.id AS pc_id, pc.name_ar AS pc_name_ar, pc.name_en AS pc_name_en, "
                    "pc.slug AS pc_slug, pc.icon AS pc_icon, pc.category_group AS pc_category_group "
                    "FROM profiles p LEFT JOIN profession_categories pc ON p.profession_id = pc.id "
                    "WHERE p.user_id = :uid", uid=user_id
                )
            except Exception:
                rows = conn.run(
                    "SELECT headline, bio, short_bio, location, skills, avatar_url, website, is_verified, "
                    "dob, phone, country, city, avail, title, sections_order, custom_sections, "
                    "profile_color, profile_style, cover_url, first_name, middle_name, last_name "
                    "FROM profiles WHERE user_id = :uid", uid=user_id
                )
        cols = [c["name"] for c in conn.columns]
        profile = _serialize(_row_to_dict(cols, rows[0])) if rows else {}
        profession = None
        if profile.get('pc_id') is not None:
            profession = {
                'id':             profile.get('pc_id'),
                'name_ar':        profile.get('pc_name_ar'),
                'name_en':        profile.get('pc_name_en'),
                'slug':           profile.get('pc_slug'),
                'icon':           profile.get('pc_icon'),
                'category_group': profile.get('pc_category_group'),
            }
        for k in ('pc_id','pc_name_ar','pc_name_en','pc_slug','pc_icon','pc_category_group'):
            profile.pop(k, None)
        profile['profession'] = profession

        return {**user, **profile, **_get_extras(conn, user_id)}
    finally:
        release_conn(conn)


def get_full_profile(user_id: int) -> Optional[dict]:
    cached = _cache_get('profile:'+str(user_id))
    if cached is not None: return cached
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, tw_id, full_name, email, user_type, created_at FROM users WHERE id = :uid",
            uid=user_id
        )
        if not rows:
            return None
        cols = [c["name"] for c in conn.columns]
        user = _serialize(_row_to_dict(cols, rows[0]))

        # Full query with all columns
        # Columns are created in init_db migrations
        try:
            rows = conn.run(
                "SELECT headline, bio, short_bio, location, skills, avatar_url, website, is_verified, "
                "updated_at, dob, phone, country, city, avail, title, sections_order, custom_sections, "
                "profile_color, profile_style, profession_id, cover_url, "
                "first_name, middle_name, last_name "
                "FROM profiles WHERE user_id = :uid", uid=user_id
            )
        except Exception as e:
            print(f"[Profile query error] {e} - trying to add missing columns")
            # Add missing columns and retry
            for col_sql in [
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS dob TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS phone TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS country TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS city TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS avail TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS title TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS sections_order TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS custom_sections TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS profile_color TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS profile_style TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS profession_id INTEGER",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS cover_url TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS first_name TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS middle_name TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS last_name TEXT",
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS short_bio TEXT",
            ]:
                try: conn.run(col_sql)
                except Exception: pass
            # Retry with full query
            try:
                rows = conn.run(
                    "SELECT headline, bio, short_bio, location, skills, avatar_url, website, is_verified, "
                    "updated_at, dob, phone, country, city, avail, title, sections_order, custom_sections, "
                    "profile_color, profile_style, profession_id, cover_url, "
                    "first_name, middle_name, last_name "
                    "FROM profiles WHERE user_id = :uid", uid=user_id
                )
            except Exception as e2:
                print(f"[Profile query FATAL] {e2}")
                raise e2  # Don't return partial data
        cols = [c["name"] for c in conn.columns]
        profile = _serialize(_row_to_dict(cols, rows[0])) if rows else {}

        # Profession lookup (lightweight PK query)
        profession = None
        prof_id = profile.get('profession_id')
        if prof_id:
            try:
                prows = conn.run(
                    "SELECT id,name_ar,name_en,slug,icon,category_group FROM profession_categories WHERE id=:pid",
                    pid=prof_id
                )
                if prows:
                    pcols = [c["name"] for c in conn.columns]
                    profession = _serialize(_row_to_dict(pcols, prows[0]))
            except Exception: pass
        profile['profession'] = profession

        rows = conn.run(
            "SELECT id, status, created_at FROM verify_requests "
            "WHERE user_id = :uid ORDER BY id DESC LIMIT 1", uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        verify_req = _serialize(_row_to_dict(cols, rows[0])) if rows else None

        extras = _get_extras(conn, user_id)
        result = {**user, **profile, **extras, "verify_request": verify_req}
        _cache_set('profile:'+str(user_id), result)
        return result
    finally:
        release_conn(conn)


def update_profile(user_id: int, data: dict) -> dict:
    _TEXT_FIELDS = ("full_name", "first_name", "middle_name", "last_name", "bio", "short_bio", "headline", "title", "location", "phone", "website")
    for _f in _TEXT_FIELDS:
        validate_professional_text(data.get(_f), _f)

    _t0 = _time_mod.time()
    _cache_del('profile:'+str(user_id))
    _THEME_FIELDS = {"profile_color", "profile_style"}
    conn = get_conn()
    try:
        # Clear theme cache only when theme fields change — saves SELECT round-trip on normal saves
        if _THEME_FIELDS & set(data.keys()):
            try:
                _tw = conn.run("SELECT tw_id FROM users WHERE id=:uid", uid=user_id)
                if _tw and _tw[0][0]: _cache_del('theme:'+str(_tw[0][0]))
            except Exception: pass

        # Build full_name from name parts if provided (Profile V2 flow)
        _name_parts = [data.get("first_name"), data.get("middle_name"), data.get("last_name")]
        _built_name = " ".join(p for p in _name_parts if p and p.strip())
        if _built_name:
            conn.run("UPDATE users SET full_name = :name WHERE id = :uid", name=_built_name, uid=user_id)
        elif data.get("full_name"):
            conn.run("UPDATE users SET full_name = :name WHERE id = :uid", name=data["full_name"], uid=user_id)

        # Schema guaranteed by init_db — no runtime ALTER TABLE needed
        allowed = ["headline", "bio", "short_bio", "location", "skills", "avatar_url", "website", "phone", "sections_order", "custom_sections", "dob", "country", "city", "avail", "title", "profile_color", "profile_style", "profession_id", "first_name", "middle_name", "last_name", "cover_url"]
        _clearable = {"dob", "country", "city", "avail"}
        fields = {k: v for k, v in data.items() if k in allowed and (v is not None or k in _clearable)}
        print(f"[update_profile] user={user_id} saving fields: {list(fields.keys())}")

        rows = conn.run("SELECT id FROM profiles WHERE user_id = :uid", uid=user_id)
        if rows:
            if fields:
                set_clause = ", ".join(f"{k} = :{k}" for k in fields)
                update_rows = conn.run(
                    f"UPDATE profiles SET {set_clause}, updated_at = NOW() WHERE user_id = :uid RETURNING id",
                    uid=user_id, **fields
                )
                if not update_rows:
                    print(f"[update_profile] ⚠️ UPDATE returned 0 rows for user {user_id} — running INSERT")
                    raise ValueError("no_profile_row")
                print(f"[update_profile] ✅ DB UPDATE success for user {user_id}, rows={len(update_rows)} — {_time_mod.time()-_t0:.3f}s")
        else:
            cols_list = ["user_id"] + list(fields.keys())
            placeholders = ", ".join(f":{c}" for c in cols_list)
            conn.run(
                f"INSERT INTO profiles ({', '.join(cols_list)}) VALUES ({placeholders})",
                user_id=user_id, **fields
            )
    finally:
        release_conn(conn)
    resp = {"id": user_id, "updated": True}
    resp.update(fields)
    if data.get("full_name"):
        resp["full_name"] = data["full_name"]
    print(f"[update_profile] ⏱ total: {_time_mod.time()-_t0:.3f}s")
    return resp


# ══ الخبرات ══
def add_experience(user_id: int, data: dict) -> dict:
    for _f in ("title", "company", "location", "description"):
        validate_professional_text(data.get(_f), _f)
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO experience (user_id, title, company, location, start_date, end_date, is_current, description) "
            "VALUES (:uid, :title, :company, :location, :start_date, :end_date, :is_current, :description) "
            "RETURNING id, user_id, title, company, location, start_date, end_date, is_current, description, created_at",
            uid=user_id, title=data["title"], company=data["company"],
            location=data.get("location"), start_date=data.get("start_date"),
            end_date=data.get("end_date"), is_current=data.get("is_current", False),
            description=data.get("description")
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)


def update_experience(exp_id: int, user_id: int, data: dict) -> dict:
    for _f in ("title", "company", "location", "description"):
        validate_professional_text(data.get(_f), _f)
    conn = get_conn()
    try:
        allowed = {"title", "company", "location", "start_date", "end_date", "is_current", "description"}
        _nullable = {"end_date"}
        fields = {k: data[k] for k in allowed if k in data and (data[k] is not None or k in _nullable)}
        # clear end_date when is_current becomes True
        if fields.get('is_current') is True:
            fields['end_date'] = None
        if not fields:
            raise ValueError("لا توجد حقول للتحديث")
        set_parts = [f"{k} = :{k}" for k in fields]
        sql = (
            "UPDATE experience SET " + ", ".join(set_parts) +
            " WHERE id = :exp_id AND user_id = :user_id "
            "RETURNING id, user_id, title, company, location, start_date, end_date, is_current, description, created_at"
        )
        rows = conn.run(sql, exp_id=exp_id, user_id=user_id, **fields)
        if not rows:
            raise ValueError("الخبرة غير موجودة أو غير مصرح بتعديلها")
        cols = [c["name"] for c in conn.columns]
        _cache_del('profile:' + str(user_id))
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)


def reorder_experience(user_id: int, ordered_ids: list) -> bool:
    if not ordered_ids:
        return True
    conn = get_conn()
    try:
        # Verify ALL ids belong to this user before any UPDATE
        placeholders = ', '.join([':id' + str(i) for i in range(len(ordered_ids))])
        params = {'uid': user_id}
        for i, eid in enumerate(ordered_ids):
            params['id' + str(i)] = int(eid)
        rows = conn.run(
            f"SELECT id FROM experience WHERE user_id = :uid AND id IN ({placeholders})",
            **params
        )
        if len(rows) != len(ordered_ids):
            raise ValueError("بعض الخبرات غير موجودة أو غير مصرح بترتيبها")
        for pos, eid in enumerate(ordered_ids):
            conn.run(
                "UPDATE experience SET sort_order = :pos WHERE id = :id AND user_id = :uid",
                pos=pos, id=int(eid), uid=user_id
            )
        _cache_del('profile:' + str(user_id))
        return True
    finally:
        release_conn(conn)


# ══ الشهادات ══
def add_education(user_id: int, data: dict) -> dict:
    for _f in ("institution", "degree", "field", "description"):
        validate_professional_text(data.get(_f), _f)
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO education (user_id, institution, degree, field, start_year, end_year, is_current, description) "
            "VALUES (:uid, :institution, :degree, :field, :start_year, :end_year, :is_current, :description) "
            "RETURNING id, user_id, institution, degree, field, start_year, end_year, is_current, description, created_at",
            uid=user_id, institution=data["institution"],
            degree=data.get("degree"), field=data.get("field"),
            start_year=data.get("start_year"), end_year=data.get("end_year"),
            is_current=bool(data.get("is_current", False)),
            description=data.get("description")
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)


# ══ الدورات ══
def add_course(user_id: int, data: dict) -> dict:
    for _f in ("title", "provider", "description"):
        validate_professional_text(data.get(_f), _f)
    conn = get_conn()
    try:
        title_val = data.get("title") or data.get("name") or ""
        rows = conn.run(
            "INSERT INTO courses (user_id, title, provider, completion_date, certificate_url, description) "
            "VALUES (:uid, :title, :provider, :completion_date, :certificate_url, :description) "
            "RETURNING id, user_id, title, provider, completion_date, certificate_url, description, created_at",
            uid=user_id, title=title_val, provider=data.get("provider"),
            completion_date=data.get("completion_date"),
            certificate_url=data.get("certificate_url"),
            description=data.get("description")
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)


def update_education(edu_id: int, user_id: int, data: dict):
    for _f in ("institution", "degree", "field", "description"):
        validate_professional_text(data.get(_f), _f)
    conn = get_conn()
    try:
        rows = conn.run(
            "UPDATE education SET institution=:inst, degree=:deg, field=:fld, "
            "start_year=:sy, end_year=:ey, is_current=:isc, description=:desc "
            "WHERE id=:id AND user_id=:uid "
            "RETURNING id, user_id, institution, degree, field, start_year, end_year, is_current, description, created_at",
            inst=data.get("institution"), deg=data.get("degree"), fld=data.get("field"),
            sy=data.get("start_year"), ey=data.get("end_year"),
            isc=bool(data.get("is_current", False)),
            desc=data.get("description"),
            id=edu_id, uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0])) if rows else None
    finally:
        release_conn(conn)


def update_course(course_id: int, user_id: int, data: dict):
    for _f in ("title", "provider", "description"):
        validate_professional_text(data.get(_f), _f)
    conn = get_conn()
    try:
        title_val = data.get("title") or data.get("name") or ""
        rows = conn.run(
            "UPDATE courses SET title=:title, provider=:provider, completion_date=:cd, "
            "certificate_url=:curl, description=:desc "
            "WHERE id=:id AND user_id=:uid "
            "RETURNING id, user_id, title, provider, completion_date, certificate_url, description, created_at",
            title=title_val, provider=data.get("provider"), cd=data.get("completion_date"),
            curl=data.get("certificate_url"), desc=data.get("description"),
            id=course_id, uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0])) if rows else None
    finally:
        release_conn(conn)


# ══ طلبات التحقق ══
def create_verify_request(user_id: int, data: dict) -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO verify_requests (user_id, document_url, notes, status) "
            "VALUES (:uid, :doc_url, :notes, 'pending') "
            "RETURNING id, user_id, document_url, notes, status, created_at",
            uid=user_id, doc_url=data.get("document_url"), notes=data.get("notes")
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)


def get_user_id_by_tw_id(tw_id: str) -> Optional[int]:
    """يرجع الـ id الرقمي من الـ tw_id."""
    conn = get_conn()
    try:
        rows = conn.run("SELECT id FROM users WHERE tw_id = :tw_id", tw_id=tw_id)
        return rows[0][0] if rows else None
    finally:
        release_conn(conn)


def get_profile_by_tw_id(tw_id: str) -> Optional[dict]:
    """يجيب الملف الشخصي العام بالـ tw_id."""
    uid = get_user_id_by_tw_id(tw_id)
    return get_public_profile(uid) if uid else None


def get_full_profile_by_tw_id(tw_id: str) -> Optional[dict]:
    uid = get_user_id_by_tw_id(tw_id)
    if not uid: return None
    return get_full_profile(uid)


# ══ الوظائف ══

def add_job(company_id: int, data: dict) -> dict:
    _cache_del('jobs:')
    conn = get_conn()
    try:
        skills = data.get("skills") or []
        rows = conn.run(
            "INSERT INTO jobs (company_id, title, description, location, job_type, "
            "salary_min, salary_max, currency, experience_years, skills, status) "
            "VALUES (:cid, :title, :desc, :loc, :jtype, :smin, :smax, :cur, :exp, :skills, 'active') "
            "RETURNING id, company_id, title, description, location, job_type, "
            "salary_min, salary_max, currency, experience_years, skills, status, created_at",
            cid=company_id, title=data.get("title",""),
            desc=data.get("description",""), loc=data.get("location",""),
            jtype=data.get("job_type","full_time"),
            smin=data.get("salary_min"), smax=data.get("salary_max"),
            cur=data.get("currency","USD"),
            exp=data.get("experience_years",0),
            skills=skills if skills else None
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)

def get_jobs(filters: dict = None) -> list:
    cache_key = 'jobs:' + str(sorted((filters or {}).items()))
    cached = _cache_get(cache_key)
    if cached is not None: return cached
    conn = get_conn()
    try:
        where = "WHERE j.status='active'"
        params = {}
        if filters:
            if filters.get("search"):
                where += " AND (j.title ILIKE :search OR j.description ILIKE :search)"
                params["search"] = f"%{filters['search']}%"
            if filters.get("location"):
                where += " AND j.location ILIKE :loc"
                params["loc"] = f"%{filters['location']}%"
            if filters.get("job_type"):
                where += " AND j.job_type = :jtype"
                params["jtype"] = filters["job_type"]
            if filters.get("company_id"):
                where += " AND j.company_id = :cid"
                params["cid"] = filters["company_id"]
        rows = conn.run(
            f"SELECT j.id, j.company_id, j.title, j.description, j.location, "
            f"j.job_type, j.salary_min, j.salary_max, j.currency, "
            f"j.experience_years, j.skills, j.status, j.views, j.created_at, "
            f"u.full_name AS company_name "
            f"FROM jobs j JOIN users u ON u.id=j.company_id "
            f"{where} ORDER BY j.created_at DESC LIMIT 50",
            **params
        )
        cols = [c["name"] for c in conn.columns]
        result = [_serialize(_row_to_dict(cols, r)) for r in rows]
        _cache_set(cache_key, result)
        return result
    finally:
        release_conn(conn)

def get_job(job_id: int) -> dict:
    conn = get_conn()
    try:
        conn.run("UPDATE jobs SET views=views+1 WHERE id=:id", id=job_id)
        rows = conn.run(
            "SELECT j.*, u.full_name AS company_name "
            "FROM jobs j JOIN users u ON u.id=j.company_id "
            "WHERE j.id=:id", id=job_id
        )
        if not rows: return None
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)

def apply_job(job_id: int, user_id: int, cover_letter: str = "") -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO job_applications (job_id, user_id, cover_letter) "
            "VALUES (:jid, :uid, :cl) "
            "ON CONFLICT (job_id, user_id) DO NOTHING "
            "RETURNING id, job_id, user_id, status, applied_at",
            jid=job_id, uid=user_id, cl=cover_letter
        )
        if not rows:
            return {"already_applied": True}
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)

def get_job_applicants(job_id: int) -> list:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT ja.id, ja.job_id, ja.user_id, ja.status, ja.cover_letter, ja.applied_at, "
            "u.full_name, u.email, u.user_type "
            "FROM job_applications ja JOIN users u ON u.id=ja.user_id "
            "WHERE ja.job_id=:jid ORDER BY ja.applied_at DESC",
            jid=job_id
        )
        cols = [c["name"] for c in conn.columns]
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)

def get_user_applications(user_id: int) -> list:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT ja.id, ja.job_id, ja.status, ja.applied_at, "
            "j.title, j.location, j.company_id, u.full_name AS company_name "
            "FROM job_applications ja "
            "JOIN jobs j ON j.id=ja.job_id "
            "JOIN users u ON u.id=j.company_id "
            "WHERE ja.user_id=:uid ORDER BY ja.applied_at DESC",
            uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)

def update_application_status(app_id: int, status: str) -> dict:
    conn = get_conn()
    try:
        conn.run("UPDATE job_applications SET status=:s WHERE id=:id", s=status, id=app_id)
        return {"success": True}
    finally:
        release_conn(conn)

def delete_job(job_id: int, company_id: int) -> bool:
    conn = get_conn()
    try:
        conn.run("DELETE FROM jobs WHERE id=:id AND company_id=:cid", id=job_id, cid=company_id)
        return True
    finally:
        release_conn(conn)


# ══ KYC System ══
import random, string

def generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

def start_kyc(user_id: int) -> dict:
    """Start or get KYC submission"""
    conn = get_conn()
    try:
        rows = conn.run("SELECT * FROM kyc_submissions WHERE user_id=:uid", uid=user_id)
        if rows:
            cols = [c["name"] for c in conn.columns]
            return _serialize(_row_to_dict(cols, rows[0]))
        # Create new
        rows = conn.run(
            "INSERT INTO kyc_submissions (user_id, step) VALUES (:uid, 'email') RETURNING *",
            uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)

def send_email_code(user_id: int, email: str) -> str:
    """Generate email verification code"""
    code = generate_code()
    conn = get_conn()
    try:
        conn.run(
            "UPDATE kyc_submissions SET email_code=:code WHERE user_id=:uid",
            code=code, uid=user_id
        )
        return code  # In production: send via email API
    finally:
        release_conn(conn)

def verify_email_code(user_id: int, code: str) -> bool:
    """Verify email code"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT email_code FROM kyc_submissions WHERE user_id=:uid",
            uid=user_id
        )
        if not rows or rows[0][0] != code:
            return False
        conn.run(
            "UPDATE kyc_submissions SET email_verified=TRUE, step='phone' WHERE user_id=:uid",
            uid=user_id
        )
        conn.run("UPDATE users SET email_verified=TRUE WHERE id=:uid", uid=user_id)
        return True
    finally:
        release_conn(conn)

def send_phone_code(user_id: int, phone: str) -> str:
    """Generate phone verification code"""
    code = generate_code()
    conn = get_conn()
    try:
        conn.run(
            "UPDATE kyc_submissions SET phone=:phone, phone_code=:code WHERE user_id=:uid",
            phone=phone, code=code, uid=user_id
        )
        return code  # In production: send via SMS API
    finally:
        release_conn(conn)

def verify_phone_code(user_id: int, code: str) -> bool:
    """Verify phone code"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT phone_code FROM kyc_submissions WHERE user_id=:uid",
            uid=user_id
        )
        if not rows or rows[0][0] != code:
            return False
        conn.run(
            "UPDATE kyc_submissions SET phone_verified=TRUE, step='id_upload' WHERE user_id=:uid",
            uid=user_id
        )
        conn.run("UPDATE users SET phone_verified=TRUE WHERE id=:uid", uid=user_id)
        return True
    finally:
        release_conn(conn)

def upload_kyc_docs(user_id: int, id_url: str, selfie_url: str = None) -> dict:
    """Save uploaded ID and selfie"""
    conn = get_conn()
    try:
        conn.run(
            "UPDATE kyc_submissions SET id_front_url=:id_url, selfie_url=:selfie, step='review', submitted_at=NOW() WHERE user_id=:uid",
            id_url=id_url, selfie=selfie_url, uid=user_id
        )
        # Create admin review request
        rows = conn.run(
            "SELECT u.full_name FROM users u WHERE u.id=:uid",
            uid=user_id
        )
        return {"status": "submitted", "step": "review"}
    finally:
        release_conn(conn)

def get_kyc_status(user_id: int) -> dict:
    """Get current KYC status"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT ks.*, u.is_verified, u.email_verified, u.phone_verified "
            "FROM kyc_submissions ks JOIN users u ON u.id=ks.user_id WHERE ks.user_id=:uid",
            uid=user_id
        )
        if not rows:
            return {"step": "none", "status": "not_started"}
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)

def admin_approve_kyc(user_id: int, note: str = "") -> dict:
    """Admin approves KYC"""
    conn = get_conn()
    try:
        conn.run(
            "UPDATE kyc_submissions SET status='approved', admin_note=:note, reviewed_at=NOW() WHERE user_id=:uid",
            note=note, uid=user_id
        )
        conn.run("UPDATE users SET is_verified=TRUE WHERE id=:uid", uid=user_id)
        return {"success": True}
    finally:
        release_conn(conn)

def admin_reject_kyc(user_id: int, note: str = "") -> dict:
    """Admin rejects KYC"""
    conn = get_conn()
    try:
        conn.run(
            "UPDATE kyc_submissions SET status='rejected', step='rejected', admin_note=:note, reviewed_at=NOW() WHERE user_id=:uid",
            note=note, uid=user_id
        )
        return {"success": True}
    finally:
        release_conn(conn)

def get_all_kyc_submissions() -> list:
    """Get all KYC submissions for admin"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT ks.*, u.full_name, u.email, u.user_type "
            "FROM kyc_submissions ks JOIN users u ON u.id=ks.user_id "
            "ORDER BY ks.submitted_at DESC"
        )
        cols = [c["name"] for c in conn.columns]
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)


# ══ Messages System ══

def send_message(sender_id: int, receiver_id: int, content: str) -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO messages (sender_id, receiver_id, content) "
            "VALUES (:sid, :rid, :content) RETURNING id, sender_id, receiver_id, content, is_read, created_at",
            sid=sender_id, rid=receiver_id, content=content
        )
        cols = [c["name"] for c in conn.columns]
        msg = _serialize(_row_to_dict(cols, rows[0]))
        # Create notification for receiver
        create_notification(receiver_id, 'message', 'رسالة جديدة', content[:60], '/messages.html')
        return msg
    finally:
        release_conn(conn)

def get_conversations(user_id: int) -> list:
    """Get all unique conversations for a user"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT DISTINCT ON (other_id) "
            "CASE WHEN sender_id=:uid THEN receiver_id ELSE sender_id END AS other_id, "
            "content, created_at, is_read, sender_id, "
            "u.full_name, u.user_type "
            "FROM messages m "
            "JOIN users u ON u.id = CASE WHEN m.sender_id=:uid THEN m.receiver_id ELSE m.sender_id END "
            "WHERE sender_id=:uid OR receiver_id=:uid "
            "ORDER BY other_id, created_at DESC",
            uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)

def get_messages(user_id: int, other_id: int) -> list:
    """Get messages between two users"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT m.*, u.full_name as sender_name "
            "FROM messages m JOIN users u ON u.id=m.sender_id "
            "WHERE (sender_id=:uid AND receiver_id=:oid) "
            "OR (sender_id=:oid AND receiver_id=:uid) "
            "ORDER BY created_at ASC LIMIT 100",
            uid=user_id, oid=other_id
        )
        cols = [c["name"] for c in conn.columns]
        # Mark as read
        conn.run(
            "UPDATE messages SET is_read=TRUE "
            "WHERE receiver_id=:uid AND sender_id=:oid AND is_read=FALSE",
            uid=user_id, oid=other_id
        )
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)

def get_unread_count(user_id: int) -> int:
    """Get count of unread messages"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT COUNT(*) FROM messages WHERE receiver_id=:uid AND is_read=FALSE",
            uid=user_id
        )
        return rows[0][0] if rows else 0
    finally:
        release_conn(conn)

def get_profile_style(tw_id: str) -> str:
    """Lightweight: get only profile_style for a given tw_id. Used for SSR theme injection.
    Uses _cache to avoid re-querying on repeated page views (TTL 60s).
    """
    cache_key = f"theme:{tw_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return str(cached)
    try:
        conn = get_conn()
        try:
            rows = conn.run(
                "SELECT p.profile_style FROM profiles p "
                "JOIN users u ON u.id = p.user_id "
                "WHERE u.tw_id = :tw_id",
                tw_id=tw_id
            )
            style = str(rows[0][0]) if rows and rows[0][0] else "1"
            _cache_set(cache_key, style, ttl=60)
            return style
        finally:
            release_conn(conn)
    except Exception:
        pass
    return "1"


# ══ Notifications System ══

def create_notification(user_id: int, type_: str, title: str, body: str, link: str = "") -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO notifications (user_id, type, title, body, link) "
            "VALUES (:uid, :type, :title, :body, :link) RETURNING id, user_id, type, title, body, link, is_read, created_at",
            uid=user_id, type=type_, title=title, body=body, link=link
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)

def get_notifications(user_id: int, limit: int = 50) -> list:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT * FROM notifications WHERE user_id=:uid "
            "ORDER BY created_at DESC LIMIT :lim",
            uid=user_id, lim=limit
        )
        cols = [c["name"] for c in conn.columns]
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)

def mark_notifications_read(user_id: int) -> bool:
    conn = get_conn()
    try:
        conn.run("UPDATE notifications SET is_read=TRUE WHERE user_id=:uid", uid=user_id)
        return True
    finally:
        release_conn(conn)

def get_unread_notifications(user_id: int) -> int:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT COUNT(*) FROM notifications WHERE user_id=:uid AND is_read=FALSE",
            uid=user_id
        )
        return rows[0][0] if rows else 0
    finally:
        release_conn(conn)

# ── Site Settings (logos, sizes) ──
def get_site_setting(key: str) -> str:
    try:
        conn = get_conn()
        rows = conn.run("SELECT value FROM site_settings WHERE key=:k LIMIT 1", k=key)
        release_conn(conn)
        return rows[0][0] if rows else ''
    except: return ''

def set_site_setting(key: str, value: str):
    try:
        conn = get_conn()
        conn.run("""
            INSERT INTO site_settings(key,value) VALUES(:k,:v)
            ON CONFLICT(key) DO UPDATE SET value=:v, updated_at=NOW()
        """, k=key, v=value)
        release_conn(conn)
        return True
    except Exception as e:
        print(f"[Settings] Error: {e}")
        return False

def ensure_site_settings_table():
    try:
        conn = get_conn()
        conn.run('''
            CREATE TABLE IF NOT EXISTS site_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        ''')
        release_conn(conn)
    except Exception as e:
        print(f"[DB] site_settings: {e}")

def ensure_reports_table():
    try:
        conn = get_conn()
        conn.run('''
            CREATE TABLE IF NOT EXISTS reports (
                id SERIAL PRIMARY KEY,
                reporter_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                reported_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                reported_type TEXT DEFAULT 'user',
                report_type TEXT NOT NULL,
                reason TEXT,
                target_url TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        ''')
        release_conn(conn)
    except Exception as e:
        print(f"[DB] reports table: {e}")


# ══ Phase 2: Company Profile System Tables (Rule #18) ══
def ensure_company_tables():
    """
    Creates company_profiles, company_follows, company_ratings.
    Safe migration: CREATE TABLE IF NOT EXISTS only — no changes to
    existing tables (users/jobs/profiles untouched). Rule: backward compatible.
    company identity = users.id everywhere (consistent with jobs.company_id).
    """
    try:
        conn = get_conn()
        # ── company_profiles — 1:1 with users (user_id = PK + FK) ──
        conn.run("""
            CREATE TABLE IF NOT EXISTS company_profiles (
                user_id       INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                company_type  TEXT DEFAULT 'private',
                founded_year  INTEGER,
                company_size  TEXT,
                industry      TEXT,
                description   TEXT,
                headquarters  TEXT,
                contact_email TEXT,
                cover_url     TEXT,
                verified_co   BOOLEAN NOT NULL DEFAULT FALSE,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        # ── company_follows — M:M, UNIQUE prevents double-follow at DB level ──
        conn.run("""
            CREATE TABLE IF NOT EXISTS company_follows (
                id          SERIAL PRIMARY KEY,
                company_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                follower_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_follow UNIQUE (company_id, follower_id)
            )
        """)
        conn.run("CREATE INDEX IF NOT EXISTS idx_follows_company  ON company_follows(company_id)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_follows_follower ON company_follows(follower_id)")
        # ── company_ratings — M:M, one rating per (company, rater), score 1-5 ──
        conn.run("""
            CREATE TABLE IF NOT EXISTS company_ratings (
                id          SERIAL PRIMARY KEY,
                company_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                rater_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                score       INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
                comment     TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_rating UNIQUE (company_id, rater_id)
            )
        """)
        conn.run("CREATE INDEX IF NOT EXISTS idx_ratings_company ON company_ratings(company_id)")
        # ── company_posts — M posts per company (Phase 3) ──
        conn.run("""
            CREATE TABLE IF NOT EXISTS company_posts (
                id          SERIAL PRIMARY KEY,
                company_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                body        TEXT NOT NULL,
                tags        TEXT[],
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.run("CREATE INDEX IF NOT EXISTS idx_posts_company ON company_posts(company_id)")
        release_conn(conn)
        print("✅ company tables ready")
    except Exception as e:
        print(f"[DB] company tables: {e}")


# ══ Phase 2: Company Profile Data Layer (Rule #5,#6 — Single Source) ══
# All helpers are pure data layer. No authorization here (that lives in server.py).
# company identity = users.id everywhere.

def ensure_company_profile(user_id: int) -> None:
    """Insert default company_profiles row if missing. Idempotent."""
    conn = get_conn()
    try:
        conn.run(
            "INSERT INTO company_profiles (user_id) VALUES (:uid) "
            "ON CONFLICT (user_id) DO NOTHING",
            uid=user_id
        )
    finally:
        release_conn(conn)


def get_company_profile_row(company_id: int) -> dict:
    """Return company_profiles row as dict, or defaults if none exists."""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT company_type, founded_year, company_size, industry, "
            "description, headquarters, contact_email, cover_url, verified_co "
            "FROM company_profiles WHERE user_id = :uid",
            uid=company_id
        )
        if not rows:
            return {
                "company_type": None, "founded_year": None, "company_size": None,
                "industry": None, "description": None, "headquarters": None,
                "contact_email": None, "cover_url": None, "verified_co": False,
            }
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)


def get_company_extras(company_id: int, viewer_id: int = None) -> dict:
    """
    Aggregated company data: profile + derived stats + viewer-specific flags.
    Derived values (followers_count, rating_avg) computed on demand — not stored.
    """
    conn = get_conn()
    try:
        # followers count — uses idx_follows_company
        fc = conn.run("SELECT COUNT(*) FROM company_follows WHERE company_id = :cid",
                      cid=company_id)
        followers_count = fc[0][0] if fc else 0

        # rating avg + count — uses idx_ratings_company
        rt = conn.run(
            "SELECT AVG(score), COUNT(*) FROM company_ratings WHERE company_id = :cid",
            cid=company_id)
        rating_avg   = round(float(rt[0][0]), 1) if rt and rt[0][0] is not None else None
        rating_count = rt[0][1] if rt else 0

        # viewer-specific: is_following + my_rating (composite indexes)
        is_following = False
        my_rating    = None
        if viewer_id:
            f = conn.run(
                "SELECT 1 FROM company_follows WHERE company_id = :cid AND follower_id = :vid",
                cid=company_id, vid=viewer_id)
            is_following = bool(f)
            r = conn.run(
                "SELECT score FROM company_ratings WHERE company_id = :cid AND rater_id = :vid",
                cid=company_id, vid=viewer_id)
            my_rating = r[0][0] if r else None

        return {
            "followers_count": followers_count,
            "rating_avg":      rating_avg,
            "rating_count":    rating_count,
            "is_following":    is_following,
            "my_rating":       my_rating,
        }
    finally:
        release_conn(conn)


def update_company_profile(user_id: int, fields: dict) -> bool:
    """Update company_profiles for owner. Ensures row exists first."""
    allowed = {"company_type","founded_year","company_size","industry",
               "description","headquarters","contact_email","cover_url"}
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return False
    ensure_company_profile(user_id)
    conn = get_conn()
    try:
        set_clause = ", ".join(f"{k} = :{k}" for k in clean)
        conn.run(
            f"UPDATE company_profiles SET {set_clause}, updated_at = NOW() WHERE user_id = :uid",
            uid=user_id, **clean)
        return True
    finally:
        release_conn(conn)


def follow_company(follower_id: int, company_id: int) -> int:
    """Follow (idempotent). Returns new followers_count."""
    conn = get_conn()
    try:
        conn.run(
            "INSERT INTO company_follows (company_id, follower_id) VALUES (:cid, :fid) "
            "ON CONFLICT (company_id, follower_id) DO NOTHING",
            cid=company_id, fid=follower_id)
        fc = conn.run("SELECT COUNT(*) FROM company_follows WHERE company_id = :cid",
                      cid=company_id)
        return fc[0][0] if fc else 0
    finally:
        release_conn(conn)


def unfollow_company(follower_id: int, company_id: int) -> int:
    """Unfollow (idempotent). Returns new followers_count."""
    conn = get_conn()
    try:
        conn.run(
            "DELETE FROM company_follows WHERE company_id = :cid AND follower_id = :fid",
            cid=company_id, fid=follower_id)
        fc = conn.run("SELECT COUNT(*) FROM company_follows WHERE company_id = :cid",
                      cid=company_id)
        return fc[0][0] if fc else 0
    finally:
        release_conn(conn)


def rate_company(rater_id: int, company_id: int, score: int, comment: str = None) -> dict:
    """Rate (UPSERT — one rating per user). Returns new avg + count."""
    conn = get_conn()
    try:
        conn.run(
            "INSERT INTO company_ratings (company_id, rater_id, score, comment) "
            "VALUES (:cid, :rid, :score, :comment) "
            "ON CONFLICT (company_id, rater_id) "
            "DO UPDATE SET score = :score, comment = :comment, updated_at = NOW()",
            cid=company_id, rid=rater_id, score=score, comment=comment)
        rt = conn.run(
            "SELECT AVG(score), COUNT(*) FROM company_ratings WHERE company_id = :cid",
            cid=company_id)
        return {
            "rating_avg":   round(float(rt[0][0]), 1) if rt and rt[0][0] is not None else None,
            "rating_count": rt[0][1] if rt else 0,
        }
    finally:
        release_conn(conn)


# ══ Phase 3: Company Posts Data Layer (Rule #5,#6 — Single Source) ══
# Pure data layer. No authorization (that lives in server.py). company_id = users.id.

def get_company_posts(company_id: int) -> list:
    """Return all posts for a company, newest first. Uses idx_posts_company."""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, body, tags, created_at FROM company_posts "
            "WHERE company_id = :cid ORDER BY created_at DESC",
            cid=company_id)
        cols = ["id", "body", "tags", "created_at"]
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)


def create_company_post(company_id: int, body: str, tags=None) -> dict:
    """Insert a post. Returns the created row. body required (non-empty)."""
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO company_posts (company_id, body, tags) "
            "VALUES (:cid, :body, :tags) RETURNING id, body, tags, created_at",
            cid=company_id, body=body, tags=(tags if tags else None))
        cols = ["id", "body", "tags", "created_at"]
        return _serialize(_row_to_dict(cols, rows[0])) if rows else {}
    finally:
        release_conn(conn)


def get_post_owner(post_id: int):
    """Return company_id (owner) of a post, or None if not found.
    Used by server.py for ownership check before delete."""
    conn = get_conn()
    try:
        rows = conn.run("SELECT company_id FROM company_posts WHERE id = :pid", pid=post_id)
        return rows[0][0] if rows else None
    finally:
        release_conn(conn)


def delete_company_post(post_id: int) -> bool:
    """Delete a post by id. Returns True if a row was deleted."""
    conn = get_conn()
    try:
        rows = conn.run("DELETE FROM company_posts WHERE id = :pid RETURNING id", pid=post_id)
        return bool(rows)
    finally:
        release_conn(conn)


# ══ Profile Follow System ══

def follow_profile(follower_id: int, followed_id: int) -> int:
    """Follow a profile (idempotent). Returns new followers_count."""
    if follower_id == followed_id:
        raise ValueError("لا يمكنك متابعة نفسك")
    conn = get_conn()
    try:
        conn.run(
            "INSERT INTO profile_follows (follower_id, followed_id) "
            "VALUES (:frid, :fdid) ON CONFLICT (follower_id, followed_id) DO NOTHING",
            frid=follower_id, fdid=followed_id)
        rows = conn.run(
            "SELECT COUNT(*) FROM profile_follows WHERE followed_id = :fdid",
            fdid=followed_id)
        return rows[0][0] if rows else 0
    finally:
        release_conn(conn)


def unfollow_profile(follower_id: int, followed_id: int) -> int:
    """Unfollow a profile (idempotent). Returns new followers_count."""
    conn = get_conn()
    try:
        conn.run(
            "DELETE FROM profile_follows WHERE follower_id = :frid AND followed_id = :fdid",
            frid=follower_id, fdid=followed_id)
        rows = conn.run(
            "SELECT COUNT(*) FROM profile_follows WHERE followed_id = :fdid",
            fdid=followed_id)
        return rows[0][0] if rows else 0
    finally:
        release_conn(conn)


def get_profile_followers_count(followed_id: int) -> int:
    """Return number of followers for a profile."""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT COUNT(*) FROM profile_follows WHERE followed_id = :fdid",
            fdid=followed_id)
        return rows[0][0] if rows else 0
    finally:
        release_conn(conn)


def is_profile_following(follower_id: int, followed_id: int) -> bool:
    """Return True if follower_id follows followed_id."""
    if follower_id == followed_id:
        return False
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT 1 FROM profile_follows WHERE follower_id = :frid AND followed_id = :fdid",
            frid=follower_id, fdid=followed_id)
        return bool(rows)
    finally:
        release_conn(conn)


# ══ Profile Views System ══

def record_profile_view(viewed_user_id: int, viewer_user_id: int) -> bool:
    """Record a profile view. 24h anti-duplicate: same viewer only counted once per 24h window.
    Returns True if a new view row was inserted, False if within 24h cooldown."""
    if viewed_user_id == viewer_user_id:
        return False
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT 1 FROM profile_views "
            "WHERE viewed_user_id = :vuid AND viewer_user_id = :viid "
            "AND viewed_at > NOW() - INTERVAL '24 hours' "
            "LIMIT 1",
            vuid=viewed_user_id, viid=viewer_user_id)
        if rows:
            return False
        conn.run(
            "INSERT INTO profile_views (viewed_user_id, viewer_user_id) VALUES (:vuid, :viid)",
            vuid=viewed_user_id, viid=viewer_user_id)
        return True
    finally:
        release_conn(conn)


def get_profile_views_count(viewed_user_id: int) -> int:
    """Return total number of unique viewers for a profile."""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT COUNT(*) FROM profile_views WHERE viewed_user_id = :vuid",
            vuid=viewed_user_id)
        return rows[0][0] if rows else 0
    finally:
        release_conn(conn)

