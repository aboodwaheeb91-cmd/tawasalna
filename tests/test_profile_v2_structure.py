"""test_profile_v2_structure.py — PR 4.2a: Profile V2 structure + errors.

  A  _calc_profile_score = the ONE completion checklist (PROFILE_SCORE_ITEMS, F29): points sum to
     100 · empty profile → 0 · full → 100 · city / country count as location · profession_id counts
  B  GET /profile/{id}/score: everyone → score + level · items + tips only for the owner JWT / admin
     (PROFILE-DATA-VISIBILITY → Completion score) — a visitor never gets the checklist
  C  load error (real profile-v2.render.js in node vm): 404 → "not found" (no retry) · network →
     "check connection" + retry · error state visible ([hidden] removed) and the skeleton hidden
     (root cause: CSS display:none + inline style '' → blank page)
  D  completion card (real profile-v2.completion.js): % and the stats tile come from /score;
     no server score → card hidden

Run: python tests/test_profile_v2_structure.py
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("JWT_SECRET", "test-secret-for-profile-structure-0123456789")

import server  # noqa: E402

failures = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  [{detail}]"))
    if not cond:
        failures.append(name)


class FakeConn:
    """profiles row + per-table counts; answers the queries _calc_profile_score makes."""
    def __init__(self, prof, counts):
        self.prof, self.counts, self.columns = prof, counts, []

    def run(self, sql, **kw):
        if sql.lstrip().upper().startswith("SELECT HEADLINE"):
            if self.prof is None:
                return []
            cols = [c.strip() for c in sql.split("SELECT", 1)[1].split("FROM", 1)[0].split(",")]
            self.columns = [{"name": c} for c in cols]
            return [[self.prof.get(c) for c in cols]]
        table = sql.split("FROM", 1)[1].split()[0]
        return [[self.counts.get(table, 0)]]


FULL_PROF = {"avatar_url": "https://x/a.png", "headline": None, "title": "", "bio": "bio", "short_bio": "s",
             "location": None, "city": "عمّان", "country": None, "avail": "open", "profession_id": 3,
             "is_verified": True}
FULL_COUNTS = {"experience": 1, "education": 1, "user_skills": 3, "user_links": 1, "courses": 1, "user_langs": 1}

print("\nA — one checklist on the server")
check("A points sum to 100", sum(p for _, p, _ in server.PROFILE_SCORE_ITEMS) == 100)
ids = [i for i, _, _ in server.PROFILE_SCORE_ITEMS]
check("A ids unique", len(ids) == len(set(ids)), ids)
empty = server._calc_profile_score(1, FakeConn({}, {}))
check("A empty profile → 0, every item missing", empty["score"] == 0 and not any(i["done"] for i in empty["items"]))
full = server._calc_profile_score(1, FakeConn(FULL_PROF, FULL_COUNTS))
check("A full profile → 100 (city = location · profession_id = profession)", full["score"] == 100, full["items"])
two = server._calc_profile_score(1, FakeConn(FULL_PROF, dict(FULL_COUNTS, user_skills=2)))
check("A skills need 3 (2 skills → item missing, -10)", two["score"] == 90
      and [i for i in two["items"] if i["id"] == "skills"][0]["done"] is False)
none = server._calc_profile_score(1, FakeConn(None, FULL_COUNTS))
check("A no profiles row → 0", none["score"] == 0)

print("\nB — GET /profile/{id}/score (privacy: checklist = owner / admin only)")
from fastapi.testclient import TestClient  # noqa: E402
_orig = (server.get_conn, server.release_conn, server._password_changed_epoch)
server.get_conn = lambda: FakeConn(FULL_PROF, dict(FULL_COUNTS, courses=0))
server.release_conn = lambda c: None
server._password_changed_epoch = lambda uid: None   # no DB for the session-invalidation lookup
client = TestClient(server.app)
try:
    guest = client.get("/profile/7/score")
    other = client.get("/profile/7/score",
                       headers={"Authorization": "Bearer " + server._jwt_encode({"user_id": 8, "user_type": "co"})})
    owner = client.get("/profile/7/score",
                       headers={"Authorization": "Bearer " + server._jwt_encode({"user_id": 7, "user_type": "emp"})})
    bad = client.get("/profile/7/score", headers={"X-Admin-Token": "not-a-valid-admin-jwt"})
finally:
    server.get_conn, server.release_conn, server._password_changed_epoch = _orig
g, o, w, b = (x.json() if x.status_code == 200 else {} for x in (guest, other, owner, bad))
check("B visitor (no JWT) → score + level only — no items / tips",
      guest.status_code == 200 and g.get("score") == 95 and set(g) == {"score", "level"}, (guest.status_code, g))
check("B another account's JWT → no items / tips", set(o) == {"score", "level"}, o)
check("B invalid admin token → no items / tips", set(b) == {"score", "level"}, (bad.status_code, b))
check("B owner JWT → score 95 + tips + items with id/done/points",
      w.get("score") == 95 and "tips" in w and len(w.get("items", [])) == len(ids)
      and all(set(i) == {"id", "done", "points"} for i in w["items"]), w)

NODE = r"""
const vm = require('vm'), fs = require('fs');
function el() {
  return { hidden: false, style: {}, textContent: '', innerHTML: '', dataset: {},
    classList: { add() {}, remove() {}, contains() { return false; }, toggle() {} },
    addEventListener() {}, setAttribute() {}, appendChild() {},
    querySelector() { return null; }, querySelectorAll() { return []; } };
}
function ctxWith(els, extra) {
  const ctx = Object.assign({ console: { log() {}, warn() {}, error() {} }, setTimeout, clearTimeout,
    setInterval() {}, requestAnimationFrame() {}, URLSearchParams, addEventListener() {},
    location: { search: '', pathname: '/u/U1' }, history: {},
    twT: k => k, twEscHtml: v => String(v), twEscAttr: v => String(v),
    document: { getElementById: id => els[id] || null, querySelector() { return null; },
      querySelectorAll() { return []; }, addEventListener() {},
      body: { classList: { contains() { return false; }, add() {}, remove() {} } } } }, extra);
  ctx.window = ctx;
  vm.createContext(ctx);
  return ctx;
}
async function loadError(status) {
  const els = { scLoading: el(), scContent: el(), scErrorState: el(), scErrTitle: el(), scErrSub: el(), scRetryBtn: el() };
  els.scErrorState.hidden = true;
  const ctx = ctxWith(els, { _scProfileIdFromRoute: 5,
    getProfile: () => Promise.reject(Object.assign(new Error('x'), { status })) });
  vm.runInContext(fs.readFileSync('profile-v2.state.js', 'utf8'), ctx);
  vm.runInContext(fs.readFileSync('profile-v2.render.js', 'utf8'), ctx);
  await new Promise(r => setTimeout(r, 10));
  return { shown: els.scErrorState.hidden === false, loading: els.scLoading.style.display,
           title: els.scErrTitle.textContent, retryHidden: els.scRetryBtn.hidden };
}
async function completion(score) {
  const ids = ['scComplCard', 'scComplPct', 'scComplFill', 'scComplLabel', 'scComplToggle', 'scComplPanel',
               'scComplList', 'scComplRow', 'scStatScore', 'scGrowthRow', 'scGrowthPanel'];
  const els = {}; ids.forEach(i => { els[i] = el(); });
  els.scComplPanel.style.display = 'none';
  const ctx = ctxWith(els, { _scViewerType: 'owner', _scUserId: 5, _scProfile: {},
    getScore: () => Promise.resolve(score) });
  vm.runInContext(fs.readFileSync('profile-v2.completion.js', 'utf8'), ctx);
  ctx._updateCompletion();
  await new Promise(r => setTimeout(r, 10));
  return { card: els.scComplCard.style.display, pct: els.scComplPct.textContent, tile: els.scStatScore.textContent };
}
(async () => {
  const out = { e404: await loadError(404), eNet: await loadError(0),
    c55: await completion({ score: 55, items: [{ id: 'exp', done: false, points: 15 }] }),
    cNone: await completion(null) };
  process.stdout.write(JSON.stringify(out));
})();
"""
res = subprocess.run(["node", "-e", NODE], capture_output=True, text=True, timeout=60)
try:
    out = json.loads(res.stdout)
except ValueError:
    out = {}
    print(res.stderr[-800:])

print("\nC — load error state (profile-v2.render.js)")
e404, enet = out.get("e404", {}), out.get("eNet", {})
check("C 404 → error visible, skeleton hidden, 'not found', no retry",
      e404.get("shown") and e404.get("loading") == "none"
      and e404.get("title") == "profile.error.not_found" and e404.get("retryHidden") is True, e404)
check("C network → error visible + retry button",
      enet.get("shown") and enet.get("title") == "profile.error.title" and enet.get("retryHidden") is False, enet)

print("\nD — completion card from /score (profile-v2.completion.js)")
c55, cnone = out.get("c55", {}), out.get("cNone", {})
check("D server score 55 → card shown, 55%, stats tile 55",
      c55.get("card") == "" and c55.get("pct") == "55%" and c55.get("tile") == "55", c55)
check("D no server score → card hidden", cnone.get("card") == "none", cnone)

print(f"\n{'=' * 50}\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
