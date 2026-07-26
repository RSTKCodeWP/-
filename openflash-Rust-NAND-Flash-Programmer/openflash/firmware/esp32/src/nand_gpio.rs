//! Parallel NAND GPIO Controller for ESP32
//! 
//! Bit-bang parallel NAND interface using GPIO pins

use embedded_hal::digital::{InputPin, OutputPin};

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

/// Status register bits
pub mod status {
    pub const FAIL: u8 = 0x01;        // Program/Erase fail
    pub const READY: u8 = 0x40;       // Ready (1) / Busy (0)
    pub const WRITE_PROTECT: u8 = 0x80; // Write protected
}

/// NAND timing constants (nanoseconds)
pub mod timing {
    pub const T_WP: u32 = 25;   // Write pulse width
    pub const T_WH: u32 = 15;   // Write hold time
    pub const T_RP: u32 = 25;   // Read pulse width
    pub const T_REH: u32 = 15;  // Read hold time
    pub const T_CS: u32 = 35;   // CE# setup time
    pub const T_CLS: u32 = 15;  // CLE setup time
    pub const T_ALS: u32 = 15;  // ALE setup time
}
