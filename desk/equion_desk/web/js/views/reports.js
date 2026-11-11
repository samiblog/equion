// 보고서 — 사람의 글 사이에 기록에서 보낸 표·차트(구역)가 끼어 있는 문서(reports/*.md).
//
//   · 구역마다 어느 기록에서 왔는지가 적혀 있어, '검사'가 더 새 기록 · 낡음(자료·정의가 바뀜) · 손으로 고침 · 없는 기록을 알린다
//   · '새 기록으로 바꾸기'는 같은 모양으로 다시 만든 구역의 차이를 먼저 보이고 나서 바꾼다 — 글은 건드리지 않는다
//   · 손으로 고친 구역은 고친 곳을 보이고, 덮겠다고 할 때만 덮는다
//
// 보고서를 만드는 길은 둘: 결과 화면의 '보고서로'(표 하나를 보낸다), 여기의 '새 보고서'(빈 틀 또는 지난 보고서를 틀로).
// 글은 파일 보기의 '고치기'로 고친다. 하는 일은 모두 `equion report new·add·check·update` 와 같다.

import { confirmDialog } from '../dialog.js';
import { renderDoc } from '../md.js';
import { query } from '../api.js';
import { clear, flash, h, icon, when } from '../util.js';

const TONE = { 정상: 'ok', '더 새 기록': 'warn', 낡음: 'warn', '손으로 고침': 'info', '없는 기록': 'bad' };

/** 차이 글(unified diff) → 줄마다 색 */
function diffBox(text, limit = 60) {
  const lines = String(text || '').replace(/\n$/, '').split('\n').filter((l) => !/^(---|\+\+\+|@@)/.test(l));
  return h('div', { class: 'diff' }, lines.slice(0, limit).map((l) => h('span', { class: `dl ${l.startsWith('+') ? 'add' : l.startsWith('-') ? 'del' : ''}`.trim() }, l || ' ')),
    lines.length > limit ? h('span', { class: 'dl' }, `… ${lines.length - limit}줄 더`) : null);
}

