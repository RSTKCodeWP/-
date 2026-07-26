//! Tauri IPC commands for OpenFlash GUI

use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, State};

use crate::config::AppConfig;
use crate::device::{ChipInfo, DeviceInfo, DeviceManager, FlashInterface, UfsLunInfo, 
                    DevicePlatform, DeviceCapabilities, ConnectionType};
use crate::mock;

#[tauri::command]
pub fn enable_mock_mode() -> Result<(), String> {
    mock::enable_mock();
    Ok(())
}

#[tauri::command]
pub fn scan_devices(
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<Vec<DeviceInfo>, String> {
    let mut manager = device_manager.lock().map_err(|e| e.to_string())?;
    let mut devices = manager.scan_devices();

    // Add mock devices if enabled
    devices.extend(mock::get_mock_devices());

    Ok(devices)
}

#[tauri::command]
pub fn list_devices(
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<Vec<DeviceInfo>, String> {
    let manager = device_manager.lock().map_err(|e| e.to_string())?;
    Ok(manager.list_devices())
}

#[tauri::command]
pub fn connect_device(
    device_id: String,
    device_manager: State<'_, Mutex<DeviceManager>>,
    config: State<'_, Mutex<AppConfig>>,
) -> Result<(), String> {
    // Save last device
    if let Ok(mut cfg) = config.lock() {
        cfg.last_device = Some(device_id.clone());
        let _ = cfg.save();
    }

    // Check if it's a mock device
    if device_id.starts_with("mock:") {
        return mock::mock_connect(&device_id);
    }

    let mut manager = device_manager.lock().map_err(|e| e.to_string())?;
    manager.connect(&device_id)
}

#[tauri::command]
pub fn disconnect_device(device_manager: State<'_, Mutex<DeviceManager>>) -> Result<(), String> {
    if mock::is_mock_connected() {
        mock::mock_disconnect();
        return Ok(());
    }

    let mut manager = device_manager.lock().map_err(|e| e.to_string())?;
    manager.disconnect();
    Ok(())
}

#[tauri::command]
pub async fn ping(device_manager: State<'_, Mutex<DeviceManager>>) -> Result<bool, String> {
    if mock::is_mock_connected() {
        let response = mock::process_mock_command(openflash_core::protocol::Command::Ping, &[]);
        return Ok(response.len() >= 2 && response[0] == 0x01 && response[1] == 0x00);
    }

    let device = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_active_device().ok_or("No device connected")?
    };

    let dev = device.lock().await;
    let response = dev
        .send_command(openflash_core::protocol::Command::Ping, &[])
        .await?;
    Ok(response.len() >= 2 && response[0] == 0x01 && response[1] == 0x00)
}

#[tauri::command]
pub async fn read_nand_id(
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<Vec<u8>, String> {
    if mock::is_mock_connected() {
        let response =
            mock::process_mock_command(openflash_core::protocol::Command::NandReadId, &[]);
        if response.len() >= 7 && response[1] == 0x00 {
            return Ok(response[2..7].to_vec());
        }
        return Err("Mock read ID failed".to_string());
    }

    let device = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_active_device().ok_or("No device connected")?
    };

    let dev = device.lock().await;
    let response = dev
        .send_command(openflash_core::protocol::Command::NandReadId, &[])
        .await?;

    if response.len() >= 7 && response[1] == 0x00 {
        Ok(response[2..7].to_vec())
    } else {
        Err("Failed to read chip ID".to_string())
    }
}

#[tauri::command]
pub async fn get_chip_info(
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<ChipInfo, String> {
    if mock::is_mock_connected() {
        return Ok(mock::get_mock_chip_info());
    }

    // Check current interface mode
    let interface = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_interface()
    };

    match interface {
        FlashInterface::ParallelNand => {
            let chip_id = read_nand_id(device_manager.clone()).await?;
            if let Some(info) = openflash_core::onfi::get_chip_info(&chip_id) {
                Ok(ChipInfo {
                    manufacturer: info.manufacturer,
                    model: info.model,
                    chip_id,
                    size_mb: info.size_mb,
                    page_size: info.page_size,
                    block_size: info.block_size,
                    interface: FlashInterface::ParallelNand,
                    sector_size: None,
                    jedec_id: None,
                    has_qspi: None,
                    has_dual: None,
                    voltage: None,
                    max_clock_mhz: None,
                    protected: None,
                    luns: None,
                    ufs_version: None,
                    serial_number: None,
                    boot_lun_enabled: None,
                })
            } else {
                Ok(ChipInfo {
                    manufacturer: format!("Unknown (0x{:02X})", chip_id.first().unwrap_or(&0)),
                    model: "Unknown".to_string(),
                    chip_id,
                    size_mb: 0,
                    page_size: 2048,
                    block_size: 64,
                    interface: FlashInterface::ParallelNand,
                    sector_size: None,
                    jedec_id: None,
                    has_qspi: None,
                    has_dual: None,
                    voltage: None,
                    max_clock_mhz: None,
                    protected: None,
                    luns: None,
                    ufs_version: None,
                    serial_number: None,
                    boot_lun_enabled: None,
                })
            }
        }
        FlashInterface::SpiNand => {
            let chip_id = read_spi_nand_id(device_manager.clone()).await?;
            if let Some(info) = openflash_core::spi_nand::get_spi_nand_chip_info(&chip_id) {
                Ok(ChipInfo {
                    manufacturer: info.manufacturer,
                    model: info.model,
                    chip_id,
                    size_mb: info.size_mb,
                    page_size: info.page_size,
                    block_size: info.block_size,
                    interface: FlashInterface::SpiNand,
                    sector_size: None,
                    jedec_id: None,
                    has_qspi: None,
                    has_dual: None,
                    voltage: None,
                    max_clock_mhz: None,
                    protected: None,
                    luns: None,
                    ufs_version: None,
                    serial_number: None,
                    boot_lun_enabled: None,
                })
            } else {
                Ok(ChipInfo {
                    manufacturer: format!("Unknown (0x{:02X})", chip_id.first().unwrap_or(&0)),
                    model: "Unknown SPI NAND".to_string(),
                    chip_id,
                    size_mb: 0,
                    page_size: 2048,
                    block_size: 64,
                    interface: FlashInterface::SpiNand,
                    sector_size: None,
                    jedec_id: None,
                    has_qspi: None,
                    has_dual: None,
                    voltage: None,
                    max_clock_mhz: None,
                    protected: None,
                    luns: None,
                    ufs_version: None,
                    serial_number: None,
                    boot_lun_enabled: None,
                })
            }
        }
        FlashInterface::SpiNor => {
            let jedec_id = read_spi_nor_jedec_id(device_manager.clone()).await?;
            let jedec_arr: [u8; 3] = [
                jedec_id.first().copied().unwrap_or(0),
                jedec_id.get(1).copied().unwrap_or(0),
                jedec_id.get(2).copied().unwrap_or(0),
            ];

            if let Some(info) = openflash_core::spi_nor::get_spi_nor_chip_info(&jedec_arr) {
                Ok(ChipInfo {
                    manufacturer: info.manufacturer.clone(),
                    model: info.model.clone(),
                    chip_id: jedec_id.clone(),
                    size_mb: (info.size_bytes / (1024 * 1024)) as u32,
                    page_size: info.page_size,
                    block_size: info.block_size,
                    interface: FlashInterface::SpiNor,
                    sector_size: Some(info.sector_size),
                    jedec_id: Some(jedec_id),
                    has_qspi: Some(info.has_qspi),
                    has_dual: Some(info.has_dual),
                    voltage: Some(info.voltage.clone()),
                    max_clock_mhz: Some(info.max_clock_mhz),
                    protected: None, // Will be read separately
                    luns: None,
                    ufs_version: None,
                    serial_number: None,
                    boot_lun_enabled: None,
                })
            } else {
                let mfr_name = openflash_core::spi_nor::get_spi_nor_manufacturer_name(jedec_arr[0]);
                Ok(ChipInfo {
                    manufacturer: mfr_name.to_string(),
                    model: format!(
                        "Unknown SPI NOR 0x{:02X}{:02X}{:02X}",
                        jedec_arr[0], jedec_arr[1], jedec_arr[2]
                    ),
                    chip_id: jedec_id.clone(),
                    size_mb: 0,
                    page_size: 256,
                    block_size: 65536,
                    interface: FlashInterface::SpiNor,
                    sector_size: Some(4096),
                    jedec_id: Some(jedec_id),
                    has_qspi: None,
                    has_dual: None,
                    voltage: None,
                    max_clock_mhz: None,
                    protected: None,
                    luns: None,
                    ufs_version: None,
                    serial_number: None,
                    boot_lun_enabled: None,
                })
            }
        }
        FlashInterface::Ufs => {
            // For UFS, we need to read device descriptor
            let ufs_info = read_ufs_device_info(device_manager.clone()).await?;
            Ok(ufs_info)
        }
        FlashInterface::Emmc => {
            // eMMC support - placeholder for now
            Ok(ChipInfo {
                manufacturer: "Unknown".to_string(),
                model: "eMMC Device".to_string(),
                chip_id: vec![],
                size_mb: 0,
                page_size: 512,
                block_size: 512,
                interface: FlashInterface::Emmc,
                sector_size: None,
                jedec_id: None,
                has_qspi: None,
                has_dual: None,
                voltage: None,
                max_clock_mhz: None,
                protected: None,
                luns: None,
                ufs_version: None,
                serial_number: None,
                boot_lun_enabled: None,
            })
        }
    }
}

/// Set the flash interface mode (Parallel NAND or SPI NAND)
#[tauri::command]
pub fn set_interface(
    interface: FlashInterface,
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<(), String> {
    let mut manager = device_manager.lock().map_err(|e| e.to_string())?;
    manager.set_interface(interface);
    Ok(())
}

/// Get the current flash interface mode
#[tauri::command]
pub fn get_interface(
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<FlashInterface, String> {
    let manager = device_manager.lock().map_err(|e| e.to_string())?;
    Ok(manager.get_interface())
}

/// Read SPI NAND chip ID
#[tauri::command]
pub async fn read_spi_nand_id(
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<Vec<u8>, String> {
    if mock::is_mock_connected() {
        // Return mock SPI NAND ID (GigaDevice GD5F1GQ4)
        return Ok(vec![0xC8, 0xD1, 0x00]);
    }

    let device = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_active_device().ok_or("No device connected")?
    };

    let dev = device.lock().await;
    let response = dev
        .send_command(openflash_core::protocol::Command::SpiNandReadId, &[])
        .await?;

    if response.len() >= 5 && response[1] == 0x00 {
        Ok(response[2..5].to_vec())
    } else {
        Err("Failed to read SPI NAND chip ID".to_string())
    }
}

// ============================================================================
// SPI NOR Flash commands (v1.6)
// ============================================================================

/// Read SPI NOR JEDEC ID
#[tauri::command]
pub async fn read_spi_nor_jedec_id(
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<Vec<u8>, String> {
    if mock::is_mock_connected() {
        // Return mock SPI NOR ID (Winbond W25Q128JV)
        return Ok(vec![0xEF, 0x40, 0x18]);
    }

    let device = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_active_device().ok_or("No device connected")?
    };

    let dev = device.lock().await;
    let response = dev
        .send_command(openflash_core::protocol::Command::SpiNorReadJedecId, &[])
        .await?;

    if response.len() >= 5 && response[1] == 0x00 {
        Ok(response[2..5].to_vec())
    } else {
        Err("Failed to read SPI NOR JEDEC ID".to_string())
    }
}

/// SPI NOR sector erase (4KB)
#[tauri::command]
pub async fn spi_nor_sector_erase(
    address: u32,
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<(), String> {
    if mock::is_mock_connected() {
        return Ok(());
    }

    let device = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_active_device().ok_or("No device connected")?
    };

    let dev = device.lock().await;
    let args = address.to_le_bytes();
    let response = dev
        .send_command(openflash_core::protocol::Command::SpiNorSectorErase, &args)
        .await?;

    if response.len() >= 2 && response[1] == 0x00 {
        Ok(())
    } else {
        Err("Sector erase failed".to_string())
    }
}

/// SPI NOR block erase (64KB)
#[tauri::command]
pub async fn spi_nor_block_erase(
    address: u32,
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<(), String> {
    if mock::is_mock_connected() {
        return Ok(());
    }

    let device = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_active_device().ok_or("No device connected")?
    };

    let dev = device.lock().await;
    let args = address.to_le_bytes();
    let response = dev
        .send_command(
            openflash_core::protocol::Command::SpiNorBlockErase64K,
            &args,
        )
        .await?;

    if response.len() >= 2 && response[1] == 0x00 {
        Ok(())
    } else {
        Err("Block erase failed".to_string())
    }
}

/// SPI NOR chip erase
#[tauri::command]
pub async fn spi_nor_chip_erase(
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<(), String> {
    if mock::is_mock_connected() {
        return Ok(());
    }

    let device = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_active_device().ok_or("No device connected")?
    };

    let dev = device.lock().await;
    let response = dev
        .send_command(openflash_core::protocol::Command::SpiNorChipErase, &[])
        .await?;

    if response.len() >= 2 && response[1] == 0x00 {
        Ok(())
    } else {
        Err("Chip erase failed".to_string())
    }
}

/// SPI NOR unlock all protection
#[tauri::command]
pub async fn spi_nor_unlock_all(
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<(), String> {
    if mock::is_mock_connected() {
        return Ok(());
    }

    let device = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_active_device().ok_or("No device connected")?
    };

    let dev = device.lock().await;
    // Write 0x00 to status register 1 to clear all protection bits
    let response = dev
        .send_command(
            openflash_core::protocol::Command::SpiNorWriteStatus1,
            &[0x00],
        )
        .await?;

    if response.len() >= 2 && response[1] == 0x00 {
        Ok(())
    } else {
        Err("Failed to unlock protection".to_string())
    }
}

// ============================================================================
// UFS commands (v1.6)
// ============================================================================

/// Read UFS device information
#[tauri::command]
pub async fn read_ufs_device_info(
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<ChipInfo, String> {
    if mock::is_mock_connected() {
        // Return mock UFS device info
        return Ok(ChipInfo {
            manufacturer: "Samsung".to_string(),
            model: "KLUDG4U1EA-B0C1".to_string(),
            chip_id: vec![0x01, 0xCE],
            size_mb: 128 * 1024, // 128GB
            page_size: 4096,
            block_size: 4096,
            interface: FlashInterface::Ufs,
            sector_size: None,
            jedec_id: None,
            has_qspi: None,
            has_dual: None,
            voltage: None,
            max_clock_mhz: None,
            protected: None,
            luns: Some(vec![
                UfsLunInfo {
                    lun_type: "UserData".to_string(),
                    capacity_bytes: 128 * 1024 * 1024 * 1024,
                    block_size: 4096,
                    enabled: true,
                    write_protected: false,
                },
                UfsLunInfo {
                    lun_type: "BootA".to_string(),
                    capacity_bytes: 4 * 1024 * 1024,
                    block_size: 4096,
                    enabled: true,
                    write_protected: false,
                },
                UfsLunInfo {
                    lun_type: "BootB".to_string(),
                    capacity_bytes: 4 * 1024 * 1024,
                    block_size: 4096,
                    enabled: true,
                    write_protected: false,
                },
                UfsLunInfo {
                    lun_type: "Rpmb".to_string(),
                    capacity_bytes: 512 * 1024,
                    block_size: 256,
                    enabled: true,
                    write_protected: true,
                },
            ]),
            ufs_version: Some("UFS 3.1".to_string()),
            serial_number: Some("S4EVNX0M123456".to_string()),
            boot_lun_enabled: Some(true),
        });
    }

    let device = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_active_device().ok_or("No device connected")?
    };

    let dev = device.lock().await;

    // Read device descriptor
    let response = dev
        .send_command(
            openflash_core::protocol::Command::UfsReadDescriptor,
            &[openflash_core::ufs::descriptors::DEVICE],
        )
        .await?;

    if response.len() < 34 {
        return Err("Failed to read UFS device descriptor".to_string());
    }

    // Parse device descriptor
    if let Some(desc) = openflash_core::ufs::DeviceDescriptor::parse(&response[2..]) {
        let version = desc.get_ufs_version();
        let mfr_name = desc.get_manufacturer_name();

        Ok(ChipInfo {
            manufacturer: mfr_name.to_string(),
            model: format!("UFS Device 0x{:04X}", desc.manufacturer_id),
            chip_id: vec![
                (desc.manufacturer_id >> 8) as u8,
                desc.manufacturer_id as u8,
            ],
            size_mb: 0, // Will be calculated from LUNs
            page_size: 4096,
            block_size: 4096,
            interface: FlashInterface::Ufs,
            sector_size: None,
            jedec_id: None,
            has_qspi: None,
            has_dual: None,
            voltage: None,
            max_clock_mhz: None,
            protected: None,
            luns: None, // Would need to enumerate LUNs
            ufs_version: Some(version.as_str().to_string()),
            serial_number: None,
            boot_lun_enabled: Some(desc.boot_enable != 0),
        })
    } else {
        Err("Failed to parse UFS device descriptor".to_string())
    }
}

/// Select UFS LUN for operations
#[tauri::command]
pub async fn ufs_select_lun(
    lun_type: String,
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<(), String> {
    if mock::is_mock_connected() {
        return Ok(());
    }

    let lun_id = match lun_type.as_str() {
        "UserData" => 0x00,
        "BootA" => 0x01,
        "BootB" => 0x02,
        "Rpmb" => 0xC4,
        _ => return Err(format!("Unknown LUN type: {}", lun_type)),
    };

    let device = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_active_device().ok_or("No device connected")?
    };

    let dev = device.lock().await;
    let response = dev
        .send_command(openflash_core::protocol::Command::UfsSelectLun, &[lun_id])
        .await?;

    if response.len() >= 2 && response[1] == 0x00 {
        Ok(())
    } else {
        Err("Failed to select LUN".to_string())
    }
}

#[tauri::command]
pub async fn dump_nand(
    start_page: u32,
    num_pages: u32,
    page_size: u16,
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<Vec<u8>, String> {
    if mock::is_mock_connected() {
        let mut data = Vec::with_capacity((num_pages as usize) * (page_size as usize));
        for page in start_page..(start_page + num_pages) {
            let mut args = [0u8; 6];
            args[0..4].copy_from_slice(&page.to_le_bytes());
            args[4..6].copy_from_slice(&page_size.to_le_bytes());
            let page_data =
                mock::process_mock_command(openflash_core::protocol::Command::NandReadPage, &args);
            data.extend(page_data);
        }
        return Ok(data);
    }

    let device = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_active_device().ok_or("No device connected")?
    };

    let dev = device.lock().await;
    let mut data = Vec::with_capacity((num_pages as usize) * (page_size as usize));

    for page in start_page..(start_page + num_pages) {
        let page_data = dev.read_page(page, page_size).await?;
        data.extend(page_data);
    }

    Ok(data)
}

#[tauri::command]
pub fn analyze_dump(
    data: Vec<u8>,
    page_size: u32,
    pages_per_block: u32,
) -> Result<AnalysisResult, String> {
    let analyzer =
        openflash_core::analysis::Analyzer::new(page_size as usize, pages_per_block as usize);

    let result = analyzer.analyze_dump(&data);

    Ok(AnalysisResult {
        filesystem_type: result.filesystem_type,
        signatures: result
            .signatures_found
            .into_iter()
            .map(|s| SignatureInfo {
                name: s.name,
                offset: s.offset,
                confidence: s.confidence,
            })
            .collect(),
        bad_blocks: result.bad_blocks,
        empty_pages: result.empty_pages,
        data_pages: result.data_pages,
    })
}

#[derive(Serialize, Deserialize)]
pub struct AnalysisResult {
    pub filesystem_type: Option<String>,
    pub signatures: Vec<SignatureInfo>,
    pub bad_blocks: Vec<u32>,
    pub empty_pages: u32,
    pub data_pages: u32,
}

#[derive(Serialize, Deserialize)]
pub struct SignatureInfo {
    pub name: String,
    pub offset: usize,
    pub confidence: f32,
}

// ============================================================================
// AI Analysis commands (v1.4)
// ============================================================================

#[derive(Serialize, Deserialize)]
pub struct AiAnalysisResponse {
    pub patterns: Vec<PatternInfo>,
    pub anomalies: Vec<AnomalyInfo>,
    pub recovery_suggestions: Vec<RecoverySuggestionInfo>,
    pub chip_recommendations: Vec<ChipRecommendationInfo>,
    pub data_quality_score: f32,
    pub encryption_probability: f32,
    pub compression_probability: f32,
    pub summary: String,
    // v1.4 additions
    pub filesystems: Vec<FilesystemInfo>,
    pub oob_analysis: Option<OobAnalysisInfo>,
    pub key_candidates: Vec<KeyCandidateInfo>,
    pub wear_analysis: Option<WearAnalysisInfo>,
    pub memory_map: Option<MemoryMapInfo>,
}

#[derive(Serialize, Deserialize)]
pub struct PatternInfo {
    pub pattern_type: String,
    pub start_offset: usize,
    pub end_offset: usize,
    pub confidence: String,
    pub description: String,
}

#[derive(Serialize, Deserialize)]
pub struct AnomalyInfo {
    pub severity: String,
    pub location: Option<usize>,
    pub description: String,
    pub recommendation: String,
}

#[derive(Serialize, Deserialize)]
pub struct RecoverySuggestionInfo {
    pub priority: u8,
    pub action: String,
    pub description: String,
    pub estimated_success: f32,
}

#[derive(Serialize, Deserialize)]
pub struct ChipRecommendationInfo {
    pub category: String,
    pub title: String,
    pub description: String,
    pub importance: u8,
}

// v1.4 new structs
#[derive(Serialize, Deserialize)]
pub struct FilesystemInfo {
    pub fs_type: String,
    pub offset: usize,
    pub size: Option<usize>,
    pub confidence: String,
}

#[derive(Serialize, Deserialize)]
pub struct OobAnalysisInfo {
    pub oob_size: usize,
    pub ecc_scheme: String,
    pub ecc_offset: usize,
    pub ecc_size: usize,
    pub bad_block_marker_offset: usize,
    pub confidence: String,
}

#[derive(Serialize, Deserialize)]
pub struct KeyCandidateInfo {
    pub offset: usize,
    pub key_type: String,
    pub key_length: usize,
    pub entropy: f64,
    pub confidence: String,
    pub context: String,
}

#[derive(Serialize, Deserialize)]
pub struct WearAnalysisInfo {
    pub hottest_blocks: Vec<usize>,
    pub coldest_blocks: Vec<usize>,
    pub min_erases: u32,
    pub max_erases: u32,
    pub avg_erases: f32,
    pub estimated_remaining_life_percent: f32,
    pub recommendations: Vec<String>,
}

#[derive(Serialize, Deserialize)]
pub struct MemoryMapInfo {
    pub total_size: usize,
    pub regions: Vec<MemoryMapRegionInfo>,
}

#[derive(Serialize, Deserialize)]
pub struct MemoryMapRegionInfo {
    pub start: usize,
    pub end: usize,
    pub region_type: String,
    pub name: String,
    pub color: String,
}

#[derive(Serialize, Deserialize)]
pub struct DumpDiffResponse {
    pub total_differences: usize,
    pub changed_pages: Vec<usize>,
    pub changed_blocks: Vec<usize>,
    pub similarity_percent: f32,
    pub modified_regions: Vec<DiffRegionInfo>,
}

#[derive(Serialize, Deserialize)]
pub struct DiffRegionInfo {
    pub offset: usize,
    pub size: usize,
    pub change_type: String,
    pub description: String,
}

/// AI-powered analysis of dump data (v1.4)
#[tauri::command]
pub fn ai_analyze_dump(
    data: Vec<u8>,
    page_size: u32,
    pages_per_block: u32,
) -> Result<AiAnalysisResponse, String> {
    let analyzer =
        openflash_core::ai::AiAnalyzer::new(page_size as usize, pages_per_block as usize);

    let result = analyzer.analyze(&data);

    Ok(AiAnalysisResponse {
        patterns: result
            .patterns
            .into_iter()
            .map(|p| PatternInfo {
                pattern_type: format!("{:?}", p.pattern_type),
                start_offset: p.start_offset,
                end_offset: p.end_offset,
                confidence: format!("{:?}", p.confidence),
                description: p.description,
            })
            .collect(),
        anomalies: result
            .anomalies
            .into_iter()
            .map(|a| AnomalyInfo {
                severity: format!("{:?}", a.severity),
                location: a.location,
                description: a.description,
                recommendation: a.recommendation,
            })
            .collect(),
        recovery_suggestions: result
            .recovery_suggestions
            .into_iter()
            .map(|s| RecoverySuggestionInfo {
                priority: s.priority,
                action: s.action,
                description: s.description,
                estimated_success: s.estimated_success,
            })
            .collect(),
        chip_recommendations: result
            .chip_recommendations
            .into_iter()
            .map(|r| ChipRecommendationInfo {
                category: r.category,
                title: r.title,
                description: r.description,
                importance: r.importance,
            })
            .collect(),
        data_quality_score: result.data_quality_score,
        encryption_probability: result.encryption_probability,
        compression_probability: result.compression_probability,
        summary: result.summary,
        // v1.4 additions
        filesystems: result
            .filesystems
            .into_iter()
            .map(|f| FilesystemInfo {
                fs_type: f.fs_type.name().to_string(),
                offset: f.offset,
                size: f.size,
                confidence: format!("{:?}", f.confidence),
            })
            .collect(),
        oob_analysis: result.oob_analysis.map(|o| OobAnalysisInfo {
            oob_size: o.oob_size,
            ecc_scheme: format!("{:?}", o.ecc_scheme),
            ecc_offset: o.ecc_offset,
            ecc_size: o.ecc_size,
            bad_block_marker_offset: o.bad_block_marker_offset,
            confidence: format!("{:?}", o.confidence),
        }),
        key_candidates: result
            .key_candidates
            .into_iter()
            .map(|k| KeyCandidateInfo {
                offset: k.offset,
                key_type: k.key_type,
                key_length: k.key_length,
                entropy: k.entropy,
                confidence: format!("{:?}", k.confidence),
                context: k.context,
            })
            .collect(),
        wear_analysis: result.wear_analysis.map(|w| WearAnalysisInfo {
            hottest_blocks: w.hottest_blocks,
            coldest_blocks: w.coldest_blocks,
            min_erases: w.wear_distribution.min_erases,
            max_erases: w.wear_distribution.max_erases,
            avg_erases: w.wear_distribution.avg_erases,
            estimated_remaining_life_percent: w.estimated_remaining_life_percent,
            recommendations: w.recommendations,
        }),
        memory_map: result.memory_map.map(|m| MemoryMapInfo {
            total_size: m.total_size,
            regions: m
                .regions
                .into_iter()
                .map(|r| MemoryMapRegionInfo {
                    start: r.start,
                    end: r.end,
                    region_type: r.region_type,
                    name: r.name,
                    color: r.color,
                })
                .collect(),
        }),
    })
}

/// Quick AI pattern detection (lighter analysis)
#[tauri::command]
pub fn ai_detect_patterns(data: Vec<u8>, page_size: u32) -> Result<Vec<PatternInfo>, String> {
    let analyzer = openflash_core::ai::AiAnalyzer::new(page_size as usize, 64);
    let patterns = analyzer.detect_patterns(&data);

    Ok(patterns
        .into_iter()
        .map(|p| PatternInfo {
            pattern_type: format!("{:?}", p.pattern_type),
            start_offset: p.start_offset,
            end_offset: p.end_offset,
            confidence: format!("{:?}", p.confidence),
            description: p.description,
        })
        .collect())
}

/// Get AI-powered chip recommendations
#[tauri::command]
pub fn ai_get_recommendations(
    data: Vec<u8>,
    page_size: u32,
    pages_per_block: u32,
) -> Result<Vec<ChipRecommendationInfo>, String> {
    let analyzer =
        openflash_core::ai::AiAnalyzer::new(page_size as usize, pages_per_block as usize);

    let patterns = analyzer.detect_patterns(&data);
    let recommendations = analyzer.generate_chip_recommendations(&data, &patterns);

    Ok(recommendations
        .into_iter()
        .map(|r| ChipRecommendationInfo {
            category: r.category,
            title: r.title,
            description: r.description,
            importance: r.importance,
        })
        .collect())
}

/// v1.4: Compare two dumps
#[tauri::command]
pub fn ai_compare_dumps(
    dump1: Vec<u8>,
    dump2: Vec<u8>,
    page_size: u32,
    pages_per_block: u32,
) -> Result<DumpDiffResponse, String> {
    let analyzer =
        openflash_core::ai::AiAnalyzer::new(page_size as usize, pages_per_block as usize);

    let diff = analyzer.compare_dumps(&dump1, &dump2);

    Ok(DumpDiffResponse {
        total_differences: diff.total_differences,
        changed_pages: diff.changed_pages,
        changed_blocks: diff.changed_blocks,
        similarity_percent: diff.similarity_percent,
        modified_regions: diff
            .modified_regions
            .into_iter()
            .map(|r| DiffRegionInfo {
                offset: r.offset,
                size: r.size,
                change_type: format!("{:?}", r.change_type),
                description: r.description,
            })
            .collect(),
    })
}

/// v1.4: Deep scan for encryption keys
#[tauri::command]
pub fn ai_search_keys(data: Vec<u8>, page_size: u32) -> Result<Vec<KeyCandidateInfo>, String> {
    let analyzer = openflash_core::ai::AiAnalyzer::new(page_size as usize, 64).with_deep_scan(true);

    let keys = analyzer.search_encryption_keys(&data);

    Ok(keys
        .into_iter()
        .map(|k| KeyCandidateInfo {
            offset: k.offset,
            key_type: k.key_type,
            key_length: k.key_length,
            entropy: k.entropy,
            confidence: format!("{:?}", k.confidence),
            context: k.context,
        })
        .collect())
}

/// v1.4: Generate AI analysis report
#[tauri::command]
pub fn ai_generate_report(
    data: Vec<u8>,
    page_size: u32,
    pages_per_block: u32,
) -> Result<String, String> {
    let analyzer =
        openflash_core::ai::AiAnalyzer::new(page_size as usize, pages_per_block as usize);

    let result = analyzer.analyze(&data);
    let report = analyzer.generate_report(&result);

    Ok(report)
}

// ============================================================================
// Progress-enabled dump command
// ============================================================================

#[derive(Clone, Serialize)]
pub struct DumpProgress {
    pub current_page: u32,
    pub total_pages: u32,
    pub percent: u8,
    pub bytes_read: usize,
}

#[tauri::command]
pub async fn dump_nand_with_progress(
    app: AppHandle,
    start_page: u32,
    num_pages: u32,
    page_size: u16,
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<Vec<u8>, String> {
    let chunk_size = 64u32; // Pages per progress update
    let mut data = Vec::with_capacity((num_pages as usize) * (page_size as usize));

    if mock::is_mock_connected() {
        for page in start_page..(start_page + num_pages) {
            let mut args = [0u8; 6];
            args[0..4].copy_from_slice(&page.to_le_bytes());
            args[4..6].copy_from_slice(&page_size.to_le_bytes());
            let page_data =
                mock::process_mock_command(openflash_core::protocol::Command::NandReadPage, &args);
            data.extend(page_data);

            // Emit progress every chunk_size pages
            if (page - start_page) % chunk_size == 0 || page == start_page + num_pages - 1 {
                let progress = DumpProgress {
                    current_page: page - start_page + 1,
                    total_pages: num_pages,
                    percent: (((page - start_page + 1) as f32 / num_pages as f32) * 100.0) as u8,
                    bytes_read: data.len(),
                };
                let _ = app.emit("dump-progress", progress);
            }
        }
        return Ok(data);
    }

    let device = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_active_device().ok_or("No device connected")?
    };

    let dev = device.lock().await;

    for page in start_page..(start_page + num_pages) {
        let page_data = dev.read_page(page, page_size).await?;
        data.extend(page_data);

        // Emit progress
        if (page - start_page) % chunk_size == 0 || page == start_page + num_pages - 1 {
            let progress = DumpProgress {
                current_page: page - start_page + 1,
                total_pages: num_pages,
                percent: (((page - start_page + 1) as f32 / num_pages as f32) * 100.0) as u8,
                bytes_read: data.len(),
            };
            let _ = app.emit("dump-progress", progress);
        }
    }

    Ok(data)
}

// ============================================================================
// Configuration commands
// ============================================================================

#[tauri::command]
pub fn get_config(config: State<'_, Mutex<AppConfig>>) -> Result<AppConfig, String> {
    let cfg = config.lock().map_err(|e| e.to_string())?;
    Ok(cfg.clone())
}

#[tauri::command]
pub fn set_config(
    new_config: AppConfig,
    config: State<'_, Mutex<AppConfig>>,
) -> Result<(), String> {
    let mut cfg = config.lock().map_err(|e| e.to_string())?;
    *cfg = new_config;
    cfg.save()
}

#[tauri::command]
pub fn add_recent_file(path: String, config: State<'_, Mutex<AppConfig>>) -> Result<(), String> {
    let mut cfg = config.lock().map_err(|e| e.to_string())?;
    cfg.add_recent_file(&path);
    cfg.save()
}

// ============================================================================
// Platform commands (v2.3)
// ============================================================================

/// Platform info response
#[derive(Serialize, Deserialize)]
pub struct PlatformInfo {
    pub platform: String,
    pub platform_id: u8,
    pub icon: String,
    pub name: String,
    pub is_sbc: bool,
    pub capabilities: DeviceCapabilitiesInfo,
    pub protocol_version: u8,
    pub firmware_version: Option<String>,
}

#[derive(Serialize, Deserialize)]
pub struct DeviceCapabilitiesInfo {
    pub parallel_nand: bool,
    pub spi_nand: bool,
    pub spi_nor: bool,
    pub emmc: bool,
    pub nvddr: bool,
    pub hardware_ecc: bool,
    pub wifi: bool,
    pub bluetooth: bool,
    pub high_speed_usb: bool,
}

/// Get detailed device info including platform and capabilities
#[tauri::command]
pub async fn get_device_info(
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<PlatformInfo, String> {
    if mock::is_mock_connected() {
        let response = mock::get_mock_device_info_response();
        let platform = DevicePlatform::from_id(response[1]);
        let caps = mock::get_mock_capabilities(platform);
        
        return Ok(PlatformInfo {
            platform: format!("{:?}", platform),
            platform_id: response[1],
            icon: platform.icon().to_string(),
            name: platform.name().to_string(),
            is_sbc: platform.is_sbc(),
            capabilities: DeviceCapabilitiesInfo {
                parallel_nand: caps.parallel_nand,
                spi_nand: caps.spi_nand,
                spi_nor: caps.spi_nor,
                emmc: caps.emmc,
                nvddr: caps.nvddr,
                hardware_ecc: caps.hardware_ecc,
                wifi: caps.wifi,
                bluetooth: caps.bluetooth,
                high_speed_usb: caps.high_speed_usb,
            },
            protocol_version: response[2],
            firmware_version: Some("2.3.0".to_string()),
        });
    }

    let device = {
        let manager = device_manager.lock().map_err(|e| e.to_string())?;
        manager.get_active_device().ok_or("No device connected")?
    };

    let dev = device.lock().await;
    
    // Send GetDeviceInfo command (0xBB from scripting module, or 0x01 for basic info)
    let response = dev
        .send_command(openflash_core::protocol::Command::Ping, &[])
        .await?;

    // For now, return basic info - real implementation would parse device response
    let platform = DevicePlatform::Unknown;
    
    Ok(PlatformInfo {
        platform: format!("{:?}", platform),
        platform_id: 0,
        icon: platform.icon().to_string(),
        name: platform.name().to_string(),
        is_sbc: platform.is_sbc(),
        capabilities: DeviceCapabilitiesInfo {
            parallel_nand: true,
            spi_nand: true,
            spi_nor: true,
            emmc: true,
            nvddr: false,
            hardware_ecc: false,
            wifi: false,
            bluetooth: false,
            high_speed_usb: false,
        },
        protocol_version: if response.len() >= 2 { response[1] } else { 0 },
        firmware_version: None,
    })
}

/// Get platform info for the current connection
#[tauri::command]
pub fn get_platform_info(
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<Option<PlatformInfo>, String> {
    let manager = device_manager.lock().map_err(|e| e.to_string())?;
    
    if let Some(platform) = manager.get_platform() {
        let caps = manager.get_capabilities().cloned().unwrap_or_default();
        
        Ok(Some(PlatformInfo {
            platform: format!("{:?}", platform),
            platform_id: match platform {
                DevicePlatform::Rp2040 => 0x01,
                DevicePlatform::Stm32f1 => 0x02,
                DevicePlatform::Stm32f4 => 0x03,
                DevicePlatform::Esp32 => 0x04,
                DevicePlatform::Rp2350 => 0x05,
                DevicePlatform::RaspberryPi => 0x10,
                DevicePlatform::OrangePi => 0x11,
                DevicePlatform::ArduinoGiga => 0x20,
                DevicePlatform::Unknown => 0x00,
            },
            icon: platform.icon().to_string(),
            name: platform.name().to_string(),
            is_sbc: platform.is_sbc(),
            capabilities: DeviceCapabilitiesInfo {
                parallel_nand: caps.parallel_nand,
                spi_nand: caps.spi_nand,
                spi_nor: caps.spi_nor,
                emmc: caps.emmc,
                nvddr: caps.nvddr,
                hardware_ecc: caps.hardware_ecc,
                wifi: caps.wifi,
                bluetooth: caps.bluetooth,
                high_speed_usb: caps.high_speed_usb,
            },
            protocol_version: 0x23,
            firmware_version: None,
        }))
    } else {
        Ok(None)
    }
}

/// Add a network device (SBC) to the device list
#[tauri::command]
pub fn add_network_device(
    host: String,
    port: u16,
    name: Option<String>,
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<(), String> {
    let mut manager = device_manager.lock().map_err(|e| e.to_string())?;
    manager.add_network_device(host, port, name);
    Ok(())
}

/// Connect to a network device (TCP)
#[tauri::command]
pub async fn connect_network_device(
    host: String,
    port: u16,
    device_manager: State<'_, Mutex<DeviceManager>>,
) -> Result<(), String> {
    // For mock devices
    if host == "localhost" && port == 9999 && mock::is_mock_enabled() {
        return mock::mock_connect(&format!("mock:tcp:{}:{}", host, port));
    }
    
    let mut manager = device_manager.lock().map_err(|e| e.to_string())?;
    
    // Use tokio runtime for async connection
    // Note: This is a simplified version - real implementation would use proper async
    Err("Network connection not yet implemented for real devices".to_string())
}

/// Set mock platform for testing
#[tauri::command]
pub fn set_mock_platform(platform: String) -> Result<(), String> {
    let platform = match platform.to_lowercase().as_str() {
        "rp2040" | "pico" => DevicePlatform::Rp2040,
        "rp2350" | "pico2" => DevicePlatform::Rp2350,
        "stm32f1" | "bluepill" => DevicePlatform::Stm32f1,
        "stm32f4" | "blackpill" => DevicePlatform::Stm32f4,
        "esp32" => DevicePlatform::Esp32,
        "raspberrypi" | "rpi" => DevicePlatform::RaspberryPi,
        "orangepi" | "opi" => DevicePlatform::OrangePi,
        "arduinogiga" | "giga" => DevicePlatform::ArduinoGiga,
        _ => return Err(format!("Unknown platform: {}", platform)),
    };
    
    mock::set_mock_platform(platform);
    Ok(())
}
