"""Unauthenticated, process-isolated, read-only GitHub REST connector."""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import sys
import threading
from typing import Any
from urllib import parse as urlparse

from scripts.blind_sniper_connectors import Connector
from scripts.blind_sniper_native_connectors import run_process


_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_SHA = re.compile(r"[0-9a-fA-F]{40}\Z")
_MAX_RESPONSE = 2 * 1024 * 1024

# This code executes in a fresh Python process with run_process's scrubbed env.
_HTTP_CHILD = r'''import base64,json,sys,urllib.error,urllib.request
url,limit=sys.argv[1],int(sys.argv[2])
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  sys.exit(3)
opener=urllib.request.build_opener(NoRedirect)
req=urllib.request.Request(url,headers={"Accept":"application/vnd.github+json","User-Agent":"BlindSniper-ReadOnly"},method="GET")
try:
 response=opener.open(req,timeout=300)
except urllib.error.HTTPError as exc:
 response=exc
body=response.read(limit+1)
if len(body)>limit:
 print(json.dumps({"oversized":True,"status":int(response.code)}));sys.exit(0)
print(json.dumps({"status":int(response.code),"body":base64.b64encode(body).decode("ascii")}))
'''


def _tool(name: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "description": "Read public GitHub repository data",
        "side_effects": "read_only",
        "input_schema": {"type": "object", "properties": properties,
                         "required": required, "additionalProperties": False},
    }


