FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

# The MCP Registry verifies image ownership with this label: it must match "name" in server.json.
LABEL io.modelcontextprotocol.server.name="io.github.GermaniU/ga4-seo-mcp"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    # Only used with --transport streamable-http: inside the container the server has to listen
    # on every interface for port mapping to work. Publish it on the host's loopback only
    # (-p 127.0.0.1:8000:8000) and set MCP_AUTH_TOKEN.
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src

RUN uv sync --locked --no-editable --extra ads \
    && useradd --system --uid 10001 --create-home --home-dir /home/app app

# ADC lives in ~/.config/gcloud: mount yours read-only at /home/app/.config/gcloud,
# or mount a service account key and set GOOGLE_APPLICATION_CREDENTIALS.
USER app
EXPOSE 8000

# stdio by default, so `docker run -i --rm <image>` works as an MCP stdio server;
# any extra argument goes straight to the CLI (--toolsets, --enable-writes, --transport ...).
ENTRYPOINT ["ga4-seo-mcp"]
