FROM denoland/deno:2.2.1

WORKDIR /app

# Copy source files and vendored dependencies
COPY deno.json .
COPY main.ts .
COPY db.ts .
COPY vendor/ vendor/

# Create data directories
RUN mkdir -p /data/photos

ENV DB_PATH=/data/fpv-inventory.db
ENV PHOTOS_DIR=/data/photos
ENV PORT=8000

EXPOSE 8000

# Run with only the permissions needed
CMD ["deno", "run", "--allow-net", "--allow-read=/app,/data", "--allow-write=/data", "--allow-env", "main.ts"]
