import Foundation

/// Fetches and parses firmware release metadata from the hd-zero GitHub repos,
/// mirroring download.py + parse_file.py. All four device families are loaded
/// concurrently on launch.
@MainActor
final class FirmwareCatalog: ObservableObject {
    enum State: Equatable {
        case idle, loading, ready
        case failed(String)
    }

    @Published var state: State = .idle

    // VTX: target name -> (id, [version -> assetURL])
    struct VTXTarget: Identifiable, Hashable {
        let name: String           // e.g. "hdzero_freestyle"
        let id: Int                // VTX_ID from common.h
        var versions: [VersionAsset]
        var displayName: String {
            name.replacingOccurrences(of: "hdzero_", with: "")
                .replacingOccurrences(of: "_", with: " ")
                .capitalized
        }
        var idValue: String { name }   // Identifiable
    }
    struct VersionAsset: Hashable {
        let version: String
        let url: URL
    }

    @Published var vtxTargets: [VTXTarget] = []
    // Monitor / Event VRX / Radio: simple [version -> assetURL]
    @Published var monitorVersions:  [VersionAsset] = []
    @Published var eventVRXVersions: [VersionAsset] = []
    @Published var radioVersions:    [VersionAsset] = []
    @Published var goggle2Versions:  [VersionAsset] = []

    func versions(for kind: DeviceKind) -> [VersionAsset] {
        switch kind {
        case .vtx:      return []   // VTX is per-target, handled separately
        case .monitor:  return monitorVersions
        case .eventVRX: return eventVRXVersions
        case .radio:    return radioVersions
        case .goggle2:  return goggle2Versions
        }
    }

    func refreshAll() async {
        state = .loading
        do {
            async let vtxReleases = fetchReleases(repo: DeviceKind.vtx.releasesRepo)
            async let common      = fetchText(
                "https://raw.githubusercontent.com/hd-zero/hdzero-vtx/main/src/common.h")
            async let mon  = fetchReleases(repo: DeviceKind.monitor.releasesRepo)
            async let evrx = fetchReleases(repo: DeviceKind.eventVRX.releasesRepo)
            async let rad  = fetchReleases(repo: DeviceKind.radio.releasesRepo)
            async let gog2 = fetchReleases(repo: DeviceKind.goggle2.releasesRepo)

            let (vtxRel, commonH, monRel, evrxRel, radRel, gog2Rel) =
                try await (vtxReleases, common, mon, evrx, rad, gog2)

            vtxTargets       = Self.parseVTX(releases: vtxRel, commonHeader: commonH)
            monitorVersions  = Self.flatVersions(monRel)
            eventVRXVersions = Self.flatVersions(evrxRel)
            radioVersions    = Self.flatVersions(radRel)
            goggle2Versions  = Self.flatVersions(gog2Rel)
            state = .ready
        } catch {
            state = .failed((error as NSError).localizedDescription)
        }
    }

    // MARK: - Networking

    private func fetchReleases(repo: String) async throws -> [GHRelease] {
        let url = URL(string: "https://api.github.com/repos/\(repo)/releases")!
        var req = URLRequest(url: url)
        req.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        req.setValue("HDZeroProgrammer", forHTTPHeaderField: "User-Agent")
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw NSError(domain: "catalog", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "GitHub \(repo) unreachable"])
        }
        return try JSONDecoder().decode([GHRelease].self, from: data)
    }

    private func fetchText(_ urlString: String) async throws -> String {
        let (data, _) = try await URLSession.shared.data(from: URL(string: urlString)!)
        return String(decoding: data, as: UTF8.self)
    }

    // MARK: - Parsing (mirrors parse_file.py)

    /// Parse the `#define <NAME> ... VTX_ID 0xNN` block in common.h, between the
    /// `/* define VTX ID start */` and `/* define VTX ID end */` markers, then
    /// attach release assets (zip files) by matching asset base name to target.
    static func parseVTX(releases: [GHRelease], commonHeader: String) -> [VTXTarget] {
        var idByName: [String: Int] = [:]
        var inBlock = false
        // In common.h the `#if defined HDZERO_X` and the following `#define
        // VTX_ID 0xNN` are on SEPARATE lines, so `name` must persist across
        // lines (the Python relies on loop-variable leakage to do this).
        var name: String?
        for rawLine in commonHeader.components(separatedBy: "\n") {
            let line = rawLine.trimmingCharacters(in: .whitespaces)
            if line.contains("define VTX ID start") { inBlock = true; continue }
            if line.contains("define VTX ID end")   { inBlock = false; continue }
            guard inBlock else { continue }
            let words = line.split(separator: " ").map(String.init)
            for (j, w) in words.enumerated() {
                if w == "defined", j + 1 < words.count {
                    name = words[j + 1].lowercased()
                }
                if w == "VTX_ID", j + 1 < words.count, let n = name {
                    let hex = words[j + 1]
                    if hex != "0x00", hex.hasPrefix("0x") {
                        let stripped = String(hex.dropFirst(2))
                        if let v = Int(stripped, radix: 16) { idByName[n] = v }
                    }
                }
            }
        }

        var targets: [String: VTXTarget] = [:]
        for (name, id) in idByName {
            targets[name] = VTXTarget(name: name, id: id, versions: [])
        }
        for rel in releases {
            for asset in rel.assets {
                let urlStr = asset.browser_download_url
                guard let lastSlash = urlStr.lastIndex(of: "/"),
                      let zipRange = urlStr.range(of: ".zip", range: urlStr.index(after: lastSlash)..<urlStr.endIndex)
                else { continue }
                var base = String(urlStr[urlStr.index(after: lastSlash)..<zipRange.lowerBound])
                if base == "hdzero_freestyle" { base = "hdzero_freestyle_v1" }
                guard let url = URL(string: urlStr) else { continue }
                if targets[base] != nil {
                    targets[base]!.versions.append(.init(version: rel.tag_name, url: url))
                }
            }
        }
        return targets.values
            .filter { !$0.versions.isEmpty }
            .sorted { $0.name < $1.name }
    }

    static func flatVersions(_ releases: [GHRelease]) -> [VersionAsset] {
        var out: [VersionAsset] = []
        for rel in releases {
            for asset in rel.assets {
                if let url = URL(string: asset.browser_download_url) {
                    out.append(.init(version: rel.tag_name, url: url))
                }
            }
        }
        return out
    }
}

// MARK: - GitHub release JSON

struct GHRelease: Decodable {
    let tag_name: String
    let assets: [GHAsset]
}
struct GHAsset: Decodable {
    let browser_download_url: String
}
