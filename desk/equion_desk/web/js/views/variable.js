// 변수 창 · 그룹 창 (DESK_V2 §2.3) — 변수 하나를 두 번 누르면 변수 창, 여럿(또는 묶음)을 골라 열면 그룹 창.
//
//   변수 창:  차트 · 값 · 내력 · 분석      그룹 창:  차트 · 값 · 상관 · 분석
//
// 보기의 변환(수준 · 로그 · 차분 · 로그차분 · 전년동기비)은 화면에서만 계산한다 — 파생 시리즈를 만들지 않는다.
// 분석 보기는 그 대상에 돌린 기록이 있으면 가장 새 것을 보이고, 없으면 '돌리기'를 권한다. 여기서 돌려도 결과는 기록(an:)으로 남는다.

import { drawLines } from '../chart.js';
import { renderDoc } from '../md.js';
import { clear, h, icon, num, when } from '../util.js';
import { openVarMenu, targetText, TRANSFORMS } from '../varmenu.js';

const COLORS = ['var(--c-actual)', 'var(--k-est)', 'var(--k-sim)', 'var(--k-hs)', 'var(--k-an)', 'var(--k-data)', 'var(--k-run)', 'var(--k-prop)'];
const LAG = { Q: 4, M: 12, A: 1 };
const SUGGEST_ONE = ['stats', 'acf', 'unitroot', 'hist'];
const SUGGEST_MANY = ['corr', 'granger', 'coint', 'stats'];
const MAX_VALUES = 120;

/** 값 열에 변환을 건다(화면에서만) — 앞의 값이 없거나 로그를 못 하는 곳은 빈칸 */
function transform(values, key, freq) {
  const lag = LAG[freq] || 1;
  const log = (v) => (v != null && v > 0 ? Math.log(v) : null);
  if (!key) return values;
  if (key === 'log') return values.map(log);
  if (key === 'd') return values.map((v, i) => (i && v != null && values[i - 1] != null ? v - values[i - 1] : null));
  if (key === 'dlog') return values.map((v, i) => (i && log(v) != null && log(values[i - 1]) != null ? log(v) - log(values[i - 1]) : null));
  if (key === 'pcy') return values.map((v, i) => (i >= lag && v != null && values[i - lag] ? (v / values[i - lag] - 1) * 100 : null));
  return values;
}

const hasToken = (target, name) => new RegExp(`(^|[^A-Za-z0-9_])${name.replace(/[^A-Za-z0-9_]/g, '')}([^A-Za-z0-9_]|$)`, 'i').test(String(target || ''));

