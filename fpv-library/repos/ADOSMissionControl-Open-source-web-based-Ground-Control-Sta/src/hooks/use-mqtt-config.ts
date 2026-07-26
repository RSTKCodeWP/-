"use client";

/**
 * @module use-mqtt-config
 * @description State and connection-test logic for the MQTT broker config form
 * inside the System tab Fleet Network section. Encapsulates broker mode (cloud
 * vs self-hosted), credentials, TLS toggle, and async test state so the UI
 * component stays presentational.
 * @license GPL-3.0-only
 */

import { useCallback, useState } from "react";

import { OFFICIAL_MQTT_HOST } from "@/lib/config/endpoints";

export type MqttMode = "cloud" | "self-hosted";

export interface MqttConfig {
  mode: MqttMode;
  brokerUrl: string;
  username: string;
  password: string;
  tls: boolean;
}

export interface MqttTestResult {
  ok: boolean;
  message: string;
  at: number;
}

const DEFAULT_CONFIG: MqttConfig = {
  mode: "cloud",
  brokerUrl: OFFICIAL_MQTT_HOST,
  username: "",
  password: "",
  tls: true,
};

export interface UseMqttConfigResult {
  config: MqttConfig;
  setMode: (mode: MqttMode) => void;
  setBrokerUrl: (url: string) => void;
  setUsername: (user: string) => void;
  setPassword: (pwd: string) => void;
  setTls: (tls: boolean) => void;
  testConnection: () => Promise<void>;
  isTesting: boolean;
  lastResult: MqttTestResult | null;
}

/**
 * Manage MQTT broker configuration state and a stub connection-test action.
 * The test currently waits 2 seconds and reports success. Wire to a real
 * agent endpoint when broker probe is available.
 */
export function useMqttConfig(initial?: Partial<MqttConfig>): UseMqttConfigResult {
  const [config, setConfig] = useState<MqttConfig>({ ...DEFAULT_CONFIG, ...initial });
  const [isTesting, setIsTesting] = useState(false);
  const [lastResult, setLastResult] = useState<MqttTestResult | null>(null);

  const setMode = useCallback((mode: MqttMode) => {
    setConfig((prev) => ({ ...prev, mode }));
  }, []);

  const setBrokerUrl = useCallback((brokerUrl: string) => {
    setConfig((prev) => ({ ...prev, brokerUrl }));
  }, []);

  const setUsername = useCallback((username: string) => {
    setConfig((prev) => ({ ...prev, username }));
  }, []);

  const setPassword = useCallback((password: string) => {
    setConfig((prev) => ({ ...prev, password }));
  }, []);

  const setTls = useCallback((tls: boolean) => {
    setConfig((prev) => ({ ...prev, tls }));
  }, []);

  const testConnection = useCallback(async () => {
    setIsTesting(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      setLastResult({
        ok: true,
        message: "Connection test completed",
        at: Date.now(),
      });
    } finally {
      setIsTesting(false);
    }
  }, []);

  return {
    config,
    setMode,
    setBrokerUrl,
    setUsername,
    setPassword,
    setTls,
    testConnection,
    isTesting,
    lastResult,
  };
}
