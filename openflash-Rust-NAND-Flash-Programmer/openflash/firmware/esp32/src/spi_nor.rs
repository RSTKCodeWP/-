//! SPI NOR Flash driver for ESP32
//! Uses hardware SPI peripheral for communication with SPI NOR flash chips
//!
//! Supports standard SPI NOR commands including:
//! - JEDEC ID reading
//! - Standard and fast read operations
//! - Page program and erase operations
//! - Status register read/write
//!
//! ESP32 supports up to 80MHz SPI clock for NOR flash operations.
//!
//! Requirements: 9.4

use esp_hal::gpio::Output;
use esp_hal::spi::master::Spi;
use esp_hal::Delay;

/// SPI NOR standard commands
pub mod commands {
    // Identification
    pub const READ_JEDEC_ID: u8 = 0x9F;
    pub const READ_SFDP: u8 = 0x5A;

    // Read commands
    pub const READ: u8 = 0x03;
    pub const FAST_READ: u8 = 0x0B;
    pub const DUAL_READ: u8 = 0x3B;
    pub const QUAD_READ: u8 = 0x6B;

    // Write commands
    pub const WRITE_ENABLE: u8 = 0x06;
    pub const WRITE_DISABLE: u8 = 0x04;
    pub const PAGE_PROGRAM: u8 = 0x02;

    // Erase commands
    pub const SECTOR_ERASE: u8 = 0x20;    // 4KB
    pub const BLOCK_ERASE_32K: u8 = 0x52;
    pub const BLOCK_ERASE_64K: u8 = 0xD8;
    pub const CHIP_ERASE: u8 = 0xC7;

    // Status commands
    pub const READ_STATUS_1: u8 = 0x05;
    pub const READ_STATUS_2: u8 = 0x35;
    pub const READ_STATUS_3: u8 = 0x15;
    pub const WRITE_STATUS_1: u8 = 0x01;
    pub const WRITE_STATUS_2: u8 = 0x31;
    pub const WRITE_STATUS_3: u8 = 0x11;

    // Other
    pub const RESET_ENABLE: u8 = 0x66;
    pub const RESET: u8 = 0x99;
    pub const ENTER_4BYTE_MODE: u8 = 0xB7;
    pub const EXIT_4BYTE_MODE: u8 = 0xE9;
}

/// Status register 1 bits
pub mod status1 {
    pub const BUSY: u8 = 0x01;
    pub const WEL: u8 = 0x02;
    pub const BP0: u8 = 0x04;
    pub const BP1: u8 = 0x08;
    pub const BP2: u8 = 0x10;
    pub const TB: u8 = 0x20;
    pub const SEC: u8 = 0x40;
    pub const SRP0: u8 = 0x80;
}

/// SPI NOR controller for ESP32
///
/// Provides low-level access to SPI NOR flash chips using hardware SPI.
/// Supports 3-byte and 4-byte addressing modes.
/// ESP32 can achieve up to 80MHz SPI clock speed.
pub struct SpiNorController<'d, SPI: esp_hal::spi::master::Instance> {
    spi: Spi<'d, SPI, esp_hal::spi::FullDuplexMode>,
    cs: Output<'d>,
    delay: Delay,
    address_bytes: u8,
}

impl<'d, SPI: esp_hal::spi::master::Instance> SpiNorController<'d, SPI> {
    /// Create a new SPI NOR controller
    ///
    /// # Arguments
    /// * `spi` - SPI peripheral instance
    /// * `cs` - Chip select GPIO output (active low)
    /// * `delay` - Delay provider for timing operations
    pub fn new(
        spi: Spi<'d, SPI, esp_hal::spi::FullDuplexMode>,
        cs: Output<'d>,
        delay: Delay,
    ) -> Self {
        Self {
            spi,
            cs,
            delay,
            address_bytes: 3,  // Default to 3-byte addressing
        }
    }

    /// Set address byte count (3 or 4 bytes)
    ///
    /// Use 4-byte addressing for chips > 16MB (128Mbit)
    pub fn set_address_bytes(&mut self, bytes: u8) {
        self.address_bytes = bytes.clamp(3, 4);
    }

    /// Assert chip select (active low)
    fn cs_low(&mut self) {
        self.cs.set_low();
    }

    /// Deassert chip select
    fn cs_high(&mut self) {
        self.cs.set_high();
    }

    /// Send command only (no data)
    fn write_cmd(&mut self, cmd: &[u8]) {
        self.cs_low();
        let _ = self.spi.write_bytes(cmd);
        self.cs_high();
    }

