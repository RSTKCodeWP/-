//! UFS (Universal Flash Storage) module
//! Contains UFS device information, descriptor types, and SCSI command builders

use serde::{Deserialize, Serialize};

/// UFS device information
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct UfsDeviceInfo {
    pub manufacturer: String,
    pub product_name: String,
    pub serial_number: String,
    pub ufs_version: UfsVersion,
    pub capacity_bytes: u64,
    pub logical_block_size: u32,
    pub num_luns: u8,
    pub boot_lun_enabled: bool,
}

/// UFS version
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum UfsVersion {
    Ufs20,
    Ufs21,
    Ufs30,
    Ufs31,
    Ufs40,
    Unknown(u16),
}

impl UfsVersion {
    /// Parse UFS version from raw version field
    pub fn from_raw(version: u16) -> Self {
        match version {
            0x0200 => UfsVersion::Ufs20,
            0x0210 => UfsVersion::Ufs21,
            0x0300 => UfsVersion::Ufs30,
            0x0310 => UfsVersion::Ufs31,
            0x0400 => UfsVersion::Ufs40,
            v => UfsVersion::Unknown(v),
        }
    }

    /// Convert to raw version field
    pub fn to_raw(&self) -> u16 {
        match self {
            UfsVersion::Ufs20 => 0x0200,
            UfsVersion::Ufs21 => 0x0210,
            UfsVersion::Ufs30 => 0x0300,
            UfsVersion::Ufs31 => 0x0310,
            UfsVersion::Ufs40 => 0x0400,
            UfsVersion::Unknown(v) => *v,
        }
    }

    /// Get human-readable version string
    pub fn as_str(&self) -> &'static str {
        match self {
            UfsVersion::Ufs20 => "UFS 2.0",
            UfsVersion::Ufs21 => "UFS 2.1",
            UfsVersion::Ufs30 => "UFS 3.0",
            UfsVersion::Ufs31 => "UFS 3.1",
            UfsVersion::Ufs40 => "UFS 4.0",
            UfsVersion::Unknown(_) => "Unknown",
        }
    }
}

/// UFS Logical Unit types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum UfsLun {
    /// User data LUN (main storage)
    UserData,
    /// Boot LUN A
    BootA,
    /// Boot LUN B
    BootB,
    /// Replay Protected Memory Block
    Rpmb,
}

impl UfsLun {
    /// Get LUN number for SCSI commands
    pub fn to_lun_id(&self) -> u8 {
        match self {
            UfsLun::UserData => 0x00,
            UfsLun::BootA => 0x01,
            UfsLun::BootB => 0x02,
            UfsLun::Rpmb => 0xC4,
        }
    }

    /// Parse LUN type from LUN ID
    pub fn from_lun_id(lun_id: u8) -> Option<Self> {
        match lun_id {
            0x00 => Some(UfsLun::UserData),
            0x01 => Some(UfsLun::BootA),
            0x02 => Some(UfsLun::BootB),
            0xC4 => Some(UfsLun::Rpmb),
            _ => None,
        }
    }

    /// Get human-readable name
    pub fn as_str(&self) -> &'static str {
        match self {
            UfsLun::UserData => "User Data",
            UfsLun::BootA => "Boot LUN A",
            UfsLun::BootB => "Boot LUN B",
            UfsLun::Rpmb => "RPMB",
        }
    }
}

/// UFS SCSI command constants
pub mod scsi {
    /// Test Unit Ready - check if device is ready
    pub const TEST_UNIT_READY: u8 = 0x00;
    /// Read (6) - short read command
    pub const READ_6: u8 = 0x08;
    /// Read (10) - standard read command for addresses < 2TB
    pub const READ_10: u8 = 0x28;
    /// Read (16) - extended read command for addresses >= 2TB
    pub const READ_16: u8 = 0x88;
    /// Write (10) - standard write command
    pub const WRITE_10: u8 = 0x2A;
    /// Write (16) - extended write command
    pub const WRITE_16: u8 = 0x8A;
    /// Inquiry - get device identification
    pub const INQUIRY: u8 = 0x12;
    /// Read Capacity (10) - get device capacity
    pub const READ_CAPACITY_10: u8 = 0x25;
    /// Read Capacity (16) - get extended device capacity
    pub const READ_CAPACITY_16: u8 = 0x9E;
    /// Request Sense - get error information
    pub const REQUEST_SENSE: u8 = 0x03;
    /// Mode Sense (6) - get device parameters
    pub const MODE_SENSE_6: u8 = 0x1A;
    /// Mode Sense (10) - get extended device parameters
    pub const MODE_SENSE_10: u8 = 0x5A;
    /// Start Stop Unit - control device power state
    pub const START_STOP_UNIT: u8 = 0x1B;
    /// Synchronize Cache (10) - flush write cache
    pub const SYNCHRONIZE_CACHE_10: u8 = 0x35;
    /// Unmap - TRIM/discard blocks
    pub const UNMAP: u8 = 0x42;
}

/// UFS descriptor type constants
pub mod descriptors {
    /// Device Descriptor - general device information
    pub const DEVICE: u8 = 0x00;
    /// Configuration Descriptor - device configuration
    pub const CONFIGURATION: u8 = 0x01;
    /// Unit Descriptor - logical unit information
    pub const UNIT: u8 = 0x02;
    /// Interconnect Descriptor - UniPro parameters
    pub const INTERCONNECT: u8 = 0x04;
    /// String Descriptor - text strings
    pub const STRING: u8 = 0x05;
    /// Geometry Descriptor - physical parameters
    pub const GEOMETRY: u8 = 0x07;
    /// Power Descriptor - power management
    pub const POWER: u8 = 0x08;
    /// Device Health Descriptor - health information
    pub const DEVICE_HEALTH: u8 = 0x09;
}

/// UFS manufacturer IDs (JEDEC)
pub mod manufacturers {
    pub const SAMSUNG: u16 = 0x01CE;
    pub const TOSHIBA: u16 = 0x0198;
    pub const SANDISK: u16 = 0x0145;
    pub const SK_HYNIX: u16 = 0x01AD;
    pub const MICRON: u16 = 0x012C;
    // Note: KIOXIA uses the same ID as TOSHIBA (rebranding)
}

/// Get manufacturer name from JEDEC ID
pub fn get_ufs_manufacturer_name(mfr_id: u16) -> &'static str {
    match mfr_id {
        manufacturers::SAMSUNG => "Samsung",
        manufacturers::TOSHIBA => "Kioxia/Toshiba",
        manufacturers::SANDISK => "SanDisk/Western Digital",
        manufacturers::SK_HYNIX => "SK Hynix",
        manufacturers::MICRON => "Micron",
        _ => "Unknown",
    }
}

// ============================================================================
// UFS Descriptor Structures
// ============================================================================

