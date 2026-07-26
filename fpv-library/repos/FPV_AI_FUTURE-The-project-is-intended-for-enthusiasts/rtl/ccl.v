// ccl.v -- 4-connected connected-components labeller (Block-3 PL detect front-end, M0).
//
// Labels a binary mask (top-hat > threshold) so the per-component bbox/area feed the centroid.
// _connected_components uses 4-connectivity; the component SET is what matters (the label integers
// are arbitrary), so this uses iterative min-label propagation: each foreground pixel starts with a
// unique label (raster index+1), then relaxes to the MIN label among its 4-connected foreground
// neighbours via alternating forward/backward Gauss-Seidel sweeps until a full round makes no
// change.  Each component ends labelled by the minimum initial index in it -- the same GROUPING as
// the software CCL (verified: same partition + same bbox/area), just different label numbers.
//
// Frame-addressed, one pixel per sweep-cycle; converges in a few rounds for compact blobs.  A fielded
// high-throughput CCL uses single-pass union-find; the grouping is identical.
//
// Verified by fpga/rtl/test_ccl_rtl.py against fpv.seeker.detect._connected_components.

`timescale 1ns/1ps

module ccl #(
    parameter integer W  = 32,
    parameter integer H  = 32,
    parameter integer LW = 12       // label width; must hold W*H
) (
    input  wire clk,
    input  wire start,
    output reg  done
);
    localparam integer N = W * H;

    reg           mask_mem  [0:N-1];   // 1-bit input mask (loaded by the testbench)
    reg [LW-1:0]  label_mem [0:N-1];   // component labels (read back by the testbench)

    localparam [2:0] S_IDLE=0, S_INIT=1, S_FWD=2, S_BWD=3, S_CHK=4, S_DONE=5;
    reg [2:0]  state;
    integer    i, row, col, idx;
    reg        changed;
    reg [LW-1:0] cand, nl;

    initial begin state = S_IDLE; done = 1'b0; end

    always @(posedge clk) begin
        case (state)
            S_IDLE: if (start) begin i = 0; done = 1'b0; state = S_INIT; end

            // unique seed label per foreground pixel (index+1); background = 0
            S_INIT: begin
                label_mem[i] = mask_mem[i] ? (i + 1) : 0;
                if (i == N-1) begin row = 0; col = 0; changed = 1'b0; state = S_FWD; end
                else i = i + 1;
            end

            // forward sweep: relax to min(self, up, left) over foreground
            S_FWD: begin
                idx = row*W + col;
                if (label_mem[idx] != 0) begin
                    cand = label_mem[idx];
                    if (row > 0) begin nl = label_mem[idx-W]; if (nl != 0 && nl < cand) cand = nl; end
                    if (col > 0) begin nl = label_mem[idx-1]; if (nl != 0 && nl < cand) cand = nl; end
                    if (cand != label_mem[idx]) begin label_mem[idx] = cand; changed = 1'b1; end
                end
                if (col == W-1) begin
                    col = 0;
                    if (row == H-1) begin row = H-1; col = W-1; state = S_BWD; end
                    else row = row + 1;
                end else col = col + 1;
            end

            // backward sweep: relax to min(self, down, right) over foreground
            S_BWD: begin
                idx = row*W + col;
                if (label_mem[idx] != 0) begin
                    cand = label_mem[idx];
                    if (row < H-1) begin nl = label_mem[idx+W]; if (nl != 0 && nl < cand) cand = nl; end
                    if (col < W-1) begin nl = label_mem[idx+1]; if (nl != 0 && nl < cand) cand = nl; end
                    if (cand != label_mem[idx]) begin label_mem[idx] = cand; changed = 1'b1; end
                end
                if (col == 0) begin
                    col = W-1;
                    if (row == 0) state = S_CHK;
                    else row = row - 1;
                end else col = col - 1;
            end

            S_CHK: if (changed) begin changed = 1'b0; row = 0; col = 0; state = S_FWD; end
                   else begin done = 1'b1; state = S_DONE; end

            S_DONE: ;
        endcase
    end
endmodule
