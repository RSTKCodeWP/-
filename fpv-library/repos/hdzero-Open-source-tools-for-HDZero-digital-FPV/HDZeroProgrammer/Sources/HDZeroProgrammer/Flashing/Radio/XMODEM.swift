import Foundation

/// Minimal XMODEM sender (128-byte blocks, checksum or CRC-16) used to push the
/// STM32 firmware to the HDZero radio's bootloader, mirroring the Python
/// `XMODEM(getc, putc).send(stream)`.
///
/// ⚠️ Hardware-unverified.
enum XMODEM {
    private static let SOH: UInt8 = 0x01
    private static let EOT: UInt8 = 0x04
    private static let ACK: UInt8 = 0x06
    private static let NAK: UInt8 = 0x15
    private static let CAN: UInt8 = 0x18
    private static let C:   UInt8 = 0x43   // 'C' — receiver requests CRC mode

    enum XError: LocalizedError {
        case noHandshake, tooManyRetries, cancelled
        var errorDescription: String? {
            switch self {
            case .noHandshake:    return "XMODEM: receiver never started (no NAK/C)."
            case .tooManyRetries: return "XMODEM: too many retries on a block."
            case .cancelled:      return "XMODEM: cancelled by receiver."
            }
        }
    }

    /// Send `data` over `port`. Calls `onProgress(fraction)` as blocks ACK.
    static func send(_ data: [UInt8], over port: SerialPort,
                     onProgress: (Double) -> Void) throws {
        // 1. Wait for the receiver's start byte (NAK = checksum, C = CRC).
        var useCRC = false
        var started = false
        for _ in 0..<60 {                    // up to ~60s
            let b = (try? port.read(max: 1, timeout: 1.0)) ?? []
            if let x = b.first {
                if x == NAK { started = true; useCRC = false; break }
                if x == C   { started = true; useCRC = true;  break }
                if x == CAN { throw XError.cancelled }
            }
        }
        guard started else { throw XError.noHandshake }

        // 2. Send 128-byte blocks.
        let blockSize = 128
        let blocks = (data.count + blockSize - 1) / blockSize
        var blockNum: UInt8 = 1
        for i in 0..<blocks {
            let start = i * blockSize
            let end = min(start + blockSize, data.count)
            var payload = Array(data[start..<end])
            if payload.count < blockSize {
                payload.append(contentsOf: [UInt8](repeating: 0x1A, count: blockSize - payload.count)) // pad ^Z
            }

            var packet: [UInt8] = [SOH, blockNum, 255 &- blockNum]
            packet.append(contentsOf: payload)
            if useCRC {
                let crc = crc16(payload)
                packet.append(UInt8(crc >> 8)); packet.append(UInt8(crc & 0xFF))
            } else {
                packet.append(payload.reduce(0, &+))
            }

            var acked = false
            for _ in 0..<10 {
                try port.write(packet)
                let resp = (try? port.read(max: 1, timeout: 2.0))?.first
                if resp == ACK { acked = true; break }
                if resp == CAN { throw XError.cancelled }
                // NAK or timeout → retransmit
            }
            guard acked else { throw XError.tooManyRetries }
            blockNum = blockNum &+ 1
            onProgress(Double(i + 1) / Double(blocks))
        }

        // 3. End of transmission.
        for _ in 0..<10 {
            try port.write([EOT])
            if (try? port.read(max: 1, timeout: 2.0))?.first == ACK { break }
        }
    }

    private static func crc16(_ data: [UInt8]) -> UInt16 {
        var crc: UInt16 = 0
        for b in data {
            crc ^= UInt16(b) << 8
            for _ in 0..<8 {
                crc = (crc & 0x8000) != 0 ? (crc << 1) ^ 0x1021 : (crc << 1)
            }
        }
        return crc
    }
}
