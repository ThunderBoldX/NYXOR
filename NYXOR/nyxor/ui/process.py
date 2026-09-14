from __future__ import annotations

import asyncio
import os
import signal
import sys

from nyxor.localization import tr
from nyxor.paths import (
    BASE_DIR,
    CORE_PATH,
    LOG_PATH,
    PID_PATH,
    WORKER_PATH,
    ensure_directories,
)
from nyxor.process_control import (
    cleanup_stale_pid,
    process_running,
    read_pid,
)
from nyxor.storage import load_queue


BRAND_NAME = tr("app.name", default="NYXOR")


class ProcessMixin:
    async def start_nyxor_process(self) -> None:
            cleanup_stale_pid()

            if process_running():
                self.notify(tr("notifications.already_running"), severity="warning")
                return

            if not CORE_PATH.exists() or not WORKER_PATH.exists():
                self.notify(
                    tr("notifications.missing_files"),
                    title=tr("errors.launch"),
                    severity="error",
                )
                return

            if not load_queue():
                self.notify(
                    tr("queue.empty_start"),
                    severity="warning",
                )
                return

            ensure_directories()
            self._stop_requested = False

            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            try:
                # Raw stdout is kept only for a fatal startup traceback.
                # Each manual start truncates the file so it cannot grow forever.
                with LOG_PATH.open("wb", buffering=0) as log_file:
                    process = await asyncio.create_subprocess_exec(
                        sys.executable,
                        str(WORKER_PATH),
                        cwd=str(BASE_DIR),
                        stdout=log_file,
                        stderr=asyncio.subprocess.STDOUT,
                        env=env,
                        start_new_session=True,
                    )
            except OSError as error:
                self.notify(
                    str(error),
                    title=tr("notifications.start_failed"),
                    severity="error",
                )
                return

            PID_PATH.write_text(str(process.pid), encoding="utf-8")
            self.notify(f"PID {process.pid}", title=tr("notifications.started"))
            self.refresh_runtime()

    async def stop_nyxor_process(self, quiet: bool = False) -> None:
            pid = read_pid()

            if not process_running(pid):
                cleanup_stale_pid()
                if not quiet:
                    self.notify(tr("notifications.already_stopped"), severity="warning")
                return

            self._stop_requested = True

            try:
                os.killpg(pid, signal.SIGINT)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    os.kill(pid, signal.SIGINT)
                except (ProcessLookupError, PermissionError, OSError):
                    pass

            for _ in range(20):
                if not process_running(pid):
                    break
                await asyncio.sleep(0.5)

            if process_running(pid):
                try:
                    os.killpg(pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except (ProcessLookupError, PermissionError, OSError):
                        pass

                for _ in range(6):
                    if not process_running(pid):
                        break
                    await asyncio.sleep(0.5)

            if process_running(pid):
                try:
                    os.killpg(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError, OSError):
                        pass

            PID_PATH.unlink(missing_ok=True)

            if not quiet:
                self.notify(tr("notifications.stopped"), title=BRAND_NAME)

            self.refresh_runtime()

    async def restart_nyxor_process(self) -> None:
            if process_running():
                await self.stop_nyxor_process(quiet=True)

            await asyncio.sleep(0.5)
            await self.start_nyxor_process()

    def action_start_nyxor(self) -> None:
            self.run_worker(
                self.start_nyxor_process(),
                group="nyxor-control",
                exclusive=True,
                exit_on_error=False,
            )

    def action_stop_nyxor(self) -> None:
            self.run_worker(
                self.stop_nyxor_process(),
                group="nyxor-control",
                exclusive=True,
                exit_on_error=False,
            )

    def action_restart_nyxor(self) -> None:
            self.run_worker(
                self.restart_nyxor_process(),
                group="nyxor-control",
                exclusive=True,
                exit_on_error=False,
            )
