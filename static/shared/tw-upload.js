// static/shared/tw-upload.js — Shared image upload client helper
// Usage: TW.uploadImage({ kind, dataUrl, jwt })
//   kind: employee-avatar | employee-cover | company-logo | company-cover | kyc-id-front | kyc-selfie
//   The server decides bucket + file name from `kind` and user_id from the JWT (PR-7a).
// Returns: Promise<{ ok: boolean, data: object }>
// Endpoint: POST /upload/image — accepts JPEG/PNG/WebP, 5 MB max
// On failure (!ok) callers must NOT save the data URL — show TW.uploadErrorText(res) instead.

(function(){
  if (!window.TW) window.TW = {};

  TW.uploadImage = function(opts) {
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
    }).then(function(r){
      return r.json().catch(function(){ return {}; })
        .then(function(d){ return { ok: r.ok, data: d }; });
    });
  };

  // User-facing message for a failed upload: the server's (generic, Arabic)
  // error text when present, else the caller's fallback.
  TW.uploadErrorText = function(res, fallback) {
    var e = res && res.data && res.data.error;
    return (typeof e === 'string' && e) ? e : fallback;
  };
})();
