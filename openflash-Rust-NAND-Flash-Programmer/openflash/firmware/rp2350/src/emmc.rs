//! eMMC driver for RP2350

use defmt::*;

/// eMMC controller
pub struct Emmc {
    hs200_enabled: bool,
}

impl Emmc {
    pub fn new() -> Self {
        Self {
            hs200_enabled: false,
        }
    }
    
    pub fn init(&mut self) {
        info!("Initializing eMMC controller");
    }
    
    pub fn read_cid(&self) -> [u8; 16] {
        [0; 16]
    }
    
    pub fn read_block(&self, _lba: u32, _buf: &mut [u8]) -> Result<(), EmmcError> {
        Ok(())
    }
    
    pub fn write_block(&self, _lba: u32, _data: &[u8]) -> Result<(), EmmcError> {
        Ok(())
    }
}

#[derive(Debug)]
pub enum EmmcError {
    Timeout,
    CrcError,
    WriteFailed,
}
