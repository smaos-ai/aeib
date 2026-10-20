// File: Sources/AEIBAgent/SwiftSyntaxContextCart.swift
// Completes the `AEIBAgent` target in Package.swift (Swift 6 Strict Concurrency)

import AEIBCore
import CryptoKit
import Foundation
#if canImport(SwiftParser)
import SwiftParser
#endif
#if canImport(SwiftSyntax)
import SwiftSyntax
#endif

/// Praxist (arXiv:2608.25955) 4-state artifact-grounded finding classification.
public enum FindingClassification: String, Sendable, Codable {
    case positive = "POSITIVE"
    case negative = "NEGATIVE"
    case diagnostic = "DIAGNOSTIC"
    case uncertain = "UNCERTAIN"
}

/// SANS 2026 AI Governance Field Guide mandatory deployer metadata (109:1 machine-identity binding).
public struct SansGovernanceIdentity: Sendable, Codable, Equatable {
    public let agentMachineIdentityID: String
    public let namedHumanOwnerID: String
    public let haltAuthorityKeyID: String
    public let telemetryRetentionDays: Int
    public let mappedFrameworks: [String]

    public init(
        agentMachineIdentityID: String,
        namedHumanOwnerID: String,
        haltAuthorityKeyID: String,
        telemetryRetentionDays: Int = 90,
        mappedFrameworks: [String] = ["NIST_AI_RMF", "EU_AI_ACT_EN_18286", "ISO_42001", "CSA_AICM"]
    ) throws {
        // SANS 2026 Question 1: Must support at least 90 days of on-demand telemetry
        guard telemetryRetentionDays >= 90,
              !namedHumanOwnerID.isEmpty,
              !haltAuthorityKeyID.isEmpty else {
            throw AEIBError.keyCustodyFailure(reason: "SANS_2026_GOVERNANCE_IDENTITY_INCOMPLETE")
        }
        self.agentMachineIdentityID = agentMachineIdentityID
        self.namedHumanOwnerID = namedHumanOwnerID
        self.haltAuthorityKeyID = haltAuthorityKeyID
        self.telemetryRetentionDays = telemetryRetentionDays
        self.mappedFrameworks = mappedFrameworks
    }
}

/// Cross-harness handoff packet (inspired by `ai-memory` v3.1.1) with AEIB Taint & Single-Owner Lease.
/// Prevents taint laundering when switching from Claude Code to Codex/Cursor mid-task.
public struct GovernedCrossHarnessHandoff: Sendable, Codable, Equatable {
    public let handoffID: String
    public let sourceHarness: String
    public let targetHarness: String
    public let claimedByOwnerID: String?
    public let inheritedTaintTier: TaintTier
    public let externalRandomSeed: UInt64 // DeepMind fix: host-supplied seed, never LLM-generated
    public let findingState: FindingClassification
    public let boundedSummary: String
    public let artifactLineageDigests: [String]

    public init(
        handoffID: String,
        sourceHarness: String,
        targetHarness: String,
        claimedByOwnerID: String?,
        inheritedTaintTier: TaintTier,
        externalRandomSeed: UInt64,
        findingState: FindingClassification,
        boundedSummary: String,
        artifactLineageDigests: [String]
    ) {
        self.handoffID = handoffID
        self.sourceHarness = sourceHarness
        self.targetHarness = targetHarness
        self.claimedByOwnerID = claimedByOwnerID
        self.inheritedTaintTier = inheritedTaintTier
        self.externalRandomSeed = externalRandomSeed
        self.findingState = findingState
        self.boundedSummary = boundedSummary
        self.artifactLineageDigests = artifactLineageDigests
    }
}

/// Extracted Swift AST symbol slice with byte offsets and dual-digest taint provenance.
public struct SwiftSymbolSlice: Sendable, Codable, Equatable {
    public let symbolName: String
    public let symbolKind: String
    public let signatureOnly: String
    public let startUTF8Offset: Int
    public let endUTF8Offset: Int
    public let rawFileSHA256: String
    public let sliceSHA256: String
    public let taintTier: TaintTier
    public let byteReductionRatio: Double

