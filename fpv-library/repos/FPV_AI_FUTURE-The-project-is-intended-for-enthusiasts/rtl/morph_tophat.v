// morph_tophat.v -- white top-hat morphology engine (Block-3 PL detect front-end, M0 middle).
//
//   tophat = f - opening(f) ,   opening = dilate(erode(f, SE), SE)
//
// SE is the 11x11 cv2 MORPH_ELLIPSE footprint (loaded identically to the software detector, so the
// numerics match by construction).  The fixed-point study proved this stage is INTEGER-EXACT
// (erode = min, dilate = max over integer counts), so there is no quantisation -- only the min/max.
//
// This is a frame-addressed engine (BRAM in / BRAM out, one footprint tap per clock): it computes
// erode into erode_mem, then dilate into open_mem, then tophat = f - open.  It is a faithful,
// bit-exact model of the datapath; a fielded high-throughput version replaces the frame BRAM +
// address sweep with line buffers + a sliding window (same min/max numerics).  Border pixels are
// left uncomputed: the co-sim verifies the margin-2R interior, where the window is fully inside the
// frame (border policy irrelevant) and where the target always sits.
//
// Verified by fpga/rtl/test_morph_tophat.py against fpv.seeker.detect._white_tophat, byte-exact.

`timescale 1ns/1ps

module morph_tophat #(
    parameter integer W = 32,
    parameter integer H = 32,
    parameter integer D = 11          // SE diameter (odd)
) (
    input  wire clk,
    input  wire start,
    output reg  done
);
    localparam integer R = D / 2;     // SE radius (5 for D=11)
    localparam integer N = W * H;

    reg [15:0] frame_mem  [0:N-1];    // input  (loaded by the testbench)
    reg [15:0] erode_mem  [0:N-1];    // erode(f)
    reg [15:0] open_mem   [0:N-1];    // dilate(erode(f)) = opening
    reg [15:0] tophat_mem [0:N-1];    // f - opening   (read back by the testbench)
    reg        se         [0:D*D-1];  // 11x11 ellipse footprint (row-major, loaded by the testbench)

    localparam [2:0] S_IDLE = 3'd0, S_ERODE = 3'd1, S_DILATE = 3'd2, S_SUB = 3'd3, S_DONE = 3'd4;
    reg  [2:0] state;
    integer    oy, ox, ddy, ddx, seidx;
    reg [15:0] acc, tapv;

    initial begin state = S_IDLE; done = 1'b0; end

    always @(posedge clk) begin
        case (state)
            S_IDLE: if (start) begin
                oy = R; ox = R; ddy = 0; ddx = 0; acc = 16'hFFFF; done = 1'b0; state = S_ERODE;
            end

            // ---- erode: min over the SE footprint, region [R, W-1-R] x [R, H-1-R] ----
            S_ERODE: begin
                seidx = ddy * D + ddx;
                if (se[seidx]) begin
                    tapv = frame_mem[(oy + ddy - R) * W + (ox + ddx - R)];
                    if (tapv < acc) acc = tapv;
                end
                if (ddx == D - 1) begin
                    ddx = 0;
                    if (ddy == D - 1) begin
                        ddy = 0;
                        erode_mem[oy * W + ox] = acc;
                        acc = 16'hFFFF;
                        if (ox == W - 1 - R) begin
                            ox = R;
                            if (oy == H - 1 - R) begin oy = 2*R; ox = 2*R; acc = 16'h0; state = S_DILATE; end
                            else oy = oy + 1;
                        end else ox = ox + 1;
                    end else ddy = ddy + 1;
                end else ddx = ddx + 1;
            end

            // ---- dilate: max over the SE footprint of erode, region [2R, W-1-2R] x [2R, H-1-2R] ----
            S_DILATE: begin
                seidx = ddy * D + ddx;
                if (se[seidx]) begin
                    tapv = erode_mem[(oy + ddy - R) * W + (ox + ddx - R)];
                    if (tapv > acc) acc = tapv;
                end
                if (ddx == D - 1) begin
                    ddx = 0;
                    if (ddy == D - 1) begin
                        ddy = 0;
                        open_mem[oy * W + ox] = acc;
                        acc = 16'h0;
                        if (ox == W - 1 - 2*R) begin
                            ox = 2*R;
                            if (oy == H - 1 - 2*R) begin oy = 2*R; ox = 2*R; state = S_SUB; end
                            else oy = oy + 1;
                        end else ox = ox + 1;
                    end else ddy = ddy + 1;
                end else ddx = ddx + 1;
            end

            // ---- subtract: tophat = f - opening (>=0 since opening is anti-extensive) ----
            S_SUB: begin
                tophat_mem[oy * W + ox] = frame_mem[oy * W + ox] - open_mem[oy * W + ox];
                if (ox == W - 1 - 2*R) begin
                    ox = 2*R;
                    if (oy == H - 1 - 2*R) begin state = S_DONE; done = 1'b1; end
                    else oy = oy + 1;
                end else ox = ox + 1;
            end

            S_DONE: ;   // hold
        endcase
    end
endmodule
