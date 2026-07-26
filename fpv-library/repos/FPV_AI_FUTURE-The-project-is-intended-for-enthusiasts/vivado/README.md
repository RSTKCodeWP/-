# fpga/vivado/ — Vivado bring-up scaffolds (BoChen ZYNQ MINI, XC7Z020-CLG400)

Turnkey scaffolds for the Vivado stage. **None of this is validated on this dev machine** (no Vivado
here — only iverilog/clang co-sim). Run on a Vivado box; treat as starting points, not finished flow.

| File | What | Status |
|------|------|--------|
| `ooc_synth.tcl` | Out-of-context synthesis + utilisation/timing of each PL block on `xc7z020clg400-1`. Answers "do the blocks fit the -020 and how fast do they clock?" — no board/XSA needed. | scaffold, unrun here |
| `zynqmini_ext_io.xdc` | Pin **template** mapping the CVBS→BT.656 decoder bus (pclk + 8 data + I2C) onto the `EXT IO 3.3V` header. | template — **verify pins vs vendor pinout** |

## Honest scope / what's still required
- **No bitstream yet.** The blocks are verified *individually* and now *composed in co-sim*
  (`../rtl/test_frontend_integration.py`), but a **synthesizable streaming top-level** (line buffers
  around the windowed stages + AXI-Stream, divider IP for the centroid) is still to be written — see
  `../BRINGUP.md` §3. `ooc_synth.tcl` sizes the leaf blocks; it does not implement a design.
- **Vendor XSA needed** for PS DDR/MIO/clock/HDMI. This XDC only constrains the PL ingest pins.
- **Pinout is photo-transcribed** (`../BRINGUP_ZYNQMINI_BOCHEN.md` §4) and may have errors — verify
  every `PACKAGE_PIN` against the vendor silk/pinout before wiring or building.

## Order of use
1. `vivado -mode batch -source ooc_synth.tcl` → read `ooc_reports/*_util.rpt` and confirm LUT/FF/BRAM/DSP
   fit the XC7Z020 (53k LUT, 220 DSP, 4.9 Mb BRAM) and setup WNS ≥ 0 at your target clock.
2. Write the streaming top-level (golden = the Python `detect_frame`; keep the co-sim green).
3. Fix the real EXT-IO pins in `zynqmini_ext_io.xdc` from the vendor pinout; add `set_input_delay`.
4. Integrate the vendor XSA (PS) + this PL, build the bitstream, bring up per `../BRINGUP.md`.
