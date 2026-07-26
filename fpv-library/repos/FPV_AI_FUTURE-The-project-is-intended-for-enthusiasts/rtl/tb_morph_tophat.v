// tb_morph_tophat.v -- loads a frame + SE, runs the morphology engine, dumps the interior top-hat.
//
// Reads "frame.hex" (W*H hex uint16, row-major) and "se.txt" (D*D bits) from the run cwd, pulses
// start, waits for done, then prints "TH <y> <x> <val>" for the margin-2R interior.  The Python
// co-sim compares those against fpv.seeker.detect._white_tophat.

`timescale 1ns/1ps

module tb_morph_tophat;
    localparam integer W = 32, H = 32, D = 11, R = 5;

    reg  clk = 1'b0, start = 1'b0;
    wire done;

    morph_tophat #(.W(W), .H(H), .D(D)) dut (.clk(clk), .start(start), .done(done));

    always #5 clk = ~clk;

    integer y, x;
    initial begin
        $readmemh("frame.hex", dut.frame_mem);
        $readmemb("se.txt",    dut.se);

        @(negedge clk); start = 1'b1;
        @(negedge clk); start = 1'b0;
        wait (done == 1'b1);

        for (y = 2*R; y <= H - 1 - 2*R; y = y + 1)
            for (x = 2*R; x <= W - 1 - 2*R; x = x + 1)
                $display("TH %0d %0d %0d", y, x, dut.tophat_mem[y*W + x]);
        $finish;
    end
endmodule
