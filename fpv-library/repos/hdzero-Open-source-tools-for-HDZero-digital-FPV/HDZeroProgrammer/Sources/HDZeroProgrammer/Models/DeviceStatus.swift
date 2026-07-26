import Foundation

// MARK: - High-level phase reported to the UI for any device operation.
// This is a SwiftUI-friendly distillation of the Python `ch341_status` /
// `download_status` state machines (global_var.py). We don't need every raw
// transition in the UI — we need: are we idle, connecting, downloading,
// flashing (with progress), done, or failed.

enum OperationPhase: Equatable {
    case idle
    case connecting          // looking for the device on USB/serial
    case downloading         // fetching firmware from GitHub
    case preparing           // unzip / pad / parse firmware
    case erasing             // flash erase in progress
    case flashing            // writing firmware (progress 0…1)
    case verifying           // read-back / CRC check
    case done(String)        // success summary
    case failed(String)      // error summary

    var isBusy: Bool {
        switch self {
        case .idle, .done, .failed: return false
        default: return true
        }
    }
}

// MARK: - The device families this tool programs.

enum DeviceKind: String, CaseIterable, Identifiable {
    case vtx        = "VTX"
    case monitor    = "Monitor"
    case eventVRX   = "Event VRX"
    case radio      = "Radio"
    case goggle2    = "Goggle 2"

    var id: String { rawValue }

    /// hd-zero GitHub repo whose releases hold this device's firmware.
    var releasesRepo: String {
        switch self {
        case .vtx:      return "hd-zero/hdzero-vtx"
        case .monitor:  return "hd-zero/monitor"
        case .eventVRX: return "hd-zero/event-vrx"
        case .radio:    return "hd-zero/hdzero-radio"
        case .goggle2:  return "hd-zero/hdzero-goggle2"
        }
    }

    /// Which hardware transport programs this device.
    var transport: Transport {
        switch self {
        case .vtx:                  return .flashromSPI      // single W25Q80 chip
        case .monitor, .eventVRX:   return .ch341Native      // multi-chip via GPIO
        case .radio:                return .serial           // XMODEM + esptool
        case .goggle2:              return .flashromSPI      // CH341A SPI to the goggle's firmware socket
        }
    }
}

// MARK: - Result of a Read/Detect probe (shown in the UI before flashing).

/// What a "Read / Detect device" probe found. `connected == false` means the
/// programmer/cable couldn't talk to a chip (loose clip, unpowered device, etc.).
struct DeviceInfo: Equatable {
    var connected: Bool
    var chipId: Int?          // JEDEC RDID (native CH341) when available
    var chipName: String?     // human chip/family name
    var sizeKB: Int?          // flash size in kB when known
    var detail: String        // one-line summary for the status row
}

enum Transport {
    case flashromSPI    // bundled flashrom -p ch341a_spi  (proven path)
    case ch341Native    // native IOKit CH341 driver with GPIO bank-switch
    case serial         // USB-serial: STM32 XMODEM / ESP32 esptool
}

// MARK: - Firmware source selection.

enum FirmwareSource: Equatable {
    case online(version: String, url: URL)   // download from GitHub release asset
    case local(URL)                          // user-picked file on disk
    case none
}
