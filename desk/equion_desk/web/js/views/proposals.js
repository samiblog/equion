// 제안 — "이렇게 바꾸면 이렇게 된다"를 적용하기 전에 본다(work/proposals/). 제안은 Claude(또는 사람)가 `equion propose new` 로 만든다.
//
//   · 제안 카드: 바뀔 내용의 차이(지금 파일 대비) · 까닭 · 식 · 미리 계산한 결과(과거 재현이면 전후 RMSPE)
//   · 적용 — 바꿀 파일을 새 내용으로 쓰고 바뀜 기록에 "제안 … 적용"으로 남는다(거기서 되돌린다)
//   · 버림 — 파일은 그대로, 제안 기록은 남는다
//   · 만든 뒤 그 파일이 바뀌었으면 '낡음' — 적용하면 그 바뀜을 덮으므로, 덮겠다고 할 때만 적용한다
//
// 화면은 제안을 만들지 않는다. 받는 길은 둘: 'Claude ▾ 제안 받기'(요청 글을 터미널에 붙인다) · 터미널에서 직접.

import { confirmDialog } from '../dialog.js';
import { clear, copyText, flash, h, icon, kindPill, when, whoLabel } from '../util.js';
import { compareStrip } from './card.js';
import { diffBlock } from './lists.js';

const STATUS = { open: ['열림', 'accent'], applied: ['적용함', 'ok'], dropped: ['버림', ''] };

