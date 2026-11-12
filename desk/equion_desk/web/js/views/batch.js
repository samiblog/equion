// 후보 묶음 (2차판 — DESK_SOLO 장면 3, D56) — 고를 칸의 조합으로 식 여러 개를 만들어 한꺼번에 추정한다. 모두 그 부품의 후보로 쌓인다.
//
//   종속 [dlog(I)]   늘 넣을 것 [c]
//   ① [dlog(Y) | dlog(Y(-1))]
//   ② [RR(-1) | RR(-2) | RR(-1 to -2)]
//   ③ [(없음) | log(I(-1)/Y(-1))]
//   → 만들어질 식 12개(글자 그대로 — 빼고 싶은 것은 끈다) → 모두 추정 → 후보 목록에서 견주고 채택
//
// 같은 일을 하는 명령은 `equion est '식' --for 부품`을 줄마다 — '노트로 저장'은 그 줄들을 노트의 블록 하나로 남긴다(다음 회차에 노트 전체 실행).

import { addToNote } from '../noteops.js';
import { clear, flash, h, icon } from '../util.js';
import { quote } from '../command.js';

const MAX = 64;              // 한 번에 만드는 식(서버도 같은 한도)
const NONE = /^(\(없음\)|없음|-|—)?$/;
const COV = [['', '보통'], ['white', 'White'], ['hac', 'HAC']];

/** 괄호 밖의 빈칸으로 나눈다 — CN(-1 to -2) 은 한 항 */
function terms(text) {
  const out = [];
  let depth = 0;
  let cur = '';
  for (const ch of String(text)) {
    if (ch === '(') depth++;
    if (ch === ')') depth = Math.max(0, depth - 1);
    if (/\s/.test(ch) && depth === 0) { if (cur) out.push(cur); cur = ''; continue; }
    cur += ch;
  }
  if (cur) out.push(cur);
  return out;
}

/** 칸 하나의 고를 것들 — '|'로 나눈다. 빈칸·(없음)은 '넣지 않음' */
const choices = (slot) => String(slot).split('|').map((x) => x.trim()).map((x) => (NONE.test(x) ? '' : x));

export function combos(dep, always, slots) {
  let rows = [[]];
  for (const slot of slots) {
    const opts = choices(slot);
    if (!opts.length) continue;
    const next = [];
    for (const r of rows) for (const o of opts) next.push([...r, o]);
    rows = next;
    if (rows.length > MAX * 4) break;
  }
  const seen = new Set();
  const out = [];
  for (const r of rows) {
    const text = [dep.trim(), always.trim(), ...r].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
    if (!text || seen.has(text)) continue;
    seen.add(text);
    out.push(text);
  }
  return out;
}

