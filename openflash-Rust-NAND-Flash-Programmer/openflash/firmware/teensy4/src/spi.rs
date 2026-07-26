//! SPI controller for Teensy 4.x
//!
//! Uses LPSPI peripheral for SPI NAND/NOR flash operations.
//! Supports up to 30MHz SPI clock.

/// SPI controller
pub struct SpiController {
    initialized: bool,
    clock_hz: u32,
}

impl SpiController {
    pub fn new() -> Self {
        Self {
            initialized: false,
            clock_hz: 20_000_000, // 20MHz default
        }
    }

    /// Initialize SPI peripheral
    pub fn init(&mut self) {
        // Configure LPSPI for SPI mode 0
        // Set clock divider
        self.initialized = true;
    }

    /// Set SPI clock frequency
    pub fn set_clock(&mut self, hz: u32) {
        self.clock_hz = hz.min(30_000_000); // Max 30MHz
        // Reconfigure clock divider
    }

    /// Transfer single byte (full duplex)
    pub fn transfer(&self, tx: u8) -> u8 {
        if !self.initialized {
            return 0;
        }
        // Write TX, read RX
        let _ = tx;
        0
    }

    /// Transfer multiple bytes
    pub fn transfer_buf(&self, tx: &[u8], rx: &mut [u8]) {
        if !self.initialized {
            return;
        }
        for (i, &byte) in tx.iter().enumerate() {
            if i < rx.len() {
                rx[i] = self.transfer(byte);
            } else {
                self.transfer(byte);
            }
        }
    }

    /// Write bytes (ignore received data)
    pub fn write(&self, data: &[u8]) {
        for &byte in data {
            self.transfer(byte);
        }
    }

    /// Read bytes (send 0x00)
    pub fn read(&self, buffer: &mut [u8]) {
        for byte in buffer.iter_mut() {
            *byte = self.transfer(0x00);
        }
    }

    /// Assert CS (active low)
    pub fn cs_low(&self) {
        // Set CS pin low
    }

    /// Deassert CS
    pub fn cs_high(&self) {
        // Set CS pin high
    }

    /// Read JEDEC ID from SPI NOR
    pub fn read_jedec_id(&self) -> [u8; 3] {
        self.cs_low();
        self.transfer(0x9F); // JEDEC ID command
        let mut id = [0u8; 3];
        self.read(&mut id);
        self.cs_high();
        id
    }

    /// Read SPI NAND ID
    pub fn read_spi_nand_id(&self) -> [u8; 2] {
        self.cs_low();
        self.transfer(0x9F); // Read ID command
        self.transfer(0x00); // Dummy byte
        let mut id = [0u8; 2];
        self.read(&mut id);
        self.cs_high();
        id
    }
}

impl Default for SpiController {
    fn default() -> Self {
        Self::new()
    }
}

/// Initialize SPI controller
pub fn init_spi() -> SpiController {
    let mut spi = SpiController::new();
    spi.init();
    spi
}
