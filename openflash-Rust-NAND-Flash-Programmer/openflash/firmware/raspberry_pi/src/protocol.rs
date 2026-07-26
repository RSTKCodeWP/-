//! Protocol definitions for Raspberry Pi driver

use serde::{Deserialize, Serialize};

/// Protocol version
pub const PROTOCOL_VERSION: u8 = 0x23;

/// Command types
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum Command {
    Ping = 0x00,
    GetDeviceInfo = 0x01,
    GetVersion = 0x02,
    
    // NAND commands
    NandReadId = 0x10,
    NandReadPage = 0x11,
    NandProgramPage = 0x12,
    NandEraseBlock = 0x13,
    NandReadStatus = 0x14,
    
    // SPI commands
    SpiReadJedecId = 0x20,
    SpiRead = 0x21,
    SpiProgram = 0x22,
    SpiErase = 0x23,
    SpiReadStatus = 0x24,
    
    // eMMC commands
    EmmcReadCid = 0x30,
    EmmcReadBlock = 0x31,
    EmmcWriteBlock = 0x32,
}

/// Response status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum Status {
    Ok = 0x00,
    Error = 0x01,
    Busy = 0x02,
    Timeout = 0x03,
    InvalidCommand = 0xFF,
}

/// Device capabilities
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Capabilities {
    pub parallel_nand: bool,
    pub spi_nand: bool,
    pub spi_nor: bool,
    pub emmc: bool,
    pub high_speed_spi: bool,
}

impl Default for Capabilities {
    fn default() -> Self {
        Self {
            parallel_nand: true,
            spi_nand: true,
            spi_nor: true,
            emmc: true,
            high_speed_spi: true,
        }
    }
}
