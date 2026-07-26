// =============================================================================
//  rc_display.cpp — TFT display driver for RC (ILI9341 2.8" 320×240)
//
//  Uses Adafruit_ILI9341 + Adafruit_GFX.
//  All drawing is done with dirty-region tracking — only changed areas repaint.
//  Full redraws happen only on phase transitions.
//
//  Screen is held in LANDSCAPE (320 wide × 240 tall).
// =============================================================================

#include "rc_display.h"
#include "rc_types.h"
#include <Adafruit_ILI9341.h>
#include <Adafruit_GFX.h>
#include <Arduino.h>

static Adafruit_ILI9341 tft(TFT_CS, TFT_DC, TFT_RST);

// ---------------------------------------------------------------------------
// Dirty flags — set when a region needs repaint
// ---------------------------------------------------------------------------
static bool dirty_header    = true;
static bool dirty_hp        = true;
static bool dirty_powers    = true;
static bool dirty_bad       = true;
static bool dirty_log       = true;
static bool dirty_opp       = true;
static bool dirty_bullets   = true;
static bool dirty_full      = true;

// Previous values for change detection
static uint8_t   prev_myHp     = 255;
static uint8_t   prev_oppHp    = 255;
static uint8_t   prev_bullets  = 255;
static uint8_t   prev_myLaps   = 255;
static uint8_t   prev_oppLaps  = 255;
static uint16_t  prev_score    = 0xFFFF;
static uint8_t   prev_bad      = 255;
static uint8_t   prev_phase    = 255;
static uint8_t   prev_inv[4]   = {255,255,255,255};
static uint16_t  prev_timer    = 0xFFFF;

// Log ring buffer
static char s_log[LOG_RING_SIZE][32];
static uint8_t s_logHead = 0;
static uint8_t s_logCount = 0;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static uint16_t hp_colour(uint8_t hp) {
    if (hp > 60) return COL_HP_GREEN;
    if (hp > 30) return COL_HP_ORANGE;
    return COL_HP_RED;
}

// Draw a filled rounded rect bar  (x,y,w,h) filled to pct%
static void draw_bar(int16_t x, int16_t y, int16_t w, int16_t h,
                     uint8_t pct, uint16_t fillCol, uint16_t bgCol) {
    int16_t filled = (int16_t)((int32_t)w * pct / 100);
    tft.fillRect(x, y, filled, h, fillCol);
    if (filled < w) tft.fillRect(x + filled, y, w - filled, h, bgCol);
}

// Centred text in a box
static void draw_centred(const char* txt, int16_t cx, int16_t y,
                         uint8_t textSize, uint16_t col, uint16_t bg) {
    tft.setTextSize(textSize);
    tft.setTextColor(col, bg);
    int16_t x1, y1; uint16_t tw, th;
    tft.getTextBounds(txt, 0, 0, &x1, &y1, &tw, &th);
    tft.setCursor(cx - tw / 2, y);
    tft.print(txt);
}

static void label(const char* txt, int16_t x, int16_t y,
                  uint8_t sz, uint16_t col, uint16_t bg = COL_BG) {
    tft.setTextSize(sz);
    tft.setTextColor(col, bg);
    tft.setCursor(x, y);
    tft.print(txt);
}

static void hline(int16_t y, uint16_t col = 0x2945) {
    tft.drawFastHLine(0, y, SCREEN_W, col);
}

static const char* power_name(PowerType p) {
    switch(p) {
        case PWR_BOOST:       return "BOOST";
        case PWR_SHIELD:      return "SHIELD";
        case PWR_REGEN:       return "REGEN";
        case PWR_BULLETS:     return "BULLETS";
        case BAD_SLOWNESS:    return "SLOW";
        case BAD_RANDOM_CTRL: return "CHAOS";
        case BAD_DAMAGE:      return "DAMAGE";
        case BAD_DRIFT:       return "DRIFT";
        default:              return "---";
    }
}

