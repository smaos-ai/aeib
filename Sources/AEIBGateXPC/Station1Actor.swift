// File: Sources/AEIBGateXPC/Station1Actor.swift
// Copyright 2026 SovereignNexus Project
// Licensed under the Apache License, Version 2.0 (the "License");
// Compile with Swift 6.0+: swift test -Xswiftc -strict-concurrency=complete

import CryptoKit
import Foundation

public enum TaintTier: UInt8, Sendable, Codable {
    case tier0Pinned = 0
    case tier1Internal = 1
    case tier2UntrustedExternal = 2
}

public enum Disposition: String, Sendable, Codable {
    case dispatched = "DISPATCHED"
    case effectIndeterminate = "EFFECT_INDETERMINATE"
    case confirmed = "CONFIRMED"
    case refuted = "REFUTED"
    case notDispatched = "NOT_DISPATCHED"
}

public struct GovernedDispatchRequest: Sendable, Codable {
    public let operationID: String
    public let sponsorID: String
    public let endpoint: String
    public let recipient: String
    public let amountMinor: UInt64
    public let maxPerCallMinor: UInt64
    public let taintTier: TaintTier
    public let claimedTimestampSec: Int64

    public init(
        operationID: String,
        sponsorID: String,
        endpoint: String,
        recipient: String,
        amountMinor: UInt64,
        maxPerCallMinor: UInt64,
        taintTier: TaintTier,
        claimedTimestampSec: Int64
    ) {
        self.operationID = operationID
        self.sponsorID = sponsorID
        self.endpoint = endpoint
        self.recipient = recipient
        self.amountMinor = amountMinor
        self.maxPerCallMinor = maxPerCallMinor
        self.taintTier = taintTier
        self.claimedTimestampSec = claimedTimestampSec
    }
}

public struct GateDecision: Sendable, Codable {
    public let disposition: Disposition
    public let rejectionCode: String?
    public let p256SignatureDERBase64: String?

    public init(
        disposition: Disposition,
        rejectionCode: String?,
        p256SignatureDERBase64: String?
    ) {
        self.disposition = disposition
        self.rejectionCode = rejectionCode
        self.p256SignatureDERBase64 = p256SignatureDERBase64
    }
}

/// Signer using Apple Silicon Secure Enclave (`secp256r1` / NIST P-256) when entitled,
/// falling back to CryptoKit software P-256 for environments without biometric/SEP keychain access.
public struct SecureEnclaveWarrantSigner: Sendable {
    private let softwareFallbackKey: P256.Signing.PrivateKey

    public init() {
        self.softwareFallbackKey = P256.Signing.PrivateKey()
    }

    public func signCanonicalBytes(_ data: Data) throws -> Data {
        if SecureEnclave.isAvailable {
            do {
                // In production with signed entitlements, key is bound inside Apple SEP hardware
                let sepKey = try SecureEnclave.P256.Signing.PrivateKey()
                let sig = try sepKey.signature(for: data)
                return sig.derRepresentation
            } catch {
                // Fallback for CI/development environments without keychain entitlements
                let sig = try softwareFallbackKey.signature(for: data)
                return sig.derRepresentation
            }
        } else {
            let sig = try softwareFallbackKey.signature(for: data)
            return sig.derRepresentation
        }
    }
}

