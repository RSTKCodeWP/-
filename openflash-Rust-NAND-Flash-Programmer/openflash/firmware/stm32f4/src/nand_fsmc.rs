//! Parallel NAND Controller using FSMC for STM32F4
//! 
//! Uses FSMC (Flexible Static Memory Controller) for high-speed parallel NAND access
//! Much faster than GPIO bit-banging

use embassy_stm32::gpio::{Input, Output, Level, Pull};
use defmt::*;

/// NAND Commands
pub mod cmd {
    pub const READ_ID: u8 = 0x90;
    pub const READ_STATUS: u8 = 0x70;
    pub const READ_PAGE: u8 = 0x00;
    pub const READ_PAGE_CONFIRM: u8 = 0x30;
    pub const PROGRAM_PAGE: u8 = 0x80;
    pub const PROGRAM_PAGE_CONFIRM: u8 = 0x10;
    pub const ERASE_BLOCK: u8 = 0x60;
    pub const ERASE_BLOCK_CONFIRM: u8 = 0xD0;
    pub const RESET: u8 = 0xFF;
}

/// FSMC NAND Bank addresses
pub mod bank {
    pub const NAND_BANK2_DATA: u32 = 0x7000_0000;
    pub const NAND_BANK2_CMD: u32 = 0x7001_0000;  // A16 = CLE
    pub const NAND_BANK2_ADDR: u32 = 0x7002_0000; // A17 = ALE
}

/// Status register bits
pub mod status {
    pub const FAIL: u8 = 0x01;
    pub const READY: u8 = 0x40;
    pub const WRITE_PROTECT: u8 = 0x80;
}
