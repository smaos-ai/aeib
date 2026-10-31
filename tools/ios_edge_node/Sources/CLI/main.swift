// tools/ios_edge_node/Sources/CLI/main.swift
// CLI Entry point for EdgeTelemetryNode

import Foundation
import CryptoKit
#if canImport(EdgeTelemetryCore)
import EdgeTelemetryCore
#endif

let nodeId = "andrii’s iPhone (iPhone17,2, arm64e)"
let osVersion = "iOS 26.3 (Build 23D127)"
let sequenceNumber: Int64 = 1

let key = Curve25519.Signing.PrivateKey()

do {
    let (_, envelope) = try EdgeTelemetryReceiptGenerator.generateSignedReceipt(
        privateKey: key,
        nodeId: nodeId,
        osVersion: osVersion,
        sequenceNumber: sequenceNumber
    )
    print("--- BEGIN SOVEREIGN EDGE TELEMETRY RECEIPT ---")
    print(envelope)
    print("--- END SOVEREIGN EDGE TELEMETRY RECEIPT ---")
} catch {
    fputs("Error generating edge telemetry: \(error)\n", stderr)
    exit(1)
}