/// Device Descriptor - contains general device information
/// Minimum size: 32 bytes (UFS 2.0+)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DeviceDescriptor {
    /// Descriptor length
    pub length: u8,
    /// Descriptor type (should be 0x00)
    pub descriptor_type: u8,
    /// Device type (0x00 = UFS device)
    pub device_type: u8,
    /// Device class (0x00 = mass storage)
    pub device_class: u8,
    /// Device sub-class
    pub device_sub_class: u8,
    /// Protocol (0x50 = UFS)
    pub protocol: u8,
    /// Number of logical units
    pub num_luns: u8,
    /// Number of well-known LUNs
    pub num_wluns: u8,
    /// Boot enable flag
    pub boot_enable: u8,
    /// Descriptor access enable
    pub desc_access_enable: u8,
    /// Initial power mode
    pub init_power_mode: u8,
    /// High priority LUN
    pub high_priority_lun: u8,
    /// Secure removal type
    pub secure_removal_type: u8,
    /// Security LUN
    pub security_lun: u8,
    /// Background operations termination latency
    pub bkops_term_latency: u8,
    /// Initial active ICC level
    pub init_active_icc_level: u8,
    /// UFS specification version
    pub spec_version: u16,
    /// Manufacture date (BCD: MMYY)
    pub manufacture_date: u16,
    /// Manufacturer name string index
    pub manufacturer_name_idx: u8,
    /// Product name string index
    pub product_name_idx: u8,
    /// Serial number string index
    pub serial_number_idx: u8,
    /// OEM ID string index
    pub oem_id_idx: u8,
    /// Manufacturer ID (JEDEC)
    pub manufacturer_id: u16,
    /// UD0 base offset
    pub ud0_base_offset: u8,
    /// UD config P length
    pub ud_config_p_length: u8,
    /// Device RTT capability
    pub device_rtt_cap: u8,
    /// Periodic RTC update frequency
    pub periodic_rtc_update: u16,
}

impl DeviceDescriptor {
    /// Minimum descriptor length
    pub const MIN_LENGTH: usize = 32;

    /// Parse Device Descriptor from raw bytes
    pub fn parse(data: &[u8]) -> Option<Self> {
        if data.len() < Self::MIN_LENGTH {
            return None;
        }

        // Verify descriptor type
        if data[1] != descriptors::DEVICE {
            return None;
        }

        Some(Self {
            length: data[0],
            descriptor_type: data[1],
            device_type: data[2],
            device_class: data[3],
            device_sub_class: data[4],
            protocol: data[5],
            num_luns: data[6],
            num_wluns: data[7],
            boot_enable: data[8],
            desc_access_enable: data[9],
            init_power_mode: data[10],
            high_priority_lun: data[11],
            secure_removal_type: data[12],
            security_lun: data[13],
            bkops_term_latency: data[14],
            init_active_icc_level: data[15],
            spec_version: u16::from_be_bytes([data[16], data[17]]),
            manufacture_date: u16::from_be_bytes([data[18], data[19]]),
            manufacturer_name_idx: data[20],
            product_name_idx: data[21],
            serial_number_idx: data[22],
            oem_id_idx: data[23],
            manufacturer_id: u16::from_be_bytes([data[24], data[25]]),
            ud0_base_offset: data[26],
            ud_config_p_length: data[27],
            device_rtt_cap: data[28],
            periodic_rtc_update: u16::from_be_bytes([data[29], data[30]]),
        })
    }

    /// Serialize to bytes
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut data = vec![0u8; Self::MIN_LENGTH];
        data[0] = self.length;
        data[1] = self.descriptor_type;
        data[2] = self.device_type;
        data[3] = self.device_class;
        data[4] = self.device_sub_class;
        data[5] = self.protocol;
        data[6] = self.num_luns;
        data[7] = self.num_wluns;
        data[8] = self.boot_enable;
        data[9] = self.desc_access_enable;
        data[10] = self.init_power_mode;
        data[11] = self.high_priority_lun;
        data[12] = self.secure_removal_type;
        data[13] = self.security_lun;
        data[14] = self.bkops_term_latency;
        data[15] = self.init_active_icc_level;
        data[16..18].copy_from_slice(&self.spec_version.to_be_bytes());
        data[18..20].copy_from_slice(&self.manufacture_date.to_be_bytes());
        data[20] = self.manufacturer_name_idx;
        data[21] = self.product_name_idx;
        data[22] = self.serial_number_idx;
        data[23] = self.oem_id_idx;
        data[24..26].copy_from_slice(&self.manufacturer_id.to_be_bytes());
        data[26] = self.ud0_base_offset;
        data[27] = self.ud_config_p_length;
        data[28] = self.device_rtt_cap;
        data[29..31].copy_from_slice(&self.periodic_rtc_update.to_be_bytes());
        data
    }

    /// Get UFS version
    pub fn get_ufs_version(&self) -> UfsVersion {
        UfsVersion::from_raw(self.spec_version)
    }

    /// Get manufacturer name
    pub fn get_manufacturer_name(&self) -> &'static str {
        get_ufs_manufacturer_name(self.manufacturer_id)
    }
}

/// Unit Descriptor - contains logical unit information
/// Size: 45 bytes (UFS 2.0+)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct UnitDescriptor {
    /// Descriptor length
    pub length: u8,
    /// Descriptor type (should be 0x02)
    pub descriptor_type: u8,
    /// Unit index (LUN number)
    pub unit_index: u8,
    /// LU enable flag
    pub lu_enable: u8,
    /// Boot LUN ID
    pub boot_lun_id: u8,
    /// LU write protect
    pub lu_write_protect: u8,
    /// LU queue depth
    pub lu_queue_depth: u8,
    /// PSA sensitive flag
    pub psa_sensitive: u8,
    /// Memory type
    pub memory_type: u8,
    /// Data reliability
    pub data_reliability: u8,
    /// Logical block size (2^n bytes)
    pub logical_block_size: u8,
    /// Logical block count (capacity)
    pub logical_block_count: u64,
    /// Erase block size
    pub erase_block_size: u32,
    /// Provisioning type
    pub provisioning_type: u8,
    /// Physical memory resource count
    pub phy_mem_resource_count: u64,
    /// Context capabilities
    pub context_capabilities: u16,
    /// Large unit granularity
    pub large_unit_granularity: u8,
}

impl UnitDescriptor {
    /// Minimum descriptor length
    pub const MIN_LENGTH: usize = 45;

    /// Parse Unit Descriptor from raw bytes
    pub fn parse(data: &[u8]) -> Option<Self> {
        if data.len() < Self::MIN_LENGTH {
            return None;
        }

        // Verify descriptor type
        if data[1] != descriptors::UNIT {
            return None;
        }

        Some(Self {
            length: data[0],
            descriptor_type: data[1],
            unit_index: data[2],
            lu_enable: data[3],
            boot_lun_id: data[4],
            lu_write_protect: data[5],
            lu_queue_depth: data[6],
            psa_sensitive: data[7],
            memory_type: data[8],
            data_reliability: data[9],
            logical_block_size: data[10],
            logical_block_count: u64::from_be_bytes([
                data[11], data[12], data[13], data[14], data[15], data[16], data[17], data[18],
            ]),
            erase_block_size: u32::from_be_bytes([data[19], data[20], data[21], data[22]]),
            provisioning_type: data[23],
            phy_mem_resource_count: u64::from_be_bytes([
                data[24], data[25], data[26], data[27], data[28], data[29], data[30], data[31],
            ]),
            context_capabilities: u16::from_be_bytes([data[32], data[33]]),
            large_unit_granularity: data[34],
        })
    }

