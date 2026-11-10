// swift-tools-version: 5.10
import PackageDescription
let package = Package(name: "CompanionMac", platforms: [.macOS(.v14)], products: [
    .executable(name: "CompanionMac", targets: ["CompanionMac"]),
    .executable(name: "companion-mcp", targets: ["CompanionMCP"])
], targets: [
    .target(name: "CompanionRecorderCore"),
    .executableTarget(name: "CompanionMac", dependencies: ["CompanionRecorderCore"]),
    .executableTarget(name: "CompanionMCP", dependencies: ["CompanionRecorderCore"]),
    .testTarget(name: "CompanionRecorderCoreTests", dependencies: ["CompanionRecorderCore"],resources: [.copy("Fixtures")])
])
