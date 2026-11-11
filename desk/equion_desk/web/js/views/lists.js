// 작업 기록(모두 보기)과 바뀜 기록 — 띠와 알림에서 이어지는 목록 화면.
// 고정·메모는 결과 카드에서 하고 여기서는 가려 본다. 되돌리기는 바뀜 기록에서 — 무엇이 돌아가는지 먼저 보이고 나서(파일 하나만도 된다).

import { confirmDialog } from '../dialog.js';
import { clear, cmdText, flash, h, icon, KINDS, kindPill, when, WHO, whoLabel } from '../util.js';

export function recordsView(project) {
  const el = h('div', { class: 'view' });
  let filter = 'all';
  let picking = false;                 // 기록을 골라 스크립트로 만드는 중
  const picked = new Set();

  /** 고른 기록의 명령을 한 줄씩 적은 스크립트 초안(`FLOWS/<이름>.eqs`) — `equion script new` */
  async function toScript() {
    const ids = project.records.filter((r) => picked.has(r.id)).map((r) => r.id);
    const name = h('input', { class: 'mini-input wide', type: 'text', placeholder: '영문 이름 — 예: weekly', spellcheck: 'false', 'aria-label': '스크립트 이름' });
    const title = h('input', { class: 'mini-input wide plain', type: 'text', placeholder: '한 줄 제목', 'aria-label': '제목' });
    const body = h('div', { class: 'adopt define-form' },
      h('p', {}, `고른 기록 ${ids.length}개를 만든 명령을 차례로 적어 스크립트 초안을 만듭니다(FLOWS/이름.eqs). 초안은 글이라 고칠 수 있고, 실행은 흐름 화면에서 따로 합니다.`),
      h('div', { class: 'diff' }, project.records.filter((r) => picked.has(r.id)).map((r) => h('span', { class: 'dl' }, cmdText(r.command).replace(/^equion /, '')))),
      h('label', { class: 'field-row' }, h('span', {}, '이름'), name), h('label', { class: 'field-row' }, h('span', {}, '제목'), title));
    if (!(await confirmDialog({ title: '스크립트로 저장', body, confirm: '초안 만들기', wide: true }))) return;
    try {
      const res = await project.compute('script/new', { name: name.value.trim(), records: ids, title: title.value.trim() }, { quiet: true });
      picking = false; picked.clear();
      await project.loadOverview();
      flash(`${res.result.path} 를 만들었습니다`);
      project.openTab({ type: 'flow', path: res.result.path });
    } catch (err) {
      if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    }
  }

  function render() {
    clear(el);
    const all = project.records;
    const counts = {};
    for (const r of all) counts[r.kind] = (counts[r.kind] || 0) + 1;
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, '작업 기록'),
        h('div', { class: 'sub' }, '계산할 때마다 work/ 에 남는 기록입니다 — Desk 에서 했든 터미널·Claude 가 했든 같은 곳에, 생기는 순간 뜹니다.')),
      h('div', { class: 'tools' },
        picking ? h('button', { class: 'btn', type: 'button', onclick: () => { picking = false; picked.clear(); render(); } }, '그만두기') : null,
        picking ? h('button', { class: 'btn primary', type: 'button', 'data-act': 'to-script', disabled: !picked.size, onclick: toScript }, icon('play'), `스크립트로 저장${picked.size ? ` (${picked.size})` : ''}`)
          : h('button', { class: 'btn', type: 'button', 'data-act': 'pick', title: '기록을 골라 그 명령들을 스크립트 초안으로 만든다(equion script new)', onclick: () => { picking = true; render(); } }, icon('play'), '스크립트로…'),
        h('button', { class: 'btn quiet', type: 'button', title: '터미널에 명령을 붙인다(Enter 는 직접)', onclick: () => project.sendToTerminal('equion work list') }, icon('send'), 'equion work list'))));
    if (picking) el.append(h('div', { class: 'banner info' }, icon('info'), h('div', {}, '스크립트에 넣을 기록을 누르세요 — 만든 차례대로 한 줄씩 적힙니다. 자료(회차)·실행 기록은 넣을 수 없습니다.')));
    el.append(h('div', { class: 'filters' },
      h('button', { type: 'button', 'aria-pressed': String(filter === 'all'), onclick: () => { filter = 'all'; render(); } }, '모두', h('span', { class: 'c' }, all.length)),
      Object.keys(KINDS).filter((k) => counts[k]).map((k) => h('button', {
        type: 'button', 'aria-pressed': String(filter === k), onclick: () => { filter = k; render(); },
      }, KINDS[k], h('span', { class: 'c' }, counts[k]))),
      all.some((r) => r.pinned) ? h('button', { type: 'button', 'aria-pressed': String(filter === 'pinned'), 'data-filter': 'pinned', onclick: () => { filter = 'pinned'; render(); } }, '고정', h('span', { class: 'c' }, all.filter((r) => r.pinned).length)) : null));
    const rows = all.filter((r) => filter === 'all' || (filter === 'pinned' ? r.pinned : r.kind === filter)).reverse();
    if (!rows.length) { el.append(h('div', { class: 'empty-state' }, '기록이 없습니다.')); return; }
    const can = (r) => !['data', 'run', 'prop'].includes(r.kind) && !!r.command;
    el.append(h('div', { class: `rec-list ${picking ? 'picking' : ''}`.trim() }, rows.map((r) => h('button', {
      class: `rec-row ${picked.has(r.id) ? 'on' : ''}`.trim(), type: 'button', title: cmdText(r.command), disabled: picking && !can(r), 'data-record': r.id,
      onclick: () => { if (!picking) { project.openRecord(r.id); return; } if (picked.has(r.id)) picked.delete(r.id); else picked.add(r.id); render(); },
    }, picking ? h('span', { class: `check-box ${picked.has(r.id) ? 'on' : ''}`.trim() }, picked.has(r.id) ? icon('check') : null) : null, kindPill(r.kind), h('span', { class: 'name' }, r.pinned ? h('span', { class: 'pinmark', title: '고정' }, icon('pin')) : null, r.id),
    h('span', { class: 'metric' }, r.metric || '', r.memo ? h('span', { class: 'memo', title: r.memo }, `“${r.memo}”`) : null, r.command ? h('span', { class: 'cmd' }, `   ${cmdText(r.command)}`) : null),
    whoLabel(r.who), h('span', { class: 'when' }, when(r.created))))));
  }

  return {
    key: 'records', type: 'records', title: '작업 기록', icon: 'list', el,
    desc: () => ({ type: 'records' }),
    show: render,
    event(e) { if ((e.type === 'record' || e.type === 'records') && el.isConnected) render(); },
    dispose() {},
  };
}

