// File: Sources/AEIBCore/SwiftSyntaxAST.swift
// Copyright 2026 SovereignNexus Project
// Licensed under the Apache License, Version 2.0 (the "License");
// Compile with Swift 6.0+: swift test -Xswiftc -strict-concurrency=complete

import Foundation

public enum SyntaxVisitorViewMode: Sendable {
    case sourceAccurate
}

public enum SyntaxVisitorContinueKind: Sendable {
    case skipChildren
    case visitChildren
}

public struct SourceLocation: Sendable, Equatable {
    public let utf8Offset: Int

    public init(utf8Offset: Int) {
        self.utf8Offset = utf8Offset
    }
}

public struct SyntaxIdentifier: Sendable, Equatable {
    public let text: String

    public init(text: String) {
        self.text = text
    }
}

public struct ParameterClause: Sendable, Equatable {
    public let description: String

    public init(description: String) {
        self.description = description
    }
}

public struct ReturnClause: Sendable, Equatable {
    public let description: String

    public init(description: String) {
        self.description = description
    }
}

public struct FunctionSignatureSyntax: Sendable, Equatable {
    public let parameterClause: ParameterClause
    public let returnClause: ReturnClause?

    public init(parameterClause: ParameterClause, returnClause: ReturnClause?) {
        self.parameterClause = parameterClause
        self.returnClause = returnClause
    }
}

public struct FunctionDeclSyntax: Sendable, Equatable {
    public let name: SyntaxIdentifier
    public let signature: FunctionSignatureSyntax
    public let positionAfterSkippingLeadingTrivia: SourceLocation
    public let endPositionBeforeTrailingTrivia: SourceLocation

    public init(
        name: SyntaxIdentifier,
        signature: FunctionSignatureSyntax,
        positionAfterSkippingLeadingTrivia: SourceLocation,
        endPositionBeforeTrailingTrivia: SourceLocation
    ) {
        self.name = name
        self.signature = signature
        self.positionAfterSkippingLeadingTrivia = positionAfterSkippingLeadingTrivia
        self.endPositionBeforeTrailingTrivia = endPositionBeforeTrailingTrivia
    }
}

public struct StructDeclSyntax: Sendable, Equatable {
    public let name: SyntaxIdentifier
    public let positionAfterSkippingLeadingTrivia: SourceLocation
    public let endPositionBeforeTrailingTrivia: SourceLocation

    public init(
        name: SyntaxIdentifier,
        positionAfterSkippingLeadingTrivia: SourceLocation,
        endPositionBeforeTrailingTrivia: SourceLocation
    ) {
        self.name = name
        self.positionAfterSkippingLeadingTrivia = positionAfterSkippingLeadingTrivia
        self.endPositionBeforeTrailingTrivia = endPositionBeforeTrailingTrivia
    }
}

public struct SourceFileSyntax: Sendable {
    public let functions: [FunctionDeclSyntax]
    public let structs: [StructDeclSyntax]

    public init(functions: [FunctionDeclSyntax], structs: [StructDeclSyntax]) {
        self.functions = functions
        self.structs = structs
    }
}

open class SyntaxVisitor: @unchecked Sendable {
    public let viewMode: SyntaxVisitorViewMode

    public init(viewMode: SyntaxVisitorViewMode) {
        self.viewMode = viewMode
    }

    open func visit(_ node: FunctionDeclSyntax) -> SyntaxVisitorContinueKind {
        return .visitChildren
    }

    open func visit(_ node: StructDeclSyntax) -> SyntaxVisitorContinueKind {
        return .visitChildren
    }

    public func walk(_ tree: SourceFileSyntax) {
        for fn in tree.functions {
            _ = visit(fn)
        }
        for st in tree.structs {
            _ = visit(st)
        }
    }
}

public enum Parser: Sendable {
    public static func parse(source: String) -> SourceFileSyntax {
        var functions: [FunctionDeclSyntax] = []
        var structs: [StructDeclSyntax] = []

        let lines = source.components(separatedBy: "\n")
        var currentOffset = 0

        for line in lines {
            let lineStart = currentOffset
            let lineEnd = lineStart + line.utf8.count
            currentOffset = lineEnd + 1 // +1 for the newline

            let trimmed = line.trimmingCharacters(in: .whitespaces)

            // Skip comments and empty lines
            if trimmed.hasPrefix("//") || trimmed.hasPrefix("/*") || trimmed.isEmpty {
                continue
            }

            // Function declaration match
            if let funcRange = line.range(of: "func ") {
                let leadingTriviaCount = line[..<funcRange.lowerBound].utf8.count
                let startPos = lineStart + leadingTriviaCount
                let afterFunc = line[funcRange.upperBound...]

                if let parenOpen = afterFunc.firstIndex(of: "(") {
                    let nameStr = String(afterFunc[..<parenOpen]).trimmingCharacters(in: .whitespaces)
                    let remaining = afterFunc[parenOpen...]

                    let paramEndIndex = remaining.firstIndex(of: ")") ?? remaining.endIndex
                    let nextAfterParam = (paramEndIndex < remaining.endIndex) ? remaining.index(after: paramEndIndex) : remaining.endIndex
                    let paramStr = String(remaining[...paramEndIndex])

                    var retClause: ReturnClause? = nil
                    let afterParamStr = String(remaining[nextAfterParam...])
                    if let arrowRange = afterParamStr.range(of: "->") {
                        var returnTypeStr = String(afterParamStr[arrowRange.upperBound...])
                        if let brace = returnTypeStr.firstIndex(of: "{") {
                            returnTypeStr = String(returnTypeStr[..<brace])
                        }
                        returnTypeStr = returnTypeStr.trimmingCharacters(in: .whitespaces)
                        retClause = ReturnClause(description: "-> " + returnTypeStr)
                    }

                    let endPos = lineEnd

                    let fnDecl = FunctionDeclSyntax(
                        name: SyntaxIdentifier(text: nameStr),
                        signature: FunctionSignatureSyntax(
                            parameterClause: ParameterClause(description: paramStr),
                            returnClause: retClause
                        ),
                        positionAfterSkippingLeadingTrivia: SourceLocation(utf8Offset: startPos),
                        endPositionBeforeTrailingTrivia: SourceLocation(utf8Offset: endPos)
                    )
                    functions.append(fnDecl)
                }
            } else if let structRange = line.range(of: "struct ") {
                let leadingTriviaCount = line[..<structRange.lowerBound].utf8.count
                let startPos = lineStart + leadingTriviaCount
                let afterStruct = line[structRange.upperBound...]
                var namePart = afterStruct
                if let colon = namePart.firstIndex(of: ":") {
                    namePart = namePart[..<colon]
                }
                if let brace = namePart.firstIndex(of: "{") {
                    namePart = namePart[..<brace]
                }
                let structName = String(namePart).trimmingCharacters(in: .whitespaces)

                let stDecl = StructDeclSyntax(
                    name: SyntaxIdentifier(text: structName),
                    positionAfterSkippingLeadingTrivia: SourceLocation(utf8Offset: startPos),
                    endPositionBeforeTrailingTrivia: SourceLocation(utf8Offset: lineEnd)
                )
                structs.append(stDecl)
            }
        }

        return SourceFileSyntax(functions: functions, structs: structs)
    }
}
