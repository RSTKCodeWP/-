//! Mock device for testing without real hardware

use crate::device::{ChipInfo, DeviceInfo, DeviceCapabilities, DevicePlatform, FlashInterface, ConnectionType};
use openflash_core::protocol::Command;
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};

static MOCK_ENABLED: AtomicBool = AtomicBool::new(false);
static MOCK_CONNECTED: AtomicBool = AtomicBool::new(false);
static MOCK_PLATFORM: AtomicU8 = AtomicU8::new(0x05); // Default to RP2350

/// Enable mock device mode
pub fn enable_mock() {
    MOCK_ENABLED.store(true, Ordering::SeqCst);
}

/// Set mock platform
pub fn set_mock_platform(platform: DevicePlatform) {
    let id = match platform {
        DevicePlatform::Rp2040 => 0x01,
        DevicePlatform::Stm32f1 => 0x02,
        DevicePlatform::Stm32f4 => 0x03,
        DevicePlatform::Esp32 => 0x04,
        DevicePlatform::Rp2350 => 0x05,
        DevicePlatform::RaspberryPi => 0x10,
        DevicePlatform::OrangePi => 0x11,
        DevicePlatform::BananaPi => 0x12,
        DevicePlatform::ArduinoGiga => 0x20,
        DevicePlatform::Teensy40 => 0x30,
        DevicePlatform::Teensy41 => 0x31,
        DevicePlatform::Unknown => 0x00,
    };
    MOCK_PLATFORM.store(id, Ordering::SeqCst);
}

/// Check if mock mode is enabled
pub fn is_mock_enabled() -> bool {
    MOCK_ENABLED.load(Ordering::SeqCst)
}

/// Get mock device list
pub fn get_mock_devices() -> Vec<DeviceInfo> {
    if !is_mock_enabled() {
        return vec![];
    }

    let platform_id = MOCK_PLATFORM.load(Ordering::SeqCst);
    let platform = DevicePlatform::from_id(platform_id);
    
    vec![
        DeviceInfo {
            id: "mock:rp2350:0001".to_string(),
            name: format!("{} {} (Mock)", platform.icon(), platform.name()),
            serial: Some("MOCK-RP2350-001".to_string()),
            connected: MOCK_CONNECTED.load(Ordering::SeqCst),
            platform: Some(platform),
            capabilities: Some(get_mock_capabilities(platform)),
            connection_type: Some(ConnectionType::Usb),
            protocol_version: Some(0x23),
            firmware_version: Some("2.3.0".to_string()),
        },
        // Also add a mock SBC device
        DeviceInfo {
            id: "mock:tcp:localhost:9999".to_string(),
            name: "🥧 Raspberry Pi (Mock Network)".to_string(),
            serial: Some("MOCK-RPI-001".to_string()),
            connected: false,
            platform: Some(DevicePlatform::RaspberryPi),
            capabilities: Some(get_mock_capabilities(DevicePlatform::RaspberryPi)),
            connection_type: Some(ConnectionType::Tcp { 
                host: "localhost".to_string(), 
                port: 9999 
            }),
            protocol_version: Some(0x23),
            firmware_version: Some("2.3.0".to_string()),
        },
    ]
}

