/**
 * USB device manager — wraps navigator.usb for DFU device lifecycle.
 * Provides device enumeration, labeling, and hot-plug detection.
 *
 * Parallel to serial-port-manager.ts but for WebUSB (DFU flash-only devices).
 *
 * @module usb-device-manager
 */

/// <reference path="./protocol/web-usb.d.ts" />

export interface UsbDeviceInfo {
  device: USBDevice;
  label: string;
  vendorId: number;
  productId: number;
  isDfu: boolean;
  /** Rockchip SoC bootrom (companion-computer image flash path). */
  isRockchip: boolean;
}

type UsbEventHandler = (info: UsbDeviceInfo) => void;

/** DFU device filters — covers common FC MCUs. */
const DFU_DEVICE_FILTERS: USBDeviceFilter[] = [
  { vendorId: 0x0483, productId: 0xdf11 },  // STM32 DFU
  { vendorId: 0x2e3c, productId: 0x0788 },  // AT32 DFU
  { vendorId: 0x29ac, productId: 0x0003 },  // GD32 DFU
  { vendorId: 0x2b04, productId: 0xd058 },  // Particle DFU
  { classCode: 0xfe, subclassCode: 0x01 },  // Generic DFU class
];

/** Rockchip vendor id used by every SoC's bootrom (maskrom + loader). */
const ROCKCHIP_VID = 0x2207;

/**
 * Rockchip bootrom filters — companion-computer SBC flashing path. The
 * bootrom enumerates as `0x2207` regardless of SoC and stage; we keep
 * the filter at vendor-only so a single picker entry covers maskrom and
 * loader stages across the supported SoC family.
 */
const ROCKCHIP_DEVICE_FILTERS: USBDeviceFilter[] = [
  { vendorId: ROCKCHIP_VID },
];

/** USB vendor/product database for known flash-mode devices. */
const DFU_DEVICES: Record<number, { name: string; products?: Record<number, string> }> = {
  0x0483: { name: "STMicroelectronics", products: {
    0xdf11: "STM32 DFU Bootloader",
  }},
  0x2e3c: { name: "Artery (AT32)", products: {
    0x0788: "AT32 DFU Bootloader",
  }},
  0x29ac: { name: "GigaDevice (GD32)", products: {
    0x0003: "GD32 DFU Bootloader",
  }},
  0x2b04: { name: "Particle", products: {
    0xd058: "Particle DFU",
  }},
  [ROCKCHIP_VID]: { name: "Rockchip", products: {
    0x110b: "Rockchip RV1103 Bootrom",
    0x110c: "Rockchip RV1106 Bootrom",
    0x320a: "Rockchip RK3308 Bootrom",
    0x320c: "Rockchip RK3399 Bootrom",
    0x350a: "Rockchip RK3568 Bootrom",
    0x350b: "Rockchip RK3566 Bootrom",
    0x350c: "Rockchip RK3588 Bootrom",
  }},
};

class UsbDeviceManagerImpl {
  private connectHandlers = new Set<UsbEventHandler>();
  private disconnectHandlers = new Set<UsbEventHandler>();
  private initialized = false;

  /** Check if WebUSB is available AND in a secure context. */
  isSupported(): boolean {
    return (
      typeof navigator !== "undefined" &&
      "usb" in navigator &&
      typeof window !== "undefined" &&
      window.isSecureContext
    );
  }

  /** Initialize hot-plug event listeners (call once on app mount). */
  init(): void {
    if (this.initialized || !this.isSupported()) return;
    this.initialized = true;

    navigator.usb.addEventListener("connect", ((e: USBConnectionEvent) => {
      const device = e.device;
      if (device) {
        const info = this.buildDeviceInfo(device);
        this.connectHandlers.forEach((h) => h(info));
      }
    }) as EventListener);

    navigator.usb.addEventListener("disconnect", ((e: USBConnectionEvent) => {
      const device = e.device;
      if (device) {
        const info = this.buildDeviceInfo(device);
        this.disconnectHandlers.forEach((h) => h(info));
      }
    }) as EventListener);
  }

  /** Get all previously-permitted USB devices filtered to DFU devices (no user prompt). */
  async getKnownDevices(): Promise<UsbDeviceInfo[]> {
    if (!this.isSupported()) return [];
    try {
      const devices = await navigator.usb.getDevices();
      return devices
        .map((d) => this.buildDeviceInfo(d))
        .filter((d) => d.isDfu);
    } catch {
      return [];
    }
  }

