"""admin_perms.py — Admin permission catalog (task 8.4a · docs/rules/admin-staff.md · SYSTEMS_INDEX §25h).

The ONE list of admin permissions. Every check_admin(request, perm) in server.py names a perm from here
(a missing / unknown perm = programming error, never a 403). Two groups:
  GRANTABLE   → may be given to a staff token (plan 8.4b)
  OWNER_ONLY  → the owner's only — passes ONLY with "*", even when the perm itself is listed in the token
allows(perms, perm) → the single decision (check_admin + the email-visibility check use it).
is_email_key(k)     → the hiding rule: a key named "email" or ending in "_email" (task 8.4a2 — no name list).
strip_emails(obj)   → removes every email key (is_email_key) from an admin response without EMAIL_VIEW.
UNGUARDED_ROUTES    → admin-area routes that do NOT call check_admin, each with its reason (the route test
                      in tests/test_admin_perms_84a.py fails on any other admin route without a perm).
"""

GRANTABLE = {
    "users.view":       "عرض المستخدمين وملفاتهم",
    "users.edit":       "تعديل ملفات المستخدمين وحذف عناصر منها",
    "users.suspend":    "تعليق الحسابات وإرجاعها",
    "users.email.view": "رؤية إيميلات المستخدمين",
    "kyc.review":       "مراجعة طلبات التوثيق",
    "jobs.manage":      "إدارة الوظائف",
    "reports.manage":   "مراجعة البلاغات",
    "content.edit":     "النصوص والألوان والأخبار والشعار",
    "support.manage":   "تذاكر الدعم",
    "settings.edit":    "الإعدادات العادية وأزرار الإجراءات وقراءة إعدادات الإيميل",
    "stats.view":       "لوحة القيادة والإحصائيات والنشاط",
    "message.send":     "إرسال رسالة لمستخدم",
}

OWNER_ONLY = {
    "users.delete":      "حذف حساب",
    "users.type":        "تغيير نوع الحساب",
    "users.password":    "تغيير كلمة سر مستخدم",
    "users.email":       "تغيير إيميل مستخدم",
    "users.export":      "تصدير المستخدمين CSV",
    "settings.security": "الإعدادات الأمنية وتعديل إعدادات الإيميل",
    "audit.view":        "السجل الأمني",
    "staff.manage":      "إدارة فريق الإدارة",
    "system.manage":     "صيانة النظام وسجل الأخطاء",
}

ALL = {**GRANTABLE, **OWNER_ONLY}
OWNER = "*"
EMAIL_VIEW = "users.email.view"
EMAIL_KEYS = frozenset({"email", "guest_email"})   # docs / examples only — the rule is is_email_key()

# Admin-area routes (FastAPI route name) that never call check_admin — each with its reason.
UNGUARDED_ROUTES = {
    "admin_login":         "the admin login itself (password → admin JWT)",
    "get_logos":           "public — the site logo every page shows",
    "admin_page":          "HTML shell only — data comes from /admin/* (each with its perm)",
    "admin_email_page":    "HTML shell only",
    "admin_settings_page": "HTML shell only",
    "admin_content_page":  "HTML shell only",
    "admin_support_page":  "HTML shell only",
    "admin_view":          "HTML shell only (outside the panel path)",
    "admin_job_page":      "HTML shell only (outside the panel path)",
}


def require_known(perm) -> None:
    """A perm outside the catalog is a bug in the caller → RuntimeError (500), never a 403."""
    if perm not in ALL:
        raise RuntimeError(f"check_admin: unknown admin permission {perm!r}")


def allows(perms, perm: str) -> bool:
    """"*" passes everything · an OWNER_ONLY perm passes only with "*" · else the perm must be listed."""
    require_known(perm)
    perms = perms if isinstance(perms, (list, tuple, set, frozenset)) else []
    if OWNER in perms:
        return True
    if perm in OWNER_ONLY:
        return False
    return perm in perms


def is_email_key(key) -> bool:
    """A key named "email" or ending in "_email" (guest_email · support details account_email · …)."""
    return isinstance(key, str) and (key == "email" or key.endswith("_email"))


def strip_emails(obj):
    """Copy of obj without any is_email_key key (dicts / lists, any depth)."""
    if isinstance(obj, dict):
        return {k: strip_emails(v) for k, v in obj.items() if not is_email_key(k)}
    if isinstance(obj, list):
        return [strip_emails(v) for v in obj]
    return obj