    /// Serialize to bytes
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut data = vec![0u8; Self::MIN_LENGTH];
        data[0] = self.length;
        data[1] = self.descriptor_type;
        data[2] = self.unit_index;
        data[3] = self.lu_enable;
        data[4] = self.boot_lun_id;
        data[5] = self.lu_write_protect;
        data[6] = self.lu_queue_depth;
        data[7] = self.psa_sensitive;
        data[8] = self.memory_type;
        data[9] = self.data_reliability;
        data[10] = self.logical_block_size;
        data[11..19].copy_from_slice(&self.logical_block_count.to_be_bytes());
        data[19..23].copy_from_slice(&self.erase_block_size.to_be_bytes());
        data[23] = self.provisioning_type;
        data[24..32].copy_from_slice(&self.phy_mem_resource_count.to_be_bytes());
        data[32..34].copy_from_slice(&self.context_capabilities.to_be_bytes());
        data[34] = self.large_unit_granularity;
        data
    }

    /// Get capacity in bytes
    pub fn get_capacity_bytes(&self) -> u64 {
        let block_size = 1u64 << self.logical_block_size;
        self.logical_block_count * block_size
    }

    /// Get logical block size in bytes
    pub fn get_block_size_bytes(&self) -> u32 {
        1u32 << self.logical_block_size
    }

    /// Check if LUN is enabled
    pub fn is_enabled(&self) -> bool {
        self.lu_enable != 0
    }

    /// Check if LUN is write protected
    pub fn is_write_protected(&self) -> bool {
        self.lu_write_protect != 0
    }
}

/// Geometry Descriptor - contains physical parameters
/// Size: 72 bytes (UFS 2.0+)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GeometryDescriptor {
    /// Descriptor length
    pub length: u8,
    /// Descriptor type (should be 0x07)
    pub descriptor_type: u8,
    /// Media technology
    pub media_technology: u8,
    /// Reserved byte
    pub reserved: u8,
    /// Total raw device capacity (512-byte units)
    pub total_raw_device_capacity: u64,
    /// Max number of LUNs
    pub max_num_luns: u8,
    /// Segment size (512-byte units)
    pub segment_size: u32,
    /// Allocation unit size (512-byte units)
    pub allocation_unit_size: u8,
    /// Minimum addressable block size
    pub min_addr_block_size: u8,
    /// Optimal read block size
    pub optimal_read_block_size: u8,
    /// Optimal write block size
    pub optimal_write_block_size: u8,
    /// Max in-buffer size
    pub max_in_buffer_size: u8,
    /// Max out-buffer size
    pub max_out_buffer_size: u8,
    /// RPMB read/write size
    pub rpmb_rw_size: u8,
    /// Dynamic capacity resource policy
    pub dyn_cap_resource_policy: u8,
    /// Data ordering
    pub data_ordering: u8,
    /// Max context ID number
    pub max_context_id_num: u8,
    /// System data tag unit size
    pub sys_data_tag_unit_size: u8,
    /// System data tag resource size
    pub sys_data_tag_res_size: u8,
    /// Supported secure removal types
    pub supported_sec_rt_types: u8,
    /// Supported memory types
    pub supported_memory_types: u16,
    /// System code max number of LUNs
    pub sys_code_max_num_luns: u32,
    /// System code capacity adjustment factor
    pub sys_code_cap_adj_fac: u16,
    /// Non-persistent max number of LUNs
    pub non_persist_max_num_luns: u32,
    /// Non-persistent capacity adjustment factor
    pub non_persist_cap_adj_fac: u16,
    /// Enhanced 1 max number of LUNs
    pub enh1_max_num_luns: u32,
    /// Enhanced 1 capacity adjustment factor
    pub enh1_cap_adj_fac: u16,
    /// Enhanced 2 max number of LUNs
    pub enh2_max_num_luns: u32,
    /// Enhanced 2 capacity adjustment factor
    pub enh2_cap_adj_fac: u16,
}

impl GeometryDescriptor {
    /// Minimum descriptor length
    pub const MIN_LENGTH: usize = 72;

    /// Parse Geometry Descriptor from raw bytes
    pub fn parse(data: &[u8]) -> Option<Self> {
        if data.len() < Self::MIN_LENGTH {
            return None;
        }

        // Verify descriptor type
        if data[1] != descriptors::GEOMETRY {
            return None;
        }

        Some(Self {
            length: data[0],
            descriptor_type: data[1],
            media_technology: data[2],
            reserved: data[3],
            total_raw_device_capacity: u64::from_be_bytes([
                data[4], data[5], data[6], data[7], data[8], data[9], data[10], data[11],
            ]),
            max_num_luns: data[12],
            segment_size: u32::from_be_bytes([data[13], data[14], data[15], data[16]]),
            allocation_unit_size: data[17],
            min_addr_block_size: data[18],
            optimal_read_block_size: data[19],
            optimal_write_block_size: data[20],
            max_in_buffer_size: data[21],
            max_out_buffer_size: data[22],
            rpmb_rw_size: data[23],
            dyn_cap_resource_policy: data[24],
            data_ordering: data[25],
            max_context_id_num: data[26],
            sys_data_tag_unit_size: data[27],
            sys_data_tag_res_size: data[28],
            supported_sec_rt_types: data[29],
            supported_memory_types: u16::from_be_bytes([data[30], data[31]]),
            sys_code_max_num_luns: u32::from_be_bytes([data[32], data[33], data[34], data[35]]),
            sys_code_cap_adj_fac: u16::from_be_bytes([data[36], data[37]]),
            non_persist_max_num_luns: u32::from_be_bytes([data[38], data[39], data[40], data[41]]),
            non_persist_cap_adj_fac: u16::from_be_bytes([data[42], data[43]]),
            enh1_max_num_luns: u32::from_be_bytes([data[44], data[45], data[46], data[47]]),
            enh1_cap_adj_fac: u16::from_be_bytes([data[48], data[49]]),
            enh2_max_num_luns: u32::from_be_bytes([data[50], data[51], data[52], data[53]]),
            enh2_cap_adj_fac: u16::from_be_bytes([data[54], data[55]]),
        })
    }

    /// Serialize to bytes
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut data = vec![0u8; Self::MIN_LENGTH];
        data[0] = self.length;
        data[1] = self.descriptor_type;
        data[2] = self.media_technology;
        data[3] = self.reserved;
        data[4..12].copy_from_slice(&self.total_raw_device_capacity.to_be_bytes());
        data[12] = self.max_num_luns;
        data[13..17].copy_from_slice(&self.segment_size.to_be_bytes());
        data[17] = self.allocation_unit_size;
        data[18] = self.min_addr_block_size;
        data[19] = self.optimal_read_block_size;
        data[20] = self.optimal_write_block_size;
        data[21] = self.max_in_buffer_size;
        data[22] = self.max_out_buffer_size;
        data[23] = self.rpmb_rw_size;
        data[24] = self.dyn_cap_resource_policy;
        data[25] = self.data_ordering;
        data[26] = self.max_context_id_num;
        data[27] = self.sys_data_tag_unit_size;
        data[28] = self.sys_data_tag_res_size;
        data[29] = self.supported_sec_rt_types;
        data[30..32].copy_from_slice(&self.supported_memory_types.to_be_bytes());
        data[32..36].copy_from_slice(&self.sys_code_max_num_luns.to_be_bytes());
        data[36..38].copy_from_slice(&self.sys_code_cap_adj_fac.to_be_bytes());
        data[38..42].copy_from_slice(&self.non_persist_max_num_luns.to_be_bytes());
        data[42..44].copy_from_slice(&self.non_persist_cap_adj_fac.to_be_bytes());
        data[44..48].copy_from_slice(&self.enh1_max_num_luns.to_be_bytes());
        data[48..50].copy_from_slice(&self.enh1_cap_adj_fac.to_be_bytes());
        data[50..54].copy_from_slice(&self.enh2_max_num_luns.to_be_bytes());
        data[54..56].copy_from_slice(&self.enh2_cap_adj_fac.to_be_bytes());
        data
    }

    /// Get total raw capacity in bytes
    pub fn get_total_capacity_bytes(&self) -> u64 {
        self.total_raw_device_capacity * 512
    }

    /// Get segment size in bytes
    pub fn get_segment_size_bytes(&self) -> u64 {
        (self.segment_size as u64) * 512
    }

    /// Get allocation unit size in bytes
    pub fn get_allocation_unit_size_bytes(&self) -> u64 {
        (1u64 << self.allocation_unit_size) * 512
    }
}

