import Foundation

/// HDZero Radio update: programs the ELRS TX (ESP32), ELRS backpack (ESP32-C3),
/// and the STM32 MCU, mirroring program_radio.py + the RADIO_* states in
/// ch341.py. Firmware ships as a zip containing elrs_tx/, elrs_backpack/, and
/// hdzero_radio_stm32.bin.
///
/// ⚠️ Hardware-unverified — serial AT handshakes, esptool ROM flashing, and
/// XMODEM are all reimplemented from scratch and need a real radio to validate.
@MainActor
enum RadioFlasher {

    struct Fail: LocalizedError { let m: String; init(_ m: String){ self.m = m }; var errorDescription: String? { m } }

    /// The HDZero radio's STM32 virtual COM port. On real hardware it enumerates as
    /// "Divimath STM32 Virtual ComPort" (Divimath = HDZero's vendor), NOT
    /// "STMicroelectronics" — so match any of these across vendor/product/path.
    nonisolated static func isRadioSTM(_ i: SerialPort.Info) -> Bool {
        let hay = "\(i.vendorName) \(i.productName) \(i.path)"
        return ["Divimath", "STM32", "STMicro"].contains { hay.localizedCaseInsensitiveContains($0) }
    }
    nonisolated static func findRadioSTM() -> SerialPort.Info? {
        SerialPort.list().first(where: isRadioSTM)
    }

    // MARK: Read / Detect — confirm the radio's serial ports enumerate

    static func detect(controller c: DeviceController) async {
        c.appendLog("Scanning serial ports…\n")
        let ports = SerialPort.list()
        for p in ports { c.appendLog("• \(p.path)  [\(p.vendorName) \(p.productName)]\n") }
        let stm = ports.first(where: isRadioSTM)
        let ch340 = ports.first {
            $0.vendorName.localizedCaseInsensitiveContains("CH340") ||
            $0.productName.localizedCaseInsensitiveContains("CH340") ||
            $0.path.localizedCaseInsensitiveContains("CH340")
        }
        if let stm = stm {
            let extra = ch340 != nil ? " · ELRS (CH340) present" : ""
            c.detected(DeviceInfo(connected: true, chipId: nil, chipName: "STM32 radio", sizeKB: nil,
                                  detail: "Detected radio: STM32 @ \(stm.path)\(extra)"))
        } else if ch340 != nil {
            c.detected(DeviceInfo(connected: true, chipId: nil, chipName: "ELRS (CH340)", sizeKB: nil,
                                  detail: "ELRS (CH340) port present, but no STM32 — radio may be in bootloader."))
        } else {
            c.detected(DeviceInfo(connected: false, chipId: nil, chipName: nil, sizeKB: nil,
                                  detail: "No HDZero radio serial port found — connect the radio via USB and check the cable."))
        }
    }

    static func flash(source: URL, controller c: DeviceController) async {
        c.resetForRun()
        c.phase = .preparing
        c.appendLog("== HDZero Radio update ==\n")

        // Extract the firmware zip into a working dir.
        let root: URL
        do { root = try extractRadioZip(source) }
        catch { c.fail("Could not extract radio firmware: \(error.localizedDescription)"); return }

        let log: @Sendable (String) -> Void = { line in Task { @MainActor in c.appendLog(line) } }
        let progress: @Sendable (OperationPhase, Double) -> Void = { p, f in
            Task { @MainActor in c.phase = p; c.progress = min(max(f, 0), 1) }
        }
        let esptool = c.app?.esptoolPath ?? "esptool"

        let result: Result<Void, Error> = await Task.detached(priority: .userInitiated) {
            do {
                // 1. ELRS TX (ESP32)
                log("\n— ELRS TX (ESP32) —\n")
                try programELRS(chip: "esp32", stmCommand: "ATPGTX", subdir: "elrs_tx",
                                offsets: [("bootloader.bin", 0x1000), ("partitions.bin", 0x8000),
                                          ("boot_app0.bin", 0xe000), ("firmware.bin", 0x10000)],
                                root: root, esptool: esptool, log: log) { progress(.flashing, $0 * 0.33) }

                // 2. ELRS backpack (ESP32-C3)
                log("\n— ELRS backpack (ESP32-C3) —\n")
                try programELRS(chip: "esp32c3", stmCommand: "ATPGBP", subdir: "elrs_backpack",
                                offsets: [("bootloader.bin", 0x0000), ("partitions.bin", 0x8000),
                                          ("boot_app0.bin", 0xe000), ("firmware.bin", 0x10000)],
                                root: root, esptool: esptool, log: log) { progress(.flashing, 0.33 + $0 * 0.33) }

                // 3. STM32 via XMODEM
                log("\n— STM32 (XMODEM) —\n")
                try programSTM32(root: root, log: log) { progress(.flashing, 0.66 + $0 * 0.34) }
                return .success(())
            } catch { return .failure(error) }
        }.value

        switch result {
        case .success:        c.succeed("Radio updated — repower the radio now.")
        case .failure(let e): c.fail(e.localizedDescription)
        }
    }

