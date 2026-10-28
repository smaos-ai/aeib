# SMAOS / AEIB Zero-Egress Settlement Verification Engine (v0.1.0)
FROM python:3.11-slim

LABEL maintainer="SovereignNexus <andrii@sovereignnexus.org>"
LABEL description="Air-gapped settlement fuzzer & wire-truth verifier for autonomous AI agents"

WORKDIR /app

# Ensure non-root execution
RUN groupadd -g 1000 smaos && useradd -u 1000 -g smaos -m smaos

# Copy application files
COPY run.py demo_launcher.py entrypoint.sh /app/
COPY docs/ /app/docs/
COPY fixtures/ /app/fixtures/

RUN mkdir -p /app/audit_out && chown -R smaos:smaos /app

USER smaos

EXPOSE 8765

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEMO_MODE=live

ENTRYPOINT ["/app/entrypoint.sh"]
