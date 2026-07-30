# MSP Parsing and OSD Rendering Description

This document is intended for maintenance developers of GroundConfiguration. It explains how OSD UDP data, after entering the application, completes MSP frame reassembly, MSP v1/v2 verification, and `MSP_DISPLAYPORT` command parsing, ultimately triggering an update to the transparent OSD overlay layer.



---

## 1. Overall Architecture and Data Flow

The device's OSD data enters the Presenter through an independent UDP channel, and then the View handles the work strongly related to the UI and transparent layer resources. The complete pipeline is as follows:

```text
Device OSD UDP Datagram
  → MainPresenter / IUdpTransport
  → MainFrm.HandleOsdDataReceived
  → MspFrameReassembler
  → MspOsdParser
  → MspDisplayPortDecoder
  → OsdOverlaySnapshot
  → GdiOsdOverlayRenderer
  → Transparent GDI+ OSD Overlay Window
```

Key responsibilities are as follows:

| Component | Responsibility |
| --- | --- |
| `MainPresenter` | Starts and stops the OSD UDP channel; passes received data back to the View via `IMainView.HandleOsdDataReceived()` callback. |
| `MainFrm.HandleOsdDataReceived()` | Logs OSD data arrival status, switches to the UI thread to update the status bar, and sequentially executes reassembly, logging, and OSD parsing entry points. |
| `MspFrameReassembler` | Organizes arbitrary UDP datagram sequences into complete MSP frames, handling cross-datagram truncation, multiple frames, and leading garbage bytes. |
| `MspOsdParser` | Identifies and verifies MSP v1/v2 frames; only decodes DisplayPort subcommands for `MSP_DISPLAYPORT` frames that pass verification. |
| `MspDisplayPortDecoder` | Applies parsed DisplayPort commands sequentially to the persistent OSD state; generates a snapshot upon receiving `DRAW_SCREEN`. |
| `GdiOsdOverlayRenderer` | Receives snapshots and updates the transparent overlay layer. |

The OSD transparent layer is independent of the RTSP playback pipeline: as long as the transparent layer renderer and PNG font library are ready, OSD data can be processed; toggling OSD visibility does not require rebuilding the RTSP pipeline.

`MainFrm.HandleOsdDataReceived()` first updates the "last received OSD data" timestamp, then asynchronously updates the status bar. Only if the renderer is assembled will the data continue into the MSP pipeline. This keeps the UDP reception status independent of the parsing and rendering statuses.

---

## 2. MSP Frame Reassembly

### 2.1 Why Reassembly is Necessary

UDP preserves individual datagram boundaries, but the MSP data output by the device does not guarantee "one frame per datagram". In actual reception, the following may occur:

- A single MSP frame is split across multiple UDP datagrams;
- A single UDP datagram contains multiple consecutive MSP frames;
- Invalid leading bytes or incorrect frame markers are present;
- The header and length fields arrive, but the frame body has not yet fully arrived.

Therefore, each UDP datagram cannot be directly passed to `MspOsdParser`. `MspFrameReassembler` first confirms frame boundaries based on the header and length fields, outputting only fully received frames; incomplete tails are kept for the next `Append()` call.

### 2.2 Supported Frame Boundaries

The reassembler only recognizes the MSP wire format structure, does not read payload semantics, and does not verify XOR/CRC:

| Version | Start Marker | Length Field | Total Length |
| --- | --- | --- | --- |
| MSP v1 | `$M`, i.e., `24 4D` | Single-byte payload length at offset `+3` | `6 + payloadLength` |
| MSP v2 | `$X`, i.e., `24 58` | Little-endian two-byte payload length at offset `+6/+7` | `9 + payloadLength` |

The direction byte in the header is retained with the frame, but its semantics are not verified during the reassembly phase. Payload verification and DisplayPort parsing are handled by the subsequent `MspOsdParser`.

### 2.3 Buffering and Resynchronization Rules