    // MARK: ELRS (ESP32 / ESP32-C3) via the real esptool (matches the official tool)

    private nonisolated static func programELRS(chip: String, stmCommand: String, subdir: String,
                                    offsets: [(String, Int)], root: URL, esptool: String,
                                    log: @escaping (String) -> Void,
                                    onProgress: (Double) -> Void) throws {
        // Put the radio's ESP into passthrough/bootloader via the STM32 AT command.
        guard let stm = findRadioSTM() else {
            throw Fail("STM32 serial port not found.")
        }
        let stmPort = SerialPort()
        try stmPort.open(stm.path, baud: 115200)
        try stmPort.write("\(stmCommand)\r\n")
        Thread.sleep(forTimeInterval: 0.3)
        stmPort.close()

        // After the AT command the ELRS module re-enumerates as its own USB-serial
        // port. It can take a couple seconds and the bridge chip varies (CH340 on
        // the stock unit, GenesysLogic on others, CP210x, Espressif native USB…),
        // so poll a few seconds across those names.
        let elrsKeywords = ["CH340", "CP210", "CP2102", "Silicon Labs", "USB Serial",
                            "Espressif", "USB JTAG", "USB Single Serial", "wch", "GenesysLogic"]
        var elrs: SerialPort.Info?
        let deadline = Date().addingTimeInterval(6.0)
        while Date() < deadline {
            let ports = SerialPort.list()
            if let p = ports.first(where: { info in
                let hay = "\(info.vendorName) \(info.productName) \(info.path)"
                return elrsKeywords.contains { hay.localizedCaseInsensitiveContains($0) } && !isRadioSTM(info)
            }) { elrs = p; break }
            Thread.sleep(forTimeInterval: 0.5)
        }
        guard let elrs = elrs else {
            let seen = SerialPort.list()
                .map { "\($0.path) [\($0.vendorName) \($0.productName)]" }
                .joined(separator: "; ")
            throw Fail("ELRS serial port not found after \(stmCommand). Ports seen: \(seen.isEmpty ? "none" : seen)")
        }
        log("ELRS port: \(elrs.path) [\(elrs.vendorName) \(elrs.productName)]\n")

        // Hand off to the real esptool (it uploads the stub loader + handles the
        // reset/sync/erase/verify the ROM-only reimplementation couldn't). Mirrors
        // the official tool: esptool --chip <c> --port <p> --baud 460800 write_flash …
        var args = ["--chip", chip, "--port", elrs.path, "--baud", "460800",
                    "--before", "default_reset", "--after", "hard_reset", "write_flash"]
        for (file, offset) in offsets {
            let path = root.appendingPathComponent("\(subdir)/\(file)").path
            guard FileManager.default.fileExists(atPath: path) else { throw Fail("Missing \(subdir)/\(file)") }
            args.append(String(format: "0x%x", offset)); args.append(path)
        }
        try runEsptool(esptool, args, log: log, onProgress: onProgress)
    }

