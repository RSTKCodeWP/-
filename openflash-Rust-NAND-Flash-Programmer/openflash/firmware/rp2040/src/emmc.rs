//! eMMC Flash driver for RP2040
//! Uses SPI mode for eMMC communication (simpler than SD mode)

use embassy_rp::gpio::{Level, Output};
use embassy_rp::spi::{Spi, Config as SpiConfig};
use embassy_time::{Duration, Timer};

/// eMMC/MMC SPI mode commands
pub mod commands {
    pub const GO_IDLE_STATE: u8 = 0;        // CMD0
    pub const SEND_OP_COND: u8 = 1;         // CMD1
    pub const SEND_CID: u8 = 10;            // CMD10
    pub const SEND_CSD: u8 = 9;             // CMD9
    pub const SEND_EXT_CSD: u8 = 8;         // CMD8 (in SPI mode, different usage)
    pub const SET_BLOCKLEN: u8 = 16;        // CMD16
    pub const READ_SINGLE_BLOCK: u8 = 17;   // CMD17
    pub const READ_MULTIPLE_BLOCK: u8 = 18; // CMD18
    pub const WRITE_BLOCK: u8 = 24;         // CMD24
    pub const WRITE_MULTIPLE_BLOCK: u8 = 25;// CMD25
    pub const ERASE_WR_BLK_START: u8 = 32;  // CMD32
    pub const ERASE_WR_BLK_END: u8 = 33;    // CMD33
    pub const ERASE: u8 = 38;               // CMD38
    pub const APP_CMD: u8 = 55;             // CMD55
    pub const READ_OCR: u8 = 58;            // CMD58
    pub const CRC_ON_OFF: u8 = 59;          // CMD59
    pub const STOP_TRANSMISSION: u8 = 12;   // CMD12
}

/// SPI mode R1 response bits
pub mod r1_status {
    pub const IDLE_STATE: u8 = 0x01;
    pub const ERASE_RESET: u8 = 0x02;
    pub const ILLEGAL_CMD: u8 = 0x04;
    pub const CRC_ERROR: u8 = 0x08;
    pub const ERASE_SEQ_ERROR: u8 = 0x10;
    pub const ADDRESS_ERROR: u8 = 0x20;
    pub const PARAM_ERROR: u8 = 0x40;
}

/// Data response tokens
pub mod data_tokens {
    pub const START_BLOCK: u8 = 0xFE;
    pub const START_MULTI_BLOCK: u8 = 0xFC;
    pub const STOP_TRAN: u8 = 0xFD;
    pub const DATA_ACCEPTED: u8 = 0x05;
    pub const DATA_CRC_ERROR: u8 = 0x0B;
    pub const DATA_WRITE_ERROR: u8 = 0x0D;
}

/// eMMC partition types
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum EmmcPartition {
    UserData = 0,
    Boot1 = 1,
    Boot2 = 2,
    Rpmb = 3,
}

/// eMMC controller using SPI mode
pub struct EmmcController<'d, SPI: embassy_rp::spi::Instance> {
    spi: Spi<'d, SPI, embassy_rp::spi::Blocking>,
    cs: Output<'d>,
    sector_count: u32,
    high_capacity: bool,
    initialized: bool,
}

impl<'d, SPI: embassy_rp::spi::Instance> EmmcController<'d, SPI> {
    /// Create a new eMMC controller
    pub fn new(
        spi: Spi<'d, SPI, embassy_rp::spi::Blocking>,
        cs: Output<'d>,
    ) -> Self {
        Self {
            spi,
            cs,
            sector_count: 0,
            high_capacity: false,
            initialized: false,
        }
    }

    /// Assert chip select (active low)
    fn cs_low(&mut self) {
        self.cs.set_low();
    }

    /// Deassert chip select
    fn cs_high(&mut self) {
        self.cs.set_high();
    }

    /// Send dummy clocks with CS high (required for initialization)
    fn send_clocks(&mut self, count: usize) {
        self.cs_high();
        let dummy = [0xFF; 1];
        for _ in 0..count {
            let _ = self.spi.blocking_write(&dummy);
        }
    }

