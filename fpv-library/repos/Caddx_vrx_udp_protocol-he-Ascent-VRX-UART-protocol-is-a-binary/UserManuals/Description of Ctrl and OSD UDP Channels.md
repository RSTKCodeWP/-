# Ctrl 与 OSD UDP 通道说明

本文说明 GroundConfiguration 与 VRX 设备之间两个 UDP 通道的职责、启动方式和协作关系：

- **Ctrl UDP：9001**，用于设备控制、配置和模式切换；
- **OSD UDP：9200**，用于接收设备回传的 MSP DisplayPort OSD 数据。

设备默认连接参数由 `DeviceConnectionProfileCatalog` 定义：

| 连接方式 | 设备 IP | Ctrl UDP | OSD UDP |
| --- | --- | ---: | ---: |
| RJ45 | `192.168.1.100` | `9001` | `9200` |
| USB-C | `192.168.3.102` | `9001` | `9200` |

端口不应在 UI 事件中分散硬编码；应通过 `DeviceConnectionProfile` 的 `CtrlPort` 和 `OSDPort` 使用。

---

## 1. Ctrl UDP：9001

### 1.1 职责

9001 是 GroundConfiguration 向 VRX 设备发送控制和配置指令的主通道，具体包括：

- 遥控按键或菜单类命令；
- 无线图传的频点、状态和功率查询；
- 无线图传的频点、功率设置；
- CRSF 透传模式切换；
- OSD 输出模式切换。

该通道由 `VrxDeviceSession` 持有的 `controlTransport` 管理。Presenter 调用 `StartDeviceSession(profile)` 后，最终执行：

```csharp
controlTransport.Start(profile.UDPIp, profile.CtrlPort);
```

因此默认会连接设备的 `IP:9001`。

### 1.2 发送控制命令

遥控命令由 `VrxCommandPacketFactory.Build()` 构造，并经控制通道发送：

```text
MainPresenter.SendRemoteCommand
  → VrxDeviceSession.SendRemoteCommand
  → VrxCommandPacketFactory.Build
  → controlTransport.Send
  → 设备 UDP:9001
```

无线图传的协议命令由 `AscentVrxProtocol` 构建，例如：

- `BuildGetFrequency()`；
- `BuildGetWirelessStatus()`；
- `BuildGetPowerIndex()`；
- `BuildSetFrequency(...)`；
- `BuildSetPowerIndex(...)`。

### 1.3 模式切换

9001 还负责要求设备改变透传/输出模式：

| 调用 | 下发内容 | 目的 |
| --- | --- | --- |
| `SendCrsfModeSwitch()` | CRSF 模式切换包 | 请求设备进入 CRSF 透传模式。 |
| `SendOSDModeSwitch()` | OSD 模式切换包 | 请求设备进入 OSD 输出模式，使设备向 9200 输出 MSP OSD 数据。 |

调用路径如下：

```text
MainPresenter.SendOSDModeSwitch
  → VrxDeviceSession.SendOSDModeSwitch
  → VrxPacketBuilder.BuildSetModePacket(PassthroughMode.OSD)
  → Ctrl UDP:9001
```

当前 `VrxDeviceSession.Start()` 仅启动 9001 控制通道；其中自动发送 CRSF/OSD 模式切换的代码已被注释。因此需要由界面或 Presenter 显式调用 `SendCrsfModeSwitch()` 或 `SendOSDModeSwitch()`。

### 1.4 接收设备回包

控制通道也会接收设备回传数据。`VrxDeviceSession` 订阅 `controlTransport.DataReceived`，收到数据后：

1. 记录来源端点、长度和十六进制内容；
2. 使用 `AscentVrxProtocol.TryParseFrame()` 尝试按 VRX 帧格式解析；
3. 解析成功时记录方向、无线命令类型和负载；
4. 解析失败时只记录原始数据，不中断 UDP 通道。

VRX 控制帧格式与 MSP 不同，其典型边界是：

```text
FE EF ... 0D 0A
```

因此，9001 回包不能直接交给 MSP OSD 解析器。

---

## 2. OSD UDP：9200

### 2.1 职责

9200 是独立于控制通道的 OSD 数据通道，主要用于：

- 接收设备回传的 MSP v1/v2 帧；
- 从 `MSP_DISPLAYPORT`（命令 `0xB6`）中解析 OSD 字符数据；
- 将解析结果显示到 RTSP 视频上方的透明 GDI+ OSD 图层；
- 在调试场景下向设备发送原始 UDP 字节。

该通道由 `MainPresenter` 持有的 `osdTransport` 管理，而不属于 `VrxDeviceSession` 的控制/CRSF 双通道。

### 2.2 启动过程

调用 `MainPresenter.StartOsdChannel(ip, port)` 会：

