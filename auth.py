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

_CONN_MAX_AGE = 240  # seconds — ping only if idle longer than this

def get_conn():
    _parse_db_url()
    global _pool
    now = _time_mod.time()
    with _pool_lock:
        while _pool:
            conn, ts = _pool.pop()
            if now - ts > _CONN_MAX_AGE:
                # Connection may have been closed by Supabase idle timeout — verify
                try:
                    conn.run("SELECT 1")
                    return conn
                except Exception:
                    pass  # stale — discard, try next
            else:
                return conn  # recent enough — skip ping, save ~173ms
    return pg8000.native.Connection(**_db_params)

def release_conn(conn):
    global _pool
    now = _time_mod.time()
    with _pool_lock:
        if len(_pool) < _MAX_POOL:
            try:
                _pool.append((conn, now))
                return
            except Exception:
                pass
    try: conn.close()
    except: pass


def _ensure_async_commit(conn):
    """Set synchronous_commit=off for this session if not already done.

    Scoped to INSERT-heavy paths (send_message_pipeline).
    First call per connection = 1 RTT (~173ms). All subsequent calls = 0ms.
    Connection flag persists in the pool across reuses so the RTT is paid once.
    """
    if not getattr(conn, '_tw_async_commit', False):
        conn.run("SET synchronous_commit=off")
        conn._tw_async_commit = True


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
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS availability_status TEXT",
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

        # ── Profile Interests ──
        try:
            conn.run("""
                CREATE TABLE IF NOT EXISTS profile_interests (
                    id             BIGSERIAL PRIMARY KEY,
                    actor_user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    target_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    actor_type     TEXT NOT NULL,
                    interest_type  TEXT NOT NULL,
                    created_at     TIMESTAMPTZ DEFAULT NOW(),
                    updated_at     TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT uq_profile_interest    UNIQUE (actor_user_id, target_user_id),
                    CONSTRAINT no_self_profile_interest CHECK  (actor_user_id != target_user_id)
                )
            """)
            conn.run("CREATE INDEX IF NOT EXISTS idx_pi_actor  ON profile_interests(actor_user_id)")
            conn.run("CREATE INDEX IF NOT EXISTS idx_pi_target ON profile_interests(target_user_id)")
            conn.run("CREATE INDEX IF NOT EXISTS idx_pi_type   ON profile_interests(interest_type)")
        except Exception as _pie:
            print(f"[init_db] profile_interests setup note: {_pie}")

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
        # Delivery / read receipt columns (migration for existing tables)
        for col in [
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP NULL",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS read_at TIMESTAMP NULL",
        ]:
            try: conn.run(col)
            except: pass
        # Indexes for messages — critical for send latency and badge count
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_msg_receiver_unread ON messages(receiver_id, is_read) WHERE is_read=FALSE",
            "CREATE INDEX IF NOT EXISTS idx_msg_pair ON messages(sender_id, receiver_id)",
            "CREATE INDEX IF NOT EXISTS idx_msg_receiver ON messages(receiver_id)",
        ]:
            try: conn.run(idx_sql)
            except: pass
        # Log any triggers on messages (unexpected triggers add INSERT latency)
        try:
            trows = conn.run(
                "SELECT trigger_name, event_manipulation FROM information_schema.triggers "
                "WHERE event_object_table='messages' ORDER BY trigger_name"
            )
            if trows:
                print(f"[TW-WARN] triggers on messages table: {trows}")
            else:
                print("[TW-INFO] no triggers on messages table — clean")
        except Exception as _te:
            print(f"[TW-INFO] trigger check skipped: {_te}")
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
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS availability_status TEXT",
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

        # Self-heal: generate tw_id for legacy accounts that missed startup migration
        if not user.get("tw_id"):
            try:
                tw_id = _unique_tw_id(conn, user.get("user_type", "emp"), user.get("country_code", "DEFAULT"))
                conn.run("UPDATE users SET tw_id = :tw_id WHERE id = :uid", tw_id=tw_id, uid=user_id)
                user["tw_id"] = tw_id
                print(f"[get_public_profile] self-healed tw_id for user {user_id}: {tw_id}")
            except Exception as _e:
                print(f"[get_public_profile] tw_id self-heal failed for {user_id}: {_e}")

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


def get_user_info_by_tw_id(tw_id: str) -> Optional[dict]:
    """يرجع id, tw_id, user_type من الـ tw_id. None إذا لم يوجد.
    يُستخدم من Smart Public Router لتحديد الصفحة المناسبة."""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, tw_id, user_type FROM users WHERE tw_id = :tw_id",
            tw_id=tw_id
        )
        if not rows:
            return None
        return {'id': rows[0][0], 'tw_id': rows[0][1], 'user_type': rows[0][2]}
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

def _migrate_jobs_v2():
    """Add category, work_mode, salary_hidden, accepts_all_professions columns to jobs table (idempotent)."""
    conn = get_conn()
    try:
        conn.run("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS category VARCHAR(100)")
        conn.run("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS work_mode VARCHAR(50)")
        conn.run("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_hidden BOOLEAN DEFAULT FALSE")
        conn.run("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS accepts_all_professions BOOLEAN DEFAULT FALSE")
    finally:
        release_conn(conn)