export function batchView(project, desc) {
  const partId = desc.part;
  const part = () => project.part(partId);
  const el = h('div', { class: 'view batch' });
  const saved = desc.batch || {};
  const st = {
    dep: saved.dep ?? '', always: saved.always ?? 'c', slots: Array.isArray(saved.slots) ? saved.slots.slice(0, 8) : [],
    off: new Set(Array.isArray(saved.off) ? saved.off : []), s0: saved.s0 || '', s1: saved.s1 || '', sim: saved.sim !== false, cov: saved.cov || '',
    result: null, error: null, running: false, seeded: !!desc.batch,
  };
  const save = () => project.saveView();

  /** 처음 열면 부품의 식으로 칸을 채운다 — 종속 · 상수 · 나머지 항을 첫 칸에 */
  function seed() {
    if (st.seeded) return;
    const p = part();
    if (!p) return;
    st.seeded = true;
    const body = String(p.text).split(/\s@(?:smpl|inst|coef|start)\b/i)[0];
    const t = terms(body);
    st.dep = t[0] || '';
    const rest = t.slice(1);
    st.always = rest.includes('c') ? 'c' : '';
    const others = rest.filter((x) => x !== 'c');
    st.slots = others.length ? [others.join(' '), ''] : ['', ''];
  }

  const list = () => combos(st.dep, st.always, st.slots);
  const picked = () => list().filter((t) => !st.off.has(t));
  const smpl = () => (st.s0 || st.s1 ? `${st.s0}:${st.s1}` : '');
  const lineOf = (t) => ['est', quote(t), '--for', partId, ...(smpl() ? ['--smpl', smpl()] : []), ...(st.sim ? ['--sim'] : []), ...(st.cov ? ['--cov', st.cov] : [])].join(' ');

  const head = h('div', { class: 'view-head' });
  const form = h('div', { class: 'eq-box batch-form' });
  const listBox = h('div', { class: 'batch-list' });
  const outBox = h('div', {});
  el.append(head, form, listBox, outBox);

  function drawHead() {
    clear(head).append(h('div', {}, h('h1', {}, '후보 묶음', h('span', { class: 'mono' }, partId)),
      h('div', { class: 'sub' }, '고를 칸의 조합으로 식 여러 개를 만들어 한꺼번에 추정합니다 — 모두 이 부품의 후보로 쌓이고, 식 작업대의 후보 목록에서 견주어 채택합니다.')),
    h('div', { class: 'tools' }, h('button', { class: 'btn quiet', type: 'button', onclick: () => project.openTab({ type: 'bench', part: partId }) }, icon('equation'), '식 작업대')));
  }

  function input(value, onInput, attrs = {}) {
    const el2 = h('input', { class: 'mini-input', type: 'text', value, spellcheck: 'false', autocomplete: 'off', ...attrs });
    el2.addEventListener('input', () => { onInput(el2.value); drawList(); save(); });
    return el2;
  }

  function drawForm() {
    clear(form);
    const slotRows = st.slots.map((slot, i) => h('div', { class: 'slot-row' },
      h('span', { class: 'slot-n' }, String(i + 1)),
      input(slot, (v) => { st.slots[i] = v; }, { class: 'mini-input slot', 'data-slot': String(i), 'aria-label': `고를 칸 ${i + 1}`, placeholder: i ? '(없음) | log(I(-1)/Y(-1))' : 'dlog(Y) | dlog(Y(-1))' }),
      h('button', { class: 'icon-btn', type: 'button', title: '이 칸 빼기', 'aria-label': '칸 빼기', onclick: () => { st.slots.splice(i, 1); drawForm(); drawList(); save(); } }, icon('x'))));
    const cov = h('select', { class: 'mini-select', 'aria-label': '표준오차' }, COV.map(([v, l]) => h('option', { value: v }, l)));
    cov.value = st.cov;
    cov.addEventListener('change', () => { st.cov = cov.value; drawList(); save(); });
    const sim = h('input', { type: 'checkbox' });
    sim.checked = st.sim;
    sim.addEventListener('change', () => { st.sim = sim.checked; drawList(); save(); });
    const span = project.overview?.vintage?.span || [];
    form.append(
      h('div', { class: 'batch-top' },
        h('label', { class: 'opt' }, h('span', {}, '종속'), input(st.dep, (v) => { st.dep = v; }, { class: 'mini-input dep', 'data-field': 'dep', 'aria-label': '종속' })),
        h('label', { class: 'opt' }, h('span', {}, '늘 넣을 것'), input(st.always, (v) => { st.always = v; }, { class: 'mini-input always', 'data-field': 'always', 'aria-label': '늘 넣을 것' }))),
      h('div', { class: 'batch-slots' }, h('div', { class: 'cap-line' }, h('b', {}, '고를 칸'), h('span', { class: 'muted' }, ' — 칸마다 ‘|’로 나눈 것 가운데 하나씩. 빈칸이나 (없음)은 그 칸을 넣지 않는 것입니다.')),
        slotRows, h('button', { class: 'btn small quiet', type: 'button', 'data-act': 'add-slot', disabled: st.slots.length >= 8, onclick: () => { st.slots.push(''); drawForm(); drawList(); save(); form.querySelector(`[data-slot="${st.slots.length - 1}"]`)?.focus(); } }, icon('plus'), '칸 더하기')),
      h('div', { class: 'eq-opts' },
        h('label', { class: 'opt' }, h('span', {}, '표본'), input(st.s0, (v) => { st.s0 = v.trim(); }, { placeholder: span[0] || '', 'aria-label': '표본의 처음' }),
          h('span', { class: 'tilde' }, '~'), input(st.s1, (v) => { st.s1 = v.trim(); }, { placeholder: span[1] || '', 'aria-label': '표본의 끝' })),
        h('label', { class: 'opt' }, h('span', {}, '표준오차'), cov),
        h('label', { class: 'opt check', title: '식 하나의 동태 모의와 RMSPE — 후보를 견줄 때 쓴다' }, sim, h('span', {}, '단독 모의'))));
  }

  function drawList() {
    clear(listBox);
    const all = list();
    const on = all.filter((t) => !st.off.has(t));
    const over = on.length > MAX;
    listBox.append(h('div', { class: 'batch-head' }, h('b', {}, `만들어질 식 ${all.length}개`), h('span', { class: 'muted' }, ` · 고른 것 ${on.length}`),
      h('span', { class: 'grow' }),
      h('button', { class: 'link', type: 'button', onclick: () => { st.off.clear(); drawList(); save(); } }, '모두'),
      h('button', { class: 'link', type: 'button', onclick: () => { for (const t of all) st.off.add(t); drawList(); save(); } }, '없음')));
    if (!all.length) { listBox.append(h('div', { class: 'empty-state' }, '종속과 고를 칸을 적으면 만들어질 식이 여기에 보입니다.')); return; }
    listBox.append(h('div', { class: 'batch-rows' }, all.slice(0, MAX * 2).map((t, i) => {
      const box = h('input', { type: 'checkbox' });
      box.checked = !st.off.has(t);
      box.addEventListener('change', () => { if (box.checked) st.off.delete(t); else st.off.add(t); drawList(); save(); });
      return h('label', { class: `batch-row ${box.checked ? '' : 'off'}`.trim(), 'data-eq': t }, box, h('span', { class: 'n' }, String(i + 1)), h('code', {}, t));
    })));
    if (over) listBox.append(h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, `한 번에 ${MAX}개까지 추정합니다 — 칸을 줄이거나 몇 개를 끄세요.`)));
    listBox.append(h('div', { class: 'batch-acts' },
      h('button', { class: 'btn primary', type: 'button', 'data-act': 'run-batch', disabled: !on.length || over || st.running || project.busy,
        title: '고른 식을 차례로 추정한다 — 하나가 틀려도 나머지는 한다', onclick: runAll }, icon('play'), `모두 추정 (${on.length})`),
      h('button', { class: 'btn', type: 'button', 'data-act': 'batch-note', disabled: !on.length || over, title: '이 줄들을 노트의 블록 하나로 남긴다 — 다음 회차에는 노트 전체 실행',
        onclick: () => addToNote(project, { lines: on.map(lineOf), title: `${partId} 후보`, suggest: `notes/candidates_${(part()?.target || partId.split(':')[1] || 'x').replace(/[^A-Za-z0-9_]/g, '_')}.md` }) }, icon('doc'), '노트로 저장…'),
      h('div', { class: 'cmdline flat', title: '같은 일을 하는 명령(줄마다 하나)' }, h('span', { class: 'prompt' }, '>'),
        h('span', { class: 'cmd' }, `equion ${lineOf(on[0] || all[0])}`), on.length > 1 ? h('span', { class: 'muted' }, ` 외 ${on.length - 1}줄`) : null)));
  }

  async function runAll() {
    const texts = picked();
    if (!texts.length) return;
    st.running = true; st.error = null; st.result = null;
    drawList(); drawOut();
    try {
      const res = await project.compute('est-batch', { part: partId, texts, smpl: smpl(), sim: st.sim, cov: st.cov || undefined }, { quiet: true });
      st.result = res.result;
      for (const m of st.result.made) project.seen(m.id);
    } catch (err) {
      if (err.kind !== 'busy') st.error = err.message;
    }
    st.running = false;
    drawList(); drawOut();
  }

  function drawOut() {
    clear(outBox);
    if (st.running) { outBox.append(h('div', { class: 'empty-state' }, '추정하는 중… 아래 작업 줄에 몇 번째인지 보입니다.')); return; }
    if (st.error) outBox.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, st.error)));
    const r = st.result;
    if (!r) return;
    outBox.append(h('div', { class: `banner ${r.failed.length ? 'warn' : 'ok'}` }, icon(r.failed.length ? 'alert' : 'check'),
      h('div', {}, `후보 ${r.made.length}개를 남겼습니다`, r.failed.length ? ` · 추정하지 못한 식 ${r.failed.length}개` : '', ' — 식 작업대의 후보 목록에서 걸러 보고 겹쳐 본 뒤 채택합니다.',
        r.failed.length ? h('ul', { class: 'batch-failed' }, r.failed.map((f) => h('li', {}, h('code', {}, f.text), h('span', { class: 'muted' }, ` — ${f.error}`)))) : null),
      h('button', { class: 'btn small primary', type: 'button', 'data-act': 'to-bench', onclick: () => project.openTab({ type: 'bench', part: partId }) }, '후보 목록에서 견주기')));
  }

  function render() {
    seed();
    drawHead(); drawForm(); drawList(); drawOut();
  }

  render();
  return {
    key: `batch:${partId}`, type: 'batch', title: `후보 묶음 ${partId}`, icon: 'layers', mono: false, el,
    desc: () => ({ type: 'batch', part: partId, batch: { dep: st.dep, always: st.always, slots: st.slots, off: [...st.off].slice(0, 200), s0: st.s0, s1: st.s1, sim: st.sim, cov: st.cov } }),
    show() { if (!st.seeded) render(); },
    event(e) { if (e.type === 'overview' && !st.seeded) render(); if (e.type === 'job') { const b = el.querySelector('[data-act="run-batch"]'); if (b) b.disabled = project.busy || st.running || !picked().length; } },
    dispose() {},
  };
}
