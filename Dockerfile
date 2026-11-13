# syntax=docker/dockerfile:1
FROM python:3.15-slim-trixie AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

FROM base AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock .python-version README.md LICENSE ./
RUN uv sync --locked --no-dev --no-install-project
COPY src/ src/
RUN uv sync --locked --no-dev --no-editable

FROM build AS test
COPY tests/ tests/
RUN uv sync --locked --no-editable
CMD ["uv", "run", "--locked", "--no-sync", "pytest", "--cov=syllable_shaker", "--junitxml=output/testresults.xml", "-q"]

FROM base AS runtime
RUN groupadd --system app && useradd --system --gid app --home-dir /app app
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn --workers 2 --bind \"0.0.0.0:${PORT:-8000}\" syllable_shaker:app"]
