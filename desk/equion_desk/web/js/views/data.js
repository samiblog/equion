// 자료 작업대(W4) — 자료가 어디서 와서 무엇이 되는지를 한 화면에.
//
//   ① 원자료   받은 파일 그대로(고치지 않는다) — 넣기만 한다
//   ② 시리즈   어느 열을 어떤 시리즈로 읽는지(정의) — 시리즈마다 만드는 법·구간·쓰는 식, 누르면 차트와 내력
//   ③ 회차     정의대로 만든 자료 한 벌 — 만들기 · 견주기 · 이 회차로 바꾸기
//
// 세 칸은 설명이자 갈래다(누르면 그 칸의 목록). 그 아래 한 줄이 지금 할 일을 말한다 — "정의가 바뀌었습니다 → 자료 만들기"처럼.
// 저절로 하는 것은 없다: 만들기·바꾸기는 단추를 누를 때만, 바꾼 뒤의 다시 추정·풀기도 따로 시킨다(기획안 §2.4-1).
// 정의를 새로 짝짓는 화면(불러오기)은 다음 걸음이다 — 지금은 정의 파일을 열어 보고, 계절조정·파생은 분석 탭에서 '정의로 남기기'.

import { drawLines } from '../chart.js';
import { confirmDialog, popMenu } from '../dialog.js';
import { bytes, clear, flash, h, icon, put, short, when } from '../util.js';

const FREQ = { A: '연', Q: '분기', M: '월' };
const SECTIONS = ['raw', 'series', 'vintages'];
const stamp = (mtime) => (mtime ? when(new Date(mtime * 1000).toISOString()) : '');
const span = (a, b) => (a && b ? `${a} – ${b}` : '—');

