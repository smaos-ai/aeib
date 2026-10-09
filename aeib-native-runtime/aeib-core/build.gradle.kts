plugins {
    `java-library`
}

dependencies {
    // Resilience4j 2.3.0 supports Java 21 as baseline (Do NOT upgrade to 2.4.0)
    implementation("io.github.resilience4j:resilience4j-ratelimiter:2.3.0")
    implementation("io.github.resilience4j:resilience4j-circuitbreaker:2.3.0")
}
