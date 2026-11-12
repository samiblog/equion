// 시나리오 폼 (2차판 — DESK_SOLO 장면 7, D55) — 충격 표로 시나리오를 만들고 고친다. 파일은 `SCENARIOS/이름.toml` 그대로이고,
// 저장은 `equion scenario define`과 같다(무엇이 바뀌는지 차이와 명령을 먼저 보인다). 풀기는 전망 작업대와 같은 `equion sim`.
//
//   이름 [oil_krw]   설명 [유가와 환율 동반 상승]
//   가정 세트 [base ▾]  보정항 [(전망 기본값) ▾]  모형 [(전망 기본값) ▾]
//   충격     변수 [POIL] 크기 [20] [%|수준] 처음 [start] 끝 [end]  ×
//   식 보정   식 [demand:CN] 값 [-0.2] 처음 [start] 끝 [start+1]  ×
//   바뀌는 파일 SCENARIOS/oil_krw.toml (차이) · > equion scenario define …   [저장] [저장하고 풀기]

import { confirmDialog } from '../dialog.js';
import { clear, copyText, debounce, flash, h, icon } from '../util.js';
import { diffBlock } from './lists.js';

const WHEN = '기간 라벨(2026Q1) 또는 start · end · start+N · end-N — 전망 구간 기준';

function num(text) {
  const v = Number(String(text).replace(/,/g, '').trim());
  return Number.isFinite(v) ? v : null;
}

