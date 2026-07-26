//! Protocol definitions for Teensy 4.x firmware
//!
//! USB High Speed protocol with 512-byte packets

/// Protocol version
pub const PROTOCOL_VERSION: u8 = 0x25;

/// Platform ID for Teensy 4.x
pub const PLATFORM_ID_TEENSY40: u8 = 0x30;
pub const PLATFORM_ID_TEENSY41: u8 = 0x31;
pub const PLATFORM_ID_TEENSY_MM: u8 = 0x32;

/// USB High Speed packet size
pub const HS_PACKET_SIZE: usize = 512;

/// Command codes (same as core protocol)
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Command {
    // General commands
    Ping = 0x01,
    BusConfig = 0x02,
    GetVersion = 0x03,
    GetPlatform = 0x04,
    Reset = 0x08,
    SetInterface = 0x09,

    // Parallel NAND commands
    NandCmd = 0x10,
    NandAddr = 0x11,
    NandReadPage = 0x12,
    NandWritePage = 0x13,
    NandReadId = 0x14,
    NandErase = 0x15,
    NandReadStatus = 0x16,

    // SPI NAND commands
    SpiNandReadId = 0x20,
    SpiNandReset = 0x21,
    SpiNandGetFeature = 0x22,
    SpiNandSetFeature = 0x23,
    SpiNandPageRead = 0x24,
    SpiNandReadCache = 0x25,
    SpiNandReadCacheX4 = 0x26,
    SpiNandProgramLoad = 0x27,
    SpiNandProgramLoadX4 = 0x28,
    SpiNandProgramExec = 0x29,
    SpiNandBlockErase = 0x2A,
    SpiNandWriteEnable = 0x2B,
    SpiNandWriteDisable = 0x2C,

    // eMMC commands
    EmmcInit = 0x40,
    EmmcReadCid = 0x41,
    EmmcReadCsd = 0x42,
    EmmcReadExtCsd = 0x43,
    EmmcReadBlock = 0x44,
    EmmcReadMultiple = 0x45,
    EmmcWriteBlock = 0x46,
    EmmcWriteMultiple = 0x47,
    EmmcErase = 0x48,
    EmmcGetStatus = 0x49,
    EmmcSetPartition = 0x4A,

    // SPI NOR commands
    SpiNorReadJedecId = 0x60,
    SpiNorReadSfdp = 0x61,
    SpiNorRead = 0x62,
    SpiNorFastRead = 0x63,
    SpiNorDualRead = 0x64,
    SpiNorQuadRead = 0x65,
    SpiNorPageProgram = 0x66,
    SpiNorSectorErase = 0x67,
    SpiNorBlockErase32K = 0x68,
    SpiNorBlockErase64K = 0x69,
    SpiNorChipErase = 0x6A,

    // Teensy-specific commands
    TeensyGetSpeed = 0xF0,      // Get USB speed info
    TeensySdInit = 0xF1,        // Initialize SD card (4.1 only)
    TeensySdRead = 0xF2,        // Read from SD card
    TeensySdWrite = 0xF3,       // Write to SD card
    TeensyLogicArm = 0xF4,      // Arm logic analyzer
    TeensyLogicCapture = 0xF5,  // Get logic capture data
    TeensySoftEcc = 0xF6,       // Enable soft ECC on-the-fly
}

impl Command {
    pub fn from_u8(value: u8) -> Option<Self> {
        match value {
            0x01 => Some(Command::Ping),
            0x02 => Some(Command::BusConfig),
            0x03 => Some(Command::GetVersion),
            0x04 => Some(Command::GetPlatform),
            0x08 => Some(Command::Reset),
            0x09 => Some(Command::SetInterface),
            0x10 => Some(Command::NandCmd),
            0x11 => Some(Command::NandAddr),
            0x12 => Some(Command::NandReadPage),
            0x13 => Some(Command::NandWritePage),
            0x14 => Some(Command::NandReadId),
            0x15 => Some(Command::NandErase),
            0x16 => Some(Command::NandReadStatus),
            0x20 => Some(Command::SpiNandReadId),
            0x21 => Some(Command::SpiNandReset),
            0x22 => Some(Command::SpiNandGetFeature),
            0x23 => Some(Command::SpiNandSetFeature),
            0x24 => Some(Command::SpiNandPageRead),
            0x25 => Some(Command::SpiNandReadCache),
            0x26 => Some(Command::SpiNandReadCacheX4),
            0x27 => Some(Command::SpiNandProgramLoad),
            0x28 => Some(Command::SpiNandProgramLoadX4),
            0x29 => Some(Command::SpiNandProgramExec),
            0x2A => Some(Command::SpiNandBlockErase),
            0x2B => Some(Command::SpiNandWriteEnable),
            0x2C => Some(Command::SpiNandWriteDisable),
            0x40 => Some(Command::EmmcInit),
            0x41 => Some(Command::EmmcReadCid),
            0x42 => Some(Command::EmmcReadCsd),
            0x43 => Some(Command::EmmcReadExtCsd),
            0x44 => Some(Command::EmmcReadBlock),
            0x45 => Some(Command::EmmcReadMultiple),
            0x46 => Some(Command::EmmcWriteBlock),
            0x47 => Some(Command::EmmcWriteMultiple),
            0x48 => Some(Command::EmmcErase),
            0x49 => Some(Command::EmmcGetStatus),
            0x4A => Some(Command::EmmcSetPartition),
            0x60 => Some(Command::SpiNorReadJedecId),
            0x61 => Some(Command::SpiNorReadSfdp),
            0x62 => Some(Command::SpiNorRead),
            0x63 => Some(Command::SpiNorFastRead),
            0x64 => Some(Command::SpiNorDualRead),
            0x65 => Some(Command::SpiNorQuadRead),
            0x66 => Some(Command::SpiNorPageProgram),
            0x67 => Some(Command::SpiNorSectorErase),
            0x68 => Some(Command::SpiNorBlockErase32K),
            0x69 => Some(Command::SpiNorBlockErase64K),
            0x6A => Some(Command::SpiNorChipErase),
            0xF0 => Some(Command::TeensyGetSpeed),
            0xF1 => Some(Command::TeensySdInit),
            0xF2 => Some(Command::TeensySdRead),
            0xF3 => Some(Command::TeensySdWrite),
            0xF4 => Some(Command::TeensyLogicArm),
            0xF5 => Some(Command::TeensyLogicCapture),
            0xF6 => Some(Command::TeensySoftEcc),
            _ => None,
        }
    }
}

/// Response status codes
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    Ok = 0x00,
    Error = 0x01,
    Busy = 0x02,
    Timeout = 0x03,
    InvalidCommand = 0xFF,
}
