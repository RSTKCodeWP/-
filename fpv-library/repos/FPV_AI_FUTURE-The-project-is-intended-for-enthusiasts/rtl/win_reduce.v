// win_reduce.v -- streaming line-buffered windowed min/max (Block-3 PL, synthesis-oriented morphology).
//
// The frame-addressed `morph_tophat.v` re-reads a D*D footprint per output pixel from a frame BRAM.
// This block is the FIELDED form: pixels stream in raster order (one per `in_valid`), (D-1) line
// buffers + a D*D sliding window are maintained, and one SE-masked reduce (min for erode, max for
// dilate) is emitted per interior center. No frame-sized address sweep -- true line-buffer streaming.
//
//   MAXOP = 0 -> min over the SE window  (erode)
//   MAXOP = 1 -> max over the SE window  (dilate)
//
// Emits `out_valid` with the reduced value + the CENTER coords (out_y,out_x) for every fully-inside
// window, i.e. centers in [R, H-1-R] x [R, W-1-R] (raster order). The interior stream it produces is
// itself a clean (H-2R)x(W-2R) raster image -- so two of these chain (erode -> dilate) to form an
// opening, with the second instance parameterised W2=W-2R, H2=H-2R.
//
// SE (`se`, row-major D*D bits) is loaded by the testbench (same convention as morph_tophat). Integer
// min/max only -- no quantisation, bit-exact to the software erode/dilate on the interior.

`timescale 1ns/1ps

module win_reduce #(
    parameter integer W     = 32,
    parameter integer H     = 32,
    parameter integer D     = 11,          // SE diameter (odd)
    parameter integer MAXOP = 0            // 0 = min (erode), 1 = max (dilate)
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        in_valid,
    input  wire [15:0] in_data,
    output reg         out_valid,
    output reg  [15:0] out_data,
    output reg  [15:0] out_x,              // center column (0..W-1)
    output reg  [15:0] out_y               // center row    (0..H-1)
);
    localparam integer R = D / 2;

    reg  [15:0] lb  [0:D-2][0:W-1];        // D-1 line buffers (previous rows)
    reg  [15:0] win [0:D*D-1];             // D x D sliding window (row-major, r=0 top / c=0 left)
    reg         se  [0:D*D-1];             // SE footprint, loaded by the tb ($readmemb)

    integer in_x, in_y;                    // coords of the pixel arriving this in_valid
    integer r, c, k, i;
    reg [15:0] col [0:D-1];                // the fresh column at in_x: col[D-1]=current row pixel
    reg [15:0] red;

    initial begin
        in_x = 0; in_y = 0; out_valid = 1'b0; out_x = 0; out_y = 0; out_data = 0;
    end

    // Output registers are NON-BLOCKING so downstream @(posedge) blocks (the cascaded stage and the
    // subtract) read a stable, race-free value; the internal window/line-buffers/counters stay blocking
    // (read within this same block on the cycle they are written).
    always @(posedge clk) begin
        if (rst) begin
            in_x = 0; in_y = 0; out_valid <= 1'b0;
        end else begin
            out_valid <= 1'b0;
            if (in_valid) begin
                // 1) fresh column at column in_x: top = oldest kept row ... bottom = current pixel
                for (r = 0; r < D-1; r = r + 1) col[r] = lb[r][in_x];
                col[D-1] = in_data;

                // 2) shift the window left, insert the fresh column at the rightmost column
                for (r = 0; r < D; r = r + 1) begin
                    for (c = 0; c < D-1; c = c + 1) win[r*D + c] = win[r*D + c + 1];
                    win[r*D + (D-1)] = col[r];
                end

                // 3) scroll the line buffers at this column (drop oldest row, push current pixel)
                for (k = 0; k < D-2; k = k + 1) lb[k][in_x] = lb[k+1][in_x];
                lb[D-2][in_x] = in_data;

                // 4) SE-masked reduce over the window (now spanning rows/cols [in_y-(D-1)..in_y] etc.)
                red = (MAXOP != 0) ? 16'h0000 : 16'hFFFF;
                for (i = 0; i < D*D; i = i + 1)
                    if (se[i]) begin
                        if (MAXOP != 0) begin if (win[i] > red) red = win[i]; end
                        else            begin if (win[i] < red) red = win[i]; end
                    end

                // 5) emit for a fully-inside window -> center at (in_y-R, in_x-R)
                if (in_x >= D-1 && in_y >= D-1) begin
                    out_valid <= 1'b1;
                    out_data  <= red;
                    out_y     <= in_y - R;
                    out_x     <= in_x - R;
                end

                // 6) advance raster coords
                if (in_x == W-1) begin in_x = 0; in_y = in_y + 1; end
                else in_x = in_x + 1;
            end
        end
    end
endmodule
