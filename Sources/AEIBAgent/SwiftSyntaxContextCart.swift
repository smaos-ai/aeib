// File: Sources/AEIBAgent/SwiftSyntaxContextCart.swift
// Copyright 2026 SovereignNexus Project
// Licensed under the Apache License, Version 2.0 (the "License");
// Compile with Swift 6.0+: swift test -Xswiftc -strict-concurrency=complete

import CryptoKit
import Foundation

public enum SymbolKind: String, Sendable, Codable {
    case `struct` = "STRUCT"
    case `class` = "CLASS"
    case `actor` = "ACTOR"
    case `protocol` = "PROTOCOL"
    case `enum` = "ENUM"
    case `function` = "FUNCTION"
    case `initializer` = "INITIALIZER"
    case `property` = "PROPERTY"
    case `typealias` = "TYPEALIAS"
    case `extension` = "EXTENSION"
}

public struct ASTSymbol: Sendable, Codable, Equatable {
    public let name: String
    public let kind: SymbolKind
    public let accessLevel: String
    public let signature: String
    public let lineStart: Int
    public let lineEnd: Int

    public init(
        name: String,
        kind: SymbolKind,
        accessLevel: String,
        signature: String,
        lineStart: Int,
        lineEnd: Int
    ) {
        self.name = name
        self.kind = kind
        self.accessLevel = accessLevel
        self.signature = signature
        self.lineStart = lineStart
        self.lineEnd = lineEnd
    }
}

public struct SlicedASTResult: Sendable, Codable {
    public let originalFileDigestSHA256: String
    public let slicedDigestSHA256: String
    public let rawCharacterCount: Int
    public let boundedCharacterCount: Int
    public let rawEstimatedTokens: Int
    public let boundedEstimatedTokens: Int
    public let reductionRatio: Double
    public let reductionPercentage: Double
    public let symbols: [ASTSymbol]
    public let slicedSignaturesView: String

    public init(
        originalFileDigestSHA256: String,
        slicedDigestSHA256: String,
        rawCharacterCount: Int,
        boundedCharacterCount: Int,
        rawEstimatedTokens: Int,
        boundedEstimatedTokens: Int,
        reductionRatio: Double,
        reductionPercentage: Double,
        symbols: [ASTSymbol],
        slicedSignaturesView: String
    ) {
        self.originalFileDigestSHA256 = originalFileDigestSHA256
        self.slicedDigestSHA256 = slicedDigestSHA256
        self.rawCharacterCount = rawCharacterCount
        self.boundedCharacterCount = boundedCharacterCount
        self.rawEstimatedTokens = rawEstimatedTokens
        self.boundedEstimatedTokens = boundedEstimatedTokens
        self.reductionRatio = reductionRatio
        self.reductionPercentage = reductionPercentage
        self.symbols = symbols
        self.slicedSignaturesView = slicedSignaturesView
    }
}

/// Swift ContextCart AST Token Slicer.
/// Extracts high-level symbol declarations, signatures, and protocol conformances
/// while stripping function/method implementations, large literals, and comment bloat.
public struct SwiftSyntaxContextCart: Sendable {
    public let tokenBudgetCeiling: Int

    public init(tokenBudgetCeiling: Int = 1_500) {
        self.tokenBudgetCeiling = tokenBudgetCeiling
    }

    /// Estimates token count using standard 1 token ~= 4 UTF-8 characters heuristic.
    public static func estimateTokens(for text: String) -> Int {
        let utf8Count = text.utf8.count
        return max(1, (utf8Count + 3) / 4)
    }

