// static/shared/tw-image-cropper.js — Shared canvas-based image cropper helper
// Usage:
//   var c = TW.createCropper({ canvas, ratio, shape, outputW, outputH, quality });
//   c.load(dataUrl);          // after overlay is visible
//   c.setZoom(1.5);           // 1.0 = fit, 3.0 = max
//   var dataUrl = c.export(); // JPEG dataUrl at outputW × outputH
//   c.reset();                // clear state, keep listeners
//   c.destroy();              // remove listeners (when overlay removed from DOM)
//
// Separation of concerns:
//   - tw-image-cropper.js handles crop / zoom / drag / export ONLY
//   - tw-upload.js    handles HTTP upload ONLY (POST /upload/image)
//   - The page passes export() → TW.uploadImage() — neither file knows the other
//
// No fetch, no uploadImage, no userId, no jwt, no bucket, no filename.

(function () {
  'use strict';

  if (!window.TW) window.TW = {};

  TW.createCropper = function (opts) {
    var canvas  = opts.canvas;
    var ratio   = opts.ratio   || 1;       // width ÷ height  e.g. 6/1, 4/1, 1/1
    var shape   = opts.shape   || 'rect';  // 'rect' | 'circle'
    var outputW = opts.outputW || 260;     // export pixel width
    var outputH = opts.outputH || 260;     // export pixel height
    var quality = opts.quality || 0.85;   // JPEG quality 0–1

    var ctx = canvas.getContext('2d');

    // ── Display size in CSS pixels + devicePixelRatio ──
    // DPR: physical canvas pixels = CSS pixels × DPR.
    // ctx.scale(dpr, dpr) lets all drawing use CSS pixel coords → sharp on Retina.
    // Measured on load(), which must be called after the overlay is visible.
    var _dw  = 0;   // canvas display width  (CSS px)
    var _dh  = 0;   // canvas display height (CSS px)
    var _dpr = 1;   // devicePixelRatio snapshot

    // ── Image state ──
    var _img      = null;
    var _scale    = 1;
    var _minScale = 1;  // scale at which image exactly fills canvas
    var _ox = 0, _oy = 0;  // image top-left offset in CSS px

    // ── Drag state ──
    var _drag  = false;
    var _lastX = 0, _lastY = 0;

    // ── Canvas setup with DPR ──
    function _setupCanvas() {
      var rect = canvas.getBoundingClientRect();
      _dpr = window.devicePixelRatio || 1;
      _dw  = Math.round(rect.width)  || outputW;
      _dh  = Math.round(rect.height) || Math.round(_dw / ratio);

      // Physical canvas resolution scaled by DPR
      canvas.width  = _dw * _dpr;
      canvas.height = _dh * _dpr;

      // Reset transform then apply DPR scale once
      // All subsequent drawing uses CSS pixel coords
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(_dpr, _dpr);
    }

    // ── Min scale: image must cover the full canvas at all times ──
    function _calcMinScale() {
      return Math.max(_dw / _img.width, _dh / _img.height);
    }

    // ── Center image inside canvas ──
    function _center() {
      _ox = (_dw - _img.width  * _scale) / 2;
      _oy = (_dh - _img.height * _scale) / 2;
    }

    // ── Clamp: image must always fully cover the visible canvas area ──
    function _clamp() {
      var iw = _img.width  * _scale;
      var ih = _img.height * _scale;
      if (_ox > 0) _ox = 0;
      if (_oy > 0) _oy = 0;
      if (_ox + iw < _dw) _ox = _dw - iw;
      if (_oy + ih < _dh) _oy = _dh - ih;
    }

    // ── Draw current frame ──
    function _draw() {
      if (!_img) return;

      ctx.clearRect(0, 0, _dw, _dh);
      ctx.fillStyle = '#0f1420';
      ctx.fillRect(0, 0, _dw, _dh);

      if (shape === 'circle') {
        // Circular preview clip
        var r = Math.min(_dw, _dh) / 2;
        ctx.save();
        ctx.beginPath();
        ctx.arc(_dw / 2, _dh / 2, r, 0, Math.PI * 2);
        ctx.clip();
      }

      ctx.drawImage(_img, _ox, _oy, _img.width * _scale, _img.height * _scale);

      if (shape === 'circle') {
        ctx.restore();
        // Accent ring
        var r2 = Math.min(_dw, _dh) / 2 - 1;
        ctx.beginPath();
        ctx.arc(_dw / 2, _dh / 2, r2, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(0,200,150,.5)';
        ctx.lineWidth = 2;
        ctx.stroke();
      } else {
        // Subtle guide border
        ctx.strokeStyle = 'rgba(0,200,150,.2)';
        ctx.lineWidth = 1;
        ctx.strokeRect(0.5, 0.5, _dw - 1, _dh - 1);
      }
    }

    // ── Mouse drag ──
    function _onMouseDown(e) {
      _drag = true;
      _lastX = e.clientX;
      _lastY = e.clientY;
    }
    function _onMouseMove(e) {
      if (!_drag) return;
      _ox += e.clientX - _lastX;
      _oy += e.clientY - _lastY;
      _lastX = e.clientX;
      _lastY = e.clientY;
      _clamp();
      _draw();
    }
    function _onMouseUp() { _drag = false; }

    // ── Touch drag — passive:false is mandatory to allow e.preventDefault()
    //    which blocks page scroll while the user drags inside the crop overlay ──
    function _onTouchStart(e) {
      if (e.touches.length !== 1) return;
      e.preventDefault();
      _drag = true;
      _lastX = e.touches[0].clientX;
      _lastY = e.touches[0].clientY;
    }
    function _onTouchMove(e) {
      if (!_drag || e.touches.length !== 1) return;
      e.preventDefault();  // prevents page scroll during drag
      _ox += e.touches[0].clientX - _lastX;
      _oy += e.touches[0].clientY - _lastY;
      _lastX = e.touches[0].clientX;
      _lastY = e.touches[0].clientY;
      _clamp();
      _draw();
    }
    function _onTouchEnd() { _drag = false; }

    // Attach listeners — touchmove must be non-passive
    canvas.addEventListener('mousedown',  _onMouseDown);
    window.addEventListener('mousemove',  _onMouseMove);
    window.addEventListener('mouseup',    _onMouseUp);
    canvas.addEventListener('touchstart', _onTouchStart, { passive: false });
    canvas.addEventListener('touchmove',  _onTouchMove,  { passive: false });
    canvas.addEventListener('touchend',   _onTouchEnd);

    // ── Public API ──────────────────────────────────────────────────────────

    return {

      // Load a dataUrl (from FileReader.onload) into the cropper.
      // IMPORTANT: call this AFTER the crop overlay is visible so that
      // canvas.getBoundingClientRect() returns non-zero dimensions.
      load: function (src) {
        _setupCanvas();
        var img = new Image();
        img.onload = function () {
          _img      = img;
          _minScale = _calcMinScale();
          _scale    = _minScale;
          _center();
          _draw();
        };
        img.src = src;
      },

      // Set zoom level relative to fit-scale.
      // zoomRatio: 1.0 = image exactly fits canvas, 3.0 = 3× fit-scale.
      setZoom: function (zoomRatio) {
        if (!_img) return;
        var newScale = _minScale * zoomRatio;
        // Keep the canvas center stable during zoom
        var cx = _dw / 2, cy = _dh / 2;
        _ox = cx - (cx - _ox) * (newScale / _scale);
        _oy = cy - (cy - _oy) * (newScale / _scale);
        _scale = newScale;
        _clamp();
        _draw();
      },

      // Export current crop as JPEG dataUrl at outputW × outputH.
      // Export is always rectangular (no circular clip) — the page applies
      // CSS border-radius to display avatars as circles.
      export: function () {
        var exp = document.createElement('canvas');
        exp.width  = outputW;
        exp.height = outputH;
        var ec = exp.getContext('2d');

        // White background (fills transparent areas if image is PNG)
        ec.fillStyle = '#ffffff';
        ec.fillRect(0, 0, outputW, outputH);

        if (_img) {
          // Scale coordinates from display canvas to export canvas
          var sx = outputW / _dw;
          var sy = outputH / _dh;
          ec.drawImage(
            _img,
            _ox * sx, _oy * sy,
            _img.width  * _scale * sx,
            _img.height * _scale * sy
          );
        }

        return exp.toDataURL('image/jpeg', quality);
      },

      // Clear canvas and reset image state. Listeners stay active.
      reset: function () {
        _img   = null;
        _drag  = false;
        _scale = 1;
        _ox    = 0;
        _oy    = 0;
        if (_dw && _dh) ctx.clearRect(0, 0, _dw, _dh);
      },

      // Remove all event listeners. Call when the overlay element is permanently
      // removed from the DOM to avoid memory leaks.
      destroy: function () {
        canvas.removeEventListener('mousedown',  _onMouseDown);
        window.removeEventListener('mousemove',  _onMouseMove);
        window.removeEventListener('mouseup',    _onMouseUp);
        canvas.removeEventListener('touchstart', _onTouchStart);
        canvas.removeEventListener('touchmove',  _onTouchMove);
        canvas.removeEventListener('touchend',   _onTouchEnd);
      }
    };
  };

})();
