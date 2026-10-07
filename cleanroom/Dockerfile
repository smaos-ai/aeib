# Clean-Room Verification Protocol (CRVP) Isolated Dockerfile
# Explicitly isolates production code from test suites and benchmarks
FROM python:3.11-slim

# Install only the absolute minimum runtime cryptographic dependency
RUN pip install --no-cache-dir cryptography

WORKDIR /app

# Copy ONLY production source and cleanroom verifier
# Tests, benchmarks, and fixtures are deliberately excluded
COPY src/ /app/src/
COPY cleanroom/ /app/cleanroom/

ENV PYTHONPATH="/app/src:/app"

# Execute clean-room verification on container start
ENTRYPOINT ["python3", "/app/cleanroom/verify_from_scratch.py"]
