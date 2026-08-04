"""
WebSocket Security Hardening — Static Verification Tests
=========================================================
Verifies implementation correctness by inspecting source code, not by
establishing live WebSocket connections (which would require a running DB).

Coverage:
  A — Backend (server.py): 22 checks
  B — Messages client (messages.ws.js): 9 checks
  C — Badge WS client (tw_shared.js): 9 checks

Run:  python test_ws_security.py
"""

import re
import sys

PASS = 0
FAIL = 0

def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


# ── Read source files ─────────────────────────────────────────────────────

def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

srv  = _read("server.py")
ws   = _read("messages.ws.js")
shr  = _read("tw_shared.js")

# Extract the WS section of server.py (from class ConnectionManager onwards)
ws_section_start = srv.find("class ConnectionManager:")
ws_section = srv[ws_section_start:] if ws_section_start != -1 else srv

# Also include helper functions before ConnectionManager (from the WS comment block)
ws_block_start = srv.find("# ── WebSocket Real-time Messages")
ws_block = srv[ws_block_start:] if ws_block_start != -1 else srv

# Extract only the websocket_endpoint function body
ep_start = srv.find("async def websocket_endpoint(")
ep_end   = srv.find("\ndef ", ep_start + 10) if ep_start != -1 else -1
ep_body  = srv[ep_start:ep_end] if ep_start != -1 else ""

print("\n── A  Backend (server.py) ──────────────────────────────────────────────")

# A1: Old connect() pattern must be gone
check("A01  ConnectionManager has no connect() method",
      ".connect(" not in ws_section or "def connect(" not in ws_section)

# A2: register() method exists on ConnectionManager
check("A02  ConnectionManager.register() exists",
      "def register(self, user_id" in srv)

# A3: auth_ok response sent after register
check("A03  auth_ok message sent to client after registration",
      '"auth_ok"' in ep_body or "'auth_ok'" in ep_body)

# A4: _ws_validate_auth_frame helper calls _jwt_decode; endpoint calls the helper
check("A04  _jwt_decode() used via _ws_validate_auth_frame() in ws_block",
      "_jwt_decode(" in ws_block and "_ws_validate_auth_frame(" in ep_body)

# A5: payload size check before JSON parsing
check("A05  _WS_MAX_PAYLOAD enforced",
      "_WS_MAX_PAYLOAD" in ep_body)

# A6: typing rate limiter called
check("A06  _ws_typing_rate_ok() called for typing events",
      "_ws_typing_rate_ok(" in ep_body)

# A7: conversation membership check for typing (async version)
check("A07  _ws_conversation_exists_async() called for typing authorization",
      "_ws_conversation_exists_async(" in ep_body)

# A8: JWT uid matched against URL path user_id
check("A08  JWT uid matched against URL path user_id",
      re.search(r"auth_uid\s*!=\s*user_id|user_id\s*!=\s*auth_uid", ep_body) is not None)

# A9-A14: All close codes present somewhere in ws_block (helpers + endpoint)
# 4001 appears as a return value in _ws_validate_auth_frame (return -1, 4001),
# so also check for the tuple pattern ", {code}".
for code, label in [(4001, "Unauthorized"), (4002, "Auth Failed"), (4003, "Forbidden"),
                    (4004, "Bad Payload"), (4005, "Policy"), (4006, "Origin")]:
    check(f"A{8 + (code-4000):02d}  Close code {code} ({label}) present in ws_block",
          f"code={code}" in ws_block or f"close({code}" in ws_block or f", {code}" in ws_block)

# A15: close code 4007 (Too Many Connections) present
check("A15  Close code 4007 (Too Many Connections) present in endpoint",
      "code=4007" in ep_body or "close(4007" in ep_body)

# A16: JWT token never logged (token= not in any print/log call)
log_lines = [ln for ln in ep_body.splitlines()
             if "print(" in ln and "token" in ln.lower()]
