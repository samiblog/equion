// 문서(md) 그리기 — 결과 카드(summary.md)와 프로젝트의 md 파일. 표·코드·그림과 ```vega-lite 차트(같은 폴더의 CSV)를 그린다.
//
// - md 속 HTML 은 글로만 보인다(html: false). 그린 뒤 한 번 더 정화한다(DOMPurify) — 프로젝트의 파일은 믿지 않는다.
// - 차트의 자료는 이 프로젝트 안의 파일만 읽는다(문서 기준 상대 경로 → 서버가 폴더 밖을 거절한다). 바깥 주소는 읽지 않는다.
// - 문서 속 링크: 프로젝트 안의 파일은 앱에서 열고, 바깥 주소는 열지 않고 복사한다(앱은 인터넷으로 나가지 않는다).
// 차트의 색·글꼴은 tokens.css 에서 읽는다. 테마가 바뀌면 다시 그린다. 틀은 Lectern 0.69.1 의 charts.js 를 따랐다.

import { blobURL, getJSON, papi, query } from './api.js';
import { copyText, h } from './util.js';

const VEGA = ['/web/vendor/vega/vega.min.js', '/web/vendor/vega/vega-lite.min.js'];
const IMAGE = /\.(png|jpe?g|gif|webp)$/i;
const NUMBER = /^[-+−]?(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+)?(?:[eE][-+]?\d+)?\s*(?:%|%p)?$/;
let vegaLoading = null;
const charts = new Set();      // 그려 둔 차트들 {node, redraw} — 테마가 바뀌면 다시 그린다

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const node = document.createElement('script');
    node.src = src;
    node.onload = () => resolve(undefined);
    node.onerror = () => reject(new Error(`불러오지 못했습니다: ${src}`));
    document.head.append(node);
  });
}

async function vegaLibs() {
  if (!vegaLoading) vegaLoading = (async () => { for (const src of VEGA) await loadScript(src); })();
  await vegaLoading;
  return [window.vega, window.vegaLite];
}

