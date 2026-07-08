// profile-v2.avatar.js — Avatar Upload + Circular Crop
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.utils.js, tw-image-cropper.js

(function(){
  var MAX_BYTES = 5 * 1024 * 1024; // 5 MB

  var camBtn     = document.getElementById('avCamBtn');
  var fileInput  = document.getElementById('avFileInput');
  var overlay    = document.getElementById('avCropOverlay');
  var canvas     = document.getElementById('avCropCanvas');
  var zoomSlider = document.getElementById('avZoomSlider');
  var saveBtn    = document.getElementById('avCropSaveBtn');
  var cancelBtn  = document.getElementById('avCropCancelBtn');

  if(!camBtn || !canvas) return;

  var _cropper = TW.createCropper({
    canvas:  canvas,
    ratio:   1 / 1,
    shape:   'circle',
    outputW: 260,
    outputH: 260,
    quality: 0.85
  });

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
    overlay.classList.add('open');
    zoomSlider.min   = 100;
    zoomSlider.max   = 300;
    zoomSlider.value = 100;
    // Load after overlay is visible so getBoundingClientRect returns real dimensions
    requestAnimationFrame(function(){
      _cropper.load(src);
    });
  }

  // ── Zoom slider ──
  zoomSlider.addEventListener('input', function(){
    _cropper.setZoom(parseInt(this.value, 10) / 100);
  });

  // ── Close ──
  function closeCrop(){
    overlay.classList.remove('open');
    _cropper.reset();
  }

  cancelBtn.addEventListener('click', closeCrop);
  overlay.addEventListener('click', function(e){ if(e.target === overlay) closeCrop(); });

  // ── Save ──
  saveBtn.addEventListener('click', function(){
    var uid = window._scUserId;
    if(!uid){ toast('خطأ: لم يتم التعرف على المستخدم'); return; }

    var dataUrl = _cropper.export();
    saveBtn.disabled = true;
    saveBtn.textContent = 'جاري الرفع…';

    uploadAvatar(uid, dataUrl)
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
        if(window._updateCompletion) window._updateCompletion();
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