static uint16_t power_colour(PowerType p) {
    switch(p) {
        case PWR_BOOST:       return 0xFFE0; // yellow
        case PWR_SHIELD:      return 0x001F; // blue
        case PWR_REGEN:       return 0x07E0; // green
        case PWR_BULLETS:     return 0xF81F; // magenta
        case BAD_SLOWNESS:
        case BAD_RANDOM_CTRL:
        case BAD_DAMAGE:
        case BAD_DRIFT:       return 0xF800; // red
        default:              return 0x4208; // grey
    }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
void display_init() {
    tft.begin();
    tft.setRotation(1); // landscape
    tft.fillScreen(COL_BG);
    dirty_full = true;
}

void display_force_full_redraw() {
    dirty_full = dirty_header = dirty_hp = dirty_powers =
    dirty_bad  = dirty_log   = dirty_opp = dirty_bullets = true;
    prev_myHp = prev_oppHp = prev_bullets = prev_myLaps =
    prev_oppLaps = prev_bad = prev_phase = 255;
}

// ---------------------------------------------------------------------------
// Log ring buffer
// ---------------------------------------------------------------------------
void display_push_log(const char* msg) {
    strncpy(s_log[s_logHead], msg, 31);
    s_log[s_logHead][31] = 0;
    s_logHead = (s_logHead + 1) % LOG_RING_SIZE;
    if (s_logCount < LOG_RING_SIZE) s_logCount++;
    dirty_log = true;
}

// ---------------------------------------------------------------------------
// BOOT / SPLASH SCREEN
// ---------------------------------------------------------------------------
void display_splash() {
    tft.fillScreen(COL_BG);

    // Title
    tft.setTextSize(3);
    tft.setTextColor(COL_ACCENT);
    draw_centred("FPV RACER", 160, 60, 3, COL_ACCENT, COL_BG);

    tft.setTextSize(1);
    draw_centred("v2.0  HACKCLUB FALLOUT", 160, 100, 1, COL_GREY, COL_BG);
    draw_centred("Booting...", 160, 130, 1, COL_WHITE, COL_BG);

    // Animated boot bar
    for (int i = 0; i <= 100; i += 4) {
        draw_bar(60, 150, 200, 8, i, COL_ACCENT, 0x2945);
        delay(20);
    }
}

// ---------------------------------------------------------------------------
// IDLE / FREE DRIVE screen
// ---------------------------------------------------------------------------
void display_idle(bool carConnected, uint8_t battPct) {
    if (!dirty_full) return;
    dirty_full = false;
    tft.fillScreen(COL_BG);

    draw_centred("FPV RACER", 160, 20, 3, COL_ACCENT, COL_BG);
    hline(62);

    if (carConnected) {
        draw_centred("CAR CONNECTED", 160, 80, 2, COL_GREEN, COL_BG);
        draw_centred("Free drive mode active", 160, 110, 1, COL_GREY, COL_BG);
        draw_centred("Press CONNECT to find race", 160, 130, 1, COL_WHITE, COL_BG);
    } else {
        draw_centred("NO CAR FOUND", 160, 80, 2, COL_RED, COL_BG);
        draw_centred("Searching for paired car...", 160, 110, 1, COL_GREY, COL_BG);
        // Spinner dots
        static uint8_t dot = 0;
        const char* dots[] = {"[  .  ]","[ ..  ]","[ ... ]","[  .. ]"};
        draw_centred(dots[dot++ % 4], 160, 140, 2, COL_YELLOW, COL_BG);
    }

    hline(170);
    // Battery indicator
    char bat[16]; snprintf(bat, sizeof(bat), "BAT %d%%", battPct);
    label(bat, 4, 176, 1, battPct > 30 ? COL_GREEN : COL_RED, COL_BG);
    char rcid[16]; snprintf(rcid, sizeof(rcid), "RC %d", RC_ID);
    label(rcid, 270, 176, 1, COL_GREY, COL_BG);
}

// ---------------------------------------------------------------------------
// CONNECTING / LOOKING screen
// ---------------------------------------------------------------------------
void display_looking(uint8_t dotAnim) {
    if (!dirty_full) return;
    dirty_full = false;
    tft.fillScreen(COL_BG);

    draw_centred("FIND RACE", 160, 30, 3, COL_YELLOW, COL_BG);
    hline(65);
    draw_centred("Broadcasting...", 160, 90, 2, COL_WHITE, COL_BG);

    const char* dots[] = {"●○○○","●●○○","●●●○","●●●●"};
    draw_centred(dots[dotAnim % 4], 160, 130, 2, COL_ACCENT, COL_BG);
    draw_centred("Waiting for opponent", 160, 170, 1, COL_GREY, COL_BG);
    draw_centred("Press BACK to cancel", 160, 190, 1, COL_GREY, COL_BG);
}

// ---------------------------------------------------------------------------
// ACCEPT REQUEST screen
// ---------------------------------------------------------------------------
void display_accept_request(uint8_t fromRcId) {
    tft.fillScreen(COL_BG);

    draw_centred("RACE REQUEST", 160, 25, 2, COL_YELLOW, COL_BG);
    hline(55);

    char msg[40];
    snprintf(msg, sizeof(msg), "Player %d wants to race!", fromRcId);
    draw_centred(msg, 160, 85, 1, COL_WHITE, COL_BG);

    // Two big buttons
    tft.fillRoundRect(30,  120, 110, 50, 8, COL_GREEN);
    tft.fillRoundRect(180, 120, 110, 50, 8, COL_RED);
    draw_centred("OK",   85,  140, 2, COL_BG, COL_GREEN);
    draw_centred("BACK", 235, 140, 2, COL_BG, COL_RED);
    draw_centred("Accept?", 160, 185, 1, COL_GREY, COL_BG);
}

// ---------------------------------------------------------------------------
// NFC SETUP screen
// ---------------------------------------------------------------------------
void display_nfc_setup(uint8_t done, uint8_t total, bool isHost) {
    static uint8_t prev_done = 255;
    if (done == prev_done && !dirty_full) return;
    prev_done = done;
    dirty_full = false;

    tft.fillScreen(COL_BG);
    draw_centred("NFC SETUP", 160, 18, 2, COL_ACCENT, COL_BG);
    hline(44);

    if (isHost) {
        draw_centred("Hold each tag to HOST car", 160, 58, 1, COL_WHITE, COL_BG);
        draw_centred("(underside PN532 reader)", 160, 74, 1, COL_GREY, COL_BG);
    } else {
        draw_centred("HOST scanning tags...", 160, 66, 1, COL_GREY, COL_BG);
    }

    // Progress bar + count
    char prog[20]; snprintf(prog, sizeof(prog), "%d / %d tags", done, total);
    draw_centred(prog, 160, 104, 2, COL_YELLOW, COL_BG);
    draw_bar(40, 130, 240, 14, (done * 100) / (total > 0 ? total : 1),
             COL_ACCENT, 0x2945);

    if (done >= total && total > 0) {
        draw_centred("ALL DONE! Place tags on track", 160, 160, 1, COL_GREEN, COL_BG);
    } else {
        draw_centred(isHost ? "Scan next tag..." : "Waiting...", 160, 160, 1, COL_GREY, COL_BG);
    }
}

// ---------------------------------------------------------------------------
// LOBBY screen
// ---------------------------------------------------------------------------
void display_lobby(bool p1Ready, bool p2Ready, uint8_t mode,
                   uint8_t laps, uint16_t timeSec, uint8_t tagCount, bool isHost) {
    if (!dirty_full) return;
    dirty_full = false;
    tft.fillScreen(COL_BG);

    draw_centred("LOBBY", 160, 10, 2, COL_ACCENT, COL_BG);
    hline(36);

    // Players
    tft.fillRoundRect(10,  44, 140, 36, 6, p1Ready ? 0x0420 : 0x2104);
    tft.fillRoundRect(170, 44, 140, 36, 6, p2Ready ? 0x0420 : 0x2104);

    label(p1Ready ? "P1  READY" : "P1  WAIT", 20,  56, 1,
          p1Ready ? COL_GREEN : COL_GREY, p1Ready ? 0x0420 : 0x2104);
    label(p2Ready ? "P2  READY" : "P2  WAIT", 180, 56, 1,
          p2Ready ? COL_GREEN : COL_GREY, p2Ready ? 0x0420 : 0x2104);

    hline(88);

    // Settings
    char modeStr[32];
    if (mode == 0) snprintf(modeStr, sizeof(modeStr), "Mode: LAP RACE  x%d laps", laps);
    else           snprintf(modeStr, sizeof(modeStr), "Mode: TIME RACE  %ds", timeSec);
    label(modeStr, 10, 98, 1, COL_WHITE, COL_BG);

    char tagStr[24]; snprintf(tagStr, sizeof(tagStr), "Tags: %d registered", tagCount);
    label(tagStr, 10, 114, 1, COL_GREY, COL_BG);

    hline(132);

    if (isHost) {
        // D-pad hints for host settings
        label("UP/DN: laps  LT/RT: mode", 10, 140, 1, COL_GREY, COL_BG);
        tft.fillRoundRect(80, 156, 160, 36, 8, COL_GREEN);
        draw_centred("OK = START", 160, 168, 1, COL_BG, COL_GREEN);
    } else {
        draw_centred("Waiting for host to start...", 160, 158, 1, COL_GREY, COL_BG);
    }
}

// ---------------------------------------------------------------------------
// COUNTDOWN screen  (3-2-1-GO)
// ---------------------------------------------------------------------------
void display_countdown(uint8_t tick) {
    tft.fillScreen(COL_BG);
    if (tick == 0) {
        // GO!
        tft.fillScreen(0x07E0); // flash green
        draw_centred("GO!", 160, 80, 6, COL_BG, 0x07E0);
        delay(400);
        tft.fillScreen(COL_BG);
    } else {
        char buf[4]; snprintf(buf, sizeof(buf), "%d", tick);
        tft.setTextSize(8);
        tft.setTextColor(tick == 1 ? COL_RED : COL_YELLOW, COL_BG);
        draw_centred(buf, 160, 60, 8, tick == 1 ? COL_RED : COL_YELLOW, COL_BG);
        draw_centred("READY...", 160, 180, 2, COL_GREY, COL_BG);
    }
    display_force_full_redraw(); // next frame is racing UI — full redraw
}

// ---------------------------------------------------------------------------
// RACING SCREEN — main HUD (320×240, landscape)
//
//  Layout:
//  ┌──────────────────────────────────────────────────────────────────┐
//  │ [P1 HOST]        02:31         LAP 3/5       [SCORE: 120]  H:5 │  ← header row  y=0-20
//  ├──────────────────────────────────────────────────────────────────┤
//  │ MY HP  ████████████░░░ 80%     │  OPP HP  ████████░░░░ 65%     │  ← HP bars     y=22-52
//  ├─────────────────────────────────┼────────────────────────────────┤
//  │ [BOOST] [SHIELD] [REGEN] [BUL:3]                               │  ← power row   y=54-90
//  ├──────────────────────────────────────────────────────────────────┤
//  │  ⚠ BAD POWER: SLOWNESS   ████░░░░ (timer bar)                  │  ← bad power   y=92-116
//  ├──────────────────────────────────────────────────────────────────┤
//  │  LOG: HIT +5pts │ LAP DONE │ SHIELD ABSORBED │ TAG BOOST       │  ← log strip   y=118-136
//  ├──────────────────────────────────────────────────────────────────┤
//  │ [ SHOOT  ] [ BOOST ] [ SHIELD ] [ REGEN ]  ← button hints      │  ← hint row    y=138-160
//  └──────────────────────────────────────────────────────────────────┘
//  Bottom-right: bullet count large
// ---------------------------------------------------------------------------

static uint32_t s_badStartMs    = 0;
static uint32_t s_badDurationMs = 0;

void display_set_bad_timer(uint32_t durationMs) {
    s_badStartMs    = millis();
    s_badDurationMs = durationMs;
}

void display_racing(const RCGameState& gs, uint32_t nowMs) {
    bool shieldActive = (gs.flags & 0x01);
    bool frozen       = (gs.flags & 0x04);

    // ── Header ─────────────────────────────────────────────────────────────
    if (dirty_header || gs.myLaps != prev_myLaps || gs.countdown != prev_timer
        || gs.phase != prev_phase || gs.myScore != prev_score) {
        dirty_header = false;
        prev_myLaps  = gs.myLaps;
        prev_timer   = gs.countdown;
        prev_phase   = gs.phase;
        prev_score   = gs.myScore;

        tft.fillRect(0, 0, SCREEN_W, 20, COL_PANEL);

        // P1/P2 label + host indicator
        char pid[16]; snprintf(pid, sizeof(pid), "P%d%s", RC_ID, gs.phase == 8 ? "" : "");
        label(pid, 4, 4, 1, COL_ACCENT, COL_PANEL);

        // Timer
        uint32_t sec = gs.countdown;
        char timer[12];
        if (gs.mode == 0) {
            // LAP mode — show elapsed
            uint32_t el = gs.matchTimeMs / 1000;
            snprintf(timer, sizeof(timer), "%02lu:%02lu", el/60, el%60);
        } else {
            snprintf(timer, sizeof(timer), "%02lu:%02lu", sec/60, sec%60);
        }
        draw_centred(timer, 160, 4, 2, frozen ? COL_YELLOW : COL_WHITE, COL_PANEL);

        // Lap counter
        char lapbuf[16];
        snprintf(lapbuf, sizeof(lapbuf), "L%d/%d",
                 gs.myLaps, (gs.mode == 0) ? 5 : 0);
        label(lapbuf, 230, 4, 1, COL_ACCENT, COL_PANEL);

        // Score
        char scbuf[12]; snprintf(scbuf, sizeof(scbuf), "%d", gs.myScore);
        label(scbuf, 292, 4, 1, COL_YELLOW, COL_PANEL);
    }

    // ── HP Bars ─────────────────────────────────────────────────────────────
    if (dirty_hp || gs.myHealth != prev_myHp || gs.oppHealth != prev_oppHp) {
        dirty_hp   = false;
        prev_myHp  = gs.myHealth;
        prev_oppHp = gs.oppHealth;

        tft.fillRect(0, 22, SCREEN_W, 30, COL_BG);

        // My HP — left half
        uint16_t myCol = hp_colour(gs.myHealth);
        label("ME", 4, 24, 1, myCol, COL_BG);
        draw_bar(28, 24, 110, 10, gs.myHealth, myCol, 0x2945);
        if (shieldActive) {
            // Shield overlay border
            tft.drawRect(27, 23, 112, 12, COL_SHIELD_BLU);
        }
        char hpbuf[8]; snprintf(hpbuf, sizeof(hpbuf), "%d%%", gs.myHealth);
        label(hpbuf, 142, 24, 1, myCol, COL_BG);

        // Opp HP — right half
        uint16_t oppCol = hp_colour(gs.oppHealth);
        label("OPP", 170, 24, 1, oppCol, COL_BG);
        draw_bar(198, 24, 110, 10, gs.oppHealth, oppCol, 0x2945);
        snprintf(hpbuf, sizeof(hpbuf), "%d%%", gs.oppHealth);
        label(hpbuf, 312, 24, 1, oppCol, COL_BG);

        // Opp lap count
        char olap[10]; snprintf(olap, sizeof(olap), "L%d", gs.oppLaps);
        label(olap, 290, 35, 1, COL_GREY, COL_BG);

        hline(52);
    }

    // ── Power inventory row ─────────────────────────────────────────────────
    bool invChanged = false;
    for (int i = 0; i < 4; i++) if (gs.inventory[i] != prev_inv[i]) { invChanged = true; break; }
    if (dirty_powers || invChanged || dirty_bullets || gs.myBullets != prev_bullets) {
        dirty_powers = false;
        dirty_bullets= false;
        for (int i = 0; i < 4; i++) prev_inv[i] = gs.inventory[i];
        prev_bullets = gs.myBullets;

        tft.fillRect(0, 54, SCREEN_W, 36, COL_BG);

        // 4 power slots  (each slot 70px wide, gap 5px)
        const int slotW = 68, slotH = 28, slotY = 56, gap = 4;
        for (int i = 0; i < 4; i++) {
            int x = 4 + i * (slotW + gap);
            PowerType p = gs.inventory[i];
            bool hasPower = (p != PWR_NONE);
            uint16_t bg  = hasPower ? 0x1863 : 0x1082;
            uint16_t col = hasPower ? power_colour(p) : COL_GREY;

            tft.fillRoundRect(x, slotY, slotW, slotH, 5, bg);
            tft.drawRoundRect(x, slotY, slotW, slotH, 5, col);

            if (hasPower) {
                draw_centred(power_name(p), x + slotW/2, slotY + 4, 1, col, bg);
                // Slot number hint at bottom-right of each slot
                char sn[3]; snprintf(sn, sizeof(sn), "%d", i+1);
                tft.setTextSize(1);
                tft.setTextColor(0x4208, bg);
                tft.setCursor(x + slotW - 8, slotY + 16);
                tft.print(sn);
            } else {
                draw_centred("---", x + slotW/2, slotY + 8, 1, COL_GREY, bg);
            }
        }

        // Bullet counter — right side of power row
        tft.fillRoundRect(284, 56, 32, 28, 5,
                          gs.myBullets > 0 ? 0x300C : 0x1082);
        char bul[4]; snprintf(bul, sizeof(bul), "%d", gs.myBullets);
        draw_centred(bul, 300, 62, 2,
                     gs.myBullets > 0 ? COL_RED : COL_GREY,
                     gs.myBullets > 0 ? 0x300C : 0x1082);

        hline(90);
    }

    // ── Bad power strip ──────────────────────────────────────────────────────
    if (dirty_bad || gs.badPower != (PowerType)prev_bad) {
        dirty_bad = false;
        prev_bad  = gs.badPower;

        tft.fillRect(0, 92, SCREEN_W, 24, COL_BG);

        if (gs.badPower != PWR_NONE) {
            // Flashing warning background
            static bool flashState = false;
            flashState = !flashState;
            uint16_t warnBg = flashState ? 0x2000 : 0x1000;
            tft.fillRect(0, 92, SCREEN_W, 24, warnBg);

            label("\x21 BAD: ", 4, 97, 1, COL_RED, warnBg); // ⚠ symbol via !
            label(power_name(gs.badPower), 60, 97, 1, COL_YELLOW, warnBg);
            label(">> drive to station", 150, 97, 1, COL_GREY, warnBg);

            // Bad power timer bar (if known duration)
            if (s_badDurationMs > 0) {
                uint32_t elapsed = nowMs - s_badStartMs;
                uint8_t pct = (elapsed < s_badDurationMs) ?
                    (uint8_t)(100 - elapsed * 100 / s_badDurationMs) : 0;
                draw_bar(4, 110, 180, 4, pct, COL_RED, 0x2000);
            }
        } else {
            // No bad power — show a status info line
            label("Status: OK  |  Shield: ", 4, 97, 1, COL_GREEN, COL_BG);
            label(shieldActive ? "ACTIVE" : "OFF",
                  shieldActive ? 136 : 136, 97, 1,
                  shieldActive ? COL_SHIELD_BLU : COL_GREY, COL_BG);
        }

        hline(116);
    }

    // ── Log strip ────────────────────────────────────────────────────────────
    if (dirty_log) {
        dirty_log = false;
        tft.fillRect(0, 118, SCREEN_W, 18, 0x0820);

        // Show last 3 log entries scrolling right-to-left
        uint8_t shown = s_logCount < 3 ? s_logCount : 3;
        int xpos = 4;
        for (int i = shown - 1; i >= 0; i--) {
            uint8_t idx = (s_logHead + LOG_RING_SIZE - 1 - i) % LOG_RING_SIZE;
            uint16_t c = (i == 0) ? COL_WHITE : COL_GREY;
            tft.setTextSize(1);
            tft.setTextColor(c, 0x0820);
            tft.setCursor(xpos, 123);
            tft.print(s_log[idx]);
            xpos += strlen(s_log[idx]) * 6 + 8;
            if (i > 0 && xpos < SCREEN_W - 4) {
                label("|", xpos - 4, 123, 1, 0x2945, 0x0820);
            }
        }

        hline(136);
    }

    // ── Button hint bar ──────────────────────────────────────────────────────
    // Redrawn only on phase entry (already cleared by full redraw)
    if (dirty_full) {
        dirty_full = false;
        tft.fillRect(0, 138, SCREEN_W, 22, 0x0820);
        const char* hints[] = {"SHOOT", "BOOST", "SHIELD", "REGEN"};
        for (int i = 0; i < 4; i++) {
            int x = 4 + i * 80;
            tft.fillRoundRect(x, 140, 74, 18, 4, 0x1863);
            draw_centred(hints[i], x + 37, 144, 1, COL_ACCENT, 0x1863);
        }
        hline(160);
    }

    // ── Frozen overlay ──────────────────────────────────────────────────────
    if (frozen) {
        // Semi-transparent yellow stripe overlay at bottom
        tft.fillRect(0, 162, SCREEN_W, 78, 0x2000);
        draw_centred("!! FROZEN !!", 160, 185, 3, COL_YELLOW, 0x2000);
        draw_centred("Move away from tags", 160, 215, 1, COL_WHITE, 0x2000);
    } else {
        // Opp score at bottom-right
        tft.fillRect(0, 162, SCREEN_W, 78, COL_BG);
        char oppsc[24]; snprintf(oppsc, sizeof(oppsc), "OPP SCORE: %d", gs.oppScore);
        label(oppsc, 4, 168, 1, COL_GREY, COL_BG);
    }
}

// ---------------------------------------------------------------------------
// Mark regions dirty from outside
// ---------------------------------------------------------------------------
void display_dirty_hp()     { dirty_hp     = true; }
void display_dirty_powers() { dirty_powers = true; }
void display_dirty_bad()    { dirty_bad    = true;  dirty_log = true; }
void display_dirty_log()    { dirty_log    = true; }
void display_dirty_header() { dirty_header = true; }
void display_dirty_full()   { display_force_full_redraw(); }

// ---------------------------------------------------------------------------
// RESULTS / FINISHED screen
// ---------------------------------------------------------------------------
void display_results(const PktMatchEnd* end, uint8_t myRcId) {
    tft.fillScreen(COL_BG);

    bool iWon = (end->winner == myRcId);
    uint16_t titleCol = iWon ? COL_GREEN : COL_RED;
    const char* title = iWon ? "VICTORY!" : "DEFEAT";

    // Flash
    for (int f = 0; f < 3; f++) {
        tft.fillScreen(iWon ? 0x0420 : 0x2000);
        delay(150);
        tft.fillScreen(COL_BG);
        delay(100);
    }

    draw_centred(title, 160, 18, 3, titleCol, COL_BG);
    hline(50);

    // Score table
    tft.fillRect(10, 56, 140, 80, COL_PANEL);
    tft.fillRect(170,56, 140, 80, COL_PANEL);

    label("P1",              20, 64,  2, COL_ACCENT, COL_PANEL);
    char p1sc[12]; snprintf(p1sc, sizeof(p1sc), "%d pts", end->p1Score);
    label(p1sc,              20, 84,  1, COL_WHITE,  COL_PANEL);
    char p1hp[12]; snprintf(p1hp, sizeof(p1hp), "HP: %d%%", end->p1HealthFinal);
    label(p1hp,              20, 98,  1, hp_colour(end->p1HealthFinal), COL_PANEL);
    char p1lp[10]; snprintf(p1lp, sizeof(p1lp), "Laps: %d", end->p1Laps);
    label(p1lp,              20, 112, 1, COL_GREY,   COL_PANEL);

    label("P2",              180, 64, 2, COL_ACCENT, COL_PANEL);
    char p2sc[12]; snprintf(p2sc, sizeof(p2sc), "%d pts", end->p2Score);
    label(p2sc,              180, 84, 1, COL_WHITE,  COL_PANEL);
    char p2hp[12]; snprintf(p2hp, sizeof(p2hp), "HP: %d%%", end->p2HealthFinal);
    label(p2hp,              180, 98, 1, hp_colour(end->p2HealthFinal), COL_PANEL);
    char p2lp[10]; snprintf(p2lp, sizeof(p2lp), "Laps: %d", end->p2Laps);
    label(p2lp,              180, 112,1, COL_GREY,   COL_PANEL);

    hline(142);
    draw_centred(iWon ? "You won! Well raced." : "Better luck next time.",
                 160, 152, 1, COL_GREY, COL_BG);
    draw_centred("Press CONNECT to play again", 160, 170, 1, COL_WHITE, COL_BG);
}
