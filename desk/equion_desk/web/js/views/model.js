// 모형 작업대 — 모형 하나가 무엇으로 이루어지고(W0 조립), 과거를 얼마나 잘 재현하는지(W2).
//
//   ① 조립        블록과 식 · 내생과 외생 · 블록 사이의 연결 · 풀이 순서 · 문제 — 계산하지 않고 파일을 읽어 검사한다
//   ② 과거 재현   모형이나 블록 하나를 풀고(단추를 누를 때만) 변수마다의 오차, 기간마다의 풀이 상태, 실측과 해를 본다
//                 변수를 누르면 '원인 따라가기' — 그 식의 입력마다 오차가 얼마인지 보고 거슬러 올라간다
//
// 모형을 고치는 일(블록·끼울 모형·뺄 식)과 새 모형·새 블록은 무엇이 equion.toml 에 적히는지 보이고 나서 한다(`equion model define`·
// `equion block define`). 블록 파일의 식은 파일 보기의 '고치기'로. 푼 기록은 고치지 않는다 — 다시 풀면 새 기록이 생긴다.

import { drawLines } from '../chart.js';
import { claudeButton } from '../claude.js';
import { confirmDialog, nameRule } from '../dialog.js';
import { clear, cmdText, copyText, flash, h, icon, kindPill, put, when, whoLabel } from '../util.js';
import { diffBlock } from './lists.js';

