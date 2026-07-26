//! eMMC Controller for ESP32
//! 
//! Supports eMMC/MMC cards via SPI mode

use embedded_hal::spi::SpiDevice;
use embedded_hal::digital::OutputPin;

/// MMC/SD Commands (SPI mode)
pub mod cmd {
    pub const GO_IDLE_STATE: u8 = 0;
    pub const SEND_OP_COND: u8 = 1;
    pub const ALL_SEND_CID: u8 = 2;
    pub const SEND_RELATIVE_ADDR: u8 = 3;
    pub const SWITCH_FUNC: u8 = 6;
    pub const SELECT_CARD: u8 = 7;
    pub const SEND_IF_COND: u8 = 8;
    pub const SEND_CSD: u8 = 9;
    pub const SEND_CID: u8 = 10;
    pub const STOP_TRANSMISSION: u8 = 12;
    pub const SEND_STATUS: u8 = 13;
    pub const SET_BLOCKLEN: u8 = 16;
    pub const READ_SINGLE_BLOCK: u8 = 17;
    pub const READ_MULTIPLE_BLOCK: u8 = 18;
    pub const WRITE_BLOCK: u8 = 24;
    pub const WRITE_MULTIPLE_BLOCK: u8 = 25;
    pub const ERASE_WR_BLK_START: u8 = 32;
    pub const ERASE_WR_BLK_END: u8 = 33;
    pub const ERASE: u8 = 38;
    pub const APP_CMD: u8 = 55;
    pub const READ_OCR: u8 = 58;
    pub const CRC_ON_OFF: u8 = 59;
}

/// R1 Response bits
pub mod r1 {
    pub const IDLE: u8 = 0x01;
    pub const ERASE_RESET: u8 = 0x02;
    pub const ILLEGAL_CMD: u8 = 0x04;
    pub const CRC_ERROR: u8 = 0x08;
    pub const ERASE_SEQ_ERROR: u8 = 0x10;
    pub const ADDRESS_ERROR: u8 = 0x20;
    pub const PARAM_ERROR: u8 = 0x40;
}
