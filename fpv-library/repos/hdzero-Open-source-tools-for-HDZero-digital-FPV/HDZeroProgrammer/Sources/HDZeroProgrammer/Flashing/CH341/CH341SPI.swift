import Foundation

/// Protocol layer over CH341Device — the native equivalent of the CH341DLL.DLL
/// functions the Python tool calls (SetStream, StreamSPI4, SetOutput, ReadI2C,
/// SetDelaymS). Opcodes/framing follow flashrom's ch341a_spi.c and ch341prog.
///
/// ⚠️ Hardware-unverified. The SPI/I2C framing is well-specified; the `setOutput`
/// (0xA1) packet used for flash bank-switching is NOT published in open source
/// and is implemented best-effort here — capture it from a Windows USB sniff if
/// Monitor / Event-VRX flashing misbehaves.
final class CH341SPI {

    // Top-level command opcodes
    private let CMD_SET_OUTPUT: UInt8 = 0xA1
    private let CMD_SPI_STREAM: UInt8 = 0xA8
    private let CMD_I2C_STREAM: UInt8 = 0xAA
    private let CMD_UIO_STREAM: UInt8 = 0xAB
    // I2C sub-commands
    private let I2C_STM_STA: UInt8 = 0x74
    private let I2C_STM_STO: UInt8 = 0x75
    private let I2C_STM_OUT: UInt8 = 0x80
    private let I2C_STM_IN:  UInt8 = 0xC0
    private let I2C_STM_SET: UInt8 = 0x60
    private let I2C_STM_END: UInt8 = 0x00
    private let I2C_STM_MS:  UInt8 = 0x50
    // UIO sub-commands
    private let UIO_STM_IN:  UInt8 = 0x00
    private let UIO_STM_DIR: UInt8 = 0x40
    private let UIO_STM_OUT: UInt8 = 0x80
    private let UIO_STM_END: UInt8 = 0x20

    let dev: CH341Device
    /// When true (SetStream bit7 / MSB-first SPI flash mode), each SPI byte must
    /// be bit-reversed because the CH341 shifts LSB-first.
    private var bitReverse = true

    init(_ dev: CH341Device) { self.dev = dev }

    // MARK: SetStream

    /// CH341SetStream(mode): configure SPI speed/bit-order. Only the low 3 bits
    /// reach the chip; bit7 (MSB-first) is emulated by software bit reversal.
    func setStream(mode: UInt8) throws {
        bitReverse = (mode & 0x80) != 0
        try dev.bulkOut([CMD_I2C_STREAM, I2C_STM_SET | (mode & 0x07), I2C_STM_END])
    }

    // MARK: SPI (4-wire, with chip-select)

    /// CH341StreamSPI4(chipSelect, length, buffer). chipSelect: 0x80=CS0(D0),
    /// 0x81=CS1(D1), 0x82=CS2(D2). Full-duplex: returns the bytes clocked in.
    @discardableResult
    func streamSPI4(chipSelect: UInt8, _ data: [UInt8]) throws -> [UInt8] {
        let csIndex = Int(chipSelect & 0x03)
        try csAssert(csIndex)
        defer { try? csDeassert() }

        var result: [UInt8] = []
        result.reserveCapacity(data.count)
        var i = 0
        // Max 31 data bytes per packet (1 byte is the SPI_STREAM opcode).
        while i < data.count {
            let chunk = Array(data[i..<min(i + 31, data.count)])
            var packet: [UInt8] = [CMD_SPI_STREAM]
            packet.append(contentsOf: chunk.map { bitReverse ? Self.reverse($0) : $0 })
            try dev.bulkOut(packet)
            let resp = try dev.bulkIn(length: chunk.count)
            result.append(contentsOf: resp.map { bitReverse ? Self.reverse($0) : $0 })
            i += chunk.count
        }
        return result
    }

    /// Assert chip-select for the given index (D0/D1/D2 driven low, others high).
    private func csAssert(_ index: Int) throws {
        // Idle level = 0x37 (all CS high); pull the selected CS bit low.
        let level = UInt8(0x37 & ~(1 << index))
        try dev.bulkOut([CMD_UIO_STREAM, UIO_STM_OUT | (level & 0x3F),
                         UIO_STM_DIR | 0x3F, UIO_STM_END])
    }
    private func csDeassert() throws {
        try dev.bulkOut([CMD_UIO_STREAM, UIO_STM_OUT | 0x37, UIO_STM_END])
    }

    // MARK: SetOutput (GPIO bank-switch) — ⚠️ unverified A1 framing

    /// CH341SetOutput(enable, dirOut, dataOut). Drives the CH341 D0..D15 lines.
    /// The HDZero board uses the upper byte (D8..D15) to select which flash chip
    /// is active (flash_switch0/1/2). The exact 0xA1 packet layout is not public;
    /// this reconstruction packs the documented field order. VERIFY via USB sniff.
    func setOutput(enable: UInt32, dirOut: UInt32, dataOut: UInt32) throws {
        // Best-effort 11-byte SET_OUTPUT packet (WCH CH341 field order):
        //   [0]=0xA1 [1]=enable
        //   [2]=data D15-D8  [3]=data D7-D0
        //   [4]=dir  D15-D8  [5]=dir  D7-D0
        //   remaining bytes zero-padded.
        var p = [UInt8](repeating: 0, count: 11)
        p[0] = CMD_SET_OUTPUT
        p[1] = UInt8(enable & 0xFF)
        p[2] = UInt8((dataOut >> 8) & 0xFF)
        p[3] = UInt8(dataOut & 0xFF)
        p[4] = UInt8((dirOut >> 8) & 0xFF)
        p[5] = UInt8(dirOut & 0xFF)
        try dev.bulkOut(p)
    }

