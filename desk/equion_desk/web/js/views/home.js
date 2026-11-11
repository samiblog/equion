// 개요 — 프로젝트를 열면 처음 보이는 화면. 모형·블록과 부품·최근 작업 기록. 여기서 과거 재현·전망을 시킨다(계산은 단추를 눌렀을 때만).

import { clear, h, icon, kindPill, when, whoLabel } from '../util.js';

export function homeView(project) {
  const el = h('div', { class: 'view' });

  function modelCard(model, o) {
    const isHs = o.hs?.model === model.name;
    const isSim = o.forecast?.model === model.name;
    const made = h('div', { class: 'made' },
      model.include.map((name) => h('span', { class: 'pc inc', title: '끼운 모형' }, name)),
      model.blocks.map((name) => h('span', { class: 'pc', title: '블록' }, name)),
      model.exclude.map((name) => h('span', { class: 'pc exc', title: '뺀 식 — 그 목표는 외생(실측)이 된다' }, name)));
    return h('div', { class: 'card' },
      h('div', { class: 'top' }, h('span', { class: 'glyph model' }, 'M'), h('span', { class: 'name' }, model.name),
        isHs || isSim ? h('span', { class: 'tag accent', title: 'equion.toml 의 [hs]·[forecast] 기본 모형' }, '기본') : null),
      h('div', { class: 'desc' }, model.desc || ''),
      made,
      h('div', { class: 'foot' },
        h('button', { class: 'btn small', type: 'button', title: `equion hs ${model.name}`, onclick: () => project.compute('hs', { model: model.name }) }, icon('rewind'), '과거 재현'),
        h('button', { class: 'btn small', type: 'button', title: `equion sim base --model ${model.name}`, onclick: () => project.compute('sim', { scenario: 'base', model: model.name }) }, icon('forward'), '전망'),
        h('span', { class: 'grow' }),
        h('button', { class: 'btn small quiet', type: 'button', title: '터미널에 조립 검사 명령을 붙인다(Enter 는 직접)', onclick: () => project.sendToTerminal(`equion assemble ${model.name}`) }, icon('send'), '조립 검사')));
  }

  function render() {
    clear(el);
    const o = project.overview;
    if (!o) {
      el.append(h('div', { class: 'view-head' }, h('div', {}, h('h1', {}, project.name), h('div', { class: 'sub' }, project.root))));
      if (project.error) el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, '프로젝트를 읽지 못했습니다.', h('pre', {}, project.error))));
      else el.append(h('div', { class: 'empty-state' }, '작업 프로세스를 띄우는 중…'));
      return;
    }
    const nParts = o.blocks.reduce((a, b) => a + b.parts.length, 0);
    const nEq = o.blocks.reduce((a, b) => a + b.parts.filter((p) => p.kind !== 'identity').length, 0);
    const nAdopted = o.blocks.reduce((a, b) => a + b.parts.filter((p) => p.adopted).length, 0);
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, o.project), h('div', { class: 'sub' }, h('span', {}, 'Equion 프로젝트'),
        o.freq ? h('span', {}, { Q: '분기 자료', M: '월 자료', A: '연 자료' }[o.freq] || o.freq) : null,
        o.criteria ? h('span', { title: 'equion.toml 의 [criteria] — 추정 기록마다 통과·걸러짐을 적는다' }, '판단 기준 있음') : null)),
      h('div', { class: 'tools' },
        h('button', { class: 'btn', type: 'button', onclick: () => project.openTab({ type: 'file', path: 'equion.toml' }) }, icon('doc'), 'equion.toml'),
        h('button', { class: 'btn', type: 'button', onclick: () => project.openTab({ type: 'records' }) }, icon('list'), '작업 기록'))));
    if (project.error) el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, '정의 파일에 문제가 있어 지난 내용을 보이고 있습니다.', h('pre', {}, project.error))));
    for (const w of o.warnings || []) el.append(h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, w)));

    const v = o.vintage;
    el.append(h('div', { class: 'facts' },
      h('div', { class: 'fact', style: { 'grid-column': 'span 2' }, title: v?.n_series ? `시리즈 ${v.n_series}개` : '' },
        h('div', { class: 'k' }, v?.id ? ['자료 회차 ', h('span', { class: 'mono' }, v.id)] : '자료'),
        h('div', { class: 'v' }, v?.span ? `${v.span[0]} – ${v.span[1]}` : (o.data_file || '없음'))),
      h('div', { class: 'fact' }, h('div', { class: 'k' }, '모형'), h('div', { class: 'v' }, o.models.length)),
      h('div', { class: 'fact' }, h('div', { class: 'k' }, '블록'), h('div', { class: 'v' }, o.blocks.length)),
      h('div', { class: 'fact' }, h('div', { class: 'k' }, '부품'), h('div', { class: 'v' }, nParts, h('small', {}, `추정식 ${nEq}`))),
      h('div', { class: 'fact' }, h('div', { class: 'k' }, '채택'), h('div', { class: 'v' }, `${nAdopted}`, h('small', {}, `/ ${nEq}`)))));

    el.append(h('h2', { class: 'sect' }, '모형', h('span', { class: 'count' }, o.models.length)));
    el.append(o.models.length ? h('div', { class: 'cards' }, o.models.map((m) => modelCard(m, o)))
      : h('div', { class: 'empty-state' }, 'equion.toml 에 [model.이름] 이 없습니다.'));

    el.append(h('h2', { class: 'sect' }, '블록과 부품', h('span', { class: 'count' }, nParts)));
    el.append(h('div', { class: 'blocks' }, o.blocks.map((b) => h('div', { class: 'block-row' },
      h('div', { class: 'bn' }, h('span', { class: 'mono' }, b.name), h('small', {}, b.desc || '')),
      h('div', { class: 'parts' }, b.parts.map((p) => h('button', {
        class: 'part-chip', type: 'button', title: `${p.text}\n${p.where}`, onclick: () => project.openTab({ type: 'bench', part: p.id }),
      }, h('span', { class: `glyph ${p.kind === 'identity' ? 'identity' : ''}` }, p.kind === 'identity' ? '≡' : 'ƒ'), h('b', {}, p.target),
      p.desc ? h('small', {}, p.desc) : null, p.adopted ? h('span', { class: 'star', title: `채택: ${p.adopted}` }, '★') : null)))))));

    const recent = project.records.slice(-8).reverse();
    el.append(h('h2', { class: 'sect' }, '최근 작업 기록', h('span', { class: 'count' }, project.records.length)));
    el.append(recent.length ? h('div', { class: 'rec-list' }, recent.map((r) => h('button', {
      class: 'rec-row', type: 'button', onclick: () => project.openRecord(r.id),
    }, kindPill(r.kind), h('span', { class: 'name' }, r.id), h('span', { class: 'metric' }, r.metric || ''), whoLabel(r.who), h('span', { class: 'when' }, when(r.created)))))
      : h('div', { class: 'empty-state' }, '아직 기록이 없습니다. 모형의 ‘과거 재현’을 누르거나, 왼쪽에서 식을 골라 추정해 보세요.', h('br'),
        '터미널에서 ', h('code', {}, 'equion est demand:CN'), ' 처럼 친 명령의 기록도 여기에 뜹니다.'));
  }

  render();
  return {
    key: 'home', type: 'home', title: '개요', icon: 'home', pinned: true, el,
    desc: () => ({ type: 'home' }),
    show: render,
    event(e) { if (['overview', 'record', 'records'].includes(e.type)) render(); },
    dispose() {},
  };
}
