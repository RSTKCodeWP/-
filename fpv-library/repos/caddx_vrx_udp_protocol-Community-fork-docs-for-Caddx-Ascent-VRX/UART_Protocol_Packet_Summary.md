# UART Protocol Packet Assembly & Disassembly Summary 

## Ascent VRX - The Protocol of UART Command

---

## Overview

The Ascent VRX UART protocol is a **binary frame-based communication protocol** that uses a structured packet format to exchange commands and data between a host controller and the VRX device. This document provides a comprehensive guide on how to **assemble (pack)** outgoing command packets and **disassemble (unpack)** incoming response packets.

---

## 1. Packet Frame Structure

Every UART transaction consists of a single packet with the following structure:

```
┌─────────────────┬───────────┬──────────────┬──────────────────────┬───────────┬─────────────────┐
│   Header ID     │  Command  │  Data Length │    Data Content      │  Checksum │    Tail ID      │
│    (2 Bytes)    │  (1 Byte) │   (2 Bytes)  │  (0 ~ 65535 Bytes)   │  (2 Bytes)│    (2 Bytes)    │
├─────────────────┼───────────┼──────────────┼──────────────────────┼───────────┼─────────────────┤
│   0xFE 0xEF     │  CMD      │   LEN_H L    │       Payload        │   SUM     │   0x0D 0x0A     │
└─────────────────┴───────────┴──────────────┴──────────────────────┴───────────┴─────────────────┘
```

### Field Definitions

| Field | Size | Value / Range | Description |
|-------|------|---------------|-------------|
| **Header Identifier** | 2 Bytes | `0xFE 0xEF` | Fixed start-of-frame marker |
| **Command** | 1 Byte | `0x00 ~ 0x7F` | Operation code; Bit 7 indicates direction |
| **Data Length** | 2 Bytes | `0x0000 ~ 0xFFFF` | Byte count of Data Content field only |
| **Data Content** | Variable | 0 ~ 65535 Bytes | Command-specific payload data |
| **Checksum** | 2 Bytes | Calculated | Sum of all Data Content bytes |
| **Tail Identifier** | 2 Bytes | `0x0D 0x0A` | Fixed end-of-frame marker (`CR LF`) |

---

## 2. Packet Assembly (Packing) Procedure

### Step-by-Step Packing Algorithm

#### **Step 1: Define the Command**

Determine the operation to perform:

- **Command Byte Format**: `0b0DDD_DDDD`
  - **Bit 7 = 0**: Write command (host → VRX)
  - **Bit 7 = 1**: Read command (VRX → host)
  - **Bits 6-0**: Command identifier

| Direction | Command Code Example | Description |
|-----------|---------------------|-------------|
| Write | `0x22` | Send key simulation or set parameter |
| Read | `0xA2` | Request wireless status or power info |

#### **Step 2: Construct the Data Content Payload**

Build the payload according to the specific command type:

##### **For Key Simulation Commands (cmd_type = 0x40):**

```
Data Content (4 Bytes):
┌───────────┬──────────┬─────────────┬──────┐
│ key_type  │ key_num  │ press_type  │ rsv  │
│ (1 Byte)  │ (1 Byte) │ (1 Byte)    │(1 B) │
├───────────┼──────────┼─────────────┼──────┤
│   0x40    │  0x00~09 │   0 or 1    │ 0x00 │
└───────────┴──────────┴─────────────┴──────┘
```

**Key Mapping Table:**

| key_num | press_type | Function |
|---------|------------|----------|
| 0 | 0 | Up Key |
| 1 | 0 | Down Key |
| 2 | 0 | Left Key |
| 3 | 0 | Right Key |
| 4 | 0 | Confirm Key |
| 5 | 0 | Pairing Key |
| 5 | 1 | Upgrade Key |
| 6 | 0 | Recording Key |
| 7 | 0 | Back Key |
| 7 | 1 | Force 720p60 Key |
| 9 | 0 | Debug3 Mode Key |

##### **For Wireless Control Commands:**

```
Data Content (8 Bytes):
┌───────────┬───────────────────────────────┐
│ cmd_type  │           value               │
│ (1 Byte)  │          (7 Bytes)            │
├───────────┼───────────────────────────────┤
│  0x50     │ band, channel, hop, [padding] │  ← Set Frequency
│  0x51     │ band, channel, hop, [padding] │  ← Read Frequency
│  0x52     │ rssi1, rssi2, dr, delay, state│  ← Get Wireless Status
│  0x53     │ power_idx, bitmap[4 bytes]    │  ← Get Power Index
│  0x54     │ power_idx, [padding]          │  ← Set Power Index
└───────────┴───────────────────────────────┘
```