Processing rules for `MspFrameReassembler.Append(byte[] data)`:

1. Appends the newly arrived datagram to the internal linear buffer;
2. Scans for `0x24` (`$`) to find candidate headers;
3. When encountering a non-`$` byte, or a byte other than `M`/`X` following `$`, treats it as garbage and continues scanning;
4. If the candidate header, length field, or frame body is not yet complete, retains the tail starting from the candidate header;
5. Continues scanning each time a complete frame is found, allowing multiple consecutive frame bytes to be returned at once;
6. Consumed leading garbage and complete frames are removed from the internal buffer.

The default maximum retention buffer is `8 KiB`. If an incomplete tail continuously accumulates and exceeds this limit, the buffer is cleared entirely to restore synchronization and prevent unbounded memory growth caused by malformed lengths or persistent garbage data.

This class is not thread-safe and should be called sequentially by the same OSD UDP receive call chain.

---

## 3. MSP v1/v2 Parsing and Verification

`MspOsdParser.TryParse(byte[] data, out MspOsdParseResult result)` scans and parses the complete frame bytes output by the reassembler. The parse result includes:

- `Frames`: The read MSP frames along with version, direction, command, payload, original checksum, and calculated checksum;
- `DisplayPortCommands`: OSD commands converted from `MSP_DISPLAYPORT` frames that passed verification;
- `Issues`: Problems found during parsing, with original byte offsets, severity, classification, and description.

`TryParse` returns `true` as long as at least one complete MSP frame is successfully read. This does not mean all frames passed verification; the caller must also check `result.HasErrors`.

### 3.1 MSP v1 Format

The MSP v1 frame format is as follows:

```text
$ M direction payloadLength command payload... xorChecksum
```

| Field | Length | Description |
| --- | ---: | --- |
| `$M` | 2 | Fixed header: `0x24 0x4D` |
| `direction` | 1 | Usually `<` (request) or `>` (response) |
| `payloadLength` | 1 | Number of payload bytes |
| `command` | 1 | Single-byte MSP command number |
| `payload` | N | Command payload |
| `xorChecksum` | 1 | `payloadLength ^ command ^ all bytes in payload` |

The parser determines the total frame length using `6 + payloadLength`. Frames that fail verification are still written to `Frames` and an `InvalidChecksum` error is added; such frames will not be interpreted as DisplayPort data.

### 3.2 MSP v2 Format

The MSP v2 frame format is as follows:

```text
$ X direction flags commandLE payloadLengthLE payload... crc8
```

| Field | Length | Description |
| --- | ---: | --- |
| `$X` | 2 | Fixed header: `0x24 0x58` |
| `direction` | 1 | Usually `<` or `>` |
| `flags` | 1 | v2 flag bits, the parser retains this value |
| `commandLE` | 2 | Little-endian 16-bit command number |
| `payloadLengthLE` | 2 | Little-endian 16-bit payload length |
| `payload` | N | Command payload |
| `crc8` | 1 | DVB-S2 CRC-8 |

The v2 CRC starts from `flags`, covering `flags + command + payloadLength + payload`, using the DVB-S2 polynomial `0xD5`. The parser determines the total frame length using `9 + payloadLength`.

### 3.3 Parsing Issues and Caller Rejection Strategy

The parser does not immediately throw an exception upon encountering a single issue; it writes the issue to `Issues` and continues scanning subsequent data as much as possible. Common categories include:

| Category | Meaning |
| --- | --- |
| `UnexpectedByte` | Current position is not `$`; skipped this byte and continued scanning. |
| `UnsupportedMarker` | Character after `$` is not `M` or `X`. |
| `IncompleteHeader` | Input ended before the MSP header was complete. |
| `TruncatedFrame` | Declared frame length exceeds remaining bytes of current input. |
| `InvalidChecksum` | v1 XOR or v2 CRC-8 verification failed. |
| `DisplayPortTooShort` | `MSP_DISPLAYPORT` payload is missing the subcommand or required fields for that subcommand. |
| `UnsupportedDisplayPortSubcommand` | DisplayPort subcommand not supported by the current implementation. |
| `InvalidDisplayPortSegmentLength` | Segment length in the extended complete frame is less than the minimum structure length. |
| `TruncatedDisplayPortSegment` | Segment in the extended complete frame exceeds the payload boundary. |

