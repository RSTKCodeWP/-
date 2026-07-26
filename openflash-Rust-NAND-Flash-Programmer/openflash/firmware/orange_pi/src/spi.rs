//! SPI driver for Orange Pi
//!
//! Uses Linux spidev interface.

use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use thiserror::Error;

/// SPI device path
pub const SPI_DEV: &str = "/dev/spidev0.0";

/// SPI controller
pub struct SpiController {
    device: Option<File>,
    speed_hz: u32,
}

#[derive(Error, Debug)]
pub enum SpiError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    
    #[error("Not initialized")]
    NotInitialized,
}

impl SpiController {
    pub fn new() -> Self {
        Self {
            device: None,
            speed_hz: 10_000_000,
        }
    }
    
    /// Initialize SPI device
    pub fn init(&mut self) -> Result<(), SpiError> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .open(SPI_DEV)?;
        
        self.device = Some(file);
        Ok(())
    }
    
    /// Set SPI speed
    pub fn set_speed(&mut self, speed_hz: u32) {
        self.speed_hz = speed_hz;
    }
    
    /// Transfer data
    pub fn transfer(&mut self, data: &mut [u8]) -> Result<(), SpiError> {
        let device = self.device.as_mut().ok_or(SpiError::NotInitialized)?;
        device.write_all(data)?;
        device.read_exact(data)?;
        Ok(())
    }
    
    /// Write data
    pub fn write(&mut self, data: &[u8]) -> Result<(), SpiError> {
        let device = self.device.as_mut().ok_or(SpiError::NotInitialized)?;
        device.write_all(data)?;
        Ok(())
    }
}
