FROM python:3.12-slim
WORKDIR /app
RUN useradd -u 1000 -m appuser && \
    mkdir -p /app/out && \
    chown -R appuser:appuser /app
COPY --chown=appuser:appuser . /app
USER appuser
CMD ["python3", "runner/scorer.py"]
