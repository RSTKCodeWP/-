//! SPI interface for Banana Pi boards
//!
//! Uses Linux spidev for hardware SPI access.
//! This is the recommended interface for flash operations on SBCs.

use std::fs::{File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::unix::io::AsRawFd;

/// SPI mode flags
pub const SPI_MODE_0: u8 = 0;
pub const SPI_MODE_1: u8 = 1;
pub const SPI_MODE_2: u8 = 2;
pub const SPI_MODE_3: u8 = 3;

/// SPI controller using spidev
pub struct SpiDev {
    file: File,
    speed_hz: u32,
    mode: u8,
}

impl SpiDev {
    /// Open SPI device
    pub fn open(path: &str) -> io::Result<Self> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .open(path)?;
        
        Ok(Self {
            file,
            speed_hz: 1_000_000, // 1MHz default
            mode: SPI_MODE_0,
        })
    }
    
    /// Set SPI speed
    pub fn set_speed(&mut self, hz: u32) -> io::Result<()> {
        self.speed_hz = hz;
        // Use ioctl to set speed
        unsafe {
            let fd = self.file.as_raw_fd();
            let speed = hz;
            // SPI_IOC_WR_MAX_SPEED_HZ = 0x40046B04
            if libc::ioctl(fd, 0x40046B04, &speed) < 0 {
                return Err(io::Error::last_os_error());
            }
        }
        Ok(())
    }
    
    /// Set SPI mode
    pub fn set_mode(&mut self, mode: u8) -> io::Result<()> {
        self.mode = mode;
        unsafe {
            let fd = self.file.as_raw_fd();
            // SPI_IOC_WR_MODE = 0x40016B01
            if libc::ioctl(fd, 0x40016B01, &mode) < 0 {
                return Err(io::Error::last_os_error());
            }
        }
        Ok(())
    }
    
    /// Transfer data (full duplex)
    pub fn transfer(&mut self, tx: &[u8], rx: &mut [u8]) -> io::Result<()> {
        // For simple transfers, we can use read/write
        // For full duplex, we need ioctl with spi_ioc_transfer
        self.file.write_all(tx)?;
        self.file.read_exact(rx)?;
        Ok(())
    }
    
    /// Write data
    pub fn write(&mut self, data: &[u8]) -> io::Result<()> {
        self.file.write_all(data)
    }
    
    /// Read data
    pub fn read(&mut self, buffer: &mut [u8]) -> io::Result<()> {
        self.file.read_exact(buffer)
    }
}

/// Read JEDEC ID from SPI NOR flash
pub fn read_jedec_id(spi_dev: &str) -> io::Result<[u8; 3]> {
    let mut spi = SpiDev::open(spi_dev)?;
    spi.set_speed(1_000_000)?; // 1MHz for ID read
    
    // Send JEDEC ID command (0x9F)
    spi.write(&[0x9F])?;
    
    // Read 3 bytes
    let mut id = [0u8; 3];
    spi.read(&mut id)?;
    
    Ok(id)
}

/// Read SPI NAND ID
pub fn read_spi_nand_id(spi_dev: &str) -> io::Result<[u8; 2]> {
    let mut spi = SpiDev::open(spi_dev)?;
    spi.set_speed(1_000_000)?;
    
    // Send Read ID command (0x9F) + dummy byte
    spi.write(&[0x9F, 0x00])?;
    
    // Read 2 bytes
    let mut id = [0u8; 2];
    spi.read(&mut id)?;
    
    Ok(id)
}

/// SPI NAND operations
pub struct SpiNand {
    spi: SpiDev,
}

impl SpiNand {
    pub fn new(spi_dev: &str) -> io::Result<Self> {
        let mut spi = SpiDev::open(spi_dev)?;
        spi.set_speed(40_000_000)?; // 40MHz
        Ok(Self { spi })
    }
    
    /// Reset chip
    pub fn reset(&mut self) -> io::Result<()> {
        self.spi.write(&[0xFF]) // Reset command
    }
    
    /// Read ID
    pub fn read_id(&mut self) -> io::Result<[u8; 2]> {
        self.spi.write(&[0x9F, 0x00])?;
        let mut id = [0u8; 2];
        self.spi.read(&mut id)?;
        Ok(id)
    }
    
    /// Get feature register
    pub fn get_feature(&mut self, addr: u8) -> io::Result<u8> {
        self.spi.write(&[0x0F, addr])?;
        let mut val = [0u8; 1];
        self.spi.read(&mut val)?;
        Ok(val[0])
    }
    
    /// Set feature register
    pub fn set_feature(&mut self, addr: u8, val: u8) -> io::Result<()> {
        self.spi.write(&[0x1F, addr, val])
    }
    
    /// Write enable
    pub fn write_enable(&mut self) -> io::Result<()> {
        self.spi.write(&[0x06])
    }
    
    /// Page read to cache
    pub fn page_read(&mut self, page_addr: u32) -> io::Result<()> {
        let cmd = [
            0x13, // Page Read command
            ((page_addr >> 16) & 0xFF) as u8,
            ((page_addr >> 8) & 0xFF) as u8,
            (page_addr & 0xFF) as u8,
        ];
        self.spi.write(&cmd)
    }
    
    /// Read from cache
    pub fn read_cache(&mut self, col_addr: u16, buffer: &mut [u8]) -> io::Result<()> {
        let cmd = [
            0x03, // Read from cache
            ((col_addr >> 8) & 0xFF) as u8,
            (col_addr & 0xFF) as u8,
            0x00, // Dummy byte
        ];
        self.spi.write(&cmd)?;
        self.spi.read(buffer)
    }
}

/// SPI NOR operations
pub struct SpiNor {
    spi: SpiDev,
}

impl SpiNor {
    pub fn new(spi_dev: &str) -> io::Result<Self> {
        let mut spi = SpiDev::open(spi_dev)?;
        spi.set_speed(50_000_000)?; // 50MHz
        Ok(Self { spi })
    }
    
    /// Read JEDEC ID
    pub fn read_jedec_id(&mut self) -> io::Result<[u8; 3]> {
        self.spi.write(&[0x9F])?;
        let mut id = [0u8; 3];
        self.spi.read(&mut id)?;
        Ok(id)
    }
    
    /// Read status register
    pub fn read_status(&mut self) -> io::Result<u8> {
        self.spi.write(&[0x05])?;
        let mut status = [0u8; 1];
        self.spi.read(&mut status)?;
        Ok(status[0])
    }
    
    /// Write enable
    pub fn write_enable(&mut self) -> io::Result<()> {
        self.spi.write(&[0x06])
    }
    
    /// Read data
    pub fn read(&mut self, addr: u32, buffer: &mut [u8]) -> io::Result<()> {
        let cmd = [
            0x03, // Read command
            ((addr >> 16) & 0xFF) as u8,
            ((addr >> 8) & 0xFF) as u8,
            (addr & 0xFF) as u8,
        ];
        self.spi.write(&cmd)?;
        self.spi.read(buffer)
    }
    
    /// Fast read
    pub fn fast_read(&mut self, addr: u32, buffer: &mut [u8]) -> io::Result<()> {
        let cmd = [
            0x0B, // Fast Read command
            ((addr >> 16) & 0xFF) as u8,
            ((addr >> 8) & 0xFF) as u8,
            (addr & 0xFF) as u8,
            0x00, // Dummy byte
        ];
        self.spi.write(&cmd)?;
        self.spi.read(buffer)
    }
}
