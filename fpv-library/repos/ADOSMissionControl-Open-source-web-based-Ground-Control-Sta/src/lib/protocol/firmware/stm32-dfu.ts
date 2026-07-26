/**
 * STM32 USB DFU v1.1 + DFuSe extensions via WebUSB API.
 *
 * For flight controllers that expose a native USB DFU interface
 * (e.g. STM32H743 boards without USB-UART bridge). Secondary
 * flash method — most FCs use the serial bootloader instead.
 *
 * @module protocol/firmware/stm32-dfu
 */

/// <reference path="../web-usb.d.ts" />

import type { FirmwareFlasher, FlashProgressCallback, FlashLogCallback, FlashRunOptions, ParsedFirmware, DfuFlashLayout } from "./types";
import { DFU_STATE, DFU_STATE_NAME } from "./types";
import { usbDeviceManager, type UsbDeviceInfo } from "../../usb-device-manager";
import { getFlashLayout, getTransferSize } from "./stm32-dfu-descriptors";
import { dfuErasePages, dfuWriteBlocks, dfuVerifyBlocks, type DfuFlashContext } from "./stm32-dfu-flash";

const DFU_DNLOAD = 0x01;
const DFU_UPLOAD = 0x02;
const DFU_GETSTATUS = 0x03;
const DFU_CLRSTATUS = 0x04;
const DFU_ABORT = 0x06;
const DFUSE_CMD_SET_ADDRESS = 0x21;
const DFUSE_CMD_ERASE = 0x41;
const DEFAULT_TRANSFER_SIZE = 2048;
const DFU_TIMEOUT = 5000;
const ERASE_TIMEOUT = 30000;

export class STM32DfuFlasher implements FirmwareFlasher {
  readonly method = "dfu" as const;
  private device: USBDevice;
  private interfaceNumber = 0;
  private transferSize = DEFAULT_TRANSFER_SIZE;
  private flashLayout: DfuFlashLayout | null = null;
  private aborted = false;

  constructor(device: USBDevice) { this.device = device; }

  static isSupported(): boolean { return usbDeviceManager.isSupported(); }
  static async requestDevice(): Promise<USBDevice> { return usbDeviceManager.requestDevice(); }
  static async getKnownDevices(): Promise<UsbDeviceInfo[]> { return usbDeviceManager.getKnownDevices(); }

  private get flashCtx(): DfuFlashContext {
    return {
      transferSize: this.transferSize, flashLayout: this.flashLayout,
      erasePage: (a) => this.erasePage(a), loadAddress: (a) => this.loadAddress(a),
      writeBlock: (n, d) => this.writeBlock(n, d), readBlock: (n, l) => this.readBlock(n, l),
      checkAbort: () => this.checkAbort(),
    };
  }

  async flash(firmware: ParsedFirmware, onProgress: FlashProgressCallback, signal?: AbortSignal, onLog?: FlashLogCallback, options?: FlashRunOptions): Promise<void> {
    this.aborted = false;
    if (signal) signal.addEventListener("abort", () => this.abort(), { once: true });
    try {
      onProgress({ phase: "bootloader_init", percent: 8, message: "Opening USB device..." });
      await this.openAndClaim();
      onProgress({ phase: "chip_detect", percent: 10, message: "Reading flash layout..." });
      this.flashLayout = await getFlashLayout(this.device, this.interfaceNumber);
      this.transferSize = await getTransferSize(this.device, DEFAULT_TRANSFER_SIZE);
      if (this.flashLayout) onProgress({ phase: "chip_detect", percent: 12, message: `Flash: ${this.flashLayout.name} (${(this.flashLayout.totalSize / 1024)}KB), transfer size: ${this.transferSize}` });
      await this.clearStatus();
      this.checkAbort();
      if (this.flashLayout) {
        if (firmware.totalBytes > this.flashLayout.totalSize) throw new Error(`Firmware (${firmware.totalBytes} bytes) exceeds flash size (${this.flashLayout.totalSize} bytes)`);
        onProgress({ phase: "erasing", percent: 15, message: "Erasing flash sectors..." });
        await dfuErasePages(this.flashCtx, firmware, onProgress);
      } else {
        console.warn("[DFU] Flash layout unavailable — falling back to mass erase");
        await this.massErase(onProgress);
      }
      onProgress({ phase: "erasing", percent: 25, message: "Erase complete" });
      this.checkAbort();
      await dfuWriteBlocks(this.flashCtx, firmware, onProgress);
      this.checkAbort();
      // Verify (read back + compare) MUST run here, while still in DFU mode.
      // leave() below reboots the board out of the bootloader — the device
      // disconnects, so a post-leave read-back is impossible.
      if (options?.verify !== false) {
        await this.verifyWritten(firmware, onProgress, onLog);
        this.checkAbort();
      }
      onProgress({ phase: "restarting", percent: 95, message: "Leaving DFU mode..." });
      await this.leave(firmware.blocks[0]?.address ?? 0x08000000);
      onProgress({ phase: "done", percent: 100, message: "Flash complete!" });
    } finally { await this.releaseDevice(); }
  }

