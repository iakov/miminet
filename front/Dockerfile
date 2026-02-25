FROM python:3.11
#RUN echo ${PWD} && ls -lR
COPY ./src /app/src
#RUN echo ${PWD} && ls -lR
#COPY ../pyproject.toml ../poetry.lock /app/

WORKDIR /app

RUN pip install --upgrade --no-cache-dir pip poetry
COPY --from=project_root pyproject.toml poetry.lock /app/
RUN poetry install --no-root --no-directory --without dev

# Setup Python cache directory for PostgreSQL SSL
RUN mkdir -p /app/.postgresql && \
    wget "https://storage.yandexcloud.net/cloud-certs/CA.pem" -O /app/.postgresql/root.crt && \
    chmod 0600 /app/.postgresql/root.crt



ADD run_app.sh /app/run_app.sh
RUN chmod +x /app/run_app.sh

CMD ["/app/run_app.sh"]
