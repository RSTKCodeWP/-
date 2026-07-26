// morph_tophat_stream.v -- streaming white top-hat (Block-3 PL, synthesis-oriented; fielded form).
//
//   tophat = f - opening(f),   opening = dilate(erode(f, SE), SE)
//
// The fielded replacement for the frame-addressed morph_tophat.v: two cascaded streaming
// line-buffer windowed reduces (win_reduce: erode=min then dilate=max), plus a frame buffer that
// holds f for the final subtract. Pixels stream in raster order (one per in_valid); the opening
// emerges from the dilate stage on the margin-2R interior, aligned to f by coordinates, and
// tophat = f - opening is emitted with its center coords.
//
// Geometry: erode emits the [R,H-1-R]x[R,W-1-R] interior as a clean (H-2R)x(W-2R) raster; the dilate
// stage consumes that sub-image (W2=W-2R, H2=H-2R) and emits opening on sub-centers [R,H2-1-R], i.e.
// original coords [2R,H-1-2R] -- exactly the golden region. original = (d.center + R).
//
// Verified by fpga/rtl/test_morph_tophat_stream.py against fpv.seeker.detect._white_tophat, byte-exact
// on the interior (same golden the frame-addressed morph_tophat.v is checked against).

`timescale 1ns/1ps

module morph_tophat_stream #(
    parameter integer W = 32,
    parameter integer H = 32,
    parameter integer D = 11
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        in_valid,
    input  wire [15:0] in_data,
    output reg         out_valid,
    output reg  [15:0] out_data,
    output reg  [15:0] out_x,
    output reg  [15:0] out_y
);
    localparam integer R  = D / 2;
    localparam integer W2 = W - 2*R;
    localparam integer H2 = H - 2*R;

    reg [15:0] f_mem [0:W*H-1];       // frame buffer for the subtract (f - opening)
    integer    wr;

    // stage E -- erode (min) over the full frame
    wire        e_v; wire [15:0] e_d, e_x, e_y;
    win_reduce #(.W(W), .H(H), .D(D), .MAXOP(0)) e (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_data(in_data),
        .out_valid(e_v), .out_data(e_d), .out_x(e_x), .out_y(e_y));

    // stage D -- dilate (max) over the erode sub-image (W2 x H2)
    wire        d_v; wire [15:0] d_d, d_x, d_y;
    win_reduce #(.W(W2), .H(H2), .D(D), .MAXOP(1)) d (
        .clk(clk), .rst(rst), .in_valid(e_v), .in_data(e_d),
        .out_valid(d_v), .out_data(d_d), .out_x(d_x), .out_y(d_y));

    integer oy, ox;
    initial begin wr = 0; out_valid = 1'b0; out_x = 0; out_y = 0; out_data = 0; end

    // Output regs are NON-BLOCKING so a downstream @(posedge) reader (e.g. detect_frontend_top's
    // capture) samples them race-free; the frame buffer / counter stay blocking (local to this block).
    always @(posedge clk) begin
        if (rst) begin
            wr = 0; out_valid <= 1'b0;
        end else begin
            if (in_valid) begin                       // capture f for the subtract
                f_mem[wr] = in_data;
                if (wr != W*H - 1) wr = wr + 1;
            end
            out_valid <= 1'b0;
            if (d_v) begin                            // opening ready -> tophat = f - opening
                oy = d_y + R; ox = d_x + R;           // dilate sub-center -> original coords
                out_data  <= f_mem[oy*W + ox] - d_d;
                out_y <= oy; out_x <= ox; out_valid <= 1'b1;
            end
        end
    end
endmodule
