# System Registry Check — فحص فهرس الأنظمة

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Pre-PR System Registry Check (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

**Before implementing any new feature or opening a PR, you MUST:**

1. Read `docs/SYSTEMS_INDEX.md` — the authoritative index of all documented systems.
2. Find the relevant system entry and note the "Source of Truth" and "Details" pointer.
3. Read the linked section in ARCHITECTURE.md or CLAUDE.md.
4. Read any shared files the system depends on.

Then decide:
- **Use** the existing system if it already covers the need.
- **Extend** the existing system if the need is a natural addition.
- **Document as missing** — add to `docs/SYSTEMS_INDEX.md → Systems Needing Documentation` before building anything new.

### Forbidden without checking the index first

```
❌ Building a system that duplicates an existing one
❌ Creating a DB table when an official table exists for the same purpose
❌ Using localStorage as permanent storage when a backend system exists or is planned
❌ Creating a per-page helper/catalog/mapping that already exists in a shared module
❌ Adding a new public profile route outside Smart Router
❌ Implementing skill icons or category lists outside tw-skills.js / tw-options-data.js
❌ Copying logic from one system into another instead of using the shared helper
```

### Index location

`docs/SYSTEMS_INDEX.md` — read it (as an index) before every PR.

---

## Rule Index First (mandatory for all AI sessions)

This rule is permanent and applies to all future AI sessions.

**Before implementing any new feature, fix, or opening a PR:**

1. Read `docs/SYSTEMS_INDEX.md` — the authoritative index of all documented systems.
2. Locate the system that matches your change. Note its "Source of Truth" and "Details" pointers.
3. Follow the documented system; do not rebuild it from scratch.

This rule is a shortcut to the full checklist in `CLAUDE.md → Pre-PR System Registry Check`. Both are mandatory — this one is the quick reminder, the other is the full procedure.

### Forbidden without reading the index first

```
❌ Building a system that duplicates an existing one
❌ Creating a DB table when an official table exists for the same purpose
❌ Adding a new endpoint that overlaps with a documented API contract
❌ Using localStorage as permanent storage when a backend system exists
❌ Creating a per-page helper/catalog/mapping that already exists in a shared module
```
