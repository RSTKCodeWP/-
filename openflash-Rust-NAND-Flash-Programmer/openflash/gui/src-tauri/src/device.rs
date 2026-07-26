//! USB device management for OpenFlash

use nusb::transfer::RequestBuffer;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::Mutex as TokioMutex;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;
#[cfg(unix)]
use tokio::net::UnixStream;

use openflash_core::protocol::{Command, Packet};

const VENDOR_ID: u16 = 0xC0DE;
const PRODUCT_ID: u16 = 0xCAFE;
const EP_OUT: u8 = 0x01;
const EP_IN: u8 = 0x81;

/// Flash interface type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
pub enum FlashInterface {
    #[default]
    ParallelNand,
    SpiNand,
    SpiNor,
    Ufs,
    Emmc,
}

/// Device platform type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum DevicePlatform {
    Unknown,
    Rp2040,      // 0x01 - Raspberry Pi Pico
    Stm32f1,     // 0x02 - Blue Pill
    Stm32f4,     // 0x03 - Black Pill
    Esp32,       // 0x04 - ESP32
    Rp2350,      // 0x05 - Raspberry Pi Pico 2
    RaspberryPi, // 0x10 - Raspberry Pi SBC
    OrangePi,    // 0x11 - Orange Pi SBC
    BananaPi,    // 0x12 - Banana Pi SBC
    ArduinoGiga, // 0x20 - Arduino GIGA R1 WiFi
    Teensy40,    // 0x30 - Teensy 4.0
    Teensy41,    // 0x31 - Teensy 4.1
}

impl DevicePlatform {
    pub fn from_id(id: u8) -> Self {
        match id {
            0x01 => DevicePlatform::Rp2040,
            0x02 => DevicePlatform::Stm32f1,
            0x03 => DevicePlatform::Stm32f4,
            0x04 => DevicePlatform::Esp32,
            0x05 => DevicePlatform::Rp2350,
            0x10 => DevicePlatform::RaspberryPi,
            0x11 => DevicePlatform::OrangePi,
            0x12 | 0x13 | 0x14 => DevicePlatform::BananaPi,
            0x20 => DevicePlatform::ArduinoGiga,
            0x30 => DevicePlatform::Teensy40,
            0x31 => DevicePlatform::Teensy41,
            _ => DevicePlatform::Unknown,
        }
    }

    pub fn name(&self) -> &'static str {
        match self {
            DevicePlatform::Unknown => "Unknown",
            DevicePlatform::Rp2040 => "Raspberry Pi Pico",
            DevicePlatform::Stm32f1 => "STM32F1 Blue Pill",
            DevicePlatform::Stm32f4 => "STM32F4 Black Pill",
            DevicePlatform::Esp32 => "ESP32",
            DevicePlatform::Rp2350 => "Raspberry Pi Pico 2",
            DevicePlatform::RaspberryPi => "Raspberry Pi",
            DevicePlatform::OrangePi => "Orange Pi",
            DevicePlatform::BananaPi => "Banana Pi",
            DevicePlatform::ArduinoGiga => "Arduino GIGA R1 WiFi",
            DevicePlatform::Teensy40 => "Teensy 4.0",
            DevicePlatform::Teensy41 => "Teensy 4.1",
        }
    }

    pub fn icon(&self) -> &'static str {
        match self {
            DevicePlatform::Unknown => "❓",
            DevicePlatform::Rp2040 => "🍓",
            DevicePlatform::Stm32f1 => "💙",
            DevicePlatform::Stm32f4 => "🖤",
            DevicePlatform::Esp32 => "📶",
            DevicePlatform::Rp2350 => "🍓",
            DevicePlatform::RaspberryPi => "🥧",
            DevicePlatform::OrangePi => "🍊",
            DevicePlatform::BananaPi => "🍌",
            DevicePlatform::ArduinoGiga => "🔵",
            DevicePlatform::Teensy40 => "⚡",
            DevicePlatform::Teensy41 => "⚡",
        }
    }

    pub fn is_sbc(&self) -> bool {
        matches!(self, DevicePlatform::RaspberryPi | DevicePlatform::OrangePi | DevicePlatform::BananaPi)
    }

    pub fn is_high_speed(&self) -> bool {
        matches!(self, DevicePlatform::Teensy40 | DevicePlatform::Teensy41 | DevicePlatform::ArduinoGiga)
    }

    pub fn has_sd_card(&self) -> bool {
        matches!(self, DevicePlatform::Teensy41)
    }
}

