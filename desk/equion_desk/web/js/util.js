// 화면 공통 도구 — 요소 만들기, 숫자·때 표기, 복사, 늦춰 부르기.

import { ICONS } from './icons.js';

/** 요소 하나. props: class·dataset·on<이벤트>·그 밖은 속성. 자식은 요소·글·null. */
export function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value == null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key === 'style' && typeof value === 'object') for (const [k, v] of Object.entries(value)) node.style.setProperty(k, v);
    else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'hidden' || key === 'disabled') node[key] = !!value;
    else node.setAttribute(key, value === true ? '' : String(value));
  }
  add(node, children);
  return node;
}

function add(node, children) {
  for (const child of children) {
    if (child == null || child === false) continue;
    if (Array.isArray(child)) add(node, child);
    else node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

/** 아이콘(SVG). 이름은 icons.js */
export function icon(name, cls = '') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('class', `ic ${cls}`.trim());
  svg.setAttribute('aria-hidden', 'true');
  svg.innerHTML = ICONS[name] || '';       // icons.js 의 고정된 글자뿐이다(바깥 글이 들어오지 않는다)
  return svg;
}

export function clear(node) { node.textContent = ''; return node; }

// ---- 표기 --------------------------------------------------------------------------------------

export function num(v, digits = 4) {
  if (v == null || Number.isNaN(v)) return '—';
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-4 || a >= 1e9)) return v.toExponential(3);
  return v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** p값 — 아주 작으면 '<0.001' */
export function pval(p) {
  if (p == null || Number.isNaN(p)) return '—';
  return p < 0.001 ? '<0.001' : p.toFixed(3);
}

/** 축·말풍선의 짧은 숫자 */
export function short(v) {
  if (v == null || Number.isNaN(v)) return '—';
  const a = Math.abs(v);
  if (a === 0) return '0';
  if (a >= 1e6 || a < 1e-3) return v.toExponential(2);
  const digits = a >= 1000 ? 0 : a >= 100 ? 1 : a >= 1 ? 2 : 3;
  return v.toLocaleString('en-US', { maximumFractionDigits: digits });
}

export function bytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10240 ? 1 : 0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function seconds(s) {
  if (s == null) return '';
  if (s < 1) return `${s.toFixed(2)}초`;
  if (s < 60) return `${s.toFixed(1)}초`;
  return `${Math.floor(s / 60)}분 ${Math.round(s % 60)}초`;
}

/** '2026-11-11T11:51:42' → '방금'·'3분 전'·'오늘 11:51'·'11월 9일 14:02' */
export function when(iso, now = Date.now()) {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return String(iso);
  const d = (now - t) / 1000;
  if (d < 45) return '방금';
  if (d < 3600) return `${Math.max(1, Math.round(d / 60))}분 전`;
  const date = new Date(t);
  const hm = `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  const today = new Date(now);
  if (date.toDateString() === today.toDateString()) return `오늘 ${hm}`;
  const y = date.getFullYear() === today.getFullYear() ? '' : `${date.getFullYear()}년 `;
  return `${y}${date.getMonth() + 1}월 ${date.getDate()}일 ${hm}`;
}

export const KINDS = { est: '추정', hs: '과거 재현', sim: '전망', an: '분석', run: '실행', data: '자료', prop: '제안' };
export const WHO = { desk: 'Desk', terminal: '터미널', claude: 'Claude', python: 'Python', script: '스크립트', 바깥: '바깥' };

/** 기록의 명령 글 — 터미널에서 치는 모양으로(옛 기록은 앞의 equion 이 없다) */
export function cmdText(command) {
  if (!command) return '';
  return /^equion(\s|$)/.test(command) ? command : `equion ${command}`;
}

export function kindClass(kind) { return KINDS[kind] ? `k-${kind}` : 'k-other'; }

export function kindPill(kind) {
  return h('span', { class: `kind ${kindClass(kind)}` }, KINDS[kind] || kind || '기록');
}

export function whoLabel(who) {
  return h('span', { class: `who ${who === 'claude' ? 'claude' : ''}`.trim() }, who === 'claude' ? icon('spark') : null, WHO[who] || who || '');
}

// ---- 그 밖 -------------------------------------------------------------------------------------

export function debounce(fn, wait) {
  let timer = 0;
  const run = (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); };
  run.flush = (...args) => { clearTimeout(timer); fn(...args); };
  return run;
}

let flashTimer = 0;
/** 화면 아래에 잠깐 뜨는 한 줄 */
export function flash(text) {
  document.getElementById('flash')?.remove();
  clearTimeout(flashTimer);
  document.body.append(h('div', { id: 'flash', role: 'status' }, text));
  flashTimer = setTimeout(() => document.getElementById('flash')?.remove(), 1800);
}

export async function copyText(text, said = '복사했습니다') {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = h('textarea', { style: { position: 'fixed', opacity: '0' } });
    area.value = text;
    document.body.append(area);
    area.select();
    document.execCommand('copy');
    area.remove();
  }
  flash(said);
}

/** 이름순(숫자는 크기대로) */
export const natural = new Intl.Collator('ko', { numeric: true, sensitivity: 'base' }).compare;
