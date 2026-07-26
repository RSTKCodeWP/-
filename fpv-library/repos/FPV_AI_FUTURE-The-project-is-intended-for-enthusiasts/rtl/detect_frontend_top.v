// detect_frontend_top.v -- streaming detect front-end TOP: the PL blocks wired in real RTL (M0 capstone).
//
// Chains the fielded streaming blocks into one module (vs the Python-orchestrated integration co-sim),
// end to end from a raster frame to the target aim-point:
//
//   frame --> morph_tophat_stream --> th_mem --> [PS threshold injected] --> mask --> ccl_stream
//         --> dominant component --> centroid_dp --> (cx,cy,den)
//
// Two passes, because the adaptive threshold needs the whole frame's top-hat first:
//   PASS 1  (S_P1)      stream the frame through morph_tophat_stream; buffer the raw frame (f_mem, for
//                       centroid weights) + the interior top-hat (th_mem); assert p1_done.
//   inject  (S_WAITTHR) the PS provides thr_in (thr_valid); latch it.
//   PASS 2  (S_P2..)    mask (interior th_mem > thr) -> ccl_stream -> label_mem; then tally areas, pick
//                       the dominant (max-area) component, and stream its pixels (weight = raw - local
//                       background) through centroid_dp -> the fixed-point centroid.
//
// The threshold STATS stay on the PS (injected); everything else is PL. Verified by
// fpga/rtl/test_detect_frontend_top.py against the Python tophat->threshold->CCL->centroid chain.