#### **Step 3: Calculate Data Length**

Extract the byte count of the Data Content:

```python
data_length = len(data_content)  # 2-byte big-endian value
# Example: If Data Content = [0x40, 0x00, 0x00, 0x00], then data_length = 4
```

#### **Step 4: Compute Checksum**

Calculate the **16-bit cumulative sum** of all Data Content bytes:

```python
def calculate_checksum(data_content):
    """
    Compute checksum as accumulated sum of data content bytes.
    Returns a 2-byte value.
    """
    checksum = sum(data_content) & 0xFFFF  # Mask to 16 bits
    return checksum.to_bytes(2, byteorder='big')
```

> **Note:** The checksum covers **only** the Data Content field, not the entire packet.

#### **Step 5: Assemble Complete Packet**

Concatenate all fields in order:

```python
def assemble_packet(command, data_content):
    """Assemble a complete UART command packet."""
    
    HEADER = bytes([0xFE, 0xEF])
    TAIL = bytes([0x0D, 0x0A])
    
    data_length = len(data_content).to_bytes(2, byteorder='big')
    checksum = sum(data_content).to_bytes(2, byteorder='big')
    
    packet = HEADER + bytes([command]) + data_length + data_content + checksum + TAIL
    
    return packet
```

---

## 3. Practical Packing Examples

### Example 1: Simulate "Up" Key Press

**Target Packet:** `FE EF 22 00 04 40 00 00 00 04 00 D0 A0`

| Field | Hex Value | Explanation |
|-------|-----------|-------------|
| Header | `FE EF` | Start of frame |
| Command | `22` | Write command (bit7=0) |
| Data Len | `00 04` | 4 bytes of payload |
| Data[0] | `40` | key_type = 0x40 (key simulation) |
| Data[1] | `00` | key_num = 0 (Up Key) |
| Data[2] | `00` | press_type = 0 |
| Data[3] | `00` | reserved |
| Checksum | `04 00` | Sum = 0x40+0+0+0 = 64 = 0x0040 |
| Tail | `D0 A0` | End of frame |

### Example 2: Set Frequency (Band A, CH1, No Hopping)

**Target Packet:** `FE EF 22 00 08 50 00 00 00 00 00 00 00 00 05 00 D0 A0`

| Field | Hex Value | Explanation |
|-------|-----------|-------------|
| Header | `FE EF` | Start of frame |
| Command | `22` | Write command |
| Data Len | `00 08` | 8 bytes of payload |
| Data[0] | `50` | cmd_type = 0x50 (Set Frequency) |
| Data[1] | `00` | band = 0 (Band A) |
| Data[2] | `00` | channel = 0 (CH1) |
| Data[3] | `00` | hop = 0 (fixed frequency) |
| Data[4-7] | `00 00 00 00` | Padding zeros |
| Checksum | `05 00` | Sum = 0x50+0+0+0+0+0+0+0 = 80 = 0x0050 |
| Tail | `D0 A0` | End of frame |

---

## 4. Packet Disassembly (Unpacking) Procedure

### Step-by-Step Unpacking Algorithm

#### **Step 1: Locate Frame Boundaries**

Scan incoming byte stream for frame delimiters:

```python
def find_packet(byte_stream):
    """Extract a valid packet from raw byte stream."""
    
    HEADER = bytes([0xFE, 0xEF])
    TAIL = bytes([0x0D, 0x0A])
    
    start = byte_stream.find(HEADER)
    if start == -1:
        return None  # No header found
    
    end = byte_stream.find(TAIL, start)
    if end == -1:
        return None  # Incomplete packet
    
    return byte_stream[start:end + len(TAIL)]
```

#### **Step 2: Parse Header Fields**

Extract fixed-length header information:

```python
def parse_header(packet):
    """Parse header identifier and command byte."""
    
    header_id = packet[0:2]
    command = packet[2]
    
    assert header_id == bytes([0xFE, 0xEF]), "Invalid header"
    
    direction = "READ" if (command & 0x80) else "WRITE"
    cmd_code = command & 0x7F
    
    return {
        'header': header_id.hex(),
        'command': f'0x{command:02X}',
        'direction': direction,
        'opcode': f'0x{cmd_code:02X}'
    }
```