    public init(
        symbolName: String,
        symbolKind: String,
        signatureOnly: String,
        startUTF8Offset: Int,
        endUTF8Offset: Int,
        rawFileSHA256: String,
        sliceSHA256: String,
        taintTier: TaintTier,
        byteReductionRatio: Double
    ) {
        self.symbolName = symbolName
        self.symbolKind = symbolKind
        self.signatureOnly = signatureOnly
        self.startUTF8Offset = startUTF8Offset
        self.endUTF8Offset = endUTF8Offset
        self.rawFileSHA256 = rawFileSHA256
        self.sliceSHA256 = sliceSHA256
        self.taintTier = taintTier
        self.byteReductionRatio = byteReductionRatio
    }
}

/// Native SwiftSyntax visitor that extracts function and type signatures without C-bindings.
public final class SymbolSignatureExtractor: SyntaxVisitor, @unchecked Sendable {
    public let sourceBytes: [UInt8]
    public let rawFileDigest: String
    public let taintTier: TaintTier
    public var extractedSlices: [SwiftSymbolSlice] = []

    public init(sourceBytes: [UInt8], rawFileDigest: String, taintTier: TaintTier) {
        self.sourceBytes = sourceBytes
        self.rawFileDigest = rawFileDigest
        self.taintTier = taintTier
        super.init(viewMode: .sourceAccurate)
    }

    public override func visit(_ node: FunctionDeclSyntax) -> SyntaxVisitorContinueKind {
        let name = node.name.text
        let params = node.signature.parameterClause.description.trimmingCharacters(in: .whitespacesAndNewlines)
        let ret = node.signature.returnClause?.description.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let compactSig = "func \(name)\(params) \(ret)".trimmingCharacters(in: .whitespaces)

        let sigData = Data(compactSig.utf8)
        let sliceHash = CanonicalJSONv1.sha256Prefixed(sigData)
        let startOffset = node.positionAfterSkippingLeadingTrivia.utf8Offset
        let endOffset = node.endPositionBeforeTrailingTrivia.utf8Offset
        let ratio = Double(max(sourceBytes.count, 1)) / Double(max(sigData.count, 1))

        extractedSlices.append(
            SwiftSymbolSlice(
                symbolName: name,
                symbolKind: "function",
                signatureOnly: compactSig,
                startUTF8Offset: startOffset,
                endUTF8Offset: endOffset,
                rawFileSHA256: rawFileDigest,
                sliceSHA256: sliceHash,
                taintTier: taintTier,
                byteReductionRatio: (ratio * 100).rounded() / 100
            )
        )
        return .skipChildren
    }

    public override func visit(_ node: StructDeclSyntax) -> SyntaxVisitorContinueKind {
        let name = node.name.text
        let compactSig = "struct \(name)".trimmingCharacters(in: .whitespaces)

        let sigData = Data(compactSig.utf8)
        let sliceHash = CanonicalJSONv1.sha256Prefixed(sigData)
        let startOffset = node.positionAfterSkippingLeadingTrivia.utf8Offset
        let endOffset = node.endPositionBeforeTrailingTrivia.utf8Offset
        let ratio = Double(max(sourceBytes.count, 1)) / Double(max(sigData.count, 1))

        extractedSlices.append(
            SwiftSymbolSlice(
                symbolName: name,
                symbolKind: "struct",
                signatureOnly: compactSig,
                startUTF8Offset: startOffset,
                endUTF8Offset: endOffset,
                rawFileSHA256: rawFileDigest,
                sliceSHA256: sliceHash,
                taintTier: taintTier,
                byteReductionRatio: (ratio * 100).rounded() / 100
            )
        )
        return .skipChildren
    }
}

public enum SwiftSyntaxContextCart {
    /// Parses a Swift source file using Apple SwiftSyntax AST and extracts compact symbol
    /// signatures with dual-digest taint binding (`rawFileSHA256` + `sliceSHA256`).
    public static func sliceSwiftSource(
        _ sourceCode: String,
        taintTier: TaintTier = .tier0Pinned
    ) -> [SwiftSymbolSlice] {
        let rawData = Data(sourceCode.utf8)
        let rawDigest = CanonicalJSONv1.sha256Prefixed(rawData)
        let tree = Parser.parse(source: sourceCode)
        let visitor = SymbolSignatureExtractor(
            sourceBytes: Array(rawData),
            rawFileDigest: rawDigest,
            taintTier: taintTier
        )
        visitor.walk(tree)
        return visitor.extractedSlices
    }
}