    /// Wait for card to be ready (not busy)
    async fn wait_ready(&mut self) -> bool {
        let mut buf = [0u8; 1];
        for _ in 0..1000 {
            let _ = self.spi.blocking_read(&mut buf);
            if buf[0] == 0xFF {
                return true;
            }
            Timer::after(Duration::from_micros(100)).await;
        }
        false
    }

    /// Send command and get R1 response
    fn send_cmd(&mut self, cmd: u8, arg: u32) -> u8 {
        // Wait for card ready
        let mut dummy = [0xFF; 1];
        let _ = self.spi.blocking_write(&dummy);

        // Build command packet
        let cmd_buf = [
            0x40 | cmd,                    // Command index with start bits
            ((arg >> 24) & 0xFF) as u8,
            ((arg >> 16) & 0xFF) as u8,
            ((arg >> 8) & 0xFF) as u8,
            (arg & 0xFF) as u8,
            Self::crc7_cmd(cmd, arg),      // CRC7 + stop bit
        ];

        self.cs_low();
        let _ = self.spi.blocking_write(&cmd_buf);

        // Wait for response (R1)
        let mut response = 0xFF;
        for _ in 0..10 {
            let _ = self.spi.blocking_read(&mut dummy);
            if dummy[0] != 0xFF {
                response = dummy[0];
                break;
            }
        }
        self.cs_high();
        
        // Extra clock
        let _ = self.spi.blocking_write(&[0xFF]);
        
        response
    }

    /// Send command with CS held low (for data transfer)
    fn send_cmd_hold(&mut self, cmd: u8, arg: u32) -> u8 {
        let mut dummy = [0xFF; 1];
        let _ = self.spi.blocking_write(&dummy);

        let cmd_buf = [
            0x40 | cmd,
            ((arg >> 24) & 0xFF) as u8,
            ((arg >> 16) & 0xFF) as u8,
            ((arg >> 8) & 0xFF) as u8,
            (arg & 0xFF) as u8,
            Self::crc7_cmd(cmd, arg),
        ];

        self.cs_low();
        let _ = self.spi.blocking_write(&cmd_buf);

        let mut response = 0xFF;
        for _ in 0..10 {
            let _ = self.spi.blocking_read(&mut dummy);
            if dummy[0] != 0xFF {
                response = dummy[0];
                break;
            }
        }
        // Note: CS stays low for data transfer
        response
    }

    /// Calculate CRC7 for command
    fn crc7_cmd(cmd: u8, arg: u32) -> u8 {
        let data = [
            0x40 | cmd,
            ((arg >> 24) & 0xFF) as u8,
            ((arg >> 16) & 0xFF) as u8,
            ((arg >> 8) & 0xFF) as u8,
            (arg & 0xFF) as u8,
        ];
        
        let mut crc: u8 = 0;
        for &byte in &data {
            for i in (0..8).rev() {
                crc <<= 1;
                if ((byte >> i) & 1) ^ ((crc >> 7) & 1) != 0 {
                    crc ^= 0x09;
                }
            }
        }
        (crc << 1) | 1
    }

