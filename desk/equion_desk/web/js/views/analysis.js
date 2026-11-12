// 분석 탭 — 등록부의 분석을 골라 돌리고, 결과를 같은 화면에서 본다.
//
//   분석 [단위근 ▾]   대상 [core            ]   [실행]
//   옵션(등록부에서 나온다 — 명령줄 `equion an …` 의 옵션과 같은 것) · 표본
//   > equion an unitroot core --trend ct        ← 실행하기 전에 같은 일을 하는 명령을 그대로 보인다
//   결과 카드(기록 an: 의 summary.md) · [남기기]
//
// 분석은 보는 것이다 — 돌려도 정의 파일은 바뀌지 않는다. 계절조정·파생·ECM 처럼 무언가를 만드는 분석도 미리보기일 뿐이고,
// '남기기'를 눌러야(무엇이 어디에 적히는지 보이고 나서) 시리즈 정의·파생식·식 후보가 된다.
// 화면이 아는 분석은 없다: 이름·대상·옵션·도움말이 모두 등록부(`equion.registry`)에서 온다 — 분석이 늘면 여기도 늘어난다.

import { confirmDialog } from '../dialog.js';
import { addToNote } from '../noteops.js';
import { toModel } from '../partops.js';
import { renderDoc } from '../md.js';
import { clear, cmdText, copyText, debounce, flash, h, icon, kindPill, put, when, whoLabel } from '../util.js';

const MANY = 18;                       // 고를 이름이 이보다 많으면 접어 둔다
const MULTI = new Set(['expr', 'group', 'records']);     // 대상에 이름 여럿을 빈칸으로 띄워 적는 분석
const QUOTE = "'";
const MAKES = { definition: '정의를 만든다', derived: '파생식을 만든다', candidate: '식 후보를 낸다' };

/** 터미널에 치는 글의 낱말 하나 — Python 의 shlex.quote 와 같은 규칙(기록에 적히는 명령과 글자까지 같아야 한다) */
function quote(word) {
  const s = String(word);
  if (s === '') return QUOTE + QUOTE;
  return /[^A-Za-z0-9_@%+=:,./-]/.test(s) ? QUOTE + s.split(QUOTE).join(`${QUOTE}"${QUOTE}"${QUOTE}`) + QUOTE : s;
}

const flagOf = (o) => `--${o.name.replace(/_/g, '-')}`;

/** 옵션의 도움말에서 짧은 이름과 고를 값의 풀이를 얻는다 — '결정항 — n 없음 · c 상수 · ct 상수+추세' → 결정항, {n: 없음, …} */
function explain(o) {
  const help = String(o.help || '');
  let label = help;
  let rest = '';
  let note = '';
  const paren = /^(.*?)\((.*)\)$/.exec(help);
  if (paren) { label = paren[1].trim(); note = paren[2].trim(); }
  else if (help.includes(' — ')) { [label, rest] = help.split(' — ', 2); }
  else if (o.type === 'choice' && o.choices.length && help.startsWith(`${o.choices[0]} `)) { label = ''; rest = help; }
  else {
    const m = /^(.*?)\s+([−-]?\d+ \S+ · .+)$/.exec(help);
    if (m) { label = m[1]; rest = m[2]; }
  }
  const names = {};
  if (o.type === 'choice' && rest) {
    for (const bit of rest.split(' · ')) {
      const key = o.choices.find((c) => bit === c || bit.startsWith(`${c} `));
      if (key) names[key] = bit.slice(key.length).trim();
    }
  }
  const required = /필수/.test(note);
  return { label: label || flagOf(o), flag: !label, names, required };
}

/** 기본값과 다른 옵션만 — 보내는 것도, 명령 글에 적는 것도 이것뿐이다 */
function changed(spec, values) {
  const out = {};
  for (const o of spec?.options || []) {
    const v = values[o.name];
    if (v == null || v === '') continue;
    if (o.type === 'bool') { if (!!v !== !!o.default) out[o.name] = !!v; }
    else if (o.type === 'int' || o.type === 'float') { if (Number.isFinite(Number(v)) && Number(v) !== o.default) out[o.name] = Number(v); }
    else if (String(v) !== String(o.default ?? '')) out[o.name] = String(v);
  }
  return out;
}