  /**
   * Read the written firmware back and compare it, in-place, before leave().
   * A byte mismatch is a hard failure. A transfer-level read-back error (some
   * STM32 bootloaders reject DFU_UPLOAD under readout protection) is downgraded
   * to a warning: dfuWriteBlocks already confirmed each block via getStatus
   * polling during download, so an un-readable-back board must not turn an
   * otherwise-good flash into a failure.
   */
  private async verifyWritten(firmware: ParsedFirmware, onProgress: FlashProgressCallback, onLog?: FlashLogCallback): Promise<void> {
    onProgress({ phase: "verifying", percent: 78, message: "Verifying firmware..." });
    try {
      await this.abortToIdle();
      await dfuVerifyBlocks(this.flashCtx, firmware, onProgress);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (this.aborted || msg.includes("Verification failed at") || msg.includes("aborted")) throw err;
      onLog?.("warning", `read-back verification unavailable (${msg}); write confirmed by bootloader`);
    }
  }

  abort(): void { this.aborted = true; }
  async dispose(): Promise<void> { await this.releaseDevice(); }

  // ── USB Device Management ──────────────────────────────

  private async openAndClaim(): Promise<void> {
    if (!this.device.opened) await this.device.open();
    if (this.device.configuration === null) await this.device.selectConfiguration(1);
    const iface = this.device.configuration?.interfaces.find((i) => i.alternates.some((a) => a.interfaceClass === 0xfe && a.interfaceSubclass === 0x01));
    if (!iface) throw new Error("No DFU interface found on this USB device");
    this.interfaceNumber = iface.interfaceNumber;
    await this.device.claimInterface(this.interfaceNumber);
    const flashAlt = iface.alternates.find((a) => a.interfaceClass === 0xfe && a.interfaceSubclass === 0x01 && (a.interfaceName?.includes("Flash") || a.interfaceName?.includes("@Internal")))
      ?? iface.alternates.find((a) => a.interfaceClass === 0xfe && a.interfaceSubclass === 0x01);
    if (flashAlt) await this.device.selectAlternateInterface(this.interfaceNumber, flashAlt.alternateSetting);
  }

  private async releaseDevice(): Promise<void> {
    try { if (this.device.opened) { await this.device.releaseInterface(this.interfaceNumber).catch(() => {}); await this.device.close().catch(() => {}); } } catch { /* Ignore */ }
  }

  // ── DFU Protocol Operations ────────────────────────────

  private async getStatus(): Promise<{ status: number; pollTimeout: number; state: number }> {
    const r = await this.device.controlTransferIn({ requestType: "class", recipient: "interface", request: DFU_GETSTATUS, value: 0, index: this.interfaceNumber }, 6);
    if (!r.data || r.data.byteLength < 6) throw new Error("Invalid DFU_GETSTATUS response");
    return { status: r.data.getUint8(0), pollTimeout: r.data.getUint8(1) | (r.data.getUint8(2) << 8) | (r.data.getUint8(3) << 16), state: r.data.getUint8(4) };
  }

  private clrStatus(): Promise<USBOutTransferResult> {
    return this.device.controlTransferOut({ requestType: "class", recipient: "interface", request: DFU_CLRSTATUS, value: 0, index: this.interfaceNumber });
  }

  private async clearStatus(): Promise<void> {
    await this.clrStatus();
    for (let i = 0; i < 10; i++) {
      const s = await this.getStatus();
      if (s.state === DFU_STATE.dfuIDLE) return;
      if (s.state === DFU_STATE.dfuERROR) await this.clrStatus();
      await this.delay(s.pollTimeout || 100);
    }
    throw new Error("Failed to reach dfuIDLE state");
  }

  private async loadAddress(address: number): Promise<void> {
    const d = new Uint8Array([DFUSE_CMD_SET_ADDRESS, address & 0xff, (address >> 8) & 0xff, (address >> 16) & 0xff, (address >> 24) & 0xff]);
    await this.device.controlTransferOut({ requestType: "class", recipient: "interface", request: DFU_DNLOAD, value: 0, index: this.interfaceNumber }, d);
    await this.pollUntilIdle(DFU_TIMEOUT);
  }