The strategy for `MainFrm.TryRenderMspOsd()` is:

1. Rejects directly if the PNG OSD font library is not loaded;
2. Logs parsing failure and rejects if `TryParse()` returns `false`;
3. Logs a warning and rejects the entire batch of data if `result.HasErrors` is `true`;
4. Passes the snapshot to the renderer only if parsing has no errors and the subsequent decoder receives a draw commit.

If you need to treat any issue as an exception in strict scenarios, you can use `MspOsdParser.Parse()`; it will throw a `FormatException` with an offset upon the first issue.

### 3.4 Generic Streaming MSP State Machine

The project also retains `Msp.ProcessData()`: a byte-by-byte MSP v1/v2 state machine ported from underlying C++, suitable for scenarios where bytes are continuously fed and a callback is executed when a complete message arrives.

The OSD UDP overlay currently uses the `MspFrameReassembler + MspOsdParser` path, which "first reassembles by UDP datagram boundaries, then parses in batches", rather than directly using this state machine. Both support basic frame verification for v1/v2, but have different responsibilities:

| Implementation | Applicable Method | Output |
| --- | --- | --- |
| `Msp.ProcessData()` | Single-byte streaming protocol processing | Callback for complete `MspMsg` |
| `MspFrameReassembler` | UDP datagram boundary organization | Consecutive complete raw MSP frame bytes |
| `MspOsdParser` | OSD batch parsing | Collection of frames, DisplayPort commands, and issues |

---

## 4. MSP_DISPLAYPORT Decoding

The command number for `MSP_DISPLAYPORT` is `182` (hex `0xB6`). Only frames with correct MSP verification and command number `0xB6` will enter DisplayPort payload decoding.

### 4.1 Standard Subcommands

The first byte of the DisplayPort payload is the subcommand:

| Value | Enum | Processing Method |
| ---: | --- | --- |
| `0` | `Heartbeat` | Logs the command, does not change character content. |
| `1` | `Release` | Logs the command; upon receipt, the decoder clears existing screen state. |
| `2` | `ClearScreen` | Logs the command; upon receipt, the decoder clears existing screen state. |
| `3` | `WriteString` | Parses row, column, attribute, and subsequent variable-length character data. |
| `4` | `DrawScreen` | Commits a draw; the decoder generates a snapshot at this point. |
| `5` | `Options` | Parses font number and display mode. |
| `6` | `Sys` | Logs the command, currently does not change character content. |

### 4.2 `WRITE_STRING` Format

`WRITE_STRING` payload format:

```text
03 row column attribute character0 character1 ...
```

Where:

- `row` and `column` are OSD character grid coordinates;
- `attribute` is retained with the command; the current character display path uses its lower two bits to select the font page;
- Starting from the 5th byte to the end of the payload are character codes, so the string length is variable;
- If the payload is less than 4 bytes (`subcommand + row + column + attribute`), the parser reports `DisplayPortTooShort`.

### 4.3 `OPTIONS` Format

`OPTIONS` payload format:

```text
05 font mode
```

- `font`: Font number provided by the device, retained by the parser;
- `mode`: OSD grid mode. The current decoder supports modes `0`, `1`, `2`, `3`; when the mode changes, previous screen content is cleared;
- If `font` or `mode` is missing, the parser reports `DisplayPortTooShort`.

### 4.4 Device Extended Complete Frame `0x35`

The device also sends an extended complete frame starting with `0x35`. Its format is not a standard single DisplayPort subcommand:

```text
35 prefixByte1 prefixByte2
   segment...

segment = segmentLength row column attribute characters...
```

Processing rules:

1. The first three bytes are treated as the extended frame prefix;
2. Reads segment by segment starting from offset `3`;
3. The first byte of each segment, `segmentLength`, contains the total length of the segment; the minimum length is `4`, corresponding to the row, column, attribute fields, and the length byte itself;
4. Each segment is converted into a standard `WriteString` command;
5. After all segments are processed, the parser automatically appends a `DrawScreen` command.

Therefore, `0x35` indicates a "complete screen update": the receiver does not need to wait for an independent standard `DRAW_SCREEN` packet to commit the draw after processing this frame. If the segment length is less than `4` or the end of the segment crosses the payload boundary, the entire batch of parsing results will record an error.

---

## 5. Error Handling and Troubleshooting

### 5.1 First Determine Which Layer the Fault is In

It is recommended to locate the issue in the following order:

1. **Has UDP arrived**: Does the status bar change from `OSD=disconnect` to the port number; if no data is received for about 1 second, the status bar will show `OSD=No rec`.
2. **Has it entered the OSD processing branch**: Only when the transparent layer renderer is assembled will the received data enter reassembly and parsing.
3. **Is the font library loaded**: `EnsureOsdFontLoaded()` requires `_osdFont.Fonts[0]` to be available; otherwise, the data will not be used for rendering.
4. **Does the reassembler output complete frames**: Half frames across datagrams will be retained; the parser will not be called until the next packet arrives.
5. **Did the MSP frame pass verification**: `InvalidChecksum` indicates an XOR or CRC-8 mismatch.
6. **Is it valid DisplayPort data**: It must be command `0xB6`, and the subcommand payload length must be correct.
7. **Is there a draw commit**: Normal writes only update the internal OSD state; an independent `DRAW_SCREEN` or an implicit commit from extended `0x35` is required to generate a new snapshot.

### 5.2 Common Symptoms and Causes

| Symptom | Priority Check Items |
| --- | --- |
| Status bar constantly shows `OSD=disconnect` | Is the OSD UDP channel started, are the device address and port correct. |
| Status bar changes to `OSD=No rec` | The UDP channel is still running, but no data has been received for about 1 second; check if the device is currently sending OSD. |
| UDP logs exist but no OSD display | Check if the PNG font library is loaded, whether the data can be reassembled into complete MSP frames, and whether `DRAW_SCREEN` exists. |
| Log shows `msp osd parse failed` | The current input failed to read a complete MSP frame; check the frame header, length field, and whether the reassembler was bypassed. |
| Log shows `msp osd overlay error` | `MspOsdParseResult.HasErrors` is true; check the classification and offset of the first error. |
| OSD only updates partially or does not commit | Check whether the device sends `WRITE_STRING` or `DRAW_SCREEN`; the write command itself does not equal a commit. |
| Occasional unrecoverable state | Check if malformed lengths or garbage data are continuously sent; the reassembler's 8 KiB buffer protection will clear the tail and wait for a new valid frame header. |

### 5.3 Key Points for Log Location

In `HandleOsdDataReceived()`, after the reassembler outputs complete frames, a hexadecimal log is recorded:

```text
Rec from=<endpoint>,msg=<hexadecimal string of complete MSP frames>
```

This log records the **reassembled complete set of MSP frames**, which does not necessarily correspond one-to-one with a single UDP datagram. When troubleshooting differences between packet captures and application logs, special attention should be paid to:

- A single log entry may contain multiple MSP frames;
- The first half of a frame in a UDP datagram may not immediately generate a log;
- Garbage bytes before a frame will be discarded during reassembly and will not appear in the output frame log;
- Complete frames that fail verification may still be logged, but will be rejected during the parsing phase.

---







# MSP 解析与 OSD 渲染说明