`timescale 1ns/1ps

module detect_frontend_top #(
    parameter integer W  = 32,
    parameter integer H  = 32,
    parameter integer D  = 11,
    parameter integer LW = 12,
    parameter integer F  = 8,
    parameter integer ACC = 48
) (
    input  wire            clk,
    input  wire            rst,
    input  wire            in_valid,      // pass-1 frame stream (raster, N pixels)
    input  wire [15:0]     in_data,
    input  wire            thr_valid,     // PS threshold ready (after p1_done)
    input  wire [15:0]     thr_in,
    output reg             p1_done,       // pass-1 top-hat complete (PS may read/threshold now)
    output reg             done,          // pipeline complete; centroid valid
    output reg             out_valid,     // dominant-component centroid valid
    output reg [ACC-1:0]   cx_fixed,      // cx * 2^F (floor)
    output reg [ACC-1:0]   cy_fixed,      // cy * 2^F (floor)
    output reg [ACC-1:0]   den_out        // sum of weights
);
    localparam integer N       = W * H;
    localparam integer MAXL    = N + 1;
    localparam integer R       = D / 2;
    localparam integer TH_LO   = 2 * R;
    localparam integer TH_HI_Y = H - 1 - 2 * R;
    localparam integer TH_HI_X = W - 1 - 2 * R;
    localparam integer TH_COUNT = (H - 4 * R) * (W - 4 * R);

    reg [15:0]  f_mem  [0:N-1];        // raw frame (centroid weights)
    reg [15:0]  th_mem [0:N-1];        // interior top-hat
    reg [15:0]  thr_lat;
    integer     area   [0:MAXL-1];     // per-label pixel count (pass 2)
    integer     tcnt, p2idx, fwr, ci, li;
    integer     best_area, last_dom_idx;
    reg [LW-1:0] dom;
    reg [15:0]  local_bg, wt;
    integer     px, py;

    localparam [3:0] S_P1=0, S_WAITTHR=1, S_P2=2, S_P2WAIT=3, S_TALLY=4, S_BG=5,
                     S_CENTRST=6, S_CENT=7, S_CENTWAIT=8, S_DONE=9;
    reg [3:0] state;
    reg       cent_ready;             // centroid_dp emitted (it can pulse during S_CENT, not just wait)

    // pass-1 streaming top-hat
    wire        mt_v; wire [15:0] mt_d, mt_x, mt_y;
    morph_tophat_stream #(.W(W), .H(H), .D(D)) mt (
        .clk(clk), .rst(rst), .in_valid(in_valid && state == S_P1), .in_data(in_data),
        .out_valid(mt_v), .out_data(mt_d), .out_x(mt_x), .out_y(mt_y));

    // pass-2 streaming CCL (held in reset until pass 2)
    wire ccl_rst = (state == S_P1) || (state == S_WAITTHR);
    reg  ccl_iv, ccl_id;
    wire ccl_done;
    ccl_stream #(.W(W), .H(H), .LW(LW)) ccl (
        .clk(clk), .rst(ccl_rst), .in_valid(ccl_iv), .in_data(ccl_id), .done(ccl_done));

    // centroid datapath (fed the dominant component's pixels)
    reg              cdp_rst, cdp_valid, cdp_last;
    reg [15:0]       cdp_x, cdp_y, cdp_w;
    wire             cdp_ov;
    wire [ACC-1:0]   cdp_cx, cdp_cy, cdp_den;
    centroid_dp #(.XW(16), .WW(16), .ACC(ACC), .F(F)) cdp (
        .clk(clk), .rst(cdp_rst), .valid(cdp_valid), .x(cdp_x), .y(cdp_y), .w(cdp_w), .last(cdp_last),
        .out_valid(cdp_ov), .cx_fixed(cdp_cx), .cy_fixed(cdp_cy), .den_out(cdp_den));

    integer j;
    initial begin
        state = S_P1; p1_done = 0; done = 0; out_valid = 0; tcnt = 0; p2idx = 0; fwr = 0;
        ccl_iv = 0; ccl_id = 0; cdp_rst = 1; cdp_valid = 0; cdp_last = 0; cent_ready = 0;
    end

    always @(posedge clk) begin
        if (rst) begin
            state <= S_P1; p1_done <= 0; done <= 0; out_valid <= 0; tcnt = 0; p2idx = 0; fwr = 0;
            ccl_iv <= 0; ccl_id <= 0; cdp_rst <= 1; cdp_valid <= 0; cdp_last <= 0; cent_ready <= 0;
        end else begin
          // latch the centroid the moment centroid_dp emits it (may be during S_CENT, not only S_CENTWAIT)
          if (cdp_ov) begin cx_fixed <= cdp_cx; cy_fixed <= cdp_cy; den_out <= cdp_den; cent_ready <= 1'b1; end
          case (state)
            S_P1: begin
                if (in_valid) begin f_mem[fwr] = in_data; if (fwr != N-1) fwr = fwr + 1; end
                if (mt_v) begin
                    th_mem[mt_y * W + mt_x] = mt_d;
                    tcnt = tcnt + 1;
                    if (tcnt == TH_COUNT) begin p1_done <= 1; state <= S_WAITTHR; end
                end
            end

            S_WAITTHR: if (thr_valid) begin thr_lat <= thr_in; p2idx = 0; state <= S_P2; end

            S_P2: begin
                px = p2idx % W; py = p2idx / W;
                ccl_iv <= 1'b1;
                ccl_id <= (py >= TH_LO && py <= TH_HI_Y && px >= TH_LO && px <= TH_HI_X
                           && th_mem[p2idx] > thr_lat) ? 1'b1 : 1'b0;
                if (p2idx == N - 1) state <= S_P2WAIT; else p2idx = p2idx + 1;
            end

            S_P2WAIT: begin
                ccl_iv <= 1'b0;
                if (ccl_done) begin
                    for (j = 0; j < MAXL; j = j + 1) area[j] = 0;   // tally per-component area
                    for (j = 0; j < N; j = j + 1)
                        if (ccl.label_mem[j] != 0) area[ccl.label_mem[j]] = area[ccl.label_mem[j]] + 1;
                    state <= S_TALLY;
                end
            end

            S_TALLY: begin                                          // dominant = max-area component
                best_area = 0; dom = 0;
                for (j = 1; j < MAXL; j = j + 1)
                    if (area[j] > best_area) begin best_area = area[j]; dom = j[LW-1:0]; end
                state <= S_BG;
            end

            S_BG: begin                                             // local background + last dom pixel
                local_bg = 16'hFFFF; last_dom_idx = 0;
                for (j = 0; j < N; j = j + 1)
                    if (ccl.label_mem[j] == dom) begin
                        if (f_mem[j] < local_bg) local_bg = f_mem[j];
                        last_dom_idx = j;
                    end
                cdp_rst <= 1'b1; cdp_valid <= 1'b0; ci = 0; state <= S_CENTRST;
            end

            S_CENTRST: begin cdp_rst <= 1'b0; state <= S_CENT; end   // one clean reset cycle

            S_CENT: begin                                           // stream dom pixels -> centroid_dp
                if (ccl.label_mem[ci] == dom) begin
                    cdp_valid <= 1'b1;
                    cdp_x <= (ci % W); cdp_y <= (ci / W);
                    cdp_w <= (f_mem[ci] > local_bg) ? (f_mem[ci] - local_bg) : 16'd0;
                    cdp_last <= (ci == last_dom_idx) ? 1'b1 : 1'b0;
                end else begin
                    cdp_valid <= 1'b0; cdp_last <= 1'b0;
                end
                if (ci == N - 1) state <= S_CENTWAIT; else ci = ci + 1;
            end

            S_CENTWAIT: begin
                cdp_valid <= 1'b0; cdp_last <= 1'b0;
                if (cent_ready) begin out_valid <= 1'b1; done <= 1'b1; state <= S_DONE; end
            end

            S_DONE: ;
          endcase
        end
    end
endmodule
