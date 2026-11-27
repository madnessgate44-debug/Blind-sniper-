"""Local, process-isolated connectors for files, explicitly allowed commands, and git."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import ctypes
from typing import Any, Sequence

from scripts.blind_sniper_connectors import Connector


DEFAULT_OUTPUT_CAP = 1024 * 1024


def _rooted(root: str | os.PathLike[str], cwd: str | os.PathLike[str] | None = None) -> Path:
    base = Path(root).resolve(strict=True)
    target = base if cwd is None else (base / cwd).resolve(strict=True)
    if not target.is_dir() or not target.is_relative_to(base):
        raise ValueError("cwd must be a directory inside the configured root")
    return target


def _safe_path(root: Path, value: str) -> Path:
    rel = Path(value)
    if not value or rel.is_absolute() or ".." in rel.parts:
        raise ValueError("path must be relative and may not traverse parents")
    target = root / rel
    # Resolve existing parents to reject symlink escapes, even for a new leaf.
    resolved = target.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValueError("path escapes configured root")
    return target


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _kill_group(pgid: int, grace_s: float = 0.15) -> bool:
    """Send TERM, escalate to KILL, and leave reaping to the process owner."""
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return not _group_exists(pgid)
    deadline = time.monotonic() + max(0.0, grace_s)
    while time.monotonic() < deadline and _group_exists(pgid):
        time.sleep(0.01)
    if _group_exists(pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return True


def _descendants(root_pid: int) -> set[int]:
    """Linux: every live descendant of root_pid by parent links, including ones that left the process group."""
    parents: dict[int, int] = {}
    try:
        names = os.listdir("/proc")
    except OSError:
        return set()
    for name in names:
        if name.isdigit():
            try:
                with open(f"/proc/{name}/stat", "rb") as f:
                    parents[int(name)] = int(f.read().rsplit(b")", 1)[1].split()[1])
            except (OSError, ValueError, IndexError):
                pass
    found: set[int] = set()
    frontier = {root_pid}
    while frontier:
        frontier = {pid for pid, ppid in parents.items() if ppid in frontier and pid not in found}
        found |= frontier
    return found


def _alive(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            return f.read().rsplit(b")", 1)[1].split()[0] != b"Z"
    except (OSError, IndexError):
        return False


def _kill_snapshot(pids: set[int]) -> bool:
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and any(_alive(p) for p in pids):
        time.sleep(0.01)
    return not any(_alive(p) for p in pids)


def _become_subreaper() -> None:
    """On Linux, adopt orphaned grandchildren so this process can reap them."""
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err))


def _reap_group_children(pgid: int) -> None:
    """Reap adopted descendants from this process group, without touching others."""
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        try:
            pid, _ = os.waitpid(-pgid, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            if not _group_exists(pgid):
                return
            time.sleep(0.01)


def run_process(
    argv: Sequence[str], *, root: str | os.PathLike[str], cwd: str | os.PathLike[str] | None = None,
    timeout_s: float, cancel: threading.Event | None = None, output_cap: int = DEFAULT_OUTPUT_CAP,
    input_data: bytes | None = None,
) -> dict[str, Any]:
    """Run argv in a fresh session with a minimal environment and bounded captured output."""
    if not isinstance(argv, (list, tuple)) or not argv or any(not isinstance(x, str) for x in argv):
        raise ValueError("argv must be a non-empty list of strings")
    if output_cap <= 0:
        raise ValueError("output_cap must be positive")
    workdir = _rooted(root, cwd)
    _become_subreaper()
    with tempfile.TemporaryDirectory(prefix="bs-native-home-") as home:
        env = {"PATH": os.defpath, "LANG": "C.UTF-8", "HOME": home}
        proc = subprocess.Popen(list(argv), cwd=workdir, env=env,
                                stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                start_new_session=True, shell=False)
        assert proc.stdout is not None
        output = bytearray()
        timed_out = False
        capped = False
        # A reader thread drains output to avoid deadlock while retaining only the cap.
        def drain() -> None:
            nonlocal capped
            while True:
                chunk = proc.stdout.read(8192)
                if not chunk:
                    break
                remaining = output_cap - len(output)
                if remaining > 0:
                    output.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    capped = True
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        if input_data is not None:
            assert proc.stdin is not None
            def feed() -> None:
                try:
                    proc.stdin.write(input_data)
                    proc.stdin.flush()
                except OSError:
                    pass
                finally:
                    proc.stdin.close()
            threading.Thread(target=feed, daemon=True).start()
        deadline = time.monotonic() + max(0.0, timeout_s)
        while proc.poll() is None or reader.is_alive() or _group_exists(proc.pid):
            if (cancel is not None and cancel.is_set()) or time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(0.01)
        group_dead = True
        if timed_out:
            snapshot = _descendants(proc.pid)  # includes children that called setsid and left the group
            group_dead = _kill_group(proc.pid)
            group_dead = _kill_snapshot(snapshot) and group_dead
            # Let ConnectorRegistry reach its timeout and signal cancellation before this
            # worker returns, so it can observe that all subprocess work has stopped.
            if cancel is not None:
                cancel.wait(0.5)
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            group_dead = _kill_group(proc.pid) and group_dead
            proc.wait()
        if timed_out:
            _reap_group_children(proc.pid)
            group_dead = not _group_exists(proc.pid) and group_dead
        reader.join(timeout=3)
        if reader.is_alive():
            # A surviving descendant still holds the pipe; fail closed after group cleanup.
            group_dead = _kill_group(proc.pid) and group_dead
            reader.join(timeout=1)
        proc.stdout.close()
        raw_output = bytes(output)
        for value in env.values():
            encoded = value.encode("utf-8", "ignore")
            if encoded:
                raw_output = raw_output.replace(encoded, b"[REDACTED]")
        return {"returncode": proc.returncode, "output": raw_output.decode("utf-8", "replace"),
                "output_truncated": capped, "timed_out": timed_out, "group_dead": group_dead}


def _tool(name: str, props: dict[str, Any], required: list[str], effects: str) -> dict[str, Any]:
    return {"name": name, "description": name.replace("_", " "), "side_effects": effects,
            "input_schema": {"type": "object", "properties": props, "required": required,
                             "additionalProperties": False}}


class _NativeConnector(Connector):
    cancellable = True

    def __init__(self, root: str | os.PathLike[str], *, output_cap: int = DEFAULT_OUTPUT_CAP):
        self.root = _rooted(root)
        self.output_cap = output_cap

    def health(self) -> dict[str, Any]:
        return {"health": "healthy", "root": str(self.root)}

    def _run(self, argv: Sequence[str], *, timeout_s: float, cancel: threading.Event | None,
             cwd: str | os.PathLike[str] | None = None) -> dict[str, Any]:
        result = run_process(argv, root=self.root, cwd=cwd, timeout_s=timeout_s,
                             cancel=cancel, output_cap=self.output_cap)
        if result["timed_out"]:
            # Keep this call running if a group cannot be proven dead; Registry will record
            # timeout_unknown_state and prevent replay while the call thread remains alive.
            if not result["group_dead"]:
                raise RuntimeError("process group termination could not be verified")
            raise TimeoutError("native process timed out")
        if result["returncode"] != 0:
            raise RuntimeError("native command failed with exit status %s: %s" %
                               (result["returncode"], result["output"]))
        return {"output": result["output"], "output_truncated": result["output_truncated"]}


_FILE_SCRIPT = r'''import json, os, pathlib, sys, uuid
root=pathlib.Path(sys.argv[1]).resolve(); op=sys.argv[2]; rel=pathlib.PurePosixPath(sys.argv[3])
if rel.is_absolute() or any(part in ("..", "") for part in rel.parts): raise SystemExit("invalid relative path")
parts=list(rel.parts)
rootfd=os.open(root, os.O_RDONLY | os.O_DIRECTORY)
parentfd=rootfd
owned_parent=False
tmp_name=None
try:
 for part in parts[:-1]:
  nextfd=os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parentfd)
  if owned_parent: os.close(parentfd)
  parentfd=nextfd; owned_parent=True
 leaf=parts[-1] if parts else None
 if op=="read":
  if leaf is None: raise SystemExit("cannot read directory root")
  fd=os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parentfd)
  with os.fdopen(fd,"rb") as f: data=f.read(int(sys.argv[4])+1)
  if len(data)>int(sys.argv[4]): raise SystemExit("file exceeds size cap")
  print(json.dumps({"data":data.decode("utf-8"),"size":len(data)}))
 elif op=="list":
  if leaf is None:
   dfd=os.dup(rootfd)
  else:
   dfd=os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parentfd)
  try: print(json.dumps({"entries":sorted(os.listdir(dfd))}))
  finally: os.close(dfd)
 elif op=="write":
  if leaf is None: raise SystemExit("cannot replace directory root")
  data=sys.stdin.buffer.read(int(sys.argv[4])+1)
  if len(data)>int(sys.argv[4]): raise SystemExit("file exceeds size cap")
  tmp_name=".bs-write-"+uuid.uuid4().hex
  fd=os.open(tmp_name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parentfd)
  try:
   with os.fdopen(fd,"wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
   os.rename(tmp_name,leaf,src_dir_fd=parentfd,dst_dir_fd=parentfd)
   tmp_name=None
  finally:
   if tmp_name is not None:
    try: os.unlink(tmp_name,dir_fd=parentfd)
    except OSError: pass
  print(json.dumps({"written":len(data)}))
finally:
 if owned_parent: os.close(parentfd)
 os.close(rootfd)
'''


class FilesConnector(_NativeConnector):
    @property
    def connector_id(self) -> str:
        return "files"

    def tools(self) -> list[dict[str, Any]]:
        path = {"path": {"type": "string"}}
        return [_tool("read_file", path, ["path"], "read_only"),
                _tool("list_dir", path, ["path"], "read_only"),
                _tool("write_file", {**path, "content": {"type": "string"}}, ["path", "content"], "mutating")]

    def call(self, tool_name: str, arguments: dict[str, Any], *, timeout_s: float,
             cancel: threading.Event | None = None) -> dict[str, Any]:
        name = {"read_file": "read", "list_dir": "list", "write_file": "write"}.get(tool_name)
        if name is None:
            raise ValueError("unknown files tool")
        target = _safe_path(self.root, arguments["path"])
        content = arguments.get("content", "")
        limit = min(4 * 1024 * 1024, max(1, self.output_cap // 6)) if name == "read" else 4 * 1024 * 1024
        if name == "write" and len(content.encode("utf-8")) > limit:
            raise ValueError("file exceeds size cap")
        argv = [sys.executable, "-I", "-c", _FILE_SCRIPT, str(self.root), name,
                str(target.relative_to(self.root)), str(limit)]
        result = run_process(argv, root=self.root, timeout_s=timeout_s, cancel=cancel,
                             output_cap=self.output_cap,
                             input_data=content.encode("utf-8") if name == "write" else None)
        if result["timed_out"]:
            if not result["group_dead"]:
                raise RuntimeError("process group termination could not be verified")
            raise TimeoutError("native process timed out")
        if result["returncode"] != 0:
            raise RuntimeError("native file operation failed")
        # The script emits a JSON record; output is already capped by the helper.
        return json.loads(result["output"])


class TerminalConnector(_NativeConnector):
    def __init__(self, root: str | os.PathLike[str], executables: set[str] | frozenset[str] | list[str],
                 *, cwd: str | os.PathLike[str] | None = None, output_cap: int = DEFAULT_OUTPUT_CAP):
        super().__init__(root, output_cap=output_cap)
        if not executables or any(not isinstance(x, str) or not os.path.isabs(x) for x in executables):
            raise ValueError("allowlist must contain exact absolute executable paths")
        self.executables = frozenset(os.path.realpath(x) for x in executables)
        self.cwd = _rooted(self.root, cwd)

    @property
    def connector_id(self) -> str:
        return "terminal"

    def tools(self) -> list[dict[str, Any]]:
        return [_tool("run_command", {"argv": {"type": "array", "items": {"type": "string"}}},
                      ["argv"], "mutating")]

    def call(self, tool_name: str, arguments: dict[str, Any], *, timeout_s: float,
             cancel: threading.Event | None = None) -> dict[str, Any]:
        argv = arguments.get("argv")
        if tool_name != "run_command" or not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
            raise ValueError("argv must be a non-empty list of strings")
        executable = os.path.realpath(argv[0])
        if executable not in self.executables:
            raise ValueError("executable is not on the exact allowlist")
        return self._run([executable, *argv[1:]], timeout_s=timeout_s, cancel=cancel, cwd=self.cwd)


class GitConnector(_NativeConnector):
    def __init__(self, root: str | os.PathLike[str], *, output_cap: int = DEFAULT_OUTPUT_CAP):
        super().__init__(root, output_cap=output_cap)

    @property
    def connector_id(self) -> str:
        return "git"

    def tools(self) -> list[dict[str, Any]]:
        return [_tool("status", {}, [], "read_only"), _tool("diff", {}, [], "read_only"),
                _tool("log", {"limit": {"type": "integer"}}, [], "read_only")]

    def call(self, tool_name: str, arguments: dict[str, Any], *, timeout_s: float,
             cancel: threading.Event | None = None) -> dict[str, Any]:
        git = shutil.which("git")
        if git is None:
            raise RuntimeError("git executable is unavailable")
        if tool_name == "status":
            argv = [git, "-C", str(self.root), "status", "--short", "--branch", "--no-renames"]
        elif tool_name == "diff":
            argv = [git, "-C", str(self.root), "diff", "--no-ext-diff", "--no-renames", "--"]
        elif tool_name == "log":
            limit = arguments.get("limit", 10)
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
                raise ValueError("limit must be between 1 and 100")
            argv = [git, "-C", str(self.root), "log", "--no-ext-diff", "--no-decorate",
                    "--format=%h %s", f"-{limit}"]
        else:
            raise ValueError("unknown git tool")
        return self._run(argv, timeout_s=timeout_s, cancel=cancel)


__all__ = ["run_process", "FilesConnector", "TerminalConnector", "GitConnector"]