// ============================================================================
// SCSI Command Builders
// ============================================================================

/// SCSI Command Descriptor Block (CDB) builder
pub struct ScsiCdbBuilder;

impl ScsiCdbBuilder {
    /// Build READ(10) CDB for addresses < 2TB
    /// Returns 10-byte CDB
    ///
    /// # Arguments
    /// * `lba` - Logical Block Address (must fit in 32 bits)
    /// * `transfer_length` - Number of blocks to read (max 65535)
    /// * `lun` - Logical Unit Number
    pub fn build_read10(lba: u32, transfer_length: u16, lun: u8) -> [u8; 10] {
        let mut cdb = [0u8; 10];
        cdb[0] = scsi::READ_10;
        // Byte 1: LUN in upper 3 bits (for older SCSI), flags in lower bits
        cdb[1] = (lun & 0x07) << 5;
        // Bytes 2-5: LBA (big-endian)
        cdb[2..6].copy_from_slice(&lba.to_be_bytes());
        // Byte 6: Reserved/Group number
        cdb[6] = 0;
        // Bytes 7-8: Transfer length (big-endian)
        cdb[7..9].copy_from_slice(&transfer_length.to_be_bytes());
        // Byte 9: Control
        cdb[9] = 0;
        cdb
    }

    /// Build READ(16) CDB for addresses >= 2TB
    /// Returns 16-byte CDB
    ///
    /// # Arguments
    /// * `lba` - Logical Block Address (64-bit)
    /// * `transfer_length` - Number of blocks to read (max 4294967295)
    /// * `lun` - Logical Unit Number
    pub fn build_read16(lba: u64, transfer_length: u32, lun: u8) -> [u8; 16] {
        let mut cdb = [0u8; 16];
        cdb[0] = scsi::READ_16;
        // Byte 1: Flags (DLD, FUA, etc.)
        cdb[1] = 0;
        // Bytes 2-9: LBA (big-endian)
        cdb[2..10].copy_from_slice(&lba.to_be_bytes());
        // Bytes 10-13: Transfer length (big-endian)
        cdb[10..14].copy_from_slice(&transfer_length.to_be_bytes());
        // Byte 14: Group number
        cdb[14] = 0;
        // Byte 15: Control
        cdb[15] = 0;
        // Note: LUN is typically in the SCSI transport layer, not CDB for modern SCSI
        let _ = lun; // LUN handled at transport layer
        cdb
    }

    /// Build WRITE(10) CDB
    /// Returns 10-byte CDB
    pub fn build_write10(lba: u32, transfer_length: u16, lun: u8) -> [u8; 10] {
        let mut cdb = [0u8; 10];
        cdb[0] = scsi::WRITE_10;
        cdb[1] = (lun & 0x07) << 5;
        cdb[2..6].copy_from_slice(&lba.to_be_bytes());
        cdb[6] = 0;
        cdb[7..9].copy_from_slice(&transfer_length.to_be_bytes());
        cdb[9] = 0;
        cdb
    }

    /// Build WRITE(16) CDB
    /// Returns 16-byte CDB
    pub fn build_write16(lba: u64, transfer_length: u32, lun: u8) -> [u8; 16] {
        let mut cdb = [0u8; 16];
        cdb[0] = scsi::WRITE_16;
        cdb[1] = 0;
        cdb[2..10].copy_from_slice(&lba.to_be_bytes());
        cdb[10..14].copy_from_slice(&transfer_length.to_be_bytes());
        cdb[14] = 0;
        cdb[15] = 0;
        let _ = lun;
        cdb
    }

    /// Build TEST UNIT READY CDB
    /// Returns 6-byte CDB
    pub fn build_test_unit_ready() -> [u8; 6] {
        let mut cdb = [0u8; 6];
        cdb[0] = scsi::TEST_UNIT_READY;
        cdb
    }

    /// Build INQUIRY CDB
    /// Returns 6-byte CDB
    pub fn build_inquiry(allocation_length: u8) -> [u8; 6] {
        let mut cdb = [0u8; 6];
        cdb[0] = scsi::INQUIRY;
        cdb[4] = allocation_length;
        cdb
    }

    /// Build READ CAPACITY(10) CDB
    /// Returns 10-byte CDB
    pub fn build_read_capacity10() -> [u8; 10] {
        let mut cdb = [0u8; 10];
        cdb[0] = scsi::READ_CAPACITY_10;
        cdb
    }

    /// Build READ CAPACITY(16) CDB
    /// Returns 16-byte CDB
    pub fn build_read_capacity16(allocation_length: u32) -> [u8; 16] {
        let mut cdb = [0u8; 16];
        cdb[0] = scsi::READ_CAPACITY_16;
        cdb[1] = 0x10; // Service action: READ CAPACITY(16)
        cdb[10..14].copy_from_slice(&allocation_length.to_be_bytes());
        cdb
    }

    /// Build REQUEST SENSE CDB
    /// Returns 6-byte CDB
    pub fn build_request_sense(allocation_length: u8) -> [u8; 6] {
        let mut cdb = [0u8; 6];
        cdb[0] = scsi::REQUEST_SENSE;
        cdb[4] = allocation_length;
        cdb
    }

    /// Extract LBA from READ(10) CDB
    pub fn extract_lba_from_read10(cdb: &[u8; 10]) -> u32 {
        u32::from_be_bytes([cdb[2], cdb[3], cdb[4], cdb[5]])
    }

    /// Extract transfer length from READ(10) CDB
    pub fn extract_transfer_length_from_read10(cdb: &[u8; 10]) -> u16 {
        u16::from_be_bytes([cdb[7], cdb[8]])
    }

    /// Extract LBA from READ(16) CDB
    pub fn extract_lba_from_read16(cdb: &[u8; 16]) -> u64 {
        u64::from_be_bytes([
            cdb[2], cdb[3], cdb[4], cdb[5], cdb[6], cdb[7], cdb[8], cdb[9],
        ])
    }

    /// Extract transfer length from READ(16) CDB
    pub fn extract_transfer_length_from_read16(cdb: &[u8; 16]) -> u32 {
        u32::from_be_bytes([cdb[10], cdb[11], cdb[12], cdb[13]])
    }
}

