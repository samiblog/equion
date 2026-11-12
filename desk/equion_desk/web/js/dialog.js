// 확인 대화상자와 작은 메뉴 — 파일이 바뀌는 일(채택)은 무엇이 어떻게 바뀌는지 보이고 나서 한다.
// 브라우저의 confirm()·alert() 은 쓰지 않는다(창 모드에서 앱을 멈춘다).

import { h, icon } from './util.js';

/**
 * 가운데 뜨는 확인 상자. body 는 요소. 돌려주는 것: 확인이면 true, 취소·Esc·바깥 누름이면 false.
 * 닫으면 앞서 가리키던 곳으로 돌아간다(키보드로 쓰던 흐름이 끊기지 않게).
 *
 * 입력을 받는 상자(이름 짓기)는 `valid` 로 확인 단추를 지킨다 — true 가 아니면 단추를 끄고 돌려준 글(까닭)을 단추 옆에 보인다.
 * 상자 안의 입력이 바뀔 때마다 다시 본다(비동기 미리보기가 끝난 뒤에는 body 안에서 'dialog-check' 사건을 보내면 된다).
 * `enter` 면 입력칸에서 Enter 가 확인과 같다(한글 조합 중에는 아니다).
 * `alt` 를 주면 세 번째 길(단추 글) — 누르면 'alt' 를 돌려준다(예: 밖에서 바뀐 칸 — 내 값으로 · 밖의 값으로 · 취소).
 */
export function confirmDialog({ title, body, confirm = '확인', cancel = '취소', tone = 'primary', wide = false, valid = null, enter = false, alt = null }) {
  return new Promise((resolve) => {
    const before = document.activeElement;
    const ok = h('button', { class: `btn ${tone}`, type: 'button', 'data-act': 'confirm' }, confirm);
    const no = h('button', { class: 'btn', type: 'button', 'data-act': 'cancel' }, cancel);
    const other = alt ? h('button', { class: 'btn', type: 'button', 'data-act': 'alt' }, alt) : null;
    const why = h('span', { class: 'dialog-why', 'aria-live': 'polite' });
    const card = h('div', { class: `dialog ${wide ? 'wide' : ''}`.trim(), role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
      h('div', { class: 'dialog-head' }, h('h2', {}, title),
        h('button', { class: 'icon-btn', type: 'button', title: '닫기', 'aria-label': '닫기', onclick: () => done(false) }, icon('x'))),
      h('div', { class: 'dialog-body' }, body),
      h('div', { class: 'dialog-foot' }, why, no, other, ok));
    const back = h('div', { class: 'backdrop' }, card);
    /** 확인할 수 있나 — 단추와 까닭 글을 맞춘다 */
    const recheck = () => {
      if (!valid) return true;
      let r;
      try { r = valid(); } catch { r = false; }
      ok.disabled = r !== true;
      why.textContent = r === true || typeof r !== 'string' ? '' : r;
      return r === true;
    };
    function done(value) {
      document.removeEventListener('keydown', onKey, true);
      back.remove();
      if (before instanceof HTMLElement && before.isConnected) before.focus();
      resolve(value);
    }
    function onKey(e) {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); done(false); return; }
      if (e.key === 'Enter' && enter && !e.isComposing && e.target instanceof HTMLInputElement && card.contains(e.target) && e.target.type !== 'checkbox') {
        e.preventDefault();
        if (recheck()) done(true);
        return;
      }
      if (e.key === 'Tab') {             // 상자 안에서만 돈다
        const items = [...card.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')].filter((n) => !n.disabled);
        const first = items[0], last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
    ok.addEventListener('click', () => { if (recheck()) done(true); });
    no.addEventListener('click', () => done(false));
    other?.addEventListener('click', () => done('alt'));
    back.addEventListener('pointerdown', (e) => { if (e.target === back) done(false); });
    for (const type of ['input', 'change', 'dialog-check']) card.addEventListener(type, recheck);
    document.addEventListener('keydown', onKey, true);
    document.body.append(back);
    recheck();
    if (!valid) ok.focus();
    else (card.querySelector('.dialog-body input:not([type=checkbox]):not(:disabled), .dialog-body textarea') || ok).focus();
  });
}

/** 이름 칸의 까닭 글 — 비었으면 '적으세요', 모양이 틀리면 규칙. 맞으면 true(confirmDialog 의 valid 에 그대로) */
export function nameRule(value, { what = '이름', re = /^[A-Za-z][A-Za-z0-9_]*$/, rule = '영문으로 시작 — 영문·숫자·_', max = 60 } = {}) {
  const v = String(value ?? '').trim();
  if (!v) return `${what}을 적으세요`;
  if (!re.test(v)) return `${what}은 ${rule}`;
  if (v.length > max) return `${what}은 ${max}자까지`;
  return true;
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
