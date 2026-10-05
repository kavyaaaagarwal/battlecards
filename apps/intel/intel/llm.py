"""Provider-agnostic LLM client that returns validated Pydantic objects.

Uses plain "reply with JSON matching this schema" prompting + validation + one
repair retry, which works across Anthropic, OpenAI and any OpenAI-compatible
endpoint (Gemini, Groq, Ollama, ...)."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-5",
    "openai": "gpt-4.1-mini",
    "openrouter": "",  # blank = auto-pick the best free models at run time
}

OPENROUTER_URL = "https://openrouter.ai/api/v1"
# Model families ranked for long-document analysis + reliable JSON. Earlier = preferred.
# OpenRouter's free line-up rotates, so we rank whatever is live rather than hardcoding IDs.
FREE_MODEL_PREFERENCE = [
    "deepseek", "qwen3", "kimi", "glm", "gpt-oss", "gemini", "llama-4",
    "nemotron", "mistral", "llama-3.3", "gemma",
]


def pick_free_openrouter_models(n: int = 3, min_context: int = 64_000) -> list[str]:
    """Return the n best currently-free OpenRouter models (primary first, then fallbacks)."""
    import requests

    try:
        data = requests.get(f"{OPENROUTER_URL}/models", timeout=20).json()["data"]
    except Exception as e:
        raise LLMError(f"Couldn't fetch OpenRouter's model list ({e}). Set LLM_MODEL in .env manually.") from e

    def is_free(m) -> bool:
        p = m.get("pricing") or {}
        return m["id"].endswith(":free") or (str(p.get("prompt")) == "0" and str(p.get("completion")) == "0")

    def rank(m):
        mid = m["id"].lower()
        family = next((i for i, f in enumerate(FREE_MODEL_PREFERENCE) if f in mid), len(FREE_MODEL_PREFERENCE))
        json_ok = "response_format" in (m.get("supported_parameters") or [])
        return (family, not json_ok, -(m.get("context_length") or 0))

    candidates = [
        m for m in data
        if is_free(m)
        and not m["id"].startswith("openrouter/")
        and (m.get("context_length") or 0) >= min_context
        and "text" in ((m.get("architecture") or {}).get("output_modalities") or ["text"])
    ]
    if not candidates:
        raise LLMError("OpenRouter currently lists no free models with a large enough context. Set LLM_MODEL manually.")
    return [m["id"] for m in sorted(candidates, key=rank)[:n]]


class LLMError(RuntimeError):
    pass


class TransientLLMError(LLMError):
    """Provider hiccup (timeout, empty reply) - worth retrying on another model."""


class LLM:
    def __init__(self, cfg):
        self.provider = cfg.llm_provider
        self.deadline: float | None = None  # time.monotonic() by which the current stage must finish
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        self._lock = threading.Lock()
        self._fallbacks: list[str] = []
        self.models_used: set[str] = set()

        if self.provider == "openrouter":
            import openai

            # LLM_MODEL may be blank (auto), one model, or a comma-separated fallback list
            models = [m.strip() for m in cfg.llm_model.split(",") if m.strip()] or pick_free_openrouter_models()
            self.model, self._fallbacks = models[0], models[1:3]
            log.info("OpenRouter models: %s", " -> ".join(models[:3]))
            self._client = openai.OpenAI(
                api_key=cfg.openrouter_api_key,
                base_url=OPENROUTER_URL,
                max_retries=4,
                default_headers={"X-Title": "Competitive Intel Agent"},
            )
            self._json_mode = True
            return

        self.model = cfg.llm_model or DEFAULT_MODELS[self.provider]
        if self.provider == "anthropic":
            import anthropic

            self._client = anthropic.Anthropic(api_key=cfg.anthropic_api_key, max_retries=4)
        else:
            import openai

            # Always pass base_url: a blank OPENAI_BASE_URL= in .env is loaded into
            # os.environ as "", which the SDK would otherwise use verbatim.
            kwargs = {
                "api_key": cfg.openai_api_key,
                "max_retries": 4,
                "base_url": cfg.openai_base_url or "https://api.openai.com/v1",
            }
            self._client = openai.OpenAI(**kwargs)
        self._json_mode = True  # disabled automatically if an endpoint rejects it

    # ── raw completion ────────────────────────────────────────
    def _remaining(self) -> float | None:
        return None if self.deadline is None else self.deadline - time.monotonic()

    def _apply_deadline(self, kwargs: dict) -> None:
        """Never let one model call outlive the stage's function time limit."""
        rem = self._remaining()
        if rem is None:
            return
        if rem < 15:
            raise TransientLLMError("This stage's time budget is used up")
        kwargs["timeout"] = rem - 5

    def _wait_seconds(self, wanted: float) -> float:
        rem = self._remaining()
        return wanted if rem is None else max(0.0, min(wanted, rem - 20))

    def _complete(self, system: str, messages: list[dict], max_tokens: int, attempt: int = 0) -> str:
        if self.provider == "anthropic":
            kwargs = dict(model=self.model, system=system, messages=messages, max_tokens=max_tokens, temperature=0.2)
            self._apply_deadline(kwargs)
            resp = self._client.messages.create(**kwargs)
            self._track(resp.usage.input_tokens, resp.usage.output_tokens)
            return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

        import openai

        # On a retry, lead with the next fallback: the same free model tends to repeat a bad reply.
        models = [self.model, *self._fallbacks]
        k = attempt % len(models)
        models = models[k:] + models[:k]
        kwargs = dict(
            model=models[0],
            messages=[{"role": "system", "content": system}, *messages],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        if self._json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        extra_body = {}
        if self.provider == "openrouter":
            # Free models are mostly reasoning models; hidden thinking otherwise eats the
            # whole max_tokens budget, leaving empty or truncated JSON.
            extra_body["reasoning"] = {"effort": "none"}
        if self._fallbacks:
            # OpenRouter tries these in order if the primary is down or rate-limited
            extra_body["models"] = models
        if extra_body:
            kwargs["extra_body"] = extra_body
        self._apply_deadline(kwargs)
        try:
            resp = self._create_with_rate_limit_wait(kwargs)
        except openai.BadRequestError as e:
            if self._json_mode and "response_format" in str(e).lower():
                log.info("Endpoint rejected JSON mode; falling back to plain prompting.")
                self._json_mode = False
                kwargs.pop("response_format")
                resp = self._create_with_rate_limit_wait(kwargs)
            else:
                raise
        if getattr(resp, "error", None):  # OpenRouter can return 200 with an error body
            raise TransientLLMError(f"Model error: {resp.error}")
        if not resp.choices:
            raise TransientLLMError("Model returned no choices (provider hiccup).")
        if resp.usage:
            self._track(resp.usage.prompt_tokens, resp.usage.completion_tokens)
        if getattr(resp, "model", None):
            self.models_used.add(resp.model)
            log.debug("Served by %s (finish=%s)", resp.model, resp.choices[0].finish_reason)
        content = resp.choices[0].message.content or ""
        if resp.choices[0].finish_reason == "length":
            log.warning("%s hit max_tokens (%d) - output %s.", resp.model, max_tokens,
                        "is empty" if not content.strip() else "was cut off")
        return content

    def _create_with_rate_limit_wait(self, kwargs: dict, attempts: int = 6):
        """Free tiers (e.g. Gemini: 5 req/min) need longer waits than the SDK's backoff."""
        import time

        import openai

        for i in range(attempts):
            try:
                return self._client.chat.completions.create(**kwargs)
            except openai.RateLimitError as e:
                if "per-day" in str(e) or "per day" in str(e).lower():
                    raise LLMError(
                        "Daily free-model limit reached on OpenRouter (50 requests/day without credits; "
                        "1,000/day after a one-time $10 top-up). Try again tomorrow."
                    ) from e
                if i == attempts - 1:
                    raise
                log.info("Rate limited by the LLM endpoint; waiting 60s before retrying.")
                wait = self._wait_seconds(60)
                if wait <= 0:
                    raise TransientLLMError("Rate limited and out of stage time") from e
                time.sleep(wait)

    def _track(self, inp: int, out: int) -> None:
        with self._lock:
            self.usage["calls"] += 1
            self.usage["input_tokens"] += inp or 0
            self.usage["output_tokens"] += out or 0

    # ── structured output ─────────────────────────────────────
    def structured(self, system: str, prompt: str, schema: type[T], max_tokens: int = 8000) -> T:
        schema_json = json.dumps(schema.model_json_schema(), separators=(",", ":"))
        system_full = (
            f"{system}\n\nRespond with ONE JSON object that validates against this JSON Schema. "
            f"No prose, no markdown fences.\nSCHEMA: {schema_json}"
        )
        messages = [{"role": "user", "content": prompt}]
        last_err: Exception | None = None
        for attempt in range(3):
            t0 = time.time()
            try:
                text = self._complete(system_full, messages, max_tokens, attempt)
            except TransientLLMError as e:
                last_err = e
                log.warning("%s call failed (attempt %d): %s", schema.__name__, attempt + 1, e)
                continue
            log.debug("LLM %s call took %.1fs", schema.__name__, time.time() - t0)
            try:
                data = extract_json(text)
                if not set(data) & set(schema.model_fields):
                    raise ValueError(f"Reply has none of the expected fields (got keys {list(data)[:5]})")
                return schema.model_validate(data)
            except (ValueError, ValidationError) as e:
                last_err = e
                log.warning("Invalid %s JSON (attempt %d): %s", schema.__name__, attempt + 1, str(e)[:300])
                log.debug("Raw model output (%d chars): %r", len(text), text[:1000])
                messages = [
                    *messages,
                    {"role": "assistant", "content": text},
                    {
                        "role": "user",
                        "content": f"That did not validate: {str(e)[:1500]}\n"
                        "Return the corrected JSON object only.",
                    },
                ]
        raise LLMError(f"Could not get valid {schema.__name__} from the model: {last_err}")


def extract_json(text: str) -> dict:
    """Pull the first top-level JSON object out of a model reply."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in model output")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("Unterminated JSON object in model output (response may have been cut off)")
