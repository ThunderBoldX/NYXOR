"""Private JSON-lines transport for the shared farming engine; no listening socket."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import sys

CORE = Path(__file__).resolve().parents[1] / "core"
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(CORE))

ACTIONS = {"snapshot", "check_connection", "start", "stop", "auth", "logout", "delete_history",
           "queue", "streamers", "points_games", "settings", "directory", "search",
           "browser_begin", "browser_import", "browser_error", "browser_cancel"}


def main():
    # Frozen Python does not inherit PYTHONUTF8 at interpreter startup.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    output = sys.stdout
    sys.stdout = sys.stderr  # Worker diagnostics must never enter the protocol.
    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    resources = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else CORE / "nyxor"
    shutil.copytree(resources / "locales", root / "locales", dirs_exist_ok=True)
    os.environ["NYXOR_PLATFORM"] = "desktop"
    from nyxor import android_runtime as runtime
    runtime.initialize(str(root))

    async def shutdown():
        tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    try:
        for line in sys.stdin:
            identifier = None
            try:
                if len(line) > 65536:
                    raise ValueError("Request too large")
                envelope = json.loads(line)
                identifier = envelope.get("id")
                payload = envelope.get("payload")
                if not isinstance(identifier, str) or not isinstance(payload, dict):
                    raise ValueError("Invalid request")
                if payload.get("action") == "shutdown":
                    break
                if payload.get("action") not in ACTIONS:
                    raise ValueError("Unknown action")
                response = json.loads(runtime.request(json.dumps(payload)))
            except Exception as error:
                response = {"ok": False, "error": str(error)[:240]}
            output.write(json.dumps({"id": identifier, "response": response}, ensure_ascii=False) + "\n")
            output.flush()
    finally:
        try:
            asyncio.run_coroutine_threadsafe(shutdown(), runtime._loop).result(timeout=8)
        finally:
            runtime._loop.call_soon_threadsafe(runtime._loop.stop)
            runtime._thread.join(timeout=2)


if __name__ == "__main__":
    main()