/// Swift 6 Actor evaluating compile-time data-race immunity across concurrent XPC subagents.
public actor Station1FinancialGateActor {
    private let sprintLimitMinor: UInt64
    private let pinnedRecipients: Set<String>
    private let signer: SecureEnclaveWarrantSigner
    private let walFileDescriptor: Int32

    private var escrowedMinor: UInt64 = 0
    private var settledMinor: UInt64 = 0
    private var activeOperations: [String: (Disposition, UInt64)] = [:]

    public init(
        sprintLimitMinor: UInt64,
        pinnedRecipients: Set<String>,
        walPath: String
    ) throws {
        self.sprintLimitMinor = sprintLimitMinor
        self.pinnedRecipients = pinnedRecipients
        self.signer = SecureEnclaveWarrantSigner()
        self.walFileDescriptor = open(walPath, O_CREAT | O_WRONLY | O_APPEND, 0o600)
        guard self.walFileDescriptor >= 0 else {
            throw POSIXError(.EIO)
        }
    }

    deinit {
        if walFileDescriptor >= 0 {
            close(walFileDescriptor)
        }
    }

    /// Evaluates all P0 invariants inside a single serialized Actor turn.
    public func evaluateAndReserve(
        _ req: GovernedDispatchRequest,
        gateNowSec: Int64
    ) throws -> GateDecision {
        // 1. P0 #3 Fix (AT70): Gate-owned clock check (max 5s drift)
        if abs(req.claimedTimestampSec - gateNowSec) > 5 {
            return GateDecision(
                disposition: .notDispatched,
                rejectionCode: "REJECTED_CLOCK_SKEW_OR_MANIPULATION",
                p256SignatureDERBase64: nil
            )
        }

        // 2. AT58: Prohibit blind retry on in-flight or indeterminate operations
        if let (existingDisp, _) = activeOperations[req.operationID] {
            let code = (existingDisp == .effectIndeterminate)
                ? "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY"
                : "REJECTED_DUPLICATE_OPERATION_ID"
            return GateDecision(
                disposition: .notDispatched,
                rejectionCode: code,
                p256SignatureDERBase64: nil
            )
        }

        // 3. P0 #5 Fix (AT71): Enforce per-call delegation attenuation ceiling
        if req.amountMinor == 0 || req.amountMinor > req.maxPerCallMinor {
            return GateDecision(
                disposition: .notDispatched,
                rejectionCode: "ERR_DELEGATION_ATTENUATION_BREACH",
                p256SignatureDERBase64: nil
            )
        }

        // 4. P0 #2 Fix (AT57b): Derive recipient pinning strictly from Actor's TIER_1 allowlist
        if req.taintTier == .tier2UntrustedExternal && !pinnedRecipients.contains(req.recipient) {
            return GateDecision(
                disposition: .notDispatched,
                rejectionCode: "UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP",
                p256SignatureDERBase64: nil
            )
        }

        // 5. Overflow-safe 64-bit budget & escrow check
        let (subTotal, ovf1) = settledMinor.addingReportingOverflow(escrowedMinor)
        let (totalExposure, ovf2) = subTotal.addingReportingOverflow(req.amountMinor)
        if ovf1 || ovf2 || totalExposure > sprintLimitMinor {
            return GateDecision(
                disposition: .notDispatched,
                rejectionCode: "HALT_SPRINT_LIMIT_EXCEEDED",
                p256SignatureDERBase64: nil
            )
        }

        // 6. Durable Darwin F_FULLFSYNC WAL write before socket dispatch
        let canonicalLine = "\(req.operationID)|\(req.recipient)|\(req.amountMinor)|DISPATCHED\n"
        let lineData = Data(canonicalLine.utf8)
        try lineData.withUnsafeBytes { rawBuf in
            guard let base = rawBuf.baseAddress else { return }
            let written = write(walFileDescriptor, base, rawBuf.count)
            if written != rawBuf.count {
                throw POSIXError(.EIO)
            }
        }
        #if os(macOS) || os(iOS) || os(visionOS)
        _ = fcntl(walFileDescriptor, F_FULLFSYNC)
        #else
        _ = fsync(walFileDescriptor)
        #endif

        escrowedMinor += req.amountMinor
        activeOperations[req.operationID] = (.dispatched, req.amountMinor)

        let sigDER = try signer.signCanonicalBytes(lineData)
        return GateDecision(
            disposition: .dispatched,
            rejectionCode: nil,
            p256SignatureDERBase64: sigDER.base64EncodedString()
        )
    }

    public func recordDownstreamEffect(
        operationID: String,
        newDisposition: Disposition
    ) throws {
        guard let (priorDisp, amount) = activeOperations[operationID] else {
            throw POSIXError(.ENOENT)
        }
        guard priorDisp == .dispatched || priorDisp == .effectIndeterminate else {
            throw POSIXError(.EINVAL)
        }

        switch newDisposition {
        case .effectIndeterminate:
            activeOperations[operationID] = (.effectIndeterminate, amount)
        case .confirmed:
            if escrowedMinor >= amount {
                escrowedMinor -= amount
            } else {
                escrowedMinor = 0
            }
            settledMinor += amount
            activeOperations[operationID] = (.confirmed, amount)
        case .refuted:
            if escrowedMinor >= amount {
                escrowedMinor -= amount
            } else {
                escrowedMinor = 0
            }
            activeOperations[operationID] = (.refuted, amount)
        default:
            throw POSIXError(.EINVAL)
        }
    }

    public func getEscrowedAmountMinor() -> UInt64 {
        return escrowedMinor
    }

    public func getSettledAmountMinor() -> UInt64 {
        return settledMinor
    }
}
