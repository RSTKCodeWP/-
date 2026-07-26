import Foundation

/// Live Monitor display settings over CH341 I2C (FPGA device 0x65), mirroring
/// read_setting() in ch341.py. Each value is a register on the I2C device.
/// The I2C framing is well-specified, so this panel can work independently of
/// the (unverified) multi-chip flash path.
@MainActor
final class MonitorSettings: ObservableObject {
    static let device7bit: UInt8 = 0x65
    enum Reg: UInt8 {
        case brightness = 0x22, contrast = 0x23, saturation = 0x24,
             backlight = 0x25, cellCount = 0x26, warningCellV = 0x27, osd = 0x28
    }

    @Published var connected = false
    @Published var brightness: Double = 0
    @Published var contrast: Double = 0
    @Published var saturation: Double = 0
    @Published var backlight: Double = 100
    @Published var cellCount: Double = 1
    @Published var warningCellV: Double = 28
    @Published var osd = false
    @Published var fpgaVersion: String = "—"
    @Published var statusMessage = "Not connected"

    /// Open the CH341, read all settings, leave values populated.
    func connectAndRead() async {
        statusMessage = "Connecting…"
        let result: Result<[UInt8], Error> = await Task.detached {
            let dev = CH341Device()
            do {
                try dev.open(); defer { dev.close() }
                let spi = CH341SPI(dev)
                try spi.setStream(mode: 0x80)
                let regs: [UInt8] = [0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0xff]
                var out: [UInt8] = []
                for r in regs { out.append(try spi.readI2C(device7bit: Self.device7bit, reg: r)) }
                return .success(out)
            } catch { return .failure(error) }
        }.value

        switch result {
        case .failure(let e):
            connected = false
            statusMessage = e.localizedDescription
        case .success(let v):
            brightness   = Double(v[0])
            contrast     = Double(v[1])
            saturation   = Double(v[2])
            backlight    = Double(v[3])
            cellCount    = Double(max(v[4], 1))
            warningCellV = Double(v[5])
            osd          = v[6] != 0
            fpgaVersion  = "0x" + String(v[7], radix: 16)
            connected = true
            statusMessage = "Connected · FPGA \(fpgaVersion)"
        }
    }

    /// Write a single register live (open/write/close).
    func write(_ reg: Reg, _ value: UInt8) {
        Task.detached {
            let dev = CH341Device()
            guard (try? dev.open()) != nil else { return }
            defer { dev.close() }
            let spi = CH341SPI(dev)
            try? spi.setStream(mode: 0x80)
            try? spi.writeI2C(device7bit: Self.device7bit, reg: reg.rawValue, value: value)
        }
    }
}
