//! OpenFlash Firmware for Raspberry Pi Pico 2 (RP2350)
//!
//! This firmware provides USB-to-GPIO bridge functionality for flash memory operations.
//! The RP2350 offers improved performance over RP2040:
//! - Dual Cortex-M33 cores at 150MHz (or RISC-V Hazard3)
//! - 520KB SRAM (vs 264KB on RP2040)
//! - Enhanced PIO blocks for faster NAND timing
//! - Security features (ARM TrustZone, secure boot)

#![no_std]
#![no_main]

use defmt::*;
use defmt_rtt as _;
use embassy_executor::Spawner;
use embassy_rp::bind_interrupts;
use embassy_rp::peripherals::USB;
use embassy_rp::usb::{Driver, InterruptHandler};
use embassy_usb::class::cdc_acm::{CdcAcmClass, State};
use embassy_usb::Builder;
use heapless::Vec;
use panic_probe as _;

mod pio_nand;
mod spi_nand;
mod spi_nor;
mod emmc;
mod usb_handler;

bind_interrupts!(struct Irqs {
    USBCTRL_IRQ => InterruptHandler<USB>;
});

/// Protocol version for v2.3.0
const PROTOCOL_VERSION: u8 = 0x23;

/// Firmware version
const FIRMWARE_VERSION: &str = "2.3.0";

/// Platform identifier
const PLATFORM_ID: u8 = 0x05; // RP2350

/// RP2350 specific capabilities
const CAPABILITIES: u32 = 0b0000_0000_0000_0000_0000_0000_0011_1111;
// Bit 0: Parallel NAND
// Bit 1: SPI NAND
// Bit 2: SPI NOR
// Bit 3: eMMC
// Bit 4: Enhanced PIO (NV-DDR support)
// Bit 5: Security features (TrustZone)

#[embassy_executor::main]
async fn main(_spawner: Spawner) {
    info!("OpenFlash RP2350 Firmware v{}", FIRMWARE_VERSION);
    
    let p = embassy_rp::init(Default::default());
    
    // Create USB driver
    let driver = Driver::new(p.USB, Irqs);
    
    // USB device configuration
    let mut config = embassy_usb::Config::new(0x1209, 0x0F1A); // OpenFlash VID/PID
    config.manufacturer = Some("OpenFlash");
    config.product = Some("OpenFlash Pico 2");
    config.serial_number = Some("OF-RP2350-001");
    config.max_power = 500;
    config.max_packet_size_0 = 64;
    
    // USB buffers
    let mut config_descriptor = [0; 256];
    let mut bos_descriptor = [0; 256];
    let mut control_buf = [0; 64];
    
    let mut state = State::new();
    
    let mut builder = Builder::new(
        driver,
        config,
        &mut config_descriptor,
        &mut bos_descriptor,
        &mut [], // msos_descriptor
        &mut control_buf,
    );
    
    // Create CDC ACM class for serial communication
    let mut class = CdcAcmClass::new(&mut builder, &mut state, 64);
    
    // Build USB device
    let mut usb = builder.build();
    
    // Command buffer
    let mut cmd_buf: Vec<u8, 64> = Vec::new();
    
    info!("USB initialized, waiting for host...");
    
    loop {
        // Run USB device
        usb.run().await;
    }
}

/// Handle incoming USB commands
async fn handle_command(cmd: &[u8]) -> Vec<u8, 64> {
    let mut response: Vec<u8, 64> = Vec::new();
    
    if cmd.is_empty() {
        return response;
    }
    
    match cmd[0] {
        // Ping
        0x00 => {
            let _ = response.push(0x00);
            let _ = response.push(PROTOCOL_VERSION);
        }
        
        // Get device info
        0x01 => {
            let _ = response.push(0x01);
            let _ = response.push(PLATFORM_ID);
            let _ = response.push(PROTOCOL_VERSION);
            // Capabilities (4 bytes, little-endian)
            let _ = response.extend_from_slice(&CAPABILITIES.to_le_bytes());
        }
        
        // Get firmware version
        0x02 => {
            let _ = response.push(0x02);
            for b in FIRMWARE_VERSION.bytes() {
                let _ = response.push(b);
            }
        }
        
        // Unknown command
        _ => {
            let _ = response.push(0xFF);
            let _ = response.push(cmd[0]);
        }
    }
    
    response
}
