//! Protocol definitions for Orange Pi driver

use serde::{Deserialize, Serialize};

pub const PROTOCOL_VERSION: u8 = 0x23;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum Command {
    Ping = 0x00,
    GetDeviceInfo = 0x01,
    GetVersion = 0x02,
    
    NandReadId = 0x10,
    NandReadPage = 0x11,
    NandProgramPage = 0x12,
    NandEraseBlock = 0x13,
    
    SpiReadJedecId = 0x20,
    SpiRead = 0x21,
    SpiProgram = 0x22,
    SpiErase = 0x23,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum Status {
    Ok = 0x00,
    Error = 0x01,
    Busy = 0x02,
    Timeout = 0x03,
    InvalidCommand = 0xFF,
}
