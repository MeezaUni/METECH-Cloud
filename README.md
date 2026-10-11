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

Scored on the hand-written real-world test set (43 logbook messages, 25 questions) that the local
edition's model is also scored on (`eval/realworld_test.jsonl`), as the supervisor sees the result
(after the depot priority policy, see below):

| | Rule engine | Gemini (`gemini-flash-latest`, thinking off) |
|---|---|---|
| Logbook messages fully correct | 74.4% | **100%** (88.4% before the priority policy) |
| Facts extracted: precision / recall | 94.9% / 75.5% | **100% / 100%** |
| Questions understood | 84.0% | **100%** |
| Time per request | instant | ~2 s |

Re-run with `cd backend && uv run python ../eval/evaluate.py`; failures go to `eval/reports/`.

## Priority policy

How urgent a new job card is (Critical / High / Routine) is decided by `backend/app/priority.py`, not by
the AI: brakes, wheels, bogies, train control, smoke and door-safety faults are always Critical; passenger-facing
failures (doors, AC, PIS, CCTV, radio, traction) are High; comfort and cosmetic items are Routine. "Urgent" in the
text escalates, "minor" de-escalates (never below Critical for safety items). Every override is shown to the
supervisor with its reason. Edit the rules there; both editions and the local model's training data use them.

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
