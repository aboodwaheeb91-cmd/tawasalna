"""data_export.py — «تنزيل بياناتي» (task 8.5b · docs/rules/data-export.md · docs/SYSTEMS_INDEX.md §1e).

The ONE builder of a user's own data copy. Every section is read straight from the DB with an explicit column
list (never `SELECT *`) — so a new column never leaks into the file by itself.

  build_export(user_id) → dict — the JSON file of POST /me/export (server.py — JWT + password + rate limit).
KYC documents are never in the file: POST /me/export/kyc-docs (server.py) signs the paths of the user's own
kyc_submissions row with _sign_kyc_doc (short-lived links).

What the file never carries (checked again by forbidden_keys() before it leaves — a hit is a server error):
  secrets (password_hash · session_version · tokens · OTP codes · reset links · MFA) · deleted_* / suspended_* ·
  admin notes / audit / admin_hidden_reason · IPs · KYC document paths · other people's private data
  (their messages · a company's notes / pipeline · applicants of a company's jobs — a count per job only).
Other accounts appear as tw_id (+ public name for follows) only; a deleted account → tw_id null + is_deleted.
"""
from datetime import date, datetime

FORMAT_VERSION = 1

# Keys that must never appear anywhere in the file (any depth). Also the test's list.
FORBIDDEN_KEYS = frozenset({
    "password", "password_hash", "session_version", "sv", "token", "jwt",
    "email_code", "phone_code", "email_code_target", "phone_code_target", "email_code_expires_at",
    "phone_code_expires_at", "email_code_attempts", "phone_code_attempts", "otp", "code_hash", "token_hash",
    "reset_token", "mfa_secret", "mfa_secret_enc", "secret", "secret_enc", "recovery_codes",
    "deleted_at", "deleted_by", "deleted_kind", "deleted_reason",
    "suspended_at", "suspended_reason", "suspended_by",
    "admin_note", "admin_hidden_reason", "admin_hidden_at", "notes", "note",
    "ip", "ip_address", "client_ip", "id_front_url", "selfie_url",
})

_PROFILE_COLS = ("headline, title, first_name, middle_name, last_name, short_bio, bio, dob, phone, country, city, "
                 "location, website, avail, availability_status, skills, avatar_url, cover_url, profile_color, "
                 "profile_style, sections_order, custom_sections, is_verified, profession_id, updated_at")


