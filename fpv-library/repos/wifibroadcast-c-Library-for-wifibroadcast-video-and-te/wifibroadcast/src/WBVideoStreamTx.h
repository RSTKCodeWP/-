//
// Created by consti10 on 06.01.24.
//

#ifndef WIFIBROADCAST_WBVIDEOSTREAMTX_H
#define WIFIBROADCAST_WBVIDEOSTREAMTX_H

#include <queue>
#include <thread>
#include <variant>

#include "../fec/FEC.h"
#include "../fec/FECEncoder.h"
#include "FunkyQueue.h"
#include "SimpleStream.hpp"
#include "TimeHelper.hpp"
#include "WBTxRx.h"

class WBVideoStreamTx {
 public:
  struct Options {
    // needs to match the radio port of the corresponding rx
    uint8_t radio_port = 0;
    int frame_queue_size = 2;
    // overwrite the console used for logging
    std::shared_ptr<spdlog::logger> opt_console = nullptr;
    // set sched_param = max realtime on the thread that dequeues and injects
    // the packets
    bool dequeue_thread_max_realtime = true;
    std::chrono::milliseconds codec_config_interval = std::chrono::seconds(1);
  };
  WBVideoStreamTx(
      std::shared_ptr<WBTxRx> txrx, Options options,
      std::shared_ptr<RadiotapHeaderTxHolder> radiotap_header_holder);
  WBVideoStreamTx(const WBVideoStreamTx&) = delete;
  WBVideoStreamTx& operator=(const WBVideoStreamTx&) = delete;
  ~WBVideoStreamTx();
  void set_config_data(uint8_t codec_type,
                       std::shared_ptr<std::vector<uint8_t>> config_buff);
  bool enqueue_frame(std::shared_ptr<std::vector<uint8_t>> frame,
                     int max_block_size, int fec_overhead_perc,
                     std::chrono::steady_clock::time_point creation_time =
                         std::chrono::steady_clock::now());
  std::atomic_int32_t in_fps = 0;
  std::atomic_int32_t in_bps = 0;
  std::atomic_int32_t out_pps = 0;

 private:
  struct EnqueuedFrame {
    std::chrono::steady_clock::time_point enqueue_time_point =
        std::chrono::steady_clock::now();
    std::chrono::steady_clock::time_point creation_time =
        std::chrono::steady_clock::now();
    int max_block_size;
    int fec_overhead_perc;
    std::shared_ptr<std::vector<uint8_t>> frame = nullptr;
  };
  struct CodecConfigData {
    uint8_t codec_type;
    std::shared_ptr<std::vector<uint8_t>> config_buff = nullptr;
  };

 private:
  const Options options;
  std::shared_ptr<WBTxRx> m_txrx;
  std::shared_ptr<RadiotapHeaderTxHolder> m_radiotap_header_holder;
  std::shared_ptr<spdlog::logger> m_console;
  // On the tx, either one of those two is active at the same time
  std::unique_ptr<FECEncoder> m_fec_encoder = nullptr;
  std::unique_ptr<std::thread> m_process_data_thread;
  using FrameQueueType = FunkyQueue<std::shared_ptr<EnqueuedFrame>>;
  std::unique_ptr<FrameQueueType> m_block_queue;
  bool m_process_data_thread_run = true;
  void loop_process_data();
  void process_enqueued_frame(const EnqueuedFrame& enq_frame);
  void send_packet(const uint8_t* packet, int packet_len);
  bool send_video_config();
  std::shared_ptr<CodecConfigData> m_codec_config = nullptr;
  std::mutex m_codec_config_mutex;
  std::atomic<bool> m_enable_encryption = true;
};

#endif  // WIFIBROADCAST_WBVIDEOSTREAMTX_H
