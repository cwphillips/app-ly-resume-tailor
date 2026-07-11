# Minimal self-host image for the Streamlit app.
#
# Build:  docker build -t app-ly .
# Run:    docker run --rm -p 8501:8501 -e ANTHROPIC_API_KEY=sk-ant-... app-ly
#
# PDF/ODT export needs LibreOffice, which is a large layer and is left out by
# default. To enable it, uncomment the apt-get block below and rebuild.

FROM python:3.13-slim

# uv provides fast, reproducible installs from the committed uv.lock.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

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

CMD ["uv", "run", "streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]
