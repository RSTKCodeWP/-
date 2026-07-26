// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "HDZeroConverter",
    platforms: [
        .macOS(.v13)
    ],
    targets: [
        .executableTarget(
            name: "HDZeroConverter",
            path: "Sources/HDZeroConverter"
        )
    ]
)
