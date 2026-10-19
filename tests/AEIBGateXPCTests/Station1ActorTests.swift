// File: Tests/AEIBGateXPCTests/Station1ActorTests.swift
// Copyright 2026 SovereignNexus Project
// Licensed under the Apache License, Version 2.0 (the "License");

import CryptoKit
import Foundation
import Testing
@testable import AEIBGateXPC

@Suite("AEIB Station 1 Swift 6 Actor Invariants")
struct Station1ActorTests {

    @Test("Valid dispatch creates WAL record and valid P-256 signature")
    func testValidDispatch() async throws {
        let tempDir = FileManager.default.temporaryDirectory
        let walPath = tempDir.appendingPathComponent("test_wal_\(UUID().uuidString).log").path
        defer { try? FileManager.default.removeItem(atPath: walPath) }

        let pinnedRecipient = "iban:DE89370400440532013000"
        let gate = try Station1FinancialGateActor(
            sprintLimitMinor: 800_00,
            pinnedRecipients: [pinnedRecipient],
            walPath: walPath
        )

        let nowSec: Int64 = 1_760_000_000
        let req = GovernedDispatchRequest(
            operationID: "op-swift-1",
            sponsorID: "sponsor-1",
            endpoint: "POST /v1/refunds",
            recipient: pinnedRecipient,
            amountMinor: 450_00,
            maxPerCallMinor: 500_00,
            taintTier: .tier0Pinned,
            claimedTimestampSec: nowSec
        )

        let decision = try await gate.evaluateAndReserve(req, gateNowSec: nowSec)
        #expect(decision.disposition == .dispatched)
        #expect(decision.rejectionCode == nil)
        #expect(decision.p256SignatureDERBase64 != nil)

        let escrowed = await gate.getEscrowedAmountMinor()
        #expect(escrowed == 450_00)

        // Verify WAL file exists and contains canonical line
        let walContent = try String(contentsOfFile: walPath, encoding: .utf8)
        #expect(walContent.contains("op-swift-1|iban:DE89370400440532013000|45000|DISPATCHED"))
    }

    @Test("Tainted context to unpinned recipient is rejected fail-closed")
    func testTaintedContextToUnpinnedRecipient() async throws {
        let tempDir = FileManager.default.temporaryDirectory
        let walPath = tempDir.appendingPathComponent("test_wal_\(UUID().uuidString).log").path
        defer { try? FileManager.default.removeItem(atPath: walPath) }

        let pinnedRecipient = "iban:DE89370400440532013000"
        let attackerRecipient = "iban:CH9300000000000000000"
        let gate = try Station1FinancialGateActor(
            sprintLimitMinor: 800_00,
            pinnedRecipients: [pinnedRecipient],
            walPath: walPath
        )

        let nowSec: Int64 = 1_760_000_000
        let req = GovernedDispatchRequest(
            operationID: "op-taint-1",
            sponsorID: "sponsor-1",
            endpoint: "POST /v1/refunds",
            recipient: attackerRecipient,
            amountMinor: 100_00,
            maxPerCallMinor: 500_00,
            taintTier: .tier2UntrustedExternal,
            claimedTimestampSec: nowSec
        )

        let decision = try await gate.evaluateAndReserve(req, gateNowSec: nowSec)
        #expect(decision.disposition == .notDispatched)
        #expect(decision.rejectionCode == "UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP")
    }

    @Test("Delegation attenuation ceiling breach is rejected")
    func testDelegationAttenuationCeilingBreach() async throws {
        let tempDir = FileManager.default.temporaryDirectory
        let walPath = tempDir.appendingPathComponent("test_wal_\(UUID().uuidString).log").path
        defer { try? FileManager.default.removeItem(atPath: walPath) }

        let pinnedRecipient = "iban:DE89370400440532013000"
        let gate = try Station1FinancialGateActor(
            sprintLimitMinor: 800_00,
            pinnedRecipients: [pinnedRecipient],
            walPath: walPath
        )

        let nowSec: Int64 = 1_760_000_000
        // maxPerCall is 500_00, requested is 550_00
        let req = GovernedDispatchRequest(
            operationID: "op-atten-1",
            sponsorID: "sponsor-1",
            endpoint: "POST /v1/refunds",
            recipient: pinnedRecipient,
            amountMinor: 550_00,
            maxPerCallMinor: 500_00,
            taintTier: .tier0Pinned,
            claimedTimestampSec: nowSec
        )

        let decision = try await gate.evaluateAndReserve(req, gateNowSec: nowSec)
        #expect(decision.disposition == .notDispatched)
        #expect(decision.rejectionCode == "ERR_DELEGATION_ATTENUATION_BREACH")
    }