#### **Step 3: Extract Data Length**

Read the 2-byte length field (big-endian):

```python
def parse_data_length(packet):
    """Extract data content length from packet."""
    
    length_bytes = packet[3:5]
    data_length = (length_bytes[0] << 8) | length_bytes[1]
    
    return data_length
```

#### **Step 4: Extract Data Content**

Using the parsed length, extract the variable-length payload:

```python
def parse_data_content(packet, data_length):
    """Extract data content based on length field."""
    
    data_start = 5
    data_end = data_start + data_length
    
    data_content = packet[data_start:data_end]
    
    return data_content
```

#### **Step 5: Validate Checksum**

Verify data integrity by recalculating and comparing:

```python
def validate_checksum(packet, data_length):
    """Validate packet checksum."""
    
    checksum_start = 5 + data_length
    received_checksum = packet[checksum_start:checksum_start + 2]
    data_content = packet[5:checksum_start]
    
    calculated_checksum = sum(data_content).to_bytes(2, byteorder='big')
    
    is_valid = received_checksum == calculated_checksum
    
    return {
        'received': received_checksum.hex(),
        'calculated': calculated_checksum.hex(),
        'valid': is_valid
    }
```

#### **Step 6: Verify Tail Identifier**

Confirm end-of-frame marker:

```python
def parse_tail(packet, data_length):
    """Extract and verify tail identifier."""
    
    tail_start = 5 + data_length + 2
    tail_id = packet[tail_start:tail_start + 2]
    
    assert tail_id == bytes([0x0D, 0x0A]), "Invalid tail"
    
    return tail_id.hex()
```

#### **Complete Unpacking Function**

```python
def disassemble_packet(packet):
    """Full packet disassembly with validation."""
    
    result = {}
    
    # Step 1-2: Parse header
    result.update(parse_header(packet))
    
    # Step 3: Get data length
    data_length = parse_data_length(packet)
    result['data_length'] = data_length
    
    # Step 4: Extract payload
    result['data_content'] = parse_data_content(packet, data_length).hex()
    
    # Step 5: Verify checksum
    result['checksum'] = validate_checksum(packet, data_length)
    
    # Step 6: Verify tail
    result['tail'] = parse_tail(packet, data_length)
    
    return result
```

---

## 5. Response Packet Handling

When sending a **read command** (Bit 7 = 1), the VRX device responds with a packet containing the requested data:

### Response Structure for Read Commands

| Command | Response cmd_type | Returned Data |
|---------|-------------------|---------------|
| `0x51` (Read Freq) | `0x51` | band, channel, hop status |
| `0x52` (Get Status) | `0x52` | rssi1, rssi2, data_rate, delay, connection_state |
| `0x53` (Get Power) | `0x53` | current_power_index, settable_bitmap |

### Example: Parsing Get Power Index Response

**Response Packet:** `FE EF A2 00 08 53 05 01 FF FF FF FF 00 58 D0 A0`

```
┌─────────────────────────────────────────────────────────────────────┐
│ PARSING BREAKDOWN                                                   │
├─────────────────────────────────────────────────────────────────────┤
│ Header:      FE EF          → Valid start marker                    │
│ Command:     A2              → Read response (bit7=1)              │
│ Data Length: 00 08           → 8 bytes of payload                   │
│ Data[0]:     53              → cmd_type = Get Power Index           │
│ Data[1]:     05              → Current power index = 5 (350 mW)     │
│ Data[2-5]:   01 FF FF FF     → Settable bitmap                      │
│              → Indices 0,8-23 are settable                          │
│ Checksum:    00 58           → Sum = 0x0058 (valid)                 │
│ Tail:        D0 A0           → Valid end marker                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. Quick Reference: Packing/Unpacking Flowchart

```
                    ┌─────────────────────┐
                    │   PACKING (TX)      │
                    └─────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ 1. Set Command   │
                    │    (with dir bit)│
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 2. Build Payload │
                    │ (per cmd format) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 3. Calc Length   │
                    │  = len(payload)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 4. Calc Checksum │
                    │  = sum(payload)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 5. Concatenate:  │
                    │ HDR+CMD+LEN+     │
                    │ DATA+CKSUM+TAIL  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 6. Transmit via  │
                    │    UART @ 3.3V   │
                    └─────────────────┘


                    ┌─────────────────────┐
                    │ UNPACKING (RX)      │
                    └─────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ 1. Scan for FE EF│
                    │   (header sync)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 2. Read CMD byte │
                    │  Check direction │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 3. Read 2-byte   │
                    │    data length   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 4. Extract N     │
                    │   data bytes     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 5. Verify CKSUM  │
                    │  Error if mismatch│
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 6. Confirm 0D 0A │
                    │   (end marker)   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 7. Process data  │
                    │ per cmd_type     │
                    └─────────────────┘
