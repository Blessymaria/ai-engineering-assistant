"""Ollama chat provider (native tool calling), using only the standard library."""

import json
import os
import time
import urllib.error
import urllib.request

from app.llm.base import LLMError, LLMReply, ToolCallRequest

DEFAULT_MODEL = "gemma4:e4b"
DEFAULT_URL = "http://localhost:11434"


class OllamaProvider:
    def __init__(self, model: str | None = None, base_url: str | None = None, timeout: float = 600):
        self.name = model or os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
        self.base_url = (base_url or os.environ.get("OLLAMA_URL", DEFAULT_URL)).rstrip("/")
        self.timeout = timeout
        self._think_supported = True

    def _post(self, body: dict) -> dict:
        req = urllib.request.Request(
            f"{self.base_url}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as res:
            return json.load(res)

    def chat(self, messages: list[dict], tools: list[dict] | None = None, max_tokens: int = 1024) -> LLMReply:
        body = {
            "model": self.name,
            "messages": messages,
            "stream": False,
            # Temperature 0 for repeatable runs; a hard cap because small models can loop (see DEVLOG).
            "options": {"temperature": 0, "num_predict": max_tokens},
        }
        if tools:
            body["tools"] = tools
        if self._think_supported:
            body["think"] = False
        start = time.perf_counter()
        try:
            try:
                data = self._post(body)
            except urllib.error.HTTPError as err:
                detail = err.read().decode(errors="replace")
                if "does not support thinking" not in detail:
                    raise LLMError(f"Ollama error {err.code}: {detail[:300]}") from err
                self._think_supported = False
                body.pop("think")
                data = self._post(body)
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            raise LLMError(f"cannot reach Ollama at {self.base_url}: {err}") from err

        message = data.get("message", {})
        calls = []
        for call in message.get("tool_calls") or []:
            fn = call.get("function", {})
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            calls.append(ToolCallRequest(fn.get("name", ""), args))
        return LLMReply(
            content=message.get("content", "") or "",
            tool_calls=calls,
            tokens=data.get("eval_count", 0),
            seconds=round(time.perf_counter() - start, 1),
            done_reason=data.get("done_reason"),
        )
