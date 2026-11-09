#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""작업 명령(D33, E3) — `equion est · adopt · compare · hs · work · history`.

    equion est 부품|"식" [--as 이름] [--for 부품] [--method auto|ls|tsls] [--smpl S:E] [--sim]
    equion adopt est:이름 [--part 부품]
    equion compare 기록… | --target CN | --part demand:CN
    equion hs [모형|블록] [--range S:E] [--mode] [--swap 부품=est:이름|"식"]… [--vs hs:이름] [--as 이름] | --replay hs:이름
    equion work list|show|pin|unpin|memo|clean        equion history list|show|revert

모두 프로젝트 폴더(`-p`, 기본 지금 폴더)에서 돌고, 출력은 짧은 글(기본) 또는 `--json`. 계산은 할 때마다 `work/`에 기록을 남긴다.
입력 오류(없는 부품·기록·이름 겹침·조립 문제)는 종료 코드 3.
"""

import json
import sys

from .runner import EXIT_INPUT, EXIT_OK

PROG = "equion"
COMMANDS = ("est", "adopt", "compare", "hs", "work", "history")


def _common(sp):
    sp.add_argument("--project", "-p", default=".", metavar="폴더", help="프로젝트 폴더(기본: 지금 폴더)")
    sp.add_argument("--json", action="store_true", help="결과를 JSON으로")
    return sp


def add_parsers(sub):
    e = _common(sub.add_parser("est", help="식 하나를 추정해 기록을 남긴다(부품 또는 식 글자 — 후보)"))
    e.add_argument("target", metavar="부품|식", help='부품 블록:목표(블록 파일의 그 줄) 또는 식 글자(예: "CN c Y CN(-1)")')
    e.add_argument("--as", dest="as_name", metavar="이름", help="기록 이름(기본: 목표변수_0001 …)")
    e.add_argument("--for", dest="part", metavar="부품", help="어느 부품의 후보인지(목표가 같은 식이 여럿일 때)")
    e.add_argument("--method", choices=("auto", "ls", "tsls"), default="auto", help="추정법(기본 auto — @inst가 있으면 tsls)")
    e.add_argument("--smpl", metavar="S:E", help="표본(상대 기간 가능 — 1990Q1:last)")
    e.add_argument("--sim", action="store_true", help="식 하나의 동태 모의([hs] range, 다른 변수는 실측)와 RMSPE")
    e.add_argument("--cov", help="계수 공분산(white · hac …)")

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

    w = sub.add_parser("work", help="작업 기록 — 목록·보기·고정·메모·정리")
    wsub = w.add_subparsers(dest="work_command", metavar="동작")
    wsub.required = True
    wl = _common(wsub.add_parser("list", help="기록 목록(새것이 아래)"))
    wl.add_argument("--kind", choices=("est", "hs", "sim"), help="종류")
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
    wc = _common(wsub.add_parser("clean", help="정리 — 고정·채택·참조되지 않은 기록(기본은 목록만, --yes면 지움)"))
    wc.add_argument("--kind", choices=("est", "hs", "sim"), help="종류")
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
    if d.get("kind") == "vintage" and p.vintage and d.get("id") != p.vintage:
        f.append(f"회차 다름({d.get('id')})")
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
    return m.get("target") or ""


def _referenced(p, store):
    """정리에서 빠지는 기록 — 채택·고정·다른 기록이 가리키는 것(vs·replay)."""
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
    return keep


def _record_text(rec):
    from ..projects.records import est_text, hs_text
    if rec.kind == "est":
        return est_text(rec.meta)
    if rec.kind == "hs":
        return hs_text(rec.meta)
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
            r = p.est(args.target, method=args.method, smpl=args.smpl, as_name=args.as_name, part=args.part, sim=args.sim,
                      cov=args.cov, who=who, command=cmdline)
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
        elif cmd == "work":
            out = _work(p, args)
        else:
            out = _history(p, args, who, cmdline)
    except (ProjectError, RecordError, KeyError, ValueError) as e:
        print(f"{PROG}: 오류: {e.args[0] if isinstance(e, KeyError) else e}", file=sys.stderr)
        return EXIT_INPUT
    finally:
        verbose(old)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str) if args.json else out)
    return code


def _work(p, args):
    store = p.work
    act = args.work_command
    if act == "list":
        adopted, marks = p.adopted, store.marks()
        recs = store.records(args.kind)
        if args.target:
            recs = [r for r in recs if str(r.meta.get("target", "")).lower() == args.target.lower()]
        if args.part:
            pid = p.part(args.part).id
            recs = [r for r in recs if r.meta.get("part") == pid]
        if args.limit:
            recs = recs[-args.limit:]
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
    cand = [r for r in store.records(args.kind) if r.id not in keep]
    if args.yes:
        for r in cand:
            store.remove(r.id)
    ids = [r.id for r in cand]
    if args.json:
        return {"removed" if args.yes else "would_remove": ids, "kept": sorted(keep)}
    head = f"[work clean] {'지움' if args.yes else '지울 기록(미리보기 — 지우려면 --yes)'} {len(ids)}"
    return "\n".join([head] + [f"  {i}" for i in ids] + [f"  남김(채택·고정·참조) {len(keep)}"])


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
