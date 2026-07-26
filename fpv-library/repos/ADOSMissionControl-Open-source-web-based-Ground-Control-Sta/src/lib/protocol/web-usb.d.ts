/**
 * WebUSB API type declarations.
 * These types are not included in standard TypeScript lib definitions.
 */

type USBDirection = "in" | "out";
type USBEndpointType = "bulk" | "interrupt" | "isochronous";
type USBRequestType = "standard" | "class" | "vendor";
type USBRecipient = "device" | "interface" | "endpoint" | "other";
type USBTransferStatus = "ok" | "stall" | "babble";

interface USBDeviceFilter {
  vendorId?: number;
  productId?: number;
  classCode?: number;
  subclassCode?: number;
  protocolCode?: number;
  serialNumber?: string;
}

interface USBDeviceRequestOptions {
  filters: USBDeviceFilter[];
}

interface USBControlTransferParameters {
  requestType: USBRequestType;
  recipient: USBRecipient;
  request: number;
  value: number;
  index: number;
}

interface USBInTransferResult {
  data: DataView | null;
  status: USBTransferStatus;
}

interface USBOutTransferResult {
  bytesWritten: number;
  status: USBTransferStatus;
}

interface USBEndpoint {
  endpointNumber: number;
  direction: USBDirection;
  type: USBEndpointType;
  packetSize: number;
}

interface USBAlternateInterface {
  alternateSetting: number;
  interfaceClass: number;
  interfaceSubclass: number;
  interfaceProtocol: number;
  interfaceName: string | null;
  endpoints: USBEndpoint[];
}

interface USBInterface {
  interfaceNumber: number;
  alternate: USBAlternateInterface;
  alternates: USBAlternateInterface[];
  claimed: boolean;
}

interface USBConfiguration {
  configurationValue: number;
  configurationName: string | null;
  interfaces: USBInterface[];
}

interface USBDevice {
  readonly usbVersionMajor: number;
  readonly usbVersionMinor: number;
  readonly usbVersionSubminor: number;
  readonly deviceClass: number;
  readonly deviceSubclass: number;
  readonly deviceProtocol: number;
  readonly vendorId: number;
  readonly productId: number;
  readonly deviceVersionMajor: number;
  readonly deviceVersionMinor: number;
  readonly deviceVersionSubminor: number;
  readonly manufacturerName: string | null;
  readonly productName: string | null;
  readonly serialNumber: string | null;
  readonly configuration: USBConfiguration | null;
  readonly configurations: USBConfiguration[];
  readonly opened: boolean;

  open(): Promise<void>;
  close(): Promise<void>;
  forget(): Promise<void>;
  selectConfiguration(configurationValue: number): Promise<void>;
  claimInterface(interfaceNumber: number): Promise<void>;
  releaseInterface(interfaceNumber: number): Promise<void>;
  selectAlternateInterface(interfaceNumber: number, alternateSetting: number): Promise<void>;
  controlTransferIn(setup: USBControlTransferParameters, length: number): Promise<USBInTransferResult>;
  controlTransferOut(setup: USBControlTransferParameters, data?: ArrayBuffer | ArrayBufferView | Uint8Array): Promise<USBOutTransferResult>;
  clearHalt(direction: USBDirection, endpointNumber: number): Promise<void>;
  transferIn(endpointNumber: number, length: number): Promise<USBInTransferResult>;
  transferOut(endpointNumber: number, data: BufferSource): Promise<USBOutTransferResult>;
  isochronousTransferIn(endpointNumber: number, packetLengths: number[]): Promise<USBInTransferResult>;
  isochronousTransferOut(endpointNumber: number, data: BufferSource, packetLengths: number[]): Promise<USBOutTransferResult>;
  reset(): Promise<void>;
}

interface USBConnectionEvent extends Event {
  readonly device: USBDevice;
}

interface USB extends EventTarget {
  onconnect: ((event: USBConnectionEvent) => void) | null;
  ondisconnect: ((event: USBConnectionEvent) => void) | null;
  getDevices(): Promise<USBDevice[]>;
  requestDevice(options: USBDeviceRequestOptions): Promise<USBDevice>;
}

interface Navigator {
  readonly usb: USB;
}
