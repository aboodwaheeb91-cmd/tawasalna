# Color System V1 (DS-COLOR)

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Color System V1 (DS-COLOR) Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.
Full specification: `docs/design-system/COLOR-SYSTEM.md` (CLR-00 → CLR-36).

1. **Always check CLR-00 first.** Any task involving color (adding a new color, changing a color, defining a token, migrating a hardcoded hex) must start at CLR-00 (Routing Protocol) in `COLOR-SYSTEM.md`. Do NOT guess which token to use — follow the routing table.

2. **`--color-*` namespace is reserved for DS-COLOR exclusively.** No page CSS file (e.g. `company.css`, `profile-v2.css`, `index.css`) may define or redefine any `--color-*` variable. All `--color-*` tokens live only in `tw_shared.css` (Runtime Source of Truth — Phase 1 ✅ complete).

3. **Feature CSS uses Semantic layer tokens only.** Feature CSS files reference `--color-brand-*`, `--color-surface-*`, `--color-border-*`, `--color-text-*`, `--color-status-*`, or `--color-categorical-*`. They never reference Foundation/Primitive tokens (`--color-prim-*`) directly. For alpha/rgba variants, use Semantic RGB channels (`--color-brand-primary-rgb`, `--color-status-success-rgb`) — never `--color-prim-*-rgb` directly.

4. **Domain Aliases (Tier 2) reference DS-COLOR — they never define their own hex values.**
   ```css
   ✅  --co-accent: var(--color-brand-secondary);
   ❌  --co-accent: #2563ff;  /* hardcoded hex in T2 = architectural violation */
   ```

5. **Token Identity ≠ Token Value.** Two tokens with the same hex value are independent. Changing `--color-brand-primary` does not automatically change `--color-categorical-teal`, even if both happen to be `#00c896` today. Treat each token as its own identity.

6. **Semantic ≠ Categorical — never cross-use.**
   - `--color-status-warning` = UX signal (something is wrong/risky). Use for: form errors, expiration notices, warnings.
   - `--color-categorical-amber` = data category marker (e.g. "expert" skill level in Tawasolna). Use for: charts, skill tiers, badges.
   - Using a Status token for data categorization (or vice versa) is a permanent violation.
   - **Tawasolna skill level mapping:** beginner=`--color-categorical-neutral`, intermediate=`--color-categorical-blue`, good=`--color-categorical-purple`, advanced=`--color-categorical-teal`, expert=`--color-categorical-amber`.

7. **Migration ≠ Redesign.**
   - `#00c896` → `var(--color-brand-primary)` = migration (zero visual change, approved).
   - `#00c896` → `#00b386` = redesign (visual change, requires explicit architectural approval).
   - Never bundle a redesign inside a migration PR.

8. **`company.css` architectural debt (CLR-16).** `company.css` redefines `--ac: #2563ff` and `--ac2: #00c896` (swapping the global teal/blue values). This is a known architectural debt — do NOT "fix" it by further overriding tokens. The planned migration path is: replace with `--co-accent: var(--color-brand-secondary)` in a dedicated Phase 1+ PR.