  private async erasePage(address: number): Promise<void> {
    const d = new Uint8Array([DFUSE_CMD_ERASE, address & 0xff, (address >> 8) & 0xff, (address >> 16) & 0xff, (address >> 24) & 0xff]);
    await this.device.controlTransferOut({ requestType: "class", recipient: "interface", request: DFU_DNLOAD, value: 0, index: this.interfaceNumber }, d);
    await this.pollUntilIdle(ERASE_TIMEOUT);
  }

  private async massErase(onProgress: FlashProgressCallback): Promise<void> {
    onProgress({ phase: "erasing", percent: 15, message: "Mass erasing flash (descriptor unavailable)..." });
    await this.device.controlTransferOut({ requestType: "class", recipient: "interface", request: DFU_DNLOAD, value: 0, index: this.interfaceNumber }, new Uint8Array([DFUSE_CMD_ERASE]));
    await this.pollUntilIdle(ERASE_TIMEOUT);
  }

  private async writeBlock(blockNum: number, data: Uint8Array): Promise<void> {
    await this.device.controlTransferOut({ requestType: "class", recipient: "interface", request: DFU_DNLOAD, value: blockNum, index: this.interfaceNumber }, data);
    await this.pollUntilIdle(DFU_TIMEOUT);
  }

  private async readBlock(blockNum: number, length: number): Promise<Uint8Array> {
    const r = await this.device.controlTransferIn({ requestType: "class", recipient: "interface", request: DFU_UPLOAD, value: blockNum, index: this.interfaceNumber }, length);
    if (!r.data) throw new Error("No data in DFU_UPLOAD response");
    return new Uint8Array(r.data.buffer, r.data.byteOffset, r.data.byteLength);
  }

  private async leave(startAddress: number): Promise<void> {
    await this.loadAddress(startAddress);
    try {
      await this.device.controlTransferOut({ requestType: "class", recipient: "interface", request: DFU_DNLOAD, value: 0, index: this.interfaceNumber });
      await this.getStatus().catch(() => {});
    } catch { /* Expected — device resets */ }
  }

  private dfuAbort(): Promise<USBOutTransferResult> {
    return this.device.controlTransferOut({ requestType: "class", recipient: "interface", request: DFU_ABORT, value: 0, index: this.interfaceNumber });
  }

  /**
   * Return the device to dfuIDLE so DFU_UPLOAD (read-back) is accepted. After a
   * download the device sits in dfuDNLOAD_IDLE; DFU_ABORT is the spec-correct
   * transition dfuDNLOAD_IDLE -> dfuIDLE. Clears an error state if one is seen.
   */
  private async abortToIdle(): Promise<void> {
    await this.dfuAbort();
    for (let i = 0; i < 10; i++) {
      const s = await this.getStatus();
      if (s.state === DFU_STATE.dfuIDLE) return;
      if (s.state === DFU_STATE.dfuERROR) await this.clrStatus();
      await this.delay(s.pollTimeout || 50);
    }
    throw new Error("Failed to reach dfuIDLE for read-back");
  }

  private async pollUntilIdle(timeoutMs: number): Promise<void> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const s = await this.getStatus();
      if (s.state === DFU_STATE.dfuDNLOAD_IDLE || s.state === DFU_STATE.dfuIDLE) return;
      if (s.state === DFU_STATE.dfuERROR) {
        await this.clrStatus();
        const r = await this.getStatus();
        if (r.state === DFU_STATE.dfuIDLE || r.state === DFU_STATE.dfuDNLOAD_IDLE) return;
        throw new Error(`DFU error state: ${DFU_STATE_NAME[s.state] ?? `unknown(${s.state})`}, status: ${s.status}`);
      }
      await this.delay(Math.min(Math.max(s.pollTimeout, 50), 5000));
    }
    // H743 Rev.V workaround
    try {
      const s = await this.getStatus();
      if (s.state === DFU_STATE.dfuDNBUSY || s.state === DFU_STATE.dfuDNLOAD_SYNC) {
        await this.clrStatus(); await this.getStatus(); await this.clrStatus();
        const r = await this.getStatus();
        if (r.state === DFU_STATE.dfuIDLE || r.state === DFU_STATE.dfuDNLOAD_IDLE) return;
      }
    } catch { /* Recovery failed */ }
    throw new Error("DFU poll timeout");
  }

  private checkAbort(): void { if (this.aborted) throw new Error("Flash aborted by user"); }
  private delay(ms: number): Promise<void> { return new Promise((r) => setTimeout(r, ms)); }
}
