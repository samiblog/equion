// 실측·적합·잔차 차트 — 의존 없이 SVG로 그린다(식 작업대). 위 칸은 실측과 적합, 아래 칸은 잔차와 ±2 표준오차 띠.
// 마우스를 올리면 그 기간의 값이 뜬다. 색은 tokens.css 의 --c-* (밝은·어두운 바탕에서 함께 바뀐다).
// 문서(md)의 vega-lite 차트는 md.js 가 그린다.

import { h, short } from './util.js';

const NS = 'http://www.w3.org/2000/svg';

function el(name, attrs = {}, text = '') {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  if (text) node.textContent = text;
  return node;
}

function extent(lists, include = []) {
  let lo = Infinity;
  let hi = -Infinity;
  for (const list of lists) for (const v of list) if (v != null) { if (v < lo) lo = v; if (v > hi) hi = v; }
  for (const v of include) { if (v < lo) lo = v; if (v > hi) hi = v; }
  if (!Number.isFinite(lo)) return [0, 1];
  if (lo === hi) return [lo - 1, hi + 1];
  const pad = (hi - lo) * 0.06;
  return [lo - pad, hi + pad];
}

/** 보기 좋은 눈금 값들(1·2·5 × 10ⁿ 간격) */
function ticks(lo, hi, count) {
  const raw = (hi - lo) / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(Math.abs(v) < step * 1e-9 ? 0 : v);
  return out;
}

function path(ys, sx, sy) {
  let d = '';
  let pen = false;
  for (let i = 0; i < ys.length; i++) {
    if (ys[i] == null) { pen = false; continue; }
    d += `${pen ? 'L' : 'M'}${sx(i).toFixed(1)},${sy(ys[i]).toFixed(1)}`;
    pen = true;
  }
  return d;
}

/** 기간 눈금 — 해가 바뀌는 곳(분기·월 자료)이나 고르게 */
function periodTicks(period, room) {
  const n = period.length;
  const want = Math.max(2, Math.floor(room / 64));
  const years = period.map((p) => /^\d{4}/.exec(String(p))?.[0]);
  const starts = [];
  for (let i = 0; i < n; i++) if (years[i] && (i === 0 || years[i] !== years[i - 1])) starts.push(i);
  if (starts.length >= 3 && starts.length < n) {
    const every = Math.max(1, Math.ceil(starts.length / want));
    // 해 단위로 끊되 5·10년처럼 읽기 쉬운 간격으로
    const nice = [1, 2, 5, 10, 20, 25, 50].find((s) => s >= every) || every;
    return starts.filter((i) => Number(years[i]) % nice === 0).map((i) => ({ i, label: years[i] }));
  }
  const every = Math.max(1, Math.ceil(n / want));
  const out = [];
  for (let i = 0; i < n; i += every) out.push({ i, label: String(period[i]) });
  return out;
}

function std(values) {
  const xs = values.filter((v) => v != null);
  if (xs.length < 2) return 0;
  const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
  return Math.sqrt(xs.reduce((a, b) => a + (b - mean) ** 2, 0) / (xs.length - 1));
}

/**
 * box 에 차트를 그린다. series: {period, actual, fitted, resid}. opts.se: 회귀 표준오차(없으면 잔차의 표준편차).
 * 돌려주는 것: 치우는 함수.
 */