export function proposalsView(project, desc) {
  const list = h('div', { class: 'list' });
  const detail = h('div', { class: 'detail' });
  const el = h('div', { class: 'split-view proposals' }, list, detail);
  let items = [];
  let selected = desc.id || null;
  let loaded = false;
  let turn = 0;

  const tag = (status) => h('span', { class: `tag ${STATUS[status]?.[1] || ''}`.trim() }, STATUS[status]?.[0] || status);

  function renderList() {
    clear(list);
    if (!items.length) {
      list.append(h('div', { class: 'side-note' }, '아직 제안이 없습니다.\n\n식 작업대·모형 작업대의 ‘Claude ▾ 제안 받기’가 요청 글을 터미널에 붙입니다 — Claude 가 파일은 그대로 두고 제안만 남기면 여기에 뜹니다.'));
      return;
    }
    for (const p of [...items].reverse()) {
      list.append(h('button', { class: `change-row ${p.id === selected ? 'on' : ''}`.trim(), type: 'button', 'data-prop': p.id, onclick: () => select(p.id) },
        h('div', { class: 'l1' }, h('span', { class: 'id' }, p.name), tag(p.status), p.stale?.length ? h('span', { class: 'tag warn' }, '낡음') : null,
          h('span', { class: `who ${p.who === 'claude' ? 'claude' : ''}`.trim() }, whoLabel(p.who)), h('span', { class: 'when' }, when(p.created))),
        h('div', { class: 'l2' }, p.title || ''),
        h('div', { class: 'l3' }, p.files.map((f) => f.path).join(' · '))));
    }
  }

  async function apply(p, thenEdit = false) {
    const stale = p.stale || [];
    const force = h('input', { type: 'checkbox' });
    const body = h('div', { class: 'adopt' },
      h('p', {}, h('b', {}, `제안 ${p.name}`), ` 을 적용합니다 — 파일 ${p.files.length}개를 새 내용으로 쓰고, 바뀜 기록에 “제안 ${p.name} 적용”으로 남습니다(거기서 되돌릴 수 있습니다).`),
      h('div', { class: 'diff' }, p.files.map((f) => h('span', { class: `dl ${f.delete ? 'del' : 'add'}` }, `${f.delete ? '지움' : '고침'}  ${f.path}${f.stale ? '   — 만든 뒤 바뀜' : ''}`))),
      stale.length ? h('label', { class: 'check-row' }, force, h('span', {}, `만든 뒤 바뀐 파일 ${stale.length}개를 덮는다 — 그 사이에 고친 것은 사라집니다(바뀜 기록에는 남아 있습니다)`)) : null,
      h('div', { class: 'cmd-note mono' }, p.commands?.apply || `equion propose apply ${p.name}`));
    if (!(await confirmDialog({ title: '제안 적용', body, confirm: '적용', wide: true }))) return;
    if (stale.length && !force.checked) { flash('적용하지 않았습니다 — 낡은 파일을 덮겠다고 고르지 않았습니다'); return; }
    try {
      await project.compute('proposal/apply', { id: p.id, force: force.checked }, { quiet: true });
      flash(`제안 ${p.name} 을 적용했습니다`);
      await load();
      if (thenEdit) for (const f of p.files.filter((x) => !x.delete).slice(0, 3)) project.openTab({ type: 'file', path: f.path, edit: true });
    } catch (err) {
      if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    }
  }

  async function drop(p) {
    const why = h('input', { class: 'mini-input wide plain', type: 'text', placeholder: '까닭(적지 않아도 됩니다) — 예: 더미로는 설명이 안 된다', 'aria-label': '버리는 까닭' });
    const body = h('div', { class: 'adopt define-form' }, h('p', {}, h('b', {}, `제안 ${p.name}`), ' 을 버립니다. 파일은 그대로이고, 제안과 까닭은 기록으로 남습니다.'),
      h('label', { class: 'field-row' }, h('span', {}, '까닭'), why));
    if (!(await confirmDialog({ title: '제안 버림', body, confirm: '버림', tone: '', wide: true }))) return;
    try {
      await project.compute('proposal/drop', { id: p.id, why: why.value.trim() }, { quiet: true });
      flash(`제안 ${p.name} 을 버렸습니다`);
      await load();
    } catch (err) {
      if (err.kind !== 'busy') project.notify({ level: 'error', text: err.message });
    }
  }

  async function select(id) {
    selected = id;
    renderList();
    project.saveView();
    const mine = ++turn;
    clear(detail);
    if (!id) { detail.append(h('div', { class: 'empty-state' }, items.length ? '왼쪽에서 제안을 고르면 바뀔 내용이 보입니다.' : '제안은 파일을 바꾸기 전에 “이렇게 바꾸면 이렇게 된다”를 보여 주는 기록입니다.')); return; }
    let p;
    try { p = await project.get(`proposal?id=${encodeURIComponent(id)}`); } catch (err) { if (mine === turn) detail.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, err.message))); return; }
    if (mine !== turn) return;
    project.seenProposal(id);
    const open = p.status === 'open';
    detail.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, kindPill('prop'), h('span', { class: 'mono' }, p.name), tag(p.status)),
        h('div', { class: 'sub' }, h('span', {}, p.title || ''), p.who ? whoLabel(p.who) : null, h('span', {}, when(p.created)))),
      h('div', { class: 'tools' },
        open ? h('button', { class: 'btn primary', type: 'button', 'data-act': 'apply', disabled: project.busy, title: '바꿀 파일을 새 내용으로 쓴다 — 바뀜 기록에 남고 거기서 되돌린다', onclick: () => apply(p) }, icon('check'), '적용') : null,
        open ? h('button', { class: 'btn', type: 'button', 'data-act': 'apply-edit', disabled: project.busy, title: '적용한 뒤 바뀐 파일을 고치기로 연다', onclick: () => apply(p, true) }, '적용하고 고치기') : null,
        open ? h('button', { class: 'btn quiet', type: 'button', 'data-act': 'drop', disabled: project.busy, title: '파일은 그대로 두고 제안을 닫는다(기록은 남는다)', onclick: () => drop(p) }, '버림') : null,
        h('button', { class: 'btn quiet', type: 'button', title: '터미널에 제안 이름을 붙인다(Enter 는 직접) — Claude 에게 다듬어 달라고 할 때', onclick: () => project.sendToTerminal(p.id) }, icon('send'), '터미널로'))));
    if (open && p.stale?.length) {
      detail.append(h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, h('b', {}, '낡음'), ` — 제안을 만든 뒤 바뀐 파일: ${p.stale.join(' · ')}. 아래 차이는 지금 파일과 견준 것입니다. 적용하면 그 사이에 고친 것을 덮습니다.`)));
    }
    if (p.decided) {
      const d = p.decided;
      detail.append(h('div', { class: 'banner info' }, icon('info'), h('div', { class: 'grow' }, `${STATUS[p.status]?.[0] || p.status} — `, whoLabel(d.who), ` · ${when(d.at)}`, d.note ? ` · ${d.note}` : ''),
        d.change ? h('button', { class: 'btn small', type: 'button', title: '이 적용의 전후 차이 — 되돌리기는 거기서', onclick: () => project.openTab({ type: 'changes', id: d.change }) }, `바뀜 기록 ${d.change}`) : null));
    }
    detail.append(h('h2', { class: 'sect' }, '까닭'), h('p', { class: 'prop-why' }, p.why || '(적지 않았습니다)'));
    const parts = Object.entries(p.parts || {});
    if (parts.length) {
      detail.append(h('h2', { class: 'sect' }, '식', h('span', { class: 'count' }, parts.length)), h('div', { class: 'prop-parts' }, parts.map(([part, value]) => h('div', { class: 'prop-part' },
        h('button', { class: 'link mono', type: 'button', title: '식 작업대에서 본다', onclick: () => project.openTab(String(value).startsWith('est:') ? { type: 'bench', part, shown: String(value) } : { type: 'bench', part }) }, part),
        h('span', { class: 'arrow' }, '←'),
        String(value).startsWith('est:') ? h('button', { class: 'link mono', type: 'button', title: '그 추정 기록의 카드', onclick: () => project.openRecord(String(value)) }, String(value)) : h('code', {}, String(value))))));
    }
    if (p.previews?.length) {
      detail.append(h('h2', { class: 'sect' }, '미리 계산한 결과', h('span', { class: 'count' }, p.previews.length)));
      for (const r of p.previews) {
        if (r.missing) { detail.append(h('div', { class: 'muted' }, `${r.id} — 기록이 없습니다`)); continue; }
        detail.append(h('div', { class: 'prop-preview' }, kindPill(r.kind), h('button', { class: 'link mono', type: 'button', title: '기록의 카드를 연다', onclick: () => project.openRecord(r.id) }, r.id),
          r.model ? h('span', { class: 'muted' }, `모형 ${r.model}`) : null, r.swaps ? h('span', { class: 'muted' }, '바꿔 끼워 푼 것 — 파일은 그대로') : null));
        const strip = r.vs ? compareStrip(r.vs) : null;
        if (strip) detail.append(strip);
      }
    }
    detail.append(h('h2', { class: 'sect' }, '바꿀 내용', h('span', { class: 'count' }, p.files.length)),
      h('div', { class: 'card-meta' }, p.files.map((f) => h('div', { class: 'pair' }, h('span', {}, f.delete ? '지움' : '고침'),
        h('button', { class: 'file-chip', type: 'button', onclick: () => project.openTab({ type: 'file', path: f.path }) }, f.path), f.stale ? h('span', { class: 'tag warn' }, '만든 뒤 바뀜') : null))),
      p.diff ? diffBlock(p.diff) : h('div', { class: 'empty-state' }, open ? '지금 파일과 차이가 없습니다 — 이미 같은 내용입니다.' : '지금 파일은 이 제안의 내용과 같습니다.'));
    if (p.command) detail.append(h('button', { class: 'cmdline', type: 'button', title: '이 제안을 만든 명령 — 누르면 복사합니다', onclick: () => copyText(p.command, '명령을 복사했습니다') }, h('span', { class: 'prompt' }, '>'), h('span', { class: 'cmd' }, p.command), icon('copy')));
  }

  async function load() {
    loaded = true;
    try { items = (await project.get('proposals')).proposals; } catch { items = []; }
    if (!items.some((p) => p.id === selected)) selected = [...items].reverse().find((p) => p.status === 'open')?.id || items[items.length - 1]?.id || null;
    renderList();
    select(selected);
  }

  return {
    key: 'proposals', type: 'proposals', title: '제안', icon: 'spark', el, flush: true,
    desc: () => ({ type: 'proposals', id: selected }),
    show() { if (!loaded) load(); },
    open(next) { if (next.id) { selected = next.id; if (loaded) load(); } },
    event(e) {
      if (e.type === 'proposal' || e.type === 'change') { if (el.isConnected && loaded && !el.parentElement.hidden) load(); else loaded = false; }
      else if (e.type === 'job') for (const b of detail.querySelectorAll('[data-act]')) b.disabled = project.busy;
    },
    dispose() {},
  };
}
