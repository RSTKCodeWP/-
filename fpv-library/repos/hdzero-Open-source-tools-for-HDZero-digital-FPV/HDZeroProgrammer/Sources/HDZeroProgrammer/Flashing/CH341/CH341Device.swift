import Foundation
import IOKit
import IOUSBHost

/// Low-level USB transport for the CH341A in SPI/I2C mode (VID 0x1A86 /
/// PID 0x5512). Replaces WCH's Windows-only CH341DLL.DLL with native IOUSBHost
/// bulk transfers on interface 0 (bulk OUT 0x02 / bulk IN 0x82).
///
/// ⚠️ Hardware-unverified: written against the flashrom/ch341prog protocol spec.
/// Needs a real CH341A + HDZero device to validate.
final class CH341Device {
    static let vid: Int = 0x1A86
    static let pid: Int = 0x5512
    static let interfaceNumber: Int = 0
    static let epOut: Int = 0x02
    static let epIn: Int = 0x82
    static let packetLength = 32          // CH341_PACKET_LENGTH
    static let timeout: TimeInterval = 2.0

    enum USBError: LocalizedError {
        case notFound
        case openFailed(String)
        case noPipe
        case transfer(String)
        var errorDescription: String? {
            switch self {
            case .notFound:          return "CH341A programmer not found on USB. Plug it in and try again."
            case .openFailed(let s): return "Could not open CH341A: \(s)"
            case .noPipe:            return "CH341A bulk endpoints unavailable."
            case .transfer(let s):   return "USB transfer error: \(s)"
            }
        }
    }

    private var interface: IOUSBHostInterface?
    private var outPipe: IOUSBHostPipe?
    private var inPipe: IOUSBHostPipe?

    var isOpen: Bool { interface != nil }

    // MARK: Open / close

    func open() throws {
        // Match the USB interface (not the device) so we can grab pipes directly.
        guard let matching = IOServiceMatching("IOUSBHostInterface") as NSMutableDictionary? else {
            throw USBError.notFound
        }
        matching["idVendor"] = Self.vid
        matching["idProduct"] = Self.pid
        matching["bInterfaceNumber"] = Self.interfaceNumber

        let service = IOServiceGetMatchingService(kIOMainPortDefault, matching)
        guard service != 0 else { throw USBError.notFound }
        defer { IOObjectRelease(service) }

        do {
            let iface = try IOUSBHostInterface(__ioService: service,
                                               options: [],
                                               queue: nil,
                                               interestHandler: nil)
            self.interface = iface
            self.outPipe = try iface.copyPipe(withAddress: Self.epOut)
            self.inPipe  = try iface.copyPipe(withAddress: Self.epIn)
        } catch {
            throw USBError.openFailed(error.localizedDescription)
        }
        guard outPipe != nil, inPipe != nil else { throw USBError.noPipe }
    }

    func close() {
        outPipe = nil
        inPipe = nil
        interface?.destroy()
        interface = nil
    }

    // MARK: Bulk transfers

    /// Send raw bytes on the bulk OUT endpoint.
    func bulkOut(_ bytes: [UInt8]) throws {
        guard let pipe = outPipe else { throw USBError.noPipe }
        let data = NSMutableData(bytes: bytes, length: bytes.count)
        var transferred: UInt = 0
        do {
            try pipe.__sendIORequest(with: data,
                                     bytesTransferred: &transferred,
                                     completionTimeout: Self.timeout)
        } catch {
            throw USBError.transfer("OUT \(error.localizedDescription)")
        }
    }

    /// Read up to `length` bytes from the bulk IN endpoint. Returns the bytes
    /// actually transferred.
    func bulkIn(length: Int) throws -> [UInt8] {
        guard let pipe = inPipe else { throw USBError.noPipe }
        let data = NSMutableData(length: length)!
        var transferred: UInt = 0
        do {
            try pipe.__sendIORequest(with: data,
                                     bytesTransferred: &transferred,
                                     completionTimeout: Self.timeout)
        } catch {
            throw USBError.transfer("IN \(error.localizedDescription)")
        }
        let n = Int(transferred)
        let ptr = data.bytes.bindMemory(to: UInt8.self, capacity: n)
        return Array(UnsafeBufferPointer(start: ptr, count: n))
    }
}
