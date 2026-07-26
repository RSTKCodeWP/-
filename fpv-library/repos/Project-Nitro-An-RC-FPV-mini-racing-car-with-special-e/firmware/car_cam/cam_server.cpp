// =============================================================================
//  FPV Racer v2.0 — ESP32-S3 Sense Camera Server
//
//  Board:   Seeed XIAO ESP32-S3 Sense  (OV2640 camera built-in)
//  What it does:
//    - Creates a WiFi Access Point: "FPV-CAR-1"
//    - Hosts a web page at 192.168.4.1
//    - Streams MJPEG camera feed in the browser
//    - Shows camera controls (brightness, contrast, flip, resolution)
//    - Completely standalone — no connection to game ESP32 needed
//
//  Library needed (add to platformio.ini):
//    espressif/esp32-camera @ ^2.0.4
// =============================================================================

#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"

// ---------------------------------------------------------------------------
// Config — change AP name per car
// ---------------------------------------------------------------------------
#define CAR_NUMBER    1           // change to 2 for second car
#define AP_PASSWORD   "fpvracer"  // WiFi password (min 8 chars)

// Derived AP name: FPV-CAR-1 or FPV-CAR-2
char AP_SSID[16];

// ---------------------------------------------------------------------------
// XIAO ESP32-S3 Sense camera pin definitions
// ---------------------------------------------------------------------------
#define PWDN_GPIO_NUM   -1
#define RESET_GPIO_NUM  -1
#define XCLK_GPIO_NUM   10
#define SIOD_GPIO_NUM   40
#define SIOC_GPIO_NUM   39
#define Y9_GPIO_NUM     48
#define Y8_GPIO_NUM     11
#define Y7_GPIO_NUM     12
#define Y6_GPIO_NUM     14
#define Y5_GPIO_NUM     16
#define Y4_GPIO_NUM     18
#define Y3_GPIO_NUM     17
#define Y2_GPIO_NUM     15
#define VSYNC_GPIO_NUM  38
#define HREF_GPIO_NUM   47
#define PCLK_GPIO_NUM   13

