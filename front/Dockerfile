FROM python:3.11

# Install Poetry
RUN pip install --no-cache-dir poetry

WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies (doesn't install the project itself)
RUN poetry install --no-dev --no-root --no-directory


# Setup Python cache directory for PostgreSQL SSL
RUN mkdir -p /app/.postgresql && \
    wget "https://storage.yandexcloud.net/cloud-certs/CA.pem" -O /app/.postgresql/root.crt && \
    chmod 0600 /app/.postgresql/root.crt

ADD ./src /app

ADD run_app.sh /app/run_app.sh
RUN chmod +x /app/run_app.sh

CMD ["/app/run_app.sh"]
