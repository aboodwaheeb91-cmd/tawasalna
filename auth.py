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


def _migrate_job_lifecycle():
    """Add lifecycle columns (closed_at, paused_at, duration_days) and back-fill (idempotent)."""
    conn = get_conn()
    try:
        conn.run("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS closed_at TIMESTAMP")
        conn.run("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS paused_at TIMESTAMP")
        conn.run("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS duration_days SMALLINT DEFAULT 7")
        # Back-fill expires_at for active/paused jobs that predate the lifecycle system
        conn.run("""
            UPDATE jobs
            SET expires_at = created_at + INTERVAL '30 days'
            WHERE expires_at IS NULL AND status IN ('active', 'paused')
        """)
    except Exception:
        pass
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


def _eff_status(status: str, closed_at, expires_at, paused_at=None) -> str:
    """Compute effective lifecycle status — never stored in DB, always derived at request time.

    Transitions:
      active/paused + expires_at elapsed       → 'closed' (auto-expired by duration)
      closed or auto-closed + ref + 30d         → 'expired' (viewer window closed)
      active/paused within window               → status unchanged
    """
    now = datetime.utcnow()

    def _to_dt(v):
        if v is None: return None
        if isinstance(v, datetime): return v
        try: return datetime.fromisoformat(str(v).replace('Z', ''))
        except Exception: return None

    closed_at_dt  = _to_dt(closed_at)
    expires_at_dt = _to_dt(expires_at)

    if status == 'closed':
        ref = closed_at_dt or expires_at_dt
        if ref and (now - ref).days >= 30:
            return 'expired'
        return 'closed'

    # active or paused: check if listing duration elapsed (auto-close)
    if expires_at_dt and now > expires_at_dt:
        if (now - expires_at_dt).days >= 30:
            return 'expired'
        return 'closed'

    return status


_ALLOWED_DURATIONS = frozenset({3, 7, 14, 30})


def add_job(company_id: int, data: dict) -> dict:
    _cache_del('jobs:')
    conn = get_conn()
    result = None
    try:
        skills      = data.get("skills") or []
        sal_hidden  = bool(data.get("salary_hidden", False))
        prof_id     = data.get("profession_id") or None
        accepts_all = bool(data.get("accepts_all_professions") or False)

        # Validate accepted_profession_ids BEFORE any mutation — fail fast
        # When accepts_all_professions=True, individual targets are cleared (empty list)
        raw_accepted = [] if accepts_all else (data.get("accepted_profession_ids") or [])
        accepted_pids = _validate_accepted_profession_ids(conn, prof_id, raw_accepted)

        # Validate and apply listing duration (default 7 days)
        raw_dur = data.get("duration_days")
        if raw_dur is None:
            dur = 7
        else:
            dur = int(raw_dur)
            if dur not in _ALLOWED_DURATIONS:
                raise ValueError("مدة استقبال الطلبات يجب أن تكون: 3، 7، 14، أو 30 يوماً")

        rows = conn.run(
            "INSERT INTO jobs (company_id, title, description, location, job_type, "
            "salary_min, salary_max, currency, experience_years, skills, status, "
            "category, work_mode, salary_hidden, profession_id, accepts_all_professions, "
            f"expires_at, duration_days) "
            "VALUES (:cid, :title, :desc, :loc, :jtype, :smin, :smax, :cur, :exp, "
            f":skills, 'active', :cat, :wmode, :shide, :profid, :accall, "
            f"NOW() + INTERVAL '{dur} days', :dur) "
            "RETURNING id, company_id, title, description, location, job_type, "
            "salary_min, salary_max, currency, experience_years, skills, status, created_at, "
            "expires_at, duration_days, "
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
            dur=dur,
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
    finally:
        release_conn(conn)
    # S4: schedule job_expiring_soon 48h before expiry — non-fatal
    if result:
        _expires_str = result.get("expires_at")
        if _expires_str:
            try:
                from datetime import datetime as _dt_j, timezone as _tz_j, timedelta as _td_j
                _expires = _dt_j.fromisoformat(str(_expires_str).replace('Z', '+00:00'))
                if _expires.tzinfo is None:
                    _expires = _expires.replace(tzinfo=_tz_j.utc)
                _hook_at = _expires - _td_j(hours=48)
                _exp_ts = int(_expires.timestamp())
                if _hook_at > _dt_j.now(_tz_j.utc):
                    schedule_job(
                        "job_expiring_soon",
                        {"job_id": result["id"], "expected_expires_at_ts": _exp_ts},
                        _hook_at,
                        f"job_expiring_soon:{result['id']}:{_exp_ts}",
                    )
            except Exception as _sje:
                print(f"[add_job] schedule_job(job_expiring_soon) failed: {_sje}")
    return result

def get_jobs(filters: dict = None) -> list:
    # Company-profile visitor view: show active + paused jobs + closed_count.
    # Global feed (no company_id): active-only, cached.
    has_company_id = bool(filters and filters.get("company_id"))
    cache_key = 'jobs:' + str(sorted((filters or {}).items()))
    if not has_company_id:
        cached = _cache_get(cache_key)
        if cached is not None: return cached

    conn = get_conn()
    try:
        if has_company_id:
            # Visitor company-profile: active + paused (visitor cannot apply to paused)
            where = "WHERE j.status IN ('active','paused')"
        else:
            # Global public feed: active only (also exclude auto-expired via expires_at)
            where = "WHERE j.status='active' AND (j.expires_at IS NULL OR j.expires_at > NOW())"
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
            f"SELECT j.id, j.company_id, j.profession_id, j.title, j.description, j.location, "
            f"j.job_type, j.salary_min, j.salary_max, j.currency, "
            f"j.experience_years, j.skills, j.status, j.views, j.created_at, "
            f"j.expires_at, j.closed_at, j.duration_days, "
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
            d["effective_status"] = _eff_status(
                d.get("status", "active"), d.get("closed_at"), d.get("expires_at")
            )

        if has_company_id:
            # Visitor company-profile:
            # 1. Filter out any auto-closed/expired jobs from the visible list
            visible = [d for d in result if d["effective_status"] in ("active", "paused")]
            auto_closed = len(result) - len(visible)  # jobs DB says active/paused but effectively closed

            # 2. Count manually-closed jobs (status='closed' in DB)
            cid = filters["company_id"]
            cnt_rows = conn.run(
                "SELECT COUNT(*) FROM jobs WHERE company_id=:cid AND status='closed'",
                cid=cid
            )
            db_closed_cnt = cnt_rows[0][0] if cnt_rows else 0

            response = {
                "jobs": visible,
                "count": len(visible),
                "closed_count": db_closed_cnt + auto_closed,
            }
        else:
            response = {"jobs": result, "count": len(result)}
            # Cache the full response dict — same shape on cache hit and cache miss
            _cache_set(cache_key, response)

        return response
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
        result["effective_status"] = _eff_status(
            result.get("status", "active"), result.get("closed_at"), result.get("expires_at")
        )
        return result
    finally:
        release_conn(conn)

def apply_job(job_id: int, user_id: int, cover_letter: str = "") -> dict:
    conn = get_conn()
    try:
        job_rows = conn.run(
            "SELECT status, closed_at, expires_at, company_id, title FROM jobs WHERE id=:jid", jid=job_id
        )
        if not job_rows:
            raise ValueError("الوظيفة غير موجودة")
        eff = _eff_status(job_rows[0][0], job_rows[0][1], job_rows[0][2])
        if eff != 'active':
            raise ValueError("التقديم على هذه الوظيفة غير متاح حالياً")
        job_company_id = int(job_rows[0][3])
        job_title = job_rows[0][4] or ""
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
        result = _serialize(_row_to_dict(cols, rows[0]))
        # V2-3: aggregated job_applied notification (non-fatal)
        try:
            urows = conn.run("SELECT full_name FROM users WHERE id=:uid", uid=user_id)
            applicant_name = urows[0][0] if urows else ""
            if job_company_id != user_id:
                agg_key = f"job_applications_agg:job:{job_id}"
                jt = job_title or "هذه الوظيفة"
                ex_agg = conn.run(
                    "SELECT aggregation_count FROM notifications "
                    "WHERE user_id = :uid AND aggregation_key = :akey AND is_read = FALSE "
                    "ORDER BY created_at DESC LIMIT 1",
                    uid=job_company_id, akey=agg_key
                )
                ex_count = ex_agg[0][0] if ex_agg else 0
                new_count = ex_count + 1
                applicant_display = applicant_name or "متقدم جديد"
                if new_count == 1:
                    notif_title = "متقدم جديد"
                    notif_body = f"{applicant_display} تقدّم على وظيفة \"{jt}\""
                else:
                    notif_title = f"{new_count} متقدمين جدد"
                    notif_body = f"{applicant_name or 'متقدم'} و{new_count - 1} آخرين تقدموا على وظيفة \"{jt}\""
                create_or_update_aggregated_notification(
                    recipient_user_id=job_company_id,
                    type_="job_applied",
                    title=notif_title,
                    body=notif_body,
                    aggregation_key=agg_key,
                    target_type="job",
                    target_id=job_id,
                    actor_id=user_id,
                    action_url=f"/job-detail?id={job_id}",
                    aggregation_kind="job_applied",
                )
        except Exception as _notif_err:
            print(f"[TW-WARN] job_applied notification (job {job_id}) failed: {_notif_err}")
        return result
    finally:
        release_conn(conn)

def get_job_applicants(job_id: int, company_id: int = 0) -> list:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT ja.id, ja.job_id, ja.user_id, ja.status, ja.cover_letter, ja.applied_at, "
            "u.full_name, u.user_type, u.tw_id, "
            "p.avatar_url, "
            "CASE WHEN sc.candidate_id IS NOT NULL THEN true ELSE false END AS is_saved "
            "FROM job_applications ja "
            "JOIN users u ON u.id=ja.user_id "
            "LEFT JOIN profiles p ON p.user_id=ja.user_id "
            "LEFT JOIN company_saved_candidates sc "
            "  ON sc.company_id=:cid AND sc.candidate_id=ja.user_id "
            "WHERE ja.job_id=:jid ORDER BY ja.applied_at DESC",
            jid=job_id, cid=company_id
        )
        cols = [c["name"] for c in conn.columns]
        items = [_serialize(_row_to_dict(cols, r)) for r in rows]

        # Batch-fetch other job refs for saved candidates
        # Source: company_candidate_job_refs (only company-intentional links, not all applications)
        if company_id:
            saved_uids = [a['user_id'] for a in items if a.get('is_saved') and a.get('user_id')]
            other_titles_map = {}
            if saved_uids:
                id_clause = ','.join(str(int(uid)) for uid in saved_uids)
                trows = conn.run(
                    f"SELECT r.candidate_id, j2.title "
                    f"FROM company_candidate_job_refs r "
                    f"JOIN jobs j2 ON j2.id = r.job_id "
                    f"WHERE r.candidate_id IN ({id_clause}) AND r.company_id = :cid "
                    f"AND r.job_id != :jid ORDER BY j2.id",
                    cid=company_id, jid=job_id) or []
                for trow in trows:
                    uid, title = int(trow[0]), trow[1]
                    if uid not in other_titles_map:
                        other_titles_map[uid] = []
                    other_titles_map[uid].append(title)
            for a in items:
                a['other_job_titles'] = other_titles_map.get(a.get('user_id', 0), [])
        else:
            for a in items:
                a['other_job_titles'] = []

        return items
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

def update_application_status(app_id: int, status: str, actor_id: int = None) -> dict:
    applicant_id = None
    job_id = None
    job_title = ""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT ja.user_id, j.id AS job_id, j.title "
            "FROM job_applications ja JOIN jobs j ON j.id = ja.job_id "
            "WHERE ja.id = :id",
            id=app_id
        )
        if rows:
            applicant_id = rows[0][0]
            job_id       = rows[0][1]
            job_title    = rows[0][2] or ""
        conn.run("UPDATE job_applications SET status=:s WHERE id=:id", s=status, id=app_id)
    finally:
        release_conn(conn)
    # All pipeline classification states are internal to the company — no notification to applicant.
    # The only applicant-visible action is a formal appointment invitation via the Appointments system.
    _INTERNAL_STATUSES = {"pending", "viewed", "accepted", "rejected", "contacted", "interview", "hired"}
    if applicant_id and status not in _INTERNAL_STATUSES and (actor_id is None or int(applicant_id) != int(actor_id)):
        _labels = {
            "viewed": ("بدأت مراجعة طلبك", f"بدأت الشركة مراجعة طلبك على وظيفة «{job_title}»"),
        }
        title, body = _labels.get(
            status,
            ("تحديث على طلبك", f"تم تحديث حالة طلبك على وظيفة «{job_title}»")
        )
        link = f"/job-detail?id={job_id}" if job_id else ""
        try:
            create_notification(
                user_id=int(applicant_id),
                type_="application_status_changed",
                title=title,
                body=body,
                link=link,
                actor_id=actor_id,
                entity_id=app_id,
                entity_type="job_application",
                event_key=f"application_status:{app_id}:{status}",
            )
        except Exception as e:
            print(f"[NOTIF] application_status_changed failed for app {app_id}: {e}")
    return {"success": True}

def delete_job(job_id: int, company_id: int) -> bool:
    conn = get_conn()
    try:
        conn.run("DELETE FROM jobs WHERE id=:id AND company_id=:cid", id=job_id, cid=company_id)
        return True
    finally:
        release_conn(conn)

def get_company_jobs_all(company_id: int) -> list:
    """Return all jobs for the authenticated owner — all statuses + effective_status, no cache."""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT j.id, j.company_id, j.title, j.description, j.location, "
            "j.job_type, j.salary_min, j.salary_max, j.currency, "
            "j.experience_years, j.skills, j.status, j.views, j.created_at, "
            "j.expires_at, j.closed_at, j.paused_at, j.duration_days, "
            "COALESCE(j.accepts_all_professions, false) AS accepts_all_professions, "
            "j.profession_id, j.work_mode, "
            "COALESCE(j.salary_hidden, false) AS salary_hidden, "
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
            d["effective_status"]     = _eff_status(
                d.get("status", "active"), d.get("closed_at"), d.get("expires_at")
            )
        return result
    finally:
        release_conn(conn)

def set_job_status(job_id: int, company_id: int, new_status: str) -> None:
    _ALLOWED = ('active', 'paused', 'closed')
    if new_status not in _ALLOWED:
        raise ValueError(f"Invalid status '{new_status}'. Allowed: {_ALLOWED}")

    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT status, closed_at, expires_at, paused_at "
            "FROM jobs WHERE id=:id AND company_id=:cid",
            id=job_id, cid=company_id
        )
        if not rows:
            raise ValueError("الوظيفة غير موجودة أو ليست ملكك")

        cur_status, cur_closed_at, cur_expires_at, cur_paused_at = rows[0]
        eff = _eff_status(cur_status, cur_closed_at, cur_expires_at, cur_paused_at)

        # Block re-opening closed/expired jobs
        if eff in ('closed', 'expired') and new_status in ('active', 'paused'):
            raise ValueError("لا يمكن إعادة فتح إعلان منتهٍ أو انتهت صلاحيته")

        # Block closing an already-closed/expired job
        if eff in ('closed', 'expired') and new_status == 'closed':
            raise ValueError("الإعلان منتهٍ بالفعل")

        # Build UPDATE based on transition
        if new_status == 'paused' and eff == 'active':
            conn.run(
                "UPDATE jobs SET status='paused', paused_at=NOW() WHERE id=:id AND company_id=:cid",
                id=job_id, cid=company_id
            )
        elif new_status == 'active' and eff == 'paused' and cur_paused_at:
            # Resume: extend expires_at by the paused duration so the timer doesn't count paused time
            conn.run(
                "UPDATE jobs SET status='active', paused_at=NULL, "
                "expires_at = expires_at + (NOW() - paused_at) "
                "WHERE id=:id AND company_id=:cid",
                id=job_id, cid=company_id
            )
        elif new_status == 'active' and eff == 'paused':
            # paused_at was NULL (edge case) — just resume without extending
            conn.run(
                "UPDATE jobs SET status='active', paused_at=NULL WHERE id=:id AND company_id=:cid",
                id=job_id, cid=company_id
            )
        elif new_status == 'closed':
            conn.run(
                "UPDATE jobs SET status='closed', closed_at=NOW(), paused_at=NULL "
                "WHERE id=:id AND company_id=:cid",
                id=job_id, cid=company_id
            )
        else:
            # Fallback (same-status no-op or unhandled edge)
            conn.run(
                "UPDATE jobs SET status=:s WHERE id=:id AND company_id=:cid",
                s=new_status, id=job_id, cid=company_id
            )
    finally:
        release_conn(conn)
    _cache_del('jobs:')  # Invalidate public listings immediately


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