    /// Build address bytes for read/write commands
    fn build_address(&self, address: u32) -> [u8; 4] {
        [
            ((address >> 24) & 0xFF) as u8,
            ((address >> 16) & 0xFF) as u8,
            ((address >> 8) & 0xFF) as u8,
            (address & 0xFF) as u8,
        ]
    }

    // ========== Identification Commands ==========

    /// Read JEDEC ID (3 bytes: manufacturer, memory type, capacity)
    ///
    /// Requirements: 1.1
    pub fn read_jedec_id(&mut self) -> [u8; 3] {
        let mut id = [0u8; 3];
        self.cs_low();
        let _ = self.spi.write_bytes(&[commands::READ_JEDEC_ID]);
        let _ = self.spi.read_bytes(&mut id);
        self.cs_high();
        id
    }

    /// Read SFDP (Serial Flash Discoverable Parameters) data
    ///
    /// # Arguments
    /// * `address` - SFDP address (typically 0 for header)
    /// * `buf` - Buffer to store SFDP data
    ///
    /// Requirements: 1.3
    pub fn read_sfdp(&mut self, address: u32, buf: &mut [u8]) {
        self.cs_low();
        // SFDP uses 3-byte address + 1 dummy byte
        let cmd = [
            commands::READ_SFDP,
            ((address >> 16) & 0xFF) as u8,
            ((address >> 8) & 0xFF) as u8,
            (address & 0xFF) as u8,
            0x00, // dummy byte
        ];
        let _ = self.spi.write_bytes(&cmd);
        let _ = self.spi.read_bytes(buf);
        self.cs_high();
    }

    // ========== Read Commands ==========

    /// Standard read (command 0x03)
    ///
    /// Reads data at up to ~33MHz clock speed.
    ///
    /// # Arguments
    /// * `address` - Start address
    /// * `buf` - Buffer to store read data
    ///
    /// Requirements: 2.1
    pub fn read(&mut self, address: u32, buf: &mut [u8]) {
        self.cs_low();

        if self.address_bytes == 4 {
            let addr = self.build_address(address);
            let _ = self.spi.write_bytes(&[commands::READ, addr[0], addr[1], addr[2], addr[3]]);
        } else {
            let _ = self.spi.write_bytes(&[
                commands::READ,
                ((address >> 16) & 0xFF) as u8,
                ((address >> 8) & 0xFF) as u8,
                (address & 0xFF) as u8,
            ]);
        }

        let _ = self.spi.read_bytes(buf);
        self.cs_high();
    }

    /// Fast read with dummy cycle (command 0x0B)
    ///
    /// Reads data at higher clock speeds (up to 80MHz on ESP32).
    /// Includes one dummy byte after address.
    ///
    /// # Arguments
    /// * `address` - Start address
    /// * `buf` - Buffer to store read data
    ///
    /// Requirements: 2.2
    pub fn fast_read(&mut self, address: u32, buf: &mut [u8]) {
        self.cs_low();

        if self.address_bytes == 4 {
            let addr = self.build_address(address);
            let _ = self.spi.write_bytes(&[
                commands::FAST_READ,
                addr[0], addr[1], addr[2], addr[3],
                0x00, // dummy byte
            ]);
        } else {
            let _ = self.spi.write_bytes(&[
                commands::FAST_READ,
                ((address >> 16) & 0xFF) as u8,
                ((address >> 8) & 0xFF) as u8,
                (address & 0xFF) as u8,
                0x00, // dummy byte
            ]);
        }

        let _ = self.spi.read_bytes(buf);
        self.cs_high();
    }

    // ========== Status Register Commands ==========

    /// Read status register 1
    ///
    /// Returns status byte with BUSY, WEL, BP0-BP2, TB, SEC, SRP0 bits.
    ///
    /// Requirements: 4.1
    pub fn read_status1(&mut self) -> u8 {
        let mut status = [0u8; 1];
        self.cs_low();
        let _ = self.spi.write_bytes(&[commands::READ_STATUS_1]);
        let _ = self.spi.read_bytes(&mut status);
        self.cs_high();
        status[0]
    }

    /// Read status register 2
    ///
    /// Requirements: 4.1
    pub fn read_status2(&mut self) -> u8 {
        let mut status = [0u8; 1];
        self.cs_low();
        let _ = self.spi.write_bytes(&[commands::READ_STATUS_2]);
        let _ = self.spi.read_bytes(&mut status);
        self.cs_high();
        status[0]
    }

