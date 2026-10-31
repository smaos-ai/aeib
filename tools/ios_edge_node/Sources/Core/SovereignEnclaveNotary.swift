// File: SovereignEnclaveNotary.swift
// Target: iOS 18+ (iPhone 16 Pro Max — A18 Pro Secure Enclave)
// Implements: NIST P-256 (secp256r1) ECDSA-SHA256 hardware signing locked to FaceID

import CryptoKit
import Foundation
import LocalAuthentication
import Security

public enum EnclaveNotaryError: Error, CustomStringConvertible {
    case secureEnclaveUnavailable
    case accessControlCreationFailed
    case invalidCanonicalJCSPayload
    case signatureGenerationFailed(String)

    public var description: String {
        switch self {
        case .secureEnclaveUnavailable:
            return "HALT_SECURE_ENCLAVE_HARDWARE_UNAVAILABLE"
        case .accessControlCreationFailed:
            return "HALT_ACCESS_CONTROL_CREATION_FAILED"
        case .invalidCanonicalJCSPayload:
            return "HALT_INVALID_CANONICAL_JCS_PAYLOAD"
        case .signatureGenerationFailed(let reason):
            return "HALT_ENCLAVE_SIGN_FAILED:\(reason)"
        }
    }
}

/// Exact structure parsed from the Mac's RFC 8785 JCS canonical bytes (WYSIWYS).
public struct T3ActionProposal: Codable, Equatable {
    public let action_type: String
    public let amount_minor: Int
    public let attempt_fence: Int
    public let expires_at_epoch_sec: Int
    public let intent_caid: String
    public let operation_id: String
    public let target_resource: String

    public init(
        action_type: String,
        amount_minor: Int,
        attempt_fence: Int,
        expires_at_epoch_sec: Int,
        intent_caid: String,
        operation_id: String,
        target_resource: String
    ) {
        self.action_type = action_type
        self.amount_minor = amount_minor
        self.attempt_fence = attempt_fence
        self.expires_at_epoch_sec = expires_at_epoch_sec
        self.intent_caid = intent_caid
        self.operation_id = operation_id
        self.target_resource = target_resource
    }
}

/// Cryptographic warrant returned from the iPhone 16 Pro Max to the Mac M3 Pro.
public struct EnclaveSignedWarrant: Codable {
    public let canonical_payload_utf8: String
    public let payload_sha256_caid: String
    public let public_key_x963_hex: String
    public let signature_der_hex: String
    public let algorithm: String

    public init(
        canonical_payload_utf8: String,
        payload_sha256_caid: String,
        public_key_x963_hex: String,
        signature_der_hex: String,
        algorithm: String
    ) {
        self.canonical_payload_utf8 = canonical_payload_utf8
        self.payload_sha256_caid = payload_sha256_caid
        self.public_key_x963_hex = public_key_x963_hex
        self.signature_der_hex = signature_der_hex
        self.algorithm = algorithm
    }
}

public final class SovereignEnclaveNotary {
    private let keyTag = "com.sovereignnexus.notary.p256.key"

    public init() {}

    /// Provisions or loads the hardware-bound P-256 key inside the A18 Pro Secure Enclave.
    public func loadOrCreateEnclaveKey() throws -> SecureEnclave.P256.Signing.PrivateKey {
        guard SecureEnclave.isAvailable else {
            throw EnclaveNotaryError.secureEnclaveUnavailable
        }

        if let savedData = UserDefaults.standard.data(forKey: keyTag) {
            return try SecureEnclave.P256.Signing.PrivateKey(dataRepresentation: savedData)
        }

        var error: Unmanaged<CFError>?
        guard let accessControl = SecAccessControlCreateWithFlags(
            kCFAllocatorDefault,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            [.privateKeyUsage, .biometryCurrentSet], // Strict FaceID only; no passcode fallback
            &error
        ) else {
            throw EnclaveNotaryError.accessControlCreationFailed
        }

        let privateKey = try SecureEnclave.P256.Signing.PrivateKey(accessControl: accessControl)
        UserDefaults.standard.set(privateKey.dataRepresentation, forKey: keyTag)
        return privateKey
    }

    /// Parses the canonical JCS bytes for display, triggers FaceID, and signs the exact bytes.
    public func authorizeT3ActionWithFaceID(
        canonicalJCSBytes: Data
    ) throws -> (proposal: T3ActionProposal, warrant: EnclaveSignedWarrant) {
        guard let utf8String = String(data: canonicalJCSBytes, encoding: .utf8),
              let proposal = try? JSONDecoder().decode(T3ActionProposal.self, from: canonicalJCSBytes) else {
            throw EnclaveNotaryError.invalidCanonicalJCSPayload
        }

        let authContext = LAContext()
        authContext.localizedReason = "Authorize T3 Irreversible Action: \(proposal.action_type) on \(proposal.target_resource)"
        authContext.localizedFallbackTitle = "" // Explicitly hide passcode fallback button

        let savedKey = try loadOrCreateEnclaveKey()
        let boundKey = try SecureEnclave.P256.Signing.PrivateKey(
            dataRepresentation: savedKey.dataRepresentation,
            authenticationContext: authContext
        )

        do {
            // Hardware ECDSA P-256 signature computed inside the A18 Pro Secure Enclave
            let signature = try boundKey.signature(for: canonicalJCSBytes)
            let digest = SHA256.hash(data: canonicalJCSBytes)
            let digestHex = digest.map { String(format: "%02x", $0) }.joined()
            let pubKeyHex = boundKey.publicKey.x963Representation.map { String(format: "%02x", $0) }.joined()
            let sigDerHex = signature.derRepresentation.map { String(format: "%02x", $0) }.joined()

            let warrant = EnclaveSignedWarrant(
                canonical_payload_utf8: utf8String,
                payload_sha256_caid: "sha256:\(digestHex)",
                public_key_x963_hex: pubKeyHex,
                signature_der_hex: sigDerHex,
                algorithm: "ECDSA_P256_SHA256_SECURE_ENCLAVE"
            )
            return (proposal, warrant)
        } catch {
            throw EnclaveNotaryError.signatureGenerationFailed(error.localizedDescription)
        }
    }
}