本文面向 GroundConfiguration 的维护开发者，说明 OSD UDP 数据进入应用后，如何完成 MSP 帧重组、MSP v1/v2 校验与 `MSP_DISPLAYPORT` 命令解析，并最终触发透明 OSD 叠加层更新。


---

## 1. 整体架构与数据流

设备的 OSD 数据通过独立 UDP 通道进入 Presenter，再由视图处理与 UI、透明层资源强相关的工作。完整链路如下：

```text
设备 OSD UDP 数据报
  → MainPresenter / IUdpTransport
  → MainFrm.HandleOsdDataReceived
  → MspFrameReassembler
  → MspOsdParser
  → MspDisplayPortDecoder
  → OsdOverlaySnapshot
  → GdiOsdOverlayRenderer
  → 透明 GDI+ OSD 叠加窗口
```

关键职责如下：

| 组件 | 职责 |
| --- | --- |
| `MainPresenter` | 启动、停止 OSD UDP 通道；将接收数据经 `IMainView.HandleOsdDataReceived()` 回调给视图。 |
| `MainFrm.HandleOsdDataReceived()` | 记录 OSD 数据到达状态、切换到 UI 线程更新状态栏，并依次执行重组、日志记录与 OSD 解析入口。 |
| `MspFrameReassembler` | 将任意 UDP 数据报序列整理为完整 MSP 帧，处理跨数据报截断、多个帧和前导垃圾字节。 |
| `MspOsdParser` | 识别并校验 MSP v1/v2 帧；仅对校验正确的 `MSP_DISPLAYPORT` 帧解码 DisplayPort 子命令。 |
| `MspDisplayPortDecoder` | 将已解析的 DisplayPort 命令按顺序应用到持久 OSD 状态；收到 `DRAW_SCREEN` 后生成快照。 |
| `GdiOsdOverlayRenderer` | 接收快照并更新透明叠加层。 |

OSD 透明层独立于 RTSP 播放管线：只要透明层渲染器和 PNG 字库已准备好，OSD 数据即可被处理；OSD 显隐不需要重建 RTSP 管线。

`MainFrm.HandleOsdDataReceived()` 会先更新“最近收到 OSD 数据”的时间戳，再异步更新状态栏。若渲染器已经装配，数据才会继续进入 MSP 链路。这样 UDP 接收状态与解析、绘制状态相互独立。

---

## 2. MSP 帧重组

### 2.1 为什么需要重组

UDP 保留单个数据报边界，但设备输出的 MSP 数据不保证恰好“一帧对应一个数据报”。实际接收时可能出现：

- 一帧 MSP 数据被切分到多个 UDP 数据报；
- 一个 UDP 数据报连续包含多帧 MSP 数据；
- 有无效前导字节或错误的帧标识；
- 收到帧头和长度字段后，帧体尚未到齐。

因此不能直接把每个 UDP 数据报交给 `MspOsdParser`。`MspFrameReassembler` 先依据帧头和长度字段确认帧边界，只输出已收全的帧；未完成的尾部留待下一次 `Append()` 调用。

### 2.2 支持的帧边界

重组器只识别 MSP 线格式的结构，不读取负载语义，也不验证 XOR/CRC：

| 版本 | 起始标识 | 长度字段 | 总长度 |
| --- | --- | --- | --- |
| MSP v1 | `$M`，即 `24 4D` | 偏移 `+3` 的单字节负载长度 | `6 + payloadLength` |
| MSP v2 | `$X`，即 `24 58` | 偏移 `+6/+7` 的小端双字节负载长度 | `9 + payloadLength` |

帧头中的方向字节会随帧一起保留，但重组阶段不对其语义做校验。负载校验及 DisplayPort 解析由后续 `MspOsdParser` 负责。

### 2.3 缓冲与重新同步规则

`MspFrameReassembler.Append(byte[] data)` 的处理规则：

