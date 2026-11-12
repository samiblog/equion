// 노트 화면 (2차판 — D57) — `notes/*.md`를 문서로 읽되, ```equion 블록마다 상태와 ▶ 실행을 붙인다.
//
//   ```equion                         ← [정상 · 낡음 · 실행 안 함 · 손으로 고침] [▶ 실행] [이전 기록과 비교]
//   an unitroot core --trend ct
//   ```
//   (결과 구역 — 그 블록이 만든 기록의 카드)
//
// 실행은 누를 때만(`equion note run 노트 --block n`) — 블록마다 새 기록이 생기고 결과 구역이 바뀐다. 손으로 고친 구역은 묻고 나서 덮는다.
// Python 블록은 앱에서 돌리지 않는다 — 터미널에 그 명령을 붙인다(Enter는 직접). 글을 고치려면 '고치기'(파일 보기의 편집).

import { confirmDialog } from '../dialog.js';
import { renderDoc } from '../md.js';
import { clear, flash, h, icon, kindPill, when } from '../util.js';

const STATUS = {
  ok: ['정상', 'ok'], stale: ['낡음', 'warn'], never: ['실행 안 함', ''], edited: ['손으로 고침', 'warn'], missing: ['없는 기록', 'warn'],
  denied: ['허용 안 됨', 'bad'], run: ['실행함', 'ok'], error: ['오류', 'bad'], skip: ['건너뜀', ''],
};

