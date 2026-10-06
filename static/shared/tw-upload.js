// static/shared/tw-upload.js — Shared image upload client helper
// Usage: TW.uploadImage({ kind, dataUrl, jwt })
//   kind: employee-avatar | employee-cover | company-logo | company-cover | kyc-id-front | kyc-selfie
//   The server decides bucket + file name from `kind` and user_id from the JWT (PR-7a).
// Returns: Promise<{ ok, status, data, errorType }> — never rejects.
//   errorType: null (ok) | 'network' (fetch failed, status 0) | 'non_json' (reply was
//   not JSON — e.g. an edge/proxy HTML page) | 'server' (JSON error from the API)
// Endpoint: POST /upload/image — accepts JPEG/PNG/WebP, 5 MB max
// On failure (!ok) callers must NOT save the data URL — show TW.uploadErrorText(res) instead.
// Every catch of an image flow (upload → save URL) shows TW.uploadFailureMessage(e, fallback).

(function(){
  if (!window.TW) window.TW = {};

  var SESSION_MSG = 'انتهت الجلسة — سجّل الدخول من جديد';
  var NETWORK_MSG = 'تعذّر الاتصال بالخادم — تحقّق من الإنترنت وحاول مرة أخرى';

  // Response → { ok, status, data, errorType } without ever throwing on a non-JSON body.
  TW.uploadResult = function(r) {
    return r.text().then(function(txt){
      var d = null;
      try { d = txt ? JSON.parse(txt) : {}; } catch (_) { d = null; }
      var isObj = d !== null && typeof d === 'object';
      return {
        ok:        r.ok && isObj,
        status:    r.status,
        data:      isObj ? d : {},
        errorType: !isObj ? 'non_json' : (r.ok ? null : 'server')
      };
    });
  };

  TW.uploadImage = function(opts) {
    var payloadBytes = (opts.dataUrl && opts.dataUrl.length) || 0;
    return fetch('/upload/image', {
      method:  'POST',
      headers: {
        'Content-Type':  'application/json',
        'Authorization': 'Bearer ' + opts.jwt
      },
      body: JSON.stringify({
        kind:     opts.kind,
        data_url: opts.dataUrl
      })
    }).then(TW.uploadResult, function(e){
      return { ok: false, status: 0, data: {}, errorType: 'network',
               detail: (e && e.name) || 'TypeError' };
    }).then(function(res){
      if (!res.ok) {
        // Details only — never the image data
        console.error('[TW.uploadImage] failed', {
          kind: opts.kind, status: res.status, errorType: res.errorType,
          detail: res.detail || (res.data && (res.data.error || res.data.detail)) || null,
          payloadBytes: payloadBytes
        });
        res.logged = true;
      }
      return res;
    });
  };

  // User-facing message for a failed result ({ok,status,data,errorType}):
  //   session (401 / client guard 'session_invalid') → session message
  //   network → connection message · JSON error from the server → its (Arabic) text
  //   non-JSON / other → fallback + " (رمز {status})"
  TW.uploadErrorText = function(res, fallback) {
    if (!res || typeof res !== 'object') return fallback;
    var d = res.data || {};
    if (res.status === 401 || d.detail === 'session_invalid') return SESSION_MSG;
    if (res.errorType === 'network') return NETWORK_MSG;
    if (typeof d.error === 'string' && d.error) return d.error;
    if (res.status) return fallback + ' (رمز ' + res.status + ')';
    return fallback;
  };

  // For the catch of an image flow: e = a thrown Error with .userMsg (already
  // classified), a rejected result object (e.g. the profile page's session guard),
  // or an unexpected exception. Logs anything not logged yet; returns the toast text.
  TW.uploadFailureMessage = function(e, fallback) {
    if (e && typeof e.userMsg === 'string') return e.userMsg;
    if (e && typeof e === 'object' && !(e instanceof Error) && ('ok' in e || 'data' in e)) {
      if (!e.logged) console.error('[TW.upload] rejected', { status: e.status || 0, detail: (e.data && e.data.detail) || null });
      return TW.uploadErrorText(e, fallback);
    }
    console.error('[TW.upload] exception', { name: e && e.name, message: e && e.message });
    return fallback;
  };

  // A thrown Error carrying the classified message of a failed result.
  TW.uploadError = function(res, fallback, stage) {
    var err = new Error(stage || 'upload_failed');
    err.userMsg = TW.uploadErrorText(res, fallback);
    if (!(res && res.logged)) {
      console.error('[TW.upload] ' + (stage || 'failed'), {
        status: res && res.status, errorType: res && res.errorType,
        detail: res && res.data && (res.data.error || res.data.detail) || null
      });
    }
    return err;
  };
})();
