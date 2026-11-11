// 식 작업대의 차트 — 의존 없이 SVG로 그린다. 색은 tokens.css 의 이름(밝은·어두운 바탕에서 함께 바뀐다).
//
//   drawFit(box, series, {se, onPick})    위 칸은 실측과 적합, 아래 칸은 잔차와 ±2 표준오차 띠
//   drawLines(box, {period, lines, …})    선 여러 개를 한 칸에(겹쳐 보기·단독 모의·항등식 검사)
//
// 마우스를 올리면 그 기간의 값이 뜨고, 누르면 onPick(그 기간)을 부른다(잔차가 튄 기간을 짚어 더미를 넣는 일 등).
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
    const nice = [1, 2, 5, 10, 20, 25, 50].find((s) => s >= every) || every;      // 5·10년처럼 읽기 쉬운 간격으로
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

/** 기간 이름을 차례가 서는 숫자로 — '1990Q2'·'1990M11'·'1990-03'·'1990' (겹쳐 볼 때 표본이 다른 기록의 기간을 한 축에 놓는다) */
export function periodKey(label) {
  const m = /^(\d{4})\D*(\d+)?/.exec(String(label));
  return m ? Number(m[1]) * 100 + Number(m[2] || 0) : 0;
}

/** 여러 시리즈의 기간을 한 축으로 — [{period, …}] → 차례대로 선 기간 목록 */
export function unionPeriods(lists) {
  const seen = new Map();
  for (const list of lists) for (const p of list || []) if (!seen.has(p)) seen.set(p, periodKey(p));
  return [...seen.entries()].sort((a, b) => a[1] - b[1]).map(([p]) => p);
}

/** 한 축(periods)에 맞춰 값을 놓는다 — 없는 기간은 null */
export function align(periods, period, values) {
  const at = new Map((period || []).map((p, i) => [p, values?.[i] ?? null]));
  return periods.map((p) => (at.has(p) ? at.get(p) : null));
}

/**
 * 그리는 틀 — 폭이 바뀌면 다시 그리고, 마우스가 가리키는 기간을 알려 준다.
 * paint(svg, W) 는 {H, L, R, T, B, sx, marks:[{values, sy, color}], rows(i)} 를 돌려준다.
 */