    /// Computes SHA-256 hex digest of a string.
    public static func sha256Hex(_ input: String) -> String {
        let digest = SHA256.hash(data: Data(input.utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    /// Slices raw Swift or C/Obj-C source code down to an AST signature outline.
    public func slice(source: String, filename: String = "Source.swift") -> SlicedASTResult {
        let rawTokens = Self.estimateTokens(for: source)
        let rawSha256 = Self.sha256Hex(source)

        let parsedSymbols = parseDeclarations(from: source)
        let renderedSignatures = renderSignatureView(
            symbols: parsedSymbols,
            filename: filename,
            sourceDigest: rawSha256
        )

        let boundedTokens = Self.estimateTokens(for: renderedSignatures)
        let boundedSha256 = Self.sha256Hex(renderedSignatures)

        let ratio = (boundedTokens > 0) ? (Double(rawTokens) / Double(boundedTokens)) : 1.0
        let percentage = (rawTokens > 0)
            ? (Double(rawTokens - boundedTokens) / Double(rawTokens) * 100.0)
            : 0.0

        return SlicedASTResult(
            originalFileDigestSHA256: rawSha256,
            slicedDigestSHA256: boundedSha256,
            rawCharacterCount: source.count,
            boundedCharacterCount: renderedSignatures.count,
            rawEstimatedTokens: rawTokens,
            boundedEstimatedTokens: boundedTokens,
            reductionRatio: (ratio * 100).rounded() / 100,
            reductionPercentage: (percentage * 100).rounded() / 100,
            symbols: parsedSymbols,
            slicedSignaturesView: renderedSignatures
        )
    }

    private func parseDeclarations(from source: String) -> [ASTSymbol] {
        var symbols: [ASTSymbol] = []
        let lines = source.components(separatedBy: .newlines)

        var insideMultilineComment = false
        var currentBraceDepth = 0

        for (index, rawLine) in lines.enumerated() {
            let lineNum = index + 1
            let trimmed = rawLine.trimmingCharacters(in: .whitespaces)

            // Track block comments
            if trimmed.contains("/*") {
                insideMultilineComment = true
            }
            if insideMultilineComment {
                if trimmed.contains("*/") {
                    insideMultilineComment = false
                }
                continue
            }

            // Skip line comments and empty lines
            if trimmed.isEmpty || trimmed.hasPrefix("//") {
                continue
            }

            // Track brace depth
            let openCount = trimmed.filter { $0 == "{" }.count
            let closeCount = trimmed.filter { $0 == "}" }.count
            let priorDepth = currentBraceDepth
            currentBraceDepth += (openCount - closeCount)
            if currentBraceDepth < 0 { currentBraceDepth = 0 }

            // Only parse declarations at root or direct type member level (depth <= 1)
            if priorDepth > 1 {
                continue
            }

            if let symbol = parseLineForSymbol(trimmed, lineNum: lineNum) {
                symbols.append(symbol)
            }
        }

        return symbols
    }

    private func parseLineForSymbol(_ line: String, lineNum: Int) -> ASTSymbol? {
        let accessLevel = extractAccessLevel(from: line)
        let stripped = stripAttributesAndAccess(from: line)

        // Patterns: struct, class, actor, protocol, enum, extension
        if let match = matchTypeDeclaration(stripped) {
            return ASTSymbol(
                name: match.name,
                kind: match.kind,
                accessLevel: accessLevel,
                signature: cleanSignature(line),
                lineStart: lineNum,
                lineEnd: lineNum
            )
        }

        // Functions / Initializers
        if stripped.hasPrefix("func ") || stripped.contains(" func ") {
            let funcName = extractIdentifier(after: "func ", in: stripped)
            return ASTSymbol(
                name: funcName,
                kind: .function,
                accessLevel: accessLevel,
                signature: cleanSignature(line),
                lineStart: lineNum,
                lineEnd: lineNum
            )
        }

        if stripped.hasPrefix("init(") || stripped.hasPrefix("init?(") || stripped.hasPrefix("init!(") {
            return ASTSymbol(
                name: "init",
                kind: .initializer,
                accessLevel: accessLevel,
                signature: cleanSignature(line),
                lineStart: lineNum,
                lineEnd: lineNum
            )
        }

        if stripped.hasPrefix("typealias ") {
            let aliasName = extractIdentifier(after: "typealias ", in: stripped)
            return ASTSymbol(
                name: aliasName,
                kind: .typealias,
                accessLevel: accessLevel,
                signature: cleanSignature(line),
                lineStart: lineNum,
                lineEnd: lineNum
            )
        }

        // Properties (let / var at type scope)
        if stripped.hasPrefix("public let ") || stripped.hasPrefix("public var ") ||
           stripped.hasPrefix("let ") || stripped.hasPrefix("var ") {
            let propName = extractPropertyIdentifier(in: stripped)
            if !propName.isEmpty {
                return ASTSymbol(
                    name: propName,
                    kind: .property,
                    accessLevel: accessLevel,
                    signature: cleanSignature(line),
                    lineStart: lineNum,
                    lineEnd: lineNum
                )
            }
        }

        return nil
    }

    private func extractAccessLevel(from line: String) -> String {
        let tokens = line.split(separator: " ")
        let valid = ["public", "open", "package", "internal", "fileprivate", "private"]
        for t in tokens {
            if valid.contains(String(t)) {
                return String(t)
            }
        }
        return "internal"
    }

    private func stripAttributesAndAccess(from line: String) -> String {
        var str = line
        let prefixes = [
            "@Sendable", "@MainActor", "@objc", "@frozen", "@inlinable", "@discardableResult",
            "public", "open", "package", "internal", "fileprivate", "private",
            "final", "mutating", "nonmutating", "override", "static", "weak", "unowned",
            "async", "throws"
        ]
        var changed = true
        while changed {
            changed = false
            for p in prefixes {
                let withSpace = p + " "
                if str.hasPrefix(withSpace) {
                    str = String(str.dropFirst(withSpace.count)).trimmingCharacters(in: .whitespaces)
                    changed = true
                }
            }
        }
        return str
    }

    private func matchTypeDeclaration(_ line: String) -> (name: String, kind: SymbolKind)? {
        let kinds: [(prefix: String, kind: SymbolKind)] = [
            ("actor ", .actor),
            ("struct ", .struct),
            ("class ", .class),
            ("protocol ", .protocol),
            ("enum ", .enum),
            ("extension ", .extension)
        ]

        for item in kinds {
            if line.hasPrefix(item.prefix) {
                let name = extractIdentifier(after: item.prefix, in: line)
                return (name, item.kind)
            }
        }
        return nil
    }

    private func extractIdentifier(after prefix: String, in text: String) -> String {
        guard let range = text.range(of: prefix) else { return "anonymous" }
        let remainder = text[range.upperBound...].trimmingCharacters(in: .whitespaces)
        let delimiterChars: CharacterSet = .alphanumerics.union(CharacterSet(charactersIn: "_")).inverted
        if let delimRange = remainder.rangeOfCharacter(from: delimiterChars) {
            return String(remainder[..<delimRange.lowerBound])
        }
        return remainder
    }

    private func extractPropertyIdentifier(in line: String) -> String {
        let parts = line.split(separator: ":")
        if let first = parts.first {
            let words = first.split(separator: " ")
            if let last = words.last {
                return String(last)
            }
        }
        return ""
    }

    private func cleanSignature(_ line: String) -> String {
        var sig = line
        if let braceIndex = sig.firstIndex(of: "{") {
            sig = String(sig[..<braceIndex]).trimmingCharacters(in: .whitespaces)
        }
        return sig
    }

    private func renderSignatureView(
        symbols: [ASTSymbol],
        filename: String,
        sourceDigest: String
    ) -> String {
        var out = "// ContextCart-MCP Apple Native Sliced AST [Target: \(filename)] [SHA256: \(sourceDigest.prefix(16))...]\n"
        for sym in symbols {
            out += "\(sym.signature)\n"
        }
        return out
    }
}
