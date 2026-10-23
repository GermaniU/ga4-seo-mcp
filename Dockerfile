FROM python:3.12-slim

# uv >= 0.13.4 no longer trusts the distrusted eMudhra root; pinned by digest.
COPY --from=ghcr.io/astral-sh/uv:0.13.4@sha256:9f130421e930bfbdc563c00740466603f8723158e90297d07957c2294640262b /uv /usr/local/bin/uv

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

# The base image ships pip 25.x, whose vendored CA bundle still trusts the distrusted eMudhra
# root. The server never calls pip, but the image should not carry a vulnerable installer:
# replace it with a hash-pinned pip 26.2.2 installed by uv (never by the old pip itself).
RUN echo "pip==26.2.2 --hash=sha256:fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70" > /tmp/pip-requirements.txt \
    && uv pip install --system --no-cache --require-hashes -r /tmp/pip-requirements.txt \
    && rm /tmp/pip-requirements.txt \
    && uv sync --locked --no-editable --extra ads \
    && useradd --system --uid 10001 --create-home --home-dir /home/app app

# Credentials: mount the ADC file or a service account key read-only (e.g. at
# /creds/credentials.json), set GOOGLE_APPLICATION_CREDENTIALS to it, and run with
# --user "$(id -u):$(id -g)" so a 0600 key stays readable.
USER app
EXPOSE 8000

# stdio by default, so `docker run -i --rm <image>` works as an MCP stdio server;
# any extra argument goes straight to the CLI (--toolsets, --enable-writes, --transport ...).
ENTRYPOINT ["ga4-seo-mcp"]
