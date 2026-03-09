FROM python:3.11-slim AS builder
RUN --mount=type=cache,target=/var/lib/apt/lists --mount=type=cache,target=/var/cache/apt \
    apt-get update \
    && apt-get install -y --no-install-recommends \
    curl ca-certificates gcc libc6-dev git-core make

RUN --mount=type=cache,target=/var/lib/astral \
    mkdir -p /var/lib/astral \
    && curl -LsSf https://astral.sh/uv/install.sh > /var/lib/astral/install_uv.sh \
    && sh /var/lib/astral/install_uv.sh

# Setup Python cache directory for PostgreSQL SSL
RUN mkdir -p /app/.postgresql && \
    curl -Lo /app/.postgresql/root.crt "https://storage.yandexcloud.net/cloud-certs/CA.pem" && \
    chmod 0600 /app/.postgresql/root.crt

COPY --from=project_root pyproject.toml uv.lock /app/
COPY ./src /app
WORKDIR /app
RUN --mount=type=cache,sharing=locked,target=/root/.cache/uv \
    $HOME/.local/bin/uv venv --seed --link-mode=copy \
    && $HOME/.local/bin/uv sync --group frontend --group prod --no-install-project

FROM python:3.11-slim
COPY --from=builder /app /app
COPY --from=builder /root/.local/bin/uv /bin/uv
COPY run_app.sh /app
WORKDIR /app
RUN --mount=type=cache,sharing=locked,target=/root/.cache/uv \
    /bin/uv sync --group frontend --group prod --no-install-project
CMD ["/bin/uv","run", "--no-sync", "/app/run_app.sh"]
