// swift-tools-version: 6.0
// Copyright 2026 SovereignNexus Project
// Licensed under the Apache License, Version 2.0 (the "License");

import PackageDescription

let package = Package(
    name: "AEIBAppleKit",
    platforms: [
        .macOS(.v14),
        .iOS(.v17),
        .visionOS(.v1),
    ],
    products: [
        .library(
            name: "AEIBGateXPC",
            targets: ["AEIBGateXPC"]
        ),
    ],
    dependencies: [],
    targets: [
        .target(
            name: "AEIBGateXPC",
            dependencies: [],
            path: "Sources/AEIBGateXPC"
        ),
        .testTarget(
            name: "AEIBGateXPCTests",
            dependencies: ["AEIBGateXPC"],
            path: "Tests/AEIBGateXPCTests"
        ),
    ]
)
