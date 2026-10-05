"""Vercel Queues subscriber: runs one research stage per message, then queues the next.

Registered in pyproject.toml under [[tool.vercel.subscribers]]; Vercel compiles it into a
private queue-triggered function. Delivery is at-least-once - run_stage is idempotent."""
from __future__ import annotations

import asyncio
from functools import cache

from vercel.queue import Message, Topic, send, subscribe

from .config import load_settings
from .runner import MAX_ATTEMPTS, run_stage
from .store import make_store

stages_topic = Topic[dict[str, str]]("run-stages")


@cache
def _store():
    return make_store()


@cache
def _settings():
    return load_settings()


@subscribe(topic=stages_topic, max_attempts=MAX_ATTEMPTS, retry_after=20)
async def handle_stage(message: Message[dict[str, str]]) -> None:
    run_id, stage = message.payload["run_id"], message.payload["stage"]
    nxt = await asyncio.to_thread(run_stage, _store(), _settings(), run_id, stage,
                                  attempt=message.metadata.delivery_count)
    if nxt:
        await send(stages_topic, {"run_id": run_id, "stage": nxt}, idempotency_key=f"{run_id}:{nxt}")
