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
            name: "AEIBCore",
            targets: ["AEIBCore"]
        ),
        .library(
            name: "AEIBGateXPC",
            targets: ["AEIBGateXPC"]
        ),
        .library(
            name: "AEIBAgent",
            targets: ["AEIBAgent"]
        ),
    ],
    dependencies: [],
    targets: [
        .target(
            name: "AEIBCore",
            dependencies: [],
            path: "Sources/AEIBCore"
        ),
        .target(
            name: "AEIBGateXPC",
            dependencies: ["AEIBCore"],
            path: "Sources/AEIBGateXPC"
        ),
        .target(
            name: "AEIBAgent",
            dependencies: ["AEIBCore", "AEIBGateXPC"],
            path: "Sources/AEIBAgent"
        ),
        .testTarget(
            name: "AEIBTests",
            dependencies: ["AEIBCore", "AEIBGateXPC", "AEIBAgent"],
            path: "Tests/AEIBTests"
        ),
    ]
)
