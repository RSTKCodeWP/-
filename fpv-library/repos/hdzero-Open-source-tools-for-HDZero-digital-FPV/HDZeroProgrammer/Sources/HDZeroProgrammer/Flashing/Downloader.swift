import Foundation

/// Downloads a firmware asset to a temp file and returns its local URL.
enum Downloader {
    static func download(_ url: URL) async throws -> URL {
        var req = URLRequest(url: url)
        req.setValue("HDZeroProgrammer", forHTTPHeaderField: "User-Agent")
        let (tmp, resp) = try await URLSession.shared.download(for: req)
        guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw NSError(domain: "download", code: 2,
                          userInfo: [NSLocalizedDescriptionKey: "HTTP error fetching \(url.lastPathComponent)"])
        }
        // Preserve the original filename/extension so downstream unzip logic works.
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("hdzero_dl_\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let dest = dir.appendingPathComponent(url.lastPathComponent)
        try FileManager.default.moveItem(at: tmp, to: dest)
        return dest
    }
}
