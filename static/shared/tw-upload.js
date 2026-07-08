// static/shared/tw-upload.js — Shared image upload client helper
// Usage: TW.uploadImage({ userId, bucket, filename, dataUrl, jwt })
// Returns: Promise<{ ok: boolean, data: object }>
// Endpoint: POST /upload/image — accepts JPEG/PNG/WebP, 5 MB max

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
        user_id:  opts.userId,
        bucket:   opts.bucket,
        filename: opts.filename,
        data_url: opts.dataUrl
      })
    }).then(function(r){
      return r.json().then(function(d){ return { ok: r.ok, data: d }; });
    });
  };
})();
