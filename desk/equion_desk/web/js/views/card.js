// 결과 카드 — 기록 하나(`work/<종류>/<이름>/`)의 카드 `summary.md` 를 그린다. 손으로 낸 결과도 터미널·Claude 가 낸 결과도 같은 모양이다.
// 기록은 고치지 않는 파일이라(D33) 한 번 읽으면 다시 읽지 않는다.

import { renderDoc } from '../md.js';
import { bytes, clear, cmdText, copyText, h, icon, kindPill, when, whoLabel } from '../util.js';

export function cardView(project, desc) {
  const id = desc.id;
  const kind = String(id).split(':')[0];
  const el = h('div', { class: 'view' });
  let loaded = false;

  async function load() {
    loaded = true;
    clear(el);
    el.append(h('div', { class: 'empty-state' }, '기록을 읽는 중…'));
    let rec;
    try {
      rec = await project.get(`record?id=${encodeURIComponent(id)}`);
    } catch (err) {
      clear(el);
      el.append(h('div', { class: 'view-head' }, h('div', {}, h('h1', {}, kindPill(kind), h('span', { class: 'mono' }, id)))),
        h('div', { class: 'banner error' }, icon('alert'), h('div', {}, err.message)));
      return;
    }
    const m = rec.meta || {};
    clear(el);
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, kindPill(kind), h('span', { class: 'mono' }, id)),
        h('div', { class: 'sub' }, m.who ? whoLabel(m.who) : null, m.created ? h('span', {}, when(m.created)) : null,
          m.command ? h('span', { class: 'mono', title: '이 기록을 만든 명령' }, cmdText(m.command)) : h('span', { class: 'mono' }, rec.path))),
      h('div', { class: 'tools' },
        kind === 'est' && m.part ? h('button', { class: 'btn', type: 'button', onclick: () => project.openTab({ type: 'bench', part: m.part, shown: id }, { replace: true }) }, icon('equation'), '식 작업대에서') : null,
        h('button', { class: 'btn quiet', type: 'button', title: '이름 복사', onclick: () => copyText(id, `${id} — 복사했습니다`) }, icon('copy'), '이름'),
        h('button', { class: 'btn quiet', type: 'button', title: '터미널에 이름을 붙인다(Enter 는 직접)', onclick: () => project.sendToTerminal(id) }, icon('send'), '터미널로'))));
    const doc = h('div', { class: 'of-record' });
    el.append(doc);
    if (rec.summary) {
      await renderDoc(doc, rec.summary, { pid: project.id, dir: rec.path, openFile: (path) => project.openTab({ type: 'file', path }) });
    } else doc.append(h('div', { class: 'empty-state' }, '이 기록에는 카드(summary.md)가 없습니다.'));
    el.append(h('div', { class: 'files-line' }, '파일', rec.files.map((f) => h('button', {
      class: 'file-chip', type: 'button', title: bytes(f.size), onclick: () => project.openTab({ type: 'file', path: `${rec.path}/${f.name}` }),
    }, f.name))));
  }

  return {
    key: `record:${id}`, type: 'record', title: id, mono: true, kind, el,
    desc: () => ({ type: 'record', id }),
    show() { if (!loaded) load(); },
    event() {},
    dispose() {},
  };
}