```

---

## 7. Implementation Tips

### Common Pitfalls to Avoid

| Issue | Cause | Solution |
|-------|-------|----------|
| Wrong checksum | Including header/tail in sum | Sum **only** Data Content bytes |
| Byte order error | Little-endian length encoding | Use **big-endian** for Data Length and Checksum |
| Missing data | Incorrect length parsing | Ensure 2-byte length is read before extracting payload |
| Frame sync loss | Noise corruption | Always scan for `FE EF` header; implement timeout |

### Recommended UART Configuration

| Parameter | Value |
|-----------|-------|
| Voltage Level | 3.3V |
| Baud Rate | Refer to device datasheet |
| Data Bits | 8 |
| Parity | None |
| Stop Bits | 1 |
| Flow Control | None |

---

## 8. Summary

This UART protocol follows a straightforward **TLV (Type-Length-Value)** pattern with fixed delimiters:

### **Packing (TX):**
1. Prepare command byte with direction flag
2. Construct payload per command specification
3. Calculate payload length (2 bytes, big-endian)
4. Compute checksum from payload bytes
5. Wrap with header (`FE EF`) and tail (`0D 0A`)
6. Transmit via 3.3V UART

### **Unpacking (RX):**
1. Synchronize on header pattern (`FE EF`)
2. Extract command and determine direction
3. Read 2-byte length field
4. Extract payload using length value
5. Validate checksum against payload
6. Confirm tail marker (`0D 0A`)
7. Interpret payload per command type

---


# UART协议数据包组包与解包技术总结

## Ascent VRX - UART命令协议

---

## 概述

Ascent VRX UART协议是一种**基于二进制帧的通信协议**，采用结构化的数据包格式在主机控制器与VRX设备之间交换命令和数据。本文档全面介绍了如何**组装（组包）**发送命令包以及**拆解（解包）**接收响应包。

---

## 1. 数据包帧结构

每次UART通信都由一个具有以下结构的单一数据包组成：

```
┌─────────────────┬───────────┬──────────────┬──────────────────────┬───────────┬─────────────────┐
│   帧头标识      │   命令    │   数据长度   │     数据内容         │   校验和  │   帧尾标识      │
│    (2字节)      │  (1字节)  │   (2字节)    │  (0 ~ 65535 字节)    │  (2字节)  │    (2字节)      │
├─────────────────┼───────────┼──────────────┼──────────────────────┼───────────┼─────────────────┤
│   0xFE 0xEF     │   CMD     │   LEN_H L    │       载荷数据       │   SUM     │   0x0D 0x0A     │
└─────────────────┴───────────┴──────────────┴──────────────────────┴───────────┴─────────────────┘
```

### 字段定义

| 字段名称 | 大小 | 取值范围 | 说明 |
|---------|------|----------|------|
| **帧头标识（Header Identifier）** | 2字节 | `0xFE 0xEF` | 固定的帧起始标记 |
| **命令（Command）** | 1字节 | `0x00 ~ 0x7F` | 操作码；最高位(Bit7)表示方向 |
| **数据长度（Data Length）** | 2字节 | `0x0000 ~ 0xFFFF` | 数据内容字段的字节数 |
| **数据内容（Data Content）** | 可变 | 0 ~ 65535字节 | 命令特定的载荷数据 |
| **校验和（Checksum）** | 2字节 | 计算得出 | 所有数据内容字节的累加和 |
| **帧尾标识（Tail Identifier）** | 2字节 | `0x0D 0x0A` | 固定的帧结束标记（回车换行） |

---

## 2. 组包流程（Packet Assembly）

### 分步组包算法

#### **第1步：定义命令**

确定要执行的操作：

- **命令字节格式**: `0b0DDD_DDDD`
  - **Bit7 = 0**: 写命令（主机 → VRX）
  - **Bit7 = 1**: 读命令（VRX → 主机）
  - **Bits 6-0**: 命令标识符

| 方向 | 命令码示例 | 说明 |
|------|-----------|------|
| 写操作 | `0x22` | 发送按键模拟或设置参数 |
| 读操作 | `0xA2` | 请求无线状态或功率信息 |

#### **第2步：构建数据内容载荷**

根据具体命令类型构建载荷：

##### **按键模拟命令（cmd_type = 0x40）：**

```
数据内容（4字节）：
┌───────────┬──────────┬─────────────┬──────┐
│ key_type  │ key_num  │ press_type  │ rsv  │
│ (1字节)   │ (1字节)  │ (1字节)     │(1字节)│
├───────────┼──────────┼─────────────┼──────┤
│   0x40    │  0x00~09 │   0 或 1    │ 0x00 │
└───────────┴──────────┴─────────────┴──────┘
```

**按键映射表：**

| key_num | press_type | 功能说明 |
|---------|------------|----------|
| 0 | 0 | 上键（Up Key）|
| 1 | 0 | 下键（Down Key）|
| 2 | 0 | 左键（Left Key）|
| 3 | 0 | 右键（Right Key）|
| 4 | 0 | 确认键（Confirm Key）|
| 5 | 0 | 配对键（Pairing Key）|
| 5 | 1 | 升级键（Upgrade Key）|
| 6 | 0 | 录制键（Recording Key）|
| 7 | 0 | 返回键（Back Key）|
| 7 | 1 | 强制720p60键（Force 720p60 Key）|
| 9 | 0 | Debug3模式键（Debug3 Mode Key）|

##### **无线控制命令：**

```
数据内容（8字节）：
┌───────────┬───────────────────────────────┐
│ cmd_type  │           value               │
│ (1字节)   │          (7字节)              │
├───────────┼───────────────────────────────┤
│  0x50     │ band, channel, hop, [填充]    │  ← 设置频率
│  0x51     │ band, channel, hop, [填充]    │  ← 读取频率
│  0x52     │ rssi1, rssi2, dr, delay, state│  ← 获取无线状态
│  0x53     │ power_idx, bitmap[4字节]      │  ← 获取功率索引
│  0x54     │ power_idx, [填充]             │  ← 设置功率索引
└───────────┴───────────────────────────────┘
```

#### **第3步：计算数据长度**

提取数据内容的字节数：

```python
data_length = len(data_content)  # 2字节大端序值
# 示例：若数据内容 = [0x40, 0x00, 0x00, 0x00]，则 data_length = 4
```

#### **第4步：计算校验和**

计算所有数据内容字节的**16位累加和**：

```python
def calculate_checksum(data_content):
    """
    计算校验和：对数据内容字节进行累加求和。
    返回2字节值。
    """
    checksum = sum(data_content) & 0xFFFF  # 掩码至16位
    return checksum.to_bytes(2, byteorder='big')
