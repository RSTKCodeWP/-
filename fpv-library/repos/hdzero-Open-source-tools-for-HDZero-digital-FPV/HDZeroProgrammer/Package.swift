// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "HDZeroProgrammer",
    platforms: [
        .macOS(.v13)
    ],
    targets: [
        .executableTarget(
            name: "HDZeroProgrammer",
            path: "Sources/HDZeroProgrammer"
        )
    ]
)
