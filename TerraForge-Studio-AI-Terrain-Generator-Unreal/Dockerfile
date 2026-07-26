# Multi-stage build for TerraForge Studio
# Production-optimized Docker image

# Stage 1: Build frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy frontend package files
COPY frontend-new/package*.json ./
RUN npm ci --only=production

# Copy frontend source and build
COPY frontend-new/ ./
RUN npm run build

# Stage 2: Build backend
FROM python:3.13-slim AS backend

WORKDIR /app

# Install system dependencies for GDAL and other tools
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry for Python dependency management
RUN pip install --no-cache-dir poetry==1.7.1

# Copy Python dependency files
COPY pyproject.toml poetry.lock ./

# Configure Poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY realworldmapgen/ ./realworldmapgen/

# Copy built frontend from previous stage
COPY --from=frontend-builder /app/frontend/dist ./static

# Create directories for cache and output
RUN mkdir -p /app/cache /app/output

# Create non-root user for security
RUN useradd -m -u 1000 terraforge && \
    chown -R terraforge:terraforge /app

USER terraforge

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

# Run the application
CMD ["uvicorn", "realworldmapgen.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

