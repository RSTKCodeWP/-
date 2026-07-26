/******************************************************************************
 * OpenHD
 *
 * Licensed under the GNU General Public License (GPL) Version 3.
 *
 * This software is provided "as-is," without warranty of any kind, express or
 * implied, including but not limited to the warranties of merchantability,
 * fitness for a particular purpose, and non-infringement. For details, see the
 * full license in the LICENSE file provided with this source code.
 *
 * Non-Military Use Only:
 * This software and its associated components are explicitly intended for
 * civilian and non-military purposes. Use in any military or defense
 * applications is strictly prohibited unless explicitly and individually
 * licensed otherwise by the OpenHD Team.
 *
 * Contributors:
 * A full list of contributors can be found at the OpenHD GitHub repository:
 * https://github.com/OpenHD
 *
 * © OpenHD, All Rights Reserved.
 ******************************************************************************/

#include "WBEndpoint.h"

#include <utility>

#include "openhd_spdlog_include.h"

WBEndpoint::WBEndpoint(std::shared_ptr<OHDLink> link, std::string TAG)
    : MEndpoint(std::move(TAG)), m_link_handle(std::move(link)) {
  // assert(m_tx_rx_handle);
  if (!m_link_handle) {
    openhd::log::get_default()->warn(
        "WBEndpoint-tx rx handle is missing (no telemetry connection between "
        "air and ground)");
  } else {
    auto cb = [this](std::shared_ptr<std::vector<uint8_t>> data) {
      MEndpoint::parseNewData(data->data(), data->size());
    };
    m_link_handle->register_on_receive_telemetry_data_cb(cb);
  }
}

WBEndpoint::~WBEndpoint() {
  if (m_link_handle) {
    m_link_handle->register_on_receive_telemetry_data_cb(nullptr);
  }
}

bool WBEndpoint::sendMessagesImpl(const std::vector<MavlinkMessage>& messages) {
  std::vector<MavlinkMessage> rc_messages;
  std::vector<MavlinkMessage> telemetry_messages;
  rc_messages.reserve(messages.size());
  telemetry_messages.reserve(messages.size());
  for (const auto& message : messages) {
    if (is_rc_message(message)) {
      rc_messages.push_back(message);
    } else {
      telemetry_messages.push_back(message);
    }
  }

  const auto send_packets = [this](const std::vector<MavlinkMessage>& msgs,
                                   OHDLink::TelemetryPacketType packet_type) {
    auto message_buffers = aggregate_pack_messages(msgs);
    for (const auto& message_buffer : message_buffers) {
      if (m_link_handle) {
        std::lock_guard<std::mutex> guard(m_send_messages_mutex);
        OHDLink::TelemetryTxPacket packet;
        packet.data = message_buffer.aggregated_data;
        packet.n_injections = message_buffer.recommended_n_retransmissions;
        packet.packet_type = packet_type;
        m_link_handle->transmit_telemetry_data(packet);
      }
    }
  };

  if (!rc_messages.empty()) {
    send_packets(rc_messages, OHDLink::TelemetryPacketType::RC);
  }
  if (!telemetry_messages.empty()) {
    send_packets(telemetry_messages, OHDLink::TelemetryPacketType::Telemetry);
  }
  return true;
}
