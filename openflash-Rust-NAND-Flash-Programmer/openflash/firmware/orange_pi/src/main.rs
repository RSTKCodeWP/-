//! OpenFlash GPIO Driver for Orange Pi
//!
//! Supports various Orange Pi boards:
//! - Orange Pi Zero 3 (Allwinner H618)
//! - Orange Pi Zero 2W (Allwinner H616)
//! - Orange Pi 5 (Rockchip RK3588)
//!
//! Uses memory-mapped GPIO for direct register access.

use log::{info, error, warn};
use std::io::{Read, Write};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::Path;

mod gpio;
mod spi;
mod protocol;

/// Protocol version for v2.3.0
const PROTOCOL_VERSION: u8 = 0x23;

/// Firmware version
const VERSION: &str = "2.3.0";

/// Platform identifier
const PLATFORM_ID: u8 = 0x11; // Orange Pi

/// Socket path
const SOCKET_PATH: &str = "/tmp/openflash.sock";

fn main() {
    env_logger::init();
    
    info!("OpenFlash Orange Pi Driver v{}", VERSION);
    info!("Protocol version: 0x{:02X}", PROTOCOL_VERSION);
    
    // Detect board
    match detect_board() {
        Some(board) => info!("Detected: {}", board),
        None => {
            error!("Failed to detect Orange Pi board");
            std::process::exit(1);
        }
    }
    
    // Remove old socket
    if Path::new(SOCKET_PATH).exists() {
        std::fs::remove_file(SOCKET_PATH).ok();
    }
    
    // Create listener
    let listener = match UnixListener::bind(SOCKET_PATH) {
        Ok(l) => l,
        Err(e) => {
            error!("Failed to bind socket: {}", e);
            std::process::exit(1);
        }
    };
    
    info!("Listening on {}", SOCKET_PATH);
    
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

/// Detect Orange Pi board from device tree
fn detect_board() -> Option<&'static str> {
    let model = std::fs::read_to_string("/proc/device-tree/model").ok()?;
    
    if model.contains("Zero 3") || model.contains("H618") {
        Some("Orange Pi Zero 3 (H618)")
    } else if model.contains("Zero 2W") || model.contains("H616") {
        Some("Orange Pi Zero 2W (H616)")
    } else if model.contains("5") || model.contains("RK3588") {
        Some("Orange Pi 5 (RK3588)")
    } else if model.contains("Orange Pi") {
        Some("Orange Pi (Unknown)")
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

/// Process command
fn process_command(cmd: &[u8]) -> Vec<u8> {
    if cmd.is_empty() {
        return vec![0xFF];
    }
    
    match cmd[0] {
        0x00 => vec![0x00, PROTOCOL_VERSION],
        0x01 => {
            let mut resp = vec![0x01, PLATFORM_ID, PROTOCOL_VERSION];
            resp.extend_from_slice(&0x0000_001Fu32.to_le_bytes());
            resp
        }
        0x02 => {
            let mut resp = vec![0x02];
            resp.extend_from_slice(VERSION.as_bytes());
            resp
        }
        _ => vec![0xFF, cmd[0]],
    }
}