/// Device capabilities bitmap
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct DeviceCapabilities {
    pub parallel_nand: bool,
    pub spi_nand: bool,
    pub spi_nor: bool,
    pub emmc: bool,
    pub nvddr: bool,           // NV-DDR timing support (RP2350)
    pub hardware_ecc: bool,    // Hardware ECC (STM32H747 FMC)
    pub wifi: bool,            // WiFi connectivity
    pub bluetooth: bool,       // Bluetooth connectivity
    pub high_speed_usb: bool,  // USB HS (480Mbps) - Teensy 4.x
    pub sd_card: bool,         // SD card slot (Teensy 4.1)
    pub logic_analyzer: bool,  // Logic analyzer mode (Teensy 4.x)
    pub soft_ecc: bool,        // Soft ECC on-the-fly (Teensy 4.x)
}

impl DeviceCapabilities {
    pub fn from_bitmap(bitmap: u32) -> Self {
        Self {
            parallel_nand: bitmap & 0x01 != 0,
            spi_nand: bitmap & 0x02 != 0,
            spi_nor: bitmap & 0x04 != 0,
            emmc: bitmap & 0x08 != 0,
            nvddr: bitmap & 0x10 != 0,
            hardware_ecc: bitmap & 0x20 != 0,
            wifi: bitmap & 0x40 != 0,
            bluetooth: bitmap & 0x80 != 0,
            high_speed_usb: bitmap & 0x100 != 0,
            sd_card: bitmap & 0x200 != 0,
            logic_analyzer: bitmap & 0x400 != 0,
            soft_ecc: bitmap & 0x800 != 0,
        }
    }
}

/// Connection type for device
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ConnectionType {
    Usb,
    Tcp { host: String, port: u16 },
    #[cfg(unix)]
    UnixSocket { path: String },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceInfo {
    pub id: String,
    pub name: String,
    pub serial: Option<String>,
    pub connected: bool,
    #[serde(default)]
    pub platform: Option<DevicePlatform>,
    #[serde(default)]
    pub capabilities: Option<DeviceCapabilities>,
    #[serde(default)]
    pub connection_type: Option<ConnectionType>,
    #[serde(default)]
    pub protocol_version: Option<u8>,
    #[serde(default)]
    pub firmware_version: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChipInfo {
    pub manufacturer: String,
    pub model: String,
    pub chip_id: Vec<u8>,
    pub size_mb: u32,
    pub page_size: u32,
    pub block_size: u32,
    pub interface: FlashInterface,
    // SPI NOR specific fields
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sector_size: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub jedec_id: Option<Vec<u8>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub has_qspi: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub has_dual: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub voltage: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_clock_mhz: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub protected: Option<bool>,
    // UFS specific fields
    #[serde(skip_serializing_if = "Option::is_none")]
    pub luns: Option<Vec<UfsLunInfo>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ufs_version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub serial_number: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub boot_lun_enabled: Option<bool>,
}

/// UFS Logical Unit information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UfsLunInfo {
    #[serde(rename = "type")]
    pub lun_type: String,
    pub capacity_bytes: u64,
    pub block_size: u32,
    pub enabled: bool,
    pub write_protected: bool,
}

pub struct UsbDevice {
    interface: nusb::Interface,
}

/// Network device (TCP or Unix socket)
pub struct NetworkDevice {
    stream: NetworkStream,
}

enum NetworkStream {
    Tcp(TcpStream),
    #[cfg(unix)]
    Unix(UnixStream),
}

impl NetworkDevice {
    pub async fn connect_tcp(host: &str, port: u16) -> Result<Self, String> {
        let addr = format!("{}:{}", host, port);
        let stream = TcpStream::connect(&addr)
            .await
            .map_err(|e| format!("TCP connection failed: {}", e))?;
        Ok(Self {
            stream: NetworkStream::Tcp(stream),
        })
    }

    #[cfg(unix)]
    pub async fn connect_unix(path: &str) -> Result<Self, String> {
        let stream = UnixStream::connect(path)
            .await
            .map_err(|e| format!("Unix socket connection failed: {}", e))?;
        Ok(Self {
            stream: NetworkStream::Unix(stream),
        })
    }

    pub async fn send_command(&mut self, cmd: Command, args: &[u8]) -> Result<Vec<u8>, String> {
        let packet = Packet::new(cmd, args);
        let data = packet.to_bytes();

        // Send command
        match &mut self.stream {
            NetworkStream::Tcp(stream) => {
                stream.write_all(&data).await
                    .map_err(|e| format!("TCP write error: {}", e))?;
            }
            #[cfg(unix)]
            NetworkStream::Unix(stream) => {
                stream.write_all(&data).await
                    .map_err(|e| format!("Unix socket write error: {}", e))?;
            }
        }

        // Receive response
        let mut response = vec![0u8; 64];
        match &mut self.stream {
            NetworkStream::Tcp(stream) => {
                stream.read_exact(&mut response).await
                    .map_err(|e| format!("TCP read error: {}", e))?;
            }
            #[cfg(unix)]
            NetworkStream::Unix(stream) => {
                stream.read_exact(&mut response).await
                    .map_err(|e| format!("Unix socket read error: {}", e))?;
            }
        }

        Ok(response)
    }
}

/// Active device connection (USB or Network)
pub enum ActiveDevice {
    Usb(Arc<TokioMutex<UsbDevice>>),
    Network(Arc<TokioMutex<NetworkDevice>>),
}
    interface: nusb::Interface,
}

