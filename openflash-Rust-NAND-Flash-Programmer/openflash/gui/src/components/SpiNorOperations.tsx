import { useState } from "react";
import "./SpiNorOperations.css";

interface ProtectionBits {
  bp0: boolean;
  bp1: boolean;
  bp2: boolean;
  tb: boolean;
  sec: boolean;
  cmp: boolean;
}

interface SpiNorOperationsProps {
  chipInfo: {
    manufacturer: string;
    model: string;
    size_mb: number;
    sector_size?: number;
    block_size: number;
    protected?: boolean;
    protection_bits?: ProtectionBits;
    has_qspi?: boolean;
    voltage?: string;
  };
  onOperation: (operation: string, address?: number) => Promise<void>;
  disabled: boolean;
  onStatusChange: (status: string) => void;
}

export function SpiNorOperations({ 
  chipInfo, 
  onOperation, 
  disabled,
  onStatusChange 
}: SpiNorOperationsProps) {
  const [eraseAddress, setEraseAddress] = useState<string>("0x0");
  const [isErasing, setIsErasing] = useState(false);

  const sectorSize = chipInfo.sector_size || 4096;
  const blockSize = chipInfo.block_size || 65536;

  async function handleSectorErase() {
    const address = parseInt(eraseAddress, 16);
    if (isNaN(address)) {
      onStatusChange("Invalid address");
      return;
    }
    
    setIsErasing(true);
    try {
      await onOperation("sector_erase", address);
      onStatusChange(`Sector erased at 0x${address.toString(16).toUpperCase()}`);
    } catch (e) {
      onStatusChange(`Erase failed: ${e}`);
    } finally {
      setIsErasing(false);
    }
  }

  async function handleBlockErase() {
    const address = parseInt(eraseAddress, 16);
    if (isNaN(address)) {
      onStatusChange("Invalid address");
      return;
    }
    
    setIsErasing(true);
    try {
      await onOperation("block_erase", address);
      onStatusChange(`Block erased at 0x${address.toString(16).toUpperCase()}`);
    } catch (e) {
      onStatusChange(`Erase failed: ${e}`);
    } finally {
      setIsErasing(false);
    }
  }

  async function handleChipErase() {
    if (!confirm("Are you sure you want to erase the entire chip? This cannot be undone.")) {
      return;
    }
    
    setIsErasing(true);
    try {
      await onOperation("chip_erase");
      onStatusChange("Chip erase complete");
    } catch (e) {
      onStatusChange(`Chip erase failed: ${e}`);
    } finally {
      setIsErasing(false);
    }
  }

  async function handleUnlockAll() {
    try {
      await onOperation("unlock_all");
      onStatusChange("Protection removed");
    } catch (e) {
      onStatusChange(`Unlock failed: ${e}`);
    }
  }

  function formatProtectionBits(bits?: ProtectionBits): string {
    if (!bits) return "Unknown";
    const active: string[] = [];
    if (bits.bp0) active.push("BP0");
    if (bits.bp1) active.push("BP1");
    if (bits.bp2) active.push("BP2");
    if (bits.tb) active.push("TB");
    if (bits.sec) active.push("SEC");
    if (bits.cmp) active.push("CMP");
    return active.length > 0 ? active.join(", ") : "None";
  }

  return (
    <div className="spi-nor-operations">
      <h3>SPI NOR Operations</h3>
      
      {/* Chip Details */}
      <div className="nor-chip-details">
        <div className="detail-row">
          <span className="label">Sector Size:</span>
          <span className="value">{(sectorSize / 1024).toFixed(0)} KB</span>
        </div>
        <div className="detail-row">
          <span className="label">Block Size:</span>
          <span className="value">{(blockSize / 1024).toFixed(0)} KB</span>
        </div>
        {chipInfo.voltage && (
          <div className="detail-row">
            <span className="label">Voltage:</span>
            <span className="value">{chipInfo.voltage}</span>
          </div>
        )}
        {chipInfo.has_qspi !== undefined && (
          <div className="detail-row">
            <span className="label">QSPI:</span>
            <span className="value">{chipInfo.has_qspi ? "✓ Supported" : "✗ Not supported"}</span>
          </div>
        )}
      </div>

      {/* Protection Status */}
      <div className="protection-section">
        <h4>Protection Status</h4>
        <div className="protection-status">
          <span className={`status-indicator ${chipInfo.protected ? "protected" : "unprotected"}`}>
            {chipInfo.protected ? "🔒 Protected" : "🔓 Unprotected"}
          </span>
          {chipInfo.protection_bits && (
            <span className="protection-bits">
              Active bits: {formatProtectionBits(chipInfo.protection_bits)}
            </span>
          )}
        </div>
        <button 
          onClick={handleUnlockAll} 
          disabled={disabled || !chipInfo.protected}
          className="unlock-btn"
        >
          🔓 Unlock All
        </button>
      </div>

      {/* Erase Operations */}
      <div className="erase-section">
        <h4>Erase Operations</h4>
        
        <div className="address-input">
          <label>Address:</label>
          <input
            type="text"
            value={eraseAddress}
            onChange={(e) => setEraseAddress(e.target.value)}
            placeholder="0x0"
            disabled={disabled || isErasing}
          />
        </div>

        <div className="erase-buttons">
          <button 
            onClick={handleSectorErase} 
            disabled={disabled || isErasing}
            title={`Erase ${(sectorSize / 1024).toFixed(0)}KB sector at address`}
          >
            {isErasing ? "⏳" : "🗑️"} Sector ({(sectorSize / 1024).toFixed(0)}KB)
          </button>
          <button 
            onClick={handleBlockErase} 
            disabled={disabled || isErasing}
            title={`Erase ${(blockSize / 1024).toFixed(0)}KB block at address`}
          >
            {isErasing ? "⏳" : "🗑️"} Block ({(blockSize / 1024).toFixed(0)}KB)
          </button>
          <button 
            onClick={handleChipErase} 
            disabled={disabled || isErasing}
            className="danger"
            title="Erase entire chip - WARNING: This cannot be undone!"
          >
            {isErasing ? "⏳ Erasing..." : "⚠️ Chip Erase"}
          </button>
        </div>
      </div>
    </div>
  );
}
