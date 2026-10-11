"""Google Gemini engine. Runs server-side so the API key never reaches the browser."""
from __future__ import annotations

import logging
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from ..models import AIInfo, FleetUpdate, ParsedUpdates, QueryIntent
from .base import AIContext, AIUnavailable

log = logging.getLogger(__name__)
RETRY_DELAYS_S = (2, 6)

PARSER_INSTRUCTIONS = """You extract structured fleet updates for the Kochi Metro Rail (KMRL) depot from
unstructured logbook entries, WhatsApp messages and shift handover notes. Staff write in informal
English, sometimes mixed with Malayalam words, abbreviations and typos.

Rules:
- Train ids are always KMRL-TS-NNN (three digits). "train 4", "TS 4", "rake 04", "set-4" -> "KMRL-TS-004".
- Actions:
  renew_certificate     department (Rolling-Stock | Signalling | Telecom) + date (YYYY-MM-DD new expiry)
  close_job_card        job_card_id (the number on the job card / work order)
  open_job_card         description (short, clean) + priority (Critical for safety issues such as brakes,
                        wheels, bogie cracks, signalling/CBTC, doors failing to detect obstruction, smoke;
                        High for failures affecting passengers; otherwise Routine)
  flag_cleaning         train needs a deep clean (dirty, vandalism, graffiti, spills)
  mark_cleaned          deep cleaning has been completed
  complete_maintenance  inspection / A-check / IBL work completed (resets wear counter)
  update_mileage        km = kilometres run since last inspection
- Resolve relative dates ("till next March", "for 6 months", "tomorrow") against today's date.
- A job card closed without naming the train is still an update: emit close_job_card with the job_card_id,
  taking train_name from the open job card list if it is there, otherwise "" (the system resolves it).
- One update per distinct fact. If one sentence renews two certificates, emit two updates.
- source_text must be the exact snippet from the input that justifies the update.
- If the text contains no actionable fleet update, return an empty list. Never invent trains or job card numbers."""

QUESTION_INSTRUCTIONS = """You convert a KMRL depot supervisor's question into a structured query. Do not answer it.
Intents:
  count / list            trains with a status. status is one of: Service, Standby, Inspection Bay, Cleaning,
                          Held (tonight's plan) or Fit, Warning, Unfit (readiness). green=Fit, yellow=Warning, red=Unfit.
  train_detail            everything about one train (train_name)
  explain_assignment      why a train got its assignment (train_name)
  expiring_certificates   certificates expiring within `days` (default 7)
  open_jobs               open job cards, optional priority (Critical | High | Routine)
  branding_status         advertising / branding contract exposure
  plan_summary            overview of tonight's induction plan
  highest_wear            trains with most km since inspection (limit, default 5)
  help                    anything else
Train ids are KMRL-TS-NNN."""


class GeminiProvider:
    def __init__(self, api_key: str | None, model: str, thinking_budget: int = 0):
        self.model = model
        self.thinking = types.ThinkingConfig(thinking_budget=thinking_budget) if thinking_budget >= 0 else None
        self._client = genai.Client(api_key=api_key) if api_key else None

    def info(self) -> AIInfo:
        if self._client is None:
            return AIInfo(edition="cloud", engine="Google Gemini", model=self.model, ready=False,
                          note="GEMINI_API_KEY is not set — using the built-in rule engine")
        return AIInfo(edition="cloud", engine="Google Gemini", model=self.model, ready=True)

    def _generate(self, instructions: str, prompt: str, schema: type) -> str:
        if self._client is None:
            raise AIUnavailable("Gemini API key not configured")
        config = types.GenerateContentConfig(
            system_instruction=instructions,
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
            temperature=0,
            thinking_config=self.thinking,
        )
        for attempt in range(3):
            try:
                response = self._client.models.generate_content(model=self.model, contents=prompt, config=config)
                break
            except genai_errors.APIError as exc:
                # Rate limits (429) and overload (503) are usually gone within seconds; anything else falls back now.
                if exc.code in (429, 503) and attempt < 2:
                    time.sleep(RETRY_DELAYS_S[attempt])
                    continue
                log.warning("Gemini request failed: %s", exc)
                raise AIUnavailable(str(exc)) from exc
            except Exception as exc:  # network errors and the like also mean "fall back"
                log.warning("Gemini request failed: %s", exc)
                raise AIUnavailable(str(exc)) from exc
        if not response.text:
            raise AIUnavailable("Gemini returned an empty response")
        return response.text

    def parse_logbook(self, text: str, ctx: AIContext) -> list[FleetUpdate]:
        prompt = (
            f"Today's date: {ctx.today.isoformat()}\n"
            f"Fleet: {ctx.train_names[0]} .. {ctx.train_names[-1]}\n"
            "Open job cards:\n" + ("\n".join(ctx.open_jobs) or "(none)") +
            f"\n\nLogbook text:\n\"\"\"\n{text}\n\"\"\""
        )
        raw = self._generate(PARSER_INSTRUCTIONS, prompt, ParsedUpdates)
        try:
            return ParsedUpdates.model_validate_json(raw).updates
        except ValueError as exc:
            raise AIUnavailable(f"Gemini returned malformed JSON: {exc}") from exc

    def interpret_question(self, question: str, ctx: AIContext) -> QueryIntent:
        raw = self._generate(QUESTION_INSTRUCTIONS, f"Question: {question}", QueryIntent)
        try:
            return QueryIntent.model_validate_json(raw)
        except ValueError as exc:
            raise AIUnavailable(f"Gemini returned malformed JSON: {exc}") from exc

    def freeform_answer(self, question: str, facts: str) -> str | None:
        if self._client is None:
            return None
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=f"Depot facts (authoritative):\n{facts}\n\nQuestion: {question}",
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are the KMRL depot operations assistant. Answer briefly using ONLY the facts given. "
                        "If the facts don't contain the answer, say so. Plain text, no markdown headings."
                    ),
                    temperature=0.2,
                    thinking_config=self.thinking,
                ),
            )
            return response.text
        except Exception as exc:
            log.warning("Gemini free-form answer failed: %s", exc)
            return None


def build_provider(settings) -> GeminiProvider:
    return GeminiProvider(settings.gemini_api_key, settings.gemini_model, settings.gemini_thinking_budget)
