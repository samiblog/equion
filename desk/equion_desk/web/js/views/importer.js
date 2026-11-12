// 불러오기(W4 의 둘째 걸음) — 원자료의 어느 열을 어떤 이름의 시리즈로 읽을지 정한다.
//
//   ① 파일      DATA/raw/ 의 파일 하나(이미 어느 출처가 읽고 있으면 그 틀과 시리즈를 고친다, 아니면 새 출처)
//   ② 틀        어느 줄이 열 이름인가 · 단위 줄 · 시점 열 · 결측으로 볼 글자 · 천 단위 — '읽은 그대로'의 표를 보며 맞춘다
//   ③ 시리즈    열마다 이름·단위·설명·변환(주기 변환·계절조정) — 고른 열만 시리즈가 된다
//   ④ 저장      무엇이 series.toml 에 적히는지(차이)를 보이고 나서 — `equion data define` 과 같은 일
//
// 원자료는 고치지 않는다. 여기서 정하는 것은 '읽는 법'(정의)뿐이고, 저장해도 자료는 생기지 않는다 — 자료 작업대의 '자료 만들기'가 만든다.
// 미리보기(표·차트)는 기록을 남기지 않는다. 화면이 TOML 을 직접 쓰지 않는다 — 검사와 쓰기는 패키지가 한다(주석·순서를 지킨다).
// 쓰던 짝짓기는 탭과 함께 기억한다(닫았다 열어도 이어진다).

import { drawLines } from '../chart.js';
import { confirmDialog } from '../dialog.js';
import { clear, debounce, flash, h, icon, put } from '../util.js';
import { diffBlock } from './lists.js';