export function scenarioView(project, desc) {
  let name = desc.name || null;
  const el = h('div', { class: 'view scenario-form' });
  const st = { info: null, error: null, dry: null, dryError: null, f: null, loaded: false };

  const blankShock = () => ({ var: '', size: '', pct: true, from: 'start', to: 'end' });
  const blankAf = () => ({ eq: '', value: '', from: 'start', to: 'end' });

  function fill() {
    const sc = name ? st.info.scenarios.find((s) => s.name === name) : null;
    if (sc && !sc.error) {
      st.f = { name, desc: sc.desc || '', base: sc.base || '', addfactors: sc.addfactors || '', model: sc.model || '',
        shocks: sc.shocks.map((s) => ({ var: s.var, size: String(s.value), pct: s.kind === 'pct', from: s.from, to: s.to })),
        addfactor: sc.addfactor.map((a) => ({ eq: a.eq, value: String(a.value), from: a.from, to: a.to })) };
    } else {
      st.f = { name: name || '', desc: '', base: '', addfactors: '', model: '', shocks: [blankShock()], addfactor: [] };
      if (sc?.error) st.error = sc.error;
    }
    if (desc.draft && typeof desc.draft === 'object') Object.assign(st.f, desc.draft);
  }

  async function load() {
    st.loaded = true;
    try { st.info = await project.get('scenario-info'); st.error = null; fill(); } catch (err) { st.error = err.message; }
    render();
    preview();
  }

  /** 폼 → 서버가 받는 모양(명령줄의 --shock 글) */
  function payload() {
    const f = st.f;
    const when = (r) => ((r.from || 'start') === 'start' && (r.to || 'end') === 'end' ? '' : `@${r.from || 'start'}:${r.to || 'end'}`);
    const shocks = f.shocks.filter((r) => r.var.trim() && num(r.size) != null)
      .map((r) => `${r.var.trim()}=${num(r.size) >= 0 ? '+' : ''}${num(r.size)}${r.pct ? '%' : ''}${when(r)}`);
    const addfactor = f.addfactor.filter((r) => r.eq.trim() && num(r.value) != null)
      .map((r) => `${r.eq.trim()}=${num(r.value) >= 0 ? '+' : ''}${num(r.value)}${when(r)}`);
    return { name: f.name.trim(), desc: f.desc.trim(), base: f.base, addfactors: f.addfactors, model: f.model, shocks, addfactor };
  }

  const preview = debounce(async () => {
    const body = payload();
    if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(body.name) || body.name === 'base') { st.dry = null; st.dryError = body.name ? '이름은 영문으로 시작 — 영문·숫자·_(base 는 기준선 이름)' : '이름을 적으세요'; drawPreview(); return; }
    try { st.dry = await project.post('scenario/define', { ...body, dry: true }); st.dryError = null; } catch (err) { st.dry = null; st.dryError = err.message; }
    drawPreview();
  }, 300);

  const touched = () => { project.saveView(); preview(); };

  async function save({ solve = false } = {}) {
    const body = payload();
    try {
      const res = await project.compute('scenario/define', body, { quiet: true });
      flash(res.result.change ? `${res.result.file} 을(를) 저장했습니다` : '바뀐 것이 없습니다');
      if (!name) {                        // 새 시나리오 — 이름이 붙은 탭으로 바꿔 연다
        name = body.name;
        project.closeTab(`scenario:~new`, { select: false });
        project.openTab({ type: 'scenario', name });
      }
      project.loadOverview();
      if (solve) {
        const ran = await project.compute('sim/run', { scenarios: ['base', body.name], model: body.model || undefined }, { quiet: true });
        if (ran.result.error) project.notify({ level: 'error', text: `${ran.result.failed} 을(를) 풀지 못했습니다 — ${ran.result.error}` });
        if (ran.result.id) project.openTab({ type: 'forecast', shown: ran.result.id, scenarios: ['base', body.name] });
      } else await load();
    } catch (err) {
      if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    }
  }

  async function remove() {
    const body = h('div', { class: 'adopt' }, h('p', {}, h('b', { class: 'mono' }, `SCENARIOS/${name}.toml`), ' 을 지웁니다. 이 시나리오로 푼 기록은 그대로 남습니다.'),
      h('div', { class: 'cmd-note mono' }, `equion scenario remove ${name}`), h('p', { class: 'muted' }, '바뀜 기록에 남고, 거기서 되돌릴 수 있습니다.'));
    if (!(await confirmDialog({ title: '시나리오 지우기', body, confirm: '지우기', tone: 'danger', wide: true }))) return;
    try {
      await project.compute('scenario/remove', { name }, { quiet: true });
      project.loadOverview();
      project.closeTab(`scenario:${name}`);
    } catch (err) { if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message }); }
  }

  // ---- 그리기 -----------------------------------------------------------------------------------

  const previewBox = h('div', { class: 'sc-preview' });

  function text(value, set, attrs = {}) {
    const input = h('input', { class: 'mini-input', type: 'text', value: value ?? '', spellcheck: 'false', autocomplete: 'off', ...attrs });
    input.addEventListener('input', () => { set(input.value); touched(); });
    return input;
  }

  function select(value, options, set, label) {
    const s = h('select', { class: 'mini-select', 'aria-label': label }, options.map(([v, l]) => h('option', { value: v }, l)));
    s.value = value ?? '';
    s.addEventListener('change', () => { set(s.value); touched(); });
    return s;
  }

  function shockRows() {
    const f = st.f;
    const rows = f.shocks.map((r, i) => h('tr', { 'data-row': String(i) },
      h('td', {}, text(r.var, (v) => { r.var = v; }, { list: 'sc-series', class: 'mini-input mono', 'aria-label': '변수', placeholder: 'POIL' })),
      h('td', {}, text(r.size, (v) => { r.size = v; }, { class: 'mini-input num', 'aria-label': '크기', placeholder: '+20' })),
      h('td', {}, h('div', { class: 'segmented small' }, [[true, '%'], [false, '수준']].map(([v, l]) => h('button', {
        type: 'button', 'aria-pressed': String(r.pct === v), title: v ? '경로를 이만큼 % 올리고 내린다' : '경로에 이 값을 더한다(같은 단위)',
        onclick: (e) => { r.pct = v; for (const b of e.currentTarget.parentElement.children) b.setAttribute('aria-pressed', String(b === e.currentTarget)); touched(); },
      }, l)))),
      h('td', {}, text(r.from, (v) => { r.from = v; }, { class: 'mini-input when', 'aria-label': '처음', title: WHEN })),
      h('td', {}, text(r.to, (v) => { r.to = v; }, { class: 'mini-input when', 'aria-label': '끝', title: WHEN })),
      h('td', {}, h('button', { class: 'icon-btn', type: 'button', title: '이 충격 빼기', 'aria-label': '빼기', onclick: () => { f.shocks.splice(i, 1); render(); touched(); } }, icon('x')))));
    return h('table', { class: 'grid plain sc-table' }, h('thead', {}, h('tr', {}, ['변수', '크기', '단위', '처음', '끝', ''].map((c) => h('th', {}, c)))), h('tbody', {}, rows));
  }

  function afRows() {
    const f = st.f;
    const rows = f.addfactor.map((r, i) => h('tr', { 'data-row': String(i) },
      h('td', {}, text(r.eq, (v) => { r.eq = v; }, { list: 'sc-parts', class: 'mini-input mono', 'aria-label': '식', placeholder: 'demand:CN' })),
      h('td', {}, text(r.value, (v) => { r.value = v; }, { class: 'mini-input num', 'aria-label': '값', placeholder: '-0.2' })),
      h('td', {}, text(r.from, (v) => { r.from = v; }, { class: 'mini-input when', 'aria-label': '처음', title: WHEN })),
      h('td', {}, text(r.to, (v) => { r.to = v; }, { class: 'mini-input when', 'aria-label': '끝', title: WHEN })),
      h('td', {}, h('button', { class: 'icon-btn', type: 'button', title: '이 보정 빼기', 'aria-label': '빼기', onclick: () => { f.addfactor.splice(i, 1); render(); touched(); } }, icon('x')))));
    return h('table', { class: 'grid plain sc-table' }, h('thead', {}, h('tr', {}, ['식(블록:목표)', '값(잔차에 더함)', '처음', '끝', ''].map((c) => h('th', {}, c)))), h('tbody', {}, rows));
  }

  function drawPreview() {
    clear(previewBox);
    if (st.dryError) { previewBox.append(h('div', { class: 'banner warn' }, icon('alert'), h('div', { style: { 'white-space': 'pre-wrap' } }, st.dryError))); }
    const d = st.dry;
    if (d) {
      previewBox.append(h('h4', {}, '바뀌는 파일 ', h('span', { class: 'mono' }, d.file), d.new ? h('span', { class: 'tag accent' }, '새 시나리오') : null),
        d.diff ? diffBlock(d.diff) : h('div', { class: 'muted' }, '바뀐 것이 없습니다.'),
        h('button', { class: 'cmdline', type: 'button', title: '같은 일을 터미널에서 하는 명령 — 누르면 복사', onclick: () => copyText(d.command, '명령을 복사했습니다') },
          h('span', { class: 'prompt' }, '>'), h('span', { class: 'cmd' }, d.command), icon('copy')));
    }
    for (const b of el.querySelectorAll('[data-act="save-scenario"], [data-act="save-solve"]')) b.disabled = !d || !d.diff && !!name || project.busy;
  }

  function render() {
    clear(el);
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, icon('layers'), name ? h('span', { class: 'mono' }, name) : '새 시나리오'),
        h('div', { class: 'sub' }, '외생 변수의 경로를 바꾸는 충격과 식 보정을 적습니다 — 저장해도 풀지는 않습니다. 기준선(base)과 함께 풀어 차이를 봅니다.')),
      h('div', { class: 'tools' },
        name ? h('button', { class: 'btn quiet', type: 'button', title: '파일을 글로 본다', onclick: () => project.openTab({ type: 'file', path: `SCENARIOS/${name}.toml` }) }, icon('code'), '파일') : null,
        name ? h('button', { class: 'btn quiet', type: 'button', 'data-act': 'remove-scenario', onclick: remove }, icon('trash'), '지우기') : null)));
    if (st.error && !st.f) { el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, st.error))); return; }
    if (!st.f) { el.append(h('div', { class: 'empty-state' }, '읽는 중…')); return; }
    if (st.error) el.append(h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, `지금 파일을 읽지 못했습니다 — 저장하면 이 폼의 내용으로 바뀝니다. ${st.error}`)));
    const f = st.f;
    const info = st.info;
    const fc = info.forecast || {};
    el.append(
      h('datalist', { id: 'sc-series' }, info.series.map((s) => h('option', { value: s }))),
      h('datalist', { id: 'sc-parts' }, info.parts.map((s) => h('option', { value: s }))),
      h('div', { class: 'eq-box sc-box' },
        h('div', { class: 'sc-grid' },
          h('label', { class: 'opt' }, h('span', {}, '이름'), name ? h('b', { class: 'mono' }, name)
            : text(f.name, (v) => { f.name = v.trim(); }, { class: 'mini-input mono', 'data-field': 'name', placeholder: 'oil_krw', 'aria-label': '이름' })),
          h('label', { class: 'opt wide' }, h('span', {}, '설명'), text(f.desc, (v) => { f.desc = v; }, { class: 'mini-input wide', 'data-field': 'desc', placeholder: '유가와 환율 동반 상승', 'aria-label': '설명' })),
          h('label', { class: 'opt' }, h('span', {}, '가정 세트'), select(f.base, [['', `(전망 기본값${fc.assume ? ` ${fc.assume}` : ''})`], ...info.assumptions.map((a) => [a, a])], (v) => { f.base = v; }, '가정 세트')),
          h('label', { class: 'opt' }, h('span', {}, '보정항'), select(f.addfactors, [['', `(전망 기본값${fc.addfactors ? ` ${fc.addfactors}` : ''})`], ...info.addfactor_sets.map((a) => [a, a])], (v) => { f.addfactors = v; }, '보정항')),
          h('label', { class: 'opt' }, h('span', {}, '모형'), select(f.model, [['', `(전망 기본값${fc.model ? ` ${fc.model}` : ''})`], ...info.models.map((m) => [m, m])], (v) => { f.model = v; }, '모형'))),
        h('h3', { class: 'cap' }, '충격', h('small', {}, ' — 외생 경로를 % 또는 수준만큼(끝을 비우면 전망 끝까지)')),
        shockRows(),
        h('button', { class: 'btn small quiet', type: 'button', 'data-act': 'add-shock', onclick: () => { f.shocks.push(blankShock()); render(); } }, icon('plus'), '충격 더하기'),
        h('h3', { class: 'cap' }, '식 보정', h('small', {}, ' — 그 식의 잔차에 값을 더한다(판단)')),
        f.addfactor.length ? afRows() : null,
        h('button', { class: 'btn small quiet', type: 'button', 'data-act': 'add-af', onclick: () => { f.addfactor.push(blankAf()); render(); } }, icon('plus'), '식 보정 더하기')),
      previewBox,
      h('div', { class: 'sc-acts' },
        h('button', { class: 'btn primary', type: 'button', 'data-act': 'save-scenario', onclick: () => save() }, icon('check'), '저장'),
        h('button', { class: 'btn', type: 'button', 'data-act': 'save-solve', title: '저장한 뒤 기준선과 함께 푼다(equion sim base 이름)', onclick: () => save({ solve: true }) }, icon('play'), '저장하고 풀기')));
    drawPreview();
  }

  render();
  return {
    key: `scenario:${name || '~new'}`, type: 'scenario', title: name ? `시나리오 ${name}` : '새 시나리오', icon: 'layers', el,
    desc: () => ({ type: 'scenario', name, ...(st.f && !name ? { draft: { name: st.f.name, desc: st.f.desc } } : {}) }),
    show() { if (!st.loaded) load(); },
    event(e) { if (e.type === 'job') for (const b of el.querySelectorAll('[data-act="save-scenario"], [data-act="save-solve"]')) b.disabled = project.busy || !st.dry; },
    dispose() {},
  };
}