def _migrate_taxonomy_foundation():
    """
    PR feat/taxonomy-db-foundation:
      1. Create skill_catalog table (official source for all skills).
      2. Seed ~335 skills from profile-v2.skills.js CATALOG.
      3. Add jobs.profession_id FK → profession_categories (optional).
    Idempotent — safe to run on every startup.
    """
    conn = get_conn()
    try:
        # ── 1. skill_catalog table ────────────────────────────────
        conn.run("""
            CREATE TABLE IF NOT EXISTS skill_catalog (
                id             SERIAL PRIMARY KEY,
                slug           VARCHAR(100) NOT NULL UNIQUE,
                name_en        VARCHAR(150) NOT NULL,
                name_ar        VARCHAR(150),
                keywords       TEXT DEFAULT '',
                icon           VARCHAR(60)  NOT NULL DEFAULT 'code',
                category_group VARCHAR(60),
                sort_order     SMALLINT DEFAULT 0,
                is_active      BOOLEAN DEFAULT TRUE,
                created_at     TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        try:
            conn.run("CREATE INDEX IF NOT EXISTS idx_skill_catalog_slug   ON skill_catalog(slug)")
            conn.run("CREATE INDEX IF NOT EXISTS idx_skill_catalog_group  ON skill_catalog(category_group)")
            conn.run("CREATE INDEX IF NOT EXISTS idx_skill_catalog_active ON skill_catalog(is_active)")
        except Exception: pass

        # ── 2. jobs.profession_id — guaranteed before seed ───────────
        # Must run before seed so add_job() never sees a missing column
        # even if seed fails below.
        try:
            conn.run(
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS profession_id INTEGER "
                "REFERENCES profession_categories(id) ON DELETE SET NULL"
            )
        except Exception: pass
        try:
            conn.run("CREATE INDEX IF NOT EXISTS idx_jobs_profession ON jobs(profession_id)")
        except Exception: pass

        # ── 3. Seed — all skills from profile-v2.skills.js CATALOG ─
        # Wrapped in its own try/except: seed failure must not break job posting.
        # Format per row: (slug, name_en, name_ar, keywords, icon, category_group, sort_order)
        try:
            _SKILL_SEED = [
            # ── Programming Languages (tech, 10–220) ──
            ('javascript','JavaScript','جافا سكريبت','js جافاسكريبت web','code','tech',10),
            ('python','Python','بايثون','بايثون py','code','tech',11),
            ('java','Java','جافا','جافا oop','code','tech',12),
            ('typescript','TypeScript','تايب سكريبت','ts','code','tech',13),
            ('cpp','C++','سي بلس بلس','cpp سي بلس','code','tech',14),
            ('csharp','C#','سي شارب','dotnet سي شارب','code','tech',15),
            ('php','PHP','PHP','لارافيل','code','tech',16),
            ('swift','Swift','سويفت','ios apple','code','tech',17),
            ('kotlin','Kotlin','كوتلن','android','code','tech',18),
            ('go','Go','Go','golang','code','tech',19),
            ('ruby','Ruby','روبي','rails','code','tech',20),
            ('r_lang','R','R','r language احصاء statistics','code','tech',21),
            ('dart','Dart','دارت','flutter','code','tech',22),
            ('scala','Scala','سكالا','','code','tech',23),
            ('rust','Rust','رست','','code','tech',24),
            ('matlab','MATLAB','ماتلاب','simulation محاكاة','cpu','tech',25),
            ('vba','VBA','VBA','excel macro اكسل ماكرو','code','tech',26),
            ('bash','Bash / Shell Script','باش / سكريبت','bash shell script linux','terminal','tech',27),
            ('perl','Perl','Perl','perl scripting','code','tech',28),
            ('lua','Lua','لوا','lua game','code','tech',29),
            ('solidity','Solidity','سوليديتي','blockchain web3 ethereum','code','tech',30),
            ('assembly','Assembly','أسمبلي','asm assembly low-level','cpu','tech',31),
            # ── Web Frontend ──
            ('html','HTML','HTML','html5 markup','code','tech',40),
            ('css','CSS','CSS','css3 styling','palette','tech',41),
            ('react','React','رياكت','reactjs','code','tech',42),
            ('vuejs','Vue.js','فيو','vue vuejs','code','tech',43),
            ('angular','Angular','أنغولار','angularjs','code','tech',44),
            ('nextjs','Next.js','نكست','nextjs','code','tech',45),
            ('nuxtjs','Nuxt.js','نكست فيو','nuxt','code','tech',46),
            ('bootstrap','Bootstrap','بوتستراب','css framework','palette','tech',47),
            ('tailwind','Tailwind CSS','تيلويند','tailwindcss','palette','tech',48),
            ('jquery','jQuery','jQuery','js library','code','tech',49),
            ('svelte','Svelte','سفيلت','svelte frontend','code','tech',50),
            ('redux','Redux','ريدكس','redux state management','code','tech',51),
            ('graphql','GraphQL','GraphQL','graphql api query','code','tech',52),
            ('webpack','Webpack','ويب باك','webpack bundler build','settings','tech',53),
            ('vite','Vite','فيت','vite build tool frontend','zap','tech',54),
            # ── Backend Frameworks ──
            ('nodejs','Node.js','نود','nodejs node express','server','tech',60),
            ('django','Django','دجانغو','python framework','server','tech',61),
            ('flask','Flask','فلاسك','python flask','server','tech',62),
            ('fastapi','FastAPI','FastAPI','python api','server','tech',63),
            ('laravel','Laravel','لارافيل','php','server','tech',64),
            ('springboot','Spring Boot','سبرينغ','spring java framework','server','tech',65),
            ('aspnet','ASP.NET','ASP.NET','dotnet csharp','server','tech',66),
            ('expressjs','Express.js','إكسبريس','nodejs express','server','tech',67),
            ('nestjs','NestJS','نست','nestjs nodejs typescript','server','tech',68),
            ('rails','Ruby on Rails','روبي أون ريلز','rails ruby framework','server','tech',69),
            ('rest_api','REST API','REST API','rest api web services','server','tech',70),
            # ── Mobile ──
            ('react_native','React Native','ريأكت نيتف','mobile cross platform','smartphone','tech',80),
            ('flutter','Flutter','فلاتر','dart mobile','smartphone','tech',81),
            ('android_dev','Android Development','تطوير أندرويد','android kotlin java mobile','smartphone','tech',82),
            ('ios_dev','iOS Development','تطوير iOS','ios swift apple','smartphone','tech',83),
            # ── Databases ──
            ('sql','SQL','إس كيو إل','قواعد بيانات database استعلامات','database','tech',90),
            ('mysql','MySQL','ماي إس كيو إل','mysql database','database','tech',91),
            ('postgresql','PostgreSQL','بوستغريس','postgres postgresql','database','tech',92),
            ('mongodb','MongoDB','مونغو','nosql mongodb','database','tech',93),
            ('oracle_db','Oracle Database','أوراكل','oracle plsql','database','tech',94),
            ('redis','Redis','ريديس','redis cache','database','tech',95),
            ('firebase','Firebase','فايربيز','firebase google','database','tech',96),
            ('sqlite','SQLite','إس كيو لايت','sqlite local','database','tech',97),
            ('elasticsearch','Elasticsearch','إلاستيك سيرش','elastic search','database','tech',98),
            ('mariadb','MariaDB','ماريا دي بي','mariadb mysql','database','tech',99),
            ('dynamodb','DynamoDB','دينامو دي بي','dynamodb aws nosql','database','tech',100),
            ('cassandra','Cassandra','كاساندرا','cassandra nosql','database','tech',101),
            ('supabase','Supabase','سوبابيس','supabase postgres','database','tech',102),
            # ── Cloud / DevOps ──
            ('docker','Docker','دوكر','docker containers','server','tech',110),
            ('kubernetes','Kubernetes','كوبيرنيتس','k8s orchestration','server','tech',111),
            ('aws','AWS','أمازون كلاود','amazon aws cloud','cloud','tech',112),
            ('azure','Microsoft Azure','أزور','azure microsoft cloud','cloud','tech',113),
            ('gcp','Google Cloud','جوجل كلاود','gcp google cloud','cloud','tech',114),
            ('git','Git','جيت','git github gitlab version control','git-branch','tech',115),
            ('linux','Linux','لينكس','linux ubuntu bash terminal','terminal','tech',116),
            ('cicd','CI/CD','CI/CD','devops cicd jenkins github actions','settings','tech',117),
            ('terraform','Terraform','تيرافورم','terraform iac infrastructure','layers','tech',118),
            ('nginx','Nginx','إنجينكس','nginx web server','server','tech',119),
            ('ansible','Ansible','أنسيبل','ansible automation devops','settings','tech',120),
            ('jenkins','Jenkins','جينكنز','jenkins ci pipeline','settings','tech',121),
            ('helm','Helm','هيلم','helm kubernetes charts','layers','tech',122),
            ('github_actions','GitHub Actions','GitHub Actions','github actions workflow','git-branch','tech',123),
            # ── Networking ──
            ('networking','Networking','شبكات','network ccna tcp/ip شبكات','network','tech',130),
            ('ccna','CCNA','CCNA','ccna cisco networking','router','tech',131),
            ('cisco','Cisco','سيسكو','cisco networking routers switches','router','tech',132),
            ('vpn','VPN','VPN','vpn virtual private network','wifi','tech',133),
            ('lan_wan','LAN / WAN','LAN / WAN','lan wan networking','wifi','tech',134),
            ('mikrotik','MikroTik','ميكروتيك','mikrotik router networking','router','tech',135),
            ('network_admin','Network Administration','إدارة الشبكات','network administration إدارة شبكات','network','tech',136),
            ('routing_switching','Routing & Switching','التوجيه والتبديل','routing switching cisco','router','tech',137),
            ('network_monitoring','Network Monitoring','مراقبة الشبكات','network monitoring wireshark','signal','tech',138),
            ('wireshark','Wireshark','وايرشارك','wireshark packet analysis','wifi','tech',139),
            ('voip','VoIP','VoIP','voip ip telephony','phone','tech',140),
            # ── AI / Data ──
            ('machine_learning','Machine Learning','تعلم الآلة','ml ai ذكاء اصطناعي','brain','tech',150),
            ('deep_learning','Deep Learning','التعلم العميق','dl neural network شبكات عصبية','cpu','tech',151),
            ('data_analysis','Data Analysis','تحليل البيانات','data analyst تحليل بيانات','bar-chart','tech',152),
            ('data_science','Data Science','علم البيانات','datascience علم البيانات','brain','tech',153),
            ('tensorflow','TensorFlow','تنسرفلو','google ai tensorflow','brain','tech',154),
            ('pytorch','PyTorch','بايتورش','pytorch deep learning','brain','tech',155),
            ('pandas','Pandas','باندا','python data pandas','database','tech',156),
            ('numpy','NumPy','نمباي','python math numpy','code','tech',157),
            ('powerbi','Power BI','باور بي آي','powerbi microsoft bi تحليل','bar-chart','tech',158),
            ('tableau','Tableau','تابلو','data visualization tableau','bar-chart','tech',159),
            ('nlp','NLP','معالجة اللغة الطبيعية','natural language processing nlp','brain','tech',160),
            ('computer_vision','Computer Vision','رؤية الحاسوب','computer vision image recognition','camera','tech',161),
            ('generative_ai','Generative AI','الذكاء الاصطناعي التوليدي','generative ai llm chatgpt','bot','tech',162),
            ('mlops','MLOps','MLOps','mlops machine learning operations','settings','tech',163),
            ('apache_spark','Apache Spark','أباتشي سبارك','spark big data apache','database','tech',164),
            ('hadoop','Hadoop','هادوب','hadoop big data mapreduce','database','tech',165),
            ('etl','ETL','ETL','etl extract transform load data','database','tech',166),
            ('data_warehousing','Data Warehousing','مستودعات البيانات','data warehouse dwh','hard-drive','tech',167),
            # ── Cybersecurity ──
            ('cybersecurity','Cybersecurity','الأمن السيبراني','security cyber أمن سيبراني','shield','security',10),
            ('pen_testing','Penetration Testing','اختبار الاختراق','pen test penetration اختراق','shield-check','security',11),
            ('network_security','Network Security','أمن الشبكات','network security أمن شبكات','shield','security',12),
            ('ethical_hacking','Ethical Hacking','القرصنة الأخلاقية','ethical hacking قرصنة أخلاقية','shield-check','security',13),
            ('vulnerability_assessment','Vulnerability Assessment','تقييم الثغرات','vulnerability assessment ثغرات','shield-check','security',14),
            ('siem','SIEM','SIEM','siem security information event management','shield','security',15),
            ('digital_forensics','Digital Forensics','الجنائيات الرقمية','digital forensics جنائيات رقمية','fingerprint','security',16),
            ('soc','SOC','مركز عمليات الأمن','soc security operations center','shield','security',17),
            ('malware_analysis','Malware Analysis','تحليل البرمجيات الخبيثة','malware analysis فيروسات','shield','security',18),
            ('cryptography','Cryptography','التشفير','cryptography encryption تشفير','lock','security',19),
            ('iso27001','ISO 27001','ISO 27001','iso 27001 security standard','shield','security',20),
            ('incident_response','Incident Response','الاستجابة للحوادث','incident response security','shield','security',21),
            ('osint','OSINT','استخبارات المصادر المفتوحة','osint open source intelligence','search','security',22),
            # ── Design ──
            ('photoshop','Adobe Photoshop','فوتوشوب','photoshop ps تصميم','palette','design',10),
            ('illustrator','Adobe Illustrator','إليستريتور','illustrator ai vector','pen-tool','design',11),
            ('figma','Figma','فيغما','figma ui prototype تصميم','pen-tool','design',12),
            ('xd','Adobe XD','أدوبي XD','xd ux wireframe','pen-tool','design',13),
            ('premiere','Adobe Premiere','بريمير','premiere video editing تحرير فيديو','video','design',14),
            ('aftereffects','Adobe After Effects','أفتر إفيكتس','after effects motion animation','video','design',15),
            ('ui_design','UI Design','تصميم الواجهات','ui user interface تصميم','monitor','design',16),
            ('ux_design','UX Design','تجربة المستخدم','ux user experience usability','users','design',17),
            ('graphic_design','Graphic Design','تصميم جرافيك','graphic جرافيك design','palette','design',18),
            ('autocad','AutoCAD','أوتوكاد','autocad cad هندسة','hard-hat','design',19),
            ('three_d','3D Modeling','نمذجة ثلاثية الأبعاد','3d blender modeling','layers','design',20),
            ('motion_graphics','Motion Graphics','موشن جرافيك','motion graphics animation موشن','video','design',21),
            ('logo_design','Logo Design','تصميم الشعارات','logo design شعار','pen-tool','design',22),
            ('brand_identity','Brand Identity','الهوية البصرية','brand identity هوية بصرية','award','design',23),
            ('canva','Canva','كانفا','canva design تصميم','palette','design',24),
            ('davinci','DaVinci Resolve','دافنشي','davinci video editing montage','video','design',25),
            ('indesign','Adobe InDesign','إن ديزاين','indesign print layout','pen-tool','design',26),
            ('sketch_design','Sketch','سكتش','sketch ui design mac','pen-tool','design',27),
            ('social_media_design','Social Media Design','تصميم السوشيال ميديا','social media design post','palette','design',28),
            # ── Office / Productivity ──
            ('excel','Microsoft Excel','إكسل','excel spreadsheet جداول بيانات','bar-chart','office',10),
            ('word','Microsoft Word','وورد','word document وورد','file-text','office',11),
            ('powerpoint','Microsoft PowerPoint','باوربوينت','powerpoint presentation عروض','monitor','office',12),
            ('access','Microsoft Access','أكسس','access microsoft','database','office',13),
            ('ms_office','Microsoft Office','مايكروسوفت أوفيس','office أوفيس','briefcase','office',14),
            ('google_sheets','Google Sheets','جوجل شيتس','sheets google docs','bar-chart','office',15),
            ('google_workspace','Google Workspace','جوجل ورك سبيس','google drive gmail docs','briefcase','office',16),
            ('data_entry','Data Entry','إدخال البيانات','data entry إدخال بيانات typing','file-text','office',17),
            ('jira','Jira','جيرا','jira project management agile','briefcase','office',18),
            ('trello','Trello','تريلو','trello kanban project','briefcase','office',19),
            ('notion','Notion','نوشن','notion workspace productivity','file-text','office',20),
            # ── Management / Soft Skills ──
            ('project_management','Project Management','إدارة المشاريع','pm pmp إدارة مشاريع','clipboard','management',10),
            ('agile','Agile / Scrum','أجايل / سكرام','agile scrum sprint kanban','settings','management',11),
            ('team_leadership','Team Leadership','قيادة الفريق','leadership قيادة فريق','users','management',12),
            ('communication','Communication Skills','مهارات التواصل','communication تواصل presentation','messages-square','management',13),
            ('problem_solving','Problem Solving','حل المشكلات','problem solving analytical تحليل','layers','management',14),
            ('time_management','Time Management','إدارة الوقت','time management productivity وقت','clock','management',15),
            ('critical_thinking','Critical Thinking','التفكير النقدي','critical thinking تفكير نقدي','brain','management',16),
            ('strategic_planning','Strategic Planning','التخطيط الاستراتيجي','strategic planning تخطيط استراتيجي','clipboard','management',17),
            ('operations_mgmt','Operations Management','إدارة العمليات','operations management عمليات','settings','management',18),
            ('change_management','Change Management','إدارة التغيير','change management تغيير','clock','management',19),
            ('business_analysis','Business Analysis','تحليل الأعمال','business analysis تحليل أعمال','briefcase','management',20),
            ('business_dev','Business Development','تطوير الأعمال','business development تطوير','trending-up','management',21),
            ('okr','OKR','OKR','okr goals objectives','target','management',22),
            ('kpi','KPIs','مؤشرات الأداء','kpi performance indicators أداء','bar-chart','management',23),
            ('process_improvement','Process Improvement','تحسين العمليات','process improvement lean','settings','management',24),
            ('emotional_intelligence','Emotional Intelligence','الذكاء العاطفي','emotional intelligence ذكاء عاطفي eq','heart','management',25),
            ('adaptability','Adaptability','القدرة على التكيف','adaptability flexibility تكيف','activity','management',26),
            ('creativity','Creativity','الإبداع','creativity innovation إبداع ابتكار','palette','management',27),
            ('teamwork','Teamwork','العمل الجماعي','teamwork collaboration عمل فريق','users','management',28),
            ('presentation_skills','Presentation Skills','مهارات العرض والتقديم','presentation skills عرض تقديم','monitor','management',29),
            ('writing_skills','Writing Skills','مهارات الكتابة','writing skills كتابة','file-text','management',30),
            ('active_listening','Active Listening','الاستماع الفعال','active listening استماع','headset','management',31),
            ('conflict_resolution','Conflict Resolution','حل النزاعات','conflict resolution نزاع','messages-square','management',32),
            ('decision_making','Decision Making','صنع القرار','decision making قرار','compass','management',33),
            ('research_skills','Research Skills','مهارات البحث','research skills بحث','search','management',34),
            # ── Marketing ──
            ('marketing','Marketing','تسويق','marketing digital تسويق رقمي','megaphone','marketing',10),
            ('seo','SEO','تحسين محركات البحث','seo search engine تحسين','search','marketing',11),
            ('social_media','Social Media Marketing','تسويق التواصل الاجتماعي','social media instagram twitter تواصل','megaphone','marketing',12),
            ('content_writing','Content Writing','كتابة المحتوى','content copywriting كتابة محتوى','file-text','marketing',13),
            ('email_marketing','Email Marketing','تسويق البريد الإلكتروني','email marketing newsletter','mail','marketing',14),
            ('google_ads','Google Ads','إعلانات جوجل','google ads ppc sem','target','marketing',15),
            ('facebook_ads','Facebook Ads','إعلانات فيسبوك','facebook ads meta social','target','marketing',16),
            ('google_analytics','Google Analytics','جوجل أناليتيكس','google analytics tracking','bar-chart','marketing',17),
            ('brand_management','Brand Management','إدارة العلامات التجارية','brand management علامة تجارية','award','marketing',18),
            ('market_research','Market Research','بحث السوق','market research بحث سوق','search','marketing',19),
            ('public_relations','Public Relations','العلاقات العامة','pr public relations علاقات عامة','share-2','marketing',20),
            ('influencer_mkt','Influencer Marketing','التسويق عبر المؤثرين','influencer marketing مؤثرين','megaphone','marketing',21),
            ('affiliate_mkt','Affiliate Marketing','التسويق بالعمولة','affiliate marketing عمولة','trending-up','marketing',22),
            ('hubspot','HubSpot','هب سبوت','hubspot crm marketing','users','marketing',23),
            ('crm_tools','CRM','إدارة علاقات العملاء','crm salesforce hubspot','users','marketing',24),
            ('salesforce','Salesforce','سيلز فورس','salesforce crm sales','users','marketing',25),
            # ── Sales ──
            ('sales','Sales','المبيعات','sales selling مبيعات','trending-up','marketing',30),
            ('b2b_sales','B2B Sales','مبيعات B2B','b2b sales business','briefcase','marketing',31),
            ('b2c_sales','B2C Sales','مبيعات B2C','b2c sales consumer retail','briefcase','marketing',32),
            ('negotiation','Negotiation','التفاوض','negotiation تفاوض مفاوضة','messages-square','marketing',33),
            ('cold_calling','Cold Calling','المكالمات الباردة','cold calling telemarketing','phone','marketing',34),
            ('sales_strategy','Sales Strategy','استراتيجية المبيعات','sales strategy خطة مبيعات','target','marketing',35),
            ('retail_sales','Retail Sales','مبيعات التجزئة','retail sales تجزئة','shopping-cart','marketing',36),
            ('telesales','Telesales','مبيعات هاتفية','telesales phone sales','phone','marketing',37),
            ('account_management','Account Management','إدارة الحسابات','account management key accounts','users','marketing',38),
            # ── Accounting & Finance ──
            ('accounting','Accounting','محاسبة','accounting محاسبة ميزانية','calculator','finance',10),
            ('financial_analysis','Financial Analysis','تحليل مالي','finance financial مالي','trending-up','finance',11),
            ('bookkeeping','Bookkeeping','مسك الدفاتر','bookkeeping دفاتر محاسبة','file-text','finance',12),
            ('ifrs','IFRS','المعايير الدولية للتقارير المالية','ifrs international financial reporting','file-text','finance',13),
            ('quickbooks','QuickBooks','كويك بوكس','quickbooks accounting software','briefcase','finance',14),
            ('sap_finance','SAP Finance','ساب مالية','sap fi finance erp','briefcase','finance',15),
            ('tax_accounting','Tax Accounting','المحاسبة الضريبية','tax accounting ضريبة','calculator','finance',16),
            ('payroll','Payroll','كشوف الرواتب','payroll رواتب','calculator','finance',17),
            ('financial_reporting','Financial Reporting','إعداد التقارير المالية','financial reporting تقارير مالية','file-text','finance',18),
            ('budgeting','Budgeting','إعداد الميزانيات','budgeting ميزانية','calculator','finance',19),
            ('cost_accounting','Cost Accounting','محاسبة التكاليف','cost accounting تكاليف','calculator','finance',20),
            ('auditing','Auditing','التدقيق المحاسبي','auditing تدقيق مراجعة','file-text','finance',21),
            ('investment_analysis','Investment Analysis','تحليل الاستثمار','investment analysis استثمار','trending-up','finance',22),
            ('risk_management','Risk Management','إدارة المخاطر','risk management مخاطر','shield','finance',23),
            ('financial_planning','Financial Planning','التخطيط المالي','financial planning تخطيط مالي','trending-up','finance',24),
            # ── Human Resources ──
            ('hr','Human Resources','الموارد البشرية','hr human resources موارد بشرية','users','hr',10),
            ('talent_acquisition','Talent Acquisition','استقطاب المواهب','talent acquisition recruitment استقطاب','users','hr',11),
            ('performance_mgmt','Performance Management','إدارة الأداء','performance management أداء','bar-chart','hr',12),
            ('training_dev','Training & Development','التدريب والتطوير','training development تدريب تطوير','graduation-cap','hr',13),
            ('employee_relations','Employee Relations','علاقات الموظفين','employee relations علاقات','users','hr',14),
            ('compensation','Compensation & Benefits','التعويضات والمزايا','compensation benefits مزايا','calculator','hr',15),
            ('onboarding','Onboarding','تأهيل الموظفين','onboarding تأهيل','users','hr',16),
            ('labor_law','Labor Law','قانون العمل','labor law قانون عمل','file-text','hr',17),
            ('hris','HRIS','نظام معلومات الموارد البشرية','hris hr system موارد بشرية نظام','database','hr',18),
            ('hr_analytics','HR Analytics','تحليلات الموارد البشرية','hr analytics تحليل موارد','bar-chart','hr',19),
            # ── Education & Training ──
            ('curriculum_design','Curriculum Design','تصميم المناهج','curriculum design مناهج','graduation-cap','education',10),
            ('elearning','E-Learning','التعليم الإلكتروني','elearning online learning تعلم إلكتروني','monitor','education',11),
            ('instructional_design','Instructional Design','التصميم التعليمي','instructional design تصميم تعليمي','graduation-cap','education',12),
            ('lms','LMS','نظام إدارة التعلم','lms learning management system moodle','monitor','education',13),
            ('coaching','Coaching','الكوتشينج','coaching personal development كوتشينج','users','education',14),
            ('mentoring','Mentoring','التوجيه والإرشاد','mentoring coaching توجيه','users','education',15),
            ('toefl_ielts','TOEFL / IELTS','TOEFL / IELTS','toefl ielts english exam','award','education',16),
            ('edu_technology','Educational Technology','تكنولوجيا التعليم','edtech educational technology','monitor','education',17),
            ('classroom_mgmt','Classroom Management','إدارة الفصل الدراسي','classroom management فصل دراسي','graduation-cap','education',18),
            # ── Engineering ──
            ('solidworks','SolidWorks','سوليدووركس','solidworks cad 3d design','hard-hat','engineering',10),
            ('revit','Revit','ريفيت','revit bim architecture','hard-hat','engineering',11),
            ('catia','CATIA','كاتيا','catia cad automotive','hard-hat','engineering',12),
            ('bim','BIM','نمذجة معلومات البناء','bim building information modeling','hard-hat','engineering',13),
            ('structural_analysis','Structural Analysis','التحليل الإنشائي','structural analysis engineering تحليل إنشائي','hard-hat','engineering',14),
            ('plc','PLC Programming','برمجة PLC','plc programming automation','cpu','engineering',15),
            ('scada','SCADA','SCADA','scada control systems automation','cpu','engineering',16),
            ('six_sigma','Six Sigma','ستة سيجما','six sigma quality lean','settings','engineering',17),
            ('lean_manufacturing','Lean Manufacturing','التصنيع الرشيق','lean manufacturing kaizen','settings','engineering',18),
            ('quality_control','Quality Control','ضبط الجودة','quality control qc جودة','settings','engineering',19),
            ('hse','HSE / Safety','الصحة والسلامة والبيئة','hse health safety environment سلامة','shield','engineering',20),
            ('sap_pm','SAP PM','ساب صيانة','sap pm plant maintenance erp','briefcase','engineering',21),
            # ── Medical & Nursing ──
            ('patient_care','Patient Care','رعاية المرضى','patient care رعاية مرضى','stethoscope','health',10),
            ('clinical_skills','Clinical Skills','المهارات السريرية','clinical skills سريري','stethoscope','health',11),
            ('emr','EMR / EHR','السجلات الطبية الإلكترونية','emr ehr electronic medical records','hospital','health',12),
            ('medical_coding','Medical Coding','الترميز الطبي','medical coding icd billing','file-text','health',13),
            ('cpr','CPR / First Aid','الإسعافات الأولية','cpr first aid إسعافات','heart-pulse','health',14),
            ('phlebotomy','Phlebotomy','سحب الدم','phlebotomy blood draw','syringe','health',15),
            ('medical_lab','Medical Laboratory','المختبر الطبي','medical laboratory مختبر','hospital','health',16),
            ('radiology','Radiology','الأشعة','radiology imaging أشعة','scan','health',17),
            ('pharmacy_skills','Pharmacy','الصيدلة','pharmacy dispensing صيدلة','pill','health',18),
            ('healthcare_admin','Healthcare Administration','إدارة الرعاية الصحية','healthcare administration رعاية صحية','hospital','health',19),
            ('infection_control','Infection Control','مكافحة العدوى','infection control prevention عدوى','shield','health',20),
            # ── Crafts & Technical Trades ──
            ('electrical_installation','Electrical Installation','التركيبات الكهربائية','electrical installation كهرباء تركيب','zap','trades',10),
            ('plumbing_craft','Plumbing','السباكة','plumbing سباكة','wrench','trades',11),
            ('carpentry','Carpentry','النجارة','carpentry woodwork نجارة','hammer','trades',12),
            ('hvac','HVAC / Air Conditioning','تكييف الهواء','hvac ac air conditioning تكييف','wind','trades',13),
            ('welding','Welding','اللحام','welding لحام','flame','trades',14),
            ('auto_mechanics','Auto Mechanics','ميكانيكا السيارات','auto mechanics ميكانيكا سيارات','wrench','trades',15),
            ('painting_craft','Painting & Finishing','الدهان','painting دهان','paint-bucket','trades',16),
            ('tiling','Tiling','التبليط والسيراميك','tiling بلاط سيراميك','layers','trades',17),
            ('cctv','CCTV Installation','تركيب كاميرات المراقبة','cctv surveillance cameras مراقبة','camera','trades',18),
            ('alarm_systems','Alarm Systems','أنظمة الإنذار','alarm systems إنذار حماية','lock','trades',19),
            ('fiber_optic','Fiber Optic','الألياف البصرية','fiber optic networking ألياف بصرية','cable','trades',20),
            # ── Hospitality / Restaurants ──
            ('food_service','Food Service','خدمة الطعام','food service طعام خدمة','utensils','hospitality',10),
            ('hotel_management','Hotel Management','إدارة الفندق','hotel management فندق','hotel','hospitality',11),
            ('hospitality','Hospitality','الضيافة','hospitality ضيافة','building-2','hospitality',12),
            ('kitchen_management','Kitchen Management','إدارة المطبخ','kitchen chef cooking مطبخ','chef-hat','hospitality',13),
            ('food_safety','Food Safety / HACCP','سلامة الغذاء','food safety haccp سلامة غذاء','shield','hospitality',14),
            ('pos_systems','POS Systems','أنظمة نقاط البيع','pos point of sale نقطة بيع','shopping-cart','hospitality',15),
            ('event_management','Event Management','إدارة الفعاليات','event management فعاليات','calendar','hospitality',16),
            ('bartending','Bartending','بارتندر','bartending drinks bar','utensils','hospitality',17),
            ('catering','Catering','خدمات الضيافة والتموين','catering تموين ضيافة','utensils','hospitality',18),
            # ── Logistics & Supply Chain ──
            ('supply_chain','Supply Chain Management','إدارة سلسلة التوريد','supply chain سلسلة توريد','truck','logistics',10),
            ('inventory_management','Inventory Management','إدارة المخزون','inventory management مخزون','warehouse','logistics',11),
            ('warehouse_management','Warehouse Management','إدارة المستودعات','warehouse management مستودعات','warehouse','logistics',12),
            ('shipping','Shipping & Freight','الشحن والنقل','shipping freight شحن','ship','logistics',13),
            ('customs','Customs & Clearance','الجمارك والتخليص','customs clearance جمارك','clipboard','logistics',14),
            ('fleet_management','Fleet Management','إدارة الأسطول','fleet management أسطول','car','logistics',15),
            ('demand_planning','Demand Planning','تخطيط الطلب','demand planning forecasting','bar-chart','logistics',16),
            ('erp','ERP Systems','أنظمة ERP','erp enterprise resource planning','briefcase','logistics',17),
            ('sap_mm','SAP MM','ساب مشتريات','sap mm materials management erp','briefcase','logistics',18),
            # ── Customer Service ──
            ('customer_service','Customer Service','خدمة العملاء','customer service support خدمة عملاء','headset','customer_service',10),
            ('technical_support','Technical Support','الدعم الفني','technical support دعم فني','headset','customer_service',11),
            ('help_desk','Help Desk','مكتب المساعدة','help desk support helpdesk','headset','customer_service',12),
            ('call_center','Call Center','مركز الاتصال','call center مركز اتصال','phone','customer_service',13),
            ('complaint_handling','Complaint Handling','معالجة الشكاوى','complaint handling شكاوى','inbox','customer_service',14),
            ('zendesk','Zendesk','زن ديسك','zendesk support crm','headset','customer_service',15),
            ('after_sales','After-Sales Service','خدمة ما بعد البيع','after sales service ما بعد البيع','headset','customer_service',16),
            # ── Human Languages ──
            ('arabic_lang','Arabic Language','اللغة العربية','arabic language عربي','languages','languages',10),
            ('english_lang','English Language','اللغة الإنجليزية','english language إنجليزي','languages','languages',11),
            ('french_lang','French Language','اللغة الفرنسية','french français فرنسي','languages','languages',12),
            ('german_lang','German Language','اللغة الألمانية','german deutsch ألماني','languages','languages',13),
            ('spanish_lang','Spanish Language','اللغة الإسبانية','spanish español إسباني','languages','languages',14),
            ('chinese_lang','Chinese Language','اللغة الصينية','chinese mandarin صيني','languages','languages',15),
            ('turkish_lang','Turkish Language','اللغة التركية','turkish türkçe تركي','languages','languages',16),
            ('italian_lang','Italian Language','اللغة الإيطالية','italian italiano إيطالي','languages','languages',17),
            ('korean_lang','Korean Language','اللغة الكورية','korean 한국어 كوري','languages','languages',18),
            ('japanese_lang','Japanese Language','اللغة اليابانية','japanese 日本語 ياباني','languages','languages',19),
            ('russian_lang','Russian Language','اللغة الروسية','russian روسي','languages','languages',20),
            ('portuguese_lang','Portuguese Language','اللغة البرتغالية','portuguese برتغالي','languages','languages',21),
            ('persian_lang','Persian Language','اللغة الفارسية','persian farsi فارسي','languages','languages',22),
            ('arabic_typing','Arabic Typing','طباعة عربية','arabic typing طباعة عربية','type','languages',23),
            ('translation','Translation','ترجمة','translation ترجمة english arabic','globe','languages',24),
            ('technical_writing','Technical Writing','الكتابة التقنية','technical writing documentation توثيق','file-text','languages',25),
        ]

            # Insert in batches to stay under param limits
            BATCH = 50
            for i in range(0, len(_SKILL_SEED), BATCH):
                batch = _SKILL_SEED[i:i+BATCH]
                placeholders = ','.join(
                    f"(:s{j},:en{j},:ar{j},:kw{j},:ic{j},:cg{j},:so{j})"
                    for j in range(len(batch))
                )
                params = {}
                for j, row in enumerate(batch):
                    params[f's{j}']  = row[0]
                    params[f'en{j}'] = row[1]
                    params[f'ar{j}'] = row[2]
                    params[f'kw{j}'] = row[3]
                    params[f'ic{j}'] = row[4]
                    params[f'cg{j}'] = row[5]
                    params[f'so{j}'] = row[6]
                conn.run(
                    f"INSERT INTO skill_catalog (slug,name_en,name_ar,keywords,icon,category_group,sort_order) "
                    f"VALUES {placeholders} ON CONFLICT (slug) DO NOTHING",
                    **params
                )
        except Exception: pass  # seed failure must not break startup

    finally:
        release_conn(conn)


def _migrate_job_profession_targets():
    """Create job_profession_targets table for many-to-many job ↔ profession targeting."""
    conn = get_conn()
    try:
        conn.run("""
            CREATE TABLE IF NOT EXISTS job_profession_targets (
                id            SERIAL PRIMARY KEY,
                job_id        INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                profession_id INTEGER NOT NULL REFERENCES profession_categories(id) ON DELETE CASCADE,
                display_order SMALLINT DEFAULT 0,
                created_at    TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(job_id, profession_id)
            )
        """)
        try:
            conn.run("CREATE INDEX IF NOT EXISTS idx_jpt_job_id ON job_profession_targets(job_id)")
        except Exception:
            pass
    except Exception:
        pass
    finally:
        release_conn(conn)


def _fetch_accepted_professions_batch(conn, job_ids):
    """Batch-fetch accepted professions for a list of job IDs.
    Returns {job_id: [{"id": int, "name_ar": str, "name_en": str, "icon": str}]}.
    Never raises — returns {} on any error.
    """
    if not job_ids:
        return {}
    try:
        placeholders = ','.join(f':j{i}' for i in range(len(job_ids)))
        params = {f'j{i}': jid for i, jid in enumerate(job_ids)}
        rows = conn.run(
            f"SELECT jpt.job_id, pc.id, pc.name_ar, pc.name_en, pc.icon "
            f"FROM job_profession_targets jpt "
            f"JOIN profession_categories pc ON jpt.profession_id = pc.id "
            f"WHERE jpt.job_id IN ({placeholders}) "
            f"ORDER BY jpt.job_id, jpt.display_order",
            **params
        )
        result = {}
        for row in (rows or []):
            jid, pid, name_ar, name_en, icon = row
            if jid not in result:
                result[jid] = []
            result[jid].append({
                "id": pid,
                "name_ar": name_ar or "",
                "name_en": name_en or "",
                "icon": icon or "",
            })
        return result
    except Exception:
        return {}


def _fetch_applicant_counts_batch(conn, job_ids):
    """Batch-fetch job_applications counts for a list of job IDs.
    Returns {job_id: int}. Never raises — returns {} on any error.
    """
    if not job_ids:
        return {}
    try:
        placeholders = ','.join(f':j{i}' for i in range(len(job_ids)))
        params = {f'j{i}': jid for i, jid in enumerate(job_ids)}
        rows = conn.run(
            f"SELECT job_id, COUNT(*) AS cnt FROM job_applications "
            f"WHERE job_id IN ({placeholders}) GROUP BY job_id",
            **params
        )
        return {r[0]: int(r[1]) for r in (rows or [])}
    except Exception:
        return {}


def _validate_accepted_profession_ids(conn, primary_pid, accepted_ids):
    """Validate accepted_profession_ids before any DB mutation.

    Rules (server-enforced):
      - None / [] → return []
      - Must be a list; each element must be castable to int
      - Deduplicate (preserve first-occurrence order)
      - Max 5 entries
      - primary_pid must NOT appear in the list
      - Every ID must exist in profession_categories WITH is_active = true

    Returns clean List[int] or raises ValueError with a descriptive message.
    """
    if not accepted_ids:
        return []

    if not isinstance(accepted_ids, (list, tuple)):
        raise ValueError("accepted_profession_ids must be a list of integers")

    try:
        as_ints = [int(x) for x in accepted_ids]
    except (ValueError, TypeError):
        raise ValueError("accepted_profession_ids must contain integers only")

    # Deduplicate preserving first-occurrence order
    seen = set()
    deduped = []
    for pid in as_ints:
        if pid not in seen:
            seen.add(pid)
            deduped.append(pid)

    if len(deduped) > 5:
        raise ValueError(
            f"accepted_profession_ids: maximum 5 entries allowed, received {len(deduped)}"
        )

    if primary_pid and int(primary_pid) in seen:
        raise ValueError(
            f"accepted_profession_ids must not include the primary profession_id ({primary_pid})"
        )

    # Batch-verify all IDs exist and are active in profession_categories
    placeholders = ','.join(f':p{i}' for i in range(len(deduped)))
    params = {f'p{i}': pid for i, pid in enumerate(deduped)}
    rows = conn.run(
        f"SELECT id FROM profession_categories WHERE id IN ({placeholders}) AND is_active = true",
        **params
    )
    valid_ids = {row[0] for row in (rows or [])}
    invalid = [pid for pid in deduped if pid not in valid_ids]
    if invalid:
        raise ValueError(
            f"accepted_profession_ids contains invalid or inactive profession IDs: {invalid}"
        )

    return deduped


def add_job(company_id: int, data: dict) -> dict:
    _cache_del('jobs:')
    conn = get_conn()
    try:
        skills      = data.get("skills") or []
        sal_hidden  = bool(data.get("salary_hidden", False))
        prof_id     = data.get("profession_id") or None
        accepts_all = bool(data.get("accepts_all_professions") or False)

        # Validate accepted_profession_ids BEFORE any mutation — fail fast
        # When accepts_all_professions=True, individual targets are cleared (empty list)
        raw_accepted = [] if accepts_all else (data.get("accepted_profession_ids") or [])
        accepted_pids = _validate_accepted_profession_ids(conn, prof_id, raw_accepted)

        rows = conn.run(
            "INSERT INTO jobs (company_id, title, description, location, job_type, "
            "salary_min, salary_max, currency, experience_years, skills, status, "
            "category, work_mode, salary_hidden, profession_id, accepts_all_professions) "
            "VALUES (:cid, :title, :desc, :loc, :jtype, :smin, :smax, :cur, :exp, "
            ":skills, 'active', :cat, :wmode, :shide, :profid, :accall) "
            "RETURNING id, company_id, title, description, location, job_type, "
            "salary_min, salary_max, currency, experience_years, skills, status, created_at, "
            "category, work_mode, salary_hidden, profession_id, accepts_all_professions",
            cid=company_id, title=data.get("title",""),
            desc=data.get("description",""), loc=data.get("location",""),
            jtype=data.get("job_type","دوام كامل"),
            smin=None if sal_hidden else data.get("salary_min"),
            smax=None if sal_hidden else data.get("salary_max"),
            cur=data.get("currency","USD"),
            exp=data.get("experience_years",0),
            skills=skills if skills else None,
            cat=data.get("category"),
            wmode=data.get("work_mode","في الموقع"),
            shide=sal_hidden,
            profid=prof_id,
            accall=accepts_all,
        )
        cols = [c["name"] for c in conn.columns]
        result = _serialize(_row_to_dict(cols, rows[0]))

        # Save accepted professions — skipped when accepts_all_professions=True
        if accepted_pids:
            job_id = result["id"]
            for i, pid in enumerate(accepted_pids):
                conn.run(
                    "INSERT INTO job_profession_targets (job_id, profession_id, display_order) "
                    "VALUES (:jid, :pid, :ord)",
                    jid=job_id, pid=pid, ord=i
                )
            result["accepted_professions"] = _fetch_accepted_professions_batch(conn, [job_id]).get(job_id, [])
        else:
            result["accepted_professions"] = []
        return result
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
            f"COALESCE(j.accepts_all_professions, false) AS accepts_all_professions, "
            f"u.full_name AS company_name "
            f"FROM jobs j JOIN users u ON u.id=j.company_id "
            f"{where} ORDER BY j.created_at DESC LIMIT 50",
            **params
        )
        cols = [c["name"] for c in conn.columns]
        result = [_serialize(_row_to_dict(cols, r)) for r in rows]
        # Attach accepted_professions + applicant_count — single batch query each, no N+1
        job_ids = [d["id"] for d in result if d.get("id")]
        acc_map = _fetch_accepted_professions_batch(conn, job_ids)
        cnt_map = _fetch_applicant_counts_batch(conn, job_ids)
        for d in result:
            d["accepted_professions"] = acc_map.get(d["id"], [])
            d["applicant_count"] = cnt_map.get(d["id"], 0)
        _cache_set(cache_key, result)
        return result
    finally:
        release_conn(conn)

def get_job(job_id: int) -> dict:
    conn = get_conn()
    try:
        conn.run("UPDATE jobs SET views=views+1 WHERE id=:id", id=job_id)
        rows = conn.run(
            "SELECT j.*, "
            "u.full_name AS company_name, u.tw_id AS company_tw_id, "
            "COALESCE(cp.avatar_url,'') AS company_logo, "
            "COALESCE(cp.is_verified,false) AS company_verified, "
            "COALESCE(pc.name_ar,'') AS profession_name_ar, "
            "COALESCE(pc.name_en,'') AS profession_name_en, "
            "COALESCE(pc.icon,'') AS profession_icon, "
            "COALESCE(pc.category_group,'') AS profession_category_group "
            "FROM jobs j "
            "JOIN users u ON u.id=j.company_id "
            "LEFT JOIN profiles cp ON j.company_id=cp.user_id "
            "LEFT JOIN profession_categories pc ON j.profession_id=pc.id "
            "WHERE j.id=:id", id=job_id
        )
        if not rows: return None
        cols = [c["name"] for c in conn.columns]
        result = _serialize(_row_to_dict(cols, rows[0]))
        result["accepted_professions"] = _fetch_accepted_professions_batch(conn, [job_id]).get(job_id, [])
        return result
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

def get_job_applicants(job_id: int, company_id: int = 0) -> list:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT ja.id, ja.job_id, ja.user_id, ja.status, ja.cover_letter, ja.applied_at, "
            "u.full_name, u.user_type, u.tw_id, "
            "CASE WHEN sc.candidate_id IS NOT NULL THEN true ELSE false END AS is_saved "
            "FROM job_applications ja "
            "JOIN users u ON u.id=ja.user_id "
            "LEFT JOIN company_saved_candidates sc "
            "  ON sc.company_id=:cid AND sc.candidate_id=ja.user_id "
            "WHERE ja.job_id=:jid ORDER BY ja.applied_at DESC",
            jid=job_id, cid=company_id
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
            "j.title, j.location, j.company_id, "
            "u.full_name AS company_name, u.tw_id AS company_tw_id "
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

def get_company_jobs_all(company_id: int) -> list:
    """Return all jobs for the authenticated owner — all statuses, no cache."""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT j.id, j.company_id, j.title, j.description, j.location, "
            "j.job_type, j.salary_min, j.salary_max, j.currency, "
            "j.experience_years, j.skills, j.status, j.views, j.created_at, "
            "COALESCE(j.accepts_all_professions, false) AS accepts_all_professions, "
            "u.full_name AS company_name "
            "FROM jobs j JOIN users u ON u.id=j.company_id "
            "WHERE j.company_id=:cid ORDER BY j.created_at DESC LIMIT 100",
            cid=company_id
        )
        cols = [c["name"] for c in conn.columns]
        result = [_serialize(_row_to_dict(cols, r)) for r in rows]
        job_ids = [d["id"] for d in result if d.get("id")]
        acc_map = _fetch_accepted_professions_batch(conn, job_ids)
        cnt_map = _fetch_applicant_counts_batch(conn, job_ids)
        for d in result:
            d["accepted_professions"] = acc_map.get(d["id"], [])
            d["applicant_count"]      = cnt_map.get(d["id"], 0)
        return result
    finally:
        release_conn(conn)

def set_job_status(job_id: int, company_id: int, status: str) -> None:
    _ALLOWED = ('active', 'paused', 'closed')
    if status not in _ALLOWED:
        raise ValueError(f"Invalid status '{status}'. Allowed: {_ALLOWED}")
    conn = get_conn()
    try:
        conn.run(
            "UPDATE jobs SET status=:s WHERE id=:id AND company_id=:cid",
            s=status, id=job_id, cid=company_id
        )
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

def mark_message_read_immediate(msg_id: int):
    """Mark a message as read immediately when receiver has the conversation open."""
    conn = get_conn()
    try:
        conn.run(
            "UPDATE messages SET is_read=TRUE, read_at=NOW(), "
            "delivered_at=COALESCE(delivered_at, NOW()) WHERE id=:id",
            id=msg_id
        )
    finally:
        release_conn(conn)

def send_message(sender_id: int, receiver_id: int, content: str) -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO messages (sender_id, receiver_id, content) "
            "VALUES (:sid, :rid, :content) "
            "RETURNING id, sender_id, receiver_id, content, is_read, delivered_at, read_at, created_at",
            sid=sender_id, rid=receiver_id, content=content
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)


def send_message_pipeline(sender_id: int, receiver_id: int, content: str, mark_as_read: bool) -> tuple:
    """Single-connection send pipeline — two optimised paths:

    Hot  (mark_as_read=True):  1 query  — INSERT already-read (no UPDATE, no COUNT).
                                Returns (msg, None, timing). Caller skips badge update.
    Cold (mark_as_read=False): 2 queries — INSERT unread + COUNT for badge.
                                Returns (msg, unread_count, timing). Badge pushed in background.

    One DB connection, one SELECT 1 ping regardless of path.
    """
    t0 = _time_mod.perf_counter()
    conn = get_conn()
    t_after_conn = _time_mod.perf_counter()
    try:
        # SET synchronous_commit=off: 1 RTT on first use of this connection, 0ms after.
        _ensure_async_commit(conn)
        t_after_set = _time_mod.perf_counter()

        if mark_as_read:
            # Save message as already delivered+read in one INSERT — no UPDATE needed
            rows = conn.run(
                "INSERT INTO messages (sender_id, receiver_id, content, is_read, delivered_at, read_at) "
                "VALUES (:sid, :rid, :content, TRUE, NOW(), NOW()) "
                "RETURNING id, sender_id, receiver_id, content, is_read, delivered_at, read_at, created_at",
                sid=sender_id, rid=receiver_id, content=content
            )
            cols = [c["name"] for c in conn.columns]
            msg = _serialize(_row_to_dict(cols, rows[0]))
            t_after_insert = _time_mod.perf_counter()
            msg["delivered_at"] = True
            msg["read_at"] = True
            timing = {
                "conn_ms":        round((t_after_conn   - t0)            * 1000),
                "sync_set_ms":    round((t_after_set    - t_after_conn)   * 1000),
                "insert_exec_ms": round((t_after_insert - t_after_set)    * 1000),
                "insert_ms":      round((t_after_insert - t_after_conn)   * 1000),
                "update_ms": 0,   # skipped — inserted as read directly
                "count_ms":  0,   # skipped — badge unchanged when receiver is reading
                "db_ms":     round((t_after_insert - t0) * 1000),
            }
            return msg, None, timing  # None = badge update not needed

        else:
            # Cold path: save unread, then count for badge (2 queries, 1 connection)
            rows = conn.run(
                "INSERT INTO messages (sender_id, receiver_id, content) "
                "VALUES (:sid, :rid, :content) "
                "RETURNING id, sender_id, receiver_id, content, is_read, delivered_at, read_at, created_at",
                sid=sender_id, rid=receiver_id, content=content
            )
            cols = [c["name"] for c in conn.columns]
            msg = _serialize(_row_to_dict(cols, rows[0]))
            t_after_insert = _time_mod.perf_counter()

            uc = conn.run(
                "SELECT COUNT(*) FROM messages WHERE receiver_id=:rid AND is_read=FALSE",
                rid=receiver_id
            )
            unread = int(uc[0][0]) if uc else 0
            t_after_count = _time_mod.perf_counter()

            timing = {
                "conn_ms":        round((t_after_conn   - t0)              * 1000),
                "sync_set_ms":    round((t_after_set    - t_after_conn)    * 1000),
                "insert_exec_ms": round((t_after_insert - t_after_set)     * 1000),
                "insert_ms":      round((t_after_insert - t_after_conn)    * 1000),
                "update_ms": 0,
                "count_ms":       round((t_after_count  - t_after_insert)  * 1000),
                "db_ms":          round((t_after_count  - t0)              * 1000),
            }
            return msg, unread, timing
    finally:
        release_conn(conn)


def mark_message_delivered(msg_id: int):
    """Mark a single message as delivered (receiver WS connection confirmed receipt)."""
    conn = get_conn()
    try:
        conn.run(
            "UPDATE messages SET delivered_at=NOW() WHERE id=:id AND delivered_at IS NULL",
            id=msg_id
        )
    finally:
        release_conn(conn)

def get_conversations(user_id: int) -> list:
    """Get all unique conversations for a user, sorted by most recent message.

    Root-cause note: all columns must be qualified with 'm.' to avoid
    PostgreSQL "column reference is ambiguous" error — both messages and users
    tables have a created_at column, which caused 500 when unqualified.
    """
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT * FROM ("
            "SELECT DISTINCT ON (other_id) "
            "CASE WHEN m.sender_id=:uid THEN m.receiver_id ELSE m.sender_id END AS other_id, "
            "m.content, m.created_at, m.is_read, m.sender_id, "
            "u.full_name, u.user_type, u.tw_id, "
            "p.avatar_url, p.headline, p.title "
            "FROM messages m "
            "JOIN users u ON u.id = CASE WHEN m.sender_id=:uid THEN m.receiver_id ELSE m.sender_id END "
            "LEFT JOIN profiles p ON p.user_id = u.id "
            "WHERE m.sender_id=:uid OR m.receiver_id=:uid "
            "ORDER BY other_id, m.created_at DESC"
            ") sub ORDER BY created_at DESC",
            uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        convs = [_serialize(_row_to_dict(cols, r)) for r in rows]

        # Enrich with per-conversation unread_count in a single batch query
        if convs:
            other_ids = [c["other_id"] for c in convs]
            placeholders = ", ".join(":oid" + str(i) for i in range(len(other_ids)))
            params = {"uid": user_id}
            for i, oid in enumerate(other_ids):
                params["oid" + str(i)] = oid
            unread_rows = conn.run(
                "SELECT sender_id, COUNT(*) AS cnt FROM messages "
                "WHERE receiver_id=:uid AND sender_id IN (" + placeholders + ") AND is_read=FALSE "
                "GROUP BY sender_id",
                **params
            )
            unread_map = {r[0]: r[1] for r in (unread_rows or [])}
            for c in convs:
                c["unread_count"] = unread_map.get(c["other_id"], 0)

        return convs
    finally:
        release_conn(conn)

def get_messages(user_id: int, other_id: int):
    """Get messages between two users.

    Returns (messages, newly_read_ids) where newly_read_ids are IDs of messages
    that were just marked read — used by the caller to push WS read receipts to sender.
    Also marks delivered_at for messages received by this user that weren't yet delivered.
    """
    conn = get_conn()
    try:
        # Root-cause note: must take the latest 100 by DESC first, then
        # re-sort ASC for display — "ORDER BY created_at ASC LIMIT 100"
        # silently dropped the newest messages once a conversation passed
        # 100 rows, keeping only the oldest 100 instead of the most recent.
        rows = conn.run(
            "SELECT * FROM ("
            "SELECT m.*, u.full_name as sender_name "
            "FROM messages m JOIN users u ON u.id=m.sender_id "
            "WHERE (sender_id=:uid AND receiver_id=:oid) "
            "OR (sender_id=:oid AND receiver_id=:uid) "
            "ORDER BY m.created_at DESC LIMIT 100"
            ") sub ORDER BY created_at ASC",
            uid=user_id, oid=other_id
        )
        cols = [c["name"] for c in conn.columns]
        messages = [_serialize(_row_to_dict(cols, r)) for r in rows]

        # Mark undelivered messages as delivered (receiver is viewing the conversation)
        conn.run(
            "UPDATE messages SET delivered_at=NOW() "
            "WHERE receiver_id=:uid AND sender_id=:oid AND delivered_at IS NULL",
            uid=user_id, oid=other_id
        )

        # Collect IDs to mark as read (before the UPDATE so we know which changed)
        unread_rows = conn.run(
            "SELECT id FROM messages "
            "WHERE receiver_id=:uid AND sender_id=:oid AND is_read=FALSE",
            uid=user_id, oid=other_id
        )
        newly_read_ids = [r[0] for r in (unread_rows or [])]

        # Mark as read with timestamp
        if newly_read_ids:
            conn.run(
                "UPDATE messages SET is_read=TRUE, read_at=NOW() "
                "WHERE receiver_id=:uid AND sender_id=:oid AND is_read=FALSE",
                uid=user_id, oid=other_id
            )

        return messages, newly_read_ids
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
            "SELECT * FROM notifications WHERE user_id=:uid AND type != 'message' "
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
            "SELECT COUNT(*) FROM notifications WHERE user_id=:uid AND is_read=FALSE AND type != 'message'",
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


def get_company_followers_list(company_id: int, viewer_id, limit: int, offset: int, user_type: str = "all") -> dict:
    """Paginated list of accounts following company_id. viewer_id=None for guests."""
    conn = get_conn()
    try:
        # Per-type counts (single query)
        type_rows = conn.run(
            "SELECT u.user_type, COUNT(*) FROM company_follows cf "
            "JOIN users u ON u.id=cf.follower_id "
            "WHERE cf.company_id=:cid GROUP BY u.user_type",
            cid=company_id) or []
        type_counts = {"emp": 0, "co": 0, "edu": 0}
        for row in type_rows:
            utype, cnt = row[0], row[1]
            if utype in type_counts:
                type_counts[utype] = cnt
        total_all = sum(type_counts.values())
        counts = {"all": total_all, **type_counts}
        total = type_counts.get(user_type, 0) if user_type != "all" else total_all

        where_type = "AND u.user_type=:utype " if user_type != "all" else ""
        # Check if viewer follows each follower (via profile_follows — cross-entity follow)
        if viewer_id is not None:
            is_following_expr = (
                "EXISTS(SELECT 1 FROM profile_follows v "
                "WHERE v.follower_id=:vid AND v.followed_id=u.id)")
        else:
            is_following_expr = "FALSE"

        query = (
            "SELECT u.id, u.tw_id, u.full_name, u.user_type, p.avatar_url, "
            "pc.name_ar, pc.icon, cf.created_at, " + is_following_expr + " "
            "FROM company_follows cf "
            "JOIN users u ON u.id=cf.follower_id "
            "LEFT JOIN profiles p ON p.user_id=u.id "
            "LEFT JOIN profession_categories pc ON pc.id=p.profession_id "
            "WHERE cf.company_id=:cid " + where_type +
            "ORDER BY cf.created_at DESC LIMIT :lim OFFSET :off"
        )
        params = {"cid": company_id, "lim": limit, "off": offset}
        if viewer_id is not None:
            params["vid"] = int(viewer_id)
        if user_type != "all":
            params["utype"] = user_type

        rows = conn.run(query, **params) or []
        items = []
        for r in rows:
            uid, tw_id, full_name, utype, avatar_url, prof_name, prof_icon, followed_at, is_following = r
            items.append({
                "id":           uid,
                "tw_id":        tw_id,
                "display_name": full_name,
                "avatar_url":   avatar_url,
                "user_type":    utype,
                "profession":   {"name_ar": prof_name, "icon": prof_icon} if prof_name else None,
                "is_following": bool(is_following),
                "can_follow":   viewer_id is not None and int(viewer_id) != uid,
                "followed_at":  followed_at.isoformat() if hasattr(followed_at, "isoformat") else (str(followed_at) if followed_at else None),
            })
        return {
            "items":      items,
            "filter":     {"type": user_type},
            "counts":     counts,
            "pagination": {"limit": limit, "offset": offset, "has_more": (offset + limit) < total, "total": total},
        }
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


def get_company_ratings_detail(company_id: int, viewer_id=None, limit: int = 5) -> dict:
    """Read-only ratings detail: avg, count, distribution, recent comments, viewer's own score."""
    conn = get_conn()
    try:
        # Aggregate
        rt = conn.run(
            "SELECT AVG(score), COUNT(*) FROM company_ratings WHERE company_id=:cid",
            cid=company_id) or [[None, 0]]
        rating_avg   = round(float(rt[0][0]), 1) if rt and rt[0][0] is not None else None
        rating_count = int(rt[0][1]) if rt else 0

        # Distribution 1-5
        dist_rows = conn.run(
            "SELECT score, COUNT(*) FROM company_ratings "
            "WHERE company_id=:cid GROUP BY score",
            cid=company_id) or []
        distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
        for row in dist_rows:
            distribution[str(row[0])] = int(row[1])

        # Recent comments (no rater name — privacy)
        limit = min(max(int(limit), 1), 20)
        c_rows = conn.run(
            "SELECT score, comment, created_at FROM company_ratings "
            "WHERE company_id=:cid AND comment IS NOT NULL AND TRIM(comment) != '' "
            "ORDER BY created_at DESC LIMIT :lim",
            cid=company_id, lim=limit) or []
        recent_comments = [
            {"score": r[0], "comment": r[1],
             "created_at": _serialize(r[2]) if r[2] else None}
            for r in c_rows
        ]

        # Viewer's own rating
        my_rating = None
        if viewer_id is not None:
            my_rows = conn.run(
                "SELECT score FROM company_ratings "
                "WHERE company_id=:cid AND rater_id=:vid",
                cid=company_id, vid=int(viewer_id)) or []
            if my_rows:
                my_rating = int(my_rows[0][0])

        return {
            "rating_avg":      rating_avg,
            "rating_count":    rating_count,
            "distribution":    distribution,
            "recent_comments": recent_comments,
            "my_rating":       my_rating,
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


def get_company_posts_count(company_id: int) -> int:
    """Return total number of posts for a company (COUNT — no row fetch)."""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT COUNT(*) FROM company_posts WHERE company_id = :cid",
            cid=company_id)
        return rows[0][0] if rows else 0
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


def get_profile_followers_list(followed_id: int, viewer_id, limit: int, offset: int, user_type: str = "all") -> dict:
    """Paginated list of accounts that follow followed_id. viewer_id=None for guests."""
    conn = get_conn()
    try:
        # Per-type counts (single query)
        type_rows = conn.run(
            "SELECT u.user_type, COUNT(*) FROM profile_follows pf "
            "JOIN users u ON u.id=pf.follower_id "
            "WHERE pf.followed_id=:fdid GROUP BY u.user_type",
            fdid=followed_id) or []
        type_counts = {"emp": 0, "co": 0, "edu": 0}
        for utype, cnt in type_rows:
            if utype in type_counts:
                type_counts[utype] = cnt
        total_all = sum(type_counts.values())
        counts = {"all": total_all, **type_counts}

        total = type_counts.get(user_type, 0) if user_type != "all" else total_all

        # Build query
        where_type = "AND u.user_type=:utype " if user_type != "all" else ""
        if viewer_id is not None:
            is_following_expr = (
                "EXISTS(SELECT 1 FROM profile_follows v "
                "WHERE v.follower_id=:vid AND v.followed_id=u.id)")
        else:
            is_following_expr = "FALSE"

        query = (
            "SELECT u.id, u.tw_id, u.full_name, u.user_type, p.avatar_url, "
            "pc.name_ar, pc.icon, pf.created_at, " + is_following_expr + " "
            "FROM profile_follows pf "
            "JOIN users u ON u.id=pf.follower_id "
            "LEFT JOIN profiles p ON p.user_id=u.id "
            "LEFT JOIN profession_categories pc ON pc.id=p.profession_id "
            "WHERE pf.followed_id=:fdid " + where_type +
            "ORDER BY pf.created_at DESC LIMIT :lim OFFSET :off"
        )
        params = {"fdid": followed_id, "lim": limit, "off": offset}
        if viewer_id is not None:
            params["vid"] = int(viewer_id)
        if user_type != "all":
            params["utype"] = user_type

        rows = conn.run(query, **params)

        items = []
        for r in rows:
            uid, tw_id, full_name, utype, avatar_url, prof_name, prof_icon, followed_at, is_following = r
            items.append({
                "id":           uid,
                "tw_id":        tw_id,
                "display_name": full_name,
                "avatar_url":   avatar_url,
                "user_type":    utype,
                "profession":   {"name_ar": prof_name, "icon": prof_icon} if prof_name else None,
                "is_following": bool(is_following),
                "can_follow":   viewer_id is not None and int(viewer_id) != uid,
                "followed_at":  followed_at.isoformat() if hasattr(followed_at, "isoformat") else (str(followed_at) if followed_at else None),
            })
        return {
            "items":      items,
            "filter":     {"type": user_type},
            "counts":     counts,
            "pagination": {"limit": limit, "offset": offset, "has_more": (offset + limit) < total, "total": total},
        }
    finally:
        release_conn(conn)


def get_profile_following_list(follower_id: int, viewer_id, limit: int, offset: int, user_type: str = "all") -> dict:
    """Paginated list of accounts that follower_id follows. viewer_id=None for guests."""
    conn = get_conn()
    try:
        # Per-type counts (single query)
        type_rows = conn.run(
            "SELECT u.user_type, COUNT(*) FROM profile_follows pf "
            "JOIN users u ON u.id=pf.followed_id "
            "WHERE pf.follower_id=:frid GROUP BY u.user_type",
            frid=follower_id) or []
        type_counts = {"emp": 0, "co": 0, "edu": 0}
        for utype, cnt in type_rows:
            if utype in type_counts:
                type_counts[utype] = cnt
        total_all = sum(type_counts.values())
        counts = {"all": total_all, **type_counts}

        total = type_counts.get(user_type, 0) if user_type != "all" else total_all

        # Build query
        where_type = "AND u.user_type=:utype " if user_type != "all" else ""
        if viewer_id is not None:
            is_following_expr = (
                "EXISTS(SELECT 1 FROM profile_follows v "
                "WHERE v.follower_id=:vid AND v.followed_id=u.id)")
        else:
            is_following_expr = "FALSE"

        query = (
            "SELECT u.id, u.tw_id, u.full_name, u.user_type, p.avatar_url, "
            "pc.name_ar, pc.icon, pf.created_at, " + is_following_expr + " "
            "FROM profile_follows pf "
            "JOIN users u ON u.id=pf.followed_id "
            "LEFT JOIN profiles p ON p.user_id=u.id "
            "LEFT JOIN profession_categories pc ON pc.id=p.profession_id "
            "WHERE pf.follower_id=:frid " + where_type +
            "ORDER BY pf.created_at DESC LIMIT :lim OFFSET :off"
        )
        params = {"frid": follower_id, "lim": limit, "off": offset}
        if viewer_id is not None:
            params["vid"] = int(viewer_id)
        if user_type != "all":
            params["utype"] = user_type

        rows = conn.run(query, **params)

        items = []
        for r in rows:
            uid, tw_id, full_name, utype, avatar_url, prof_name, prof_icon, followed_at, is_following = r
            items.append({
                "id":           uid,
                "tw_id":        tw_id,
                "display_name": full_name,
                "avatar_url":   avatar_url,
                "user_type":    utype,
                "profession":   {"name_ar": prof_name, "icon": prof_icon} if prof_name else None,
                "is_following": bool(is_following),
                "can_follow":   viewer_id is not None and int(viewer_id) != uid,
                "followed_at":  followed_at.isoformat() if hasattr(followed_at, "isoformat") else (str(followed_at) if followed_at else None),
            })
        return {
            "items":      items,
            "filter":     {"type": user_type},
            "counts":     counts,
            "pagination": {"limit": limit, "offset": offset, "has_more": (offset + limit) < total, "total": total},
        }
    finally:
        release_conn(conn)

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


# ══ Profile Interest System ══

_INTEREST_TYPE_MAP = {
    "emp": "profile_like",
    "co":  "candidate_save",
    "edu": "training_invite",
}

_INTEREST_LABEL_MAP = {
    "co":  {"inactive": "حفظ كمرشح",     "active": "محفوظ كمرشح"},
    "edu": {"inactive": "دعوة للتدريب",   "active": "تم حفظ الدعوة"},
    "emp": {"inactive": "أعجبني ملفك",    "active": "تم الإعجاب"},
}


def get_profile_interest_type(actor_user_type: str) -> str:
    """Return the interest_type for a given actor user_type.
    Backend owns this mapping — frontend never decides."""
    return _INTEREST_TYPE_MAP.get(actor_user_type, "profile_like")


def get_profile_interest_label(actor_user_type: str, is_active: bool) -> str:
    """Return the display label for the interest button."""
    state = "active" if is_active else "inactive"
    labels = _INTEREST_LABEL_MAP.get(actor_user_type, {"inactive": "أعجبني", "active": "تم الإعجاب"})
    return labels[state]


def save_profile_interest(actor_user_id: int, target_user_id: int) -> dict:
    """Save a profile interest. actor_type and interest_type are derived server-side.
    Uses UPSERT (ON CONFLICT DO NOTHING) — idempotent.
    Returns {"success": bool, "interest_type": str, "is_active": bool}."""
    if actor_user_id == target_user_id:
        return {"success": False, "error": "لا يمكن حفظ ملفك الشخصي"}

    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT user_type FROM users WHERE id = :uid",
            uid=actor_user_id)
        if not rows:
            return {"success": False, "error": "المستخدم غير موجود"}

        actor_type    = rows[0][0]
        interest_type = get_profile_interest_type(actor_type)

        conn.run(
            """
            INSERT INTO profile_interests
                (actor_user_id, target_user_id, actor_type, interest_type, updated_at)
            VALUES
                (:aid, :tid, :atype, :itype, NOW())
            ON CONFLICT (actor_user_id, target_user_id)
            DO UPDATE SET updated_at = NOW()
            """,
            aid=actor_user_id, tid=target_user_id,
            atype=actor_type, itype=interest_type)

        return {"success": True, "interest_type": interest_type, "is_active": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        release_conn(conn)


def remove_profile_interest(actor_user_id: int, target_user_id: int) -> dict:
    """Remove a profile interest. Idempotent — no error if row missing.
    Returns {"success": bool, "is_active": False}."""
    conn = get_conn()
    try:
        conn.run(
            "DELETE FROM profile_interests "
            "WHERE actor_user_id = :aid AND target_user_id = :tid",
            aid=actor_user_id, tid=target_user_id)
        return {"success": True, "is_active": False}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        release_conn(conn)


def is_profile_interest_active(actor_user_id: int, target_user_id: int) -> bool:
    """Return True if actor has an active interest on target profile."""
    if actor_user_id == target_user_id:
        return False
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT 1 FROM profile_interests "
            "WHERE actor_user_id = :aid AND target_user_id = :tid",
            aid=actor_user_id, tid=target_user_id)
        return bool(rows)
    finally:
        release_conn(conn)


