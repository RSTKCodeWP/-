// tb_ccl_stream.v -- stream a binary mask through ccl_stream, print each fg pixel's final label.
// Reads "mask.txt" (W*H bits, row-major) from cwd, streams one bit/clock, waits for done, prints
// "L <idx> <label>". The Python co-sim groups by label and compares to _connected_components.

`timescale 1ns/1ps

module tb_ccl_stream;
    localparam integer W = 32, H = 32, LW = 12, N = W*H;

    reg  clk = 1'b0, rst = 1'b1, in_valid = 1'b0, in_data = 1'b0;
    wire done;

    ccl_stream #(.W(W), .H(H), .LW(LW)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_data(in_data), .done(done));

    always #5 clk = ~clk;

    reg mask [0:N-1];
    integer i;
    initial begin
        $readmemb("mask.txt", mask);

        @(negedge clk); rst = 1'b0;
        for (i = 0; i < N; i = i + 1) begin
            @(negedge clk); in_valid = 1'b1; in_data = mask[i];
        end
        @(negedge clk); in_valid = 1'b0;
        wait (done == 1'b1);

        for (i = 0; i < N; i = i + 1)
            if (dut.label_mem[i] != 0) $display("L %0d %0d", i, dut.label_mem[i]);
        $finish;
    end
endmodule