def _migrate_notifications_schema_v2():
    """Add actor_id, entity_id, entity_type, event_key columns + unique index (idempotent, Phase 2)."""
    conn = get_conn()
    try:
        conn.run("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        conn.run("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS entity_id INTEGER")
        conn.run("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS entity_type TEXT")
        conn.run("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS event_key TEXT")
        conn.run(
            "CREATE UNIQUE INDEX IF NOT EXISTS uniq_notif_event_key "
            "ON notifications (user_id, event_key) WHERE event_key IS NOT NULL"
        )
    except Exception as e:
        print(f"[migration] notifications_schema_v2 failed: {e}")
        raise
    finally:
        release_conn(conn)


def _migrate_notifications_schema_v2_1():
    """Add aggregation columns + partial index to notifications (idempotent, V2-1)."""
    conn = get_conn()
    try:
        conn.run("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS aggregation_key TEXT")
        conn.run("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS aggregation_count INTEGER DEFAULT 1")
        conn.run("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS aggregation_kind TEXT")
        conn.run("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS last_actor_id INTEGER")
        conn.run("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS last_event_at TIMESTAMPTZ")
        conn.run("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS target_type TEXT")
        conn.run("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS target_id INTEGER")
        conn.run(
            "CREATE INDEX IF NOT EXISTS idx_notifications_aggregation_unread "
            "ON notifications (user_id, aggregation_key, is_read) "
            "WHERE aggregation_key IS NOT NULL"
        )
    except Exception as e:
        print(f"[migration] notifications_schema_v2_1 failed: {e}")
        raise
    finally:
        release_conn(conn)


def create_notification(
    user_id: int, type_: str, title: str, body: str, link: str = "",
    actor_id: int = None, entity_id: int = None, entity_type: str = None,
    event_key: str = None
):
    """Create a notification. Returns the created row dict, or None if event_key already exists (idempotent)."""
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO notifications (user_id, type, title, body, link, actor_id, entity_id, entity_type, event_key) "
            "VALUES (:uid, :type, :title, :body, :link, :actor, :eid, :etype, :ekey) "
            "ON CONFLICT (user_id, event_key) WHERE event_key IS NOT NULL DO NOTHING "
            "RETURNING id, user_id, type, title, body, link, is_read, created_at",
            uid=user_id, type=type_, title=title, body=body, link=link,
            actor=actor_id, eid=entity_id, etype=entity_type, ekey=event_key
        )
        if not rows:
            return None  # duplicate event_key — idempotent skip
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)


def create_or_update_aggregated_notification(
    recipient_user_id: int,
    type_: str,
    title: str,
    body: str,
    aggregation_key: str,
    target_type: str,
    target_id: int,
    actor_id: int = None,
    action_url: str = None,
    payload: dict = None,
    aggregation_kind: str = None,
):
    """
    V2 aggregation helper (V2-1) — creates or updates an aggregated notification.

    Option A — aggregate while unread:
      A. No unread aggregate for (recipient_user_id, aggregation_key):
         → INSERT new notification (aggregation_count=1, is_read=FALSE)
      B. Unread aggregate exists for same key:
         → UPDATE same row (aggregation_count += 1, last_actor_id, last_event_at, title, body)
         → Does NOT create a new row
      C. Previous aggregate was read (is_read=TRUE):
         → Treated as case A — new aggregate starts fresh (count=1)

    No hooks activate this helper in V2-1 — schema + helper only, no active aggregation.

    Returns dict {id, aggregation_count, created: bool} on success, None on failure (error logged).
    payload is accepted for API completeness but not stored until a dedicated column is added.
    """
    conn = get_conn()
    try:
        existing = conn.run(
            "SELECT id, aggregation_count FROM notifications "
            "WHERE user_id = :uid AND aggregation_key = :akey AND is_read = FALSE "
            "ORDER BY created_at DESC LIMIT 1",
            uid=recipient_user_id, akey=aggregation_key
        )
        ex_cols = [c["name"] for c in conn.columns]

        if existing:
            row = _row_to_dict(ex_cols, existing[0])
            new_count = (row.get("aggregation_count") or 1) + 1
            conn.run(
                "UPDATE notifications "
                "SET aggregation_count = :cnt, last_actor_id = :actor, "
                "    last_event_at = NOW(), title = :title, body = :body "
                "WHERE id = :nid",
                cnt=new_count, actor=actor_id, title=title, body=body, nid=row["id"]
            )
            return {"id": row["id"], "aggregation_count": new_count, "created": False}

        rows = conn.run(
            "INSERT INTO notifications "
            "(user_id, type, title, body, link, actor_id, "
            " aggregation_key, aggregation_count, aggregation_kind, "
            " last_actor_id, last_event_at, target_type, target_id) "
            "VALUES (:uid, :type, :title, :body, :url, :actor, "
            "        :akey, 1, :akind, :actor, NOW(), :ttype, :tid) "
            "RETURNING id",
            uid=recipient_user_id, type=type_, title=title, body=body,
            url=action_url or "", actor=actor_id, akey=aggregation_key,
            akind=aggregation_kind or type_, ttype=target_type, tid=target_id
        )
        new_id = rows[0][0] if rows else None
        return {"id": new_id, "aggregation_count": 1, "created": True}

    except Exception as exc:
        print(f"[create_or_update_aggregated_notification] ERROR uid={recipient_user_id} key={aggregation_key}: {exc}")
        return None
    finally:
        release_conn(conn)


def get_notifications(user_id: int, limit: int = 50, offset: int = 0) -> list:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT * FROM notifications WHERE user_id=:uid AND type != 'message' "
            "ORDER BY created_at DESC LIMIT :lim OFFSET :off",
            uid=user_id, lim=limit, off=offset
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

