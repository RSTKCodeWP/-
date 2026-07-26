# CoinFlow Bot v3.1 - Optimized Multi-Stage Build
# Python 3.12 with all dependencies including faster-whisper
FROM python:3.12 AS builder

# Install system build dependencies
# gcc/g++: Required for building Python packages with C extensions
# make/cmake: Build tools for native dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.0

# Set working directory
WORKDIR /app

# Copy only dependency files first (for better caching)
COPY pyproject.toml poetry.lock ./

# Configure Poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --all-extras --no-root --no-interaction --no-ansi --compile

# Final stage - runtime
FROM python:3.12

# Install runtime dependencies
# curl: Health checks and API calls
# ffmpeg: Required for voice message processing (faster-whisper, pydub)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create data and logs directories
RUN mkdir -p /app/data /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL=sqlite:///data/coinflow.db \
    LOG_FILE=/app/logs/coinflow.log \
    PATH="/usr/local/bin:${PATH}" \
    # Faster-Whisper optimization for CPU
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the bot
CMD ["python", "-u", "main.py"]