/// Get mock capabilities for a platform
pub fn get_mock_capabilities(platform: DevicePlatform) -> DeviceCapabilities {
    match platform {
        DevicePlatform::Rp2040 => DeviceCapabilities {
            parallel_nand: true,
            spi_nand: true,
            spi_nor: true,
            emmc: true,
            nvddr: false,
            hardware_ecc: false,
            wifi: false,
            bluetooth: false,
            high_speed_usb: false,
            sd_card: false,
            logic_analyzer: false,
            soft_ecc: false,
        },
        DevicePlatform::Rp2350 => DeviceCapabilities {
            parallel_nand: true,
            spi_nand: true,
            spi_nor: true,
            emmc: true,
            nvddr: true,  // RP2350 supports NV-DDR
            hardware_ecc: false,
            wifi: false,
            bluetooth: false,
            high_speed_usb: false,
            sd_card: false,
            logic_analyzer: false,
            soft_ecc: false,
        },
        DevicePlatform::ArduinoGiga => DeviceCapabilities {
            parallel_nand: true,
            spi_nand: true,
            spi_nor: true,
            emmc: true,
            nvddr: false,
            hardware_ecc: true,  // STM32H747 FMC has hardware ECC
            wifi: true,
            bluetooth: true,
            high_speed_usb: true,  // USB OTG HS
            sd_card: true,
            logic_analyzer: false,
            soft_ecc: false,
        },
        DevicePlatform::Esp32 => DeviceCapabilities {
            parallel_nand: true,
            spi_nand: true,
            spi_nor: true,
            emmc: true,
            nvddr: false,
            hardware_ecc: false,
            wifi: true,
            bluetooth: true,
            high_speed_usb: false,
            sd_card: false,
            logic_analyzer: false,
            soft_ecc: false,
        },
        DevicePlatform::Teensy40 => DeviceCapabilities {
            parallel_nand: true,
            spi_nand: true,
            spi_nor: true,
            emmc: true,
            nvddr: true,  // FlexIO supports NV-DDR timing
            hardware_ecc: false,
            wifi: false,
            bluetooth: false,
            high_speed_usb: true,  // USB HS 480Mbps!
            sd_card: false,
            logic_analyzer: true,  // 600MHz CPU enables logic analyzer
            soft_ecc: true,  // 600MHz CPU enables soft ECC on-the-fly
        },
        DevicePlatform::Teensy41 => DeviceCapabilities {
            parallel_nand: true,
            spi_nand: true,
            spi_nor: true,
            emmc: true,
            nvddr: true,
            hardware_ecc: false,
            wifi: false,
            bluetooth: false,
            high_speed_usb: true,  // USB HS 480Mbps!
            sd_card: true,  // Teensy 4.1 has SD card slot
            logic_analyzer: true,
            soft_ecc: true,
        },
        DevicePlatform::BananaPi => DeviceCapabilities {
            parallel_nand: false,  // Not recommended on Linux SBCs
            spi_nand: true,
            spi_nor: true,
            emmc: true,
            nvddr: false,
            hardware_ecc: false,
            wifi: true,
            bluetooth: true,
            high_speed_usb: false,
            sd_card: true,
            logic_analyzer: false,
            soft_ecc: false,
        },
        DevicePlatform::RaspberryPi | DevicePlatform::OrangePi => DeviceCapabilities {
            parallel_nand: true,
            spi_nand: true,
            spi_nor: true,
            emmc: true,
            nvddr: false,
            hardware_ecc: false,
            wifi: true,  // Most SBCs have WiFi
            bluetooth: true,
            high_speed_usb: false,
            sd_card: true,
            logic_analyzer: false,
            soft_ecc: false,
        },
        _ => DeviceCapabilities::default(),
    }
}

/// Connect to mock device
pub fn mock_connect(device_id: &str) -> Result<(), String> {
    if device_id.starts_with("mock:") {
        MOCK_CONNECTED.store(true, Ordering::SeqCst);
        Ok(())
    } else {
        Err("Not a mock device".to_string())
    }
}

/// Disconnect mock device
pub fn mock_disconnect() {
    MOCK_CONNECTED.store(false, Ordering::SeqCst);
}

/// Check if mock is connected
pub fn is_mock_connected() -> bool {
    MOCK_CONNECTED.load(Ordering::SeqCst)
}

/// Get mock chip info
pub fn get_mock_chip_info() -> ChipInfo {
    ChipInfo {
        manufacturer: "Samsung".to_string(),
        model: "K9F4G08U0D (Mock)".to_string(),
        chip_id: vec![0xEC, 0xDC, 0x10, 0x95, 0x54],
        size_mb: 512,
        page_size: 2048,
        block_size: 64,
        interface: FlashInterface::ParallelNand,
        sector_size: None,
        jedec_id: None,
        has_qspi: None,
        has_dual: None,
        voltage: None,
        max_clock_mhz: None,
        protected: None,
        luns: None,
        ufs_version: None,
        serial_number: None,
        boot_lun_enabled: None,
    }
}

/// Get mock device info response
pub fn get_mock_device_info_response() -> Vec<u8> {
    let platform_id = MOCK_PLATFORM.load(Ordering::SeqCst);
    let platform = DevicePlatform::from_id(platform_id);
    let caps = get_mock_capabilities(platform);
    
    // Build capabilities bitmap
    let mut bitmap: u32 = 0;
    if caps.parallel_nand { bitmap |= 0x01; }
    if caps.spi_nand { bitmap |= 0x02; }
    if caps.spi_nor { bitmap |= 0x04; }
    if caps.emmc { bitmap |= 0x08; }
    if caps.nvddr { bitmap |= 0x10; }
    if caps.hardware_ecc { bitmap |= 0x20; }
    if caps.wifi { bitmap |= 0x40; }
    if caps.bluetooth { bitmap |= 0x80; }
    if caps.high_speed_usb { bitmap |= 0x100; }
    if caps.sd_card { bitmap |= 0x200; }
    if caps.logic_analyzer { bitmap |= 0x400; }
    if caps.soft_ecc { bitmap |= 0x800; }
    
    let mut response = vec![0x01, platform_id, 0x23]; // cmd, platform, protocol version
    response.extend_from_slice(&bitmap.to_le_bytes());
    response
}