```

> **注意：** 校验和**仅覆盖**数据内容字段，不包括整个数据包的其他部分。

#### **第5步：组装完整数据包**

按顺序拼接所有字段：

```python
def assemble_packet(command, data_content):
    """组装完整的UART命令数据包"""
    
    HEADER = bytes([0xFE, 0xEF])  # 帧头
    TAIL = bytes([0x0D, 0x0A])    # 帧尾
    
    data_length = len(data_content).to_bytes(2, byteorder='big')  # 大端序长度
    checksum = sum(data_content).to_bytes(2, byteorder='big')    # 大端序校验和
    
    packet = HEADER + bytes([command]) + data_length + data_content + checksum + TAIL
    
    return packet
```

---

## 3. 实际组包示例

### 示例1：模拟"上键"按下

**目标数据包:** `FE EF 22 00 04 40 00 00 00 04 00 D0 A0`

| 字段 | 十六进制值 | 说明 |
|------|-----------|------|
| 帧头 | `FE EF` | 帧起始标记 |
| 命令 | `22` | 写命令（bit7=0）|
| 数据长度 | `00 04` | 4字节载荷 |
| Data[0] | `40` | key_type = 0x40（按键模拟）|
| Data[1] | `00` | key_num = 0（上键）|
| Data[2] | `00` | press_type = 0 |
| Data[3] | `00` | 保留位 |
| 校验和 | `04 00` | 累加和 = 0x40+0+0+0 = 64 = 0x0040 |
| 帧尾 | `D0 A0` | 帧结束标记 |

### 示例2：设置频率（频段A，CH1，不跳频）

**目标数据包:** `FE EF 22 00 08 50 00 00 00 00 00 00 00 00 05 00 D0 A0`

| 字段 | 十六进制值 | 说明 |
|------|-----------|------|
| 帧头 | `FE EF` | 帧起始标记 |
| 命令 | `22` | 写命令 |
| 数据长度 | `00 08` | 8字节载荷 |
| Data[0] | `50` | cmd_type = 0x50（设置频率）|
| Data[1] | `00` | band = 0（频段A）|
| Data[2] | `00` | channel = 0（CH1信道）|
| Data[3] | `00` | hop = 0（固定频率）|
| Data[4-7] | `00 00 00 00` | 填充零字节 |
| 校验和 | `05 00` | 累加和 = 0x50+0+0+0+0+0+0+0 = 80 = 0x0050 |
| 帧尾 | `D0 A0` | 帧结束标记 |

---

## 4. 解包流程（Packet Disassembly）

### 分步解包算法

#### **第1步：定位帧边界**

扫描输入的字节流以查找帧分隔符：

```python
def find_packet(byte_stream):
    """从原始字节流中提取有效数据包"""
    
    HEADER = bytes([0xFE, 0xEF])  # 帧头标记
    TAIL = bytes([0x0D, 0x0A])    # 帧尾标记
    
    start = byte_stream.find(HEADER)
    if start == -1:
        return None  # 未找到帧头
    
    end = byte_stream.find(TAIL, start)
    if end == -1:
        return None  # 数据包不完整
    
    return byte_stream[start:end + len(TAIL)]