def is_candidate_saved(company_id: int, candidate_id: int) -> bool:
    """Return True if the company has saved this candidate in company_saved_candidates."""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT 1 FROM company_saved_candidates "
            "WHERE company_id = :cid AND candidate_id = :uid",
            cid=company_id, uid=candidate_id)
        return bool(rows)
    finally:
        release_conn(conn)


# ── Company Branches ──────────────────────────────────────────────────────────

def _migrate_company_branches():
    """Create company_branches table + index if they don't exist (idempotent)."""
    conn = get_conn()
    try:
        conn.run("""
            CREATE TABLE IF NOT EXISTS company_branches (
                id            BIGSERIAL PRIMARY KEY,
                company_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                branch_name   TEXT,
                country       TEXT NOT NULL,
                city          TEXT,
                district      TEXT,
                display_order INTEGER DEFAULT 0,
                created_at    TIMESTAMPTZ DEFAULT NOW(),
                updated_at    TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.run("""
            CREATE INDEX IF NOT EXISTS idx_company_branches_company
            ON company_branches(company_id)
        """)
    finally:
        release_conn(conn)


def get_company_branches(company_id: int) -> list:
    """Return all branches for a company ordered by display_order then id."""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, branch_name, country, city, district, display_order "
            "FROM company_branches "
            "WHERE company_id = :cid "
            "ORDER BY display_order ASC, id ASC",
            cid=company_id,
        )
        cols = ["id", "branch_name", "country", "city", "district", "display_order"]
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)


def save_company_branches(company_id: int, branches: list) -> list:
    """Replace all branches atomically (BEGIN → DELETE → INSERT → COMMIT).
    Skips rows with empty country. Returns saved list."""
    if len(branches) > 10:
        raise ValueError("لا يمكن إضافة أكثر من 10 فروع")

    conn = get_conn()
    try:
        conn.run("BEGIN")
        conn.run(
            "DELETE FROM company_branches WHERE company_id = :cid",
            cid=company_id,
        )
        saved = []
        for i, b in enumerate(branches):
            country = (b.get("country") or "").strip()
            if not country:
                continue
            name     = (b.get("branch_name") or "").strip() or None
            city     = (b.get("city")        or "").strip() or None
            district = (b.get("district")    or "").strip() or None
            rows = conn.run(
                "INSERT INTO company_branches "
                "(company_id, branch_name, country, city, district, display_order) "
                "VALUES (:cid, :name, :country, :city, :district, :ord) "
                "RETURNING id",
                cid=company_id, name=name, country=country,
                city=city, district=district, ord=i,
            )
            saved.append(_serialize({
                "id":            rows[0][0] if rows else None,
                "branch_name":   name,
                "country":       country,
                "city":          city,
                "district":      district,
                "display_order": i,
            }))
        conn.run("COMMIT")
        return saved
    except Exception:
        try:
            conn.run("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        release_conn(conn)


# ══ Phase 3: Company Saved Candidates ══════════════════════════════════════
# Private data — visible only to the company owner. Never returned to guests.
# candidate_id must be user_type='emp'. company_id must be user_type='co'.

def _migrate_company_saved_candidates():
    """Create company_saved_candidates table + indexes (idempotent)."""
    conn = get_conn()
    try:
        conn.run("""
            CREATE TABLE IF NOT EXISTS company_saved_candidates (
                id           BIGSERIAL PRIMARY KEY,
                company_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                job_id       INTEGER NULL REFERENCES jobs(id) ON DELETE SET NULL,
                status       TEXT NOT NULL DEFAULT 'saved',
                notes        TEXT,
                saved_by     INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_saved_candidate UNIQUE (company_id, candidate_id)
            )
        """)
        conn.run("""
            CREATE INDEX IF NOT EXISTS idx_saved_cands_company
            ON company_saved_candidates(company_id)
        """)
        conn.run("""
            CREATE INDEX IF NOT EXISTS idx_saved_cands_candidate
            ON company_saved_candidates(candidate_id)
        """)
    finally:
        release_conn(conn)


def save_company_candidate(company_id: int, candidate_id: int, saved_by: int,
                            job_id: int = None, notes: str = None) -> int:
    """
    Save a candidate to the company's private list (UPSERT — idempotent).
    Returns updated total count.
    Raises ValueError if candidate is not user_type='emp'.
    """
    conn = get_conn()
    try:
        check = conn.run("SELECT user_type FROM users WHERE id = :uid", uid=candidate_id)
        if not check or check[0][0] != "emp":
            raise ValueError("يجب أن يكون المرشح موظفاً")
        conn.run(
            "INSERT INTO company_saved_candidates "
            "(company_id, candidate_id, job_id, notes, saved_by) "
            "VALUES (:cid, :uid, :jid, :notes, :sid) "
            "ON CONFLICT (company_id, candidate_id) DO UPDATE "
            "SET updated_at=NOW(), job_id=EXCLUDED.job_id, notes=EXCLUDED.notes",
            cid=company_id, uid=candidate_id,
            jid=job_id, notes=notes, sid=saved_by)
        count_row = conn.run(
            "SELECT COUNT(*) FROM company_saved_candidates WHERE company_id=:cid",
            cid=company_id)
        return count_row[0][0] if count_row else 0
    finally:
        release_conn(conn)


def remove_company_candidate(company_id: int, candidate_id: int) -> int:
    """
    Remove a candidate from the company's saved list.
    Returns new total count after removal.
    """
    conn = get_conn()
    try:
        conn.run(
            "DELETE FROM company_saved_candidates "
            "WHERE company_id=:cid AND candidate_id=:uid",
            cid=company_id, uid=candidate_id)
        count_row = conn.run(
            "SELECT COUNT(*) FROM company_saved_candidates WHERE company_id=:cid",
            cid=company_id)
        return count_row[0][0] if count_row else 0
    finally:
        release_conn(conn)


def get_company_saved_candidates(company_id: int, limit: int = 20, offset: int = 0) -> dict:
    """
    Paginated private list of saved candidates for a company.
    Returns: candidate_id, tw_id, full_name, avatar_url, profession, city, country,
             job_id, status, notes, created_at.
    Sensitive fields (email, phone, detailed location) are NOT returned.
    """
    conn = get_conn()
    try:
        total_row = conn.run(
            "SELECT COUNT(*) FROM company_saved_candidates WHERE company_id=:cid",
            cid=company_id)
        total = total_row[0][0] if total_row else 0

        rows = conn.run(
            "SELECT u.id, u.tw_id, u.full_name, p.avatar_url, "
            "pc.name_ar, p.city, p.country, "
            "sc.job_id, sc.status, sc.notes, sc.created_at "
            "FROM company_saved_candidates sc "
            "JOIN users u ON u.id=sc.candidate_id "
            "LEFT JOIN profiles p ON p.user_id=u.id "
            "LEFT JOIN profession_categories pc ON pc.id=p.profession_id "
            "WHERE sc.company_id=:cid "
            "ORDER BY sc.created_at DESC LIMIT :lim OFFSET :off",
            cid=company_id, lim=limit, off=offset) or []

        items = []
        for r in rows:
            cand_id, tw_id, full_name, avatar_url, prof_name, city, country, \
                job_id, status, notes, created_at = r
            items.append(_serialize({
                "candidate_id": cand_id,
                "tw_id":        tw_id,
                "full_name":    full_name,
                "avatar_url":   avatar_url,
                "profession":   prof_name or None,
                "city":         city,
                "country":      country,
                "job_id":       job_id,
                "status":       status or "saved",
                "notes":        notes,
                "created_at":   created_at,
            }))

        return {
            "count": total,
            "items": items,
            "pagination": {
                "limit":    limit,
                "offset":   offset,
                "has_more": (offset + limit) < total,
                "total":    total,
            },
        }
    finally:
        release_conn(conn)


def get_company_saved_candidates_count(company_id: int) -> int:
    """Return total count of saved candidates (used for badge display)."""
    conn = get_conn()
    try:
        row = conn.run(
            "SELECT COUNT(*) FROM company_saved_candidates WHERE company_id=:cid",
            cid=company_id)
        return row[0][0] if row else 0
    finally:
        release_conn(conn)


# ── Pipeline status constants ────────────────────────────────────────────────

VALID_CANDIDATE_STATUSES = frozenset({
    "saved", "shortlisted", "contacted", "interview", "hired", "rejected"
})

CANDIDATE_STATUS_LABELS = {
    "saved":       "محفوظ",
    "shortlisted": "مرشح قوي",
    "contacted":   "تم التواصل",
    "interview":   "مقابلة",
    "hired":       "تم التوظيف",
    "rejected":    "غير مناسب",
}

# Allowed sort keys → ORDER BY expression (safe — never interpolated from user input directly)
VALID_CANDIDATE_SORTS = {
    "updated_desc": "sc.updated_at DESC NULLS LAST, sc.created_at DESC",
    "updated_asc":  "sc.updated_at ASC NULLS FIRST, sc.created_at ASC",
    "created_desc": "sc.created_at DESC",
    "created_asc":  "sc.created_at ASC",
    "name_asc":     "u.full_name ASC",
    "status_asc":   "sc.status ASC",
}


def get_company_saved_candidates_filtered(
    company_id: int,
    limit: int = 20,
    offset: int = 0,
    status: str = None,
    job_id: int = None,
    unlinked: bool = False,
    q: str = None,
    sort: str = "updated_desc",
) -> dict:
    """
    Filtered + paginated private list of saved candidates for a company.

    All filter params are optional — omitting all reproduces original
    get_company_saved_candidates() behavior.

    Raises ValueError if job_id is provided but doesn't belong to this company.

    Returns:
      { count (=filtered total), items, pagination, filters }
      'count' == pagination.total == filtered total.
      When no filters active: count == all saved candidates (badge-safe).
    """
    conn = get_conn()
    try:
        # Validate job_id ownership before running expensive query
        if job_id is not None:
            job_check = conn.run(
                "SELECT id FROM jobs WHERE id=:jid AND company_id=:cid",
                jid=job_id, cid=company_id)
            if not job_check:
                raise ValueError("الوظيفة غير موجودة أو لا تتبع شركتك")

        # Build WHERE clause dynamically (all user values are parameterized)
        where_parts = ["sc.company_id = :cid"]
        params = {"cid": company_id}

        if status:
            where_parts.append("sc.status = :status")
            params["status"] = status

        if job_id is not None:
            where_parts.append("sc.job_id = :job_id")
            params["job_id"] = job_id
        elif unlinked:
            where_parts.append("sc.job_id IS NULL")

        if q:
            where_parts.append(
                "(u.full_name ILIKE :q OR u.tw_id ILIKE :q "
                "OR pc.name_ar ILIKE :q OR p.city ILIKE :q OR p.country ILIKE :q)"
            )
            params["q"] = "%" + q + "%"

        where_sql = " AND ".join(where_parts)
        order_sql = VALID_CANDIDATE_SORTS.get(sort, VALID_CANDIDATE_SORTS["updated_desc"])

        base_from = (
            "FROM company_saved_candidates sc "
            "JOIN users u ON u.id = sc.candidate_id "
            "LEFT JOIN profiles p ON p.user_id = u.id "
            "LEFT JOIN profession_categories pc ON pc.id = p.profession_id "
        )

        # Filtered total
        cnt_row = conn.run(
            "SELECT COUNT(*) " + base_from + "WHERE " + where_sql,
            **params)
        total = cnt_row[0][0] if cnt_row else 0

        # Items
        rows = conn.run(
            "SELECT u.id, u.tw_id, u.full_name, p.avatar_url, "
            "pc.name_ar, p.city, p.country, "
            "sc.job_id, sc.status, sc.notes, sc.created_at, sc.updated_at "
            + base_from +
            "WHERE " + where_sql + " "
            "ORDER BY " + order_sql + " "
            "LIMIT :lim OFFSET :off",
            lim=limit, off=offset, **params
        ) or []

        items = []
        for r in rows:
            (cand_id, tw_id, full_name, avatar_url, prof_name,
             city, country, sc_job_id, sc_status, notes,
             created_at, updated_at) = r
            items.append(_serialize({
                "candidate_id": cand_id,
                "tw_id":        tw_id,
                "full_name":    full_name,
                "avatar_url":   avatar_url,
                "profession":   prof_name or None,
                "city":         city,
                "country":      country,
                "job_id":       sc_job_id,
                "status":       sc_status or "saved",
                "notes":        notes,
                "created_at":   created_at,
                "updated_at":   updated_at,
            }))

        return {
            "count": total,
            "items": items,
            "pagination": {
                "limit":    limit,
                "offset":   offset,
                "has_more": (offset + limit) < total,
                "total":    total,
            },
            "filters": {
                "status":   status,
                "job_id":   job_id,
                "unlinked": unlinked,
                "q":        q,
                "sort":     sort,
            },
        }
    finally:
        release_conn(conn)


def get_company_saved_candidates_stats(company_id: int) -> dict:
    """
    Pipeline statistics for a company's saved candidates.
    All 6 pipeline statuses are always present in by_status (zero-filled).
    No candidate data is returned — counts only.
    """
    conn = get_conn()
    try:
        # Counts by status
        status_rows = conn.run(
            "SELECT COALESCE(status, 'saved'), COUNT(*) "
            "FROM company_saved_candidates "
            "WHERE company_id = :cid "
            "GROUP BY status",
            cid=company_id) or []

        # Total, with_job, unlinked — single-pass via FILTER
        summary_row = conn.run(
            "SELECT COUNT(*), "
            "COUNT(*) FILTER (WHERE job_id IS NOT NULL), "
            "COUNT(*) FILTER (WHERE job_id IS NULL) "
            "FROM company_saved_candidates WHERE company_id = :cid",
            cid=company_id) or []

        by_status = {s: 0 for s in VALID_CANDIDATE_STATUSES}
        for row in status_rows:
            st, cnt = row
            if st in by_status:
                by_status[st] = int(cnt or 0)

        sr = summary_row[0] if summary_row else (0, 0, 0)
        return {
            "total":     int(sr[0] or 0),
            "by_status": by_status,
            "with_job":  int(sr[1] or 0),
            "unlinked":  int(sr[2] or 0),
        }
    finally:
        release_conn(conn)


def update_company_saved_candidate(
    company_id: int,
    candidate_id: int,
    updates: dict
) -> dict:
    """
    Partial update of a saved candidate's pipeline fields (status, notes, job_id).
    Only keys present in `updates` are written — absent keys are untouched.

    Returns the updated safe item dict, or None if the row doesn't exist.
    Raises ValueError for invalid status, oversized notes, or foreign job_id.
    """
    conn = get_conn()
    try:
        # 1. Confirm row exists
        row_check = conn.run(
            "SELECT id FROM company_saved_candidates "
            "WHERE company_id=:cid AND candidate_id=:uid",
            cid=company_id, uid=candidate_id)
        if not row_check:
            return None

        # 2. Validate & normalize each update field
        if 'status' in updates:
            s = updates['status']
            if s not in VALID_CANDIDATE_STATUSES:
                raise ValueError(
                    "قيمة status غير مسموحة. القيم المسموحة: "
                    + ", ".join(sorted(VALID_CANDIDATE_STATUSES)))

        if 'notes' in updates:
            n = updates['notes']
            if n is not None:
                n = n.strip()
                if len(n) > 500:
                    raise ValueError("الملاحظات لا يمكن أن تتجاوز 500 حرف")
                updates['notes'] = n if n else None
            # else: None → clear (store NULL)

        if 'job_id' in updates and updates['job_id'] is not None:
            job_check = conn.run(
                "SELECT id FROM jobs WHERE id=:jid AND company_id=:cid",
                jid=updates['job_id'], cid=company_id)
            if not job_check:
                raise ValueError("الوظيفة غير موجودة أو لا تتبع شركتك")

        # 3. Build dynamic SET clause
        set_parts = ["updated_at = NOW()"]
        params = {"cid": company_id, "uid": candidate_id}

        if 'status' in updates:
            set_parts.append("status = :status")
            params['status'] = updates['status']

        if 'notes' in updates:
            set_parts.append("notes = :notes")
            params['notes'] = updates['notes']

        if 'job_id' in updates:
            set_parts.append("job_id = :job_id")
            params['job_id'] = updates['job_id']

        conn.run(
            "UPDATE company_saved_candidates "
            "SET " + ", ".join(set_parts) + " "
            "WHERE company_id=:cid AND candidate_id=:uid",
            **params)

        # 4. Return updated item (same safe shape as list endpoint + updated_at)
        r = conn.run(
            "SELECT u.id, u.tw_id, u.full_name, p.avatar_url, "
            "       pc.name_ar, p.city, p.country, "
            "       sc.job_id, sc.status, sc.notes, sc.created_at, sc.updated_at "
            "FROM company_saved_candidates sc "
            "JOIN users u ON u.id = sc.candidate_id "
            "LEFT JOIN profiles p ON p.user_id = u.id "
            "LEFT JOIN profession_categories pc ON pc.id = p.profession_id "
            "WHERE sc.company_id=:cid AND sc.candidate_id=:uid",
            cid=company_id, uid=candidate_id)
        if not r:
            return None

        row = r[0]
        raw_status = row[8] or "saved"
        return _serialize({
            "candidate_id":   row[0],
            "tw_id":          row[1],
            "full_name":      row[2],
            "avatar_url":     row[3],
            "profession":     row[4] or None,
            "city":           row[5],
            "country":        row[6],
            "job_id":         row[7],
            "status":         raw_status,
            "status_label":   CANDIDATE_STATUS_LABELS.get(raw_status, raw_status),
            "notes":          row[9],
            "created_at":     row[10],
            "updated_at":     row[11],
        })
    finally:
        release_conn(conn)


def get_company_candidate_suggestions(
    company_id: int,
    limit: int = 20,
    offset: int = 0,
    include_saved: bool = False
) -> dict:
    """
    Return scored candidate suggestions for a company based on its active jobs.

    Scoring (max 100):
      +45  candidate profession_id matches a job's primary profession_id
      +35  candidate profession_id is in job_profession_targets (secondary, not double-counted)
      +20  skill overlap between candidate skills and job required skills (scaled)
      +10  city or country match with company location
      +10  profile quality (has headline +5, actively looking avail +5)

    Returns empty list with status='no_jobs' if company has no active jobs.
    Excludes already-saved candidates by default (include_saved=False).
    Never returns email, phone, dob, or any non-public field.
    """
    conn = get_conn()
    try:
        # ── 1. Active jobs for this company ─────────────────────────────────
        job_rows = conn.run(
            "SELECT j.id, j.profession_id, j.skills, j.accepts_all_professions, "
            "       pc.name_ar AS profession_name "
            "FROM jobs j "
            "LEFT JOIN profession_categories pc ON pc.id = j.profession_id "
            "WHERE j.company_id = :cid AND j.status = 'active'",
            cid=company_id)

        if not job_rows:
            return {
                "status": "no_jobs",
                "message": "لا توجد اقتراحات بعد — انشر وظيفة أولاً لتحسين الاقتراحات.",
                "items": [], "count": 0,
                "pagination": {"limit": limit, "offset": offset, "has_more": False, "total": 0}
            }

        # ── 2. Aggregate job signals ─────────────────────────────────────────
        job_ids = [r[0] for r in job_rows]
        any_accepts_all = any(bool(r[3]) for r in job_rows)
        primary_prof_ids = set()
        all_job_skills = set()

        for r in job_rows:
            if r[1]:
                primary_prof_ids.add(r[1])
            for sk in (r[2] or []):
                if sk:
                    all_job_skills.add(sk.strip().lower())

        # ── 3. Secondary professions (job_profession_targets) ────────────────
        secondary_prof_ids = set()
        if job_ids:
            ph = ",".join(f":jid{i}" for i in range(len(job_ids)))
            p = {f"jid{i}": jid for i, jid in enumerate(job_ids)}
            if primary_prof_ids:
                xph = ",".join(f":xp{i}" for i in range(len(primary_prof_ids)))
                p.update({f"xp{i}": pid for i, pid in enumerate(primary_prof_ids)})
                rows = conn.run(
                    f"SELECT DISTINCT profession_id FROM job_profession_targets "
                    f"WHERE job_id IN ({ph}) AND profession_id NOT IN ({xph})",
                    **p)
            else:
                rows = conn.run(
                    f"SELECT DISTINCT profession_id FROM job_profession_targets "
                    f"WHERE job_id IN ({ph})",
                    **p)
            secondary_prof_ids = {r[0] for r in rows}

        all_rel_prof_ids = primary_prof_ids | secondary_prof_ids

        # ── 4. Company location for scoring ──────────────────────────────────
        co_loc = conn.run(
            "SELECT city, country FROM profiles WHERE user_id = :uid", uid=company_id)
        co_city    = (co_loc[0][0] or "").strip() if co_loc else ""
        co_country = (co_loc[0][1] or "").strip() if co_loc else ""

        # ── 5. Already-saved candidate IDs ───────────────────────────────────
        saved_rows = conn.run(
            "SELECT candidate_id FROM company_saved_candidates WHERE company_id = :cid",
            cid=company_id)
        saved_ids = {r[0] for r in saved_rows}

        # ── 6. Build candidate filter ─────────────────────────────────────────
        where_parts = ["u.user_type = 'emp'", "u.id != :cid"]
        qp = {"cid": company_id}

        if not include_saved and saved_ids:
            sph = ",".join(f":sid{i}" for i in range(len(saved_ids)))
            qp.update({f"sid{i}": sid for i, sid in enumerate(saved_ids)})
            where_parts.append(f"u.id NOT IN ({sph})")

        # Profession pre-filter when job doesn't accept all (improves performance)
        if not any_accepts_all and all_rel_prof_ids:
            pph = ",".join(f":pf{i}" for i in range(len(all_rel_prof_ids)))
            qp.update({f"pf{i}": pid for i, pid in enumerate(all_rel_prof_ids)})
            where_parts.append(f"p.profession_id IN ({pph})")

        where_sql = " AND ".join(where_parts)

        cand_rows = conn.run(
            f"SELECT u.id, u.tw_id, u.full_name, p.avatar_url, p.profession_id, "
            f"       p.city, p.country, p.avail, p.skills, p.headline, "
            f"       pc.name_ar AS profession_name "
            f"FROM users u "
            f"JOIN profiles p ON p.user_id = u.id "
            f"LEFT JOIN profession_categories pc ON pc.id = p.profession_id "
            f"WHERE {where_sql} "
            f"ORDER BY u.id LIMIT 500",
            **qp)

        if not cand_rows:
            return {
                "status": "success",
                "items": [], "count": 0,
                "pagination": {"limit": limit, "offset": offset, "has_more": False, "total": 0}
            }

        candidates = [{
            "id": r[0], "tw_id": r[1], "full_name": r[2],
            "avatar_url": r[3], "profession_id": r[4],
            "city": r[5] or "", "country": r[6] or "",
            "avail": r[7] or "", "profile_skills": [s.strip().lower() for s in (r[8] or []) if s],
            "headline": r[9] or "", "profession_name": r[10] or ""
        } for r in cand_rows]

        # ── 7. Batch-fetch user_skills ────────────────────────────────────────
        cand_ids = [c["id"] for c in candidates]
        user_skills_map = {}
        if cand_ids:
            usph = ",".join(f":us{i}" for i in range(len(cand_ids)))
            usp  = {f"us{i}": uid for i, uid in enumerate(cand_ids)}
            us_rows = conn.run(
                f"SELECT user_id, skill FROM user_skills WHERE user_id IN ({usph})",
                **usp)
            for r in us_rows:
                user_skills_map.setdefault(r[0], set()).add((r[1] or "").strip().lower())

        # ── 8. Score each candidate ───────────────────────────────────────────
        scored = []
        for c in candidates:
            score   = 0
            reasons = []
            is_saved_flag = c["id"] in saved_ids

            # Profession (mutually exclusive: primary takes precedence)
            prof_id = c["profession_id"]
            if prof_id:
                if prof_id in primary_prof_ids:
                    score += 45
                    reasons.append("تخصصه يطابق إحدى وظائفك")
                elif prof_id in secondary_prof_ids:
                    score += 35
                    reasons.append("تخصصه ضمن التخصصات المقبولة لإحدى وظائفك")

            # Skills
            cand_skills = set(c["profile_skills"]) | user_skills_map.get(c["id"], set())
            if all_job_skills and cand_skills:
                common = cand_skills & all_job_skills
                if common:
                    n = len(common)
                    skill_score = min(20, max(5, n * 5))
                    score += skill_score
                    word = "مهارة مشتركة" if n == 1 else "مهارات مشتركة"
                    reasons.append(f"يمتلك {n} {word}")

            # Location (city preferred over country)
            if co_city and c["city"] and co_city == c["city"]:
                score += 10
                reasons.append("في نفس المدينة")
            elif co_country and c["country"] and co_country == c["country"]:
                score += 10
                reasons.append("في نفس البلد")

            # Profile quality
            quality = 0
            if c["headline"]:
                quality += 5
            avail = c["avail"]
            if avail and avail not in ("", "not_looking", "unavailable"):
                quality += 5
                reasons.append("يبحث عن فرص عمل")
            score += quality

            if is_saved_flag:
                reasons.append("محفوظ مسبقاً")

            score = min(100, score)

            # Only suggest candidates with at least one matching signal
            if score > 0:
                scored.append({
                    "candidate_id": c["id"],
                    "tw_id":        c["tw_id"],
                    "full_name":    c["full_name"],
                    "avatar_url":   c["avatar_url"],
                    "profession":   c["profession_name"],
                    "city":         c["city"],
                    "country":      c["country"],
                    "match_score":  score,
                    "match_reasons": reasons,
                    "is_saved":     is_saved_flag
                })

        # ── 9. Sort and paginate ──────────────────────────────────────────────
        scored.sort(key=lambda x: x["match_score"], reverse=True)
        total = len(scored)
        page  = scored[offset: offset + limit]

        return {
            "status": "success",
            "count": len(page),
            "items": page,
            "pagination": {
                "limit": limit, "offset": offset,
                "has_more": (offset + limit) < total,
                "total": total
            }
        }

    finally:
        release_conn(conn)

