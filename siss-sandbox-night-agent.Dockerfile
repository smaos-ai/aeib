FROM rust:1.82-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN useradd -m -s /bin/bash agent
WORKDIR /work
ENV CARGO_NET_OFFLINE=true
ENV RUST_BACKTRACE=1
USER agent
ENTRYPOINT ["bash", "-c"]
CMD ["echo 'Container ready for agent injection'"]
