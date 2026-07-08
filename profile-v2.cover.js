// profile-v2.cover.js — Cover Upload + Crop (6:1 ratio)
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.utils.js, tw-image-cropper.js

(function(){
  var MAX_BYTES = 5 * 1024 * 1024; // 5 MB

  var editBtn   = document.getElementById('cvEditBtn');
  var fileInput = document.getElementById('cvFileInput');
  var overlay   = document.getElementById('cvCropOverlay');
  var canvas    = document.getElementById('cvCropCanvas');
  var zoomSlider= document.getElementById('cvZoomSlider');
  var saveBtn   = document.getElementById('cvCropSaveBtn');
  var cancelBtn = document.getElementById('cvCropCancelBtn');

  if(!editBtn || !canvas) return;

  var _cropper = TW.createCropper({
    canvas:  canvas,
    ratio:   6 / 1,
    shape:   'rect',
    outputW: 720,
    outputH: 120,
    quality: 0.88
  });

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
