"""FIFO Job Queue and Concurrency Manager for audio transcription models."""
from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

LOGGER = logging.getLogger("sheet_studio.queue")


class IpActiveSessionError(Exception):
    """Raised when an IP address already has an active or queued job."""

    def __init__(self, client_ip: str, active_job_id: str):
        super().__init__(
            f"Địa chỉ IP của bạn ({client_ip}) đang có một tác vụ đang xử lý hoặc chờ trong hàng đợi "
            f"(Mã tác vụ: {active_job_id}). Vui lòng chờ tác vụ hiện tại hoàn tất trước khi tạo yêu cầu mới."
        )
        self.client_ip = client_ip
        self.active_job_id = active_job_id


class QueueBusyError(Exception):
    """Raised when the backend FIFO queue has reached its maximum capacity."""

    def __init__(self, current_queued: int, max_queue: int):
        super().__init__(
            f"Máy chủ đang quá tải. Hàng đợi hiện đã đầy ({current_queued}/{max_queue} tác vụ đang chờ). "
            f"Vui lòng thử lại sau khi các tác vụ trước hoàn tất."
        )
        self.current_queued = current_queued
        self.max_queue = max_queue


class QueueManager:
    """Thread-safe FIFO queue coordinator with per-IP concurrency throttling."""

    def __init__(
        self,
        store: Any,
        max_workers: int | None = None,
        max_queue: int | None = None,
        max_active_per_ip: int | None = None,
    ):
        self.store = store
        self.max_workers = max_workers or int(os.environ.get("SHEET_STUDIO_MAX_WORKERS", "1"))
        self.max_queue = max_queue or int(os.environ.get("SHEET_STUDIO_MAX_QUEUE", "10"))
        self.max_active_per_ip = max_active_per_ip or int(os.environ.get("SHEET_STUDIO_MAX_ACTIVE_PER_IP", "1"))

        self.lock = threading.RLock()
        self.cancellations: dict[str, threading.Event] = {}
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="transcription-worker"
        )
        LOGGER.info(
            "QueueManager initialized: max_workers=%d, max_queue=%d, max_per_ip=%d",
            self.max_workers,
            self.max_queue,
            self.max_active_per_ip,
        )

    def enqueue(
        self,
        project_id: str,
        options: dict,
        client_ip: str | None,
        job_runner: Callable[[dict, dict, threading.Event], None],
    ) -> dict:
        """Validate IP session limit and queue capacity, then enqueue job FIFO."""
        with self.lock:
            # 1. Enforce 1 active session per client IP
            if client_ip:
                active_job = self.store.get_active_job_for_ip(client_ip)
                if active_job:
                    raise IpActiveSessionError(client_ip, active_job["id"])

            # 2. Enforce maximum queue capacity to prevent server overload
            running, queued = self.store.count_active_and_queued_jobs()
            if queued >= self.max_queue:
                raise QueueBusyError(queued, self.max_queue)

            # 3. Create job in storage with client IP
            job = self.store.create_job(project_id, options, client_ip=client_ip)
            event = threading.Event()
            self.cancellations[job["id"]] = event

        # 4. Submit to FIFO thread pool executor
        self.executor.submit(self._worker_wrapper, job, options, event, job_runner)
        # Return updated job metadata including queue position
        return self.store.job(job["id"])

    def _worker_wrapper(
        self,
        job: dict,
        options: dict,
        event: threading.Event,
        job_runner: Callable[[dict, dict, threading.Event], None],
    ):
        job_id = job["id"]
        try:
            if event.is_set():
                self.store.update_job(job_id, "cancelled", "cancelled", "Đã hủy tác vụ trước khi bắt đầu.")
                return
            job_runner(job, options, event)
        except Exception as exc:
            LOGGER.exception("Unhandled error in job %s: %s", job_id, exc)
            self.store.update_job(job_id, "failed", "failed", "Lỗi xử lý tác vụ", str(exc)[:2000])
        finally:
            with self.lock:
                self.cancellations.pop(job_id, None)

    def cancel(self, job_id: str) -> dict:
        """Cancel a running or queued job and release worker/IP slot."""
        with self.lock:
            event = self.cancellations.get(job_id)
            if event:
                event.set()
            job = self.store.job(job_id)
            if job["status"] in ("queued", "running"):
                self.store.update_job(job_id, "cancelled", "cancelled", "Đã yêu cầu hủy phân tích")
            return self.store.job(job_id)

    def get_status(self, client_ip: str | None = None) -> dict:
        """Query current FIFO queue load, worker occupancy, and client IP availability."""
        running, queued = self.store.count_active_and_queued_jobs()
        active_job = self.store.get_active_job_for_ip(client_ip) if client_ip else None
        return {
            "max_workers": self.max_workers,
            "max_queue": self.max_queue,
            "max_active_per_ip": self.max_active_per_ip,
            "running_jobs": running,
            "queued_jobs": queued,
            "is_busy": running >= self.max_workers,
            "is_full": queued >= self.max_queue,
            "client_ip": client_ip,
            "client_active_job_id": active_job["id"] if active_job else None,
            "client_can_submit": (queued < self.max_queue) and (active_job is None),
        }

    def shutdown(self):
        """Clean shutdown of all worker threads and cancel events."""
        with self.lock:
            for event in self.cancellations.values():
                event.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
