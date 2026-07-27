FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    git curl make wget xz-utils ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workdir

# Copy project files into the image (not bind-mount)
COPY . /workdir/

# Run build inside the container (toolchain extracted to /workdir, not macOS fs)
RUN bash /workdir/build.sh all

# Default: print the binary path
CMD ["ls", "-lh", "/workdir/sdcard/divinus"]
