# airgap-agent

A truly **air-gapped** agent harness. No network access, local-only inference, no telemetry, no phone-home. This is the next evolution of running a base model with no internet connection (Zephyr on the ISS) — now the *harness itself* is airgapped, not just the model.

Architecturally inspired by [Hermes Agent](https://github.com/nousresearch/hermes-agent), but with the **opposite goal**: where Hermes is designed to live everywhere (Telegram, Discord, cloud VMs, serverless) and reach out to many providers, airgap-agent is designed to reach *nothing*. Isolation is the core invariant, not a config flag.

airgap-agent is an independent project — not affiliated with, endorsed by, or derived from Hermes Agent's source code. We share none of their code, icons, or branding; we only borrow ideas and reimplement them. See [NOTICE](NOTICE).

## Design goals

- **No egress, ever.** The harness must be *incapable* of outbound network I/O — not merely configured to avoid it. Isolation is enforced structurally (no HTTP client is importable in the agent core, sandboxed subprocesses run with networking disabled) and is verified by tests.
- **Local-only inference.** Models run on-device via a local runtime (e.g. llama.cpp / vLLM / a local socket). No hosted API providers, no API keys, no OAuth.
- **Deterministic, auditable tool surface.** A small, explicit set of tools that touch only the local filesystem and local compute. Every tool declares whether it performs I/O.
- **Portable state, offline.** Conversation/session state persists locally (SQLite), fully functional with no connectivity.
- **No auto-update, no installer that fetches from the internet.** Everything is vendored or built from a local mirror.

## What we borrow from Hermes (and what we deliberately drop)

| Hermes concept | airgap-agent |
| --- | --- |
| Agent loop / tool-calling core | **Kept** — the loop, tool dispatch, and trajectory handling are the reusable heart. |
| Toolset system | **Kept**, but every tool is audited for network calls; anything that egresses is removed. |
| Local state / session DB (SQLite, FTS search) | **Kept** — works great offline. |
| Provider abstraction (OpenRouter, OpenAI, Nous Portal, ...) | **Replaced** with a single local-inference backend. No remote providers. |
| Messaging gateway (Telegram, Discord, Slack, WhatsApp, Signal, Email) | **Removed** — every one of these is an egress path. |
| Cloud/serverless terminal backends (SSH, Modal, Daytona, Vercel) | **Removed** — only the local backend remains. |
| MCP integration to remote servers | **Removed / local-socket only.** |
| Skills Hub / remote skill install | **Removed** — skills are local files only. |
| curl-pipe-bash installer, auto-update | **Removed** — offline install from a vendored bundle only. |

## Non-goals

- Talking to any remote service.
- Being reachable from outside the host.
- Any form of self-update over a network.

## Repository layout (planned)

```
airgap_agent/
  agent/            # agent loop, tool dispatch, trajectory handling
  inference/        # local-only model backend (no remote providers)
  tools/            # audited, local-only tools (fs, local compute)
  state/            # SQLite session persistence, offline search
  config/           # local config; no secrets, no keys
sandbox/            # network-disabled subprocess execution
tests/
  test_no_egress.py # asserts the harness cannot open a socket
AGENTS.md
SECURITY.md
NOTICE
```

## Status

Early scaffolding. See `SECURITY.md` for the isolation model and `AGENTS.md` for contributor conventions.

## License

Licensed under the Apache License, Version 2.0 — see [LICENSE](LICENSE). Attribution and project lineage are recorded in [NOTICE](NOTICE).
