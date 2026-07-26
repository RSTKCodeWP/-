// bt656_rx.v -- ITU-R BT.656 receiver: 8-bit 4:2:2 byte stream -> luma (Y) frame (Block-3 ingest).
//
// The FT640 (analog CVBS) reaches the fabric through a CVBS->BT.656 decoder (ADV7280/TVP5150) as
// an 8-bit parallel stream at ~27 MHz with EMBEDDED sync: 4-byte preambles FF 00 00 XY where the
// XY status byte carries F(ield)=bit6, V(ertical-blank)=bit5, H=bit4 (0=SAV start-of-active-video,
// 1=EAV end-of-active-video).  Between an active-line SAV (V=0) and its EAV the data is YCbCr 4:2:2
// multiplexed  Cb Y0 Cr Y1 Cb Y2 Cr Y3 ...  For a MONOCHROME thermal core the picture is the Y
// channel (Cb=Cr=neutral), so this receiver demuxes and emits only Y, with start-of-frame /
// start-of-line strobes.  One BT.656 RX serves every analog camera behind a decoder -- the
// camera-agnostic ingest layer.
//
// Verified by fpga/rtl/test_bt656_rx.py: a Python BT.656 encoder wraps a known Y frame, this module
// unwraps it, and the recovered frame must equal the original byte-for-byte.

`timescale 1ns/1ps

module bt656_rx (
    input  wire       clk,
    input  wire       rst,
    input  wire       byte_valid,   // a decoder byte is present this cycle
    input  wire [7:0] byte_in,
    output reg        y_valid,      // y_data is an active-video luma sample this cycle
    output reg [7:0]  y_data,
    output reg        sof,          // pulse: first active line of a frame
    output reg        sol           // pulse: start of an active line
);
    // preamble-capture FSM: FF 00 00 XY is consumed as sync, never emitted as video.
    localparam [1:0] S_VID = 2'd0, S_FF = 2'd1, S_FF00 = 2'd2, S_FF0000 = 2'd3;
    reg [1:0] state;
    reg       in_active;   // between an active-line SAV and its EAV
    reg       phase;       // 0 -> next active byte is chroma, 1 -> luma
    reg       prev_v;      // last V bit seen at a SAV (for the frame-start edge)

    always @(posedge clk) begin
        if (rst) begin
            state <= S_VID; in_active <= 1'b0; phase <= 1'b0; prev_v <= 1'b1;
            y_valid <= 1'b0; y_data <= 8'd0; sof <= 1'b0; sol <= 1'b0;
        end else begin
            y_valid <= 1'b0; sof <= 1'b0; sol <= 1'b0;   // default: strobes are single-cycle
            if (byte_valid) begin
                case (state)
                    S_VID: begin
                        if (byte_in == 8'hFF) begin
                            state <= S_FF;                       // possible preamble start
                        end else if (in_active) begin
                            if (phase) begin                     // luma phase -> emit Y
                                y_valid <= 1'b1;
                                y_data  <= byte_in;
                            end
                            phase <= ~phase;                     // toggle chroma/luma each byte
                        end
                    end
                    S_FF:     state <= (byte_in == 8'h00) ? S_FF00   : S_VID;
                    S_FF00:   state <= (byte_in == 8'h00) ? S_FF0000 : S_VID;
                    S_FF0000: begin                              // byte_in is the XY status byte
                        if (byte_in[4] == 1'b0) begin            // SAV (start of active video)
                            if (byte_in[5] == 1'b0) begin        // V=0: an active line
                                in_active <= 1'b1;
                                phase     <= 1'b0;               // first active byte is chroma (Cb)
                                sol       <= 1'b1;
                                if (prev_v == 1'b1) sof <= 1'b1; // first active line after blanking
                                prev_v <= 1'b0;
                            end else begin                       // V=1: vertical blanking
                                in_active <= 1'b0;
                                prev_v    <= 1'b1;
                            end
                        end else begin                           // EAV (H=1)
                            in_active <= 1'b0;
                        end
                        state <= S_VID;
                    end
                endcase
            end
        end
    end
endmodule
