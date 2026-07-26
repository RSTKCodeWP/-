// tb_win_reduce.v -- stream a frame through win_reduce, dump the interior reduce as "R <y> <x> <v>".
//
// Reads "frame.hex" (W*H hex uint16, row-major) + "se.txt" (D*D bits) from cwd, streams the frame
// one pixel per clock (raster), and prints each emitted center. Compile with -DMAXOP for max (dilate);
// default is min (erode). The Python co-sim compares against a numpy erode/dilate over the SE.

`timescale 1ns/1ps

module tb_win_reduce;
    localparam integer W = 32, H = 32, D = 11, R = 5;
`ifdef MAXOP
    localparam integer MAXOP_VAL = 1;
`else
    localparam integer MAXOP_VAL = 0;
`endif

    reg         clk = 1'b0, rst = 1'b1, in_valid = 1'b0;
    reg  [15:0] in_data = 16'd0;
    wire        out_valid;
    wire [15:0] out_data, out_x, out_y;

    win_reduce #(.W(W), .H(H), .D(D), .MAXOP(MAXOP_VAL)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_data(in_data),
        .out_valid(out_valid), .out_data(out_data), .out_x(out_x), .out_y(out_y));

    always #5 clk = ~clk;

    reg [15:0] frame [0:W*H-1];
    integer idx;
    initial begin
        $readmemh("frame.hex", frame);
        $readmemb("se.txt",    dut.se);

        @(negedge clk); rst = 1'b0;
        for (idx = 0; idx < W*H; idx = idx + 1) begin
            @(negedge clk); in_valid = 1'b1; in_data = frame[idx];
        end
        @(negedge clk); in_valid = 1'b0;
        repeat (4) @(negedge clk);
        $finish;
    end

    // sample at negedge so the posedge-updated out_valid is stable (no race with the DUT block)
    always @(negedge clk)
        if (out_valid) $display("R %0d %0d %0d", out_y, out_x, out_data);
endmodule
