# Security & Isolation Model

airgap-agent's single most important property is that it **cannot reach the outside world**. This document describes how that is enforced and how to verify it.

> **Implementation status.** This document describes the *intended* isolation
> model. Several invariants below are not yet enforced by code: there is no
> sandbox, no import contract, and no CI. The egress guard tests in
> `tests/test_no_egress.py` are the only part currently exercised. See
> [`docs/VERIFIED.md`](docs/VERIFIED.md) for what has actually been run.

## Threat model

The harness runs untrusted model output and executes tools on behalf of a language model. We assume the model may attempt (or be manipulated into attempting) to exfiltrate data or fetch remote content. The design goal is that even a fully compromised agent loop has **no available egress path**.

## Isolation invariants

1. **No external network client in the core.** The agent core (`airgap_agent/agent`, `airgap_agent/tools`) must not import any HTTP/socket client library for external use. This is enforced by an import-linter contract and a runtime test.
2. **Local inference only.**
   - The **primary** backend (llama.cpp) runs **in-process** and opens no sockets at all.
   - The **backup** backend (Ollama) may speak HTTP **only to a loopback address** (`127.0.0.1` / `::1` / `localhost`) or a UNIX domain socket. This is the one deliberate, narrow exception to "no HTTP client," and it is safe because loopback traffic never leaves the host and is unaffected by `--network none`. The Ollama backend refuses to construct a client for any non-loopback host.
3. **Sandboxed tool execution.** Any tool that spawns a subprocess runs it with networking disabled (e.g. `unshare --net`, a seccomp filter denying `socket(2)`, or an equivalent OS mechanism).
4. **No secrets, no credentials.** There are no API keys, tokens, or provider configs anywhere in the tree. A CI check greps for common credential patterns and fails the build if any appear.
5. **Offline build & install.** Dependencies are pinned and installed at build time; the runtime container has no network. Model weights are mounted read-only or baked in — never downloaded at runtime. For the Ollama backup, models are pulled **at build time only** (a pull is an egress event).

## Container isolation

airgap-agent deploys as a single Docker container:

- It is run with **`--network none`**, which removes every network interface. Because the primary backend is in-process and the backup binds to loopback, the agent works fully offline.
- The root filesystem is **read-only** with a writable `/data` volume for state and a `tmpfs` for `/tmp`.
- It runs as a **non-root** user, with `--cap-drop ALL` and `--security-opt no-new-privileges`.
- Build online once, `docker save` the image, carry it across the gap, `docker load`, run offline. See `docs/AIRGAP.md`.

## Verification

- `tests/test_no_egress.py` blocks socket creation to **non-loopback** addresses and asserts that importing and running the full agent loop never attempts an external connection. Connections to `127.0.0.1` / `::1` and UNIX sockets are permitted (that is the sanctioned inference path); everything else raises.
- An import-linter (or equivalent) contract asserts the core packages have no dependency on external networking libraries.
- CI runs the whole suite inside a network-disabled container as a belt-and-suspenders check.

## Reporting

Because the harness is meant to run fully offline, there is no online reporting channel. File issues in the local tracker of your deployment. Do **not** add any mechanism that transmits crash/telemetry data off-host.
