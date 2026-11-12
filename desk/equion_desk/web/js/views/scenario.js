// 시나리오 폼 (2차판 — DESK_SOLO 장면 7, D55) — 충격 표로 시나리오를 만들고 고친다. 파일은 `SCENARIOS/이름.toml` 그대로이고,
// 저장은 `equion scenario define`과 같다(무엇이 바뀌는지 차이와 명령을 먼저 보인다). 풀기는 전망 작업대와 같은 `equion sim`.
//
//   이름 [oil_krw]   설명 [유가와 환율 동반 상승]
//   가정 세트 [base ▾]  보정항 [(전망 기본값) ▾]  모형 [(전망 기본값) ▾]
//   충격     변수 [POIL] 크기 [20] [%|수준] 처음 [start] 끝 [end]  ×
//   식 보정   식 [demand:CN] 값 [-0.2] 처음 [start] 끝 [start+1]  ×
//   바뀌는 파일 SCENARIOS/oil_krw.toml (차이) · > equion scenario define …   [저장] [저장하고 풀기]
//
// 줄마다 치는 동안 본다 — 숫자가 아닌 크기 · 읽을 수 없는 기간 · 끝보다 늦은 처음은 그 칸을 붉게 하고 까닭을 줄 아래에 적으며 저장을 막는다
// (그대로 저장하면 그 줄이 빠진 시나리오가 된다). 모형이 푸는 내생 변수에 준 충격은 막지 않고 무엇이 되는지 알린다.
// 쓰던 폼(충격 표·식 보정)은 탭과 함께 기억한다 — 닫았다 열어도 이어진다(식 작업대의 쓰던 식과 같다).

import { confirmDialog } from '../dialog.js';
import { clear, copyText, debounce, flash, h, icon } from '../util.js';
import { diffBlock } from './lists.js';

const WHEN = '기간 라벨(2026Q1) 또는 start · end · start+N · end-N — 전망 구간 기준';
const REL = /^(start|end)\s*(?:([+-])\s*(\d+))?$/i;
const FREQ_NAME = { Q: '분기(2026Q1 꼴)', M: '월(2026M3 꼴)', A: '연(2026 꼴)' };

function num(text) {
  const t = String(text ?? '').replace(/,/g, '').trim();
  if (!t) return null;
  const v = Number(t);
  return Number.isFinite(v) ? v : null;
}

/** 기간 라벨 → 차례 수(같은 주기끼리 앞뒤를 견준다). 읽을 수 없으면 null, 주기가 다르면 'freq' */
function ordinal(label, freq) {
  const t = String(label).trim();
  let m;
  if ((m = /^(\d{4})\s*[Qq]\s*([1-4])$/.exec(t))) return freq === 'Q' ? Number(m[1]) * 4 + Number(m[2]) - 1 : 'freq';
  if ((m = /^(\d{4})\s*(?:[Mm]|-)\s*(\d{1,2})$/.exec(t)) && Number(m[2]) >= 1 && Number(m[2]) <= 12) return freq === 'M' ? Number(m[1]) * 12 + Number(m[2]) - 1 : 'freq';
  if ((m = /^(\d{4})$/.exec(t))) return freq === 'A' ? Number(m[1]) : 'freq';
  return null;
}

