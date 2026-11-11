// 확인 대화상자와 작은 메뉴 — 파일이 바뀌는 일(채택)은 무엇이 어떻게 바뀌는지 보이고 나서 한다.
// 브라우저의 confirm()·alert() 은 쓰지 않는다(창 모드에서 앱을 멈춘다).

import { h, icon } from './util.js';

/**
 * 가운데 뜨는 확인 상자. body 는 요소. 돌려주는 것: 확인이면 true, 취소·Esc·바깥 누름이면 false.
 * 닫으면 앞서 가리키던 곳으로 돌아간다(키보드로 쓰던 흐름이 끊기지 않게).
 */
export function confirmDialog({ title, body, confirm = '확인', cancel = '취소', tone = 'primary', wide = false }) {
  return new Promise((resolve) => {
    const before = document.activeElement;
    const ok = h('button', { class: `btn ${tone}`, type: 'button' }, confirm);
    const no = h('button', { class: 'btn', type: 'button' }, cancel);
    const card = h('div', { class: `dialog ${wide ? 'wide' : ''}`.trim(), role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
      h('div', { class: 'dialog-head' }, h('h2', {}, title),
        h('button', { class: 'icon-btn', type: 'button', title: '닫기', 'aria-label': '닫기', onclick: () => done(false) }, icon('x'))),
      h('div', { class: 'dialog-body' }, body),
      h('div', { class: 'dialog-foot' }, no, ok));
    const back = h('div', { class: 'backdrop' }, card);
    function done(value) {
      document.removeEventListener('keydown', onKey, true);
      back.remove();
      if (before instanceof HTMLElement && before.isConnected) before.focus();
      resolve(value);
    }
    function onKey(e) {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); done(false); return; }
      if (e.key === 'Tab') {             // 상자 안에서만 돈다
        const items = [...card.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')].filter((n) => !n.disabled);
        const first = items[0], last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
    ok.addEventListener('click', () => done(true));
    no.addEventListener('click', () => done(false));
    back.addEventListener('pointerdown', (e) => { if (e.target === back) done(false); });
    document.addEventListener('keydown', onKey, true);
    document.body.append(back);
    ok.focus();
  });
}

/**
 * 단추 아래에 뜨는 작은 메뉴. items: [{label, hint, onPick, disabled}] 또는 요소. 바깥을 누르거나 Esc 면 닫힌다.
 * 돌려주는 것: 닫는 함수.
 */
export function popMenu(anchor, items, { align = 'left', cls = '' } = {}) {
  document.querySelector('.menu')?.remove();
  const menu = h('div', { class: `menu ${cls}`.trim(), role: 'menu' });
  const close = () => {
    menu.remove();
    document.removeEventListener('pointerdown', away, true);
    document.removeEventListener('keydown', onKey, true);
  };
  const away = (e) => { if (!menu.contains(e.target) && !anchor.contains(e.target)) close(); };
  const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); anchor.focus(); } };
  for (const item of items) {
    if (item instanceof Node) { menu.append(item); continue; }
    if (!item) continue;
    menu.append(h('button', { class: 'menu-item', type: 'button', role: 'menuitem', disabled: item.disabled, title: item.title || '',
      onclick: () => { close(); item.onPick(); } }, h('span', {}, item.label), item.hint ? h('small', {}, item.hint) : null));
  }
  document.body.append(menu);
  const r = anchor.getBoundingClientRect();
  const left = align === 'right' ? r.right - menu.offsetWidth : r.left;
  menu.style.left = `${Math.max(8, Math.min(left, window.innerWidth - menu.offsetWidth - 8))}px`;
  const below = r.bottom + 4;
  menu.style.top = `${below + menu.offsetHeight > window.innerHeight - 8 ? Math.max(8, r.top - menu.offsetHeight - 4) : below}px`;
  setTimeout(() => {
    document.addEventListener('pointerdown', away, true);
    document.addEventListener('keydown', onKey, true);
  }, 0);
  menu.querySelector('button:not(:disabled), input')?.focus();
  return close;
}
