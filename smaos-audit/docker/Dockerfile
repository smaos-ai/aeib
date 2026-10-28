# smaos-audit: Air-Gapped Zero-Egress Sovereign Audit Container (Moat 4)
# Build: docker build -t smaos-audit -f docker/Dockerfile .
# Run:   docker run --rm --network none -v $(pwd):/workspace:ro smaos-audit --help

FROM python:3.12-slim-bookworm

LABEL maintainer="SMAOS Trust Infrastructure <andrejlo123@gmail.com>"
LABEL org.opencontainers.image.title="smaos-audit"
LABEL org.opencontainers.image.description="Deterministic Agent Settlement & Wire Truth Control Plane"
LABEL org.opencontainers.image.version="1.1.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

# Create non-root user
RUN groupadd -g 10001 smaos && \
    useradd -u 10001 -g smaos -s /bin/sh -m smaos

WORKDIR /app

# Copy application source
COPY core/ /app/core/
COPY protocols/ /app/protocols/
COPY runtime/ /app/runtime/

USER smaos:smaos

ENTRYPOINT ["python3", "-m", "core.detector"]
CMD ["--help"]