    // The four flash-select states from ch341.py (CH341SetOutput(0,0x03,0x0000FF00,X)).
    func flashSwitch0() throws { try setOutput(enable: 0x03, dirOut: 0x0000FF00, dataOut: 0x4300) }
    func flashSwitch1() throws { try setOutput(enable: 0x03, dirOut: 0x0000FF00, dataOut: 0x8300) }
    func flashSwitch2() throws { try setOutput(enable: 0x03, dirOut: 0x0000FF00, dataOut: 0xC800) }
    func flashRelease() throws { try setOutput(enable: 0x03, dirOut: 0x0000FF00, dataOut: 0xC200) }

    /// Event-VRX flash selects: CH341SetOutput(0x03, 0xffffffff, 0xffff40ff/0xffff80ff).
    func flashSet5680() throws { try setOutput(enable: 0x03, dirOut: 0xFFFFFFFF, dataOut: 0xFFFF40FF) }
    func flashSetFPGA() throws { try setOutput(enable: 0x03, dirOut: 0xFFFFFFFF, dataOut: 0xFFFF80FF) }

    // MARK: SPI flash primitives (mirror ch341.py)

    func flashReadID() throws -> Int {
        let r = try streamSPI4(chipSelect: 0x80, [0x9f, 0x9f, 0x9f, 0x9f, 0x9f, 0x9f])
        guard r.count >= 4 else { return 0 }
        return Int(r[1]) << 16 | Int(r[2]) << 8 | Int(r[3])
    }
    func flashWriteEnable() throws  { try streamSPI4(chipSelect: 0x80, [0x06]) }
    func flashWriteDisable() throws { try streamSPI4(chipSelect: 0x80, [0x04]) }

    func flashIsBusy() throws -> Bool {
        let r = try streamSPI4(chipSelect: 0x80, [0x05, 0x00])
        return r.count >= 2 && (r[1] & 1) != 0
    }
    func flashWaitBusy() throws { while try flashIsBusy() { } }

    func flashEraseBlock64(_ addr: Int = 0) throws {
        try streamSPI4(chipSelect: 0x80,
                       [0xD8, UInt8((addr >> 16) & 0xFF), UInt8((addr >> 8) & 0xFF), UInt8(addr & 0xFF)])
    }
    func flashEraseSector(_ addr: Int) throws {
        try streamSPI4(chipSelect: 0x80,
                       [0x20, UInt8((addr >> 16) & 0x1F), UInt8((addr >> 8) & 0x1F), UInt8(addr & 0x1F)])
    }

    func flashWritePage(_ base: Int, _ bytes: ArraySlice<UInt8>) throws {
        var p: [UInt8] = [0x02, UInt8((base >> 16) & 0xFF), UInt8((base >> 8) & 0xFF), UInt8(base & 0xFF)]
        p.append(contentsOf: bytes)
        try streamSPI4(chipSelect: 0x80, p)
    }
    func flashReadPage(_ base: Int, _ length: Int) throws -> [UInt8] {
        var p: [UInt8] = [0x03, UInt8((base >> 16) & 0xFF), UInt8((base >> 8) & 0xFF), UInt8(base & 0xFF)]
        p.append(contentsOf: [UInt8](repeating: 0, count: length))
        let r = try streamSPI4(chipSelect: 0x80, p)
        return Array(r.dropFirst(4))
    }

    // MARK: I2C (Monitor live settings — well-specified, can work pre-flash)

    /// CH341ReadI2C(device7bit, regAddr): read one register byte.
    func readI2C(device7bit: UInt8, reg: UInt8) throws -> UInt8 {
        let addr = device7bit << 1
        try dev.bulkOut([CMD_I2C_STREAM, I2C_STM_STA,
                         I2C_STM_OUT | 0x02, addr, reg,
                         I2C_STM_STA, I2C_STM_OUT | 0x01, addr | 1,
                         I2C_STM_IN | 0x01, I2C_STM_STO, I2C_STM_END])
        let r = try dev.bulkIn(length: 1)
        return r.first ?? 0
    }

    /// Write one register byte to an I2C device.
    func writeI2C(device7bit: UInt8, reg: UInt8, value: UInt8) throws {
        let addr = device7bit << 1
        try dev.bulkOut([CMD_I2C_STREAM, I2C_STM_STA,
                         I2C_STM_OUT | 0x03, addr, reg, value,
                         I2C_STM_STO, I2C_STM_END])
    }

    // MARK: Delay

    func delay(ms: Int) { if ms > 0 { Thread.sleep(forTimeInterval: Double(ms) / 1000.0) } }

    // MARK: Bit reversal (CH341 shifts SPI LSB-first)

    static func reverse(_ b: UInt8) -> UInt8 {
        var x = b
        x = (x >> 1) & 0x55 | (x << 1) & 0xAA
        x = (x >> 2) & 0x33 | (x << 2) & 0xCC
        x = (x >> 4) & 0x0F | (x << 4) & 0xF0
        return x
    }
}
