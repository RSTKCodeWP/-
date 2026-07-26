// =============================================================================
//  comms.cpp — ESP-NOW abstraction layer (Car firmware)
//
//  This is the file that was marked "you write this" in the README.
//  It is now fully written and ready to use.
//
//  How it works:
//    - comms_init()  starts WiFi STA + ESP-NOW, registers ISR callbacks
//    - All received packets are dropped into a FreeRTOS queue (xRxQueue)
//      which main.cpp drains every loop tick via comms_recv()
//    - comms_start_looking() fires a FreeRTOS timer that broadcasts
//      PKT_RACE_LOOKING every 500ms until comms_stop_looking() is called
//    - Heartbeat timestamps are updated by comms_heartbeat_update() and
//      checked by comms_peer_lost() in host_tick()
// =============================================================================

#include "comms.h"
#include "types.h"
#include <WiFi.h>
#include <esp_now.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/timers.h>
#include <string.h>
#include <Arduino.h>

// ---------------------------------------------------------------------------
// Internal state
// ---------------------------------------------------------------------------

// Receive queue — filled by ISR, drained by Core 0 loop
// Declared extern in main.cpp — defined here
QueueHandle_t xRxQueue = nullptr;
#define RX_QUEUE_DEPTH  32

// Peer MAC address table
static uint8_t s_peerMac[PEER_COUNT][6] = {};
static bool    s_peerAdded[PEER_COUNT]  = {};

// Heartbeat timestamps
static volatile uint32_t s_lastSeen[PEER_COUNT] = {};

// Pairing state
static volatile bool    s_looking       = false;
static volatile bool    s_gotLooking    = false;
static uint8_t          s_lookingMac[6] = {};
static TimerHandle_t    s_lookTimer     = nullptr;

// Broadcast MAC
static const uint8_t BCAST_MAC[6] = {0xFF,0xFF,0xFF,0xFF,0xFF,0xFF};

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

static void add_peer_mac(const uint8_t* mac) {
    if (esp_now_is_peer_exist(mac)) return;
    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, mac, 6);
    peer.channel = 0;
    peer.encrypt = false;
    esp_now_add_peer(&peer);
}

// ---------------------------------------------------------------------------
// ESP-NOW receive callback (runs in WiFi task / ISR context — keep SHORT)
// ---------------------------------------------------------------------------
static void on_data_recv(const uint8_t* mac, const uint8_t* data, int len) {
    if (!xRxQueue) return;

    IncomingPacket pkt;
    memcpy(pkt.senderMac, mac, 6);
    pkt.len = (len > COMMS_PKT_MAX) ? COMMS_PKT_MAX : (uint8_t)len;
    memcpy(pkt.data, data, pkt.len);

    // Check if this is a RACE_LOOKING packet from unknown peer
    if (pkt.len >= 1 && pkt.data[0] == PKT_RACE_LOOKING && s_looking) {
        memcpy(s_lookingMac, mac, 6);
        s_gotLooking = true;
    }

    // Always enqueue — main.cpp dispatch handles all logic
    BaseType_t woken = pdFALSE;
    xQueueSendFromISR(xRxQueue, &pkt, &woken);
    if (woken) portYIELD_FROM_ISR();
}

// ESP-NOW send callback (optional — used for debug)
static void on_data_sent(const uint8_t* mac, esp_now_send_status_t status) {
    // Uncomment for debug:
    // if (status != ESP_NOW_SEND_SUCCESS)
    //     Serial.printf("[COMMS] Send FAILED to %02X:%02X:%02X:%02X:%02X:%02X\n",
    //                   mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
}

