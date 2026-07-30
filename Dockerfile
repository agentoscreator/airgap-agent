# airgap-agent — single-container image.
#
# Everything network-dependent happens at BUILD time. At RUN time the
# container is launched with `--network none` and cannot reach anything.
#
#   Primary runtime : llama.cpp (in-process, GGUF, no server)
#   Backup runtime  : Ollama (local server on 127.0.0.1:11434, same container)
#
# Build once (online):   docker build -t airgap-agent .
# Transfer across gap:   docker save airgap-agent | ...  ->  docker load
# Run offline:           see docker-compose.yml or docs/AIRGAP.md

FROM python:3.11-slim AS base

# ---- system deps (build-time network) --------------------------------------
# build-essential + cmake are needed to compile llama-cpp-python wheels;
# curl is used only here, at build time, to fetch the Ollama binary.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---- Ollama (backup runtime), installed at build time ----------------------
# The official installer only writes the binary; it does NOT pull models.
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

# ---- Python deps (build-time network; pinned) ------------------------------
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ---- application code ------------------------------------------------------
COPY airgap_agent/ ./airgap_agent/
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# ---- optional: bake a model for a SEALED distribution ----------------------
# For llama.cpp, drop a GGUF into ./models and uncomment:
#   COPY models/ /models/
#   ENV MODEL_PATH=/models/model.gguf
# For Ollama backup, pull the model into the image at build time:
#   RUN ollama serve & sleep 3 && ollama pull "${OLLAMA_MODEL:-llama3.1}" && pkill ollama
# Leaving these commented keeps the image lean; weights are mounted at runtime.

# ---- runtime configuration -------------------------------------------------
# llamacpp is PRIMARY. Switch to the backup with -e RUNTIME=ollama.
ENV RUNTIME=llamacpp \
    MODEL_PATH=/models/model.gguf \
    OLLAMA_HOST=127.0.0.1 \
    OLLAMA_PORT=11434 \
    PYTHONUNBUFFERED=1

# ---- non-root -------------------------------------------------------------
RUN useradd --create-home --uid 10001 airgap \
    && mkdir -p /models /data \
    && chown -R airgap:airgap /app /models /data
USER airgap

VOLUME ["/models", "/data"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