export function reportsView(project, desc) {
  const el = h('div', { class: 'view reports' });
  const st = { list: null, error: null, name: desc.report || null, check: null, text: null, mtime: 0 };
  const body = h('div', { class: 'report-body' });
  let loaded = false;
  const save = () => project.saveView();

  async function load() {
    loaded = true;
    try {
      st.list = (await project.get('reports')).reports;
      st.error = null;
    } catch (err) {
      st.error = err.message;
      st.list = st.list || [];
    }
    if (!st.list.some((r) => r.name === st.name)) st.name = st.list[0]?.name || null;
    render();
    if (st.name) await loadReport();
  }

  async function loadReport() {
    const name = st.name;
    const item = st.list.find((r) => r.name === name);
    if (!item) return;
    try {
      const [check, file] = await Promise.all([project.get(`report/check${query({ report: name })}`), project.get(`file${query({ path: item.path })}`)]);
      if (name !== st.name) return;
      st.check = check;
      st.text = file.kind === 'text' ? file.text : '';
      st.mtime = file.mtime;
      st.error = null;
    } catch (err) {
      if (name !== st.name) return;
      st.check = null; st.text = null; st.error = err.message;
    }
    drawReport();
  }

  function pick(name) {
    if (name === st.name) return;
    Object.assign(st, { name, check: null, text: null });
    save();
    render();
    loadReport();
  }

  async function newReport() {
    const name = h('input', { class: 'mini-input wide', type: 'text', placeholder: '영문 이름 — 예: forecast_2026_12', spellcheck: 'false', 'aria-label': '보고서 이름' });
    const title = h('input', { class: 'mini-input wide plain', type: 'text', placeholder: '제목 — 예: 2026년 12월 경제전망', 'aria-label': '제목' });
    const from = h('select', { class: 'mini-select wide', 'aria-label': '틀' }, h('option', { value: '' }, '빈 틀(제목·날짜·자료 회차·모형)'),
      (st.list || []).map((r) => h('option', { value: r.name }, `지난 보고서 ${r.name}${r.title ? ` — ${r.title}` : ''}`)));
    const box = h('div', { class: 'adopt define-form' },
      h('p', {}, '보고서는 사람의 글입니다(reports/이름.md). 지난 보고서를 틀로 삼으면 글과 구역의 자리를 그대로 가져오고, 구역마다 바꿔 낄 새 기록을 알려 줍니다.'),
      h('label', { class: 'field-row' }, h('span', {}, '이름'), name), h('label', { class: 'field-row' }, h('span', {}, '제목'), title), h('label', { class: 'field-row' }, h('span', {}, '틀'), from));
    if (!(await confirmDialog({ title: '새 보고서', body: box, confirm: '만들기', wide: true }))) return;
    try {
      const res = await project.compute('report/new', { name: name.value.trim(), title: title.value.trim(), from: from.value }, { quiet: true });
      flash(`${res.result.report} 를 만들었습니다`);
      st.name = name.value.trim();
      save();
      await load();
    } catch (err) {
      if (err.kind !== 'busy') { st.error = err.message; render(); }
    }
  }

  /** 새 기록으로 바꾸기 — 먼저 무엇이 달라지는지(구역마다의 차이)를 보이고, 그 다음에 바꾼다. region: 구역 하나만 */
  async function update(region = null) {
    const name = st.name;
    let plan;
    try {
      plan = await project.post('report/update', { report: name, region, dry: true });
    } catch (err) { st.error = err.message; drawReport(); return; }
    const hand = plan.items.filter((x) => String(x.status).startsWith('손으로 고침'));
    const moved = plan.items.filter((x) => String(x.status).startsWith('바뀜'));
    const stuck = plan.items.filter((x) => x.status === '바꿀 수 없음');
    if (!moved.length && !hand.length) { flash(stuck.length ? `바꿀 수 없는 구역 ${stuck.length} — ${stuck[0].detail}` : '바꿀 것이 없습니다 — 구역이 모두 가장 새 기록과 같습니다'); return; }
    const force = h('input', { type: 'checkbox' });
    const box = h('div', { class: 'adopt' },
      h('p', {}, h('b', { class: 'mono' }, plan.report), ' 의 구역을 같은 모양의 새 기록으로 다시 만듭니다. 글은 그대로이고, 바뀜 기록에 남아 되돌릴 수 있습니다.'),
      plan.items.map((x) => h('div', { class: 'region-plan' },
        h('div', { class: 'region-line' }, h('b', {}, `#${x.n}`), h('span', { class: 'mono' }, x.record), x.to && x.to !== x.record ? [h('span', { class: 'arrow' }, '→'), h('span', { class: 'mono' }, x.to)] : null,
          h('span', { class: `tag ${String(x.status).startsWith('바뀜') ? 'accent' : String(x.status).startsWith('손으로') ? 'warn' : x.status === '바꿀 수 없음' ? 'bad' : ''}`.trim() }, String(x.status).replace(' (미리보기)', '').replace('(--force)', '').replace(/ — 바꾸지 않음$/, ''))),
        x.status === '바꿀 수 없음' ? h('div', { class: 'muted' }, x.detail) : null,
        String(x.status).startsWith('손으로 고침') ? h('div', { class: 'muted' }, '보낸 뒤 손으로 고친 구역입니다 — 고친 곳:') : null,
        x.diff ? diffBox(x.diff, 24) : null)),
      hand.length ? h('label', { class: 'check-row' }, force, h('span', {}, `손으로 고친 구역 ${hand.length}개도 새 기록으로 덮는다(고친 곳은 사라집니다)`)) : null,
      h('div', { class: 'cmd-note mono' }, plan.command));
    if (!(await confirmDialog({ title: '새 기록으로 바꾸기', body: box, confirm: moved.length ? `구역 ${moved.length}개 바꾸기` : '바꾸기', wide: true }))) return;
    if (!moved.length && !force.checked) { flash('바꾼 것이 없습니다 — 손으로 고친 구역은 그대로 두었습니다'); return; }
    try {
      const res = await project.compute('report/update', { report: name, region, force: force.checked }, { quiet: true });
      flash(res.result.change ? `구역을 바꿨습니다 — 바뀜 기록 ${res.result.change}` : '바뀐 것이 없습니다');
      await load();
    } catch (err) {
      if (err.kind !== 'busy') { st.error = err.message; drawReport(); }
    }
  }

  function checkBox() {
    const c = st.check;
    if (!c) return null;
    if (!c.items.length) {
      return h('div', { class: 'banner info' }, icon('info'), h('div', {}, '아직 기록에서 보낸 구역이 없습니다. 결과 화면(전망·과거 재현·추정·분석 기록)의 ‘보고서로’가 표를 이 보고서의 한 구역으로 보냅니다.'));
    }
    const odd = c.items.filter((x) => x.status !== '정상');
    const fresh = c.items.filter((x) => x.to);
    return h('div', { class: 'region-box' },
      h('div', { class: 'raw-cap' }, h('b', {}, '구역 검사'), h('span', { class: 'muted' }, odd.length ? ` — 손볼 구역 ${odd.length} / ${c.items.length}` : ` — 구역 ${c.items.length}개가 모두 가장 새 기록입니다`), h('span', { class: 'grow' }),
        fresh.length ? h('button', { class: 'btn small primary', type: 'button', 'data-act': 'update', disabled: project.busy, title: '구역마다 무엇이 달라지는지 먼저 보이고 나서 바꾼다(equion report update)', onclick: () => update() }, icon('refresh'), '새 기록으로 바꾸기…') : null),
      h('div', { class: 'region-rows' }, c.items.map((x) => h('div', { class: 'region-row', 'data-region': x.n },
        h('b', { class: 'n' }, `#${x.n}`),
        h('button', { class: 'link mono', type: 'button', title: '이 기록의 카드를 연다', disabled: x.status === '없는 기록', onclick: () => project.openRecord(x.record) }, x.record),
        String(x.status).split(' · ').map((s) => h('span', { class: `tag ${TONE[s] || ''}`.trim() }, s)),
        x.to ? h('span', { class: 'to' }, h('span', { class: 'arrow' }, '→'), h('span', { class: 'mono' }, x.to)) : (x.status !== '정상' && x.detail ? h('span', { class: 'muted' }, x.detail) : null),
        h('span', { class: 'grow' }),
        x.to ? h('button', { class: 'btn small quiet', type: 'button', disabled: project.busy, title: '이 구역만 새 기록으로', onclick: () => update(x.n) }, '이 구역만') : null))));
  }

  async function drawReport() {
    clear(body);
    const item = st.list?.find((r) => r.name === st.name);
    if (!item) return;
    body.append(h('div', { class: 'result-head' }, icon('doc'), h('b', { class: 'mono' }, item.name), item.title ? h('span', { class: 'meta' }, h('span', {}, item.title)) : null, h('span', { class: 'grow' }),
      h('button', { class: 'btn small', type: 'button', 'data-act': 'edit-report', title: '보고서의 글을 고친다 — 저장하면 바뀜 기록에 남는다', onclick: () => project.openTab({ type: 'file', path: item.path, edit: true }) }, icon('doc'), '글 고치기')));
    if (st.error) body.append(h('div', { class: 'banner error' }, icon('alert'), h('div', { class: 'grow' }, st.error)));
    if (st.text == null) { if (!st.error) body.append(h('div', { class: 'empty-state' }, '보고서를 읽는 중…')); return; }
    const box = checkBox();
    if (box) body.append(box);
    const doc = h('div', { class: 'report-doc' });
    body.append(doc);
    const dir = item.path.includes('/') ? item.path.slice(0, item.path.lastIndexOf('/')) : '';
    await renderDoc(doc, st.text, { pid: project.id, dir, openFile: (p) => project.openTab({ type: 'file', path: p }) });
  }

  function render() {
    clear(el);
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, '보고서'), h('div', { class: 'sub' }, '사람의 글 사이에 기록에서 보낸 표·차트가 끼어 있습니다. 새 기록으로 바꿀 때는 그 구역만 바뀝니다.')),
      h('div', { class: 'tools' }, h('button', { class: 'btn', type: 'button', 'data-act': 'new-report', onclick: newReport }, icon('plus'), '새 보고서'))));
    if (st.error && !st.name) el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', { class: 'grow' }, st.error)));
    if (!st.list) { el.append(h('div', { class: 'empty-state' }, '보고서를 읽는 중…')); return; }
    if (!st.list.length) {
      el.append(h('div', { class: 'empty-state' }, '아직 보고서가 없습니다.', h('br'), '전망이나 과거 재현 결과의 ‘보고서로’를 누르거나, 위의 ‘새 보고서’로 빈 틀을 만드세요.'));
      return;
    }
    el.append(h('div', { class: 'report-list', role: 'tablist', 'aria-label': '보고서' }, st.list.map((r) => h('button', {
      class: 'report-chip', type: 'button', role: 'tab', 'aria-selected': String(r.name === st.name), 'data-report': r.name, title: r.path, onclick: () => pick(r.name),
    }, h('b', { class: 'mono' }, r.name), h('span', { class: 'ttl' }, r.title || ''), h('small', {}, `구역 ${r.regions} · ${when(new Date(r.mtime * 1000).toISOString())}`)))), body);
    drawReport();
  }

  render();
  return {
    key: 'reports', type: 'reports', title: '보고서', icon: 'doc', el,
    desc: () => ({ type: 'reports', report: st.name }),
    show() { if (!loaded) load(); },
    open(next) { if (next.report && next.report !== st.name) { st.name = next.report; if (loaded) load(); } else if (next.report && loaded) load(); },
    event(e) {
      if ((e.type === 'defs' || e.type === 'tree' || e.type === 'record') && loaded) { if (el.isConnected && !el.parentElement.hidden && !project.busy) load(); else loaded = false; }
      else if (e.type === 'job' && !project.busy && !loaded && el.isConnected && !el.parentElement.hidden) load();
    },
    dispose() {},
  };
}