export function drawFit(box, series, opts = {}) {
  box.textContent = '';
  box.classList.add('fit');
  const period = series?.period || [];
  const n = period.length;
  if (!n) return () => {};
  const actual = series.actual || [];
  const fitted = series.fitted || [];
  const resid = series.resid || [];
  const se = opts.se || std(resid);

  box.append(h('div', { class: 'legend' },
    h('span', { class: 'key', style: { '--c': 'var(--c-actual)' } }, '실측'),
    h('span', { class: 'key dashed', style: { '--c': 'var(--c-fitted)' } }, '적합'),
    h('span', { class: 'key', style: { '--c': 'var(--c-resid)' } }, '잔차'),
    se ? h('span', { class: 'key band', style: { '--c': 'var(--c-band)' } }, '±2 표준오차') : null));
  const holder = h('div', { style: { position: 'relative' } });
  const tip = h('div', { class: 'tip', hidden: true });
  box.append(holder, tip);

  let svg = null;
  const draw = () => {
    const W = Math.max(360, Math.round(box.clientWidth || 760));
    const L = 52, R = 12, T = 8, TOP_H = Math.round(Math.min(250, Math.max(170, W * 0.26))), GAP = 22, BOT_H = 96, B = 24;
    const H = T + TOP_H + GAP + BOT_H + B;
    const sx = (i) => L + (n > 1 ? (i / (n - 1)) * (W - L - R) : (W - L - R) / 2);
    svg?.remove();
    svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': '실측·적합·잔차 차트' });

    const panel = (top, height, [lo, hi], count) => {
      const sy = (v) => top + height - ((v - lo) / (hi - lo)) * height;
      for (const v of ticks(lo, hi, count)) {
        svg.append(el('line', { x1: L, x2: W - R, y1: sy(v), y2: sy(v), style: 'stroke: var(--c-grid)', 'stroke-width': 1 }));
        svg.append(el('text', { x: L - 8, y: sy(v) + 3.8, 'text-anchor': 'end' }, short(v)));
      }
      return sy;
    };
    const syTop = panel(T, TOP_H, extent([actual, fitted]), 4);
    svg.append(el('path', { d: path(fitted, sx, syTop), fill: 'none', style: 'stroke: var(--c-fitted)', 'stroke-width': 1.7, 'stroke-dasharray': '5 3', 'stroke-linejoin': 'round' }));
    svg.append(el('path', { d: path(actual, sx, syTop), fill: 'none', style: 'stroke: var(--c-actual)', 'stroke-width': 1.5, 'stroke-linejoin': 'round' }));

    const botTop = T + TOP_H + GAP;
    const syBot = panel(botTop, BOT_H, extent([resid], se ? [-2.2 * se, 2.2 * se] : [0]), 2);
    if (se) svg.append(el('rect', { x: L, width: W - L - R, y: syBot(2 * se), height: syBot(-2 * se) - syBot(2 * se), style: 'fill: var(--c-band)' }));
    svg.append(el('line', { x1: L, x2: W - R, y1: syBot(0), y2: syBot(0), style: 'stroke: var(--ink-4)', 'stroke-width': 1 }));
    svg.append(el('path', { d: path(resid, sx, syBot), fill: 'none', style: 'stroke: var(--c-resid)', 'stroke-width': 1.4, 'stroke-linejoin': 'round' }));

    for (const { i, label } of periodTicks(period, W - L - R)) {
      svg.append(el('line', { x1: sx(i), x2: sx(i), y1: H - B, y2: H - B + 4, style: 'stroke: var(--ink-4)', 'stroke-width': 1 }));
      svg.append(el('text', { x: sx(i), y: H - 6, 'text-anchor': 'middle' }, label));
    }
    svg.append(el('line', { x1: L, x2: W - R, y1: H - B, y2: H - B, style: 'stroke: var(--line-strong)', 'stroke-width': 1 }));

    // 마우스를 올린 기간
    const cross = el('line', { y1: T, y2: H - B, style: 'stroke: var(--ink-4)', 'stroke-width': 1, 'stroke-dasharray': '3 3', visibility: 'hidden' });
    const dots = ['--c-actual', '--c-fitted', '--c-resid'].map((c) => el('circle', { r: 3.4, style: `fill: var(${c}); stroke: var(--paper)`, 'stroke-width': 1.5, visibility: 'hidden' }));
    const hit = el('rect', { x: L, y: T, width: W - L - R, height: H - B - T, fill: 'transparent' });
    svg.append(cross, ...dots, hit);
    const hide = () => { tip.hidden = true; for (const node of [cross, ...dots]) node.setAttribute('visibility', 'hidden'); };
    hit.addEventListener('pointerleave', hide);
    hit.addEventListener('pointermove', (e) => {
      const rect = svg.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * W;
      const i = Math.max(0, Math.min(n - 1, Math.round(((x - L) / (W - L - R)) * (n - 1))));
      cross.setAttribute('x1', sx(i)); cross.setAttribute('x2', sx(i)); cross.setAttribute('visibility', 'visible');
      [[actual, syTop], [fitted, syTop], [resid, syBot]].forEach(([ys, sy], k) => {
        if (ys[i] == null) { dots[k].setAttribute('visibility', 'hidden'); return; }
        dots[k].setAttribute('cx', sx(i)); dots[k].setAttribute('cy', sy(ys[i])); dots[k].setAttribute('visibility', 'visible');
      });
      tip.textContent = '';
      tip.append(h('div', { class: 't' }, String(period[i])),
        ...[['실측', actual, '--c-actual'], ['적합', fitted, '--c-fitted'], ['잔차', resid, '--c-resid']].map(([label, ys, c]) =>
          h('div', { class: 'r' }, h('i', { style: { '--c': `var(${c})` } }, label), h('b', {}, short(ys[i])))));
      tip.hidden = false;
      const scale = rect.width / W;
      const left = sx(i) * scale;
      const flip = left > rect.width - tip.offsetWidth - 24;
      tip.style.left = `${flip ? left - tip.offsetWidth - 12 : left + 12}px`;
      tip.style.top = `${holder.offsetTop + T + 6}px`;
    });
    holder.append(svg);
  };
  draw();
  let timer = 0;
  let width = box.clientWidth;
  const watcher = new ResizeObserver(() => {
    if (!box.clientWidth || Math.abs(box.clientWidth - width) < 8) return;
    width = box.clientWidth;
    clearTimeout(timer);
    timer = setTimeout(draw, 80);
  });
  watcher.observe(box);
  return () => watcher.disconnect();
}
