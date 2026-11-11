// 식 작업대(W1) — 식 하나를 다듬고, 후보를 견주고, 채택한다. Desk 에서 가장 많이 쓰는 화면이다.
//
//   식 칸      치는 동안 문법만 검사한다(계산이 아니다) — 종류·목표·자료에 없는 변수·이 부품의 목표와 다른지
//   추정       단추나 Ctrl+Enter 일 때만. 표본·표준오차(보통·White·HAC)·단독 모의를 고른다. 1초 안에 결과
//   후보 목록  이 부품에 묶인 추정 기록 모두(사람·터미널·Claude) — 줄을 누르면 그 기록이 아래에(다시 계산하지 않는다)
//   겹쳐 보기  둘에서 넷 — 적합·잔차·단독 모의를 한 축에, 계수와 통계를 나란히
//   채택       무엇이 바뀌는지(블록 파일의 줄·채택표) 보이고 나서 — `equion adopt` 와 같다. 바뀜 기록에 남는다
//   이 후보로 과거 재현   파일은 그대로 두고 끼워 풀어 지금 파일로 푼 것과 견준다 — `equion hs --swap … --vs …`
//
// 화면을 여는 것만으로는 계산하지 않는다(기획안 §2.4-1). 쓰던 식·고른 기록·옵션은 탭과 함께 기억한다.

import { drawLines } from '../chart.js';
import { claudeButton } from '../claude.js';
import { confirmDialog, popMenu } from '../dialog.js';
import { clear, copyText, debounce, flash, h, icon, num, put, short } from '../util.js';
import { candidateRail, MAX_OVERLAY } from './candidates.js';
import { renderOverlay, renderSingle, summaryLine } from './result.js';

const COV = [['', '보통'], ['white', 'White'], ['hac', 'HAC']];      // White: 이분산에 견고 · HAC: 계열상관·이분산에 견고(Newey-West)
const TAIL = /\s@(?:smpl|inst|coef|start)\b/i;      // 꼬리 지시자 — 항은 그 앞에 넣는다