/// Determine which READ command to use based on LBA
pub fn select_read_command(lba: u64, transfer_length: u32) -> ReadCommandType {
    // READ(10) can address up to 2^32 blocks
    // With 512-byte blocks, that's 2TB
    // With 4KB blocks, that's 16TB
    // Use READ(16) if LBA exceeds 32-bit range or transfer length exceeds 16-bit range
    if lba > u32::MAX as u64 || transfer_length > u16::MAX as u32 {
        ReadCommandType::Read16
    } else {
        ReadCommandType::Read10
    }
}

/// Read command type selection
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReadCommandType {
    Read10,
    Read16,
}

// ============================================================================
// Error Handling and Sense Data
// ============================================================================

/// UFS error types
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum UfsError {
    /// UniPro link initialization failed
    LinkFailure,
    /// Device not ready after initialization
    DeviceNotReady,
    /// Protocol error during communication
    ProtocolError(u8),
    /// SCSI command failed with sense data
    ScsiError { sense_key: u8, asc: u8, ascq: u8 },
    /// Invalid LUN specified
    InvalidLun(u8),
    /// Timeout waiting for response
    Timeout,
    /// Descriptor parsing failed
    DescriptorParseError,
    /// Invalid command
    InvalidCommand,
    /// Device busy
    DeviceBusy,
}

impl UfsError {
    /// Decode sense data from SCSI response
    /// Expects fixed format sense data (at least 18 bytes)
    pub fn from_sense_data(data: &[u8]) -> Self {
        if data.len() < 18 {
            return UfsError::ProtocolError(0);
        }

        // Check response code (byte 0)
        let response_code = data[0] & 0x7F;

        // Fixed format sense data: 0x70 (current) or 0x71 (deferred)
        // Descriptor format sense data: 0x72 (current) or 0x73 (deferred)
        match response_code {
            0x70 | 0x71 => {
                // Fixed format sense data
                UfsError::ScsiError {
                    sense_key: data[2] & 0x0F,
                    asc: data[12],
                    ascq: data[13],
                }
            }
            0x72 | 0x73 => {
                // Descriptor format sense data
                UfsError::ScsiError {
                    sense_key: data[1] & 0x0F,
                    asc: data[2],
                    ascq: data[3],
                }
            }
            _ => UfsError::ProtocolError(response_code),
        }
    }

    /// Create sense data bytes from UfsError (for round-trip testing)
    /// Returns fixed format sense data (18 bytes)
    pub fn to_sense_data(&self) -> Option<Vec<u8>> {
        match self {
            UfsError::ScsiError {
                sense_key,
                asc,
                ascq,
            } => {
                let mut data = vec![0u8; 18];
                data[0] = 0x70; // Fixed format, current errors
                data[2] = *sense_key & 0x0F;
                data[7] = 10; // Additional sense length
                data[12] = *asc;
                data[13] = *ascq;
                Some(data)
            }
            _ => None,
        }
    }

    /// Get human-readable error description
    pub fn description(&self) -> &'static str {
        match self {
            UfsError::LinkFailure => "UniPro link failed to initialize",
            UfsError::DeviceNotReady => "UFS device not ready",
            UfsError::ProtocolError(_) => "Protocol communication error",
            UfsError::ScsiError { sense_key, .. } => Self::sense_key_description(*sense_key),
            UfsError::InvalidLun(_) => "Invalid logical unit number",
            UfsError::Timeout => "Operation timed out",
            UfsError::DescriptorParseError => "Failed to parse descriptor",
            UfsError::InvalidCommand => "Invalid command",
            UfsError::DeviceBusy => "Device is busy",
        }
    }

    /// Get sense key description
    fn sense_key_description(sense_key: u8) -> &'static str {
        match sense_key {
            0x00 => "No sense",
            0x01 => "Recovered error",
            0x02 => "Not ready",
            0x03 => "Medium error",
            0x04 => "Hardware error",
            0x05 => "Illegal request",
            0x06 => "Unit attention",
            0x07 => "Data protect",
            0x08 => "Blank check",
            0x09 => "Vendor specific",
            0x0A => "Copy aborted",
            0x0B => "Aborted command",
            0x0C => "Equal (obsolete)",
            0x0D => "Volume overflow",
            0x0E => "Miscompare",
            0x0F => "Completed",
            _ => "Unknown sense key",
        }
    }

    /// Get detailed ASC/ASCQ description for common codes
    pub fn asc_description(&self) -> Option<&'static str> {
        match self {
            UfsError::ScsiError { asc, ascq, .. } => Some(Self::get_asc_description(*asc, *ascq)),
            _ => None,
        }
    }

    fn get_asc_description(asc: u8, ascq: u8) -> &'static str {
        match (asc, ascq) {
            (0x00, 0x00) => "No additional sense information",
            (0x04, 0x00) => "Logical unit not ready, cause not reportable",
            (0x04, 0x01) => "Logical unit is in process of becoming ready",
            (0x04, 0x02) => "Logical unit not ready, initializing command required",
            (0x04, 0x03) => "Logical unit not ready, manual intervention required",
            (0x04, 0x04) => "Logical unit not ready, format in progress",
            (0x11, 0x00) => "Unrecovered read error",
            (0x11, 0x01) => "Read retries exhausted",
            (0x14, 0x00) => "Recorded entity not found",
            (0x20, 0x00) => "Invalid command operation code",
            (0x21, 0x00) => "Logical block address out of range",
            (0x24, 0x00) => "Invalid field in CDB",
            (0x25, 0x00) => "Logical unit not supported",
            (0x26, 0x00) => "Invalid field in parameter list",
            (0x27, 0x00) => "Write protected",
            (0x28, 0x00) => "Not ready to ready change, medium may have changed",
            (0x29, 0x00) => "Power on, reset, or bus device reset occurred",
            (0x2A, 0x00) => "Parameters changed",
            (0x2C, 0x00) => "Command sequence error",
            (0x3A, 0x00) => "Medium not present",
            (0x3D, 0x00) => "Invalid bits in identify message",
            (0x3E, 0x00) => "Logical unit has not self-configured yet",
            (0x44, 0x00) => "Internal target failure",
            _ => "Unknown ASC/ASCQ",
        }
    }
}

/// SCSI sense key constants
pub mod sense_keys {
    pub const NO_SENSE: u8 = 0x00;
    pub const RECOVERED_ERROR: u8 = 0x01;
    pub const NOT_READY: u8 = 0x02;
    pub const MEDIUM_ERROR: u8 = 0x03;
    pub const HARDWARE_ERROR: u8 = 0x04;
    pub const ILLEGAL_REQUEST: u8 = 0x05;
    pub const UNIT_ATTENTION: u8 = 0x06;
    pub const DATA_PROTECT: u8 = 0x07;
    pub const BLANK_CHECK: u8 = 0x08;
    pub const VENDOR_SPECIFIC: u8 = 0x09;
    pub const COPY_ABORTED: u8 = 0x0A;
    pub const ABORTED_COMMAND: u8 = 0x0B;
    pub const VOLUME_OVERFLOW: u8 = 0x0D;
    pub const MISCOMPARE: u8 = 0x0E;
    pub const COMPLETED: u8 = 0x0F;
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ufs_version_parsing() {
        assert_eq!(UfsVersion::from_raw(0x0200), UfsVersion::Ufs20);
        assert_eq!(UfsVersion::from_raw(0x0210), UfsVersion::Ufs21);
        assert_eq!(UfsVersion::from_raw(0x0300), UfsVersion::Ufs30);
        assert_eq!(UfsVersion::from_raw(0x0310), UfsVersion::Ufs31);
        assert_eq!(UfsVersion::from_raw(0x0400), UfsVersion::Ufs40);
        assert_eq!(UfsVersion::from_raw(0x0500), UfsVersion::Unknown(0x0500));
    }