function commandText(spec, target, values, smpl, name) {
  const words = ['equion', 'an', spec.name, target.trim()];
  const opts = changed(spec, values);
  for (const o of spec.options) {
    if (!(o.name in opts)) continue;
    const v = opts[o.name];
    if (o.type === 'bool') words.push(o.default ? `--no-${o.name.replace(/_/g, '-')}` : flagOf(o));
    else words.push(flagOf(o), o.type === 'float' && Number.isInteger(v) ? v.toFixed(1) : v);
  }
  if (smpl.trim()) words.push('--smpl', smpl.trim());
  if (name.trim()) words.push('--as', name.trim());
  return words.filter((w) => w !== '').map(quote).join(' ');
}

export function analysisView(project, desc) {
  const el = h('div', { class: 'view analysis' });
  const st = {
    reg: null, error: null, analysis: desc.analysis || null, target: desc.target || '', options: { ...(desc.options || {}) }, smpl: desc.smpl || '', name: '',
    shown: desc.shown || null, rec: null, recError: null, kept: null, running: false, more: false, autorun: !!desc.run,
  };
  let loaded = false;
  let targetInput = null;
  const formBox = h('div', {});
  const outBox = h('div', { class: 'an-out' });
  const recentBox = h('div', {});
  const preview = h('span', { class: 'cmd' });

  const spec = () => st.reg?.analyses.find((a) => a.name === st.analysis) || null;
  const names = () => st.reg?.names || {};
  const save = () => project.saveView();

  async function load() {
    loaded = true;
    try {
      st.reg = await project.get('analyses');
      st.error = null;
      if (!spec()) st.analysis = null;
    } catch (err) {
      st.error = err.message;
    }
    render();
    if (st.autorun) { st.autorun = false; st.shown = null; run(); }
    else if (st.shown && !st.rec) showRecord(st.shown, { form: !st.analysis });
  }
  const reloadNames = debounce(async () => {
    if (!loaded) return;
    try { st.reg = await project.get('analyses'); drawPick(); } catch { /* 다음 알림 때 다시 */ }
  }, 600);

  // ---- 하는 일 ----------------------------------------------------------------------------------

  function choose(name, { target = null, focus = true } = {}) {
    if (st.analysis !== name) { st.analysis = name; st.options = {}; st.name = ''; }
    if (target != null) st.target = target;
    else if (!fits(st.target)) st.target = '';
    render();
    save();
    if (focus) requestAnimationFrame(() => targetInput?.focus());
  }

  /** 지금 적힌 대상이 이 분석이 받는 것인가 — 분석을 바꿨을 때 남길지 비울지 */
  function fits(target) {
    const a = spec();
    const t = target.trim();
    if (!a || !t) return false;
    const n = names();
    const kinds = a.targets;
    if (kinds.includes('assign')) return t.includes('=');
    if (t.includes('=')) return false;
    if (kinds.includes('series') && n.series?.includes(t)) return true;
    if (kinds.includes('group') && n.group?.includes(t)) return true;
    if (kinds.includes('part') && (n.part?.includes(t) || t.startsWith('est:'))) return true;
    if (kinds.includes('model') && n.model?.includes(t)) return true;
    if (kinds.includes('block') && n.block?.includes(t)) return true;
    if (kinds.includes('records')) return /^(hs|sim|est):/.test(t);
    if (kinds.includes('expr')) return !t.includes(':') && !n.group?.includes(t);
    return false;
  }

  async function run() {
    const a = spec();
    if (!a) { flash('분석을 먼저 고르세요'); return; }
    const target = st.target.trim();
    if (!target) { flash('대상을 적으세요'); targetInput?.focus(); return; }
    const need = a.options.find((o) => explain(o).required && !st.options[o.name]);
    if (need) { flash(`${explain(need).label} 칸을 채우세요`); formBox.querySelector(`[data-opt="${need.name}"]`)?.focus(); return; }
    const wrong = a.options.find((o) => outOfRange(o, st.options[o.name]));
    if (wrong) { flash(outOfRange(wrong, st.options[wrong.name])); formBox.querySelector(`[data-opt="${wrong.name}"]`)?.focus(); return; }
    st.running = true; st.recError = null; st.kept = null;
    drawOut();
    try {
      const res = await project.compute('an', { analysis: a.name, target, options: changed(a, st.options), smpl: st.smpl.trim(), name: st.name.trim() }, { quiet: true });
      st.running = false;
      st.name = '';
      const field = formBox.querySelector('[data-field="name"]');
      if (field) field.value = '';
      drawPreview();
      await showRecord(res.result.id, { form: false });
    } catch (err) {
      st.running = false;
      if (err.kind !== 'busy') st.recError = err.message;
      drawOut();
    }
  }

  /** 기록 하나를 이 화면에 — form: 그 기록의 분석·대상·옵션을 폼에도 옮긴다(옵션만 바꿔 다시 돌리기 쉽게) */
  async function showRecord(id, { form = true } = {}) {
    st.shown = id;
    st.recError = null;
    st.kept = null;
    save();
    try {
      const rec = await project.get(`record?id=${encodeURIComponent(id)}`);
      if (st.shown !== id) return;
      st.rec = rec;
      project.seen(id);
      const m = rec.meta || {};
      if (form && st.reg?.analyses.some((a) => a.name === m.analysis)) {
        st.analysis = m.analysis;
        st.target = m.target || '';
        st.options = { ...(m.options || {}) };
        st.smpl = m.smpl || '';
        render();
        return;
      }
    } catch (err) {
      if (st.shown !== id) return;
      st.rec = null;
      st.shown = null;
      st.recError = err.message;
    }
    drawOut();
    drawRecent();
  }

  async function keep() {
    const m = st.rec?.meta || {};
    const mk = m.makes;
    if (!mk) return;
    const id = st.shown;
    let nameInput = null;
    let replaceBox = null;
    let body;
    if (mk.kind === 'definition') {
      const taken = new Set((names().series || []).map((s) => s.toUpperCase()));
      const base = `${mk.series}SA`;
      nameInput = h('input', { class: 'mini-input wide', type: 'text', value: taken.has(base.toUpperCase()) ? `${mk.series}_SA` : base, spellcheck: 'false', 'aria-label': '새 시리즈 이름' });
      replaceBox = h('input', { type: 'checkbox' });
      const line = h('span', { class: 'dl add' });
      const seas = Object.entries(mk.seas || {}).map(([k, v]) => `${k} = ${JSON.stringify(v)}`).join(', ');
      const draw = () => {
        nameInput.disabled = replaceBox.checked;
        line.textContent = replaceBox.checked ? `~ [series.${mk.series}]  seas = { ${seas} }`
          : `+ [series.${nameInput.value.trim() || '이름'}]  ${mk.series} 와 같은 원자료 · seas = { ${seas} }`;
      };
      nameInput.addEventListener('input', draw);
      replaceBox.addEventListener('change', draw);
      draw();
      body = h('div', { class: 'adopt' },
        h('p', {}, h('b', { class: 'mono' }, mk.series), ' 를 계절조정한 시리즈를 ', h('b', {}, '정의'), '로 남깁니다. 값은 여기서 만들지 않습니다 — 다음 ‘자료 만들기’ 때 새 회차에 들어갑니다.'),
        h('label', { class: 'field-row' }, h('span', {}, '새 시리즈 이름'), nameInput),
        h('label', { class: 'check-row' }, replaceBox, h('span', {}, '새 시리즈를 만들지 않고 ', h('b', { class: 'mono' }, mk.series), ' 자체를 계절조정한 것으로 바꾼다')),
        h('h4', {}, '바뀌는 파일 ', h('span', { class: 'mono' }, 'DATA/series.toml')), h('div', { class: 'diff' }, line),
        h('p', { class: 'muted' }, '바뀜 기록에 남고, 거기서 되돌릴 수 있습니다.'));
    } else if (mk.kind === 'derived') {
      nameInput = h('input', { class: 'mini-input wide', type: 'text', value: mk.name || '', spellcheck: 'false', 'aria-label': '시리즈 이름' });
      const line = h('span', { class: 'dl add' });
      const draw = () => { line.textContent = `+ ${nameInput.value.trim() || '이름'} = ${mk.expr}   # ${id}`; };
      nameInput.addEventListener('input', draw);
      draw();
      body = h('div', { class: 'adopt' },
        h('p', {}, '이 식을 ', h('b', {}, '파생식'), '으로 남깁니다. 값은 다음 ‘자료 만들기’ 때 새 회차에 들어갑니다.'),
        h('label', { class: 'field-row' }, h('span', {}, '시리즈 이름'), nameInput),
        h('h4', {}, '바뀌는 파일 ', h('span', { class: 'mono' }, 'DATA/derived.txt')), h('div', { class: 'diff' }, line),
        h('p', { class: 'muted' }, '바뀜 기록에 남고, 거기서 되돌릴 수 있습니다.'));
    } else {
      const eqs = mk.equations || [];
      body = h('div', { class: 'adopt' },
        h('p', {}, `이 분석이 낸 식 ${eqs.length}개를 `, h('b', {}, '식 후보'), '(추정 기록 est:)로 남깁니다. 정의 파일은 바뀌지 않습니다 — 모형에 쓰려면 식 작업대에서 견주어 보고 채택합니다.'),
        h('div', { class: 'diff' }, eqs.map((e) => h('span', { class: 'dl' }, e.text))));
    }
    const label = mk.kind === 'candidate' ? '식 후보로 남기기' : '정의로 남기기';
    if (!(await confirmDialog({ title: `${m.label || '분석'} — ${label}`, body, confirm: label, wide: true }))) return;
    const replace = !!replaceBox?.checked;
    try {
      const res = await project.compute('an/keep', { record: id, name: replace ? '' : nameInput?.value.trim() || '', replace }, { quiet: true });
      st.kept = res.result;
      st.recError = null;
    } catch (err) {
      if (err.kind === 'busy') return;
      st.recError = err.message;
    }
    drawOut();
  }

  // ---- 그리기 -----------------------------------------------------------------------------------

  function drawPreview() {
    const a = spec();
    preview.textContent = a ? commandText(a, st.target.trim() || '대상', st.options, st.smpl, st.name) : '';
    preview.classList.toggle('dim', !st.target.trim());
  }

  /** 대상으로 고를 수 있는 이름들 — 누르면 대상 칸에 들어간다(여럿 받는 분석이면 더하고 뺀다) */
  function drawPick() {
    const box = formBox.querySelector('.an-pick');
    const a = spec();
    if (!box || !a) return;
    clear(box);
    const n = names();
    const kinds = a.targets;
    const multi = kinds.some((k) => MULTI.has(k));
    const words = () => st.target.trim().split(/\s+/).filter(Boolean);
    const setTarget = (value) => { st.target = value; targetInput.value = value; drawPreview(); drawPick(); save(); targetInput.focus(); };
    const groups = [];
    const add = (title, items, mode) => { if (items?.length) groups.push({ title, items, mode }); };
    if (kinds.includes('group')) add('묶음', n.group, 'one');
    if (kinds.includes('model')) add('모형', n.model, 'one');
    if (kinds.includes('block')) add('블록', n.block, 'one');
    if (kinds.includes('part')) add('부품', n.part, 'one');
    if (kinds.includes('series') || kinds.includes('expr')) add('시리즈', n.series, multi ? 'toggle' : 'one');
    if (kinds.includes('assign')) add('시리즈', n.series, 'insert');
    if (kinds.includes('records')) add('기록', project.records.filter((r) => r.kind === 'hs' || r.kind === 'sim').slice(-8).reverse().map((r) => r.id), 'toggle');
    if (kinds.includes('est')) add('추정 기록', project.records.filter((r) => r.kind === 'est').slice(-6).reverse().map((r) => r.id), 'one');
    const single = groups.filter((g) => g.mode === 'one').flatMap((g) => g.items);
    let room = st.more ? Infinity : MANY;
    let hidden = 0;
    for (const g of groups) {
      const row = h('div', { class: 'pick-row' }, h('span', { class: 'k' }, g.title));
      for (const item of g.items) {
        if (room <= 0) { hidden++; continue; }
        room--;
        const on = g.mode === 'toggle' ? words().includes(item) : g.mode === 'one' ? st.target.trim() === item : false;
        row.append(h('button', { class: 'pc', type: 'button', 'aria-pressed': g.mode === 'insert' ? null : String(on), onclick: () => {
          if (g.mode === 'one') setTarget(item);
          else if (g.mode === 'insert') setTarget(`${st.target}${st.target && !/[\s(*/+-]$/.test(st.target) ? ' ' : ''}${item}`);
          else {
            const cur = words().filter((w) => !single.includes(w));       // 묶음처럼 하나만 받는 이름이 적혀 있었다면 그것부터 지운다
            setTarget((cur.includes(item) ? cur.filter((w) => w !== item) : [...cur, item]).join(' '));
          }
        } }, item));
      }
      if (row.children.length > 1) box.append(row);
    }
    if (hidden || (st.more && groups.reduce((sum, g) => sum + g.items.length, 0) > MANY)) {
      box.append(h('button', { class: 'link', type: 'button', onclick: () => { st.more = !st.more; drawPick(); } }, st.more ? '줄이기' : `${hidden}개 더 보기`));
    }
  }

  /** 숫자 칸이 받는 범위 — {min, max} 또는 null. 틀린 값이면 까닭 */
  function outOfRange(o, value) {
    const b = bounds(o);
    if (value === '' || value == null || !b) return null;
    const v = Number(value);
    if (!Number.isFinite(v) || (o.type === 'int' && !Number.isInteger(v))) return `${explain(o).label}: ${o.type === 'int' ? '정수' : '숫자'}를 적으세요`;
    const range = b.min != null && b.max != null ? `${b.min}~${b.max} 사이여야` : b.min != null ? `${b.min} 이상이어야` : `${b.max} 이하여야`;
    if ((b.min != null && v < b.min) || (b.max != null && v > b.max)) return `${explain(o).label}: ${range} 합니다`;
    return null;
  }

  function optionField(o) {
    const ex = explain(o);
    const title = `${flagOf(o)} — ${o.help}`;
    const set = (value) => { if (value === '' || value == null) delete st.options[o.name]; else st.options[o.name] = value; drawPreview(); save(); };
    const cur = st.options[o.name];
    if (o.type === 'bool') {
      const box = h('input', { type: 'checkbox', 'data-opt': o.name });
      box.checked = cur == null ? !!o.default : !!cur;
      box.addEventListener('change', () => set(box.checked));
      return h('label', { class: 'opt check', title }, box, ex.label);
    }
    let input;
    if (o.type === 'choice') {
      input = h('select', { class: 'mini-select', 'data-opt': o.name }, o.choices.map((c) => h('option', { value: c }, ex.names[c] ? `${ex.names[c]} (${c})` : c)));
      input.value = cur ?? o.default ?? o.choices[0];
      input.addEventListener('change', () => set(input.value));
    } else {
      const number = o.type === 'int' || o.type === 'float';
      const b = bounds(o) || {};
      input = h('input', { class: `mini-input ${number ? 'num' : 'text'}`, type: number ? 'number' : 'text', step: o.type === 'float' ? 'any' : number ? '1' : null, min: b.min, max: b.max, 'data-opt': o.name, spellcheck: 'false',
        placeholder: o.default != null ? String(o.default) : ex.required ? '필수' : number ? '자동' : (o.metavar || ''), value: cur != null && cur !== '' ? String(cur) : '' });
      const mark = () => {
        const why = number ? outOfRange(o, input.value.trim()) : null;
        input.classList.toggle('bad', !!why);
        input.setAttribute('aria-invalid', String(!!why));
        input.title = why || (b.min != null || b.max != null ? `${b.min ?? ''}~${b.max ?? ''}` : '');
      };
      input.addEventListener('input', () => { set(input.value.trim()); mark(); });
      mark();
    }
    return h('label', { class: `opt ${ex.required ? 'need' : ''}`.trim(), title }, h('span', { class: ex.flag ? 'mono' : '' }, ex.label), input);
  }

  function drawForm() {
    clear(formBox);
    targetInput = null;
    const reg = st.reg;
    if (!reg) return;
    const a = spec();
    if (!a) { formBox.append(gallery()); return; }
    const groups = [...new Set(reg.analyses.map((x) => x.group))];
    const select = h('select', { class: 'an-select', 'aria-label': '분석' }, groups.map((g) => h('optgroup', { label: g }, reg.analyses.filter((x) => x.group === g).map((x) => h('option', { value: x.name }, x.label)))));
    select.value = a.name;
    select.addEventListener('change', () => { st.shown = null; st.rec = null; st.kept = null; st.recError = null; choose(select.value); });
    const example = (/^equion an \S+ (?:"([^"]*)"|(\S+))/.exec(a.example || '') || []).slice(1).find(Boolean);
    targetInput = h('input', { class: 'an-target', type: 'text', value: st.target, spellcheck: 'false', autocomplete: 'off', 'aria-label': '대상',
      placeholder: `${a.target_labels.join(' · ')}${example ? ` — 예: ${example}` : ''}` });
    targetInput.addEventListener('input', () => { st.target = targetInput.value; drawPreview(); drawPick(); save(); });
    const smpl = h('input', { class: 'mini-input text', type: 'text', value: st.smpl, placeholder: '전체', spellcheck: 'false', 'data-field': 'smpl' });
    smpl.addEventListener('input', () => { st.smpl = smpl.value; drawPreview(); save(); });
    const name = h('input', { class: 'mini-input text', type: 'text', value: st.name, placeholder: '자동', spellcheck: 'false', 'data-field': 'name' });
    name.addEventListener('input', () => { st.name = name.value; drawPreview(); });
    const runBtn = h('button', { class: 'btn primary an-run', type: 'button', title: '분석을 돌린다(Ctrl+Enter · 대상 칸에서는 Enter) — 결과는 기록(an:)으로 남는다', onclick: run }, icon('play'), '실행');
    formBox.append(h('div', { class: 'an-form', onkeydown: (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey || e.target === targetInput)) { e.preventDefault(); run(); }
    } },
    h('div', { class: 'an-top' }, h('label', { class: 'an-field' }, h('span', {}, '분석'), select), h('label', { class: 'an-field grow' }, h('span', {}, '대상'), targetInput), runBtn),
    h('div', { class: 'an-what' }, h('span', {}, a.help), h('span', { class: 'muted' }, `보이는 것 — ${a.results}`),
      a.makes ? h('span', { class: 'tag accent', title: '돌리는 것만으로는 아무것도 바뀌지 않습니다 — 결과를 본 뒤 ‘남기기’를 눌러야 적힙니다' }, `남기면 → ${a.makes_label}`) : null),
    h('div', { class: 'an-pick' }),
    h('div', { class: 'eq-opts an-opts' }, a.options.map(optionField),
      h('label', { class: 'opt', title: '--smpl 처음:끝 — 이 구간의 자료만 쓴다. 상대 기간도 된다(1990Q1:last)' }, h('span', {}, '표본'), smpl),
      h('label', { class: 'opt', title: '--as 이름 — 기록의 이름(비우면 an:분석_0001 처럼 차례로)' }, h('span', {}, '기록 이름'), name)),
    h('button', { class: 'cmdline', type: 'button', title: '같은 일을 터미널에서 하는 명령 — 누르면 복사합니다', onclick: () => copyText(preview.textContent, '명령을 복사했습니다') },
      h('span', { class: 'prompt' }, '>'), preview, icon('copy'))));
    drawPreview();
    drawPick();
  }

  /** 분석을 아직 고르지 않았을 때 — 무엇을 할 수 있는지 갈래마다 한 줄씩 */
  function gallery() {
    const reg = st.reg;
    const groups = [...new Set(reg.analyses.map((x) => x.group))];
    return h('div', { class: 'an-list' }, groups.flatMap((g) => reg.analyses.filter((x) => x.group === g).map((x, i) => h('button', {
      class: `an-row ${i ? '' : 'first'}`.trim(), type: 'button', 'data-analysis': x.name, title: `대상 — ${x.target_labels.join(' · ')}\n보이는 것 — ${x.results}`, onclick: () => choose(x.name),
    }, h('span', { class: 'g' }, i ? '' : g), h('b', {}, x.label), h('span', { class: 'what' }, x.help),
    x.makes ? h('span', { class: 'tag accent', title: `결과를 본 뒤 ‘남기기’를 누르면 ${x.makes_label} 이(가) 됩니다` }, MAKES[x.makes] || x.makes_label) : h('span', {})))));
  }

  function drawOut() {
    clear(outBox);
    if (st.recError) outBox.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, st.recError)));
    if (st.running) { outBox.append(h('div', { class: 'empty-state' }, '계산하는 중…')); return; }
    const rec = st.rec;
    if (!rec || !st.shown) {
      if (spec() && !st.recError) outBox.append(h('div', { class: 'empty-state' }, '대상을 적고 ‘실행’을 누르면 결과가 여기에 나옵니다.'));
      return;
    }
    const m = rec.meta || {};
    const id = st.shown;
    const mk = m.makes;
    const vintage = project.overview?.vintage?.id;
    const keepLabel = mk ? (mk.kind === 'candidate' ? '식 후보로 남기기' : '정의로 남기기') : null;
    outBox.append(h('div', { class: 'result-head' }, kindPill('an'),
      h('button', { class: 'rid', type: 'button', title: '이 기록의 카드를 따로 연다', onclick: () => project.openRecord(id) }, id),
      h('span', { class: 'meta' }, h('b', {}, m.label || ''), h('span', { class: 'mono' }, m.target_label || m.target || ''),
        m.sample ? h('span', {}, `${m.sample[0]} – ${m.sample[1]}`) : null, m.data?.id && m.data.id === vintage ? h('span', { title: '계산에 쓴 자료 회차' }, `자료 ${m.data.id}`) : null, m.who ? whoLabel(m.who) : null, m.created ? h('span', {}, when(m.created)) : null,
        m.data?.id && vintage && m.data.id !== vintage ? h('span', { class: 'tag warn', title: `이 기록은 자료 회차 ${m.data.id} 로 계산했습니다 — 지금 회차는 ${vintage}` }, `다른 회차 ${m.data.id}`) : null),
      h('span', { class: 'grow' }),
      mk && !st.kept ? h('button', { class: 'btn small primary', type: 'button', 'data-act': 'keep', title: `equion an keep ${id} — 무엇이 어디에 적히는지 먼저 보입니다`, onclick: keep }, icon('pin'), keepLabel) : null,
      h('button', { class: 'btn small quiet', type: 'button', 'data-act': 'compare-prev', title: '같은 분석·같은 대상의 이전 기록과 나란히 — 판단이 바뀐 줄을 강조', onclick: () => comparePrev(id) }, icon('diff'), '이전과'),
      h('button', { class: 'btn small quiet', type: 'button', 'data-act': 'to-note', title: '이 기록의 명령과 결과를 노트의 블록으로 담는다 — 다음 회차에 노트에서 다시 실행', onclick: () => addToNote(project, { record: id }) }, icon('doc'), '노트에'),
      h('button', { class: 'btn small quiet', type: 'button', title: '이 기록을 만든 명령을 복사', onclick: () => copyText(cmdText(m.command), '명령을 복사했습니다') }, icon('copy'), '명령')));
    if (st.kept) {
      const k = st.kept;
      const made = k.kind === 'candidate'
        ? h('div', {}, `식 후보 ${k.records.length}개를 남겼습니다 — 식 작업대에서 견주어 채택하거나, 바로 모형의 블록에 넣습니다.`,
          h('div', { class: 'kept-list' }, k.records.map((r, i) => h('div', { class: 'kept-row' },
            h('button', { class: 'link mono', type: 'button', onclick: () => project.openRecord(r) }, r),
            mk?.equations?.[i]?.text ? h('code', {}, mk.equations[i].text) : null,
            mk?.equations?.[i]?.text ? h('button', { class: 'btn small', type: 'button', 'data-act': 'to-model', title: '이 식을 모형이 쓰는 블록에 한 줄로 더하고 이 후보를 채택한다(equion block add · adopt)',
              onclick: () => toModel(project, { text: mk.equations[i].text, record: r }) }, '모형에 넣기') : null))))
        : h('div', {}, h('b', {}, '정의로 남겼습니다.'), ` ${k.what.join(' · ')}`, h('br'), '값은 아직 없습니다 — ‘자료 만들기’로 새 회차를 만들면 들어갑니다.');
      outBox.append(h('div', { class: 'banner ok' }, icon('check'), made,
        k.kind === 'candidate' ? null : h('button', { class: 'btn small primary', type: 'button', onclick: () => project.openTab({ type: 'data', section: 'series' }) }, '자료 작업대로')));
    } else if (mk) {
      outBox.append(h('div', { class: 'banner info' }, icon('info'), h('div', {}, '미리보기입니다 — 아직 아무것도 바뀌지 않았습니다. 마음에 들면 ', h('b', {}, keepLabel), '를 누르세요.')));
    }
    const doc = h('div', { class: 'of-record' });
    outBox.append(doc);
    if (rec.summary) renderDoc(doc, rec.summary, { pid: project.id, dir: rec.path, openFile: (path) => project.openTab({ type: 'file', path }) });
    else doc.append(h('div', { class: 'empty-state' }, '이 기록에는 카드(summary.md)가 없습니다.'));
  }

  async function comparePrev(id) {
    try {
      const hist = await project.get(`an-history?id=${encodeURIComponent(id)}`);
      if (!hist.previous) { flash('같은 분석·같은 대상의 이전 기록이 없습니다 — 다음 회차에 다시 돌리면 견줄 수 있습니다'); return; }
      project.openTab({ type: 'ancompare', a: hist.previous, b: id });
    } catch (err) { project.notify({ level: 'error', text: err.message }); }
  }

  function drawRecent() {
    clear(recentBox);
    const all = project.records.filter((r) => r.kind === 'an');
    if (!all.length) return;
    put(recentBox, h('h2', { class: 'sect' }, '지난 분석', h('span', { class: 'count' }, all.length)),
      h('div', { class: 'rec-list' }, all.slice(-6).reverse().map((r) => h('button', { class: `rec-row ${r.id === st.shown ? 'on' : ''}`.trim(), type: 'button', title: cmdText(r.command), onclick: () => showRecord(r.id) },
        kindPill(r.kind), h('span', { class: 'name' }, r.id), h('span', { class: 'metric' }, r.metric || cmdText(r.command).replace(/^equion an /, '')), whoLabel(r.who), h('span', { class: 'when' }, when(r.created))))));
  }

  function render() {
    clear(el);
    el.append(h('div', { class: 'view-head' },
      h('div', {}, h('h1', {}, '분석 실행'), h('div', { class: 'sub' }, '자료와 식을 살펴봅니다. 돌려도 정의 파일은 바뀌지 않고, 결과는 기록으로 남습니다.')),
      st.analysis && st.reg ? h('div', { class: 'tools' }, h('button', { class: 'btn quiet', type: 'button', title: '할 수 있는 분석을 모두 본다',
        onclick: () => { Object.assign(st, { analysis: null, shown: null, rec: null, kept: null, recError: null }); save(); render(); } }, icon('list'), '분석 모두 보기')) : null));
    if (st.error) el.append(h('div', { class: 'banner error' }, icon('alert'), h('div', {}, st.error)));
    if (!st.reg) { if (!st.error) el.append(h('div', { class: 'empty-state' }, '분석 목록을 읽는 중…')); return; }
    drawForm();
    drawOut();
    drawRecent();
    el.append(formBox, outBox, recentBox);
  }

  render();
  return {
    key: 'analysis', type: 'analysis', title: '분석 실행', icon: 'flask', el,
    desc: () => ({ type: 'analysis', analysis: st.analysis, target: st.target, options: st.options, smpl: st.smpl, shown: st.shown }),
    show() { if (!loaded) load(); },
    open(next) {
      if (next.shown) { showRecord(next.shown); return; }
      if (!next.analysis) return;
      if (!st.reg) {
        Object.assign(st, { analysis: next.analysis, target: next.target || '', options: { ...(next.options || {}) }, shown: null, autorun: !!next.run });
        if (next.smpl !== undefined) st.smpl = next.smpl || '';
        return;
      }
      Object.assign(st, { shown: null, rec: null, kept: null, recError: null });
      if (st.analysis !== next.analysis) { st.analysis = next.analysis; st.name = ''; }
      st.options = { ...(next.options || {}) };                    // 메뉴·분석 탭에서 온 옵션(다시 돌리기) — 없으면 기본값
      if (next.smpl !== undefined) st.smpl = next.smpl || '';       // 지금 표본(작업대 줄)을 따른다
      choose(next.analysis, { target: next.target ?? null, focus: !next.run });
      if (next.run) run();
    },
    event(e) {
      if (e.type === 'records' || e.type === 'record') { drawRecent(); if (spec()?.targets.some((t) => t === 'records' || t === 'est')) drawPick(); }
      else if (e.type === 'defs' || e.type === 'data') reloadNames();
      else if (e.type === 'overview' && st.rec && !st.running) drawOut();
    },
    dispose() {},
  };
}

/**
 * 숫자 옵션의 범위 — 등록부(패키지)는 형(int·float)과 기본값만 준다. 이름으로 상식적인 범위를 두어 칸이 음수 시차 같은 값을 받지 않게 한다
 * (넘치는 값은 패키지가 한 번 더 막는다). 정수 옵션은 모두 셈(시차·기간·횟수)이라 기본은 0 이상 — 결정항(det)만 −1 을 받는다.
 */
export function bounds(o) {
  if (o.type !== 'int') return null;
  const n = String(o.name).toLowerCase();
  if (n === 'det') return { min: -1, max: 1 };
  if (n === 'rank') return { min: 1, max: 20 };
  if (n === 'bins') return { min: 2, max: 200 };
  if (n === 'reps') return { min: 1, max: 10000 };
  if (n === 'irf' || n === 'periods') return { min: 1, max: 400 };
  if (n.includes('lag')) return { min: 0, max: 99 };
  if (o.default != null && Number(o.default) < 0) return null;
  return { min: 0 };
}
