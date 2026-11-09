#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""작업 명령(D33, E3) — `equion est · adopt · compare · hs · work · history`.

    equion est 부품|"식" [--as 이름] [--for 부품] [--method auto|ls|tsls] [--smpl S:E] [--sim]
    equion adopt est:이름 [--part 부품]
    equion compare 기록… | --target CN | --part demand:CN
    equion hs [모형|블록] [--range S:E] [--mode] [--swap 부품=est:이름|"식"]… [--vs hs:이름] [--as 이름] | --replay hs:이름
    equion est --adopted [모형] --adopt never|if_pass|all      (채택한 식을 다시 추정 — 정책대로 새 계수 채택)
    equion sim [시나리오…] [--model] [--range next:8] [--vintage 회차] [--vs sim:이름] [--as 이름]
    equion propose new|list|show|apply|drop          equion export 기록… --xlsx 파일
    equion work list|show|pin|unpin|memo|clean        equion history list|show|revert

모두 프로젝트 폴더(`-p`, 기본 지금 폴더)에서 돌고, 출력은 짧은 글(기본) 또는 `--json`. 계산은 할 때마다 `work/`에 기록을 남긴다.
입력 오류(없는 부품·기록·이름 겹침·조립 문제)는 종료 코드 3.
"""

import json
import os
import sys
from .errors import fail

from .runner import EXIT_INPUT, EXIT_OK

PROG = "equion"
COMMANDS = ("est", "adopt", "compare", "hs", "sim", "propose", "export", "work", "history")


def _common(sp):
    sp.add_argument("--project", "-p", default=".", metavar="폴더", help="프로젝트 폴더(기본: 지금 폴더)")
    sp.add_argument("--json", action="store_true", help="결과를 JSON으로")
    return sp


def add_parsers(sub):
    e = _common(sub.add_parser("est", help="식 하나를 추정해 기록을 남긴다(부품 또는 식 글자 — 후보)"))
    e.add_argument("target", nargs="?", metavar="부품|식",
                   help='부품 블록:목표(블록 파일의 그 줄) 또는 식 글자(예: "CN c Y CN(-1)") — --adopted면 모형·블록')
    e.add_argument("--as", dest="as_name", metavar="이름", help="기록 이름(기본: 목표변수_0001 …)")
    e.add_argument("--for", dest="part", metavar="부품", help="어느 부품의 후보인지(목표가 같은 식이 여럿일 때)")
    e.add_argument("--method", choices=("auto", "ls", "tsls"), default="auto", help="추정법(기본 auto — @inst가 있으면 tsls)")
    e.add_argument("--smpl", metavar="S:E", help="표본(상대 기간 가능 — 1990Q1:last)")
    e.add_argument("--sim", action="store_true", help="식 하나의 동태 모의([hs] range, 다른 변수는 실측)와 RMSPE")
    e.add_argument("--cov", help="계수 공분산(white · hac …)")
    e.add_argument("--adopted", action="store_true", help="모형(기본 [hs] model)의 추정식을 모두 지금 자료로 다시 추정")
    e.add_argument("--adopt", choices=("never", "if_pass", "all"), default="never",
                   help="--adopted의 채택 정책(기본 never — 기록만, if_pass — 판단 기준을 통과한 식만)")

    a = _common(sub.add_parser("adopt", help="추정 기록을 부품의 채택 계수로(블록 파일의 줄·채택표를 고치고 바뀜 기록에)"))
    a.add_argument("record", metavar="est:이름", help="채택할 추정 기록")
    a.add_argument("--part", metavar="부품", help="부품(기록이 후보로 묶인 부품이 아니면)")

    c = _common(sub.add_parser("compare", help="기록 비교 — 추정 후보(적합·진단·기준·단독 모의) 또는 HS(변수별 RMSPE)"))
    c.add_argument("records", nargs="*", metavar="기록", help="est:… · hs:…")
    c.add_argument("--target", metavar="변수", help="이 목표변수의 추정 기록 전부")
    c.add_argument("--part", metavar="부품", help="이 부품의 후보 전부")

    h = _common(sub.add_parser("hs", help="과거 재현을 풀고 기록을 남긴다(바꿔 끼우기·전후 비교·그때 그대로 다시)"))
    h.add_argument("model", nargs="?", metavar="모형|블록", help="모형 또는 블록(기본: [hs] model)")
    h.add_argument("--range", metavar="S:E", help="구간(기본: [hs] range — 상대 기간 가능)")
    h.add_argument("--mode", choices=("dynamic", "static", "fit"), help="풀이 방식(기본: [hs] mode)")
    h.add_argument("--swap", action="append", default=[], metavar="부품=값",
                   help='파일을 바꾸지 않고 바꿔 끼우기 — 값은 est:기록(그 계수) 또는 식 글자(여러 번)')
    h.add_argument("--vs", metavar="hs:이름", help="견줄 HS 기록 — 변수별 RMSPE 전후")
    h.add_argument("--as", dest="as_name", metavar="이름", help="기록 이름(기본 hs_0001 …)")
    h.add_argument("--replay", metavar="hs:이름", help="그 기록의 조립 명세로 그대로 다시(지금 파일과 무관)")

    sm = _common(sub.add_parser("sim", help="전망·시나리오를 풀고 기록을 남긴다(가정 세트·보정항·시나리오 파일)"))
    sm.add_argument("scenarios", nargs="*", metavar="시나리오", help="base(기준선) 또는 SCENARIOS/의 이름(여럿이면 하나씩, 기본 base)")
    sm.add_argument("--model", metavar="모형", help="모형(기본: 시나리오 → [forecast] → [hs] model)")
    sm.add_argument("--range", metavar="S:E", help="전망 구간(기본 [forecast] range, 없으면 next:8)")
    sm.add_argument("--vintage", metavar="회차", help="다른 자료 회차로(지금 회차는 그대로)")
    sm.add_argument("--vs", metavar="sim:이름", help="견줄 전망 기록 — 연간 증가율 전후")
    sm.add_argument("--as", dest="as_name", metavar="이름", help="기록 이름(시나리오가 하나일 때, 기본 연-월_시나리오)")
    sm.add_argument("--mode", choices=("dynamic", "static"), help="풀이 방식(기본 [forecast] mode, 없으면 dynamic)")

    pr = sub.add_parser("propose", help="제안 — 파일을 바꾸기 전에 보여 주기(만들기·목록·보기·적용·버림)")
    psub = pr.add_subparsers(dest="propose_command", metavar="동작")
    psub.required = True
    pn = _common(psub.add_parser("new", help="제안을 만든다(파일은 그대로)"))
    pn.add_argument("name", nargs="?", metavar="이름", help="제안 이름(기본 p1, p2 …)")
    pn.add_argument("--title", default="", help="제목")
    pn.add_argument("--why", default="", help="까닭(근거 기록 이름을 넣는다)")
    pn.add_argument("--part", action="append", default=[], metavar="부품=값", help="식 바꾸기 — 값은 est:기록(그 식으로 바꾸고 채택) 또는 식 글자")
    pn.add_argument("--file", action="append", default=[], metavar="경로=새파일", help="파일 통째로 — 프로젝트 안 경로=새 내용 파일")
    pn.add_argument("--preview", action="append", default=[], metavar="기록", help="미리 계산한 기록(hs:… · sim:… · est:…)")
    _common(psub.add_parser("list", help="제안 목록"))
    ps = _common(psub.add_parser("show", help="제안 하나 — 까닭·차이·미리 계산"))
    ps.add_argument("name", metavar="이름")
    pa = _common(psub.add_parser("apply", help="적용 — 파일을 바꾸고 바뀜 기록에(낡았으면 --force)"))
    pa.add_argument("name", metavar="이름")
    pa.add_argument("--force", action="store_true", help="만든 뒤 파일이 바뀌었어도 적용")
    pd_ = _common(psub.add_parser("drop", help="버림 — 파일은 그대로, 제안 기록은 남는다"))
    pd_.add_argument("name", metavar="이름")
    pd_.add_argument("--why", default="", help="버린 까닭")

    ex = _common(sub.add_parser("export", help="기록의 값·값의 종류·출처를 엑셀로"))
    ex.add_argument("records", nargs="+", metavar="기록", help="est:… · hs:… · sim:… · data:회차")
    ex.add_argument("--xlsx", required=True, metavar="파일", help="만들 엑셀 파일(.xlsx — 프로젝트 기준 경로)")

    w = sub.add_parser("work", help="작업 기록 — 목록·보기·고정·메모·정리")
    wsub = w.add_subparsers(dest="work_command", metavar="동작")
    wsub.required = True
    wl = _common(wsub.add_parser("list", help="기록 목록(새것이 아래)"))
    wl.add_argument("--kind", choices=("est", "hs", "sim", "an", "run"), help="종류")
    wl.add_argument("--target", metavar="이름", help="대상(목표변수·모형)")
    wl.add_argument("--part", metavar="부품", help="이 부품의 후보")
    wl.add_argument("--limit", type=int, default=30, help="보일 수(기본 30, 0이면 전부)")
    ws = _common(wsub.add_parser("show", help="기록 하나 — 짧은 글(--md면 카드 summary.md)"))
    ws.add_argument("record", metavar="기록")
    ws.add_argument("--md", action="store_true", help="카드(summary.md)를 그대로")
    for nm, hl in (("pin", "고정(정리에서 빠진다)"), ("unpin", "고정 풀기")):
        sp = _common(wsub.add_parser(nm, help=hl))
        sp.add_argument("record", metavar="기록")
    wm = _common(wsub.add_parser("memo", help="메모(기록은 그대로, marks.json에)"))
    wm.add_argument("record", metavar="기록")
    wm.add_argument("text", metavar="글")
    wc = _common(wsub.add_parser("clean", help="정리 — 고정·채택·참조되지 않은 기록(기본은 목록만, --yes면 지움). 실행 기록(run:)과 그 "
                                                "단계의 기록은 남긴다 — 실행 기록은 --kind run일 때만"))
    wc.add_argument("--kind", choices=("est", "hs", "sim", "an", "run"), help="종류")
    wc.add_argument("--yes", action="store_true", help="목록의 기록을 지운다")

    hi = sub.add_parser("history", help="바뀜 기록 — 정의 파일이 누가·언제·어떻게 바뀌었나, 되돌리기")
    hsub = hi.add_subparsers(dest="history_command", metavar="동작")
    hsub.required = True
    hl = _common(hsub.add_parser("list", help="바뀜 목록(새것이 아래)"))
    hl.add_argument("--limit", type=int, default=30, help="보일 수(기본 30, 0이면 전부)")
    hs_ = _common(hsub.add_parser("show", help="바뀜 하나 — 파일과 차이"))
    hs_.add_argument("change", metavar="h0001")
    hr = _common(hsub.add_parser("revert", help="그 바뀜 앞의 내용으로 되돌린다(이것도 바뀜 기록에 남는다)"))
    hr.add_argument("change", metavar="h0001")


# ---------------------------------------------------------------------------
def _range(text):
    if not text:
        return None, None
    if ":" not in text:
        raise ValueError(f"--range는 시작:끝 꼴입니다: {text!r}")
    s, e = [t.strip() or None for t in text.split(":", 1)]
    return s, e


def _swaps(items):
    out = {}
    for it in items:
        if "=" not in it:
            raise ValueError(f"--swap은 부품=값 꼴입니다(예: demand:CN=est:cons_c5): {it!r}")
        k, v = it.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _flags(p, store, rec, adopted, marks):
    f = []
    m = rec.meta
    if rec.kind == "est" and adopted.get(m.get("part") or "") == rec.id:
        f.append("★채택")
    cr = m.get("criteria")
    if cr is not None:
        f.append("통과" if cr["pass"] else "걸러짐")
    if marks.get(rec.id, {}).get("pinned"):
        f.append("고정")
    d = m.get("data") or {}
    vid = (m.get("vintage") or {}).get("end") if rec.kind == "run" else (d.get("id") if d.get("kind") == "vintage" else None)
    if vid and p.vintage and vid != p.vintage:          # 실행 기록은 끝났을 때의 회차로(시작 회차는 record.json에)
        f.append(f"회차 다름({vid})")
    if marks.get(rec.id, {}).get("memo"):
        f.append(f"메모: {marks[rec.id]['memo']}")
    return f


def _metric(rec):
    from ..projects.records import pct, short
    m = rec.meta
    if rec.kind == "est":
        return f"R²adj {short((m.get('stats') or {}).get('adj_r_squared'))} · {m.get('text')}"
    if rec.kind == "hs":
        rm = list((m.get("rmspe") or {}).items())[:3]
        return f"{m.get('model')} {m['range'][0]}~{m['range'][1]} · " + " · ".join(f"{k} {pct(v)}" for k, v in rm)
    if rec.kind == "sim":
        ann = list((m.get("annual") or {}).items())[:1]
        g = " · ".join(f"{y} {v} {pct(x)}" for y, row in ann for v, x in list(row.items())[:2])
        return f"{m.get('model')} {m.get('scenario')} {m['range'][0]}~{m['range'][1]}" + (f" · {g}" if g else "")
    return m.get("target") or ""


def _referenced(p, store):
    """정리에서 빠지는 기록 — 채택·고정·다른 기록이 가리키는 것(vs·replay·바꿔 끼우기)·제안이 미리 계산한 것."""
    keep = set(p.adopted.values())
    keep |= {k for k, v in store.marks().items() if v.get("pinned")}
    for r in store.records():
        m = r.meta
        if m.get("vs"):
            keep.add(m["vs"]["id"])
        if m.get("replay"):
            keep.add(m["replay"]["of"])
        for v in (m.get("swaps") or {}).values():
            if str(v).startswith("est:"):
                keep.add(v)
    for pr in p.proposals():
        keep |= set(pr.meta.get("previews") or [])
        keep |= {v for v in (pr.meta.get("parts") or {}).values() if str(v).startswith("est:")}
    keep |= _used_by_documents(p)
    for r in store.records("run"):                  # 실행 기록이 남아 있으면 그 단계의 기록도(재연이 견준다)
        for s in r.meta.get("steps") or []:
            keep |= {x for x in s.get("records") or [] if not str(x).startswith("data:")}
    return keep


def _used_by_documents(p) -> set:
    """노트의 결과 구역·보고서의 구역이 가리키는 기록."""
    import glob
    from ..projects.notes import parse, read_text
    from ..projects.reports import regions
    out = set()
    for f in glob.glob(os.path.join(p.root, "notes", "**", "*.md"), recursive=True):
        for b in parse(read_text(f)):
            if b.region:
                out |= set(b.region[2].get("records") or [])
    for f in glob.glob(os.path.join(p.root, "reports", "**", "*.md"), recursive=True):
        out |= {r.record for r in regions(read_text(f))}
    return out


def _record_text(rec):
    from ..projects.records import est_text, hs_text
    from ..projects.sim import sim_text
    if rec.kind == "est":
        return est_text(rec.meta)
    if rec.kind == "hs":
        return hs_text(rec.meta)
    if rec.kind == "sim":
        return sim_text(rec.meta)
    if rec.kind == "an":
        from ..projects.analyses import an_text
        return an_text(rec.meta)
    if rec.kind == "run":
        from ..script.record import run_text
        return run_text(rec.meta)
    return json.dumps(rec.meta, ensure_ascii=False, indent=2)


def dispatch(args, cmdline: str) -> int:
    from ..projects import Project, ProjectError
    from ..work.store import RecordError, detect_who
    from ..workfile.output import verbose
    old = verbose()
    verbose(0)
    who = detect_who("terminal")
    code = EXIT_OK
    try:
        p = Project.open(args.project)
        cmd = args.command
        if cmd == "est":
            if args.adopted:
                if args.as_name or args.part or args.smpl or args.sim or args.method != "auto":
                    raise ValueError("--adopted는 블록 파일의 글자 그대로 다시 추정합니다(--as·--for·--smpl·--sim·--method 없이)")
                r = p.reestimate(args.target, adopt=args.adopt, who=who, command=cmdline)
            else:
                if not args.target:
                    raise ValueError("추정할 부품이나 식을 주세요(또는 --adopted)")
                if args.adopt != "never":
                    raise ValueError("--adopt는 --adopted와 함께 씁니다(후보 하나는 equion adopt est:…)")
                r = p.est(args.target, method=args.method, smpl=args.smpl, as_name=args.as_name, part=args.part,
                          sim=args.sim, cov=args.cov, who=who, command=cmdline)
            out = r.to_dict() if args.json else r.text()
        elif cmd == "adopt":
            r = p.adopt(args.record, part=args.part, who=who, command=cmdline)
            out = r.to_dict() if args.json else r.text()
        elif cmd == "compare":
            r = p.compare(*args.records, target=args.target, part=args.part)
            out = r.to_dict() if args.json else r.text()
        elif cmd == "hs":
            if args.replay:
                if args.model or args.range or args.mode or args.swap:
                    raise ValueError("--replay는 기록 하나만 받습니다(모형·--range·--mode·--swap 없이 — 그때 그대로)")
                r = p.replay(args.replay, as_name=args.as_name, who=who, command=cmdline)
            else:
                s, e = _range(args.range)
                r = p.hs(args.model, start=s, end=e, mode=args.mode, swap=_swaps(args.swap) or None, record=True,
                         vs=args.vs, as_name=args.as_name, who=who, command=cmdline)
            out = r.to_dict() if args.json else r.text()
        elif cmd == "sim":
            scs = args.scenarios or ["base"]
            if args.as_name and len(scs) > 1:
                raise ValueError("--as는 시나리오가 하나일 때만")
            rs = [p.sim(sc, model=args.model, range=args.range, vintage=args.vintage, vs=args.vs, as_name=args.as_name,
                        mode=args.mode, who=who, command=cmdline) for sc in scs]
            out = [r.to_dict() for r in rs] if args.json else "\n".join(r.text() for r in rs)
            if args.json and len(rs) == 1:
                out = out[0]
        elif cmd == "propose":
            out = _propose(p, args, who, cmdline)
        elif cmd == "export":
            r = p.export(args.records, args.xlsx)
            out = r if args.json else (f"[export] {os.path.relpath(r['path'], p.root).replace(os.sep, '/')} — 기록 "
                                       f"{len(r['records'])} · 시트 {len(r['sheets'])}: {', '.join(r['sheets'][:8])}"
                                       + (" …" if len(r["sheets"]) > 8 else ""))
        elif cmd == "work":
            out = _work(p, args)
        else:
            out = _history(p, args, who, cmdline)
    except (ProjectError, RecordError, KeyError, ValueError) as e:
        fail(f"{e.args[0] if isinstance(e, KeyError) else e}")
        return EXIT_INPUT
    finally:
        verbose(old)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str) if args.json else out)
    return code


def _load(store, lines):
    from ..work.store import RecordError
    out = []
    for x in lines:
        try:
            out.append(store.get(x["id"]))
        except RecordError:
            continue
    return out


def _work(p, args):
    store = p.work
    act = args.work_command
    if act == "list":
        adopted, marks = p.adopted, store.marks()
        lines = [x for x in store.log() if not args.kind or x.get("kind") == args.kind]   # 목록은 log.jsonl로 거르고
        if args.target:
            lines = [x for x in lines if str(x.get("target", "")).lower() == args.target.lower()]
        if args.part:
            pid = p.part(args.part).id
            recs = [r for r in _load(store, lines) if r.meta.get("part") == pid]
            if args.limit:
                recs = recs[-args.limit:]
        else:
            recs = _load(store, lines[-args.limit:] if args.limit else lines)   # 보일 기록만 연다(기록이 많아도 빠르게)
        rows = [{"id": r.id, "created": r.meta.get("created"), "who": r.meta.get("who"), "target": r.meta.get("target"),
                 "part": r.meta.get("part"), "metric": _metric(r), "flags": _flags(p, store, r, adopted, marks)}
                for r in recs]
        if args.json:
            return rows
        if not rows:
            return f"[work list] {p.name}: 기록 없음"
        from ..work.store import WHO_KO
        L = [f"[work list] {p.name}: 기록 {len(rows)}" + (f" (최근 {args.limit})" if args.limit else "")]
        for r in rows:
            L.append(f"  {r['id']:<18} {str(r['created'])[:16]:<16} {WHO_KO.get(r['who'], r['who'] or ''):<6} "
                     f"{r['metric']}" + (f"   {' · '.join(r['flags'])}" if r["flags"] else ""))
        return "\n".join(L)
    if act == "show":
        rec = store.get(args.record)
        if args.json:
            d = dict(rec.meta)
            d.pop("equation", None)
            d["path"] = rec.path
            return d
        if args.md:
            return rec.summary_md().rstrip()
        return _record_text(rec) + f"\n  카드   {rec.meta.get('path', '')}/summary.md"
    if act in ("pin", "unpin"):
        e = store.mark(args.record, pinned=(act == "pin"))
        return e if args.json else f"[work {act}] {args.record} — " + ("고정(정리에서 빠진다)" if e.get("pinned") else "고정 풀림")
    if act == "memo":
        e = store.mark(args.record, memo=args.text)
        return e if args.json else f"[work memo] {args.record} — {args.text}"
    # clean
    keep = _referenced(p, store)
    cand = [r for r in store.records(args.kind) if r.id not in keep
            and (r.kind != "run" or args.kind == "run")]   # 실행 기록은 --kind run으로 고를 때만
    if args.yes:
        for r in cand:
            store.remove(r.id)
    ids = [r.id for r in cand]
    if args.json:
        return {"removed" if args.yes else "would_remove": ids, "kept": sorted(keep)}
    head = f"[work clean] {'지움' if args.yes else '지울 기록(미리보기 — 지우려면 --yes)'} {len(ids)}"
    return "\n".join([head] + [f"  {i}" for i in ids] + [f"  남김(채택·고정·참조) {len(keep)}"])


def _propose(p, args, who, cmdline):
    act = args.propose_command
    if act == "new":
        parts, files = {}, {}
        for it in args.part:
            if "=" not in it:
                raise ValueError(f"--part는 부품=값 꼴입니다: {it!r}")
            k, v = it.split("=", 1)
            parts[k.strip()] = v.strip()
        for it in args.file:
            if "=" not in it:
                raise ValueError(f"--file은 경로=새파일 꼴입니다: {it!r}")
            k, v = it.split("=", 1)
            files[k.strip()] = v.strip()
        r = p.propose(args.name, title=args.title, why=args.why, parts=parts, files=files, previews=args.preview,
                      who=who, command=cmdline)
        return r.to_dict() if args.json else r.text() + f"\n  카드   {os.path.relpath(r.path, p.root).replace(os.sep, '/')}/proposal.md"
    if act == "list":
        items = p.proposals()
        if args.json:
            return [x.to_dict() for x in items]
        if not items:
            return f"[propose list] {p.name}: 제안 없음"
        return "\n".join([f"[propose list] {p.name}: 제안 {len(items)}"] + [x.text() for x in items])
    if act == "show":
        from ..projects import proposals
        r = proposals.get(p, args.name)
        return r.to_dict() if args.json else r.text() + "\n" + (r.diff().rstrip() or "(차이 없음)")
    if act == "apply":
        r = p.apply_proposal(args.name, force=args.force, who=who, command=cmdline)
        return r.to_dict() if args.json else r.text()
    r = p.drop_proposal(args.name, why=args.why, who=who)
    return r.to_dict() if args.json else r.text()


def _history(p, args, who, cmdline):
    h = p.history
    act = args.history_command
    if act == "list":
        h.scan()
        items = h.list()
        if args.limit:
            items = items[-args.limit:]
        if args.json:
            return [c.to_dict() | {"diff": None} for c in items]
        if not items:
            return f"[history list] {p.name}: 바뀜 기록 없음"
        return "\n".join([f"[history list] {p.name}: 바뀜 {len(items)}"] + [c.text() for c in items])
    if act == "show":
        c = h.get(args.change)
        return c.to_dict() if args.json else c.text() + "\n" + (c.diff.rstrip() or "(차이 없음)")
    c = h.revert(args.change, who, how=cmdline)
    p._reset()
    if c is None:
        return {"change": None} if args.json else f"[history revert] {args.change} — 지금 내용이 이미 그 앞과 같습니다(바꾼 것 없음)"
    return c.to_dict() if args.json else f"[history revert] {args.change} 되돌림\n" + c.text()
