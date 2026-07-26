//! OpenFlash ESP32 Firmware
//! Firmware for NAND/eMMC/SPI NOR flash operations via USB/UART
//! Supports: Parallel NAND, SPI NAND, eMMC, SPI NOR
//! 
//! ESP32 advantages:
//! - WiFi/BLE for wireless operation
//! - Dual-core for parallel processing
//! - More GPIO pins
//! - Built-in USB Serial/JTAG (ESP32-S2/S3/C3)
//! - Up to 80MHz SPI clock for NOR flash

#![no_std]
#![no_main]

use esp_backtrace as _;
use esp_hal::{
    clock::ClockControl,
    gpio::{Input, Output, PullUp, IO},
    peripherals::Peripherals,
    prelude::*,
    spi::{master::Spi, SpiMode},
    uart::{config::Config as UartConfig, Uart},
    Delay,
};
use esp_println::println;
use heapless::Vec;

mod spi_nand;
mod emmc;
mod nand_gpio;
mod protocol;
mod spi_nor;

use protocol::{Command, Response, Interface, PROTOCOL_VERSION};
use spi_nor::SpiNorController;

/// Pin assignments for ESP32
/// 
/// === Parallel NAND Mode ===
/// Control signals:
///   GPIO4  - CLE (Command Latch Enable)
///   GPIO5  - ALE (Address Latch Enable)
///   GPIO12 - WE# (Write Enable, active low)
///   GPIO13 - RE# (Read Enable, active low)
///   GPIO14 - CE# (Chip Enable, active low)
///   GPIO15 - R/B# (Ready/Busy, active low = busy)
///
/// Data bus:
///   GPIO16 - D0
///   GPIO17 - D1
///   GPIO18 - D2
///   GPIO19 - D3
///   GPIO21 - D4
///   GPIO22 - D5
///   GPIO23 - D6
///   GPIO25 - D7
///
/// === SPI NAND/eMMC/SPI NOR Mode ===
/// SPI signals (VSPI):
///   GPIO18 - SCK
///   GPIO19 - MISO
///   GPIO23 - MOSI
///   GPIO5  - CS# (SPI NAND)
///   GPIO4  - CS# (eMMC)
///   GPIO27 - CS# (SPI NOR)
///
/// === Communication ===
/// UART0 (default):
///   GPIO1  - TX
///   GPIO3  - RX
///
/// USB Serial/JTAG (ESP32-S2/S3/C3):
///   Built-in USB pins

const FIRMWARE_VERSION: &str = "1.6.0";

/// Current active interface
static mut CURRENT_INTERFACE: Interface = Interface::SpiNand;

#[entry]
fn main() -> ! {
    let peripherals = Peripherals::take();
    let system = peripherals.SYSTEM.split();
    let clocks = ClockControl::max(system.clock_control).freeze();
    let delay = Delay::new(&clocks);

    let io = IO::new(peripherals.GPIO, peripherals.IO_MUX);

    println!("OpenFlash ESP32 Firmware v{}", FIRMWARE_VERSION);
    println!("Protocol version: {}", PROTOCOL_VERSION);

    // Initialize UART for communication
    let uart_config = UartConfig::default().baudrate(115200);
    let mut uart = Uart::new(peripherals.UART0, uart_config, &clocks, io.pins.gpio1, io.pins.gpio3);

    // Initialize SPI for SPI NAND and eMMC (SPI2)
    let sck = io.pins.gpio18;
    let miso = io.pins.gpio19;
    let mosi = io.pins.gpio23;
    let _spi_nand_cs = Output::new(io.pins.gpio5, esp_hal::gpio::Level::High);
    let _emmc_cs = Output::new(io.pins.gpio4, esp_hal::gpio::Level::High);

    let _spi = Spi::new(
        peripherals.SPI2,
        40u32.MHz(),
        SpiMode::Mode0,
        &clocks,
    ).with_pins(Some(sck), Some(mosi), Some(miso), esp_hal::spi::master::NO_PIN);

    // Initialize SPI NOR controller (SPI3)
    // Using separate pins for SPI NOR to avoid conflicts
    let spi_nor_sck = io.pins.gpio14;
    let spi_nor_miso = io.pins.gpio12;
    let spi_nor_mosi = io.pins.gpio13;
    let spi_nor_cs = Output::new(io.pins.gpio27, esp_hal::gpio::Level::High);
    
    // SPI NOR uses up to 80MHz for fast operations
    let spi_nor = Spi::new(
        peripherals.SPI3,
        80u32.MHz(),
        SpiMode::Mode0,
        &clocks,
    ).with_pins(Some(spi_nor_sck), Some(spi_nor_mosi), Some(spi_nor_miso), esp_hal::spi::master::NO_PIN);
    
    let mut spi_nor_controller = SpiNorController::new(spi_nor, spi_nor_cs, delay);

    // Status LED (built-in on most ESP32 boards)
    let mut led = Output::new(io.pins.gpio2, esp_hal::gpio::Level::Low);
    let mut delay_led = Delay::new(&clocks);

    println!("Initialization complete");
    println!("Waiting for commands...");

    let mut cmd_buffer: Vec<u8, 256> = Vec::new();
    let mut data_buffer: [u8; 256] = [0u8; 256];

    loop {
        // Blink LED to show we're alive
        led.toggle();
        delay_led.delay_ms(100u32);

        // Read commands from UART
        let mut byte = [0u8; 1];
        if uart.read(&mut byte).is_ok() {
            if byte[0] == 0x0A || byte[0] == 0x0D {
                // End of command
                if !cmd_buffer.is_empty() {
                    process_command(&cmd_buffer, &mut uart, &mut spi_nor_controller, &mut data_buffer);
                    cmd_buffer.clear();
                }
            } else {
                let _ = cmd_buffer.push(byte[0]);
            }
        }
    }
}

