"""Score Gemini (and the rule engine) on the hand-written real-world test set.

    cd backend
    uv run python ../eval/evaluate.py              # Gemini vs rule engine
    uv run python ../eval/evaluate.py --engine rules

Same test set and scoring as kmrl-hub-local/ml/evaluate.py, so the cloud model and the
on-device model can be compared directly. Facts are compared (train, action, department,
date, job card, km, priority); free text (description, source_text) is not scored.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))
from app.ai import AIContext, AIUnavailable, build_provider, rules  # noqa: E402
from app.config import settings  # noqa: E402

DEFAULTS = {"expiring_certificates": {"days": 7}, "highest_wear": {"limit": 5}}


def fact_key(u: dict, strict: bool) -> tuple:
    if u.get("action") == "close_job_card":
        return ("close_job_card", u.get("job_card_id"))
    key = (u.get("train_name"), u.get("action"), u.get("department"), u.get("date"), u.get("km"))
    return key + ((u.get("priority"),) if strict else ())


def norm_intent(d: dict | None) -> dict:
    d = {k: v for k, v in (d or {}).items() if v is not None}
    return {**DEFAULTS.get(d.get("intent"), {}), **d}


def run(engine: str, rows: list[dict]) -> tuple[list, int, float]:
    provider = build_provider(settings)
    ctx = AIContext(today=date(2026, 10, 11), train_names=[f"KMRL-TS-{i:03d}" for i in range(1, 26)], open_jobs=[], job_owner={})
    preds, errors, started = [], 0, time.perf_counter()
    for r in rows:
        try:
            if r["task"] == "parse":
                ctx_r = AIContext(date.fromisoformat(r["today"]), ctx.train_names, [], {})
                ups = provider.parse_logbook(r["text"], ctx_r) if engine == "gemini" else rules.parse_logbook(r["text"], ctx_r.today)
                preds.append([u.model_dump(exclude_none=True) for u in ups])
            else:
                q = provider.interpret_question(r["question"], ctx) if engine == "gemini" else rules.interpret_question(r["question"])
                preds.append(q.model_dump(exclude_none=True))
        except AIUnavailable as exc:
            errors += 1
            print(f"  ! {exc}"[:160])
            preds.append(None)
    return preds, errors, time.perf_counter() - started


def score(rows: list[dict], preds: list) -> dict:
    s = {"parse_n": 0, "exact": 0, "exact_relaxed": 0, "tp": 0, "fp": 0, "fn": 0, "ask_n": 0, "ask_exact": 0, "failures": []}
    for r, p in zip(rows, preds):
        if r["task"] == "parse":
            s["parse_n"] += 1
            p = p or []
            es, gs = {fact_key(u, True) for u in r["expected"]}, {fact_key(u, True) for u in p}
            er, gr = {fact_key(u, False) for u in r["expected"]}, {fact_key(u, False) for u in p}
            s["exact"] += es == gs
            s["exact_relaxed"] += er == gr
            s["tp"] += len(er & gr); s["fp"] += len(gr - er); s["fn"] += len(er - gr)
            if es != gs:
                s["failures"].append({"text": r["text"], "expected": sorted(map(str, es)), "got": sorted(map(str, gs))})
        else:
            s["ask_n"] += 1
            ok = norm_intent(p) == norm_intent(r["expected"])
            s["ask_exact"] += ok
            if not ok:
                s["failures"].append({"question": r["question"], "expected": r["expected"], "got": p})
    prec = s["tp"] / max(1, s["tp"] + s["fp"]); rec = s["tp"] / max(1, s["tp"] + s["fn"])
    s.update(precision=prec, recall=rec, f1=2 * prec * rec / max(1e-9, prec + rec))
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["gemini", "rules", "both"], default="both")
    args = ap.parse_args()
    rows = [json.loads(l) for l in open(ROOT / "realworld_test.jsonl", encoding="utf-8")]
    report = {}
    for engine in (["rules", "gemini"] if args.engine == "both" else [args.engine]):
        if engine == "gemini" and not settings.gemini_api_key:
            sys.exit("GEMINI_API_KEY is not set in backend/.env")
        preds, errors, secs = run(engine, rows)
        s = score(rows, preds)
        s.update(errors=errors, seconds=round(secs, 1), model=settings.gemini_model if engine == "gemini" else "rules")
        report[engine] = s
        print(f"\n== {engine} ({s['model']}) on {s['parse_n']} logbook messages + {s['ask_n']} questions, {s['seconds']}s, {errors} errors")
        print(f"  logbook   exact {s['exact'] / s['parse_n']:.1%}   ignoring priority {s['exact_relaxed'] / s['parse_n']:.1%}   "
              f"precision {s['precision']:.1%}  recall {s['recall']:.1%}  F1 {s['f1']:.1%}")
        print(f"  questions exact {s['ask_exact'] / s['ask_n']:.1%}")
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / f"eval_{args.engine}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFailures and details: {out / f'eval_{args.engine}.json'}")


if __name__ == "__main__":
    main()