    /// Read status register 3
    ///
    /// Requirements: 4.1
    pub fn read_status3(&mut self) -> u8 {
        let mut status = [0u8; 1];
        self.cs_low();
        let _ = self.spi.write_bytes(&[commands::READ_STATUS_3]);
        let _ = self.spi.read_bytes(&mut status);
        self.cs_high();
        status[0]
    }

    /// Write status register 1
    ///
    /// Note: Requires write_enable() to be called first.
    ///
    /// Requirements: 4.1
    pub fn write_status1(&mut self, value: u8) {
        self.write_cmd(&[commands::WRITE_STATUS_1, value]);
    }

    /// Write status register 2
    ///
    /// Note: Requires write_enable() to be called first.
    pub fn write_status2(&mut self, value: u8) {
        self.write_cmd(&[commands::WRITE_STATUS_2, value]);
    }

    /// Write status register 3
    ///
    /// Note: Requires write_enable() to be called first.
    pub fn write_status3(&mut self, value: u8) {
        self.write_cmd(&[commands::WRITE_STATUS_3, value]);
    }

    /// Check if chip is busy (operation in progress)
    pub fn is_busy(&mut self) -> bool {
        (self.read_status1() & status1::BUSY) != 0
    }

    /// Check if write enable latch is set
    pub fn is_write_enabled(&mut self) -> bool {
        (self.read_status1() & status1::WEL) != 0
    }

    // ========== Write Enable/Disable ==========

    /// Enable write operations
    ///
    /// Must be called before any program or erase operation.
    /// Sets the WEL (Write Enable Latch) bit in status register.
    ///
    /// Requirements: 3.1
    pub fn write_enable(&mut self) {
        self.write_cmd(&[commands::WRITE_ENABLE]);
    }

    /// Disable write operations
    ///
    /// Clears the WEL bit in status register.
    pub fn write_disable(&mut self) {
        self.write_cmd(&[commands::WRITE_DISABLE]);
    }

    // ========== Wait for Ready ==========

    /// Wait for chip to become ready (not busy)
    ///
    /// Polls status register until BUSY bit is cleared.
    /// Returns the final status register value.
    pub fn wait_ready(&mut self) -> u8 {
        loop {
            let status = self.read_status1();
            if (status & status1::BUSY) == 0 {
                return status;
            }
            self.delay.delay_micros(100);
        }
    }

    /// Wait for chip to become ready with timeout
    ///
    /// Returns Some(status) if ready, None if timeout.
    pub fn wait_ready_timeout(&mut self, timeout_ms: u32) -> Option<u8> {
        let iterations = timeout_ms * 10; // 100us per iteration
        for _ in 0..iterations {
            let status = self.read_status1();
            if (status & status1::BUSY) == 0 {
                return Some(status);
            }
            self.delay.delay_micros(100);
        }
        None
    }

    // ========== Program Commands ==========

    /// Page program (write up to 256 bytes)
    ///
    /// Programs data to flash. Data must be within a single page boundary.
    /// Automatically enables write before programming.
    ///
    /// # Arguments
    /// * `address` - Start address (should be page-aligned for best results)
    /// * `data` - Data to program (max 256 bytes)
    ///
    /// # Returns
    /// `true` if programming succeeded, `false` if timeout or error.
    ///
    /// Requirements: 3.1
    pub fn page_program(&mut self, address: u32, data: &[u8]) -> bool {
        if data.is_empty() || data.len() > 256 {
            return false;
        }

        self.write_enable();

        self.cs_low();

        if self.address_bytes == 4 {
            let addr = self.build_address(address);
            let _ = self.spi.write_bytes(&[
                commands::PAGE_PROGRAM,
                addr[0], addr[1], addr[2], addr[3],
            ]);
        } else {
            let _ = self.spi.write_bytes(&[
                commands::PAGE_PROGRAM,
                ((address >> 16) & 0xFF) as u8,
                ((address >> 8) & 0xFF) as u8,
                (address & 0xFF) as u8,
            ]);
        }

        let _ = self.spi.write_bytes(data);
        self.cs_high();

        // Wait for programming to complete (typical 0.7ms, max 3ms)
        self.wait_ready_timeout(10).is_some()
    }

    // ========== Erase Commands ==========

