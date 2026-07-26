// tb_hist.v -- streams top-hat values through hist and prints the non-zero histbin.
// Reads "vals.txt" (one decimal value per line) from the run cwd; prints "H <bin> <count>".

`timescale 1ns/1ps

module tb_hist;
    localparam integer NBINS = 2048, CW = 20;

    reg          clk = 1'b0, start = 1'b0, valid = 1'b0;
    reg  [15:0]  val = 16'd0;
    wire         ready;

    hist #(.NBINS(NBINS), .CW(CW)) dut (.clk(clk), .start(start), .ready(ready),
                                        .valid(valid), .val(val));

    always #5 clk = ~clk;

    integer fd, r, v, i;
    initial begin
        fd = $fopen("vals.txt", "r");
        if (fd == 0) begin $display("ERR: cannot open vals"); $finish; end

        @(negedge clk); start = 1'b1;
        @(negedge clk); start = 1'b0;
        wait (ready == 1'b1);

        r = $fscanf(fd, "%d\n", v);
        while (r == 1) begin
            @(negedge clk); valid = 1'b1; val = v[15:0];
            @(posedge clk);
            r = $fscanf(fd, "%d\n", v);
        end
        @(negedge clk); valid = 1'b0;
        @(posedge clk);

        for (i = 0; i < NBINS; i = i + 1)
            if (dut.histbin[i] != 0) $display("H %0d %0d", i, dut.histbin[i]);
        $fclose(fd);
        $finish;
    end
endmodule
