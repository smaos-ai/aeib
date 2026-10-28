# SMAOS JVM Core (Java 24 / 25 Runtime)

High-density Sovereign Agent Application Server control plane with:
- **JEP 491 Virtual Thread Unpinning**: Non-blocking carrier thread unmounting during JDBC/socket 504 probes.
- **JEP 506 Scoped Values**: Immutable stack-bounded context propagation (`tenant_id`, `principal_did`, `caid`) down multi-agent trees.
- **HikariCP Semaphore Gate**: Constrains physical connection pool (e.g. 32 connections) while parking 10,000+ virtual threads in user-space heap.
- **AeibDispositionEngine**: Port of the 5 closed policy verdicts and 7 disposition mapping rules.
- **CaidDerivation**: `CAID = H(Noun_EntityID || Verb_Action || JCS(Payload))`.

## Build & Test

### Local Execution (requires JDK 24+ with `--enable-preview`)
```bash
./gradlew test
```

### Docker Execution
```bash
docker build -t smaos-jvm-core .
docker run --rm smaos-jvm-core
```
