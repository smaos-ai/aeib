import Foundation
import CryptoKit
import LocalAuthentication

/// CryptographicApprovalFlow: Manages P256 key generation, FaceID auth, and ECDSA signing
class CryptographicApprovalFlow {

    // MARK: - Key Management

    /// Generate and store P256 private key in Secure Enclave
    static func generateSecureEnclaveKey() -> Result<SecureEnclave.P256.PrivateKey, KeyError> {
        do {
            let privateKey = try SecureEnclave.P256.PrivateKey()
            print("[✓] Secure Enclave P256 private key generated")
            print("[✓] Public key: \(privateKey.publicKey)")
            return .success(privateKey)
        } catch {
            print("[✗] Failed to generate Secure Enclave key: \(error)")
            return .failure(.generationFailed(error))
        }
    }

    // MARK: - FaceID Authentication

    /// Authenticate user with FaceID or fallback
    static func authenticateWithBiometrics(completion: @escaping (Bool, String?) -> Void) {
        let context = LAContext()
        var error: NSError?

        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            let message = error?.localizedDescription ?? "Biometrics not available"
            completion(false, message)
            return
        }

        context.evaluatePolicy(
            .deviceOwnerAuthenticationWithBiometrics,
            localizedReason: "Approve this decision with biometric authentication"
        ) { success, authError in
            if success {
                print("[✓] FaceID authentication successful")
                completion(true, nil)
            } else {
                let message = authError?.localizedDescription ?? "Authentication failed"
                print("[✗] FaceID authentication failed: \(message)")
                completion(false, message)
            }
        }
    }

    // MARK: - Capsule Hashing & Signing

    /// Hash the capsule content with SHA256
    static func hashCapsule(_ content: String) -> Data {
        let data = content.data(using: .utf8) ?? Data()
        return Data(CryptoKit.SHA256.hash(data: data))
    }

    /// Sign capsule_hash with P256 private key from Secure Enclave
    static func signCapsuleHash(
        _ capsuleHash: Data,
        with privateKey: SecureEnclave.P256.PrivateKey
    ) -> Result<Data, SigningError> {
        do {
            let signature = try privateKey.signature(for: capsuleHash)
            print("[✓] ECDSA P256 signature generated: \(signature.rawRepresentation.base64EncodedString())")
            return .success(signature.rawRepresentation)
        } catch {
            print("[✗] Signing failed: \(error)")
            return .failure(.signingFailed(error))
        }
    }

    // MARK: - Vision API Submission

    /// POST signed proof to Vision API /v1/govern endpoint
    static func submitSignedProof(
        capsuleHash: Data,
        signature: Data,
        publicKeyPEM: String,
        to endpoint: URL
    ) async -> Result<GovernanceResponse, APIError> {
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer YOUR_AUTH_TOKEN", forHTTPHeaderField: "Authorization")

        let payload = GovernanceRequest(
            capsule_hash: capsuleHash.base64EncodedString(),
            signature: signature.base64EncodedString(),
            public_key: publicKeyPEM,
            timestamp: ISO8601DateFormatter().string(from: Date()),
            algorithm: "ECDSA-P256"
        )

        do {
            request.httpBody = try JSONEncoder().encode(payload)
        } catch {
            return .failure(.encodingFailed(error))
        }

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return .failure(.invalidResponse)
            }

            if (200...299).contains(httpResponse.statusCode) {
                let governanceResponse = try JSONDecoder().decode(GovernanceResponse.self, from: data)
                print("[✓] Vision API approval successful: \(governanceResponse.approval_id)")
                return .success(governanceResponse)
            } else {
                print("[✗] Vision API error: HTTP \(httpResponse.statusCode)")
                return .failure(.serverError(httpResponse.statusCode))
            }
        } catch {
            print("[✗] Request failed: \(error)")
            return .failure(.networkError(error))
        }
    }

    // MARK: - Complete Flow Orchestration

    /// Execute full approval flow: generate key → auth → hash → sign → submit
    static func executeApprovalFlow(
        capsuleContent: String,
        visionAPIEndpoint: URL,
        completion: @escaping (ApprovalResult) -> Void
    ) {
        // Step 1: Generate or retrieve Secure Enclave key
        let keyResult = generateSecureEnclaveKey()
        guard case .success(let privateKey) = keyResult else {
            completion(.failure(.keyGenerationFailed))
            return
        }

        // Step 2: Prompt for FaceID approval
        authenticateWithBiometrics { success, error in
            guard success else {
                completion(.failure(.biometricAuthFailed(error)))
                return
            }

            // Step 3: Hash capsule content
            let capsuleHash = hashCapsule(capsuleContent)
            print("[✓] Capsule hash: \(capsuleHash.base64EncodedString())")

            // Step 4: Sign with P256
            let signResult = signCapsuleHash(capsuleHash, with: privateKey)
            guard case .success(let signature) = signResult else {
                completion(.failure(.signingFailed))
                return
            }

            // Step 5: Submit to Vision API
            let publicKeyPEM = privateKey.publicKey.pemRepresentation

            Task {
                let apiResult = await submitSignedProof(
                    capsuleHash: capsuleHash,
                    signature: signature,
                    publicKeyPEM: publicKeyPEM,
                    to: visionAPIEndpoint
                )

                switch apiResult {
                case .success(let response):
                    completion(.success(response))
                case .failure(let error):
                    completion(.failure(.apiSubmissionFailed(error)))
                }
            }
        }
    }
}

// MARK: - Data Models

struct GovernanceRequest: Codable {
    let capsule_hash: String
    let signature: String
    let public_key: String
    let timestamp: String
    let algorithm: String
}

struct GovernanceResponse: Codable {
    let approval_id: String
    let status: String
    let verified: Bool
    let timestamp: String
}

// MARK: - Error Types

enum KeyError: Error {
    case generationFailed(Error)
    case storageError(String)
}

enum SigningError: Error {
    case signingFailed(Error)
    case invalidInput
}

enum APIError: Error {
    case encodingFailed(Error)
    case networkError(Error)
    case invalidResponse
    case serverError(Int)
    case decodingFailed(Error)
}

enum ApprovalResult {
    case success(GovernanceResponse)
    case failure(ApprovalFlowError)
}

enum ApprovalFlowError: Error {
    case keyGenerationFailed
    case biometricAuthFailed(String?)
    case signingFailed
    case apiSubmissionFailed(APIError)
    case invalidCapsule
}

// MARK: - Extension: PEM Encoding

extension SecureEnclave.P256.PublicKey {
    var pemRepresentation: String {
        let rawRepresentation = self.rawRepresentation
        let base64 = rawRepresentation.base64EncodedString()

        // ANSI X.962 uncompressed point format
        let pemHeader = "-----BEGIN PUBLIC KEY-----"
        let pemFooter = "-----END PUBLIC KEY-----"

        // Format base64 in 64-character lines
        let lines = base64.chunked(into: 64).joined(separator: "\n")

        return "\(pemHeader)\n\(lines)\n\(pemFooter)"
    }
}

// MARK: - Extension: String Chunking

extension String {
    func chunked(into size: Int) -> [String] {
        stride(from: 0, to: count, by: size).map {
            let start = index(startIndex, offsetBy: $0)
            let end = index(start, offsetBy: size, limitedBy: endIndex) ?? endIndex
            return String(self[start..<end])
        }
    }
}