/// Process mock command
pub fn process_mock_command(cmd: Command, args: &[u8]) -> Vec<u8> {
    match cmd {
        Command::Ping => vec![0x01, 0x00], // OK

        Command::NandReadId => {
            // Return Samsung K9F4G08U0D ID
            vec![0x14, 0x00, 0xEC, 0xDC, 0x10, 0x95, 0x54]
        }

        Command::SpiNandReadId => {
            // Return GigaDevice GD5F1GQ4 ID
            vec![0x20, 0x00, 0xC8, 0xD1, 0x00]
        }

        // SPI NOR commands
        Command::SpiNorReadJedecId => {
            // Return Winbond W25Q128JV JEDEC ID
            vec![0x60, 0x00, 0xEF, 0x40, 0x18]
        }
        Command::SpiNorReadSfdp => {
            // Return mock SFDP header
            let mut data = vec![0x61, 0x00];
            data.extend_from_slice(b"SFDP");
            data.extend_from_slice(&[0x00; 60]); // Padding
            data
        }
        Command::SpiNorRead | Command::SpiNorFastRead => {
            // Generate mock SPI NOR data
            if args.len() >= 4 {
                let address = u32::from_le_bytes([args[0], args[1], args[2], args[3]]);
                let size = if args.len() >= 6 {
                    u16::from_le_bytes([args[4], args[5]]) as usize
                } else {
                    256
                };
                let mut data = vec![0x62, 0x00];
                for i in 0..size {
                    data.push(((address as usize + i) % 256) as u8);
                }
                data
            } else {
                vec![0x62, 0x01] // Error
            }
        }
        Command::SpiNorPageProgram => vec![0x66, 0x00],
        Command::SpiNorSectorErase => vec![0x67, 0x00],
        Command::SpiNorBlockErase32K => vec![0x68, 0x00],
        Command::SpiNorBlockErase64K => vec![0x69, 0x00],
        Command::SpiNorChipErase => vec![0x6A, 0x00],
        Command::SpiNorReadStatus1 => vec![0x6B, 0x00, 0x00], // Status = 0 (not busy, not protected)
        Command::SpiNorReadStatus2 => vec![0x6C, 0x00, 0x02], // QE bit set
        Command::SpiNorReadStatus3 => vec![0x6D, 0x00, 0x00],
        Command::SpiNorWriteStatus1 => vec![0x6E, 0x00],
        Command::SpiNorWriteStatus2 => vec![0x6F, 0x00],
        Command::SpiNorWriteStatus3 => vec![0x70, 0x00],
        Command::SpiNorWriteEnable => vec![0x71, 0x00],
        Command::SpiNorWriteDisable => vec![0x72, 0x00],
        Command::SpiNorReset => vec![0x73, 0x00],

        // UFS commands
        Command::UfsInit => vec![0x80, 0x00],
        Command::UfsReadDescriptor => {
            // Return mock device descriptor
            let mut data = vec![0x81, 0x00];
            // Device descriptor (32 bytes minimum)
            data.push(32); // length
            data.push(0x00); // descriptor type (device)
            data.push(0x00); // device type
            data.push(0x00); // device class
            data.push(0x00); // device sub-class
            data.push(0x50); // protocol (UFS)
            data.push(4); // num LUNs
            data.push(1); // num WLUNs
            data.push(1); // boot enable
            data.push(1); // desc access enable
            data.push(0); // init power mode
            data.push(0); // high priority LUN
            data.push(0); // secure removal type
            data.push(0); // security LUN
            data.push(0); // bkops term latency
            data.push(0); // init active ICC level
            data.extend_from_slice(&[0x03, 0x10]); // spec version (UFS 3.1)
            data.extend_from_slice(&[0x01, 0x24]); // manufacture date
            data.push(1); // manufacturer name idx
            data.push(2); // product name idx
            data.push(3); // serial number idx
            data.push(4); // OEM ID idx
            data.extend_from_slice(&[0x01, 0xCE]); // manufacturer ID (Samsung)
            data.push(0); // UD0 base offset
            data.push(0); // UD config P length
            data.push(0); // device RTT cap
            data.extend_from_slice(&[0x00, 0x00]); // periodic RTC update
            data
        }
        Command::UfsReadCapacity => {
            // Return mock capacity
            let mut data = vec![0x82, 0x00];
            data.extend_from_slice(&128u64.to_be_bytes()); // 128GB in blocks
            data.extend_from_slice(&4096u32.to_be_bytes()); // block size
            data
        }
        Command::UfsRead10 | Command::UfsRead16 => {
            // Generate mock UFS data
            let mut data = vec![0x83, 0x00];
            for i in 0..4096 {
                data.push((i % 256) as u8);
            }
            data
        }
        Command::UfsWrite10 | Command::UfsWrite16 => vec![0x85, 0x00],
        Command::UfsSelectLun => vec![0x87, 0x00],
        Command::UfsGetStatus => vec![0x88, 0x00, 0x00], // Status OK

        Command::Reset => vec![0x08, 0x00],

        Command::BusConfig => vec![0x02, 0x00],

        Command::NandCmd => vec![0x10, 0x00],

        Command::NandAddr => vec![0x11, 0x00],

        Command::NandReadPage | Command::SpiNandReadCache => {
            // Generate mock page data
            if args.len() >= 6 {
                let page_addr = u32::from_le_bytes([args[0], args[1], args[2], args[3]]);
                let page_size = u16::from_le_bytes([args[4], args[5]]) as usize;
                generate_mock_page(page_addr, page_size)
            } else {
                vec![0x12, 0x01] // Error
            }
        }

        Command::NandWritePage | Command::SpiNandProgramExec => vec![0x13, 0x00],

        Command::SpiNandReset => vec![0x21, 0x00],
        Command::SpiNandGetFeature => vec![0x22, 0x00, 0x00], // Feature value = 0
        Command::SpiNandSetFeature => vec![0x23, 0x00],
        Command::SpiNandPageRead => vec![0x24, 0x00],
        Command::SpiNandProgramLoad | Command::SpiNandProgramLoadX4 => vec![0x27, 0x00],
        Command::SpiNandBlockErase => vec![0x2A, 0x00],
        Command::SpiNandWriteEnable => vec![0x2B, 0x00],
        Command::SpiNandWriteDisable => vec![0x2C, 0x00],

        _ => vec![0x00, 0x01], // Unknown command error
    }
}