const STATUS = { ok: ['정상', 'ok'], partial: ['일부식 제외', 'warn'], fallback: ['실패대체', 'bad'], failed: ['실패', 'bad'] };
const MODES = [['dynamic', '동태 — 풀린 값을 다음 기에 쓴다'], ['static', '정태 — 시차에는 실측을'], ['fit', '식마다 — 다른 변수는 실측을']];
const SECTIONS = ['assembly', 'hs'];
const pct = (v, digits = 2) => (v == null ? '—' : `${v.toFixed(digits)}%`);
const signed = (v) => (v == null ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(3)}`);

export function modelView(project, desc) {
  const el = h('div', { class: 'view model' });
  const st = {
    model: desc.model, section: SECTIONS.includes(desc.section) ? desc.section : 'assembly', asm: null, error: null,
    run: { target: desc.target || desc.model, start: desc.start || '', end: desc.end || '', mode: desc.mode || 'dynamic' },
    shown: desc.shown || null, vs: desc.vs || null, view: null, vsView: null, pick: desc.pick || null, path: [], series: null, trace: null, more: false,
  };
  let disposeChart = () => {};
  let loaded = false;
  const save = () => project.saveView();
  const report = () => st.asm?.report || null;

  // ---- 읽기 -------------------------------------------------------------------------------------

  async function loadAssembly() {
    loaded = true;
    try {
      st.asm = await project.get(`assembly?model=${encodeURIComponent(st.model)}`);
      st.error = st.asm.error;
    } catch (err) {
      st.error = err.message;
    }
    if (!st.shown) st.shown = runs()[0]?.id || null;
    render();
    if (st.shown && !st.view) showRun(st.shown);
  }

  /** 이 모형(과 그 블록)의 과거 재현 기록 — 새것부터 */
  function runs() {
    const blocks = new Set((report()?.parts || []).map((p) => p.block));
    return project.records.filter((r) => r.kind === 'hs' && (r.target === st.model || blocks.has(r.target))).reverse();
  }

  async function showRun(id, { keepPick = true } = {}) {
    st.shown = id;
    if (st.vs === id) st.vs = null;
    if (!keepPick) { st.pick = null; st.path = []; }
    st.series = null; st.trace = null;
    save();
    try {
      st.view = await project.get(`hs/view?id=${encodeURIComponent(id)}`);
      project.seen(id);
      st.vsView = st.vs ? await project.get(`hs/view?id=${encodeURIComponent(st.vs)}`).catch(() => null) : null;
      st.error = null;
    } catch (err) {
      st.view = null;
      st.shown = null;
      st.error = err.message;
    }
    if (st.pick && !st.view?.stats.some((s) => s.name === st.pick)) st.pick = null;
    render();
    if (st.pick) loadPick();
  }

  async function loadPick() {
    const name = st.pick;
    const id = st.shown;
    if (!name || !id) return;
    try {
      const [series, trace, other] = await Promise.all([
        project.get(`hs/series?id=${encodeURIComponent(id)}&names=${encodeURIComponent(name)}`),
        project.get(`trace?id=${encodeURIComponent(id)}&name=${encodeURIComponent(name)}`),
        st.vs ? project.get(`hs/series?id=${encodeURIComponent(st.vs)}&names=${encodeURIComponent(name)}`).catch(() => null) : null]);
      if (st.pick !== name || st.shown !== id) return;
      st.series = { ...series, other };
      st.trace = trace;
    } catch (err) {
      if (st.pick !== name) return;
      st.error = err.message;
    }
    drawDetail();
  }

  function pickVar(name, { follow = false } = {}) {
    if (follow && st.pick && st.pick !== name) st.path = [...st.path.filter((p) => p !== st.pick), st.pick];
    else if (!follow) st.path = [];
    st.pick = name;
    st.path = st.path.filter((p) => p !== name);
    st.series = null; st.trace = null;
    save();
    render();
    loadPick();
  }

  // ---- 하는 일 ----------------------------------------------------------------------------------

  function runCommand() {
    const r = st.run;
    return ['equion hs', r.target, r.start || r.end ? `--range ${r.start || 'first'}:${r.end || 'last'}` : '', r.mode !== 'dynamic' ? `--mode ${r.mode}` : ''].filter(Boolean).join(' ');
  }

  async function solve(extra = {}) {
    const r = { ...st.run, ...extra };
    try {
      const res = await project.compute('hs/run', { target: r.target, start: r.start.trim(), end: r.end.trim(), mode: r.mode }, { quiet: true });
      st.section = 'hs';
      const before = st.shown;
      if (extra.compare && before) st.vs = before;         // 방금 보던 것과 견준다(블록만 풀기·식마다 풀기)
      await showRun(res.result.id);
    } catch (err) {
      if (err.kind !== 'busy') { st.error = err.message; render(); }
    }
  }

  async function replay() {
    try {
      const res = await project.compute('hs/replay', { record: st.shown }, { quiet: true });
      const r = res.result.replay || {};
      flash(r.same ? `그때와 같은 숫자입니다(가장 큰 차이 ${Number(r.max_abs_diff || 0).toExponential(1)})` : '그때와 다른 숫자가 나왔습니다 — 기록을 확인하세요');
      render();
    } catch (err) {
      if (err.kind !== 'busy') { st.error = err.message; render(); }
    }
  }

  async function solo(part) {
    try {
      await project.compute('est', { target: part, sim: true }, { quiet: true });
      loadPick();
    } catch (err) {
      if (err.kind !== 'busy') { st.error = err.message; render(); }
    }
  }

  /** 모형 고치기·새 모형 — 고르고 → 무엇이 적히는지 보고 → 저장 */
  async function defineModel(isNew) {
    const o = project.overview;
    const spec = isNew ? { name: '', desc: '', blocks: [], include: [], exclude: [] } : st.asm.spec;
    const name = h('input', { class: 'mini-input wide', type: 'text', value: spec.name, placeholder: '영문 이름 — 예: main_labor', spellcheck: 'false', disabled: !isNew, 'aria-label': '모형 이름' });
    const text = h('input', { class: 'mini-input wide plain', type: 'text', value: spec.desc || '', placeholder: '한 줄 설명', 'aria-label': '설명' });
    const picked = { blocks: new Set(spec.blocks), include: new Set(spec.include), exclude: new Set(spec.exclude) };
    const chips = (key, items, cls = '') => h('div', { class: 'chip-set' }, items.length ? items.map((item) => {
      const b = h('button', { class: `pc ${cls}`.trim(), type: 'button', 'aria-pressed': String(picked[key].has(item)), 'data-pick': `${key}:${item}` }, item);
      b.addEventListener('click', () => { if (picked[key].has(item)) picked[key].delete(item); else picked[key].add(item); b.setAttribute('aria-pressed', String(picked[key].has(item))); b.dispatchEvent(new Event('dialog-check', { bubbles: true })); });
      return b;
    }) : h('span', { class: 'muted' }, '없습니다'));
    const parts = o.blocks.flatMap((b) => b.parts.filter((p) => p.kind !== 'identity').map((p) => p.id));
    const form = h('div', { class: 'adopt define-form' },
      h('label', { class: 'field-row' }, h('span', {}, '이름'), name),
      h('label', { class: 'field-row' }, h('span', {}, '설명'), text),
      h('div', { class: 'field-row top' }, h('span', {}, '블록'), chips('blocks', o.blocks.map((b) => b.name))),
      h('div', { class: 'field-row top' }, h('span', { title: '다른 모형을 통째로 끼운다 — 그 모형이 바뀌면 함께 바뀐다' }, '끼울 모형'), chips('include', o.models.map((m) => m.name).filter((m) => m !== spec.name))),
      h('div', { class: 'field-row top' }, h('span', { title: '뺀 식의 목표는 외생(실측)이 된다' }, '뺄 식'), chips('exclude', parts)),
      h('p', { class: 'muted' }, '누르면 다음 상자에서 equion.toml 에 적힐 줄을 보입니다 — 거기서 저장합니다.'));
    // 새 모형은 이름과 블록(또는 끼울 모형)이 있어야 다음으로 — 빈 채로 누르면 무엇을 적을지 단추 옆에 보인다
    const valid = () => {
      const r = isNew ? nameRule(name.value, { what: '모형 이름' }) : true;
      if (r !== true) return r;
      return picked.blocks.size || picked.include.size ? true : '블록이나 끼울 모형을 하나 이상 고르세요';
    };
    if (!(await confirmDialog({ title: isNew ? '새 모형' : `모형 ${spec.name} 고치기`, body: form, confirm: '바뀔 내용 보기', wide: true, valid, enter: true }))) return;
    const body = { name: name.value.trim(), desc: text.value.trim(), blocks: [...picked.blocks], include: [...picked.include], exclude: [...picked.exclude] };
    await writeDefinition('model/define', body, isNew ? '새 모형' : '모형 고치기', (res) => {
      if (isNew) project.openTab({ type: 'model', model: res.name });
      else loadAssembly();
    });
  }

  async function defineBlock() {
    const name = h('input', { class: 'mini-input wide', type: 'text', placeholder: '영문 이름 — 예: labor', spellcheck: 'false', 'aria-label': '블록 이름' });
    const text = h('input', { class: 'mini-input wide plain', type: 'text', placeholder: '한 줄 설명 — 예: 노동', 'aria-label': '설명' });
    const form = h('div', { class: 'adopt define-form' }, h('p', {}, '블록은 방정식 파일 하나입니다. 빈 파일(EQUATIONS/이름.txt)을 만들고 equion.toml 의 [block] 에 적습니다 — 식은 그 파일에 한 줄에 하나씩 적고, 모형에는 ‘모형 고치기’로 넣습니다.'),
      h('label', { class: 'field-row' }, h('span', {}, '이름'), name), h('label', { class: 'field-row' }, h('span', {}, '설명'), text));
    if (!(await confirmDialog({ title: '새 블록', body: form, confirm: '바뀔 내용 보기', wide: true, valid: () => nameRule(name.value, { what: '블록 이름' }), enter: true }))) return;
    await writeDefinition('block/define', { name: name.value.trim(), desc: text.value.trim() }, '새 블록', (res) => {
      if (res.files?.[0]) project.openTab({ type: 'file', path: res.files[0], edit: true });
    });
  }

  async function writeDefinition(path, body, title, then) {
    let plan;
    try { plan = await project.post(path, { ...body, dry: true }); } catch (err) { st.error = err.message; render(); return; }
    st.error = null;
    if (plan.same) { flash('바뀐 것이 없습니다'); return; }
    const box = h('div', { class: 'adopt' },
      plan.files?.length ? h('p', {}, '새 파일 ', plan.files.map((f) => h('b', { class: 'mono' }, f)), ' 을(를) 함께 만듭니다.') : null,
      h('h4', {}, '바뀌는 파일 ', h('span', { class: 'mono' }, plan.path)), diffBlock(plan.diff),
      h('h4', {}, '같은 일을 하는 명령'), h('div', { class: 'readonly-eq compact' }, plan.command),
      h('p', { class: 'muted' }, '주석과 순서는 그대로 둡니다. 바뀜 기록에 남고, 거기서 되돌릴 수 있습니다.'));
    if (!(await confirmDialog({ title, body: box, confirm: '저장', wide: true }))) return;
    try {
      const res = await project.compute(path, body, { quiet: true });
      flash(`저장했습니다 — 바뀜 기록 ${res.result.change}`);
      await project.loadOverview();
      then(res.result);
    } catch (err) {
      if (err.kind !== 'busy') { st.error = err.message; render(); }
    }
  }

  // ---- 그리기: 조립 -----------------------------------------------------------------------------

  function flow() {
    const r = report();
    const last = runs()[0];
    const card = (key, n, title, big, small, mark) => h('button', { class: `flow-card ${st.section === key ? 'on' : ''}`.trim(), type: 'button', 'aria-pressed': String(st.section === key),
      onclick: () => { st.section = key; render(); save(); } }, h('span', { class: 'step' }, n), h('span', { class: 'ft' }, title, mark ? h('span', { class: `dot ${mark}` }) : null), h('span', { class: 'fb' }, big), h('span', { class: 'fs' }, small));
    const sim = project.records.filter((x) => x.kind === 'sim' && x.target === st.model).pop();
    return h('div', { class: 'flow', role: 'tablist', 'aria-label': '조립 · 과거 재현 · 전망' },
      card('assembly', '1', '조립', r ? `식 ${r.parts.length}개` : '—', r ? (r.problems.length ? `문제 ${r.problems.length}` : `내생 ${r.endogenous.length} · 외생 ${r.exogenous.length}`) : '', r ? (r.problems.length ? 'bad' : 'ok') : ''),
      h('span', { class: 'flow-arrow', 'aria-hidden': 'true' }, icon('arrow')),
      card('hs', '2', '과거 재현', last ? last.id.replace(/^hs:/, '') : '아직 풀지 않았습니다', last ? (last.metric || '') : '풀기를 누르세요', ''),
      h('span', { class: 'flow-arrow', 'aria-hidden': 'true' }, icon('arrow')),
      h('button', { class: 'flow-card go', type: 'button', 'data-act': 'to-forecast', title: '전망 작업대를 연다 — 가정을 적고 기준선과 시나리오를 푼다',
        onclick: () => project.openTab({ type: 'forecast', model: st.model, ...(sim ? { shown: sim.id } : {}) }) },
      h('span', { class: 'step' }, '3'), h('span', { class: 'ft' }, '전망', icon('external')), h('span', { class: 'fb' }, sim ? sim.id.replace(/^sim:/, '') : '전망 작업대'),
      h('span', { class: 'fs' }, sim ? (sim.metric || '가정 · 시나리오 · 결과') : '가정 · 시나리오 · 결과')));
  }

  function assemblySection() {
    const r = report();
    if (!r) return h('div', { class: 'empty-state' }, st.error ? '' : '조립을 읽는 중…');
    const out = h('div', {});
    if (r.problems.length) {
      out.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, h('b', {}, `조립에 문제가 ${r.problems.length}개 있습니다`), ' — 풀기 전에 고쳐야 합니다.',
        h('ul', { class: 'plain-list' }, r.problems.map((p) => h('li', {}, p))))));
    } else {
      const simultaneous = r.blocks.filter((b) => b.type === '동시').length;
      out.append(h('div', { class: 'banner ok' }, icon('check'), h('div', {}, h('b', {}, '조립에 문제가 없습니다'), ` — ${r.composition}. 추정식 ${r.parts.filter((p) => p.kind !== 'identity').length} · 항등식 ${r.parts.filter((p) => p.kind === 'identity').length}`
        + ` · 내생 ${r.endogenous.length} · 외생 ${r.exogenous.length} · 풀이 블록 ${r.blocks.length}(동시 ${simultaneous})`)));
    }
    for (const w of r.warnings || []) out.append(h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, w)));

    // 구성 — 블록마다 식. 끼운 모형에서 온 블록에는 어디서 왔는지
    const from = {};
    for (const [m, blocks] of Object.entries(r.includes || {})) for (const b of blocks) from[b] = m;
    const byBlock = new Map();
    for (const p of r.parts) { if (!byBlock.has(p.block)) byBlock.set(p.block, []); byBlock.get(p.block).push(p); }
    const excluded = new Set(r.excluded);
    const info = Object.fromEntries((st.asm.blocks || []).map((b) => [b.name, b]));
    out.append(h('h2', { class: 'sect' }, '구성', h('span', { class: 'count' }, `블록 ${byBlock.size}`)),
      h('div', { class: 'blocks' }, [...byBlock.entries()].map(([block, parts]) => h('div', { class: 'block-row asm' },
        h('div', { class: 'bn' }, h('span', { class: 'mono' }, block), h('small', {}, info[block]?.desc || ''), from[block] ? h('span', { class: 'tag', title: `끼운 모형 ${from[block]} 에서 온 블록` }, `${from[block]} 에서`) : null),
        h('div', { class: 'parts' }, parts.map((p) => h('button', { class: 'part-chip', type: 'button', title: `${p.text}\n${p.where}`, onclick: () => project.openTab({ type: 'bench', part: p.id }) },
          h('span', { class: `glyph ${p.kind === 'identity' ? 'identity' : ''}` }, p.kind === 'identity' ? '≡' : 'ƒ'), h('b', {}, p.target), p.desc ? h('small', {}, p.desc) : null,
          p.adopted ? h('span', { class: 'star', title: `채택: ${p.adopted}` }, '★') : null)),
        [...excluded].filter((x) => x.startsWith(`${block}:`)).map((x) => h('span', { class: 'part-chip out', title: '이 모형에서는 뺀 식 — 그 목표는 외생(실측)입니다' }, h('b', {}, x.split(':')[1]), h('small', {}, '뺌')))),
        h('div', { class: 'side-acts' },
          r.used_by[block]?.length ? h('span', { class: 'muted', title: '이 블록을 쓰는 다른 모형 — 블록 파일을 고치면 함께 바뀝니다' }, `함께 쓰는 모형 ${r.used_by[block].join(' · ')}`) : null,
          info[block] ? h('button', { class: 'btn small quiet', type: 'button', title: `${info[block].file} 을(를) 고친다`, onclick: () => project.openTab({ type: 'file', path: info[block].file, edit: true }) }, icon('doc'), '식 고치기') : null)))));

    // 연결과 풀이 순서
    const links = new Map();
    for (const [a, v, b] of r.links) { const k = `${a} → ${b}`; links.set(k, [...(links.get(k) || []), v]); }
    out.append(h('div', { class: 'two-col' },
      h('div', {}, h('h2', { class: 'sect' }, '블록 사이의 연결', h('span', { class: 'count' }, links.size)),
        links.size ? h('div', { class: 'link-list' }, [...links.entries()].map(([k, vars]) => h('div', { class: 'link-row' }, h('span', { class: 'mono' }, k), h('span', { class: 'vars' }, vars.map((v) => h('span', { class: 'pc-flat' }, v))))))
          : h('div', { class: 'muted pad0' }, '블록끼리 주고받는 변수가 없습니다.')),
      h('div', {}, h('h2', { class: 'sect' }, '풀이 순서', h('span', { class: 'count' }, r.blocks.length)),
        h('div', { class: 'solve-list' }, r.blocks.map((b, i) => h('span', { class: `solve ${b.type === '동시' ? 'sim' : ''}`.trim(), title: b.type === '동시' ? '서로 물려 있어 함께 푼다(동시 블록)' : '앞에서 풀린 값으로 차례로 푼다' },
          h('small', {}, i + 1), b.variables.join(' · '), b.type === '동시' ? h('em', {}, '동시') : null))))));

    // 외생
    const exo = r.exogenous.map((v) => ({ name: v, ...(r.exogenous_data[v] || {}) }));
    out.append(h('h2', { class: 'sect' }, '외생 변수', h('span', { class: 'count' }, exo.length)),
      exo.length ? h('div', { class: 'exo-list' }, exo.map((x) => h('span', { class: `exo ${x.in_data === false && !x.indicator ? 'bad' : ''}`.trim(), title: x.indicator ? '지시자(더미·추세) — 저절로 만든다' : x.in_data === false ? '자료에 없습니다' : `자료 ${x.first} – ${x.last}` },
        h('b', { class: 'mono' }, x.name), h('small', {}, x.indicator ? '지시자' : x.in_data === false ? '자료에 없음' : `– ${x.last}`))))
        : h('div', { class: 'muted pad0' }, '외생 변수가 없습니다.'),
      h('p', { class: 'foot-note' }, '외생 변수는 모형이 풀지 않고 받는 값입니다 — 과거 재현에서는 실측을, 전망에서는 가정을 씁니다. 자료 끝이 전망 구간에 못 미치면 가정이 채워야 합니다.'));
    return out;
  }

  // ---- 그리기: 과거 재현 --------------------------------------------------------------------------

  function runRow() {
    const r = st.run;
    const blocks = [...new Set((report()?.parts || []).map((p) => p.block))];
    const target = h('select', { class: 'an-select', 'aria-label': '무엇을 풀까', 'data-run': 'target' },
      h('option', { value: st.model }, `모형 ${st.model}`), blocks.map((b) => h('option', { value: b }, `블록 ${b} 만(나머지는 실측)`)));
    target.value = r.target;
    const cmd = h('span', { class: 'cmd' }, runCommand());
    const change = (key, value) => { r[key] = value; cmd.textContent = runCommand(); save(); };
    target.addEventListener('change', () => change('target', target.value));
    const period = (key, placeholder, title) => {
      const input = h('input', { class: 'mini-input', type: 'text', value: r[key], placeholder, title, spellcheck: 'false', 'data-run': key });
      input.addEventListener('input', () => change(key, input.value.trim()));
      return input;
    };
    const mode = h('select', { class: 'mini-select', title: '푸는 방식', 'data-run': 'mode' }, MODES.map(([v, label]) => h('option', { value: v }, label)));
    mode.value = r.mode;
    mode.addEventListener('change', () => change('mode', mode.value));
    const range = project.overview?.hs?.range || '';
    return h('div', { class: 'an-form', onkeydown: (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey || e.target.tagName === 'INPUT')) { e.preventDefault(); solve(); } } },
      h('div', { class: 'an-top' }, h('label', { class: 'an-field grow' }, h('span', {}, '무엇을'), target),
        h('button', { class: 'btn primary an-run', type: 'button', 'data-act': 'solve', disabled: project.busy || !!report()?.problems.length, title: report()?.problems.length ? '조립의 문제를 먼저 고치세요' : '과거를 풀어 실측과 견준다(Ctrl+Enter) — 기록(hs:)으로 남는다', onclick: () => solve() }, icon('rewind'), '풀기')),
      h('div', { class: 'eq-opts an-opts' },
        h('label', { class: 'opt' }, h('span', {}, '범위'), period('start', range.split(':')[0] || '처음', '시작 — 비우면 equion.toml [hs] range. 상대 기간도 됩니다(last-39)'), h('span', { class: 'tilde' }, '~'), period('end', range.split(':')[1] || '끝', '끝')),
        h('label', { class: 'opt' }, h('span', {}, '방식'), mode)),
      h('button', { class: 'cmdline', type: 'button', title: '같은 일을 터미널에서 하는 명령 — 누르면 복사합니다', onclick: () => copyText(cmd.textContent, '명령을 복사했습니다') }, h('span', { class: 'prompt' }, '>'), cmd, icon('copy')));
  }

  function runList() {
    const list = runs();
    if (!list.length) return h('div', { class: 'empty-state' }, '아직 푼 기록이 없습니다. ‘풀기’를 누르면 과거 구간을 풀어 실측과 견줍니다.', h('br'), '터미널에서 ', h('code', {}, `equion hs ${st.model}`), ' 로 푼 기록도 여기에 뜹니다.');
    const rows = (st.more ? list : list.slice(0, 4)).map((r) => h('tr', { class: `${r.id === st.shown ? 'on' : ''} ${r.id === st.vs ? 'vs' : ''}`.trim(), 'data-run-id': r.id, onclick: () => showRun(r.id) },
      h('td', { class: 'c-check' }, r.id !== st.shown ? h('button', { class: 'check', type: 'button', role: 'checkbox', 'aria-checked': String(r.id === st.vs), title: '보는 기록과 견준다(전후 비교)', 'aria-label': `${r.id} 와 견주기`,
        onclick: (e) => { e.stopPropagation(); st.vs = st.vs === r.id ? null : r.id; showRun(st.shown); } }, r.id === st.vs ? icon('check') : null) : null),
      h('td', { class: 'c-name' }, h('span', { class: 'mono' }, r.id.replace(/^hs:/, '')), r.target !== st.model ? h('span', { class: 'tag' }, `블록 ${r.target}`) : null),
      h('td', { class: 'c-eq' }, r.metric || ''), h('td', { class: 'c-when' }, whoLabel(r.who), ' · ', when(r.created))));
    return h('div', { class: 'cands runs' }, h('div', { class: 'cand-head' }, h('div', { class: 'cand-sum' }, h('b', {}, '푼 기록'), h('span', { class: 'n' }, list.length), h('span', { class: 'muted' }, '— 줄을 누르면 보이고, 네모를 고르면 견줍니다')),
      h('span', { class: 'grow' }), list.length > 4 ? h('button', { class: 'btn small quiet', type: 'button', onclick: () => { st.more = !st.more; render(); } }, st.more ? '줄이기' : `모두 ${list.length}`) : null),
    h('table', { class: 'cand' }, h('tbody', {}, rows)));
  }

  function runView() {
    const v = st.view;
    if (!v) return st.shown ? h('div', { class: 'empty-state' }, '기록을 읽는 중…') : null;
    const m = v.meta;
    const counts = m.counts || {};
    const vintage = project.overview?.vintage?.id;
    const out = h('div', { class: 'run-view' });
    out.append(h('div', { class: 'result-head' }, kindPill('hs'), h('button', { class: 'rid', type: 'button', title: '이 기록의 카드를 따로 연다', onclick: () => project.openRecord(v.id) }, v.id),
      h('span', { class: 'meta' }, h('b', {}, m.target === st.model ? `모형 ${m.target}` : `블록 ${m.target}`), h('span', {}, `${m.range?.[0]} – ${m.range?.[1]}`), h('span', {}, (MODES.find(([k]) => k === m.mode) || ['', m.mode])[1].split(' — ')[0]),
        m.who ? whoLabel(m.who) : null, h('span', {}, when(m.created)),
        v.vintage && vintage && v.vintage !== vintage ? h('span', { class: 'tag warn', title: `이 기록은 자료 회차 ${v.vintage} 로 풀었습니다 — 지금 회차는 ${vintage}` }, `다른 회차 ${v.vintage}`) : null,
        m.replay ? h('span', { class: `tag ${m.replay.same ? 'ok' : 'bad'}`, title: `${m.replay.of} 을(를) 그때 그대로 다시 푼 것` }, m.replay.same ? '그때와 같음' : '그때와 다름') : null),
      h('span', { class: 'grow' }),
      h('button', { class: 'btn small quiet', type: 'button', disabled: project.busy, title: `equion hs --replay ${v.id} — 기록의 조립 명세·자료로 다시 풀어 같은 숫자가 나오는지 본다`, onclick: replay }, icon('refresh'), '그때 그대로 다시')));
    // 기간마다의 풀이 상태 — 실패한 해를 다음 기로 넘기지 않았다는 것까지 여기서 보인다
    const odd = v.status.filter((s) => s.status !== 'ok');
    out.append(h('div', { class: 'status-box' },
      h('div', { class: 'status-head' }, Object.entries(STATUS).map(([k, [label, cls]]) => h('span', { class: `st ${counts[k] ? cls : 'none'}` }, h('i', { class: `sq ${cls}` }), `${label} ${counts[k] || 0}`)),
        h('span', { class: 'grow' }), h('span', { class: 'muted' }, `${v.status.length}기`)),
      h('div', { class: 'status-band', role: 'img', 'aria-label': '기간마다의 풀이 상태' }, v.status.map((s) => h('i', { class: `sq ${(STATUS[s.status] || ['', 'bad'])[1]}`, title: `${s.period} — ${(STATUS[s.status] || [s.status])[0]}${s.excluded ? `\n뺀 식: ${s.excluded}` : ''}${s.fallback ? `\n실측으로 대신: ${s.fallback}` : ''}${s.message ? `\n${s.message}` : ''}` }))),
      odd.length ? h('div', { class: 'status-odd' }, odd.slice(0, 4).map((s) => h('div', {}, h('b', { class: 'mono' }, s.period), ` ${(STATUS[s.status] || [s.status])[0]}`, s.excluded ? ` — 뺀 식 ${s.excluded}` : '', s.fallback ? ` — 실측으로 대신 ${s.fallback}` : '', s.message ? ` (${s.message})` : '')),
        odd.length > 4 ? h('div', { class: 'muted' }, `… 그 밖에 ${odd.length - 4}기`) : null) : null));
    if (m.implicit?.length) out.append(h('details', { class: 'implicit-box' }, h('summary', {}, `알아서 한 것 ${m.implicit.length}`), h('ul', { class: 'implicit' }, m.implicit.map((x) => h('li', {}, x)))));

    // 변수마다의 적합도 — 견주는 기록이 있으면 앞 → 지금
    const other = st.vsView ? Object.fromEntries(st.vsView.stats.map((s) => [s.name, s])) : null;
    const top = Math.max(...v.stats.map((s) => s.rmspe || 0), 1e-9);
    const rows = [...v.stats].sort((a, b) => (b.rmspe || 0) - (a.rmspe || 0));
    out.append(h('h3', { class: 'cap' }, '변수마다의 적합도', h('small', {}, other ? ` — ${st.vs} → ${v.id}` : ' — 줄을 누르면 실측과 해, 그리고 오차가 어디서 오는지')),
      h('table', { class: 'grid plain fit-table' }, h('thead', {}, h('tr', {}, ['변수', 'RMSPE', other ? '앞' : null, other ? '달라짐' : null, 'MAE%', '평균오차', ''].filter((c) => c !== null).map((c, i) => h('th', { class: i ? 'num' : '' }, c)))),
        h('tbody', {}, rows.map((s) => {
          const o = other?.[s.name];
          const d = o && o.rmspe != null && s.rmspe != null ? s.rmspe - o.rmspe : null;
          const small = s.mae != null && Math.abs(s.mae) < 1 && (s.rmspe || 0) > 5;
          return h('tr', { class: `row ${st.pick === s.name ? 'on' : ''}`.trim(), tabindex: '0', 'data-var': s.name, onclick: () => pickVar(s.name), onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pickVar(s.name); } } },
            h('td', {}, h('b', { class: 'mono' }, s.name)),
            h('td', { class: 'num bar-cell' }, h('i', { class: 'bar', style: { width: `${Math.round(((s.rmspe || 0) / top) * 100)}%` } }), h('span', {}, pct(s.rmspe))),
            other ? h('td', { class: 'num dim' }, pct(o?.rmspe)) : null,
            other ? h('td', { class: `num ${d == null || Math.abs(d) < 0.005 ? 'dim' : d < 0 ? 'good' : 'poor'}` }, d == null ? '—' : Math.abs(d) < 0.005 ? '그대로' : `${d > 0 ? '+' : '−'}${Math.abs(d).toFixed(2)}%p`) : null,
            h('td', { class: 'num' }, pct(s.mae_pct), small ? h('span', { class: 'tag', title: '0 에 가까운 값이라 % 오차가 커 보입니다 — 평균오차(수준)도 함께 보세요' }, '0 근처') : null),
            h('td', { class: 'num' }, signed(s.mean_error)), h('td', { class: 'num' }, icon('chevron', 'go')));
        }))));
    out.append(detailBox);
    return out;
  }

  const detailBox = h('div', { class: 'var-detail' });
  function drawDetail() {
    disposeChart();
    disposeChart = () => {};
    clear(detailBox);
    if (!st.pick || !st.view) return;
    const name = st.pick;
    const crumbs = [...st.path, name];
    detailBox.append(h('div', { class: 'raw-cap' }, h('b', {}, '원인 따라가기'), crumbs.map((c, i) => [i ? icon('arrow') : null, i === crumbs.length - 1 ? h('b', { class: 'mono' }, c)
      : h('button', { class: 'link mono', type: 'button', title: '여기로 돌아간다', onclick: () => { Object.assign(st, { pick: c, path: crumbs.slice(0, i), series: null, trace: null }); save(); render(); loadPick(); } }, c)]),
    h('span', { class: 'grow' }), h('button', { class: 'icon-btn', type: 'button', title: '닫기', 'aria-label': '닫기', onclick: () => { st.pick = null; st.path = []; save(); render(); } }, icon('x'))));
    if (!st.series || !st.trace) { detailBox.append(h('div', { class: 'muted pad' }, '읽는 중…')); return; }
    const s = st.series.series[name];
    const t = st.trace;
    const chart = h('div', { class: 'pad-chart' });
    const panel = h('div', { class: 'trace' });
    detailBox.append(h('div', { class: 'detail-grid' }, chart, panel));
    if (s) {
      const o = st.series.other?.series?.[name];
      const lines = [{ label: '실측', values: s.actual || [], color: 'var(--c-actual)', width: 1.5 }, { label: `해 ${st.shown.replace(/^hs:/, '')}`, values: s.solved, color: 'var(--c-fitted)', dashed: true, width: 1.7 }];
      if (o && st.series.other.period.join() === st.series.period.join()) lines.push({ label: `해 ${st.vs.replace(/^hs:/, '')}`, values: o.solved, color: 'var(--c-resid)', dashed: true, width: 1.3 });
      requestAnimationFrame(() => { disposeChart = drawLines(chart, { period: st.series.period, lines, height: 200, title: name }); });
    } else chart.append(h('div', { class: 'muted pad' }, '이 기록에 풀린 값이 없습니다.'));
    if (!t.part) { panel.append(h('p', {}, t.note || '이 변수의 식이 없습니다.')); return; }
    const p = t.part;
    put(panel,
      h('div', { class: 'trace-eq' }, h('button', { class: 'part-chip', type: 'button', title: '식 작업대에서 이 식을 본다', onclick: () => project.openTab({ type: 'bench', part: p.id }) },
        h('span', { class: `glyph ${p.kind === 'identity' ? 'identity' : ''}` }, p.kind === 'identity' ? '≡' : 'ƒ'), h('b', {}, p.id)), h('code', {}, p.text)),
      h('div', { class: 'trace-own' }, `이 풀이에서 ${name} 의 오차 `, h('b', {}, pct(t.own?.rmspe)), t.own?.mean_error != null ? ` · 평균오차 ${signed(t.own.mean_error)}` : '',
        p.kind === 'identity' ? ' — 항등식이라 식 자체의 오차는 없습니다. 입력에서 옵니다.' : ''),
      p.kind === 'identity' ? null : h('div', { class: 'trace-solo' }, t.solo ? ['식만 따로 모의하면(다른 변수는 실측) ', h('b', {}, pct(t.solo.rmspe)), ' ', h('button', { class: 'link mono', type: 'button', onclick: () => project.openRecord(t.solo.record) }, t.solo.record),
        t.own?.rmspe != null && t.solo.rmspe != null ? h('span', { class: 'muted' }, t.solo.rmspe >= t.own.rmspe * 0.8 ? ' — 오차의 대부분이 이 식 자체에서 옵니다' : ' — 식 자체보다 입력에서 더 옵니다') : null]
        : ['식만 따로 모의한 기록이 없습니다 ', h('button', { class: 'btn small', type: 'button', disabled: project.busy, title: `equion est ${p.id} --sim — 다른 변수는 실측을 넣고 이 식만 푼다`, onclick: () => solo(p.id) }, '식만 따로 모의')]),
      h('h4', {}, '이 식의 입력'),
      t.inputs.length ? h('div', { class: 'trace-inputs' }, t.inputs.map((x) => (x.endogenous
        ? h('button', { class: 'trace-in endo', type: 'button', 'data-follow': x.name, title: `${x.part} 이(가) 정한다 — 누르면 그 변수로 거슬러 올라간다`, onclick: () => pickVar(x.name, { follow: true }) },
          h('b', { class: 'mono' }, x.name), h('span', { class: 'muted' }, x.block), h('span', { class: 'grow' }), h('span', { class: x.rmspe != null && t.own?.rmspe != null && x.rmspe > t.own.rmspe ? 'poor' : '' }, pct(x.rmspe)), icon('chevron', 'go'))
        : h('div', { class: 'trace-in' }, h('b', { class: 'mono' }, x.name), h('span', { class: 'muted' }, '외생'), h('span', { class: 'grow' }), h('span', { class: 'muted' }, '실측 — 오차 없음')))),
      t.self_lag ? h('div', { class: 'trace-in' }, h('b', { class: 'mono' }, `${name}(시차)`), h('span', { class: 'muted' }, '자기 시차'), h('span', { class: 'grow' }), h('span', { class: 'muted' }, st.view.meta.mode === 'dynamic' ? '앞 기의 해 — 오차가 쌓인다' : '실측')) : null)
        : h('div', { class: 'muted' }, '입력이 없습니다.'),
      h('div', { class: 'trace-acts' },
        st.view.meta.target !== p.block ? h('button', { class: 'btn small', type: 'button', disabled: project.busy, 'data-act': 'block', title: `equion hs ${p.block} — 이 블록만 풀고 나머지는 실측을 넣는다. 그래도 어긋나면 블록 안의 문제다`, onclick: () => solve({ target: p.block, compare: true }) }, `블록 ${p.block} 만 풀기`) : null,
        st.view.meta.mode !== 'fit' ? h('button', { class: 'btn small', type: 'button', disabled: project.busy, title: `equion hs ${st.view.meta.target} --mode fit — 식마다 다른 변수에 실측을 넣어 푼다. 식 자체의 오차만 남는다`, onclick: () => solve({ target: st.view.meta.target, mode: 'fit', compare: true }) }, '식마다 풀기') : null),
      h('p', { class: 'foot-note' }, '입력의 오차가 크면 그 변수로 거슬러 올라가고, 입력은 괜찮은데 이 변수만 나쁘면 식 자체를 식 작업대에서 봅니다.'));
  }

  const listBox = h('div', {});
  /** 푼 기록의 목록만 다시 그린다 — 새 기록이 생기는 순간(아래에 펼쳐 둔 변수는 그대로 둔다) */
  function drawList() { clear(listBox); put(listBox, runList()); }

  function hsSection() {
    drawList();
    return put(h('div', {}), runRow(), listBox, runView());
  }

  function render() {
    clear(el);
    const o = project.overview;
    const spec = st.asm?.spec;
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, h('span', { class: 'glyph model' }, 'M'), h('span', { class: 'mono' }, st.model)), h('div', { class: 'sub' }, spec?.desc || o?.models.find((m) => m.name === st.model)?.desc || '모형')),
      h('div', { class: 'tools' },
        spec ? h('button', { class: 'btn', type: 'button', 'data-act': 'edit-model', title: '이 모형의 블록·끼울 모형·뺄 식을 고친다(equion model define) — 적힐 줄을 먼저 보인다', onclick: () => defineModel(false) }, icon('doc'), '모형 고치기') : null,
        h('button', { class: 'btn quiet', type: 'button', 'data-act': 'new-model', title: '블록과 모형을 골라 새 모형을 만든다', onclick: () => defineModel(true) }, icon('plus'), '새 모형'),
        h('button', { class: 'btn quiet', type: 'button', 'data-act': 'new-block', title: '새 블록(방정식 파일 하나)을 만든다', onclick: defineBlock }, icon('plus'), '새 블록'),
        claudeButton(project, () => { const r = project.records.find((x) => x.id === st.shown); return { name: `모형 ${st.model}`, summary: r ? `과거 재현 ${r.id}${r.metric ? ` (${r.metric})` : ''}` : '' }; }))));
    if (st.error) el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', { class: 'grow' }, st.error)));
    if (!st.asm) { if (!st.error) el.append(h('div', { class: 'empty-state' }, '모형을 읽는 중…')); return; }
    el.append(flow(), st.section === 'hs' ? hsSection() : assemblySection());
    if (st.section === 'hs') drawDetail();
  }

  render();
  return {
    key: `model:${st.model}`, type: 'model', title: st.model, icon: 'cube', mono: true, el,
    desc: () => ({ type: 'model', model: st.model, section: st.section, shown: st.shown, vs: st.vs, pick: st.pick, ...st.run }),
    show() { if (!loaded) loadAssembly(); },
    open(next) {
      if (next.section && SECTIONS.includes(next.section)) st.section = next.section;
      if (next.shown && next.shown !== st.shown) { st.section = 'hs'; showRun(next.shown, { keepPick: false }); } else render();
    },
    event(e) {
      if (e.type === 'defs' || e.type === 'overview') { if (loaded && e.type === 'overview') loadAssembly(); } else if ((e.type === 'record' && e.record?.kind === 'hs') || e.type === 'records') { if (st.section === 'hs' && st.asm) drawList(); } else if (e.type === 'job') {
        for (const b of el.querySelectorAll('[data-act="solve"], .trace-acts .btn, .trace-solo .btn')) b.disabled = project.busy || (b.dataset.act === 'solve' && !!report()?.problems.length);
      }
    },
    dispose() { disposeChart(); },
  };
}
