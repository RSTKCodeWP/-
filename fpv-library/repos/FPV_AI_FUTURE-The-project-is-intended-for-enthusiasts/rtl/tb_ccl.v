// tb_ccl.v -- loads a binary mask, runs the labeller, prints each foreground pixel's label.
// Reads "mask.txt" (W*H bits, row-major) from the run cwd; prints "L <idx> <label>".

`timescale 1ns/1ps

module tb_ccl;
    localparam integer W = 32, H = 32, LW = 12, N = W*H;

    reg  clk = 1'b0, start = 1'b0;
    wire done;

    ccl #(.W(W), .H(H), .LW(LW)) dut (.clk(clk), .start(start), .done(done));

    always #5 clk = ~clk;

    integer i;
    initial begin
        $readmemb("mask.txt", dut.mask_mem);

        @(negedge clk); start = 1'b1;
        @(negedge clk); start = 1'b0;
        wait (done == 1'b1);

        for (i = 0; i < N; i = i + 1)
            if (dut.label_mem[i] != 0) $display("L %0d %0d", i, dut.label_mem[i]);
        $finish;
    end
endmodule
