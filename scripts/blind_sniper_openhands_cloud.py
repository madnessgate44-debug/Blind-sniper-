#!/usr/bin/env python3
"""OpenHands Cloud V1 app-server API adapter.

Implements the documented V1 endpoints used for delegation:

- ``POST /api/v1/app-conversations``                 create a conversation (async start-task)
- ``GET  /api/v1/app-conversations/start-tasks``      poll the start-task until READY
- ``GET  /api/v1/app-conversations?ids=...``          conversation status
- ``GET  /api/v1/conversation/{id}/events/search``    conversation messages/events
- ``GET  /api/v1/app-conversations/{id}/download``    artifacts (trajectory zip)
- ``POST /api/v1/app-conversations/{id}/...``         cancellation where supported

Auth is a bearer token from ``OPENHANDS_CLOUD_API_KEY`` (falling back to the
legacy ``OPENHANDS_API_KEY``). The adapter is *disabled without the secret* and
never creates, prints or persists a credential. All request/response bodies are
redacted before they can reach a receipt or log.

Dispatch is idempotent: a caller-supplied ``idempotency_key`` maps to one
in-flight start-task so a retried call returns the original task instead of
creating a second sandbox.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from blind_sniper_redaction import redact_value

DEFAULT_BASE_URL = "https://app.all-hands.dev"
CREATE_PATH = "/api/v1/app-conversations"
START_TASKS_PATH = "/api/v1/app-conversations/start-tasks"
DOWNLOAD_PATH = "/api/v1/app-conversations/{id}/download"
EVENTS_PATH = "/api/v1/conversation/{id}/events/search"

# Start-task / execution terminal states we treat as a stop condition.
TERMINAL_START_STATES = {"READY", "ERROR", "FAILED", "CANCELLED"}


class OpenHandsCloudError(RuntimeError):
    """OpenHands Cloud API call failed or the adapter is disabled."""


class OpenHandsCloudClient:
    """Bearer-authenticated V1 client with redaction and idempotent dispatch."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        transport=None,
        timeout: int = 30,
    ) -> None:
        if api_key is None:
            api_key = os.environ.get("OPENHANDS_CLOUD_API_KEY") or os.environ.get("OPENHANDS_API_KEY", "")
        self.api_key = api_key or ""
        self.base_url = base_url.rstrip("/")
        self.transport = transport or self._urlopen_transport
        if not 1 <= timeout <= 120:
            raise OpenHandsCloudError("timeout must be between 1 and 120 seconds")
        self.timeout = timeout
        # idempotency_key -> recorded dispatch result
        self._dispatches: dict[str, dict[str, Any]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Blind-Sniper-OpenHands-Adapter",
        }

    def _urlopen_transport(self, method: str, url: str, headers: dict, body: bytes | None):
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except urllib.error.URLError as exc:
            raise OpenHandsCloudError(f"OpenHands transport failed: {exc.reason}") from exc

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        if not self.enabled:
            raise OpenHandsCloudError("OpenHands Cloud adapter is disabled: no OPENHANDS_CLOUD_API_KEY configured")
        raw = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
        status, payload = self.transport(method, f"{self.base_url}{path}", self._headers(), raw)
        if not payload:
            return status, None
        try:
            return status, json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OpenHandsCloudError("OpenHands response is not valid JSON") from exc

    # -- operations -----------------------------------------------------
    def create_conversation(
        self,
        *,
        initial_message: str,
        selected_repository: str | None = None,
        selected_branch: str | None = None,
        title: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if idempotency_key and idempotency_key in self._dispatches:
            return {**self._dispatches[idempotency_key], "idempotent_replay": True}
        if not isinstance(initial_message, str) or not initial_message.strip():
            raise OpenHandsCloudError("initial_message must be a non-empty string")
        body: dict[str, Any] = {
            "initial_message": {"content": [{"type": "text", "text": initial_message}]},
        }
        if selected_repository:
            body["selected_repository"] = selected_repository
        if selected_branch:
            body["selected_branch"] = selected_branch
        if title:
            body["title"] = title
        status, response = self._request("POST", CREATE_PATH, body)
        if status not in (200, 201, 202):
            raise OpenHandsCloudError(f"create_conversation failed with HTTP {status}")
        result = redact_value(response if isinstance(response, dict) else {})
        record = {
            "start_task_id": result.get("id"),
            "app_conversation_id": result.get("app_conversation_id"),
            "status": result.get("status"),
            "raw": result,
        }
        if idempotency_key:
            self._dispatches[idempotency_key] = record
        return {**record, "idempotent_replay": False}

    def poll_start_task(self, start_task_id: str) -> dict[str, Any]:
        status, response = self._request("GET", f"{START_TASKS_PATH}?ids={start_task_id}")
        if status != 200:
            raise OpenHandsCloudError(f"start-task poll failed with HTTP {status}")
        items = response.get("items") if isinstance(response, dict) else None
        record = items[0] if items else (response if isinstance(response, dict) else {})
        return redact_value({
            "start_task_id": start_task_id,
            "app_conversation_id": record.get("app_conversation_id"),
            "status": record.get("status"),
            "detail": record.get("detail"),
        })

    def wait_for_start_task(self, start_task_id: str, *, max_polls: int = 10, sleep=None) -> dict[str, Any]:
        if not 1 <= max_polls <= 60:
            raise OpenHandsCloudError("max_polls must be between 1 and 60")
        sleep = sleep or (lambda _s: None)
        last = {"start_task_id": start_task_id, "status": None}
        for _ in range(max_polls):
            last = self.poll_start_task(start_task_id)
            if last.get("status") in TERMINAL_START_STATES:
                return last
            sleep(1)
        return last

    def conversation_status(self, app_conversation_id: str) -> dict[str, Any]:
        status, response = self._request("GET", f"{CREATE_PATH}?ids={app_conversation_id}")
        if status != 200:
            raise OpenHandsCloudError(f"conversation status failed with HTTP {status}")
        items = response.get("items") if isinstance(response, dict) else None
        record = items[0] if items else (response if isinstance(response, dict) else {})
        return redact_value({
            "app_conversation_id": app_conversation_id,
            "sandbox_status": record.get("sandbox_status"),
            "execution_status": record.get("execution_status"),
            "conversation_ui_url": record.get("conversation_ui_url"),
        })

    def conversation_messages(self, app_conversation_id: str, *, limit: int = 50) -> dict[str, Any]:
        if not 1 <= limit <= 200:
            raise OpenHandsCloudError("limit must be between 1 and 200")
        status, response = self._request("GET", f"{EVENTS_PATH.format(id=app_conversation_id)}?limit={limit}")
        if status != 200:
            raise OpenHandsCloudError(f"conversation events failed with HTTP {status}")
        items = response.get("items", []) if isinstance(response, dict) else []
        return redact_value({
            "app_conversation_id": app_conversation_id,
            "event_count": len(items),
            "events": items,
        })

    def conversation_artifacts(self, app_conversation_id: str) -> dict[str, Any]:
        """Report artifact availability without downloading the trajectory."""
        status, payload = self.transport(
            "GET", f"{self.base_url}{DOWNLOAD_PATH.format(id=app_conversation_id)}", self._headers(), None,
        )
        if status not in (200, 302):
            return {"app_conversation_id": app_conversation_id, "artifacts_available": False, "status": status}
        size = len(payload) if isinstance(payload, (bytes, bytearray)) else None
        return {"app_conversation_id": app_conversation_id, "artifacts_available": True,
                "trajectory_bytes": size, "path": DOWNLOAD_PATH.format(id=app_conversation_id)}

    def cancel(self, app_conversation_id: str) -> dict[str, Any]:
        """Cancel via the pause endpoint; some deployments do not support it."""
        for method, path in (
            ("POST", f"/api/v1/app-conversations/{app_conversation_id}/pause"),
            ("POST", f"/api/v1/app-conversations/{app_conversation_id}/cancel"),
        ):
            status, _ = self._request(method, path, {})
            if status in (200, 202, 204):
                return {"cancelled": True, "app_conversation_id": app_conversation_id, "endpoint": path}
            if status in (404, 405):
                continue
        return {"cancelled": False, "app_conversation_id": app_conversation_id,
                "reason": "cancellation endpoint not supported by this deployment"}

    def capabilities(self) -> dict[str, Any]:
        return {
            "adapter": "openhands_cloud_v1",
            "enabled": self.enabled,
            "auth": "bearer",
            "secret_env": "OPENHANDS_CLOUD_API_KEY",
            "operations": ["create_conversation", "poll_start_task", "conversation_status",
                           "conversation_messages", "conversation_artifacts", "cancel"],
            "cost_class": "usage_based_unverified",
            "notes": "Disabled without the secret; no live call is made by this module unless invoked.",
        }