    #[test]
    fn test_ufs_version_roundtrip() {
        let versions = [
            UfsVersion::Ufs20,
            UfsVersion::Ufs21,
            UfsVersion::Ufs30,
            UfsVersion::Ufs31,
            UfsVersion::Ufs40,
        ];
        for v in versions {
            assert_eq!(UfsVersion::from_raw(v.to_raw()), v);
        }
    }

    #[test]
    fn test_ufs_lun_conversion() {
        assert_eq!(UfsLun::UserData.to_lun_id(), 0x00);
        assert_eq!(UfsLun::BootA.to_lun_id(), 0x01);
        assert_eq!(UfsLun::BootB.to_lun_id(), 0x02);
        assert_eq!(UfsLun::Rpmb.to_lun_id(), 0xC4);

        assert_eq!(UfsLun::from_lun_id(0x00), Some(UfsLun::UserData));
        assert_eq!(UfsLun::from_lun_id(0x01), Some(UfsLun::BootA));
        assert_eq!(UfsLun::from_lun_id(0x02), Some(UfsLun::BootB));
        assert_eq!(UfsLun::from_lun_id(0xC4), Some(UfsLun::Rpmb));
        assert_eq!(UfsLun::from_lun_id(0xFF), None);
    }

    #[test]
    fn test_manufacturer_names() {
        assert_eq!(get_ufs_manufacturer_name(manufacturers::SAMSUNG), "Samsung");
        assert_eq!(
            get_ufs_manufacturer_name(manufacturers::SK_HYNIX),
            "SK Hynix"
        );
        assert_eq!(get_ufs_manufacturer_name(manufacturers::MICRON), "Micron");
        assert_eq!(get_ufs_manufacturer_name(0xFFFF), "Unknown");
    }

    #[test]
    fn test_device_descriptor_parse() {
        let mut data = vec![0u8; DeviceDescriptor::MIN_LENGTH];
        data[0] = 32; // length
        data[1] = descriptors::DEVICE;
        data[6] = 4; // num_luns
        data[16..18].copy_from_slice(&0x0310u16.to_be_bytes()); // UFS 3.1
        data[24..26].copy_from_slice(&manufacturers::SAMSUNG.to_be_bytes());

        let desc = DeviceDescriptor::parse(&data).unwrap();
        assert_eq!(desc.num_luns, 4);
        assert_eq!(desc.get_ufs_version(), UfsVersion::Ufs31);
        assert_eq!(desc.get_manufacturer_name(), "Samsung");
    }

    #[test]
    fn test_device_descriptor_invalid_type() {
        let mut data = vec![0u8; DeviceDescriptor::MIN_LENGTH];
        data[0] = 32;
        data[1] = 0xFF; // Invalid type

        assert!(DeviceDescriptor::parse(&data).is_none());
    }

    #[test]
    fn test_unit_descriptor_parse() {
        let mut data = vec![0u8; UnitDescriptor::MIN_LENGTH];
        data[0] = 45; // length
        data[1] = descriptors::UNIT;
        data[2] = 0; // unit_index
        data[3] = 1; // lu_enable
        data[10] = 12; // logical_block_size (2^12 = 4096)
        data[11..19].copy_from_slice(&1000000u64.to_be_bytes()); // logical_block_count

        let desc = UnitDescriptor::parse(&data).unwrap();
        assert_eq!(desc.unit_index, 0);
        assert!(desc.is_enabled());
        assert_eq!(desc.get_block_size_bytes(), 4096);
        assert_eq!(desc.logical_block_count, 1000000);
        assert_eq!(desc.get_capacity_bytes(), 1000000 * 4096);
    }

    #[test]
    fn test_geometry_descriptor_parse() {
        let mut data = vec![0u8; GeometryDescriptor::MIN_LENGTH];
        data[0] = 72; // length
        data[1] = descriptors::GEOMETRY;
        data[4..12].copy_from_slice(&(256u64 * 1024 * 1024 * 1024 / 512).to_be_bytes()); // 256GB in 512-byte units
        data[12] = 8; // max_num_luns

        let desc = GeometryDescriptor::parse(&data).unwrap();
        assert_eq!(desc.max_num_luns, 8);
        assert_eq!(desc.get_total_capacity_bytes(), 256 * 1024 * 1024 * 1024);
    }

    #[test]
    fn test_read10_cdb_build() {
        let cdb = ScsiCdbBuilder::build_read10(0x12345678, 256, 0);

        assert_eq!(cdb[0], scsi::READ_10);
        assert_eq!(ScsiCdbBuilder::extract_lba_from_read10(&cdb), 0x12345678);
        assert_eq!(
            ScsiCdbBuilder::extract_transfer_length_from_read10(&cdb),
            256
        );
    }

    #[test]
    fn test_read16_cdb_build() {
        let cdb = ScsiCdbBuilder::build_read16(0x123456789ABCDEF0, 0x12345678, 0);

        assert_eq!(cdb[0], scsi::READ_16);
        assert_eq!(
            ScsiCdbBuilder::extract_lba_from_read16(&cdb),
            0x123456789ABCDEF0
        );
        assert_eq!(
            ScsiCdbBuilder::extract_transfer_length_from_read16(&cdb),
            0x12345678
        );
    }

    #[test]
    fn test_select_read_command() {
        // Small address and length -> READ(10)
        assert_eq!(select_read_command(0, 100), ReadCommandType::Read10);
        assert_eq!(
            select_read_command(u32::MAX as u64, u16::MAX as u32),
            ReadCommandType::Read10
        );

        // Large address -> READ(16)
        assert_eq!(
            select_read_command(u32::MAX as u64 + 1, 100),
            ReadCommandType::Read16
        );

        // Large transfer length -> READ(16)
        assert_eq!(
            select_read_command(0, u16::MAX as u32 + 1),
            ReadCommandType::Read16
        );
    }

    #[test]
    fn test_sense_data_decode_fixed_format() {
        let mut sense_data = vec![0u8; 18];
        sense_data[0] = 0x70; // Fixed format, current errors
        sense_data[2] = 0x05; // Illegal request
        sense_data[12] = 0x24; // ASC: Invalid field in CDB
        sense_data[13] = 0x00; // ASCQ

        let error = UfsError::from_sense_data(&sense_data);
        match error {
            UfsError::ScsiError {
                sense_key,
                asc,
                ascq,
            } => {
                assert_eq!(sense_key, 0x05);
                assert_eq!(asc, 0x24);
                assert_eq!(ascq, 0x00);
            }
            _ => panic!("Expected ScsiError"),
        }
    }

