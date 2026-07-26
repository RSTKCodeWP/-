# Dockerfile for RHFest GitHub Action
ARG PYTHON_VERSION=3.13
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-alpine
ENV UV_LINK_MODE=copy

# Set the working directory
WORKDIR /app

# Add build arguments
ARG RHFEST_VERSION
ENV RHFEST_VERSION=${RHFEST_VERSION}

# Copy project metadata files
COPY pyproject.toml uv.lock ./

# Install dependencies first (before copying source code for caching efficiency)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy RHFest source code
COPY rhfest /app/rhfest

# Install the project itself (so it's recognized as an installed package)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Ensure Python can find installed binaries & packages
ENV PATH="/app/.venv/bin:$PATH"

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []

# Run RHFest validation
CMD ["python", "/app/rhfest/core.py"]
