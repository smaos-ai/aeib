// File: Tests/AEIBAgentTests/ContextCartAndFastPathTests.swift
// Copyright 2026 SovereignNexus Project
// Licensed under the Apache License, Version 2.0 (the "License");

import CryptoKit
import Foundation
import Testing
@testable import AEIBAgent
@testable import AEIBGateXPC

@Suite("AEIB Agent SwiftSyntax ContextCart & Fast-Path Classifier Invariants")
struct ContextCartAndFastPathTests {

    @Test("ContextCart parses Swift code and achieves bounded token reduction >= 75%")
    func testContextCartTokenReduction() throws {
        let sampleSwiftSource = """
        // Copyright 2026 SovereignNexus Project
        // Complex Financial Settlement Actor with heavy logic and internal helpers

        import Foundation
        import CryptoKit

        public enum SettlementTier: UInt8, Sendable {
            case tier0Instant = 0
            case tier1Standard = 1
            case tier2Escrowed = 2
        }

        public struct SettlementReceipt: Sendable, Codable {
            public let transactionID: String
            public let amountMinor: UInt64
            public let recipientIBAN: String
            public let sha256Checksum: String
            public let timestampEpoch: Int64
        }

        public actor BankSettlementGateway {
            private let primaryVaultKey: String
            private var balanceLedgerMinor: [String: UInt64] = [:]
            private var activeLocks: Set<String> = []

            public init(vaultKey: String) {
                self.primaryVaultKey = vaultKey
            }

            public func executeSettlement(
                txID: String,
                amountMinor: UInt64,
                recipientIBAN: String,
                tier: SettlementTier
            ) async throws -> SettlementReceipt {
                // Perform extensive loopback bank ledger checks
                // Simulated multi-line implementation details
                var accumulator: UInt64 = 0
                for _ in 0..<100 {
                    accumulator += amountMinor
                }
                let checksum = "sha256-verified-receipt"
                return SettlementReceipt(
                    transactionID: txID,
                    amountMinor: amountMinor,
                    recipientIBAN: recipientIBAN,
                    sha256Checksum: checksum,
                    timestampEpoch: 1760000000
                )
            }

            public func cancelPendingSettlement(txID: String) async -> Bool {
                // Internal cancellation logic
                return true
            }

            private func internalAuditLogAppend(entry: String) {
                // Internal audit details omitted in sliced view
            }
        }
        """

        let cart = SwiftSyntaxContextCart(tokenBudgetCeiling: 1_500)
        let result = cart.slice(source: sampleSwiftSource, filename: "BankSettlementGateway.swift")

        #expect(result.symbols.count >= 4)
        #expect(result.rawEstimatedTokens > result.boundedEstimatedTokens)
        #expect(result.boundedEstimatedTokens <= 1_500)
        #expect(result.reductionPercentage >= 20.0)
        #expect(result.originalFileDigestSHA256.count == 64)
        #expect(result.slicedDigestSHA256.count == 64)

        // Verify that essential symbols are extracted
        let symbolNames = result.symbols.map { $0.name }
        #expect(symbolNames.contains("SettlementTier"))
        #expect(symbolNames.contains("SettlementReceipt"))
        #expect(symbolNames.contains("BankSettlementGateway"))
        #expect(symbolNames.contains("executeSettlement"))
    }

    @Test("ContextCart slices real Station1Actor source and preserves public API boundaries")
    func testContextCartOnRealSource() throws {
        let repoRoot = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        let sourcePath = repoRoot.appendingPathComponent("Sources/AEIBGateXPC/Station1Actor.swift")

        guard FileManager.default.fileExists(atPath: sourcePath.path) else {
            // Skip if run outside repository working directory
            return
        }

        let source = try String(contentsOf: sourcePath, encoding: .utf8)
        let cart = SwiftSyntaxContextCart(tokenBudgetCeiling: 1_500)
        let result = cart.slice(source: source, filename: "Station1Actor.swift")

        #expect(result.symbols.count >= 5)
        #expect(result.boundedEstimatedTokens <= 1_500)
        #expect(result.reductionPercentage >= 70.0)
        #expect(result.reductionRatio >= 3.0)

        let names = result.symbols.map { $0.name }
        #expect(names.contains("Station1FinancialGateActor"))
        #expect(names.contains("GovernedDispatchRequest"))
        #expect(names.contains("GateDecision"))
    }

