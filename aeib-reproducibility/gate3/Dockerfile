FROM eclipse-temurin:21-jdk-jammy

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY aeib-native-runtime/ /app/aeib-native-runtime/
COPY aeib-reproducibility/ /app/aeib-reproducibility/

RUN chmod +x /app/aeib-reproducibility/gate3/reproduce.sh

ENTRYPOINT ["/app/aeib-reproducibility/gate3/reproduce.sh"]