def mark_notification_read(user_id: int, notif_id: int) -> bool:
    """Mark single notification as read — only if it belongs to user_id."""
    conn = get_conn()
    try:
        conn.run(
            "UPDATE notifications SET is_read=TRUE WHERE id=:nid AND user_id=:uid",
            nid=notif_id, uid=user_id
        )
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
        conn.run("ALTER TABLE company_posts ADD COLUMN IF NOT EXISTS theme_color VARCHAR(20) DEFAULT NULL")
        conn.run("ALTER TABLE company_posts ADD COLUMN IF NOT EXISTS comments_enabled BOOLEAN DEFAULT TRUE")
        # ── company_post_views — unique-per-viewer view tracking ──
        conn.run("""
            CREATE TABLE IF NOT EXISTS company_post_views (
                id              SERIAL PRIMARY KEY,
                post_id         INTEGER NOT NULL REFERENCES company_posts(id) ON DELETE CASCADE,
                viewer_user_id  INTEGER REFERENCES users(id) ON DELETE SET NULL,
                visitor_key     VARCHAR(64),
                viewed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.run("CREATE INDEX IF NOT EXISTS idx_post_views_post ON company_post_views(post_id)")
        # Partial unique indexes: one row per logged-in user per post, one per visitor_key per post
        conn.run("CREATE UNIQUE INDEX IF NOT EXISTS uq_post_view_user    ON company_post_views(post_id, viewer_user_id) WHERE viewer_user_id IS NOT NULL")
        conn.run("CREATE UNIQUE INDEX IF NOT EXISTS uq_post_view_visitor ON company_post_views(post_id, visitor_key)     WHERE visitor_key   IS NOT NULL")
        # ── company_post_appreciations — one appreciation per user per post ──
        conn.run("""
            CREATE TABLE IF NOT EXISTS company_post_appreciations (
                id         SERIAL PRIMARY KEY,
                post_id    INTEGER NOT NULL REFERENCES company_posts(id) ON DELETE CASCADE,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.run("CREATE INDEX IF NOT EXISTS idx_post_appr_post ON company_post_appreciations(post_id)")
        conn.run("CREATE UNIQUE INDEX IF NOT EXISTS uq_post_appr_user ON company_post_appreciations(post_id, user_id)")
        # ── company_post_saves — one save per user per post ──
        conn.run("""
            CREATE TABLE IF NOT EXISTS company_post_saves (
                id         SERIAL PRIMARY KEY,
                post_id    INTEGER NOT NULL REFERENCES company_posts(id) ON DELETE CASCADE,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.run("CREATE INDEX IF NOT EXISTS idx_post_saves_post ON company_post_saves(post_id)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_post_saves_user ON company_post_saves(user_id)")
        conn.run("CREATE UNIQUE INDEX IF NOT EXISTS uq_post_save_user ON company_post_saves(post_id, user_id)")
        # ── company_post_comments — threaded comments per post (V1: flat only) ──
        conn.run("""
            CREATE TABLE IF NOT EXISTS company_post_comments (
                id         SERIAL PRIMARY KEY,
                post_id    INTEGER NOT NULL REFERENCES company_posts(id) ON DELETE CASCADE,
                user_id    INTEGER NOT NULL REFERENCES users(id)         ON DELETE CASCADE,
                body       TEXT    NOT NULL,
                status     VARCHAR(20)  NOT NULL DEFAULT 'active',
                created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ,
                deleted_at TIMESTAMPTZ
            )
        """)
        conn.run("CREATE INDEX IF NOT EXISTS idx_post_cmts_post   ON company_post_comments(post_id, created_at)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_post_cmts_user   ON company_post_comments(user_id)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_post_cmts_active ON company_post_comments(post_id, status)")
        # Migration: reply threading V1 — add reply_to_comment_id if not yet present
        try:
            conn.run("ALTER TABLE company_post_comments ADD COLUMN IF NOT EXISTS reply_to_comment_id INTEGER REFERENCES company_post_comments(id) ON DELETE SET NULL")
            conn.run("CREATE INDEX IF NOT EXISTS idx_post_cmts_reply ON company_post_comments(reply_to_comment_id) WHERE reply_to_comment_id IS NOT NULL")
        except Exception as _e_reply:
            print(f"[DB] reply_to_comment_id migration: {_e_reply}")
        # Migration: free mention tw_id — stores the mentioned user's tw_id from autocomplete
        try:
            conn.run("ALTER TABLE company_post_comments ADD COLUMN IF NOT EXISTS mentioned_tw_id VARCHAR(50) DEFAULT NULL")
            conn.run("CREATE INDEX IF NOT EXISTS idx_post_cmts_mentioned ON company_post_comments(mentioned_tw_id) WHERE mentioned_tw_id IS NOT NULL")
        except Exception as _e_ment:
            print(f"[DB] mentioned_tw_id migration: {_e_ment}")
        # Migration: multi-mention junction table — supports multiple @mentions per comment
        try:
            conn.run(
                "CREATE TABLE IF NOT EXISTS company_post_comment_mentions ("
                "id SERIAL PRIMARY KEY, "
                "comment_id INTEGER NOT NULL REFERENCES company_post_comments(id) ON DELETE CASCADE, "
                "mentioned_tw_id VARCHAR(50) NOT NULL, "
                "created_at TIMESTAMPTZ DEFAULT NOW(), "
                "UNIQUE(comment_id, mentioned_tw_id)"
                ")"
            )
            conn.run("CREATE INDEX IF NOT EXISTS idx_cpcm_comment ON company_post_comment_mentions(comment_id)")
        except Exception as _e_multiment:
            print(f"[DB] company_post_comment_mentions migration: {_e_multiment}")
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
        ins_rows = conn.run(
            "INSERT INTO company_follows (company_id, follower_id) VALUES (:cid, :fid) "
            "ON CONFLICT (company_id, follower_id) DO NOTHING RETURNING follower_id",
            cid=company_id, fid=follower_id)
        fc = conn.run("SELECT COUNT(*) FROM company_follows WHERE company_id = :cid",
                      cid=company_id)
        count = fc[0][0] if fc else 0
        # V2-2: aggregated follow notification (non-fatal, fresh follow only)
        if ins_rows:
            if follower_id != company_id:
                try:
                    urows = conn.run(
                        "SELECT full_name, tw_id FROM users WHERE id = :fid", fid=follower_id)
                    crows = conn.run(
                        "SELECT tw_id FROM users WHERE id = :cid", cid=company_id)
                    if urows:
                        follower_name = urows[0][0] or ''
                        company_tw_id = crows[0][0] if crows else ''
                        agg_key = f"follow_agg:company:{company_id}"
                        ex_agg = conn.run(
                            "SELECT aggregation_count FROM notifications "
                            "WHERE user_id = :uid AND aggregation_key = :akey AND is_read = FALSE "
                            "ORDER BY created_at DESC LIMIT 1",
                            uid=company_id, akey=agg_key
                        )
                        ex_count = ex_agg[0][0] if ex_agg else 0
                        new_count = ex_count + 1
                        if new_count == 1:
                            notif_title = "شخص جديد يتابعك"
                            notif_body = f"{follower_name} بدأ بمتابعتك"
                        else:
                            notif_title = f"{new_count} أشخاص يتابعونك"
                            notif_body = f"{follower_name} و{new_count - 1} آخرون بدأوا بمتابعتك"
                        create_or_update_aggregated_notification(
                            recipient_user_id=company_id,
                            type_="follow",
                            title=notif_title,
                            body=notif_body,
                            aggregation_key=agg_key,
                            target_type="company",
                            target_id=company_id,
                            actor_id=follower_id,
                            action_url=f"/u/{company_tw_id}#followers",
                            aggregation_kind="follow",
                        )
                except Exception as _notif_err:
                    print(f"[TW-WARN] follow notification (company {company_id}) failed: {_notif_err}")
        return count
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
    company_tw_id = None
    rating_avg    = None
    rating_count  = 0
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
        rating_avg   = round(float(rt[0][0]), 1) if rt and rt[0][0] is not None else None
        rating_count = rt[0][1] if rt else 0
        tw_rows = conn.run("SELECT tw_id FROM users WHERE id = :cid", cid=company_id)
        if tw_rows:
            company_tw_id = tw_rows[0][0]
    finally:
        release_conn(conn)
    # Notify the company owner after connection is released.
    # event_key rating:{company_id}:{rater_id} is idempotent — UPSERT updates are silent (ON CONFLICT DO NOTHING in create_notification).
    if company_tw_id and int(rater_id) != int(company_id):
        link = f"/u/{company_tw_id}"
        try:
            create_notification(
                user_id=int(company_id),
                type_="rating_received",
                title="وصلك تقييم جديد",
                body=f"قام مستخدم بتقييم شركتك بـ {score} نجوم",
                link=link,
                actor_id=rater_id,
                entity_id=company_id,
                entity_type="company_rating",
                event_key=f"rating:{company_id}:{rater_id}",
            )
        except Exception as e:
            print(f"[NOTIF] rating_received failed for company {company_id}: {e}")
    return {
        "rating_avg":   rating_avg,
        "rating_count": rating_count,
    }


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

def get_company_posts(company_id: int, viewer_user_id=None) -> list:
    """Return all posts for a company, newest first.
    Includes views_count, appreciations_count, viewer_appreciated, and viewer_saved (if viewer_user_id provided)."""
    conn = get_conn()
    try:
        if viewer_user_id:
            rows = conn.run(
                "SELECT cp.id, cp.body, cp.tags, cp.theme_color, cp.comments_enabled, cp.created_at, "
                "COALESCE(v.cnt, 0) AS views_count, "
                "COALESCE(a.cnt, 0) AS appreciations_count, "
                "(upa.user_id IS NOT NULL) AS viewer_appreciated, "
                "(ups.user_id IS NOT NULL) AS viewer_saved, "
                "COALESCE(cmt.cnt, 0) AS comments_count "
                "FROM company_posts cp "
                "LEFT JOIN (SELECT post_id, COUNT(*) AS cnt FROM company_post_views GROUP BY post_id) v ON cp.id = v.post_id "
                "LEFT JOIN (SELECT post_id, COUNT(*) AS cnt FROM company_post_appreciations GROUP BY post_id) a ON cp.id = a.post_id "
                "LEFT JOIN company_post_appreciations upa ON upa.post_id = cp.id AND upa.user_id = :viewer_uid "
                "LEFT JOIN company_post_saves ups ON ups.post_id = cp.id AND ups.user_id = :viewer_uid "
                "LEFT JOIN (SELECT post_id, COUNT(*) AS cnt FROM company_post_comments WHERE status='active' GROUP BY post_id) cmt ON cp.id = cmt.post_id "
                "WHERE cp.company_id = :cid ORDER BY cp.created_at DESC",
                cid=company_id, viewer_uid=int(viewer_user_id))
        else:
            rows = conn.run(
                "SELECT cp.id, cp.body, cp.tags, cp.theme_color, cp.comments_enabled, cp.created_at, "
                "COALESCE(v.cnt, 0) AS views_count, "
                "COALESCE(a.cnt, 0) AS appreciations_count, "
                "FALSE AS viewer_appreciated, "
                "FALSE AS viewer_saved, "
                "COALESCE(cmt.cnt, 0) AS comments_count "
                "FROM company_posts cp "
                "LEFT JOIN (SELECT post_id, COUNT(*) AS cnt FROM company_post_views GROUP BY post_id) v ON cp.id = v.post_id "
                "LEFT JOIN (SELECT post_id, COUNT(*) AS cnt FROM company_post_appreciations GROUP BY post_id) a ON cp.id = a.post_id "
                "LEFT JOIN (SELECT post_id, COUNT(*) AS cnt FROM company_post_comments WHERE status='active' GROUP BY post_id) cmt ON cp.id = cmt.post_id "
                "WHERE cp.company_id = :cid ORDER BY cp.created_at DESC",
                cid=company_id)
        cols = ["id", "body", "tags", "theme_color", "comments_enabled", "created_at",
                "views_count", "appreciations_count", "viewer_appreciated", "viewer_saved",
                "comments_count"]
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


def create_company_post(company_id: int, body: str, tags=None, theme_color=None, comments_enabled=True) -> dict:
    """Insert a post. Returns the created row. body required (non-empty)."""
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO company_posts (company_id, body, tags, theme_color, comments_enabled) "
            "VALUES (:cid, :body, :tags, :tc, :ce) "
            "RETURNING id, body, tags, theme_color, comments_enabled, created_at",
            cid=company_id, body=body, tags=(tags if tags else None), tc=theme_color,
            ce=(comments_enabled if comments_enabled is not None else True))
        cols = ["id", "body", "tags", "theme_color", "comments_enabled", "created_at"]
        return _serialize(_row_to_dict(cols, rows[0])) if rows else {}
    finally:
        release_conn(conn)


def update_company_post(post_id: int, body: str, tags=None, theme_color=None, comments_enabled=True) -> dict:
    """Update body/tags/theme_color/comments_enabled of an existing post. Returns updated row."""
    conn = get_conn()
    try:
        rows = conn.run(
            "UPDATE company_posts SET body=:body, tags=:tags, theme_color=:tc, "
            "comments_enabled=:ce, updated_at=NOW() WHERE id=:pid "
            "RETURNING id, body, tags, theme_color, comments_enabled, created_at",
            body=body, tags=(tags if tags else None), tc=theme_color,
            ce=(comments_enabled if comments_enabled is not None else True), pid=post_id)
        cols = ["id", "body", "tags", "theme_color", "comments_enabled", "created_at"]
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


def record_company_post_view(post_id: int, viewer_user_id=None, visitor_key=None) -> bool:
    """Record a post view. Returns True if a new view was inserted, False if already viewed.
    One of viewer_user_id or visitor_key must be provided.
    Uniqueness is enforced via partial indexes (uq_post_view_user / uq_post_view_visitor)."""
    if not viewer_user_id and not visitor_key:
        return False
    conn = get_conn()
    try:
        if viewer_user_id:
            # Check existing view for this logged-in user
            rows = conn.run(
                "SELECT 1 FROM company_post_views WHERE post_id=:pid AND viewer_user_id=:uid LIMIT 1",
                pid=post_id, uid=viewer_user_id)
            if rows:
                return False
            conn.run(
                "INSERT INTO company_post_views (post_id, viewer_user_id) VALUES (:pid, :uid)",
                pid=post_id, uid=viewer_user_id)
        else:
            # Check existing view for this visitor_key
            rows = conn.run(
                "SELECT 1 FROM company_post_views WHERE post_id=:pid AND visitor_key=:vk LIMIT 1",
                pid=post_id, vk=visitor_key)
            if rows:
                return False
            conn.run(
                "INSERT INTO company_post_views (post_id, visitor_key) VALUES (:pid, :vk)",
                pid=post_id, vk=visitor_key)
        return True
    except Exception:
        return False
    finally:
        release_conn(conn)


def toggle_company_post_appreciation(post_id: int, user_id: int) -> dict:
    """Toggle appreciation for a post. Returns {appreciated, appreciations_count}.
    Uniqueness enforced via uq_post_appr_user index."""
    conn = get_conn()
    try:
        existing = conn.run(
            "SELECT 1 FROM company_post_appreciations WHERE post_id=:pid AND user_id=:uid",
            pid=post_id, uid=user_id)
        if existing:
            conn.run(
                "DELETE FROM company_post_appreciations WHERE post_id=:pid AND user_id=:uid",
                pid=post_id, uid=user_id)
            appreciated = False
        else:
            conn.run(
                "INSERT INTO company_post_appreciations (post_id, user_id) VALUES (:pid, :uid)",
                pid=post_id, uid=user_id)
            appreciated = True
        cnt_rows = conn.run(
            "SELECT COUNT(*) FROM company_post_appreciations WHERE post_id=:pid", pid=post_id)
        count = int(cnt_rows[0][0]) if cnt_rows else 0
        return {"appreciated": appreciated, "appreciations_count": count}
    finally:
        release_conn(conn)


def set_company_post_appreciation(post_id: int, user_id: int, appreciated: bool) -> dict:
    """Idempotent — sets exact appreciation state. No unique-constraint errors.
    appreciated=True  → INSERT ... ON CONFLICT DO NOTHING
    appreciated=False → DELETE (no-op if absent)
    Returns {appreciated, appreciations_count}."""
    conn = get_conn()
    try:
        if appreciated:
            conn.run(
                "INSERT INTO company_post_appreciations (post_id, user_id) "
                "VALUES (:pid, :uid) ON CONFLICT DO NOTHING",
                pid=post_id, uid=user_id)
        else:
            conn.run(
                "DELETE FROM company_post_appreciations WHERE post_id=:pid AND user_id=:uid",
                pid=post_id, uid=user_id)
        cnt_rows = conn.run(
            "SELECT COUNT(*) FROM company_post_appreciations WHERE post_id=:pid", pid=post_id)
        count = int(cnt_rows[0][0]) if cnt_rows else 0
        return {"appreciated": appreciated, "appreciations_count": count}
    finally:
        release_conn(conn)


def set_company_post_save(post_id: int, user_id: int, saved: bool) -> dict:
    """Idempotent — sets exact save state. No unique-constraint errors.
    saved=True  → INSERT ... ON CONFLICT DO NOTHING
    saved=False → DELETE (no-op if absent)
    Returns {saved}."""
    conn = get_conn()
    try:
        if saved:
            conn.run(
                "INSERT INTO company_post_saves (post_id, user_id) "
                "VALUES (:pid, :uid) ON CONFLICT DO NOTHING",
                pid=post_id, uid=user_id)
        else:
            conn.run(
                "DELETE FROM company_post_saves WHERE post_id=:pid AND user_id=:uid",
                pid=post_id, uid=user_id)
        return {"saved": saved}
    finally:
        release_conn(conn)


# ══ Post Comments System ══

_MAX_COMMENT_BODY = 1000


def get_company_post_comments(post_id: int, viewer_user_id=None) -> list:
    """Return active comments for a post, oldest first.
    viewer_user_id controls viewer_can_edit / viewer_can_delete flags."""
    conn = get_conn()
    try:
        post_rows = conn.run("SELECT company_id FROM company_posts WHERE id = :pid", pid=post_id)
        if not post_rows:
            return []
        post_company_id = int(post_rows[0][0])
        rows = conn.run(
            "SELECT c.id, c.body, c.created_at, c.updated_at, "
            "u.full_name, u.tw_id, u.user_type, p.avatar_url, c.user_id, "
            "c.reply_to_comment_id, ru.full_name AS reply_to_author_name, ru.tw_id AS reply_to_author_tw_id, "
            "c.mentioned_tw_id, mu.full_name AS mentioned_author_name "
            "FROM company_post_comments c "
            "JOIN users u ON u.id = c.user_id "
            "LEFT JOIN profiles p ON p.user_id = c.user_id "
            "LEFT JOIN company_post_comments rc ON rc.id = c.reply_to_comment_id "
            "LEFT JOIN users ru ON ru.id = rc.user_id "
            "LEFT JOIN users mu ON mu.tw_id = c.mentioned_tw_id "
            "WHERE c.post_id = :pid AND c.status = 'active' "
            "ORDER BY c.created_at ASC",
            pid=post_id)
        cols = ["id", "body", "created_at", "updated_at",
                "author_name", "author_tw_id", "author_user_type", "author_avatar", "user_id",
                "reply_to_comment_id", "reply_to_author_name", "reply_to_author_tw_id",
                "mentioned_tw_id", "mentioned_author_name"]
        viewer_id = int(viewer_user_id) if viewer_user_id else None
        viewer_is_owner = (viewer_id is not None and viewer_id == post_company_id)
        result = []
        for r in rows:
            d = _serialize(_row_to_dict(cols, r))
            uid = d.get("user_id")
            d["viewer_can_edit"]   = (viewer_id is not None and uid == viewer_id)
            d["viewer_can_delete"] = (viewer_id is not None and (uid == viewer_id or viewer_is_owner))
            result.append(d)
        if not result:
            return result
        # Batch-fetch mentions from junction table and attach to each comment
        comment_ids = [d["id"] for d in result]
        id_placeholders = ", ".join(str(int(cid)) for cid in comment_ids)
        try:
            mrows = conn.run(
                "SELECT m.comment_id, u.full_name, m.mentioned_tw_id "
                "FROM company_post_comment_mentions m "
                "JOIN users u ON u.tw_id = m.mentioned_tw_id "
                "WHERE m.comment_id IN (" + id_placeholders + ") "
                "ORDER BY m.id ASC"
            )
        except Exception:
            mrows = []
        # Build map: comment_id -> [{name, tw_id}]
        mention_map = {}
        for mr in (mrows or []):
            cid = int(mr[0])
            if cid not in mention_map:
                mention_map[cid] = []
            mention_map[cid].append({"name": mr[1] or "", "tw_id": mr[2] or ""})
        for d in result:
            cid = d["id"]
            if cid in mention_map and mention_map[cid]:
                d["mentions"] = mention_map[cid]
            elif d.get("mentioned_tw_id"):
                # Backward compat: old single-mention column
                d["mentions"] = [{"name": d.get("mentioned_author_name") or "", "tw_id": d["mentioned_tw_id"]}]
            else:
                d["mentions"] = []
        return result
    finally:
        release_conn(conn)


def create_company_post_comment(post_id: int, user_id: int, body: str, reply_to_comment_id=None, mentioned_tw_ids=None) -> dict:
    """Create a new active comment. Validates body + checks comments_enabled.
    Optional reply_to_comment_id is resolved to max depth 1 (no nested replies).
    mentioned_tw_ids: list of tw_ids for @mentioned users — each must exist and '@name' must be in body."""
    body = body.strip()
    if not body:
        raise ValueError("التعليق لا يمكن أن يكون فارغاً")
    if len(body) > _MAX_COMMENT_BODY:
        raise ValueError(f"التعليق يتجاوز الحد الأقصى البالغ {_MAX_COMMENT_BODY} حرف")
    conn = get_conn()
    try:
        post_rows = conn.run(
            "SELECT comments_enabled, company_id FROM company_posts WHERE id = :pid", pid=post_id)
        if not post_rows:
            raise ValueError("المنشور غير موجود")
        if post_rows[0][0] is False:
            raise PermissionError("التعليقات معطّلة لهذا المنشور")
        # Validate and resolve reply_to depth (max 1 level)
        resolved_reply_to = None
        reply_to_author_name  = None
        reply_to_author_tw_id = None
        reply_to_author_id    = None
        if reply_to_comment_id is not None:
            ref_rows = conn.run(
                "SELECT id, reply_to_comment_id, post_id, status FROM company_post_comments WHERE id = :cid",
                cid=int(reply_to_comment_id))
            if not ref_rows or ref_rows[0][3] != 'active' or int(ref_rows[0][2]) != post_id:
                raise ValueError("التعليق المرجعي غير موجود أو لا ينتمي لهذا المنشور")
            # If target is itself a reply, resolve to its parent (enforce depth=1)
            if ref_rows[0][1] is not None:
                resolved_reply_to = int(ref_rows[0][1])
                # Verify the resolved root parent is also active and on the same post
                root_rows = conn.run(
                    "SELECT id, post_id, status FROM company_post_comments WHERE id = :cid",
                    cid=resolved_reply_to)
                if not root_rows or root_rows[0][2] != 'active' or int(root_rows[0][1]) != post_id:
                    raise ValueError("التعليق الأصلي غير موجود أو تم حذفه")
            else:
                resolved_reply_to = int(ref_rows[0][0])
            # Fetch author name + tw_id + user_id of the resolved parent comment
            ra_rows = conn.run(
                "SELECT u.full_name, u.tw_id, u.id FROM company_post_comments c "
                "JOIN users u ON u.id = c.user_id WHERE c.id = :cid",
                cid=resolved_reply_to)
            reply_to_author_name  = ra_rows[0][0] if ra_rows else None
            reply_to_author_tw_id = ra_rows[0][1] if ra_rows else None
            reply_to_author_id    = int(ra_rows[0][2]) if ra_rows else None
        # Validate each mentioned_tw_id — user must exist AND '@name' must appear anywhere in body
        resolved_mentions = []
        for mtw_raw in (mentioned_tw_ids or []):
            mtw = str(mtw_raw).strip()
            if not mtw:
                continue
            mrows = conn.run(
                "SELECT id, full_name FROM users WHERE tw_id = :tid", tid=mtw)
            if not mrows:
                raise ValueError("mentioned_tw_id لا يشير لمستخدم موجود")
            m_name = mrows[0][1]
            if ('@' + m_name) not in body:
                raise ValueError("mentioned_tw_id لا يوجد في نص التعليق")
            if not any(r["tw_id"] == mtw for r in resolved_mentions):
                resolved_mentions.append({"name": m_name, "tw_id": mtw, "id": int(mrows[0][0])})
        # ── Atomic transaction: comment + mentions succeed or fail together ──
        # If any mention INSERT fails the whole unit is rolled back — no orphan comments.
        conn.run("BEGIN")
        committed = False
        try:
            rows = conn.run(
                "INSERT INTO company_post_comments (post_id, user_id, body, reply_to_comment_id) "
                "VALUES (:pid, :uid, :body, :rtid) RETURNING id, body, created_at, updated_at, reply_to_comment_id",
                pid=post_id, uid=user_id, body=body, rtid=resolved_reply_to)
            if not rows:
                raise RuntimeError("insert failed")
            new_comment_id = int(rows[0][0])
            for rm in resolved_mentions:
                conn.run(
                    "INSERT INTO company_post_comment_mentions (comment_id, mentioned_tw_id) "
                    "VALUES (:cid, :mtw) ON CONFLICT (comment_id, mentioned_tw_id) DO NOTHING",
                    cid=new_comment_id, mtw=rm["tw_id"])
            conn.run("COMMIT")
            committed = True
        except Exception as _tx_err:
            if not committed:
                try:
                    conn.run("ROLLBACK")
                except Exception:
                    pass
            raise RuntimeError(f"فشل حفظ التعليق والمنشنات: {_tx_err}") from _tx_err
        # ── Post-commit: read-only queries to build return value ──
        cols = ["id", "body", "created_at", "updated_at", "reply_to_comment_id"]
        d = _serialize(_row_to_dict(cols, rows[0]))
        urows = conn.run(
            "SELECT u.full_name, u.tw_id, u.user_type, p.avatar_url "
            "FROM users u LEFT JOIN profiles p ON p.user_id = u.id WHERE u.id = :uid",
            uid=user_id)
        if urows:
            d["author_name"]      = urows[0][0]
            d["author_tw_id"]     = urows[0][1]
            d["author_user_type"] = urows[0][2]
            d["author_avatar"]    = urows[0][3]
        d["user_id"]               = user_id
        d["viewer_can_edit"]       = True
        d["viewer_can_delete"]     = True
        d["reply_to_author_name"]  = reply_to_author_name
        d["reply_to_author_tw_id"] = reply_to_author_tw_id
        d["mentions"]              = resolved_mentions
        # ── Phase 3 + 4: Notification hooks (non-fatal, after COMMIT) ──
        try:
            post_owner_id = int(post_rows[0][1])
            _ntw = conn.run("SELECT tw_id FROM users WHERE id = :uid", uid=post_owner_id)
            _company_tw_id = _ntw[0][0] if _ntw else None
            if _company_tw_id:
                commenter_name = d.get('author_name') or ''
                # V2-4: aggregated comment notification (Phase 3)
                if post_owner_id != user_id:
                    _cmtr = commenter_name or "مستخدم جديد"
                    _cagg_key = f"comments_agg:post:{post_id}"
                    _cex = conn.run(
                        "SELECT aggregation_count FROM notifications "
                        "WHERE user_id = :uid AND aggregation_key = :akey AND is_read = FALSE "
                        "ORDER BY created_at DESC LIMIT 1",
                        uid=post_owner_id, akey=_cagg_key
                    )
                    _cex_count = _cex[0][0] if _cex else 0
                    _cnew = _cex_count + 1
                    if _cnew == 1:
                        _c_title = "تعليق جديد"
                        _c_body  = f"{_cmtr} علّق على منشورك"
                    else:
                        _c_title = f"{_cnew} تعليقات جديدة"
                        _c_body  = f"{_cmtr} و{_cnew - 1} آخرين علّقوا على منشورك"
                    create_or_update_aggregated_notification(
                        recipient_user_id=post_owner_id,
                        type_="comment",
                        title=_c_title,
                        body=_c_body,
                        aggregation_key=_cagg_key,
                        target_type="post",
                        target_id=post_id,
                        actor_id=user_id,
                        action_url=f"/u/{_company_tw_id}#post-{post_id}",
                        aggregation_kind="comment",
                    )
                # V2-4: aggregated reply notification (Phase 4)
                if resolved_reply_to and reply_to_author_id and reply_to_author_id != user_id:
                    _rplr = commenter_name or "مستخدم جديد"
                    _ragg_key = f"replies_agg:comment:{resolved_reply_to}"
                    _rex = conn.run(
                        "SELECT aggregation_count FROM notifications "
                        "WHERE user_id = :uid AND aggregation_key = :akey AND is_read = FALSE "
                        "ORDER BY created_at DESC LIMIT 1",
                        uid=reply_to_author_id, akey=_ragg_key
                    )
                    _rex_count = _rex[0][0] if _rex else 0
                    _rnew = _rex_count + 1
                    if _rnew == 1:
                        _r_title = "رد جديد"
                        _r_body  = f"{_rplr} ردّ على تعليقك"
                    else:
                        _r_title = f"{_rnew} ردود جديدة"
                        _r_body  = f"{_rplr} و{_rnew - 1} آخرين ردّوا على تعليقك"
                    create_or_update_aggregated_notification(
                        recipient_user_id=reply_to_author_id,
                        type_="reply",
                        title=_r_title,
                        body=_r_body,
                        aggregation_key=_ragg_key,
                        target_type="comment",
                        target_id=resolved_reply_to,
                        actor_id=user_id,
                        action_url=f"/u/{_company_tw_id}#comment-{resolved_reply_to}",
                        aggregation_kind="reply",
                    )
                # Phase 5: notify each @mentioned user (skip self-mention)
                for _m in resolved_mentions:
                    _m_uid = _m.get("id")
                    if _m_uid and _m_uid != user_id:
                        create_notification(
                            user_id=_m_uid,
                            type_="mention",
                            title=f"ذكرك {commenter_name} في تعليق",
                            body=body[:60],
                            link=f"/u/{_company_tw_id}#comment-{new_comment_id}",
                            actor_id=user_id,
                            entity_id=new_comment_id,
                            entity_type="comment",
                            event_key=f"mention:comment:{new_comment_id}:{_m_uid}"
                        )
        except Exception as _notif_err:
            print(f"[TW-WARN] notification hook (post {post_id}) failed: {_notif_err}")
        return d
    finally:
        release_conn(conn)


def update_company_post_comment(comment_id: int, user_id: int, body: str) -> dict:
    """Edit a comment — only the comment author may edit."""
    body = body.strip()
    if not body:
        raise ValueError("التعليق لا يمكن أن يكون فارغاً")
    if len(body) > _MAX_COMMENT_BODY:
        raise ValueError(f"التعليق يتجاوز الحد الأقصى البالغ {_MAX_COMMENT_BODY} حرف")
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT user_id, status FROM company_post_comments WHERE id = :cid", cid=comment_id)
        if not rows:
            raise ValueError("التعليق غير موجود")
        owner_id, status = int(rows[0][0]), rows[0][1]
        if status != 'active':
            raise ValueError("التعليق غير موجود")
        if owner_id != user_id:
            raise PermissionError("لا تملك صلاحية تعديل هذا التعليق")
        rows = conn.run(
            "UPDATE company_post_comments SET body=:body, updated_at=NOW() WHERE id=:cid "
            "RETURNING id, body, created_at, updated_at",
            body=body, cid=comment_id)
        if not rows:
            raise RuntimeError("update failed")
        cols = ["id", "body", "created_at", "updated_at"]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)


def delete_company_post_comment(comment_id: int, user_id: int) -> bool:
    """Soft-delete a comment. Allowed for: comment author OR company page owner."""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT c.user_id, c.status, cp.company_id "
            "FROM company_post_comments c "
            "JOIN company_posts cp ON cp.id = c.post_id "
            "WHERE c.id = :cid",
            cid=comment_id)
        if not rows:
            raise ValueError("التعليق غير موجود")
        owner_id, status, company_id = int(rows[0][0]), rows[0][1], int(rows[0][2])
        if status != 'active':
            raise ValueError("التعليق غير موجود")
        if owner_id != user_id and company_id != user_id:
            raise PermissionError("لا تملك صلاحية حذف هذا التعليق")
        conn.run(
            "UPDATE company_post_comments SET status='deleted', deleted_at=NOW() WHERE id=:cid",
            cid=comment_id)
        return True
    finally:
        release_conn(conn)


# ══ Profile Follow System ══

def follow_profile(follower_id: int, followed_id: int) -> int:
    """Follow a profile (idempotent). Returns new followers_count."""
    if follower_id == followed_id:
        raise ValueError("لا يمكنك متابعة نفسك")
    conn = get_conn()
    try:
        ins_rows = conn.run(
            "INSERT INTO profile_follows (follower_id, followed_id) "
            "VALUES (:frid, :fdid) ON CONFLICT (follower_id, followed_id) DO NOTHING RETURNING follower_id",
            frid=follower_id, fdid=followed_id)
        rows = conn.run(
            "SELECT COUNT(*) FROM profile_follows WHERE followed_id = :fdid",
            fdid=followed_id)
        count = rows[0][0] if rows else 0
        # V2-2: aggregated follow notification (non-fatal, fresh follow only)
        if ins_rows:
            if follower_id != followed_id:
                try:
                    urows = conn.run(
                        "SELECT full_name, tw_id FROM users WHERE id = :fid", fid=follower_id)
                    rrows = conn.run(
                        "SELECT tw_id FROM users WHERE id = :rid", rid=followed_id)
                    if urows:
                        follower_name = urows[0][0] or ''
                        recip_tw_id = rrows[0][0] if rrows else ''
                        agg_key = f"follow_agg:user:{followed_id}"
                        ex_agg = conn.run(
                            "SELECT aggregation_count FROM notifications "
                            "WHERE user_id = :uid AND aggregation_key = :akey AND is_read = FALSE "
                            "ORDER BY created_at DESC LIMIT 1",
                            uid=followed_id, akey=agg_key
                        )
                        ex_count = ex_agg[0][0] if ex_agg else 0
                        new_count = ex_count + 1
                        if new_count == 1:
                            notif_title = "شخص جديد يتابعك"
                            notif_body = f"{follower_name} بدأ بمتابعتك"
                        else:
                            notif_title = f"{new_count} أشخاص يتابعونك"
                            notif_body = f"{follower_name} و{new_count - 1} آخرون بدأوا بمتابعتك"
                        create_or_update_aggregated_notification(
                            recipient_user_id=followed_id,
                            type_="follow",
                            title=notif_title,
                            body=notif_body,
                            aggregation_key=agg_key,
                            target_type="user",
                            target_id=followed_id,
                            actor_id=follower_id,
                            action_url=f"/u/{recip_tw_id}#followers",
                            aggregation_kind="follow",
                        )
                except Exception as _notif_err:
                    print(f"[TW-WARN] follow notification (profile {followed_id}) failed: {_notif_err}")
        return count
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


def _migrate_company_candidate_job_refs():
    """Create company_candidate_job_refs junction table (idempotent).

    Records every company-initiated intentional link between a saved candidate
    and a specific job. Populated on save (with job_id) and on promote.
    This is the authoritative source for job_titles[] in saved candidate
    and applicant responses — job_applications is NOT used for this purpose.
    """
    conn = get_conn()
    try:
        conn.run("""
            CREATE TABLE IF NOT EXISTS company_candidate_job_refs (
                company_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                job_id       INTEGER NOT NULL REFERENCES jobs(id)  ON DELETE CASCADE,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (company_id, candidate_id, job_id)
            )
        """)
        conn.run("""
            CREATE INDEX IF NOT EXISTS idx_ccjr_company_candidate
            ON company_candidate_job_refs(company_id, candidate_id)
        """)
        # Backfill existing saved candidates that already have a job_id
        conn.run("""
            INSERT INTO company_candidate_job_refs(company_id, candidate_id, job_id)
            SELECT company_id, candidate_id, job_id
            FROM company_saved_candidates
            WHERE job_id IS NOT NULL
            ON CONFLICT DO NOTHING
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
        if job_id is not None:
            # Atomic: both writes succeed or both roll back
            conn.run("BEGIN")
            committed = False
            try:
                conn.run(
                    "INSERT INTO company_saved_candidates "
                    "(company_id, candidate_id, job_id, notes, saved_by) "
                    "VALUES (:cid, :uid, :jid, :notes, :sid) "
                    "ON CONFLICT (company_id, candidate_id) DO UPDATE "
                    "SET updated_at=NOW(), notes=EXCLUDED.notes",
                    cid=company_id, uid=candidate_id,
                    jid=job_id, notes=notes, sid=saved_by)
                conn.run(
                    "INSERT INTO company_candidate_job_refs "
                    "(company_id, candidate_id, job_id) "
                    "VALUES (:cid, :uid, :jid) "
                    "ON CONFLICT DO NOTHING",
                    cid=company_id, uid=candidate_id, jid=job_id)
                conn.run("COMMIT")
                committed = True
            except Exception:
                if not committed:
                    try:
                        conn.run("ROLLBACK")
                    except Exception:
                        pass
                raise
        else:
            conn.run(
                "INSERT INTO company_saved_candidates "
                "(company_id, candidate_id, job_id, notes, saved_by) "
                "VALUES (:cid, :uid, :jid, :notes, :sid) "
                "ON CONFLICT (company_id, candidate_id) DO UPDATE "
                "SET updated_at=NOW(), notes=EXCLUDED.notes",
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

        # Batch-fetch job titles + rich job_links from company_candidate_job_refs
        if items:
            id_clause = ','.join(str(r['candidate_id']) for r in items)
            trows = conn.run(
                f"SELECT r.candidate_id, j.id, j.title, ja.applied_at, ja.status "
                f"FROM company_candidate_job_refs r "
                f"JOIN jobs j ON j.id = r.job_id "
                f"LEFT JOIN job_applications ja ON ja.job_id = j.id AND ja.user_id = r.candidate_id "
                f"WHERE r.candidate_id IN ({id_clause}) AND r.company_id = :cid "
                f"ORDER BY j.id",
                cid=company_id) or []
            jtmap = {}
            jlmap = {}
            for trow in trows:
                uid  = int(trow[0])
                jid, title, apply_date, app_status = int(trow[1]), trow[2], trow[3], trow[4]
                if uid not in jtmap:
                    jtmap[uid] = []
                    jlmap[uid] = []
                jtmap[uid].append(title)
                jlmap[uid].append({
                    'job_id':     jid,
                    'title':      title,
                    'apply_date': apply_date.isoformat() if apply_date else None,
                    'status':     app_status or None,
                })
            for item in items:
                item['job_titles'] = jtmap.get(item['candidate_id'], [])
                item['job_links']  = jlmap.get(item['candidate_id'], [])

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

# Numeric rank for "don't downgrade" logic in promote_application_to_shortlist.
# rejected is absent intentionally — it's checked as a Conflict before rank comparison.
_CANDIDATE_STATUS_RANK = {
    "saved":       1,
    "shortlisted": 2,
    "contacted":   3,
    "interview":   4,
    "hired":       5,
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
            where_parts.append(
                "EXISTS (SELECT 1 FROM company_candidate_job_refs r "
                "WHERE r.company_id = sc.company_id "
                "AND r.candidate_id = sc.candidate_id "
                "AND r.job_id = :job_id)"
            )
            params["job_id"] = job_id
        elif unlinked:
            where_parts.append(
                "NOT EXISTS (SELECT 1 FROM company_candidate_job_refs r "
                "WHERE r.company_id = sc.company_id "
                "AND r.candidate_id = sc.candidate_id)"
            )

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

        # Batch-fetch job titles + rich job_links from refs + per_job_accepted
        if items:
            id_clause = ','.join(str(r['candidate_id']) for r in items)
            trows = conn.run(
                f"SELECT r.candidate_id, j.id, j.title, ja.applied_at, ja.status "
                f"FROM company_candidate_job_refs r "
                f"JOIN jobs j ON j.id = r.job_id "
                f"LEFT JOIN job_applications ja ON ja.job_id = j.id AND ja.user_id = r.candidate_id "
                f"WHERE r.candidate_id IN ({id_clause}) AND r.company_id = :cid "
                f"ORDER BY j.id",
                cid=company_id) or []
            jtmap = {}
            jlmap = {}
            for trow in trows:
                uid  = int(trow[0])
                jid, title, apply_date, app_status = int(trow[1]), trow[2], trow[3], trow[4]
                if uid not in jtmap:
                    jtmap[uid] = []
                    jlmap[uid] = []
                jtmap[uid].append(title)
                jlmap[uid].append({
                    'job_id':     jid,
                    'title':      title,
                    'apply_date': apply_date.isoformat() if apply_date else None,
                    'status':     app_status or None,
                })
            accepted_ids = set()
            if job_id is not None:
                acc_rows = conn.run(
                    f"SELECT ja.user_id "
                    f"FROM job_applications ja "
                    f"WHERE ja.job_id = :jid AND ja.status = 'accepted' "
                    f"AND ja.user_id IN ({id_clause})",
                    jid=job_id) or []
                accepted_ids = {int(r[0]) for r in acc_rows}
            for item in items:
                item['job_titles'] = jtmap.get(item['candidate_id'], [])
                item['job_links']  = jlmap.get(item['candidate_id'], [])
                if job_id is not None:
                    item['per_job_accepted'] = item['candidate_id'] in accepted_ids

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

        # Total, with_job, unlinked — derived from refs table for consistency with filters
        summary_row = conn.run(
            "SELECT COUNT(*), "
            "COUNT(*) FILTER (WHERE EXISTS ("
            "  SELECT 1 FROM company_candidate_job_refs r "
            "  WHERE r.company_id = sc.company_id AND r.candidate_id = sc.candidate_id"
            ")), "
            "COUNT(*) FILTER (WHERE NOT EXISTS ("
            "  SELECT 1 FROM company_candidate_job_refs r "
            "  WHERE r.company_id = sc.company_id AND r.candidate_id = sc.candidate_id"
            ")) "
            "FROM company_saved_candidates sc WHERE sc.company_id = :cid",
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


def promote_application_to_shortlist(app_id: int, company_id: int) -> dict:
    """
    Atomic business operation: mark application 'accepted' + UPSERT candidate to 'shortlisted'.

    All critical reads happen INSIDE BEGIN with FOR UPDATE row locks — no race condition.
    Both writes complete atomically or roll back together — no partial state.

    UPSERT always runs (not gated on skip logic). RETURNING is the authoritative final state.
    This closes the race where a concurrent INSERT with status='rejected' could slip through
    while no candidate row existed to lock with FOR UPDATE.

    Status policy (candidate):
      • not saved / saved / shortlisted → promoted to 'shortlisted'   (action: created|updated|unchanged)
      • contacted / interview / hired   → application accepted, candidate status preserved  (action: unchanged)
      • rejected (existing row)         → pre-UPSERT check → ROLLBACK → HTTP 409
      • rejected (RETURNING after race) → post-UPSERT check BEFORE COMMIT → ROLLBACK → HTTP 409

    Defense in depth: UPSERT CASE in DO UPDATE independently preserves higher/rejected statuses
    at the SQL layer, regardless of application-level state.

    Idempotent: repeated calls succeed; `action` field reports what actually changed.

    Raises:
      KeyError        → app_id not found (→ 404)
      PermissionError → caller doesn't own the job (→ 403)
      ValueError      → applicant not emp, or candidate is rejected (→ 409)
      RuntimeError    → unexpected DB error (→ 500)
    """
    conn = get_conn()
    try:
        conn.run("BEGIN")
        committed = False
        try:
            # ── 1. Lock application row + fetch ownership/type inside transaction ──
            # FOR UPDATE OF ja prevents concurrent promotes on the same application.
            rows = conn.run(
                "SELECT ja.user_id, ja.job_id, ja.status, j.company_id, u.user_type "
                "FROM job_applications ja "
                "JOIN jobs j ON j.id = ja.job_id "
                "JOIN users u ON u.id = ja.user_id "
                "WHERE ja.id = :id "
                "FOR UPDATE OF ja",
                id=app_id)
            if not rows:
                raise KeyError("الطلب غير موجود")

            applicant_id, job_id, _app_status, job_company_id, applicant_type = rows[0]

            if int(job_company_id) != int(company_id):
                raise PermissionError("غير مصرح — هذا الطلب ليس لوظيفة شركتك")

            if applicant_type != "emp":
                raise ValueError("المتقدم ليس موظفاً — لا يمكن ترقيته للـ pipeline")

            # ── 2. Lock candidate row (if exists) inside transaction ──
            # FOR UPDATE prevents concurrent PATCH on the existing row.
            # NOTE: FOR UPDATE cannot lock a non-existent row — concurrent INSERT-as-rejected
            # is handled by the post-UPSERT RETURNING check in step 6.
            cand_rows = conn.run(
                "SELECT id, status "
                "FROM company_saved_candidates "
                "WHERE company_id = :cid AND candidate_id = :uid "
                "FOR UPDATE",
                cid=company_id, uid=applicant_id)
            current_cand_status = cand_rows[0][1] if cand_rows else None

            # ── 3. Pre-UPSERT rejected check (fast path for existing rejected row) ──
            if current_cand_status == "rejected":
                raise ValueError(
                    "المرشح محدد كـ'غير مناسب' — يجب تغيير حالته يدوياً قبل الترقية")

            # ── 4. Always mark application as accepted ──
            conn.run(
                "UPDATE job_applications SET status = 'accepted' WHERE id = :id",
                id=app_id)

            # ── 5. UPSERT always runs — RETURNING is the authoritative final state ──
            # Rationale: FOR UPDATE cannot lock a non-existent row.
            # A concurrent writer could INSERT status='rejected' between step 2 and here.
            # The CASE in DO UPDATE preserves rejected/higher statuses at the SQL layer.
            # (xmax = 0) is true when a fresh INSERT happened; false when DO UPDATE ran.
            upsert_rows = conn.run(
                "INSERT INTO company_saved_candidates "
                "  (company_id, candidate_id, job_id, saved_by, status) "
                "VALUES (:cid, :uid, :jid, :cid, 'shortlisted') "
                "ON CONFLICT (company_id, candidate_id) DO UPDATE SET "
                "  status = CASE "
                "    WHEN company_saved_candidates.status "
                "         IN ('contacted','interview','hired','rejected') "
                "    THEN company_saved_candidates.status "
                "    ELSE 'shortlisted' "
                "  END, "
                "  updated_at = NOW() "
                "RETURNING status, (xmax = 0) AS was_inserted",
                cid=company_id, uid=applicant_id, jid=job_id)

            if not upsert_rows:
                raise RuntimeError(
                    f"UPSERT لم يُرجع نتيجة — حالة غير متوقعة "
                    f"(app={app_id}, candidate={applicant_id})")

            final_status = upsert_rows[0][0]
            was_inserted = upsert_rows[0][1]

            # ── 6. Post-UPSERT, pre-COMMIT: RETURNING is the authoritative decision ──
            # Catches race: concurrent INSERT-as-rejected while no row existed to lock.
            # Application update (step 4) will be rolled back with the transaction.
            if final_status == "rejected":
                raise ValueError(
                    "المرشح محدد كـ'غير مناسب' (تعارض متزامن) — يجب تغيير حالته يدوياً")

            # ── 6.5. Record company-job link in refs table (inside transaction) ──
            # This is the authoritative write for job_titles[] in saved candidate views.
            conn.run(
                "INSERT INTO company_candidate_job_refs "
                "(company_id, candidate_id, job_id) "
                "VALUES (:cid, :uid, :jid) "
                "ON CONFLICT DO NOTHING",
                cid=company_id, uid=applicant_id, jid=job_id)

            conn.run("COMMIT")
            committed = True

        except (KeyError, PermissionError, ValueError):
            # Known, expected exceptions — ROLLBACK then re-raise as-is
            # so the endpoint maps them to the correct HTTP status.
            if not committed:
                try:
                    conn.run("ROLLBACK")
                except Exception:
                    pass
            raise

        except Exception as _tx_err:
            # Unexpected DB failure — ROLLBACK then wrap for HTTP 500
            if not committed:
                try:
                    conn.run("ROLLBACK")
                except Exception:
                    pass
            raise RuntimeError(f"فشلت عملية الترقية: {_tx_err}") from _tx_err

        # ── 7. Compute action from locked pre-state + RETURNING result ──
        # was_inserted=True → fresh row (no prior row existed)
        # was_inserted=False + status changed → DO UPDATE ran and status moved up
        # was_inserted=False + status same → DO UPDATE ran but CASE preserved existing
        if was_inserted:
            candidate_action = "created"
        elif final_status == current_cand_status:
            candidate_action = "unchanged"
        else:
            candidate_action = "updated"

        return {
            "application": {
                "id":     app_id,
                "status": "accepted",
            },
            "candidate": {
                "candidate_id": int(applicant_id),
                "status":       final_status,
                "status_label": CANDIDATE_STATUS_LABELS.get(final_status, final_status),
                "action":       candidate_action,
            },
        }
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


# ══════════════════════════════════════════════════════════════════════════
# Appointments & Interview Rooms System — Phase 1: Schema + Migration
# Phase 0 plan: docs/APPOINTMENTS_PLAN.md
# No endpoints, no business logic, no notifications — schema only.
# Status values: draft|pending_response|reschedule_requested|confirmed|
#                cancelled|expired|missed|completed|closed
# Mode values:   online|onsite
# Participant roles: company|applicant|representative
# Event types: appointment_created|appointment_sent|appointment_accepted|
#              appointment_reschedule_requested|appointment_rescheduled|
#              appointment_confirmed|appointment_cancelled|appointment_expired|
#              appointment_completed|appointment_closed|message_sent
# ══════════════════════════════════════════════════════════════════════════

def _migrate_appointments():
    """
    Create appointments system tables (idempotent — safe to run multiple times).

    Tables created:
      - appointments               : core scheduling record
      - appointment_participants   : parties to each appointment
      - appointment_events         : immutable audit trail (F18/F27 — never hard-deleted)
      - appointment_messages       : appointment-specific thread (separate from Messenger)

    Foreign keys follow the project pattern (ON DELETE CASCADE / SET NULL).
    No endpoints, no business logic, no notifications in this migration.
    """
    conn = get_conn()
    try:
        # ── 1. appointments ──────────────────────────────────────────────
        conn.run("""
            CREATE TABLE IF NOT EXISTS appointments (
                id                    SERIAL PRIMARY KEY,
                job_id                INTEGER NULL
                                          REFERENCES jobs(id) ON DELETE SET NULL,
                application_id        INTEGER NULL
                                          REFERENCES job_applications(id) ON DELETE SET NULL,
                company_id            INTEGER NOT NULL
                                          REFERENCES users(id) ON DELETE CASCADE,
                applicant_id          INTEGER NOT NULL
                                          REFERENCES users(id) ON DELETE CASCADE,
                created_by            INTEGER NOT NULL
                                          REFERENCES users(id) ON DELETE CASCADE,
                representative_user_id INTEGER NULL
                                          REFERENCES users(id) ON DELETE SET NULL,
                representative_name   TEXT NULL,
                status                TEXT NOT NULL DEFAULT 'draft',
                mode                  TEXT NOT NULL DEFAULT 'online',
                scheduled_at          TIMESTAMPTZ NULL,
                response_deadline_at  TIMESTAMPTZ NULL,
                location_text         TEXT NULL,
                online_url            TEXT NULL,
                notes                 TEXT NULL,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                closed_at             TIMESTAMPTZ NULL
            )
        """)

        # ── 2. appointment_participants ───────────────────────────────────
        conn.run("""
            CREATE TABLE IF NOT EXISTS appointment_participants (
                id             SERIAL PRIMARY KEY,
                appointment_id INTEGER NOT NULL
                                   REFERENCES appointments(id) ON DELETE CASCADE,
                user_id        INTEGER NOT NULL
                                   REFERENCES users(id) ON DELETE CASCADE,
                role           TEXT NOT NULL,
                can_message    BOOLEAN NOT NULL DEFAULT TRUE,
                can_decide     BOOLEAN NOT NULL DEFAULT FALSE,
                created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_appt_participant UNIQUE (appointment_id, user_id)
            )
        """)

        # ── 3. appointment_events (immutable audit trail — F18/F27) ──────
        conn.run("""
            CREATE TABLE IF NOT EXISTS appointment_events (
                id             SERIAL PRIMARY KEY,
                appointment_id INTEGER NOT NULL
                                   REFERENCES appointments(id) ON DELETE CASCADE,
                actor_id       INTEGER NULL
                                   REFERENCES users(id) ON DELETE SET NULL,
                event_type     TEXT NOT NULL,
                old_status     TEXT NULL,
                new_status     TEXT NULL,
                payload        JSONB NULL,
                created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # ── 4. appointment_messages ───────────────────────────────────────
        # Separate from Messenger العام — scoped to a single appointment.
        # Soft delete via deleted_at (F27) — no hard deletes.
        conn.run("""
            CREATE TABLE IF NOT EXISTS appointment_messages (
                id             SERIAL PRIMARY KEY,
                appointment_id INTEGER NOT NULL
                                   REFERENCES appointments(id) ON DELETE CASCADE,
                sender_id      INTEGER NOT NULL
                                   REFERENCES users(id) ON DELETE CASCADE,
                body           TEXT NOT NULL,
                created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                edited_at      TIMESTAMPTZ NULL,
                deleted_at     TIMESTAMPTZ NULL
            )
        """)

        # ── Indexes: appointments ─────────────────────────────────────────
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_company    ON appointments(company_id)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_applicant  ON appointments(applicant_id)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_application ON appointments(application_id)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_job        ON appointments(job_id)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_status     ON appointments(status)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_scheduled  ON appointments(scheduled_at)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_deadline   ON appointments(response_deadline_at)")

        # ── Indexes: appointment_participants ─────────────────────────────
        # UNIQUE constraint on (appointment_id, user_id) already creates an index;
        # add a separate user_id index for reverse lookups (all appointments of a user).
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_part_appt  ON appointment_participants(appointment_id)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_part_user  ON appointment_participants(user_id)")

        # ── Indexes: appointment_events ───────────────────────────────────
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_evt_appt   ON appointment_events(appointment_id)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_evt_type   ON appointment_events(event_type)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_evt_created ON appointment_events(created_at)")

        # ── Indexes: appointment_messages ─────────────────────────────────
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_msg_appt   ON appointment_messages(appointment_id)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_msg_created ON appointment_messages(created_at)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_appt_msg_sender  ON appointment_messages(sender_id)")

    finally:
        release_conn(conn)



# ══════════════════════════════════════════════════════════════════════════
# Appointments & Interview Rooms System — Phase 2: Backend Helpers + Phase 7: Notifications
# ══════════════════════════════════════════════════════════════════════════

_APPT_VALID_STATUSES = {
    'draft', 'pending_response', 'reschedule_requested', 'confirmed',
    'cancelled', 'expired', 'missed', 'completed', 'closed'
}
_APPT_TERMINAL_STATUSES = {'cancelled', 'expired', 'missed', 'closed'}
_APPT_VALID_MODES = {'online', 'onsite'}
_APPT_DEADLINE_HOURS_ALLOWED = {24, 48, 72, 168}


def _insert_appointment_event(conn, appointment_id: int, actor_id, event_type: str,
                               old_status=None, new_status=None, payload=None):
    """Insert immutable event into appointment_events. Caller owns the connection (F18/F27)."""
    payload_str = _json_mod.dumps(payload) if payload else None
    conn.run(
        """INSERT INTO appointment_events
           (appointment_id, actor_id, event_type, old_status, new_status, payload)
           VALUES (:appt, :actor, :etype, :old, :new,
                   CASE WHEN :payload IS NULL THEN NULL ELSE :payload::jsonb END)""",
        appt=appointment_id, actor=actor_id, etype=event_type,
        old=old_status, new=new_status, payload=payload_str
    )


def _check_appt_participant(conn, appointment_id: int, user_id: int) -> dict:
    """Returns {role, can_message, can_decide} if participant, else raises PermissionError."""
    rows = conn.run(
        """SELECT role, can_message, can_decide
           FROM appointment_participants
           WHERE appointment_id = :appt AND user_id = :uid""",
        appt=appointment_id, uid=user_id
    )
    if not rows:
        raise PermissionError("غير مصرح: لست طرفاً في هذا الموعد")
    return {"role": rows[0][0], "can_message": rows[0][1], "can_decide": rows[0][2]}


def _get_appointment_row(conn, appointment_id: int):
    """Fetch single appointment row as dict, or None."""
    rows = conn.run(
        """SELECT id, job_id, application_id, company_id, applicant_id, created_by,
                  representative_user_id, representative_name, status, mode,
                  scheduled_at, response_deadline_at, location_text, online_url,
                  notes, created_at, updated_at, closed_at
           FROM appointments WHERE id = :id""",
        id=appointment_id
    )
    if not rows:
        return None
    cols = ["id","job_id","application_id","company_id","applicant_id","created_by",
            "representative_user_id","representative_name","status","mode",
            "scheduled_at","response_deadline_at","location_text","online_url",
            "notes","created_at","updated_at","closed_at"]
    return _serialize(_row_to_dict(cols, rows[0]))


def _appt_computed_status(appt: dict) -> str:
    """
    Returns computed status: if pending_response and deadline passed → 'expired'.
    Does NOT write to DB (no scheduler). Read-time computation only.
    """
    from datetime import datetime as _dt, timezone as _tz
    status = appt.get('status', '')
    if status == 'pending_response':
        deadline = appt.get('response_deadline_at')
        if deadline:
            if isinstance(deadline, str):
                try:
                    deadline_dt = _dt.fromisoformat(deadline.replace('Z', '+00:00'))
                    if deadline_dt.tzinfo is None:
                        deadline_dt = deadline_dt.replace(tzinfo=_tz.utc)
                except Exception:
                    return status
            else:
                deadline_dt = deadline
                if hasattr(deadline_dt, 'tzinfo') and deadline_dt.tzinfo is None:
                    deadline_dt = deadline_dt.replace(tzinfo=_tz.utc)
            if _dt.now(_tz.utc) > deadline_dt:
                return 'expired'
    return status


def create_appointment(company_user_id: int, application_id: int,
                       mode: str = "online", notes: str = None,
                       online_url: str = None, location_text: str = None,
                       representative_name: str = None) -> dict:
    """Create appointment in status=draft. Company users only.
    applicant_id and job_id are derived from job_applications — never trusted from caller."""
    if mode not in _APPT_VALID_MODES:
        raise ValueError(f"نوع الموعد غير صالح: {mode}")
    if online_url:
        if not online_url.startswith("https://"):
            raise ValueError("رابط المقابلة يجب أن يبدأ بـ https://")
        online_url = online_url.strip()[:2000]
    if notes:
        notes = notes.strip()[:1000]
    if location_text:
        location_text = location_text.strip()[:500]
    if representative_name:
        representative_name = representative_name.strip()[:200]

    conn = get_conn()
    committed = False
    try:
        # Derive applicant_id and job_id from the actual job_applications row
        app_rows = conn.run(
            "SELECT id, user_id, job_id FROM job_applications WHERE id = :id",
            id=application_id
        )
        if not app_rows:
            raise ValueError("طلب التوظيف غير موجود")
        applicant_id = app_rows[0][1]
        job_id = app_rows[0][2]

        # Verify that this company owns the job — F6: backend owns permissions
        job_rows = conn.run(
            "SELECT company_id FROM jobs WHERE id = :id", id=job_id
        )
        if not job_rows:
            raise ValueError("الوظيفة غير موجودة")
        db_company_id = job_rows[0][0]
        if int(db_company_id) != int(company_user_id):
            raise PermissionError("غير مصرح: هذه الوظيفة لا تخص شركتك")

        # Verify applicant is an employee
        u_rows = conn.run("SELECT id, user_type FROM users WHERE id = :id", id=applicant_id)
        if not u_rows:
            raise ValueError("المتقدم غير موجود")
        if u_rows[0][1] != 'emp':
            raise ValueError("المستخدم المحدد ليس موظفاً")

        # Duplicate guard per application_id (not per job+applicant pair)
        dup = conn.run(
            """SELECT id FROM appointments
               WHERE application_id = :appid
                 AND status NOT IN ('cancelled','expired','missed','closed')
               LIMIT 1""",
            appid=application_id
        )
        if dup:
            raise ValueError("يوجد موعد نشط لهذا الطلب")

        conn.run("BEGIN")
        rows = conn.run(
            """INSERT INTO appointments
               (company_id, applicant_id, created_by, job_id, application_id,
                mode, representative_name, notes,
                online_url, location_text, status)
               VALUES (:cid, :aid, :cb, :jid, :appid, :mode,
                       :rep_name, :notes, :url, :loc, 'draft')
               RETURNING id""",
            cid=company_user_id, aid=applicant_id, cb=company_user_id,
            jid=job_id, appid=application_id, mode=mode,
            rep_name=representative_name,
            notes=notes, url=online_url, loc=location_text
        )
        appt_id = rows[0][0]

        conn.run(
            """INSERT INTO appointment_participants
               (appointment_id, user_id, role, can_message, can_decide)
               VALUES (:appt, :uid, 'company', TRUE, TRUE)
               ON CONFLICT (appointment_id, user_id) DO NOTHING""",
            appt=appt_id, uid=company_user_id
        )
        conn.run(
            """INSERT INTO appointment_participants
               (appointment_id, user_id, role, can_message, can_decide)
               VALUES (:appt, :uid, 'applicant', TRUE, TRUE)
               ON CONFLICT (appointment_id, user_id) DO NOTHING""",
            appt=appt_id, uid=applicant_id
        )

        _insert_appointment_event(conn, appt_id, company_user_id,
                                   'appointment_created', new_status='draft')
        result = _get_appointment_row(conn, appt_id)
        conn.run("COMMIT")
        committed = True
        return result
    except Exception:
        if not committed:
            try:
                conn.run("ROLLBACK")
            except Exception:
                pass
        raise
    finally:
        release_conn(conn)


def send_appointment(appointment_id: int, user_id: int, scheduled_at_iso: str,
                     deadline_hours: int = 48, online_url: str = None,
                     location_text: str = None, notes: str = None,
                     representative_name: str = None) -> dict:
    """Send invitation: draft → pending_response. Company only."""
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    if deadline_hours not in _APPT_DEADLINE_HOURS_ALLOWED:
        raise ValueError("مهلة الرد: 24 أو 48 أو 72 أو 168 ساعة فقط")
    if online_url:
        if not online_url.startswith("https://"):
            raise ValueError("رابط المقابلة يجب أن يبدأ بـ https://")
        online_url = online_url.strip()[:2000]
    if notes:
        notes = notes.strip()[:1000]
    if location_text:
        location_text = location_text.strip()[:500]
    if representative_name:
        representative_name = representative_name.strip()[:200]

    appt_result = None
    notify_payload = None
    deadline_for_hook = None
    conn = get_conn()
    try:
        appt = _get_appointment_row(conn, appointment_id)
        if not appt:
            raise ValueError("الموعد غير موجود")
        if appt['company_id'] != user_id:
            raise PermissionError("غير مصرح: فقط الشركة المنشئة يمكنها إرسال الدعوة")
        if appt['status'] != 'draft':
            raise ValueError(f"لا يمكن إرسال موعد بحالة '{appt['status']}'")

        # mode-required field validation — backend is source of truth (F6/F21)
        effective_url = online_url or appt.get('online_url')
        effective_loc = location_text or appt.get('location_text')
        if appt['mode'] == 'online' and not effective_url:
            raise ValueError("رابط المقابلة مطلوب للمواعيد الأونلاين")
        if appt['mode'] == 'onsite' and not effective_loc:
            raise ValueError("موقع المقابلة مطلوب للمواعيد الحضورية")

        try:
            scheduled_dt = _dt.fromisoformat(scheduled_at_iso.replace('Z', '+00:00'))
            if scheduled_dt.tzinfo is None:
                scheduled_dt = scheduled_dt.replace(tzinfo=_tz.utc)
        except Exception:
            raise ValueError("تنسيق التاريخ غير صالح — استخدم ISO 8601")

        now_utc = _dt.now(_tz.utc)
        if scheduled_dt <= now_utc:
            raise ValueError("وقت الموعد يجب أن يكون في المستقبل")

        deadline_dt = now_utc + _td(hours=deadline_hours)
        if deadline_dt >= scheduled_dt:
            raise ValueError("مهلة الرد تنتهي بعد وقت الموعد — اختر مهلة أقصر أو موعداً أبعد")

        conn.run(
            """UPDATE appointments
               SET status='pending_response', scheduled_at=:sched,
                   response_deadline_at=:deadline,
                   online_url=COALESCE(:url, online_url),
                   location_text=COALESCE(:loc, location_text),
                   notes=COALESCE(:notes, notes),
                   representative_name=COALESCE(:rep, representative_name),
                   updated_at=NOW()
               WHERE id=:id""",
            sched=scheduled_dt.isoformat(), deadline=deadline_dt.isoformat(),
            url=online_url, loc=location_text, notes=notes,
            rep=representative_name, id=appointment_id
        )
        _insert_appointment_event(
            conn, appointment_id, user_id, 'appointment_sent',
            old_status='draft', new_status='pending_response',
            payload={"scheduled_at": scheduled_dt.isoformat(), "deadline_hours": deadline_hours}
        )

        applicant_id = appt['applicant_id']
        co_rows = conn.run("SELECT full_name FROM users WHERE id=:id", id=user_id)
        co_name = co_rows[0][0] if co_rows else "شركة"
        job_title = ""
        if appt.get('job_id'):
            j_rows = conn.run("SELECT title FROM jobs WHERE id=:id", id=appt['job_id'])
            job_title = j_rows[0][0] if j_rows else ""

        deadline_for_hook = deadline_dt
        appt_result = _get_appointment_row(conn, appointment_id)
        notify_payload = {
            "user_id": applicant_id, "type_": "appointment_invited",
            "title": f"دعوة مقابلة من {co_name}",
            "body": f"وصلتك دعوة مقابلة{(' للوظيفة: ' + job_title) if job_title else ''}",
            "link": f"/appointment-room?id={appointment_id}",
            "actor_id": user_id, "entity_id": appointment_id,
            "entity_type": "appointment",
            "event_key": f"appointment_invited:{appointment_id}:{applicant_id}"
        }
    finally:
        release_conn(conn)
    if notify_payload:
        try:
            create_notification(**notify_payload)
        except Exception as e:
            print(f"[send_appointment] notification failed: {e}")
    # S4: schedule appointment_deadline_expire — non-fatal, idempotent dedupe_key
    if deadline_for_hook:
        try:
            _dl_ts = int(deadline_for_hook.timestamp())
            schedule_job(
                "appointment_deadline_expire",
                {"appointment_id": appointment_id, "response_deadline_at_ts": _dl_ts},
                deadline_for_hook,
                f"appointment_deadline_expire:{appointment_id}:{_dl_ts}",
            )
        except Exception as _sje:
            print(f"[send_appointment] schedule_job(deadline_expire) failed: {_sje}")
    return appt_result


def accept_appointment(appointment_id: int, user_id: int) -> dict:
    """Employee accepts: pending_response → confirmed."""
    appt_result = None
    notify_payload = None
    sched_at_str = None
    conn = get_conn()
    try:
        appt = _get_appointment_row(conn, appointment_id)
        if not appt:
            raise ValueError("الموعد غير موجود")
        if appt['applicant_id'] != user_id:
            raise PermissionError("غير مصرح: فقط الموظف المدعو يمكنه قبول الموعد")
        _current_status = _appt_computed_status(appt)
        if _current_status != 'pending_response':
            raise ValueError(f"لا يمكن قبول موعد بحالة '{_current_status}'")

        conn.run(
            "UPDATE appointments SET status='confirmed', updated_at=NOW() WHERE id=:id",
            id=appointment_id
        )
        _insert_appointment_event(conn, appointment_id, user_id, 'appointment_accepted',
                                   old_status='pending_response', new_status='confirmed')

        company_id = appt['company_id']
        emp_rows = conn.run("SELECT full_name FROM users WHERE id=:id", id=user_id)
        emp_name = emp_rows[0][0] if emp_rows else "الموظف"

        sched_at_str = appt.get('scheduled_at')
        appt_result = _get_appointment_row(conn, appointment_id)
        notify_payload = {
            "user_id": company_id, "type_": "appointment_accepted",
            "title": f"{emp_name} وافق على الموعد",
            "body": "تم تأكيد موعد المقابلة",
            "link": f"/appointment-room?id={appointment_id}",
            "actor_id": user_id, "entity_id": appointment_id,
            "entity_type": "appointment",
            "event_key": f"appointment_accepted:{appointment_id}:{company_id}"
        }
    finally:
        release_conn(conn)
    if notify_payload:
        try:
            create_notification(**notify_payload)
        except Exception as e:
            print(f"[accept_appointment] notification failed: {e}")
    # S4: schedule appointment_reminder (24h before) and appointment_missed (15 min after) — non-fatal
    if sched_at_str:
        from datetime import datetime as _dt_a, timezone as _tz_a, timedelta as _td_a
        try:
            _sched = _dt_a.fromisoformat(str(sched_at_str).replace('Z', '+00:00'))
            if _sched.tzinfo is None:
                _sched = _sched.replace(tzinfo=_tz_a.utc)
            _sched_ts = int(_sched.timestamp())
            _now_a = _dt_a.now(_tz_a.utc)
            _reminder_at = _sched - _td_a(hours=24)
            if _reminder_at > _now_a:
                schedule_job(
                    "appointment_reminder",
                    {"appointment_id": appointment_id, "scheduled_at_ts": _sched_ts},
                    _reminder_at,
                    f"appointment_reminder:{appointment_id}:{_sched_ts}",
                )
        except Exception as _sje:
            print(f"[accept_appointment] schedule_job(reminder) failed: {_sje}")
        try:
            _sched2 = _dt_a.fromisoformat(str(sched_at_str).replace('Z', '+00:00'))
            if _sched2.tzinfo is None:
                _sched2 = _sched2.replace(tzinfo=_tz_a.utc)
            _sched2_ts = int(_sched2.timestamp())
            _missed_at = _sched2 + _td_a(minutes=15)
            schedule_job(
                "appointment_missed",
                {"appointment_id": appointment_id, "scheduled_at_ts": _sched2_ts},
                _missed_at,
                f"appointment_missed:{appointment_id}:{_sched2_ts}",
            )
        except Exception as _sje:
            print(f"[accept_appointment] schedule_job(missed) failed: {_sje}")
    return appt_result


def request_reschedule_appointment(appointment_id: int, user_id: int,
                                    reason: str = "") -> dict:
    """Employee requests reschedule: pending_response → reschedule_requested."""
    if reason:
        reason = reason.strip()[:500]
    appt_result = None
    notify_payload = None
    conn = get_conn()
    try:
        appt = _get_appointment_row(conn, appointment_id)
        if not appt:
            raise ValueError("الموعد غير موجود")
        if appt['applicant_id'] != user_id:
            raise PermissionError("غير مصرح: فقط الموظف المدعو يمكنه طلب تغيير الموعد")
        _current_status = _appt_computed_status(appt)
        if _current_status != 'pending_response':
            raise ValueError(f"لا يمكن طلب تغيير موعد بحالة '{_current_status}'")

        conn.run(
            "UPDATE appointments SET status='reschedule_requested', updated_at=NOW() WHERE id=:id",
            id=appointment_id
        )
        _insert_appointment_event(
            conn, appointment_id, user_id, 'appointment_reschedule_requested',
            old_status='pending_response', new_status='reschedule_requested',
            payload={"reason": reason} if reason else None
        )

        company_id = appt['company_id']
        emp_rows = conn.run("SELECT full_name FROM users WHERE id=:id", id=user_id)
        emp_name = emp_rows[0][0] if emp_rows else "الموظف"

        appt_result = _get_appointment_row(conn, appointment_id)
        notify_payload = {
            "user_id": company_id, "type_": "appointment_reschedule_requested",
            "title": f"{emp_name} طلب موعداً آخر",
            "body": reason[:80] if reason else "الموظف طلب تغيير موعد المقابلة",
            "link": f"/appointment-room?id={appointment_id}",
            "actor_id": user_id, "entity_id": appointment_id,
            "entity_type": "appointment",
            "event_key": f"appointment_reschedule_requested:{appointment_id}:{company_id}"
        }
    finally:
        release_conn(conn)
    if notify_payload:
        try:
            create_notification(**notify_payload)
        except Exception as e:
            print(f"[request_reschedule_appointment] notification failed: {e}")
    return appt_result


def reschedule_appointment(appointment_id: int, user_id: int,
                            new_scheduled_at_iso: str, deadline_hours: int = 48,
                            online_url: str = None, location_text: str = None,
                            notes: str = None) -> dict:
    """Company proposes new time: reschedule_requested → pending_response."""
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    if deadline_hours not in _APPT_DEADLINE_HOURS_ALLOWED:
        raise ValueError("مهلة الرد: 24 أو 48 أو 72 أو 168 ساعة فقط")
    if online_url:
        if not online_url.startswith("https://"):
            raise ValueError("رابط المقابلة يجب أن يبدأ بـ https://")
        online_url = online_url.strip()[:2000]
    if notes:
        notes = notes.strip()[:1000]
    if location_text:
        location_text = location_text.strip()[:500]

    appt_result = None
    notify_payload = None
    deadline_for_hook = None
    conn = get_conn()
    try:
        appt = _get_appointment_row(conn, appointment_id)
        if not appt:
            raise ValueError("الموعد غير موجود")
        if appt['company_id'] != user_id:
            raise PermissionError("غير مصرح: فقط الشركة يمكنها اقتراح موعد جديد")
        if appt['status'] != 'reschedule_requested':
            raise ValueError(f"لا يمكن اقتراح موعد بحالة '{appt['status']}'")

        # mode-required field validation — backend is source of truth (F6/F21)
        effective_url = online_url or appt.get('online_url')
        effective_loc = location_text or appt.get('location_text')
        if appt['mode'] == 'online' and not effective_url:
            raise ValueError("رابط المقابلة مطلوب للمواعيد الأونلاين")
        if appt['mode'] == 'onsite' and not effective_loc:
            raise ValueError("موقع المقابلة مطلوب للمواعيد الحضورية")

        try:
            scheduled_dt = _dt.fromisoformat(new_scheduled_at_iso.replace('Z', '+00:00'))
            if scheduled_dt.tzinfo is None:
                scheduled_dt = scheduled_dt.replace(tzinfo=_tz.utc)
        except Exception:
            raise ValueError("تنسيق التاريخ غير صالح — استخدم ISO 8601")

        now_utc = _dt.now(_tz.utc)
        if scheduled_dt <= now_utc:
            raise ValueError("وقت الموعد الجديد يجب أن يكون في المستقبل")

        deadline_dt = now_utc + _td(hours=deadline_hours)
        if deadline_dt >= scheduled_dt:
            raise ValueError("مهلة الرد تنتهي بعد وقت الموعد — اختر مهلة أقصر أو موعداً أبعد")

        conn.run(
            """UPDATE appointments
               SET status='pending_response', scheduled_at=:sched,
                   response_deadline_at=:deadline,
                   online_url=COALESCE(:url, online_url),
                   location_text=COALESCE(:loc, location_text),
                   notes=COALESCE(:notes, notes),
                   updated_at=NOW()
               WHERE id=:id""",
            sched=scheduled_dt.isoformat(), deadline=deadline_dt.isoformat(),
            url=online_url, loc=location_text, notes=notes, id=appointment_id
        )
        _insert_appointment_event(
            conn, appointment_id, user_id, 'appointment_rescheduled',
            old_status='reschedule_requested', new_status='pending_response',
            payload={"new_scheduled_at": scheduled_dt.isoformat(),
                     "deadline_hours": deadline_hours}
        )

        applicant_id = appt['applicant_id']
        co_rows = conn.run("SELECT full_name FROM users WHERE id=:id", id=user_id)
        co_name = co_rows[0][0] if co_rows else "الشركة"

        deadline_for_hook = deadline_dt
        appt_result = _get_appointment_row(conn, appointment_id)
        notify_payload = {
            "user_id": applicant_id, "type_": "appointment_rescheduled",
            "title": f"{co_name} اقترحت موعداً جديداً",
            "body": f"تاريخ مقترح جديد: {scheduled_dt.strftime('%Y-%m-%d %H:%M')} UTC",
            "link": f"/appointment-room?id={appointment_id}",
            "actor_id": user_id, "entity_id": appointment_id,
            "entity_type": "appointment",
            "event_key": f"appointment_rescheduled:{appointment_id}:{applicant_id}"
        }
    finally:
        release_conn(conn)
    if notify_payload:
        try:
            create_notification(**notify_payload)
        except Exception as e:
            print(f"[reschedule_appointment] notification failed: {e}")
    # S4: schedule appointment_deadline_expire for the new deadline — non-fatal, idempotent dedupe_key
    if deadline_for_hook:
        try:
            _dl_ts = int(deadline_for_hook.timestamp())
            schedule_job(
                "appointment_deadline_expire",
                {"appointment_id": appointment_id, "response_deadline_at_ts": _dl_ts},
                deadline_for_hook,
                f"appointment_deadline_expire:{appointment_id}:{_dl_ts}",
            )
        except Exception as _sje:
            print(f"[reschedule_appointment] schedule_job(deadline_expire) failed: {_sje}")
    return appt_result


def cancel_appointment(appointment_id: int, user_id: int, reason: str = "") -> dict:
    """Any participant cancels: pending_response|confirmed|reschedule_requested|draft → cancelled."""
    if reason:
        reason = reason.strip()[:500]
    appt_result = None
    notify_payloads = []
    conn = get_conn()
    try:
        appt = _get_appointment_row(conn, appointment_id)
        if not appt:
            raise ValueError("الموعد غير موجود")
        _check_appt_participant(conn, appointment_id, user_id)

        if appt['status'] not in ('draft', 'pending_response', 'confirmed', 'reschedule_requested'):
            raise ValueError(f"لا يمكن إلغاء موعد بحالة '{appt['status']}'")

        conn.run(
            "UPDATE appointments SET status='cancelled', updated_at=NOW() WHERE id=:id",
            id=appointment_id
        )
        _insert_appointment_event(
            conn, appointment_id, user_id, 'appointment_cancelled',
            old_status=appt['status'], new_status='cancelled',
            payload={"reason": reason} if reason else None
        )

        actor_rows = conn.run("SELECT full_name FROM users WHERE id=:id", id=user_id)
        actor_name = actor_rows[0][0] if actor_rows else "أحد الأطراف"

        for uid in [appt['company_id'], appt['applicant_id']]:
            if uid != user_id:
                notify_payloads.append({
                    "user_id": uid, "type_": "appointment_cancelled",
                    "title": "تم إلغاء موعد المقابلة",
                    "body": f"قام {actor_name} بإلغاء الموعد." + (
                        f" السبب: {reason[:60]}" if reason else ""),
                    "link": f"/appointment-room?id={appointment_id}",
                    "actor_id": user_id, "entity_id": appointment_id,
                    "entity_type": "appointment",
                    "event_key": f"appointment_cancelled:{appointment_id}:{uid}"
                })

        appt_result = _get_appointment_row(conn, appointment_id)
    finally:
        release_conn(conn)
    for payload in notify_payloads:
        try:
            create_notification(**payload)
        except Exception as e:
            print(f"[cancel_appointment] notification failed: {e}")
    return appt_result


def complete_appointment(appointment_id: int, user_id: int) -> dict:
    """Company marks interview done: confirmed → completed."""
    conn = get_conn()
    try:
        appt = _get_appointment_row(conn, appointment_id)
        if not appt:
            raise ValueError("الموعد غير موجود")
        if appt['company_id'] != user_id:
            raise PermissionError("غير مصرح: فقط الشركة يمكنها إنهاء المقابلة")
        if appt['status'] != 'confirmed':
            raise ValueError(f"لا يمكن إنهاء مقابلة بحالة '{appt['status']}' — يجب confirmed")
        if appt.get('scheduled_at'):
            from datetime import datetime as _dt, timezone as _tz
            _now = _dt.now(_tz.utc)
            _sched = appt['scheduled_at']
            if hasattr(_sched, 'tzinfo') and _sched.tzinfo is None:
                _sched = _sched.replace(tzinfo=_tz.utc)
            elif isinstance(_sched, str):
                _sched = _dt.fromisoformat(_sched.replace('Z', '+00:00'))
            if _sched > _now:
                raise ValueError("لا يمكن إنهاء المقابلة قبل موعدها المحدد")

        conn.run(
            "UPDATE appointments SET status='completed', updated_at=NOW() WHERE id=:id",
            id=appointment_id
        )
        _insert_appointment_event(
            conn, appointment_id, user_id, 'appointment_completed',
            old_status='confirmed', new_status='completed'
        )
        return _get_appointment_row(conn, appointment_id)
    finally:
        release_conn(conn)


def close_appointment(appointment_id: int, user_id: int) -> dict:
    """Company closes room: completed|cancelled → closed."""
    appt_result = None
    notify_payloads = []
    conn = get_conn()
    try:
        appt = _get_appointment_row(conn, appointment_id)
        if not appt:
            raise ValueError("الموعد غير موجود")
        if appt['company_id'] != user_id:
            raise PermissionError("غير مصرح: فقط الشركة يمكنها إغلاق الغرفة")
        if appt['status'] not in ('completed', 'cancelled'):
            raise ValueError(f"لا يمكن إغلاق موعد بحالة '{appt['status']}' — يجب completed أو cancelled")

        conn.run(
            "UPDATE appointments SET status='closed', closed_at=NOW(), updated_at=NOW() WHERE id=:id",
            id=appointment_id
        )
        _insert_appointment_event(
            conn, appointment_id, user_id, 'appointment_closed',
            old_status=appt['status'], new_status='closed'
        )

        for uid in [appt['company_id'], appt['applicant_id']]:
            if uid == user_id:
                continue
            notify_payloads.append({
                "user_id": uid, "type_": "appointment_closed",
                "title": "تم إغلاق غرفة الموعد",
                "body": "الغرفة أصبحت للقراءة فقط",
                "link": f"/appointment-room?id={appointment_id}",
                "actor_id": user_id, "entity_id": appointment_id,
                "entity_type": "appointment",
                "event_key": f"appointment_closed:{appointment_id}:{uid}"
            })

        appt_result = _get_appointment_row(conn, appointment_id)
    finally:
        release_conn(conn)
    for payload in notify_payloads:
        try:
            create_notification(**payload)
        except Exception as e:
            print(f"[close_appointment] notification failed: {e}")
    return appt_result


def list_appointments(user_id: int, status_filter: str = None,
                      limit: int = 20, offset: int = 0) -> list:
    """List appointments where user is a participant. Enriched with names and computed status."""
    conn = get_conn()
    try:
        params = {"uid": user_id, "limit": min(limit, 50), "offset": max(offset, 0)}
        status_clause = ""
        if status_filter:
            if status_filter == 'expired':
                # expired is computed (pending_response + passed deadline), not stored in DB
                status_clause = " AND a.status = 'pending_response' AND a.response_deadline_at < NOW()"
            elif status_filter in _APPT_VALID_STATUSES:
                status_clause = " AND a.status = :status"
                params["status"] = status_filter

        rows = conn.run(
            f"""SELECT a.id, a.job_id, a.application_id, a.company_id, a.applicant_id,
                       a.status, a.mode, a.scheduled_at, a.response_deadline_at,
                       a.created_at, a.updated_at, a.closed_at,
                       a.representative_name,
                       ap.role AS viewer_role,
                       co.full_name AS company_name,
                       emp.full_name AS applicant_name,
                       j.title AS job_title
                FROM appointments a
                JOIN appointment_participants ap
                     ON ap.appointment_id = a.id AND ap.user_id = :uid
                JOIN users co ON co.id = a.company_id
                JOIN users emp ON emp.id = a.applicant_id
                LEFT JOIN jobs j ON j.id = a.job_id
                WHERE 1=1{status_clause}
                ORDER BY a.updated_at DESC
                LIMIT :limit OFFSET :offset""",
            **params
        )
        cols = ["id","job_id","application_id","company_id","applicant_id",
                "status","mode","scheduled_at","response_deadline_at",
                "created_at","updated_at","closed_at","representative_name",
                "viewer_role","company_name","applicant_name","job_title"]
        result = []
        for r in (rows or []):
            d = _serialize(_row_to_dict(cols, r))
            d['computed_status'] = _appt_computed_status(d)
            result.append(d)
        return result
    finally:
        release_conn(conn)


def get_appointment_room(appointment_id: int, user_id: int) -> dict:
    """Full room details for a verified participant. Includes participants list."""
    conn = get_conn()
    try:
        appt = _get_appointment_row(conn, appointment_id)
        if not appt:
            raise ValueError("الموعد غير موجود")
        participant = _check_appt_participant(conn, appointment_id, user_id)

        appt['viewer_role'] = participant['role']
        appt['can_message'] = participant['can_message']
        appt['can_decide'] = participant['can_decide']
        appt['computed_status'] = _appt_computed_status(appt)

        co_rows = conn.run(
            "SELECT u.full_name, COALESCE(p.avatar_url,'') FROM users u "
            "LEFT JOIN profiles p ON p.user_id=u.id WHERE u.id=:id",
            id=appt['company_id']
        )
        emp_rows = conn.run(
            "SELECT u.full_name, COALESCE(p.avatar_url,'') FROM users u "
            "LEFT JOIN profiles p ON p.user_id=u.id WHERE u.id=:id",
            id=appt['applicant_id']
        )
        appt['company_name'] = co_rows[0][0] if co_rows else ""
        appt['company_avatar'] = co_rows[0][1] if co_rows else ""
        appt['applicant_name'] = emp_rows[0][0] if emp_rows else ""
        appt['applicant_avatar'] = emp_rows[0][1] if emp_rows else ""

        if appt.get('job_id'):
            j_rows = conn.run("SELECT title FROM jobs WHERE id=:id", id=appt['job_id'])
            appt['job_title'] = j_rows[0][0] if j_rows else None
        else:
            appt['job_title'] = None

        p_rows = conn.run(
            """SELECT ap.user_id, ap.role, ap.can_message, ap.can_decide, u.full_name
               FROM appointment_participants ap
               JOIN users u ON u.id=ap.user_id
               WHERE ap.appointment_id=:appt ORDER BY ap.created_at""",
            appt=appointment_id
        )
        appt['participants'] = [
            {"user_id": r[0], "role": r[1], "can_message": r[2],
             "can_decide": r[3], "full_name": r[4]}
            for r in (p_rows or [])
        ]
        return appt
    finally:
        release_conn(conn)


def get_appointment_events(appointment_id: int, user_id: int) -> list:
    """Return timeline events for a participant (immutable log)."""
    conn = get_conn()
    try:
        _appt_exists = _get_appointment_row(conn, appointment_id)
        if not _appt_exists:
            raise ValueError("الموعد غير موجود")
        _check_appt_participant(conn, appointment_id, user_id)
        rows = conn.run(
            """SELECT ae.id, ae.event_type, ae.old_status, ae.new_status,
                      ae.payload, ae.created_at, ae.actor_id,
                      COALESCE(u.full_name, 'النظام') AS actor_name
               FROM appointment_events ae
               LEFT JOIN users u ON u.id=ae.actor_id
               WHERE ae.appointment_id=:appt
               ORDER BY ae.created_at ASC""",
            appt=appointment_id
        )
        cols = ["id","event_type","old_status","new_status","payload",
                "created_at","actor_id","actor_name"]
        result = []
        for r in (rows or []):
            d = _serialize(_row_to_dict(cols, r))
            if d.get('payload') and isinstance(d['payload'], str):
                try:
                    d['payload'] = _json_mod.loads(d['payload'])
                except Exception:
                    pass
            result.append(d)
        return result
    finally:
        release_conn(conn)


def get_appointment_messages(appointment_id: int, user_id: int,
                              limit: int = 50, offset: int = 0) -> list:
    """Return active messages (excludes soft-deleted) for a participant."""
    conn = get_conn()
    try:
        _check_appt_participant(conn, appointment_id, user_id)
        rows = conn.run(
            """SELECT am.id, am.appointment_id, am.sender_id, am.body,
                      am.created_at, am.edited_at, u.full_name AS sender_name
               FROM appointment_messages am
               JOIN users u ON u.id=am.sender_id
               WHERE am.appointment_id=:appt AND am.deleted_at IS NULL
               ORDER BY am.created_at ASC
               LIMIT :lim OFFSET :off""",
            appt=appointment_id, lim=max(1, min(limit, 100)), off=max(offset, 0)
        )
        cols = ["id","appointment_id","sender_id","body","created_at","edited_at","sender_name"]
        result = []
        for r in (rows or []):
            d = _serialize(_row_to_dict(cols, r))
            d['is_own'] = (d['sender_id'] == user_id)
            result.append(d)
        return result
    finally:
        release_conn(conn)


def create_appointment_message(appointment_id: int, user_id: int, body: str) -> dict:
    """Send message in appointment thread. Participants only. Closed rooms reject."""
    body = (body or "").strip()
    if not body:
        raise ValueError("نص الرسالة مطلوب")
    if len(body) > 2000:
        raise ValueError("الرسالة طويلة جداً — الحد الأقصى 2000 حرف")

    conn = get_conn()
    try:
        appt = _get_appointment_row(conn, appointment_id)
        if not appt:
            raise ValueError("الموعد غير موجود")
        _msg_status = _appt_computed_status(appt)
        if _msg_status in _APPT_TERMINAL_STATUSES:
            raise ValueError("لا يمكن إرسال رسائل في موعد منتهٍ أو ملغى أو مغلق")

        participant = _check_appt_participant(conn, appointment_id, user_id)
        if not participant['can_message']:
            raise PermissionError("غير مصرح: لا صلاحية إرسال رسائل في هذا الموعد")

        rows = conn.run(
            """INSERT INTO appointment_messages (appointment_id, sender_id, body)
               VALUES (:appt, :uid, :body)
               RETURNING id, appointment_id, sender_id, body, created_at""",
            appt=appointment_id, uid=user_id, body=body
        )
        sndr_rows = conn.run("SELECT full_name FROM users WHERE id=:id", id=user_id)
        sender_name = sndr_rows[0][0] if sndr_rows else ""
        r = rows[0]
        return {
            "id": r[0], "appointment_id": r[1], "sender_id": r[2],
            "body": r[3],
            "created_at": r[4].isoformat() if r[4] else None,
            "edited_at": None, "sender_name": sender_name, "is_own": True
        }
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════
# Scheduler Infrastructure — S1: Schema Only
# Decision: External Cron + Secure Endpoint (PR #464 — S0 Tooling Decision)
# No runner, no helpers, no hooks, no endpoints in this migration.
# ══════════════════════════════════════════════════════════════════════════

def _migrate_scheduler_jobs():
    """
    Create scheduler_jobs table for time-based background job scheduling.

    S1 phase — schema only. This migration:
      - Creates the scheduler_jobs table with all required columns.
      - Adds dedupe_key UNIQUE constraint (idempotency at DB level).
      - Adds status / attempts / max_attempts CHECK constraints.
      - Adds 4 indexes for due-jobs lookup, lock cleanup, monitoring, audit.

    What is NOT included (deferred to S2/S3):
      - No schedule_job() helper function.
      - No run_due_jobs() runner.
      - No /internal/run-due-jobs endpoint.
      - No hooks in appointment or notification code.
      - The table will not be read or written at runtime until S2/S3.

    Idempotent — safe to run on every startup (CREATE IF NOT EXISTS).
    """
    conn = get_conn()
    try:
        conn.run("""
            CREATE TABLE IF NOT EXISTS scheduler_jobs (
                id           BIGSERIAL PRIMARY KEY,
                job_type     TEXT NOT NULL,
                payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
                run_at       TIMESTAMPTZ NOT NULL,
                status       TEXT NOT NULL DEFAULT 'pending',
                attempts     INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 5,
                last_error   TEXT,
                dedupe_key   TEXT NOT NULL,
                locked_at    TIMESTAMPTZ,
                locked_by    TEXT,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_sched_dedupe   UNIQUE (dedupe_key),
                CONSTRAINT ck_sched_status   CHECK (status IN ('pending','running','done','failed','cancelled')),
                CONSTRAINT ck_sched_attempts CHECK (attempts >= 0),
                CONSTRAINT ck_sched_maxatt   CHECK (max_attempts >= 1)
            )
        """)

        # Due-jobs lookup: pending jobs whose run_at has passed.
        # Primary query in run_due_jobs(): WHERE status='pending' AND run_at<=NOW()
        conn.run("CREATE INDEX IF NOT EXISTS idx_sched_due       ON scheduler_jobs(status, run_at)")

        # Stale lock cleanup: find running jobs with old locked_at for reset.
        conn.run("CREATE INDEX IF NOT EXISTS idx_sched_locked_at ON scheduler_jobs(locked_at)")

        # Monitoring / debug: group or count by job type.
        conn.run("CREATE INDEX IF NOT EXISTS idx_sched_job_type  ON scheduler_jobs(job_type)")

        # Audit review: most recent jobs first.
        conn.run("CREATE INDEX IF NOT EXISTS idx_sched_created   ON scheduler_jobs(created_at DESC)")

    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════
# Scheduler Infrastructure — S2: schedule_job helper
# Decision: External Cron + Secure Endpoint (PR #464 — S0)
# Schema: scheduler_jobs (PR #465 — S1)
# This helper inserts jobs idempotently. No execution, no notifications,
# no hooks, no endpoint, no runner.
# ══════════════════════════════════════════════════════════════════════════

def schedule_job(
    job_type: str,
    payload: dict,
    run_at,
    dedupe_key: str,
    max_attempts: int = 5
) -> dict:
    """
    Insert a job into scheduler_jobs idempotently.

    S2 phase — helper only. This function:
      - Validates all inputs before touching the DB.
      - Inserts a single row with status='pending', attempts=0.
      - On dedupe_key conflict (ON CONFLICT DO NOTHING), returns the
        existing row unchanged with created=False.
      - Does NOT execute the job.
      - Does NOT send notifications.
      - Does NOT modify appointment or job table rows.

    Idempotency:
      INSERT ... ON CONFLICT (dedupe_key) DO NOTHING RETURNING id, ...
      - If RETURNING has rows → newly inserted → created=True
      - If RETURNING is empty → conflict hit → SELECT existing → created=False

    The DO NOTHING approach is chosen over DO UPDATE because:
      - It never overwrites a job that is already running or done.
      - All statuses (pending/running/done/failed/cancelled) are preserved.
      - Callers can inspect created=False and decide whether to act.

    Args:
        job_type:     Non-empty string (e.g. 'appointment_reminder')
        payload:      dict — JSON-serializable data for the job handler
        run_at:       datetime (UTC) — execution target time
        dedupe_key:   Non-empty unique string; prevents duplicate jobs
        max_attempts: Maximum retries (default 5, minimum 1)

    Returns:
        {
            "id":         int,
            "job_type":   str,
            "run_at":     str (ISO 8601),
            "status":     str,
            "dedupe_key": str,
            "created_at": str (ISO 8601),
            "created":    bool  # True if newly inserted, False if already existed
        }

    Raises:
        ValueError:     on invalid inputs
        RuntimeError:   on unexpected DB failure
    """
    # ── Input validation ──────────────────────────────────────────────────
    if not isinstance(job_type, str) or not job_type.strip():
        raise ValueError("schedule_job: job_type must be a non-empty string")
    if not isinstance(payload, dict):
        raise ValueError("schedule_job: payload must be a dict")
    if not isinstance(dedupe_key, str) or not dedupe_key.strip():
        raise ValueError("schedule_job: dedupe_key must be a non-empty string")
    if not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError("schedule_job: max_attempts must be an integer >= 1")

    payload_str = _json_mod.dumps(payload)

    conn = get_conn()
    try:
        # INSERT with RETURNING — only returns rows when INSERT actually succeeds.
        # ON CONFLICT DO NOTHING produces zero rows if dedupe_key already exists.
        ins_rows = conn.run(
            """INSERT INTO scheduler_jobs
               (job_type, payload, run_at, dedupe_key, max_attempts,
                status, attempts, locked_at, locked_by)
               VALUES (:jtype, :payload::jsonb, :run_at, :dk, :maxatt,
                       'pending', 0, NULL, NULL)
               ON CONFLICT (dedupe_key) DO NOTHING
               RETURNING id, job_type, run_at, status, dedupe_key, created_at""",
            jtype=job_type,
            payload=payload_str,
            run_at=run_at,
            dk=dedupe_key,
            maxatt=max_attempts,
        )

        if ins_rows:
            # Newly inserted — RETURNING row is authoritative.
            cols = [c["name"] for c in conn.columns]
            row = _serialize(_row_to_dict(cols, ins_rows[0]))
            row["created"] = True
            return row

        # Conflict: dedupe_key already exists. Fetch the existing row.
        sel_rows = conn.run(
            """SELECT id, job_type, run_at, status, dedupe_key, created_at
               FROM scheduler_jobs
               WHERE dedupe_key = :dk""",
            dk=dedupe_key,
        )
        if not sel_rows:
            # Should not happen: conflict means the row exists; guard against race.
            raise RuntimeError(
                f"schedule_job: ON CONFLICT triggered but SELECT found no row "
                f"for dedupe_key={dedupe_key!r}"
            )
        cols = [c["name"] for c in conn.columns]
        row = _serialize(_row_to_dict(cols, sel_rows[0]))
        row["created"] = False
        return row

    except ValueError:
        raise
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"schedule_job: unexpected DB error: {exc}") from exc
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════
# Scheduler Infrastructure — S3: Runner + Secure Endpoint
# Decision: External Cron + Secure Endpoint (PR #464 — S0)
# Schema: scheduler_jobs (PR #465 — S1)
# Helper: schedule_job() (PR #466 — S2)
#
# Two functions:
#   _execute_scheduler_job(job) — dispatches to job type handler
#   run_due_scheduler_jobs(limit, runner_id) — picks + marks + executes + updates
#
# No hooks, no appointment/notification side effects, no cron config.
# ══════════════════════════════════════════════════════════════════════════

# Supported job types (updated in S4 with domain handlers).
_SCHEDULER_HANDLERS = {
    "noop",                          # Test-only: succeeds immediately with no side effects.
    "appointment_reminder",          # S4: 24h-before reminder for confirmed appointments.
    "appointment_deadline_expire",   # S4: expire pending_response when deadline passes.
    "appointment_missed",            # S4: mark confirmed appointment missed (15 min after).
    "job_expiring_soon",             # S4: notify company 48h before job listing expires.
}


# ── S4 Domain Handlers ────────────────────────────────────────────────────────
# Each handler is idempotent: re-reads DB state before acting so a double-fire
# is safe.  The conn is released before sending notifications (each notification
# helper opens its own conn).  All handlers raise on missing payload fields;
# the runner handles retries / exhaustion through the normal S3 pipeline.
# ─────────────────────────────────────────────────────────────────────────────

def _ts_from_db_val(val) -> int:
    """Convert a DB datetime value (ISO string or datetime) to UTC epoch seconds."""
    from datetime import datetime as _ddt, timezone as _dtz
    dt = _ddt.fromisoformat(str(val).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dtz.utc)
    return int(dt.timestamp())


def _handle_appointment_reminder(job: dict) -> None:
    """Send 24h-before reminder notifications for a confirmed appointment.

    Stale check: payload must carry scheduled_at_ts (epoch s). If the appointment's
    current scheduled_at differs the job was created for an older cycle — safe no-op.
    Notification failures are re-raised so the runner retries; event_key idempotency
    prevents duplicates when a previous notification already succeeded.
    """
    from datetime import datetime as _dt, timezone as _tz
    payload = job.get("payload", {})
    appt_id = payload.get("appointment_id")
    sched_ts_payload = payload.get("scheduled_at_ts")
    if not appt_id:
        raise ValueError("appointment_reminder: missing appointment_id in payload")
    conn = get_conn()
    company_id = applicant_id = None
    try:
        appt = _get_appointment_row(conn, int(appt_id))
        if not appt or appt["status"] != "confirmed":
            return  # cancelled, expired, missed, etc. — safe no-op
        # Stale check: if scheduled_at changed (reschedule cycle), this job is outdated
        if sched_ts_payload is not None:
            db_sched_val = appt.get("scheduled_at")
            if db_sched_val and _ts_from_db_val(db_sched_val) != int(sched_ts_payload):
                return  # stale — safe no-op
        company_id = appt["company_id"]
        applicant_id = appt["applicant_id"]
    finally:
        release_conn(conn)
    errors = []
    for uid in [company_id, applicant_id]:
        if uid:
            try:
                create_notification(
                    user_id=uid,
                    type_="appointment_reminder",
                    title="تذكير: موعد مقابلة خلال 24 ساعة",
                    body="تذكير بموعد مقابلتك غداً",
                    link=f"/appointment-room?id={appt_id}",
                    entity_id=int(appt_id),
                    entity_type="appointment",
                    event_key=f"appointment_reminder:{appt_id}:{uid}:{sched_ts_payload}",
                )
            except Exception as _ne:
                print(
                    f"[scheduler:appointment_reminder] notification failed "
                    f"uid={uid} appt={appt_id}: {_ne}"
                )
                errors.append(_ne)
    if errors:
        raise errors[0]


def _handle_appointment_deadline_expire(job: dict) -> None:
    """Transition pending_response → expired when response_deadline_at has passed.

    Stale check: payload carries response_deadline_at_ts. If the DB deadline no
    longer matches (reschedule set a new deadline) this is a stale job — safe no-op.

    Retry safety: if the transition already happened (status='expired') but the
    notification failed, allow re-notification without re-transitioning. event_key
    idempotency prevents duplicate notifications.
    """
    from datetime import datetime as _dt, timezone as _tz
    payload = job.get("payload", {})
    appt_id = payload.get("appointment_id")
    dl_ts_payload = payload.get("response_deadline_at_ts")
    if not appt_id:
        raise ValueError("appointment_deadline_expire: missing appointment_id in payload")
    conn = get_conn()
    company_id = None
    transitioned = False
    already_expired = False
    try:
        appt = _get_appointment_row(conn, int(appt_id))
        if not appt:
            return  # deleted — safe no-op
        # Stale check: if deadline changed (reschedule), this job is for an old cycle
        if dl_ts_payload is not None:
            db_dl_val = appt.get("response_deadline_at")
            if db_dl_val and _ts_from_db_val(db_dl_val) != int(dl_ts_payload):
                return  # stale — safe no-op
        if appt["status"] == "pending_response":
            deadline_val = appt.get("response_deadline_at")
            if not deadline_val:
                return
            deadline_dt = _dt.fromisoformat(str(deadline_val).replace("Z", "+00:00"))
            if deadline_dt.tzinfo is None:
                deadline_dt = deadline_dt.replace(tzinfo=_tz.utc)
            if _dt.now(_tz.utc) < deadline_dt:
                return  # too early
            rows = conn.run(
                "UPDATE appointments SET status='expired', updated_at=NOW() "
                "WHERE id=:id AND status='pending_response' RETURNING id",
                id=int(appt_id),
            )
            transitioned = bool(rows)
            if transitioned:
                _insert_appointment_event(
                    conn, int(appt_id), None, "appointment_expired",
                    old_status="pending_response", new_status="expired",
                )
        elif appt["status"] == "expired":
            already_expired = True  # retry scenario: transition done, notification pending
        else:
            return  # confirmed, cancelled, missed, etc. — safe no-op
        company_id = appt["company_id"]
    finally:
        release_conn(conn)
    if (transitioned or already_expired) and company_id:
        try:
            create_notification(
                user_id=company_id,
                type_="appointment_expired",
                title="انتهت مهلة الرد على دعوة المقابلة",
                body="لم يرد الموظف خلال المهلة المحددة",
                link=f"/appointment-room?id={appt_id}",
                entity_id=int(appt_id),
                entity_type="appointment",
                event_key=f"appointment_deadline_expired:{appt_id}:{company_id}:{dl_ts_payload}",
            )
        except Exception as _ne:
            print(
                f"[scheduler:appointment_deadline_expire] notification failed "
                f"appt={appt_id}: {_ne}"
            )
            raise  # re-raise — runner retries; event_key idempotency prevents duplicate


def _handle_appointment_missed(job: dict) -> None:
    """Transition confirmed → missed when scheduled_at + 15 min has passed.

    Stale check: payload carries scheduled_at_ts. If the current DB scheduled_at
    differs, this job targets an old cycle after a reschedule — safe no-op.

    Time check: NOW() must be >= scheduled_at + 15 minutes before transitioning.

    Retry safety: if transition already happened (status='missed') but notification
    failed, allow re-notification without re-transitioning.
    """
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    payload = job.get("payload", {})
    appt_id = payload.get("appointment_id")
    sched_ts_payload = payload.get("scheduled_at_ts")
    if not appt_id:
        raise ValueError("appointment_missed: missing appointment_id in payload")
    conn = get_conn()
    company_id = applicant_id = None
    transitioned = False
    already_missed = False
    try:
        appt = _get_appointment_row(conn, int(appt_id))
        if not appt:
            return  # deleted — safe no-op
        # Stale check: if scheduled_at changed (reschedule), this job is outdated
        if sched_ts_payload is not None:
            db_sched_val = appt.get("scheduled_at")
            if db_sched_val and _ts_from_db_val(db_sched_val) != int(sched_ts_payload):
                return  # stale — safe no-op
        if appt["status"] == "confirmed":
            sched_val = appt.get("scheduled_at")
            if not sched_val:
                return
            sched_dt = _dt.fromisoformat(str(sched_val).replace("Z", "+00:00"))
            if sched_dt.tzinfo is None:
                sched_dt = sched_dt.replace(tzinfo=_tz.utc)
            if _dt.now(_tz.utc) < sched_dt + _td(minutes=15):
                return  # too early — appointment not yet overdue
            rows = conn.run(
                "UPDATE appointments SET status='missed', updated_at=NOW() "
                "WHERE id=:id AND status='confirmed' RETURNING id",
                id=int(appt_id),
            )
            transitioned = bool(rows)
            if transitioned:
                _insert_appointment_event(
                    conn, int(appt_id), None, "appointment_missed",
                    old_status="confirmed", new_status="missed",
                )
        elif appt["status"] == "missed":
            already_missed = True  # retry scenario: transition done, notification pending
        else:
            return  # expired, cancelled, etc. — safe no-op
        company_id = appt["company_id"]
        applicant_id = appt["applicant_id"]
    finally:
        release_conn(conn)
    if transitioned or already_missed:
        errors = []
        for uid in [company_id, applicant_id]:
            if uid:
                try:
                    create_notification(
                        user_id=uid,
                        type_="appointment_missed",
                        title="فات موعد المقابلة",
                        body="مرّ وقت الموعد بدون إجراء رسمي",
                        link=f"/appointment-room?id={appt_id}",
                        entity_id=int(appt_id),
                        entity_type="appointment",
                        event_key=f"appointment_missed:{appt_id}:{uid}:{sched_ts_payload}",
                    )
                except Exception as _ne:
                    print(
                        f"[scheduler:appointment_missed] notification failed "
                        f"uid={uid} appt={appt_id}: {_ne}"
                    )
                    errors.append(_ne)
        if errors:
            raise errors[0]  # re-raise — runner retries; event_key idempotency prevents duplicate


def _handle_job_expiring_soon(job: dict) -> None:
    """Send job-expiring-soon notification to company 48h before listing expires.

    company_id is read from DB — never trusted from payload (F21/F6).
    Stale check: expected_expires_at_ts in payload must match current DB expires_at.
    Only active jobs receive notifications (not paused, closed, or expired).
    Notification failure is re-raised so the runner can retry.
    """
    payload = job.get("payload", {})
    job_id = payload.get("job_id")
    expected_exp_ts = payload.get("expected_expires_at_ts")
    if not job_id:
        raise ValueError("job_expiring_soon: missing job_id in payload")
    conn = get_conn()
    company_id = job_title = None
    try:
        rows = conn.run(
            "SELECT title, status, expires_at, company_id FROM jobs WHERE id=:id",
            id=int(job_id),
        )
        if not rows:
            return  # job deleted — safe no-op
        job_title, job_status, db_expires_at, company_id = rows[0]
        # Only notify for active jobs (not paused, closed, or expired)
        if job_status != "active":
            return
        # Stale check: if expires_at changed, this job targets an old expiry cycle
        if expected_exp_ts is not None and db_expires_at is not None:
            if _ts_from_db_val(db_expires_at) != int(expected_exp_ts):
                return  # stale — safe no-op
    finally:
        release_conn(conn)
    try:
        create_notification(
            user_id=int(company_id),
            type_="job_expiring_soon",
            title="وظيفتك ستنتهي قريباً",
            body=f'وظيفة "{str(job_title or "")[:60]}" ستنتهي خلال 48 ساعة',
            link="/company-profile",
            entity_id=int(job_id),
            entity_type="job",
            event_key=f"job_expiring_soon:{job_id}:{company_id}:{expected_exp_ts}",
        )
    except Exception as _ne:
        print(f"[scheduler:job_expiring_soon] notification failed job={job_id}: {_ne}")
        raise  # re-raise — runner retries; event_key idempotency prevents duplicate


def _execute_scheduler_job(job: dict) -> None:
    """
    Dispatch a single scheduler job to the correct handler.

    Supported job types (S4):
      'noop'                        — instant success, zero side effects.
      'appointment_reminder'        — 24h-before reminder notifications.
      'appointment_deadline_expire' — expire pending_response when deadline passes.
      'appointment_missed'          — mark confirmed appointment as missed.
      'job_expiring_soon'           — notify company 48h before job listing expires.

    Unknown job types raise ValueError — the runner treats this as a handler
    failure subject to normal retry/exhaustion logic.

    No eval, no dynamic import, no getattr dispatch. All handlers are
    explicitly listed in _SCHEDULER_HANDLERS and branched here.
    """
    job_type = job.get("job_type", "")

    if job_type == "noop":
        return
    if job_type == "appointment_reminder":
        _handle_appointment_reminder(job); return
    if job_type == "appointment_deadline_expire":
        _handle_appointment_deadline_expire(job); return
    if job_type == "appointment_missed":
        _handle_appointment_missed(job); return
    if job_type == "job_expiring_soon":
        _handle_job_expiring_soon(job); return

    raise ValueError(f"_execute_scheduler_job: unsupported job_type={job_type!r}")


def _update_scheduler_job_final_status(
    conn, jid: int, new_status: str, err_msg, runner_id: str
) -> bool:
    """
    Write the final status of one scheduler job: 'done', 'failed', or 'pending' (retry).

    Uses RETURNING id + ownership guards in WHERE to verify the update was real:
      AND status = 'running'    — prevents touching jobs not in the expected state
      AND locked_by = :runner_id — verifies this runner still owns the lock

    Returns True only when RETURNING returns exactly one row.
    Returns False (with a clear log) when:
      - RETURNING returns zero rows (lock stolen, job already cleaned, state mismatch)
      - the UPDATE raised an exception (DB disconnect, etc.)
    Never swallows errors. Caller decides how to count and report.
    """
    try:
        rows = conn.run(
            """UPDATE scheduler_jobs
               SET status     = :status,
                   locked_at  = NULL,
                   locked_by  = NULL,
                   last_error = :err,
                   updated_at = NOW()
               WHERE id = :id
                 AND status = 'running'
                 AND locked_by = :runner_id
               RETURNING id""",
            status=new_status,
            err=err_msg,
            id=jid,
            runner_id=runner_id,
        )
        if rows:
            return True
        print(
            f"[scheduler] ERROR job_id={jid} final-update to {new_status!r} "
            f"returned zero rows — lock stolen or state mismatch — runner={runner_id}"
        )
        return False
    except Exception as upd_exc:
        print(
            f"[scheduler] ERROR job_id={jid} final-update to {new_status!r} "
            f"FAILED — job stuck in 'running' — runner={runner_id}: {upd_exc}"
        )
        return False


def run_due_scheduler_jobs(limit: int = 20, runner_id: str = None) -> dict:
    """
    Pick due jobs from scheduler_jobs, execute them, update their status.

    Transaction strategy — two phases to avoid long-held locks:

      Phase 1 (short transaction):
        BEGIN
        SELECT … WHERE status='pending' AND run_at<=NOW()
          ORDER BY run_at ASC LIMIT :limit FOR UPDATE SKIP LOCKED
        UPDATE each picked job → status='running', attempts+=1,
          locked_at=NOW(), locked_by=runner_id
        COMMIT

      Phase 2 (auto-committed per statement):
        For each job: call _execute_scheduler_job(job)
        On success       → UPDATE status='done', clear lock fields
        On failure, retryable (attempts < max_attempts)
                         → UPDATE status='pending', set last_error
        On failure, exhausted (attempts >= max_attempts)
                         → UPDATE status='failed', set last_error

    If a Phase 2 final-status UPDATE fails (rare, e.g. DB disconnect),
    the job is counted in `update_failed` / `stuck_running` and the
    response returns `"ok": false`. The job stays in status='running'
    until a stale-lock cleanup resets it (deferred to S4).

    Args:
        limit:     Jobs to pick per call. Clamped to [1, 50]. Default 20.
        runner_id: Identifier for locked_by. Defaults to 'runner-{pid}'.

    Returns:
        {
          "ok":            bool,  # False if any final-status UPDATE failed
          "picked":        int,
          "done":          int,
          "failed":        int,
          "retried":       int,
          "update_failed": int,   # jobs whose final UPDATE failed (stuck in 'running')
          "stuck_running": int,   # alias for update_failed
          "runner_id":     str,
          "jobs":          [{"id": int, "job_type": str, "status": str}, ...]
        }

    Raises:
        RuntimeError: on unexpected failure in Phase 1 (Phase 2 errors
                      are handled per-job and logged, never raised).
    """
    limit     = max(1, min(50, int(limit)))
    runner_id = runner_id or f"runner-{os.getpid()}"

    conn      = get_conn()
    committed = False
    try:
        # ── Phase 1: Pick and mark running (short transaction) ────────────
        conn.run("BEGIN")

        rows = conn.run(
            """SELECT id, job_type, payload, max_attempts, attempts
               FROM scheduler_jobs
               WHERE status = 'pending' AND run_at <= NOW()
               ORDER BY run_at ASC
               LIMIT :limit
               FOR UPDATE SKIP LOCKED""",
            limit=limit,
        )

        if not rows:
            conn.run("COMMIT")
            committed = True
            return {
                "ok": True, "picked": 0, "done": 0,
                "failed": 0, "retried": 0,
                "update_failed": 0, "stuck_running": 0,
                "runner_id": runner_id, "jobs": [],
            }

        jobs_data = [
            {
                "id":           r[0],
                "job_type":     r[1],
                "payload":      r[2],
                "max_attempts": r[3],
                "old_attempts": r[4],
            }
            for r in rows
        ]

        for job in jobs_data:
            conn.run(
                """UPDATE scheduler_jobs
                   SET status     = 'running',
                       attempts   = attempts + 1,
                       locked_at  = NOW(),
                       locked_by  = :runner,
                       updated_at = NOW()
                   WHERE id = :id""",
                runner=runner_id,
                id=job["id"],
            )

        conn.run("COMMIT")
        committed = True

        # ── Phase 2: Execute handlers + update final status ───────────────
        done_cnt          = 0
        failed_cnt        = 0
        retried_cnt       = 0
        update_failed_cnt = 0
        results           = []

        for job in jobs_data:
            jid          = job["id"]
            job_type     = job["job_type"]
            new_attempts = job["old_attempts"] + 1  # matches DB after increment
            max_attempts = job["max_attempts"]

            try:
                _execute_scheduler_job(job)

                # Handler succeeded → update to done; count only if UPDATE succeeds
                if _update_scheduler_job_final_status(conn, jid, "done", None, runner_id):
                    done_cnt += 1
                    results.append({"id": jid, "job_type": job_type, "status": "done"})
                else:
                    update_failed_cnt += 1
                    results.append({"id": jid, "job_type": job_type, "status": "update_failed"})

            except Exception as exc:
                err_msg = str(exc)[:500]
                print(f"[scheduler] job_id={jid} job_type={job_type!r} "
                      f"attempt={new_attempts}/{max_attempts} FAILED: {err_msg}")

                if new_attempts >= max_attempts:
                    # Exhausted → update to failed (terminal); count only if UPDATE succeeds
                    if _update_scheduler_job_final_status(conn, jid, "failed", err_msg, runner_id):
                        failed_cnt += 1
                        results.append({"id": jid, "job_type": job_type, "status": "failed"})
                    else:
                        update_failed_cnt += 1
                        results.append({"id": jid, "job_type": job_type, "status": "update_failed"})
                else:
                    # Retryable → update back to pending; count only if UPDATE succeeds
                    if _update_scheduler_job_final_status(conn, jid, "pending", err_msg, runner_id):
                        retried_cnt += 1
                        results.append({"id": jid, "job_type": job_type, "status": "retried"})
                    else:
                        update_failed_cnt += 1
                        results.append({"id": jid, "job_type": job_type, "status": "update_failed"})

        return {
            "ok":            update_failed_cnt == 0,
            "picked":        len(jobs_data),
            "done":          done_cnt,
            "failed":        failed_cnt,
            "retried":       retried_cnt,
            "update_failed": update_failed_cnt,
            "stuck_running": update_failed_cnt,
            "runner_id":     runner_id,
            "jobs":          results,
        }

    except Exception as exc:
        if not committed:
            try:
                conn.run("ROLLBACK")
            except Exception as rollback_exc:
                print(f"[scheduler] ERROR rollback failed — runner={runner_id}: {rollback_exc}")
        raise RuntimeError(f"run_due_scheduler_jobs: {exc}") from exc
    finally:
        release_conn(conn)
