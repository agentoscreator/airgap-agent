"""Entry point: `python -m airgap_agent`.

Invoked by the container entrypoint. Selects the local inference backend
(llamacpp primary, ollama backup) and starts an offline REPL. The agent
loop itself lands in airgap_agent/agent/ next.
"""

from __future__ import annotations

import os
import sys

from .inference import GenerationConfig, load_backend


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    runtime = os.environ.get("RUNTIME", "llamacpp")
    try:
        backend = load_backend(runtime)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"airgap-agent — runtime={backend.name} (offline)", file=sys.stderr)

    try:
        backend.health_check()
    except Exception as exc:  # noqa: BLE001
        print(f"error: backend not ready: {exc}", file=sys.stderr)
        return 1

    config = GenerationConfig()

    # One-shot mode if a prompt was passed as arguments.
    if argv:
        print(backend.generate(" ".join(argv), config))
        return 0

    # Otherwise, a minimal offline REPL.
    print("Type a prompt, or Ctrl-D to exit.", file=sys.stderr)
    while True:
        try:
            prompt = input("> ")
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return 0
        if not prompt.strip():
            continue
        for chunk in backend.stream(prompt, config):
            print(chunk, end="", flush=True)
        print()


if __name__ == "__main__":
    raise SystemExit(main())
