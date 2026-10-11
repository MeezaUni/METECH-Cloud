# METECH Cloud — KMRL Depot Planner

AI-driven train induction planning for Kochi Metro Rail Limited, with **Google Gemini** reading logbooks
and answering questions. Smart India Hackathon 2025, problem statement **SIH25081**, team **METECH**.

Every night a KMRL depot supervisor decides, for all 25 trainsets, which go into revenue service at 05:30,
which wait on standby, and which go for inspection or deep cleaning. Today that is a two-hour spreadsheet
exercise. This app does it in under a second and explains every decision.

> A fully offline edition with our own fine-tuned model lives at
> [MeezaUni/METECH-Local](https://github.com/MeezaUni/METECH-Local). Same planner and dashboard, no API key.

## Run it

**Windows:** double-click `run.bat` (or run it from a terminal).
**macOS / Linux:** `./run.sh`

It installs what it needs on the first run, asks for your Gemini API key once, builds the dashboard and opens
<http://127.0.0.1:8010>. Requirements: [Node.js 20+](https://nodejs.org/) and [uv](https://docs.astral.sh/uv/)
(the script offers to install uv for you).

No key? Press Enter when asked: the app then reads logbooks with its built-in rule engine. You can add a key
later in `backend/.env` (get one at <https://aistudio.google.com/apikey>). The key stays on your machine and is
only used by the backend; it never reaches the browser.

## What it does

- **Induction planner** (Google OR-Tools CP-SAT). Assigns every train to Service, Standby, Inspection Bay,
  Cleaning or Held, balancing the six factors in the problem statement:
  1. Fitness certificates: a train with *any* expired Rolling-Stock, Signalling or Telecom certificate is never inducted
  2. Job cards: open critical work keeps a train out; other open work prefers the inspection bay
  3. Branding: trains behind on contracted advertising hours are preferred for service
  4. Mileage balancing: trains with less wear since their last inspection are preferred
  5. Cleaning slots: overdue trains compete for the limited deep-cleaning bays
  6. Stabling geometry: inducting a train parked behind one that stays costs a shunting move
- **Explanations**: each decision lists its reasons and the score that tipped it.
- **What-if simulation**: stage changes (close a job card, renew a certificate, mark a clean) as a draft,
  see the re-solved plan with before/after badges, then save or discard.
- **3D depot view**: stabling lines, inspection bay and cleaning bay; trains glide to their new track when the plan changes.
- **Logbook reader**: paste shift notes or WhatsApp messages; Gemini turns them into fleet updates you confirm one by one.
- **Ask**: questions in plain English ("why is TS-09 on standby?"). Gemini only interprets the question;
  every number in the answer is computed from live data, so it can't make up train states.
- **Priority policy**: how urgent a new job card is (Critical / High / Routine) is decided by
  `backend/app/priority.py`, not by the AI, and every override is explained.
- **Audit trail**: every change and every approved plan is logged with who made it and how.

## How well Gemini does

Hand-written real-world test set (43 logbook messages, 25 questions, `eval/realworld_test.jsonl`), scored as
the supervisor sees the result:

| | Rule engine | Gemini (`gemini-flash-latest`, thinking off) |
|---|---|---|
| Logbook messages fully correct | 76.7% | **100%** |
| Facts extracted: precision / recall | 97.4% / 77.6% | **100% / 100%** |
| Questions understood | 84.0% | **100%** |
| Time per request | instant | ~2 s |

Re-run with `cd backend && uv run python ../eval/evaluate.py`; failures go to `eval/reports/`.

`GEMINI_THINKING_BUDGET=0` (the default) turns off Gemini's hidden reasoning tokens: extraction doesn't need
them and they made each request ~3x slower. Rate-limit (429) and overload (503) errors are retried twice before
falling back to the rule engine.

## Configuration

`backend/.env` (created on first run from `.env.example`):

```
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-flash-latest
GEMINI_THINKING_BUDGET=0
```

Planner settings (service target, standby minimum, bay capacities, thresholds) are in `backend/app/config.py`.
The demo fleet is regenerated from **History → Reset demo data**.

## Develop

```bash
cd backend  && uv run uvicorn app.main:app --reload --port 8010
cd frontend && npm run dev          # http://localhost:5173, proxies /api to :8010
cd backend  && uv run pytest
```

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

Interactive API docs at <http://127.0.0.1:8010/docs>.

## Layout

```
backend/app/       FastAPI app: planner.py, fleet.py, updates.py, priority.py, assistant.py, ai/gemini.py, ai/rules.py
backend/tests/     43 tests
frontend/src/      React + TypeScript + three.js dashboard
eval/              real-world test set and scorer
run.bat, run.sh
```

## What changed from the hackathon prototype (v1.2)

| v1.2 (Sept 2025) | Now |
|---|---|
| Backend grounded a train only if *all* certificates had expired (the frontend said *any*) | One readiness check used everywhere, with a regression test |
| Gemini key shipped inside the browser bundle | Key stays on the server |
| Edit dialog never showed job cards (`train.id` typo) | Fixed; job cards can be closed from the train panel |
| CSV files overwritten on save, no history | SQLite with an audit log and approved-plan history |
| 3 factors and a branding bonus | All 6 factors, depot capacities, explanations, shortfall alerts |
| No tests | 43 backend tests |