1. 将新到达的数据报追加到内部线性缓冲；
2. 扫描 `0x24`（`$`）寻找候选帧头；
3. 遇到非 `$` 字节、或 `$` 后不是 `M`/`X` 时，将其视为垃圾并继续扫描；
4. 候选帧头、长度字段或帧体尚未到齐时，保留自候选帧头起的尾部；
5. 每找到一帧完整帧，继续扫描，因此可一次返回多帧连续字节；
6. 已消费的前导垃圾和完整帧从内部缓冲移除。

默认最大保留缓冲为 `8 KiB`。若一个未完成尾部持续累积并超过上限，缓冲会整体清空，以恢复同步并避免畸形长度或持续垃圾数据导致内存无限增长。

该类不是线程安全的，应保持由同一条 OSD UDP 接收调用链顺序调用。

---

## 3. MSP v1/v2 解析与校验

`MspOsdParser.TryParse(byte[] data, out MspOsdParseResult result)` 对重组器输出的完整帧字节进行扫描和解析。解析结果包含：

- `Frames`：读取出的 MSP 帧及版本、方向、命令、负载、原始校验值和计算校验值；
- `DisplayPortCommands`：由校验通过的 `MSP_DISPLAYPORT` 帧转换得到的 OSD 命令；
- `Issues`：解析过程中发现的问题，带有原始字节偏移、严重度、分类和说明。

`TryParse` 只要至少成功读取一帧完整 MSP 帧就返回 `true`。这不代表所有帧都校验正确；调用方还必须检查 `result.HasErrors`。

### 3.1 MSP v1 格式

MSP v1 帧格式如下：

```text
$ M direction payloadLength command payload... xorChecksum
```

| 字段 | 长度 | 说明 |
| --- | ---: | --- |
| `$M` | 2 | 固定头：`0x24 0x4D` |
| `direction` | 1 | 通常为 `<`（请求）或 `>`（响应） |
| `payloadLength` | 1 | 负载字节数 |
| `command` | 1 | 单字节 MSP 命令号 |
| `payload` | N | 命令负载 |
| `xorChecksum` | 1 | `payloadLength ^ command ^ payload 中全部字节` |

解析器以 `6 + payloadLength` 确定帧总长。校验失败的帧仍会写入 `Frames`，并添加 `InvalidChecksum` 错误；该帧不会继续解释为 DisplayPort 数据。

### 3.2 MSP v2 格式

MSP v2 帧格式如下：

```text
$ X direction flags commandLE payloadLengthLE payload... crc8
```

| 字段 | 长度 | 说明 |
| --- | ---: | --- |
| `$X` | 2 | 固定头：`0x24 0x58` |
| `direction` | 1 | 通常为 `<` 或 `>` |
| `flags` | 1 | v2 标志位，解析结果保留该值 |
| `commandLE` | 2 | 小端 16 位命令号 |
| `payloadLengthLE` | 2 | 小端 16 位负载长度 |
| `payload` | N | 命令负载 |
| `crc8` | 1 | DVB-S2 CRC-8 |

v2 CRC 从 `flags` 开始，覆盖 `flags + command + payloadLength + payload`，采用 DVB-S2 多项式 `0xD5`。解析器以 `9 + payloadLength` 确定帧总长。

### 3.3 解析问题与调用方拒绝策略

解析器不会因为单个问题立即抛出异常；它将问题写入 `Issues`，尽可能继续扫描后续数据。常见分类包括：

| 分类 | 含义 |
| --- | --- |
| `UnexpectedByte` | 当前位置不是 `$`，已跳过该字节继续扫描。 |
| `UnsupportedMarker` | `$` 后不是 `M` 或 `X`。 |
| `IncompleteHeader` | 输入在 MSP 头部尚未完整时结束。 |
| `TruncatedFrame` | 已声明的帧长度超过当前输入剩余字节。 |
| `InvalidChecksum` | v1 XOR 或 v2 CRC-8 校验失败。 |
| `DisplayPortTooShort` | `MSP_DISPLAYPORT` 负载缺少子命令或该子命令所需字段。 |
| `UnsupportedDisplayPortSubcommand` | 当前实现不支持的 DisplayPort 子命令。 |
| `InvalidDisplayPortSegmentLength` | 扩展完整帧中的段长度小于最小结构长度。 |
| `TruncatedDisplayPortSegment` | 扩展完整帧中的段超出负载边界。 |

