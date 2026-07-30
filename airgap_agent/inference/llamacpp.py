"""PRIMARY backend: llama.cpp, in-process.

Loads a local GGUF file and runs inference in-process. There is no server
and no socket of any kind here, which makes this the most airgap-faithful
option: even a compromised process has no network primitive to reach for.

The model path is taken from config (MODEL_PATH). Weights are mounted
read-only at runtime or baked into the image for a sealed distribution;
this backend never downloads anything.
"""

from __future__ import annotations

import os
from typing import Iterator

from .base import GenerationConfig, InferenceBackend


class LlamaCppBackend(InferenceBackend):
    name = "llamacpp"

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path or os.environ.get("MODEL_PATH", "")
        self._llm = None  # lazily constructed so import stays cheap

    def _ensure_loaded(self):
        if self._llm is not None:
            return self._llm
        if not self.model_path or not os.path.exists(self.model_path):
            raise FileNotFoundError(
                "MODEL_PATH does not point at a readable GGUF file: "
                f"{self.model_path!r}. Mount the weights read-only or bake "
                "them into the image; this backend never downloads."
            )
        # Imported lazily; llama_cpp performs no network I/O.
        from llama_cpp import Llama

        self._llm = Llama(
            model_path=self.model_path,
            n_ctx=int(os.environ.get("N_CTX", "4096")),
            verbose=False,
        )
        return self._llm

    def health_check(self) -> None:
        self._ensure_loaded()

    def generate(self, prompt: str, config: GenerationConfig) -> str:
        llm = self._ensure_loaded()
        out = llm(
            prompt,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            stop=list(config.stop) or None,
        )
        return out["choices"][0]["text"]

    def stream(self, prompt: str, config: GenerationConfig) -> Iterator[str]:
        llm = self._ensure_loaded()
        for chunk in llm(
            prompt,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            stop=list(config.stop) or None,
            stream=True,
        ):
            yield chunk["choices"][0]["text"]
