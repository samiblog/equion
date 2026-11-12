// 전망 작업대(W3) — 가정을 적고, 기준선과 시나리오를 풀고, 결과를 본다.
//
//   ① 가정      외생 변수 × 전망 구간의 표(ASSUMPTIONS/*.csv). 직접 친 칸이 '가정', 비운 칸은 채우기 규칙이 채운다('채움').
//               엑셀에서 복사한 칸들을 그대로 붙여 넣는다. 저장해야 풀 때 쓰인다(풀기를 누르면 먼저 저장한다)
//               저장은 이 화면에서 친 칸만 보낸다 — 서버가 지금 파일에 얹으므로 그 사이 엑셀·Claude 가 고친 다른 칸은 그대로 남는다.
//               고치는 동안 파일이 밖에서 바뀌면 치지 않은 칸은 새 값으로 바꿔 보이고, 친 칸이 밖에서도 바뀌었으면 저장할 때 어느 값을 쓸지 묻는다.
//   ② 풀기      기준선(base)과 시나리오를 골라 푼다 — 단추를 누를 때만. 시나리오는 같은 가정의 기준선과 견준 차이를 함께 남긴다
//   ③ 결과      수준·전기비·전년동기비·연간·기준선 대비, 값의 종류(실측·가정·채움·해)를 칸의 색으로. 여러 기록을 고르면 연간 증가율을 나란히
//
// 가정·보정항·시나리오를 고쳐도 저절로 다시 풀지 않는다. 보정항의 규칙과 시나리오는 정의 파일이라 파일 보기의 '고치기'로 고친다.
// 보기(VIEWS/*.toml)는 어느 시리즈를 어떤 모양으로 볼지를 이름으로 적어 둔 것 — 다음 결과에도 같은 모양을 다시 적용한다.
// 푼 전망이 있으면 가정 표는 접어 두고(한 줄 요약) 결과를 먼저 보인다 — 가정을 고치려면 그 줄을 눌러 편다.

import { drawLines } from '../chart.js';
import { claudeButton } from '../claude.js';
import { confirmDialog, nameRule, popMenu } from '../dialog.js';
import { clear, copyText, flash, h, icon, kindPill, put, when, whoLabel } from '../util.js';
import { exportXlsx, sendToReport } from './send.js';

const MODES = [['level', '수준'], ['qoq', '전기비'], ['yoy', '전년동기비'], ['annual', '연간'], ['diff', '기준선 대비']];
const FLAG = { 실측: 'f-act', 가정: 'f-asm', 채움: 'f-fill', 해: 'f-sol', 결측: 'f-miss' };
const FILL = { last: '끝 값 그대로', growth: '최근 증가율로', trend: '추세로', none: '채우지 않음' };
const HIST = 4;             // 결과 표에서 전망 앞에 보이는 실측 기간 수
const fmt = (v, digits) => (v == null ? '—' : v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }));
const short = (id) => String(id).replace(/^sim:/, '');

