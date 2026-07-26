// centroid_dp.v -- fixed-point intensity-weighted centroid datapath (Block-3 PL detect IP, M0).
//
// Streams the pixels of ONE connected component (x, y, weight) and, on `last`, emits the
// intensity-weighted centroid in fixed-point:
//
//     cx_fixed = floor( (Sum x*w << F) / Sum w )      // = cx * 2^F
//     cy_fixed = floor( (Sum y*w << F) / Sum w )      // = cy * 2^F
//
// This is the exact fixed-point model characterised in Python (fpga/ref_model/fixed_point.py):
// the moment sums are EXACT integers; the only quantiser is the final divide, which keeps F
// fractional bits with truncation.  The accumulators are sized from the golden-vector study
// (Sum x*w <= ~23 bits, Sum w <= ~15 bits) -- ACC=48 is comfortable headroom.
//
// Verified bit-exactly against the Python reference by fpga/rtl/test_centroid_dp_rtl.py, which
// drives real detected blobs from the golden scenes through this module and compares cx/cy/den.
//
// Note: behavioural `/` stands in for a divider IP; the NUMERICS (floor of the fixed-point
// quotient) are what the co-sim verifies and what synthesis must reproduce.

`timescale 1ns/1ps

module centroid_dp #(
    parameter integer XW  = 16,   // x / y pixel-coordinate width (720x480 -> 10 bits, 16 is safe)
    parameter integer WW  = 16,   // weight width (background-subtracted count)
    parameter integer ACC = 48,   // moment-accumulator width
    parameter integer F   = 8     // fractional bits kept in the output centroid
) (
    input  wire            clk,
    input  wire            rst,        // synchronous reset: clears the accumulators (start of blob)
    input  wire            valid,      // a component pixel is presented this cycle
    input  wire [XW-1:0]   x,
    input  wire [XW-1:0]   y,
    input  wire [WW-1:0]   w,
    input  wire            last,       // asserted with the final pixel of the component
    output reg             out_valid,  // cx_fixed/cy_fixed/den_out valid this cycle
    output reg  [ACC-1:0]  cx_fixed,   // cx * 2^F  (floor)
    output reg  [ACC-1:0]  cy_fixed,   // cy * 2^F  (floor)
    output reg  [ACC-1:0]  den_out     // Sum w
);
    reg [ACC-1:0] num_x, num_y, den;

    // Combinational next-sums so the `last` pixel is included before the divide.
    wire [ACC-1:0] nx = num_x + (x * w);
    wire [ACC-1:0] ny = num_y + (y * w);
    wire [ACC-1:0] nd = den   + w;

    always @(posedge clk) begin
        if (rst) begin
            num_x     <= {ACC{1'b0}};
            num_y     <= {ACC{1'b0}};
            den       <= {ACC{1'b0}};
            out_valid <= 1'b0;
        end else begin
            out_valid <= 1'b0;
            if (valid) begin
                if (last) begin
                    cx_fixed  <= (nd == 0) ? {ACC{1'b0}} : ((nx << F) / nd);
                    cy_fixed  <= (nd == 0) ? {ACC{1'b0}} : ((ny << F) / nd);
                    den_out   <= nd;
                    out_valid <= 1'b1;
                    num_x     <= {ACC{1'b0}};   // auto-clear for the next component
                    num_y     <= {ACC{1'b0}};
                    den       <= {ACC{1'b0}};
                end else begin
                    num_x <= nx;
                    num_y <= ny;
                    den   <= nd;
                end
            end
        end
    end
endmodule
