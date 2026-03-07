FROM debian:stable-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates
COPY ./src /app/src
WORKDIR /app
COPY --from=project_root pyproject.toml uv.lock /app/
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN $HOME/.local/bin/uv venv --seed && $HOME/.local/bin/uv sync --group frontend --group prod --no-install-project

# Setup Python cache directory for PostgreSQL SSL
RUN mkdir -p /app/.postgresql && \
    curl -Lo /app/.postgresql/root.crt "https://storage.yandexcloud.net/cloud-certs/CA.pem" && \
    chmod 0600 /app/.postgresql/root.crt



ADD run_app.sh /app/run_app.sh
RUN chmod +x /app/run_app.sh

CMD ["/app/run_app.sh"]
