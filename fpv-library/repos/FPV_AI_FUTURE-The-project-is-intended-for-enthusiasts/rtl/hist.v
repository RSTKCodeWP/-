// hist.v -- streaming histogram accumulator for the adaptive threshold (Block-3 PL, M0).
//
// The per-frame threshold statistics (percentile + MAD + iterative sigma-clip) are once-per-frame,
// control-flow-heavy float math -> they belong on the PS (ARM, in C: fpga/ps/threshold_stats).  The
// PER-PIXEL part that must run in the fabric is building the histogram of top-hat values, which is
// what this block does: on `start` it clears the histbin, then accumulates one value per clock.  The
// PS reads the histbin out and computes the threshold.
//
// (Reg-array model: back-to-back same-bin increments are correct here because the nonblocking write
//  commits before the next clock's read; a true BRAM implementation adds a 1-cycle RMW bypass.)
//
// Verified by fpga/rtl/test_hist_rtl.py: RTL histbin == numpy bincount of the top-hat, bit-exact.

`timescale 1ns/1ps

module hist #(
    parameter integer NBINS = 2048,   // one bin per integer top-hat value (clamp above)
    parameter integer CW    = 20      // bin-counter width
) (
    input  wire        clk,
    input  wire        start,         // pulse: clear the histbin, then raise `ready`
    output reg         ready,         // high once cleared -> accumulation may proceed
    input  wire        valid,         // accumulate `val` this cycle (when ready)
    input  wire [15:0] val
);
    reg [CW-1:0] histbin [0:NBINS-1];
    reg          clearing;
    integer      caddr, idx;

    initial begin ready = 1'b0; clearing = 1'b0; caddr = 0; end

    always @(posedge clk) begin
        if (start) begin
            clearing <= 1'b1; ready <= 1'b0; caddr <= 0;
        end else if (clearing) begin
            histbin[caddr] <= {CW{1'b0}};
            if (caddr == NBINS - 1) begin clearing <= 1'b0; ready <= 1'b1; caddr <= 0; end
            else caddr <= caddr + 1;
        end else if (ready && valid) begin
            idx = (val >= NBINS) ? (NBINS - 1) : val;   // clamp out-of-range into the top bin
            histbin[idx] <= histbin[idx] + 1'b1;
        end
    end
endmodule
