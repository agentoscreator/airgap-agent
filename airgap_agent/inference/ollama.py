"""BACKUP backend: local Ollama server over loopback only.

Ollama runs as `ollama serve` inside the SAME container, bound to
127.0.0.1:11434. This backend speaks HTTP to that loopback address and
nowhere else. Loopback traffic never leaves the host and is unaffected by
`docker run --network none`.

Hard rules enforced here:
  * The host MUST be a loopback literal (127.0.0.1 / ::1 / localhost).
    We refuse to construct a client for any other host, so a config typo
    or tampering cannot turn this into an egress path.
  * Models are pulled at BUILD time into the image. This backend never
    pulls at runtime (a pull is an egress event).
"""

from __future__ import annotations

import os
from typing import Iterator

from .base import GenerationConfig, InferenceBackend

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _assert_loopback(host: str) -> None:
    if host not in _LOOPBACK_HOSTS:
        raise ValueError(
            f"Ollama host {host!r} is not loopback. The airgap invariant "
            "allows the inference backend to reach ONLY 127.0.0.1 / ::1 / "
            "localhost. Refusing to create a client that could egress."
        )


def _think_from_env() -> bool | None:
    """Reasoning ("thinking") toggle for models that support it.

    Unset  -> omit the field entirely (works with every model).
    "0"    -> ask the model NOT to think, so the whole token budget goes to
              the answer instead of a scratchpad.
    "1"    -> ask the model to think.
    "auto" -> omit the field, i.e. let the model decide.
    """
    raw = os.environ.get("OLLAMA_THINK")
    if raw is None:
        return None
    raw = raw.strip().lower()
    if raw in {"", "auto", "model"}:
        return None
    return raw not in {"0", "false", "no", "off"}


class OllamaBackend(InferenceBackend):
    name = "ollama"

    def __init__(self, host: str | None = None, model: str | None = None) -> None:
        self.host = host or os.environ.get("OLLAMA_HOST", "127.0.0.1")
        _assert_loopback(self.host)
        self.port = int(os.environ.get("OLLAMA_PORT", "11434"))
        self.model = model or os.environ.get("OLLAMA_MODEL", "")
        self._base = f"http://{self.host}:{self.port}"
        self.think = _think_from_env()
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        _assert_loopback(self.host)  # re-check; cheap and paranoid
        import httpx  # loopback-only use; see SECURITY.md carve-out

        self._client = httpx.Client(base_url=self._base, timeout=None)
        return self._client

    def health_check(self) -> None:
        client = self._ensure_client()
        client.get("/api/tags").raise_for_status()

    def _payload(self, prompt: str, config: GenerationConfig, *, stream: bool) -> dict:
        body: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "num_predict": config.max_tokens,
                "temperature": config.temperature,
                "stop": list(config.stop),
            },
        }
        if self.think is not None:
            body["think"] = self.think
        return body

    @staticmethod
    def _explain_empty(data: dict, config: GenerationConfig) -> str:
        reason = data.get("done_reason")
        if (data.get("thinking") or "") and reason == "length":
            return (
                "Ollama returned no answer: this is a reasoning model and it "
                f"spent its entire {config.max_tokens}-token budget on the "
                "hidden 'thinking' field (done_reason='length'). Raise "
                "max_tokens, or set OLLAMA_THINK=0 to skip reasoning."
            )
        return f"Ollama returned an empty response (done_reason={reason!r})."

    def generate(self, prompt: str, config: GenerationConfig) -> str:
        client = self._ensure_client()
        resp = client.post("/api/generate", json=self._payload(prompt, config, stream=False))
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response") or ""
        if not text:
            # Never hand an agent loop a silent empty string: it would spin.
            raise RuntimeError(self._explain_empty(data, config))
        return text

    def stream(self, prompt: str, config: GenerationConfig) -> Iterator[str]:
        import json

        client = self._ensure_client()
        emitted = False
        last: dict = {}
        with client.stream(
            "POST", "/api/generate", json=self._payload(prompt, config, stream=True)
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                last = chunk
                if chunk.get("response"):
                    emitted = True
                    yield chunk["response"]
        if not emitted:
            raise RuntimeError(self._explain_empty(last, config))
