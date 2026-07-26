//
// Created by consti10 on 02.02.24.
//

#ifndef WIFIBROADCAST_FUNKYQUEUE_H
#define WIFIBROADCAST_FUNKYQUEUE_H

#include <cassert>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <optional>
#include <queue>

/**
 * Thread-safe queue for the openhd use case where there is one producer thread
 * (encoder) and one consumer thread (link). Funky because the operations are a
 * bit funky (but make sense in this use case).
 */
template <class T>
class FunkyQueue {
 public:
  explicit FunkyQueue(int capacity) : m_capacity(capacity){};
  // Enqueues a new element. Return true on success, false otherwise
  bool try_enqueue(T element) {
    std::unique_lock<std::mutex> lk(mtx);
    if (queue.size() >= m_capacity) {
      return false;
    }
    queue.push(element);
    lk.unlock();
    cv.notify_one();
    return true;
  }
  // If there is enough space on the queue, enqueue the given element and return
  // 0; Otherwise, remove all elements currently in the queue, then enqueue the
  // given element, and return the n of removed elements
  int enqueue_or_clear_enqueue(T element) {
    std::unique_lock<std::mutex> lk(mtx);
    if (queue.size() >= m_capacity) {
      // Not enough space
      const int count_removed = queue.size();
      while (!queue.empty()) queue.pop();
      queue.push(element);
      lk.unlock();
      cv.notify_one();
      return count_removed;
    }
    // enough space
    queue.push(element);
    lk.unlock();
    cv.notify_one();
    return 0;
  }
  // Wait up to timeout until element is available.
  template <typename Rep, typename Period>
  std::optional<T> wait_dequeue_timed(
      std::chrono::duration<Rep, Period> const& timeout) {
    std::unique_lock<std::mutex> ul(mtx);
    if (!queue.empty()) {
      auto tmp = queue.front();
      queue.pop();
      return tmp;
    }
    const auto res =
        cv.wait_for(ul, timeout, [this]() { return !queue.empty(); });
    if (!res) {
      // Timeout
      return std::nullopt;
    }
    assert(!queue.empty());
    auto tmp = queue.front();
    queue.pop();
    return tmp;
  }
  int get_current_size() {
    std::unique_lock<std::mutex> ul(mtx);
    return queue.size();
  }

 private:
  const int m_capacity;
  std::queue<T> queue;
  std::mutex mtx;
  std::condition_variable cv;
};

#endif  // WIFIBROADCAST_FUNKYQUEUE_H
