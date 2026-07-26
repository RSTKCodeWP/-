# Out-of-context (OOC) synthesis + sizing for the Block-3 seeker PL blocks.
# Part = the BoChen ZYNQ MINI's XC7Z020-CLG400. Needs NO board files / XSA — just the part — so it
# answers "do the blocks fit the -020 and how fast can they clock?" without the vendor BSP or a
# top-level. This is a SIZING/timing scaffold; it does NOT build a bitstream (the synthesizable
# streaming top-level with line buffers is still to be written — see BRINGUP.md §3).
#
#   vivado -mode batch -source fpga/vivado/ooc_synth.tcl
#
# Reports land in fpga/vivado/ooc_reports/<block>_{util,timing}.rpt.
# NOTE (honest): the frame-addressed behavioural blocks (morph_tophat, ccl) infer large BRAMs and a
# behavioural divider; OOC still gives a valid utilisation/timing estimate, but the *fielded*
# streaming versions (line buffers, divider IP) will size differently. Treat these as upper-bound-ish
# ball-parks, not the final resource budget.

set PART      xc7z020clg400-1
set HERE      [file normalize [file dirname [info script]]]
set RTL       [file normalize $HERE/../rtl]
set OUT       $HERE/ooc_reports
set PERIOD_NS 6.0    ;# 166 MHz target clock — adjust to your real pixel/compute clock
file mkdir $OUT

# leaf blocks that make up the PL detect front-end
set BLOCKS {bt656_rx centroid_dp morph_tophat hist ccl}

foreach blk $BLOCKS {
    puts "==================== OOC synth: $blk ===================="
    read_verilog -sv [file join $RTL $blk.v]
    synth_design -top $blk -part $PART -mode out_of_context
    if {[llength [get_ports -quiet clk]] > 0} {
        create_clock -name clk -period $PERIOD_NS [get_ports clk]
    }
    report_utilization    -file [file join $OUT ${blk}_util.rpt]
    report_timing_summary -file [file join $OUT ${blk}_timing.rpt]
    set wns [get_property -quiet SLACK [get_timing_paths -quiet -max_paths 1 -nworst 1 -setup]]
    puts "  $blk : util -> ${blk}_util.rpt ; setup WNS = $wns ns (target ${PERIOD_NS} ns)"
}
puts "OOC sizing done -> $OUT"
