#pragma once
// =============================================================================
//  comms.h — ESP-NOW abstraction layer
//
//  All ESP-NOW send/receive is handled here.
//  Receive callbacks enqueue packets into FreeRTOS queues consumed by Core 0.
//
//  Peers:
//    PEER_OWN_RC   — our paired remote controller
//    PEER_OPP_CAR  — opponent's car ESP32
//    PEER_OPP_RC   — opponent's remote controller
//
//  During pairing these MACs are unknown — comms_pair_*() resolves them.
// =============================================================================

#include "types.h"
#include <stdint.h>
#include <stddef.h>

// Peer indices
#define PEER_OWN_RC   0
#define PEER_OPP_CAR  1
#define PEER_OPP_RC   2
#define PEER_COUNT    3

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

// Call once. Starts ESP-NOW, registers send/receive callbacks.
// ownMac[] is filled with this device's MAC address.
void comms_init(uint8_t* ownMacOut);

// Register a known peer MAC at the given peer index
void comms_add_peer(uint8_t peerIdx, const uint8_t* mac);

// Broadcast to ALL registered peers
void comms_broadcast(const void* data, size_t len);

// Send to a specific peer (PEER_OWN_RC, PEER_OPP_CAR, PEER_OPP_RC)
void comms_send(uint8_t peerIdx, const void* data, size_t len);

// ---------------------------------------------------------------------------
// Receive queue
// ---------------------------------------------------------------------------

// Max raw packet size that can be enqueued
#define COMMS_PKT_MAX 250

struct IncomingPacket {
    uint8_t  senderMac[6];
    uint8_t  data[COMMS_PKT_MAX];
    uint8_t  len;
};

// Returns true and fills pkt if a packet is available (non-blocking).
// Call from Core 0 game loop.
bool comms_recv(IncomingPacket* pkt);

// ---------------------------------------------------------------------------
// Heartbeat tracking
// ---------------------------------------------------------------------------

// Called by Core 0 every loop. Updates last-seen timestamps per peer.
void comms_heartbeat_update(uint8_t peerIdx);

// Returns true if peer has been silent for > thresholdMs
bool comms_peer_lost(uint8_t peerIdx, uint32_t thresholdMs);

// ---------------------------------------------------------------------------
// Pairing helpers (used during CONNECTING phase)
// ---------------------------------------------------------------------------

// Start broadcasting PKT_RACE_LOOKING every 500ms (non-blocking, uses timer)
void comms_start_looking();

// Stop the broadcast timer
void comms_stop_looking();

// Returns true if a PKT_RACE_LOOKING was received from an unknown peer.
// Fills senderMac with that peer's address.
bool comms_got_looking(uint8_t* senderMacOut);

// Send PKT_RACE_ACCEPT to the given MAC.
// This triggers the receiver to finalize the peer group.
void comms_send_accept(const uint8_t* targetMac);
