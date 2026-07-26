import Foundation
import IOKit
import IOKit.serial

/// POSIX serial-port wrapper + IOKit enumeration, used by the Radio path
/// (STM32 over its virtual COM port, ELRS over the CH340 UART).
///
/// ⚠️ Hardware-unverified.
final class SerialPort {
    struct Info {
        let path: String          // /dev/cu.usbserial-XXXX
        let vendorName: String
        let productName: String
        let vid: Int
        let pid: Int
    }

    enum SerialError: LocalizedError {
        case openFailed(String), notConfigured, timeout
        var errorDescription: String? {
            switch self {
            case .openFailed(let s): return "Serial open failed: \(s)"
            case .notConfigured:     return "Serial port not open."
            case .timeout:           return "Serial read timed out."
            }
        }
    }

    private var fd: Int32 = -1
    var isOpen: Bool { fd >= 0 }

    // MARK: Enumeration

    static func list() -> [Info] {
        var infos: [Info] = []
        var iterator: io_iterator_t = 0
        let matching = IOServiceMatching(kIOSerialBSDServiceValue)
        guard IOServiceGetMatchingServices(kIOMainPortDefault, matching, &iterator) == KERN_SUCCESS
        else { return [] }
        defer { IOObjectRelease(iterator) }

        var service = IOIteratorNext(iterator)
        while service != 0 {
            defer { IOObjectRelease(service); service = IOIteratorNext(iterator) }
            guard let path = stringProperty(service, kIOCalloutDeviceKey) else { continue }
            let vendor  = usbAncestorString(service, "USB Vendor Name") ?? ""
            let product = usbAncestorString(service, "USB Product Name") ?? ""
            let vid = usbAncestorInt(service, "idVendor") ?? 0
            let pid = usbAncestorInt(service, "idProduct") ?? 0
            infos.append(Info(path: path, vendorName: vendor, productName: product, vid: vid, pid: pid))
        }
        return infos
    }

    /// First port whose vendor/product strings contain `keyword` (e.g.
    /// "STMicroelectronics" or "CH340"), matching program_radio.py.
    static func find(keyword: String) -> Info? {
        list().first {
            $0.vendorName.localizedCaseInsensitiveContains(keyword) ||
            $0.productName.localizedCaseInsensitiveContains(keyword) ||
            $0.path.localizedCaseInsensitiveContains(keyword)
        }
    }

    // MARK: Open / configure / close

    func open(_ path: String, baud: speed_t) throws {
        fd = Darwin.open(path, O_RDWR | O_NOCTTY | O_NONBLOCK)
        guard fd >= 0 else { throw SerialError.openFailed(String(cString: strerror(errno))) }

        var tty = termios()
        guard tcgetattr(fd, &tty) == 0 else { throw SerialError.openFailed("tcgetattr") }
        cfmakeraw(&tty)
        cfsetispeed(&tty, baud)
        cfsetospeed(&tty, baud)
        tty.c_cflag |= tcflag_t(CREAD | CLOCAL)
        tty.c_cflag &= ~tcflag_t(PARENB | CSTOPB | CRTSCTS)
        // 8 data bits
        tty.c_cflag &= ~tcflag_t(CSIZE)
        tty.c_cflag |= tcflag_t(CS8)
        guard tcsetattr(fd, TCSANOW, &tty) == 0 else { throw SerialError.openFailed("tcsetattr") }
        // Switch back to blocking with a per-read timeout via select().
        _ = fcntl(fd, F_SETFL, 0)
    }

    func close() {
        if fd >= 0 { Darwin.close(fd); fd = -1 }
    }

    // MARK: I/O

    func write(_ bytes: [UInt8]) throws {
        guard fd >= 0 else { throw SerialError.notConfigured }
        var off = 0
        try bytes.withUnsafeBytes { raw in
            while off < bytes.count {
                let n = Darwin.write(fd, raw.baseAddress!.advanced(by: off), bytes.count - off)
                if n <= 0 { throw SerialError.openFailed("write \(errno)") }
                off += n
            }
        }
    }
    func write(_ string: String) throws { try write([UInt8](string.utf8)) }

    /// Read up to `max` bytes, waiting up to `timeout` seconds for the first byte.
    func read(max: Int, timeout: TimeInterval) throws -> [UInt8] {
        guard fd >= 0 else { throw SerialError.notConfigured }
        var readfds = fd_set()
        fdZero(&readfds); fdSet(fd, &readfds)
        var tv = timeval(tv_sec: Int(timeout), tv_usec: __darwin_suseconds_t((timeout - floor(timeout)) * 1e6))
        let sel = select(fd + 1, &readfds, nil, nil, &tv)
        if sel <= 0 { return [] }                 // timeout / no data
        var buf = [UInt8](repeating: 0, count: max)
        let n = Darwin.read(fd, &buf, max)
        return n > 0 ? Array(buf[0..<n]) : []
    }

    /// Read until `timeout` elapses with no new data; returns all bytes seen.
    func drain(timeout: TimeInterval) -> [UInt8] {
        var out: [UInt8] = []
        while let chunk = try? read(max: 256, timeout: timeout), !chunk.isEmpty {
            out.append(contentsOf: chunk)
        }
        return out
    }

    // MARK: Modem control (DTR/RTS) — ESP reset-to-bootloader sequence

    func setDTR(_ on: Bool) { setBit(TIOCM_DTR, on) }
    func setRTS(_ on: Bool) { setBit(TIOCM_RTS, on) }

    private func setBit(_ bit: Int32, _ on: Bool) {
        guard fd >= 0 else { return }
        var status: Int32 = 0
        _ = ioctl(fd, TIOCMGET, &status)
        if on { status |= bit } else { status &= ~bit }
        _ = ioctl(fd, TIOCMSET, &status)
    }

    // MARK: IOKit property helpers

    private static func stringProperty(_ service: io_object_t, _ key: String) -> String? {
        guard let cf = IORegistryEntryCreateCFProperty(service, key as CFString, kCFAllocatorDefault, 0)
        else { return nil }
        return cf.takeRetainedValue() as? String
    }
    private static func usbAncestorString(_ service: io_object_t, _ key: String) -> String? {
        if let s = IORegistryEntrySearchCFProperty(
            service, kIOServicePlane, key as CFString, kCFAllocatorDefault,
            IOOptionBits(kIORegistryIterateRecursively | kIORegistryIterateParents)) as? String { return s }
        return nil
    }
    private static func usbAncestorInt(_ service: io_object_t, _ key: String) -> Int? {
        if let n = IORegistryEntrySearchCFProperty(
            service, kIOServicePlane, key as CFString, kCFAllocatorDefault,
            IOOptionBits(kIORegistryIterateRecursively | kIORegistryIterateParents)) as? Int { return n }
        return nil
    }
}

// fd_set helpers (Swift can't index the C bitmask directly)
private func fdZero(_ set: inout fd_set) { bzero(&set, MemoryLayout<fd_set>.size) }
private func fdSet(_ fd: Int32, _ set: inout fd_set) {
    let offset = Int(fd) / 32
    let mask = Int32(1 << (Int(fd) % 32))
    withUnsafeMutablePointer(to: &set.fds_bits) {
        $0.withMemoryRebound(to: Int32.self, capacity: 32) { $0[offset] |= mask }
    }
}