export function noteView(project, desc) {
  const path = desc.path;
  const el = h('div', { class: 'view note-view' });
  const st = { data: null, error: null, ran: null };
  let loaded = false;

  async function load() {
    loaded = true;
    try { st.data = await project.get(`note?path=${encodeURIComponent(path)}`); st.error = null; } catch (err) { st.error = err.message; }
    render();
  }

  async function run({ block = null, stale = false } = {}) {
    let force = false;
    const blocks = st.data?.blocks || [];
    const edited = blocks.filter((b) => b.status === 'edited' && (block == null || b.block === block));
    if (edited.length) {
      const body = h('div', { class: 'adopt' }, h('p', {}, `손으로 고친 결과 구역이 ${edited.length}개 있습니다(블록 ${edited.map((b) => b.block).join(' · ')}).`),
        h('p', {}, '덮으면 고친 글은 새 결과로 바뀝니다 — 바뀜 기록에 남아 되돌릴 수 있습니다. 덮지 않으면 그 블록은 건너뜁니다.'));
      force = await confirmDialog({ title: '손으로 고친 구역', body, confirm: '덮고 실행', cancel: '건너뛰고 실행' });
    }
    try {
      const res = await project.compute('note/run', { path, ...(block ? { block } : {}), ...(stale ? { stale: true } : {}), ...(force ? { force: true } : {}) }, { quiet: true });
      st.ran = res.result;
      for (const id of res.result.records) project.seen(id);
      const bad = res.result.blocks.filter((b) => ['error', 'denied'].includes(b.status));
      flash(bad.length ? `블록 ${bad.map((b) => b.block).join(' · ')} 이(가) 실패했습니다` : `실행했습니다 — 새 기록 ${res.result.records.length}개`);
    } catch (err) {
      if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    }
    await load();
  }

  async function compare(record) {
    try {
      const hist = await project.get(`an-history?id=${encodeURIComponent(record)}`);
      if (!hist.previous) { flash('같은 분석·같은 대상의 이전 기록이 없습니다'); return; }
      project.openTab({ type: 'ancompare', a: hist.previous, b: record });
    } catch (err) { project.notify({ level: 'error', text: err.message }); }
  }

  function bar(b) {
    const [label, tone] = STATUS[b.status] || [b.status, ''];
    const an = (b.records || []).find((r) => r.startsWith('an:'));
    const runBtn = b.lang === 'python'
      ? h('button', { class: 'btn small', type: 'button', title: 'Python 블록은 앱에서 돌리지 않습니다 — 터미널에 명령을 붙입니다(Enter 는 직접)',
        onclick: () => project.sendToTerminal(`equion note run ${path} --block ${b.block}`) }, icon('send'), '터미널로')
      : h('button', { class: 'btn small primary', type: 'button', 'data-act': 'run-block', 'data-block': String(b.block), disabled: b.status === 'denied' || project.busy,
        title: `equion note run ${path} --block ${b.block} — 블록의 줄마다 새 기록`, onclick: () => run({ block: b.block }) }, icon('play'), '실행');
    return h('div', { class: 'nb-bar', 'data-block': String(b.block) },
      h('span', { class: 'nb-n' }, `블록 ${b.block}`), h('span', { class: `tag ${tone}`.trim(), title: b.detail || '' }, label),
      (b.records || []).slice(0, 4).map((r) => h('button', { class: 'cmd-chip', type: 'button', title: `${r} — 카드 열기`, onclick: () => project.openRecord(r) },
        kindPill(r.split(':')[0]), h('span', { class: 'mono' }, r.split(':').slice(1).join(':')))),
      (b.records || []).length > 4 ? h('span', { class: 'muted' }, `외 ${b.records.length - 4}`) : null,
      h('span', { class: 'grow' }),
      an ? h('button', { class: 'btn small quiet', type: 'button', 'data-act': 'compare-prev', title: '같은 분석·같은 대상의 이전 기록과 나란히', onclick: () => compare(an) }, '이전 기록과 비교') : null,
      runBtn);
  }

  async function render() {
    clear(el);
    const d = st.data;
    const counts = {};
    for (const b of d?.blocks || []) counts[b.status] = (counts[b.status] || 0) + 1;
    const stale = (counts.stale || 0) + (counts.never || 0) + (counts.missing || 0);
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, icon('doc'), h('span', { class: 'mono' }, path.split('/').pop())),
        h('div', { class: 'sub' }, h('span', { class: 'mono' }, path), d ? h('span', {}, `실행 블록 ${d.blocks.length}`) : null,
          Object.entries(counts).map(([k, n]) => h('span', { class: `tag ${(STATUS[k] || [])[1] || ''}`.trim() }, `${(STATUS[k] || [k])[0]} ${n}`)))),
      h('div', { class: 'tools' },
        h('button', { class: 'btn primary', type: 'button', 'data-act': 'run-note', disabled: !d?.blocks.length || project.busy, title: `equion note run ${path} — 모든 equion 블록(Python 블록은 빼고)`, onclick: () => run() }, icon('play'), '노트 전체 실행'),
        h('button', { class: 'btn', type: 'button', 'data-act': 'run-stale', disabled: !stale || project.busy, title: `equion note run ${path} --stale — 낡았거나 아직 실행 안 한 블록만`, onclick: () => run({ stale: true }) }, `낡은 것만 (${stale})`),
        h('button', { class: 'btn quiet', type: 'button', title: '글을 고친다(파일 보기의 편집) — 저장하면 바뀜 기록에', onclick: () => project.openTab({ type: 'file', path, edit: true }) }, icon('code'), '고치기'))));
    if (st.error) { el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, st.error))); return; }
    if (!d) { el.append(h('div', { class: 'empty-state' }, '읽는 중…')); return; }
    if (st.ran) {
      const r = st.ran;
      el.append(h('div', { class: 'banner info' }, icon('info'), h('div', {}, `${when(new Date().toISOString())} 실행 — `,
        r.blocks.map((b) => `블록 ${b.block} ${(STATUS[b.status] || [b.status])[0]}`).join(' · '), r.change ? ` · 바뀜 기록 ${r.change}` : '')));
    }
    if (!d.blocks.length) el.append(h('div', { class: 'banner info' }, icon('info'), h('div', {}, '실행 블록이 없는 노트입니다. 분석 결과의 ‘노트에 담기’나 후보 묶음의 ‘노트로 저장’으로 블록을 더하거나, ‘고치기’로 ```equion 블록을 적습니다.')));
    const doc = h('div', { class: 'of-record note-doc' });
    el.append(doc);
    await renderDoc(doc, d.text, { pid: project.id, dir: path.split('/').slice(0, -1).join('/'), openFile: (p) => project.openTab({ type: 'file', path: p }) });
    // 문서 차례의 실행 블록(```equion · ```python) — 패키지가 센 차례와 같다
    const pres = [...doc.querySelectorAll('pre')].filter((pre) => pre.classList.contains('eq-block') || pre.querySelector('code.language-python'));
    pres.forEach((pre, i) => { const b = d.blocks[i]; if (b) { pre.before(bar(b)); pre.classList.add('nb-code'); } });
  }

  render();
  return {
    key: `note:${path}`, type: 'note', title: path.split('/').pop(), icon: 'doc', el,
    desc: () => ({ type: 'note', path }),
    show() { if (!loaded) load(); },
    event(e) {
      if ((e.type === 'tree' || e.type === 'defs' || e.type === 'change') && loaded && el.isConnected && !project.busy) load();
      if (e.type === 'job') for (const b of el.querySelectorAll('[data-act="run-block"], [data-act="run-note"]')) b.disabled = project.busy;
    },
    dispose() {},
  };
}
