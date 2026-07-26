// tb_centroid_dp.v -- drives real detected-blob pixels through centroid_dp and prints the result.
//
// Stimulus file (path via +stim=<file>): one "x y w last" per line; `last`=1 ends a component.
// For every component the DUT emits one centroid, printed as "RES <cx_fixed> <cy_fixed> <den>".
// The Python co-sim (test_centroid_dp_rtl.py) compares those against the bit-exact reference.

`timescale 1ns/1ps

module tb_centroid_dp;
    localparam integer F = 8;

    reg          clk = 1'b0, rst = 1'b0, valid = 1'b0, last = 1'b0;
    reg  [15:0]  x = 16'd0, y = 16'd0, w = 16'd0;
    wire         out_valid;
    wire [47:0]  cx_fixed, cy_fixed, den_out;

    centroid_dp #(.XW(16), .WW(16), .ACC(48), .F(F)) dut (
        .clk(clk), .rst(rst), .valid(valid), .x(x), .y(y), .w(w), .last(last),
        .out_valid(out_valid), .cx_fixed(cx_fixed), .cy_fixed(cy_fixed), .den_out(den_out));

    always #5 clk = ~clk;   // 100 MHz

    integer fd, r;
    integer vx, vy, vw, vlast;
    reg [8*256:1] stimpath;

    initial begin
        if (!$value$plusargs("stim=%s", stimpath)) stimpath = "stim.txt";
        fd = $fopen(stimpath, "r");
        if (fd == 0) begin $display("ERR: cannot open stim file"); $finish; end

        // synchronous reset (valid low)
        @(negedge clk); valid = 1'b0; rst = 1'b1;
        @(negedge clk); rst = 1'b0;

        r = $fscanf(fd, "%d %d %d %d\n", vx, vy, vw, vlast);
        while (r == 4) begin
            @(negedge clk);
            valid = 1'b1; x = vx[15:0]; y = vy[15:0]; w = vw[15:0]; last = vlast[0];
            @(posedge clk); #1;
            if (out_valid) $display("RES %0d %0d %0d", cx_fixed, cy_fixed, den_out);
            r = $fscanf(fd, "%d %d %d %d\n", vx, vy, vw, vlast);
        end

        @(negedge clk); valid = 1'b0; last = 1'b0;
        @(posedge clk); #1;
        if (out_valid) $display("RES %0d %0d %0d", cx_fixed, cy_fixed, den_out);
        $fclose(fd);
        $finish;
    end
endmodule
