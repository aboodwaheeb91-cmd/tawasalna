'use strict';
/**
 * test_upload_client_runtime.js — runtime tests for static/shared/tw-upload.js
 * (real code in a vm, fake fetch). Covers the failure classes every image flow
 * (avatar · cover · company logo/cover · KYC) shows to the user:
 *   ok · network failure · non-JSON reply (edge HTML 413/502) · JSON server error
 *   · 401 / client session guard · unexpected exception — and the console.error
 *   details (status, type, payload size — never the image data).
 *
 * Run: node tests/test_upload_client_runtime.js
 */
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const SRC = fs.readFileSync(__dirname + '/../static/shared/tw-upload.js', 'utf8');
const DATA_URL = 'data:image/jpeg;base64,' + 'A'.repeat(4000);

function load(fetchImpl) {
  const errors = [];
  const ctx = {
    fetch: fetchImpl, JSON, Promise, Error,
    console: { error: (...a) => errors.push(a), log() {}, warn() {} },
  };
  ctx.window = ctx;   // browser: window is the global object (tw-upload.js uses bare TW)
  vm.runInNewContext(SRC, ctx);
  return { TW: ctx.TW, errors };
}

function resp(status, body) {
  return { ok: status >= 200 && status < 300, status, text: () => Promise.resolve(body) };
}

const cases = [];
function test(name, fn) { cases.push([name, fn]); }

test('success → ok, no console.error', async () => {
  const { TW, errors } = load(() => Promise.resolve(resp(200, '{"status":"success","url":"https://x/a.jpg"}')));
  const r = await TW.uploadImage({ kind: 'employee-avatar', dataUrl: DATA_URL, jwt: 't' });
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.errorType, null);
  assert.strictEqual(r.data.url, 'https://x/a.jpg');
  assert.strictEqual(errors.length, 0);
});

test('network failure → resolves (no reject), network message, logged', async () => {
  const { TW, errors } = load(() => Promise.reject(new TypeError('Failed to fetch')));
  const r = await TW.uploadImage({ kind: 'employee-avatar', dataUrl: DATA_URL, jwt: 't' });
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.status, 0);
  assert.strictEqual(r.errorType, 'network');
  assert.match(TW.uploadErrorText(r, 'FB'), /الاتصال بالخادم/);
  assert.strictEqual(errors.length, 1);
});

test('non-JSON 413 (edge HTML) → fallback + status code, payload size logged, no image data', async () => {
  const { TW, errors } = load(() => Promise.resolve(resp(413, '<html>Request Entity Too Large</html>')));
  const r = await TW.uploadImage({ kind: 'employee-cover', dataUrl: DATA_URL, jwt: 't' });
  assert.strictEqual(r.errorType, 'non_json');
  assert.strictEqual(TW.uploadErrorText(r, 'FB'), 'FB (رمز 413)');
  const info = errors[0][1];
  assert.strictEqual(info.status, 413);
  assert.strictEqual(info.errorType, 'non_json');
  assert.strictEqual(info.payloadBytes, DATA_URL.length);
  assert.ok(!JSON.stringify(errors).includes('AAAA'), 'image data must never be logged');
});

test('200 with non-JSON body is not ok', async () => {
  const { TW } = load(() => Promise.resolve(resp(200, '<html>proxy</html>')));
  const r = await TW.uploadImage({ kind: 'company-logo', dataUrl: DATA_URL, jwt: 't' });
  assert.strictEqual(r.ok, false);
  assert.strictEqual(TW.uploadErrorText(r, 'FB'), 'FB (رمز 200)');
});

test('JSON server error → server message', async () => {
  const { TW } = load(() => Promise.resolve(resp(502, '{"error":"تعذّر رفع الصورة، حاول مرة أخرى"}')));
  const r = await TW.uploadImage({ kind: 'kyc-selfie', dataUrl: DATA_URL, jwt: 't' });
  assert.strictEqual(r.errorType, 'server');
  assert.strictEqual(TW.uploadErrorText(r, 'FB'), 'تعذّر رفع الصورة، حاول مرة أخرى');
});

test('401 → session message (even with a server error text)', async () => {
  const { TW } = load(() => Promise.resolve(resp(401, '{"error":"Token invalid or expired"}')));
  const r = await TW.uploadImage({ kind: 'employee-avatar', dataUrl: DATA_URL, jwt: 't' });
  assert.match(TW.uploadErrorText(r, 'FB'), /انتهت الجلسة/);
});

test('uploadFailureMessage: client session guard reject (_STALE shape) → session message', () => {
  const { TW, errors } = load(() => Promise.reject(new Error('unused')));
  const msg = TW.uploadFailureMessage({ ok: false, data: { detail: 'session_invalid' } }, 'FB');
  assert.match(msg, /انتهت الجلسة/);
  assert.strictEqual(errors.length, 1);
});

test('uploadFailureMessage: thrown uploadError keeps its classified message (save step)', () => {
  const { TW } = load(() => Promise.reject(new Error('unused')));
  const err = TW.uploadError({ ok: false, status: 400, data: { error: 'رابط الصورة غير صالح' }, errorType: 'server' }, 'FB', 'save_failed');
  assert.strictEqual(TW.uploadFailureMessage(err, 'OTHER'), 'رابط الصورة غير صالح');
});

test('uploadFailureMessage: unexpected exception → fallback + logged', () => {
  const { TW, errors } = load(() => Promise.reject(new Error('unused')));
  assert.strictEqual(TW.uploadFailureMessage(new SyntaxError('bad json'), 'FB'), 'FB');
  assert.strictEqual(errors[0][1].name, 'SyntaxError');
});

(async () => {
  let failed = 0;
  for (const [name, fn] of cases) {
    try { await fn(); console.log('✓ ' + name); }
    catch (e) { failed++; console.log('✗ ' + name + '\n   ' + e.message); }
  }
  console.log(`\n${cases.length - failed}/${cases.length} passed`);
  process.exit(failed ? 1 : 0);
})();
