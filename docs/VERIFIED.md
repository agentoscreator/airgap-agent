# Verification record

This file records what has actually been **executed**, on what hardware, and
what has not. It exists because "air-gapped" is a security claim, and a
security claim that has never been run is just a wish.

Update this file in the same change as anything touching the isolation model.

## Last verified

- **Date:** 2026-07-31
- **Host:** NVIDIA Jetson Orin (`aarch64`), JetPack R36 revision 4.7
- **OS / kernel:** Ubuntu 22.04.5 LTS, Linux 5.15.148-tegra
- **Python:** 3.10.12 (system interpreter)
- **Ollama:** 0.30.8
- **Model:** a locally present 35B GGUF served by Ollama

## Verified working

| What | How | Result |
| --- | --- | --- |
| Package parses | `python3 -m compileall airgap_agent tests` | pass |
| Test suite | `pytest tests/ -q` | 6 passed, 1 skipped |
| External egress blocked | raw `socket.connect` and `httpx.get` to a non-loopback IP | `EgressAttempt` raised |
| Loopback permitted | `socket.create_connection` to a closed loopback port | `ConnectionRefusedError`, *not* `EgressAttempt` |
| httpx over loopback | `httpx.get` to a closed loopback port under the guard | `httpx.ConnectError`, *not* `EgressAttempt` |
| Backend selection | `load_backend()` with `RUNTIME=ollama` | returns the Ollama backend |
| Ollama health check | `GET /api/tags` over loopback | HTTP 200 |
| Ollama `generate()` | prompt in, completion out, `OLLAMA_THINK=0` | returned the expected word |
| Ollama `stream()` | streamed token iterator | returned a complete multi-line answer |
| Reasoning-model truncation | 16-token budget on a reasoning model | raises `RuntimeError` naming the remedy, instead of silently returning `""` |

## NOT verified

Nothing in this list has ever been executed. Treat it as untested.

- **The llama.cpp backend.** This is the *primary* runtime and it has never
  run. There is no prebuilt `llama-cpp-python` wheel for `aarch64`, and
  building from the sdist on this host failed while installing its build
  dependencies. It needs `cmake` and a C++ toolchain, neither of which is in a
  stock JetPack image. See the README prerequisites.
- **The container.** `Dockerfile`, `docker/entrypoint.sh` and
  `docker-compose.yml` have never been built or run. Two known suspects:
  `read_only: true` conflicts with Ollama's need for a writable state
  directory, and the `curl | sh` Ollama install step is unreliable on
  `python:*-slim` images.
- **`docker run --network none`** as an end-to-end path.
- **The agent loop, tool dispatch, session state and sandbox.** These do not
  exist yet. The skipped test in `tests/test_no_egress.py` is the placeholder.
- **Any real `pip install` of this package.** Installation has so far only
  been exercised as a source checkout on `PYTHONPATH`.

## How to reproduce

```
git clone https://github.com/agentoscreator/airgap-agent && cd airgap-agent
pip install pytest httpx
python3 -m pytest tests/ -v
```

The egress tests are hermetic: they need no network and no model. They bind a
loopback port, release it, and assert on the resulting connection error, so
they distinguish "the guard blocked this" from "nothing was listening".
