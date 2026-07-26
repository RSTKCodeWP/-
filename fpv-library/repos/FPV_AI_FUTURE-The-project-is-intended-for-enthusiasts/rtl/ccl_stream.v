// ccl_stream.v -- single-pass STREAMING connected-components labeller (Block-3 PL, fielded form).
//
// The frame-addressed ccl.v relaxes labels with iterative forward/backward Gauss-Seidel sweeps until
// stable (O(N * rounds)). This is the fielded replacement: ONE raster streaming pass (only a 1-row
// label line buffer `prev_lbl` + a union-find `parent` table) assigns provisional labels from the
// west/north 4-neighbours and records equivalences on collision; then a single RESOLVE pass flattens
// every label to its union-find root. Same GROUPING as fpv.seeker.detect._connected_components (the
// label integers are arbitrary; the partition + per-component bbox/area are what match).
//
// The union-find `find` is a behavioural pointer-chase (parent links strictly decrease -> terminates),
// standing in for a hardware union-find engine (cf. the behavioural divide in centroid_dp.v). Streamed
// input: one mask bit per in_valid, raster order; `done` pulses high once labelled+resolved.
//
// Verified by fpga/rtl/test_ccl_stream.py against fpv.seeker.detect._connected_components.

`timescale 1ns/1ps

module ccl_stream #(
    parameter integer W  = 32,
    parameter integer H  = 32,
    parameter integer LW = 12          // label width; must hold W*H
) (
    input  wire clk,
    input  wire rst,
    input  wire in_valid,
    input  wire in_data,               // 1-bit mask pixel, raster order
    output reg  done
);
    localparam integer N    = W * H;
    localparam integer MAXL = N + 1;

    reg [LW-1:0] label_mem [0:N-1];    // final labels (read back by the testbench)
    reg [LW-1:0] parent    [0:MAXL-1]; // union-find parent table
    reg [LW-1:0] prev_lbl  [0:W-1];    // label of the pixel directly above (previous row)
    reg [LW-1:0] left_lbl, next_label;

    integer      in_x, in_y, pcnt, j, k;
    reg [LW-1:0] north, west, L, ra, rb;

    localparam [1:0] S_STREAM = 2'd0, S_RESOLVE = 2'd1, S_DONE = 2'd2;
    reg [1:0] state;

    // union-find root is done INLINE as a procedural pointer-chase (parent links only ever point to a
    // smaller label, so the chase terminates). iverilog rejects a while-loop function over a module
    // array, hence the inline form.

    task do_reset;
        begin
            done = 1'b0; state = S_STREAM; in_x = 0; in_y = 0; pcnt = 0;
            left_lbl = 0; next_label = 1;
            for (j = 0; j < W;    j = j + 1) prev_lbl[j] = 0;
            for (j = 0; j < MAXL; j = j + 1) parent[j]   = j[LW-1:0];
        end
    endtask

    initial do_reset;

    always @(posedge clk) begin
        if (rst) do_reset;
        else case (state)
            S_STREAM: if (in_valid) begin
                north = prev_lbl[in_x];
                west  = (in_x > 0) ? left_lbl : {LW{1'b0}};
                if (in_data) begin
                    if (west == 0 && north == 0) begin
                        L = next_label; parent[L] = L; next_label = next_label + 1;
                    end else if (north == 0) begin
                        L = west;
                    end else if (west == 0) begin
                        L = north;
                    end else begin                        // both neighbours labelled -> union roots
                        ra = west;  while (parent[ra] != ra) ra = parent[ra];   // find(west)
                        rb = north; while (parent[rb] != rb) rb = parent[rb];   // find(north)
                        if (ra <= rb) begin L = ra; if (ra != rb) parent[rb] = ra; end
                        else          begin L = rb; parent[ra] = rb;                 end
                    end
                    label_mem[pcnt] = L;  left_lbl = L;  prev_lbl[in_x] = L;
                end else begin
                    label_mem[pcnt] = 0;  left_lbl = 0;  prev_lbl[in_x] = 0;
                end
                if (in_x == W-1) begin in_x = 0; in_y = in_y + 1; end else in_x = in_x + 1;
                if (pcnt == N-1) state <= S_RESOLVE; else pcnt = pcnt + 1;
            end

            S_RESOLVE: begin                              // flatten every label to its root
                for (k = 0; k < N; k = k + 1)
                    if (label_mem[k] != 0) begin
                        L = label_mem[k];
                        while (parent[L] != L) L = parent[L];
                        label_mem[k] = L;
                    end
                done <= 1'b1; state <= S_DONE;
            end

            S_DONE: ;
        endcase
    end
endmodule
