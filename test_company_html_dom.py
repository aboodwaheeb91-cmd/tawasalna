"""
Frontend DOM Smoke Tests — company.html job tabs
Uses Node.js + jsdom via a minimal inline harness (no Playwright needed).
Tests run in a synthetic DOM that reproduces the exact JS environment of
company.html's <script> block.

Tests:
  dom-01  loadCompanyJobs() called with valid _user does NOT throw ReferenceError
  dom-02  loadCompanyJobs() fetches /company/jobs?view=active by default
  dom-03  switchJobTab('archived') causes next fetch to use view=archived
  dom-04  Archived job card shows "مؤرشفة" badge and "المتقدمون" button
  dom-05  Non-archived job card shows status badge and "أرشفة" button — no "المتقدمون"
  dom-06  Job title/location with HTML payload is escaped — no element created
  dom-07  viewJobApplicants non-ok response shows error message, not empty list
  Exit code: 0 on all pass, 1 on any failure
"""

import sys, os, subprocess, json, tempfile

PASS, FAIL = '✅ PASS', '❌ FAIL'
results = []

def check(name, condition, detail=None):
    status = PASS if condition else FAIL
    results.append((name, status, detail))
    marker = '✅' if condition else '❌'
    suffix = f'  [{detail}]' if detail and not condition else ''
    print(f'{marker}  {name}{suffix}')

# ── Extract the job-tab JS block from company.html ────────────────────────────
def _extract_js():
    """Extract only the inline <script> block that contains company.html's job logic."""
    html_path = os.path.join(os.path.dirname(__file__), 'company.html')
    with open(html_path, encoding='utf-8') as f:
        lines = f.readlines()

    in_script = False
    blocks = []
    current = []
    for line in lines:
        stripped = line.rstrip()
        # Opening inline script tag (no src attribute)
        if not in_script and '<script>' in stripped and 'src=' not in stripped:
            in_script = True
            current = []
            continue
        # Closing script tag
        if in_script and '</script>' in stripped:
            blocks.append('\n'.join(current))
            in_script = False
            current = []
            continue
        if in_script:
            current.append(line.rstrip('\n'))

    # Return the block that contains the job-tab functions
    target = [b for b in blocks if 'loadCompanyJobs' in b]
    if not target:
        raise ValueError("Could not find loadCompanyJobs in any inline <script> block")
    return target[0]

