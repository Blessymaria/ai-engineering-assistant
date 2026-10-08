"""Run a generated tool in a throwaway, locked-down Docker container.

Protocol (one JSON object per line):
  backend -> container  {"code": "<full source>", "args": {...}}          (first line)
  container -> backend  {"type": "call", "method": "...", "args": {...}}  (a ctx request)
  backend -> container  {"result": ...} or {"error": "..."}               (the ctx reply)
  container -> backend  {"type": "result", "result": ...} or {"type": "error", "error": "..."}
Only JSON crosses the boundary. The generated code is executed by HARNESS inside the
container; the backend process never executes it.
"""

import json
import os
import shlex
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

IMAGE = "aiea-python-base:local"
TIMEOUT_S = 10
MEMORY = "256m"
CPUS = "1"
MAX_CTX_CALLS = 200

HARNESS = r'''
import json, sys

def _send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

class _Ctx:
    def _call(self, method, **args):
        _send({"type": "call", "method": method, "args": {k: v for k, v in args.items() if v is not None}})
        line = sys.stdin.readline()
        if not line:
            raise RuntimeError("ctx channel closed")
        reply = json.loads(line)
        if "error" in reply:
            raise RuntimeError(reply["error"])
        return reply["result"]
    def search_code(self, query, limit=None): return self._call("search_code", query=query, limit=limit)
    def query_graph(self, node, relation, depth=None): return self._call("query_graph", node=node, relation=relation, depth=depth)
    def read_file(self, path, start=None, end=None): return self._call("read_file", path=path, start=start, end=end)
    def list_files(self, path=None, depth=None): return self._call("list_files", path=path, depth=depth)
    def list_nodes(self, kind): return self._call("list_nodes", kind=kind)
    def git_log(self, path, limit=None): return self._call("git_log", path=path, limit=limit)
    def git_log_lines(self, path, start, end, limit=None): return self._call("git_log_lines", path=path, start=start, end=end, limit=limit)
    def git_blame(self, path, start, end): return self._call("git_blame", path=path, start=start, end=end)

first = json.loads(sys.stdin.readline())
try:
    namespace = {}
    exec(compile(first["code"], "<tool>", "exec"), namespace)
    result = namespace["run"](first["args"], _Ctx())
    _send({"type": "result", "result": result})
except Exception as err:
    _send({"type": "error", "error": type(err).__name__ + ": " + str(err)})
'''


@dataclass
class RunResult:
    ok: bool
    result: Any = None
    error: str | None = None
    seconds: float = 0.0
    ctx_calls: list[dict] = field(default_factory=list)


def default_docker_cmd() -> list[str]:
    """`docker`, or Docker Engine inside WSL on Windows. Override with AIEA_DOCKER."""
    if os.environ.get("AIEA_DOCKER"):
        return shlex.split(os.environ["AIEA_DOCKER"])
    return ["wsl", "-d", "Ubuntu", "-u", "root", "--", "docker"] if os.name == "nt" else ["docker"]


class DockerRunner:
    def __init__(self, docker_cmd: list[str] | None = None, image: str = IMAGE, timeout: float = TIMEOUT_S):
        self.docker = docker_cmd or default_docker_cmd()
        self.image = image
        self.timeout = timeout

    def available(self) -> bool:
        try:
            out = subprocess.run([*self.docker, "image", "inspect", self.image], capture_output=True, timeout=30)
            return out.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def command(self, name: str) -> list[str]:
        return [
            *self.docker, "run", "--rm", "-i", "--name", name,
            "--network", "none", "--read-only", "--memory", MEMORY, "--cpus", CPUS,
            "--pids-limit", "64", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            self.image, "python3", "-u", "-c", HARNESS,
        ]

    def run(self, code: str, args: dict, handle_call: Callable[[str, dict], Any]) -> RunResult:
        """Run `code` (defining run(args, ctx)) with args; ctx requests go to handle_call."""
        name = f"aiea-tool-{uuid.uuid4().hex[:10]}"
        start = time.perf_counter()
        calls: list[dict] = []
        try:
            proc = subprocess.Popen(self.command(name), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, encoding="utf-8")
        except OSError as err:
            return RunResult(False, error=f"cannot start docker: {err}")

        timed_out = threading.Event()

        def kill() -> None:
            timed_out.set()
            subprocess.run([*self.docker, "kill", name], capture_output=True, timeout=30)
            proc.kill()

        timer = threading.Timer(self.timeout, kill)
        timer.start()
        try:
            proc.stdin.write(json.dumps({"code": code, "args": args}) + "\n")
            proc.stdin.flush()
            while True:
                line = proc.stdout.readline()
                if not line:
                    if timed_out.is_set():
                        return self._done(False, None, f"timed out after {self.timeout}s", start, calls)
                    proc.wait(timeout=5)
                    err = proc.stderr.read().strip()[-500:]
                    return self._done(False, None, f"container exited without a result: {err}", start, calls)
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    return self._done(False, None, f"tool printed non-JSON output: {line[:200]!r}", start, calls)
                if msg.get("type") == "result":
                    return self._done(True, msg.get("result"), None, start, calls)
                if msg.get("type") == "error":
                    return self._done(False, None, msg.get("error"), start, calls)
                if msg.get("type") != "call" or len(calls) >= MAX_CTX_CALLS:
                    return self._done(False, None, "too many ctx calls or bad message", start, calls)
                calls.append({"method": msg.get("method"), "args": msg.get("args", {})})
                try:
                    reply = {"result": handle_call(msg.get("method", ""), msg.get("args") or {})}
                except Exception as err:  # returned to the tool as an exception
                    reply = {"error": str(err)}
                proc.stdin.write(json.dumps(reply) + "\n")
                proc.stdin.flush()
        except (BrokenPipeError, OSError) as err:
            if timed_out.is_set():
                return self._done(False, None, f"timed out after {self.timeout}s", start, calls)
            return self._done(False, None, f"container I/O error: {err}", start, calls)
        finally:
            timer.cancel()
            if proc.poll() is None:
                proc.kill()

    @staticmethod
    def _done(ok: bool, result: Any, error: str | None, start: float, calls: list[dict]) -> RunResult:
        return RunResult(ok, result, error, round(time.perf_counter() - start, 2), calls)
