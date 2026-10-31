// File: NotaryRPCServer.swift
// Target: iOS 18+ (iPhone 16 Pro Max — Network.framework + SwiftUI Host)

import CryptoKit
import Foundation
import Network
import SwiftUI
import Combine

private func notaryLog(_ msg: String) {
    print(msg)
    fflush(stdout)
}

/// Represents an in-flight T3 request waiting for human FaceID or Veto on the iPhone screen.
public struct PendingT3Approval: Identifiable {
    public let id = UUID()
    public let proposal: T3ActionProposal
    public let canonicalJCSBytes: Data
    public let onDecision: (Result<EnclaveSignedWarrant, Error>) -> Void
}

public enum HumanVetoError: Error, CustomStringConvertible {
    case explicitlyVetoedByOperator

    public var description: String {
        return "HALT_HUMAN_VETOED_ON_IPHONE"
    }
}

@MainActor
public final class NotaryRPCServer: ObservableObject {
    @Published public var activeRequest: PendingT3Approval? = nil
    @Published public var serverStatus: String = "Stopped"

    public let enclavePublicKeyHex: String
    private let cachedPublicKeyData: Data

    private var listener: NWListener?
    private let notary: SovereignEnclaveNotary
    private let port: NWEndpoint.Port

    public init(port: UInt16 = 8080) {
        self.port = NWEndpoint.Port(rawValue: port)!
        let notary = SovereignEnclaveNotary()
        self.notary = notary

        notaryLog("NOTARY_SERVER: Bootstrapping Enclave Key...")
        do {
            let key = try notary.loadOrCreateEnclaveKey()
            let hex = key.publicKey.x963Representation
                .map { String(format: "%02x", $0) }
                .joined()
            self.enclavePublicKeyHex = hex
            self.cachedPublicKeyData = Data(hex.utf8)
            notaryLog("NOTARY_SERVER: Enclave Public Key provisioned: \(hex)")
        } catch {
            notaryLog("NOTARY_SERVER: Enclave Key Provisioning Error: \(error)")
            let errStr = "ERROR:\(error)"
            self.enclavePublicKeyHex = errStr
            self.cachedPublicKeyData = Data(errStr.utf8)
        }
    }

    public func start() {
        notaryLog("NOTARY_SERVER: start() called for port \(port.rawValue)")
        do {
            let params = NWParameters.tcp
            params.allowLocalEndpointReuse = true
            params.includePeerToPeer = true
            let nwListener = try NWListener(using: params, on: port)

            nwListener.stateUpdateHandler = { [weak self] state in
                notaryLog("NOTARY_SERVER: stateUpdateHandler -> \(state)")
                Task { @MainActor in
                    switch state {
                    case .ready:
                        notaryLog("NOTARY_SERVER: Listener READY on port \(self?.port.rawValue ?? 8080)")
                        self?.serverStatus = "Listening on TCP :\(self?.port.rawValue ?? 8080)"
                    case .failed(let err):
                        notaryLog("NOTARY_SERVER: Listener FAILED with error: \(err)")
                        self?.serverStatus = "Failed: \(err.localizedDescription)"
                    case .waiting(let err):
                        notaryLog("NOTARY_SERVER: Listener WAITING with error: \(err)")
                        self?.serverStatus = "Waiting: \(err.localizedDescription)"
                    default:
                        break
                    }
                }
            }

            nwListener.newConnectionHandler = { [weak self] connection in
                notaryLog("NOTARY_SERVER: New connection received from \(connection.endpoint)")
                self?.handleConnection(connection)
            }

            nwListener.start(queue: .global(qos: .userInitiated))
            self.listener = nwListener
            notaryLog("NOTARY_SERVER: nwListener.start() dispatched successfully")
        } catch {
            notaryLog("NOTARY_SERVER: NWListener creation error: \(error)")
            self.serverStatus = "Listener error: \(error.localizedDescription)"
        }
    }

    public func stop() {
        listener?.cancel()
        listener = nil
        serverStatus = "Stopped"
        notaryLog("NOTARY_SERVER: stopped")
    }

    private nonisolated func handleConnection(_ connection: NWConnection) {
        notaryLog("NOTARY_SERVER: handleConnection started for \(connection.endpoint)")
        connection.stateUpdateHandler = { state in
            notaryLog("NOTARY_SERVER: connection state: \(state)")
        }
        connection.start(queue: .global(qos: .userInitiated))
        receiveHTTPRequest(on: connection, accumulated: Data())
    }

    private nonisolated func receiveHTTPRequest(on connection: NWConnection, accumulated: Data) {
        notaryLog("NOTARY_SERVER: receiveHTTPRequest waiting for data on \(connection.endpoint)...")
        connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] chunk, _, isComplete, error in
            guard let self = self else { return }
            notaryLog("NOTARY_SERVER: chunk received: \(chunk?.count ?? 0) bytes, isComplete: \(isComplete), error: \(String(describing: error))")
            if error != nil {
                connection.cancel()
                return
            }

            var buffer = accumulated
            if let chunk = chunk {
                buffer.append(chunk)
            }