export function scenarioView(project, desc) {
  let name = desc.name || null;
  let draft = desc.draft && typeof desc.draft === 'object' ? desc.draft : null;      // 지난번에 쓰던 폼 — 처음 읽을 때 한 번만 덮는다
  const el = h('div', { class: 'view scenario-form' });
  // asked: 미리보기를 보낸 차례 — 폼을 고친 뒤 새 미리보기가 오기 전에는 저장하지 않는다(보이는 차이 = 적힐 내용)
  const st = { info: null, error: null, dry: null, dryError: null, f: null, loaded: false, base: '', asked: 0, seen: 0 };

  const blankShock = () => ({ var: '', size: '', pct: true, from: 'start', to: 'end' });
  const blankAf = () => ({ eq: '', value: '', from: 'start', to: 'end' });
  const snap = (f) => JSON.stringify(f);
  const dirty = () => !!st.f && snap(st.f) !== st.base;

  /** 지난 폼을 받아들일 수 있는 모양으로(설정 파일에서 온 것 — 모양이 틀리면 버린다) */
  function restore(d) {
    const str = (v, dflt = '') => (typeof v === 'string' ? v.slice(0, 200) : typeof v === 'number' ? String(v) : dflt);
    const out = {};
    for (const k of ['name', 'desc', 'base', 'addfactors', 'model']) if (k in d) out[k] = str(d[k]);
    if (Array.isArray(d.shocks)) out.shocks = d.shocks.filter((r) => r && typeof r === 'object').slice(0, 100)
      .map((r) => ({ var: str(r.var), size: str(r.size), pct: r.pct !== false, from: str(r.from, 'start'), to: str(r.to, 'end') }));
    if (Array.isArray(d.addfactor)) out.addfactor = d.addfactor.filter((r) => r && typeof r === 'object').slice(0, 100)
      .map((r) => ({ eq: str(r.eq), value: str(r.value), from: str(r.from, 'start'), to: str(r.to, 'end') }));
    return out;
  }

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
    st.base = snap(st.f);
    if (draft) { Object.assign(st.f, restore(draft)); if (name) st.f.name = name; draft = null; }
  }

  async function load() {
    st.loaded = true;
    try { st.info = await project.get('scenario-info'); st.error = null; fill(); } catch (err) { st.error = err.message; }
    st.asked += 1;                // 다시 읽은 폼 — 새 미리보기가 올 때까지 저장은 기다린다
    render();
    preview();
  }

  // ---- 줄마다 보기 ------------------------------------------------------------------------------

  /** 이 시나리오를 풀 모형 — 폼에서 고른 것, 없으면 전망 기본값 */
  const modelName = () => st.f?.model || st.info?.default_model || null;

  /** 처음·끝 칸 — 까닭(막음) 또는 null. 앞뒤를 견줄 차례 수도 */
  function when(text, fallback) {
    const t = String(text || fallback).trim();
    const freq = st.info?.freq;
    const periods = st.info?.periods || [];
    const m = REL.exec(t);
    if (m) {
      if (!periods.length) return { at: null };
      const base = ordinal(m[1].toLowerCase() === 'start' ? periods[0] : periods[periods.length - 1], freq);
      return { at: typeof base === 'number' ? base + (m[2] === '-' ? -1 : 1) * Number(m[3] || 0) : null };
    }
    const o = ordinal(t, freq);
    if (o === 'freq') return { bad: `이 프로젝트의 기간은 ${FREQ_NAME[freq] || freq} 입니다` };
    if (o == null) return { bad: `‘${t}’ 는 읽을 수 없는 기간입니다 — ${WHEN}` };
    return { at: o };
  }

  /** 기간 두 칸 — 칸마다의 까닭과 줄의 까닭 */
  function span(r, bad, msgs) {
    const a = when(r.from, 'start'), b = when(r.to, 'end');
    if (a.bad) { bad.from = true; msgs.push(['bad', `처음: ${a.bad}`]); }
    if (b.bad) { bad.to = true; msgs.push(['bad', `끝: ${b.bad}`]); }
    if (!a.bad && !b.bad && a.at != null && b.at != null && a.at > b.at) {
      bad.from = bad.to = true;
      msgs.push(['bad', `처음(${r.from || 'start'})이 끝(${r.to || 'end'})보다 늦습니다 — 이대로면 아무 기간에도 충격이 없습니다`]);
    }
  }

  /** 줄마다의 문제 — {shocks: [{bad: {칸: true}, msgs: [[종류, 글]]}], addfactor: […], blocking} */
  function problems() {
    const f = st.f;
    const info = st.info;
    const out = { shocks: [], addfactor: [], blocking: 0 };
    if (!f || !info) return out;
    const series = new Map(info.series.map((s) => [s.toUpperCase(), s]));
    const model = modelName();
    const mv = model ? info.model_vars?.[model] : null;
    const upper = (xs) => new Set((xs || []).map((x) => x.toUpperCase()));
    const eq = upper(mv?.equation), ident = upper(mv?.identity), exo = upper(mv?.exogenous);
    for (const r of f.shocks) {
      const bad = {}, msgs = [];
      const v = r.var.trim(), size = String(r.size).trim();
      if (v || size) {
        if (!v) { bad.var = true; msgs.push(['bad', '변수를 적으세요']); }
        if (!size) { bad.size = true; msgs.push(['bad', '크기를 적으세요 — 예: 20(%) 또는 0.5(수준)']); } else if (num(size) == null) { bad.size = true; msgs.push(['bad', `크기 ‘${size}’ 는 숫자가 아닙니다 — 이대로 저장하면 이 충격이 빠집니다`]); }
        span(r, bad, msgs);
        const V = v.toUpperCase();
        if (v && !/^[A-Za-z_][A-Za-z0-9_]*$/.test(v)) { bad.var = true; msgs.push(['bad', `‘${v}’ 는 변수 이름이 아닙니다(영문·숫자·_)`]); } else if (v && mv) {
          if (ident.has(V)) { bad.var = true; msgs.push(['bad', `${v} 는 모형 ${model} 의 항등식이 푸는 변수라 충격을 줄 수 없습니다 — 그 항등식이 쓰는 외생 변수에 주세요`]); }
          else if (eq.has(V)) msgs.push(['warn', `${v} 는 모형 ${model} 의 식이 푸는 내생 변수입니다 — 경로를 바꾸지 않고 그 식의 잔차에 ${size || '크기'}${r.pct ? '(%가 아니라 그 값 그대로)' : ''}를 더합니다(식 보정과 같다). 외생 변수의 경로를 바꾸려면 외생 변수를 고르세요.`]);
          else if (!exo.has(V)) msgs.push(['warn', `${v} 는 모형 ${model} 이 쓰지 않는 변수입니다 — 이대로 풀면 오류가 납니다`]);
        } else if (v && !series.has(V)) msgs.push(['warn', `${v} 는 자료에 없는 변수입니다`]);
      }
      out.shocks.push({ bad, msgs });
    }
    const parts = new Set(info.parts.map((p) => p.toLowerCase()));
    for (const r of f.addfactor) {
      const bad = {}, msgs = [];
      const e = r.eq.trim(), value = String(r.value).trim();
      if (e || value) {
        if (!e) { bad.eq = true; msgs.push(['bad', '식을 고르세요(블록:목표)']); } else if (!parts.has(e.toLowerCase())) { bad.eq = true; msgs.push(['bad', `‘${e}’ 는 이 프로젝트에 없는 식입니다 — 목록에서 고르세요(블록:목표, 예: ${info.parts[0] || 'demand:CN'})`]); }
        if (!value) { bad.value = true; msgs.push(['bad', '값을 적으세요 — 그 식의 잔차에 더할 값']); } else if (num(value) == null) { bad.value = true; msgs.push(['bad', `값 ‘${value}’ 는 숫자가 아닙니다 — 이대로 저장하면 이 보정이 빠집니다`]); }
        span(r, bad, msgs);
      }
      out.addfactor.push({ bad, msgs });
    }
    out.blocking = [...out.shocks, ...out.addfactor].filter((x) => x.msgs.some(([k]) => k === 'bad')).length;
    return out;
  }

  /** 칸의 붉은 표시와 줄 아래의 까닭을 맞춘다(다시 그리지 않는다 — 치던 칸의 커서가 그대로) */
  function paintChecks() {
    const p = problems();
    for (const [table, list] of [['shock', p.shocks], ['af', p.addfactor]]) {
      list.forEach((x, i) => {
        const row = el.querySelector(`.sc-table[data-table="${table}"] tr[data-row="${i}"]`);
        const msg = el.querySelector(`.sc-table[data-table="${table}"] tr[data-msg="${i}"]`);
        if (!row || !msg) return;
        for (const input of row.querySelectorAll('input[data-field]')) {
          const bad = !!x.bad[input.dataset.field];
          input.classList.toggle('bad', bad);
          input.setAttribute('aria-invalid', String(bad));
        }
        const cell = clear(msg.firstChild);
        msg.hidden = !x.msgs.length;
        for (const [kind, text] of x.msgs) cell.append(h('div', { class: `sc-why ${kind}` }, icon('alert'), h('span', {}, text)));
      });
    }
    const box = el.querySelector('.sc-blocked');
    if (box) {
      box.hidden = !p.blocking;
      box.textContent = p.blocking ? `고칠 줄이 ${p.blocking}개 있습니다 — 붉은 칸을 고치면 저장할 수 있습니다(고치지 않은 줄은 아래 차이에 빠져 있습니다).` : '';
    }
    return p;
  }

  const canSave = (p = problems()) => !!st.dry && st.seen === st.asked && !(!st.dry.diff && !!name) && !project.busy && !p.blocking;
  const syncButtons = (p) => { for (const b of el.querySelectorAll('[data-act="save-scenario"], [data-act="save-solve"]')) b.disabled = !canSave(p); };

  /** 폼 → 서버가 받는 모양(명령줄의 --shock 글). 고칠 칸이 있는 줄은 빼고 보낸다(미리보기는 그 줄 없이 — 저장은 막힌다) */
  function payload() {
    const f = st.f;
    const p = problems();
    const ok = (list, i) => !Object.keys(list[i]?.bad || {}).length;
    const when = (r) => ((r.from || 'start') === 'start' && (r.to || 'end') === 'end' ? '' : `@${r.from || 'start'}:${r.to || 'end'}`);
    const shocks = f.shocks.filter((r, i) => r.var.trim() && num(r.size) != null && ok(p.shocks, i))
      .map((r) => `${r.var.trim()}=${num(r.size) >= 0 ? '+' : ''}${num(r.size)}${r.pct ? '%' : ''}${when(r)}`);
    const addfactor = f.addfactor.filter((r, i) => r.eq.trim() && num(r.value) != null && ok(p.addfactor, i))
      .map((r) => `${r.eq.trim()}=${num(r.value) >= 0 ? '+' : ''}${num(r.value)}${when(r)}`);
    return { name: f.name.trim(), desc: f.desc.trim(), base: f.base, addfactors: f.addfactors, model: f.model, shocks, addfactor };
  }

  const preview = debounce(async () => {
    const body = payload();
    const asked = st.asked;
    if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(body.name) || body.name === 'base') { st.dry = null; st.seen = asked; st.dryError = body.name ? '이름은 영문으로 시작 — 영문·숫자·_(base 는 기준선 이름)' : '이름을 적으세요'; drawPreview(); return; }
    let dry = null, error = null;
    try { dry = await project.post('scenario/define', { ...body, dry: true }); } catch (err) { error = err.message; }
    if (asked !== st.asked) return;          // 그 사이에 또 고쳤다 — 늦게 온 답은 버린다
    Object.assign(st, { dry, dryError: error, seen: asked });
    drawPreview();
  }, 300);

  const touched = () => { st.asked += 1; project.saveView(); syncButtons(paintChecks()); preview(); };

  async function save({ solve = false } = {}) {
    if (problems().blocking) { paintChecks(); flash('붉은 칸을 먼저 고치세요'); return; }
    const body = payload();
    try {
      const res = await project.compute('scenario/define', body, { quiet: true });
      flash(res.result.change ? `${res.result.file} 을(를) 저장했습니다` : '바뀐 것이 없습니다');
      st.base = snap(st.f);             // 저장한 폼 — 닫을 때 묻지 않는다
      if (!name) {                        // 새 시나리오 — 이름이 붙은 탭으로 바꿔 연다
        name = body.name;
        project.closeTab(`scenario:~new`, { select: false, ask: false });
        project.openTab({ type: 'scenario', name });
      }
      project.loadOverview();
      if (solve) {
        const ran = await project.compute('sim/run', { scenarios: ['base', body.name], model: body.model || undefined }, { quiet: true });
        if (ran.result.error) project.notify({ level: 'error', text: `${ran.result.failed} 을(를) 풀지 못했습니다 — ${ran.result.error}` });
        // 함께 푼 기준선은 나란히 견주게 고른다 — 전망 화면의 '풀기'와 같다
        if (ran.result.id) project.openTab({ type: 'forecast', shown: ran.result.id, scenarios: ['base', body.name], compare: (ran.result.ids || []).slice(0, -1) });
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
      project.closeTab(`scenario:${name}`, { ask: false });
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

  /** 줄 아래의 까닭 칸(처음에는 숨김 — paintChecks 가 채운다) */
  const msgRow = (i, span) => h('tr', { class: 'sc-msg', 'data-msg': String(i), hidden: true }, h('td', { colspan: String(span) }));

  function shockRows() {
    const f = st.f;
    const rows = f.shocks.flatMap((r, i) => [h('tr', { 'data-row': String(i) },
      h('td', {}, text(r.var, (v) => { r.var = v; }, { list: 'sc-series', class: 'mini-input mono', 'aria-label': '변수', placeholder: 'POIL', 'data-field': 'var' })),
      h('td', {}, text(r.size, (v) => { r.size = v; }, { class: 'mini-input num', 'aria-label': '크기', placeholder: '+20', inputmode: 'decimal', 'data-field': 'size' })),
      h('td', {}, h('div', { class: 'segmented small' }, [[true, '%'], [false, '수준']].map(([v, l]) => h('button', {
        type: 'button', 'aria-pressed': String(r.pct === v), title: v ? '경로를 이만큼 % 올리고 내린다' : '경로에 이 값을 더한다(같은 단위)',
        onclick: (e) => { r.pct = v; for (const b of e.currentTarget.parentElement.children) b.setAttribute('aria-pressed', String(b === e.currentTarget)); touched(); },
      }, l)))),
      h('td', {}, text(r.from, (v) => { r.from = v; }, { class: 'mini-input when', 'aria-label': '처음', title: WHEN, 'data-field': 'from' })),
      h('td', {}, text(r.to, (v) => { r.to = v; }, { class: 'mini-input when', 'aria-label': '끝', title: WHEN, 'data-field': 'to' })),
      h('td', {}, h('button', { class: 'icon-btn', type: 'button', title: '이 충격 빼기', 'aria-label': '빼기', onclick: () => { f.shocks.splice(i, 1); render(); touched(); } }, icon('x')))),
    msgRow(i, 6)]);
    return h('table', { class: 'grid plain sc-table', 'data-table': 'shock' }, h('thead', {}, h('tr', {}, ['변수', '크기', '단위', '처음', '끝', ''].map((c) => h('th', {}, c)))), h('tbody', {}, rows));
  }

  function afRows() {
    const f = st.f;
    const rows = f.addfactor.flatMap((r, i) => [h('tr', { 'data-row': String(i) },
      h('td', {}, text(r.eq, (v) => { r.eq = v; }, { list: 'sc-parts', class: 'mini-input mono', 'aria-label': '식', placeholder: 'demand:CN', 'data-field': 'eq' })),
      h('td', {}, text(r.value, (v) => { r.value = v; }, { class: 'mini-input num', 'aria-label': '값', placeholder: '-0.2', inputmode: 'decimal', 'data-field': 'value' })),
      h('td', {}, text(r.from, (v) => { r.from = v; }, { class: 'mini-input when', 'aria-label': '처음', title: WHEN, 'data-field': 'from' })),
      h('td', {}, text(r.to, (v) => { r.to = v; }, { class: 'mini-input when', 'aria-label': '끝', title: WHEN, 'data-field': 'to' })),
      h('td', {}, h('button', { class: 'icon-btn', type: 'button', title: '이 보정 빼기', 'aria-label': '빼기', onclick: () => { f.addfactor.splice(i, 1); render(); touched(); } }, icon('x')))),
    msgRow(i, 5)]);
    return h('table', { class: 'grid plain sc-table', 'data-table': 'af' }, h('thead', {}, h('tr', {}, ['식(블록:목표)', '값(잔차에 더함)', '처음', '끝', ''].map((c) => h('th', {}, c)))), h('tbody', {}, rows));
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
    syncButtons(paintChecks());
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
          h('label', { class: 'opt' }, h('span', {}, '모형'), select(f.model, [['', `(전망 기본값${info.default_model ? ` ${info.default_model}` : ''})`], ...info.models.map((m) => [m, m])], (v) => { f.model = v; }, '모형'))),
        h('h3', { class: 'cap' }, '충격', h('small', {}, ' — 외생 경로를 % 또는 수준만큼(끝을 비우면 전망 끝까지)')),
        shockRows(),
        h('button', { class: 'btn small quiet', type: 'button', 'data-act': 'add-shock', onclick: () => { f.shocks.push(blankShock()); render(); project.saveView(); } }, icon('plus'), '충격 더하기'),
        h('h3', { class: 'cap' }, '식 보정', h('small', {}, ' — 그 식의 잔차에 값을 더한다(판단)')),
        f.addfactor.length ? afRows() : null,
        h('button', { class: 'btn small quiet', type: 'button', 'data-act': 'add-af', onclick: () => { f.addfactor.push(blankAf()); render(); project.saveView(); } }, icon('plus'), '식 보정 더하기')),
      h('div', { class: 'banner warn sc-blocked', hidden: true, role: 'status' }),
      previewBox,
      h('div', { class: 'sc-acts' },
        h('button', { class: 'btn primary', type: 'button', 'data-act': 'save-scenario', onclick: () => save() }, icon('check'), '저장'),
        h('button', { class: 'btn', type: 'button', 'data-act': 'save-solve', title: '저장한 뒤 기준선과 함께 푼다(equion sim base 이름)', onclick: () => save({ solve: true }) }, icon('play'), '저장하고 풀기')));
    drawPreview();
  }

  render();
  return {
    key: `scenario:${name || '~new'}`, type: 'scenario', title: name ? `시나리오 ${name}` : '새 시나리오', icon: 'layers', el,
    // 쓰던 폼은 파일과 다를 때만 함께 적는다(닫았다 열면 이어진다). 읽기 전이면 지난번 것을 그대로
    desc: () => ({ type: 'scenario', name, ...(st.f ? (dirty() ? { draft: st.f } : {}) : draft ? { draft } : {}) }),
    unsaved: () => {
      if (st.f ? !dirty() : !draft) return null;
      return `${name ? `시나리오 ${name}` : '새 시나리오'} 에 저장하지 않은 고침이 있습니다 — 닫으면 충격 표와 식 보정의 고침을 버립니다.`;
    },
    show() { if (!st.loaded) load(); },
    event(e) { if (e.type === 'job') syncButtons(); },
    dispose() {},
  };
}