    /// Run the bundled/system esptool, streaming its output to the log and parsing
    /// its "(NN %)" progress.
    private nonisolated static func runEsptool(_ tool: String, _ args: [String],
                                    log: @escaping (String) -> Void,
                                    onProgress: (Double) -> Void) throws {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: tool)
        p.arguments = args
        let pipe = Pipe()
        p.standardOutput = pipe; p.standardError = pipe
        log("$ \(tool) \(args.joined(separator: " "))\n")
        do { try p.run() }
        catch { throw Fail("Could not launch esptool (\(tool)): \(error.localizedDescription). Install esptool (`pip install esptool` or `brew install esptool`).") }
        let h = pipe.fileHandleForReading
        while true {
            let chunk = h.availableData
            if chunk.isEmpty { break }
            guard let s = String(data: chunk, encoding: .utf8) else { continue }
            log(s)
            if let pct = lastPercent(in: s) { onProgress(Double(pct) / 100.0) }
        }
        p.waitUntilExit()
        if p.terminationStatus != 0 {
            throw Fail("esptool exited with status \(p.terminationStatus). See log.")
        }
    }

    /// Last "NN %" seen in an esptool output chunk.
    private nonisolated static func lastPercent(in s: String) -> Int? {
        var result: Int?
        guard let re = try? NSRegularExpression(pattern: #"(\d+)\s*%"#) else { return nil }
        let ns = s as NSString
        re.enumerateMatches(in: s, range: NSRange(location: 0, length: ns.length)) { m, _, _ in
            if let m = m, let r = Range(m.range(at: 1), in: s), let v = Int(s[r]) { result = v }
        }
        return result
    }

    // MARK: STM32 via XMODEM

    private nonisolated static func programSTM32(root: URL, log: @escaping (String) -> Void,
                                     onProgress: (Double) -> Void) throws {
        // Enter bootloader: ATPROG ×3, then reopen and send "XXX".
        guard let stm = findRadioSTM() else {
            throw Fail("STM32 serial port not found.")
        }
        let p1 = SerialPort()
        try p1.open(stm.path, baud: 115200)
        for _ in 0..<3 { try p1.write("ATPROG\r\n") }
        Thread.sleep(forTimeInterval: 0.5)
        p1.close()
        Thread.sleep(forTimeInterval: 0.5)

        guard let stm2 = findRadioSTM() else {
            throw Fail("STM32 port disappeared after ATPROG.")
        }
        let port = SerialPort()
        try port.open(stm2.path, baud: 115200)
        defer { port.close() }
        Thread.sleep(forTimeInterval: 0.2)
        for _ in 0..<3 { try port.write("XXX") }
        Thread.sleep(forTimeInterval: 0.5)
        _ = port.drain(timeout: 0.2)

        let binURL = root.appendingPathComponent("hdzero_radio_stm32.bin")
        guard let data = try? [UInt8](Data(contentsOf: binURL)) else {
            throw Fail("Missing hdzero_radio_stm32.bin")
        }
        log("XMODEM sending \(data.count) bytes…\n")
        try XMODEM.send(data, over: port, onProgress: onProgress)
        for _ in 0..<3 { try port.write("ccc") }
        Thread.sleep(forTimeInterval: 0.5)
    }

    // MARK: Zip extraction

    private nonisolated static func extractRadioZip(_ source: URL) throws -> URL {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("hdzero_radio_\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        // The HDZero radio firmware is a ZIP — but the GitHub asset is named `.bin`
        // (it contains elrs_tx/, elrs_backpack/, hdzero_radio_stm32.bin). Detect by
        // the "PK" zip magic, not the extension, so the `.bin` is extracted too.
        let magic: Data = {
            guard let fh = try? FileHandle(forReadingFrom: source) else { return Data() }
            defer { try? fh.close() }
            return (try? fh.read(upToCount: 2)) ?? Data()
        }()
        if magic == Data([0x50, 0x4B]) {     // "PK"
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/unzip")
            p.arguments = ["-o", "-q", source.path, "-d", dir.path]
            p.standardError = Pipe(); p.standardOutput = Pipe()
            try p.run(); p.waitUntilExit()
            if p.terminationStatus != 0 { throw Fail("unzip exit \(p.terminationStatus)") }
        }
        // The zip may extract into a subfolder; find the dir containing the STM32 bin.
        if FileManager.default.fileExists(atPath: dir.appendingPathComponent("hdzero_radio_stm32.bin").path) {
            return dir
        }
        if let en = FileManager.default.enumerator(at: dir, includingPropertiesForKeys: nil) {
            for case let u as URL in en where u.lastPathComponent == "hdzero_radio_stm32.bin" {
                return u.deletingLastPathComponent()
            }
        }
        return dir
    }
}
