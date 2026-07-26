#ifndef WEBHOOK_H
#define WEBHOOK_H

#include <Arduino.h>
#include <vector>

#define MAX_WEBHOOKS 10
#define WEBHOOK_TIMEOUT_MS 300  // Reduced timeout
#define WEBHOOK_QUEUE_SIZE 10   // Max pending webhook requests

struct WebhookRequest {
    char endpoint[32];  // Fixed size to avoid String allocation
    uint32_t timestamp;
};

class WebhookManager {
   public:
    WebhookManager();
    
    // Add/remove webhook IPs - use const char* to avoid String copies
    bool addWebhook(const char* ip);
    bool removeWebhook(const char* ip);
    void clearWebhooks();
    uint8_t getWebhookCount() const;
    const char* getWebhookIP(uint8_t index) const;
    
    // Trigger webhook events (queued, truly non-blocking)
    void triggerLap();
    void triggerGhostLap();
    void triggerRaceStart();
    void triggerRaceStop();
    void triggerOff();
    void triggerFlash();
    
    // Process queued webhooks (call from main loop)
    void process();
    
    // Enable/disable webhooks
    void setEnabled(bool enabled);
    bool isEnabled() const;
    
   private:
    char webhookIPs[MAX_WEBHOOKS][16];  // Fixed-size IP storage (xxx.xxx.xxx.xxx\0)
    uint8_t webhookCount;
    bool enabled;
    
    // Queue for webhook requests
    WebhookRequest requestQueue[WEBHOOK_QUEUE_SIZE];
    uint8_t queueHead;
    uint8_t queueTail;
    uint8_t queueCount;
    
    // Rate limiting
    uint32_t lastWebhookMs;
    
    // Queue a webhook request
    void queueRequest(const char* endpoint);
    
    // Process one queued request
    void processNextRequest();
    
    // Send to all IPs (called from process loop)
    void sendToAll(const char* endpoint);
    
    // Send to specific IP
    void sendWebhook(const char* ip, const char* endpoint);
};

#endif // WEBHOOK_H
