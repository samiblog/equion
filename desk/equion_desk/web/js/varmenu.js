// 변수 메뉴 (DESK_V2 §2.2) — 고른 변수(하나·여럿)나 묶음에 맞는 일만 보인다. 변수 탭의 우클릭·'할 수 있는 일 ▾' 단추,
// 그리고 화면 어디서든 변수 이름(data-var)을 우클릭하면 같은 메뉴다.
//
// 분석은 화면이 따로 알지 않는다 — 패키지의 등록부(분석마다 받는 대상과 수 count: one·two·many·any)에서 고른다. 분석이 늘면 메뉴도 는다.
// 변환(수준·로그·차분·로그차분·전년동기비)은 그 자리에서 고른다 — 파생 시리즈를 만들지 않고 대상 글이 log(Y) 처럼 된다.
// 메뉴에서 고른 분석은 작업대 줄의 지금 표본으로 바로 돈다. '옵션'을 누르면 돌리지 않고 분석 실행 화면에 대상이 채워진 채로 열린다.

import { h } from './util.js';

export const TRANSFORMS = [
  ['', '수준', (v) => v],
  ['log', '로그', (v) => `log(${v})`],
  ['d', '차분', (v) => `d(${v})`],
  ['dlog', '로그차분', (v) => `dlog(${v})`],
  ['pcy', '전년비', (v) => `@pcy(${v})`],
];

/** 변수 이름들과 변환 → 분석의 대상 글. 묶음이면 그 이름(변환이 없을 때) */
export function targetText({ series = [], group = null }, transform = '') {
  if (group && !transform) return group.name;
  const fn = (TRANSFORMS.find((t) => t[0] === transform) || TRANSFORMS[0])[2];
  const names = group ? group.series : series;
  return names.map(fn).join(' ');
}

/** 고른 것에 맞는 분석 — 등록부의 대상 종류와 수(count)로 */
export function fitting(registry, sel) {
  const n = sel.group ? sel.group.series.length : sel.series.length;
  if (!registry || !n) return [];
  return registry.analyses.filter((a) => {
    if (a.targets.includes('assign')) return false;
    const takes = sel.group ? a.targets.some((t) => t === 'group' || t === 'expr') : n === 1 ? a.targets.some((t) => t === 'series' || t === 'expr') : a.targets.some((t) => t === 'expr' || t === 'group');
    if (!takes) return false;
    const c = a.count || 'any';
    if (n === 1) return c === 'one' || c === 'any';
    if (n === 2) return c !== 'one';
    return c === 'many' || c === 'any';
  });
}

let closeOpen = null;

/**
 * 메뉴를 띄운다. at: 마우스 자리 {x, y} 또는 단추 요소. sel: {series: [이름…], group: {name, series} | null}.
 * 돌려주는 것: 닫는 함수.
 */
