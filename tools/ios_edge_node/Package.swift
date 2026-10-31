// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "EdgeTelemetryNode",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    products: [
        .library(
            name: "EdgeTelemetryCore",
            targets: ["EdgeTelemetryCore"]
        ),
        .executable(
            name: "EdgeTelemetryNode",
            targets: ["EdgeTelemetryNode"]
        ),
    ],
    targets: [
        .target(
            name: "EdgeTelemetryCore",
            path: "Sources/Core"
        ),
        .executableTarget(
            name: "EdgeTelemetryNode",
            dependencies: ["EdgeTelemetryCore"],
            path: "Sources/CLI"
        ),
        .testTarget(
            name: "EdgeTelemetryNodeTests",
            dependencies: ["EdgeTelemetryCore"],
            path: "Tests/EdgeTelemetryNodeTests"
        ),
    ]
)
