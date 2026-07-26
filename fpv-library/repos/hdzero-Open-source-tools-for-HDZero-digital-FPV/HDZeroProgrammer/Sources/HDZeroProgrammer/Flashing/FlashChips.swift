import Foundation

/// Decodes a JEDEC RDID (0x9F) result — `manufacturer<<16 | memType<<8 | capacity`
/// — into a human name + size, so Read/Detect can show "Winbond W25Q128 · 16384 kB"
/// instead of a raw hex id. Covers the SPI-NOR makers seen on HDZero gear.
enum FlashChips {

    private static let makers: [Int: String] = [
        0xEF: "Winbond", 0xC8: "GigaDevice", 0xC2: "Macronix", 0x20: "Micron/XMC",
        0x1F: "Adesto/Atmel", 0x9D: "ISSI", 0x68: "Boya", 0x0B: "XTX", 0x85: "Puya",
    ]

    /// Returns (name, sizeKB?). For most SPI-NOR the capacity byte is `log2(bytes)`,
    /// e.g. 0x14 → 2^20 = 1 MB → 1024 kB ; 0x18 → 2^24 = 16 MB → 16384 kB.
    static func describe(jedec id: Int) -> (name: String, sizeKB: Int?) {
        let mfg = (id >> 16) & 0xFF
        let cap = id & 0xFF
        let maker = makers[mfg] ?? "SPI flash"
        var sizeKB: Int? = nil
        if cap >= 0x10 && cap <= 0x1B { sizeKB = (1 << cap) / 1024 }
        let hex = String(format: "0x%06X", id)
        let name: String
        if let kb = sizeKB {
            let mbit = kb * 8 / 1024
            name = "\(maker) \(mbit) Mbit (\(hex))"
        } else {
            name = "\(maker) (\(hex))"
        }
        return (name, sizeKB)
    }

    /// A JEDEC id is plausible if it isn't all-zero (no MISO / no chip) or all-ones
    /// (bus stuck high / clip not contacting).
    static func isValid(jedec id: Int) -> Bool {
        let v = id & 0xFFFFFF
        return v != 0 && v != 0xFFFFFF
    }
}
