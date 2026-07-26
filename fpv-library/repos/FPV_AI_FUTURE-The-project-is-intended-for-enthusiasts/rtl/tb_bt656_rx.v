// tb_bt656_rx.v -- streams a BT.656 byte file through bt656_rx and prints the recovered events.
//
// Stimulus file (+stim=<file>): one decimal byte per line.  Prints, in order:
//   "SOF"      frame start        "SOL"  line start        "Y <val>"  a luma sample
// The Python co-sim (test_bt656_rx.py) reassembles those into a frame and compares to the original.

`timescale 1ns/1ps

module tb_bt656_rx;
    reg          clk = 1'b0, rst = 1'b0, byte_valid = 1'b0;
    reg  [7:0]   byte_in = 8'd0;
    wire         y_valid, sof, sol;
    wire [7:0]   y_data;

    bt656_rx dut (.clk(clk), .rst(rst), .byte_valid(byte_valid), .byte_in(byte_in),
                  .y_valid(y_valid), .y_data(y_data), .sof(sof), .sol(sol));

    always #5 clk = ~clk;

    integer fd, r, vbyte;
    reg [8*256:1] stimpath;

    initial begin
        if (!$value$plusargs("stim=%s", stimpath)) stimpath = "stim.txt";
        fd = $fopen(stimpath, "r");
        if (fd == 0) begin $display("ERR: cannot open stim file"); $finish; end

        @(negedge clk); byte_valid = 1'b0; rst = 1'b1;
        @(negedge clk); rst = 1'b0;

        r = $fscanf(fd, "%d\n", vbyte);
        while (r == 1) begin
            @(negedge clk); byte_valid = 1'b1; byte_in = vbyte[7:0];
            @(posedge clk); #1;
            if (sof)     $display("SOF");
            if (sol)     $display("SOL");
            if (y_valid) $display("Y %0d", y_data);
            r = $fscanf(fd, "%d\n", vbyte);
        end
        @(negedge clk); byte_valid = 1'b0;
        $fclose(fd);
        $finish;
    end
endmodule
