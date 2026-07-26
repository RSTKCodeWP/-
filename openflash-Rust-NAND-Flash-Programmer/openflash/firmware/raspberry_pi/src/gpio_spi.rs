//! SPI driver for Raspberry Pi
//!
//! Uses hardware SPI via rppal for SPI NOR and SPI NAND.

use rppal::spi::{Bus, Mode, SlaveSelect, Spi};
use thiserror::Error;

/// SPI configuration
pub struct SpiConfig {
    pub bus: Bus,
    pub slave_select: SlaveSelect,
    pub clock_speed: u32,
    pub mode: Mode,
}

impl Default for SpiConfig {
    fn default() -> Self {
        Self {
            bus: Bus::Spi0,
            slave_select: SlaveSelect::Ss0,
            clock_speed: 10_000_000, // 10 MHz
            mode: Mode::Mode0,
        }
    }
}

/// SPI controller
pub struct GpioSpi {
    spi: Option<Spi>,
    config: SpiConfig,
}

#[derive(Error, Debug)]
pub enum SpiError {
    #[error("SPI error: {0}")]
    Spi(#[from] rppal::spi::Error),
    
    #[error("Not initialized")]
    NotInitialized,
    
    #[error("Timeout")]
    Timeout,
}

impl GpioSpi {
    pub fn new(config: SpiConfig) -> Self {
        Self {
            spi: None,
            config,
        }
    }
    
    /// Initialize SPI
    pub fn init(&mut self) -> Result<(), SpiError> {
        let spi = Spi::new(
            self.config.bus,
            self.config.slave_select,
            self.config.clock_speed,
            self.config.mode,
        )?;
        
        self.spi = Some(spi);
        Ok(())
    }
    
    /// Transfer data (full duplex)
    pub fn transfer(&mut self, data: &mut [u8]) -> Result<(), SpiError> {
        let spi = self.spi.as_mut().ok_or(SpiError::NotInitialized)?;
        spi.transfer(data)?;
        Ok(())
    }
    
    /// Write data
    pub fn write(&mut self, data: &[u8]) -> Result<(), SpiError> {
        let spi = self.spi.as_mut().ok_or(SpiError::NotInitialized)?;
        spi.write(data)?;
        Ok(())
    }
    
    /// Read JEDEC ID (SPI NOR/NAND)
    pub fn read_jedec_id(&mut self) -> Result<[u8; 3], SpiError> {
        let mut buf = [0x9F, 0, 0, 0]; // READ_JEDEC_ID command
        self.transfer(&mut buf)?;
        Ok([buf[1], buf[2], buf[3]])
    }
    
    /// Read status register
    pub fn read_status(&mut self) -> Result<u8, SpiError> {
        let mut buf = [0x05, 0]; // READ_STATUS command
        self.transfer(&mut buf)?;
        Ok(buf[1])
    }
    
    /// Write enable
    pub fn write_enable(&mut self) -> Result<(), SpiError> {
        self.write(&[0x06]) // WRITE_ENABLE command
    }
    
    /// Wait for write complete
    pub fn wait_busy(&mut self, timeout_ms: u64) -> Result<(), SpiError> {
        let start = std::time::Instant::now();
        let timeout = std::time::Duration::from_millis(timeout_ms);
        
        while start.elapsed() < timeout {
            let status = self.read_status()?;
            if status & 0x01 == 0 {
                return Ok(());
            }
            std::thread::sleep(std::time::Duration::from_micros(100));
        }
        
        Err(SpiError::Timeout)
    }
}