```

#### **第2步：解析帧头字段**

提取固定长度的帧头信息：

```python
def parse_header(packet):
    """解析帧头标识和命令字节"""
    
    header_id = packet[0:2]
    command = packet[2]
    
    assert header_id == bytes([0xFE, 0xEF]), "无效的帧头"
    
    direction = "读" if (command & 0x80) else "写"
    cmd_code = command & 0x7F
    
    return {
        'header': header_id.hex(),
        'command': f'0x{command:02X}',
        'direction': direction,
        'opcode': f'0x{cmd_code:02X}'
    }
```

#### **第3步：提取数据长度**

读取2字节长度字段（大端序）：

```python
def parse_data_length(packet):
    """从数据包中提取数据内容长度"""
    
    length_bytes = packet[3:5]
    data_length = (length_bytes[0] << 8) | length_bytes[1]
    
    return data_length
```

#### **第4步：提取数据内容**

使用解析出的长度值提取可变长度载荷：

```python
def parse_data_content(packet, data_length):
    """根据长度字段提取数据内容"""
    
    data_start = 5          # 数据起始位置
    data_end = data_start + data_length  # 数据结束位置
    
    data_content = packet[data_start:data_end]
    
    return data_content
```

#### **第5步：验证校验和**

通过重新计算并比较来验证数据完整性：

```python
def validate_checksum(packet, data_length):
    """验证数据包校验和"""
    
    checksum_start = 5 + data_length
    received_checksum = packet[checksum_start:checksum_start + 2]  # 接收到的校验和
    data_content = packet[5:checksum_start]                       # 数据内容
    
    calculated_checksum = sum(data_content).to_bytes(2, byteorder='big')  # 计算的校验和
    
    is_valid = received_checksum == calculated_checksum
    
    return {
        'received': received_checksum.hex(),
        'calculated': calculated_checksum.hex(),
        'valid': is_valid
    }
```

#### **第6步：验证帧尾标识**

确认帧结束标记：

```python
def parse_tail(packet, data_length):
    """提取并验证帧尾标识"""
    
    tail_start = 5 + data_length + 2
    tail_id = packet[tail_start:tail_start + 2]
    
    assert tail_id == bytes([0x0D, 0x0A]), "无效的帧尾"
    
    return tail_id.hex()
```

#### **完整解包函数**

```python
def disassemble_packet(packet):
    """完整的数据包解包及验证"""
    
    result = {}
    
    # 第1-2步：解析帧头
    result.update(parse_header(packet))
    
    # 第3步：获取数据长度
    data_length = parse_data_length(packet)
    result['data_length'] = data_length
    
    # 第4步：提取载荷
    result['data_content'] = parse_data_content(packet, data_length).hex()
    
    # 第5步：验证校验和
    result['checksum'] = validate_checksum(packet, data_length)
    
    # 第6步：验证帧尾
    result['tail'] = parse_tail(packet, data_length)
    
    return result
