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


class OllamaBackend(InferenceBackend):
    name = "ollama"

    def __init__(self, host: str | None = None, model: str | None = None) -> None:
        self.host = host or os.environ.get("OLLAMA_HOST", "127.0.0.1")
        _assert_loopback(self.host)
        self.port = int(os.environ.get("OLLAMA_PORT", "11434"))
        self.model = model or os.environ.get("OLLAMA_MODEL", "")
        self._base = f"http://{self.host}:{self.port}"
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

    def generate(self, prompt: str, config: GenerationConfig) -> str:
        client = self._ensure_client()
        resp = client.post(
            "/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": config.max_tokens,
                    "temperature": config.temperature,
                    "stop": list(config.stop),
                },
            },
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    def stream(self, prompt: str, config: GenerationConfig) -> Iterator[str]:
        import json

        client = self._ensure_client()
        with client.stream(
            "POST",
            "/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "num_predict": config.max_tokens,
                    "temperature": config.temperature,
                    "stop": list(config.stop),
                },
            },
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("response"):
                    yield chunk["response"]
