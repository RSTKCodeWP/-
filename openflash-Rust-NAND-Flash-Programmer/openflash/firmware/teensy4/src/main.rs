//! OpenFlash Firmware for Teensy 4.0/4.1
//!
//! High-performance flash programmer firmware leveraging:
//! - NXP i.MX RT1062 @ 600MHz (ARM Cortex-M7)
//! - USB High Speed (480 Mbit/s) - 10-20x faster than RP2040/STM32
//! - FlexIO for precise NAND timing
//! - DMA for zero-copy transfers
//! - SD card slot on Teensy 4.1 for autonomous operation
//!
//! Supported boards:
//! - Teensy 4.0 (IMXRT1062, 1MB flash, no SD)
//! - Teensy 4.1 (IMXRT1062, 8MB flash, SD slot, Ethernet)
//! - Teensy MicroMod (SparkFun carrier boards)

#![no_std]
#![no_main]

use teensy4_panic as _;

mod flexio_nand;
mod gpio_nand;
mod protocol;
mod spi;
mod usb;

use cortex_m_rt::entry;
use teensy4_bsp as bsp;
use bsp::board;

/// Protocol version for v2.3.5
const PROTOCOL_VERSION: u8 = 0x25;

/// Firmware version
const VERSION: &str = "2.3.5";

/// Platform identifier for Teensy 4.x
const PLATFORM_ID: u8 = 0x30;

/// Capabilities bitmap
/// Bit 0: Parallel NAND
/// Bit 1: SPI NAND
/// Bit 2: SPI NOR
/// Bit 3: eMMC
/// Bit 4: NV-DDR (high-speed timing)
/// Bit 5: Hardware ECC
/// Bit 6: WiFi (not available)
/// Bit 7: Bluetooth (not available)
/// Bit 8: USB High Speed (480 Mbit/s)
/// Bit 9: SD Card (Teensy 4.1 only)
/// Bit 10: Logic Analyzer mode
/// Bit 11: Soft ECC on-the-fly
const CAPABILITIES_TEENSY40: u32 = 0x0000_051F; // All flash + USB HS + Logic Analyzer
const CAPABILITIES_TEENSY41: u32 = 0x0000_071F; // + SD Card

/// USB packet buffer size (512 bytes for High Speed)
const USB_PACKET_SIZE: usize = 512;

/// Command buffer
static mut CMD_BUFFER: [u8; USB_PACKET_SIZE] = [0u8; USB_PACKET_SIZE];

/// Response buffer
static mut RESP_BUFFER: [u8; USB_PACKET_SIZE] = [0u8; USB_PACKET_SIZE];

/// Page buffer for NAND operations (8KB + spare)
static mut PAGE_BUFFER: [u8; 8192 + 448] = [0u8; 8192 + 448];

#[entry]
fn main() -> ! {
    // Initialize board
    let board::Resources {
        pins,
        usb,
        mut gpio1,
        mut gpio2,
        mut gpio3,
        mut gpio4,
        pit,
        ..
    } = board::t40(board::instances());

    // Detect Teensy variant
    let is_teensy41 = detect_teensy41();
    let capabilities = if is_teensy41 {
        CAPABILITIES_TEENSY41
    } else {
        CAPABILITIES_TEENSY40
    };

    // Initialize USB High Speed
    let usb_device = usb::init_usb_hs(usb);

    // Initialize GPIO for NAND interface
    let nand_gpio = gpio_nand::NandGpio::new(
        &mut gpio1,
        &mut gpio2,
        &mut gpio3,
        &mut gpio4,
        pins,
    );

    // Initialize SPI for SPI NAND/NOR
    let spi = spi::init_spi();

    // Initialize FlexIO for high-speed NAND timing
    let flexio = flexio_nand::init_flexio();

    // Main loop
    loop {
        // Poll USB for commands
        if let Some(cmd_len) = usb_device.poll_command(unsafe { &mut CMD_BUFFER }) {
            let response = process_command(
                unsafe { &CMD_BUFFER[..cmd_len] },
                capabilities,
                &nand_gpio,
                &spi,
                &flexio,
            );
            
            usb_device.send_response(&response);
        }
    }
}

/// Detect if running on Teensy 4.1 (has SD card pins)
fn detect_teensy41() -> bool {
    // Teensy 4.1 has specific pins for SD card
    // Check for presence of SD_CD pin
    #[cfg(feature = "teensy41")]
    return true;
    
    #[cfg(not(feature = "teensy41"))]
    return false;
}

/// Process incoming USB command
fn process_command(
    cmd: &[u8],
    capabilities: u32,
    _nand: &gpio_nand::NandGpio,
    _spi: &spi::SpiController,
    _flexio: &flexio_nand::FlexioNand,
) -> &'static [u8] {
    if cmd.is_empty() {
        return &[0xFF];
    }

    let response = unsafe { &mut RESP_BUFFER };
    
    match cmd[0] {
        // Ping
        0x00 | 0x01 => {
            response[0] = 0x00;
            response[1] = PROTOCOL_VERSION;
            &response[..2]
        }

        // Get device info
        0x01 => {
            response[0] = 0x01;
            response[1] = PLATFORM_ID;
            response[2] = PROTOCOL_VERSION;
            response[3..7].copy_from_slice(&capabilities.to_le_bytes());
            &response[..7]
        }

        // Get version string
        0x02 => {
            response[0] = 0x02;
            let version_bytes = VERSION.as_bytes();
            response[1..1 + version_bytes.len()].copy_from_slice(version_bytes);
            &response[..1 + version_bytes.len()]
        }

        // Get platform name
        0x03 => {
            response[0] = 0x03;
            #[cfg(feature = "teensy41")]
            let name = b"Teensy 4.1";
            #[cfg(feature = "teensy40")]
            let name = b"Teensy 4.0";
            #[cfg(feature = "mm")]
            let name = b"Teensy MicroMod";
            #[cfg(not(any(feature = "teensy40", feature = "teensy41", feature = "mm")))]
            let name = b"Teensy 4.0";
            
            response[1..1 + name.len()].copy_from_slice(name);
            &response[..1 + name.len()]
        }

        // Get USB speed info
        0x04 => {
            response[0] = 0x04;
            response[1] = 0x02; // USB High Speed (480 Mbit/s)
            response[2..4].copy_from_slice(&(USB_PACKET_SIZE as u16).to_le_bytes());
            &response[..4]
        }

        // Unknown command
        _ => {
            response[0] = 0xFF;
            response[1] = cmd[0];
            &response[..2]
        }
    }
}
