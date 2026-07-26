import { query } from "./_generated/server";

export const getClientConfig = query({
  args: {},
  handler: async () => {
    const rawLimit = process.env.AI_PID_WEEKLY_LIMIT;
    const parsed = rawLimit ? parseInt(rawLimit, 10) : NaN;
    return {
      cesiumIonToken: process.env.CESIUM_ION_TOKEN ?? null,
      aiPidWeeklyLimit: Number.isFinite(parsed) && parsed > 0 ? parsed : 3,
      mqttBrokerUrl: process.env.MQTT_BROKER_URL ?? null,
      // Read-only viewer credential for the in-browser MQTT subscriber.
      // The broker enforces `topic read ados/+/#` on this user; it cannot
      // publish. The password is shared across browser sessions; protect
      // beyond that via broker TLS + Cloudflare Tunnel.
      mqttViewerUsername: process.env.MQTT_VIEWER_USERNAME ?? "gcs-viewer",
      mqttViewerPassword: process.env.MQTT_VIEWER_PASSWORD ?? null,
      videoRelayUrl: process.env.VIDEO_RELAY_URL ?? null,
    };
  },
});