1. 启动 `osdTransport`；
2. 向设备发送探测字节 `24 4D 53 50`，即 ASCII 文本 `$MSP`；
3. 将 UDP 接收事件经 `IMainView.HandleOsdDataReceived()` 交给 `MainFrm`。

核心逻辑：

```csharp
osdTransport.Start(ip, port);
osdTransport.Send(new byte[] { 0x24, 0x4D, 0x53, 0x50 });
```

启动后的数据流：

```text
设备 UDP:9200
  → osdTransport.DataReceived
  → MainPresenter
  → IMainView.HandleOsdDataReceived
  → MainFrm.HandleOsdDataReceived
```

### 2.3 OSD 数据接收与渲染

`MainFrm.HandleOsdDataReceived()` 收到 UDP 数据后：

1. 更新最近一次 OSD 数据到达时间；
2. 切换到 UI 线程，将状态栏更新为来源端口并显示绿色；
3. 若透明 OSD 渲染器已装配，则将数据交给 `MspFrameReassembler`；
4. 重组器仅输出完整 MSP 帧，跨 UDP 数据报的残帧会保留等待后续数据；
5. `MspOsdParser` 解析 MSP v1/v2 并校验 XOR 或 CRC-8；
6. `MspDisplayPortDecoder` 将 DisplayPort 命令应用到 OSD 状态；
7. 收到 `DRAW_SCREEN` 或设备扩展完整帧的隐式提交后，生成快照并交给 `GdiOsdOverlayRenderer`。

```text
OSD UDP:9200
  → MspFrameReassembler
  → MspOsdParser
  → MspDisplayPortDecoder
  → OsdOverlaySnapshot
  → GdiOsdOverlayRenderer
  → 透明 OSD 图层
```

详细的 MSP 帧格式、DisplayPort 子命令和解析错误处理见 [MSP解析与OSD渲染说明.md](MSP解析与OSD渲染说明.md)。

### 2.4 通道状态与超时

OSD 数据看门狗独立于 UDP 接收循环运行：

- 收到数据时，状态栏显示 `OSD=<来源端口>` 并标记为绿色；
- 超过约 1 秒未收到数据时：
  - 若 9200 通道仍在运行，显示 `OSD=No rec`；
  - 若通道未运行，显示 `OSD=disconnect`；
- 看门狗每 500 ms 检查一次。

这表示“UDP 通道已启动”和“设备实际正在输出 OSD”是两个不同状态。

### 2.5 原始数据发送

`MainPresenter.SendOsdData(byte[] data)` 可以向 OSD 通道发送原始字节。此接口仅用于调试或协议验证；正常 OSD 显示流程以设备向 9200 回传 MSP DisplayPort 数据为主。

---

## 3. 两个端口的协作关系

两个通道分工明确：

```text
Ctrl UDP:9001
  ├─ 下发控制、查询、配置命令
  ├─ 下发 CRSF 或 OSD 模式切换命令
  └─ 接收并记录 VRX 控制协议回包

OSD UDP:9200
  ├─ 接收 MSP DisplayPort OSD 数据
  ├─ 重组、解析和校验 MSP 帧
  └─ 更新 RTSP 视频上方的透明 OSD 图层
```

典型 OSD 工作流程：

```text
1. 启动 Ctrl UDP:9001
2. 启动 OSD UDP:9200
3. 通过 Ctrl UDP:9001 发送 OSD 模式切换命令
4. 设备开始向 OSD UDP:9200 回传 MSP DisplayPort 数据
5. 应用解析数据并更新透明 OSD 图层
```

简言之：

> **9001 负责命令设备进入或改变工作状态；9200 负责接收设备输出的 OSD 内容。**

---

## 4. 关键源码索引

| 目标 | 文件 |
| --- | --- |
| 设备 IP、9001、9200 默认 profile | [DeviceConnectionProfileCatalog.cs](GroundConfiguration/04_Configuration/DeviceConnectionProfileCatalog.cs) |
| profile 中控制、CRSF、OSD 端口定义 | [DeviceConnectionProfile.cs](GroundConfiguration/04_Configuration/DeviceConnectionProfile.cs) |
| 9001 控制通道、命令发送、回包日志、模式切换 | [VrxDeviceSession.cs](GroundConfiguration/05_Device/VrxDeviceSession.cs) |
| OSD 通道启动、探测包、接收回调与重启 | [MainPresenter.cs](GroundConfiguration/03_Presentation/MainPresenter.cs) |
| OSD UDP 数据接收、重组和渲染入口 | [MainFrm.cs](GroundConfiguration/00_View/MainFrm.cs) |
| MSP 帧重组、解析和 DisplayPort 解码 | [MSP解析与OSD渲染说明.md](MSP解析与OSD渲染说明.md) |