    /// Initialize eMMC card in SPI mode
    pub async fn init(&mut self) -> bool {
        // Send 80+ clocks with CS high
        self.send_clocks(10);
        Timer::after(Duration::from_millis(10)).await;

        // CMD0 - Go to idle state
        let mut retries = 100;
        loop {
            let r1 = self.send_cmd(commands::GO_IDLE_STATE, 0);
            if r1 == r1_status::IDLE_STATE {
                break;
            }
            retries -= 1;
            if retries == 0 {
                return false;
            }
            Timer::after(Duration::from_millis(10)).await;
        }

        // CMD1 - Send OP_COND (MMC initialization)
        retries = 1000;
        loop {
            let r1 = self.send_cmd(commands::SEND_OP_COND, 0x40000000); // HCS bit
            if r1 == 0x00 {
                break;
            }
            if r1 != r1_status::IDLE_STATE {
                return false;
            }
            retries -= 1;
            if retries == 0 {
                return false;
            }
            Timer::after(Duration::from_millis(1)).await;
        }

        // CMD58 - Read OCR to check capacity
        self.cs_low();
        let r1 = self.send_cmd_hold(commands::READ_OCR, 0);
        if r1 == 0x00 {
            let mut ocr = [0u8; 4];
            let _ = self.spi.blocking_read(&mut ocr);
            self.high_capacity = (ocr[0] & 0x40) != 0;
        }
        self.cs_high();
        let _ = self.spi.blocking_write(&[0xFF]);

        // CMD16 - Set block length to 512 (for non-HC cards)
        if !self.high_capacity {
            let r1 = self.send_cmd(commands::SET_BLOCKLEN, 512);
            if r1 != 0x00 {
                return false;
            }
        }

        // CMD59 - Disable CRC (optional, speeds up transfers)
        let _ = self.send_cmd(commands::CRC_ON_OFF, 0);

        self.initialized = true;
        true
    }

    /// Read CID register (16 bytes)
    pub async fn read_cid(&mut self, buf: &mut [u8; 16]) -> bool {
        if !self.initialized {
            return false;
        }

        let r1 = self.send_cmd_hold(commands::SEND_CID, 0);
        if r1 != 0x00 {
            self.cs_high();
            return false;
        }

        // Wait for data token
        let mut token = [0u8; 1];
        for _ in 0..1000 {
            let _ = self.spi.blocking_read(&mut token);
            if token[0] == data_tokens::START_BLOCK {
                break;
            }
            if token[0] != 0xFF {
                self.cs_high();
                return false;
            }
        }

        // Read CID data
        let _ = self.spi.blocking_read(buf);
        
        // Read and discard CRC
        let mut crc = [0u8; 2];
        let _ = self.spi.blocking_read(&mut crc);

        self.cs_high();
        let _ = self.spi.blocking_write(&[0xFF]);
        true
    }

    /// Read CSD register (16 bytes)
    pub async fn read_csd(&mut self, buf: &mut [u8; 16]) -> bool {
        if !self.initialized {
            return false;
        }

        let r1 = self.send_cmd_hold(commands::SEND_CSD, 0);
        if r1 != 0x00 {
            self.cs_high();
            return false;
        }

        let mut token = [0u8; 1];
        for _ in 0..1000 {
            let _ = self.spi.blocking_read(&mut token);
            if token[0] == data_tokens::START_BLOCK {
                break;
            }
        }

        let _ = self.spi.blocking_read(buf);
        
        let mut crc = [0u8; 2];
        let _ = self.spi.blocking_read(&mut crc);

        self.cs_high();
        let _ = self.spi.blocking_write(&[0xFF]);
        true
    }

    /// Read a single 512-byte block
    pub async fn read_block(&mut self, block_addr: u32, buf: &mut [u8; 512]) -> bool {
        if !self.initialized {
            return false;
        }

        let addr = if self.high_capacity { block_addr } else { block_addr * 512 };
        
        let r1 = self.send_cmd_hold(commands::READ_SINGLE_BLOCK, addr);
        if r1 != 0x00 {
            self.cs_high();
            return false;
        }

        // Wait for data token
        let mut token = [0u8; 1];
        for _ in 0..10000 {
            let _ = self.spi.blocking_read(&mut token);
            if token[0] == data_tokens::START_BLOCK {
                break;
            }
            if token[0] != 0xFF && token[0] & 0xF0 == 0x00 {
                // Error token
                self.cs_high();
                return false;
            }
        }

        if token[0] != data_tokens::START_BLOCK {
            self.cs_high();
            return false;
        }

        // Read data
        let _ = self.spi.blocking_read(buf);
        
        // Read CRC
        let mut crc = [0u8; 2];
        let _ = self.spi.blocking_read(&mut crc);

        self.cs_high();
        let _ = self.spi.blocking_write(&[0xFF]);
        true
    }

