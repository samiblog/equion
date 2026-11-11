// 흐름 화면 — 스크립트(.eqs) 하나를 단계로 보고, 미리 보고, 실행한다.
//
// 스크립트는 원자료에서 보고서까지의 순서를 적은 글이다(`FLOWS/*.eqs` — 한 줄에 명령 하나, `##` 은 묶음 제목).
// 이 화면은 그 글을 단계 줄로 펼친다: 실행하기 전에는 무엇을 하고 어느 파일을 바꾸는지(미리보기 — 기록을 남기지 않는다),
// 실행하면 단계마다 끝난 모양(✓ 통과 · ! 표시하고 계속 · ✗ 멈춤)과 남긴 기록. '이 단계부터'는 앞 단계를 건너뛰고 이어서 돈다.
// 저절로 도는 것은 없다 — 원자료가 들어와도 '실행'을 누를 때만 돈다. Python 단계(`py`)는 앱이 돌리지 않는다(터미널에서).
// 글을 고치는 것은 파일 보기의 '고치기'로 — 저장하면 이 화면이 다시 읽는다.

import { clear, cmdText, copyText, flash, h, icon, kindPill, put, seconds, when, whoLabel } from '../util.js';

const MARK = { ok: ['✓', 'ok', '통과'], flag: ['!', 'warn', '표시하고 계속'], stop: ['✗', 'bad', '멈춤'], error: ['✗', 'bad', '오류'], denied: ['✗', 'bad', '할 수 없는 줄'],
  skip: ['–', 'none', '건너뜀'], interrupted: ['✗', 'bad', '끊김'] };
const RUN = { ok: '끝까지 통과', flag: '표시한 단계가 있습니다', stop: '멈췄습니다', error: '오류로 멈췄습니다', denied: '할 수 없는 줄에서 멈췄습니다', interrupted: '끊겼습니다' };