impl UsbDevice {
    pub async fn send_command(&self, cmd: Command, args: &[u8]) -> Result<Vec<u8>, String> {
        let packet = Packet::new(cmd, args);
        let data = packet.to_bytes();

        // Send command
        self.interface
            .bulk_out(EP_OUT, data.to_vec())
            .await
            .status
            .map_err(|e| format!("USB write error: {:?}", e))?;

        // Receive response
        let buf = RequestBuffer::new(64);
        let result = self.interface.bulk_in(EP_IN, buf).await;

        result
            .status
            .map_err(|e| format!("USB read error: {:?}", e))?;
        Ok(result.data)
    }

    pub async fn read_page(&self, page_addr: u32, page_size: u16) -> Result<Vec<u8>, String> {
        let mut args = [0u8; 6];
        args[0..4].copy_from_slice(&page_addr.to_le_bytes());
        args[4..6].copy_from_slice(&page_size.to_le_bytes());

        self.send_command(Command::NandReadPage, &args).await?;

        let mut data = Vec::with_capacity(page_size as usize);
        while data.len() < page_size as usize {
            let buf = RequestBuffer::new(64);
            let result = self.interface.bulk_in(EP_IN, buf).await;
            result
                .status
                .map_err(|e| format!("USB read error: {:?}", e))?;

            let remaining = page_size as usize - data.len();
            let to_copy = remaining.min(result.data.len());
            data.extend_from_slice(&result.data[..to_copy]);
        }

        Ok(data)
    }
}

pub struct DeviceManager {
    devices: Vec<DeviceInfo>,
    active_device: Option<ActiveDevice>,
    interface: FlashInterface,
    current_platform: Option<DevicePlatform>,
    current_capabilities: Option<DeviceCapabilities>,
}

impl DeviceManager {
    pub fn new() -> Self {
        Self {
            devices: Vec::new(),
            active_device: None,
            interface: FlashInterface::ParallelNand,
            current_platform: None,
            current_capabilities: None,
        }
    }

    pub fn set_interface(&mut self, interface: FlashInterface) {
        self.interface = interface;
    }

    pub fn get_interface(&self) -> FlashInterface {
        self.interface
    }

    pub fn get_platform(&self) -> Option<DevicePlatform> {
        self.current_platform
    }

    pub fn get_capabilities(&self) -> Option<&DeviceCapabilities> {
        self.current_capabilities.as_ref()
    }

    pub fn scan_devices(&mut self) -> Vec<DeviceInfo> {
        self.devices.clear();

        // Scan USB devices
        if let Ok(devices) = nusb::list_devices() {
            for dev_info in devices {
                if dev_info.vendor_id() == VENDOR_ID && dev_info.product_id() == PRODUCT_ID {
                    let id = format!(
                        "{:04x}:{:04x}:{}",
                        dev_info.vendor_id(),
                        dev_info.product_id(),
                        dev_info.bus_number()
                    );

                    let name = dev_info
                        .product_string()
                        .unwrap_or("OpenFlash Device")
                        .to_string();

                    let serial = dev_info.serial_number().map(|s| s.to_string());

                    self.devices.push(DeviceInfo {
                        id,
                        name,
                        serial,
                        connected: false,
                        platform: None,
                        capabilities: None,
                        connection_type: Some(ConnectionType::Usb),
                        protocol_version: None,
                        firmware_version: None,
                    });
                }
            }
        }

        self.devices.clone()
    }

    /// Add a network device (SBC) manually
    pub fn add_network_device(&mut self, host: String, port: u16, name: Option<String>) {
        let id = format!("tcp:{}:{}", host, port);
        let device_name = name.unwrap_or_else(|| format!("Network Device ({}:{})", host, port));
        
        self.devices.push(DeviceInfo {
            id,
            name: device_name,
            serial: None,
            connected: false,
            platform: None,
            capabilities: None,
            connection_type: Some(ConnectionType::Tcp { host, port }),
            protocol_version: None,
            firmware_version: None,
        });
    }

