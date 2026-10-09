package com.aeib.verifier;

import com.fasterxml.jackson.databind.JsonNode;

/**
 * Validated in-memory structure representing a parsed ContinuityReceipt.
 */
public record ParsedReceipt(
    String operationId,
    long epoch,
    String chainTip,
    String keyId,
    byte[] signature,
    byte[] signedStatement,
    JsonNode statementNode,
    JsonNode rootNode
) {}
