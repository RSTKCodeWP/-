import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import "./PlatformInfo.css";

interface DeviceCapabilities {
  parallel_nand: boolean;
  spi_nand: boolean;
  spi_nor: boolean;
  emmc: boolean;
  nvddr: boolean;
  hardware_ecc: boolean;
  wifi: boolean;
  bluetooth: boolean;
  high_speed_usb: boolean;
  sd_card: boolean;
  logic_analyzer: boolean;
  soft_ecc: boolean;
}

interface PlatformInfoData {
  platform: string;
  platform_id: number;
  icon: string;
  name: string;
  is_sbc: boolean;
  capabilities: DeviceCapabilities;
  protocol_version: number;
  firmware_version: string | null;
}

interface Props {
  connected: boolean;
  onStatusChange?: (status: string) => void;
}

export function PlatformInfo({ connected, onStatusChange }: Props) {
  const [platformInfo, setPlatformInfo] = useState<PlatformInfoData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (connected) {
      fetchPlatformInfo();
    } else {
      setPlatformInfo(null);
    }
  }, [connected]);

  async function fetchPlatformInfo() {
    try {
      setLoading(true);
      const info = await invoke<PlatformInfoData>("get_device_info");
      setPlatformInfo(info);
      onStatusChange?.(`Connected to ${info.name}`);
    } catch (e) {
      onStatusChange?.(`Error: ${e}`);
    } finally {
      setLoading(false);
    }
  }

  if (!connected || loading) {
    return null;
  }

  if (!platformInfo) {
    return null;
  }

  const caps = platformInfo.capabilities;

  return (
    <div className="platform-info">
      <div className="platform-header">
        <span className="platform-icon">{platformInfo.icon}</span>
        <div className="platform-details">
          <span className="platform-name">{platformInfo.name}</span>
          <span className="platform-version">
            Protocol v{platformInfo.protocol_version.toString(16).toUpperCase()}
            {platformInfo.firmware_version && ` • FW ${platformInfo.firmware_version}`}
          </span>
        </div>
        {platformInfo.is_sbc && (
          <span className="sbc-badge" title="Single Board Computer">SBC</span>
        )}
      </div>

      <div className="capabilities">
        <div className="cap-row">
          <span className="cap-label">Interfaces:</span>
          <div className="cap-badges">
            {caps.parallel_nand && <span className="cap-badge">Parallel NAND</span>}
            {caps.spi_nand && <span className="cap-badge">SPI NAND</span>}
            {caps.spi_nor && <span className="cap-badge">SPI NOR</span>}
            {caps.emmc && <span className="cap-badge">eMMC</span>}
          </div>
        </div>
        
        <div className="cap-row">
          <span className="cap-label">Features:</span>
          <div className="cap-badges">
            {caps.nvddr && <span className="cap-badge feature">NV-DDR</span>}
            {caps.hardware_ecc && <span className="cap-badge feature">HW ECC</span>}
            {caps.high_speed_usb && <span className="cap-badge feature">USB HS 480M</span>}
            {caps.sd_card && <span className="cap-badge feature">SD Card</span>}
            {caps.logic_analyzer && <span className="cap-badge feature">Logic Analyzer</span>}
            {caps.soft_ecc && <span className="cap-badge feature">Soft ECC</span>}
            {caps.wifi && <span className="cap-badge wireless">WiFi</span>}
            {caps.bluetooth && <span className="cap-badge wireless">BT</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