    /// Read multiple 512-byte blocks
    pub async fn read_blocks(&mut self, block_addr: u32, buf: &mut [u8], block_count: u32) -> bool {
        if !self.initialized || buf.len() < (block_count as usize * 512) {
            return false;
        }

        let addr = if self.high_capacity { block_addr } else { block_addr * 512 };
        
        let r1 = self.send_cmd_hold(commands::READ_MULTIPLE_BLOCK, addr);
        if r1 != 0x00 {
            self.cs_high();
            return false;
        }

        for i in 0..block_count as usize {
            // Wait for data token
            let mut token = [0u8; 1];
            for _ in 0..10000 {
                let _ = self.spi.blocking_read(&mut token);
                if token[0] == data_tokens::START_BLOCK {
                    break;
                }
            }

            if token[0] != data_tokens::START_BLOCK {
                self.cs_high();
                return false;
            }

            // Read block
            let offset = i * 512;
            let _ = self.spi.blocking_read(&mut buf[offset..offset + 512]);
            
            // Read CRC
            let mut crc = [0u8; 2];
            let _ = self.spi.blocking_read(&mut crc);
        }

        // CMD12 - Stop transmission
        let _ = self.spi.blocking_write(&[0x40 | commands::STOP_TRANSMISSION, 0, 0, 0, 0, 0x61]);
        
        // Wait for card ready
        self.wait_ready().await;

        self.cs_high();
        let _ = self.spi.blocking_write(&[0xFF]);
        true
    }

    /// Write a single 512-byte block
    pub async fn write_block(&mut self, block_addr: u32, data: &[u8; 512]) -> bool {
        if !self.initialized {
            return false;
        }

        let addr = if self.high_capacity { block_addr } else { block_addr * 512 };
        
        let r1 = self.send_cmd_hold(commands::WRITE_BLOCK, addr);
        if r1 != 0x00 {
            self.cs_high();
            return false;
        }

        // Send data token
        let _ = self.spi.blocking_write(&[0xFF, data_tokens::START_BLOCK]);
        
        // Send data
        let _ = self.spi.blocking_write(data);
        
        // Send dummy CRC
        let _ = self.spi.blocking_write(&[0xFF, 0xFF]);

        // Get data response
        let mut response = [0u8; 1];
        let _ = self.spi.blocking_read(&mut response);
        
        if (response[0] & 0x1F) != data_tokens::DATA_ACCEPTED {
            self.cs_high();
            return false;
        }

        // Wait for write to complete
        if !self.wait_ready().await {
            self.cs_high();
            return false;
        }

        self.cs_high();
        let _ = self.spi.blocking_write(&[0xFF]);
        true
    }

    /// Erase blocks
    pub async fn erase_blocks(&mut self, start_block: u32, end_block: u32) -> bool {
        if !self.initialized {
            return false;
        }

        let start_addr = if self.high_capacity { start_block } else { start_block * 512 };
        let end_addr = if self.high_capacity { end_block } else { end_block * 512 };

        // CMD32 - Set erase start
        let r1 = self.send_cmd(commands::ERASE_WR_BLK_START, start_addr);
        if r1 != 0x00 {
            return false;
        }

        // CMD33 - Set erase end
        let r1 = self.send_cmd(commands::ERASE_WR_BLK_END, end_addr);
        if r1 != 0x00 {
            return false;
        }

        // CMD38 - Erase
        self.cs_low();
        let r1 = self.send_cmd_hold(commands::ERASE, 0);
        if r1 != 0x00 {
            self.cs_high();
            return false;
        }

        // Wait for erase to complete (can take a long time)
        if !self.wait_ready().await {
            self.cs_high();
            return false;
        }

        self.cs_high();
        let _ = self.spi.blocking_write(&[0xFF]);
        true
    }

    /// Get card capacity in bytes
    pub fn get_capacity(&self) -> u64 {
        (self.sector_count as u64) * 512
    }

    /// Check if card is high capacity (SDHC/SDXC/eMMC > 2GB)
    pub fn is_high_capacity(&self) -> bool {
        self.high_capacity
    }

    /// Check if initialized
    pub fn is_initialized(&self) -> bool {
        self.initialized
    }
}