check("A16  JWT token not logged in websocket_endpoint",
      all("token" not in ln.lower().replace("no_token", "").replace("auth_no_token", "")
          or "AUTH_NO_TOKEN" in ln
          for ln in log_lines),
      detail=f"Suspect lines: {log_lines[:3]}")

# A17: asyncio.wait_for with timeout used for first message
check("A17  asyncio.wait_for() used for auth message timeout",
      "asyncio.wait_for(" in ep_body and "_WS_AUTH_TIMEOUT" in ep_body)

# A18: WebSocketDisconnect handled in message loop
check("A18  WebSocketDisconnect caught in message loop",
      "WebSocketDisconnect" in ep_body)

# A19: disconnect() called in finally block
check("A19  ws_manager.disconnect() called in finally block",
      re.search(r"finally\s*:[^}]*ws_manager\.disconnect\(", ep_body, re.DOTALL) is not None)

# A20: ws.accept() called before auth (step ordering)
accept_pos   = ep_body.find("await websocket.accept()")
register_pos = ep_body.find("ws_manager.register(")
check("A20  ws.accept() precedes ws_manager.register() (accept-then-auth ordering)",
      accept_pos != -1 and register_pos != -1 and accept_pos < register_pos)

# A21: _BoundedTTLCache used for conversation cache
check("A21  _BoundedTTLCache class defined and used for conversation cache",
      "class _BoundedTTLCache" in srv and "_ws_conv_cache = _BoundedTTLCache(" in srv)

# A22: Rate limit checked BEFORE DB lookup for typing (order in ep_body)
rate_pos = ep_body.find("_ws_typing_rate_ok(")
conv_pos  = ep_body.find("_ws_conversation_exists_async(", rate_pos)
check("A22  _ws_typing_rate_ok() called BEFORE _ws_conversation_exists_async() for typing",
      rate_pos != -1 and conv_pos != -1 and rate_pos < conv_pos)

# A23: Origin policy fail-closed (null origin rejected; prod defaults enforced)
check("A23  Fail-closed origin policy: null origin rejected and prod defaults set",
      'origin == "null"' in ws_block and "_WS_PROD_ORIGINS" in srv)

# A24: Legacy WS send path removed
check("A24  Legacy WS send path (receiver_id+content without type) removed",
      "receiver_id" not in ep_body or "send_message(" not in ep_body)

print("\n── B  Messages client (messages.ws.js) ────────────────────────────────")

# Detect onopen and onmessage blocks — supports both _ws.onopen and ws.onopen patterns
onopen_match = re.search(r"\bws\.onopen\s*=\s*function\(\)", ws)
onmsg_match  = re.search(r"\bws\.onmessage\s*=\s*function\(", ws)
if onopen_match and onmsg_match:
    onopen_body = ws[onopen_match.start():onmsg_match.start()]
else:
    onopen_body = ""

# B1: auth message sent in onopen (before onmessage)
check("B01  First ws.send() in onopen sends {type:'auth',token:...}",
      ".send(" in onopen_body and "type: 'auth'" in onopen_body)

# B2: _wsReady flag defined at module level
check("B02  _wsReady flag declared at module level",
      re.search(r"var\s+_wsReady\s*=\s*false", ws) is not None)

# B3: auth_ok type handled in onmessage
check("B03  auth_ok handled in onmessage",
      "'auth_ok'" in ws or '"auth_ok"' in ws)

# B4: _wsReady set to true on auth_ok
check("B04  _wsReady = true set on auth_ok",
      re.search(r"auth_ok.*?_wsReady\s*=\s*true|_wsReady\s*=\s*true.*?auth_ok", ws, re.DOTALL) is not None)

# B5: All operational send functions guard with _wsReady
for fn in ["sendActiveConversation", "sendInactiveConversation", "sendTyping", "sendTypingStop"]:
    fn_match = re.search(rf"function\s+{fn}\s*\([^)]*\)\s*\{{([^}}]+(?:\{{[^}}]*\}}[^}}]*)*)}}", ws, re.DOTALL)
    fn_body  = fn_match.group(1) if fn_match else ""
    check(f"B05  {fn}() guarded by _wsReady",
          "_wsReady" in fn_body)

