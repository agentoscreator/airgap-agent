"""Local inference backends.

llama.cpp is the primary (in-process) runtime; Ollama is the loopback-only
backup. Select via load_backend(runtime).
"""

from .base import GenerationConfig, InferenceBackend, load_backend

__all__ = ["GenerationConfig", "InferenceBackend", "load_backend"]