function frame(box, period, paint, { onPick, label }) {
  const n = period.length;
  const holder = h('div', { style: { position: 'relative' } });
  const tip = h('div', { class: 'tip', hidden: true });
  box.append(holder, tip);
  let svg = null;
  const draw = () => {
    const W = Math.max(320, Math.round(box.clientWidth || 720));
    svg?.remove();
    svg = el('svg', { role: 'img', 'aria-label': label });
    const g = paint(svg, W);
    svg.setAttribute('viewBox', `0 0 ${W} ${g.H}`);
    const { L, R, T, B, H, sx } = g;
    const cross = el('line', { y1: T, y2: H - B, style: 'stroke: var(--ink-4)', 'stroke-width': 1, 'stroke-dasharray': '3 3', visibility: 'hidden' });
    const dots = g.marks.map((m) => el('circle', { r: 3.4, style: `fill: ${m.color}; stroke: var(--paper)`, 'stroke-width': 1.5, visibility: 'hidden' }));
    const hit = el('rect', { x: L, y: T, width: W - L - R, height: H - B - T, fill: 'transparent', style: onPick ? 'cursor: crosshair' : '' });
    svg.append(cross, ...dots, hit);
    const at = (e) => {
      const rect = svg.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * W;
      return [Math.max(0, Math.min(n - 1, Math.round(((x - L) / (W - L - R)) * (n - 1)))), rect];
    };
    const hide = () => { tip.hidden = true; for (const node of [cross, ...dots]) node.setAttribute('visibility', 'hidden'); };
    hit.addEventListener('pointerleave', hide);
    hit.addEventListener('pointermove', (e) => {
      const [i, rect] = at(e);
      cross.setAttribute('x1', sx(i)); cross.setAttribute('x2', sx(i)); cross.setAttribute('visibility', 'visible');
      g.marks.forEach((m, k) => {
        if (m.values[i] == null) { dots[k].setAttribute('visibility', 'hidden'); return; }
        dots[k].setAttribute('cx', sx(i)); dots[k].setAttribute('cy', m.sy(m.values[i])); dots[k].setAttribute('visibility', 'visible');
      });
      tip.textContent = '';
      tip.append(h('div', { class: 't' }, String(period[i])), ...g.rows(i).map(([name, value, color]) =>
        h('div', { class: 'r' }, h('i', { style: { '--c': color } }, name), h('b', {}, short(value)))));
      if (onPick) tip.append(h('div', { class: 'hint' }, '누르면 이 기간을 짚습니다'));
      tip.hidden = false;
      const left = sx(i) * (rect.width / W);
      const flip = left > rect.width - tip.offsetWidth - 24;
      tip.style.left = `${flip ? left - tip.offsetWidth - 12 : left + 12}px`;
      tip.style.top = `${holder.offsetTop + T + 6}px`;
    });
    if (onPick) hit.addEventListener('click', (e) => onPick(at(e)[0]));
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

function grid(svg, W, L, R, top, height, [lo, hi], count) {
  const sy = (v) => top + height - ((v - lo) / (hi - lo)) * height;
  for (const v of ticks(lo, hi, count)) {
    svg.append(el('line', { x1: L, x2: W - R, y1: sy(v), y2: sy(v), style: 'stroke: var(--c-grid)', 'stroke-width': 1 }));
    svg.append(el('text', { x: L - 8, y: sy(v) + 3.8, 'text-anchor': 'end' }, short(v)));
  }
  return sy;
}

function xAxis(svg, period, sx, W, L, R, H, B) {
  for (const { i, label } of periodTicks(period, W - L - R)) {
    svg.append(el('line', { x1: sx(i), x2: sx(i), y1: H - B, y2: H - B + 4, style: 'stroke: var(--ink-4)', 'stroke-width': 1 }));
    svg.append(el('text', { x: sx(i), y: H - 6, 'text-anchor': 'middle' }, label));
  }
  svg.append(el('line', { x1: L, x2: W - R, y1: H - B, y2: H - B, style: 'stroke: var(--line-strong)', 'stroke-width': 1 }));
}

/**
 * 실측·적합·잔차. series: {period, actual, fitted, resid}. opts.se: 회귀 표준오차(없으면 잔차의 표준편차),
 * opts.onPick(i): 기간을 눌렀을 때, opts.picked: 짚어 둔 기간의 자리(세로줄로 표시). 돌려주는 것: 치우는 함수.
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
  return frame(box, period, (svg, W) => {
    const L = 52, R = 12, T = 8, TOP_H = Math.round(Math.min(250, Math.max(170, W * 0.26))), GAP = 22, BOT_H = 96, B = 24;
    const H = T + TOP_H + GAP + BOT_H + B;
    const sx = (i) => L + (n > 1 ? (i / (n - 1)) * (W - L - R) : (W - L - R) / 2);
    const syTop = grid(svg, W, L, R, T, TOP_H, extent([actual, fitted]), 4);
    svg.append(el('path', { d: path(fitted, sx, syTop), fill: 'none', style: 'stroke: var(--c-fitted)', 'stroke-width': 1.7, 'stroke-dasharray': '5 3', 'stroke-linejoin': 'round' }));
    svg.append(el('path', { d: path(actual, sx, syTop), fill: 'none', style: 'stroke: var(--c-actual)', 'stroke-width': 1.5, 'stroke-linejoin': 'round' }));
    const syBot = grid(svg, W, L, R, T + TOP_H + GAP, BOT_H, extent([resid], se ? [-2.2 * se, 2.2 * se] : [0]), 2);
    if (se) svg.append(el('rect', { x: L, width: W - L - R, y: syBot(2 * se), height: syBot(-2 * se) - syBot(2 * se), style: 'fill: var(--c-band)' }));
    svg.append(el('line', { x1: L, x2: W - R, y1: syBot(0), y2: syBot(0), style: 'stroke: var(--ink-4)', 'stroke-width': 1 }));
    svg.append(el('path', { d: path(resid, sx, syBot), fill: 'none', style: 'stroke: var(--c-resid)', 'stroke-width': 1.4, 'stroke-linejoin': 'round' }));
    // 띠 밖으로 나간 잔차는 점으로 — 어느 기간이 튀었는지 한눈에
    if (se) for (let i = 0; i < n; i++) if (resid[i] != null && Math.abs(resid[i]) > 2 * se) svg.append(el('circle', { cx: sx(i), cy: syBot(resid[i]), r: 2.6, style: 'fill: var(--c-resid)' }));
    if (opts.picked != null && opts.picked >= 0 && opts.picked < n) {
      svg.append(el('line', { x1: sx(opts.picked), x2: sx(opts.picked), y1: T, y2: H - B, style: 'stroke: var(--accent)', 'stroke-width': 1.5 }));
    }
    xAxis(svg, period, sx, W, L, R, H, B);
    return { H, L, R, T, B, sx,
      marks: [{ values: actual, sy: syTop, color: 'var(--c-actual)' }, { values: fitted, sy: syTop, color: 'var(--c-fitted)' }, { values: resid, sy: syBot, color: 'var(--c-resid)' }],
      rows: (i) => [['실측', actual[i], 'var(--c-actual)'], ['적합', fitted[i], 'var(--c-fitted)'], ['잔차', resid[i], 'var(--c-resid)']] };
  }, { onPick: opts.onPick, label: '실측·적합·잔차 차트' });
}

/**
 * 선 여러 개를 한 칸에. spec: {period, lines: [{label, values, color, dashed, width}], zero(0 선을 긋는다), height, note}.
 * opts.onPick(i). 돌려주는 것: 치우는 함수.
 */
export function drawLines(box, spec, opts = {}) {
  box.textContent = '';
  box.classList.add('fit');
  const period = spec.period || [];
  const n = period.length;
  const lines = (spec.lines || []).filter((l) => l.values?.some((v) => v != null));
  if (!n || !lines.length) { box.append(h('div', { class: 'empty-state' }, spec.empty || '그릴 값이 없습니다.')); return () => {}; }
  box.append(h('div', { class: 'legend' }, lines.map((l) => h('span', { class: `key ${l.dashed ? 'dashed' : ''}`.trim(), style: { '--c': l.color } }, l.label)),
    spec.note ? h('span', { class: 'note' }, spec.note) : null));
  return frame(box, period, (svg, W) => {
    const L = 52, R = 12, T = 8, B = 24;
    const HEIGHT = spec.height || Math.round(Math.min(280, Math.max(180, W * 0.3)));
    const H = T + HEIGHT + B;
    const sx = (i) => L + (n > 1 ? (i / (n - 1)) * (W - L - R) : (W - L - R) / 2);
    const sy = grid(svg, W, L, R, T, HEIGHT, extent(lines.map((l) => l.values), spec.zero ? [0] : []), 4);
    if (spec.zero) svg.append(el('line', { x1: L, x2: W - R, y1: sy(0), y2: sy(0), style: 'stroke: var(--ink-4)', 'stroke-width': 1 }));
    for (const l of [...lines].reverse()) {       // 첫 선(실측)이 맨 위에 오게
      svg.append(el('path', { d: path(l.values, sx, sy), fill: 'none', style: `stroke: ${l.color}`, 'stroke-width': l.width || 1.6, 'stroke-linejoin': 'round',
        ...(l.dashed ? { 'stroke-dasharray': '5 3' } : {}) }));
    }
    xAxis(svg, period, sx, W, L, R, H, B);
    return { H, L, R, T, B, sx, marks: lines.map((l) => ({ values: l.values, sy, color: l.color })), rows: (i) => lines.map((l) => [l.label, l.values[i], l.color]) };
  }, { onPick: opts.onPick, label: spec.title || '차트' });
}
