import XCTest
import CryptoKit
#if canImport(EdgeTelemetryCore)
@testable import EdgeTelemetryCore
#endif

final class EdgeTelemetryNodeTests: XCTestCase {
    func testEdgeTelemetrySigningAndProbes() throws {
        let key = Curve25519.Signing.PrivateKey()
        let (_, envelope) = try EdgeTelemetryReceiptGenerator.generateSignedReceipt(
            privateKey: key,
            nodeId: "andrii’s iPhone (iPhone17,2, arm64e)",
            osVersion: "iOS 26.3 (Build 23D127)",
            sequenceNumber: 1
        )
        XCTAssertTrue(envelope.contains("receipt_body"))
        XCTAssertTrue(envelope.contains("boundary_probes"))
        XCTAssertTrue(envelope.contains("signature_ed25519_hex"))
        print("ON_DEVICE_TEST_RECEIPT_START")
        print(envelope)
        print("ON_DEVICE_TEST_RECEIPT_END")
    }
}