    @Test("Clock skew greater than 5 seconds is rejected")
    func testClockSkewRejected() async throws {
        let tempDir = FileManager.default.temporaryDirectory
        let walPath = tempDir.appendingPathComponent("test_wal_\(UUID().uuidString).log").path
        defer { try? FileManager.default.removeItem(atPath: walPath) }

        let pinnedRecipient = "iban:DE89370400440532013000"
        let gate = try Station1FinancialGateActor(
            sprintLimitMinor: 800_00,
            pinnedRecipients: [pinnedRecipient],
            walPath: walPath
        )

        let nowSec: Int64 = 1_760_000_000
        let req = GovernedDispatchRequest(
            operationID: "op-clock-1",
            sponsorID: "sponsor-1",
            endpoint: "POST /v1/refunds",
            recipient: pinnedRecipient,
            amountMinor: 100_00,
            maxPerCallMinor: 500_00,
            taintTier: .tier0Pinned,
            claimedTimestampSec: 2_000_000_000 // Skew >> 5s
        )

        let decision = try await gate.evaluateAndReserve(req, gateNowSec: nowSec)
        #expect(decision.disposition == .notDispatched)
        #expect(decision.rejectionCode == "REJECTED_CLOCK_SKEW_OR_MANIPULATION")
    }

    @Test("Sprint limit and indeterminate escrow accounting")
    func testSprintLimitAndEscrowLifecycle() async throws {
        let tempDir = FileManager.default.temporaryDirectory
        let walPath = tempDir.appendingPathComponent("test_wal_\(UUID().uuidString).log").path
        defer { try? FileManager.default.removeItem(atPath: walPath) }

        let pinnedRecipient = "iban:DE89370400440532013000"
        let gate = try Station1FinancialGateActor(
            sprintLimitMinor: 800_00, // EUR 800 cap
            pinnedRecipients: [pinnedRecipient],
            walPath: walPath
        )

        let nowSec: Int64 = 1_760_000_000
        let req1 = GovernedDispatchRequest(
            operationID: "op-escrow-1",
            sponsorID: "sponsor-1",
            endpoint: "POST /v1/refunds",
            recipient: pinnedRecipient,
            amountMinor: 450_00,
            maxPerCallMinor: 500_00,
            taintTier: .tier0Pinned,
            claimedTimestampSec: nowSec
        )
        let dec1 = try await gate.evaluateAndReserve(req1, gateNowSec: nowSec)
        #expect(dec1.disposition == .dispatched)

        // Mark op-escrow-1 as indeterminate
        try await gate.recordDownstreamEffect(operationID: "op-escrow-1", newDisposition: .effectIndeterminate)

        // Second request for EUR 400 must exceed EUR 800 sprint cap (450 + 400 = 850 > 800)
        let req2 = GovernedDispatchRequest(
            operationID: "op-escrow-2",
            sponsorID: "sponsor-1",
            endpoint: "POST /v1/refunds",
            recipient: pinnedRecipient,
            amountMinor: 400_00,
            maxPerCallMinor: 500_00,
            taintTier: .tier0Pinned,
            claimedTimestampSec: nowSec
        )
        let dec2 = try await gate.evaluateAndReserve(req2, gateNowSec: nowSec)
        #expect(dec2.disposition == .notDispatched)
        #expect(dec2.rejectionCode == "HALT_SPRINT_LIMIT_EXCEEDED")

        // Reconcile op-escrow-1 to confirmed
        try await gate.recordDownstreamEffect(operationID: "op-escrow-1", newDisposition: .confirmed)
        let settled = await gate.getSettledAmountMinor()
        #expect(settled == 450_00)
        let escrowed = await gate.getEscrowedAmountMinor()
        #expect(escrowed == 0)
    }
}
