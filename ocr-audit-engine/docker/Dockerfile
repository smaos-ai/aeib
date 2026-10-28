FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE /app/
COPY src/ /app/src/

RUN pip install --no-cache-dir -e .

ENTRYPOINT ["ocr-audit"]
CMD ["--help"]
