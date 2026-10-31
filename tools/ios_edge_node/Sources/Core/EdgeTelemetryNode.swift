// tools/ios_edge_node/Sources/EdgeTelemetryNode.swift
// Edge Telemetry Node using Apple CryptoKit & RFC 8785 JCS
// Evaluated under the stated model: zero mock crypto, real Ed25519 signing, sandbox boundary checks.

import Foundation
import CryptoKit

public struct EdgeTelemetryReceiptGenerator {
    public static func runProbes() -> [String: JCSValue] {
        var probes: [String: JCSValue] = [:]
        
        // Probe 1: Attempt to write to /etc/sovereign_canary.txt (must fail with EPERM / sandbox denial)
        let etcPath = "/etc/sovereign_canary.txt"
        let etcWriteFailed: Bool
        do {
            try "canary".write(toFile: etcPath, atomically: true, encoding: .utf8)
            etcWriteFailed = false
        } catch {
            etcWriteFailed = true
        }
        probes["probe_root_fs_write_blocked"] = .boolean(etcWriteFailed)
        
        // Probe 2: Attempt path traversal out of App sandbox ../
        let traversalPath = "../../private/var/sovereign_canary.txt"
        let traversalFailed: Bool
        do {
            try "canary".write(toFile: traversalPath, atomically: true, encoding: .utf8)
            traversalFailed = false
        } catch {
            traversalFailed = true
        }
        probes["probe_path_traversal_blocked"] = .boolean(traversalFailed)
        
        // Probe 3: Check memory limits (physical memory in bytes, integer)
        let mem = ProcessInfo.processInfo.physicalMemory
        probes["physical_memory_bytes"] = .integer(Int64(mem))
        
        // Probe 4: Thermal state (0=nominal, 1=fair, 2=serious, 3=critical)
        let thermal = ProcessInfo.processInfo.thermalState.rawValue
        probes["thermal_state_raw"] = .integer(Int64(thermal))
        
        return probes
    }

    public static func generateSignedReceipt(
        privateKey: Curve25519.Signing.PrivateKey,
        nodeId: String,
        osVersion: String,
        sequenceNumber: Int64
    ) throws -> (canonicalJson: String, receiptDictJson: String) {
        let probes = runProbes()
        
        // 1. Build receipt_body (strictly no floats, integer unix epoch)
        let nowEpoch = Int64(Date().timeIntervalSince1970)
        let pubKeyRaw = privateKey.publicKey.rawRepresentation
        let pubKeyHex = pubKeyRaw.map { String(format: "%02x", $0) }.joined()
        
        var bodyFields: [String: JCSValue] = [:]
        bodyFields["node_id"] = .string(nodeId)
        bodyFields["os_version"] = .string(osVersion)
        bodyFields["sequence_number"] = .integer(sequenceNumber)
        bodyFields["timestamp_epoch_s"] = .integer(nowEpoch)
        bodyFields["signer_pubkey_hex"] = .string(pubKeyHex)
        bodyFields["boundary_probes"] = .object(probes)
        bodyFields["schema_version"] = .string("aeib.edge.telemetry.v1")
        
        let canonicalBodyStr = JCSCanonicalizer.encode(.object(bodyFields))
        guard let canonicalBodyData = canonicalBodyStr.data(using: .utf8) else {
            throw NSError(domain: "EdgeTelemetry", code: 1, userInfo: [NSLocalizedDescriptionKey: "UTF8 conversion failed"])
        }
        
        // 2. Compute SHA-256 CAID of canonicalBody
        let hash = SHA256.hash(data: canonicalBodyData)
        let caidHex = hash.map { String(format: "%02x", $0) }.joined()
        let fullCaid = "sha256:" + caidHex
        
        // 3. Real Ed25519 signature over canonicalBodyData using Apple CryptoKit
        let signature = try privateKey.signature(for: canonicalBodyData)
        let sigHex = signature.map { String(format: "%02x", $0) }.joined()
        
        // 4. Build final envelope
        var envelopeFields: [String: JCSValue] = [:]
        envelopeFields["receipt_body"] = .object(bodyFields)
        envelopeFields["caid"] = .string(fullCaid)
        envelopeFields["signature_ed25519_hex"] = .string(sigHex)
        envelopeFields["envelope_version"] = .string("1.0")
        
        let canonicalEnvelopeStr = JCSCanonicalizer.encode(.object(envelopeFields))
        return (canonicalBodyStr, canonicalEnvelopeStr)
    }
}
