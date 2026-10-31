// tools/ios_edge_node/Sources/JCSCanonicalizer.swift
// RFC 8785 JSON Canonicalization Scheme (JCS) Implementation in Swift
// Strictly deterministic: UTF-16 code unit key sorting, unspaced separators, zero floats.

import Foundation

public enum JCSValue {
    case string(String)
    case integer(Int64)
    case boolean(Bool)
    case null
    case array([JCSValue])
    case object([String: JCSValue])
}

public struct JCSCanonicalizer {
    public static func encode(_ value: JCSValue) -> String {
        switch value {
        case .string(let str):
            return escapeString(str)
        case .integer(let num):
            return String(num)
        case .boolean(let b):
            return b ? "true" : "false"
        case .null:
            return "null"
        case .array(let arr):
            let items = arr.map { encode($0) }
            return "[" + items.joined(separator: ",") + "]"
        case .object(let dict):
            // RFC 8785 Section 3.2.3: Object keys sorted lexicographically by UTF-16 code units
            let sortedKeys = dict.keys.sorted { k1, k2 in
                return compareUTF16(k1, k2)
            }
            let pairs = sortedKeys.map { key in
                escapeString(key) + ":" + encode(dict[key]!)
            }
            return "{" + pairs.joined(separator: ",") + "}"
        }
    }

    private static func compareUTF16(_ a: String, _ b: String) -> Bool {
        let u1 = Array(a.utf16)
        let u2 = Array(b.utf16)
        let minLen = min(u1.count, u2.count)
        for i in 0..<minLen {
            if u1[i] != u2[i] {
                return u1[i] < u2[i]
            }
        }
        return u1.count < u2.count
    }

    private static func escapeString(_ str: String) -> String {
        var result = "\""
        for scalar in str.unicodeScalars {
            switch scalar.value {
            case 0x22: // quote
                result += "\\\""
            case 0x5C: // backslash
                result += "\\\\"
            case 0x08: // backspace
                result += "\\b"
            case 0x0C: // formfeed
                result += "\\f"
            case 0x0A: // newline
                result += "\\n"
            case 0x0D: // carriage return
                result += "\\r"
            case 0x09: // tab
                result += "\\t"
            case 0x00...0x1F: // other control characters
                result += String(format: "\\u%04x", scalar.value)
            default:
                result.append(Character(scalar))
            }
        }
        result += "\""
        return result
    }
}