/** 문서 기준 상대 경로 → 프로젝트 기준 경로. 폴더 밖·바깥 주소면 null */
export function resolvePath(dir, ref) {
  if (!ref || /^[a-z][a-z0-9+.-]*:/i.test(ref) || ref.startsWith('//') || ref.startsWith('/')) return null;
  const parts = (dir ? dir.split('/') : []).filter(Boolean);
  for (const seg of decodeURIComponent(ref.split(/[?#]/)[0]).replace(/\\/g, '/').split('/')) {
    if (!seg || seg === '.') continue;
    if (seg === '..') { if (!parts.length) return null; parts.pop(); } else parts.push(seg);
  }
  return parts.join('/');
}

function token(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

function vegaConfig() {
  const font = token('--font-ui');
  const ink = token('--ink'), ink2 = token('--ink-2'), ink3 = token('--ink-3'), grid = token('--c-grid');
  const axis = { labelColor: ink3, titleColor: ink2, domainColor: token('--line-strong'), tickColor: token('--line-strong'), gridColor: grid,
    labelFont: font, titleFont: font, labelFontSize: 11, titleFontSize: 11.5, titleFontWeight: 600, labelPadding: 6, tickSize: 4 };
  return {
    background: null, font, padding: 2,
    title: { color: ink, font: token('--font-display'), fontSize: 13.5, fontWeight: 600, anchor: 'start', offset: 10 },
    axis, axisX: { grid: false, labelAngle: 0 }, axisY: { domain: false, ticks: false },
    legend: { labelColor: ink2, titleColor: ink2, labelFont: font, titleFont: font, labelFontSize: 11.5, symbolType: 'stroke', symbolStrokeWidth: 2.4, symbolSize: 180, orient: 'top', padding: 0, offset: 4 },
    header: { labelColor: ink, titleColor: ink, labelFont: font, titleFont: font },
    view: { stroke: null },
    line: { strokeWidth: 1.7, strokeJoin: 'round' }, bar: { cornerRadiusEnd: 2 }, text: { color: ink }, rule: { color: ink3 },
    range: { category: palette() },
  };
}

function palette() {
  return ['--k-est', '--k-sim', '--k-hs', '--k-an', '--k-data', '--k-run', '--k-prop'].map(token);
}

/** 색으로 나눈 시리즈에 뜻이 통하는 색을 준다 — 실측은 잉크, 나머지는 색표 순서(추정 카드와 식 작업대의 색이 같아진다) */
function meaningfulColors(spec) {
  const color = spec?.encoding?.color;
  const fold = (spec.transform || []).find((t) => Array.isArray(t.fold))?.fold;
  if (!color || color.scale || !fold || color.field !== ((spec.transform.find((t) => t.fold).as || ['key'])[0])) return;
  const rest = palette();
  let k = 0;
  color.scale = { domain: fold, range: fold.map((name) => (/실측|actual/i.test(name) ? token('--c-actual') : rest[k++ % rest.length])) };
}

/** data.url(이 프로젝트의 파일)을 읽어 values 로 바꾼다 */
async function inlineData(node, ctx, vega, depth = 0) {
  if (!node || typeof node !== 'object' || depth > 12) return;
  if (Array.isArray(node)) { for (const item of node) await inlineData(item, ctx, vega, depth + 1); return; }
  const data = node.data;
  if (data && typeof data === 'object' && typeof data.url === 'string') {
    const path = resolvePath(ctx.dir, data.url);
    if (path == null) throw new Error(`자료는 이 프로젝트 안의 파일만 읽습니다 — 문서 기준 상대 경로로 적으세요: ${data.url}`);
    const file = await getJSON(papi(ctx.pid, `file${query({ path })}`));
    if (file.kind !== 'text') throw new Error(`읽을 수 없는 자료 파일입니다: ${data.url}`);
    const type = data.format?.type || (/\.json$/i.test(path) ? 'json' : /\.tsv$/i.test(path) ? 'tsv' : 'csv');
    node.data = { values: vega.read(file.text, { ...(data.format || {}), type, parse: data.format?.parse || 'auto' }) };
  }
  for (const key of ['layer', 'concat', 'hconcat', 'vconcat', 'spec']) await inlineData(node[key], ctx, vega, depth + 1);
}

function tooltipHandler() {
  let tip = null;
  return (_handler, event, _item, value) => {
    if (value == null || value === '') { tip?.remove(); tip = null; return; }
    if (!tip) { tip = h('div', { class: 'vg-tip' }); document.body.append(tip); }
    tip.textContent = '';
    if (typeof value === 'object') {
      for (const [k, v] of Object.entries(value)) tip.append(h('div', { class: 'r' }, h('span', {}, k), h('b', {}, String(v))));
    } else tip.textContent = String(value);
    const x = Math.min(event.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    const y = Math.min(event.clientY + 14, window.innerHeight - tip.offsetHeight - 8);
    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;
  };
}

async function drawVega(node, source, ctx) {
  const [vega, vegaLite] = await vegaLibs();
  const spec = JSON.parse(source);
  await inlineData(spec, ctx, vega);
  const single = !['facet', 'repeat', 'concat', 'hconcat', 'vconcat'].some((k) => k in spec);
  const width = Math.max(240, node.clientWidth || 640);
  if (spec.width === 'container' || (single && spec.width == null)) {
    spec.width = width;
    spec.height = (typeof spec.height === 'number' ? spec.height : 220) + 46;
    spec.autosize = { type: 'fit', contains: 'padding' };
  }
  if (single) {
    meaningfulColors(spec);
    const mark = typeof spec.mark === 'string' ? { type: spec.mark } : spec.mark;
    if (mark?.type === 'line' && mark.point == null) spec.mark = { ...mark, point: { opacity: 0, size: 70 }, tooltip: true };   // 점 위에서 값이 뜨게
  }
  const problems = [];
  const logger = vega.logger(vega.Error);
  logger.error = (...args) => { problems.push(args.find((a) => a instanceof Error) || new Error(args.map(String).join(' '))); return logger; };
  const loader = vega.loader();
  loader.load = () => Promise.reject(new Error('바깥 자료는 읽지 않습니다'));      // 자료는 위에서 이미 넣었다
  loader.sanitize = () => Promise.reject(new Error('바깥 주소는 쓰지 않습니다'));
  const compiled = vegaLite.compile(spec, { config: vegaConfig(), logger }).spec;
  const view = new vega.View(vega.parse(compiled), { renderer: 'svg', container: node, hover: true, loader, logger });
  view.tooltip(tooltipHandler());
  await view.runAsync();
  if (problems.length) { view.finalize(); throw problems[0]; }
  return view;
}

function chartBlock(source, ctx) {
  const node = h('div', { class: 'chart' });
  let view = null;
  let width = 0;
  const redraw = async () => {
    if (!node.isConnected) return;
    view?.finalize();
    view = null;
    node.textContent = '';
    node.classList.remove('failed');
    width = node.clientWidth;
    try {
      view = await drawVega(node, source, ctx);
    } catch (err) {
      node.classList.add('failed');
      node.textContent = '';
      node.append(h('div', {}, `차트를 그리지 못했습니다 — ${err.message}`), h('pre', {}, source.length > 600 ? `${source.slice(0, 600)}…` : source));
    }
  };
  let timer = 0;
  new ResizeObserver(() => {
    if (!node.clientWidth || Math.abs(node.clientWidth - width) < 12) return;
    clearTimeout(timer);
    timer = setTimeout(redraw, 120);
  }).observe(node);
  charts.add({ node, redraw });
  return { node, redraw };
}

/** 테마가 바뀌었을 때 — 그려 둔 차트를 새 색으로 */
export function recolorCharts() {
  for (const entry of [...charts]) {
    if (!entry.node.isConnected) { charts.delete(entry); continue; }
    entry.redraw();
  }
}

function decorateTables(root) {
  for (const table of root.querySelectorAll('table')) {
    const rows = [...table.querySelectorAll('tbody tr')];
    const cols = Math.max(0, ...rows.map((r) => r.children.length));
    for (let c = 0; c < cols; c++) {
      const cells = rows.map((r) => r.children[c]).filter(Boolean);
      const filled = cells.filter((td) => td.textContent.trim() && td.textContent.trim() !== '—');
      const numeric = filled.length > 0 && filled.filter((td) => NUMBER.test(td.textContent.trim())).length >= filled.length * 0.7;
      if (!numeric) continue;
      for (const td of cells) td.classList.add('n');
      table.querySelector(`thead tr > :nth-child(${c + 1})`)?.classList.add('n');
    }
    const wrap = h('div', { class: 'table-wrap' });
    table.replaceWith(wrap);
    wrap.append(table);
  }
}

/**
 * md 글을 box 에 그린다.
 * ctx: {pid, dir(문서가 있는 폴더 — 프로젝트 기준), openFile(path), openRecord(id)}
 */
export async function renderDoc(box, text, ctx) {
  box.classList.add('doc');
  box.textContent = '';
  const md = window.markdownit({ html: false, linkify: false, breaks: false });
  // 주석(<!-- … --> — 노트·보고서의 구역 표시)은 보이지 않게. 코드 블록 안의 것은 그대로 둔다
  const source = String(text).split(/(^```[\s\S]*?^```[^\n]*$|^~~~[\s\S]*?^~~~[^\n]*$)/m)
    .map((part, i) => (i % 2 ? part : part.replace(/<!--[\s\S]*?-->/g, ''))).join('');
  const clean = window.DOMPurify.sanitize(md.render(source), { USE_PROFILES: { html: true }, FORBID_TAGS: ['style', 'form', 'input', 'button', 'iframe'] });
  const holder = document.createElement('template');
  holder.innerHTML = clean;
  const root = holder.content;

  const pending = [];
  for (const code of root.querySelectorAll('pre > code')) {
    const lang = (/language-([\w-]+)/.exec(code.className) || [])[1] || '';
    if (lang === 'vega-lite') {
      const block = chartBlock(code.textContent, ctx);
      code.parentElement.replaceWith(block.node);
      pending.push(block);
    } else if (lang === 'equion') code.parentElement.classList.add('eq-block');
  }
  decorateTables(root);
  for (const img of root.querySelectorAll('img')) {
    const path = resolvePath(ctx.dir, img.getAttribute('src') || '');
    img.removeAttribute('src');
    if (path && IMAGE.test(path)) blobURL(papi(ctx.pid, `raw${query({ path })}`)).then((url) => { img.src = url; }).catch(() => {});
  }
  for (const a of root.querySelectorAll('a[href]')) {
    const href = a.getAttribute('href') || '';
    a.removeAttribute('target');
    a.addEventListener('click', (e) => {
      e.preventDefault();
      if (href.startsWith('#')) {
        document.getElementById(href.slice(1))?.scrollIntoView({ behavior: 'smooth' });
        return;
      }
      const path = resolvePath(ctx.dir, href);
      if (path != null) ctx.openFile?.(path);
      else copyText(href, '바깥 주소는 앱에서 열지 않습니다 — 주소를 복사했습니다');
    });
  }
  box.append(root);
  // 요소가 화면에 붙은 뒤에야 폭을 잴 수 있다
  await Promise.all(pending.map((block) => block.redraw()));
}