def _val(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return [_val(x) for x in v]
    return v


def _q(conn, sql, **kw) -> list:
    rows = conn.run(sql, **kw) or []
    cols = [c["name"] for c in conn.columns or []]
    return [{c: _val(r[i]) for i, c in enumerate(cols)} for r in rows]


def _one(conn, sql, **kw):
    rows = _q(conn, sql, **kw)
    return rows[0] if rows else None


def _party(d: dict, deleted_key: str = "is_deleted") -> dict:
    """Another account in a shared record: a deleted one never shows its tw_id / name (account-deletion rule 4)."""
    import account_deletion as ad
    return ad.scrub(d, d.pop(deleted_key, False))


def forbidden_keys(obj, path="") -> list:
    """Every forbidden key in obj (recursive) → ['path.key', …]."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            if str(k).lower() in FORBIDDEN_KEYS:
                found.append(p)
            found.extend(forbidden_keys(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(forbidden_keys(v, f"{path}[{i}]"))
    return found


def build_export(user_id: int) -> dict:
    """The whole file for user_id. Raises LookupError when the account row is missing."""
    import account_deletion as ad
    import auth
    import blocks_suspension as bs
    import email_service
    uid = int(user_id)
    with auth.db_conn() as conn:
        account = _one(conn, "SELECT u.tw_id, u.full_name, u.email, p.phone, u.user_type, u.country_code, "
                             "u.created_at, u.terms_accepted_at, u.terms_version "
                             "FROM users u LEFT JOIN profiles p ON p.user_id = u.id WHERE u.id = :u", u=uid)
        if not account:
            raise LookupError("user not found")
        is_co = account["user_type"] == "co"

        profile = _one(conn, f"SELECT {_PROFILE_COLS} FROM profiles WHERE user_id = :u", u=uid) or {}
        if profile.get("profession_id"):
            prof = _one(conn, "SELECT name_ar, name_en FROM profession_categories WHERE id = :p",
                        p=profile["profession_id"])
            profile["profession"] = prof
        profile.update({
            "experience": _q(conn, "SELECT title, company, location, start_date, end_date, is_current, description, "
                                   "sort_order, created_at FROM experience WHERE user_id = :u "
                                   "ORDER BY sort_order, id", u=uid),
            "education": _q(conn, "SELECT institution, degree, field, start_year, end_year, is_current, description, "
                                  "created_at FROM education WHERE user_id = :u ORDER BY id", u=uid),
            "courses": _q(conn, "SELECT title, provider, completion_date, certificate_url, description, created_at "
                                "FROM courses WHERE user_id = :u ORDER BY id", u=uid),
            "skills_list": _q(conn, "SELECT skill, level, created_at FROM user_skills WHERE user_id = :u "
                                    "ORDER BY id", u=uid),
            "languages": _q(conn, "SELECT language, level, created_at FROM user_langs WHERE user_id = :u "
                                  "ORDER BY id", u=uid),
            "links": _q(conn, "SELECT link_type, url, created_at FROM user_links WHERE user_id = :u ORDER BY id",
                        u=uid),
        })

        company = None
        if is_co:
            company = _one(conn, "SELECT company_type, founded_year, company_size, industry, description, "
                                 "headquarters, contact_email, cover_url, created_at, updated_at "
                                 "FROM company_profiles WHERE user_id = :u", u=uid) or {}
            company["logo_url"] = profile.get("avatar_url")
            company["branches"] = _q(conn, "SELECT branch_name, country, city, district, display_order, created_at "
                                           "FROM company_branches WHERE company_id = :u "
                                           "ORDER BY display_order, id", u=uid)
            # Applicants are other people — a count per job only (never names / profiles / statuses / notes)
            company["jobs"] = _q(conn, "SELECT j.id, j.title, j.description, j.location, j.job_type, j.work_mode, "
                                       "j.category, j.salary_min, j.salary_max, j.salary_hidden, j.currency, "
                                       "j.experience_years, j.skills, j.status, j.created_at, j.expires_at, "
                                       "j.closed_at, j.paused_at, j.archived_at, "
                                       "(SELECT COUNT(*) FROM job_applications ja WHERE ja.job_id = j.id) "
                                       "AS applicants_count "
                                       "FROM jobs j WHERE j.company_id = :u ORDER BY j.id", u=uid)
            settings = _one(conn, "SELECT notify_applicant_result FROM company_settings WHERE company_id = :u", u=uid)
            company["settings"] = settings or dict(auth.COMPANY_SETTINGS_DEFAULTS)

        posts = _q(conn, "SELECT id, body, tags, theme_color, comments_enabled, created_at, updated_at "
                         "FROM company_posts WHERE company_id = :u ORDER BY id", u=uid)
        comments = _q(conn, "SELECT id, post_id, reply_to_comment_id, body, status, created_at, updated_at "
                            "FROM company_post_comments WHERE user_id = :u ORDER BY id", u=uid)
        saved = _q(conn, "SELECT post_id, created_at FROM company_post_saves WHERE user_id = :u ORDER BY id", u=uid)
        appreciated = _q(conn, "SELECT post_id, created_at FROM company_post_appreciations WHERE user_id = :u "
                               "ORDER BY id", u=uid)

        # Follows — tw_id + public name of visible (active) accounts only
        following = _q(conn, "SELECT u.tw_id, u.full_name, f.created_at FROM profile_follows f "
                             "JOIN users u ON u.id = f.followed_id WHERE f.follower_id = :u AND "
                             + bs.active_sql("f.followed_id") + " ORDER BY f.id", u=uid)
        followers = _q(conn, "SELECT u.tw_id, u.full_name, f.created_at FROM profile_follows f "
                             "JOIN users u ON u.id = f.follower_id WHERE f.followed_id = :u AND "
                             + bs.active_sql("f.follower_id") + " ORDER BY f.id", u=uid)
        blocked = [_party(r) for r in _q(
            conn, "SELECT u.tw_id, b.created_at, u.deleted_at IS NOT NULL AS is_deleted FROM blocks b "
                  "JOIN users u ON u.id = b.blocked_id WHERE b.blocker_id = :u ORDER BY b.created_at", u=uid)]

        # Own applications — the status as the applicant sees it (never the pipeline / company notes)
        applications = []
        for r in _q(conn, "SELECT ja.id, ja.job_id, j.title AS job_title, ja.status, ja.cover_letter, ja.applied_at, "
                          "c.full_name AS company_name, c.tw_id AS company_tw_id, "
                          "c.deleted_at IS NOT NULL AS company_deleted "
                          "FROM job_applications ja JOIN jobs j ON j.id = ja.job_id "
                          "JOIN users c ON c.id = j.company_id WHERE ja.user_id = :u ORDER BY ja.applied_at", u=uid):
            r["status"] = auth.applicant_visible_status(r["status"])
            if r.pop("company_deleted"):
                r["company_name"], r["company_tw_id"] = ad.deleted_label(), None
            applications.append(r)

        # Messages this user SENT only — never the other side's
        messages = [_party(r) for r in _q(
            conn, "SELECT m.id, m.content, m.created_at, u.tw_id AS conversation_with_tw_id, "
                  "u.deleted_at IS NOT NULL AS is_deleted FROM messages m JOIN users u ON u.id = m.receiver_id "
                  "WHERE m.sender_id = :u ORDER BY m.id", u=uid)]
        for m in messages:
            if m.get("is_deleted"):
                m["conversation_with_tw_id"] = None

        # Appointments this user takes part in — time + status (+ notes only when this user wrote them)
        appointments = _q(conn, "SELECT a.id, a.job_id, j.title AS job_title, a.status, a.mode, a.scheduled_at, "
                                "a.response_deadline_at, a.created_at, a.closed_at, "
                                "CASE WHEN a.company_id = :u THEN 'company' WHEN a.applicant_id = :u THEN 'applicant' "
                                "ELSE 'participant' END AS role, "
                                "CASE WHEN a.created_by = :u THEN a.notes END AS my_notes "
                                "FROM appointments a LEFT JOIN jobs j ON j.id = a.job_id "
                                "WHERE a.company_id = :u OR a.applicant_id = :u OR EXISTS (SELECT 1 FROM "
                                "appointment_participants p WHERE p.appointment_id = a.id AND p.user_id = :u) "
                                "ORDER BY a.id", u=uid)

        notifications = _q(conn, "SELECT type, title, body, link, is_read, created_at FROM notifications "
                                 "WHERE user_id = :u ORDER BY id", u=uid)

        kyc = _one(conn, "SELECT step, status, email_verified, phone_verified, submitted_at, reviewed_at, "
                         "CASE WHEN status = 'rejected' THEN reject_reason END AS reject_reason, "
                         "(id_front_url IS NOT NULL AND id_front_url <> '') AS has_id_document, "
                         "(selfie_url IS NOT NULL AND selfie_url <> '') AS has_selfie "
                         "FROM kyc_submissions WHERE user_id = :u", u=uid)

    out = {
        "export": {"format_version": FORMAT_VERSION, "generated_at": datetime.utcnow().isoformat() + "Z",
                   "tw_id": account["tw_id"]},
        "account": account,
        "profile": profile,
        "company": company,
        "posts": posts,
        "comments": comments,
        "saved_posts": saved,
        "appreciated_posts": appreciated,
        "following": following,
        "followers": followers,
        "blocked": blocked,
        "applications": applications,
        "messages_sent": messages,
        "appointments": appointments,
        "notifications": notifications,
        "email_notifications": auth.get_email_prefs(uid, email_service.PREF_TYPES),
        "kyc": kyc,
    }
    bad = forbidden_keys(out)
    if bad:   # defense in depth — a new column must never slip a secret into the file
        raise RuntimeError(f"data export carries forbidden keys: {bad[:5]}")
    return out

