//! SPI NOR driver for RP2350

use defmt::*;

/// SPI NOR commands
pub mod commands {
    pub const READ_JEDEC_ID: u8 = 0x9F;
    pub const READ_SFDP: u8 = 0x5A;
    pub const READ: u8 = 0x03;
    pub const FAST_READ: u8 = 0x0B;
    pub const FAST_READ_DUAL: u8 = 0x3B;
    pub const FAST_READ_QUAD: u8 = 0x6B;
    pub const PAGE_PROGRAM: u8 = 0x02;
    pub const SECTOR_ERASE: u8 = 0x20;
    pub const BLOCK_ERASE_32K: u8 = 0x52;
    pub const BLOCK_ERASE_64K: u8 = 0xD8;
    pub const CHIP_ERASE: u8 = 0xC7;
    pub const WRITE_ENABLE: u8 = 0x06;
    pub const WRITE_DISABLE: u8 = 0x04;
    pub const READ_STATUS: u8 = 0x05;
    pub const WRITE_STATUS: u8 = 0x01;
}

/// SPI NOR controller
pub struct SpiNor {
    quad_enabled: bool,
    four_byte_addr: bool,
}

impl SpiNor {
    pub fn new() -> Self {
        Self {
            quad_enabled: false,
            four_byte_addr: false,
        }
    }
    
    pub fn init(&mut self) {
        info!("Initializing SPI NOR controller");
    }
    
    pub fn read_jedec_id(&self) -> [u8; 3] {
        [0; 3]
    }
    
    pub fn read(&self, _addr: u32, _buf: &mut [u8]) -> Result<(), SpiNorError> {
        Ok(())
    }
    
    pub fn program_page(&self, _addr: u32, _data: &[u8]) -> Result<(), SpiNorError> {
        Ok(())
    }
    
    pub fn erase_sector(&self, _addr: u32) -> Result<(), SpiNorError> {
        Ok(())
    }
}

#[derive(Debug)]
pub enum SpiNorError {
    Timeout,
    ProgramFailed,
    EraseFailed,
}