export function dataView(project, desc) {
  const el = h('div', { class: 'view data' });
  const st = {
    data: project.dataInfo, error: null, loadError: null, loading: false, section: SECTIONS.includes(desc.section) ? desc.section : 'series',
    q: '', filter: 'all', open: desc.open || null, details: new Map(), diff: null, made: null, todo: null, reest: null,
  };
  let disposeChart = () => {};
  let loaded = false;

  const current = () => st.data?.current || null;
  const latest = () => st.data?.vintages?.[st.data.vintages.length - 1]?.id || null;

  /** 프로젝트가 읽어 둔 것을 화면에 — 정의·원자료·회차가 바뀌면 프로젝트가 다시 읽고 알린다 */
  function take() {
    st.data = project.dataInfo;
    st.loadError = project.dataError;
    st.loading = false;
    st.details.clear();
    if (st.diff && !st.data?.vintages.some((v) => v.id === st.diff.b)) st.diff = null;
    render();
    loadTodo();
  }

  /** 지금 회차가 아닌 자료로 계산한 것(채택한 계수·과거 재현·전망) — 무엇이 낡았는지만 읽는다 */
  async function loadTodo() {
    if (st.data?.mode !== 'defs' || !st.data.current) { st.todo = null; return; }
    try { st.todo = await project.get('todo'); } catch { st.todo = null; }
    const box = el.querySelector('.todo-slot');
    if (box) { clear(box); put(box, todoPanel()); }
  }

  async function reestimate() {
    try {
      const res = await project.compute('reestimate', { name: st.todo?.hs?.model || project.overview?.hs?.model || undefined }, { quiet: true });
      st.reest = { ...res.result, pick: new Set(res.result.rows.filter((r) => r.passed !== false && r.old).map((r) => r.part)) };
      render();
    } catch (err) {
      if (err.kind !== 'busy') { st.error = err.message; render(); }
    }
  }

  async function adoptPicked() {
    const rows = st.reest.rows.filter((r) => st.reest.pick.has(r.part));
    if (!rows.length) return;
    const body = h('div', { class: 'adopt' }, h('p', {}, `고른 식 ${rows.length}개의 채택 계수를 새 추정 기록의 것으로 바꿉니다. 모형은 이 계수로 풉니다 — 과거 재현·전망을 다시 푸는 것은 따로 시킵니다.`),
      h('h4', {}, '채택표 ', h('span', { class: 'mono' }, 'EQUATIONS/adopted.toml')),
      h('div', { class: 'diff' }, rows.flatMap((r) => [r.old ? h('span', { class: 'dl del' }, `- "${r.part}" = "${r.old}"`) : null, h('span', { class: 'dl add' }, `+ "${r.part}" = "${r.new}"`)])),
      h('p', { class: 'muted' }, '바뀜 기록에 남고, 거기서 되돌릴 수 있습니다.'));
    if (!(await confirmDialog({ title: '새 계수 채택', body, confirm: `${rows.length}개 채택`, wide: true }))) return;
    try {
      await project.compute('reestimate', { parts: rows.map((r) => `${r.part}=${r.new}`) }, { quiet: true });
      st.reest = null;
      flash(`식 ${rows.length}개의 새 계수를 채택했습니다`);
      await project.loadOverview();
      loadTodo();
      render();
    } catch (err) {
      if (err.kind !== 'busy') { st.error = err.message; render(); }
    }
  }

  function todoPanel() {
    const t = st.todo;
    if (!t) return null;
    const rows = [];
    if (t.adopted.length) {
      const from = [...new Set(t.adopted.map((a) => a.vintage).filter(Boolean))].join(' · ');
      rows.push(h('div', { class: 'todo-row' }, h('span', { class: 'what' }, h('b', {}, `채택한 식 ${t.adopted.length}개`), `의 계수가 옛 자료(${from || '다른 회차'})로 추정됐습니다`),
        h('button', { class: 'btn small', type: 'button', 'data-act': 'reest', disabled: project.busy, title: 'equion est --adopted — 지금 자료로 다시 추정해 기록만 남기고, 옛 계수와 견준다(채택은 고른 것만)', onclick: reestimate }, '다시 추정해 견주기')));
    }
    if (t.hs?.stale) {
      rows.push(h('div', { class: 'todo-row' }, h('span', { class: 'what' }, h('b', {}, '과거 재현 '), h('span', { class: 'mono' }, t.hs.id), ` 은(는) 옛 자료(${t.hs.vintage})로 풀었습니다`),
        h('button', { class: 'btn small', type: 'button', disabled: project.busy, title: `equion hs ${t.hs.model} — 지금 자료로 다시 푼다(새 기록)`, onclick: () => project.openTab({ type: 'model', model: t.hs.model, section: 'hs' }) }, '모형 작업대에서 다시 풀기')));
    }
    if (t.sim?.stale) {
      rows.push(h('div', { class: 'todo-row' }, h('span', { class: 'what' }, h('b', {}, '전망 '), h('span', { class: 'mono' }, t.sim.id), ` 은(는) 옛 자료(${t.sim.vintage})로 풀었습니다`),
        h('button', { class: 'btn small', type: 'button', disabled: project.busy, title: `equion sim ${t.sim.scenario || 'base'} — 지금 자료로 다시 푼다(새 기록)`, onclick: () => project.compute('sim', { scenario: t.sim.scenario || 'base', model: t.sim.model }) }, '다시 풀기')));
    }
    if (!rows.length && !st.reest) return null;
    return h('div', { class: 'todo' }, rows.length ? h('div', { class: 'todo-head' }, icon('list'), h('b', {}, `회차 ${t.vintage} 로 바꾼 뒤 할 일`), h('span', { class: 'muted' }, '— 저절로 다시 계산하지 않습니다. 누른 것만 합니다.')) : null, rows, st.reest ? reestTable() : null);
  }

  function reestTable() {
    const r = st.reest;
    const pick = r.pick;
    const short3 = (v) => (v == null ? '—' : Math.abs(v) >= 100 ? v.toFixed(1) : v.toPrecision(4));
    return h('div', { class: 'reest' }, h('div', { class: 'todo-head' }, h('b', {}, '다시 추정한 결과'), h('span', { class: 'muted' }, `— ${r.model} · 지금 자료로. 고른 식만 새 계수로 채택합니다`), h('span', { class: 'grow' }),
      h('button', { class: 'btn small quiet', type: 'button', onclick: () => { st.reest = null; render(); } }, '닫기'),
      h('button', { class: 'btn small primary', type: 'button', 'data-act': 'adopt-new', disabled: !pick.size || project.busy, onclick: adoptPicked }, `고른 식 채택${pick.size ? ` (${pick.size})` : ''}`)),
    h('table', { class: 'grid plain reest-table' }, h('thead', {}, h('tr', {}, ['', '식', '가장 크게 바뀐 계수', '조정 R²', '표준오차', '기준', '기록'].map((c, i) => h('th', { class: i >= 2 && i <= 4 ? 'num' : '' }, c)))),
      h('tbody', {}, r.rows.map((row) => {
        const box = h('input', { type: 'checkbox', 'aria-label': `${row.part} 의 새 계수 채택` });
        box.checked = pick.has(row.part);
        box.addEventListener('change', () => { if (box.checked) pick.add(row.part); else pick.delete(row.part); render(); });
        const o = row.old_fit, n = row.new_fit;
        return h('tr', {}, h('td', {}, box), h('td', {}, h('b', { class: 'mono' }, row.part), row.old ? null : h('span', { class: 'tag', title: '아직 채택한 계수가 없던 식입니다' }, '채택 없음')),
          h('td', { class: 'num' }, row.max_change_pct == null ? '—' : `${row.max_change_pct.toFixed(row.max_change_pct < 10 ? 2 : 1)}%`),
          h('td', { class: 'num' }, o ? `${short3(o.r2_adj)} → ` : '', short3(n?.r2_adj)), h('td', { class: 'num' }, o ? `${short3(o.se)} → ` : '', short3(n?.se)),
          h('td', {}, row.passed === false ? h('span', { class: 'tag warn', title: row.reasons.join('\n') }, `걸러짐 — ${row.reasons[0] || ''}`) : h('span', { class: 'tag ok' }, '통과')),
          h('td', {}, h('button', { class: 'link mono', type: 'button', title: '새 추정 기록을 식 작업대에서 본다', onclick: () => project.openTab({ type: 'bench', part: row.part, shown: row.new }) }, row.new)));
      }))));
  }

  async function load() {
    loaded = true;
    st.loading = true;
    await project.loadData();
  }

  // ---- 하는 일 ----------------------------------------------------------------------------------

  async function build() {
    try {
      const res = await project.compute('data/build', {}, { quiet: true });
      const r = res.result;
      if (r.created) {
        st.made = r;
        st.section = 'vintages';
        st.diff = r.diff ? { a: r.diff.a, b: r.diff.b, data: r.diff } : null;
        flash(`새 회차 ${r.id} 를 만들었습니다 — 지금 회차는 그대로입니다`);
      } else flash(`값이 같아 새 회차를 만들지 않았습니다(${r.id})`);
      await load();
      if (r.created && r.diff) compare(r.diff.a, r.diff.b);       // 영향(쓰는 식·모형)까지
      else if (!r.created && project.dataInfo?.fingerprint) {
        // 정의의 글(주석 등)이나 파일 이름만 바뀌고 값은 같았다 — 같은 것을 다시 권하지 않게 기억해 둔다
        project.dataChecked = { vintage: r.id, fingerprint: project.dataInfo.fingerprint };
        project.saveView();
        project.renderParts();
        render();
      }
    } catch (err) {
      if (err.kind !== 'busy') { st.error = err.message; render(); }
    }
  }

  async function compare(a, b) {
    st.section = 'vintages';
    st.diff = { a, b, data: st.diff?.a === a && st.diff?.b === b ? st.diff.data : null };
    render();
    try {
      const data = await project.get(`data/diff?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
      if (st.diff?.a === a && st.diff?.b === b) { st.diff.data = data; render(); }
    } catch (err) {
      st.diff = null;
      st.error = err.message;
      render();
    }
  }

  async function use(id) {
    const from = current();
    let diff = null;
    if (from && from !== id) { try { diff = await project.get(`data/diff?a=${encodeURIComponent(from)}&b=${encodeURIComponent(id)}`); } catch { /* 차이 없이도 바꿀 수 있다 */ } }
    const impact = diff?.impact;
    const body = h('div', { class: 'adopt' },
      h('p', {}, '이 뒤의 추정·풀이는 ', h('b', { class: 'mono' }, id), ' 의 자료로 합니다. 지금까지의 결과는 그대로 남습니다(다른 회차로 계산한 것이라는 표시가 붙습니다).'),
      diff ? h('p', {}, changeSummary(diff)) : null,
      impact?.parts?.length ? h('div', { class: 'banner info' }, icon('info'), h('div', {}, `바뀐 시리즈를 쓰는 식 ${impact.parts.length}개 · 모형 ${impact.models.length}개 — 새 자료로 다시 추정·풀기는 따로 시켜야 합니다(저절로 하지 않습니다).`)) : null,
      h('h4', {}, '프로젝트 설정 ', h('span', { class: 'mono' }, 'equion.toml [data]')),
      h('div', { class: 'diff' }, from ? h('span', { class: 'dl del' }, `- vintage = "${from}"`) : null, h('span', { class: 'dl add' }, `+ vintage = "${id}"`)),
      h('p', { class: 'muted' }, '바뀜 기록에 남습니다. 옛 회차는 지워지지 않으니 언제든 다시 바꿀 수 있습니다.'));
    if (!(await confirmDialog({ title: `${id} 회차로 바꾸기`, body, confirm: '이 회차로 바꾸기', wide: true }))) return;
    try {
      await project.compute('data/use', { vintage: id }, { quiet: true });
      st.made = null;
      flash(`지금 회차는 ${id} 입니다`);
      await project.loadOverview();
      await load();
    } catch (err) {
      if (err.kind !== 'busy') { st.error = err.message; render(); }
    }
  }

  /** then: 넣은 뒤 할 일 — 'import' 면 그 파일로 불러오기 화면을 연다(새 원자료) */
  async function addRaw(body, label, then = null) {
    try {
      const res = await project.compute('data/add', body, { quiet: true });
      if (!res.result) return;                         // 파일을 고르지 않았다
      const r = res.result;
      if (then === 'import' && !r.problems?.length) { await load(); project.openTab({ type: 'import', file: r.file }); return; }
      if (r.problems?.length) st.error = `넣지 않았습니다 — ${label || r.file.split(/[\\/]/).pop()} 이(가) ${r.source || '그 원자료'} 의 틀과 맞지 않습니다(아무것도 바뀌지 않았습니다).\n${r.problems.join('\n')}`;
      else flash(r.source ? `${label || r.file} — ${r.source} 의 새 파일로 넣었습니다. ‘자료 만들기’로 새 회차를 만드세요` : `${r.file} 을(를) 넣었습니다`);
      st.section = 'raw';
      await load();
    } catch (err) {
      if (err.kind !== 'busy') { st.error = err.message; render(); }
    }
  }

  /** '원자료 넣기…' — 어느 출처의 새 파일인지 먼저 묻고 파일을 고른다 */
  function pickRaw(anchor) {
    const sources = st.data?.sources || [];
    popMenu(anchor, [h('div', { class: 'menu-title' }, '어느 원자료의 새 파일인가요'),
      ...sources.map((s) => ({ label: s.name, hint: `${s.file.split('/').pop()} 대신 읽게`, onPick: () => addRaw({ source: s.name }) })),
      { label: '새 원자료', hint: '넣고 나서 열을 시리즈로 짝짓는다(불러오기)', onPick: () => addRaw({}, null, 'import') }], { cls: 'plain', align: 'right' });
  }

  // ---- 그리기 -----------------------------------------------------------------------------------

  function changeSummary(d) {
    const bits = [];
    if (d.span_a?.[1] !== d.span_b?.[1] || d.span_a?.[0] !== d.span_b?.[0]) bits.push(`구간 ${span(...d.span_a)} → ${span(...d.span_b)}`);
    if (d.extended) bits.push(`새 값이 생긴 시리즈 ${d.extended}`);
    if (d.revised) bits.push(`값이 고쳐진(개정) 시리즈 ${d.revised}`);
    if (d.added?.length) bits.push(`새 시리즈 ${d.added.join(', ')}`);
    if (d.removed?.length) bits.push(`없어진 시리즈 ${d.removed.join(', ')}`);
    return bits.length ? bits.join(' · ') : '두 회차의 값이 같습니다.';
  }

  function flow() {
    const d = st.data;
    const derived = d.series.filter((s) => s.kind === 'derived').length;
    const cur = d.vintages.find((v) => v.current);
    const card = (key, n, title, big, small, mark) => h('button', {
      class: `flow-card ${st.section === key ? 'on' : ''}`.trim(), type: 'button', 'aria-pressed': String(st.section === key),
      onclick: () => { st.section = key; render(); project.saveView(); },
    }, h('span', { class: 'step' }, n), h('span', { class: 'ft' }, title, mark ? h('span', { class: `dot ${mark}` }) : null), h('span', { class: 'fb' }, big), h('span', { class: 'fs' }, small));
    const rawMark = d.sources.some((s) => s.error) ? 'bad' : d.inbox.length ? 'warn' : '';
    return h('div', { class: 'flow', role: 'tablist', 'aria-label': '자료의 세 층' },
      card('raw', '1', '원자료', `파일 ${d.sources.length}개`, d.inbox.length ? `새 파일 ${d.inbox.length}개 도착` : '받은 그대로', rawMark),
      h('span', { class: 'flow-arrow', 'aria-hidden': 'true' }, icon('arrow')),
      card('series', '2', '시리즈', `${d.series.length}개`, derived ? `원자료 ${d.series.length - derived} · 파생 ${derived}` : '열 → 시리즈', d.problems.length ? 'bad' : ''),
      h('span', { class: 'flow-arrow', 'aria-hidden': 'true' }, icon('arrow')),
      card('vintages', '3', '회차', cur ? cur.id : '아직 없음', cur ? span(...(cur.span || [])) : '자료 만들기를 누르세요', project.dataPending() || (cur && latest() !== cur.id) ? 'warn' : cur ? 'ok' : 'warn'));
  }

  /** 지금 할 일 한 줄 */
  function status() {
    const d = st.data;
    const cur = current();
    if (d.problems.length) {
      return h('div', { class: 'banner error' }, icon('alert'), h('div', {}, '정의 파일을 읽지 못했습니다.', h('pre', {}, d.problems.join('\n')),
        h('button', { class: 'btn small', type: 'button', onclick: () => project.openTab({ type: 'file', path: d.series_file }) }, d.series_file)));
    }
    if (!cur) return h('div', { class: 'banner info' }, icon('info'), h('div', {}, '아직 만든 자료가 없습니다 — ‘자료 만들기’를 누르면 원자료를 정의대로 읽어 첫 회차를 만듭니다.'));
    const newest = latest();
    if (newest && newest !== cur && !project.dataPending()) {       // 지금의 원자료·정의로 만든 회차가 이미 있다 — 바꾸기만 남았다
      return h('div', { class: 'banner info' }, icon('info'), h('div', {}, h('b', {}, `새 회차 ${newest} 가 준비돼 있습니다`), ` — 계산은 아직 ${cur} 로 합니다. 무엇이 달라졌는지 보고 바꾸세요.`),
        h('button', { class: 'btn small', type: 'button', onclick: () => compare(cur, newest) }, '견주기'),
        h('button', { class: 'btn small primary', type: 'button', onclick: () => use(newest) }, '이 회차로 바꾸기'));
    }
    const stale = project.dataStale();
    if (stale) {
      const what = [...stale.definitions.map((f) => f.split('/').pop()), ...stale.sources.map((s) => `원자료 ${s}`)].join(' · ');
      return h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, h('b', {}, `지금 회차 ${cur} 를 만든 뒤 바뀐 것이 있습니다`), ` — ${what}. 계산은 아직 옛 자료로 합니다. 새 자료로 하려면 자료를 다시 만드세요.`),
        h('button', { class: 'btn small primary', type: 'button', onclick: build }, '자료 만들기'));
    }
    if (d.inbox.length) {
      return h('div', { class: 'banner info' }, icon('inbox'), h('div', {}, h('b', {}, `받은 상자에 새 파일 ${d.inbox.length}개가 있습니다`), ' — 원자료로 넣은 뒤 자료를 만들면 새 회차가 됩니다.'),
        st.section === 'raw' ? null : h('button', { class: 'btn small primary', type: 'button', onclick: () => { st.section = 'raw'; render(); project.saveView(); } }, '받은 상자 보기'));
    }
    return h('div', { class: 'banner ok' }, icon('check'), h('div', {}, `지금 회차 ${cur} 는 원자료·정의와 같습니다.`));
  }

  function seriesSection() {
    const d = st.data;
    const counts = { all: d.series.length, raw: d.series.filter((s) => s.kind !== 'derived').length, derived: d.series.filter((s) => s.kind === 'derived').length,
      used: d.series.filter((s) => s.used_by.length).length };
    const search = h('input', { class: 'find', type: 'search', placeholder: '이름·설명으로 찾기', value: st.q, 'aria-label': '시리즈 찾기', spellcheck: 'false' });
    search.addEventListener('input', () => { st.q = search.value; drawList(); });
    const chip = (key, label) => (counts[key] || key === 'all' ? h('button', { type: 'button', 'aria-pressed': String(st.filter === key), onclick: () => { st.filter = key; render(); } }, label, h('span', { class: 'c' }, counts[key])) : null);
    const list = h('div', {});
    const drawList = () => {
      const q = st.q.trim().toLowerCase();
      const shown = d.series.filter((s) => (st.filter === 'all' || (st.filter === 'derived' ? s.kind === 'derived' : st.filter === 'raw' ? s.kind !== 'derived' : s.used_by.length))
        && (!q || s.name.toLowerCase().includes(q) || (s.desc || '').toLowerCase().includes(q)));
      disposeChart();
      disposeChart = () => {};
      clear(list).append(shown.length ? seriesTable(shown) : h('div', { class: 'empty-state' }, '찾는 시리즈가 없습니다.'));
    };
    drawList();
    return h('div', {},
      h('div', { class: 'list-tools' }, h('div', { class: 'find-box' }, icon('search'), search),
        h('div', { class: 'filters' }, chip('all', '모두'), d.mode === 'defs' ? chip('raw', '원자료에서') : null, chip('derived', '파생'), chip('used', '식이 쓰는 것'))),
      list,
      d.series_file ? h('div', { class: 'files-line' }, '정의 파일',
        [d.series_file, d.derived_file].filter(Boolean).map((f) => h('button', { class: 'file-chip', type: 'button', title: `${f} 을(를) 연다(읽기 전용)`, onclick: () => project.openTab({ type: 'file', path: f }) }, f.split('/').pop())),
        h('span', {}, '— 어느 열을 어떤 시리즈로 읽는지 적는 곳입니다. 편집기·Claude 로 고치면 여기에 바로 보입니다.')) : null);
  }

  function seriesTable(rows) {
    return h('table', { class: 'grid plain series' }, h('thead', {}, h('tr', {}, ['시리즈', '만드는 법', '구간', '값', '쓰는 식'].map((c, i) => h('th', { class: i >= 3 ? 'num' : '' }, c)))),
      h('tbody', {}, rows.flatMap((s) => {
        const open = st.open === s.name;
        const how = s.kind === 'derived' ? h('span', { class: 'mono how' }, s.from) : s.kind === 'file' ? h('span', { class: 'muted' }, s.from || '')
          : h('span', { class: 'how' }, h('span', { class: 'mono' }, `${s.source} · ${s.column}`), s.how ? h('span', { class: 'tag' }, s.how) : null);
        const tr = h('tr', { class: `row ${open ? 'open' : ''}`.trim(), tabindex: '0', 'aria-expanded': String(open), title: open ? '접기' : '차트와 내력 보기',
          onclick: () => toggle(s.name), onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(s.name); } } },
        h('td', {}, icon('chevron', 'caret'), h('b', { class: 'mono' }, s.name), s.desc ? h('span', { class: 'desc' }, s.desc) : null),
        h('td', {}, how),
        h('td', { class: 'nowrap' }, s.built === false ? h('span', { class: 'tag warn', title: '정의에는 있지만 지금 회차에는 없습니다 — 자료 만들기 뒤에 들어갑니다' }, '회차에 없음') : span(s.start, s.end)),
        h('td', { class: 'num' }, s.n || '—', s.missing ? h('span', { class: 'tag warn', title: `처음과 끝 사이에 빈 값 ${s.missing}개` }, `결측 ${s.missing}`) : null),
        h('td', { class: 'num' }, s.used_by.length ? h('span', { class: 'tag accent', title: s.used_by.join('\n') }, s.used_by.length) : h('span', { class: 'muted' }, '—')));
        return open ? [tr, h('tr', { class: 'detail' }, h('td', { colspan: '5' }, detailBox(s)))] : [tr];
      })));
  }

  function toggle(name) {
    st.open = st.open === name ? null : name;
    render();
    project.saveView();
  }

  function detailBox(s) {
    const box = h('div', { class: 'series-detail' }, h('div', { class: 'muted' }, '읽는 중…'));
    const draw = (dt) => {
      clear(box);
      if (dt.error) { box.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, dt.error))); return; }
      const chart = h('div', {});
      const lineage = h('div', { class: 'lineage' }, dt.lineage.flatMap((step, i) => [i ? icon('arrow') : null,
        h(step.file ? 'button' : 'span', { class: `stepchip ${step.file ? 'go' : ''}`.trim(), type: step.file ? 'button' : null, title: step.file ? `${step.file} 열기` : '',
          onclick: step.file ? () => project.openTab({ type: 'file', path: step.file }) : null }, h('small', {}, step.step), h('span', { class: 'mono' }, step.text))]),
      dt.lineage.length ? icon('arrow') : null, h('span', { class: 'stepchip end' }, h('small', {}, '시리즈'), h('span', { class: 'mono' }, dt.name)));
      const an = (name, label, title) => h('button', { class: 'btn small', type: 'button', title, onclick: () => project.openTab({ type: 'analysis', analysis: name, target: dt.name, run: true }) }, label);
      put(box, lineage, chart,
        h('div', { class: 'detail-foot' },
          h('div', { class: 'pair' }, h('span', { class: 'k' }, '쓰는 식'), s.used_by.length ? s.used_by.map((p) => h('button', { class: 'part-chip', type: 'button', onclick: () => project.openTab({ type: 'bench', part: p }) }, h('b', {}, p)))
            : h('span', { class: 'muted' }, '아직 없습니다')),
          s.unit ? h('div', { class: 'pair' }, h('span', { class: 'k' }, '단위'), h('span', {}, s.unit)) : null,
          h('span', { class: 'grow' }),
          h('div', { class: 'pair' }, h('span', { class: 'k' }, '분석'), an('summary', '요약', '구간·결측·끝 값·수준 차트'), an('unitroot', '단위근', 'ADF·KPSS'),
            s.kind === 'series' ? an('seas', '계절조정', '계절조정을 미리 보고, 마음에 들면 정의로 남긴다') : null)));
      requestAnimationFrame(() => {
        disposeChart();
        disposeChart = drawLines(chart, { period: dt.period, height: 190, title: dt.name, empty: '값이 없습니다.',
          lines: [{ label: dt.name, values: dt.values, color: 'var(--c-actual)', width: 1.5 },
            ...(dt.raw ? [{ label: dt.raw.label, values: dt.raw.values, color: 'var(--c-resid)', dashed: true, width: 1.2 }] : [])] });
      });
    };
    if (st.details.has(s.name)) draw(st.details.get(s.name));
    else if (s.built === false) draw({ error: '지금 회차에 없는 시리즈입니다 — ‘자료 만들기’로 새 회차를 만들면 값이 생깁니다.' });
    else {
      project.get(`series?name=${encodeURIComponent(s.name)}`).then((dt) => { st.details.set(s.name, dt); if (st.open === s.name && box.isConnected) draw(dt); })
        .catch((err) => { if (box.isConnected) draw({ error: err.message }); });
    }
    return box;
  }

  function rawSection() {
    const d = st.data;
    const canPick = !!project.app.state?.can_pick_file;
    const unused = d.raw.filter((f) => !f.source);
    const sourceCard = (s) => h('div', { class: `source ${s.error ? 'bad' : ''}`.trim() },
      h('div', { class: 'top' }, h('b', { class: 'mono name' }, s.name),
        h('button', { class: 'link mono', type: 'button', title: '파일 열기', onclick: () => project.openTab({ type: 'file', path: s.file }) }, s.file),
        h('span', { class: 'grow' }), s.exists ? h('span', { class: 'muted' }, `${bytes(s.size)} · ${stamp(s.mtime)}`) : null,
        s.exists ? h('button', { class: 'btn small', type: 'button', 'data-act': 'import', title: '이 파일의 틀(열 이름 줄·시점 열·결측 표시)을 고치거나 다른 열을 시리즈로 더한다', onclick: () => project.openTab({ type: 'import', file: s.file }) }, '틀·시리즈 고치기') : null),
      s.error ? h('div', { class: 'banner error' }, icon('alert'), h('div', {}, s.error))
        : h('div', { class: 'read' }, h('span', {}, `${FREQ[s.freq] || s.freq || ''} 자료`), h('span', {}, s.note), h('span', {}, `${s.rows}줄 · 열 ${s.columns.length}개`),
          s.sheet ? h('span', {}, `시트 ${s.sheet}`) : null),
      put(h('div', { class: 'made' }), h('span', { class: 'k' }, '읽는 시리즈'), s.series.length ? s.series.map((n) => h('button', { class: 'pc', type: 'button', onclick: () => { st.section = 'series'; st.open = n; st.q = ''; st.filter = 'all'; render(); } }, n))
        : h('span', { class: 'muted' }, '아직 없습니다')),
      put(h('div', { class: 'tags' }),
        s.changed ? h('span', { class: 'tag warn', title: '지금 회차를 만든 뒤 이 파일(또는 가리키는 파일)이 바뀌었습니다 — 자료 만들기로 새 회차를' }, '회차를 만든 뒤 바뀜') : null,
        s.missing_cells ? h('span', { class: 'tag', title: `결측 표시로 읽은 칸: ${s.cells.join(' · ')}` }, `결측으로 읽은 칸 ${s.missing_cells}`) : null,
        s.bad_cells ? h('span', { class: 'tag warn', title: `숫자가 아니어서 결측으로 본 칸: ${s.cells.join(' · ')}` }, `숫자가 아닌 칸 ${s.bad_cells}`) : null));
    const inboxItem = (it) => {
      const name = it.file.split('/').pop();
      const other = d.sources.filter((s) => s.name !== it.source);
      const bad = !!it.problems?.length;
      return h('div', { class: 'inbox-item' }, icon('inbox'), h('div', { class: 'grow' }, h('b', { class: 'mono' }, name),
        h('div', { class: 'muted' }, it.source ? `${it.source} 의 새 파일로 보입니다(${it.how})` : it.candidates?.length > 1 ? `짝이 여럿입니다(${it.candidates.join(' · ')}) — 골라 주세요` : '어느 원자료의 새 파일인지 모르겠습니다 — 골라 주세요'),
        bad ? h('div', { class: 'why' }, h('span', { class: 'tag warn' }, '틀이 맞지 않음'), it.problems.slice(0, 3).join(' · ')) : null),
      it.source ? h('button', { class: `btn small ${bad ? '' : 'primary'}`.trim(), type: 'button', disabled: bad, title: bad ? '틀이 맞지 않아 넣을 수 없습니다 — 파일을 고치거나 정의(series.toml)의 틀을 맞추세요' : `equion data add ${it.file} --source ${it.source} — DATA/raw/ 로 옮기고 ${it.source} 가 이 파일을 읽게 한다(틀이 맞을 때만)`,
        onclick: () => addRaw({ inbox: name, source: it.source }, name) }, `${it.source} 의 새 파일로 넣기`) : null,
      other.length || !it.source ? h('button', { class: 'btn small', type: 'button', onclick: (e) => popMenu(e.currentTarget, [h('div', { class: 'menu-title' }, '어느 원자료의 새 파일인가요'),
        ...(it.source ? other : d.sources).map((s) => ({ label: s.name, hint: `${s.file.split('/').pop()} 대신`, onPick: () => addRaw({ inbox: name, source: s.name }, name) }))], { cls: 'plain', align: 'right' }) },
      it.source ? '다른 것으로' : '고르기', icon('chevron', 'down')) : null,
      !it.source ? h('button', { class: 'btn small primary', type: 'button', title: 'DATA/raw/ 로 넣고, 열을 시리즈로 짝짓는 불러오기 화면을 연다', onclick: () => addRaw({ inbox: name }, name, 'import') }, '새 원자료로 불러오기') : null);
    };
    return h('div', {},
      h('div', { class: 'list-tools' }, h('span', { class: 'muted' }, '원자료는 고치지 않습니다. 새 파일을 받으면 넣기만 하고, 어느 열을 읽을지는 정의가 정합니다.'), h('span', { class: 'grow' }),
        h('button', { class: 'btn small', type: 'button', disabled: !canPick, title: canPick ? '파일을 골라 DATA/raw/ 에 넣는다(equion data add)' : '파일 고르기는 앱 창에서 됩니다 — 파일을 DATA/raw/inbox/ 에 놓으면 아래 받은 상자에 뜹니다',
          onclick: (e) => pickRaw(e.currentTarget) }, icon('plus'), '원자료 넣기…')),
      d.inbox.length ? h('div', { class: 'inbox' }, h('h3', { class: 'cap' }, '받은 상자', h('small', {}, ' — DATA/raw/inbox/ 에 놓인 새 파일')), d.inbox.map(inboxItem)) : null,
      h('h3', { class: 'cap' }, '정의가 읽는 파일', h('small', {}, ` — ${d.sources.length}개`)),
      d.sources.length ? d.sources.map(sourceCard) : h('div', { class: 'empty-state' }, '정의에 원자료가 없습니다.'),
      unused.length ? h('div', {}, h('h3', { class: 'cap' }, '읽지 않는 파일', h('small', {}, ' — 옛 파일은 지우지 않고 남겨 둡니다')),
        h('div', { class: 'unused' }, unused.map((f) => h('span', { class: 'unused-item' },
          h('button', { class: 'file-chip', type: 'button', title: `${bytes(f.size)} · ${stamp(f.mtime)} — 열어 본다`, onclick: () => project.openTab({ type: 'file', path: f.file }) }, f.file.split('/').pop()),
          h('button', { class: 'link', type: 'button', title: '이 파일의 열을 시리즈로 짝짓는다', onclick: () => project.openTab({ type: 'import', file: f.file }) }, '불러오기'))))) : null);
  }

  function vintageSection() {
    const d = st.data;
    const cur = current();
    if (!d.vintages.length) return h('div', { class: 'empty-state' }, '아직 만든 회차가 없습니다. 위의 ‘자료 만들기’를 누르세요.');
    const order = d.vintages.map((v) => v.id);
    // 줄마다: 이름 · 구간 · 언제 — 오른쪽에 할 수 있는 일(폭이 좁으면 아래 줄로 내려간다)
    const table = h('div', { class: 'vint-list' }, [...d.vintages].reverse().map((v) => h('div', { class: `vint ${v.current ? 'now' : ''}`.trim(), 'data-vintage': v.id },
      h('div', { class: 'vi' }, h('b', { class: 'mono' }, v.id), v.current ? h('span', { class: 'tag accent' }, '지금') : null, st.made?.id === v.id && !v.current ? h('span', { class: 'tag ok' }, '방금 만듦') : null),
      h('div', { class: 'vd' }, h('span', {}, span(...(v.span || []))), h('span', { class: 'muted' }, `시리즈 ${v.n_series}개 · ${when(v.created)}`)),
      h('div', { class: 'acts' },
        h('button', { class: 'btn small quiet', type: 'button', title: '이 회차의 카드(만든 시리즈·알아서 한 것)', onclick: () => project.openTab({ type: 'record', id: `data:${v.id}` }) }, '카드'),
        !v.current && cur ? h('button', { class: 'btn small', type: 'button', 'data-act': 'diff', 'aria-pressed': String(st.diff?.b === v.id || st.diff?.a === v.id), title: `지금 회차(${cur})와 무엇이 다른지`,
          onclick: () => (order.indexOf(v.id) < order.indexOf(cur) ? compare(v.id, cur) : compare(cur, v.id)) }, '견주기') : null,
        !v.current ? h('button', { class: 'btn small primary', type: 'button', 'data-act': 'use', title: `equion data use ${v.id}`, onclick: () => use(v.id) }, '이 회차로 바꾸기') : null))));
    return h('div', {}, table, st.diff ? diffPanel() : null,
      h('p', { class: 'foot-note' }, '회차는 ‘자료 만들기’를 누를 때 원자료나 정의가 달라져 있으면 하나 늘어납니다. 옛 회차는 지워지지 않으므로 언제든 견주거나 되돌아갈 수 있습니다.'));
  }

  function diffPanel() {
    const { a, b, data } = st.diff;
    const head = h('div', { class: 'diff-head' }, h('b', {}, h('span', { class: 'mono' }, a), ' → ', h('span', { class: 'mono' }, b)), h('span', { class: 'grow' }),
      h('button', { class: 'icon-btn', type: 'button', title: '닫기', 'aria-label': '닫기', onclick: () => { st.diff = null; render(); } }, icon('x')));
    if (!data) return h('div', { class: 'diffbox' }, head, h('div', { class: 'muted pad' }, '견주는 중…'));
    // 값이 고쳐졌거나 없어진 시리즈는 표로, 새 값만 늘어난 시리즈는 한 줄로 모은다(표가 '1기 — — —' 로 길어지지 않게)
    const rows = (data.rows || []).filter((r) => r.revised || r.lost).sort((x, y) => (y.revised - x.revised) || (y.max_pct - x.max_pct));
    const grown = (data.rows || []).filter((r) => r.new && !r.revised && !r.lost);
    const impact = data.impact;
    return h('div', { class: 'diffbox' }, head,
      h('div', { class: 'pad' }, h('p', { class: 'sum' }, changeSummary(data), data.unchanged?.length ? ` · 그대로 ${data.unchanged.length}` : ''),
        impact?.parts?.length ? h('p', { class: 'muted' }, `바뀐 시리즈를 쓰는 식 ${impact.parts.length}개(${impact.parts.slice(0, 6).join(' · ')}${impact.parts.length > 6 ? ' …' : ''}) · 모형 ${impact.models.join(' · ')} — 회차를 바꾼 뒤 다시 추정·풀기는 따로 시킵니다.`) : null),
      rows.length ? h('table', { class: 'grid plain' }, h('thead', {}, h('tr', {}, ['시리즈', '새 값', '고쳐진 값(개정)', '개정 구간', '가장 큰 차이', '(%)'].map((c, i) => h('th', { class: i ? 'num' : '' }, c)))),
        h('tbody', {}, rows.map((r) => h('tr', {}, h('td', {}, h('b', { class: 'mono' }, r.name)),
          h('td', { class: 'num' }, r.new ? `${r.new}기` : '—'), h('td', { class: `num ${r.revised ? 'alert' : ''}`.trim() }, r.revised ? `${r.revised}기` : '—'),
          h('td', { class: 'num nowrap' }, r.revised ? (r.first === r.last ? r.first : `${r.first} – ${r.last}`) : '—'),
          h('td', { class: 'num' }, r.revised ? short(r.max_abs) : '—'), h('td', { class: 'num' }, r.revised ? `${r.max_pct.toFixed(2)}%` : '—')))))
        : h('div', { class: 'muted pad' }, '값이 고쳐진 시리즈는 없습니다.'),
      grown.length ? h('div', { class: 'grown' }, h('b', {}, `새 값만 늘어난 시리즈 ${grown.length}개`), ' — ', grown.map((r) => `${r.name}(+${r.new})`).join(' · ')) : null);
  }

  function render() {
    disposeChart();
    disposeChart = () => {};
    clear(el);
    const d = st.data;
    const stale = project.dataPending() || (d && !d.current && d.mode === 'defs');
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, '자료'), h('div', { class: 'sub' }, d?.mode === 'file' ? '이 프로젝트는 자료 파일 하나를 그대로 읽습니다.'
        : '받은 파일(원자료)을 정의대로 읽어 만든 자료 한 벌이 ‘회차’입니다. 계산은 늘 지금 회차로 합니다.')),
      d?.mode === 'defs' ? h('div', { class: 'tools' }, h('button', { class: `btn ${stale ? 'primary' : ''}`.trim(), type: 'button', disabled: project.busy,
        title: 'equion data build — 원자료를 정의대로 읽어 새 회차를 만든다(내용이 같으면 만들지 않는다). 지금 회차는 바뀌지 않는다', onclick: build }, icon('refresh'), '자료 만들기')) : null));
    if (st.error) el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', { class: 'grow' }, st.error), h('button', { class: 'icon-btn', type: 'button', title: '닫기', 'aria-label': '닫기', onclick: () => { st.error = null; render(); } }, icon('x'))));
    if (st.loadError) el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, '자료를 읽지 못했습니다.', h('pre', {}, st.loadError))));
    if (!d) { if (!st.loadError) el.append(h('div', { class: 'empty-state' }, '자료를 읽는 중…')); return; }
    if (d.mode === 'file') {
      el.append(h('div', { class: 'banner info' }, icon('info'), h('div', {}, h('b', { class: 'mono' }, d.data_file || '자료 파일'), ` — ${span(...(d.span || []))}. 원자료·정의·회차로 나눠 관리하려면 `, h('code', {}, 'equion new 폴더 --template desk'),
        ' 의 예제처럼 DATA/series.toml 을 둡니다.')), seriesSection());
      return;
    }
    el.append(flow(), status(), put(h('div', { class: 'todo-slot' }), todoPanel()), st.section === 'raw' ? rawSection() : st.section === 'vintages' ? vintageSection() : seriesSection());
  }

  render();
  return {
    key: 'data', type: 'data', title: '자료', icon: 'data', el,
    desc: () => ({ type: 'data', section: st.section, open: st.open }),
    show() { if (!loaded) load(); },
    open(next) {
      if (next.section && SECTIONS.includes(next.section)) st.section = next.section;
      if (next.open) { st.open = next.open; st.section = 'series'; st.q = ''; st.filter = 'all'; }
      render();
    },
    event(e) {
      if (e.type === 'data') take();
      else if (e.type === 'job') { const b = el.querySelector('.view-head .tools .btn'); if (b) b.disabled = project.busy; }
    },
    dispose() { disposeChart(); },
  };
}
