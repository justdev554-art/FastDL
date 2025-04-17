ARG PYTHON_VERSION=3.13

# Install uv
FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Change the working directory to the `app` directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --group docker --frozen --no-install-project --no-editable

# Copy the project into the intermediate image
ADD . /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --group docker --frozen --no-editable


FROM python:${PYTHON_VERSION}-slim

RUN set -eux; \
    apt-get update; \
    apt-get install --assume-yes mime-support; \
    rm -rf /var/lib/apt/lists/*

# Copy the environment, but not the source code
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Run the application
CMD [ "/app/.venv/bin/uvicorn", "fastdl:application" ]

ENV UVICORN_ACCESS_LOG=0
ENV UVICORN_SERVER_HEADER=0

ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=8000