export function benchView(project, desc) {
  const partId = desc.part || null;
  const key = partId ? `bench:${partId}` : `bench:~${desc.free}`;
  const el = h('div', { class: 'view bench' });
  const st = {
    rows: [], adopted: null, selected: desc.shown || null, checked: new Set(Array.isArray(desc.checked) ? desc.checked.slice(0, MAX_OVERLAY) : []),
    mode: 'one', sort: desc.sort?.key ? { key: desc.sort.key, dir: desc.sort.dir > 0 ? 1 : -1 } : { key: 'created', dir: -1 }, onlyPass: !!desc.onlyPass,
    fresh: new Set(), view: { tab: desc.view?.tab === 'sim' ? 'sim' : 'fit', otab: desc.view?.otab || 'fit', picked: null },
    opts: { cov: desc.opts?.cov || '', sim: desc.opts?.sim !== false, s0: desc.opts?.s0 || '', s1: desc.opts?.s1 || '', name: '', method: 'auto' },
    cache: new Map(), timing: null, said: '', problem: null, check: null, loaded: false, ident: null, tall: !!desc.tall,
  };
  let touched = desc.draft != null;      // 사람이 식 칸을 고쳤는지 — 고치지 않았으면 부품의 식을 따라간다
  let disposeResult = () => {};
  let running = false;
  let renderSeq = 0;
  let hadSpan = false;      // 식 칸을 그릴 때 자료 구간을 알았는지(표본 칸의 흐린 글)

  const part = () => (partId ? project.part(partId) : null);
  const area = h('textarea', { rows: 1, spellcheck: 'false', autocomplete: 'off', placeholder: '식을 씁니다 — 예: CN c Y CN(-1)', 'aria-label': '식' });
  area.value = desc.draft ?? part()?.text ?? '';
  const grow = () => { area.style.height = 'auto'; area.style.height = `${Math.max(44, area.scrollHeight)}px`; };
  const edited = () => !!part() && area.value.trim() !== part().text.trim();

  const head = h('div', { class: 'view-head' });
  const form = h('div', {});
  const out = h('div', { class: 'bench-out' });
  const status = h('div', { class: 'eq-status', 'aria-live': 'polite' });
  const runButton = h('button', { class: 'btn primary', type: 'button', onclick: () => estimate() }, icon('play'), '추정', h('kbd', {}, 'Ctrl+Enter'));
  const cancelButton = h('button', { class: 'btn', type: 'button', hidden: true, onclick: () => project.cancel() }, icon('stop'), '취소');
  const rail = candidateRail({
    select: (id) => { st.selected = id; st.mode = 'one'; st.timing = null; st.said = ''; st.problem = null; st.view.picked = null; st.fresh.delete(id); refresh(); project.saveView(); },
    toggle: (id) => {
      if (st.checked.has(id)) st.checked.delete(id); else if (st.checked.size < MAX_OVERLAY) st.checked.add(id);
      if (st.mode === 'overlay' && st.checked.size < 2) st.mode = 'one';
      refresh(); project.saveView();
    },
    overlay: () => { st.mode = st.mode === 'overlay' ? 'one' : 'overlay'; refresh(); },
    sort: (k) => { st.sort = st.sort.key === k ? { key: k, dir: -st.sort.dir } : { key: k, dir: ['adj', 'pass', 'created'].includes(k) ? -1 : 1 }; refresh(false); project.saveView(); },
    filter: (on) => { st.onlyPass = on; refresh(false); project.saveView(); },
    tall: (on) => { st.tall = on; refresh(false); project.saveView(); },
    load: (id) => getRecord(id).then((rec) => rec && toEditor(rec)),
  });
  el.append(head, form, out);

  // ---- 머리 ------------------------------------------------------------------------------------

  function renderHead() {
    clear(head);
    const p = part();
    const title = p ? h('h1', {}, h('span', { class: `glyph ${p.kind === 'identity' ? 'identity' : ''}` }, p.kind === 'identity' ? '≡' : 'ƒ'),
      h('span', { class: 'mono' }, p.id), p.adopted ? h('span', { class: 'tag accent', title: `채택한 기록 ${p.adopted} — 모형은 이 계수로 푼다` }, `★ ${p.adopted.split(':')[1]}`) : null)
      : h('h1', {}, partId ? h('span', { class: 'mono' }, partId) : '새 식');
    const sub = p ? h('div', { class: 'sub' }, p.desc ? h('span', {}, p.desc) : null,
      h('button', { class: 'link mono', type: 'button', title: '블록 파일 열기', onclick: () => project.openTab({ type: 'file', path: p.where.split(':')[0] }) }, p.where),
      h('span', { title: p.models?.length ? `이 부품을 쓰는 모형: ${p.models.join(' · ')}` : '이 부품을 쓰는 모형이 없습니다' }, p.kind === 'identity' ? '항등식' : '추정식'))
      : h('div', { class: 'sub' }, partId ? '이 부품은 지금 프로젝트에 없습니다(블록 파일에서 지워졌거나 이름이 바뀜).' : '부품에 없는 식을 써서 추정해 봅니다 — 목표가 같은 부품이 있으면 그 부품의 후보로 기록됩니다.');
    const name = p?.id || '';
    put(head, h('div', {}, title, sub), name ? h('div', { class: 'tools' },
      h('button', { class: 'btn quiet', type: 'button', title: '이름 복사', onclick: () => copyText(name, `${name} — 복사했습니다`) }, icon('copy'), '이름'),
      claudeButton(project, () => { const r = project.records.find((x) => x.id === st.selected); return { name, summary: r ? `후보 ${r.id}${r.metric ? ` (${r.metric})` : ''}` : (p?.text || '') }; })) : null);
  }

  // ---- 식 칸과 옵션 ------------------------------------------------------------------------------

  function renderForm() {
    clear(form);
    const p = part();
    if (p?.kind === 'identity') { renderIdentity(p); return; }
    const span = project.overview?.vintage?.span || [];
    const sample = (k, placeholder, label) => {
      const input = h('input', { class: 'mini-input', type: 'text', value: st.opts[k], placeholder: placeholder || '', 'aria-label': label, spellcheck: 'false',
        title: '비우면 자료 전체. 상대 기간도 됩니다 — 2000Q1 · last-39 · first+4' });
      input.addEventListener('input', () => { st.opts[k] = input.value.trim(); project.saveView(); });
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); estimate(); } });
      return input;
    };
    const cov = h('select', { class: 'mini-select', 'aria-label': '표준오차', title: '계수의 표준오차·t·p를 무엇으로 볼지(계수는 같다 — equion est --cov)\nWhite: 이분산에 견고 · HAC: 계열상관과 이분산에 견고(Newey-West)' },
      COV.map(([value, label]) => h('option', { value, selected: st.opts.cov === value }, label)));
    cov.addEventListener('change', () => { st.opts.cov = cov.value; project.saveView(); });
    const sim = h('input', { type: 'checkbox', checked: st.opts.sim });
    sim.addEventListener('change', () => { st.opts.sim = sim.checked; project.saveView(); });
    const more = h('button', { class: `icon-btn ${st.opts.name || st.opts.method !== 'auto' ? 'set' : ''}`.trim(), type: 'button', title: '기록 이름 · 추정법', 'aria-label': '옵션 더 보기', onclick: (e) => moreMenu(e.currentTarget) }, icon('gear'));
    hadSpan = span.length > 0;
    form.append(h('div', { class: 'eq-box' },
      h('div', { class: 'eq-top' }, area, h('div', { class: 'eq-run' }, cancelButton, runButton)), status,
      h('div', { class: 'eq-opts' },
        h('label', { class: 'opt' }, h('span', {}, '표본'), sample('s0', span[0], '표본의 처음'), h('span', { class: 'tilde' }, '~'), sample('s1', span[1], '표본의 끝')),
        h('label', { class: 'opt' }, h('span', {}, '표준오차'), cov),
        h('label', { class: 'opt check', title: '식 하나의 동태 모의([hs] 구간, 다른 변수는 실측)와 RMSPE 를 함께 — 후보를 견줄 때 쓴다(equion est --sim)' }, sim, h('span', {}, '단독 모의')),
        h('span', { class: 'grow' }), more)));
    renderStatus();
    requestAnimationFrame(grow);
  }

  function moreMenu(anchor) {
    const mark = () => anchor.classList.toggle('set', !!st.opts.name || st.opts.method !== 'auto');
    const name = h('input', { class: 'mini-input wide', type: 'text', value: st.opts.name, placeholder: '자동(예: cn_0008)', spellcheck: 'false', 'aria-label': '기록 이름' });
    name.addEventListener('input', () => { st.opts.name = name.value.trim(); mark(); });
    const method = h('div', { class: 'segmented small' }, [['auto', '자동'], ['ls', 'LS'], ['tsls', 'TSLS']].map(([value, label]) => h('button', {
      type: 'button', 'aria-pressed': String(st.opts.method === value),
      onclick: (e) => { st.opts.method = value; for (const b of e.currentTarget.parentElement.children) b.setAttribute('aria-pressed', String(b === e.currentTarget)); mark(); },
    }, label)));
    popMenu(anchor, [h('div', { class: 'menu-form' },
      h('label', {}, h('span', {}, '기록 이름'), name), h('small', {}, '다음 추정 한 번에만 씁니다(equion est --as). 영문·숫자·_·-'),
      h('label', {}, h('span', {}, '추정법'), method), h('small', {}, '자동: 식에 @inst 가 있으면 TSLS, c(n) 이 있으면 NLS'))], { cls: 'wide' });
  }

  /** 식 칸 아래의 한 줄 — 문법 검사 결과와, 부품의 식과 다른지 */
  function renderStatus() {
    clear(status);
    const c = st.check;
    const text = area.value.trim();
    status.className = 'eq-status';
    let block = null;      // 추정을 막는 까닭
    if (!text) {
      status.append(h('span', { class: 'muted' }, '한 줄에 식 하나 — ', h('code', {}, '종속변수 c 설명변수…'), ' 또는 ', h('code', {}, '좌변 = c(1) + c(2)*X')));
      block = '식을 쓰세요';
    } else if (c && c.text === text && c.ok === false) {
      status.classList.add('bad');
      status.append(icon('alert'), h('span', {}, c.error || '읽을 수 없는 식입니다'));
      block = c.error || '식을 읽을 수 없습니다';
    } else if (c && c.text === text && c.ok) {
      const mismatch = c.part_target && c.target && c.part_target.toUpperCase() !== c.target.toUpperCase();
      if (c.kind === 'identity') {
        status.classList.add('warn');
        status.append(icon('alert'), h('span', {}, '항등식입니다(계수 c(n) 이 없는 등식) — 추정하지 않습니다'));
        block = '항등식은 추정하지 않습니다';
      } else if (c.unknown?.length) {
        status.classList.add('warn');
        status.append(icon('alert'), h('span', {}, '자료에 없는 변수: ', h('b', { class: 'mono' }, c.unknown.join(', '))));
        block = `자료에 없는 변수가 있습니다: ${c.unknown.join(', ')}`;
      } else if (mismatch) {
        status.classList.add('warn');
        status.append(icon('alert'), h('span', {}, '이 식의 목표는 ', h('b', { class: 'mono' }, c.target), ' 입니다 — 이 부품(', h('b', { class: 'mono' }, c.part_target), ')의 후보가 되지 않습니다'));
        block = `목표가 ${c.target} 인 식입니다 — 이 부품의 목표는 ${c.part_target}`;
      } else {
        status.classList.add('ok');
        status.append(icon('check'), h('span', {}, '추정식 · 목표 ', h('b', { class: 'mono' }, c.target), ' · 변수 ', h('span', { class: 'mono' }, c.variables.filter((v) => v !== c.target).join(' ') || '없음')));
      }
    } else status.append(h('span', { class: 'muted' }, '…'));
    if (part() && edited() && text) {
      status.append(h('span', { class: 'grow' }), h('span', { class: 'tag', title: '블록 파일의 식과 다릅니다 — 추정하면 이 부품의 후보로 기록됩니다. 파일은 채택할 때까지 그대로입니다.' }, '파일의 식과 다름'),
        h('button', { class: 'link', type: 'button', onclick: () => { area.value = part().text; touched = false; grow(); queueCheck.flush(); renderStatus(); project.saveView(); } }, '원래 식으로'));
    }
    runButton.dataset.block = block || '';
    runButton.disabled = running || project.busy || !!block;
    runButton.title = block || '추정하고 기록을 남긴다(equion est)';
  }

  const queueCheck = debounce(async () => {
    const text = area.value.trim();
    if (!text) { st.check = null; renderStatus(); return; }
    try {
      const res = await project.post('check', { text, part: part() ? partId : undefined });
      if (res.busy) return;                         // 다른 계산이 도는 중 — 다음에
      if (area.value.trim() === text) { st.check = { ...res, text }; renderStatus(); }
    } catch { /* 검사를 못 해도 추정은 할 수 있다 */ }
  }, 220);

  // ---- 항등식 ----------------------------------------------------------------------------------

  function renderIdentity(p) {
    const box = h('div', {});
    form.append(h('div', { class: 'readonly-eq' }, p.text),
      h('div', { class: 'ident-bar' },
        h('button', { class: 'btn primary', type: 'button', title: `equion ident ${p.id} --check — 실측으로 좌변과 우변을 계산해 견준다(기록은 남기지 않는다)`, onclick: () => checkIdentity(p, box) }, icon('check'), '실측으로 검사'),
        h('span', { class: 'muted' }, '항등식은 추정하지 않습니다. 자료가 항등식을 지키는지(개정이 한 시리즈에만 오면 어긋난다) 실측으로 봅니다.')), box);
    if (st.ident) drawIdentity(box, st.ident);
  }

  async function checkIdentity(p, box) {
    try {
      const res = await project.compute('ident', { part: p.id }, { quiet: true });
      st.ident = res.result;
      drawIdentity(box, st.ident);
    } catch (err) {
      if (err.kind !== 'busy') clear(box).append(h('div', { class: 'banner error', style: { 'margin-top': '14px' } }, icon('alert'), h('div', {}, err.message)));
    }
  }

  function drawIdentity(box, r) {
    clear(box);
    disposeResult();
    box.append(h('div', { class: 'result-head' }, h('span', { class: `tag ${r.ok ? 'ok' : 'bad'}` }, r.ok ? '실측과 맞습니다' : `어긋납니다 — ${r.mismatches?.length || 0}기`),
      h('span', { class: 'meta' }, `${r.start} – ${r.end} · 관측 ${r.n}${r.n_missing ? ` · 결측 ${r.n_missing}` : ''}`)),
    h('div', { class: 'facts' },
      h('div', { class: 'fact' }, h('div', { class: 'k' }, '가장 큰 차이'), h('div', { class: 'v' }, short(r.max_abs))),
      h('div', { class: 'fact' }, h('div', { class: 'k' }, '가장 큰 차이(%)'), h('div', { class: 'v' }, r.max_pct == null ? '—' : `${num(r.max_pct, 4)}%`)),
      h('div', { class: 'fact' }, h('div', { class: 'k' }, '허용오차'), h('div', { class: 'v' }, short(r.tol)))));
    if (r.mismatches?.length) {
      box.append(h('h3', { class: 'cap' }, '어긋난 기간'), h('div', { class: 'said' }, r.mismatches.slice(0, 12).map((m) => (typeof m === 'string' ? m : JSON.stringify(m))).join('\n')));
    }
    if (r.ok) box.append(h('p', { class: 'muted', style: { 'margin-top': '12px' } }, '모든 기간에서 좌변과 우변이 허용오차 안에서 같습니다.'));
    else if (r.series?.period?.length) {
      const chart = h('div', {});
      box.append(h('h3', { class: 'cap' }, '좌변 − 우변'), chart);
      requestAnimationFrame(() => { disposeResult = drawLines(chart, { period: r.series.period, zero: true, height: 170, title: '항등식의 차이', lines: [{ label: '차이(좌변 − 우변)', values: r.series.diff, color: 'var(--c-resid)' }] }); });
    }
  }

  // ---- 후보와 결과 ------------------------------------------------------------------------------

  async function getRecord(id) {
    if (st.cache.has(id)) return st.cache.get(id);
    try {
      const got = await project.get(`record?id=${encodeURIComponent(id)}`);
      const rec = { ...got.meta, id: got.id, series: got.series };
      st.cache.set(id, rec);
      return rec;
    } catch { return null; }
  }

  async function loadCandidates({ mark = false } = {}) {
    if (!partId) { st.loaded = true; refresh(); return; }
    let res;
    try { res = await project.get(`candidates?part=${encodeURIComponent(partId)}`); } catch { res = { rows: st.rows, adopted: st.adopted }; }
    const known = new Set(st.rows.map((r) => r.id));
    if (mark && st.loaded) for (const r of res.rows) if (!known.has(r.id) && r.id !== st.selected) st.fresh.add(r.id);
    st.rows = res.rows;
    st.adopted = res.adopted || null;
    const ids = new Set(st.rows.map((r) => r.id));
    for (const id of [...st.checked]) if (!ids.has(id)) st.checked.delete(id);
    if (!st.selected || !ids.has(st.selected)) st.selected = (st.adopted && ids.has(st.adopted) ? st.adopted : st.rows[st.rows.length - 1]?.id) || null;
    st.loaded = true;
    refresh();
  }

  /** 후보 목록과 결과를 다시 그린다. result=false 면 목록만 */
  function refresh(result = true) {
    if (part()?.kind === 'identity') return;
    if (partId) rail.update(st);
    if (result) showResult();
  }

  async function showResult() {
    if (part()?.kind === 'identity') return;
    const mine = ++renderSeq;
    const problem = st.problem ? h('div', { class: `banner ${st.problem.kind === 'cancelled' ? 'warn' : 'error'}` }, icon('alert'),
      h('div', {}, st.problem.message, st.problem.detail ? h('pre', {}, st.problem.detail) : null)) : null;
    if (st.mode === 'overlay' && st.checked.size >= 2) {
      const recs = (await Promise.all([...st.checked].map(getRecord))).filter(Boolean);
      if (mine !== renderSeq) return;
      disposeResult();
      disposeResult = renderOverlay(out, recs, {
        view: st.view, setView: (patch) => { Object.assign(st.view, patch); showResult(); project.saveView(); },
        remove: (id) => { st.checked.delete(id); if (st.checked.size < 2) st.mode = 'one'; refresh(); project.saveView(); },
        close: () => { st.mode = 'one'; refresh(); },
        select: (id) => { st.selected = id; st.mode = 'one'; refresh(); project.saveView(); },
      });
      if (problem) out.prepend(problem);
      return;
    }
    const rec = st.selected ? await getRecord(st.selected) : null;
    if (mine !== renderSeq) return;
    disposeResult();
    disposeResult = () => {};
    if (!rec) {
      clear(out);
      if (problem) out.append(problem);
      else out.append(h('div', { class: 'empty-state' }, st.loaded ? '아직 추정한 기록이 없습니다. ‘추정’을 누르면 계산하고 기록을 남깁니다.' : '기록을 읽는 중…'));
      return;
    }
    const owner = rec.part ? project.part(rec.part) : part();
    disposeResult = renderSingle(out, rec, {
      project, part: owner, adopted: partId ? st.adopted : owner?.adopted, vintage: project.overview?.vintage?.id, timing: st.timing, said: st.said,
      editorText: area.value, view: st.view,
      setView: (patch) => { Object.assign(st.view, patch); showResult(); project.saveView(); },
      orderedModels: (models) => {
        const first = project.overview?.hs?.model;
        return [...models].sort((a, b) => (a === first ? -1 : b === first ? 1 : 0)).map((name) => ({ name, note: name === first ? '기본([hs] model)' : (project.overview?.models.find((m) => m.name === name)?.desc || '') }));
      },
      actions: { adopt, hsSwap, toEditor, send: (r) => project.sendToTerminal(summaryLine(r)), diag: (r) => project.compute('diag', { target: r.id }), card: (r) => project.openTab({ type: 'record', id: r.id }), dummy,
        copy: (r) => copyText(r.id, `${r.id} — 복사했습니다`) },
    });
    if (problem) out.prepend(problem);
    if (!partId && rec.part) {
      out.prepend(h('div', { class: 'banner info' }, icon('info'), h('div', {}, h('b', { class: 'mono' }, rec.part), ' 의 후보로 기록했습니다. ',
        h('button', { class: 'btn small', type: 'button', style: { 'margin-left': '6px' }, onclick: () => project.openTab({ type: 'bench', part: rec.part, shown: rec.id }) }, '그 식 작업대 열기'))));
    }
  }

  // ---- 하는 일 ----------------------------------------------------------------------------------

  async function estimate() {
    const text = area.value.trim();
    if (running) return;
    if (runButton.dataset.block) { flash(runButton.dataset.block); return; }
    if (!text || project.busy) return;
    const asPart = partId && part() && !edited();
    const o = st.opts;
    const body = { target: asPart ? partId : text, part: !asPart && part() ? partId : undefined, sim: o.sim || undefined, cov: o.cov || undefined,
      smpl: o.s0 || o.s1 ? `${o.s0 || 'first'}:${o.s1 || 'last'}` : undefined, name: o.name || undefined, method: o.method !== 'auto' ? o.method : undefined };
    const clicked = performance.now();
    st.problem = null;
    setRunning(true);
    try {
      const res = await project.compute('est', body, { quiet: true });
      const rec = res.result;
      st.cache.set(rec.id, rec);
      st.selected = rec.id;
      st.mode = 'one';
      st.said = (res.said || '').trim();
      st.view.picked = null;
      st.opts.name = '';
      st.fresh.delete(rec.id);
      st.timing = { total: (performance.now() - clicked) / 1000, compute: res.seconds };
      await showResult();
      requestAnimationFrame(() => {      // 그린 뒤의 시간으로 고친다(성공 기준 S1 — 누른 뒤 화면까지 1초 안)
        st.timing.total = (performance.now() - clicked) / 1000;
        const t = out.querySelector('.timing');
        if (t) t.textContent = `화면까지 ${st.timing.total < 1 ? st.timing.total.toFixed(2) : st.timing.total.toFixed(1)}초 · 계산 ${res.seconds.toFixed(2)}초`;
      });
      loadCandidates();
      project.saveView();
    } catch (err) {
      if (err.kind !== 'busy') { st.problem = { message: err.message, detail: err.detail, kind: err.kind }; showResult(); }
    } finally {
      setRunning(false);
    }
  }

  function setRunning(on) {
    running = on;
    cancelButton.hidden = !on;
    renderStatus();
  }

  function toEditor(rec) {
    area.value = rec.text || '';
    touched = true;
    grow();
    queueCheck.flush();
    renderStatus();
    area.focus();
    project.saveView();
    flash('식 칸으로 가져왔습니다 — 고쳐서 Ctrl+Enter');
  }

  /** 짚은 기간의 더미를 식 칸에 붙인다(계산은 추정을 누를 때) — 꼬리 지시자(@smpl·@inst…)가 있으면 그 앞에 */
  function dummy(period) {
    const term = `@d(${period})`;
    const text = area.value.trimEnd();
    if (text.includes(term)) { flash(`${term} 은 이미 식에 있습니다`); return; }
    const m = TAIL.exec(text);
    area.value = m ? `${text.slice(0, m.index)} ${term}${text.slice(m.index)}` : `${text} ${term}`;
    touched = true;
    grow();
    queueCheck.flush();
    renderStatus();
    area.focus();
    area.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    project.saveView();
    flash(`${term} 을 식에 넣었습니다 — Ctrl+Enter 로 추정`);
  }

  async function adopt(rec) {
    const p = rec.part ? project.part(rec.part) : part();
    if (!p) return;
    const [file, line] = p.where.split(':');
    const same = (rec.text || '').trim() === p.text.trim();
    const prev = p.adopted;
    const warn = [];
    if (rec.criteria && !rec.criteria.pass) warn.push(`판단 기준에 걸린 기록입니다 — ${(rec.criteria.reasons || []).join(', ')}`);
    const vintage = project.overview?.vintage?.id;
    if (vintage && rec.data?.id && rec.data.id !== vintage) warn.push(`지금 자료 회차(${vintage})가 아니라 ${rec.data.id} 로 추정한 기록입니다`);
    const body = h('div', { class: 'adopt' },
      h('p', {}, '이 뒤로 모형은 ', h('b', { class: 'mono' }, p.id), ' 를 이 기록의 계수로 풉니다(풀 때마다 다시 추정하지 않습니다).'),
      warn.map((w) => h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, w))),
      h('h4', {}, '블록 파일 ', h('span', { class: 'mono' }, `${file} ${line}번째 줄`)),
      same ? h('div', { class: 'diff' }, h('span', { class: 'dl' }, `  ${p.text}`), h('span', { class: 'dl hunk' }, '식은 그대로입니다 — 채택표만 바뀝니다'))
        : h('div', { class: 'diff' }, h('span', { class: 'dl del' }, `- ${p.text}`), h('span', { class: 'dl add' }, `+ ${rec.text}`)),
      h('h4', {}, '채택표 ', h('span', { class: 'mono' }, 'EQUATIONS/adopted.toml')),
      h('div', { class: 'diff' }, prev ? h('span', { class: 'dl del' }, `- "${p.id}" = "${prev}"`) : null, h('span', { class: 'dl add' }, `+ "${p.id}" = "${rec.id}"`)),
      h('p', { class: 'muted' }, '바뀜 기록에 남습니다. 되돌리려면 바뀜 기록에서 그 바뀜을 고르세요(', h('code', {}, 'equion history revert'), ').'));
    if (!(await confirmDialog({ title: `${rec.id} 채택`, body, confirm: '채택', wide: true }))) return;
    try {
      const res = await project.compute('adopt', { record: rec.id, part: p.id }, { quiet: true });
      flash(`채택했습니다 — 바뀜 기록 ${res.result.change || ''}`);
      await project.loadOverview();
      await loadCandidates();
    } catch (err) {
      if (err.kind !== 'busy') { st.problem = { message: err.message, detail: err.detail, kind: err.kind }; showResult(); }
    }
  }

  async function hsSwap(rec, model) {
    const p = rec.part ? project.part(rec.part) : part();
    if (!p) return;
    try {
      const res = await project.compute('hs', { part: p.id, record: rec.id, model }, { quiet: true });
      const r = res.result;
      project.openTab({ type: 'record', id: r.id });
      flash(`${r.baseline} 과 견줍니다${r.baseline_new ? ' — 지금 파일로 먼저 풀었습니다' : ''}`);
    } catch (err) {
      if (err.kind !== 'busy') { st.problem = { message: err.message, detail: err.detail, kind: err.kind }; showResult(); }
    }
  }

  area.addEventListener('input', () => { touched = true; grow(); renderStatus(); queueCheck(); project.saveView(); });
  area.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); estimate(); }
    // 식 칸을 떠나지 않고 후보 사이를 오간다
    if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown') && partId) { e.preventDefault(); rail.move(e.key === 'ArrowDown' ? 1 : -1); }
  });

  const isEquation = () => part()?.kind !== 'identity';
  const placeRail = () => { if (partId && isEquation() && !rail.el.isConnected) el.insertBefore(rail.el, out); if (!isEquation()) { rail.el.remove(); clear(out); } };
  renderHead();
  renderForm();
  placeRail();
  showResult();

  const reloadSoon = debounce(() => loadCandidates({ mark: true }), 150);
  let wasIdentity = !isEquation();
  return {
    key, type: 'bench', title: partId || '새 식', mono: !!partId, kind: 'est', el,
    desc: () => ({ type: 'bench', ...(partId ? { part: partId } : { free: desc.free }), shown: st.selected, checked: [...st.checked],
      sort: st.sort, onlyPass: st.onlyPass, tall: st.tall, view: { tab: st.view.tab, otab: st.view.otab }, opts: { cov: st.opts.cov, sim: st.opts.sim, s0: st.opts.s0, s1: st.opts.s1 },
      ...(touched && (!part() || edited()) ? { draft: area.value } : {}) }),
    show() {
      if (!st.loaded && project.overview && isEquation()) loadCandidates();
      requestAnimationFrame(grow);
      if (!st.check && area.value.trim() && isEquation()) queueCheck.flush();
      renderStatus();
    },
    event(e) {
      if (e.type === 'overview') {
        renderHead();
        if (!touched && part()) area.value = part().text;       // 블록 파일의 식이 바뀌었으면 따라간다(쓰던 초안은 그대로 둔다)
        if (wasIdentity !== !isEquation() || !form.firstChild || !isEquation() || (!hadSpan && project.overview?.vintage?.span)) { wasIdentity = !isEquation(); renderForm(); placeRail(); }
        if (!isEquation()) return;
        st.check = null;
        if (area.value.trim() && el.isConnected) queueCheck.flush(); else renderStatus();
        if (el.isConnected) loadCandidates();
      } else if (e.type === 'job') renderStatus();
      else if (e.type === 'record' && e.record?.kind === 'est' && partId && e.record.part === partId && !st.cache.has(e.record.id)) reloadSoon();
      else if (e.type === 'records' && !st.loaded && el.isConnected && project.overview && isEquation()) loadCandidates();
    },
    /** 이미 연 작업대에 '이 기록을 보라' — 쓰던 식과 옵션은 그대로 둔다 */
    open(next) {
      if (!next.shown || next.shown === st.selected) return;
      st.selected = next.shown; st.mode = 'one'; st.timing = null; st.said = ''; st.problem = null; st.view.picked = null;
      if (st.loaded) loadCandidates(); else refresh();
    },
    focus() { area.focus(); },
    estimate,
    dispose() { disposeResult(); },
  };
}
