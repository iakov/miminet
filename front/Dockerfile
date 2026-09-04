ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}

WORKDIR /app
RUN pip install setuptools --upgrade
RUN pip install wheel uwsgi uv
COPY pyproject.toml uv.lock /app/
COPY back/pyproject.toml /app/back/pyproject.toml
COPY front/pyproject.toml /app/front/pyproject.toml
RUN uv sync --frozen --no-dev --project front
ENV PATH="/app/.venv/bin:$PATH"

# W5 fork-experiment (NEVER merge): Selenium-e2e branch coverage of front/src.
# coverage 7.16's a1_coverage.pth auto-starts a tracer in every interpreter
# that uses /app/.venv when COVERAGE_PROCESS_START points at /app/.coveragerc,
# so each uwsgi worker and celery child is measured. w5_cov.pth imports
# w5_cov_flush.py, which registers an at-fork child hook that periodically
# saves coverage data (needed because celery prefork children exit via
# os._exit and never run atexit). Data lands in the bind-mounted /app/.covout.
RUN /app/.venv/bin/pip install --no-cache-dir "coverage==7.16.0"
COPY front/w5/cov_flush.py /app/.venv/lib/python3.12/site-packages/w5_cov_flush.py
COPY front/w5/w5_cov.pth /app/.venv/lib/python3.12/site-packages/w5_cov.pth
COPY front/w5/coverage.rc /app/.coveragerc
RUN mkdir -p /app/.postgresql && \
    wget "https://storage.yandexcloud.net/cloud-certs/CA.pem" -O /app/.postgresql/root.crt && \
    chmod 0600 /app/.postgresql/root.crt

COPY front/src /app

COPY front/run_app.sh /app/run_app.sh
RUN chmod +x /app/run_app.sh

CMD ["/app/run_app.sh"]
