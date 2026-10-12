package com.aeib.runtime;

import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.*;
import ai.sovereign.aeib.core.Jcs;
import com.aeib.crypto.Ed25519ProofEngine;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.PrivateKey;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

public class Station3ContinuousLedger implements ContinuousLedger {

    private final PrivateKey ledgerKey;
    private final String keyId;
    private final long currentEpoch;
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final ConcurrentLinkedQueue<LifecycleEvent> globalEventLog = new ConcurrentLinkedQueue<>();
    private final ConcurrentHashMap<String, ConcurrentLinkedQueue<LifecycleEvent>> operationLogs = new ConcurrentHashMap<>();

    private byte[] currentHashChainTip = new byte[32]; // Genesis block zero-hash

    public Station3ContinuousLedger(PrivateKey ledgerKey, String keyId, long currentEpoch) {
        this.ledgerKey = ledgerKey;
        this.keyId = keyId;
        this.currentEpoch = currentEpoch;
    }

    private static final int MAX_BOUNDED_EVENTS = 10_000;

    @Override
    public synchronized void appendEvent(LifecycleEvent event) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            digest.update(this.currentHashChainTip);
            
            Map<String, Object> bindingMap = new LinkedHashMap<>();
            bindingMap.put("operationId", event.operationId());
            bindingMap.put("phase", event.phase().name());
            bindingMap.put("timestamp", event.timestamp().toEpochMilli());
            bindingMap.put("dataHash", Base64.getEncoder().encodeToString(event.eventDataHash() != null ? event.eventDataHash() : new byte[0]));
            
            String rawEventJson = MAPPER.writeValueAsString(bindingMap);
            byte[] canonicalEventBytes = Jcs.canonicalize(rawEventJson);
            
            digest.update(canonicalEventBytes);
            this.currentHashChainTip = digest.digest();

            if (globalEventLog.size() >= MAX_BOUNDED_EVENTS) {
                globalEventLog.poll();
            }
            globalEventLog.add(event);
            ConcurrentLinkedQueue<LifecycleEvent> opQueue = operationLogs.computeIfAbsent(event.operationId(), k -> new ConcurrentLinkedQueue<>());
            if (opQueue.size() >= MAX_BOUNDED_EVENTS) {
                opQueue.poll();
            }
            opQueue.add(event);

        } catch (Exception e) {
            throw new RuntimeException("Failed to append event to sequential hash-chain", e);
        }
    }

    @Override
    public synchronized ContinuityReceipt generateReceipt(String operationId) {
        try {
            byte[] tipSnapshot = this.currentHashChainTip.clone();
            Map<String, Object> receiptStatement = new LinkedHashMap<>();
            receiptStatement.put("operationId", operationId);
            receiptStatement.put("chainTip", Base64.getEncoder().encodeToString(tipSnapshot));
            receiptStatement.put("epoch", this.currentEpoch);
            receiptStatement.put("keyId", this.keyId);

            String rawJson = MAPPER.writeValueAsString(receiptStatement);
            
            // Unified Jcs canonicalizer
            byte[] signedStatementBytes = Jcs.canonicalize(rawJson);
            byte[] ed25519Sig = Ed25519ProofEngine.sign(signedStatementBytes, this.ledgerKey);

            HybridSignature signature = new HybridSignature(
                ed25519Sig,
                null,
                this.keyId,
                this.currentEpoch
            );

            return new ContinuityReceipt(
                operationId,
                this.currentEpoch,
                tipSnapshot.clone(),
                "Ed25519",
                "SHA-256",
                signature,
                signedStatementBytes,
                Optional.empty()
            );
        } catch (Exception e) {
            throw new RuntimeException("Failed to generate cryptographic signature", e);
        }
    }
}
