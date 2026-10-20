// File: Sources/AEIBCore/CoreTypes.swift
// Copyright 2026 SovereignNexus Project
// Licensed under the Apache License, Version 2.0 (the "License");
// Compile with Swift 6.0+: swift test -Xswiftc -strict-concurrency=complete

import CryptoKit
import Foundation

public enum TaintTier: UInt8, Sendable, Codable {
    case tier0Pinned = 0
    case tier1Internal = 1
    case tier2UntrustedExternal = 2
}

public enum AEIBError: Error, Sendable, Equatable {
    case keyCustodyFailure(reason: String)
    case invalidState(reason: String)
    case unauthorizedDispatch(reason: String)
    case timeoutOrIndeterminate(reason: String)
}

public enum CanonicalJSONv1: Sendable {
    public static func sha256Prefixed(_ data: Data) -> String {
        let digest = SHA256.hash(data: data)
        return "sha256:" + digest.map { String(format: "%02x", $0) }.joined()
    }

    public static func sha256Hex(_ data: Data) -> String {
        let digest = SHA256.hash(data: data)
        return digest.map { String(format: "%02x", $0) }.joined()
    }
}