```

---

## 5. 响应数据包处理

当发送**读命令**（Bit7 = 1）时，VRX设备会返回包含请求数据的响应数据包：

### 读命令响应结构

| 命令码 | 响应cmd_type | 返回数据 |
|--------|-------------|----------|
| `0x51`（读取频率）| `0x51` | 频段、信道、跳频状态 |
| `0x52`（获取状态）| `0x52` | rssi1、rssi2、数据速率、延迟、连接状态 |
| `0x53`（获取功率）| `0x53` | 当前功率索引、可设置位图 |

### 示例：解析获取功率索引响应

**响应数据包:** `FE EF A2 00 08 53 05 01 FF FF FF FF 00 58 D0 A0`

```
┌─────────────────────────────────────────────────────────────────────┐
│                        解析分解图                                    │
├─────────────────────────────────────────────────────────────────────┤
│ 帧头:        FE EF          → 有效的起始标记                        │
│ 命令:        A2              → 读响应（bit7=1）                     │
│ 数据长度:    00 08           → 8字节载荷                            │
│ Data[0]:     53              → cmd_type = 获取功率索引              │
│ Data[1]:     05              → 当前功率索引 = 5（350 mW）           │
│ Data[2-5]:   01 FF FF FF     → 可设置位图                           │
│             → 索引 0, 8-23 可设置                                   │
│ 校验和:      00 58           → 累加和 = 0x0058（有效）              │
│ 帧尾:        D0 A0           → 有效的结束标记                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. 快速参考：组包/解包流程图

```
                    ┌─────────────────────┐
                    │    组包流程 (发送)    │
                    └─────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ 1. 设置命令      │
                    │   （含方向位）    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 2. 构建载荷数据  │
                    │ （按命令格式）   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 3. 计算数据长度  │
                    │  = len(载荷)    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 4. 计算校验和    │
                    │  = sum(载荷)    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 5. 拼接完整帧:   │
                    │ 帧头+命令+长度+  │
                    │ 数据+校验+帧尾   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 6. 通过3.3V     │
                    │    UART发送     │
                    └─────────────────┘


                    ┌─────────────────────┐
                    │    解包流程 (接收)    │
                    └─────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ 1. 扫描 FE EF    │
                    │   （帧头同步）    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 2. 读取命令字节  │
                    │   判断通信方向    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 3. 读取2字节     │
                    │    数据长度      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 4. 提取N个       │
                    │    数据字节      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 5. 验证校验和    │
                    │  不匹配则报错    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 6. 确认 0D 0A   │
                    │   （结束标记）   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 7. 按cmd_type   │
                    │    处理数据      │
                    └─────────────────┘
```

---

## 7. 实现要点

### 常见问题及解决方案

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 校验和错误 | 将帧头/帧尾计入累加和 | **仅对**数据内容字节求和 |
| 字节序错误 | 使用小端序编码长度 | 数据长度和校验和使用**大端序** |
| 数据丢失 | 长度字段解析错误 | 提取载荷前确保正确读取2字节长度 |
| 帧同步丢失 | 噪声干扰导致损坏 | 始终扫描`FE EF`帧头；实现超时机制 |

### 推荐UART配置参数

| 参数 | 取值 |
|------|------|
| 电平电压 | 3.3V |
| 波特率 | 请参考设备数据手册 |
| 数据位 | 8 |
| 校验位 | 无 |
| 停止位 | 1 |
| 流控制 | 无 |

---

## 8. 总结

本UART协议遵循简洁的**TLV（类型-长度-值）**模式，并使用固定的分隔符：

### **组包（发送端）：**
1. 准备带方向标志的命令字节
2. 按命令规范构建载荷数据
3. 计算载荷长度（2字节，大端序）
4. 根据载荷字节计算校验和
5. 添加帧头（`FE EF`）和帧尾（`0D 0A`）封装
6. 通过3.3V UART接口发送

### **解包（接收端）：**
1. 在帧头模式（`FE EF`）上同步
2. 提取命令并判断通信方向
3. 读取2字节长度字段
4. 使用长度值提取载荷
5. 对照载荷验证校验和
6. 确认帧尾标记（`0D 0A`）
7. 按命令类型解释载荷数据

---