    /// Add a Unix socket device (local SBC)
    #[cfg(unix)]
    pub fn add_unix_socket_device(&mut self, path: String, name: Option<String>) {
        let id = format!("unix:{}", path);
        let device_name = name.unwrap_or_else(|| format!("Local Device ({})", path));
        
        self.devices.push(DeviceInfo {
            id,
            name: device_name,
            serial: None,
            connected: false,
            platform: None,
            capabilities: None,
            connection_type: Some(ConnectionType::UnixSocket { path }),
            protocol_version: None,
            firmware_version: None,
        });
    }

    pub fn list_devices(&self) -> Vec<DeviceInfo> {
        self.devices.clone()
    }

    pub fn connect(&mut self, device_id: &str) -> Result<(), String> {
        // Check if it's a network device
        if device_id.starts_with("tcp:") {
            return Err("Use connect_network for TCP devices".to_string());
        }
        
        #[cfg(unix)]
        if device_id.starts_with("unix:") {
            return Err("Use connect_unix_socket for Unix socket devices".to_string());
        }

        let devices = nusb::list_devices().map_err(|e| format!("Failed to list devices: {}", e))?;

        for dev_info in devices {
            let id = format!(
                "{:04x}:{:04x}:{}",
                dev_info.vendor_id(),
                dev_info.product_id(),
                dev_info.bus_number()
            );

            if id == device_id {
                let device = dev_info
                    .open()
                    .map_err(|e| format!("Failed to open device: {}", e))?;

                let interface = device
                    .claim_interface(0)
                    .map_err(|e| format!("Failed to claim interface: {}", e))?;

                self.active_device = Some(ActiveDevice::Usb(
                    Arc::new(TokioMutex::new(UsbDevice { interface }))
                ));

                for dev in &mut self.devices {
                    if dev.id == device_id {
                        dev.connected = true;
                    }
                }

                return Ok(());
            }
        }

        Err("Device not found".to_string())
    }

    /// Connect to a network device (TCP)
    pub async fn connect_network(&mut self, host: &str, port: u16) -> Result<(), String> {
        let network_device = NetworkDevice::connect_tcp(host, port).await?;
        
        self.active_device = Some(ActiveDevice::Network(
            Arc::new(TokioMutex::new(network_device))
        ));

        let device_id = format!("tcp:{}:{}", host, port);
        for dev in &mut self.devices {
            if dev.id == device_id {
                dev.connected = true;
            }
        }

        Ok(())
    }

    /// Connect to a Unix socket device
    #[cfg(unix)]
    pub async fn connect_unix_socket(&mut self, path: &str) -> Result<(), String> {
        let network_device = NetworkDevice::connect_unix(path).await?;
        
        self.active_device = Some(ActiveDevice::Network(
            Arc::new(TokioMutex::new(network_device))
        ));

        let device_id = format!("unix:{}", path);
        for dev in &mut self.devices {
            if dev.id == device_id {
                dev.connected = true;
            }
        }

        Ok(())
    }

    pub fn disconnect(&mut self) {
        self.active_device = None;
        self.current_platform = None;
        self.current_capabilities = None;
        for dev in &mut self.devices {
            dev.connected = false;
        }
    }

    pub fn get_active_device(&self) -> Option<Arc<TokioMutex<UsbDevice>>> {
        match &self.active_device {
            Some(ActiveDevice::Usb(dev)) => Some(dev.clone()),
            _ => None,
        }
    }

    pub fn get_active_network_device(&self) -> Option<Arc<TokioMutex<NetworkDevice>>> {
        match &self.active_device {
            Some(ActiveDevice::Network(dev)) => Some(dev.clone()),
            _ => None,
        }
    }

    pub fn is_network_connection(&self) -> bool {
        matches!(&self.active_device, Some(ActiveDevice::Network(_)))
    }

    /// Update device info after connection (platform, capabilities, etc.)
    pub fn update_device_info(&mut self, platform: DevicePlatform, capabilities: DeviceCapabilities, 
                               protocol_version: u8, firmware_version: Option<String>) {
        self.current_platform = Some(platform);
        self.current_capabilities = Some(capabilities.clone());
        
        // Update the connected device in the list
        for dev in &mut self.devices {
            if dev.connected {
                dev.platform = Some(platform);
                dev.capabilities = Some(capabilities.clone());
                dev.protocol_version = Some(protocol_version);
                dev.firmware_version = firmware_version.clone();
                dev.name = format!("{} {}", platform.icon(), platform.name());
            }
        }
    }
}

impl Default for DeviceManager {
    fn default() -> Self {
        Self::new()
    }
}