export function openVarMenu(project, at, sel) {
  closeOpen?.();
  const side = project.side;
  const reg = side.registry;
  const names = sel.group ? sel.group.series : sel.series;
  const many = names.length > 1 || !!sel.group;
  const menu = h('div', { class: 'menu var-menu', role: 'menu' });
  const close = () => {
    menu.remove();
    document.removeEventListener('pointerdown', away, true);
    document.removeEventListener('keydown', onKey, true);
    window.removeEventListener('blur', close);
    if (closeOpen === close) closeOpen = null;
  };
  closeOpen = close;
  const away = (e) => { if (!menu.contains(e.target) && !(at instanceof Element && at.contains(e.target))) close(); };
  const onKey = (e) => {
    if (e.key === 'Escape') { e.stopPropagation(); close(); if (at instanceof HTMLElement) at.focus(); return; }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      const items = [...menu.querySelectorAll('.menu-item:not(:disabled)')];
      const i = items.indexOf(document.activeElement);
      items[(i + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus();
      e.preventDefault();
    }
  };
  const item = (label, onPick, { hint = '', title = '', disabled = false, extra = null, act = null } = {}) => h('div', { class: 'menu-line' },
    h('button', { class: 'menu-item', type: 'button', role: 'menuitem', disabled, title, 'data-act': act, onclick: () => { close(); onPick(); } }, h('span', {}, label), hint ? h('small', {}, hint) : null),
    extra);
  const sep = (text) => h('div', { class: 'vm-sep' }, text);

  // 머리: 무엇을 골랐나 · 변환
  const title = sel.group ? h('span', {}, '묶음 ', h('b', { class: 'mono' }, sel.group.name), h('small', {}, ` ${names.join(' · ')}`))
    : h('span', { class: 'mono' }, names.length > 5 ? `${names.slice(0, 5).join(' · ')} … (${names.length})` : names.join(' · '));
  const tf = h('div', { class: 'segmented small tf', role: 'group', 'aria-label': '변환' }, TRANSFORMS.map(([key, label]) => h('button', {
    type: 'button', 'aria-pressed': String(side.transform === key), 'data-tf': key, title: key ? `대상을 ${TRANSFORMS.find((t) => t[0] === key)[2]('X')} 꼴로` : '변환 없이',
    onclick: (e) => { side.setTransform(key); for (const b of tf.children) b.setAttribute('aria-pressed', String(b === e.currentTarget)); preview.textContent = targetText(sel, side.transform); },
  }, label)));
  const preview = h('code', { class: 'tf-preview' }, targetText(sel, side.transform));
  menu.append(h('div', { class: 'menu-head' }, title), h('div', { class: 'menu-tf' }, tf, preview));

  // 분석 — 등록부에서
  const list = fitting(reg, sel);
  if (!reg) menu.append(h('div', { class: 'menu-note' }, '분석 목록을 읽는 중…'));
  else if (list.length) {
    menu.append(sep(`분석 — 누르면 바로 돈다 · 표본 ${side.smpl || '전체'}`));
    const grid = h('div', { class: `vm-grid ${list.length > 5 ? 'two' : ''}`.trim() });
    menu.append(grid);
    for (const a of list) {
      const go = (run) => project.openTab({ type: 'analysis', analysis: a.name, target: targetText(sel, side.transform), smpl: side.smpl, run });
      grid.append(item(a.label, () => go(true), {
        act: `an-${a.name}`, title: `${a.help}${a.makes ? `\n결과를 본 뒤 남기면 ${a.makes_label}` : ''}\n→ equion an ${a.name} ${targetText(sel, side.transform)}`,
        extra: h('button', { class: 'menu-opt', type: 'button', title: '돌리지 않고 옵션을 고르는 화면으로', onclick: () => { close(); go(false); } }, '옵션'),
      }));
    }
  }

  // 분석 아닌 일
  menu.append(sep(''));
  const one = !many ? side.variable(names[0]) : null;
  menu.append(item(many ? '그룹 창' : '변수 창', () => project.openTab({ type: 'var', names, group: sel.group?.name || null }),
    { act: 'var-window', hint: many ? '값 나란히 · 차트 · 상관' : '차트 · 값 · 내력 · 분석', title: '가운데에 창을 연다 (두 번 누르기)' }));
  if (one?.parts?.length) {
    for (const p of one.parts.slice(0, 3)) menu.append(item(`이 변수의 식 ${p}`, () => project.openTab({ type: 'bench', part: p }), { act: 'part' }));
  }
  if (!many && one?.users?.length) {
    const users = one.users.filter((p) => !one.parts?.includes(p));
    if (users.length) menu.append(item('이 변수를 쓰는 식', () => side.showUsers(names[0]), { hint: users.slice(0, 3).join(' · ') + (users.length > 3 ? ' …' : '') }));
  }
  menu.append(item('이 변수들로 새 식', () => {
    const [y, ...xs] = names;
    project.openTab({ type: 'bench', draft: `${y} c ${xs.join(' ')}`.trim() });
  }, { act: 'new-eq', hint: `${names[0]} c ${names.slice(1, 4).join(' ')}${names.length > 4 ? ' …' : ''}`.trim(), title: '첫 변수가 좌변 — 식 작업대에서 고쳐 추정한다' }));
  if (many && !sel.group) menu.append(item('묶음으로 저장…', () => side.saveGroup(names), { act: 'save-group', title: 'equion.toml 의 [group] 에 이름을 붙여 둔다' }));
  if (sel.group) {
    menu.append(item('변수로 펼쳐 고르기', () => side.select(sel.group.series), { title: '묶음의 변수들을 하나씩 고른 것으로' }));
    menu.append(item('묶음 지우기…', () => side.removeGroup(sel.group.name), { act: 'remove-group' }));
  }
  menu.append(item('이름을 명령 창에', () => project.command?.put(targetText(sel, side.transform)), { title: '명령 창 입력칸에 대상 글을 넣는다' }));

  document.body.append(menu);
  let x, y;
  if (at instanceof Element) { const r = at.getBoundingClientRect(); x = r.left; y = r.bottom + 4; } else { x = at.x; y = at.y; }
  menu.style.left = `${Math.max(8, Math.min(x, window.innerWidth - menu.offsetWidth - 8))}px`;
  menu.style.top = `${y + menu.offsetHeight > window.innerHeight - 8 ? Math.max(8, (at instanceof Element ? at.getBoundingClientRect().top - 4 : y) - menu.offsetHeight) : y}px`;
  setTimeout(() => {
    document.addEventListener('pointerdown', away, true);
    document.addEventListener('keydown', onKey, true);
    window.addEventListener('blur', close);
  }, 0);
  menu.querySelector('.menu-item:not(:disabled)')?.focus();
  return close;
}

/** 화면 어디서든 data-var 를 단 요소를 우클릭하면 그 변수의 메뉴(계수표·적합도 표·전망 표의 이름) */
export function bindVarClicks(project, root) {
  root.addEventListener('contextmenu', (e) => {
    const node = e.target instanceof Element ? e.target.closest('[data-var]') : null;
    if (!node || !root.contains(node) || !project.side) return;
    const name = node.getAttribute('data-var');
    if (!name || !project.side.variable(name)) return;
    e.preventDefault();
    openVarMenu(project, { x: e.clientX, y: e.clientY }, { series: [project.side.variable(name).name], group: null });
  });
}

