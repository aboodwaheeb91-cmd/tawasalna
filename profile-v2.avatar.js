// profile-v2.avatar.js — Avatar Upload + Circular Crop
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.utils.js

(function(){
  var CANVAS_SIZE = 260;
  var MAX_BYTES   = 5 * 1024 * 1024; // 5 MB

  var camBtn      = document.getElementById('avCamBtn');
  var fileInput   = document.getElementById('avFileInput');
  var overlay     = document.getElementById('avCropOverlay');
  var canvas      = document.getElementById('avCropCanvas');
  var zoomSlider  = document.getElementById('avZoomSlider');
  var saveBtn     = document.getElementById('avCropSaveBtn');
  var cancelBtn   = document.getElementById('avCropCancelBtn');

  if(!camBtn || !canvas) return;

  var ctx = canvas.getContext('2d');

  // State
  var _img    = null;
  var _scale  = 1;
  var _minScale = 1;
  var _ox = 0, _oy = 0;       // image origin offset (canvas coords)
  var _drag = false;
  var _lastX = 0, _lastY = 0;

  // ── Open file picker ──
  camBtn.addEventListener('click', function(){ fileInput.click(); });

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
    _img = new Image();
    _img.onload = function(){
      // minimum scale: image must cover the full canvas
      _minScale = Math.max(CANVAS_SIZE / _img.width, CANVAS_SIZE / _img.height);
      _scale = _minScale;
      _centerImage();
      zoomSlider.min   = 100;
      zoomSlider.max   = 300;
      zoomSlider.value = 100;
      drawCanvas();
      overlay.classList.add('open');
    };
    _img.src = src;
  }

  function _centerImage(){
    _ox = (CANVAS_SIZE - _img.width  * _scale) / 2;
    _oy = (CANVAS_SIZE - _img.height * _scale) / 2;
  }

  function _clampOffset(){
    var iw = _img.width  * _scale;
    var ih = _img.height * _scale;
    if(_ox > 0) _ox = 0;
    if(_oy > 0) _oy = 0;
    if(_ox + iw < CANVAS_SIZE) _ox = CANVAS_SIZE - iw;
    if(_oy + ih < CANVAS_SIZE) _oy = CANVAS_SIZE - ih;
  }

  // ── Draw: circular clip for preview only ──
  function drawCanvas(){
    ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

    // dark background
    ctx.fillStyle = '#0f1420';
    ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

    // circular clip
    ctx.save();
    ctx.beginPath();
    ctx.arc(CANVAS_SIZE/2, CANVAS_SIZE/2, CANVAS_SIZE/2, 0, Math.PI*2);
    ctx.clip();

    ctx.drawImage(_img, _ox, _oy, _img.width * _scale, _img.height * _scale);
    ctx.restore();

    // ring outline
    ctx.beginPath();
    ctx.arc(CANVAS_SIZE/2, CANVAS_SIZE/2, CANVAS_SIZE/2 - 1, 0, Math.PI*2);
    ctx.strokeStyle = 'rgba(0,200,150,.5)';
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // ── Zoom slider ──
  zoomSlider.addEventListener('input', function(){
    var ratio = parseInt(this.value, 10) / 100;   // 1.0 – 3.0
    var newScale = _minScale * ratio;
    // keep center stable during zoom
    var cx = CANVAS_SIZE / 2;
    var cy = CANVAS_SIZE / 2;
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
    ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
  }

  cancelBtn.addEventListener('click', closeCrop);
  overlay.addEventListener('click', function(e){ if(e.target === overlay) closeCrop(); });

  // ── Export: square canvas (NO clip), JPEG with white bg ──
  function exportJpeg(){
    var exp = document.createElement('canvas');
    exp.width  = CANVAS_SIZE;
    exp.height = CANVAS_SIZE;
    var ec = exp.getContext('2d');
    ec.fillStyle = '#ffffff';
    ec.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
    ec.drawImage(_img, _ox, _oy, _img.width * _scale, _img.height * _scale);
    return exp.toDataURL('image/jpeg', 0.85);
  }

  // ── Save ──
  saveBtn.addEventListener('click', function(){
    var uid = window._scUserId;
    if(!uid){ toast('خطأ: لم يتم التعرف على المستخدم'); return; }

    var dataUrl = exportJpeg();
    saveBtn.disabled = true;
    saveBtn.textContent = 'جاري الرفع…';

    uploadAvatar(uid, dataUrl, window._jwt || '')
      .then(function(res){
        if(!res.ok || !res.data || !res.data.url){
          // dev fallback: save data_url directly to profile
          return updateProfile(uid, { avatar_url: dataUrl })
            .then(function(ur){
              if(!ur.ok) throw new Error('profile update failed');
              return { url: dataUrl };
            });
        }
        return updateProfile(uid, { avatar_url: res.data.url })
          .then(function(ur){
            if(!ur.ok) throw new Error('profile update failed');
            return { url: res.data.url };
          });
      })
      .then(function(result){
        // Update avatar DOM
        var avEl = document.getElementById('scAvatar');
        if(avEl){
          var img = new Image();
          img.alt = '';
          img.style.cssText = 'width:100%;height:100%;object-fit:cover;border-radius:50%';
          img.onload = function(){ avEl.innerHTML = ''; avEl.appendChild(img); };
          img.src = result.url;
        }
        if(window._scProfile) window._scProfile.avatar_url = result.url;
        closeCrop();
        toast('تم تحديث الصورة الشخصية');
      })
      .catch(function(){
        toast('حدث خطأ أثناء رفع الصورة');
      })
      .finally(function(){
        saveBtn.disabled = false;
        saveBtn.textContent = 'حفظ الصورة';
      });
  });
})();