    /// Sector erase (4KB)
    ///
    /// Erases a 4KB sector. Address is automatically aligned to sector boundary.
    ///
    /// # Arguments
    /// * `address` - Any address within the sector to erase
    ///
    /// # Returns
    /// `true` if erase succeeded, `false` if timeout or error.
    ///
    /// Requirements: 3.1
    pub fn sector_erase(&mut self, address: u32) -> bool {
        self.write_enable();

        self.cs_low();

        if self.address_bytes == 4 {
            let addr = self.build_address(address);
            let _ = self.spi.write_bytes(&[
                commands::SECTOR_ERASE,
                addr[0], addr[1], addr[2], addr[3],
            ]);
        } else {
            let _ = self.spi.write_bytes(&[
                commands::SECTOR_ERASE,
                ((address >> 16) & 0xFF) as u8,
                ((address >> 8) & 0xFF) as u8,
                (address & 0xFF) as u8,
            ]);
        }

        self.cs_high();

        // Wait for erase to complete (typical 45ms, max 400ms)
        self.wait_ready_timeout(500).is_some()
    }

    /// Block erase 32KB
    ///
    /// Erases a 32KB block. Address is automatically aligned to block boundary.
    ///
    /// # Arguments
    /// * `address` - Any address within the block to erase
    ///
    /// # Returns
    /// `true` if erase succeeded, `false` if timeout or error.
    pub fn block_erase_32k(&mut self, address: u32) -> bool {
        self.write_enable();

        self.cs_low();

        if self.address_bytes == 4 {
            let addr = self.build_address(address);
            let _ = self.spi.write_bytes(&[
                commands::BLOCK_ERASE_32K,
                addr[0], addr[1], addr[2], addr[3],
            ]);
        } else {
            let _ = self.spi.write_bytes(&[
                commands::BLOCK_ERASE_32K,
                ((address >> 16) & 0xFF) as u8,
                ((address >> 8) & 0xFF) as u8,
                (address & 0xFF) as u8,
            ]);
        }

        self.cs_high();

        // Wait for erase to complete (typical 120ms, max 1600ms)
        self.wait_ready_timeout(2000).is_some()
    }

    /// Block erase 64KB
    ///
    /// Erases a 64KB block. Address is automatically aligned to block boundary.
    ///
    /// # Arguments
    /// * `address` - Any address within the block to erase
    ///
    /// # Returns
    /// `true` if erase succeeded, `false` if timeout or error.
    ///
    /// Requirements: 3.1
    pub fn block_erase_64k(&mut self, address: u32) -> bool {
        self.write_enable();

        self.cs_low();

        if self.address_bytes == 4 {
            let addr = self.build_address(address);
            let _ = self.spi.write_bytes(&[
                commands::BLOCK_ERASE_64K,
                addr[0], addr[1], addr[2], addr[3],
            ]);
        } else {
            let _ = self.spi.write_bytes(&[
                commands::BLOCK_ERASE_64K,
                ((address >> 16) & 0xFF) as u8,
                ((address >> 8) & 0xFF) as u8,
                (address & 0xFF) as u8,
            ]);
        }

        self.cs_high();

        // Wait for erase to complete (typical 150ms, max 2000ms)
        self.wait_ready_timeout(2500).is_some()
    }

    /// Chip erase (erase entire chip)
    ///
    /// Erases the entire flash chip. This operation can take several seconds
    /// depending on chip size.
    ///
    /// # Returns
    /// `true` if erase succeeded, `false` if timeout or error.
    ///
    /// Requirements: 3.1
    pub fn chip_erase(&mut self) -> bool {
        self.write_enable();
        self.write_cmd(&[commands::CHIP_ERASE]);

        // Wait for erase to complete (can take up to 200 seconds for large chips)
        self.wait_ready_timeout(200_000).is_some()
    }

    // ========== Reset Commands ==========

    /// Software reset
    ///
    /// Performs a software reset of the flash chip.
    /// Requires reset enable (0x66) followed by reset (0x99).
    pub fn reset(&mut self) {
        self.write_cmd(&[commands::RESET_ENABLE]);
        self.write_cmd(&[commands::RESET]);
        // Wait for reset to complete (typically 30us)
        self.delay.delay_micros(100);
    }

    // ========== 4-Byte Address Mode ==========

    /// Enter 4-byte address mode
    ///
    /// Required for chips > 16MB (128Mbit) to access addresses above 16MB.
    pub fn enter_4byte_mode(&mut self) {
        self.write_cmd(&[commands::ENTER_4BYTE_MODE]);
        self.address_bytes = 4;
    }

    /// Exit 4-byte address mode
    ///
    /// Returns to 3-byte address mode.
    pub fn exit_4byte_mode(&mut self) {
        self.write_cmd(&[commands::EXIT_4BYTE_MODE]);
        self.address_bytes = 3;
    }
}
