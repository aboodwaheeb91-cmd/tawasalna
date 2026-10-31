// static/shared/admin-sections.js — Admin Shell registry (task 5.3a · docs/rules/admin-shell.md)
// The ONE list of admin panel sections. TwAdminShell (admin-shell.js) builds the admin menu from it;
// a new admin page / section = one line here (+ its twT key in tw_strings.json).
//   key       unique id (admin.html shows the section with the same key)
//   icon      DS-ICON name (the one icon registry — F37)
//   labelKey  twT key of the menu label
//   path      relative to the admin panel root: '' = panel root · '#x' = section x of the root page
//             · 'name' = sub page (server route = panel root + '/name')
//   perm      the admin_perms.py perm of the section's data route (docs/rules/admin-staff.md table, task 8.4c-1) —
//             TwAdminShell hides the link / badge / quick icon when GET /admin/me lacks it (UX only — the
//             server checks every route; /admin/me failed → the full menu)
//   badge     optional — count source in TwAdminShell (BADGE_SOURCES): 'reports' | 'kyc' | 'support'
// ❌ the panel slug or its prefix in this file (or any served file) — paths are relative only.
// Order = the menu order (task 5.3a2). 'companies' = the users table with a fixed type filter (no 2nd table code).
window.TW_ADMIN_SECTIONS = [
  { key: 'overview',  icon: 'home',             labelKey: 'admin.nav.overview',  perm: 'stats.view', path: '' },
  { key: 'users',     icon: 'users',            labelKey: 'admin.nav.users',     perm: 'users.view', path: '#users' },
  { key: 'companies', icon: 'building-2',       labelKey: 'admin.nav.companies', perm: 'users.view', path: '#companies' },
  { key: 'jobs',      icon: 'briefcase',        labelKey: 'admin.nav.jobs',      perm: 'jobs.manage', path: '#jobs' },
  { key: 'kyc',       icon: 'id-card',          labelKey: 'admin.nav.kyc',       perm: 'kyc.review', path: '#kyc', badge: 'kyc' },
  { key: 'reports',   icon: 'report',           labelKey: 'admin.nav.reports',   perm: 'reports.manage', path: '#reports', badge: 'reports' },
  { key: 'support',   icon: 'headset',          labelKey: 'admin.nav.support',   perm: 'support.manage', path: 'support', badge: 'support' },    // task 7.1 · badge = new tickets (7.2a)
  { key: 'activity',  icon: 'activity',         labelKey: 'admin.nav.activity',  perm: 'stats.view', path: '#activity' },
  { key: 'audit',     icon: 'shield',           labelKey: 'admin.nav.audit',     perm: 'audit.view', path: '#audit' },
  { key: 'errors',    icon: 'alert',            labelKey: 'admin.nav.errors',    perm: 'system.manage', path: '#errors' },
  { key: 'email',     icon: 'mail',             labelKey: 'admin.nav.email',     perm: 'settings.edit', path: 'email' },
  { key: 'settings',  icon: 'settings-2',       labelKey: 'admin.nav.settings',  perm: 'settings.edit', path: 'settings' },   // task 4.1
  { key: 'content',   icon: 'file-text',        labelKey: 'admin.nav.content',   perm: 'content.edit', path: 'content' },    // phase 5b
  { key: 'system',    icon: 'wrench',           labelKey: 'admin.nav.system',    perm: 'system.manage', path: '#system' },
  { key: 'staff',     icon: 'shield-check',     labelKey: 'admin.nav.staff',     perm: 'staff.manage', path: 'staff' },      // task 8.4c-2b-2 — owner only
];
