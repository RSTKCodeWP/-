# VRX Communication Troubleshooting Guide

## 1. No Response for Key Simulation Command

### Description

After sending a Key Simulation command (`cmd_type = 0x40`), the VRX does not return any response.

### Cause

The Key Simulation command is a **no-response command**. Once the VRX receives a valid command, it immediately executes the corresponding key action without sending any acknowledgment (ACK) or execution result.

### Recommendation

* This behavior is normal and should not be considered a communication failure.
* It is recommended to connect an HDMI monitor to the VRX and verify whether the command has been executed by observing the on-screen interface.

---

## 2. Command Sent Successfully but No Response or Execution

### Description

The command is sent successfully, but the VRX neither responds nor performs the requested operation.

### Troubleshooting

Verify the local network configuration of the host device.

### Network Requirement

The local IP address must be configured within the **192.168.1.x** subnet, for example:

* 192.168.1.10
* 192.168.1.100
* 192.168.1.200

If the local IP address is not within the `192.168.1.x` subnet, communication with the VRX may fail.

---

## 3. VRX Network Parameters

Use the corresponding server IP address and port according to the connection method.

| Connection Method        | Server IP     | Port |
| ------------------------ | ------------- | ---- |
| RJ45 Ethernet            | 192.169.1.100 | 9001 |
| USB Type-C (USB Network) | 192.169.3.102 | 9001 |

Please ensure that the client connects to the correct server IP address and port based on the selected connection method.

---

## 4. Force 720p60 Key Causes VRX Reboot

### Description

After sending the **Force 720p60 Key** command, the VRX automatically reboots, causing the UDP connection to be interrupted.

### Cause

The **Force 720p60 Key** command applies a new video output configuration, which requires the VRX to restart. During the reboot process, the existing UDP connection becomes invalid.

### Recommendation

1. Wait for the VRX to complete the reboot process.
2. Recreate the UDP socket if necessary.
3. Reconnect to the VRX.
4. If the application maintains a persistent connection, implement an automatic reconnection mechanism after detecting the disconnection.

---

# VRX 通信异常处理文档

## 1. 按键模拟命令无响应

### 现象

发送按键模拟命令（`cmd_type = 0x40`）后，VRX 不返回任何响应数据。

### 原因

按键模拟命令属于**无应答命令**。VRX 收到格式正确的命令后，会直接执行对应按键操作，不会返回 ACK 或执行结果。

### 处理建议

* 此现象属于正常行为，不应判定为通信异常。
* 建议将 VRX 连接 HDMI 显示器，通过观察界面变化确认按键命令是否已成功执行。

---

## 2. 命令发送成功，但 VRX 无响应且未执行

### 现象

客户端提示命令发送成功，但 VRX 无任何响应，也未执行对应操作。

### 排查方法

检查本机网络配置是否正确。

### 网络要求

本机 IP 地址必须配置为 **192.168.1.x** 网段，例如：

* 192.168.1.10
* 192.168.1.100
* 192.168.1.200

如果本机 IP 不在 `192.168.1.x` 网段，可能导致无法与 VRX 建立正常通信。

---

## 3. VRX 网络连接参数

根据不同的连接方式，请使用对应的服务器 IP 地址和端口号。

| 连接方式               | 服务器 IP        | 端口号  |
| ------------------ | ------------- | ---- |
| RJ45 网口            | 192.169.1.100 | 9001 |
| USB Type-C（USB 网络） | 192.169.3.102 | 9001 |

请确认客户端连接的目标 IP 地址及端口号与实际连接方式一致。

---

## 4. Force 720p60 键导致连接断开

### 现象

发送 **Force 720p60 Key** 命令后，VRX 会自动重启，导致 UDP 通信中断。

### 原因

执行 **Force 720p60 Key** 后，VRX 会重新启动以应用新的视频输出配置。在重启过程中，原有 UDP 连接会失效。

### 处理建议

1. 等待 VRX 完成重启。
2. 如有需要，重新创建 UDP Socket。
3. 重新连接 VRX。
4. 若应用程序维护长连接，建议在检测到连接断开后自动执行重连逻辑。
