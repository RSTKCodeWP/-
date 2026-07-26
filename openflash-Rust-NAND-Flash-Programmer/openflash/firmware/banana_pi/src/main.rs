//! OpenFlash GPIO Driver for Banana Pi
//!
//! Linux userspace driver for Banana Pi SBC family:
//! - Banana Pi M2 Zero (Allwinner H3) - RPi Zero form factor
//! - Banana Pi M4 Berry (Allwinner H618) - RPi 4 alternative
//! - Banana Pi BPI-F3 (SpacemiT K1 RISC-V) - RISC-V enthusiast board
//!
//! Architecture: SBC driver (like Raspberry Pi/Orange Pi)
//! - Runs as daemon on the board itself
//! - GPIO via /dev/mem or libgpiod
//! - Hardware SPI via spidev
//! - Communication via Unix socket or TCP
//!
//! Best for: SPI NAND, SPI NOR, eMMC (not recommended for parallel NAND)

use log::{info, error, warn};
use std::io::{Read, Write};
use std::net::TcpListener;
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::Path;

mod gpio;
mod spi;
mod protocol;

/// Protocol version for v2.3.5
const PROTOCOL_VERSION: u8 = 0x25;

/// Firmware version
const VERSION: &str = "2.3.5";

/// Platform identifier for Banana Pi
const PLATFORM_ID: u8 = 0x12;

/// Capabilities bitmap
/// Bit 0: Parallel NAND (limited - not recommended)
/// Bit 1: SPI NAND
/// Bit 2: SPI NOR
/// Bit 3: eMMC
/// Bit 4-8: Reserved
const CAPABILITIES: u32 = 0x0000_000E; // SPI NAND + SPI NOR + eMMC (no parallel NAND)

/// Socket path for local communication
const SOCKET_PATH: &str = "/tmp/openflash.sock";

/// Default TCP port
const DEFAULT_TCP_PORT: u16 = 5000;

fn main() {
    env_logger::init();
    
    info!("OpenFlash Banana Pi Driver v{}", VERSION);
    info!("Protocol version: 0x{:02X}", PROTOCOL_VERSION);
    
    // Detect board model
    let board = match detect_board() {
        Some(b) => {
            info!("Detected: {}", b.name);
            b
        }
        None => {
            error!("Failed to detect Banana Pi board");
            error!("Supported: M2 Zero (H3), M4 Berry (H618), BPI-F3 (K1)");
            std::process::exit(1);
        }
    };
    
    // Parse command line arguments
    let args: Vec<String> = std::env::args().collect();
    let use_tcp = args.iter().any(|a| a == "--tcp");
    let tcp_port = args.iter()
        .position(|a| a == "--port")
        .and_then(|i| args.get(i + 1))
        .and_then(|p| p.parse().ok())
        .unwrap_or(DEFAULT_TCP_PORT);
    
    if use_tcp {
        run_tcp_server(tcp_port, &board);
    } else {
        run_unix_socket_server(&board);
    }
}

/// Board information
struct BoardInfo {
    name: &'static str,
    soc: &'static str,
    gpio_base: u32,
    spi_dev: &'static str,
}

/// Detect Banana Pi board from device tree
fn detect_board() -> Option<BoardInfo> {
    let model = std::fs::read_to_string("/proc/device-tree/model").ok()?;
    let compatible = std::fs::read_to_string("/proc/device-tree/compatible").ok().unwrap_or_default();
    
    // Banana Pi M2 Zero (Allwinner H3)
    if model.contains("M2 Zero") || model.contains("BPI-M2-Zero") || compatible.contains("sun8i-h3") {
        return Some(BoardInfo {
            name: "Banana Pi M2 Zero",
            soc: "Allwinner H3",
            gpio_base: 0x01C2_0800, // H3 GPIO base
            spi_dev: "/dev/spidev0.0",
        });
    }
    
    // Banana Pi M4 Berry (Allwinner H618)
    if model.contains("M4 Berry") || model.contains("BPI-M4-Berry") || compatible.contains("sun50i-h618") {
        return Some(BoardInfo {
            name: "Banana Pi M4 Berry",
            soc: "Allwinner H618",
            gpio_base: 0x0300_B000, // H618 GPIO base
            spi_dev: "/dev/spidev0.0",
        });
    }
    
    // Banana Pi BPI-F3 (SpacemiT K1 RISC-V)
    if model.contains("BPI-F3") || model.contains("F3") || compatible.contains("spacemit") || compatible.contains("k1") {
        return Some(BoardInfo {
            name: "Banana Pi BPI-F3",
            soc: "SpacemiT K1 (RISC-V)",
            gpio_base: 0xD401_E000, // K1 GPIO base (approximate)
            spi_dev: "/dev/spidev0.0",
        });
    }
    
    // Generic Banana Pi detection
    if model.contains("Banana") || model.contains("BPI") {
        return Some(BoardInfo {
            name: "Banana Pi (Unknown)",
            soc: "Unknown",
            gpio_base: 0,
            spi_dev: "/dev/spidev0.0",
        });
    }
    
    None
}