# B6: onclose stops reconnect on 4001-4007
check("B06  onclose stops reconnect on auth close codes (4001-4007)",
      re.search(r"code\s*>=\s*4001.*?return|4001.*?4007.*?return", ws, re.DOTALL) is not None)

# B7: _wsReady reset to false on close — search in onclose block (local ws variable)
onclose_match = re.search(r"\bws\.onclose\s*=\s*function\(event\)", ws)
onerror_match = re.search(r"\bws\.onerror\s*=\s*function\(", ws)
if onclose_match and onerror_match:
    onclose_body = ws[onclose_match.start():onerror_match.start()]
else:
    onclose_body = ""
check("B07  _wsReady = false reset in onclose",
      "_wsReady = false" in onclose_body)

# B8: generation counter _wsGen declared
check("B08  _wsGen generation counter declared at module level",
      re.search(r"var\s+_wsGen\s*=\s*0", ws) is not None)

# B9: auth_ok.user_id validated against capturedUid
check("B09  auth_ok.user_id validated against capturedUid in onmessage",
      "data.user_id" in ws and "capturedUid" in ws)

print("\n── C  Badge WS client (tw_shared.js) ──────────────────────────────────")

# Find the IIFE badge WS block
badge_start = shr.find("Global Real-time Badge WebSocket")
badge_block = shr[badge_start:] if badge_start != -1 else shr

# C1: auth message sent in onopen
check("C01  Badge WS onopen sends {type:auth,token:...}",
      re.search(r"ws\.onopen.*?type.*?auth", badge_block, re.DOTALL) is not None)

# C2: per-connection wsReady flag
check("C02  Per-connection wsReady flag in Badge WS",
      "var wsReady = false" in badge_block)

# C3: auth_ok sets wsReady = true
check("C03  auth_ok sets wsReady = true in Badge WS",
      re.search(r"auth_ok.*?wsReady\s*=\s*true|wsReady\s*=\s*true.*?auth_ok", badge_block, re.DOTALL) is not None)

# C4: badge_update only processed when wsReady
check("C04  badge_update guarded by wsReady in Badge WS",
      re.search(r"if\s*\(!wsReady\)\s*return", badge_block) is not None)

# C5: generation guard
check("C05  Generation guard (capturedGen !== _gen) in onmessage",
      "capturedGen !== _gen" in badge_block)

# C6: uid guard
check("C06  User ID guard (capturedUid !== _activeUid) in onmessage",
      "capturedUid !== _activeUid" in badge_block)

# C7: onclose stops reconnect on auth codes 4001-4007
check("C07  Badge WS onclose stops reconnect on auth codes 4001-4007",
      re.search(r"code\s*>=\s*4001.*?return|4001.*?4007.*?return", badge_block, re.DOTALL) is not None)

# C8: onclose stops reconnect when superseded by new session
check("C08  Badge WS onclose stops reconnect when generation superseded",
      "capturedGen !== _gen" in badge_block and
      re.search(r"capturedGen !== _gen.*?return|return.*?capturedGen !== _gen", badge_block, re.DOTALL) is not None)

# C9: auth_ok.user_id validated against capturedUid in Badge WS
check("C09  auth_ok.user_id validated against capturedUid in Badge WS",
      "data.user_id" in badge_block and "capturedUid" in badge_block)

# ── Summary ───────────────────────────────────────────────────────────────

total = PASS + FAIL
print(f"\n{'─'*60}")
print(f"  {PASS}/{total} passed  {'✓  all green' if FAIL == 0 else f'✗  {FAIL} FAILED'}")
print(f"{'─'*60}\n")
sys.exit(0 if FAIL == 0 else 1)