    #[test]
    fn test_sense_data_decode_descriptor_format() {
        let mut sense_data = vec![0u8; 18];
        sense_data[0] = 0x72; // Descriptor format, current errors
        sense_data[1] = 0x03; // Medium error
        sense_data[2] = 0x11; // ASC: Unrecovered read error
        sense_data[3] = 0x00; // ASCQ

        let error = UfsError::from_sense_data(&sense_data);
        match error {
            UfsError::ScsiError {
                sense_key,
                asc,
                ascq,
            } => {
                assert_eq!(sense_key, 0x03);
                assert_eq!(asc, 0x11);
                assert_eq!(ascq, 0x00);
            }
            _ => panic!("Expected ScsiError"),
        }
    }

    #[test]
    fn test_sense_data_too_short() {
        let sense_data = vec![0u8; 10]; // Too short
        let error = UfsError::from_sense_data(&sense_data);
        assert!(matches!(error, UfsError::ProtocolError(0)));
    }

    #[test]
    fn test_error_descriptions() {
        assert_eq!(
            UfsError::LinkFailure.description(),
            "UniPro link failed to initialize"
        );
        assert_eq!(UfsError::Timeout.description(), "Operation timed out");

        let scsi_error = UfsError::ScsiError {
            sense_key: 0x05,
            asc: 0x24,
            ascq: 0x00,
        };
        assert_eq!(scsi_error.description(), "Illegal request");
        assert_eq!(scsi_error.asc_description(), Some("Invalid field in CDB"));
    }
}

