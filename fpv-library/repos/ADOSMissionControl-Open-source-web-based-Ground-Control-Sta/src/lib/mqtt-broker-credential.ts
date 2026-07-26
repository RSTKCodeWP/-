/**
 * @module mqtt-broker-credential
 * @description Process-level singleton for the read-only MQTT broker
 * credential used by every in-browser MQTT client (MqttBridge,
 * CommandFleetMqttBridge, MqttMavlinkTransport, WebRTC signaling).
 *
 * The production broker enforces auth via the `gcs-viewer` username
 * + password published by Convex `clientConfig.getClientConfig`. A
 * bootstrap component (CommandShell) populates this singleton once
 * the public client config is available; transports then read it at
 * connect time without any prop drilling.
 *
 * On bench / OSS self-hosters with anonymous brokers, the credential
 * stays null and connect() falls back to anonymous.
 * @license GPL-3.0-only
 */

import { OFFICIAL_MQTT_WS_URL } from "@/lib/config/endpoints";

interface MqttBrokerCredential {
  username: string;
  password: string;
}

let current: MqttBrokerCredential | null = null;
let brokerUrl: string | null = null;

/**
 * Set or clear the broker credential. Pass `null` (or an object with
 * missing username/password) to clear.
 */
export function setMqttBrokerCredential(
  next: { username?: string | null; password?: string | null } | null,
): void {
  if (next?.username && next?.password) {
    current = { username: next.username, password: next.password };
  } else {
    current = null;
  }
}

/**
 * Read the current broker credential. Returns `null` when no auth is
 * configured (bench / anonymous broker).
 */
export function getMqttBrokerCredential(): MqttBrokerCredential | null {
  return current;
}

/**
 * Set or clear the broker WebSocket URL, resolved from
 * `clientConfig.mqttBrokerUrl`. Pass a falsy value to clear (fall back to
 * the managed default). CommandShell populates this once the public client
 * config is available, alongside the credential.
 */
export function setMqttBrokerUrl(url: string | null | undefined): void {
  brokerUrl = url && url.length > 0 ? url : null;
}

/**
 * Read the broker WebSocket URL every in-browser MQTT client should dial:
 * the `clientConfig`-resolved URL when set, otherwise the managed default.
 * This is the single resolution point that lets a self-hosted deployment
 * point telemetry AND WebRTC signaling at its own broker.
 */
export function getMqttBrokerUrl(): string {
  return brokerUrl ?? OFFICIAL_MQTT_WS_URL;
}
