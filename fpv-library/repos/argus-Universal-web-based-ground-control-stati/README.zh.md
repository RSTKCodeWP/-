# Argus

**中文** | [English](README.md)

> 通用 Web 端 MAVLink 无人机地面站。

[![CI](https://github.com/L-X-Yao/argus/actions/workflows/ci.yml/badge.svg)](https://github.com/L-X-Yao/argus/actions/workflows/ci.yml)
![Version](https://img.shields.io/github/v/tag/L-X-Yao/argus?label=version&color=blue)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![Tests](https://img.shields.io/badge/tests-1800%2B%20passing-brightgreen.svg)
![i18n](https://img.shields.io/badge/i18n-10%20languages-orange.svg)

<p align="center"><img src="docs/screenshots/hero.png" alt="Argus GCS — 地图、HUD 与遥测面板" width="900"></p>

## 定位

Argus 是一个通用 **Web 地面站** —— 一个浏览器界面控制 MAVLink 无人机，支持桌面 / 平板 / 手机，内置 10 种语言，无需安装，打开网址即可使用。

> **当前状态**：ArduPilot 已在生产环境验证。PX4 前端适配器已搭建，后端可读取 `HEARTBEAT.autopilot` 字节，但端到端链路尚未贯通 —— 详见 `CLAUDE.md ## PX4 Status`。

为什么还需要一个 GCS：

| 现有 GCS | 局限性 |
|---|---|
| QGroundControl | 原生应用，安装重，无 Web 版本 |
| Mission Planner | 仅 Windows，传统 UI |
| 云平台 (FlytBase, ADOS) | 厂商锁定，闭源 |

Argus 填补空缺：**开源 + Web 原生 + 协议无关 + 支持白标定制**。

## 功能一览

| 分类 | 功能 |
|---|---|
| **连接** | TCP / UDP / Serial / WebSerial（浏览器直连 USB，遥测和基础控制无需后端） |
| **协议** | MAVLink v2（ArduPilot 生产验证；PX4 适配器已搭建，未接入） |
| **机型** | 多旋翼、固定翼、VTOL、地面车、水下潜航器 |
| **地图** | 8 种图源（高德、Google、OSM、Esri、CartoDB、天地图）+ 3D 地形（MapLibre GL）+ 离线 mbtiles |
| **航线** | 航点 / 曲线 / 盘旋 / 测绘网格 / 交叉 / 螺旋 / 环绕 + 地形剖面与净空检查 |
| **格式** | `.waypoints` (MP) / `.plan` (QGC) / `.gpx` / `.kml` 导入导出 |
| **参数** | 元数据驱动 UI（描述/范围/单位/枚举/位掩码），树形视图，差异导出，恢复默认 |
| **校准** | 罗盘、加速度计、陀螺仪、水平、气压计向导，实时进度 |
| **RTK** | NTRIP 客户端，HTTP/1.0 + ICY-200 协商，RTCM 流式注入 |
| **固件** | 上传 `.apj`，在线固件浏览器，重启至 Bootloader |
| **编队** | 多机仪表盘，每架飞机实时遥测 |
| **视频** | RTSP 代理，AR 航点叠加，截图 |
| **HUD** | PFD（姿态/速度/高度/罗盘/风向），实时图表，EKF 状态 |
| **语音** | 10 语言本地化语音播报（模式、电量、高度、航点） |
| **多语言** | 10 种语言（中/英/日/韩/德/法/西/葡/俄/阿）+ RTL |
| **离线** | PWA + Service Worker，mbtiles 支持，瓦片缓存（5000 条 LRU） |
| **桌面** | Tauri v2 打包（Windows MSI/NSIS 安装包） |
| **安全** | Token 认证，SSRF + 路径穿越防护，statustext 过滤 |

## 快速开始

首次安装：

```bash
npm install        # 前端依赖
pip install -e .   # 后端依赖（使用 pyproject.toml）
```

### 方式一 —— 真实硬件（USB 连接 Pixhawk）

```bash
python run.py                  # 后端启动于 http://localhost:8100
# 另开终端：
npm run dev                    # 开发服务器于 http://localhost:5173
# 打开网址，插入 USB，从下拉框选择串口
```

生产部署：`npm run build` 构建前端到 `dist/`，然后 `python run.py` 在 `:8100` 提供服务。

### 方式二 —— ArduPilot SITL

```bash
sim_vehicle.py -v ArduCopter --out=udp:127.0.0.1:14550
python run.py
# 打开 UI，点击 "SITL" 快速连接按钮
```

### 方式三 —— 内置 MAVLink 模拟器（无需飞控、无需 SITL）

```bash
python run.py --sim            # 同时启动后端 + sim_pllink.py
# 连接到 "tcp:localhost:5770"
```

模拟器（`scripts/sim_pllink.py`）发送仿真遥测数据（GPS、姿态、电量消耗、心跳），响应解锁/锁定/模式切换命令。

### WebSerial（完全无需后端）

用 Chrome/Edge 打开 Argus，点击 **USB** 按钮，选择飞控。遥测、解锁/锁定/模式/RTL、参数读写、航线上传/下载/清除、围栏上传、日志列表/下载、全部 5 种校准类型均通过 WebSerial 和内置 TypeScript MAVLink v2 编解码器直连。固件上传需要 Python 后端。

## 架构

```
+------------------------------------------+
|  浏览器 (Svelte 5 + TypeScript 6)        |
|  78 组件 + 159 库文件, 22K 行             |
|  MAVLink v2 编解码器 (纯 TS)              |
|  WebSerial 直连 USB                       |
|  43 个懒加载面板 + 视图分割               |
+------------------------------------------+
|          WebSocket (JSON 增量推送)        |
+------------------------------------------+
|  Python 后端 (FastAPI + uvicorn)          |
|  29 模块, 4.9K 行                        |
|  MAVLink 分发 + 32 消息处理器             |
|  51 条命令, 瓦片/视频/固件 API            |
+------------------------------------------+
|          MAVLink v2                       |
|  TCP / UDP / Serial / PL-Link            |
+------------------------------------------+
|  飞控 (ArduPilot / PX4)                   |
+------------------------------------------+
```

### 核心模块

| 模块 | 说明 |
|---|---|
| `src/lib/mavlink/` | 纯 TypeScript MAVLink v2 编解码器，含 CRC 校验 |
| `src/lib/fc/` | 飞控适配器（ArduPilot 已接入；PX4 模式表存在但未在生产代码中引入） |
| `src/lib/transport.ts` | 双模式传输（WebSocket 后端 / WebSerial 直连） |
| `src/lib/serial.ts` | Web Serial API 封装，含飞控 USB 厂商过滤器 |
| `src/lib/terrain.ts` | SRTM 高程查询，用于地形跟随航线 |
| `src/lib/missionIO.ts` | 航线导入导出（`.waypoints` / `.plan` / `.gpx`） |
| `src/lib/survey.ts` | 测绘图案生成（网格、交叉、螺旋、环绕） |
| `src/lib/i18n.svelte.ts` | 10 语言国际化，支持 RTL |
| `backend/drone_link.py` | MAVLink 连接、帧解析、状态管理 |
| `backend/commands/` | 51 条命令处理器（解锁、模式、航线、校准、云台、NTRIP 等） |
| `backend/config.py` | 集中配置（所有超时/端口/速率常量） |

## 开发

```bash
# 后端单元测试 + 契约测试
python -m pytest tests/test_unit_*.py tests/test_contract_*.py -v

# 前端单元测试
npx vitest run

# 类型检查（必须 0 错误 0 警告）
npx svelte-check --tsconfig ./tsconfig.json

# Python 代码检查
ruff check backend/ scripts/ tests/

# E2E 测试（需要开发服务器）
npx playwright test

# 生产构建
npm run build
```

**Git 钩子**（自动从 `.githooks/` 安装）：
- **pre-commit**：ruff + svelte-check（约 3 秒）
- **pre-push**：完整 vitest + pytest 测试门

**深入文档**：

- [`CLAUDE.md`](CLAUDE.md) — 项目规范、PX4 状态、协议耦合纪律
- [`docs/FEATURE_CHECKLIST.md`](docs/FEATURE_CHECKLIST.md) — 功能验证状态
- [`docs/protocol_design.md`](docs/protocol_design.md) — 承重设计决策
- [`docs/audits/`](docs/audits/) — 归档审计报告

## 发布

```bash
bash scripts/make-release.sh 3.6.0
```

一条命令完成：同步 6 处版本号、提交、打 tag、推送。GitHub Actions 随后自动执行完整测试门、构建 Windows 安装包、生成 changelog、发布 GitHub Release 并上传产物。

本地预览 changelog：

```bash
bash scripts/changelog.sh v3.5.0   # 查看 v3.5.0 以来的变更
```

## 路线图

**近期已发布**

- 地形剖面面板，净空可视化
- 飞行中航点跳转（MISSION_SET_CURRENT）
- WebSerial 航线上传/下载/清除 + 围栏上传
- WebSerial 日志列表 + 二进制下载
- WebSerial 全部 5 种校准类型（罗盘、加速度计、陀螺仪、水平、气压计）
- 3D 地图航点编辑、围栏绘制、距离/面积测量
- NTRIP RTK 客户端（HTTP/1.0 + ICY-200，RTCM 流式注入）
- 罗盘/加速度计/陀螺仪校准，二进制进度上报
- 多语言 UI（10 种语言 + RTL）
- Tauri v2 桌面打包
- 双传输互斥锁（WS 后端 / WebSerial）
- 云台俯仰/偏航控制
- Tag 触发的发布流程，自动生成 changelog

**进行中 / 部分完成**

- WebSerial 固件上传（APJ 解析 + Bootloader 协议）
- PX4 端到端接入（后端已读取 `HEARTBEAT.autopilot`；前端适配器存在但尚未引入）

**未来计划**

- WebRTC 视频流（替代 RTSP 代理）
- MQTT 云端中继，用于编队管理
- MAVLink FTP，用于固件上传和 Lua 脚本管理
- MSP 协议支持（BetaFlight / iNav）

## 贡献

欢迎提 Issue 和 PR。提交 PR 前请确保：

1. 本地测试通过：`npx vitest run && python -m pytest tests/test_unit_*.py tests/test_contract_*.py`
2. 类型检查清洁：`npx svelte-check`（0 错误，0 警告）
3. Python 代码检查清洁：`ruff check backend/ scripts/ tests/`
4. 提交规范：`<type>: <祈使句描述>`（type：`feat`、`fix`、`refactor`、`test`、`docs`、`ci`、`chore`）
5. 飞控耦合代码（MAVLink 命令、ACK 处理、校准握手）须在注释中引用上游 ArduPilot/PX4 源码 `file:line` —— 详见 `CLAUDE.md ## Protocol Code Discipline`

## 致谢

Argus 建立在以下项目之上：

- [ArduPilot](https://ardupilot.org/) — 定义了本 GCS 所对接协议语义的飞控固件
- [pymavlink](https://github.com/ArduPilot/pymavlink) — 用于验证我们纯 TS 实现的参考 MAVLink 编解码器
- [MAVLink](https://mavlink.io/) — 通信协议本身
- [Svelte](https://svelte.dev/)、[FastAPI](https://fastapi.tiangolo.com/)、[Leaflet](https://leafletjs.com/)、[MapLibre GL](https://maplibre.org/)、[Tauri](https://tauri.app/) — 应用技术栈
- QGroundControl、Mission Planner、MAVProxy — 前辈 GCS，展示了可能性

## 许可

MIT — 见 [LICENSE](LICENSE)。
