FROM debian:stable-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gcc libc6-dev
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
# Setup Python cache directory for PostgreSQL SSL
RUN mkdir -p /app/.postgresql && \
    curl -Lo /app/.postgresql/root.crt "https://storage.yandexcloud.net/cloud-certs/CA.pem" && \
    chmod 0600 /app/.postgresql/root.crt

COPY --from=project_root pyproject.toml uv.lock /app/
COPY ./src /app/src
WORKDIR /app
RUN $HOME/.local/bin/uv venv --seed && $HOME/.local/bin/uv sync --group frontend --group prod --no-install-project

ADD run_app.sh /app/run_app.sh
RUN chmod +x /app/run_app.sh

CMD ["/root/.local/bin/uv","run", "--no-sync", "/app/run_app.sh"]