  /** Open browser USB device picker filtered to DFU devices. */
  async requestDevice(): Promise<USBDevice> {
    if (typeof navigator === "undefined" || !("usb" in navigator)) {
      throw new Error("WebUSB not supported — use Chrome or Edge");
    }
    if (typeof window !== "undefined" && !window.isSecureContext) {
      throw new Error(
        "WebUSB requires HTTPS or localhost. Current origin is not secure — " +
        "access Command via https:// or http://localhost:4000"
      );
    }
    return navigator.usb.requestDevice({ filters: DFU_DEVICE_FILTERS });
  }

  /** Open browser USB device picker filtered to Rockchip bootrom devices. */
  async requestRockchipDevice(): Promise<USBDevice> {
    if (typeof navigator === "undefined" || !("usb" in navigator)) {
      throw new Error("WebUSB not supported — use Chrome or Edge");
    }
    if (typeof window !== "undefined" && !window.isSecureContext) {
      throw new Error(
        "WebUSB requires HTTPS or localhost. Current origin is not secure — " +
        "access Command via https:// or http://localhost:4000"
      );
    }
    return navigator.usb.requestDevice({ filters: ROCKCHIP_DEVICE_FILTERS });
  }

  /** Get all previously-permitted Rockchip bootrom devices (no user prompt). */
  async getKnownRockchipDevices(): Promise<UsbDeviceInfo[]> {
    if (!this.isSupported()) return [];
    try {
      const devices = await navigator.usb.getDevices();
      return devices
        .map((d) => this.buildDeviceInfo(d))
        .filter((d) => d.isRockchip);
    } catch {
      return [];
    }
  }

  /** Subscribe to USB connect events. Returns unsubscribe function. */
  onConnect(handler: UsbEventHandler): () => void {
    this.connectHandlers.add(handler);
    return () => this.connectHandlers.delete(handler);
  }

  /** Subscribe to USB disconnect events. Returns unsubscribe function. */
  onDisconnect(handler: UsbEventHandler): () => void {
    this.disconnectHandlers.add(handler);
    return () => this.disconnectHandlers.delete(handler);
  }

  /** Build a labeled info object for a USB device. */
  buildDeviceInfo(device: USBDevice): UsbDeviceInfo {
    const vid = device.vendorId;
    const pid = device.productId;
    const isDfu = this.isDfuDevice(device);
    const isRockchip = this.isRockchipDevice(device);

    let label: string;
    const vendor = DFU_DEVICES[vid];
    const productName = vendor?.products?.[pid];
    if (productName) {
      label = `${productName} (${hex(vid)}:${hex(pid)})`;
    } else if (device.productName) {
      label = `${device.productName} (${hex(vid)}:${hex(pid)})`;
    } else if (vendor) {
      label = `${vendor.name} Device (${hex(vid)}:${hex(pid)})`;
    } else {
      label = `USB Device (${hex(vid)}:${hex(pid)})`;
    }

    return { device, label, vendorId: vid, productId: pid, isDfu, isRockchip };
  }

  /** Check if a USB device is a DFU device (by VID:PID or interface class). */
  private isDfuDevice(device: USBDevice): boolean {
    // Check known DFU VID:PID combos
    if (
      (device.vendorId === 0x0483 && device.productId === 0xdf11) ||
      (device.vendorId === 0x2e3c && device.productId === 0x0788) ||
      (device.vendorId === 0x29ac && device.productId === 0x0003) ||
      (device.vendorId === 0x2b04 && device.productId === 0xd058)
    ) {
      return true;
    }
    // Check DFU interface class (0xFE subclass 0x01)
    if (device.configuration) {
      for (const iface of device.configuration.interfaces) {
        for (const alt of iface.alternates) {
          if (alt.interfaceClass === 0xfe && alt.interfaceSubclass === 0x01) {
            return true;
          }
        }
      }
    }
    return false;
  }

  /** Check if a USB device is a Rockchip bootrom (maskrom or loader stage). */
  private isRockchipDevice(device: USBDevice): boolean {
    return device.vendorId === ROCKCHIP_VID;
  }
}

function hex(n: number): string {
  return n.toString(16).toUpperCase().padStart(4, "0");
}

/** Singleton USB device manager. */
export const usbDeviceManager = new UsbDeviceManagerImpl();
