// File: Sources/AEIBAgent/FastPathClassifier.swift
// Copyright 2026 SovereignNexus Project
// Licensed under the Apache License, Version 2.0 (the "License");
// Compile with Swift 6.0+: swift test -Xswiftc -strict-concurrency=complete

import CryptoKit
import Foundation

public struct OperationClassificationFlags: OptionSet, Sendable, Codable {
    public let rawValue: UInt64

    public init(rawValue: UInt64) {
        self.rawValue = rawValue
    }

    public static let isReadOnly                   = OperationClassificationFlags(rawValue: 1 << 0)
    public static let isFinancialMutation          = OperationClassificationFlags(rawValue: 1 << 1)
    public static let isPrivilegedCredentialAccess  = OperationClassificationFlags(rawValue: 1 << 2)
    public static let isUntrustedContextTainted    = OperationClassificationFlags(rawValue: 1 << 3)
    public static let isExternalNetworkEgress      = OperationClassificationFlags(rawValue: 1 << 4)
    public static let isStateModification          = OperationClassificationFlags(rawValue: 1 << 5)
    public static let isHighConsequence            = OperationClassificationFlags(rawValue: 1 << 6)

    public static let safeReadOnlyMask: OperationClassificationFlags = [.isReadOnly]
    public static let dangerousFlagsMask: OperationClassificationFlags = [
        .isFinancialMutation,
        .isPrivilegedCredentialAccess,
        .isUntrustedContextTainted,
        .isExternalNetworkEgress,
        .isStateModification,
        .isHighConsequence
    ]
}

public enum FastPathRoute: Sendable, Equatable {
    case fastPathDirectRead(reason: String)
    case privilegedGateRequired(reasons: [String])
    case rejectedInvalidBitmask(reason: String)
}

public struct ClassificationVerdict: Sendable {
    public let route: FastPathRoute
    public let operationID: String
    public let bitmaskHex: String
    public let auditDigestSHA256: String
    public let evaluatedAtEpochSec: Int64

    public init(
        route: FastPathRoute,
        operationID: String,
        bitmaskHex: String,
        auditDigestSHA256: String,
        evaluatedAtEpochSec: Int64
    ) {
        self.route = route
        self.operationID = operationID
        self.bitmaskHex = bitmaskHex
        self.auditDigestSHA256 = auditDigestSHA256
        self.evaluatedAtEpochSec = evaluatedAtEpochSec
    }
}

/// Ultra-low latency, on-device fast-path bitmask classifier.
/// Evaluates subagent operation intent bitmasks before invoking privileged XPC actors.
/// Routes safe read-only operations directly while failing closed on any mutation,
/// taint, or privileged credential access.
public struct FastPathOperationClassifier: Sendable {

    public init() {}

    /// Evaluates the operation classification flags and returns an immutable verdict.
    public func classify(
        operationID: String,
        flags: OperationClassificationFlags,
        endpoint: String,
        nowSec: Int64
    ) -> ClassificationVerdict {
        let bitmaskHex = String(format: "0x%016llX", flags.rawValue)

        // 1. Check for empty or uninitialized bitmask
        if flags.rawValue == 0 {
            let digest = computeAuditDigest(
                opID: operationID,
                route: "REJECTED_ZERO_MASK",
                bitmaskHex: bitmaskHex,
                nowSec: nowSec
            )
            return ClassificationVerdict(
                route: .rejectedInvalidBitmask(reason: "Bitmask is zero; unclassified operations cannot be dispatched"),
                operationID: operationID,
                bitmaskHex: bitmaskHex,
                auditDigestSHA256: digest,
                evaluatedAtEpochSec: nowSec
            )
        }

        // 2. Identify all dangerous/privileged flags
        var gatingReasons: [String] = []
        if flags.contains(.isFinancialMutation) {
            gatingReasons.append("CONTAINS_FINANCIAL_MUTATION")
        }
        if flags.contains(.isPrivilegedCredentialAccess) {
            gatingReasons.append("CONTAINS_PRIVILEGED_CREDENTIAL_ACCESS")
        }
        if flags.contains(.isUntrustedContextTainted) {
            gatingReasons.append("CONTAINS_UNTRUSTED_CONTEXT_TAINT")
        }
        if flags.contains(.isExternalNetworkEgress) {
            gatingReasons.append("CONTAINS_EXTERNAL_NETWORK_EGRESS")
        }
        if flags.contains(.isStateModification) {
            gatingReasons.append("CONTAINS_STATE_MODIFICATION")
        }
        if flags.contains(.isHighConsequence) {
            gatingReasons.append("CONTAINS_HIGH_CONSEQUENCE_ACTION")
        }

        // 3. Fast-path condition: Pure read-only with NO dangerous flags
        let hasDangerousFlags = !gatingReasons.isEmpty
        let isPureReadOnly = flags.contains(.isReadOnly) && !hasDangerousFlags

        let route: FastPathRoute
        if isPureReadOnly {
            route = .fastPathDirectRead(
                reason: "Operation contains only safe read-only flags; fast-path execution permitted without XPC actor lock"
            )
        } else {
            // Fail closed: Route to Station 1 Privileged Gate Actor
            if gatingReasons.isEmpty {
                gatingReasons.append("NON_READ_ONLY_OPERATION")
            }
            route = .privilegedGateRequired(reasons: gatingReasons)
        }

        let routeSummary: String
        switch route {
        case .fastPathDirectRead:
            routeSummary = "FAST_PATH_DIRECT_READ"
        case .privilegedGateRequired(let reasons):
            routeSummary = "PRIVILEGED_GATE_REQUIRED:" + reasons.joined(separator: ",")
        case .rejectedInvalidBitmask(let r):
            routeSummary = "REJECTED:" + r
        }

        let digest = computeAuditDigest(
            opID: operationID,
            route: routeSummary,
            bitmaskHex: bitmaskHex,
            nowSec: nowSec
        )

        return ClassificationVerdict(
            route: route,
            operationID: operationID,
            bitmaskHex: bitmaskHex,
            auditDigestSHA256: digest,
            evaluatedAtEpochSec: nowSec
        )
    }

    private func computeAuditDigest(
        opID: String,
        route: String,
        bitmaskHex: String,
        nowSec: Int64
    ) -> String {
        let canonicalPayload = "\(opID)|\(bitmaskHex)|\(route)|\(nowSec)"
        let digest = SHA256.hash(data: Data(canonicalPayload.utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }
}