`MainFrm.TryRenderMspOsd()` 的策略是：

1. PNG OSD 字库未加载时直接拒绝；
2. `TryParse()` 返回 `false` 时记录解析失败并拒绝；
3. `result.HasErrors` 为 `true` 时记录警告并拒绝整批数据；
4. 仅在解析无错误且后续解码器收到绘制提交时，才将快照交给渲染器。

如需在严格场景下将任意问题视为异常，可使用 `MspOsdParser.Parse()`；它会在第一条问题存在时抛出带偏移量的 `FormatException`。

### 3.4 通用流式 MSP 状态机

项目还保留了 `Msp.ProcessData()`：这是从底层 C++ 移植的逐字节 MSP v1/v2 状态机，适用于按字节持续喂入并在完整报文到达时执行回调的场景。

OSD UDP 叠加层当前采用的是“先按 UDP 数据报重组，再批量解析”的 `MspFrameReassembler + MspOsdParser` 路径，而不是直接使用该状态机。两者都支持 v1/v2 的基本帧校验，但职责不同：

| 实现 | 适用方式 | 输出 |
| --- | --- | --- |
| `Msp.ProcessData()` | 单字节流式协议处理 | 完整 `MspMsg` 的回调 |
| `MspFrameReassembler` | UDP 数据报边界整理 | 连续的完整原始 MSP 帧字节 |
| `MspOsdParser` | OSD 批量解析 | 帧、DisplayPort 命令和问题集合 |

---

## 4. MSP_DISPLAYPORT 解码

`MSP_DISPLAYPORT` 的命令号是 `182`（十六进制 `0xB6`）。只有 MSP 校验正确且命令号为 `0xB6` 的帧，才会进入 DisplayPort 负载解码。

### 4.1 标准子命令

DisplayPort 负载首字节是子命令：

| 值 | 枚举 | 处理方式 |
| ---: | --- | --- |
| `0` | `Heartbeat` | 记录命令，不改变字符内容。 |
| `1` | `Release` | 记录命令；解码器收到后清空已有屏幕状态。 |
| `2` | `ClearScreen` | 记录命令；解码器收到后清空已有屏幕状态。 |
| `3` | `WriteString` | 解析行、列、属性与后续可变长度字符数据。 |
| `4` | `DrawScreen` | 提交一次绘制；解码器在此时生成快照。 |
| `5` | `Options` | 解析字体号与显示模式。 |
| `6` | `Sys` | 记录命令，当前不改变字符内容。 |

### 4.2 `WRITE_STRING` 格式

`WRITE_STRING` 负载格式：

```text
03 row column attribute character0 character1 ...
```

其中：

- `row` 和 `column` 是 OSD 字符栅格坐标；
- `attribute` 会随命令保留；当前字符显示路径使用其低两位选择字体页；
- 从第 5 个字节开始到负载末尾均为字符码，因此字符串长度可变；
- 若负载少于 `subcommand + row + column + attribute` 共 4 字节，解析器报告 `DisplayPortTooShort`。

### 4.3 `OPTIONS` 格式

`OPTIONS` 负载格式：

```text
05 font mode
```

- `font`：设备提供的字体编号，解析器保留该值；
- `mode`：OSD 网格模式。当前解码器支持模式 `0`、`1`、`2`、`3`；模式改变时会清空之前的屏幕内容；
- 若缺少 `font` 或 `mode`，解析器报告 `DisplayPortTooShort`。

### 4.4 设备扩展完整帧 `0x35`

