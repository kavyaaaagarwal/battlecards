"""LLM robustness: empty replies rejected, retries rotate models, provider hiccups retried."""
import threading
import time
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from intel.llm import LLM, LLMError, TransientLLMError


class Thing(BaseModel):
    name: str


def bare_llm(provider="openrouter") -> LLM:
    llm = LLM.__new__(LLM)
    llm.provider, llm.model, llm._fallbacks = provider, "m1", ["m2", "m3"]
    llm.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
    llm._lock, llm.models_used, llm._json_mode = threading.Lock(), set(), True
    llm.deadline = None
    LLM._needs_reasoning.clear()
    return llm


def test_empty_object_reply_is_rejected_and_retried():
    llm, seen = bare_llm(), []
    replies = ['{"": ""}', '{"name": "Acme"}']

    def fake_complete(system, messages, max_tokens, attempt=0):
        seen.append(attempt)
        return replies[attempt]

    llm._complete = fake_complete
    assert llm.structured("sys", "prompt", Thing).name == "Acme"
    assert seen == [0, 1]


def test_transient_provider_error_is_retried():
    llm, calls = bare_llm(), []

    def fake_complete(system, messages, max_tokens, attempt=0):
        calls.append(attempt)
        if attempt == 0:
            raise TransientLLMError("504 upstream idle timeout")
        return '{"name": "ok"}'

    llm._complete = fake_complete
    assert llm.structured("sys", "prompt", Thing).name == "ok"
    assert calls == [0, 1]


def test_retry_leads_with_next_model_and_disables_reasoning():
    llm, sent = bare_llm(), []

    def create(**kwargs):
        sent.append(kwargs)
        msg = SimpleNamespace(content='{"name": "x"}')
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")],
                               usage=None, model=kwargs["model"], error=None)

    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    llm._complete("sys", [{"role": "user", "content": "hi"}], 100, attempt=1)
    assert sent[0]["model"] == "m2"
    assert sent[0]["extra_body"]["models"] == ["m2", "m3", "m1"]
    assert sent[0]["extra_body"]["reasoning"] == {"effort": "none"}


def test_all_attempts_failing_raises_llm_error():
    llm = bare_llm()
    llm._complete = lambda system, messages, max_tokens, attempt=0: "not json"
    with pytest.raises(LLMError):
        llm.structured("sys", "prompt", Thing)



def test_expired_deadline_stops_without_calling_the_model():
    llm, called = bare_llm(), []
    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kw: called.append(kw))))
    llm.deadline = time.monotonic() - 1
    with pytest.raises(LLMError):
        llm.structured("sys", "prompt", Thing)
    assert called == []


def test_model_that_requires_reasoning_gets_minimal_effort_and_cost_is_recorded():
    import httpx
    import openai

    llm, sent = bare_llm(), []

    def create(**kwargs):
        sent.append(kwargs["extra_body"]["reasoning"])
        if kwargs["extra_body"]["reasoning"] == {"effort": "none"}:
            req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
            raise openai.BadRequestError("Reasoning is mandatory for this endpoint and cannot be disabled.",
                                         response=httpx.Response(400, request=req), body=None)
        msg = SimpleNamespace(content='{"name": "x"}')
        usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=100, cost=0.003)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")],
                               usage=usage, model=kwargs["model"], error=None)

    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    llm._complete("sys", [{"role": "user", "content": "hi"}], 100)
    llm._complete("sys", [{"role": "user", "content": "hi"}], 100)
    assert sent == [{"effort": "none"}, {"effort": "minimal"}, {"effort": "minimal"}]  # remembered after one refusal
    assert llm.usage["cost_usd"] == 0.006