fn process_command<T, SPI>(
    buffer: &[u8], 
    uart: &mut T,
    spi_nor: &mut SpiNorController<SPI>,
    data_buffer: &mut [u8; 256],
) 
where
    T: embedded_io::Write,
    SPI: esp_hal::spi::master::Instance,
{
    if buffer.is_empty() {
        return;
    }

    match Command::try_from(buffer[0]) {
        Ok(cmd) => match cmd {
            // System commands
            Command::Ping => {
                let _ = uart.write_all(b"PONG\n");
            }
            Command::GetVersion => {
                let _ = uart.write_all(b"OpenFlash ESP32 v");
                let _ = uart.write_all(FIRMWARE_VERSION.as_bytes());
                let _ = uart.write_all(b"\n");
            }
            Command::GetCapabilities => {
                let _ = uart.write_all(b"CAP:NAND,SPI_NAND,EMMC,SPI_NOR,WIFI\n");
            }
            Command::SetInterface => {
                if buffer.len() > 1 {
                    unsafe {
                        CURRENT_INTERFACE = match buffer[1] {
                            0x00 => Interface::ParallelNand,
                            0x01 => Interface::SpiNand,
                            0x02 => Interface::Emmc,
                            0x03 => Interface::SpiNor,
                            _ => CURRENT_INTERFACE,
                        };
                    }
                    let _ = uart.write_all(b"OK\n");
                } else {
                    let _ = uart.write_all(b"ERR:MISSING_PARAM\n");
                }
            }
            
            // SPI NOR commands
            Command::SpiNorReadJedecId => {
                let jedec_id = spi_nor.read_jedec_id();
                let _ = uart.write_all(b"JEDEC:");
                write_hex_byte(uart, jedec_id[0]);
                write_hex_byte(uart, jedec_id[1]);
                write_hex_byte(uart, jedec_id[2]);
                let _ = uart.write_all(b"\n");
            }
            Command::SpiNorReadStatus1 => {
                let status = spi_nor.read_status1();
                let _ = uart.write_all(b"SR1:");
                write_hex_byte(uart, status);
                let _ = uart.write_all(b"\n");
            }
            Command::SpiNorReadStatus2 => {
                let status = spi_nor.read_status2();
                let _ = uart.write_all(b"SR2:");
                write_hex_byte(uart, status);
                let _ = uart.write_all(b"\n");
            }
            Command::SpiNorReadStatus3 => {
                let status = spi_nor.read_status3();
                let _ = uart.write_all(b"SR3:");
                write_hex_byte(uart, status);
                let _ = uart.write_all(b"\n");
            }
            Command::SpiNorWriteEnable => {
                spi_nor.write_enable();
                let _ = uart.write_all(b"OK\n");
            }
            Command::SpiNorWriteDisable => {
                spi_nor.write_disable();
                let _ = uart.write_all(b"OK\n");
            }
            Command::SpiNorRead => {
                // Format: cmd, addr[3], len
                if buffer.len() >= 5 {
                    let address = ((buffer[1] as u32) << 16) 
                        | ((buffer[2] as u32) << 8) 
                        | (buffer[3] as u32);
                    let len = (buffer[4] as usize).min(256);
                    spi_nor.read(address, &mut data_buffer[..len]);
                    let _ = uart.write_all(b"DATA:");
                    for i in 0..len {
                        write_hex_byte(uart, data_buffer[i]);
                    }
                    let _ = uart.write_all(b"\n");
                } else {
                    let _ = uart.write_all(b"ERR:MISSING_PARAM\n");
                }
            }
            Command::SpiNorFastRead => {
                // Format: cmd, addr[3], len
                if buffer.len() >= 5 {
                    let address = ((buffer[1] as u32) << 16) 
                        | ((buffer[2] as u32) << 8) 
                        | (buffer[3] as u32);
                    let len = (buffer[4] as usize).min(256);
                    spi_nor.fast_read(address, &mut data_buffer[..len]);
                    let _ = uart.write_all(b"DATA:");
                    for i in 0..len {
                        write_hex_byte(uart, data_buffer[i]);
                    }
                    let _ = uart.write_all(b"\n");
                } else {
                    let _ = uart.write_all(b"ERR:MISSING_PARAM\n");
                }
            }
            Command::SpiNorPageProgram => {
                // Format: cmd, addr[3], data...
                if buffer.len() >= 5 {
                    let address = ((buffer[1] as u32) << 16) 
                        | ((buffer[2] as u32) << 8) 
                        | (buffer[3] as u32);
                    let data = &buffer[4..];
                    if spi_nor.page_program(address, data) {
                        let _ = uart.write_all(b"OK\n");
                    } else {
                        let _ = uart.write_all(b"ERR:PROGRAM_FAILED\n");
                    }
                } else {
                    let _ = uart.write_all(b"ERR:MISSING_PARAM\n");
                }
            }
            Command::SpiNorSectorErase => {
                // Format: cmd, addr[3]
                if buffer.len() >= 4 {
                    let address = ((buffer[1] as u32) << 16) 
                        | ((buffer[2] as u32) << 8) 
                        | (buffer[3] as u32);
                    if spi_nor.sector_erase(address) {
                        let _ = uart.write_all(b"OK\n");
                    } else {
                        let _ = uart.write_all(b"ERR:ERASE_FAILED\n");
                    }
                } else {
                    let _ = uart.write_all(b"ERR:MISSING_PARAM\n");
                }
            }
            Command::SpiNorBlockErase32K => {
                // Format: cmd, addr[3]
                if buffer.len() >= 4 {
                    let address = ((buffer[1] as u32) << 16) 
                        | ((buffer[2] as u32) << 8) 
                        | (buffer[3] as u32);
                    if spi_nor.block_erase_32k(address) {
                        let _ = uart.write_all(b"OK\n");
                    } else {
                        let _ = uart.write_all(b"ERR:ERASE_FAILED\n");
                    }
                } else {
                    let _ = uart.write_all(b"ERR:MISSING_PARAM\n");
                }
            }
            Command::SpiNorBlockErase64K => {
                // Format: cmd, addr[3]
                if buffer.len() >= 4 {
                    let address = ((buffer[1] as u32) << 16) 
                        | ((buffer[2] as u32) << 8) 
                        | (buffer[3] as u32);
                    if spi_nor.block_erase_64k(address) {
                        let _ = uart.write_all(b"OK\n");
                    } else {
                        let _ = uart.write_all(b"ERR:ERASE_FAILED\n");
                    }
                } else {
                    let _ = uart.write_all(b"ERR:MISSING_PARAM\n");
                }
            }
            Command::SpiNorChipErase => {
                if spi_nor.chip_erase() {
                    let _ = uart.write_all(b"OK\n");
                } else {
                    let _ = uart.write_all(b"ERR:ERASE_FAILED\n");
                }
            }
            Command::SpiNorWriteStatus1 => {
                if buffer.len() >= 2 {
                    spi_nor.write_status1(buffer[1]);
                    let _ = uart.write_all(b"OK\n");
                } else {
                    let _ = uart.write_all(b"ERR:MISSING_PARAM\n");
                }
            }
            Command::SpiNorWriteStatus2 => {
                if buffer.len() >= 2 {
                    spi_nor.write_status2(buffer[1]);
                    let _ = uart.write_all(b"OK\n");
                } else {
                    let _ = uart.write_all(b"ERR:MISSING_PARAM\n");
                }
            }
            Command::SpiNorWriteStatus3 => {
                if buffer.len() >= 2 {
                    spi_nor.write_status3(buffer[1]);
                    let _ = uart.write_all(b"OK\n");
                } else {
                    let _ = uart.write_all(b"ERR:MISSING_PARAM\n");
                }
            }
            Command::SpiNorReset => {
                spi_nor.reset();
                let _ = uart.write_all(b"OK\n");
            }
            Command::SpiNorReadSfdp => {
                // Format: cmd, addr[3], len
                if buffer.len() >= 5 {
                    let address = ((buffer[1] as u32) << 16) 
                        | ((buffer[2] as u32) << 8) 
                        | (buffer[3] as u32);
                    let len = (buffer[4] as usize).min(256);
                    spi_nor.read_sfdp(address, &mut data_buffer[..len]);
                    let _ = uart.write_all(b"SFDP:");
                    for i in 0..len {
                        write_hex_byte(uart, data_buffer[i]);
                    }
                    let _ = uart.write_all(b"\n");
                } else {
                    let _ = uart.write_all(b"ERR:MISSING_PARAM\n");
                }
            }
            
            // Other commands not yet implemented
            _ => {
                let _ = uart.write_all(b"ERR:NOT_IMPLEMENTED\n");
            }
        },
        Err(_) => {
            let _ = uart.write_all(b"ERR:UNKNOWN_CMD\n");
        }
    }
}

/// Write a byte as two hex characters
fn write_hex_byte<T: embedded_io::Write>(uart: &mut T, byte: u8) {
    const HEX_CHARS: &[u8] = b"0123456789ABCDEF";
    let _ = uart.write_all(&[HEX_CHARS[(byte >> 4) as usize]]);
    let _ = uart.write_all(&[HEX_CHARS[(byte & 0x0F) as usize]]);
}
