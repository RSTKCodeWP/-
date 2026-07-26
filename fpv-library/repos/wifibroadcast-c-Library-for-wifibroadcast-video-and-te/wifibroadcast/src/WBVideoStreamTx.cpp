//
// Created by consti10 on 06.01.24.
//

#include "WBVideoStreamTx.h"

#include "BlockSizeHelper.hpp"
#include "SchedulingHelper.hpp"

struct CodecConfigPacket {
  uint8_t codec_type;
  uint16_t config_data_len;
  // config_data_len bytes follow
};

WBVideoStreamTx::WBVideoStreamTx(
    std::shared_ptr<WBTxRx> txrx, WBVideoStreamTx::Options options1,
    std::shared_ptr<RadiotapHeaderTxHolder> radiotap_header_holder)
    : options(options1),
      m_txrx(txrx),
      m_radiotap_header_holder(std::move(radiotap_header_holder)) {
  assert(m_txrx);
  if (options.opt_console) {
    m_console = options.opt_console;
  } else {
    m_console = wifibroadcast::log::create_or_get(
        "wb_tx" + std::to_string(options.radio_port));
  }
  assert(m_console);
  m_block_queue = std::make_unique<FrameQueueType>(options.frame_queue_size);
  m_fec_encoder = std::make_unique<FECEncoder>();
  auto cb = [this](const uint8_t* packet, int packet_len) {
    send_packet(packet, packet_len);
  };
  m_fec_encoder->m_out_cb = cb;
  m_process_data_thread_run = true;
  m_process_data_thread =
      std::make_unique<std::thread>(&WBVideoStreamTx::loop_process_data, this);
}

WBVideoStreamTx::~WBVideoStreamTx() {
  m_process_data_thread_run = false;
  if (m_process_data_thread && m_process_data_thread->joinable()) {
    m_process_data_thread->join();
  }
}

void WBVideoStreamTx::set_config_data(
    uint8_t codec_type, std::shared_ptr<std::vector<uint8_t>> config_buff) {
  auto config = std::make_shared<CodecConfigData>();
  config->codec_type = codec_type;
  config->config_buff = config_buff;
  std::lock_guard<std::mutex> guard(m_codec_config_mutex);
  m_codec_config = config;
}

bool WBVideoStreamTx::enqueue_frame(
    std::shared_ptr<std::vector<uint8_t>> frame, int max_block_size,
    int fec_overhead_perc,
    std::chrono::steady_clock::time_point creation_time) {
  auto item = std::make_shared<EnqueuedFrame>();
  item->frame = frame;
  item->max_block_size = max_block_size;
  item->fec_overhead_perc = fec_overhead_perc;
  item->creation_time = creation_time;
  const bool res = m_block_queue->try_enqueue(item);
  return res;
}

void WBVideoStreamTx::loop_process_data() {
  if (options.dequeue_thread_max_realtime) {
    SchedulingHelper::set_thread_params_max_realtime("WBVideoStreamTx::loop");
  }
  std::chrono::steady_clock::time_point last_config =
      std::chrono::steady_clock::now();
  while (m_process_data_thread_run) {
    auto opt_frame =
        m_block_queue->wait_dequeue_timed(std::chrono::milliseconds(100));
    if (opt_frame.has_value()) {
      auto frame = opt_frame.value();
      process_enqueued_frame(*frame);
    }
    const auto now = std::chrono::steady_clock::now();
    if (now - last_config >= options.codec_config_interval) {
      if (send_video_config()) {
        last_config = now;
      }
    }
  }
}

void WBVideoStreamTx::process_enqueued_frame(const EnqueuedFrame& enq_frame) {
  // TODO: Figure out the ideal fragment size for this frame
  const int n_primary_fragments =
      blocksize::div_ceil(enq_frame.frame->size(), FEC_PACKET_MAX_PAYLOAD_SIZE);
  const int n_secondary_fragments = calculate_n_secondary_fragments(
      n_primary_fragments, enq_frame.fec_overhead_perc);
  m_fec_encoder->fragment_and_encode(
      enq_frame.frame->data(), enq_frame.frame->size(), n_primary_fragments,
      n_secondary_fragments);
}

void WBVideoStreamTx::send_packet(const uint8_t* packet, int packet_len) {
  const auto radiotap_header = m_radiotap_header_holder->thread_safe_get();
  const bool encrypt = m_enable_encryption.load();
  m_txrx->tx_inject_packet(options.radio_port, packet, packet_len,
                           radiotap_header, encrypt);
}

bool WBVideoStreamTx::send_video_config() {
  std::lock_guard<std::mutex> guard(m_codec_config_mutex);
  if (m_codec_config == nullptr) return false;
  auto& config_buff = *m_codec_config->config_buff;
  assert(!config_buff.empty() && config_buff.size() < MAX_PAYLOAD_BEFORE_FEC);
  m_fec_encoder->fragment_and_encode(config_buff.data(), config_buff.size(), 1,
                                     0);
  return true;
}
