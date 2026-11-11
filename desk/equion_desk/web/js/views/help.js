// 도움말 — 앱에 든 글(web/help/ko.md)을 문서로 보인다. 화면의 지도 · 핵심 고리 · 되돌리기 · Claude 와 함께 · 같은 일을 하는 명령 · 손버릇.

import { renderDoc } from '../md.js';
import { h, icon } from '../util.js';

let cached = null;

/** 도움말 글 — 한 번 읽어 둔다 */
export async function helpText() {
  if (cached == null) {
    const res = await fetch('/web/help/ko.md');
    if (!res.ok) throw new Error(`도움말을 읽지 못했습니다(${res.status})`);
    cached = await res.text();
  }
  return cached;
}

export function helpView(project) {
  const el = h('div', { class: 'view help' });
  let loaded = false;

  async function load() {
    loaded = true;
    try {
      await renderDoc(el, await helpText(), { pid: project.id, dir: '', openFile: (path) => project.openTab({ type: 'file', path }) });
    } catch (err) {
      el.replaceChildren(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, err.message)));
    }
  }

  return {
    key: 'help', type: 'help', title: '도움말', icon: 'info', el,
    desc: () => ({ type: 'help' }),
    show() { if (!loaded) load(); },
    event() {},
    dispose() {},
  };
}
