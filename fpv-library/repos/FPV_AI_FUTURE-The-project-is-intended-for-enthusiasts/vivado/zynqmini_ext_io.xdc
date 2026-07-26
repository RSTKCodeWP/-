# ── BoChen ZYNQ MINI (XC7Z020-CLG400) — EXT IO 3.3V header: BT.656 ingest pin TEMPLATE ──────────────
#
# Maps the CVBS→BT.656 decoder (TVP5150/ADV7280) interface onto the board's `EXT IO 3.3V` PL header
# for the streaming detect front-end (bt656_rx.v ingests the 8-bit BT.656 byte stream; sync is
# embedded, so no separate HSYNC/VSYNC is needed). I2C configures the decoder.
#
# ‼️ THIS IS A TEMPLATE — DO NOT WIRE/BUILD FROM IT UNVERIFIED.
#   * Pin names are transcribed from the REV-B silk PHOTO (see fpga/BRINGUP_ZYNQMINI_BOCHEN.md §4) and
#     MAY contain read errors (e.g. a duplicated "P15"). Verify every PACKAGE_PIN against the vendor
#     pinout/XSA before committing hardware or a bitstream.
#   * The PS clock / DDR / MIO / HDMI constraints come from the vendor XSA, NOT this file. This XDC
#     only constrains the PL EXT-IO ingest pins added for the seeker.
#   * Bind these port names to the future synthesizable streaming top-level (not the per-block cores).
#
# All EXT IO pins are 3.3 V CMOS.
set_property IOSTANDARD LVCMOS33 [get_ports -filter {NAME =~ *}]

# ── pixel clock from the decoder (BT.656 = 27 MHz) ───────────────────────────────────────────────
set_property PACKAGE_PIN P15 [get_ports pclk]
create_clock -name pclk -period 37.037 [get_ports pclk]   ;# 27 MHz

# ── 8-bit BT.656 data bus ────────────────────────────────────────────────────────────────────────
set_property PACKAGE_PIN U15 [get_ports {bt656_data[0]}]
set_property PACKAGE_PIN V15 [get_ports {bt656_data[1]}]
set_property PACKAGE_PIN W15 [get_ports {bt656_data[2]}]
set_property PACKAGE_PIN V17 [get_ports {bt656_data[3]}]
set_property PACKAGE_PIN U17 [get_ports {bt656_data[4]}]
set_property PACKAGE_PIN Y18 [get_ports {bt656_data[5]}]
set_property PACKAGE_PIN V18 [get_ports {bt656_data[6]}]
set_property PACKAGE_PIN Y19 [get_ports {bt656_data[7]}]

# ── I2C to the decoder (config: standard/format, output mode) ────────────────────────────────────
set_property PACKAGE_PIN W18 [get_ports i2c_scl]
set_property PACKAGE_PIN W19 [get_ports i2c_sda]

# Input-delay budgeting for the source-synchronous BT.656 bus (pclk-relative) is left to the fielded
# top-level once real board trace/decoder Tco numbers are known; add set_input_delay there.
