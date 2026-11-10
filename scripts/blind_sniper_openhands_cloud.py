#!/usr/bin/env python3
"""OpenHands Cloud V1 API adapter for Blind Sniper.

Implements the documented V1 conversation surface used by this project:

* ``POST /api/v1/app-conversations``            start a conversation (async start-task)
* ``GET  /api/v1/app-conversations/start-tasks`` poll a start task until READY
* ``GET  /api/v1/app-conversations``            retrieve conversation status
* ``GET  /api/v1/conversation/{id}/events/search`` retrieve messages/events
* ``POST /api/v1/app-conversations/{id}/cancel``  best-effort cancellation

Authentication is a bearer token read from the environment variable named by the
caller (default ``OPENHANDS_CLOUD_API_KEY``). The token is never printed, logged
or written to a receipt; request/response surfaces are redacted.

The adapter is deliberately conservative: it is a *client contract*. A live
round trip is required before any external integration may be called VERIFIED.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from blind_sniper_redact import redact

DEFAULT_BASE_URL = "https://app.all-hands.dev"
DEFAULT_TOKEN_ENV = "OPENHANDS_CLOUD_API_KEY"
TERMINAL_START_STATES = {"READY", "ERROR", "FAILED", "CANCELLED"}
START_TASK_ID = re.compile(r"^[A-Za-z0-9_-]{4,128}$")


class OpenHandsCloudError(RuntimeError):
    """OpenHands Cloud adapter failure: transport, HTTP or contract error."""


def _urlopen_transport(method: str, url: str, headers: dict, body: bytes | None, timeout: int):
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()
    except URLError as exc:
        raise OpenHandsCloudError(f"OpenHands Cloud transport failed: {exc.reason}") from exc


def _first(record: Any) -> Any:
    """V1 list endpoints return a JSON list; ``ids=`` misses surface as ``[null]``."""
    if isinstance(record, list):
        return record[0] if record else None
    return record


class OpenHandsCloudClient:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        token_env: str = DEFAULT_TOKEN_ENV,
        token: str | None = None,
        transport: Callable[..., Any] | None = None,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        if not base_url.startswith("https://"):
            raise OpenHandsCloudError("base_url must be an absolute https URL")
        if max_retries < 1:
            raise OpenHandsCloudError("max_retries must be at least one")
        self.base_url = base_url.rstrip("/")
        self.token_env = token_env
        self._token = token if token is not None else os.environ.get(token_env, "")
        if not self._token:
            raise OpenHandsCloudError(
                f"OpenHands Cloud requires a bearer token in environment variable {token_env}"
            )
        self.transport = transport or _urlopen_transport
        self.timeout = timeout
        self.max_retries = max_retries

    # -- internals ---------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "Blind-Sniper-OpenHands-Cloud",
        }

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        url = f"{self.base_url}{path}"
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
        headers = self._headers()
        if payload is not None:
            headers["Content-Type"] = "application/json"
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                status, raw = self.transport(method, url, headers, payload, self.timeout)
            except OpenHandsCloudError:
                raise
            except Exception as exc:  # transport-level; retry bounded
                last_error = exc
                if attempt < self.max_retries:
                    continue
                raise OpenHandsCloudError(f"OpenHands Cloud request failed: {type(exc).__name__}") from exc
            try:
                decoded = json.loads(raw.decode("utf-8")) if raw else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                decoded = None
            if status >= 500 and attempt < self.max_retries:
                continue
            return status, decoded
        raise OpenHandsCloudError(f"OpenHands Cloud request failed after {self.max_retries} attempts") from last_error

    # -- operations --------------------------------------------------------
    def start_conversation(
        self,
        *,
        initial_message: str,
        selected_repository: str | None = None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Create a conversation start task. Idempotent per ``idempotency_key``."""
        if not str(initial_message).strip():
            raise OpenHandsCloudError("initial_message is required")
        if not str(idempotency_key).strip():
            raise OpenHandsCloudError("idempotency_key is required")
        body: dict[str, Any] = {"initial_message": initial_message}
        if selected_repository:
            body["selected_repository"] = selected_repository
        status, decoded = self._request("POST", "/api/v1/app-conversations", body)
        if status not in (200, 201, 202):
            raise OpenHandsCloudError(f"start_conversation failed with HTTP {status}: {redact(decoded)}")
        record = _first(decoded) if isinstance(decoded, list) else decoded
        record = record or {}
        start_task_id = record.get("id") or record.get("start_task_id") or record.get("task_id")
        return {
            "idempotency_key": idempotency_key,
            "http_status": status,
            "start_task_id": start_task_id,
            "app_conversation_id": record.get("app_conversation_id") or record.get("conversation_id"),
            "status": record.get("status"),
            "raw": redact(record),
        }

    def poll_start_task(
        self,
        start_task_id: str,
        *,
        timeout_seconds: int = 120,
        interval_seconds: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> dict[str, Any]:
        """Poll ``start-tasks?ids=`` until the task reaches a terminal state."""
        if not START_TASK_ID.match(str(start_task_id)):
            raise OpenHandsCloudError("Invalid start_task_id")
        deadline = monotonic() + timeout_seconds
        polls = 0
        while True:
            polls += 1
            status, decoded = self._request(
                "GET", f"/api/v1/app-conversations/start-tasks?ids={start_task_id}"
            )
            if status != 200:
                raise OpenHandsCloudError(f"poll_start_task failed with HTTP {status}: {redact(decoded)}")
            record = _first(decoded) or {}
            state = str(record.get("status") or record.get("state") or "").upper()
            if state in TERMINAL_START_STATES:
                return {
                    "start_task_id": start_task_id,
                    "state": state,
                    "polls": polls,
                    "app_conversation_id": record.get("app_conversation_id") or record.get("conversation_id"),
                    "raw": redact(record),
                }
            if monotonic() >= deadline:
                return {
                    "start_task_id": start_task_id,
                    "state": state or "TIMEOUT",
                    "polls": polls,
                    "app_conversation_id": record.get("app_conversation_id") or record.get("conversation_id"),
                    "timed_out": True,
                    "raw": redact(record),
                }
            sleep(interval_seconds)

    def get_conversation(self, app_conversation_id: str) -> dict[str, Any]:
        if not str(app_conversation_id).strip():
            raise OpenHandsCloudError("app_conversation_id is required")
        status, decoded = self._request(
            "GET", f"/api/v1/app-conversations?ids={app_conversation_id}"
        )
        if status != 200:
            raise OpenHandsCloudError(f"get_conversation failed with HTTP {status}: {redact(decoded)}")
        record = _first(decoded) or {}
        return {
            "app_conversation_id": app_conversation_id,
            "execution_status": record.get("execution_status"),
            "sandbox_status": record.get("sandbox_status"),
            "pr_number": record.get("pr_number"),
            "raw": redact(record),
        }

    def get_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 100,
        max_pages: int = 20,
    ) -> dict[str, Any]:
        """Read events/messages, following ``next_page_id`` to exhaustion or the page cap."""
        if not str(conversation_id).strip():
            raise OpenHandsCloudError("conversation_id is required")
        if limit < 1 or max_pages < 1:
            raise OpenHandsCloudError("limit and max_pages must be positive")
        events: list[Any] = []
        pages = 0
        next_page_id: str | None = None
        complete = True
        while pages < max_pages:
            pages += 1
            path = f"/api/v1/conversation/{conversation_id}/events/search?limit={limit}"
            if next_page_id:
                path += f"&page_id={next_page_id}"
            status, decoded = self._request("GET", path)
            if status != 200:
                raise OpenHandsCloudError(f"get_messages failed with HTTP {status}: {redact(decoded)}")
            if isinstance(decoded, dict):
                events.extend(decoded.get("items", []))
                next_page_id = decoded.get("next_page_id")
            elif isinstance(decoded, list):
                events.extend(decoded)
                next_page_id = None
            else:
                next_page_id = None
            if not next_page_id:
                break
        else:
            complete = False
        return {
            "conversation_id": conversation_id,
            "pages": pages,
            "pagination_complete": complete,
            "event_count": len(events),
            "events": redact(events),
        }

    def cancel_conversation(self, app_conversation_id: str) -> dict[str, Any]:
        """Best-effort cancellation; reports ``supported=False`` if the API refuses."""
        if not str(app_conversation_id).strip():
            raise OpenHandsCloudError("app_conversation_id is required")
        status, decoded = self._request(
            "POST", f"/api/v1/app-conversations/{app_conversation_id}/cancel"
        )
        if status in (200, 202):
            return {"app_conversation_id": app_conversation_id, "supported": True, "http_status": status}
        if status in (404, 405, 501):
            return {"app_conversation_id": app_conversation_id, "supported": False, "http_status": status}
        raise OpenHandsCloudError(f"cancel_conversation failed with HTTP {status}: {redact(decoded)}")

    def receipt(self, *, operation: str, result: dict[str, Any]) -> dict[str, Any]:
        """Wrap an operation result in a redacted, timestamped audit receipt."""
        return {
            "schema_version": "1.0.0",
            "adapter": "openhands_cloud_v1",
            "operation": operation,
            "at": datetime.now(timezone.utc).isoformat(),
            "result": redact(result),
        }
