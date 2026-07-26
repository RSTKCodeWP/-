//! USB command handler for Arduino GIGA

use heapless::Vec;

pub const PACKET_SIZE: usize = 512; // USB HS supports 512 byte packets

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
    
    pub fn process(&mut self, data: &[u8]) -> Option<&[u8]> {
        self.rx_buf.clear();
        self.tx_buf.clear();
        
        if data.is_empty() {
            return None;
        }
        
        let _ = self.tx_buf.extend_from_slice(data);
        Some(&self.tx_buf)
    }
}
