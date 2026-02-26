FROM python:3.11

COPY ./src /app/src
WORKDIR /app
RUN pip install --upgrade --no-cache-dir pip uv
COPY --from=project_root pyproject.toml uv.lock /app/
RUN uv sync --group frontend --group backend --group prod

# Setup Python cache directory for PostgreSQL SSL
RUN mkdir -p /app/.postgresql && \
    wget "https://storage.yandexcloud.net/cloud-certs/CA.pem" -O /app/.postgresql/root.crt && \
    chmod 0600 /app/.postgresql/root.crt



ADD run_app.sh /app/run_app.sh
RUN chmod +x /app/run_app.sh

CMD ["/app/run_app.sh"]