export function variableView(project, desc) {
  const names = (Array.isArray(desc.names) ? desc.names : []).filter((x) => typeof x === 'string').slice(0, 24);
  const groupName = typeof desc.group === 'string' ? desc.group : null;
  const many = names.length > 1 || !!groupName;
  const key = `var:${groupName ? `@${groupName}` : names.join(',')}`;
  const el = h('div', { class: 'view var-view' });
  const st = { tab: desc.tab || 'chart', tf: desc.tf || '', data: new Map(), errors: new Map(), shown: desc.shown || null, rec: null, recError: null, running: false, more: false };
  let disposeChart = () => {};
  let loaded = false;

  const side = () => project.side;
  const info = (n) => side()?.variable(n) || null;
  const freq = () => side()?.vars?.freq || project.overview?.freq || 'Q';
  const sel = () => ({ series: names, group: groupName ? { name: groupName, series: names } : null });
  const target = () => targetText(sel(), '');

  async function load() {
    loaded = true;
    await Promise.all(names.map(async (n) => {
      try { st.data.set(n, await project.get(`series?name=${encodeURIComponent(n)}`)); st.errors.delete(n); } catch (err) { st.errors.set(n, err.message); }
    }));
    if (!side()?.alist) await side()?.loadAnalysisList();
    render();
  }

  /** 이 대상에 돌린 분석(가장 새 것 — 분석·대상마다 하나) */
  function results() {
    const all = side()?.alist?.results || [];
    if (!many) return all.filter((r) => r.scope === 'one' && hasToken(r.target, names[0]));
    const set = new Set(names.map((n) => n.toUpperCase()));
    return all.filter((r) => r.scope === 'many' && (r.target === groupName || (() => {
      const toks = String(r.target).split(/\s+/).map((t) => t.replace(/^.*\(|\).*$/g, '').toUpperCase());
      return toks.length === set.size && toks.every((t) => set.has(t));
    })()));
  }

  async function show(id) {
    st.shown = id;
    st.rec = null;
    st.recError = null;
    project.saveView();
    drawBody();
    try {
      const rec = await project.get(`record?id=${encodeURIComponent(id)}`);
      if (st.shown !== id) return;
      st.rec = rec;
      project.seen(id);
    } catch (err) { st.recError = err.message; }
    drawBody();
  }

  async function runHere(analysis) {
    st.running = analysis;
    st.recError = null;
    drawBody();
    try {
      const res = await project.compute('an', { analysis, target: targetText(sel(), st.tf), options: {}, smpl: side()?.smpl || '', name: '' }, { quiet: true });
      st.running = false;
      await side()?.loadAnalysisList();
      await show(res.result.id);
    } catch (err) {
      st.running = false;
      if (err.kind !== 'busy') st.recError = err.message;
      drawBody();
    }
  }

  // ---- 그리기 -----------------------------------------------------------------------------------

  const head = h('div', { class: 'view-head' });
  const bar = h('div', { class: 'var-bar' });
  const body = h('div', { class: 'var-body' });
  el.append(head, bar, body);

  function drawHead() {
    clear(head);
    const one = !many ? info(names[0]) : null;
    const d = !many ? st.data.get(names[0]) : null;
    const title = many
      ? h('h1', {}, icon('layers'), groupName ? h('span', { class: 'mono' }, groupName) : '그룹', h('span', { class: 'tag' }, `변수 ${names.length}`))
      : h('h1', {}, h('span', { class: 'mono' }, names[0]), one?.kind ? h('span', { class: 'tag' }, one.kind) : null);
    const sub = many ? h('div', { class: 'sub mono' }, names.join(' · '))
      : h('div', { class: 'sub' }, one?.desc ? h('span', {}, one.desc) : null, one?.unit ? h('span', {}, one.unit) : null,
        one?.first ? h('span', {}, `${one.first}–${one.last} · ${one.n}개`) : null, d?.vintage ? h('span', { class: 'mono', title: '자료 회차' }, d.vintage) : null);
    head.append(h('div', {}, title, sub), h('div', { class: 'tools' },
      h('button', { class: 'btn', type: 'button', 'data-act': 'var-menu', title: '이 대상에 맞는 분석과 일 — 왼쪽 우클릭과 같은 메뉴', onclick: (e) => openVarMenu(project, e.currentTarget, sel()) }, '할 수 있는 일', icon('chevron', 'down'))));
  }

  function drawBar() {
    clear(bar);
    const tabs = many ? [['chart', '차트'], ['values', '값'], ['corr', '상관'], ['an', '분석']] : [['chart', '차트'], ['values', '값'], ['lineage', '내력'], ['an', '분석']];
    bar.append(h('div', { class: 'segmented', role: 'tablist' }, tabs.map(([k, label]) => h('button', {
      type: 'button', role: 'tab', 'aria-pressed': String(st.tab === k), 'data-tab': k, onclick: () => { st.tab = k; project.saveView(); drawBar(); drawBody(); },
    }, label, k === 'an' && results().length ? h('span', { class: 'c' }, results().length) : null))));
    if (st.tab === 'chart' || st.tab === 'values') {
      bar.append(h('span', { class: 'grow' }), h('div', { class: 'segmented small', role: 'group', 'aria-label': '변환' }, TRANSFORMS.map(([k, label]) => h('button', {
        type: 'button', 'aria-pressed': String(st.tf === k), 'data-tf': k, onclick: () => { st.tf = k; project.saveView(); drawBar(); drawBody(); },
      }, label))));
    }
  }

  /** 여러 시리즈를 한 기간 축에 */
  function aligned() {
    const periods = [];
    const seen = new Set();
    for (const n of names) for (const p of st.data.get(n)?.period || []) if (!seen.has(p)) { seen.add(p); periods.push(p); }
    periods.sort();
    const cols = names.map((n) => {
      const d = st.data.get(n);
      const at = new Map((d?.period || []).map((p, i) => [p, d.values[i]]));
      return transform(periods.map((p) => at.get(p) ?? null), st.tf, freq());
    });
    return { periods, cols };
  }

  function drawBody() {
    disposeChart();
    disposeChart = () => {};
    clear(body);
    const errs = names.filter((n) => st.errors.has(n));
    if (errs.length) body.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, errs.map((n) => h('div', {}, h('b', { class: 'mono' }, n), ` — ${st.errors.get(n)}`)))));
    if (!loaded || (!st.data.size && !errs.length)) { body.append(h('div', { class: 'empty-state' }, '읽는 중…')); return; }
    if (st.tab === 'chart') drawChart();
    else if (st.tab === 'values') drawValues();
    else if (st.tab === 'lineage') drawLineage();
    else if (st.tab === 'corr') drawAnalysis(['corr']);
    else drawAnalysis(null);
  }

  function drawChart() {
    const { periods, cols } = aligned();
    const box = h('div', { class: 'var-chart' });
    body.append(box);
    const tfLabel = (TRANSFORMS.find((t) => t[0] === st.tf) || TRANSFORMS[0])[1];
    requestAnimationFrame(() => {
      disposeChart = drawLines(box, {
        period: periods, height: 260, title: names.join(' · '), zero: ['d', 'dlog', 'pcy'].includes(st.tf), note: st.tf ? tfLabel : '',
        lines: names.map((n, i) => ({ label: n, values: cols[i], color: COLORS[i % COLORS.length], width: i ? 1.4 : 1.6 })),
        empty: '그릴 값이 없습니다.',
      });
    });
    if (many && !st.tf) body.append(h('p', { class: 'muted note' }, '단위가 다른 변수는 한 축에서 잘 안 보입니다 — 변환에서 로그차분·전년동기비를 고르면 견주기 쉽습니다.'));
  }

  function drawValues() {
    const { periods, cols } = aligned();
    const order = periods.map((p, i) => i).reverse();
    const shown = st.more ? order : order.slice(0, MAX_VALUES);
    const lag = LAG[freq()] || 1;
    const raw = names.map((n) => { const d = st.data.get(n); const at = new Map((d?.period || []).map((p, i) => [p, d.values[i]])); return periods.map((p) => at.get(p) ?? null); });
    const head = many ? names : [st.tf ? `${names[0]} (${(TRANSFORMS.find((t) => t[0] === st.tf) || [])[1]})` : names[0], '전기비 %', '전년동기비 %'];
    const cell = (v, digits = 4) => h('td', { class: 'num' }, v == null ? '—' : num(v, digits));
    const table = h('table', { class: 'grid plain var-values' },
      h('thead', {}, h('tr', {}, h('th', {}, '기간'), head.map((c) => h('th', { class: 'num', 'data-var': many ? c : null }, c)))),
      h('tbody', {}, shown.map((i) => h('tr', {}, h('td', { class: 'mono' }, periods[i]),
        many ? cols.map((c) => cell(c[i]))
          : [cell(cols[0][i]),
            cell(i && raw[0][i] != null && raw[0][i - 1] ? (raw[0][i] / raw[0][i - 1] - 1) * 100 : null, 3),
            cell(i >= lag && raw[0][i] != null && raw[0][i - lag] ? (raw[0][i] / raw[0][i - lag] - 1) * 100 : null, 3)]))));
    body.append(h('div', { class: 'table-wrap' }, table));
    if (order.length > MAX_VALUES && !st.more) body.append(h('button', { class: 'link', type: 'button', onclick: () => { st.more = true; drawBody(); } }, `앞의 ${order.length - MAX_VALUES}개 더 보기`));
  }

  function drawLineage() {
    const d = st.data.get(names[0]);
    const one = info(names[0]);
    if (!d) return;
    body.append(h('h3', { class: 'cap' }, '만드는 법'),
      h('div', { class: 'lineage' }, d.lineage.flatMap((step, i) => [i ? icon('arrow') : null,
        h(step.file ? 'button' : 'span', { class: `stepchip ${step.file ? 'go' : ''}`.trim(), type: step.file ? 'button' : null, title: step.file ? `${step.file} 열기` : '',
          onclick: step.file ? () => project.openTab({ type: 'file', path: step.file }) : null }, h('small', {}, step.step), h('span', { class: 'mono' }, step.text))]),
      d.lineage.length ? icon('arrow') : null, h('span', { class: 'stepchip end' }, h('small', {}, '시리즈'), h('span', { class: 'mono' }, d.name))));
    if (d.raw) {
      const box = h('div', { class: 'var-chart' });
      body.append(h('h3', { class: 'cap' }, '원자료와 견주기'), box);
      requestAnimationFrame(() => {
        disposeChart = drawLines(box, { period: d.period, height: 200, title: d.name, lines: [{ label: d.name, values: d.values, color: 'var(--c-actual)', width: 1.5 },
          { label: d.raw.label, values: d.raw.values, color: 'var(--c-resid)', dashed: true, width: 1.2 }] });
      });
    }
    const chips = (list, empty) => (list?.length ? list.map((p) => h('button', { class: 'part-chip', type: 'button', onclick: () => project.openTab({ type: 'bench', part: p }) }, h('b', {}, p))) : h('span', { class: 'muted' }, empty));
    body.append(h('h3', { class: 'cap' }, '모형과의 관계'),
      h('div', { class: 'detail-foot' },
        h('div', { class: 'pair' }, h('span', { class: 'k' }, '이 변수의 식'), chips(one?.parts, '없습니다 — 외생이거나 아직 식이 없습니다')),
        h('div', { class: 'pair' }, h('span', { class: 'k' }, '쓰는 식'), chips(one?.users, '아직 없습니다')),
        one?.models?.length ? h('div', { class: 'pair' }, h('span', { class: 'k' }, '모형'), one.models.map((m) => h('button', { class: 'part-chip', type: 'button', onclick: () => project.openTab({ type: 'model', model: m }) }, h('b', {}, m)))) : null),
      h('p', { class: 'muted note' }, '원자료 파일 · 열 · 계절조정 같은 정의는 자료 작업대에서 고칩니다.'),
      h('button', { class: 'btn small', type: 'button', onclick: () => project.openTab({ type: 'data', section: 'series' }) }, icon('data'), '자료 작업대'));
  }

  /** 분석 보기 — 돌린 기록(가장 새 것)과 '돌리기'. only: 그 분석만(그룹 창의 상관) */
  function drawAnalysis(only) {
    const reg = side()?.registry;
    const list = results().filter((r) => !only || only.includes(r.analysis));
    const ran = new Set(list.map((r) => r.analysis));
    const wanted = (only || (many ? SUGGEST_MANY : SUGGEST_ONE)).filter((a) => reg?.analyses.some((x) => x.name === a) && !ran.has(a));
    const label = (a) => reg?.analyses.find((x) => x.name === a)?.label || a;
    if (only && !st.shown && list.length) { show(list[0].id); return; }
    const runBtns = wanted.map((a) => h('button', { class: 'btn small', type: 'button', 'data-run': a, disabled: !!st.running || project.busy,
      title: `equion an ${a} ${targetText(sel(), st.tf)}${side()?.smpl ? ` --smpl ${side().smpl}` : ''}`, onclick: () => runHere(a) }, icon('play'), `${label(a)} 돌리기`));
    const rows = list.map((r) => h('button', { class: `rec-row ${r.id === st.shown ? 'on' : ''}`.trim(), type: 'button', 'data-record': r.id, onclick: () => show(r.id) },
      h('b', {}, r.label || r.analysis), h('span', { class: 'mono' }, r.target_label || r.target), r.stale ? h('span', { class: 'tag warn', title: '다른 자료 회차로 계산했습니다' }, '낡음') : null,
      h('span', { class: 'when' }, when(r.created)),
      h('span', { class: 'icon-btn mini', role: 'button', title: '같은 설정으로 다시 돌린다', onclick: (e) => { e.stopPropagation(); project.openTab({ type: 'analysis', analysis: r.analysis, target: r.target, options: r.options || {}, smpl: r.smpl || '', run: true }); } }, icon('refresh'))));
    body.append(h('div', { class: 'var-an' },
      rows.length ? h('div', { class: 'rec-list' }, rows) : h('div', { class: 'empty-state' }, only ? '아직 돌린 상관 분석이 없습니다.' : '이 대상에 돌린 분석이 아직 없습니다.'),
      runBtns.length ? h('div', { class: 'var-run' }, h('span', { class: 'muted' }, `표본 ${side()?.smpl || '전체'}${st.tf ? ` · 변환 ${(TRANSFORMS.find((t) => t[0] === st.tf) || [])[1]}` : ''}`), runBtns) : null,
      h('button', { class: 'link', type: 'button', onclick: () => project.openTab({ type: 'analysis', target: target(), analysis: only?.[0] || null }) }, '다른 분석은 분석 실행에서 →')));
    if (st.running) { body.append(h('div', { class: 'empty-state' }, `${label(st.running)} 계산하는 중…`)); return; }
    if (st.recError) body.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, st.recError)));
    if (st.shown && list.some((r) => r.id === st.shown)) {
      const doc = h('div', { class: 'of-record' });
      body.append(h('div', { class: 'result-head' }, h('button', { class: 'rid', type: 'button', title: '이 기록의 카드를 따로 연다', onclick: () => project.openRecord(st.shown) }, st.shown)), doc);
      if (st.rec?.summary) renderDoc(doc, st.rec.summary, { pid: project.id, dir: st.rec.path, openFile: (path) => project.openTab({ type: 'file', path }) });
      else if (!st.rec) doc.append(h('div', { class: 'empty-state' }, '읽는 중…'));
    } else if (!only && list.length && !st.shown) show(list[0].id);
  }

  function render() {
    drawHead();
    drawBar();
    drawBody();
  }

  render();
  return {
    key, type: 'var', title: groupName || (names.length > 3 ? `${names.slice(0, 3).join(' · ')} …` : names.join(' · ')), icon: many ? 'layers' : 'chart', mono: true, el,
    desc: () => ({ type: 'var', names, group: groupName, tab: st.tab, tf: st.tf, shown: st.shown }),
    show() { if (!loaded) load(); },
    open(next) { if (next.tab) { st.tab = next.tab; render(); } },
    event(e) {
      if (e.type === 'data' || (e.type === 'record' && e.record?.kind === 'data')) { st.data.clear(); loaded = false; if (el.isConnected) load(); }
      if (e.type === 'record' && e.record?.kind === 'an' && el.isConnected && st.tab === 'an') setTimeout(() => { drawBar(); drawBody(); }, 500);
    },
    dispose() { disposeChart(); },
  };
}