/// Generate mock page data with realistic patterns
fn generate_mock_page(page_addr: u32, size: usize) -> Vec<u8> {
    let mut data = Vec::with_capacity(size);

    // First few pages contain "bootloader" pattern
    if page_addr < 64 {
        // U-Boot header at page 0
        if page_addr == 0 {
            data.extend_from_slice(&[0x27, 0x05, 0x19, 0x56]); // U-Boot magic
            data.extend_from_slice(b"U-Boot 2024.01 for OpenFlash\0");
            while data.len() < size {
                data.push(0x00);
            }
        } else {
            // Bootloader code (random-ish but deterministic)
            for i in 0..size {
                let val = ((page_addr as usize * 256 + i) % 256) as u8;
                data.push(val ^ 0x5A);
            }
        }
    }
    // Pages 64-128 contain SquashFS
    else if page_addr >= 64 && page_addr < 128 {
        if page_addr == 64 {
            data.extend_from_slice(b"hsqs"); // SquashFS magic (little-endian)
            data.extend_from_slice(&[0x00; 28]); // Header padding
            while data.len() < size {
                data.push(((page_addr + data.len() as u32) % 256) as u8);
            }
        } else {
            // Compressed data pattern
            for i in 0..size {
                data.push(((page_addr as usize + i) % 256) as u8);
            }
        }
    }
    // Pages 128-256 contain JFFS2
    else if page_addr >= 128 && page_addr < 256 {
        if page_addr == 128 {
            data.extend_from_slice(&[0x85, 0x19]); // JFFS2 magic (LE)
            data.extend_from_slice(&[0x04, 0x00]); // Node type
            while data.len() < size {
                data.push(0xFF);
            }
        } else {
            // JFFS2 data
            for i in 0..size {
                if i % 64 == 0 {
                    data.extend_from_slice(&[0x85, 0x19]);
                } else {
                    data.push(((page_addr as usize + i) % 256) as u8);
                }
            }
            data.truncate(size);
        }
    }
    // Empty pages (erased)
    else if page_addr >= 256 && page_addr < 1024 {
        data.resize(size, 0xFF);
    }
    // Bad block simulation at block 16 (pages 1024-1087)
    else if page_addr >= 1024 && page_addr < 1088 {
        // Bad block marker
        data.push(0x00);
        data.push(0x00);
        data.resize(size, 0xFF);
    }
    // Rest is random data
    else {
        for i in 0..size {
            let seed = page_addr.wrapping_mul(31).wrapping_add(i as u32);
            data.push((seed % 256) as u8);
        }
    }

    data
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mock_page_generation() {
        let page = generate_mock_page(0, 2048);
        assert_eq!(page.len(), 2048);
        // Check U-Boot magic
        assert_eq!(&page[0..4], &[0x27, 0x05, 0x19, 0x56]);
    }

    #[test]
    fn test_mock_squashfs() {
        let page = generate_mock_page(64, 2048);
        assert_eq!(&page[0..4], b"hsqs");
    }

    #[test]
    fn test_mock_empty_page() {
        let page = generate_mock_page(300, 2048);
        assert!(page.iter().all(|&b| b == 0xFF));
    }
}