#[cfg(test)]
mod proptests {
    use super::*;
    use proptest::prelude::*;

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]

        /// Feature: nor-flash-ufs-support, Property 5: UFS Descriptor Parsing
        /// For any valid UFS descriptor bytes (Device, Unit, Geometry), parsing should
        /// extract all fields correctly, and the parsed capacity should be consistent
        /// with the raw descriptor data.
        /// **Validates: Requirements 5.2, 5.3, 5.4**
        #[test]
        fn prop_device_descriptor_roundtrip(
            num_luns in 1u8..32,
            spec_version in prop_oneof![
                Just(0x0200u16),
                Just(0x0210u16),
                Just(0x0300u16),
                Just(0x0310u16),
                Just(0x0400u16),
            ],
            manufacturer_id in prop_oneof![
                Just(manufacturers::SAMSUNG),
                Just(manufacturers::SK_HYNIX),
                Just(manufacturers::MICRON),
            ],
            boot_enable in 0u8..2,
        ) {
            let original = DeviceDescriptor {
                length: DeviceDescriptor::MIN_LENGTH as u8,
                descriptor_type: descriptors::DEVICE,
                device_type: 0,
                device_class: 0,
                device_sub_class: 0,
                protocol: 0x50,
                num_luns,
                num_wluns: 0,
                boot_enable,
                desc_access_enable: 0,
                init_power_mode: 0,
                high_priority_lun: 0,
                secure_removal_type: 0,
                security_lun: 0,
                bkops_term_latency: 0,
                init_active_icc_level: 0,
                spec_version,
                manufacture_date: 0,
                manufacturer_name_idx: 0,
                product_name_idx: 0,
                serial_number_idx: 0,
                oem_id_idx: 0,
                manufacturer_id,
                ud0_base_offset: 0,
                ud_config_p_length: 0,
                device_rtt_cap: 0,
                periodic_rtc_update: 0,
            };

            let bytes = original.to_bytes();
            let parsed = DeviceDescriptor::parse(&bytes)
                .expect("Should parse valid descriptor bytes");

            prop_assert_eq!(parsed.num_luns, original.num_luns,
                "num_luns mismatch");
            prop_assert_eq!(parsed.spec_version, original.spec_version,
                "spec_version mismatch");
            prop_assert_eq!(parsed.manufacturer_id, original.manufacturer_id,
                "manufacturer_id mismatch");
            prop_assert_eq!(parsed.boot_enable, original.boot_enable,
                "boot_enable mismatch");
        }

        /// Property 5 continued: Unit Descriptor round-trip
        #[test]
        fn prop_unit_descriptor_roundtrip(
            unit_index in 0u8..8,
            lu_enable in 0u8..2,
            logical_block_size in 9u8..13, // 512 to 4096 bytes
            logical_block_count in 1u64..1_000_000_000,
            lu_write_protect in 0u8..2,
        ) {
            let original = UnitDescriptor {
                length: UnitDescriptor::MIN_LENGTH as u8,
                descriptor_type: descriptors::UNIT,
                unit_index,
                lu_enable,
                boot_lun_id: 0,
                lu_write_protect,
                lu_queue_depth: 32,
                psa_sensitive: 0,
                memory_type: 0,
                data_reliability: 0,
                logical_block_size,
                logical_block_count,
                erase_block_size: 0,
                provisioning_type: 0,
                phy_mem_resource_count: 0,
                context_capabilities: 0,
                large_unit_granularity: 0,
            };

            let bytes = original.to_bytes();
            let parsed = UnitDescriptor::parse(&bytes)
                .expect("Should parse valid descriptor bytes");

            prop_assert_eq!(parsed.unit_index, original.unit_index,
                "unit_index mismatch");
            prop_assert_eq!(parsed.lu_enable, original.lu_enable,
                "lu_enable mismatch");
            prop_assert_eq!(parsed.logical_block_size, original.logical_block_size,
                "logical_block_size mismatch");
            prop_assert_eq!(parsed.logical_block_count, original.logical_block_count,
                "logical_block_count mismatch");

            // Verify capacity calculation is consistent
            let expected_capacity = original.logical_block_count * (1u64 << original.logical_block_size);
            prop_assert_eq!(parsed.get_capacity_bytes(), expected_capacity,
                "Capacity calculation mismatch");
        }

        /// Property 5 continued: Geometry Descriptor round-trip
        #[test]
        fn prop_geometry_descriptor_roundtrip(
            total_raw_capacity_gb in 16u64..512, // 16GB to 512GB
            max_num_luns in 1u8..32,
            segment_size in 1u32..1000,
        ) {
            let total_raw_device_capacity = total_raw_capacity_gb * 1024 * 1024 * 1024 / 512;

            let original = GeometryDescriptor {
                length: GeometryDescriptor::MIN_LENGTH as u8,
                descriptor_type: descriptors::GEOMETRY,
                media_technology: 0,
                reserved: 0,
                total_raw_device_capacity,
                max_num_luns,
                segment_size,
                allocation_unit_size: 0,
                min_addr_block_size: 0,
                optimal_read_block_size: 0,
                optimal_write_block_size: 0,
                max_in_buffer_size: 0,
                max_out_buffer_size: 0,
                rpmb_rw_size: 0,
                dyn_cap_resource_policy: 0,
                data_ordering: 0,
                max_context_id_num: 0,
                sys_data_tag_unit_size: 0,
                sys_data_tag_res_size: 0,
                supported_sec_rt_types: 0,
                supported_memory_types: 0,
                sys_code_max_num_luns: 0,
                sys_code_cap_adj_fac: 0,
                non_persist_max_num_luns: 0,
                non_persist_cap_adj_fac: 0,
                enh1_max_num_luns: 0,
                enh1_cap_adj_fac: 0,
                enh2_max_num_luns: 0,
                enh2_cap_adj_fac: 0,
            };

            let bytes = original.to_bytes();
            let parsed = GeometryDescriptor::parse(&bytes)
                .expect("Should parse valid descriptor bytes");

            prop_assert_eq!(parsed.total_raw_device_capacity, original.total_raw_device_capacity,
                "total_raw_device_capacity mismatch");
            prop_assert_eq!(parsed.max_num_luns, original.max_num_luns,
                "max_num_luns mismatch");

            // Verify capacity calculation is consistent
            let expected_capacity = original.total_raw_device_capacity * 512;
            prop_assert_eq!(parsed.get_total_capacity_bytes(), expected_capacity,
                "Capacity calculation mismatch");
        }

        /// Feature: nor-flash-ufs-support, Property 6: SCSI Command Building for Address Ranges
        /// For any logical block address and transfer length, building a READ(10) or READ(16)
        /// command should produce a valid CDB where the address and length can be extracted
        /// back correctly.
        /// **Validates: Requirements 6.1, 6.2, 6.3**
        #[test]
        fn prop_read10_cdb_roundtrip(
            lba in 0u32..u32::MAX,
            transfer_length in 1u16..u16::MAX,
            lun in 0u8..8,
        ) {
            let cdb = ScsiCdbBuilder::build_read10(lba, transfer_length, lun);

            // Verify command byte
            prop_assert_eq!(cdb[0], scsi::READ_10, "Command byte mismatch");

            // Extract and verify LBA
            let extracted_lba = ScsiCdbBuilder::extract_lba_from_read10(&cdb);
            prop_assert_eq!(extracted_lba, lba, "LBA mismatch: expected {}, got {}", lba, extracted_lba);

            // Extract and verify transfer length
            let extracted_len = ScsiCdbBuilder::extract_transfer_length_from_read10(&cdb);
            prop_assert_eq!(extracted_len, transfer_length,
                "Transfer length mismatch: expected {}, got {}", transfer_length, extracted_len);
        }

        /// Property 6 continued: READ(16) round-trip
        #[test]
        fn prop_read16_cdb_roundtrip(
            lba in 0u64..u64::MAX,
            transfer_length in 1u32..u32::MAX,
            lun in 0u8..8,
        ) {
            let cdb = ScsiCdbBuilder::build_read16(lba, transfer_length, lun);

            // Verify command byte
            prop_assert_eq!(cdb[0], scsi::READ_16, "Command byte mismatch");

            // Extract and verify LBA
            let extracted_lba = ScsiCdbBuilder::extract_lba_from_read16(&cdb);
            prop_assert_eq!(extracted_lba, lba, "LBA mismatch: expected {}, got {}", lba, extracted_lba);

            // Extract and verify transfer length
            let extracted_len = ScsiCdbBuilder::extract_transfer_length_from_read16(&cdb);
            prop_assert_eq!(extracted_len, transfer_length,
                "Transfer length mismatch: expected {}, got {}", transfer_length, extracted_len);
        }

        /// Property 6 continued: Command selection based on address range
        #[test]
        fn prop_read_command_selection(
            lba in 0u64..u64::MAX,
            transfer_length in 1u32..u32::MAX,
        ) {
            let cmd_type = select_read_command(lba, transfer_length);

            // If LBA fits in 32 bits and transfer length fits in 16 bits, should use READ(10)
            if lba <= u32::MAX as u64 && transfer_length <= u16::MAX as u32 {
                prop_assert_eq!(cmd_type, ReadCommandType::Read10,
                    "Should use READ(10) for lba={}, len={}", lba, transfer_length);
            } else {
                prop_assert_eq!(cmd_type, ReadCommandType::Read16,
                    "Should use READ(16) for lba={}, len={}", lba, transfer_length);
            }
        }

        /// Feature: nor-flash-ufs-support, Property 7: UFS Sense Data Decoding
        /// For any valid sense data bytes, decoding should produce a UfsError with correct
        /// sense_key, ASC, and ASCQ values that match the input bytes.
        /// **Validates: Requirements 6.6**
        #[test]
        fn prop_sense_data_roundtrip(
            sense_key in 0u8..16,
            asc in 0u8..=255,
            ascq in 0u8..=255,
        ) {
            // Create a ScsiError
            let original = UfsError::ScsiError { sense_key, asc, ascq };

            // Convert to sense data bytes
            let sense_data = original.to_sense_data()
                .expect("ScsiError should produce sense data");

            // Parse back
            let parsed = UfsError::from_sense_data(&sense_data);

            // Verify round-trip
            match parsed {
                UfsError::ScsiError {
                    sense_key: parsed_sk,
                    asc: parsed_asc,
                    ascq: parsed_ascq,
                } => {
                    prop_assert_eq!(parsed_sk, sense_key & 0x0F,
                        "Sense key mismatch: expected {}, got {}", sense_key & 0x0F, parsed_sk);
                    prop_assert_eq!(parsed_asc, asc,
                        "ASC mismatch: expected {}, got {}", asc, parsed_asc);
                    prop_assert_eq!(parsed_ascq, ascq,
                        "ASCQ mismatch: expected {}, got {}", ascq, parsed_ascq);
                }
                _ => prop_assert!(false, "Expected ScsiError, got {:?}", parsed),
            }
        }

        /// Property 7 continued: Fixed format sense data parsing
        #[test]
        fn prop_fixed_format_sense_data(
            sense_key in 0u8..16,
            asc in 0u8..=255,
            ascq in 0u8..=255,
        ) {
            let mut sense_data = vec![0u8; 18];
            sense_data[0] = 0x70; // Fixed format, current errors
            sense_data[2] = sense_key;
            sense_data[7] = 10; // Additional sense length
            sense_data[12] = asc;
            sense_data[13] = ascq;

            let error = UfsError::from_sense_data(&sense_data);

            match error {
                UfsError::ScsiError {
                    sense_key: parsed_sk,
                    asc: parsed_asc,
                    ascq: parsed_ascq,
                } => {
                    prop_assert_eq!(parsed_sk, sense_key & 0x0F,
                        "Sense key mismatch");
                    prop_assert_eq!(parsed_asc, asc, "ASC mismatch");
                    prop_assert_eq!(parsed_ascq, ascq, "ASCQ mismatch");
                }
                _ => prop_assert!(false, "Expected ScsiError"),
            }
        }

        /// Property 7 continued: Descriptor format sense data parsing
        #[test]
        fn prop_descriptor_format_sense_data(
            sense_key in 0u8..16,
            asc in 0u8..=255,
            ascq in 0u8..=255,
        ) {
            let mut sense_data = vec![0u8; 18];
            sense_data[0] = 0x72; // Descriptor format, current errors
            sense_data[1] = sense_key;
            sense_data[2] = asc;
            sense_data[3] = ascq;

            let error = UfsError::from_sense_data(&sense_data);

            match error {
                UfsError::ScsiError {
                    sense_key: parsed_sk,
                    asc: parsed_asc,
                    ascq: parsed_ascq,
                } => {
                    prop_assert_eq!(parsed_sk, sense_key & 0x0F,
                        "Sense key mismatch");
                    prop_assert_eq!(parsed_asc, asc, "ASC mismatch");
                    prop_assert_eq!(parsed_ascq, ascq, "ASCQ mismatch");
                }
                _ => prop_assert!(false, "Expected ScsiError"),
            }
        }
    }
}