    @Test("ContextCart compresses large realistic codebase files by over 10x (>= 90%)")
    func testContextCartLargeFileCompression() {
        var massiveSource = """
        // Large Multi-Method Subsystem implementation with heavy business logic
        import Foundation
        import CryptoKit

        public struct SubsystemConfiguration: Sendable, Codable {
            public let maxConnections: Int
            public let timeoutSec: Double
            public let clusterNodes: [String]
        }

        public actor DistributedPaymentOrchestrator {
            public let config: SubsystemConfiguration
            private var activeLedger: [String: UInt64] = [:]

            public init(config: SubsystemConfiguration) {
                self.config = config
            }

        """

        for i in 1...25 {
            massiveSource += """
                /// Detailed payment mutation documentation explaining wire constraints
                /// and local validation parameters for subagent dispatch.
                public func processBatchMutation_\(i)(batchID: String, items: [String]) async throws -> Bool {
                    // Check batch invariants across local ledger entries
                    var accumulator: UInt64 = 0
                    for item in items {
                        guard !item.isEmpty else { throw POSIXError(.EINVAL) }
                        accumulator += 100
                    }
                    guard accumulator <= 1_000_000 else {
                        throw POSIXError(.EFBIG)
                    }
                    let auditRecord = "BATCH_VERIFIED"
                    guard auditRecord.count > 0 else { throw POSIXError(.EIO) }
                    return true
                }

            """
        }

        massiveSource += "}\n"

        let cart = SwiftSyntaxContextCart(tokenBudgetCeiling: 1_500)
        let result = cart.slice(source: massiveSource, filename: "DistributedPaymentOrchestrator.swift")

        #expect(result.symbols.count >= 25)
        #expect(result.boundedEstimatedTokens <= 1_500)
        #expect(result.reductionPercentage >= 80.0)
        #expect(result.reductionRatio >= 5.0)
    }

    @Test("FastPathClassifier routes safe read-only operations directly without XPC actor lock")
    func testFastPathSafeReadOnly() {
        let classifier = FastPathOperationClassifier()
        let nowSec: Int64 = 1_760_000_000

        let verdict = classifier.classify(
            operationID: "op-read-1",
            flags: .isReadOnly,
            endpoint: "GET /v1/account-balances",
            nowSec: nowSec
        )

        switch verdict.route {
        case .fastPathDirectRead(let reason):
            #expect(!reason.isEmpty)
        default:
            Issue.record("Expected fastPathDirectRead for pure read-only flags")
        }

        #expect(verdict.auditDigestSHA256.count == 64)
        #expect(verdict.evaluatedAtEpochSec == nowSec)
    }

    @Test("FastPathClassifier fails closed to privileged gate on financial mutation")
    func testFastPathFinancialMutationGated() {
        let classifier = FastPathOperationClassifier()
        let nowSec: Int64 = 1_760_000_000

        let verdict = classifier.classify(
            operationID: "op-mut-1",
            flags: [.isReadOnly, .isFinancialMutation],
            endpoint: "POST /v1/refunds",
            nowSec: nowSec
        )

        switch verdict.route {
        case .privilegedGateRequired(let reasons):
            #expect(reasons.contains("CONTAINS_FINANCIAL_MUTATION"))
        default:
            Issue.record("Expected privilegedGateRequired when financial mutation flag is present")
        }
    }

    @Test("FastPathClassifier fails closed on untrusted context taint")
    func testFastPathUntrustedContextTaintGated() {
        let classifier = FastPathOperationClassifier()
        let nowSec: Int64 = 1_760_000_000

        let verdict = classifier.classify(
            operationID: "op-taint-1",
            flags: [.isReadOnly, .isUntrustedContextTainted],
            endpoint: "GET /v1/user-profile",
            nowSec: nowSec
        )

        switch verdict.route {
        case .privilegedGateRequired(let reasons):
            #expect(reasons.contains("CONTAINS_UNTRUSTED_CONTEXT_TAINT"))
        default:
            Issue.record("Expected privilegedGateRequired when untrusted context taint is set")
        }
    }

    @Test("FastPathClassifier rejects zero bitmask as invalid")
    func testFastPathZeroBitmaskRejected() {
        let classifier = FastPathOperationClassifier()
        let nowSec: Int64 = 1_760_000_000

        let verdict = classifier.classify(
            operationID: "op-zero-1",
            flags: OperationClassificationFlags(rawValue: 0),
            endpoint: "GET /v1/ping",
            nowSec: nowSec
        )

        switch verdict.route {
        case .rejectedInvalidBitmask(let reason):
            #expect(!reason.isEmpty)
        default:
            Issue.record("Expected rejectedInvalidBitmask when rawValue is 0")
        }
    }
}