            let separator = Data("\r\n\r\n".utf8)
            guard let headerRange = buffer.range(of: separator) else {
                if !isComplete {
                    self.receiveHTTPRequest(on: connection, accumulated: buffer)
                } else {
                    notaryLog("NOTARY_SERVER: complete without header separator, cancelling")
                    connection.cancel()
                }
                return
            }

            let headerData = buffer.subdata(in: 0..<headerRange.lowerBound)
            let bodyStart = headerRange.upperBound
            let headerString = String(data: headerData, encoding: .utf8) ?? ""
            let lines = headerString.components(separatedBy: "\r\n")
            let requestLine = lines.first ?? ""
            notaryLog("NOTARY_SERVER: received HTTP requestLine: '\(requestLine)'")

            // Route 1: GET /pubkey (Public key pinning helper)
            if requestLine.hasPrefix("GET /pubkey") {
                notaryLog("NOTARY_SERVER: serving GET /pubkey immediately (\(self.cachedPublicKeyData.count) bytes)")
                self.sendHTTPResponse(on: connection, status: "200 OK", contentType: "text/plain", body: self.cachedPublicKeyData)
                return
            }

            // Route 2: POST /approve (WYSIWYS Canonical JCS Payload)
            guard requestLine.hasPrefix("POST /approve") else {
                notaryLog("NOTARY_SERVER: unknown endpoint '\(requestLine)' -> 404")
                let errBody = Data("{\"error\":\"HALT_UNKNOWN_ENDPOINT\"}".utf8)
                self.sendHTTPResponse(on: connection, status: "404 Not Found", contentType: "application/json", body: errBody)
                return
            }

            var contentLength = 0
            for line in lines.dropFirst() {
                let parts = line.split(separator: ":", maxSplits: 1)
                if parts.count == 2 && parts[0].trimmingCharacters(in: .whitespaces).lowercased() == "content-length" {
                    contentLength = Int(parts[1].trimmingCharacters(in: .whitespaces)) ?? 0
                }
            }

            let receivedBodyBytes = buffer.count - bodyStart
            notaryLog("NOTARY_SERVER: POST /approve contentLength=\(contentLength), received=\(receivedBodyBytes)")
            if receivedBodyBytes < contentLength && !isComplete {
                self.receiveHTTPRequest(on: connection, accumulated: buffer)
                return
            }

            let canonicalJCSBytes = buffer.subdata(in: bodyStart..<(bodyStart + contentLength))
            guard let proposal = try? JSONDecoder().decode(T3ActionProposal.self, from: canonicalJCSBytes) else {
                notaryLog("NOTARY_SERVER: failed to decode T3ActionProposal -> 400")
                let badBody = Data("{\"error\":\"HALT_INVALID_CANONICAL_JCS_PAYLOAD\"}".utf8)
                self.sendHTTPResponse(on: connection, status: "400 Bad Request", contentType: "application/json", body: badBody)
                return
            }

            notaryLog("NOTARY_SERVER: decoded proposal action=\(proposal.action_type) amount=\(proposal.amount_minor), presenting sheet...")
            Task { @MainActor in
                self.activeRequest = PendingT3Approval(
                    proposal: proposal,
                    canonicalJCSBytes: canonicalJCSBytes,
                    onDecision: { result in
                        switch result {
                        case .success(let warrant):
                            notaryLog("NOTARY_SERVER: FaceID approved, sending warrant")
                            let body = (try? JSONEncoder().encode(warrant)) ?? Data()
                            self.sendHTTPResponse(on: connection, status: "200 OK", contentType: "application/json", body: body)
                        case .failure(let error):
                            notaryLog("NOTARY_SERVER: Veto/Failure error: \(error)")
                            let status = (error as? HumanVetoError) != nil ? "403 Forbidden" : "500 Internal Server Error"
                            let errBody = Data("{\"error\":\"\(error)\"}".utf8)
                            self.sendHTTPResponse(on: connection, status: status, contentType: "application/json", body: errBody)
                        }
                        Task { @MainActor in
                            self.activeRequest = nil
                        }
                    }
                )
            }
        }
    }

    private nonisolated func sendHTTPResponse(
        on connection: NWConnection,
        status: String,
        contentType: String,
        body: Data
    ) {
        let header = "HTTP/1.1 \(status)\r\n" +
            "Content-Type: \(contentType)\r\n" +
            "Content-Length: \(body.count)\r\n" +
            "Connection: close\r\n\r\n"
        var payload = Data(header.utf8)
        payload.append(body)
        notaryLog("NOTARY_SERVER: sending \(payload.count) bytes for status \(status)")
        let context = NWConnection.ContentContext(
            identifier: "httpResponse",
            expiration: 0,
            priority: 1.0,
            isFinal: true,
            antecedent: nil,
            metadata: []
        )
        connection.send(content: payload, contentContext: context, isComplete: true, completion: .contentProcessed { error in
            notaryLog("NOTARY_SERVER: send finished with isFinal=true, error: \(String(describing: error))")
            connection.cancel()
        })
    }

    public nonisolated func signPendingRequest(_ pending: PendingT3Approval) {
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                let (_, warrant) = try self.notary.authorizeT3ActionWithFaceID(
                    canonicalJCSBytes: pending.canonicalJCSBytes
                )
                pending.onDecision(.success(warrant))
            } catch {
                pending.onDecision(.failure(error))
            }
        }
    }
}
