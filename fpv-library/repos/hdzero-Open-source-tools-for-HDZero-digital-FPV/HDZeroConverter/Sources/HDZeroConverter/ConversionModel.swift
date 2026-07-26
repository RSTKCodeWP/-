import Foundation
import AppKit

// MARK: - Setting option enums

enum FPSOption: String, CaseIterable, Identifiable {
    case keep = "Keep original"
    case f30 = "30"
    case f60 = "60"
    case f90 = "90"
    case f120 = "120"
    var id: String { rawValue }
    var value: Int? {
        switch self {
        case .keep: return nil
        case .f30: return 30
        case .f60: return 60
        case .f90: return 90
        case .f120: return 120
        }
    }
}

enum ResolutionOption: String, CaseIterable, Identifiable {
    case keep = "Keep original"
    case p480 = "854 × 480"
    case p720 = "1280 × 720"
    case p1080 = "1920 × 1080"
    var id: String { rawValue }
    var height: Int? {
        switch self {
        case .keep: return nil
        case .p480: return 480
        case .p720: return 720
        case .p1080: return 1080
        }
    }
}

enum EncoderOption: String, CaseIterable, Identifiable {
    case x264 = "x264 (software)"
    case videotoolbox = "VideoToolbox (hardware)"
    var id: String { rawValue }
    var codec: String { self == .x264 ? "libx264" : "h264_videotoolbox" }
}

enum ProfileOption: String, CaseIterable, Identifiable {
    case baseline, main, high
    var id: String { rawValue }
}

enum LevelOption: String, CaseIterable, Identifiable {
    case auto = "Auto"
    case l40 = "4.0"
    case l41 = "4.1"
    case l42 = "4.2"
    case l51 = "5.1"
    var id: String { rawValue }
    var value: String? { self == .auto ? nil : rawValue }
}

enum AudioOption: String, CaseIterable, Identifiable {
    case aac = "Re-encode AAC"
    case copy = "Copy (passthrough)"
    case remove = "Remove audio"
    var id: String { rawValue }
}

// MARK: - Conversion model

@MainActor
final class ConversionModel: ObservableObject {
    // Files
    @Published var inputURL: URL?
    @Published var outputURL: URL?

    // Video settings
    @Published var fixColorRange: Bool = true
    @Published var fps: FPSOption = .f60
    @Published var resolution: ResolutionOption = .keep
    @Published var encoder: EncoderOption = .x264
    @Published var crf: Double = 20
    @Published var bitrateMbps: Double = 20
    @Published var preset: String = "medium"
    @Published var profile: ProfileOption = .high
    @Published var level: LevelOption = .l42

    // Audio / container
    @Published var audio: AudioOption = .aac
    @Published var audioBitrate: Int = 192
    @Published var faststart: Bool = true

    // Tool paths
    @Published var ffmpegPath: String = ConversionModel.detect("ffmpeg")
    @Published var ffprobePath: String = ConversionModel.detect("ffprobe")

    // Runtime state
    @Published var isRunning = false
    @Published var progress: Double = 0
    @Published var statusMessage = "Idle"
    @Published var etaText = ""
    @Published var logText = ""
    @Published var lastResultSummary = ""

    let presets = ["ultrafast", "superfast", "veryfast", "faster", "fast",
                   "medium", "slow", "slower", "veryslow"]
    let audioBitrates = [128, 192, 256, 320]

    private var process: Process?
    private var outPipe: Pipe?
    private var errPipe: Pipe?
    private var totalDuration: Double = 0
    private var startedAt: Date?
    private var wasCancelled = false
    private var finished = false
    private var stdoutBuffer = ""

    // MARK: Tool detection

    static func detect(_ tool: String) -> String {
        // 1. Prefer the self-contained copy embedded in the app bundle.
        if let res = Bundle.main.resourcePath {
            let bundled = res + "/ffmpeg/" + tool
            if FileManager.default.isExecutableFile(atPath: bundled) { return bundled }
        }
        // 2. Fall back to a system install (Homebrew / usr).
        let candidates = ["/opt/homebrew/bin/", "/usr/local/bin/", "/usr/bin/"]
        for dir in candidates {
            let p = dir + tool
            if FileManager.default.isExecutableFile(atPath: p) { return p }
        }
        return "/opt/homebrew/bin/" + tool
    }

    /// True when ffmpeg is running from inside the app bundle (portable mode).
    var usingBundledFFmpeg: Bool {
        guard let res = Bundle.main.resourcePath else { return false }
        return ffmpegPath.hasPrefix(res + "/ffmpeg/")
    }

    // MARK: Input handling

