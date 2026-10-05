"""How a new run gets processed: a background thread locally, Vercel Queues in production."""
from __future__ import annotations

import logging
import threading
from typing import Protocol

from .config import Config
from .runner import run_all
from .stages import Deps
from .store import Store

log = logging.getLogger(__name__)


class Dispatcher(Protocol):
    def start(self, run_id: str) -> None: ...


class SyncDispatcher:
    """Runs everything before returning. Tests only."""

    def __init__(self, store: Store, settings: Config, deps: Deps | None = None):
        self.store, self.settings, self.deps = store, settings, deps

    def start(self, run_id: str) -> None:
        run_all(self.store, self.settings, run_id, deps=self.deps)


class InlineDispatcher(SyncDispatcher):
    """Local development: process the run in a daemon thread of the API process."""

    def start(self, run_id: str) -> None:
        def work():
            try:
                run_all(self.store, self.settings, run_id, deps=self.deps)
            except Exception:  # noqa: BLE001
                log.exception("Run %s crashed", run_id)

        threading.Thread(target=work, name=f"run-{run_id}", daemon=True).start()


class QueueDispatcher:
    """Production: hand the first stage to Vercel Queues; the subscriber chains the rest."""

    def start(self, run_id: str) -> None:
        from vercel.queue.sync import QueueClient

        QueueClient().send("run-stages", {"run_id": run_id, "stage": "collect"}, idempotency_key=f"{run_id}:collect")


def make_dispatcher(settings: Config, store: Store) -> Dispatcher:
    if settings.run_mode == "queue":
        return QueueDispatcher()
    return InlineDispatcher(store, settings)
