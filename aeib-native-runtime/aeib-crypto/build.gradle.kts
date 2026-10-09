plugins {
    `java-library`
}

dependencies {
    // RFC 8785 JSON Canonicalization Scheme (reference implementation)
    implementation("io.github.erdtman:java-json-canonicalization:1.1")
    
    // Ed25519 via Bouncy Castle
    implementation("org.bouncycastle:bcprov-jdk18on:1.85")
    
    // Jackson, constrained to reject unknown properties and bound parsing
    implementation("com.fasterxml.jackson.core:jackson-databind:2.18.2")
}
