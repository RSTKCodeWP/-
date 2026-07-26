import Foundation
import SwiftUI

/// Central app state: shared firmware catalog, bundled-tool detection, and the
/// four per-device controllers. Mirrors the role of `main_window.py`'s globals,
/// but as a SwiftUI ObservableObject.
@MainActor
final class AppState: ObservableObject {
    @Published var selectedTab: DeviceKind = .vtx

    let catalog = FirmwareCatalog()

    // One controller per device family.
    let vtx      = DeviceController(kind: .vtx)
    let monitor  = DeviceController(kind: .monitor)
    let eventVRX = DeviceController(kind: .eventVRX)
    let radio    = DeviceController(kind: .radio)
    let goggle2  = DeviceController(kind: .goggle2)

    private var allControllers: [DeviceController] { [vtx, monitor, eventVRX, radio, goggle2] }

    /// Path to the flashrom binary used by the VTX path. Prefer the copy bundled
    /// inside the .app; fall back to a Homebrew install for `swift run` dev.
    let flashromPath: String = AppState.detectFlashrom()

    /// Path to the real `esptool` used by the Radio ELRS path (matches the official
    /// HDZero tool, which shells out to esptool for its robust stub-loader flashing).
    let esptoolPath: String = AppState.detectEsptool()

    /// True if any device is mid-operation — used to lock tab switching.
    var anyBusy: Bool {
        allControllers.contains { $0.phase.isBusy }
    }

    init() {
        for c in allControllers { c.app = self }
    }

    func controller(for kind: DeviceKind) -> DeviceController {
        switch kind {
        case .vtx:      return vtx
        case .monitor:  return monitor
        case .eventVRX: return eventVRX
        case .radio:    return radio
        case .goggle2:  return goggle2
        }
    }

    func loadCatalog() async {
        await catalog.refreshAll()
    }

    // MARK: Tool detection

    static func detectFlashrom() -> String {
        if let res = Bundle.main.resourcePath {
            let bundled = res + "/flashrom/flashrom"
            if FileManager.default.isExecutableFile(atPath: bundled) { return bundled }
        }
        for p in ["/opt/homebrew/sbin/flashrom", "/opt/homebrew/bin/flashrom",
                  "/usr/local/sbin/flashrom", "/usr/local/bin/flashrom",
                  "/usr/bin/flashrom"] {
            if FileManager.default.isExecutableFile(atPath: p) { return p }
        }
        return "/opt/homebrew/sbin/flashrom"
    }

    static func detectEsptool() -> String {
        if let res = Bundle.main.resourcePath {
            let bundled = res + "/esptool/esptool"
            if FileManager.default.isExecutableFile(atPath: bundled) { return bundled }
        }
        for p in ["/opt/homebrew/bin/esptool", "/opt/homebrew/bin/esptool.py",
                  "/usr/local/bin/esptool", "/usr/local/bin/esptool.py"] {
            if FileManager.default.isExecutableFile(atPath: p) { return p }
        }
        return "esptool"
    }
}

/// Per-device operation state + log. The actual flashing work lives in the
/// transport services (FlashromService / CH341 / RadioService); this holds the
/// observable UI state and the selected firmware source.
@MainActor
final class DeviceController: ObservableObject {
    let kind: DeviceKind
    weak var app: AppState?

    @Published var source: FirmwareSource = .none
    @Published var phase: OperationPhase = .idle
    @Published var progress: Double = 0          // 0…1 during .flashing
    @Published var log: String = ""
    @Published var info: DeviceInfo?             // last Read/Detect result (nil = not probed)

    // VTX-specific: chosen target name + version (drives the asset URL).
    @Published var vtxTarget: String?
    @Published var selectedVersion: String?

    init(kind: DeviceKind) { self.kind = kind }

    func appendLog(_ s: String) {
        log += s
        if log.count > 80_000 { log = String(log.suffix(50_000)) }
    }

    func resetForRun() {
        progress = 0
        log = ""
        phase = .connecting
    }

    func fail(_ message: String) {
        appendLog("\n✗ \(message)\n")
        phase = .failed(message)
    }

    func succeed(_ summary: String) {
        progress = 1
        phase = .done(summary)
    }

    /// Record a Read/Detect result + finish the operation accordingly.
    func detected(_ found: DeviceInfo) {
        info = found
        if found.connected { phase = .done(found.detail) }
        else { fail(found.detail) }
    }

    /// Read/Detect entry point — confirms the programmer/cable can reach the device
    /// and reads its chip/id, dispatching by transport. (No write happens.)
    func detect() async {
        guard let app = app else { return }
        info = nil
        progress = 0
        log = ""
        phase = .connecting
        appendLog("== Read / Detect \(kind.rawValue) ==\n")
        switch kind.transport {
        case .flashromSPI:
            // VTX knows its chip; Goggle 2 (and unknown chips) auto-detect with no -c.
            let chip: String? = (kind == .vtx) ? FlashromService.chip : nil
            await FlashromService.probe(chip: chip, flashrom: app.flashromPath, controller: self)
        case .ch341Native:
            await CH341Flasher.detect(kind: kind, controller: self)
        case .serial:
            await RadioFlasher.detect(controller: self)
        }
    }
}