// ---------------------------------------------------------------------------
// Looking timer callback — fires every 500ms while s_looking == true
// ---------------------------------------------------------------------------
static void looking_timer_cb(TimerHandle_t xTimer) {
    if (!s_looking) return;

    // Build PKT_RACE_LOOKING packet
    PktHeader pkt;
    pkt.type   = PKT_RACE_LOOKING;
    pkt.sender = CAR_ID;
    pkt.ts     = (uint32_t)millis();
    esp_now_send(BCAST_MAC, (const uint8_t*)&pkt, sizeof(pkt));
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

void comms_init(uint8_t* ownMacOut) {
    // Create receive queue
    xRxQueue = xQueueCreate(RX_QUEUE_DEPTH, sizeof(IncomingPacket));
    configASSERT(xRxQueue);

    // Start WiFi in station mode (required for ESP-NOW)
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();      // make sure not connected to any AP
    WiFi.macAddress(ownMacOut);

    Serial.printf("[COMMS] MAC: %02X:%02X:%02X:%02X:%02X:%02X\n",
                  ownMacOut[0], ownMacOut[1], ownMacOut[2],
                  ownMacOut[3], ownMacOut[4], ownMacOut[5]);

    // Init ESP-NOW
    if (esp_now_init() != ESP_OK) {
        Serial.println("[COMMS] ESP-NOW init FAILED — restarting");
        ESP.restart();
    }

    esp_now_register_recv_cb(on_data_recv);
    esp_now_register_send_cb(on_data_sent);

    // Add broadcast peer so we can always broadcast
    add_peer_mac(BCAST_MAC);

    // Create looking timer (500ms, auto-reload)
    s_lookTimer = xTimerCreate("looking", pdMS_TO_TICKS(500),
                               pdTRUE, nullptr, looking_timer_cb);

    Serial.println("[COMMS] ESP-NOW ready");
}

void comms_add_peer(uint8_t peerIdx, const uint8_t* mac) {
    if (peerIdx >= PEER_COUNT) return;
    memcpy(s_peerMac[peerIdx], mac, 6);
    s_peerAdded[peerIdx] = true;
    add_peer_mac(mac);
    Serial.printf("[COMMS] Peer %d added: %02X:%02X:%02X:%02X:%02X:%02X\n",
                  peerIdx, mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
}

void comms_send(uint8_t peerIdx, const void* data, size_t len) {
    if (peerIdx >= PEER_COUNT || !s_peerAdded[peerIdx]) return;
    esp_now_send(s_peerMac[peerIdx], (const uint8_t*)data, len);
}

void comms_broadcast(const void* data, size_t len) {
    esp_now_send(BCAST_MAC, (const uint8_t*)data, len);
}

bool comms_recv(IncomingPacket* pkt) {
    if (!xRxQueue) return false;
    return xQueueReceive(xRxQueue, pkt, 0) == pdTRUE;
}

void comms_heartbeat_update(uint8_t peerIdx) {
    if (peerIdx < PEER_COUNT) s_lastSeen[peerIdx] = millis();
}

bool comms_peer_lost(uint8_t peerIdx, uint32_t thresholdMs) {
    if (peerIdx >= PEER_COUNT) return false;
    if (s_lastSeen[peerIdx] == 0) return false;   // never seen — not lost yet
    return (millis() - s_lastSeen[peerIdx]) > thresholdMs;
}

void comms_start_looking() {
    s_looking    = true;
    s_gotLooking = false;
    if (s_lookTimer) xTimerStart(s_lookTimer, 0);
    Serial.println("[COMMS] Looking for peer...");
}

void comms_stop_looking() {
    s_looking = false;
    if (s_lookTimer) xTimerStop(s_lookTimer, 0);
    Serial.println("[COMMS] Stopped looking");
}

bool comms_got_looking(uint8_t* senderMacOut) {
    if (!s_gotLooking) return false;
    memcpy(senderMacOut, s_lookingMac, 6);
    s_gotLooking = false;
    return true;
}

void comms_send_accept(const uint8_t* targetMac) {
    add_peer_mac(targetMac);   // make sure they're a peer first
    PktHeader pkt;
    pkt.type   = PKT_RACE_ACCEPT;
    pkt.sender = CAR_ID;
    pkt.ts     = (uint32_t)millis();
    esp_now_send(targetMac, (const uint8_t*)&pkt, sizeof(pkt));
    Serial.printf("[COMMS] ACCEPT sent to %02X:%02X:%02X:%02X:%02X:%02X\n",
                  targetMac[0],targetMac[1],targetMac[2],
                  targetMac[3],targetMac[4],targetMac[5]);
}
