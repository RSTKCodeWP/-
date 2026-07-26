// tb_detect_frontend_top.v -- drive the streaming detect front-end top end to end.
//
// Streams "frame.hex" through pass 1, waits p1_done, injects the PS threshold (+THR=<int> plusarg),
// waits done, then prints each labelled pixel "L <idx> <label>" from ccl.label_mem. Loads the SE into
// both win_reduce stages of the top-hat. The Python co-sim compares against tophat->threshold->CCL.

`timescale 1ns/1ps

module tb_detect_frontend_top;
    localparam integer W = 32, H = 32, D = 11, LW = 12, N = W*H;

    localparam integer ACC = 48;
    reg          clk = 1'b0, rst = 1'b1, in_valid = 1'b0, thr_valid = 1'b0;
    reg  [15:0]  in_data = 16'd0, thr_in = 16'd0;
    wire         p1_done, done, out_valid;
    wire [ACC-1:0] cx_fixed, cy_fixed, den_out;

    detect_frontend_top #(.W(W), .H(H), .D(D), .LW(LW), .ACC(ACC)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_data(in_data),
        .thr_valid(thr_valid), .thr_in(thr_in), .p1_done(p1_done), .done(done),
        .out_valid(out_valid), .cx_fixed(cx_fixed), .cy_fixed(cy_fixed), .den_out(den_out));

    always #5 clk = ~clk;

    initial begin #2000000 $display("TIMEOUT"); $finish; end   // watchdog: never hang the sim

    reg [15:0] frame [0:N-1];
    reg [31:0] thrp;
    integer i;
    initial begin
        $readmemh("frame.hex", frame);
        $readmemb("se.txt", dut.mt.e.se);
        $readmemb("se.txt", dut.mt.d.se);
        if (!$value$plusargs("THR=%d", thrp)) thrp = 32'd0;

        @(negedge clk); rst = 1'b0;
        for (i = 0; i < N; i = i + 1) begin @(negedge clk); in_valid = 1'b1; in_data = frame[i]; end
        @(negedge clk); in_valid = 1'b0;

        wait (p1_done == 1'b1);
        @(negedge clk); thr_valid = 1'b1; thr_in = thrp[15:0];
        @(negedge clk); thr_valid = 1'b0;

        wait (done == 1'b1);
        for (i = 0; i < N; i = i + 1)
            if (dut.ccl.label_mem[i] != 0) $display("L %0d %0d", i, dut.ccl.label_mem[i]);
        $display("CENT %0d %0d %0d", cx_fixed, cy_fixed, den_out);
        $finish;
    end
endmodule