const NAME = /^[A-Za-z][A-Za-z0-9_]*$/;
const FREQ = { A: '연', Q: '분기', M: '월' };
const PER_YEAR = { A: 1, Q: 4, M: 12 };
const DOWN = [['', '고르세요'], ['mean', '평균'], ['sum', '합'], ['last', '끝값'], ['first', '첫값'], ['max', '최대'], ['min', '최소']];
const UP = [['', '고르세요'], ['constant', '같은 값'], ['split', '고르게 나눔'], ['linear', '선형'], ['denton', 'Denton']];
const SEAS = [['', '안 함'], ['stl', 'STL 가법'], ['stl:multiplicative', 'STL 승법'], ['classical', '고전 분해 가법'], ['classical:multiplicative', '고전 분해 승법']];
const letter = (k) => { let s = ''; for (let n = k + 1; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s; return s; };
const FILL = [['', '안 함'], ['linear', '선형으로']];
const EMPTY_FRAME = { sheet: '', header_row: 1, unit_row: '', time_col: '', missing: [], thousands: '', freq: '', time_axis: '', time_row: '', name_col: '', unit_col: '' };
/** 열 글자(A) → 자리(0부터) */
const colIndex = (s) => (/^[A-Za-z]+$/.test(String(s)) ? [...String(s).toUpperCase()].reduce((a, ch) => a * 26 + ch.charCodeAt(0) - 64, 0) - 1 : (/^\d+$/.test(String(s)) ? Number(s) - 1 : -1));
/** 머리줄 값(3 · [3, 4] · "3,4") → 줄 자리(0부터)들 */
const headerRows = (v) => {
  if (Array.isArray(v)) return v.map((x) => Number(x) - 1);
  const text = String(v ?? '').trim() || '1';
  const range = /^(\d+)\s*[-:~]\s*(\d+)$/.exec(text);
  if (range) { const a = Number(range[1]); const b = Number(range[2]); return Array.from({ length: Math.abs(b - a) + 1 }, (_, i) => Math.min(a, b) + i - 1); }
  return text.split(/[,\s]+/).filter(Boolean).map((x) => Number(x) - 1);
};

export function importView(project, desc) {
  const el = h('div', { class: 'view importer' });
  const st = {
    file: desc.file || null, source: desc.source || '', frame: desc.frame || null, picks: desc.picks || {},
    view: null, error: null, loading: false, shown: null, chart: null, chartError: null, saved: null, turn: 0,
  };
  let disposeChart = () => {};
  let loaded = false;
  const save = () => project.saveView();

  const files = () => {
    const d = project.dataInfo;
    return d ? d.raw.map((f) => ({ file: f.file, source: f.source })) : [];
  };
  const existing = () => st.view?.source?.name || null;
  const frame = () => ({ ...EMPTY_FRAME, ...(st.frame || {}) });

  /** 파일 이름에서 출처 이름을 짓는다(영문·숫자·_ 만) */
  function suggestSource(file) {
    const stem = file.split('/').pop().replace(/\.[^.]+$/, '').replace(/[^A-Za-z0-9_]+/g, '_').replace(/^_+|_+$/g, '').toLowerCase();
    const taken = new Set((st.view?.sources || []).map((s) => s.name.toLowerCase()));
    let name = /^[a-z]/.test(stem) ? stem : `src_${stem}`.replace(/_$/, '');
    if (!NAME.test(name)) name = 'src';
    for (let n = 2; taken.has(name.toLowerCase()); n++) name = `${name.replace(/_\d+$/, '')}_${n}`;
    return name;
  }

  /** 읽은 열마다 짝짓기의 첫 모습 — 이미 정의에 있으면 그것, 없으면 열 이름에서 */
  function seedPicks() {
    const v = st.view;
    if (!v?.ok) return;
    const taken = new Set(v.taken.map((n) => n.toUpperCase()));
    const next = {};
    for (const c of v.columns) {
      const had = v.mapped[c.name];
      const old = st.picks[c.name];
      if (had) next[c.name] = { on: true, fixed: true, name: had.name, unit: old?.unit ?? had.unit ?? '', desc: old?.desc ?? had.desc ?? '', convert: old?.convert ?? had.convert ?? '', seas: old?.seas ?? had.seas ?? '', fill: old?.fill ?? had.fill ?? '' };
      else if (old) next[c.name] = { ...old, fixed: false };
      else next[c.name] = { on: false, fixed: false, name: c.name_ok && !taken.has(c.name.toUpperCase()) ? c.name : '', unit: c.unit || '', desc: c.name_ok ? '' : c.name, convert: '', seas: '', fill: '' };
    }
    st.picks = next;
  }

  async function load({ keepFrame = true } = {}) {
    loaded = true;
    if (!project.dataInfo) await project.loadData();
    if (!st.file) { render(); return; }
    const turn = ++st.turn;
    st.loading = true;
    try {
      const view = await project.post('data/preview', { file: st.file, rows: 60, ...(keepFrame && st.frame ? { frame: st.frame } : {}) });
      if (turn !== st.turn) return;
      st.view = view;
      st.error = null;
      st.frame = { ...EMPTY_FRAME, ...Object.fromEntries(Object.entries(view.frame).map(([k, val]) => [k, val ?? (k === 'missing' ? [] : '')])) };
      if (!view.source && !st.source) st.source = suggestSource(st.file);
      if (view.source) st.source = view.source.name;
      seedPicks();
    } catch (err) {
      if (turn !== st.turn) return;
      st.view = null;
      st.error = err.message;
    }
    st.loading = false;
    render();
    save();
  }
  const reload = debounce(() => load(), 250);

  function choose(file) {
    Object.assign(st, { file, source: '', frame: null, picks: {}, view: null, shown: null, chart: null, chartError: null, saved: null, error: null });
    load({ keepFrame: false });
  }

  function setFrame(key, value) {
    st.frame = { ...frame(), [key]: value };
    st.shown = null; st.chart = null;
    reload();
  }

  /** 지금 고른 것을 정의 쓰기의 꼴로 — 새 시리즈는 모든 키, 있는 시리즈는 고친 키만 */
  function payload() {
    const v = st.view;
    const series = {};
    const problems = [];
    const names = new Set(v.taken.map((n) => n.toUpperCase()));
    const differs = v.freq !== v.project_freq;
    for (const c of v.columns) {
      const p = st.picks[c.name];
      if (!p?.on) continue;
      const had = v.mapped[c.name];
      if (had) {
        const changed = {};
        for (const key of ['unit', 'desc', 'convert', 'seas', 'fill']) if ((p[key] || '') !== (had[key] || '')) changed[key] = p[key] || '';
        if (Object.keys(changed).length) series[had.name] = { column: c.name, ...changed };
        continue;
      }
      const name = (p.name || '').trim();
      if (!NAME.test(name)) { problems.push(`${c.name}: 시리즈 이름은 영문으로 시작하고 영문·숫자·_ 만 씁니다`); continue; }
      if (names.has(name.toUpperCase())) { problems.push(`${c.name}: ${name} 은(는) 이미 있는 이름입니다`); continue; }
      if (differs && !p.convert) { problems.push(`${c.name}: 주기가 달라 변환을 골라야 합니다`); continue; }
      names.add(name.toUpperCase());
      series[name] = { column: c.name, ...(p.unit ? { unit: p.unit } : {}), ...(p.desc ? { desc: p.desc } : {}), ...(p.convert ? { convert: p.convert } : {}), ...(p.fill ? { fill: p.fill } : {}), ...(p.seas ? { seas: p.seas } : {}) };
    }
    return { series, problems };
  }

  async function store() {
    const v = st.view;
    if (!v?.ok) return;
    const source = st.source.trim();
    if (!NAME.test(source)) { flash('출처 이름은 영문으로 시작하고 영문·숫자·_ 만 씁니다'); el.querySelector('[data-field="source"]')?.focus(); return; }
    const { series, problems } = payload();
    if (problems.length) { st.error = problems.join('\n'); render(); return; }
    if (!existing() && !Object.keys(series).length) { flash('시리즈로 읽을 열을 하나 이상 고르세요'); return; }
    const body = { source, file: st.file, frame: frame(), series };
    let plan;
    try { plan = await project.post('data/define', { ...body, dry: true }); } catch (err) { st.error = err.message; render(); return; }
    st.error = null;
    if (plan.same) { flash('바뀐 것이 없습니다'); render(); return; }
    const bits = [plan.new_source ? `새 출처 ${plan.source}` : `출처 ${plan.source}`, plan.added.length ? `새 시리즈 ${plan.added.join(' · ')}` : null,
      plan.changed.length ? `고치는 시리즈 ${plan.changed.join(' · ')}` : null].filter(Boolean);
    const dialog = h('div', { class: 'adopt' },
      h('p', {}, bits.join(' — '), '. 원자료는 그대로이고, 값은 여기서 만들지 않습니다 — 저장한 뒤 자료 작업대의 ‘자료 만들기’가 새 회차를 만듭니다.'),
      h('h4', {}, '바뀌는 파일 ', h('span', { class: 'mono' }, plan.path)), diffBlock(plan.diff),
      h('h4', {}, '같은 일을 하는 명령'), h('div', { class: 'readonly-eq compact' }, plan.command),
      h('p', { class: 'muted' }, '사람이 쓴 주석과 순서는 그대로 둡니다. 바뀜 기록에 남고, 거기서 되돌릴 수 있습니다.'));
    if (!(await confirmDialog({ title: '정의에 저장', body: dialog, confirm: '정의에 저장', wide: true }))) return;
    try {
      const res = await project.compute('data/define', body, { quiet: true });
      st.saved = res.result;
      st.picks = {};
      await project.loadData();
      await load();
    } catch (err) {
      if (err.kind !== 'busy') { st.error = err.message; render(); }
    }
  }

  async function tryColumn(column) {
    const p = st.picks[column];
    st.shown = column;
    st.chart = null;
    st.chartError = null;
    renderChart();
    try {
      const view = await project.post('data/preview', { file: st.file, rows: 1, frame: frame(), series: { column, ...(p.convert ? { convert: p.convert } : {}), ...(p.seas ? { seas: p.seas } : {}), ...(p.fill ? { fill: p.fill } : {}) } });
      if (st.shown !== column) return;
      st.chart = view.series;
      st.chartError = view.series_error;
    } catch (err) {
      if (st.shown !== column) return;
      st.chartError = err.message;
    }
    renderChart();
  }

  // ---- 그리기 -----------------------------------------------------------------------------------

  function fileRow() {
    const list = files();
    const select = h('select', { class: 'an-select', 'aria-label': '원자료 파일' }, st.file && !list.some((f) => f.file === st.file) ? h('option', { value: st.file }, st.file.split('/').pop()) : null,
      !st.file ? h('option', { value: '' }, '파일을 고르세요') : null,
      list.map((f) => h('option', { value: f.file }, `${f.file.split('/').pop()}${f.source ? `  ·  ${f.source} 가 읽음` : ''}`)));
    select.value = st.file || '';
    select.addEventListener('change', () => { if (select.value) choose(select.value); });
    const src = h('input', { class: 'an-target', type: 'text', value: st.source, spellcheck: 'false', 'data-field': 'source', 'aria-label': '출처 이름', placeholder: '영문 이름 — 예: na' });
    src.addEventListener('input', () => { st.source = src.value; save(); });
    return h('div', { class: 'an-top' },
      h('label', { class: 'an-field grow' }, h('span', {}, '① 파일', h('small', {}, ' — DATA/raw/ 의 원자료')), select),
      existing() ? h('div', { class: 'an-field' }, h('span', {}, '출처'), h('div', { class: 'src-fixed' }, h('b', { class: 'mono' }, existing()), h('span', { class: 'muted' }, '가 이 파일을 읽습니다 — 틀과 시리즈를 고칩니다')))
        : st.file ? h('label', { class: 'an-field' }, h('span', {}, '출처 이름', h('small', {}, ' — 새 출처')), src) : null);
  }

  function frameRow() {
    const v = st.view;
    const f = frame();
    const cols = f.time_axis === 'columns';
    const width = v ? Math.max(0, ...v.grid.map((r) => r.length)) : 0;
    const head = v?.grid[headerRows(f.header_row)[0]] || [];
    const num = (key, title, placeholder) => {
      const input = h('input', { class: 'mini-input num', type: 'number', min: '1', value: f[key] === '' || f[key] == null ? '' : String(f[key]), placeholder, 'data-frame': key, title });
      input.addEventListener('input', () => setFrame(key, input.value === '' ? '' : Math.max(1, parseInt(input.value, 10) || 1)));
      return input;
    };
    const pick = (key, options, title) => {
      const select = h('select', { class: 'mini-select', 'data-frame': key, title }, options.map(([value, label]) => h('option', { value }, label)));
      const now = String(f[key] ?? '');
      if (now && !options.some(([value]) => String(value) === now)) select.append(h('option', { value: now }, now));       // 손으로 적은 값(열 이름·번호)도 그대로 보인다
      select.value = now;
      select.addEventListener('change', () => setFrame(key, /^\d+$/.test(select.value) && key === 'sheet' ? Number(select.value) : select.value));
      return select;
    };
    const miss = h('input', { class: 'mini-input text', type: 'text', value: (f.missing || []).join(' '), placeholder: '예: - … x', spellcheck: 'false', 'data-frame': 'missing',
      title: '결측으로 볼 글자 — 빈칸으로 띄워 여럿. 빈 칸은 늘 결측입니다' });
    miss.addEventListener('input', () => setFrame('missing', miss.value.split(/\s+/).filter(Boolean).slice(0, 12)));
    const hdrText = h('input', { class: 'mini-input text', type: 'text', value: Array.isArray(f.header_row) ? f.header_row.join(',') : String(f.header_row ?? ''), placeholder: '1', spellcheck: 'false', 'data-frame': 'header_row',
      title: '열 이름이 있는 줄 — 여러 줄이면 3,4(위 줄의 병합 칸은 이어 붙여 ‘국내총생산 실질’ 꼴). 표의 줄 번호를 눌러도 됩니다(Shift: 더하기)' });
    hdrText.addEventListener('input', () => { const t = hdrText.value.trim(); if (!t || /^\d+(\s*[,\-:~]\s*\d+)*$/.test(t)) setFrame('header_row', /^\d+$/.test(t) ? Number(t) : t); });
    const colPick = (key, title, none) => pick(key, [['', none], ...Array.from({ length: width }, (_, k) => [letter(k), `${letter(k)}${v?.grid.some((r) => r[k]) ? ` · ${(v.grid.find((r) => r[k]) || [])[k] || ''}`.slice(0, 22) : ''}`])], title);
    return h('div', { class: 'eq-opts an-opts frame-row' }, h('span', { class: 'lead' }, '② 틀'),
      v?.sheets?.length ? h('label', { class: 'opt' }, h('span', {}, '시트'), pick('sheet', [['', v.sheets[0]], ...v.sheets.slice(1).map((s) => [s, s])], '엑셀의 시트')) : null,
      h('label', { class: 'opt' }, h('span', {}, '시점'), pick('time_axis', [['', '행으로 내려감'], ['columns', '열로 감']], '시점이 아래로 내려가는 표(보통) · 오른쪽으로 가는 표(줄마다 시리즈 하나인 통계표)')),
      cols ? [
        h('label', { class: 'opt' }, h('span', {}, '시점 줄'), num('time_row', '시점(2003Q4 · 2018 1/4 …)이 적힌 줄 — 표의 줄 번호를 눌러도 됩니다', '1')),
        h('label', { class: 'opt' }, h('span', {}, '이름 열'), colPick('name_col', '시리즈 이름이 있는 열', '첫 열(A)')),
        h('label', { class: 'opt' }, h('span', {}, '단위 열'), colPick('unit_col', '단위가 적힌 열 — 없으면 비워 둡니다', '없음')),
      ] : [
        h('label', { class: 'opt' }, h('span', {}, '열 이름 줄'), hdrText),
        h('label', { class: 'opt' }, h('span', {}, '단위 줄'), num('unit_row', '단위가 적힌 줄 — 없으면 비워 둡니다', '없음')),
        h('label', { class: 'opt' }, h('span', {}, '시점 열'), pick('time_col', [['', '첫 열(A)'], ...Array.from({ length: width }, (_, k) => [letter(k), `${letter(k)}${head[k] ? ` · ${head[k]}` : ''}`]).slice(1)], '시점(2003Q4·2003-10·2003년 4분기…)이 적힌 열')),
      ],
      h('label', { class: 'opt' }, h('span', {}, '결측 표시'), miss),
      h('label', { class: 'opt' }, h('span', {}, '천 단위'), pick('thousands', [['', '없음'], [',', '쉼표 1,234']], '숫자의 천 단위 구분 글자')),
      h('label', { class: 'opt' }, h('span', {}, '주기'), pick('freq', [['', '시점에서 읽기'], ['Q', '분기'], ['M', '월'], ['A', '연']], '원자료의 주기 — 보통은 시점 꼴에서 읽습니다')));
  }

  /** 읽은 그대로의 줄에서 틀을 짐작한다 — 권하기만 하고(단추), 고르는 것은 사람이다 */
  function hints() {
    const v = st.view;
    const f = frame();
    const out = [];
    const filled = (row) => row.filter((c) => c !== '').length;
    const width = Math.max(0, ...v.grid.map((r) => r.length));
    const hdrNow = headerRows(f.header_row)[0] + 1;
    if (!v.ok && f.time_axis !== 'columns') {
      // 줄마다 첫 칸이 글이고 위쪽 한 줄에 시점 꼴이 줄지어 있으면 — 시점이 열로 가는 표로 보인다
      const timeLike = (c) => /^\d{4}\s*([.\-/ ]?\s*([Qq]?[1-4](\s*\/\s*4)?|[Mm]?\d{1,2})|년.*)?$/.test(c.trim());
      const across = v.grid.findIndex((row) => row.filter((c) => c && timeLike(c)).length >= 3);
      if (across >= 0 && v.grid.slice(across + 1).some((row) => row[0] && !timeLike(row[0]))) {
        out.push([`시점이 ${across + 1}줄에서 열로 가는 표로 읽기`, () => { st.frame = { ...frame(), time_axis: 'columns', time_row: across + 1 }; reload(); }]);
      }
    }
    if (!v.ok) {
      const guess = v.grid.findIndex((row) => filled(row) >= Math.max(2, Math.ceil(width / 2))) + 1;
      if (guess && guess !== hdrNow) out.push([`${guess}줄을 열 이름 줄로`, () => setFrame('header_row', guess)]);
      const below = v.grid[hdrNow];          // 열 이름 줄 바로 아래 — 시점 칸이 비고 숫자가 없으면 단위 줄로 보인다
      if (!f.unit_row && below && below[0] === '' && filled(below) && !below.some((c) => /\d/.test(c))) out.push([`${hdrNow + 1}줄을 단위 줄로`, () => setFrame('unit_row', hdrNow + 1)]);
      return out;
    }
    const texts = v.bad_cells.map((c) => (/^[A-Z]+\d+ '(.*)'$/.exec(c) || [])[1]).filter((x) => x != null);
    if (!f.thousands && texts.some((x) => /\d,\d{3}/.test(x))) out.push(['쉼표를 천 단위로 읽기', () => setFrame('thousands', ',')]);
    const marks = [...new Set(texts.filter((x) => x.length <= 4 && !/\d/.test(x)))].slice(0, 3);
    if (marks.length) out.push([`${marks.map((m) => `‘${m}’`).join(' ')} 을(를) 결측 표시로`, () => setFrame('missing', [...new Set([...(f.missing || []), ...marks])])]);
    return out;
  }

  function readLine() {
    const v = st.view;
    if (st.loading && !v) return h('div', { class: 'empty-state' }, '파일을 읽는 중…');
    if (!v) return null;
    const tips = hints().map(([label, fn]) => h('button', { class: 'btn small', type: 'button', 'data-hint': '', onclick: fn }, label));
    if (!v.ok) {
      return h('div', { class: 'banner error' }, icon('alert'), h('div', {}, h('b', {}, '이 틀로는 읽지 못했습니다'), ` — ${v.error}`, h('br'),
        tips.length ? '이렇게 해 보세요: ' : '표에서 열 이름이 있는 줄의 번호를 누르거나, 위의 틀을 맞춰 보세요.', tips.length ? h('span', { class: 'tips' }, tips) : null));
    }
    const differs = v.freq !== v.project_freq;
    return h('div', { class: `banner ${v.bad_cells.length ? 'warn' : differs ? 'info' : 'ok'}` }, icon(v.bad_cells.length ? 'alert' : differs ? 'info' : 'check'),
      h('div', {}, h('b', {}, '읽은 것'), ` — ${v.note} · ${v.shape[0]}줄 · 값이 있는 열 ${v.columns.length}개`,
        v.missing_cells.length ? ` · 결측 표시로 읽은 칸 ${v.missing_cells.length}` : '',
        v.bad_cells.length ? h('span', { title: v.bad_cells.slice(0, 12).join('\n') }, ` · 숫자가 아닌 칸 ${v.bad_cells.length}개는 결측으로 봅니다(예: ${v.bad_cells.slice(0, 2).join(' · ')})`) : '',
        tips.length ? h('div', { class: 'tips' }, tips) : null,
        differs ? h('div', {}, `원자료는 ${FREQ[v.freq]} 자료이고 프로젝트는 ${FREQ[v.project_freq]} 자료입니다 — 시리즈마다 주기 변환을 고릅니다.`) : null));
  }

  function grid() {
    const v = st.view;
    if (!v?.grid.length) return null;
    const f = frame();
    if (f.time_axis === 'columns') return gridColumns();
    const hdrs = headerRows(f.header_row);
    const hdr = Math.max(...hdrs);
    const unit = f.unit_row ? Number(f.unit_row) - 1 : -1;
    const tcol = v.ok ? v.time_col : (/^[A-Za-z]+$/.test(String(f.time_col)) ? [...String(f.time_col).toUpperCase()].reduce((a, ch) => a * 26 + ch.charCodeAt(0) - 64, 0) - 1 : 0);
    const marks = new Set(f.missing || []);
    const width = Math.max(...v.grid.map((r) => r.length));
    const picked = new Set(v.ok ? v.columns.filter((c) => st.picks[c.name]?.on).map((c) => c.col) : []);
    const byCol = new Map(v.ok ? v.columns.map((c) => [c.col, c]) : []);
    return h('div', { class: 'raw-wrap' }, h('div', { class: 'raw-cap' }, h('b', {}, '읽은 그대로'), h('span', { class: 'muted' }, ` — 앞 ${v.grid.length}줄(모두 ${v.shape[0]}줄). 줄 번호를 누르면 그 줄이 열 이름 줄이 됩니다.`),
      h('span', { class: 'grow' }), h('span', { class: 'key hdr' }, '열 이름'), unit >= 0 ? h('span', { class: 'key unit' }, '단위') : null, h('span', { class: 'key time' }, '시점'), marks.size ? h('span', { class: 'key miss' }, '결측 표시') : null),
    h('div', { class: 'raw-scroll', tabindex: '0' }, h('table', { class: 'raw-grid' },
      h('thead', {}, h('tr', {}, h('th', {}, ''), Array.from({ length: width }, (_, k) => {
        const c = byCol.get(k);
        return h('th', { class: `${k === tcol ? 'time' : ''} ${picked.has(k) ? 'picked' : ''}`.trim() },
          c ? h('button', { type: 'button', title: `${c.name} — 누르면 시리즈로 ${picked.has(k) ? '읽지 않습니다' : '읽습니다'}`, onclick: () => toggle(c.name) }, letter(k)) : letter(k));
      }))),
      h('tbody', {}, v.grid.map((row, r) => h('tr', { class: hdrs.includes(r) ? 'hdr' : r === unit ? 'unit' : r < hdr ? 'above' : '' },
        h('th', {}, h('button', { type: 'button', title: `${r + 1}줄을 열 이름 줄로 — Shift 를 누르고 누르면 머리줄에 더한다`,
          onclick: (e) => setFrame('header_row', e.shiftKey ? [...new Set([...hdrs, r])].sort((a, b) => a - b).map((x) => x + 1).join(',') : r + 1) }, r + 1)),
        Array.from({ length: width }, (_, k) => {
          const text = row[k] ?? '';
          const cls = [k === tcol ? 'time' : '', picked.has(k) ? 'picked' : '', r > hdr && r !== unit && k !== tcol && text && marks.has(text.trim()) ? 'miss' : ''].filter(Boolean).join(' ');
          return h('td', { class: cls, title: text.length > 14 ? text : null }, text);
        })))))));
  }

  /** 시점이 열로 가는 표 — 시점 줄 · 이름 열 · 단위 열과 고른 시리즈(줄)를 표시 */
  function gridColumns() {
    const v = st.view;
    const f = frame();
    const trow = v.ok && v.time_row != null ? v.time_row : (Number(f.time_row) || 1) - 1;
    const ncol = colIndex(f.name_col || 'A');
    const ucol = f.unit_col ? colIndex(f.unit_col) : -1;
    const marks = new Set(f.missing || []);
    const width = Math.max(...v.grid.map((r) => r.length));
    const byRow = new Map(v.ok ? v.columns.map((c) => [c.col, c]) : []);
    const picked = new Set(v.ok ? v.columns.filter((c) => st.picks[c.name]?.on).map((c) => c.col) : []);
    return h('div', { class: 'raw-wrap' }, h('div', { class: 'raw-cap' }, h('b', {}, '읽은 그대로'), h('span', { class: 'muted' }, ` — 앞 ${v.grid.length}줄(모두 ${v.shape[0]}줄). 줄 번호를 누르면 그 줄이 시점 줄이 됩니다 · 줄마다 시리즈 하나.`),
      h('span', { class: 'grow' }), h('span', { class: 'key time' }, '시점 줄'), h('span', { class: 'key hdr' }, '이름 열'), ucol >= 0 ? h('span', { class: 'key unit' }, '단위 열') : null, marks.size ? h('span', { class: 'key miss' }, '결측 표시') : null),
    h('div', { class: 'raw-scroll', tabindex: '0' }, h('table', { class: 'raw-grid by-row' },
      h('thead', {}, h('tr', {}, h('th', {}, ''), Array.from({ length: width }, (_, k) => h('th', { class: k === ncol ? 'name-col' : k === ucol ? 'unit-col' : '' },
        h('button', { type: 'button', title: `${letter(k)}열을 이름 열로`, onclick: () => setFrame('name_col', letter(k)) }, letter(k)))))),
      h('tbody', {}, v.grid.map((row, r) => {
        const c = byRow.get(r);
        return h('tr', { class: `${r === trow ? 'time-row' : ''} ${picked.has(r) ? 'picked' : ''} ${r < trow ? 'above' : ''}`.replace(/\s+/g, ' ').trim() },
          h('th', {}, c ? h('button', { type: 'button', title: `${c.name} — 누르면 시리즈로 ${picked.has(r) ? '읽지 않습니다' : '읽습니다'}`, onclick: () => toggle(c.name) }, r + 1)
            : h('button', { type: 'button', title: `${r + 1}줄을 시점 줄로`, onclick: () => setFrame('time_row', r + 1) }, r + 1)),
          Array.from({ length: width }, (_, k) => {
            const text = row[k] ?? '';
            const cls = [k === ncol ? 'name-col' : '', k === ucol ? 'unit-col' : '', r > trow && k !== ncol && k !== ucol && text && marks.has(text.trim()) ? 'miss' : ''].filter(Boolean).join(' ');
            return h('td', { class: cls, title: text.length > 14 ? text : null }, text);
          }));
      })))));
  }

  function toggle(column) {
    const p = st.picks[column];
    if (!p || p.fixed) return;
    p.on = !p.on;
    render();
    save();
  }

  function seriesTable() {
    const v = st.view;
    if (!v?.ok) return null;
    const differs = v.freq !== v.project_freq;
    const conv = PER_YEAR[v.freq] > PER_YEAR[v.project_freq] ? DOWN : UP;
    const seasonal = v.project_freq !== 'A';
    const taken = new Set(v.taken.map((n) => n.toUpperCase()));
    const on = v.columns.filter((c) => st.picks[c.name]?.on && !st.picks[c.name].fixed).length;
    const all = v.columns.filter((c) => !st.picks[c.name]?.fixed);
    const text = (c, key, cls, placeholder, extra = {}) => {
      const p = st.picks[c.name];
      const input = h('input', { class: `mini-input ${cls}`, type: 'text', value: p[key] || '', placeholder, spellcheck: 'false', disabled: !p.on || (key === 'name' && p.fixed), 'data-col': c.name, 'data-key': key, ...extra });
      input.addEventListener('input', () => {
        p[key] = input.value;
        if (key === 'name') { const bad = input.value && (!NAME.test(input.value.trim()) || taken.has(input.value.trim().toUpperCase())); input.classList.toggle('bad', !!bad); input.title = bad ? (NAME.test(input.value.trim()) ? '이미 있는 이름입니다' : '영문으로 시작하고 영문·숫자·_ 만 씁니다 — 한글 이름은 설명에') : ''; }
        save();
      });
      return input;
    };
    const choice = (c, key, options, title) => {
      const p = st.picks[c.name];
      const select = h('select', { class: 'mini-select', disabled: !p.on, title, 'data-col': c.name, 'data-key': key }, options.map(([value, label]) => h('option', { value }, label)));
      select.value = p[key] || '';
      select.addEventListener('change', () => { p[key] = select.value; save(); if (st.shown === c.name) tryColumn(c.name); });
      return select;
    };
    return h('div', {},
      h('div', { class: 'list-tools' }, h('b', {}, '③ 시리즈'), h('span', { class: 'muted' }, '— 고른 열만 시리즈가 됩니다. 이름은 영문(식에 쓰는 이름), 한글 이름은 설명에 적습니다.'), h('span', { class: 'grow' }),
        all.length > 1 ? h('button', { class: 'btn small quiet', type: 'button', onclick: () => { const to = on < all.length; for (const c of all) st.picks[c.name].on = to; render(); save(); } }, on < all.length ? '모두 고르기' : '모두 빼기') : null),
      h('div', { class: 'pick-list' }, v.columns.map((c) => {
        const p = st.picks[c.name];
        const box = h('input', { type: 'checkbox', disabled: p.fixed, 'aria-label': `${c.name} 을(를) 시리즈로 읽기`, 'data-col': c.name, 'data-key': 'on',
          title: p.fixed ? '이미 정의에 있는 시리즈입니다 — 빼려면 series.toml 에서 지웁니다' : '' });
        box.checked = p.on;
        box.addEventListener('change', () => toggle(c.name));
        const field = (label, control, cls = '') => h('label', { class: `opt ${cls}`.trim() }, h('span', {}, label), control);
        return h('div', { class: `pick ${p.on ? 'on' : 'off'} ${st.shown === c.name ? 'shown' : ''}`.trim(), 'data-column': c.name },
          h('div', { class: 'p1' },
            h('label', { class: 'who' }, box, h('span', { class: 'col-letter' }, c.letter), h('b', {}, c.name), p.fixed ? h('span', { class: 'tag accent' }, '정의에 있음') : null),
            h('span', { class: 'muted small' }, c.n ? `${c.first} – ${c.last} · 값 ${c.n}` : '값이 없습니다', c.missing ? ` · 결측 표시 ${c.missing}` : '', c.bad ? ` · 숫자 아님 ${c.bad}` : ''),
            h('span', { class: 'grow' }),
            h('button', { class: 'btn small quiet', type: 'button', disabled: !c.n, 'data-act': 'try', title: '이 열을 변환대로 만들어 차트로 본다(미리보기 — 아무것도 남지 않는다)',
              onclick: () => tryColumn(c.name) }, icon('chart'), '미리보기')),
          p.on ? h('div', { class: 'p2' }, field('시리즈 이름', text(c, 'name', 'name', '영문 이름')), field('단위', text(c, 'unit', 'unit', '단위')),
            field('설명', text(c, 'desc', 'wide', '설명(한글 이름)'), 'grow'),
            differs ? field('주기 변환', choice(c, 'convert', conv, `${FREQ[v.freq]} → ${FREQ[v.project_freq]}`)) : null,
            field('결측 채움', choice(c, 'fill', FILL, '처음과 끝 사이의 빈 값(안쪽 결측)을 앞뒤 값으로 잇는다 — 채운 칸은 회차에 ‘채움’으로 표시됩니다')),
            seasonal ? field('계절조정', choice(c, 'seas', SEAS, '계절조정 — 자료를 만들 때 조정한 값이 시리즈가 됩니다(안쪽 결측이 있으면 먼저 채워야 합니다)')) : null) : null);
      })));
  }

  const chartBox = h('div', { class: 'try-chart' });
  function renderChart() {
    disposeChart();
    disposeChart = () => {};
    clear(chartBox);
    if (!st.shown) return;
    if (st.chartError && !st.chart) { chartBox.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, h('b', { class: 'mono' }, st.shown), ` — ${st.chartError}`))); return; }
    const c = st.chart;
    if (!c) { chartBox.append(h('div', { class: 'muted pad' }, '만들어 보는 중…')); return; }
    const name = st.picks[st.shown]?.name || st.shown;
    const same = c.source_freq === c.freq;
    const raw = same ? c.period.map((p) => { const i = c.raw_period.indexOf(p); return i < 0 ? null : c.raw[i]; }) : null;
    const changed = same && raw.some((x, i) => x !== c.values[i]);
    chartBox.append(h('div', { class: 'raw-cap' }, h('b', {}, '미리보기'), h('span', { class: 'mono' }, ` ${st.shown} → ${name}`),
      h('span', { class: 'muted' }, ` — ${c.period[0] || '—'} – ${c.period[c.period.length - 1] || '—'} · 값 ${c.n}${c.implicit.length ? ` · ${c.implicit.map((x) => x.replace(/^[^:]+:\s*/, '')).join(' · ')}` : ''}`),
      h('span', { class: 'grow' }), h('button', { class: 'icon-btn', type: 'button', title: '닫기', 'aria-label': '닫기', onclick: () => { st.shown = null; renderChart(); render(); } }, icon('x'))));
    const box = h('div', {});
    chartBox.append(box);
    requestAnimationFrame(() => {
      disposeChart = drawLines(box, { period: c.period, height: 170, title: name, empty: '값이 없습니다.',
        lines: [{ label: changed || !same ? `${name}(만든 값)` : name, values: c.values, color: 'var(--c-actual)', width: 1.5 },
          ...(changed ? [{ label: `${st.shown}(원자료)`, values: raw, color: 'var(--c-resid)', dashed: true, width: 1.2 }] : [])],
        note: same ? null : `원자료 ${FREQ[c.source_freq]} ${c.raw.filter((x) => x != null).length}개 → ${FREQ[c.freq]} ${c.n}개` });
    });
  }

  /** 다시 그려도 치던 칸에 그대로 있게 — 틀의 숫자를 치는 동안 표가 새로 그려진다 */
  function render() {
    const a = document.activeElement;
    const d = a && el.contains(a) ? a.dataset : null;
    const sel = !d ? null : d.frame ? `[data-frame="${d.frame}"]` : d.col ? `[data-col="${CSS.escape(d.col)}"][data-key="${d.key}"]` : d.field ? `[data-field="${d.field}"]` : null;
    const pos = sel && a.type === 'text' ? a.selectionStart : null;
    draw();
    const b = sel ? el.querySelector(sel) : null;
    if (b && !b.disabled) { b.focus(); if (pos != null) b.setSelectionRange(pos, pos); }
  }

  function draw() {
    clear(el);
    const v = st.view;
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, '불러오기'), h('div', { class: 'sub' }, '원자료의 어느 열을 어떤 이름의 시리즈로 읽을지 정합니다. 파일은 고치지 않고 ‘읽는 법’만 정의에 적습니다.')),
      h('div', { class: 'tools' },
        v?.ok ? h('button', { class: 'btn primary', type: 'button', 'data-act': 'store', disabled: project.busy, title: '무엇이 series.toml 에 적히는지 먼저 보입니다(equion data define)', onclick: store }, icon('check'), '④ 정의에 저장…') : null)));
    if (st.saved) {
      const s = st.saved;
      el.append(h('div', { class: 'banner ok' }, icon('check'), h('div', {}, h('b', {}, '정의에 저장했습니다.'), ` ${[s.added.length ? `새 시리즈 ${s.added.join(' · ')}` : '', s.changed.length ? `고친 시리즈 ${s.changed.join(' · ')}` : ''].filter(Boolean).join(' — ') || `출처 ${s.source} 의 틀`}`,
        h('br'), '값은 아직 없습니다 — 자료 작업대에서 ‘자료 만들기’를 누르면 새 회차에 들어갑니다.'),
      h('button', { class: 'btn small primary', type: 'button', onclick: () => project.openTab({ type: 'data', section: 'series' }) }, '자료 작업대로')));
    }
    if (st.error) el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', { class: 'grow' }, st.error), h('button', { class: 'icon-btn', type: 'button', title: '닫기', 'aria-label': '닫기', onclick: () => { st.error = null; render(); } }, icon('x'))));
    if (project.dataInfo && project.dataInfo.mode !== 'defs') {
      el.append(h('div', { class: 'banner info' }, icon('info'), h('div', {}, '이 프로젝트는 자료 파일 하나를 그대로 읽습니다 — 불러오기는 자료 정의(DATA/series.toml)가 있는 프로젝트에서 됩니다.')));
      return;
    }
    el.append(h('div', { class: 'an-form' }, fileRow(), st.file ? frameRow() : null));
    if (!st.file) {
      el.append(h('div', { class: 'empty-state' }, files().length ? '위에서 원자료 파일을 고르세요.' : 'DATA/raw/ 에 원자료 파일이 없습니다 — 자료 작업대의 ‘원자료 넣기…’로 먼저 넣으세요.'));
      return;
    }
    put(el, readLine(), grid(), seriesTable(), chartBox);
    renderChart();
  }

  render();
  return {
    key: 'import', type: 'import', title: '불러오기', icon: 'inbox', el,
    desc: () => ({ type: 'import', file: st.file, source: st.source, frame: st.frame, picks: st.picks }),
    show() { if (!loaded) load(); },
    open(next) { if (next.file && next.file !== st.file) choose(next.file); },
    event(e) {
      if (e.type === 'data' && loaded && !st.view) render();
      else if (e.type === 'job') { const b = el.querySelector('[data-act="store"]'); if (b) b.disabled = project.busy; }
    },
    dispose() { disposeChart(); },
  };
}