const OPS = { added: '새로', removed: '지움', changed: '고침' };

/** 통합 차이(diff.txt)를 색 입혀 그린다 */
export function diffBlock(text) {
  const lines = String(text || '').replace(/\n$/, '').split('\n');
  return h('div', { class: 'diff' }, lines.map((line) => {
    let cls = '';
    if (line.startsWith('--- ')) return null;
    if (line.startsWith('+++ ')) return h('span', { class: 'dl file' }, line.slice(4).replace(/^b\//, ''));
    if (line.startsWith('@@')) cls = 'hunk';
    else if (line.startsWith('+')) cls = 'add';
    else if (line.startsWith('-')) cls = 'del';
    return h('span', { class: `dl ${cls}`.trim() }, line || ' ');
  }));
}

export function changesView(project, desc) {
  const list = h('div', { class: 'list' });
  const detail = h('div', { class: 'detail' });
  const el = h('div', { class: 'split-view' }, list, detail);
  let changes = [];
  let selected = desc.id || null;
  let loaded = false;

  function whoText(c) { return WHO[c.who] || c.who || ''; }

  /** 되돌리기 — 그 바뀜 앞의 내용으로 다시 쓴다(이것도 바뀜 기록에 남는다). file 을 주면 그 파일만 */
  async function revert(c, file = null) {
    const files = file ? c.files.filter((f) => f.path === file) : c.files;
    const command = `equion history revert ${c.id}${file ? ` --file ${file}` : ''}`;
    const body = h('div', { class: 'adopt' },
      h('p', {}, h('b', { class: 'mono' }, c.id), file ? ' 가 고친 파일 가운데 하나만' : ' 가 고친 파일을', ' 그 앞의 내용으로 되돌립니다. 그 뒤에 같은 파일을 또 고쳤으면 그것도 함께 물러납니다 — 되돌린 것도 바뀜 기록에 남아 다시 되돌릴 수 있습니다.'),
      h('div', { class: 'diff' }, files.map((f) => h('span', { class: `dl ${f.op === 'added' ? 'del' : 'add'}` }, `${f.op === 'added' ? '지움(새로 만든 파일)' : f.op === 'removed' ? '되살림' : '앞 내용으로'}  ${f.path}`))),
      h('div', { class: 'cmd-note mono' }, command));
    if (!(await confirmDialog({ title: '되돌리기', body, confirm: file ? '이 파일만 되돌리기' : '되돌리기', wide: true }))) return;
    try {
      const res = await project.compute('revert', { change: c.id, ...(file ? { files: [file] } : {}) }, { quiet: true });
      flash(res.result.change ? `되돌렸습니다 — 바뀜 기록 ${res.result.change}` : '지금 내용이 이미 그 앞과 같습니다(바꾼 것 없음)');
      if (res.result.change) { selected = res.result.change; }
      await load();
    } catch (err) {
      if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    }
  }

  function renderList() {
    clear(list);
    if (!changes.length) { list.append(h('div', { class: 'side-note' }, '바뀜 기록이 없습니다. 정의 파일(equion.toml·블록 파일·자료 정의·가정…)이 바뀌면 전후 차이가 여기에 남습니다.')); return; }
    for (const c of [...changes].reverse()) {
      list.append(h('button', { class: `change-row ${c.id === selected ? 'on' : ''}`.trim(), type: 'button', onclick: () => select(c.id) },
        h('div', { class: 'l1' }, h('span', { class: 'id' }, c.id), h('span', { class: `who ${c.who === 'claude' ? 'claude' : ''}`.trim() }, whoText(c)),
          h('span', { class: 'plus' }, `+${c.plus}`), h('span', { class: 'minus' }, `−${c.minus}`), h('span', { class: 'when' }, when(c.created))),
        h('div', { class: 'l2' }, c.how || ''),
        h('div', { class: 'l3' }, c.files.map((f) => f.path).join(' · '))));
    }
  }

  async function select(id) {
    selected = id;
    renderList();
    project.saveView();
    clear(detail);
    if (!id) { detail.append(h('div', { class: 'empty-state' }, '왼쪽에서 바뀜을 고르면 전후 차이가 보입니다.')); return; }
    let c;
    try { c = await project.get(`change?id=${encodeURIComponent(id)}`); } catch (err) { detail.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, err.message))); return; }
    if (selected !== id) return;
    detail.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, h('span', { class: 'mono' }, c.id), h('span', { class: 'tag' }, whoText(c))),
        h('div', { class: 'sub' }, h('span', {}, c.how || ''), h('span', {}, when(c.created)), c.run ? h('span', { class: 'mono' }, c.run) : null,
          c.reverts ? h('span', {}, `${c.reverts} 을 되돌림`) : null)),
      h('div', { class: 'tools' },
        h('button', { class: 'btn', type: 'button', 'data-act': 'revert', disabled: project.busy, title: '이 바뀜 앞의 내용으로 되돌린다 — 무엇이 돌아가는지 먼저 보이고, 되돌린 것도 바뀜 기록에 남는다',
          onclick: () => revert(c) }, icon('rewind'), '되돌리기'))));
    if (c.note) detail.append(h('div', { class: 'banner info' }, icon('info'), h('div', {}, c.note)));
    detail.append(h('div', { class: 'card-meta' }, c.files.map((f) => h('div', { class: 'pair' }, h('span', {}, OPS[f.op] || f.op),
      h('button', { class: 'file-chip', type: 'button', onclick: () => project.openTab({ type: 'file', path: f.path }) }, f.path),
      c.files.length > 1 ? h('button', { class: 'btn small quiet', type: 'button', 'data-act': 'revert-file', disabled: project.busy, title: '이 파일만 그 앞의 내용으로 되돌린다', onclick: () => revert(c, f.path) }, '이 파일만 되돌리기') : null))));
    detail.append(c.diff ? diffBlock(c.diff) : h('div', { class: 'empty-state' }, '글 차이가 없습니다.'));
  }

  async function load() {
    loaded = true;
    try { changes = (await project.get('changes')).changes; } catch { changes = []; }
    if (!selected && changes.length) selected = changes[changes.length - 1].id;
    renderList();
    select(selected);
  }

  return {
    key: 'changes', type: 'changes', title: '바뀜 기록', icon: 'history', el, flush: true,
    desc: () => ({ type: 'changes', id: selected }),
    show() { if (!loaded) load(); },
    open(next) { if (next.id) { selected = next.id; if (loaded) load(); } },
    event(e) { if (e.type === 'change') { if (el.isConnected && loaded) { selected = e.change.id; load(); } else loaded = false; } },
    dispose() {},
  };
}
