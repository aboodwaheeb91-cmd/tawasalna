// profile-v2.cover.js — Cover Upload + Crop (6:1 ratio)
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.utils.js

(function(){
  // Export at 720×120 (6:1, good quality)
  var EXP_W = 720, EXP_H = 120;
  var MAX_BYTES = 5 * 1024 * 1024; // 5 MB

  var editBtn   = document.getElementById('cvEditBtn');
  var fileInput = document.getElementById('cvFileInput');
  var overlay   = document.getElementById('cvCropOverlay');
  var canvas    = document.getElementById('cvCropCanvas');
  var zoomSlider= document.getElementById('cvZoomSlider');
  var saveBtn   = document.getElementById('cvCropSaveBtn');
  var cancelBtn = document.getElementById('cvCropCancelBtn');

  if(!editBtn || !canvas) return;

  // Canvas display size matches CSS (full card width), logical 6:1
  var CW = 0, CH = 0; // set on open after layout

  var ctx = canvas.getContext('2d');

  // State
  var _img     = null;
  var _scale   = 1;
  var _minScale= 1;
  var _ox = 0, _oy = 0;
  var _drag    = false;
  var _lastX   = 0, _lastY = 0;

  // ── Open file picker ──
  editBtn.addEventListener('click', function(){ fileInput.click(); });

  fileInput.addEventListener('change', function(){
    var file = fileInput.files && fileInput.files[0];
    fileInput.value = '';
    if(!file) return;
    if(!/^image\/(jpeg|png|webp)$/.test(file.type)){
      toast('يُقبل فقط: JPEG، PNG، WebP');
      return;
    }
    if(file.size > MAX_BYTES){
      toast('حجم الصورة يتجاوز 5 ميغابايت');
      return;
    }
    var reader = new FileReader();
    reader.onload = function(e){ openCrop(e.target.result); };
    reader.readAsDataURL(file);
  });

  // ── Open crop overlay ──
  function openCrop(src){
    overlay.classList.add('open');

    // Measure canvas display size after it's visible
    requestAnimationFrame(function(){
      var rect = canvas.getBoundingClientRect();
      CW = Math.round(rect.width)  || 480;
      CH = Math.round(rect.height) || Math.round(CW / 6);

      // Set canvas logical pixels to match display size (avoid blur)
      canvas.width  = CW;
      canvas.height = CH;

      _img = new Image();
      _img.onload = function(){
        _minScale = Math.max(CW / _img.width, CH / _img.height);
        _scale = _minScale;
        _centerImage();
        zoomSlider.min   = 100;
        zoomSlider.max   = 300;
        zoomSlider.value = 100;
        drawCanvas();
      };
      _img.src = src;
    });
  }

  function _centerImage(){
    _ox = (CW - _img.width  * _scale) / 2;
    _oy = (CH - _img.height * _scale) / 2;
  }

  function _clampOffset(){
    var iw = _img.width  * _scale;
    var ih = _img.height * _scale;
    if(_ox > 0) _ox = 0;
    if(_oy > 0) _oy = 0;
    if(_ox + iw < CW) _ox = CW - iw;
    if(_oy + ih < CH) _oy = CH - ih;
  }

  function drawCanvas(){
    ctx.clearRect(0, 0, CW, CH);
    ctx.fillStyle = '#0f1420';
    ctx.fillRect(0, 0, CW, CH);
    ctx.drawImage(_img, _ox, _oy, _img.width * _scale, _img.height * _scale);
    // grid lines for orientation
    ctx.strokeStyle = 'rgba(0,200,150,.2)';
    ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, CW-1, CH-1);
  }

  // ── Zoom slider ──
  zoomSlider.addEventListener('input', function(){
    var ratio    = parseInt(this.value, 10) / 100;
    var newScale = _minScale * ratio;
    var cx = CW / 2, cy = CH / 2;
    _ox = cx - (cx - _ox) * (newScale / _scale);
    _oy = cy - (cy - _oy) * (newScale / _scale);
    _scale = newScale;
    _clampOffset();
    drawCanvas();
  });

  // ── Mouse drag ──
  function onMouseDown(e){ _drag=true; _lastX=e.clientX; _lastY=e.clientY; }
  function onMouseMove(e){
    if(!_drag) return;
    _ox += e.clientX - _lastX;
    _oy += e.clientY - _lastY;
    _lastX = e.clientX; _lastY = e.clientY;
    _clampOffset();
    drawCanvas();
  }
  function onMouseUp(){ _drag = false; }

  canvas.addEventListener('mousedown', onMouseDown);
  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup',   onMouseUp);

  // ── Touch drag ──
  function onTouchStart(e){
    if(e.touches.length !== 1) return;
    e.preventDefault();
    _drag=true; _lastX=e.touches[0].clientX; _lastY=e.touches[0].clientY;
  }
  function onTouchMove(e){
    if(!_drag || e.touches.length !== 1) return;
    e.preventDefault();
    _ox += e.touches[0].clientX - _lastX;
    _oy += e.touches[0].clientY - _lastY;
    _lastX = e.touches[0].clientX; _lastY = e.touches[0].clientY;
    _clampOffset();
    drawCanvas();
  }
  function onTouchEnd(){ _drag = false; }

  canvas.addEventListener('touchstart', onTouchStart, { passive: false });
  canvas.addEventListener('touchmove',  onTouchMove,  { passive: false });
  canvas.addEventListener('touchend',   onTouchEnd);

  // ── Close ──
  function closeCrop(){
    overlay.classList.remove('open');
    _img  = null;
    _drag = false;
    ctx.clearRect(0, 0, CW, CH);
  }

  cancelBtn.addEventListener('click', closeCrop);
  overlay.addEventListener('click', function(e){ if(e.target === overlay) closeCrop(); });

  // ── Export: 720×120 canvas, no clip, JPEG with fallback white bg ──
  function exportJpeg(){
    var exp = document.createElement('canvas');
    exp.width  = EXP_W;
    exp.height = EXP_H;
    var ec = exp.getContext('2d');
    ec.fillStyle = '#ffffff';
    ec.fillRect(0, 0, EXP_W, EXP_H);
    // Scale coordinates from display canvas to export canvas
    var scaleX = EXP_W / CW;
    var scaleY = EXP_H / CH;
    ec.drawImage(
      _img,
      _ox * scaleX, _oy * scaleY,
      _img.width * _scale * scaleX,
      _img.height * _scale * scaleY
    );
    return exp.toDataURL('image/jpeg', 0.88);
  }

  // ── Save ──
  saveBtn.addEventListener('click', function(){
    var uid = window._scUserId;
    if(!uid){ toast('خطأ: لم يتم التعرف على المستخدم'); return; }

    var dataUrl = exportJpeg();
    saveBtn.disabled = true;
    saveBtn.textContent = 'جاري الرفع…';

    uploadCover(uid, dataUrl)
      .then(function(res){
        var coverUrl;
        if(res.ok && res.data && res.data.url){
          coverUrl = res.data.url;
        } else {
          // dev fallback: save data_url directly
          coverUrl = dataUrl;
        }
        return updateProfile(uid, { cover_url: coverUrl })
          .then(function(ur){
            if(!ur.ok) throw new Error('profile update failed');
            return coverUrl;
          });
      })
      .then(function(coverUrl){
        // Update cover DOM immediately
        var coverEl = document.getElementById('scCover');
        if(coverEl) coverEl.style.backgroundImage = 'url(' + coverUrl + ')';
        if(window._scProfile) window._scProfile.cover_url = coverUrl;
        closeCrop();
        toast('تم تحديث الكفر');
        // Background re-fetch
        if(window._scProfileKey){
          getProfile(_scProfileKey)
            .then(function(freshRes){
              if(freshRes && window.renderProfile) window.renderProfile(freshRes);
            })
            .catch(function(){});
        }
      })
      .catch(function(){
        toast('حدث خطأ أثناء رفع الكفر');
      })
      .finally(function(){
        saveBtn.disabled = false;
        saveBtn.textContent = 'حفظ الكفر';
      });
  });
})();
