// Claude 에게 — 화면에서 보던 것을 터미널의 Claude 에게 넘긴다.
//
// 요청 글(이름과 한 줄 요약 + 어떻게 할지)을 터미널에 Enter 없이 붙인다 — 사람이 이어 치고 Enter 를 누른다(앱이 대신 보내지 않는다).
//   · 맡기기     Claude 가 바로 파일을 고치고 명령으로 계산한다. 고친 것은 바뀜 알림과 바뀜 기록에 남고, 거기서 되돌린다
//   · 제안 받기   아무것도 바뀌지 않는다. Claude 가 제안(equion propose new)만 남기고, 사람이 제안 카드에서 적용하거나 버린다
// Claude Code 가 이 PC 에 없으면 단추는 흐리게 보이고 설치를 안내한다 — 없어도 화면의 모든 기능은 그대로다.

import { popMenu } from './dialog.js';
import { h, icon } from './util.js';

const text = (c, tail) => `${c.name}${c.summary ? ` — ${c.summary}` : ''}${tail}`;

/** 'Claude ▾' 단추. context(): {name, summary} — 무엇에 관한 일인지(이름과 한 줄 요약). 이름이 없으면 단추를 만들지 않는다 */
export function claudeButton(project, context, { cls = 'btn quiet' } = {}) {
  const has = () => !!project.app.state?.claude;
  const button = h('button', {
    class: `${cls} claude-btn ${has() ? '' : 'dim'}`.trim(), type: 'button', 'data-act': 'claude',
    title: 'Claude 에게 — 맡기기 · 제안 받기(요청 글을 터미널에 붙입니다. Enter 는 직접)',
    onclick: () => {
      const c = context() || {};
      if (!c.name) return;
      const off = !has();
      const send = (tail) => project.sendToTerminal(text(c, tail));
      popMenu(button, [
        h('div', { class: 'menu-title' }, 'Claude 에게 — ', h('span', { class: 'mono' }, c.name)),
        off ? h('div', { class: 'menu-note' }, 'Claude Code(claude 명령)를 이 PC 에서 찾지 못했습니다. 설치한 뒤 터미널에서 claude 로 띄우면 쓸 수 있습니다 — 없어도 화면의 모든 기능은 그대로입니다.') : null,
        { label: '맡기기', hint: '바로 고치고 명령으로 계산한다 — 고친 것은 바뀜 기록에서 되돌린다', disabled: off, onPick: () => send('. 바로 고치고 equion 명령으로 확인해 주세요:') },
        { label: '제안 받기', hint: '파일은 그대로 — 제안만 남긴다(적용·버림은 제안 카드에서)', disabled: off, onPick: () => send('. 파일은 고치지 말고 제안만 남겨 주세요(equion propose new):') },
        { label: '이름만 보내기', hint: '이름과 요약을 터미널에 붙인다', onPick: () => send('') },
        h('div', { class: 'menu-sep' }),
        { label: 'Claude Code 에 Equion 알려 주기', hint: '이 프로젝트에 Equion 스킬을 넣는 명령을 붙인다 — 한 번만 하면 된다', onPick: () => project.sendToTerminal('equion guide skill --install project') },
        { label: '제안 목록', hint: 'Claude 가 남긴 제안을 본다', onPick: () => project.openTab({ type: 'proposals' }) },
      ], { cls: 'plain stack', align: 'right' });
    },
  }, icon('spark'), 'Claude', icon('chevron', 'down'));
  return button;
}
