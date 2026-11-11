// 작업 기록(모두 보기)과 바뀜 기록 — 띠와 알림에서 이어지는 목록 화면.
// 고정·메모·되돌리기는 명령으로 한다(`equion work pin`·`equion history revert`) — 화면의 단추는 D5.

import { clear, cmdText, h, icon, KINDS, kindPill, when, WHO, whoLabel } from '../util.js';

export function recordsView(project) {
  const el = h('div', { class: 'view' });
  let filter = 'all';

  function render() {
    clear(el);
    const all = project.records;
    const counts = {};
    for (const r of all) counts[r.kind] = (counts[r.kind] || 0) + 1;
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, '작업 기록'),
        h('div', { class: 'sub' }, '계산할 때마다 work/ 에 남는 기록입니다 — Desk 에서 했든 터미널·Claude 가 했든 같은 곳에, 생기는 순간 뜹니다.')),
      h('div', { class: 'tools' },
        h('button', { class: 'btn quiet', type: 'button', title: '터미널에 명령을 붙인다(Enter 는 직접)', onclick: () => project.sendToTerminal('equion work list') }, icon('send'), 'equion work list'))));
    el.append(h('div', { class: 'filters' },
      h('button', { type: 'button', 'aria-pressed': String(filter === 'all'), onclick: () => { filter = 'all'; render(); } }, '모두', h('span', { class: 'c' }, all.length)),
      Object.keys(KINDS).filter((k) => counts[k]).map((k) => h('button', {
        type: 'button', 'aria-pressed': String(filter === k), onclick: () => { filter = k; render(); },
      }, KINDS[k], h('span', { class: 'c' }, counts[k])))));
    const rows = all.filter((r) => filter === 'all' || r.kind === filter).reverse();
    if (!rows.length) { el.append(h('div', { class: 'empty-state' }, '기록이 없습니다.')); return; }
    el.append(h('div', { class: 'rec-list' }, rows.map((r) => h('button', {
      class: 'rec-row', type: 'button', title: cmdText(r.command), onclick: () => project.openRecord(r.id),
    }, kindPill(r.kind), h('span', { class: 'name' }, r.id),
    h('span', { class: 'metric' }, r.metric || '', r.command ? h('span', { class: 'cmd' }, `   ${cmdText(r.command)}`) : null),
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
        h('button', { class: 'btn quiet', type: 'button', title: '되돌리기 명령을 터미널에 붙인다(Enter 는 직접) — 되돌리는 것도 바뀜 기록에 남는다',
          onclick: () => project.sendToTerminal(`equion history revert ${c.id}`) }, icon('send'), '되돌리기 명령'))));
    if (c.note) detail.append(h('div', { class: 'banner info' }, icon('info'), h('div', {}, c.note)));
    detail.append(h('div', { class: 'card-meta' }, c.files.map((f) => h('div', { class: 'pair' }, h('span', {}, OPS[f.op] || f.op),
      h('button', { class: 'file-chip', type: 'button', onclick: () => project.openTab({ type: 'file', path: f.path }) }, f.path)))));
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