export function flowView(project, desc) {
  const path = desc.path;
  const name = path.split('/').pop().replace(/\.eqs$/i, '');
  const el = h('div', { class: 'view flow-view' });
  const st = { plan: null, error: null, sets: { ...(desc.sets || {}) }, shown: desc.shown || null, run: null, running: false, lines: [], from: null };
  let loaded = false;
  const save = () => project.saveView();

  /** 이 스크립트의 실행 기록 — 새것부터 */
  const runs = () => project.records.filter((r) => r.kind === 'run' && (r.target === path || (r.command || '').includes(path))).reverse();

  async function plan() {
    loaded = true;
    try {
      st.plan = await project.post('script/plan', { path, sets: st.sets });
      st.error = null;
    } catch (err) {
      st.error = err.message;
    }
    if (!st.shown) st.shown = runs()[0]?.id || null;
    render();
    if (st.shown && !st.run) showRun(st.shown);
  }

  async function showRun(id) {
    st.shown = id;
    save();
    try { st.run = await project.get(`run/view?id=${encodeURIComponent(id)}`); project.seen(id); } catch (err) { st.run = null; st.shown = null; st.error = err.message; }
    render();
  }

  async function start(from = null) {
    if (!st.plan?.ok) return;
    st.running = true; st.lines = []; st.from = from; st.run = null;
    render();
    try {
      const res = await project.compute('script/run', { path, sets: st.sets, ...(from != null ? { from: String(from) } : {}) }, { quiet: true });
      st.running = false;
      flash(`${RUN[res.result.status] || res.result.status} — ${res.result.id}`);
      await showRun(res.result.id);
    } catch (err) {
      st.running = false;
      if (err.kind !== 'busy') st.error = err.message;
      render();
    }
  }

  // ---- 그리기 -----------------------------------------------------------------------------------

  function params() {
    const p = st.plan?.params || {};
    const keys = Object.keys(p);
    if (!keys.length) return null;
    return h('div', { class: 'eq-opts an-opts' }, h('span', { class: 'lead' }, '값'), keys.map((key) => {
      const input = h('input', { class: 'mini-input text', type: 'text', value: st.sets[key] ?? '', placeholder: p[key].join(' '), spellcheck: 'false', 'data-set': key,
        title: `param ${key} — 비우면 스크립트에 적힌 값(${p[key].join(' ')}). 실행할 때 --set ${key}=값` });
      input.addEventListener('change', () => { if (input.value.trim()) st.sets[key] = input.value.trim(); else delete st.sets[key]; save(); plan(); });
      return h('label', { class: 'opt' }, h('span', { class: 'mono' }, key), input);
    }));
  }

  function stepRows() {
    const steps = st.plan?.steps || [];
    const done = Object.fromEntries((st.run?.steps || []).map((s) => [s.n, s]));
    const live = st.running ? Object.fromEntries(st.lines.map((l) => [l.n, l])) : {};
    const out = [];
    let section = null;
    for (const s of steps) {
      if (s.section !== section) {
        section = s.section;
        if (section) out.push(h('div', { class: 'step-sect' }, section));
      }
      const r = st.running ? null : done[s.n];
      const l = live[s.n];
      const mark = r ? MARK[r.status] || ['?', 'none', r.status] : l ? [l.mark, l.mark === '✓' ? 'ok' : l.mark === '!' ? 'warn' : 'bad', ''] : st.running && s.n === (st.lines.length ? st.lines[st.lines.length - 1].n + 1 : (Number(st.from) || 1)) ? ['…', 'busy', '도는 중'] : ['', 'none', ''];
      const changing = (s.effects || []).length;
      out.push(h('div', { class: `step-row ${mark[1]} ${s.skip ? 'skipped' : ''}`.trim(), 'data-step': s.n },
        h('span', { class: `mark ${mark[1]}`, title: mark[2] }, mark[0]), h('span', { class: 'n' }, s.n),
        h('div', { class: 'body' },
          h('div', { class: 'line mono' }, s.kind === 'expect' ? h('span', { class: 'kw' }, 'expect ') : s.kind === 'py' ? h('span', { class: 'kw' }, 'py ') : null, (r?.line || s.line).replace(/^(expect|py)\s+/, '')),
          r ? h('div', { class: 'what' }, r.detail || MARK[r.status]?.[2] || '', (r.records || []).map((id) => h('button', { class: 'link mono', type: 'button', onclick: () => project.openRecord(id) }, id)),
            r.elapsed != null ? h('span', { class: 'muted' }, seconds(r.elapsed)) : null)
            : l ? h('div', { class: 'what' }, l.text)
              : h('div', { class: 'what muted' }, s.kind === 'py' ? 'Python 단계 — 앱은 돌리지 않습니다(터미널에서 equion run 으로)' : changing ? ['바꾸는 것: ', s.effects.join(' · ')] : s.kind === 'expect' ? '앞 단계의 결과를 견준다' : '기록만 남긴다')),
        changing && !r ? h('span', { class: 'tag warn', title: '정의 파일이나 지금 회차를 바꾸는 단계입니다 — 바뀜 기록에 남습니다' }, '바꿈') : null,
        !st.running && s.n > 1 ? h('button', { class: 'btn small quiet from', type: 'button', disabled: project.busy || !st.plan.ok, title: `equion run ${path} --from ${s.n} — 앞 단계는 건너뛰고 여기서부터 다시`, onclick: () => start(s.n) }, '여기부터') : null));
    }
    return out;
  }

  function runHead() {
    const r = st.run;
    if (!r || st.running) return null;
    const m = r.meta;
    return h('div', { class: `banner ${m.status === 'ok' ? 'ok' : m.status === 'flag' ? 'warn' : 'error'}` }, icon(m.status === 'ok' ? 'check' : 'alert'),
      h('div', {}, h('b', {}, RUN[m.status] || m.status), ' — ', h('button', { class: 'link mono', type: 'button', title: '실행 기록의 카드를 연다', onclick: () => project.openRecord(r.id) }, r.id),
        ` · ${when(m.created)} · ${seconds(m.elapsed)}`, m.from ? ` · ${m.from}단계부터` : '',
        m.records?.length ? h('div', { class: 'muted' }, `남긴 기록 ${m.records.length}개`, m.changes?.length ? ` · 정의 바뀜 ${m.changes.length}건(${m.changes.join(' · ')})` : '',
          m.vintage && m.vintage.start !== m.vintage.end ? ` · 자료 회차 ${m.vintage.start} → ${m.vintage.end}` : '') : null),
      h('button', { class: 'btn small', type: 'button', onclick: () => project.openRecord(r.id) }, '카드'));
  }

  function history() {
    const list = runs();
    if (list.length < 2) return null;
    return put(h('div', {}), h('h2', { class: 'sect' }, '지난 실행', h('span', { class: 'count' }, list.length)),
      h('div', { class: 'rec-list' }, list.slice(0, 6).map((r) => h('button', { class: `rec-row ${r.id === st.shown ? 'on' : ''}`.trim(), type: 'button', title: cmdText(r.command), onclick: () => showRun(r.id) },
        kindPill(r.kind), h('span', { class: 'name' }, r.id), h('span', { class: 'metric' }, r.metric || RUN[r.status] || ''), whoLabel(r.who), h('span', { class: 'when' }, when(r.created))))));
  }

  function render() {
    clear(el);
    const p = st.plan;
    const command = `equion run ${path}${Object.entries(st.sets).map(([k, v]) => ` --set ${k}=${/\s/.test(v) ? `'${v}'` : v}`).join('')}`;
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, icon('play'), h('span', { class: 'mono' }, name)), h('div', { class: 'sub' }, p?.title || '스크립트', h('span', { class: 'mono' }, path))),
      h('div', { class: 'tools' },
        h('button', { class: 'btn quiet', type: 'button', title: '스크립트의 글을 고친다 — 저장하면 이 화면이 다시 읽는다', onclick: () => project.openTab({ type: 'file', path, edit: true }) }, icon('doc'), '글 고치기'),
        h('button', { class: 'btn', type: 'button', disabled: st.running, title: 'equion run … --dry-run — 단계마다 무엇을 하는지 다시 읽는다(기록을 남기지 않는다)', onclick: plan }, icon('refresh'), '미리보기'),
        h('button', { class: 'btn primary', type: 'button', 'data-act': 'run', disabled: project.busy || st.running || !p?.ok, title: `${command} — 처음부터 끝까지. 실행 기록(run:)이 남는다`, onclick: () => start() }, icon('play'), '실행'))));
    if (st.error) el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, st.error)));
    if (!p) { if (!st.error) el.append(h('div', { class: 'empty-state' }, '스크립트를 읽는 중…')); return; }
    if (p.problems.length) {
      el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, h('b', {}, `고칠 곳 ${p.problems.length}`), ' — 문제가 있으면 아무것도 실행하지 않습니다.', h('ul', { class: 'plain-list' }, p.problems.map((x) => h('li', {}, x)))),
        h('button', { class: 'btn small', type: 'button', onclick: () => project.openTab({ type: 'file', path, edit: true }) }, '글 고치기')));
    }
    if (p.python.length) el.append(h('div', { class: 'banner info' }, icon('info'), h('div', {}, `Python 단계가 ${p.python.length}개 있습니다(${p.python.join(' · ')}단계) — 앱은 이 단계를 돌리지 않습니다. 모두 돌리려면 터미널에서 `, h('code', {}, command), '.')));
    put(el, runHead(),
      h('div', { class: 'an-form flow-form' }, params(),
        h('div', { class: 'steps' }, stepRows()),
        h('button', { class: 'cmdline', type: 'button', title: '같은 일을 터미널에서 하는 명령 — 누르면 복사합니다', onclick: () => copyText(command, '명령을 복사했습니다') }, h('span', { class: 'prompt' }, '>'), h('span', { class: 'cmd' }, command), icon('copy'))),
      st.running ? h('div', { class: 'muted pad0' }, '도는 중입니다 — 아래 작업 줄에서 취소할 수 있습니다. 끝난 단계의 기록은 띠에 뜹니다.') : null,
      history());
  }

  render();
  return {
    key: `flow:${path}`, type: 'flow', title: name, icon: 'play', mono: true, el,
    desc: () => ({ type: 'flow', path, sets: st.sets, shown: st.shown }),
    show() { if (!loaded) plan(); },
    event(e) {
      if (e.type === 'job') {
        const job = project.job;
        if (st.running && job?.op === 'script_run' && job.state === 'progress' && job.line) {
          const m = /^\[(\d+)\/\d+\]\s+(.*?)\s+([✓!✗x])\s+(.*)$/.exec(job.line);
          if (m && !st.lines.some((l) => l.n === Number(m[1]))) { st.lines.push({ n: Number(m[1]), mark: m[3], text: m[4] }); render(); }
        } else {
          for (const b of el.querySelectorAll('[data-act="run"], .step-row .from')) b.disabled = project.busy || st.running || !st.plan?.ok;
        }
      } else if (e.type === 'defs' && loaded && !st.running) plan();
      else if ((e.type === 'record' || e.type === 'records') && !st.running) render();
    },
    dispose() {},
  };
}
