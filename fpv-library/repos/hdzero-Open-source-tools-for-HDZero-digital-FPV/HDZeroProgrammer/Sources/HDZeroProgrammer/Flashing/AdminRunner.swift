import Foundation

/// Runs a shell command as root via a single Authentication Services prompt
/// (`osascript … with administrator privileges`), exactly like the proven
/// reference tool. flashrom needs root for raw USB access to the CH341A.
///
/// To give the UI a live log (osascript itself only returns final output), the
/// command's stdout+stderr are redirected to a temp file that we tail while the
/// privileged process runs.
enum AdminRunner {

    struct Result {
        let status: Int32
        let output: String
    }

    /// Run `command` as root, streaming its output to `onLine` as it appears.
    /// Returns the exit status and the full captured output.
    static func run(_ command: String,
                    onLine: @escaping (String) -> Void) async throws -> Result {
        let logURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("hdzero_admin_\(UUID().uuidString).log")
        FileManager.default.createFile(atPath: logURL.path, contents: nil)

        // The privileged shell writes everything to logURL and records the real
        // exit code so we can recover it after osascript returns.
        let statusURL = logURL.appendingPathExtension("status")
        let wrapped = "{ \(command) ; } > \(shellQuote(logURL.path)) 2>&1 ; "
            + "echo $? > \(shellQuote(statusURL.path))"

        // Tail the log file on a background task while osascript runs.
        let tailer = Task { await tail(logURL, onLine: onLine) }

        let osa = Process()
        osa.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        let appleScript = "do shell script \"\(escapeForAppleScript(wrapped))\" with administrator privileges"
        osa.arguments = ["-e", appleScript]
        let osaErr = Pipe()
        osa.standardError = osaErr
        osa.standardOutput = Pipe()

        try osa.run()
        await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
            osa.terminationHandler = { _ in cont.resume() }
        }
        tailer.cancel()

        // Drain any remaining log content and read the recorded status.
        let finalOutput = (try? String(contentsOf: logURL, encoding: .utf8)) ?? ""
        var status: Int32 = osa.terminationStatus
        if let s = try? String(contentsOf: statusURL, encoding: .utf8),
           let code = Int32(s.trimmingCharacters(in: .whitespacesAndNewlines)) {
            status = code
        } else if status == 0 {
            // osascript itself failed (e.g. user cancelled auth) → surface stderr.
            let err = String(decoding: osaErr.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
            if err.contains("-128") {
                throw NSError(domain: "admin", code: -128,
                              userInfo: [NSLocalizedDescriptionKey: "Authorization cancelled."])
            }
        }
        try? FileManager.default.removeItem(at: logURL)
        try? FileManager.default.removeItem(at: statusURL)
        return Result(status: status, output: finalOutput)
    }

    /// Poll the log file for new bytes and emit them line-wise until cancelled.
    private static func tail(_ url: URL, onLine: @escaping (String) -> Void) async {
        var offset: UInt64 = 0
        var carry = ""
        while !Task.isCancelled {
            if let h = try? FileHandle(forReadingFrom: url) {
                try? h.seek(toOffset: offset)
                let data = h.readDataToEndOfFile()
                offset += UInt64(data.count)
                try? h.close()
                if !data.isEmpty {
                    carry += String(decoding: data, as: UTF8.self)
                    while let nl = carry.firstIndex(of: "\n") {
                        let line = String(carry[..<nl])
                        carry = String(carry[carry.index(after: nl)...])
                        let out = line
                        await MainActor.run { onLine(out + "\n") }
                    }
                }
            }
            try? await Task.sleep(nanoseconds: 250_000_000)
        }
        if !carry.isEmpty {
            let out = carry
            await MainActor.run { onLine(out) }
        }
    }

    // MARK: Quoting helpers

    static func shellQuote(_ s: String) -> String {
        "'" + s.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }

    /// Escape a string to live inside an AppleScript double-quoted literal.
    private static func escapeForAppleScript(_ s: String) -> String {
        s.replacingOccurrences(of: "\\", with: "\\\\")
         .replacingOccurrences(of: "\"", with: "\\\"")
    }
}
