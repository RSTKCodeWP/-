//! eMMC Controller for STM32F4
//! 
//! Uses SPI2 peripheral with DMA support

use embassy_stm32::spi::{Spi, Config as SpiConfig};
use embassy_stm32::gpio::{Output, Level};
use defmt::*;

/// MMC/SD Commands (SPI mode)
pub mod cmd {
    pub const GO_IDLE_STATE: u8 = 0;
    pub const SEND_OP_COND: u8 = 1;
    pub const SEND_CID: u8 = 10;
    pub const SEND_CSD: u8 = 9;
    pub const READ_SINGLE_BLOCK: u8 = 17;
    pub const WRITE_BLOCK: u8 = 24;
    pub const ERASE: u8 = 38;
    pub const APP_CMD: u8 = 55;
    pub const READ_OCR: u8 = 58;
}

/// R1 Response bits
pub mod r1 {
    pub const IDLE: u8 = 0x01;
    pub const ILLEGAL_CMD: u8 = 0x04;
    pub const CRC_ERROR: u8 = 0x08;
}
