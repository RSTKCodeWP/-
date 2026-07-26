import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import "./UfsLunSelector.css";

type UfsLunType = "UserData" | "BootA" | "BootB" | "Rpmb";

interface UfsLun {
  type: UfsLunType;
  capacity_bytes: number;
  block_size: number;
  enabled: boolean;
  write_protected: boolean;
}

interface UfsLunSelectorProps {
  luns: UfsLun[];
  selectedLun: UfsLunType | null;
  onLunSelect: (lun: UfsLunType) => void;
  ufsVersion?: string;
  disabled: boolean;
  onStatusChange: (status: string) => void;
}

export function UfsLunSelector({
  luns,
  selectedLun,
  onLunSelect,
  ufsVersion,
  disabled,
  onStatusChange,
}: UfsLunSelectorProps) {
  const [isSelecting, setIsSelecting] = useState(false);

  function formatCapacity(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
  }

  function getLunIcon(type: UfsLunType): string {
    switch (type) {
      case "UserData":
        return "💾";
      case "BootA":
        return "🅰️";
      case "BootB":
        return "🅱️";
      case "Rpmb":
        return "🔐";
      default:
        return "📦";
    }
  }

  function getLunDisplayName(type: UfsLunType): string {
    switch (type) {
      case "UserData":
        return "User Data";
      case "BootA":
        return "Boot LUN A";
      case "BootB":
        return "Boot LUN B";
      case "Rpmb":
        return "RPMB";
      default:
        return type;
    }
  }

  async function handleLunSelect(lunType: UfsLunType) {
    if (disabled || isSelecting) return;
    
    setIsSelecting(true);
    try {
      await invoke("ufs_select_lun", { lunType });
      onLunSelect(lunType);
      onStatusChange(`Selected ${getLunDisplayName(lunType)}`);
    } catch (e) {
      onStatusChange(`Failed to select LUN: ${e}`);
    } finally {
      setIsSelecting(false);
    }
  }

  const enabledLuns = luns.filter(lun => lun.enabled);

  return (
    <div className="ufs-lun-selector">
      <h3>UFS Logical Units</h3>
      
      {/* UFS Version */}
      {ufsVersion && (
        <div className="ufs-version">
          <span className="label">Version:</span>
          <span className="value">{ufsVersion}</span>
        </div>
      )}

      {/* LUN List */}
      <div className="lun-list">
        {enabledLuns.length === 0 ? (
          <div className="empty-luns">
            No LUNs available
          </div>
        ) : (
          enabledLuns.map((lun) => (
            <div
              key={lun.type}
              className={`lun-item ${selectedLun === lun.type ? "selected" : ""} ${disabled || isSelecting ? "disabled" : ""}`}
              onClick={() => handleLunSelect(lun.type)}
            >
              <div className="lun-header">
                <span className="lun-icon">{getLunIcon(lun.type)}</span>
                <span className="lun-name">{getLunDisplayName(lun.type)}</span>
                {lun.write_protected && (
                  <span className="lun-protected" title="Write Protected">🔒</span>
                )}
              </div>
              <div className="lun-details">
                <span className="lun-capacity">{formatCapacity(lun.capacity_bytes)}</span>
                <span className="lun-block-size">{lun.block_size} B/block</span>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Selected LUN Info */}
      {selectedLun && (
        <div className="selected-lun-info">
          <span className="label">Active:</span>
          <span className="value">
            {getLunIcon(selectedLun)} {getLunDisplayName(selectedLun)}
          </span>
        </div>
      )}

      {/* LUN Description */}
      <div className="lun-descriptions">
        <details>
          <summary>LUN Types</summary>
          <ul>
            <li><strong>User Data:</strong> Main storage partition for user data</li>
            <li><strong>Boot LUN A/B:</strong> Boot partitions for A/B update schemes</li>
            <li><strong>RPMB:</strong> Replay Protected Memory Block for secure storage</li>
          </ul>
        </details>
      </div>
    </div>
  );
}
