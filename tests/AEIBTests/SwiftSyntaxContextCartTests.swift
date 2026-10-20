// File: Tests/AEIBTests/SwiftSyntaxContextCartTests.swift
// Copyright 2026 SovereignNexus Project
// Licensed under the Apache License, Version 2.0 (the "License");

import CryptoKit
import Foundation
import Testing
@testable import AEIBCore
@testable import AEIBAgent

@Suite("AEIB Agent ContextCart, SANS 2026 & Praxist Invariants")
struct SwiftSyntaxContextCartTests {

    @Test("SwiftSyntaxContextCart slices function and struct signatures with dual-digest SHA-256")
    func testSwiftSyntaxSliceFunctionAndStruct() {
        let sampleSource = """
        // Multi-line Header documentation
        import Foundation
        import CryptoKit

        public struct PaymentMandate {
            public let mandateID: String
            public let amountMinor: UInt64
        }

        public func executeSettlement(mandate: PaymentMandate, targetIBAN: String) -> Bool {
            // Internal processing logic with loopback details
            var count = 0
            for _ in 0..<10 {
                count += 1
            }
            return count > 0
        }
        """

        let slices = SwiftSyntaxContextCart.sliceSwiftSource(sampleSource, taintTier: .tier0Pinned)
        #expect(slices.count >= 2)

        let names = slices.map { $0.symbolName }
        #expect(names.contains("PaymentMandate"))
        #expect(names.contains("executeSettlement"))

        for slice in slices {
            #expect(slice.rawFileSHA256.hasPrefix("sha256:"))
            #expect(slice.sliceSHA256.hasPrefix("sha256:"))
            #expect(slice.taintTier == .tier0Pinned)
            #expect(slice.byteReductionRatio >= 1.0)
            #expect(slice.startUTF8Offset >= 0)
            #expect(slice.endUTF8Offset > slice.startUTF8Offset)
        }
    }

    @Test("Praxist 4-state finding classification supports all states")
    func testPraxistEvidenceClassification() {
        let states: [FindingClassification] = [.positive, .negative, .diagnostic, .uncertain]
        #expect(states.count == 4)
        #expect(FindingClassification.positive.rawValue == "POSITIVE")
        #expect(FindingClassification.negative.rawValue == "NEGATIVE")
        #expect(FindingClassification.diagnostic.rawValue == "DIAGNOSTIC")
        #expect(FindingClassification.uncertain.rawValue == "UNCERTAIN")
    }

    @Test("SANS 2026 Governance Identity requires 90-day retention and named human owner")
    func testSans2026GovernanceIdentity() throws {
        // 1. Valid SANS 2026 identity
        let validIdentity = try SansGovernanceIdentity(
            agentMachineIdentityID: "did:key:z6MkAgentMachine001",
            namedHumanOwnerID: "user:ciso-alice@enterprise.example",
            haltAuthorityKeyID: "did:key:z6MkHaltAuthorityRoot",
            telemetryRetentionDays: 90
        )
        #expect(validIdentity.telemetryRetentionDays == 90)
        #expect(validIdentity.mappedFrameworks.contains("NIST_AI_RMF"))
        #expect(validIdentity.mappedFrameworks.contains("EU_AI_ACT_EN_18286"))
        #expect(validIdentity.mappedFrameworks.contains("ISO_42001"))
        #expect(validIdentity.mappedFrameworks.contains("CSA_AICM"))

        // 2. Fails closed if retention is less than 90 days
        #expect(throws: AEIBError.keyCustodyFailure(reason: "SANS_2026_GOVERNANCE_IDENTITY_INCOMPLETE")) {
            _ = try SansGovernanceIdentity(
                agentMachineIdentityID: "did:key:z6MkAgentMachine001",
                namedHumanOwnerID: "user:ciso-alice@enterprise.example",
                haltAuthorityKeyID: "did:key:z6MkHaltAuthorityRoot",
                telemetryRetentionDays: 30 // < 90 days
            )
        }

        // 3. Fails closed if named human owner is empty (109:1 machine identity control)
        #expect(throws: AEIBError.keyCustodyFailure(reason: "SANS_2026_GOVERNANCE_IDENTITY_INCOMPLETE")) {
            _ = try SansGovernanceIdentity(
                agentMachineIdentityID: "did:key:z6MkAgentMachine001",
                namedHumanOwnerID: "",
                haltAuthorityKeyID: "did:key:z6MkHaltAuthorityRoot",
                telemetryRetentionDays: 90
            )
        }
    }

    @Test("GovernedCrossHarnessHandoff preserves taint and host-injected external seed")
    func testGovernedCrossHarnessHandoff() throws {
        let externalSeed: UInt64 = 42_949_672_950 // Host CSPRNG seed
        let handoff = GovernedCrossHarnessHandoff(
            handoffID: "handoff-001",
            sourceHarness: "claude-code",
            targetHarness: "codex-cli",
            claimedByOwnerID: "worker-subagent-7",
            inheritedTaintTier: .tier2UntrustedExternal,
            externalRandomSeed: externalSeed,
            findingState: .diagnostic,
            boundedSummary: "Bounded ContextCart brief containing scraped web endpoints",
            artifactLineageDigests: ["sha256:abc12345"]
        )

        #expect(handoff.inheritedTaintTier == .tier2UntrustedExternal)
        #expect(handoff.externalRandomSeed == externalSeed)
        #expect(handoff.findingState == .diagnostic)

        // Codable roundtrip verification
        let encoder = JSONEncoder()
        let data = try encoder.encode(handoff)
        let decoder = JSONDecoder()
        let decoded = try decoder.decode(GovernedCrossHarnessHandoff.self, from: data)
        #expect(decoded == handoff)
    }

    @Test("FastPathOperationClassifier routes read-only and gates mutations")
    func testFastPathClassifierInvariants() {
        let classifier = FastPathOperationClassifier()
        let nowSec: Int64 = 1_760_000_000

        // 1. Safe read-only fast path
        let readVerdict = classifier.classify(
            operationID: "op-read-1",
            flags: .isReadOnly,
            endpoint: "GET /v1/account",
            nowSec: nowSec
        )
        switch readVerdict.route {
        case .fastPathDirectRead(let reason):
            #expect(!reason.isEmpty)
        default:
            Issue.record("Expected fastPathDirectRead")
        }

        // 2. Mutation gated to privileged actor
        let mutVerdict = classifier.classify(
            operationID: "op-mut-1",
            flags: [.isReadOnly, .isFinancialMutation],
            endpoint: "POST /v1/refunds",
            nowSec: nowSec
        )
        switch mutVerdict.route {
        case .privilegedGateRequired(let reasons):
            #expect(reasons.contains("CONTAINS_FINANCIAL_MUTATION"))
        default:
            Issue.record("Expected privilegedGateRequired")
        }

        // 3. Zero bitmask rejected
        let zeroVerdict = classifier.classify(
            operationID: "op-zero-1",
            flags: OperationClassificationFlags(rawValue: 0),
            endpoint: "GET /v1/ping",
            nowSec: nowSec
        )
        switch zeroVerdict.route {
        case .rejectedInvalidBitmask(let reason):
            #expect(!reason.isEmpty)
        default:
            Issue.record("Expected rejectedInvalidBitmask")
        }
    }
}
