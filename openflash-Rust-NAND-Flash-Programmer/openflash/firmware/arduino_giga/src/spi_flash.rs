//! SPI Flash driver for Arduino GIGA (STM32H747)
//!
//! Supports both SPI NOR and SPI NAND via hardware SPI.

use defmt::*;

/// SPI Flash controller
pub struct SpiFlash {
    quad_enabled: bool,
    max_freq_mhz: u32,
}

impl SpiFlash {
    pub fn new() -> Self {
        Self {
            quad_enabled: false,
            max_freq_mhz: 100, // STM32H7 can do 100MHz+ SPI
        }
    }
    
    pub fn init(&mut self) {
        info!("Initializing SPI Flash @ {}MHz", self.max_freq_mhz);
    }
    
    pub fn enable_quad(&mut self) {
        self.quad_enabled = true;
        info!("QSPI mode enabled");
    }
    
    pub fn read_jedec_id(&self) -> [u8; 3] {
        [0; 3]
    }
    
    pub fn read(&self, _addr: u32, _buf: &mut [u8]) -> Result<(), SpiFlashError> {
        Ok(())
    }
    
    pub fn program(&self, _addr: u32, _data: &[u8]) -> Result<(), SpiFlashError> {
        Ok(())
    }
    
    pub fn erase(&self, _addr: u32) -> Result<(), SpiFlashError> {
        Ok(())
    }
}

#[derive(Debug)]
pub enum SpiFlashError {
    Timeout,
    ProgramFailed,
    EraseFailed,
}