    func setInput(_ url: URL) {
        inputURL = url
        let base = url.deletingPathExtension().lastPathComponent
        let dir = url.deletingLastPathComponent()
        outputURL = dir.appendingPathComponent("\(base)_compatible.mp4")
        lastResultSummary = ""
        progress = 0
        statusMessage = "Ready"
        logText = ""
        probeDuration(url)
    }

    private func probeDuration(_ url: URL) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: ffprobePath)
        p.arguments = ["-v", "error", "-show_entries", "format=duration",
                       "-of", "default=noprint_wrappers=1:nokey=1", url.path]
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = Pipe()
        do {
            try p.run()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            if let s = String(data: data, encoding: .utf8)?
                .trimmingCharacters(in: .whitespacesAndNewlines),
               let d = Double(s) {
                totalDuration = d
            }
        } catch {
            totalDuration = 0
        }
    }

    // MARK: Command building

    func buildArgs(progressPipe: Bool) -> [String] {
        guard let input = inputURL, let output = outputURL else { return [] }
        var a = ["-y", "-hide_banner"]
        if progressPipe { a += ["-nostats", "-progress", "pipe:1"] }
        a += ["-i", input.path]

        // Video filter chain
        var scaleParts: [String] = []
        if let h = resolution.height { scaleParts += ["w=-2", "h=\(h)"] }
        if fixColorRange { scaleParts += ["in_range=full", "out_range=tv"] }
        var vf: [String] = []
        if !scaleParts.isEmpty { vf.append("scale=" + scaleParts.joined(separator: ":")) }
        vf.append("format=yuv420p")
        if let f = fps.value { vf.append("fps=\(f)") }
        a += ["-vf", vf.joined(separator: ",")]

        // Video codec
        switch encoder {
        case .x264:
            a += ["-c:v", "libx264", "-preset", preset, "-crf", String(Int(crf))]
        case .videotoolbox:
            a += ["-c:v", "h264_videotoolbox", "-b:v", "\(Int(bitrateMbps * 1000))k"]
        }
        a += ["-profile:v", profile.rawValue]
        if let lvl = level.value { a += ["-level", lvl] }
        a += ["-pix_fmt", "yuv420p"]
        if fixColorRange {
            a += ["-color_range", "tv", "-colorspace", "bt709",
                  "-color_primaries", "bt709", "-color_trc", "bt709"]
        }

        // Audio
        switch audio {
        case .aac:    a += ["-c:a", "aac", "-b:a", "\(audioBitrate)k", "-ac", "2"]
        case .copy:   a += ["-c:a", "copy"]
        case .remove: a += ["-an"]
        }

        if faststart { a += ["-movflags", "+faststart"] }
        a += [output.path]
        return a
    }

    func commandPreview() -> String {
        let args = buildArgs(progressPipe: false)
        func quote(_ s: String) -> String {
            if s.contains(" ") || s.contains(",") { return "\"\(s)\"" }
            return s
        }
        return (["ffmpeg"] + args.map(quote)).joined(separator: " ")
    }

    // MARK: Run / cancel

    func start() {
        guard let output = outputURL, inputURL != nil, !isRunning else { return }

        if FileManager.default.fileExists(atPath: output.path) {
            let alert = NSAlert()
            alert.messageText = "Output file already exists"
            alert.informativeText = "\(output.lastPathComponent) will be overwritten. Continue?"
            alert.addButton(withTitle: "Overwrite")
            alert.addButton(withTitle: "Cancel")
            if alert.runModal() != .alertFirstButtonReturn { return }
        }

        wasCancelled = false
        finished = false
        stdoutBuffer = ""
        isRunning = true
        progress = 0
        etaText = ""
        logText = ""
        lastResultSummary = ""
        statusMessage = "Converting…"
        startedAt = Date()

        let p = Process()
        p.executableURL = URL(fileURLWithPath: ffmpegPath)
        p.arguments = buildArgs(progressPipe: true)

        let outPipe = Pipe()
        let errPipe = Pipe()
        p.standardOutput = outPipe
        p.standardError = errPipe
        self.outPipe = outPipe
        self.errPipe = errPipe

        outPipe.fileHandleForReading.readabilityHandler = { [weak self] h in
            let data = h.availableData
            // Empty data signals EOF — clear the handler so it stops firing.
            if data.isEmpty { h.readabilityHandler = nil; return }
            if let s = String(data: data, encoding: .utf8) {
                DispatchQueue.main.async { self?.parseProgress(s) }
            }
        }
        errPipe.fileHandleForReading.readabilityHandler = { [weak self] h in
            let data = h.availableData
            if data.isEmpty { h.readabilityHandler = nil; return }
            if let s = String(data: data, encoding: .utf8) {
                DispatchQueue.main.async { self?.appendLog(s) }
            }
        }

        p.terminationHandler = { [weak self] proc in
            let status = proc.terminationStatus
            DispatchQueue.main.async { self?.finish(status: status) }
        }

        do {
            try p.run()
            process = p
        } catch {
            isRunning = false
            statusMessage = "Failed to launch ffmpeg"
            appendLog("\nError launching ffmpeg at \(ffmpegPath): \(error.localizedDescription)\n")
        }
    }

    func cancel() {
        wasCancelled = true
        process?.terminate()
    }

    // MARK: Output parsing

    private func parseProgress(_ chunk: String) {
        stdoutBuffer += chunk
        let lines = stdoutBuffer.components(separatedBy: "\n")
        stdoutBuffer = lines.last ?? ""
        for line in lines.dropLast() {
            let parts = line.split(separator: "=", maxSplits: 1).map(String.init)
            guard parts.count == 2 else { continue }
            let key = parts[0].trimmingCharacters(in: .whitespaces)
            let val = parts[1].trimmingCharacters(in: .whitespaces)
            switch key {
            case "out_time_us", "out_time_ms":
                if let us = Double(val), totalDuration > 0 {
                    // out_time_us is microseconds; out_time_ms in ffmpeg is also microseconds.
                    updateProgress(seconds: us / 1_000_000.0)
                }
            case "out_time":
                if let t = ConversionModel.parseTime(val), totalDuration > 0 {
                    updateProgress(seconds: t)
                }
            case "progress":
                if val == "end" { progress = 1.0 }
            default:
                break
            }
        }
    }

    private func updateProgress(seconds: Double) {
        let frac = min(max(seconds / totalDuration, 0), 1)
        progress = frac
        if let start = startedAt, frac > 0.01 {
            let elapsed = Date().timeIntervalSince(start)
            let remaining = elapsed / frac - elapsed
            etaText = "ETA " + ConversionModel.formatTime(remaining)
        }
    }

    private func appendLog(_ s: String) {
        logText += s
        if logText.count > 60_000 {
            logText = String(logText.suffix(40_000))
        }
    }

    private func finish(status: Int32) {
        // terminationHandler can race with a final EOF callback — only finish once.
        guard !finished else { return }
        finished = true

        // Stop and release the pipe readers. NOTE: never reassign
        // process.standardOutput here — Process raises an Obj-C exception
        // ("task already launched") and the app would abort.
        outPipe?.fileHandleForReading.readabilityHandler = nil
        errPipe?.fileHandleForReading.readabilityHandler = nil
        outPipe = nil
        errPipe = nil
        process = nil

        isRunning = false
        etaText = ""

        if wasCancelled {
            statusMessage = "Cancelled"
            progress = 0
            return
        }
        if status == 0, let out = outputURL {
            progress = 1.0
            statusMessage = "Done ✓"
            let size = (try? FileManager.default.attributesOfItem(atPath: out.path)[.size] as? Int) ?? nil
            var summary = out.lastPathComponent
            if let outSize = size {
                let outMB = Double(outSize) / 1_048_576.0
                if let inURL = inputURL,
                   let inSize = (try? FileManager.default.attributesOfItem(atPath: inURL.path)[.size]) as? Int {
                    let inMB = Double(inSize) / 1_048_576.0
                    let pct = inMB > 0 ? (1 - outMB / inMB) * 100 : 0
                    summary = String(format: "%.0f MB → %.0f MB  (%.0f%% smaller)", inMB, outMB, pct)
                } else {
                    summary = String(format: "%.0f MB", outMB)
                }
            }
            lastResultSummary = summary
        } else {
            statusMessage = "Failed (exit \(status))"
        }
    }

    // MARK: Helpers

    static func parseTime(_ s: String) -> Double? {
        // HH:MM:SS.micro
        let comps = s.split(separator: ":")
        guard comps.count == 3,
              let h = Double(comps[0]), let m = Double(comps[1]), let sec = Double(comps[2])
        else { return nil }
        return h * 3600 + m * 60 + sec
    }

    static func formatTime(_ seconds: Double) -> String {
        guard seconds.isFinite, seconds >= 0 else { return "—" }
        let s = Int(seconds.rounded())
        let m = s / 60
        let r = s % 60
        if m > 0 { return "\(m)m \(r)s" }
        return "\(r)s"
    }

    func revealOutput() {
        guard let out = outputURL, FileManager.default.fileExists(atPath: out.path) else { return }
        NSWorkspace.shared.activateFileViewerSelecting([out])
    }
}
