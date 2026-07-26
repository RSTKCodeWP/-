import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import "./NetworkDeviceDialog.css";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onDeviceAdded: () => void;
  onStatusChange?: (status: string) => void;
}

export function NetworkDeviceDialog({ isOpen, onClose, onDeviceAdded, onStatusChange }: Props) {
  const [host, setHost] = useState("192.168.1.100");
  const [port, setPort] = useState("9999");
  const [name, setName] = useState("");
  const [isConnecting, setIsConnecting] = useState(false);

  if (!isOpen) return null;

  async function handleAdd() {
    try {
      setIsConnecting(true);
      await invoke("add_network_device", {
        host,
        port: parseInt(port, 10),
        name: name || null,
      });
      onStatusChange?.(`Added network device ${host}:${port}`);
      onDeviceAdded();
      onClose();
    } catch (e) {
      onStatusChange?.(`Error: ${e}`);
    } finally {
      setIsConnecting(false);
    }
  }

  async function handleConnect() {
    try {
      setIsConnecting(true);
      await invoke("add_network_device", {
        host,
        port: parseInt(port, 10),
        name: name || null,
      });
      await invoke("connect_network_device", {
        host,
        port: parseInt(port, 10),
      });
      onStatusChange?.(`Connected to ${host}:${port}`);
      onDeviceAdded();
      onClose();
    } catch (e) {
      onStatusChange?.(`Error: ${e}`);
    } finally {
      setIsConnecting(false);
    }
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <h3>Add Network Device</h3>
        <p className="dialog-description">
          Connect to a Raspberry Pi or Orange Pi running the OpenFlash driver.
        </p>

        <div className="form-group">
          <label htmlFor="host">Host / IP Address</label>
          <input
            id="host"
            type="text"
            value={host}
            onChange={(e) => setHost(e.target.value)}
            placeholder="192.168.1.100"
          />
        </div>

        <div className="form-group">
          <label htmlFor="port">Port</label>
          <input
            id="port"
            type="number"
            value={port}
            onChange={(e) => setPort(e.target.value)}
            placeholder="9999"
          />
        </div>

        <div className="form-group">
          <label htmlFor="name">Name (optional)</label>
          <input
            id="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My Raspberry Pi"
          />
        </div>

        <div className="dialog-actions">
          <button onClick={onClose} className="secondary" disabled={isConnecting}>
            Cancel
          </button>
          <button onClick={handleAdd} className="secondary" disabled={isConnecting}>
            Add Only
          </button>
          <button onClick={handleConnect} disabled={isConnecting}>
            {isConnecting ? "Connecting..." : "Add & Connect"}
          </button>
        </div>
      </div>
    </div>
  );
}
