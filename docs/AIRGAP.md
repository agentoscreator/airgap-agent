# Airgap deployment

airgap-agent ships as a **single Docker container**. The whole design splits
cleanly in two: everything network-dependent happens **once, at build time**;
at **run time the container has no network at all**.

- **Primary runtime:** llama.cpp, in-process, loads a local GGUF. No server, no sockets.
- **Backup runtime:** Ollama, running as a local server on `127.0.0.1:11434` **inside the same container**. Loopback only — it never leaves the host.

## 1. Build once, on a connected machine

```
docker build -t airgap-agent .
```

This is the only step that touches the network: it pulls the base image,
installs pinned Python deps, and installs the Ollama binary. No model
weights are downloaded here (weights are mounted at runtime by default).

## 2. Carry the image across the air gap

```
docker save airgap-agent:latest | gzip > airgap-agent.tar.gz
# move airgap-agent.tar.gz onto the isolated host (USB, one-way diode, etc.)
gunzip -c airgap-agent.tar.gz | docker load
```

Also copy your GGUF weights onto the isolated host, e.g. into `./models/model.gguf`.

## 3. Run offline

Preferred (compose already sets `network_mode: none` and mounts weights read-only):

```
docker compose up
```

Or with plain `docker run` — note the explicit `--network none`:

```
docker run --rm -it \
  --network none \
  --read-only --tmpfs /tmp \
  --cap-drop ALL --security-opt no-new-privileges \
  -v "$PWD/models:/models:ro" \
  -v airgap-data:/data \
  airgap-agent:latest
```

`--network none` removes every network interface from the container. Because
llama.cpp is in-process and Ollama is bound to loopback, the agent still works
with zero connectivity.

## Switching to the Ollama backup

Set `RUNTIME=ollama` and make sure the model was baked into the image at build
time (Ollama pulls are egress events and are **build-time only**):

```
# in the Dockerfile, before going offline:
#   RUN ollama serve & sleep 3 && ollama pull llama3.1 && pkill ollama
docker compose run -e RUNTIME=ollama agent
```

The entrypoint refuses any non-loopback `OLLAMA_HOST`, so a misconfiguration
cannot turn the backup into an egress path.

## Sealed distribution (weights baked in)

For a single self-contained artifact with nothing to mount, uncomment the
`COPY models/` lines in the `Dockerfile`, place your GGUF under `./models`,
and rebuild. The resulting image is larger but is a complete, one-file
airgap package.

## Verifying isolation

- `tests/test_no_egress.py` blocks non-loopback sockets and asserts the agent loop never egresses.
- Run the container with `--network none` (the default here) as the ultimate enforcement.
- CI is intended to run the suite inside a network-disabled container. See SECURITY.md.
