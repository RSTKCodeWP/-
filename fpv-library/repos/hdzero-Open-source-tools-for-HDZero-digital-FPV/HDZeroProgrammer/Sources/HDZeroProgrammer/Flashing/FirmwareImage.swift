import Foundation

/// Prepares a flashable firmware image from whatever the user supplies — a raw
/// `.bin`, a release `.zip`, or a nested zip-in-zip from hd-zero.com. The output
/// is a 1 MiB image (chip size of the W25Q80) padded with 0xFF, exactly the
/// shape the proven manual `dd` + flashrom workflow produced.
enum FirmwareImage {
    static let flashSize = 1024 * 1024            // W25Q80: 1 MiB
    static let vtxMax    = 64 * 1024              // VTX fw must be < 64 KiB

    enum PrepError: LocalizedError {
        case tooLarge(Int)
        case noBinFound
        case unzipFailed(String)
        case readFailed(String)
        var errorDescription: String? {
            switch self {
            case .tooLarge(let n):  return "Firmware is \(n) bytes — larger than the 1 MiB flash."
            case .noBinFound:       return "No HDZERO_TX.bin found inside the archive."
            case .unzipFailed(let s): return "Unzip failed: \(s)"
            case .readFailed(let s):  return "Could not read firmware: \(s)"
            }
        }
    }

    /// Returns the path to a freshly written 1 MiB padded image in a temp dir.
    static func preparePaddedImage(from source: URL) throws -> URL {
        let binURL = try resolveBin(from: source)
        let data: Data
        do { data = try Data(contentsOf: binURL) }
        catch { throw PrepError.readFailed(error.localizedDescription) }

        guard data.count <= flashSize else { throw PrepError.tooLarge(data.count) }

        var padded = Data(repeating: 0xFF, count: flashSize)
        padded.replaceSubrange(0..<data.count, with: data)

        let outDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("hdzero_flash", isDirectory: true)
        try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
        let out = outDir.appendingPathComponent("padded_\(data.count).bin")
        try padded.write(to: out)
        return out
    }

    /// Finds the HDZERO_TX.bin (or the single .bin) inside a source that may be a
    /// .bin, a .zip, or a nested zip. Returns a URL to the actual .bin on disk.
    static func resolveBin(from source: URL) throws -> URL {
        if source.pathExtension.lowercased() == "bin" { return source }

        // Extract into a temp dir and recurse into nested zips.
        let work = FileManager.default.temporaryDirectory
            .appendingPathComponent("hdzero_extract_\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: work, withIntermediateDirectories: true)
        try unzip(source, into: work)

        // Recursively unzip any inner zips, then locate a .bin.
        try expandNestedZips(in: work)
        guard let bin = findBin(in: work) else { throw PrepError.noBinFound }
        return bin
    }

    private static func expandNestedZips(in dir: URL) throws {
        let fm = FileManager.default
        guard let en = fm.enumerator(at: dir, includingPropertiesForKeys: nil) else { return }
        var innerZips: [URL] = []
        for case let u as URL in en where u.pathExtension.lowercased() == "zip" {
            innerZips.append(u)
        }
        for zip in innerZips {
            let sub = zip.deletingPathExtension()
            try? fm.createDirectory(at: sub, withIntermediateDirectories: true)
            try unzip(zip, into: sub)
        }
        // One extra pass handles two levels of nesting (outer → inner → bin).
        if !innerZips.isEmpty { try expandNestedZips(in: dir) }
    }

    private static func findBin(in dir: URL) -> URL? {
        let fm = FileManager.default
        guard let en = fm.enumerator(at: dir, includingPropertiesForKeys: nil) else { return nil }
        var candidates: [URL] = []
        for case let u as URL in en where u.pathExtension.lowercased() == "bin" {
            candidates.append(u)
        }
        // Prefer the canonical name; otherwise the first .bin.
        return candidates.first { $0.lastPathComponent == "HDZERO_TX.bin" } ?? candidates.first
    }

    private static func unzip(_ zip: URL, into dir: URL) throws {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/unzip")
        p.arguments = ["-o", "-q", zip.path, "-d", dir.path]
        let err = Pipe()
        p.standardError = err
        p.standardOutput = Pipe()
        do { try p.run() } catch { throw PrepError.unzipFailed(error.localizedDescription) }
        p.waitUntilExit()
        if p.terminationStatus != 0 {
            let msg = String(decoding: err.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
            throw PrepError.unzipFailed(msg.isEmpty ? "exit \(p.terminationStatus)" : msg)
        }
    }
}
