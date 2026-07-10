// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "EarningsCrossManager",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "EarningsCrossManager", targets: ["EarningsCrossManager"])],
    targets: [.executableTarget(name: "EarningsCrossManager", path: "Sources/EarningsCrossManager")]
)
