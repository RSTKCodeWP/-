//! OpenFlash GPIO Driver for Raspberry Pi
//!
//! This is a Linux userspace driver that uses GPIO for flash operations.
//! Unlike microcontroller firmware, this runs as a daemon on the Pi itself.
//!
//! Supported boards:
//! - Raspberry Pi 3B+ (BCM2837B0)
//! - Raspberry Pi 4 (BCM2711)
//! - Raspberry Pi 5 (BCM2712)
//! - Raspberry Pi Zero 2W (BCM2710A1)
//!
//! Communication: Unix socket or TCP for local/remote control

use log::{info, error, warn};
use std::io::{Read, Write};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::Path;

mod gpio_nand;
mod gpio_spi;
mod protocol;

/// Protocol version for v2.3.0
const PROTOCOL_VERSION: u8 = 0x23;

/// Firmware version
const VERSION: &str = "2.3.0";

/// Platform identifier
const PLATFORM_ID: u8 = 0x10; // Raspberry Pi

/// Socket path for local communication
const SOCKET_PATH: &str = "/tmp/openflash.sock";

fn main() {
    env_logger::init();
    
    info!("OpenFlash Raspberry Pi Driver v{}", VERSION);
    info!("Protocol version: 0x{:02X}", PROTOCOL_VERSION);
    
    // Detect Pi model
    match detect_pi_model() {
        Some(model) => info!("Detected: {}", model),
        None => {
            error!("Failed to detect Raspberry Pi model");
            std::process::exit(1);
        }
    }
    
    // Remove old socket if exists
    if Path::new(SOCKET_PATH).exists() {
        std::fs::remove_file(SOCKET_PATH).ok();
    }
    
    // Create Unix socket listener
    let listener = match UnixListener::bind(SOCKET_PATH) {
        Ok(l) => l,
        Err(e) => {
            error!("Failed to bind socket: {}", e);
            std::process::exit(1);
        }
    };
    
    info!("Listening on {}", SOCKET_PATH);
    
    // Accept connections
    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                info!("Client connected");
                handle_client(stream);
            }
            Err(e) => {
                warn!("Connection failed: {}", e);
            }
        }
    }
}

/// Detect Raspberry Pi model from /proc/cpuinfo
fn detect_pi_model() -> Option<&'static str> {
    let cpuinfo = std::fs::read_to_string("/proc/cpuinfo").ok()?;
    
    if cpuinfo.contains("BCM2712") {
        Some("Raspberry Pi 5")
    } else if cpuinfo.contains("BCM2711") {
        Some("Raspberry Pi 4")
    } else if cpuinfo.contains("BCM2837") {
        Some("Raspberry Pi 3B+")
    } else if cpuinfo.contains("BCM2710") {
        Some("Raspberry Pi Zero 2W")
    } else {
        None
    }
}

/// Handle client connection
fn handle_client(mut stream: UnixStream) {
    let mut buf = [0u8; 64];
    
    loop {
        match stream.read(&mut buf) {
            Ok(0) => {
                info!("Client disconnected");
                break;
            }
            Ok(n) => {
                let response = process_command(&buf[..n]);
                if let Err(e) = stream.write_all(&response) {
                    error!("Write error: {}", e);
                    break;
                }
            }
            Err(e) => {
                error!("Read error: {}", e);
                break;
            }
        }
    }
}

/// Process incoming command
fn process_command(cmd: &[u8]) -> Vec<u8> {
    if cmd.is_empty() {
        return vec![0xFF];
    }
    
    match cmd[0] {
        // Ping
        0x00 => vec![0x00, PROTOCOL_VERSION],
        
        // Get device info
        0x01 => {
            let mut resp = vec![0x01, PLATFORM_ID, PROTOCOL_VERSION];
            // Capabilities
            resp.extend_from_slice(&0x0000_001Fu32.to_le_bytes());
            resp
        }
        
        // Get version
        0x02 => {
            let mut resp = vec![0x02];
            resp.extend_from_slice(VERSION.as_bytes());
            resp
        }
        
        // Unknown
        _ => vec![0xFF, cmd[0]],
    }
}
