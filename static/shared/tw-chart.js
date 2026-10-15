// static/shared/tw-chart.js — tiny SVG charts (task 5.3a2 · SYSTEMS_INDEX §25c). No library.
//
//   twChart(container, { type: 'line' | 'bar', points: [{ label, value }], title })
//     → draws one chart into container (replaces its content) and returns the wrapper element.
//     label = text already formatted by the caller (twFormatDate …) · value = number ≥ 0.
//     title = the chart's accessible name (role="img" + aria-label "title: first → last, total").
//     Every point / bar carries a <title> (native tooltip: "label: value").
//
// Rules: colors = DS-COLOR tokens only (CSS below, injected once as <style id="tw-chart-style">) ·
// sizes = DS-SIZE tokens · text comes from the caller (twT) — this file has no visible text of its own.
// Loaded as a page asset (PAGE_ASSETS → {{v:tw-chart.js}}) — never in the Page Shell.
(function () {
  'use strict';

  var STYLE_ID = 'tw-chart-style';
  var W = 300, H = 100, PAD = 4;
  var CSS = ''
    + '.tw-chart{display:flex;flex-direction:column;gap:var(--space-2)}'
    + '.tw-chart svg{display:block;width:100%;height:clamp(96px,22vw,140px);overflow:visible}'
    + '.tw-chart-grid{stroke:var(--color-border-subtle);stroke-width:1;vector-effect:non-scaling-stroke}'
    + '.tw-chart-area{fill:rgba(var(--color-brand-primary-rgb),.12);stroke:none}'
    + '.tw-chart-line{fill:none;stroke:var(--color-brand-primary);stroke-width:2;stroke-linejoin:round;vector-effect:non-scaling-stroke}'
    + '.tw-chart-dot{fill:transparent;stroke:none}'
    + '.tw-chart-dot:hover{fill:var(--color-brand-primary)}'
    + '.tw-chart-bar{fill:var(--color-brand-primary)}'
    + '.tw-chart-bar:hover{fill:var(--color-brand-primary-hover)}'
    + '.tw-chart-x{display:flex;justify-content:space-between;gap:var(--space-2);font-size:var(--size-font-2xs);color:var(--color-text-muted)}'
    + '.tw-chart-max{font-size:var(--size-font-2xs);color:var(--color-text-muted)}';

  function injectStyle() {
    if (typeof document === 'undefined' || document.getElementById(STYLE_ID)) return;
    var s = document.createElement('style');
    s.id = STYLE_ID;
    s.textContent = CSS;
    (document.head || document.documentElement).appendChild(s);
  }

  function esc(v) {   // SVG text — twEscHtml is the one implementation (§54)
    return typeof window.twEscHtml === 'function' ? window.twEscHtml(v) : '';
  }
  function num(v) { v = Number(v); return isFinite(v) && v > 0 ? v : 0; }
  function r1(v) { return Math.round(v * 10) / 10; }

  // Pure geometry (tests read it): points → {max, xs[], ys[], bars[{x, y, w, h}]}
  function layout(points, type) {
    var n = points.length, max = 0, i;
    for (i = 0; i < n; i++) max = Math.max(max, num(points[i].value));
    var top = max || 1, innerH = H - PAD * 2, out = { max: max, xs: [], ys: [], bars: [] };
    var step = n > 1 ? (W - PAD * 2) / (n - 1) : 0, slot = n ? W / n : W;
    for (i = 0; i < n; i++) {
      var v = num(points[i].value), h = innerH * v / top;
      out.xs.push(r1(n > 1 ? PAD + step * i : W / 2));
      out.ys.push(r1(H - PAD - h));
      var bw = Math.max(1, slot * 0.6);
      out.bars.push({ x: r1(slot * i + (slot - bw) / 2), y: r1(H - PAD - h), w: r1(bw), h: r1(h) });
    }
    return out;
  }

  function svgHtml(points, type) {
    var g = layout(points, type), parts = [], i;
    for (i = 1; i <= 3; i++) {
      var gy = r1(PAD + (H - PAD * 2) * (i - 1) / 2);
      parts.push('<line class="tw-chart-grid" x1="0" x2="' + W + '" y1="' + gy + '" y2="' + gy + '"/>');
    }
    if (type === 'bar') {
      g.bars.forEach(function (b, k) {
        parts.push('<rect class="tw-chart-bar" x="' + b.x + '" y="' + b.y + '" width="' + b.w + '" height="' + Math.max(b.h, 0.5)
          + '" rx="1"><title>' + esc(points[k].label) + ': ' + num(points[k].value) + '</title></rect>');
      });
    } else if (points.length) {
      var pts = g.xs.map(function (x, k) { return x + ',' + g.ys[k]; }).join(' ');
      parts.push('<polygon class="tw-chart-area" points="' + g.xs[0] + ',' + (H - PAD) + ' ' + pts + ' '
        + g.xs[g.xs.length - 1] + ',' + (H - PAD) + '"/>');
      parts.push('<polyline class="tw-chart-line" points="' + pts + '"/>');
      g.xs.forEach(function (x, k) {
        parts.push('<circle class="tw-chart-dot" cx="' + x + '" cy="' + g.ys[k] + '" r="3"><title>'
          + esc(points[k].label) + ': ' + num(points[k].value) + '</title></circle>');
      });
    }
    return { max: g.max, html: '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" aria-hidden="true">'
      + parts.join('') + '</svg>' };
  }

  function twChart(container, opts) {
    opts = opts || {};
    injectStyle();
    var points = (opts.points || []).map(function (p) { return { label: String(p.label == null ? '' : p.label), value: num(p.value) }; });
    var type = opts.type === 'bar' ? 'bar' : 'line';
    var total = points.reduce(function (s, p) { return s + p.value; }, 0);
    var svg = svgHtml(points, type);
    var wrap = document.createElement('div');
    wrap.className = 'tw-chart';
    wrap.setAttribute('role', 'img');
    wrap.setAttribute('aria-label', String(opts.title || '') + (points.length
      ? ': ' + points[0].label + ' → ' + points[points.length - 1].label + ' · ' + total : ''));
    var mid = points.length ? points[Math.floor((points.length - 1) / 2)].label : '';
    wrap.innerHTML = '<div class="tw-chart-max">' + esc(String(svg.max)) + '</div>' + svg.html
      + '<div class="tw-chart-x"><span>' + esc(points.length ? points[0].label : '') + '</span><span>' + esc(mid)
      + '</span><span>' + esc(points.length ? points[points.length - 1].label : '') + '</span></div>';
    if (container) { container.textContent = ''; container.appendChild(wrap); }
    return wrap;
  }

  twChart.layout = layout;
  window.twChart = twChart;
}());
