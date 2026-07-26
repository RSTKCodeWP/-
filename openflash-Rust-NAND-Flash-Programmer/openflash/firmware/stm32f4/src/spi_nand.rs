//! SPI NAND Controller for STM32F4
//! 
//! Uses SPI1 peripheral with DMA support

use embassy_stm32::spi::{Spi, Config as SpiConfig};
use embassy_stm32::gpio::{Output, Level};
use defmt::*;

/// SPI NAND Commands
pub mod cmd {
    pub const READ_ID: u8 = 0x9F;
    pub const GET_FEATURE: u8 = 0x0F;
    pub const SET_FEATURE: u8 = 0x1F;
    pub const WRITE_ENABLE: u8 = 0x06;
    pub const WRITE_DISABLE: u8 = 0x04;
    pub const PAGE_READ: u8 = 0x13;
    pub const READ_FROM_CACHE: u8 = 0x03;
    pub const READ_FROM_CACHE_X4: u8 = 0x6B;
    pub const PROGRAM_LOAD: u8 = 0x02;
    pub const PROGRAM_LOAD_X4: u8 = 0x32;
    pub const PROGRAM_EXECUTE: u8 = 0x10;
    pub const BLOCK_ERASE: u8 = 0xD8;
    pub const RESET: u8 = 0xFF;
}

/// Feature register addresses
pub mod feature {
    pub const PROTECTION: u8 = 0xA0;
    pub const FEATURE: u8 = 0xB0;
    pub const STATUS: u8 = 0xC0;
}

/// Status register bits
pub mod status {
    pub const OIP: u8 = 0x01;
    pub const WEL: u8 = 0x02;
    pub const EFAIL: u8 = 0x04;
    pub const PFAIL: u8 = 0x08;
}
