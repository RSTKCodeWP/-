import Foundation

/// VTX flashing via the bundled `flashrom` + CH341A — the proven macOS path:
///   flashrom -p ch341a_spi -c "W25Q80BV/W25Q80DV" -w padded_1MiB.bin
@MainActor
enum FlashromService {

    static let chip = "W25Q80BV/W25Q80DV"
    static let programmer = "ch341a_spi"

    /// Flash a firmware file/zip to the connected VTX.
    static func flash(source: URL, flashrom: String, controller c: DeviceController) async {
        c.resetForRun()
        c.phase = .preparing
        c.appendLog("== HDZero VTX flash ==\n")

        let padded: URL
        do {
            padded = try FirmwareImage.preparePaddedImage(from: source)
            c.appendLog("→ Prepared 1 MiB image: \(padded.lastPathComponent)\n")
        } catch {
            c.fail(error.localizedDescription); return
        }

        // Build the privileged flashrom command. -c is required on flashrom 1.7.
        let cmd = "\(AdminRunner.shellQuote(flashrom)) -p \(programmer) "
            + "-c \(AdminRunner.shellQuote(chip)) -w \(AdminRunner.shellQuote(padded.path))"
        c.appendLog("→ \(cmd)\n\n")
        c.phase = .connecting

        do {
            let result = try await AdminRunner.run(cmd) { line in
                c.appendLog(line)
                Self.updatePhase(from: line, controller: c)
            }
            if result.status == 0 {
                c.succeed("Firmware written & verified — repower the VTX now.")
            } else {
                c.fail(diagnose(result.output, status: result.status))
            }
        } catch {
            c.fail(error.localizedDescription)
        }
    }

    /// Read/Detect: probe the SPI flash WITHOUT writing — confirms the CH341A +
    /// chip are reachable and identifies the chip. `chip == nil` lets flashrom
    /// auto-detect (used by Goggle 2, whose exact chip we're identifying).
    static func probe(chip: String?, flashrom: String, controller c: DeviceController) async {
        var cmd = "\(AdminRunner.shellQuote(flashrom)) -p \(programmer)"
        if let chip { cmd += " -c \(AdminRunner.shellQuote(chip))" }
        c.appendLog("→ \(cmd)\n\n")
        do {
            // flashrom with no operation just probes; it may exit non-zero when
            // several chip definitions share the detected id, but it still prints
            // the "Found ... flash chip" line(s) we parse — so ignore the status.
            let result = try await AdminRunner.run(cmd) { c.appendLog($0) }
            if let (name, kb) = parseFound(result.output) {
                let detail = "Detected: \(name)" + (kb.map { " · \($0) kB" } ?? "")
                c.detected(DeviceInfo(connected: true, chipId: nil, chipName: name,
                                      sizeKB: kb, detail: detail))
            } else {
                c.detected(DeviceInfo(connected: false, chipId: nil, chipName: nil, sizeKB: nil,
                    detail: "No flash chip detected — check the CH341A clip/cable is seated and the device is powered."))
            }
        } catch {
            c.fail(error.localizedDescription)
        }
    }

    /// Explicit standalone verify of an already-flashed chip against an image.
    static func verify(source: URL, flashrom: String, controller c: DeviceController) async {
        c.resetForRun()
        c.phase = .preparing
        c.appendLog("== Verify VTX firmware ==\n")
        let padded: URL
        do { padded = try FirmwareImage.preparePaddedImage(from: source) }
        catch { c.fail(error.localizedDescription); return }
        c.phase = .verifying
        let cmd = "\(AdminRunner.shellQuote(flashrom)) -p \(programmer) "
            + "-c \(AdminRunner.shellQuote(chip)) -v \(AdminRunner.shellQuote(padded.path))"
        c.appendLog("→ \(cmd)\n\n")
        do {
            let result = try await AdminRunner.run(cmd) { c.appendLog($0); Self.updatePhase(from: $0, controller: c) }
            if result.status == 0 { c.succeed("Verified — flash matches the image.") }
            else { c.fail(diagnose(result.output, status: result.status)) }
        } catch { c.fail(error.localizedDescription) }
    }

    /// Parse `Found <maker> flash chip "<name>" (<N> kB...` from flashrom output.
    private static func parseFound(_ output: String) -> (name: String, sizeKB: Int?)? {
        for line in output.components(separatedBy: "\n") where line.contains("Found") && line.contains("flash chip") {
            guard let q1 = line.firstIndex(of: "\""),
                  let q2 = line[line.index(after: q1)...].firstIndex(of: "\"") else { continue }
            let name = String(line[line.index(after: q1)..<q2])
            var kb: Int? = nil
            if let paren = line.range(of: "(", range: q2..<line.endIndex) {
                let after = line[paren.upperBound...]
                let digits = after.prefix { $0.isNumber }
                if after.contains("kB"), let v = Int(digits) { kb = v }
            }
            return (name, kb)
        }
        return nil
    }

    /// Read the current firmware off the VTX into a user-chosen file (backup).
    static func backup(to destination: URL, flashrom: String, controller c: DeviceController) async {
        c.resetForRun()
        c.phase = .connecting
        c.appendLog("== Backup current VTX firmware ==\n")
        let cmd = "\(AdminRunner.shellQuote(flashrom)) -p \(programmer) "
            + "-c \(AdminRunner.shellQuote(chip)) -r \(AdminRunner.shellQuote(destination.path))"
        c.appendLog("→ \(cmd)\n\n")
        do {
            let result = try await AdminRunner.run(cmd) { line in
                c.appendLog(line)
                Self.updatePhase(from: line, controller: c)
            }
            if result.status == 0 {
                c.succeed("Backup saved to \(destination.lastPathComponent)")
            } else {
                c.fail(diagnose(result.output, status: result.status))
            }
        } catch {
            c.fail(error.localizedDescription)
        }
    }

    // MARK: Output interpretation

    private static func updatePhase(from line: String, controller c: DeviceController) {
        let l = line.lowercased()
        if l.contains("erasing") || l.contains("erase/write") {
            c.phase = .erasing
        } else if l.contains("writing") {
            c.phase = .flashing
        } else if l.contains("verifying") {
            c.phase = .verifying
        } else if l.contains("reading") {
            c.phase = .flashing
        }
    }

    private static func diagnose(_ output: String, status: Int32) -> String {
        let o = output.lowercased()
        if o.contains("no eeprom/flash device found") || o.contains("could not find") {
            return "No flash chip detected. Check the CH341A clip is seated on the VTX and the VTX is powered."
        }
        if o.contains("no programmer") || o.contains("ch341a_spi") && o.contains("error") {
            return "CH341A programmer not found on USB. Replug it and try again."
        }
        if o.contains("verifying") && o.contains("failed") {
            return "Verification failed — the write did not match. Do NOT repower; try flashing again."
        }
        return "flashrom exited with status \(status). See log for details."
    }
}
