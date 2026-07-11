# Minimal self-host image for the Streamlit app.
#
# Build:  docker build -t app-ly .
# Run:    docker run --rm -p 8501:8501 -e ANTHROPIC_API_KEY=sk-ant-... app-ly
#
# PDF/ODT export needs LibreOffice, which is a large layer and is left out by
# default. To enable it, uncomment the apt-get block below and rebuild.

FROM python:3.13-slim

# uv provides fast, reproducible installs from the committed uv.lock. Pin the uv
# version so the build stays reproducible (bump deliberately).
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /bin/

# --- Optional: LibreOffice for PDF/ODT export (large; disabled by default) ---
# RUN apt-get update \
#     && apt-get install -y --no-install-recommends libreoffice \
#     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better layer caching. Only the lockfile and
# project metadata are needed, so app code changes don't bust this layer.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the application and finish the install.
COPY . .
RUN uv sync --frozen --no-dev

# ANTHROPIC_API_KEY is supplied at run time via `docker run -e ...`.
EXPOSE 8501

# Local-first tool: opt out of Streamlit's usage telemetry.
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# --frozen --no-sync: deps are already installed above, so skip uv's implicit
# resolution/sync at startup for a faster, deterministic launch.
CMD ["uv", "run", "--frozen", "--no-sync", "streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]
