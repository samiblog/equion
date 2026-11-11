// 실측·적합·잔차 차트 — 의존 없이 SVG로 그린다(시험판 D0). md 보기의 vega-lite 차트는 D1에서 Lectern 것을 옮긴다.

const NS = 'http://www.w3.org/2000/svg';
const COLORS = { actual: '#1f2328', fitted: '#1f6feb', resid: '#cf222e' };

function el(name, attrs = {}, text = '') {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  if (text) node.textContent = text;
  return node;
}

function extent(...lists) {
  let lo = Infinity;
  let hi = -Infinity;
  for (const list of lists) for (const v of list) if (v != null) { if (v < lo) lo = v; if (v > hi) hi = v; }
  if (!Number.isFinite(lo)) return [0, 1];
  if (lo === hi) return [lo - 1, hi + 1];
  const pad = (hi - lo) * 0.05;
  return [lo - pad, hi + pad];
}

function path(xs, ys, sx, sy) {
  let d = '';
  let pen = false;
  for (let i = 0; i < ys.length; i++) {
    if (ys[i] == null) { pen = false; continue; }
    d += `${pen ? 'L' : 'M'}${sx(xs[i]).toFixed(1)},${sy(ys[i]).toFixed(1)}`;
    pen = true;
  }
  return d;
}

function fmt(v) {
  const a = Math.abs(v);
  return a >= 1000 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : a >= 1 ? v.toFixed(2) : v.toPrecision(2);
}

/** series: {period: [...], actual: [...], fitted: [...], resid: [...]} */
export function drawFit(box, series) {
  box.textContent = '';
  const period = series?.period || [];
  if (!period.length) return;
  const W = 760, H = 330, L = 54, R = 10, T = 8, MID = 200, GAP = 26, B = 22;
  const n = period.length;
  const xs = period.map((_, i) => i);
  const sx = (i) => L + (n > 1 ? (i / (n - 1)) * (W - L - R) : 0);
  const legend = document.createElement('div');
  legend.className = 'legend';
  for (const [key, label] of [['actual', '실측'], ['fitted', '적합'], ['resid', '잔차(아래)']]) {
    const s = document.createElement('span');
    s.className = 'key';
    s.style.setProperty('--c', COLORS[key]);
    s.textContent = label;
    legend.append(s);
  }
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': '실측·적합·잔차' });

  const panel = (top, bottom, lists, draw) => {
    const [lo, hi] = extent(...lists);
    const sy = (v) => bottom - ((v - lo) / (hi - lo)) * (bottom - top);
    for (let k = 0; k <= 3; k++) {
      const v = lo + ((hi - lo) * k) / 3;
      svg.append(el('line', { x1: L, x2: W - R, y1: sy(v), y2: sy(v), stroke: '#e6e8eb', 'stroke-width': 1 }));
      svg.append(el('text', { x: L - 6, y: sy(v) + 3.5, 'text-anchor': 'end', 'font-size': 10.5, fill: '#6a737d' }, fmt(v)));
    }
    draw(sy, lo, hi);
  };
  panel(T, MID, [series.actual || [], series.fitted || []], (sy) => {
    svg.append(el('path', { d: path(xs, series.actual || [], sx, sy), fill: 'none', stroke: COLORS.actual, 'stroke-width': 1.4 }));
    svg.append(el('path', { d: path(xs, series.fitted || [], sx, sy), fill: 'none', stroke: COLORS.fitted, 'stroke-width': 1.4, 'stroke-dasharray': '4 2' }));
  });
  panel(MID + GAP, H - B, [series.resid || [], [0]], (sy) => {
    svg.append(el('line', { x1: L, x2: W - R, y1: sy(0), y2: sy(0), stroke: '#9aa1a9', 'stroke-width': 1 }));
    svg.append(el('path', { d: path(xs, series.resid || [], sx, sy), fill: 'none', stroke: COLORS.resid, 'stroke-width': 1.2 }));
  });
  const ticks = Math.min(6, n);
  for (let k = 0; k < ticks; k++) {
    const i = Math.round((k * (n - 1)) / Math.max(1, ticks - 1));
    svg.append(el('text', { x: sx(i), y: H - 6, 'text-anchor': k === 0 ? 'start' : k === ticks - 1 ? 'end' : 'middle', 'font-size': 10.5, fill: '#6a737d' }, period[i]));
  }
  box.append(legend, svg);
}
