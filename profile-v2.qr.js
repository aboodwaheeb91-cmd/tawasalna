// profile-v2.qr.js — QR code rendering for Profile V2
// No dependencies. Renders QR using external api.qrserver.com service.

function renderQR(el, showcaseUrl){
  if(!el) return;
  el.innerHTML = '<div class="sc-qr-inner">'
    + '<img src="https://api.qrserver.com/v1/create-qr-code/?size=160x160&qzone=1&data='
    + encodeURIComponent(showcaseUrl) + '" alt="QR">'
    + '<div class="sc-qr-center"><img src="https://wrxvmdmknhoufoeprpoc.supabase.co/storage/v1/object/public/site/55555.svg" alt=""></div>'
    + '</div>';
}
window.renderQR = renderQR;
