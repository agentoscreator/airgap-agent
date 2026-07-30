# AGENTS.md — contributor & agent conventions

This file describes conventions for both human contributors and any coding agent working in this repo.

## The one rule that overrides everything

**Never introduce an egress path.** No HTTP clients, no sockets to remote hosts, no DNS lookups, no "just fetch this one thing" convenience. If a change makes the harness capable of talking to the network, it is wrong by definition — this project's entire reason to exist is that it cannot. See `SECURITY.md`.

## Project structure

- `airgap_agent/agent/` — the agent loop, tool dispatch, and trajectory handling. Borrowed in spirit from Hermes Agent's loop, but with all remote hooks removed.
- `airgap_agent/inference/` — the local model backend. In-process or loopback-socket runtime only.
- `airgap_agent/tools/` — local-only tools. Each tool module must declare an `IO_PROFILE` describing what it touches (filesystem paths, subprocess, etc.). No tool may open a network connection.
- `airgap_agent/state/` — SQLite-backed session persistence and offline full-text search.
- `airgap_agent/config/` — local configuration. No secrets. No provider keys.
- `sandbox/` — helpers that run subprocesses with networking disabled.
- `tests/` — including `test_no_egress.py`, the canonical isolation test.

## Conventions

- Python 3.11+. Keep the core dependency-light so the offline vendored bundle stays small.
- Every new tool ships with a test and an `IO_PROFILE`.
- Prefer the standard library. Any third-party dependency must be vendorable and must not itself open network connections at import time.
- Run the full suite (including the egress test) before committing.

## What this project deliberately does not have

- Messaging gateways, cloud/serverless backends, remote MCP servers, remote skill hubs, auto-update, telemetry, or hosted model providers. If you find yourself wanting one of these, you are working on the wrong project.
