//! Protocol definitions for Banana Pi driver

/// Protocol version
pub const PROTOCOL_VERSION: u8 = 0x25;

/// Platform ID for Banana Pi variants
pub const PLATFORM_ID_M2_ZERO: u8 = 0x12;
pub const PLATFORM_ID_M4_BERRY: u8 = 0x13;
pub const PLATFORM_ID_BPI_F3: u8 = 0x14;

/// Command codes
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Command {
    Ping = 0x01,
    GetDeviceInfo = 0x02,
    GetVersion = 0x03,
    GetPlatform = 0x04,
    SpiNandReadId = 0x20,
    SpiNorReadJedecId = 0x60,
}

impl Command {
    pub fn from_u8(value: u8) -> Option<Self> {
        match value {
            0x01 => Some(Command::Ping),
            0x02 => Some(Command::GetDeviceInfo),
            0x03 => Some(Command::GetVersion),
            0x04 => Some(Command::GetPlatform),
            0x20 => Some(Command::SpiNandReadId),
            0x60 => Some(Command::SpiNorReadJedecId),
            _ => None,
        }
    }
}