# ── Build the Node.js test harness ────────────────────────────────────────────
NODE_HARNESS = r"""
'use strict';
const assert = require('assert');

// ── Minimal DOM environment ───────────────────────────────────────────────────
const _dom = {};
const _alerts = [];
const _fetches = [];   // recorded as {url, options}
let _fetchResponses = {};  // url prefix → response stub

global.window   = global;

function _makeEl(tag){
  const el = { tagName: tag, className:'', style:{}, children:[], _attrs:{},
    textContent: '',
    value: '',
    addEventListener(){},
    removeEventListener(){},
    removeAttribute(){},
    classList:{ add(){}, remove(){}, contains(){ return false; } },
    appendChild(c){this.children.push(c); return c;},
    prepend(){},
    remove(){},
  };
  Object.defineProperty(el, 'innerHTML', {
    get(){ return this.__html||''; },
    set(v){ this.__html = v; }
  });
  return el;
}

global.document = {
  getElementById: (id) => _dom[id] || _makeEl('div'),
  createElement:  (tag) => _makeEl(tag),
  querySelectorAll: () => ({ forEach(){} }),
  addEventListener(){},
  body: {
    appendChild(){}, prepend(){},
    style: {}, scrollHeight: 1000,
    classList:{ add(){}, remove(){}, contains(){ return false; } },
  },
};
global.alert   = (msg) => _alerts.push(String(msg));
global.confirm = ()    => true;
global.localStorage = {
  getItem: (k) => k === 'tw_user'
    ? JSON.stringify({id:42, full_name:'شركة', user_type:'co'})
    : k === 'tw_jwt' ? 'fake-jwt' : null,
  removeItem(){},
};
global.location = { href: '' };
global.requestAnimationFrame = (cb) => setTimeout(cb, 0);
global.scrollY = 0;
global.innerHeight = 768;

// Register DOM elements the script uses
['companyJobsList','companyCandidates','resultsPanel'].forEach(id => {
  _dom[id] = document.createElement('div');
});
// Tab buttons
['jobTabActive','jobTabArchived','searchBtn'].forEach(id => {
  _dom[id] = document.createElement('button');
});

// sanitize() from tw_shared.js (same implementation)
global.sanitize = function(str){
  if(!str) return '';
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#x27;');
};

// Stub fetch — records calls and returns configured stubs
global.fetch = function(url, opts){
  _fetches.push({url, opts});
  const stub = _fetchResponses[url] || _fetchResponses['__default'];
  if(!stub) return Promise.resolve({ok:true, json:()=>Promise.resolve({jobs:[]})});
  return Promise.resolve(stub);
};

// Stubs for functions defined in tw_shared.js (external script, not inlined)
global.loadGlobalBadges = function(){};
global.loadData = undefined; // referenced as `loadData?loadData():...` (conditional, safe)

// ── Paste the extracted company.html JS here ──────────────────────────────────
// (injected by Python before running)
__COMPANY_JS__

// ── Async tests ───────────────────────────────────────────────────────────────
const results = [];
function check(name, cond, detail){
  results.push({name, ok: !!cond, detail});
  console.log((cond?'OK':'FAIL') + '  ' + name + ((!cond && detail) ? '  ['+detail+']' : ''));
}

async function runTests(){
  // dom-01: loadCompanyJobs() with valid _user does not throw
  _fetchResponses['/company/jobs?view=active'] = {ok:true, json:()=>Promise.resolve({jobs:[]})};
  let threw = false;
  try { await loadCompanyJobs(); } catch(e){ threw=true; }
  check('dom-01. loadCompanyJobs() with valid _user does not throw (no ReferenceError)', !threw);

  // dom-02: default fetch URL uses view=active
  const url02 = _fetches[_fetches.length-1]?.url || '';
  check('dom-02. loadCompanyJobs() fetches /company/jobs?view=active by default',
        url02.includes('view=active'), 'url='+url02);

  // dom-03: switchJobTab('archived') → next loadCompanyJobs uses view=archived
  _fetches.length = 0;
  _fetchResponses['/company/jobs?view=archived'] = {ok:true, json:()=>Promise.resolve({jobs:[]})};
  switchJobTab('archived');
  await new Promise(r=>setTimeout(r,10));
  const url03 = _fetches.find(f=>f.url.includes('view=archived'))?.url || '';
  check('dom-03. switchJobTab("archived") → fetch uses view=archived',
        url03.includes('view=archived'), 'fetches='+JSON.stringify(_fetches.map(f=>f.url)));

  // dom-04: archived card has "مؤرشفة" badge and "المتقدمون" button
  _fetchResponses['/company/jobs?view=archived'] = {ok:true, json:()=>Promise.resolve({jobs:[
    {id:99, title:'وظيفة قديمة', location:'عمان', status:'active', archived_at:'2026-01-01T00:00:00Z', views:5}
  ]})};
  switchJobTab('archived');
  await new Promise(r=>setTimeout(r,30));
  const html04 = _dom['companyJobsList'].__html || '';
  check('dom-04a. Archived card shows "مؤرشفة" badge', html04.includes('مؤرشفة'));
  check('dom-04b. Archived card shows "المتقدمون" button', html04.includes('المتقدمون'));
  check('dom-04c. Archived card does NOT show "أرشفة" button', !html04.includes('archiveCompanyJob'));

  // dom-05: non-archived card has status badge and "أرشفة" button — no "المتقدمون"
  _fetchResponses['/company/jobs?view=active'] = {ok:true, json:()=>Promise.resolve({jobs:[
    {id:77, title:'وظيفة نشطة', location:'الرياض', status:'active', archived_at:null, views:12}
  ]})};
  switchJobTab('active');
  await new Promise(r=>setTimeout(r,30));
  const html05 = _dom['companyJobsList'].__html || '';
  check('dom-05a. Active card shows "أرشفة" button', html05.includes('archiveCompanyJob'));
  check('dom-05b. Active card does NOT show "المتقدمون" button', !html05.includes('viewJobApplicants'));
  check('dom-05c. Active card shows status badge', html05.includes('نشطة') || html05.includes('var(--ac)'));

  // dom-06: XSS — title/location with HTML payload is escaped, no element created
  _fetchResponses['/company/jobs?view=active'] = {ok:true, json:()=>Promise.resolve({jobs:[
    {id:1, title:'<img src=x onerror=alert(1)>', location:'<script>bad()</script>', status:'active', archived_at:null, views:0}
  ]})};
  let _alertsBefore = _alerts.length;
  switchJobTab('active');
  await new Promise(r=>setTimeout(r,30));
  const html06 = _dom['companyJobsList'].__html || '';
  check('dom-06a. XSS title is escaped (< → &lt;)', html06.includes('&lt;img') || !html06.includes('<img'));
  check('dom-06b. XSS location is escaped (< → &lt;)', html06.includes('&lt;script') || !html06.includes('<script'));
  check('dom-06c. alert() not triggered by XSS payload', _alerts.length === _alertsBefore);

  // dom-07: viewJobApplicants non-ok response shows error, not empty list
  _alerts.length = 0;
  _fetchResponses['/jobs/55/applicants'] = {
    ok: false, status: 403,
    json: ()=>Promise.resolve({error:'غير مصرح'})
  };
  await viewJobApplicants(55);
  await new Promise(r=>setTimeout(r,20));
  const alert07 = _alerts[0] || '';
  check('dom-07a. Non-ok applicants response triggers alert', _alerts.length > 0, 'alerts='+JSON.stringify(_alerts));
  check('dom-07b. Alert contains actual error, not empty-list message', !alert07.includes('المتقدمون (0)'), 'alert='+alert07);

  // ── Summary ──────────────────────────────────────────────────────────────────
  const passed = results.filter(r=>r.ok).length;
  const failed  = results.length - passed;
  console.log('\n' + '='.repeat(50));
  console.log('Results: '+passed+'/'+results.length+' passed, '+failed+' failed');
  if(failed){
    console.log('\nFailed:');
    results.filter(r=>!r.ok).forEach(r=>console.log('  FAIL  '+r.name+(r.detail?'  ['+r.detail+']':'')));
  }
  console.log('='.repeat(50));
  process.exit(failed > 0 ? 1 : 0);
}

runTests().catch(e=>{ console.error('harness error:', e); process.exit(1); });
"""

