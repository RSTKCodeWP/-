/// <reference types="leaflet" />
/// <reference types="node" />
import type * as LeafletTypes from 'leaflet';
declare global {
  const L: typeof LeafletTypes;
  namespace L {
    export type Map = LeafletTypes.Map;
    export type TileLayer = LeafletTypes.TileLayer;
    export type Marker = LeafletTypes.Marker;
    export type Polyline = LeafletTypes.Polyline;
    export type Polygon = LeafletTypes.Polygon;
    export type Circle = LeafletTypes.Circle;
    export type CircleMarker = LeafletTypes.CircleMarker;
    export type Layer = LeafletTypes.Layer;
    export type Popup = LeafletTypes.Popup;
    export type LatLng = LeafletTypes.LatLng;
    export type LeafletMouseEvent = LeafletTypes.LeafletMouseEvent;
    export type LeafletEvent = LeafletTypes.LeafletEvent;
  }
  const __BUILD_DATE__: string;

  interface SerialPortFilter {
    usbVendorId?: number;
    usbProductId?: number;
  }

  interface SerialPortInfo {
    usbVendorId?: number;
    usbProductId?: number;
  }

  interface SerialPort {
    open(options: { baudRate: number; bufferSize?: number }): Promise<void>;
    close(): Promise<void>;
    readable: ReadableStream<Uint8Array>;
    writable: WritableStream<Uint8Array>;
    getInfo(): SerialPortInfo;
  }

  interface Serial {
    requestPort(options?: { filters?: SerialPortFilter[] }): Promise<SerialPort>;
    getPorts(): Promise<SerialPort[]>;
  }

  interface Navigator {
    serial?: Serial;
  }
}
