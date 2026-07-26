//! USB command handler for RP2350

use heapless::Vec;

/// USB packet size
pub const PACKET_SIZE: usize = 64;

/// Command handler
pub struct UsbHandler {
    rx_buf: Vec<u8, PACKET_SIZE>,
    tx_buf: Vec<u8, PACKET_SIZE>,
}

impl UsbHandler {
    pub fn new() -> Self {
        Self {
            rx_buf: Vec::new(),
            tx_buf: Vec::new(),
        }
    }
    
    /// Process received data
    pub fn process(&mut self, data: &[u8]) -> Option<&[u8]> {
        self.rx_buf.clear();
        self.tx_buf.clear();
        
        if data.is_empty() {
            return None;
        }
        
        // Echo for now
        let _ = self.tx_buf.extend_from_slice(data);
        Some(&self.tx_buf)
    }
}
