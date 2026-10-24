// static/shared/admin-sections.js — Admin Shell registry (task 5.3a · docs/rules/admin-shell.md)
// The ONE list of admin panel sections. TwAdminShell (admin-shell.js) builds the admin menu from it;
// a new admin page / section = one line here (+ its twT key in tw_strings.json).
//   key       unique id (admin.html shows the section with the same key)
//   icon      DS-ICON name (the one icon registry — F37)
//   labelKey  twT key of the menu label
//   path      relative to the admin panel root: '' = panel root · '#x' = section x of the root page
//             · 'name' = sub page (server route = panel root + '/name')
//   badge     optional — count source in TwAdminShell (BADGE_SOURCES): 'reports' | 'kyc'
// ❌ the panel slug or its prefix in this file (or any served file) — paths are relative only.
// Order = the menu order (task 5.3a2). 'companies' = the users table with a fixed type filter (no 2nd table code).
window.TW_ADMIN_SECTIONS = [
  { key: 'overview',  icon: 'home',             labelKey: 'admin.nav.overview',  path: '' },
  { key: 'users',     icon: 'users',            labelKey: 'admin.nav.users',     path: '#users' },
  { key: 'companies', icon: 'building-2',       labelKey: 'admin.nav.companies', path: '#companies' },
  { key: 'jobs',      icon: 'briefcase',        labelKey: 'admin.nav.jobs',      path: '#jobs' },
  { key: 'kyc',       icon: 'id-card',          labelKey: 'admin.nav.kyc',       path: '#kyc', badge: 'kyc' },
  { key: 'reports',   icon: 'report',           labelKey: 'admin.nav.reports',   path: '#reports', badge: 'reports' },
  { key: 'support',   icon: 'headset',          labelKey: 'admin.nav.support',   path: 'support' },    // task 7.1
  { key: 'activity',  icon: 'activity',         labelKey: 'admin.nav.activity',  path: '#activity' },
  { key: 'audit',     icon: 'shield',           labelKey: 'admin.nav.audit',     path: '#audit' },
  { key: 'errors',    icon: 'alert',            labelKey: 'admin.nav.errors',    path: '#errors' },
  { key: 'email',     icon: 'mail',             labelKey: 'admin.nav.email',     path: 'email' },
  { key: 'settings',  icon: 'settings-2',       labelKey: 'admin.nav.settings',  path: 'settings' },   // task 4.1
  { key: 'content',   icon: 'file-text',        labelKey: 'admin.nav.content',   path: 'content' },    // phase 5b
  { key: 'system',    icon: 'wrench',           labelKey: 'admin.nav.system',    path: '#system' },
];
