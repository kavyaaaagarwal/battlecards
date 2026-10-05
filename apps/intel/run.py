#!/usr/bin/env python3
"""Competitive Intelligence Agent.

    python run.py                  # full run using the repo-root .env
    python run.py --env acme.env   # use a different config
    python run.py --fresh          # ignore cached search results

Every run also writes a full log to logs/, so errors are never lost.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
log = logging.getLogger("run")


def launched_in_own_window() -> bool:
    """True when Windows opened a fresh console just for us (double-click / 'Open with Python').
    That window closes the moment Python exits, so we pause before closing."""
    if os.name != "nt":
        return False
    try:
        import ctypes

        return ctypes.windll.kernel32.GetConsoleProcessList((ctypes.c_uint * 4)(), 4) <= 1
    except Exception:
        return False


def setup_logging(verbose: bool) -> Path:
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    log_file = logs / f"run-{datetime.now():%Y%m%d-%H%M%S}.log"
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(fmt)
    file = logging.FileHandler(log_file, encoding="utf-8")
    file.setLevel(logging.DEBUG)  # the file always gets full detail
    file.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers = [console, file]
    for noisy in ("httpx", "httpcore", "urllib3", "anthropic", "openai", "trafilatura", "primp", "ddgs", "charset_normalizer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return log_file


def main(args) -> None:
    from intel.config import load_config
    from intel.render_md import render_markdown
    from intel.runner import run_all
    from intel.runs import create_run, request_from_config
    from intel.store import data_dir, make_store

    if not Path(args.env).exists():
        raise SystemExit(f"Config file {args.env} not found. Copy .env.example to .env and fill it in.")
    cfg = load_config(args.env)
    if args.fresh:
        cfg.cache_ttl_hours = 0
    store = make_store()
    doc, reused = create_run(store, request_from_config(cfg))
    if doc["status"] not in ("succeeded", "partial"):
        doc = run_all(store, cfg, doc["id"])
    if doc["status"] == "failed":
        raise SystemExit(doc["error"])
    out = data_dir() / "exports" / f"{doc['id']}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(doc))
    print(f"\nRun {doc['id']} {'(reused from earlier today)' if reused else ''}: {doc['status']}\n  {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Turn competitor names into cited battlecards.")
    ap.add_argument("--env", default=str(ROOT.parents[1] / ".env"), help="config file (default: repo-root .env)")
    ap.add_argument("--fresh", action="store_true", help="bypass the search/page cache")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    # Work from the project folder no matter how the script was launched.
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    log_file = setup_logging(args.verbose)
    pause = launched_in_own_window()

    code = 0
    try:
        main(args)
    except SystemExit as e:  # config problems: show the message, not a traceback
        if e.code not in (None, 0):
            log.error("%s", e.code)
            code = 1
    except KeyboardInterrupt:
        log.error("Stopped by user.")
        code = 130
    except Exception as e:
        log.debug("Traceback:\n%s", traceback.format_exc())
        log.error("FAILED: %s: %s", type(e).__name__, e)
        code = 1

    print(f"\nFull log: {log_file}")
    if pause:
        input("\nPress Enter to close this window...")
    sys.exit(code)
