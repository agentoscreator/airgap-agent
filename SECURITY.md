# Security & Isolation Model

airgap-agent's single most important property is that it **cannot reach the outside world**. This document describes how that is enforced and how to verify it.

## Threat model

The harness runs untrusted model output and executes tools on behalf of a language model. We assume the model may attempt (or be manipulated into attempting) to exfiltrate data or fetch remote content. The design goal is that even a fully compromised agent loop has **no available egress path**.

## Isolation invariants

1. **No network client in the core.** The agent core (`airgap_agent/agent`, `airgap_agent/inference`, `airgap_agent/tools`) must not import any HTTP/socket client library. This is enforced by an import-linter contract and a runtime test.
2. **Local inference only.** The inference backend talks to a model over a local, in-process runtime or a UNIX domain socket bound to the loopback filesystem — never a TCP endpoint.
3. **Sandboxed tool execution.** Any tool that spawns a subprocess runs it in a namespace/sandbox with networking disabled (e.g. `unshare --net`, a seccomp filter denying `socket(2)`, or an equivalent OS mechanism).
4. **No secrets, no credentials.** There are no API keys, tokens, or provider configs anywhere in the tree. A CI check greps for common credential patterns and fails the build if any appear.
5. **Offline build & install.** Dependencies are vendored / installed from a local mirror. No build step performs a network fetch.

## Verification

- `tests/test_no_egress.py` monkeypatches / blocks `socket.socket` and asserts that importing and running the full agent loop never attempts to open a connection.
- An import-linter (or equivalent) contract asserts the core packages have no dependency on networking libraries.
- CI runs the whole suite inside a network-disabled container as a belt-and-suspenders check.

## Reporting

Because the harness is meant to run fully offline, there is no online reporting channel. File issues in the local tracker of your deployment. Do **not** add any mechanism that transmits crash/telemetry data off-host.
