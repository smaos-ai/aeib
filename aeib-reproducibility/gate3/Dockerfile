FROM eclipse-temurin:21-jdk-jammy

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    python3 \
    python3-cryptography \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY aeib-native-runtime/ /app/aeib-native-runtime/
COPY aeib-reproducibility/ /app/aeib-reproducibility/
COPY benchmarks/jvm_native_diff_engine.py /app/benchmarks/jvm_native_diff_engine.py
COPY scripts/verify_bpf_lsm_lock.py /app/scripts/verify_bpf_lsm_lock.py
COPY src/ /app/src/

RUN chmod +x /app/aeib-reproducibility/gate3/reproduce.sh

ENTRYPOINT ["/app/aeib-reproducibility/gate3/reproduce.sh"]