9. **Phase 0 ✅ Documentation Only (complete). Phase 1 ✅ Runtime Tokens Foundation (complete — PR #520).** `tw_shared.css` now contains `--color-*` tokens in three sections (Foundation/Semantic/Legacy Aliases). `--t3` consumer audit complete: `--t3` → `var(--color-text-muted)` ✅ (all consumers are muted-role text). `--t4` mapping deferred to Phase 2: `--t4` remains raw `rgba(255,255,255,.2)` (mixed consumers — placeholder + subtitle; requires Phase 2 consumer separation before canonical mapping). Phase 2+ = gradual page-by-page migration when pages are touched — requires explicit approval per page/system. Phase 4 = remove Legacy Aliases at zero consumers. Any DS-COLOR change needs a declared PR specifying the change type (migration / redesign / phase change).

10. **Alpha values follow the 6-level scale (CLR-19).** Values outside the scale require justification in the PR description. The scale is a text contract — not CSS custom properties.

11. **Color Role Assignment (CLR-33).** Every visible UI element must have an intentional known Color Role. Do not let color be determined by accidental inheritance or browser defaults. When no suitable role exists in DS-COLOR, use a Tier 2/3 domain role and document it as a gap if it could become shared.

12. **Phase 2 — full token set (PR 3.8 · CLR-35).** Every color the site uses has a Semantic token in `tw_shared.css`; near colors are merged (CLR-35 merge table — from → to). Alpha = `rgba(var(--color-<token>-rgb), a)`; every `-rgb` channel is the twin of a base token with the same name. Neutral translucency is built only from `--color-ink-rgb` (foreground ink — flips in a future light theme) or `--color-overlay-rgb` (scrim / shadow).

13. **Shared files carry zero hardcoded colors.** `tw_shared.css` (except `--color-*` definition lines) · `static/app-header.css` · `static/home-v2.css` · `static/shared/*` — enforced by `python -m pytest tests/test_ds_color_tokens.py -q` (C4). No `var(--x, #hex)` fallbacks either. The only exception is a same-line comment `tw-color-literal: <reason>` (image data, never UI). JS/canvas reads a token with `getComputedStyle(document.documentElement).getPropertyValue('--color-…')`; a CSS value set from JS is the string `var(--color-…)`. Other files: report only (`python scripts/ds_color_audit.py`) — each page migrates with its page (Phase 4) using the CLR-35 table and lists its visual difference in its PR.

14. **One admin override (CLR-36).** `site_settings.theme_color_tokens` (JSON `{token: color}`) → `GET /theme.css` (one `:root{}` — empty without an override) loaded by the shell head right after `tw_shared.css` · `GET/PUT /admin/theme/colors` (`check_admin`; known Semantic tokens + strict color values only; twin `-rgb` derived by the server; every save logged). Source: `theme_tokens.py`. No admin UI yet.

15. **Light theme readiness (CLR-23).** A future `:root[data-theme="light"]` block in `tw_shared.css` remaps Section B only; `data-theme` goes on `<html>` only. Do not build it without an explicit task.

### Forbidden (permanent)

```
❌ --color-* variable defined or overridden outside tw_shared.css
❌ Page CSS overriding any --color-* token
❌ Changing any DS-COLOR token or Legacy Alias value without a declared DS-COLOR PR
❌ color: #00c896 hardcoded in new feature CSS (use var(--color-brand-primary))
❌ --color-status-* used for data categorization
❌ --color-categorical-* used for UX status signals
❌ T2 domain alias with a hardcoded hex value
❌ Adding a token with no real V1 consumer
❌ DS-COLOR Phase 2 page migration without explicit approval per page/system
❌ Parallel color system outside DS-COLOR
❌ A second color-override source (localStorage, inline style, another CSS file) — /theme.css only
❌ A hardcoded color (or var() fallback color) in tw_shared.css rules / app-header.css / home-v2.css / static/shared/*
❌ An -rgb channel without its base token (twin rule)
❌ --color-prim-*-rgb used directly in feature CSS (use Semantic RGB channels)
❌ --color-status-info: var(--color-brand-secondary) (Semantic→Semantic coupling — both must reference --color-prim-blue independently)
❌ Using --t4 as a canonical Semantic token (--t4 remains raw rgba(255,255,255,.2) pending Phase 2 consumer separation)
```

### Non-CSS Color Mirror (mandatory — added Phase 2)

`<meta name="theme-color" content="#00c896">` in `index.html` cannot reference CSS custom properties. It must stay as a literal hex value. **During any Brand Redesign that changes `--color-brand-primary`, this `<meta>` tag must be updated manually to match the new value.** Do NOT remove the meta tag; do NOT set it to a CSS var string (browsers ignore it). Document the alignment check in the PR description of any Brand Redesign PR.
