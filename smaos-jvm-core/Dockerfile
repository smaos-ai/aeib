# Docker-Only Mandate: Never rely on local host JDK installations.
# Target LTS: eclipse-temurin:21-jdk (Current LTS baseline)
# Target Virtual Threads & Scoped Values: eclipse-temurin:24-jdk (JEP 491 Virtual Thread unpinning & JEP 506 Scoped Values)
FROM eclipse-temurin:24-jdk
WORKDIR /app
COPY . .
RUN chmod +x gradlew || true
CMD ["./gradlew", "test", "--info"]