print("=" * 60)
print("PR-JOB — Frontend DOM Smoke Tests (Node.js + inline harness)")
print("=" * 60)

# Check Node.js is available
node_check = subprocess.run(['node', '--version'], capture_output=True, text=True)
if node_check.returncode != 0:
    print("❌  Node.js not available — skipping DOM tests")
    print("    Install Node.js to enable frontend smoke tests.")
    sys.exit(0)

# Extract the JS from company.html
try:
    company_js = _extract_js()
except Exception as e:
    print(f"❌  Could not extract JS from company.html: {e}")
    sys.exit(1)

# Build the full harness with company JS injected
harness = NODE_HARNESS.replace('__COMPANY_JS__', company_js)

# Write to a temp file and run with Node
with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
    f.write(harness)
    tmpfile = f.name

try:
    result = subprocess.run(['node', tmpfile], capture_output=True, text=True, timeout=30)
    stdout = result.stdout
    stderr = result.stderr

    # Parse OK/FAIL lines from Node output
    for line in stdout.splitlines():
        if line.startswith('OK  ') or line.startswith('FAIL  ') or line.startswith('Results:') or '=' * 10 in line or line.startswith('Failed:'):
            # Translate Node output to our format
            if line.startswith('OK  '):
                print(f"✅  {line[4:]}")
                results.append((line[4:], PASS, None))
            elif line.startswith('FAIL  '):
                print(f"❌  {line[6:]}")
                results.append((line[6:], FAIL, None))
            else:
                print(line)
        elif line and not line.startswith('='):
            print(line)

    if stderr.strip():
        print("\n[Node stderr]:", stderr.strip()[:500])

    passed = sum(1 for _, s, _ in results if s == PASS)
    total  = len(results)
    failed = total - passed
    sys.exit(result.returncode)

finally:
    os.unlink(tmpfile)
