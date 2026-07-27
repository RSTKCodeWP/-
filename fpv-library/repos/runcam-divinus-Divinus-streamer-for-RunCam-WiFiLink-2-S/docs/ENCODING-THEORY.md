# Encoding Theory — Why These Settings

## The FPV Constraint

In FPV applications using wfb-ng (WiFi Broadcast), the practical bitrate ceiling is approximately **700 KB/s (5600 kbps)**. Going higher causes packet loss, latency spikes, and dropped frames.

This means we must extract **maximum visual quality from every single bit**.

## Bits Per Pixel Analysis

The key metric is **bits per pixel per frame** (bpp):

```
bpp = bitrate / (width × height × fps)
```

| Resolution | Pixels | BPP at 5600kbps/30fps | Visual Quality |
|---|---|---|---|
| 640×360 | 230,400 | 24.31 | Overkill — wasted bits |
| 800×448 | 358,400 | 15.62 | Very good — extra headroom |
| 960×540 | 518,400 | 10.80 | Excellent |
| **1024×576** | **589,824** | **9.49** | **★ Sweet spot** |
| 1152×648 | 746,496 | 7.50 | Good |
| 1280×720 | 921,600 | 6.07 | Acceptable |
| 1440×810 | 1,166,400 | 4.80 | Noticeable compression |
| 1920×1080 | 2,073,600 | 2.70 | Heavily compressed |

### Why 1024×576?

At ~9.5 bpp with H.265, the encoder has enough bits to:
- Preserve fine texture detail (grass, trees, buildings)
- Handle fast motion (propwash, flips, dives) without blocking
- Maintain consistent quality across scene complexity
- Keep QP in the 24-36 range for most frames

At 1280×720, you drop to ~6 bpp. The encoder compensates by:
- Raising QP (more quantization = more blocking)
- Dropping detail in motion areas
- Creating visible banding in gradients (sky)

## H.265 vs H.264

H.265 (HEVC) provides **~30-40% better compression** than H.264 at equivalent quality, primarily through:

| Feature | H.264 | H.265 |
|---|---|---|
| Max block size | 16×16 (macroblock) | 64×64 (CTU) |
| Transform sizes | 4×4, 8×8 | 4×4, 8×8, 16×16, 32×32 |
| Prediction modes | 9 angular | 35 angular |
| Entropy coding | CABAC/CAVLC | CABAC only |
| Motion vectors | Quarter-pel | Quarter-pel + advanced merge |

At 5600 kbps, H.265 at 1024×576 looks like H.264 at ~800×448. Free resolution upgrade.

## AVBR (Adaptive Variable Bitrate)

The SSC338Q hardware encoder (Sigmastar MI VPE) supports several rate control modes:

### CBR (Constant Bitrate)
- Fixed bitrate regardless of scene complexity
- Wastes bits on static scenes (blue sky)
- May not allocate enough for complex motion
- Predictable network load

### VBR (Variable Bitrate)
- Varies bitrate based on complexity
- Can exceed the WiFi ceiling during fast motion
- Best for recording, worst for FPV link

### AVBR (Adaptive VBR) ★ Our choice
- Targets bitrate with intelligent adaptation
- Allocates more bits to complex frames (fast motion)
- Uses fewer bits for simple frames (hovering, blue sky)
- Stays within maxBitrate ceiling
- statTime parameter controls adaptation window

### AVBR Parameters

```yaml
bitrate: 5600      # Target average bitrate (kbps)
maxBitrate: 6000   # Hard ceiling — never exceed this
minQp: 20          # Minimum QP (highest quality allowed)
maxQp: 42          # Maximum QP (lowest quality during motion)
statTime: 2        # Adaptation window in seconds
```

**minQp = 20**: Prevents wasting bits on already-perfect quality. Without this, static scenes might use QP 16-18, consuming bitrate budget with imperceptible quality gain.

**maxQp = 42**: Allows the encoder to degrade gracefully during extreme motion rather than exceeding the bitrate ceiling. At QP 42 with H.265, quality is still watchable.

**statTime = 2**: The encoder measures average bitrate over a 2-second window. Shorter windows react faster to scene changes but may oscillate. Longer windows smooth things out but respond slower.

## GOP (Group of Pictures)

GOP = 30 means one I-frame every 30 frames (1 second at 30 FPS).

```
Frame sequence: I P P P P P P P P P P P P P P ... P P P P I P P P ...
                └─────────── 30 frames (1 second) ──────────┘
```

### I-frames
- Full image, self-contained
- Large (typically 3-5× P-frame size)
- Required for stream recovery after packet loss

### P-frames
- Only encode differences from previous frame
- Much smaller
- Cannot be decoded without previous frames

### GOP tradeoffs

| GOP | I-frame frequency | Compression | Recovery time |
|---|---|---|---|
| 1 | Every frame | Terrible (3-5× bitrate) | Instant |
| 15 | Every 0.5s | Good | 0.5s |
| 30 | Every 1.0s | Better | 1.0s |
| 60 | Every 2.0s | Best | 2.0s |

For FPV with wfb-ng, GOP=30 is the sweet spot because:
- wfb-ng can request IDR (instant recovery) frames
- Lower GOP wastes too much budget on I-frames
- Higher GOP means longer recovery after signal loss

## High Profile

H.265 profiles control which encoding tools are available:

| Profile | Features | Compression |
|---|---|---|
| Main | Basic CTU, 8-bit | Baseline |
| **High** | 8×8 transform, better intra prediction | **+10-15%** |
| Main 10 | 10-bit depth | +5% (not needed for FPV) |

High Profile enables **8×8 transform blocks** which:
- Better represent sharp edges and fine textures
- Improve compression of smooth gradients (sky, water)
- Are free in terms of decode complexity on SSC338Q

## CABAC Entropy Coding

H.265 exclusively uses CABAC (Context-Adaptive Binary Arithmetic Coding), which provides ~15% better compression than CAVLC (used optionally in H.264).

This is a free win — SSC338Q hardware encoder always uses CABAC for H.265.