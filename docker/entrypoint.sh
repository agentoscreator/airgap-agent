#!/usr/bin/env bash
# Entrypoint for the single airgap-agent container.
#
# llama.cpp (PRIMARY) needs no server: we launch the agent directly.
# Ollama (BACKUP) runs as a local server bound to loopback in THIS
# container; we start it, wait for it, then launch the agent.
#
# Nothing here reaches the network. Ollama is bound to 127.0.0.1 and the
# container is expected to run with `--network none`.

set -euo pipefail

RUNTIME="${RUNTIME:-llamacpp}"
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"

log() { printf '[entrypoint] %s\n' "$*" >&2; }

start_ollama() {
    # Refuse anything that is not loopback — defense in depth against a
    # tampered OLLAMA_HOST turning this into an egress path.
    case "${OLLAMA_HOST}" in
        127.0.0.1|::1|localhost) : ;;
        *)
            log "OLLAMA_HOST='${OLLAMA_HOST}' is not loopback. Refusing."
            exit 1
            ;;
    esac

    log "Starting Ollama on ${OLLAMA_HOST}:${OLLAMA_PORT} (loopback only)…"
    OLLAMA_HOST="${OLLAMA_HOST}:${OLLAMA_PORT}" ollama serve &
    OLLAMA_PID=$!

    # Wait for readiness without shelling out to a network client.
    for _ in $(seq 1 30); do
        if bash -c "exec 3<>/dev/tcp/${OLLAMA_HOST}/${OLLAMA_PORT}" 2>/dev/null; then
            log "Ollama is ready."
            return 0
        fi
        sleep 1
    done

    log "Ollama did not become ready in time."
    kill "${OLLAMA_PID}" 2>/dev/null || true
    exit 1
}

case "${RUNTIME}" in
    llamacpp)
        log "Runtime: llama.cpp (primary, in-process). No server."
        ;;
    ollama)
        log "Runtime: ollama (backup)."
        start_ollama
        ;;
    *)
        log "Unknown RUNTIME='${RUNTIME}'. Expected 'llamacpp' or 'ollama'."
        exit 1
        ;;
esac

log "Launching agent…"
exec python -m airgap_agent "$@"
