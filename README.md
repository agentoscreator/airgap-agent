# airgap-agent

A truly **air-gapped** agent harness. No network access, local-only inference, no telemetry, no phone-home. This is the next evolution of running a base model with no internet connection (Zephyr on the ISS) — now the *harness itself* is airgapped, not just the model.

Architecturally inspired by [Hermes Agent](https://github.com/nousresearch/hermes-agent), but with the **opposite goal**: where Hermes is designed to live everywhere (Telegram, Discord, cloud VMs, serverless) and reach out to many providers, airgap-agent is designed to reach *nothing*. Isolation is the core invariant, not a config flag.

airgap-agent is an independent project — not affiliated with, endorsed by, or derived from Hermes Agent's source code. We share none of their code, icons, or branding; we only borrow ideas and reimplement them. See [NOTICE](NOTICE).

## Deploy

Two supported paths: a **container** (recommended for real airgapped hosts — one artifact to carry across the gap) or a **direct host install** (best for development).

### Option A — Docker, single container

Build once on a connected machine, then run with no network at all:

```
docker build -t airgap-agent .
docker compose up          # compose already sets network_mode: none
```

To move it onto an isolated host:

```
docker save airgap-agent:latest | gzip > airgap-agent.tar.gz
# transfer the tarball, then on the offline host:
gunzip -c airgap-agent.tar.gz | docker load
```

Full walkthrough, including `docker run` flags and sealed (weights-baked-in) builds: **[docs/AIRGAP.md](docs/AIRGAP.md)**.

### Option B — install on the host

One line from a checkout, using [uv](https://github.com/astral-sh/uv) (installs the `airgap-agent` command onto your PATH in its own isolated environment):

```
git clone https://github.com/agentoscreator/airgap-agent && cd airgap-agent
uv tool install ".[llamacpp]"
```

Or with plain pip in a virtualenv:

```
python -m venv .venv && source .venv/bin/activate
pip install ".[llamacpp]"
```

The runtimes are **optional extras**, so the core install pulls in zero third-party packages:

| Extra | Installs | Use |
| --- | --- | --- |
| `.[llamacpp]` | `llama-cpp-python` | **Primary.** In-process, no sockets. |
| `.[ollama]` | `httpx` | Backup. Loopback-only client. |
| `.[all]` | both | Both runtimes available. |

Because `httpx` ships only with the `ollama` extra, a default `.[llamacpp]` install has **no HTTP client in the environment at all**.

### Get a model

Nothing is ever downloaded at runtime. Fetch a GGUF on a connected machine, move it across the gap, and point `MODEL_PATH` at it:

```
mkdir -p models   # place your .gguf here, e.g. models/model.gguf
export MODEL_PATH="$PWD/models/model.gguf"
```

### Run

```
airgap-agent                       # interactive offline REPL
airgap-agent "summarize this log"  # one-shot prompt
```

Switch to the Ollama backup (requires a local Ollama server on loopback, and a model already pulled at build time):

```
RUNTIME=ollama OLLAMA_MODEL=llama3.1 airgap-agent
```

### Fully offline install

For a host that never touches the network, build a wheelhouse on a connected machine first:

```
pip wheel ".[llamacpp]" -w wheelhouse    # connected machine
# carry ./wheelhouse across the gap, then:
pip install --no-index --find-links=wheelhouse ".[llamacpp]"
```

The wheelhouse must be built on the **same platform and Python version** as the target host, since `llama-cpp-python` compiles native code.

### Why there is no `curl | bash` one-liner

Piping a remote script into a shell is the exact pattern we removed from the Hermes-inspired design. It requires trusting a network fetch at install time and gives you no chance to audit what runs. For a project whose entire premise is isolation, that tradeoff is wrong — so installation is always from a checkout you can read, or from an image you built yourself.

We also don't publish to PyPI. If you'd rather install from an index, build the wheel yourself (`pip wheel .`) and host it wherever you already trust.

## Design goals

- **No egress, ever.** The harness must be *incapable* of outbound network I/O — not merely configured to avoid it. Isolation is enforced structurally (no HTTP client is importable in the agent core, sandboxed subprocesses run with networking disabled) and is verified by tests.
- **Local-only inference.** Models run on-device. llama.cpp is primary (in-process); a loopback-only Ollama backend is the backup. No hosted API providers, no API keys, no OAuth.
- **Deterministic, auditable tool surface.** A small, explicit set of tools that touch only the local filesystem and local compute. Every tool declares whether it performs I/O.
- **Portable state, offline.** Conversation/session state persists locally (SQLite), fully functional with no connectivity.
- **No auto-update, no installer that fetches from the internet.** Everything is vendored or built from a local mirror.

## What we borrow from Hermes (and what we deliberately drop)

| Hermes concept | airgap-agent |
| --- | --- |
| Agent loop / tool-calling core | **Kept** — the loop, tool dispatch, and trajectory handling are the reusable heart. |
| Toolset system | **Kept**, but every tool is audited for network calls; anything that egresses is removed. |
| Local state / session DB (SQLite, FTS search) | **Kept** — works great offline. |
| Provider abstraction (OpenRouter, OpenAI, Nous Portal, ...) | **Replaced** with local-only backends. No remote providers. |
| Messaging gateway (Telegram, Discord, Slack, WhatsApp, Signal, Email) | **Removed** — every one of these is an egress path. |
| Cloud/serverless terminal backends (SSH, Modal, Daytona, Vercel) | **Removed** — only the local backend remains. |
| MCP integration to remote servers | **Removed / local-socket only.** |
| Skills Hub / remote skill install | **Removed** — skills are local files only. |
| curl-pipe-bash installer, auto-update | **Removed** — offline install from a checkout or vendored bundle only. |

## Non-goals

- Talking to any remote service.
- Being reachable from outside the host.
- Any form of self-update over a network.

## Repository layout

```
airgap_agent/
  __main__.py       # entry point: python -m airgap_agent / airgap-agent
  inference/        # local-only backends
    base.py         #   backend interface + factory
    llamacpp.py     #   PRIMARY: in-process, GGUF, no sockets
    ollama.py       #   BACKUP: loopback-only client
  agent/            # agent loop, tool dispatch (planned)
  tools/            # audited, local-only tools (planned)
  state/            # SQLite session persistence (planned)
docker/
  entrypoint.sh     # selects runtime; starts Ollama on loopback if needed
docs/AIRGAP.md      # build-online-once / run-offline workflow
tests/
  test_no_egress.py # allows loopback, blocks all external connections
Dockerfile
docker-compose.yml  # network_mode: none, read-only rootfs
pyproject.toml
```

## Status

Early scaffolding: the inference layer, container, and isolation test exist; the agent loop and tool system are next. See `SECURITY.md` for the isolation model and `AGENTS.md` for contributor conventions.

## License

Licensed under the Apache License, Version 2.0 — see [LICENSE](LICENSE). Attribution and project lineage are recorded in [NOTICE](NOTICE).
