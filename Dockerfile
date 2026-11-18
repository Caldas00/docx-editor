# Self-contained image: the app, LibreOffice (to lay pages out exactly) and fonts with the
# same metrics as Word's defaults, so nothing needs to be installed on the host.
#   docker build -t docx-agent .
#   docker run --rm -p 8000:8000 --env-file .env docx-agent     # then open http://localhost:8000
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# libreoffice-writer-nogui: the headless layout engine behind the "Document" view
# fonts: Carlito = Calibri, Caladea = Cambria, Liberation = Arial / Times New Roman / Courier New
RUN apt-get update \
 && apt-get install -y --no-install-recommends libreoffice-writer-nogui \
    fonts-crosextra-carlito fonts-crosextra-caladea fonts-liberation fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY samples ./samples
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "docx-agent", "serve", "--host", "0.0.0.0", "--port", "8000"]
