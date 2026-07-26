// tb_morph_tophat_stream.v -- stream a frame through morph_tophat_stream, dump interior "TH y x v".
//
// Reads "frame.hex" + "se.txt" from cwd, streams the frame one pixel/clock, loads the SE into both
// win_reduce stages, and prints each emitted top-hat center. The Python co-sim compares against
// fpv.seeker.detect._white_tophat (the same golden as the frame-addressed morph_tophat.v).

`timescale 1ns/1ps

module tb_morph_tophat_stream;
    localparam integer W = 32, H = 32, D = 11;

    reg         clk = 1'b0, rst = 1'b1, in_valid = 1'b0;
    reg  [15:0] in_data = 16'd0;
    wire        out_valid;
    wire [15:0] out_data, out_x, out_y;

    morph_tophat_stream #(.W(W), .H(H), .D(D)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_data(in_data),
        .out_valid(out_valid), .out_data(out_data), .out_x(out_x), .out_y(out_y));

    always #5 clk = ~clk;

    reg [15:0] frame [0:W*H-1];
    integer idx;
    initial begin
        $readmemh("frame.hex", frame);
        $readmemb("se.txt",    dut.e.se);
        $readmemb("se.txt",    dut.d.se);

        @(negedge clk); rst = 1'b0;
        for (idx = 0; idx < W*H; idx = idx + 1) begin
            @(negedge clk); in_valid = 1'b1; in_data = frame[idx];
        end
        @(negedge clk); in_valid = 1'b0;
        repeat (8) @(negedge clk);
        $finish;
    end

    always @(negedge clk)
        if (out_valid) $display("TH %0d %0d %0d", out_y, out_x, out_data);
endmodule