// ---------------------------------------------------------------------------
// Web page HTML — served at 192.168.4.1
// ---------------------------------------------------------------------------
static const char INDEX_HTML[] PROGMEM = R"rawhtml(
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FPV Camera</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0a0a0f; color: #cdd; font-family: 'Courier New', monospace; }
  .header { background: #06101a; border-bottom: 1px solid #1a3a5a; padding: 10px 16px;
            display: flex; align-items: center; justify-content: space-between; }
  .header h1 { font-size: 14px; letter-spacing: .1em; color: #00d4ff; text-transform: uppercase; }
  .badge { background: #0a2a0a; border: 1px solid #00cc44; border-radius: 4px;
           color: #00ff66; font-size: 10px; padding: 3px 8px; }
  .main { display: flex; gap: 12px; padding: 12px; flex-wrap: wrap; }
  .stream-box { flex: 1; min-width: 280px; }
  .stream-box img { width: 100%; border-radius: 6px; border: 1px solid #1a3a5a;
                    display: block; background: #000; min-height: 200px; }
  .controls { width: 220px; display: flex; flex-direction: column; gap: 8px; }
  .card { background: #0c1018; border: 1px solid #1a2a3a; border-radius: 6px; padding: 12px; }
  .card h3 { font-size: 10px; color: #446; letter-spacing: .1em; text-transform: uppercase;
             margin-bottom: 10px; }
  .row { display: flex; align-items: center; justify-content: space-between;
         margin-bottom: 8px; font-size: 12px; }
  .row label { color: #889; min-width: 80px; }
  .row input[type=range] { flex: 1; margin: 0 8px; accent-color: #00d4ff; }
  .row span { color: #00d4ff; min-width: 24px; text-align: right; font-size: 11px; }
  .btn-row { display: flex; gap: 6px; flex-wrap: wrap; }
  .btn { background: #0c1828; border: 1px solid #1a3a5a; border-radius: 4px;
         color: #aac; font-size: 11px; padding: 6px 10px; cursor: pointer;
         font-family: 'Courier New', monospace; text-transform: uppercase;
         letter-spacing: .05em; transition: all .15s; }
  .btn:hover { border-color: #00d4ff; color: #00d4ff; background: #061828; }
  .btn.active { background: #001828; border-color: #00d4ff; color: #00d4ff; }
  .btn.red { border-color: #442; color: #aa8; }
  .btn.red:hover { border-color: #ff4444; color: #ff6666; }
  .res-btn { font-size: 10px; padding: 4px 7px; }
  .status { font-size: 10px; color: #446; margin-top: 4px; }
  .fps-box { background: #06101a; border-radius: 4px; padding: 4px 8px;
             font-size: 11px; color: #00d4ff; text-align: center; margin-top: 6px; }
  @media (max-width: 520px) { .controls { width: 100%; } }
</style>
</head>
<body>
<div class="header">
  <h1>&#9654; FPV-CAR-<span id="carNum">?</span></h1>
  <div class="badge" id="badge">&#9679; LIVE</div>
</div>

<div class="main">
  <div class="stream-box">
    <img id="stream" src="/stream" alt="camera stream" onerror="streamError()">
    <div class="fps-box" id="fps">-- fps</div>
  </div>

  <div class="controls">

    <div class="card">
      <h3>Resolution</h3>
      <div class="btn-row">
        <div class="btn res-btn" onclick="setRes('QVGA')">QVGA<br>320</div>
        <div class="btn res-btn active" onclick="setRes('VGA')">VGA<br>640</div>
        <div class="btn res-btn" onclick="setRes('SVGA')">SVGA<br>800</div>
      </div>
    </div>

    <div class="card">
      <h3>Image</h3>
      <div class="row">
        <label>Brightness</label>
        <input type="range" min="-2" max="2" value="0" id="brightness"
               oninput="camCtrl('brightness',this.value);document.getElementById('bv').textContent=this.value">
        <span id="bv">0</span>
      </div>
      <div class="row">
        <label>Contrast</label>
        <input type="range" min="-2" max="2" value="0" id="contrast"
               oninput="camCtrl('contrast',this.value);document.getElementById('cv').textContent=this.value">
        <span id="cv">0</span>
      </div>
      <div class="row">
        <label>Saturation</label>
        <input type="range" min="-2" max="2" value="0" id="saturation"
               oninput="camCtrl('saturation',this.value);document.getElementById('sv').textContent=this.value">
        <span id="sv">0</span>
      </div>
    </div>

    <div class="card">
      <h3>Camera</h3>
      <div class="btn-row">
        <div class="btn" id="flipBtn" onclick="toggleFlip()">Flip V</div>
        <div class="btn" id="mirrorBtn" onclick="toggleMirror()">Mirror</div>
        <div class="btn" id="awbBtn" onclick="toggleAWB()">AWB</div>
      </div>
      <div class="btn-row" style="margin-top:6px">
        <div class="btn" id="nightBtn" onclick="toggleNight()">Night</div>
        <div class="btn red" onclick="resetCam()">Reset</div>
      </div>
    </div>

    <div class="card">
      <h3>Quality</h3>
      <div class="row">
        <label>JPEG Q</label>
        <input type="range" min="4" max="63" value="12" id="quality"
               oninput="camCtrl('quality',this.value);document.getElementById('qv').textContent=this.value">
        <span id="qv">12</span>
      </div>
      <div class="status">Lower = better quality + slower fps</div>
    </div>

    <div class="card">
      <h3>Info</h3>
      <div style="font-size:11px; color:#446; line-height:1.8">
        AP: <span style="color:#aac" id="ssid">-</span><br>
        IP: <span style="color:#00d4ff">192.168.4.1</span><br>
        Pass: <span style="color:#aac">fpvracer</span>
      </div>
    </div>

  </div>
</div>

<script>
let flipped=false, mirrored=false, awb=true, night=false;
let frameCount=0, lastFpsTime=Date.now();

fetch('/info').then(r=>r.json()).then(d=>{
  document.getElementById('carNum').textContent=d.car;
  document.getElementById('ssid').textContent=d.ssid;
});

document.getElementById('stream').onload=()=>{
  frameCount++;
  const now=Date.now();
  if(now-lastFpsTime>=1000){
    document.getElementById('fps').textContent=frameCount+' fps';
    frameCount=0; lastFpsTime=now;
  }
};

function camCtrl(key,val){
  fetch('/control?var='+key+'&val='+val);
}

function setRes(r){
  const map={QVGA:5,VGA:8,SVGA:9};
  fetch('/control?var=framesize&val='+map[r]);
  document.querySelectorAll('.res-btn').forEach(b=>b.classList.remove('active'));
  event.target.classList.add('active');
  // reload stream
  const img=document.getElementById('stream');
  img.src='/stream?t='+Date.now();
}

function toggleFlip(){
  flipped=!flipped;
  camCtrl('vflip', flipped?1:0);
  document.getElementById('flipBtn').classList.toggle('active',flipped);
}
function toggleMirror(){
  mirrored=!mirrored;
  camCtrl('hmirror', mirrored?1:0);
  document.getElementById('mirrorBtn').classList.toggle('active',mirrored);
}
function toggleAWB(){
  awb=!awb;
  camCtrl('awb', awb?1:0);
  document.getElementById('awbBtn').classList.toggle('active',awb);
}
function toggleNight(){
  night=!night;
  camCtrl('aec2', night?1:0);
  document.getElementById('nightBtn').classList.toggle('active',night);
}
function resetCam(){
  fetch('/reset');
  flipped=mirrored=night=false; awb=true;
  ['flipBtn','mirrorBtn','nightBtn'].forEach(id=>document.getElementById(id).classList.remove('active'));
  document.getElementById('awbBtn').classList.add('active');
  document.getElementById('brightness').value=0; document.getElementById('bv').textContent='0';
  document.getElementById('contrast').value=0;   document.getElementById('cv').textContent='0';
  document.getElementById('saturation').value=0; document.getElementById('sv').textContent='0';
  document.getElementById('quality').value=12;   document.getElementById('qv').textContent='12';
}
function streamError(){
  document.getElementById('badge').innerHTML='&#9679; RECONNECTING...';
  document.getElementById('badge').style.borderColor='#aa4400';
  document.getElementById('badge').style.color='#ff8844';
  setTimeout(()=>{
    document.getElementById('stream').src='/stream?t='+Date.now();
    document.getElementById('badge').innerHTML='&#9679; LIVE';
    document.getElementById('badge').style.borderColor='';
    document.getElementById('badge').style.color='';
  },2000);
}
</script>
</body>
</html>
)rawhtml";

// ---------------------------------------------------------------------------
// HTTP server handles
// ---------------------------------------------------------------------------
static httpd_handle_t stream_httpd = NULL;
static httpd_handle_t ctrl_httpd   = NULL;

// ── MJPEG stream handler ─────────────────────────────────────────────────────
#define PART_BOUNDARY "fpvframe"
static const char STREAM_CONTENT_TYPE[] =
    "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char STREAM_BOUNDARY[]  = "\r\n--" PART_BOUNDARY "\r\n";
static const char STREAM_PART[]      =
    "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

static esp_err_t stream_handler(httpd_req_t* req) {
    camera_fb_t* fb = NULL;
    esp_err_t res   = ESP_OK;
    char buf[64];

    res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
    if (res != ESP_OK) return res;

    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    while (true) {
        fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("[CAM] Frame capture failed");
            res = ESP_FAIL;
            break;
        }

        // Send boundary
        res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
        if (res != ESP_OK) break;

        // Send part header
        size_t hlen = snprintf(buf, sizeof(buf), STREAM_PART, fb->len);
        res = httpd_resp_send_chunk(req, buf, hlen);
        if (res != ESP_OK) break;

        // Send JPEG data
        res = httpd_resp_send_chunk(req, (const char*)fb->buf, fb->len);
        esp_camera_fb_return(fb);
        fb = NULL;
        if (res != ESP_OK) break;
    }

    if (fb) esp_camera_fb_return(fb);
    return res;
}

// ── Index page handler ───────────────────────────────────────────────────────
static esp_err_t index_handler(httpd_req_t* req) {
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, INDEX_HTML, strlen(INDEX_HTML));
}

// ── Info handler — returns JSON with car number and SSID ─────────────────────
static esp_err_t info_handler(httpd_req_t* req) {
    char buf[80];
    snprintf(buf, sizeof(buf),
             "{\"car\":%d,\"ssid\":\"%s\"}", CAR_NUMBER, AP_SSID);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    return httpd_resp_send(req, buf, strlen(buf));
}

// ── Camera control handler — /control?var=brightness&val=1 ──────────────────
static esp_err_t control_handler(httpd_req_t* req) {
    char query[128] = {};
    char varBuf[32] = {}, valBuf[8] = {};
    int val = 0;

    if (httpd_req_get_url_query_str(req, query, sizeof(query)) != ESP_OK) {
        httpd_resp_send(req, "bad query", 9);
        return ESP_OK;
    }

    httpd_query_key_value(query, "var", varBuf, sizeof(varBuf));
    httpd_query_key_value(query, "val", valBuf, sizeof(valBuf));
    val = atoi(valBuf);

    sensor_t* s = esp_camera_sensor_get();
    if (!s) { httpd_resp_send(req, "no sensor", 9); return ESP_OK; }

    if      (!strcmp(varBuf,"framesize"))  s->set_framesize(s, (framesize_t)val);
    else if (!strcmp(varBuf,"quality"))    s->set_quality(s, val);
    else if (!strcmp(varBuf,"brightness")) s->set_brightness(s, val);
    else if (!strcmp(varBuf,"contrast"))   s->set_contrast(s, val);
    else if (!strcmp(varBuf,"saturation")) s->set_saturation(s, val);
    else if (!strcmp(varBuf,"hmirror"))    s->set_hmirror(s, val);
    else if (!strcmp(varBuf,"vflip"))      s->set_vflip(s, val);
    else if (!strcmp(varBuf,"awb"))        s->set_whitebal(s, val);
    else if (!strcmp(varBuf,"aec2"))       s->set_aec2(s, val);

    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_send(req, "OK", 2);
    return ESP_OK;
}

// ── Reset handler ────────────────────────────────────────────────────────────
static esp_err_t reset_handler(httpd_req_t* req) {
    sensor_t* s = esp_camera_sensor_get();
    if (s) {
        s->set_framesize(s, FRAMESIZE_VGA);
        s->set_quality(s, 12);
        s->set_brightness(s, 0);
        s->set_contrast(s, 0);
        s->set_saturation(s, 0);
        s->set_hmirror(s, 0);
        s->set_vflip(s, 0);
        s->set_whitebal(s, 1);
        s->set_aec2(s, 0);
    }
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_send(req, "OK", 2);
    return ESP_OK;
}

// ---------------------------------------------------------------------------
// Start servers
// ---------------------------------------------------------------------------
void start_camera_server() {
    // Stream server on port 81
    httpd_config_t stream_cfg = HTTPD_DEFAULT_CONFIG();
    stream_cfg.server_port      = 81;
    stream_cfg.ctrl_port        = 32769;
    stream_cfg.max_uri_handlers = 2;

    if (httpd_start(&stream_httpd, &stream_cfg) == ESP_OK) {
        httpd_uri_t stream_uri = {
            .uri      = "/stream",
            .method   = HTTP_GET,
            .handler  = stream_handler,
            .user_ctx = NULL
        };
        httpd_register_uri_handler(stream_httpd, &stream_uri);
        Serial.println("[HTTP] Stream server on :81/stream");
    }

    // Control server on port 80
    httpd_config_t ctrl_cfg = HTTPD_DEFAULT_CONFIG();
    ctrl_cfg.max_uri_handlers = 8;

    if (httpd_start(&ctrl_httpd, &ctrl_cfg) == ESP_OK) {
        httpd_uri_t index_uri   = { "/",        HTTP_GET, index_handler,   NULL };
        httpd_uri_t control_uri = { "/control", HTTP_GET, control_handler, NULL };
        httpd_uri_t info_uri    = { "/info",    HTTP_GET, info_handler,    NULL };
        httpd_uri_t reset_uri   = { "/reset",   HTTP_GET, reset_handler,   NULL };
        httpd_register_uri_handler(ctrl_httpd, &index_uri);
        httpd_register_uri_handler(ctrl_httpd, &control_uri);
        httpd_register_uri_handler(ctrl_httpd, &info_uri);
        httpd_register_uri_handler(ctrl_httpd, &reset_uri);
        Serial.println("[HTTP] Control server on :80");
    }
}

// ---------------------------------------------------------------------------
// setup()
// ---------------------------------------------------------------------------
void setup() {
    Serial.begin(115200);
    snprintf(AP_SSID, sizeof(AP_SSID), "FPV-CAR-%d", CAR_NUMBER);
    Serial.printf("\n[FPV] %s starting...\n", AP_SSID);

    // ── Camera init ─────────────────────────────────────────────────────────
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer   = LEDC_TIMER_0;
    config.pin_d0       = Y2_GPIO_NUM;
    config.pin_d1       = Y3_GPIO_NUM;
    config.pin_d2       = Y4_GPIO_NUM;
    config.pin_d3       = Y5_GPIO_NUM;
    config.pin_d4       = Y6_GPIO_NUM;
    config.pin_d5       = Y7_GPIO_NUM;
    config.pin_d6       = Y8_GPIO_NUM;
    config.pin_d7       = Y9_GPIO_NUM;
    config.pin_xclk     = XCLK_GPIO_NUM;
    config.pin_pclk     = PCLK_GPIO_NUM;
    config.pin_vsync    = VSYNC_GPIO_NUM;
    config.pin_href     = HREF_GPIO_NUM;
    config.pin_sscb_sda = SIOD_GPIO_NUM;
    config.pin_sscb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn     = PWDN_GPIO_NUM;
    config.pin_reset    = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size   = FRAMESIZE_VGA;   // 640×480 default
    config.jpeg_quality = 12;              // 4=best 63=worst
    config.fb_count     = 2;              // double buffer for smooth stream
    config.fb_location  = CAMERA_FB_IN_PSRAM;
    config.grab_mode    = CAMERA_GRAB_WHEN_EMPTY;

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("[CAM] Init failed: 0x%x — check wiring!\n", err);
        // Blink forever to show error
        while(true) { delay(300); }
    }

    // Flip image for typical car-mount orientation
    sensor_t* s = esp_camera_sensor_get();
    if (s) {
        s->set_vflip(s, 1);      // flip vertical for roof-mount
        s->set_brightness(s, 1); // slight brightness boost for indoor
    }

    Serial.println("[CAM] Camera OK");

    // ── WiFi AP ─────────────────────────────────────────────────────────────
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASSWORD);
    delay(200); // let AP start

    IPAddress ip = WiFi.softAPIP();
    Serial.printf("[WiFi] AP: %s  Pass: %s\n", AP_SSID, AP_PASSWORD);
    Serial.printf("[WiFi] Open browser: http://%s\n", ip.toString().c_str());

    // ── HTTP servers ─────────────────────────────────────────────────────────
    start_camera_server();

    Serial.println("[FPV] Ready!");
    Serial.println("[FPV] 1. Connect phone to WiFi: " + String(AP_SSID));
    Serial.println("[FPV] 2. Open browser: http://192.168.4.1");
}

// ---------------------------------------------------------------------------
// loop() — nothing needed, servers run on their own tasks
// ---------------------------------------------------------------------------
void loop() {
    // Print connected clients every 5 seconds
    static uint32_t lastPrint = 0;
    if (millis() - lastPrint > 5000) {
        lastPrint = millis();
        Serial.printf("[WiFi] Clients connected: %d\n",
                      WiFi.softAPgetStationNum());
    }
    delay(100);
}
