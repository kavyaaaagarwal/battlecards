import asyncio
from types import SimpleNamespace

from intel import worker


def test_handle_stage_runs_one_stage_and_queues_the_next(monkeypatch):
    calls, sent = [], []
    monkeypatch.setattr(worker, "run_stage",
                        lambda store, settings, run_id, stage, attempt: calls.append((run_id, stage, attempt)) or "profiles")

    async def fake_send(topic, payload, idempotency_key=None):
        sent.append((payload, idempotency_key))

    monkeypatch.setattr(worker, "send", fake_send)
    monkeypatch.setattr(worker, "_store", lambda: "store")
    monkeypatch.setattr(worker, "_settings", lambda: "settings")
    msg = SimpleNamespace(payload={"run_id": "0123456789", "stage": "collect"},
                          metadata=SimpleNamespace(delivery_count=2))
    asyncio.run(worker.handle_stage(msg))
    assert calls == [("0123456789", "collect", 2)]
    assert sent == [({"run_id": "0123456789", "stage": "profiles"}, "0123456789:profiles")]


def test_last_stage_queues_nothing(monkeypatch):
    sent = []
    monkeypatch.setattr(worker, "run_stage", lambda *a, **k: None)
    monkeypatch.setattr(worker, "send", lambda *a, **k: sent.append(a))
    monkeypatch.setattr(worker, "_store", lambda: None)
    monkeypatch.setattr(worker, "_settings", lambda: None)
    msg = SimpleNamespace(payload={"run_id": "0123456789", "stage": "finalize"}, metadata=SimpleNamespace(delivery_count=1))
    asyncio.run(worker.handle_stage(msg))
    assert sent == []