class GitHubReadOnlyConnector(Connector):
    """Read a single public repository using only unauthenticated REST GET requests."""

    cancellable = True

    def __init__(self, repository: str, *, base_url: str = "https://api.github.com",
                 response_cap: int = _MAX_RESPONSE):
        if not isinstance(repository, str) or not _REPO.fullmatch(repository):
            raise ValueError("repository must be configured as owner/name")
        parsed = urlparse.urlsplit(base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise ValueError("base URL must contain only an allowlisted host")
        host = (parsed.hostname or "").lower()
        loopback = False
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
        if not ((parsed.scheme == "https" and host == "api.github.com") or
                (parsed.scheme == "http" and loopback)):
            raise ValueError("base URL host is not allowlisted")
        if parsed.port not in (None, 80, 443) and not loopback:
            raise ValueError("base URL port is not allowlisted")
        if not isinstance(response_cap, int) or isinstance(response_cap, bool) or response_cap < 1:
            raise ValueError("response_cap must be a positive integer")
        self.repository = repository
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.response_cap = min(response_cap, _MAX_RESPONSE)

    @property
    def connector_id(self) -> str:
        return "github"

    def health(self) -> dict[str, Any]:
        return {"health": "healthy", "repository": self.repository, "authentication": "none"}

    def tools(self) -> list[dict[str, Any]]:
        return [
            _tool("pr_status", {"number": {"type": "integer", "minimum": 1, "maximum": 2147483647}}, ["number"]),
            _tool("check_runs", {"ref": {"type": "string", "pattern": "^[0-9a-fA-F]{40}$"}}, ["ref"]),
            _tool("issue_comments", {
                "number": {"type": "integer", "minimum": 1, "maximum": 2147483647},
                "limit": {"type": "integer", "minimum": 1, "maximum": 30},
            }, ["number", "limit"]),
        ]

    def _get_json(self, path: str, timeout_s: float, cancel: threading.Event | None) -> Any:
        if cancel is not None and cancel.is_set():
            raise TimeoutError("GitHub read cancelled")
        url = self.base_url + "/repos/" + self.repository + path
        result = run_process(
            [sys.executable, "-I", "-c", _HTTP_CHILD, url, str(self.response_cap)],
            root=Path(__file__).resolve().parents[1],
            timeout_s=timeout_s, cancel=cancel,
            output_cap=(((self.response_cap + 2) // 3) * 4) + 1024,
        )
        if result["timed_out"]:
            raise TimeoutError("GitHub request timed out and child process was stopped")
        if not result["group_dead"]:
            raise RuntimeError("GitHub request child process termination could not be verified")
        if result["returncode"] != 0:
            if result["returncode"] == 3:
                raise RuntimeError("GitHub redirect refused")
            raise RuntimeError("GitHub request failed")
        if result["output_truncated"]:
            raise ValueError("GitHub response exceeded size cap")
        try:
            envelope = json.loads(result["output"])
            if envelope.get("oversized"):
                raise ValueError("GitHub response exceeded size cap")
            status = envelope["status"]
            if status in (403, 429):
                raise RuntimeError(f"GitHub rate limit or access limit (HTTP {status})")
            if status == 404:
                raise LookupError("GitHub resource not found (HTTP 404)")
            if status < 200 or status >= 300:
                raise RuntimeError(f"GitHub request failed (HTTP {status})")
            raw = base64.b64decode(envelope["body"], validate=True)
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as exc:
            raise ValueError("GitHub returned malformed JSON") from exc

    def call(self, tool_name: str, arguments: dict[str, Any], *, timeout_s: float,
             cancel: threading.Event | None = None) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be an object")
        if tool_name in ("pr_status", "issue_comments"):
            number = arguments.get("number")
            if not isinstance(number, int) or isinstance(number, bool) or not 1 <= number <= 2147483647:
                raise ValueError("number must be an integer from 1 to 2147483647")
        if tool_name == "issue_comments":
            limit = arguments.get("limit")
            if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 30:
                raise ValueError("limit must be an integer from 1 to 30")
        if tool_name == "check_runs":
            ref = arguments.get("ref")
            if not isinstance(ref, str) or not _SHA.fullmatch(ref):
                raise ValueError("ref must be a 40-character hexadecimal SHA")
        if tool_name == "pr_status":
            number = arguments["number"]
            data = self._get_json(f"/pulls/{number}", timeout_s, cancel)
            fields = ("number", "title", "state", "draft", "merged", "head", "base", "mergeable")
            if not isinstance(data, dict):
                raise ValueError("GitHub returned malformed pull request JSON")
            result = {key: data[key] for key in fields if key in data and key not in ("head", "base")}
            if isinstance(data.get("head"), dict) and "sha" in data["head"]:
                result["head_sha"] = data["head"]["sha"]
            for side in ("base", "head"):
                if isinstance(data.get(side), dict) and "ref" in data[side]:
                    result[side + "_ref"] = data[side]["ref"]
            return result
        if tool_name == "check_runs":
            ref = arguments["ref"]
            if not _SHA.fullmatch(ref):
                raise ValueError("ref must be a 40-character hexadecimal SHA")
            data = self._get_json(f"/commits/{ref}/check-runs", timeout_s, cancel)
            if not isinstance(data, dict) or not isinstance(data.get("check_runs"), list):
                raise ValueError("GitHub returned malformed check runs JSON")
            workflow_data = self._get_json(f"/actions/runs?head_sha={ref}&per_page=100", timeout_s, cancel)
            if not isinstance(workflow_data, dict) or not isinstance(workflow_data.get("workflow_runs"), list):
                raise ValueError("GitHub returned malformed workflow runs JSON")
            return {"check_runs": [{key: run[key] for key in ("name", "status", "conclusion", "html_url") if key in run}
                                   for run in data["check_runs"] if isinstance(run, dict)],
                    "workflow_run_ids": [run["id"] for run in workflow_data["workflow_runs"]
                                         if isinstance(run, dict) and isinstance(run.get("id"), int)]}
        if tool_name == "issue_comments":
            number, limit = arguments["number"], arguments["limit"]
            data = self._get_json(f"/issues/{number}/comments?per_page={limit}", timeout_s, cancel)
            if not isinstance(data, list):
                raise ValueError("GitHub returned malformed issue comments JSON")
            comments = []
            for comment in data[:limit]:
                if not isinstance(comment, dict):
                    continue
                body = comment.get("body") if isinstance(comment.get("body"), str) else ""
                user = comment.get("user") if isinstance(comment.get("user"), dict) else {}
                comments.append({
                    "id": comment.get("id"), "author_login": user.get("login"),
                    "created_at": comment.get("created_at"), "html_url": comment.get("html_url"),
                    "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "body_excerpt": body[:400],
                })
            return {"comments": comments, "untrusted_content": True}
        raise ValueError("unknown GitHub read-only tool")