export function forecastView(project, desc) {
  const el = h('div', { class: 'view forecast' });
  const st = {
    model: desc.model || null, info: null, error: null, picks: new Set(desc.scenarios || ['base']), start: desc.start || '', end: desc.end || '', vs: '', vintage: '',
    grid: null, dirty: false, open: typeof desc.open === 'boolean' ? desc.open : null, shown: desc.shown || null, view: null, compare: new Set(), others: new Map(),
    mode: desc.mode || 'level', series: desc.series || null, col: null, stale: false,
    saveError: null,        // 가정 표를 저장하지 못한 까닭 — 표 아래에(칸을 고치면 지운다). 읽기 오류(error)와 따로: 풀기를 막지 않는다
    base: null,             // 가정 표를 마지막으로 읽은 값(파일 그대로) — 친 칸의 '읽었던 값'
    typed: new Map(),       // 이 화면에서 친 칸 `기간|변수` → 치기 시작할 때 읽었던 값(저장할 때 이 칸들만 보낸다)
    clash: new Set(),       // 친 칸인데 밖에서도 다른 값으로 바뀐 칸 — 저장할 때 묻는다
    refreshed: 0,           // 고치는 동안 밖에서 바뀌어 새로 읽은(치지 않은) 칸의 수
    pending: Array.isArray(desc.compare) ? desc.compare : null,       // 열면서 견줄 기록(시나리오 폼의 '저장하고 풀기' — 함께 푼 기준선)
  };
  let disposeChart = () => {};
  let loaded = false;
  const save = () => project.saveView();

  async function load() {
    loaded = true;
    let same = false;
    try {
      const info = await project.get(`forecast${st.model ? `?model=${encodeURIComponent(st.model)}` : ''}`);
      const key = JSON.stringify(info);
      same = st.info != null && !st.error && key === st.infoKey;       // 다시 읽어도 같다(이 화면과 무관한 정의 파일이 바뀜) — 다시 그리지 않는다
      st.infoKey = key;
      st.info = info;
      st.error = st.info.error;
      st.model = st.info.model;
      mergeGrid(st.info.assume ? st.info.assume.values : null);
      for (const name of [...st.picks]) if (name !== 'base' && !st.info.scenarios.some((s) => s.name === name)) st.picks.delete(name);
      if (!st.picks.size) st.picks.add('base');
    } catch (err) {
      st.error = err.message;
    }
    const mine = records();
    if (!st.shown || !mine.some((r) => r.id === st.shown)) st.shown = mine[0]?.id || null;
    for (const id of [...st.compare]) if (!mine.some((r) => r.id === id)) st.compare.delete(id);
    if (same && (!st.shown || st.view?.id === st.shown)) { pairPending(); return; }
    render();
    if (st.shown && st.view?.id !== st.shown) showRecord(st.shown);
    pairPending();
  }

  /** 열면서 받은 '견줄 기록'을 고른다(한 번만) */
  async function pairPending() {
    const ids = st.pending;
    st.pending = null;
    if (!ids?.length) return;
    st.compare.clear();
    for (const id of ids) if (id !== st.shown && await fetchOther(id)) st.compare.add(id);
    drawResult();
  }

  /** 이 모형의 전망 기록 — 새것부터 */
  const records = () => (st.info?.records || []).filter((r) => r.model === st.model).reverse();

  /** 가정 표를 펴 둘까 — 사람이 정한 적이 없으면: 아직 푼 전망이 없을 때만 편다 */
  const assumeOpen = () => (st.dirty ? true : st.open ?? !records().length);

  async function showRecord(id) {
    st.shown = id;
    st.compare.delete(id);
    save();
    try {
      st.view = await project.get(`sim/view?id=${encodeURIComponent(id)}`);
      project.seen(id);
      if (st.mode === 'diff' && !st.view.diff) st.mode = 'level';
      if (!st.series) st.series = (st.view.meta.endogenous || st.view.names).slice(0, 6);
      st.series = st.series.filter((n) => st.view.names.includes(n));
      if (!st.series.length) st.series = st.view.names.slice(0, 6);
      if (st.col && !st.view.names.includes(st.col)) st.col = null;
    } catch (err) {
      st.view = null; st.shown = null; st.error = err.message;
    }
    drawResult();
  }

  async function fetchOther(id) {
    if (st.others.has(id)) return true;
    try { st.others.set(id, await project.get(`sim/view?id=${encodeURIComponent(id)}`)); return true; } catch { return false; }
  }

  async function toggleCompare(id) {
    if (st.compare.has(id)) st.compare.delete(id);
    else if (await fetchOther(id)) st.compare.add(id);
    drawResult();
  }

  // ---- ① 가정 표 --------------------------------------------------------------------------------

  const cellKey = (period, name) => `${period}|${name}`;
  const splitKey = (key) => { const i = key.indexOf('|'); return [key.slice(0, i), key.slice(i + 1)]; };

  /** 읽은 가정 표를 화면의 표에 — 고치는 중이 아니면 통째로. 고치는 중이면 친 칸은 그대로 두고 나머지만 지금 파일의 값으로(밖의 고침을 보인다).
   *  친 칸이 밖에서도 다른 값으로 바뀌었으면 clash 로 표시한다(저장할 때 묻는다) */
  function mergeGrid(fresh) {
    if (!fresh) { Object.assign(st, { grid: null, base: null, dirty: false, refreshed: 0 }); st.typed.clear(); st.clash.clear(); return; }
    if (!st.dirty || !st.grid) {
      Object.assign(st, { grid: structuredClone(fresh), base: structuredClone(fresh), dirty: false, refreshed: 0 });
      st.typed.clear(); st.clash.clear();
      return;
    }
    let refreshed = 0;
    for (const [p, cells] of Object.entries(fresh)) {
      const row = (st.grid[p] ||= {});
      for (const [name, now] of Object.entries(cells)) {
        const key = cellKey(p, name);
        const mine = row[name] ?? '';
        if (st.typed.has(key)) {
          const was = st.typed.get(key);
          if (mine === was || mine === now) {            // 고친 것이 없게 됐다(되돌렸거나 밖에서 같은 값을 적었다) — 파일을 따른다
            st.typed.delete(key); st.clash.delete(key);
            if (mine !== now) { row[name] = now; refreshed++; }
          } else if (now !== was) st.clash.add(key);
          else st.clash.delete(key);
        } else if (mine !== now) { row[name] = now; refreshed++; }
      }
    }
    st.base = structuredClone(fresh);
    st.refreshed += refreshed;
    st.dirty = st.typed.size > 0;
  }

  /** 칸을 친다 — 처음 치는 칸이면 그때 읽었던 값을 적어 둔다 */
  function touch(period, name) {
    const key = cellKey(period, name);
    if (!st.typed.has(key)) st.typed.set(key, st.base?.[period]?.[name] ?? '');
  }

  async function saveGrid({ quiet = false, force = false } = {}) {
    const a = st.info.assume;
    const bad = badCells();
    if (bad.length) { showBad(bad); return false; }
    // 친 칸 가운데 읽었던 값과 다른 것만 — 나머지 칸은 서버가 지금 파일 그대로 둔다
    const rows = {}, bases = {};
    for (const [key, was] of st.typed) {
      const [p, name] = splitKey(key);
      const v = String(st.grid?.[p]?.[name] ?? '').replace(/,/g, '').trim();
      if (v === was) continue;
      (rows[p] ||= {})[name] = v;
      (bases[p] ||= {})[name] = was;
    }
    const saved = () => {
      for (const [p, cells] of Object.entries(rows)) for (const [name, v] of Object.entries(cells)) ((st.base ||= {})[p] ||= {})[name] = v;    // 저장한 값이 이제 파일의 값
      st.typed.clear(); st.clash.clear();
      Object.assign(st, { dirty: false, saveError: null, refreshed: 0 });
    };
    if (!Object.keys(rows).length) {
      saved();
      if (!quiet) { flash('바뀐 것이 없습니다'); render(); }
      return true;
    }
    try {
      const res = await project.compute('assume', { name: a.name, columns: st.info.exogenous.map((x) => x.name), rows, bases, ...(force ? { force: true } : {}) }, { quiet: true });
      saved();
      if (!quiet) flash(res.result.change ? `가정 표를 저장했습니다 — 바뀜 기록 ${res.result.change}` : '바뀐 것이 없습니다');
      if (!quiet) render();
      return true;
    } catch (err) {
      if (err.kind === 'conflict' && Array.isArray(err.detail)) return resolveClash(err.detail, { quiet });
      if (err.kind !== 'busy') { st.saveError = err.message; st.open = true; render(); }
      return false;
    }
  }

  /** 친 칸이 밖에서도 바뀌었다 — 칸마다 읽었던 값·밖에서 바꾼 값·내가 친 값을 보이고 고르게 한다(밖에서 바꾼 다른 칸은 어느 쪽이든 그대로) */
  async function resolveClash(list, { quiet }) {
    for (const c of list) st.clash.add(cellKey(c.period, c.name));
    st.open = true;
    render();
    const show = (v) => (v === '' ? h('span', { class: 'muted' }, '빈칸(채움)') : v);
    const body = h('div', { class: 'adopt' },
      h('p', {}, '이 화면에서 친 칸을 밖(엑셀 · Claude · 편집기)에서도 바꿨습니다. 어느 값을 쓸지 고르세요 — 밖에서 바꾼 다른 칸은 어느 쪽이든 그대로 둡니다.'),
      h('table', { class: 'choice-table' }, h('thead', {}, h('tr', {}, ['칸', '읽었던 값', '밖에서 바꾼 값', '내가 친 값'].map((x) => h('th', {}, x)))),
        h('tbody', {}, list.slice(0, 12).map((c) => h('tr', {}, h('td', { class: 'mono' }, `${c.name} ${c.period}`), h('td', { class: 'was' }, show(c.base)), h('td', {}, show(c.now)), h('td', { class: 'mine' }, show(c.mine)))))),
      list.length > 12 ? h('p', { class: 'muted' }, `… 외 ${list.length - 12}칸`) : null);
    const pick = await confirmDialog({ title: '밖에서도 바뀐 칸이 있습니다', body, confirm: '내 값으로 저장', alt: '밖의 값 쓰기', wide: true });
    if (pick === true) return saveGrid({ quiet, force: true });
    if (pick !== 'alt') return false;
    for (const c of list) {
      const key = cellKey(c.period, c.name);
      (st.grid[c.period] ||= {})[c.name] = c.now;
      ((st.base ||= {})[c.period] ||= {})[c.name] = c.now;
      st.typed.delete(key); st.clash.delete(key);
    }
    st.dirty = st.typed.size > 0;
    if (st.dirty) return saveGrid({ quiet });
    render();
    flash('밖의 값을 표에 넣었습니다 — 저장할 내 칸이 남지 않았습니다');
    return true;
  }

  /** 숫자가 아닌 칸 — 저장하면 서버가 받지 않는다(쉼표는 천 단위로 읽는다) */
  function badCells() {
    const info = st.info;
    const out = [];
    if (!info?.assume || !st.grid) return out;
    for (const p of info.periods) {
      for (const c of info.exogenous) {
        const v = String(st.grid[p]?.[c.name] ?? '').replace(/,/g, '').trim();
        if (v !== '' && !Number.isFinite(Number(v))) out.push({ name: c.name, period: p, value: st.grid[p][c.name] });
      }
    }
    return out;
  }

  /** 숫자가 아닌 칸을 펴서 보이고 첫 칸으로 */
  function showBad(bad) {
    if (!assumeOpen()) { st.open = true; render(); }
    el.querySelector(`[data-cell="${CSS.escape(`${bad[0].period}|${bad[0].name}`)}"]`)?.focus();
    flash(`숫자가 아닌 칸이 있어 저장하지 않았습니다 — ${bad[0].name} ${bad[0].period}`);
  }

  function assumeBox() {
    const info = st.info;
    const a = info.assume;
    if (!a || !info.exogenous.length) return h('div', { class: 'muted pad0' }, '이 모형에는 가정할 외생 변수가 없습니다.');
    const cols = info.exogenous;
    const open = assumeOpen();
    const typed = (name) => info.periods.filter((p) => (st.grid[p]?.[name] ?? '') !== '').length;
    const clashNote = h('div', { class: 'asm-note', 'data-note': 'clash', hidden: !st.clash.size },
      st.clash.size ? `밖에서도 바뀐 칸 ${st.clash.size} — ${[...st.clash].slice(0, 4).map((k) => splitKey(k).reverse().join(' ')).join(' · ')}. 저장할 때 어느 값을 쓸지 묻습니다.` : '');
    const freshNote = h('div', { class: 'asm-note info', 'data-note': 'fresh', hidden: !(st.dirty && st.refreshed) },
      st.refreshed ? `고치는 동안 밖(엑셀 · Claude)에서 바뀐 칸 ${st.refreshed}개를 새로 읽었습니다 — 이 화면에서 친 칸은 그대로입니다. 저장하면 친 칸만 씁니다.` : '');
    const gapNote = h('div', { class: 'asm-note bad', hidden: true });
    const numNote = h('div', { class: 'asm-note bad', 'data-note': 'num', hidden: true });
    const saveNote = h('div', { class: 'asm-note bad', 'data-note': 'save', hidden: !st.saveError }, st.saveError ? `저장하지 못했습니다 — ${st.saveError}` : '');
    const paint = () => {             // 값 사이의 빈칸·숫자가 아닌 칸을 붉게 — 채우기 규칙은 마지막으로 적은 값 뒤만 채운다
      const found = gaps();
      const set = new Set(found.map((g) => `${g.period}|${g.name}`));
      const bad = badCells();
      const wrong = new Set(bad.map((g) => `${g.period}|${g.name}`));
      for (const cell of el.querySelectorAll('.asm-grid .cell')) {
        const gap = set.has(cell.dataset.cell);
        cell.classList.toggle('gap', gap);
        cell.classList.toggle('bad', wrong.has(cell.dataset.cell));
        cell.setAttribute('aria-invalid', String(wrong.has(cell.dataset.cell)));
        cell.placeholder = gap ? '비었음' : '채움';
      }
      gapNote.hidden = !found.length;
      if (found.length) gapNote.textContent = `값 사이의 빈칸은 채워지지 않습니다 — ${found.slice(0, 4).map((g) => `${g.name} ${g.period}`).join(' · ')}${found.length > 4 ? ` 외 ${found.length - 4}칸` : ''}. 값을 적거나, 그 뒤의 값을 지워 채우기에 맡기세요.`;
      numNote.hidden = !bad.length;
      if (bad.length) numNote.textContent = `숫자가 아닌 칸 — ${bad.slice(0, 4).map((g) => `${g.name} ${g.period} ‘${g.value}’`).join(' · ')}${bad.length > 4 ? ` 외 ${bad.length - 4}칸` : ''}. 고치기 전에는 저장하지 않습니다.`;
      const b = el.querySelector('[data-act="save-assume"]');
      if (b) { b.disabled = !st.dirty || bad.length > 0; b.classList.toggle('primary', st.dirty && !bad.length); b.title = bad.length ? '숫자가 아닌 칸을 먼저 고치세요' : '가정 표를 저장한다 — 바뀜 기록에 남는다'; }
    };
    const mark = () => {
      st.dirty = true;
      if (st.saveError) { st.saveError = null; saveNote.hidden = true; }     // 고쳤으니 지난 저장 오류는 지운다(다시 저장하면 다시 본다)
      const n = el.querySelector('.asm-note[data-note="unsaved"]');
      if (n) n.hidden = false;
      paint();
    };
    const cellInput = (period, name) => {
      const key = cellKey(period, name);
      const clash = st.clash.has(key);
      const input = h('input', { class: `cell ${st.typed.has(key) ? 'edited' : ''} ${clash ? 'clash' : ''}`.trim(), type: 'text', inputmode: 'decimal', value: st.grid[period]?.[name] ?? '', placeholder: '채움', spellcheck: 'false', 'data-cell': key, 'aria-label': `${name} ${period}`,
        title: clash ? `밖에서 ${st.base?.[period]?.[name] || '빈칸'}(으)로 바뀌었습니다 — 저장할 때 어느 값을 쓸지 묻습니다` : '' });
      input.addEventListener('input', () => { touch(period, name); (st.grid[period] ||= {})[name] = input.value.trim(); input.classList.toggle('typed', input.value.trim() !== ''); input.classList.add('edited'); mark(); });
      input.addEventListener('keydown', (e) => {            // 위·아래·Enter 로 칸을 오간다(표 계산기처럼)
        const step = e.key === 'ArrowDown' || e.key === 'Enter' ? 1 : e.key === 'ArrowUp' ? -1 : 0;
        if (!step || e.ctrlKey || e.metaKey) return;
        const next = info.periods[info.periods.indexOf(period) + step];
        const target = next && el.querySelector(`[data-cell="${CSS.escape(`${next}|${name}`)}"]`);
        if (target) { e.preventDefault(); target.focus(); target.select(); }
      });
      input.addEventListener('paste', (e) => {
        const text = e.clipboardData?.getData('text') || '';
        if (!/[\t\n]/.test(text.trim())) return;          // 칸 하나짜리는 보통처럼
        e.preventDefault();
        const r0 = info.periods.indexOf(period), c0 = cols.findIndex((x) => x.name === name);
        text.replace(/\r/g, '').replace(/\n+$/, '').split('\n').forEach((line, i) => line.split('\t').forEach((value, j) => {
          const p = info.periods[r0 + i], c = cols[c0 + j];
          if (!p || !c) return;
          touch(p, c.name);
          (st.grid[p] ||= {})[c.name] = value.replace(/,/g, '').trim();
        }));
        mark();
        render();
      });
      input.classList.toggle('typed', (st.grid[period]?.[name] ?? '') !== '');
      return input;
    };
    const head = h('div', { class: 'raw-cap' },
      h('button', { class: 'fold', type: 'button', 'aria-expanded': String(open), 'data-act': 'fold-assume', title: open ? '가정 표를 접는다' : '가정 표를 펴서 고친다',
        onclick: () => { st.open = !open; save(); render(); } }, icon('chevron', 'caret'), h('b', {}, '① 가정')),
      open ? h('span', { class: 'muted', title: '채우기 규칙(equion.toml [forecast] fill)은 마지막 값 뒤의 빈칸만 채웁니다 — 값 사이의 빈칸은 채우지 않습니다' }, '마지막 값 뒤의 빈칸은 ', h('b', {}, FILL[a.fill] || a.fill), ' 채웁니다')
        : h('span', { class: 'asm-sum' }, cols.map((c) => { const n = typed(c.name); return h('span', { class: `pc-flat ${n ? 'asm' : ''}`.trim(), title: n ? `${c.name} — 직접 적은 칸 ${n}` : `${c.name} — 모두 채움(${FILL[a.fill] || a.fill})` }, c.name, h('small', {}, n ? ` ${n}칸` : ' 채움')); })),
      h('span', { class: 'cap-tools' },
      open ? h('button', { class: 'link mono', type: 'button', title: '가정 파일을 연다', onclick: () => project.openTab({ type: 'file', path: a.file }) }, a.file) : null,
      open ? h('button', { class: `btn small ${st.dirty && !badCells().length ? 'primary' : ''}`.trim(), type: 'button', 'data-act': 'save-assume', disabled: !st.dirty || badCells().length > 0, title: '가정 표를 저장한다 — 바뀜 기록에 남는다', onclick: () => saveGrid() }, '가정 저장')
        : h('button', { class: 'btn small quiet', type: 'button', onclick: () => { st.open = true; save(); render(); } }, '고치기')));
    if (!open) return h('div', { class: 'asm-box shut' }, head);
    const hist = cols[0].last.map((x) => x.period);
    const box = h('div', { class: 'asm-box' }, head,
      h('div', { class: 'raw-scroll' }, h('table', { class: 'asm-grid' },
        h('thead', {}, h('tr', {}, h('th', {}, ''), cols.map((c) => h('th', {}, c.name)))),
        h('tbody', {},
          hist.slice(-2).map((p) => h('tr', { class: 'hist' }, h('th', {}, p), cols.map((c) => h('td', {}, fmt(c.last.find((x) => x.period === p)?.value, 3))))),
          info.periods.map((p, i) => h('tr', { class: i === 0 ? 'first' : '' }, h('th', {}, p), cols.map((c) => h('td', {}, cellInput(p, c.name)))))))),
      clashNote, gapNote, numNote, saveNote, freshNote,
      h('div', { class: 'asm-note', 'data-note': 'unsaved', hidden: !st.dirty }, '저장하지 않은 가정이 있습니다 — ‘풀기’를 누르면 먼저 저장하고 풉니다.'),
      a.extra.length ? h('div', { class: 'muted' }, `파일에는 이 모형의 외생이 아닌 열도 있습니다(${a.extra.join(' · ')}) — 쓰지 않습니다.`) : null);
    const found = gaps();
    if (found.length) {
      const set = new Set(found.map((g) => `${g.period}|${g.name}`));
      for (const cell of box.querySelectorAll('.cell')) if (set.has(cell.dataset.cell)) { cell.classList.add('gap'); cell.placeholder = '비었음'; }
      gapNote.hidden = false;
      gapNote.textContent = `값 사이의 빈칸은 채워지지 않습니다 — ${found.slice(0, 4).map((g) => `${g.name} ${g.period}`).join(' · ')}${found.length > 4 ? ` 외 ${found.length - 4}칸` : ''}. 값을 적거나, 그 뒤의 값을 지워 채우기에 맡기세요.`;
    }
    const bad = badCells();
    if (bad.length) {
      const wrong = new Set(bad.map((g) => `${g.period}|${g.name}`));
      for (const cell of box.querySelectorAll('.cell')) if (wrong.has(cell.dataset.cell)) { cell.classList.add('bad'); cell.setAttribute('aria-invalid', 'true'); }
      numNote.hidden = false;
      numNote.textContent = `숫자가 아닌 칸 — ${bad.slice(0, 4).map((g) => `${g.name} ${g.period} ‘${g.value}’`).join(' · ')}${bad.length > 4 ? ` 외 ${bad.length - 4}칸` : ''}. 고치기 전에는 저장하지 않습니다.`;
    }
    return box;
  }

  /** 값 사이의 빈칸 — 그 변수의 실측이 끝난 뒤이고, 뒤에 직접 적은 값이 있는데 비어 있는 칸. 채우기 규칙이 채우지 못해 풀 수 없다 */
  function gaps() {
    const info = st.info;
    const out = [];
    if (!info?.assume || !st.grid) return out;
    for (const c of info.exogenous) {
      const has = info.periods.map((p) => (st.grid[p]?.[c.name] ?? '') !== '');
      const lastTyped = has.lastIndexOf(true);
      const lastActual = info.periods.indexOf(c.last[c.last.length - 1]?.period);       // 전망 구간 안까지 실측이 있는 변수(끝이 들쭉날쭉한 자료)
      info.periods.forEach((p, i) => { if (i > lastActual && i < lastTyped && !has[i]) out.push({ name: c.name, period: p }); });
    }
    return out;
  }

  function addfactorBox() {
    const f = st.info.addfactors;
    if (!f) return null;
    const RULE = { zero: '0', last: '마지막 잔차 그대로', decay: '마지막 잔차를 줄여 가며', mean: '최근 잔차의 평균' };
    const eqs = Object.entries(f.eqs || {});
    return h('div', { class: 'add-box' }, h('b', {}, '보정항'), f.error ? h('span', { class: 'warn-text' }, f.error) : [
      h('span', { class: 'muted' }, `적지 않은 식은 ${RULE[f.default] || f.default}`),
      eqs.map(([part, r]) => h('span', { class: 'pc-flat', title: `${part} — ${RULE[r.rule] || r.rule}${r.half_life ? ` · 반감기 ${r.half_life}` : ''}${r.n ? ` · 최근 ${r.n}기` : ''}` }, `${part} ${r.rule}`)),
      f.values_file ? h('span', { class: 'tag', title: '직접 적은 값(판단 값)이 규칙 값을 덮습니다' }, `판단 값 ${f.values_file.split('/').pop()}`) : null],
    h('span', { class: 'grow' }), f.file ? h('button', { class: 'btn small quiet', type: 'button', title: '보정항의 규칙을 고친다(정의 파일)', onclick: () => project.openTab({ type: 'file', path: f.file, edit: true }) }, icon('doc'), '규칙 고치기') : null);
  }

  // ---- ② 풀기 -----------------------------------------------------------------------------------

  const picked = () => ['base', ...st.info.scenarios.map((s) => s.name)].filter((n) => st.picks.has(n));
  const rangeText = () => (st.start || st.end ? `${st.start || st.info.range?.[0] || ''}:${st.end || st.info.range?.[1] || ''}` : '');

  function command() {
    return `equion sim ${picked().join(' ')} --model ${st.model}${rangeText() ? ` --range ${rangeText()}` : ''}${st.vintage ? ` --vintage ${st.vintage}` : ''}${st.vs ? ` --vs ${st.vs}` : ''}`;
  }

  async function solve() {
    const found = rangeText() ? [] : gaps();          // 구간을 따로 적었으면 엔진이 그 구간으로 판단한다
    if (found.length) {
      st.open = true;
      render();
      el.querySelector(`[data-cell="${CSS.escape(`${found[0].period}|${found[0].name}`)}"]`)?.focus();
      flash('가정 표에 값 사이의 빈칸이 있어 풀 수 없습니다 — 값을 적거나 뒤의 값을 지우세요');
      return;
    }
    const bad = badCells();
    if (bad.length) { showBad(bad); return; }
    if (st.dirty && !(await saveGrid({ quiet: true }))) return;
    let made = [];
    try {
      const res = await project.compute('sim/run', { scenarios: picked(), model: st.model, range: rangeText(), vintage: st.vintage, vs: st.vs }, { quiet: true });
      made = res.result.ids;
      for (const id of made) project.seen(id);
      if (res.result.error) project.notify({ level: 'error', text: `${res.result.failed} 을(를) 풀지 못했습니다 — ${res.result.error}` });
    } catch (err) {
      if (err.kind === 'busy') return;
      st.error = err.message;
    }
    st.others.clear();
    st.compare.clear();
    if (made.length) st.open = false;             // 풀었으면 결과가 먼저 보이게 가정 표를 접는다
    await load();
    if (!made.length) return;
    for (const id of made.slice(0, -1)) if (await fetchOther(id)) st.compare.add(id);      // 함께 푼 것은 나란히
    await showRecord(made[made.length - 1]);
  }

  function runRow() {
    const info = st.info;
    const model = h('select', { class: 'an-select', 'aria-label': '모형' }, info.models.map((m) => h('option', { value: m }, m)));
    model.value = st.model;
    model.addEventListener('change', () => { Object.assign(st, { model: model.value, shown: null, view: null, series: null, dirty: false, open: null, col: null }); st.compare.clear(); save(); load(); });
    const cmd = h('span', { class: 'cmd' }, command());
    const refresh = () => { cmd.textContent = command(); save(); };
    const chip = (name, title) => {
      const b = h('button', { class: 'pc big', type: 'button', 'aria-pressed': String(st.picks.has(name)), title, 'data-scenario': name }, name === 'base' ? '기준선 base' : name);
      b.addEventListener('click', () => { if (st.picks.has(name)) st.picks.delete(name); else st.picks.add(name); if (!st.picks.size) st.picks.add('base'); for (const x of b.parentElement.querySelectorAll('[data-scenario]')) x.setAttribute('aria-pressed', String(st.picks.has(x.dataset.scenario))); refresh(); });
      return b;
    };
    const period = (key, placeholder) => {
      const input = h('input', { class: 'mini-input', type: 'text', value: st[key], placeholder, spellcheck: 'false', title: '비우면 equion.toml [forecast] range' });
      input.addEventListener('input', () => { st[key] = input.value.trim(); refresh(); });
      return input;
    };
    const pick = (key, options, title) => {
      const select = h('select', { class: 'mini-select', title }, options.map(([v, label]) => h('option', { value: v }, label)));
      select.value = st[key];
      select.addEventListener('change', () => { st[key] = select.value; refresh(); });
      return select;
    };
    const mine = records();
    const shock = (x) => `${x.var} ${x.kind === 'pct' || x.pct != null ? `${(x.pct ?? x.value) > 0 ? '+' : ''}${x.pct ?? x.value}%` : `${x.value > 0 ? '+' : ''}${x.value}`}`;
    return h('div', { class: 'an-form', onkeydown: (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); solve(); } } },
      h('div', { class: 'an-top' }, h('label', { class: 'an-field' }, h('span', {}, '모형'), model),
        h('div', { class: 'an-field grow' }, h('span', {}, '② 무엇을 풀까'), h('div', { class: 'chip-set scen' }, chip('base', '가정과 보정항만으로 푼 기준선'),
          info.scenarios.map((s) => (s.error ? h('span', { class: 'pc-flat bad', title: s.error }, `${s.name} — 읽지 못함`)
            : chip(s.name, `${s.desc || s.name}\n${(s.shocks || []).map(shock).join(' · ')}\n같은 가정의 기준선과 견준 차이를 함께 남깁니다`))))),
        h('button', { class: 'btn primary an-run', type: 'button', 'data-act': 'solve', disabled: project.busy || !!st.error, title: '고른 것을 차례로 푼다(Ctrl+Enter) — 기록(sim:)으로 남는다. 저장하지 않은 가정은 먼저 저장한다', onclick: solve }, icon('forward'), '풀기')),
      h('div', { class: 'eq-opts an-opts' },
        h('label', { class: 'opt' }, h('span', {}, '구간'), period('start', info.range?.[0] || '처음'), h('span', { class: 'tilde' }, '~'), period('end', info.range?.[1] || '끝')),
        mine.length ? h('label', { class: 'opt', title: '--vs — 지난 전망과 연간 증가율을 전후로 견준다' }, h('span', {}, '견줄 지난 전망'), pick('vs', [['', '없음'], ...mine.slice(0, 12).map((r) => [r.id, short(r.id)])])) : null,
        info.vintages.length > 1 ? h('label', { class: 'opt', title: '--vintage — 그 회차의 자료로 잠깐 푼다(지금 회차는 그대로). 자료가 바뀐 몫을 볼 때' }, h('span', {}, '자료 회차'), pick('vintage', [['', '지금 회차'], ...info.vintages.filter((v) => !v.current).map((v) => [v.id, v.id])])) : null),
      h('button', { class: 'cmdline', type: 'button', title: '같은 일을 터미널에서 하는 명령 — 누르면 복사합니다', onclick: () => copyText(cmd.textContent, '명령을 복사했습니다') }, h('span', { class: 'prompt' }, '>'), cmd, icon('copy')));
  }

  // ---- ③ 결과 -----------------------------------------------------------------------------------

  const resultBox = h('div', { class: 'fc-result' });

  function recordList() {
    const list = records();
    if (!list.length) return h('div', { class: 'empty-state' }, '아직 푼 전망이 없습니다. 가정을 적고 ‘풀기’를 누르세요.');
    return h('div', { class: 'cands runs' }, h('div', { class: 'cand-head' }, h('div', { class: 'cand-sum' }, h('b', {}, '③ 푼 전망'), h('span', { class: 'n' }, list.length), h('span', { class: 'muted' }, '— 줄을 누르면 보이고, 네모를 고르면 나란히 견줍니다'))),
      h('table', { class: 'cand' }, h('tbody', {}, list.slice(0, 6).map((r) => h('tr', { class: `${r.id === st.shown ? 'on' : ''} ${st.compare.has(r.id) ? 'vs' : ''}`.trim(), 'data-sim': r.id, onclick: () => showRecord(r.id) },
        h('td', { class: 'c-check' }, r.id !== st.shown ? h('button', { class: 'check', type: 'button', role: 'checkbox', 'aria-checked': String(st.compare.has(r.id)), 'aria-label': `${r.id} 와 견주기`, title: '보는 전망과 연간 증가율을 나란히',
          onclick: (e) => { e.stopPropagation(); toggleCompare(r.id); } }, st.compare.has(r.id) ? icon('check') : null) : null),
        h('td', { class: 'c-name' }, h('span', { class: 'mono' }, short(r.id)), r.scenario !== 'base' ? h('span', { class: 'tag accent' }, '시나리오') : null),
        h('td', { class: 'c-eq' }, `${r.range?.[0]} – ${r.range?.[1]}`, Object.keys(r.annual || {}).length ? ` · ${Object.entries(r.annual).slice(0, 2).map(([y, vals]) => `${y} ${Object.entries(vals).slice(0, 1).map(([k, v]) => `${k} ${v == null ? '—' : `${v.toFixed(2)}%`}`).join('')}`).join(' · ')}` : ''),
        h('td', { class: 'c-when' }, whoLabel(r.who), ' · ', when(r.created)))))));
  }

  function applyView(x) {
    const v = st.view;
    const names = x.series.map((n) => v.names.find((y) => y.toUpperCase() === n.toUpperCase())).filter(Boolean);
    st.series = names.length ? names : v.names.slice(0, 6);
    st.mode = x.show === 'diff' && !v.diff ? 'level' : x.show;
    st.col = null;
    save();
    drawResult();
    if (names.length < x.series.length) flash(`이 결과에 없는 시리즈는 뺐습니다 — ${x.series.filter((n) => !v.names.some((y) => y.toUpperCase() === n.toUpperCase())).join(', ')}`);
  }

  function drawResult() {
    disposeChart();
    disposeChart = () => {};
    clear(resultBox);
    put(resultBox, recordList());
    const v = st.view;
    if (!v || !st.shown) return;
    const m = v.meta;
    const vintage = project.overview?.vintage?.id;
    const start = Math.max(0, v.period.indexOf(m.range?.[0]));
    const names = st.series;
    const others = [...st.compare].map((id) => st.others.get(id)).filter(Boolean);
    resultBox.append(h('div', { class: 'result-head' }, kindPill('sim'), h('button', { class: 'rid', type: 'button', title: '이 기록의 카드를 따로 연다', onclick: () => project.openRecord(v.id) }, v.id),
      h('span', { class: 'meta' }, h('b', {}, m.scenario === 'base' ? '기준선' : `시나리오 ${m.scenario}`), h('span', {}, `모형 ${m.model}`), h('span', {}, `${m.range?.[0]} – ${m.range?.[1]}`), m.who ? whoLabel(m.who) : null, h('span', {}, when(m.created)),
        v.vintage && vintage && v.vintage !== vintage ? h('span', { class: 'tag warn', title: `자료 회차 ${v.vintage} 로 풀었습니다 — 지금 회차는 ${vintage}` }, `다른 회차 ${v.vintage}`) : null),
      h('span', { class: 'grow' }),
      st.compare.size === 1 ? h('button', { class: 'btn small', type: 'button', 'data-act': 'split', title: '고른 전망과 이 전망의 연간 성장률 바뀜을 자료 → 가정 → 식의 몫으로 나눈다(equion an split) — 하나씩 바꿔 다시 풀어',
        onclick: () => project.openTab({ type: 'analysis', analysis: 'split', target: `${[...st.compare][0]} ${v.id}`, options: {}, smpl: '', run: true }) }, icon('diff'), '요인 나누기') : null,
      h('button', { class: 'btn small', type: 'button', 'data-act': 'to-report', title: '이 전망의 표를 보고서의 한 구역으로 보낸다', onclick: () => sendToReport(project, v.id, { rows: names, show: st.mode === 'annual' ? 'level' : st.mode, annual: st.mode === 'annual' }) }, icon('doc'), '보고서로'),
      h('button', { class: 'btn small quiet', type: 'button', 'data-act': 'to-xlsx', title: '값·값의 종류·출처를 엑셀로', onclick: () => exportXlsx(project, [v.id, ...st.compare]) }, icon('table'), '엑셀로')));
    if (m.implicit?.length) resultBox.append(h('details', { class: 'implicit-box' }, h('summary', {}, `알아서 한 것 ${m.implicit.length}`), h('ul', { class: 'implicit' }, m.implicit.map((x) => h('li', {}, x)))));

    // 무엇을 어떤 모양으로 — 보이기와 저장한 보기, 그 아래 시리즈
    const views = st.info.views || [];
    const modes = MODES.filter(([k]) => k !== 'diff' || v.diff);
    resultBox.append(h('div', { class: 'fc-tools' },
      h('div', { class: 'segmented small', role: 'group', 'aria-label': '보이기' }, modes.map(([k, label]) => h('button', { type: 'button', 'aria-pressed': String(st.mode === k), 'data-mode': k, onclick: () => { st.mode = k; save(); drawResult(); } }, label))),
      h('span', { class: 'grow' }),
      h('button', { class: 'btn small quiet', type: 'button', 'data-act': 'views', title: '저장한 보기 — 어느 시리즈를 어떤 모양으로 볼지(VIEWS/*.toml)', onclick: (e) => popMenu(e.currentTarget, [h('div', { class: 'menu-title' }, '보기'),
        ...views.map((x) => ({ label: x.title || x.name, hint: `${x.series.join(' · ')} · ${(MODES.find(([k]) => k === x.show) || ['', x.show])[1]}`, onPick: () => applyView(x) })),
        { label: '이 보기 저장…', hint: '지금 고른 시리즈와 모양을 이름으로', onPick: saveView }], { cls: 'plain', align: 'right' }) }, icon('layers'), '보기', icon('chevron', 'down'))),
    h('div', { class: 'chip-set fc-series' }, v.names.map((n) => {
      const on = names.includes(n);
      return h('button', { class: `pc ${(m.exogenous || []).includes(n) ? 'exo' : ''}`.trim(), type: 'button', 'aria-pressed': String(on), 'data-series': n, title: (m.exogenous || []).includes(n) ? '외생 — 가정한 값' : '내생 — 푼 값',
        onclick: () => { st.series = on ? names.filter((x) => x !== n) : v.names.filter((x) => names.includes(x) || x === n); if (!st.series.length) st.series = [n]; if (st.col && !st.series.includes(st.col)) st.col = null; save(); drawResult(); } }, n);
    })));

    if (st.mode === 'annual' && v.annual) {
      const all = [v, ...others];
      const head = all.length > 1 ? ['연도', '', ...all.map((x) => short(x.id))] : ['연도', ...names];
      const body = all.length > 1
        ? v.annual.years.flatMap((y) => names.map((n, k) => h('tr', { class: k === 0 ? 'first' : '' }, h('th', {}, k === 0 ? y : ''), h('td', { class: 'name', 'data-var': n }, n), all.map((x) => h('td', {}, fmt(x.annual?.growth?.[n]?.[x.annual.years.indexOf(y)], 2), h('small', {}, '%'))))))
        : v.annual.years.map((y, i) => h('tr', {}, h('th', {}, y), names.map((n) => h('td', {}, fmt(v.annual.growth?.[n]?.[i], 2), h('small', {}, '%'), h('div', { class: 'sub' }, fmt(v.annual.level?.[n]?.[i], 1))))));
      resultBox.append(h('div', { class: 'raw-scroll tall' }, h('table', { class: 'fc-table' }, h('thead', {}, h('tr', {}, head.map((c) => h('th', {}, c)))), h('tbody', {}, body))),
        h('div', { class: 'fc-legend' }, h('span', {}, all.length > 1 ? '연간 증가율(%) — 고른 전망을 나란히' : '연간 증가율(%), 그 아래는 연간 수준')));
    } else {
      const src = st.mode === 'level' ? v.level : st.mode === 'qoq' ? v.qoq : st.mode === 'yoy' ? v.yoy : null;
      const periods = st.mode === 'diff' ? v.diff.period : v.period.slice(Math.max(0, start - HIST));
      const rows = periods.map((p, i) => {
        const k = v.period.indexOf(p);
        return h('tr', { class: `${k === start ? 'first' : ''} ${k < start ? 'hist' : ''}`.trim() }, h('th', {}, p), names.map((n) => {
          const value = st.mode === 'diff' ? v.diff.pct?.[n]?.[i] : src?.[n]?.[k];
          const flag = v.flag?.[n]?.[k];
          return h('td', { class: `${FLAG[flag] || ''} ${st.col === n ? 'col' : ''}`.trim(), title: flag ? `${n} ${p} — ${flag}` : '' }, fmt(value, 2), st.mode === 'level' ? null : h('small', {}, '%'),
            st.mode === 'diff' ? h('div', { class: 'sub' }, fmt(v.diff.abs?.[n]?.[i], 2)) : null);
        }));
      });
      resultBox.append(h('div', { class: 'raw-scroll tall' }, h('table', { class: 'fc-table' }, h('thead', {}, h('tr', {}, h('th', {}, ''), names.map((n) => h('th', { class: st.col === n ? 'col' : '', 'data-var': n },
        h('button', { type: 'button', title: '차트로 본다', 'data-col': n, onclick: () => { st.col = st.col === n ? null : n; drawResult(); } }, n))))), h('tbody', {}, rows))),
        h('div', { class: 'fc-legend' }, st.mode === 'diff' ? h('span', {}, '기준선 대비 차이(%), 그 아래는 수준의 차이') : [h('span', { class: 'key f-act' }, '실측'), h('span', { class: 'key f-sol' }, '해'), h('span', { class: 'key f-asm' }, '가정'), h('span', { class: 'key f-fill' }, '채움')],
          h('span', { class: 'grow' }), h('span', {}, '열 이름을 누르면 차트')));
    }
    if (st.col && v.level[st.col]) {
      const box = h('div', { class: 'pad-chart' });
      resultBox.append(h('div', { class: 'var-detail' }, h('div', { class: 'raw-cap' }, h('b', { class: 'mono' }, st.col), h('span', { class: 'muted' }, ' — 실측에 이어 전망'), h('span', { class: 'grow' }),
        h('button', { class: 'icon-btn', type: 'button', title: '닫기', 'aria-label': '닫기', onclick: () => { st.col = null; drawResult(); } }, icon('x'))), box));
      const level = v.level[st.col];
      const same = others.filter((x) => x.period.join() === v.period.join());
      requestAnimationFrame(() => {
        disposeChart = drawLines(box, { period: v.period, height: 190, title: st.col, lines: [
          { label: '실측', values: level.map((x, i) => (i < start ? x : null)), color: 'var(--c-actual)', width: 1.5 },
          { label: short(v.id), values: level.map((x, i) => (i >= start - 1 ? x : null)), color: 'var(--c-fitted)', dashed: true, width: 1.7 },
          ...same.map((x, i) => ({ label: short(x.id), values: x.level[st.col]?.map((y, j) => (j >= start - 1 ? y : null)) || [], color: i ? 'var(--k-hs)' : 'var(--c-resid)', dashed: true, width: 1.4 }))] });
      });
    }
  }

  async function saveView() {
    const name = h('input', { class: 'mini-input wide', type: 'text', placeholder: '영문 이름 — 예: core', spellcheck: 'false', 'aria-label': '보기 이름' });
    const title = h('input', { class: 'mini-input wide plain', type: 'text', placeholder: '제목 — 예: 핵심 지표', 'aria-label': '제목' });
    const body = h('div', { class: 'adopt define-form' }, h('p', {}, '지금 고른 시리즈와 모양을 이름으로 적어 둡니다(VIEWS/이름.toml) — 다음 결과에도 같은 표를 다시 봅니다.'),
      h('div', { class: 'diff' }, h('span', { class: 'dl add' }, `series = [${st.series.map((s) => `"${s}"`).join(', ')}]`), h('span', { class: 'dl add' }, `show = "${st.mode}"`)),
      h('label', { class: 'field-row' }, h('span', {}, '이름'), name), h('label', { class: 'field-row' }, h('span', {}, '제목'), title));
    if (!(await confirmDialog({ title: '이 보기 저장', body, confirm: '저장', wide: true, valid: () => nameRule(name.value, { what: '보기 이름' }), enter: true }))) return;
    try {
      const res = await project.compute('view/define', { name: name.value.trim(), series: st.series, show: st.mode, title: title.value.trim() }, { quiet: true });
      flash(`${res.result.file} 를 저장했습니다`);
      st.info.views = (await project.get('views')).views;
      drawResult();
    } catch (err) {
      if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    }
  }

  /** 다시 그린다 — 치던 칸(가리키던 곳·고른 글자)과 스크롤 자리는 지킨다(밖에서 파일이 바뀌어 다시 읽어도 치던 흐름이 끊기지 않게) */
  function render() {
    const focus = document.activeElement;
    const at = focus instanceof HTMLInputElement && el.contains(focus) && focus.dataset.cell ? [focus.dataset.cell, focus.selectionStart, focus.selectionEnd] : null;
    const top = el.parentElement?.scrollTop;
    draw();
    if (at) {
      const cell = el.querySelector(`[data-cell="${CSS.escape(at[0])}"]`);
      if (cell) { cell.focus({ preventScroll: true }); try { cell.setSelectionRange(at[1], at[2]); } catch { /* 고를 수 없는 칸 */ } }
    }
    if (top != null && el.parentElement) el.parentElement.scrollTop = top;
  }

  function draw() {
    clear(el);
    const info = st.info;
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, '전망'), h('div', { class: 'sub' }, '가정을 적고, 기준선과 시나리오를 풉니다. 가정을 고쳐도 저절로 다시 풀지 않습니다.')),
      info ? h('div', { class: 'tools' },
        h('button', { class: 'btn quiet', type: 'button', 'data-act': 'scenarios', title: '시나리오 — 충격 표로 만들고 고친다(SCENARIOS/*.toml)', onclick: (e) => popMenu(e.currentTarget, [h('div', { class: 'menu-title' }, '시나리오'),
          ...info.scenarios.map((s) => ({ label: s.name, hint: s.desc || s.file, onPick: () => project.openTab({ type: 'scenario', name: s.name }) })),
          { label: '새 시나리오…', hint: '충격 표로', onPick: () => project.openTab({ type: 'scenario' }) }], { cls: 'plain', align: 'right' }) }, icon('layers'), '시나리오', icon('chevron', 'down')),
        h('button', { class: 'btn quiet', type: 'button', onclick: () => project.openTab({ type: 'reports' }) }, icon('doc'), '보고서'),
        claudeButton(project, () => ({ name: st.shown || `모형 ${st.model} 의 전망`, summary: st.view && st.shown ? `${st.view.meta.scenario === 'base' ? '기준선' : `시나리오 ${st.view.meta.scenario}`} ${st.view.meta.range?.join('~') || ''}` : '' }))) : null));
    if (st.error) el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', { class: 'grow' }, st.error)));
    if (!info) { if (!st.error) el.append(h('div', { class: 'empty-state' }, '전망을 읽는 중…')); return; }
    if (!info.model) { el.append(h('div', { class: 'empty-state' }, '모형이 없습니다.')); return; }
    put(el, runRow(), info.range ? assumeBox() : null, info.range ? addfactorBox() : null, resultBox);
    drawResult();
  }

  render();
  return {
    key: 'forecast', type: 'forecast', title: '전망', icon: 'forward', el,
    desc: () => ({ type: 'forecast', model: st.model, scenarios: [...st.picks], start: st.start, end: st.end, shown: st.shown, mode: st.mode, series: st.series, ...(st.open == null ? {} : { open: st.open }) }),
    /** 탭을 닫기 전에 묻는 글 — 저장하지 않은 가정 칸이 있을 때(가정 표는 탭과 함께 기억하지 않는다) */
    unsaved: () => (st.dirty && st.info?.assume ? `가정 표(${st.info.assume.file})에 저장하지 않은 칸이 있습니다 — 닫으면 그 칸들을 버립니다.` : null),
    show() { if (!loaded) load(); },
    open(next) {
      if (next.model && next.model !== st.model) { Object.assign(st, { model: next.model, shown: next.shown || null, view: null, series: null, open: null, col: null }); st.compare.clear(); if (loaded) load(); return; }
      if (Array.isArray(next.scenarios) && next.scenarios.length) st.picks = new Set(next.scenarios);      // 시나리오 폼의 '저장하고 풀기'
      if (Array.isArray(next.compare)) st.pending = next.compare;
      if (next.shown) { if (loaded) { if (next.scenarios) load().then(() => showRecord(next.shown)); else showRecord(next.shown).then(pairPending); } else st.shown = next.shown; }
    },
    event(e) {
      if ((e.type === 'record' && e.record?.kind === 'sim') || e.type === 'defs') { if (loaded && !project.busy) load(); else if (loaded) st.stale = true; }
      else if (e.type === 'job') {
        const b = el.querySelector('[data-act="solve"]');
        if (b) b.disabled = project.busy || !!st.error;
        if (!project.busy && loaded && st.stale) { st.stale = false; load(); }
      }
    },
    dispose() { disposeChart(); },
  };
}