/// Run Unix socket server (local connections)
fn run_unix_socket_server(board: &BoardInfo) {
    // Remove old socket if exists
    if Path::new(SOCKET_PATH).exists() {
        std::fs::remove_file(SOCKET_PATH).ok();
    }
    
    let listener = match UnixListener::bind(SOCKET_PATH) {
        Ok(l) => l,
        Err(e) => {
            error!("Failed to bind Unix socket: {}", e);
            std::process::exit(1);
        }
    };
    
    // Set permissions so non-root users can connect
    std::fs::set_permissions(SOCKET_PATH, std::fs::Permissions::from_mode(0o666)).ok();
    
    info!("Listening on Unix socket: {}", SOCKET_PATH);
    info!("Board: {} ({})", board.name, board.soc);
    
    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                info!("Client connected (Unix socket)");
                handle_unix_client(stream, board);
            }
            Err(e) => {
                warn!("Connection failed: {}", e);
            }
        }
    }
}

/// Run TCP server (remote connections)
fn run_tcp_server(port: u16, board: &BoardInfo) {
    let addr = format!("0.0.0.0:{}", port);
    let listener = match TcpListener::bind(&addr) {
        Ok(l) => l,
        Err(e) => {
            error!("Failed to bind TCP socket: {}", e);
            std::process::exit(1);
        }
    };
    
    info!("Listening on TCP: {}", addr);
    info!("Board: {} ({})", board.name, board.soc);
    
    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                let peer = stream.peer_addr().map(|a| a.to_string()).unwrap_or_default();
                info!("Client connected from {}", peer);
                handle_tcp_client(stream, board);
            }
            Err(e) => {
                warn!("Connection failed: {}", e);
            }
        }
    }
}

/// Handle Unix socket client
fn handle_unix_client(mut stream: UnixStream, board: &BoardInfo) {
    let mut buf = [0u8; 64];
    
    loop {
        match stream.read(&mut buf) {
            Ok(0) => {
                info!("Client disconnected");
                break;
            }
            Ok(n) => {
                let response = process_command(&buf[..n], board);
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

/// Handle TCP client
fn handle_tcp_client(mut stream: std::net::TcpStream, board: &BoardInfo) {
    let mut buf = [0u8; 64];
    
    loop {
        match stream.read(&mut buf) {
            Ok(0) => {
                info!("Client disconnected");
                break;
            }
            Ok(n) => {
                let response = process_command(&buf[..n], board);
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
fn process_command(cmd: &[u8], board: &BoardInfo) -> Vec<u8> {
    if cmd.is_empty() {
        return vec![0xFF];
    }
    
    match cmd[0] {
        // Ping
        0x00 | 0x01 => vec![0x00, PROTOCOL_VERSION],
        
        // Get device info
        0x01 => {
            let mut resp = vec![0x01, PLATFORM_ID, PROTOCOL_VERSION];
            resp.extend_from_slice(&CAPABILITIES.to_le_bytes());
            resp
        }
        
        // Get version string
        0x02 => {
            let mut resp = vec![0x02];
            resp.extend_from_slice(VERSION.as_bytes());
            resp
        }
        
        // Get platform name
        0x03 => {
            let mut resp = vec![0x03];
            resp.extend_from_slice(board.name.as_bytes());
            resp
        }
        
        // Get SoC info
        0x04 => {
            let mut resp = vec![0x04];
            resp.extend_from_slice(board.soc.as_bytes());
            resp
        }
        
        // SPI NAND Read ID (0x20)
        0x20 => {
            match spi::read_spi_nand_id(board.spi_dev) {
                Ok(id) => {
                    let mut resp = vec![0x20, 0x00]; // Success
                    resp.extend_from_slice(&id);
                    resp
                }
                Err(_) => vec![0x20, 0x01], // Error
            }
        }
        
        // SPI NOR Read JEDEC ID (0x60)
        0x60 => {
            match spi::read_jedec_id(board.spi_dev) {
                Ok(id) => {
                    let mut resp = vec![0x60, 0x00]; // Success
                    resp.extend_from_slice(&id);
                    resp
                }
                Err(_) => vec![0x60, 0x01], // Error
            }
        }
        
        // Unknown command
        _ => vec![0xFF, cmd[0]],
    }
}

use std::os::unix::fs::PermissionsExt;
