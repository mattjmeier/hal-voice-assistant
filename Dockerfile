FROM ghcr.io/prefix-dev/pixi:0.70.2 AS build

# PyAudio hard-codes system include paths, so build it with the matching system toolchain.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml pixi.lock README.md ./
COPY hal ./hal
RUN pixi install --locked --environment default

COPY app.py ./
COPY models ./models
COPY scripts ./scripts

FROM debian:bookworm-slim AS runtime

LABEL org.opencontainers.image.source="https://github.com/mattjmeier/hal-voice-assistant"
LABEL org.opencontainers.image.description="HAL 9000 voice satellite for Raspberry Pi and Linux SBCs"

RUN apt-get update \
    && apt-get install --yes --no-install-recommends alsa-utils ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=build /app /app

ENV PATH="/app/.pixi/envs/default/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["hal-voice-assistant"]