设备还会发送以 `0x35` 开头的扩展完整帧。其格式并非标准的单条 DisplayPort 子命令：

```text
35 prefixByte1 prefixByte2
   segment...

segment = segmentLength row column attribute characters...
```

处理规则：

1. 前三个字节视为扩展帧前缀；
2. 从偏移 `3` 开始逐段读取；
3. 每段第一个字节 `segmentLength` 包含整段长度；最小长度为 `4`，对应行、列、属性三个字段及长度字节本身；
4. 每段被转换为一条普通 `WriteString` 命令；
5. 所有段处理完成后，解析器自动追加一条 `DrawScreen` 命令。

因此 `0x35` 表示“完整画面更新”：接收方无需等待独立的标准 `DRAW_SCREEN` 包，即可在该帧处理后提交绘制。段长度小于 `4` 或段末尾越过负载边界时，整批解析结果会记录错误。

---

## 5. 错误处理与排障

### 5.1 先判断故障位于哪一层

建议按以下顺序定位：

1. **UDP 是否到达**：状态栏是否由 `OSD=disconnect` 变为端口号；若超过约 1 秒无数据，状态栏会显示 `OSD=No rec`。
2. **是否进入 OSD 处理分支**：只有透明层渲染器已经装配时，接收数据才会进入重组与解析。
3. **字库是否加载**：`EnsureOsdFontLoaded()` 要求 `_osdFont.Fonts[0]` 可用；否则数据不会被用于渲染。
4. **重组器是否输出完整帧**：跨数据报的半帧会被保留；在下一包到达前不会调用解析器。
5. **MSP 帧是否通过校验**：`InvalidChecksum` 表示 XOR 或 CRC-8 不匹配。
6. **是否为有效的 DisplayPort 数据**：必须为命令 `0xB6`，且子命令负载长度正确。
7. **是否有绘制提交**：普通写入只更新内部 OSD 状态；需要独立 `DRAW_SCREEN` 或扩展 `0x35` 的隐式提交才会产生新快照。

### 5.2 常见现象与原因

| 现象 | 优先检查项 |
| --- | --- |
| 状态栏一直是 `OSD=disconnect` | OSD UDP 通道是否已启动、设备地址和端口是否正确。 |
| 状态栏变为 `OSD=No rec` | UDP 通道仍在运行，但最近约 1 秒没有接收到数据；检查设备是否正在发送 OSD。 |
| 有 UDP 日志但无 OSD 显示 | 检查 PNG 字库是否加载、数据是否能重组成完整 MSP 帧、是否存在 `DRAW_SCREEN`。 |
| 日志出现 `msp osd parse failed` | 当前输入没有成功读取到完整 MSP 帧；检查帧头、长度字段及是否绕过了重组器。 |
| 日志出现 `msp osd overlay error` | `MspOsdParseResult.HasErrors` 为真；查看第一条错误的分类和偏移。 |
| OSD 只更新一部分或不提交 | 检查设备发送的是 `WRITE_STRING` 还是 `DRAW_SCREEN`；写入命令本身不等于提交。 |
| 偶发无法恢复 | 检查是否持续发送畸形长度或垃圾数据；重组器的 8 KiB 缓冲保护会清空尾部并等待新的有效帧头。 |

### 5.3 日志定位要点

在 `HandleOsdDataReceived()` 中，重组器输出完整帧后会记录十六进制日志：

```text
Rec from=<endpoint>,msg=<完整 MSP 帧的十六进制字符串>
```

该日志记录的是**重组后的完整 MSP 帧集合**，并不一定与单个 UDP 数据报一一对应。排查抓包与应用日志差异时，应特别注意：

- 一个日志条目可能包含多个 MSP 帧；
- 某个 UDP 数据报的前半帧可能不会立即产生日志；
- 帧前垃圾字节会在重组时被丢弃，不会出现在输出帧日志中；
- 校验失败的完整帧仍可能被记录，但会在解析阶段被拒绝。

---

