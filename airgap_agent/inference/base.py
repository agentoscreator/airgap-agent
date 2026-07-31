"""Local inference backends for airgap-agent.

The agent core talks to exactly one backend, chosen at startup via config
(RUNTIME=llamacpp | ollama). Both run entirely on-host:

  * llamacpp (PRIMARY): in-process, loads a GGUF file. No sockets at all.
  * ollama   (BACKUP):  talks to a local Ollama server over loopback only
                        (127.0.0.1:11434). Loopback never leaves the host
                        and is unaffected by `--network none`.

The loopback exception is deliberate and narrow. See SECURITY.md: an
inference backend may speak HTTP ONLY to a loopback / unix-socket address,
and the egress test enforces exactly that.
"""

from __future__ import annotations

import abc
import os
from dataclasses import dataclass
from typing import Iterator


@dataclass
class GenerationConfig:
    max_tokens: int = 512
    temperature: float = 0.7
    stop: tuple[str, ...] = ()


class InferenceBackend(abc.ABC):
    """Uniform interface every local backend implements.

    Implementations MUST NOT perform any network I/O to a non-loopback
    address. Keep the surface tiny so it stays auditable.
    """

    name: str

    @abc.abstractmethod
    def generate(self, prompt: str, config: GenerationConfig) -> str:
        """Return a full completion for `prompt`."""

    @abc.abstractmethod
    def stream(self, prompt: str, config: GenerationConfig) -> Iterator[str]:
        """Yield completion tokens/chunks for `prompt`."""

    def health_check(self) -> None:
        """Raise if the backend is not ready. Default: assume ready."""
        return None


def load_backend(runtime: str | None = None) -> InferenceBackend:
    """Factory: pick a backend by name. llamacpp is the default/primary."""
    runtime = (runtime or os.environ.get("RUNTIME") or "llamacpp")
    runtime = runtime.strip().lower()
    if runtime == "llamacpp":
        from .llamacpp import LlamaCppBackend

        return LlamaCppBackend()
    if runtime == "ollama":
        from .ollama import OllamaBackend

        return OllamaBackend()
    raise ValueError(
        f"Unknown RUNTIME {runtime!r}; expected 'llamacpp' or 'ollama'."
    )
