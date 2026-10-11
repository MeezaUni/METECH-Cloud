# KMRL Depot Planner — cloud AI edition

The induction planner with **Google Gemini** for reading logbooks and understanding questions.
See the [top-level README](../README.md) for what the app does.

## Run

```bat
run.bat
```

Opens <http://127.0.0.1:8010>. The first run installs Python and Node dependencies.

## Gemini key

Create a key at <https://aistudio.google.com/apikey> and put it in `backend/.env`:

```
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-flash-latest
GEMINI_THINKING_BUDGET=0
```

The key is used only by the backend; it never reaches the browser. Without a key (or if Gemini is
unreachable) the app uses the built-in rule engine and says so in the top bar.

## How well Gemini does

Scored on the hand-written real-world test set (35 logbook messages, 20 questions) that the local
edition's model is also scored on (`eval/realworld_test.jsonl`):

| | Rule engine | Gemini (`gemini-flash-latest`, thinking off) |
|---|---|---|
| Logbook messages fully correct | 74.3% | **94.3%** |
| ...ignoring the Critical/High/Routine call | 77.1% | **100%** |
| Facts extracted: precision / recall | 97.0% / 80.0% | **100% / 100%** |
| Questions understood | 95.0% | **100%** |
| Time per request | instant | ~2 s |

The two remaining misses are priority judgement calls (a CCTV fault rated Routine, a slow door rated High).
Re-run with `cd backend && uv run python ../eval/evaluate.py`; failures go to `eval/reports/`.

`GEMINI_THINKING_BUDGET=0` (the default) turns off Gemini's hidden reasoning tokens: extraction doesn't need
them and they made each request ~3x slower (8 s vs 2.6 s in testing). Rate-limit (429) and overload (503)
errors are retried twice before falling back to the rule engine.

## Develop

```bat
cd backend  &  uv run uvicorn app.main:app --reload --port 8010
cd frontend &  npm run dev          :: http://localhost:5173, proxies /api to :8010
cd backend  &  uv run pytest
```

Planner settings (service target, standby minimum, bay capacities, thresholds) are in `backend/app/config.py`.
The demo fleet is regenerated from **History → Reset demo data** or `POST /api/admin/reset`.

## API

| Method | Path | |
|---|---|---|
| GET | `/api/fleet` | trains with readiness, certificates, job cards, branding |
| GET | `/api/plan` | tonight's optimised plan with reasons and KPIs |
| POST | `/api/plan/simulate` | `{updates}` → baseline vs simulated plan and the differences |
| POST | `/api/plan/approve` | record the current plan as approved |
| POST | `/api/fleet/updates` | `{updates, via}` → validate, apply, audit |
| POST | `/api/ai/parse` | `{text}` → proposed updates (not applied) |
| POST | `/api/ai/ask` | `{question}` → answer computed from live data |
| GET | `/api/audit`, `/api/plan/history`, `/api/ai/info` | |

Interactive docs at <http://127.0.0.1:8010/docs>.
