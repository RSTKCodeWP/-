# Argus GCS v3.4 — 功能清单与验证状态

> **本文档记录 v3.4 功能验证状态快照。** 499 项功能的逐条维护成本已超过参考价值，自 2026-05-24 起冻结逐行更新。后续功能变更在 git commit message 和 CHANGELOG 中追踪，不再同步到本文件的每一行。已知问题和 SITL 验证结果仍在底部更新。  
> 快照日期: 2026-05-24（冻结）  
> 飞控: ArduPilot V4.6.3, 固定翼  
> 测试方式: USB 串口 (/dev/ttyACM0) + Playwright 浏览器自动化 + pytest/vitest  
> 相关文档：`docs/protocol_design.md`（don't-refactor 设计理由）/ `docs/audits/`（历史 audit 报告归档）/ `CLAUDE.md`（协议代码纪律）

## 状态标记说明

| 标记 | 含义 |
|------|------|
| ✅ | 已通过真机/浏览器验证 |
| ✅ᵗ | 已通过自动化测试 (pytest/vitest) 验证 |
| ⚠️ | 部分验证（命令已发送，但无法确认执行结果） |
| 🔒 | 无法通过 USB 验证（需解锁/飞行/额外硬件） |
| ❌ | 未实现或有已知问题 |

---

## 一、连接与通信

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 1 | NTRIP 客户端 (rtk corrections) | ✅ᵗ | backend/commands/_ntrip.py: HTTP/1.0 GET + Basic auth, 解析 ICY 200 OK 或 HTTP 200, 流式 RTCM → GPS_RTCM_DATA(233)。单元测试覆盖 validation + lifecycle |
| 2 | WebSerial 未真机验证 | ⚠️ | 需 Chrome/Edge + USB 直连浏览器, Linux 环境未测试 |
| 3 | UDP 连接 | ✅ᵗ | 模拟器 udp:14550 验证 |
| 4 | MAVLink v2 标准协议 | ✅ | 真机 auto 检测为 standard |
| 5 | PL-Link 加密协议 | ✅ᵗ | 模拟器 sim_pllink.py 验证 |
| 6 | 协议自动检测 (auto) | ✅ | 真机 auto → standard 正确检测 |
| 7 | 波特率支持 (9600~921600) | ✅ | 真机 115200 验证, 前端提供全部 8 种 |
| 8 | 断线自动重连 | ✅ᵗ | 单元测试验证 reconnect 逻辑 |
| 9 | 重连时协议重置 | ✅ᵗ | 代码修复 + 测试验证 |
| 10 | WebSerial 浏览器直连 | ⚠️ | 需 Chrome/Edge + USB, 代码存在但未真机验证 |
| 11 | 多客户端支持 | ✅ᵗ | WS 推送测试验证多客户端接收 |
| 12 | WS 自动重连 | ✅ᵗ | ws.ts 指数退避 1.5s→30s 上限 (1000×1.5^n, 首次1500ms) |
| 13 | WS 连接保活检测 | ✅ᵗ | 15 秒无消息判定 stale, 主动重连 |
| 14 | WebSerial MAVLink编解码 | ✅ᵗ | transport.ts: MAVLink v2帧编码/解码/CRC, 自动SysID/CompID检测, 帧序号管理 |
| 15 | WebSerial 指令支持 | ✅ᵗ | arm/disarm/mode/RTL/param_set/param_request_all + **mission_upload / mission_download / mission_clear / fence_upload** (统一 MISSION_REQUEST_LIST→COUNT→REQUEST_INT→ITEM→ACK 协议, mission_type 参数化 0=任务/1=围栏; items→Waypoint 反向映射镜像 backend handle_mission_item_int) + **log_list / log_download** (LOG_REQUEST_LIST→ENTRY 列表, LOG_REQUEST_DATA→DATA 流式下载, LOG_REQUEST_END 取消) + **5 种校准**: cal_compass/compass_accept/cancel/gyro/level/baro (MAG_CAL_PROGRESS/REPORT 二进制进度桥接到 CalibrationPanel 事件流) + **accel/accel_next** (AP_AccelCal ACK 重解释 cmd=0/result=TEMPORARILY_REJECTED, 引 AP_AccelCal.cpp:367-393, 见 protocol_design.md #1) 全部通过USB直连, 绕过Python后端 |
| 16 | WebSerial 心跳+数据流 | ✅ᵗ | 1Hz GCS心跳发送, MAVLink数据流请求(REQUEST_DATA_STREAM), 缓冲区累积+帧拆分 |
| 17 | WebSerial USB设备过滤 | ✅ᵗ | serial.ts: STM32 Bootloader/STMicro/Pixhawk(3DR)/Holybro/CubePilot/Arduino vendor过滤, 5种波特率 |
| 18 | 连接超时 (8秒) | ✅ᵗ | 客户端8秒超时计时器, 超时后自动断开+错误提示 |
| 19 | SITL 快速连接按钮 | ✅ᵗ | 一键预设 udp:14550 + standard协议, 跳过手动输入 |
| 20 | 内置连接预设 | ✅ᵗ | 3种预设: tcp:localhost:5770, udp:14550, udp:14551, 下拉选择 |
| 21 | 最近连接持久化 | ✅ᵗ | argus_last_port + argus_last_baud, 重新打开时自动填充上次连接参数 |
| 22 | MAVLink v2 签名解析 | ✅ᵗ | codec.ts: incompat_flags & 0x01时帧长+13字节签名, 正确计算总帧长 |
| 23 | CRC_EXTRA 校验 | ✅ᵗ | 每消息ID对应CRC extra字节, CRC不匹配→跳过帧+0xFD重同步 |
| 24 | 流式帧解析器 | ✅ᵗ | parseFrames()跨chunk部分帧缓冲, 返回未消费remainder供下次调用 |
| 25 | WSS/WS 协议自动选择 | ✅ᵗ | HTTPS时自动用wss://, HTTP时用ws://, Tauri时用ws://127.0.0.1:8100 |
| 26 | 数据流请求配置 | ✅ᵗ | 9种消息: 姿态/位置/GPS@250ms, 系统/任务/振动/VFR_HUD@1s, 舵机/RC@500ms, SET_MESSAGE_INTERVAL请求msg148(AUTOPILOT_VERSION) |

---

## 二、遥测数据

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 27 | 姿态 (roll/pitch/yaw) | ✅ | 真机 3.1°/-1.4°/115.7° |
| 28 | GPS 位置 (lat/lon) | ✅ | 真机读取到坐标 |
| 29 | 高度 (MSL/相对) | ✅ | 真机 alt_rel=2.8m |
| 30 | 航向 (hdg) | ✅ | 真机 116° |
| 31 | 地速 (gs) | ✅ | 真机读取 |
| 32 | 电池 (电压/电流/百分比) | ✅ | 真机 voltage=1.49V |
| 33 | 电芯电压 (最多10芯) | ✅ | 真机 BATTERY_STATUS 处理 |
| 34 | GPS 状态 (fix/卫星数) | ✅ | 真机 GPS_RAW_INT 处理 |
| 35 | RC 通道 (16路) | ✅ | 真机 RC_CHANNELS 处理 |
| 36 | 舵机输出 (16路) | ✅ | 真机 SERVO_OUTPUT_RAW 处理 |
| 37 | 振动 (X/Y/Z + clip) | ✅ | 真机 VIBRATION 处理 |
| 38 | EKF 状态 (方差+标志) | ✅ᵗ | 已修复: handle_ekf_status 注册在 msg ID 335(EKF_STATUS_REPORT), 单元测试验证 |
| 39 | 地形高度 | ✅ | 真机 TERRAIN_REPORT 处理 |
| 40 | 风速/风向 | ✅ᵗ | handler 已实现, 真机无风传感器 |
| 41 | RSSI 信号强度 | ✅ | 真机 RC_CHANNELS 中的 rssi 字段 |
| 42 | ADSB 空中交通 | ✅ᵗ | handler 已实现, 需 ADS-B 接收器 |
| 43 | 飞行摘要 (时长/最大高度/距离) | ✅ᵗ | 代码逻辑验证, 解锁后自动统计 |
| 44 | 飞行模式显示 | ✅ | 真机显示"手动" |
| 45 | 解锁状态 | ✅ | 真机显示 armed=False |
| 46 | 机型识别 | ✅ | 真机 vtype_raw=1 (固定翼) |
| 47 | 固件版本 | ✅ | 真机 AUTOPILOT_VERSION 处理 |
| 48 | 状态文本过滤 (PreArm/Arm) | ✅ᵗ | statustext_filter 单元测试 |
| 49 | 垂直速度 (vz) | ✅ | 真机 GLOBAL_POSITION_INT vz字段, 用于HUD垂直速度标尺 |
| 50 | 当前航点序号 (wp_seq) | ✅ | 真机 MISSION_CURRENT msg42, 任务进度条显示当前航点 |
| 51 | MAVLink 解析错误计数 | ✅ᵗ | parse_errors累计统计, 链路质量诊断 |
| 52 | CSV日志活跃指示 | ✅ᵗ | log_active状态字段, 飞行中CSV日志记录状态 |
| 53 | 云台角度回传 | ✅ᵗ | 已修复: handle_mount_status(msg 158)解析pitch/yaw centideg, 推送gimbal_pitch/gimbal_yaw |
| 54 | 固件Git哈希+板卡ID | ✅ | 真机 AUTOPILOT_VERSION: fw_git(8字符哈希) + board_id(硬件ID) |
| 55 | 空速 (airspeed) | ✅ᵗ | 已修复: handle_vfr_hud(msg 74)解码airspeed, 后端state+WS推送 |
| 56 | 油门百分比 (throttle) | ✅ᵗ | 已修复: handle_vfr_hud(msg 74)解码throttle 0-100%, 后端state+WS推送 |
| 57 | 爬升率 (climb) | ✅ᵗ | 已修复: handle_vfr_hud(msg 74)解码climb m/s, 后端state+WS推送 |
| 58 | RC通道18路 | ✅ᵗ | WebSerial解码18路(非16路), 修正#20 |

---

## 三、状态推送与WS协议

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 59 | 增量推送 (delta push) | ✅ | 真机验证只推送变化字段 |
| 60 | 全量同步 (每10次) | ✅ | 真机验证第1/11/21次为全量 |
| 61 | 推送频率 200ms (连接) | ✅ | 真机 ~5次/秒 |
| 62 | 推送频率 1000ms (空闲) | ✅ᵗ | 配置验证 |
| 63 | 参数批量聚合 | ✅ᵗ | param_value消息聚合为单条param_batch WS帧, 减少WebSocket帧数 |
| 64 | Inspector数据推送 | ✅ᵗ | inspector_enabled时每推送周期发送type='inspector'+消息率/字段数据 |
| 65 | 控制台输出推送 | ✅ᵗ | serial_control响应文本缓冲(_console_buf), 批量推送type='console_output' |

---

## 四、飞行状态计算

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 66 | 电池剩余时间估算 | ✅ | 真机: 2分钟滑动窗口(_bat_history), ≥10秒+消耗>0后线性外推, bat_time_remaining秒 |
| 67 | Home位置自动设置 | ✅ | 真机: 首次|lat|>0.001自动设Home, HOME_POSITION(msg 242)覆盖, 事件通知 |
| 68 | Home距离实时计算 | ✅ | 真机: 经纬度→米距离公式, cos纬度修正, dist_home实时更新 |
| 69 | 飞行统计实时跟踪 | ✅ᵗ | 解锁后持续更新max_alt/max_speed/total_dist, 上锁时生成flight_summary字典 |
| 70 | 清除飞行摘要 (clear_summary) | ✅ᵗ | 用户确认摘要弹窗后WS发送clear_summary命令, 重置flight_summary=None |

---

## 五、参数管理

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 71 | 参数批量读取 | ✅ | 真机 1318 参数, 6 秒 |
| 72 | 参数进度条 | ✅ | Playwright 验证 23%→99%→完成 |
| 73 | 参数分类筛选 (9类) | ✅ | Playwright 验证按钮存在+点击 |
| 74 | 参数搜索 | ✅ᵗ | 前端组件逻辑验证 |
| 75 | 参数修改 (param_set) | ✅ | 真机 WS 命令发送验证 |
| 76 | 参数保存到文件 (param_save) | ✅ | 真机返回 JSON 文件路径 |
| 77 | 参数从文件加载 (param_load) | ✅ᵗ | 代码逻辑 + param_manager 测试 |
| 78 | 参数导出 (.param) | ✅ᵗ | 前端逻辑验证 (生成 Blob 下载) |
| 79 | 参数导入 (.param) | ✅ᵗ | 前端解析逻辑验证 |
| 80 | 参数差异导出 (Diff) | ✅ᵗ | 前端逻辑验证 |
| 81 | 参数元数据加载 | ✅ | 真机 /api/param_meta 1.5MB 加载 |
| 82 | 参数默认值对比 | ✅ᵗ | hasDefaultDiff 逻辑验证 |
| 83 | 位掩码参数编辑 | ✅ᵗ | 前端 toggleBitmaskBit 逻辑验证 |
| 84 | 参数获取超时 (60s) | ✅ᵗ | param_manager.check_timeout 测试 |
| 85 | 参数面板树形视图 | ✅ᵗ | 前端 treeGroups 逻辑验证 |
| 86 | 参数对比面板 (ParamDiff) | ✅ᵗ | 前端面板注册存在 |
| 87 | 参数存储优化 | ✅ᵗ | paramStore: name→index O(1) upsert, 完成后alphabetical排序重建索引 |
| 88 | 参数加载限.json | ✅ᵗ | param_load路径后缀验证, 仅接受.json文件 |

---

## 六、任务与航点

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 89 | 任务上传 (mission_upload) | ✅ | 真机 3 航点上传 |
| 90 | 任务下载 (mission_download) | ✅ | 真机返回"任务下载完成: 3 航点" |
| 91 | 任务清除 (mission_clear) | ✅ | 真机验证 |
| 92 | 围栏上传 (fence_upload) | ✅ | 真机 4 顶点上传, ACK 成功 |
| 93 | 集结点上传 (rally_upload) | ✅ᵗ | 2026-05 修复 + SITL 验证: 改用标准 MISSION 握手, 2 点上传 ACK 验证通过 |
| 94 | 任务下载超时 (30s) | ✅ᵗ | check_mission_dl_timeout 测试 |
| 95 | 坐标验证 (float 转换) | ✅ᵗ | 单元测试 string/None 输入 |
| 96 | 航点数量限制 (500) | ✅ᵗ | _mission.py 验证逻辑 |
| 97 | 航线撤销 | ✅ᵗ | pushUndo/undo 逻辑验证 (仅撤销, 无重做功能) |
| 98 | 航线圆形生成 | ✅ᵗ | generateCircle 逻辑验证 |
| 99 | QGC 航点导入 (.waypoints) | ✅ᵗ | parseQgcWaypoints 测试 |
| 100 | QGC Plan 导入 (.plan) | ✅ᵗ | parseQgcPlan 测试 |
| 101 | KML 导入/导出 | ✅ᵗ | parseKmlCoords/exportKml 测试 |
| 102 | 航线距离计算 | ✅ᵗ | totalDist/segDist 测试 |
| 103 | 围栏内判定 | ✅ᵗ | pointInPoly 测试 |
| 104 | 地形跟随 | ✅ᵗ | adjustWaypointsForTerrain 逻辑验证 |
| 105 | 航线 3D 显示 | ✅ᵗ | mission3d 面板注册存在 |
| 106 | 走廊规划 | ✅ᵗ | corridor 面板注册存在 |
| 107 | 测区重叠率计算 | ✅ᵗ | overlapCalc 面板注册存在 |
| 108 | 普通航点 (NAV_WAYPOINT) | ✅ | 真机任务上传验证 |
| 109 | 样条航点 (SPLINE_WAYPOINT) | ✅ᵗ | missionIO.ts MAV_CMD 82 解析 |
| 110 | 盘旋定时 (loiter_time) | ✅ᵗ | 航点类型+loiter_param 支持 |
| 111 | 盘旋定圈 (loiter_turns) | ✅ᵗ | 航点类型+loiter_param 支持 |
| 112 | 延时航点 (delay) | ✅ᵗ | AdvCmdPanel delay 秒数设置 |
| 113 | 舵机动作 (servo) | ✅ᵗ | 已修复: _upload_mission()处理cmd_servo→MAV_CMD 183(DO_SET_SERVO), 单元测试验证 |
| 114 | 相机触发 (cam_trigger) | ✅ᵗ | 已修复: _upload_mission()处理cmd_cam_trig→MAV_CMD 206(DO_SET_CAM_TRIGG_DIST) |
| 115 | 偏航朝向 (yaw) | ✅ᵗ | 已修复: _upload_mission()处理cmd_yaw→MAV_CMD 115(CONDITION_YAW), p3=direction |
| 116 | VTOL 过渡 (vtol_transition) | ✅ᵗ | 已修复: _upload_mission()处理cmd_vtol→MAV_CMD 3000(DO_VTOL_TRANSITION) |
| 117 | 投掷标记 (drop) | ✅ᵗ | 航点 drop 布尔标记 |
| 118 | 高级命令附加模式 | ✅ᵗ | 已修复: 6种MAV_CMD(183/201/206/112/115/3000)全部后端上传, pushUndo()支持 |

---

## 七、飞行控制

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 119 | 模式切换 (mode) | ✅ | 真机切换到 AUTO/手动 |
| 120 | 解锁 (arm) | ✅ᵗ | SITL Copter+Rover arm 验证通过 |
| 121 | 上锁 (disarm) | ✅ᵗ | SITL Copter+Rover disarm 验证通过 |
| 122 | 强制上锁 (force_disarm) | ✅ᵗ | SITL force_disarm magic=21196 验证通过 |
| 123 | 起飞 (takeoff) | ✅ᵗ | SITL Copter takeoff 25m, alt_rel=5.5m 达标 |
| 124 | 返航 (rtl) | ✅ᵗ | SITL RTL→auto landing→disarm 完整循环 |
| 125 | 任务开始 (mission_start) | ✅ᵗ | SITL mission_start→AUTO mode 切换验证 |
| 126 | 引导飞行 (guided_goto) | ✅ᵗ | SITL guided_goto lat/lon/alt 发送验证 |
| 127 | 投掷 (drop) | ✅ᵗ | SITL DO_SET_RELAY 命令 ACK 验证 |
| 128 | 停止投掷 (drop_stop) | ✅ᵗ | SITL DO_SET_RELAY 停止 ACK 验证 |
| 129 | ROI 设置 (do_set_roi) | ✅ᵗ | SITL DO_SET_ROI lat/lon/alt ACK 验证 |
| 130 | RC 覆盖 (rc_override) | ✅ᵗ | SITL RC_CHANNELS_OVERRIDE 8通道发送验证 |
| 131 | 飞行阶段状态机 | ✅ᵗ | 5阶段: disarmed→ground→flying→mission→returning, 各阶段显示不同按钮组合 |
| 132 | 悬停/暂停命令 | ✅ᵗ | Space键/按钮, 固定翼→QLOITER(19), 旋翼→LOITER(5), 紧急悬停 |
| 133 | 降落命令 | ✅ᵗ | 返航阶段显示, 固定翼→QLAND(20), 旋翼→LAND(9) |
| 134 | 取消返航 | ✅ᵗ | 返航阶段"取消RTL"按钮, 切换到悬停模式 |
| 135 | 飞行中高度调节 | ✅ᵗ | +5m/-5m按钮, 通过guided_goto发送当前位置+新高度 |
| 136 | Guided自动模式切换 | ✅ᵗ | guided_goto前自动set_mode(GUIDED: 旋翼4/固定翼15) |

---

## 八、校准

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 137 | 陀螺仪校准 (cal_gyro) | ✅ | 真机"开始陀螺仪校准 (请保持静止)..." |
| 138 | 罗盘校准 (cal_compass) | ✅ | 2026-05 真机端到端验证: 改用 MAV_CMD_DO_START_MAG_CAL(42424), 新增 MAG_CAL_PROGRESS/REPORT handler, 完成自动 accept(42425), 重启提示。commit e2efd90+9572d35+9b6276a |
| 139 | 加速度计校准 (cal_accel) | ✅ | 2026-05 真机端到端验证: 6 姿态依次推进 + Calibration successful。**核心发现**: AP_AccelCal::handle_command_ack 私有协议 — command 必须 ≤6 (非 MAV_CMD), result 必须 == MAV_RESULT_TEMPORARILY_REJECTED(1) (非 ACCEPTED)。commit 6a42c47 |
| 140 | 水平校准 (cal_level) | ✅ᵗ | SITL PREFLIGHT_CALIBRATION p5=4 ACK 验证 |
| 141 | 气压计校准 (cal_baro) | ✅ᵗ | SITL PREFLIGHT_CALIBRATION p3=1 ACK 验证 |
| 142 | 取消校准 (cal_cancel) | ✅ | 真机验证 |
| 143 | 加速度计6方向校准向导 | ✅ᵗ | 已修复: 正则重写为有序regex匹配(upside>back>nose_down>nose_up>left>right>level), 大小写不敏感, 校准中禁止切换标签。待真机验证 |
| 144 | 罗盘校准SVG进度 | ✅ | 2026-05 修复: 新增 handle_mag_cal_progress(msg191) + handle_mag_cal_report(msg192), CRC_EXTRA 表补 191:92/192:36。前端进度从假估算改为读真实 completion_pct。真机 0%→96% 平滑推进。commit 2f93a6d |
| 145 | 校准事件关键词过滤 | ✅ᵗ | 已修复: 全部改为case-insensitive regex匹配, 20+关键词, 最近20条滚动 |

---

## 九、设置与配置面板

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 146 | MotorTestPanel (电机测试面板) | ✅ᵗ | 8电机视觉网格, 油门(0-100%)/时长(0.5-5s)滑块, 倒计时动画, Quad X参考图, 安全警告 |
| 147 | RcCalibPanel (RC校准向导) | ✅ᵗ | 3步: ①居中记录trim+实时柱状图 ②全行程min/max(>300PWM) ③写入32参数(RC1-8 MIN/MAX/TRIM/REVERSED) |
| 148 | EscCalPanel (电调校准向导) | ✅ᵗ | 5步ESC校准: max油门PWM2000→min油门PWM1000→释放, rc_override 8通道, 安全警告 |
| 149 | FrameSelectPanel (机架选择面板) | ✅ᵗ | 8种机架类型(Quad/Hex/Octa/OctaQuad/TriY×2/Single/Plane), 子类型(+/X/V/H/Y6F), FRAME_CLASS/FRAME_TYPE参数 |
| 150 | FailsafeConfigPanel (失效保护配置) | ✅ᵗ | 4类: 电池(电压/mAh阈值)/RC丢失(PWM阈值)/GCS丢失/EKF(方差阈值), 动作(None/RTL/Land/SmartRTL/Continue/AltHold) |
| 151 | PowerCalPanel (电源校准面板) | ✅ᵗ | 电压倍率自动计算(实测/报告), 电流系数(BATT_AMP_PERVLT), 电芯数(1S-14S), 实时电压/电流/剩余显示 |
| 152 | PoiPanel (兴趣点面板) | ✅ᵗ | ROI坐标手动输入(lat/lon/alt), 从当前无人机位置预填, 设置/清除ROI, do_set_roi命令 |
| 153 | AnnotationPanel (地图标注面板) | ✅ᵗ | 命名地理标注(名称+备注+经纬度), 添加/删除/清空, localStorage argus_annotations |
| 154 | CustomDashboard (自定义仪表盘) | ✅ᵗ | 19种遥测小部件(高度/速度/电压/电池/GPS/EKF/风速/姿态等), 开关选择器, 颜色编码(绿/黄/红), localStorage |
| 155 | AiAnnotationPanel (AI巡检标注) | ✅ᵗ | 照片加载(JPG/PNG), Canvas矩形框标注, 缺陷类型(裂缝/腐蚀/损伤/其他), 严重等级(低/中/高), JSON导出, AI检测按钮(占位) |
| 156 | MultiVehiclePanel (多机显示面板) | ✅ᵗ | 所有MAVLink SysID列表, 各机遥测摘要(模式/解锁/高度/航向), "切换到"按钮 |
| 157 | RolePanel (角色选择面板) | ✅ᵗ | 飞手(全控制)/观察者(只读)/指挥官(全控制+管理), 权限说明, localStorage argus_role |
| 158 | 设置向导6步流程 | ✅ᵗ | 机架→RC校准→电机测试→传感器校准→失保配置→飞行模式, 步骤完成跟踪, 非线性导航 |
| 159 | PID响应曲线图 | ✅ᵗ | 实时actual-vs-target姿态Canvas, 200样本历史, roll/pitch/yaw切换 |
| 160 | PID实时调参 | ✅ᵗ | 滑块/输入变化即时param_set(live tuning), 独立"保存到Flash"按钮 |
| 161 | AutoTune轴选择 | ✅ᵗ | All/Roll/Pitch/Yaw选择→AUTOTUNE_AXES参数, AUTOTUNE_AGGR激进度显示 |
| 162 | 飞行模式6槽PWM映射 | ✅ᵗ | FLTMODE1-6对应6段PWM范围(1-1230/1231-1360/...), 下拉选择器, 活跃槽脉冲高亮 |
| 163 | 定位源置信度面板 | ✅ᵗ | GPS+EKF+罗盘+光流综合置信度(good/warn/bad), 光流从EKF标志推导(REL无ABS) |
| 164 | 默认航点速度设置 | ✅ᵗ | 1-30 m/s 步长0.5, 新航点默认速度, 持久化到argus_settings |
| 165 | 围栏半径设置 | ✅ᵗ | 0-10000m, 围栏圆形半径, 持久化到argus_settings |
| 166 | 构建日期显示 | ✅ᵗ | __BUILD_DATE__ 编译时间戳, 设置面板底部版本信息旁 |

---

## 十、日志与数据分析

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 167 | 日志列表 (log_list) | ✅ | 真机命令已发送 |
| 168 | 日志下载 (log_download) | ✅ᵗ | 代码逻辑验证, 分块传输 |
| 169 | 日志取消 (log_cancel) | ✅ᵗ | 代码逻辑验证 |
| 170 | 飞行日志 CSV 记录 | ✅ | 真机 logs/ 目录生成 CSV |
| 171 | 飞行日志 REST 下载 | ✅ᵗ | /api/log 端点测试 |
| 172 | 飞行记录数据库 | ✅ᵗ | flightDb localStorage 逻辑验证 |
| 173 | DataFlash .bin 解析 | ✅ᵗ | dflog.ts: ArduPilot二进制日志解析(0xA3/0x95头, FMT消息, 类型字段解包), 纯浏览器端ArrayBuffer处理 |
| 174 | 时序数据提取 | ✅ᵗ | getTimeSeries(): 按消息类型+字段名提取时间序列数据, 供LogViewerPanel和FFTPanel使用 |
| 175 | FFT频域计算 | ✅ᵗ | computeFFT(): 基2 FFT频域分析, 振动频谱诊断, 在dflog.ts中实现 |
| 176 | 飞行记录上限 | ✅ᵗ | flightDb: 200条上限, saveFlightRecord超出时自动裁剪最旧记录 |
| 177 | 检查器消息表 | ✅ᵗ | 5列(ID/名称/Hz/计数/大小), 展开行显示字段key:value, 按Hz降序, 自适应精度 |
| 178 | 检查器过滤/暂停 | ✅ᵗ | ID/名称搜索过滤, 暂停/恢复, 清除, 打开自动inspector_toggle/关闭自动禁用 |
| 179 | 控制台命令历史 | ✅ᵗ | 50条历史, ArrowUp/Down导航, 自动滚动到底部 |
| 180 | 日志下载进度条 | ✅ᵗ | 百分比进度条+速度指示器(KB/s或MB/s), logState.progress+downloadSpeed |

---

## 十一、硬件控制

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 181 | 电机测试 (motor_test) | ✅ | 真机"电机测试: #1 @ 5%" |
| 182 | 电机停止 (motor_test_stop) | ✅ᵗ | 代码逻辑验证 |
| 183 | 云台角度控制 (gimbal_angle) | ⚠️ | 命令可发送, 需云台硬件 |
| 184 | 云台速率/收回/中位 (gimbal_pitchyaw) | ⚠️ | 2026-05-23 重实现: 走 MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW(1000) via COMMAND_INT (msg 75), 字节级 pymavlink 契约测试覆盖三种模式 (角度/速率/flags-only) + instance + 越界。需云台硬件验证 set_rate_target / set_mode(RETRACT/NEUTRAL) 实际执行。AP 引用: libraries/AP_Mount/AP_Mount.cpp:363-417 |
| 185 | 相机快门 (camera_trigger) | ⚠️ | 命令可发送, 需相机 |
| 186 | 录像开始 (camera_video_start) | ⚠️ | 命令可发送 |
| 187 | 录像停止 (camera_video_stop) | ⚠️ | 命令可发送 |
| 188 | 相机变焦 (camera_zoom) | ⚠️ | 命令可发送 |
| 189 | 重启飞控 (reboot) | 🔒 | 会断开连接 |
| 190 | 重启到 Bootloader | 🔒 | 会断开连接 |
| 191 | 切换机型 (set_vtype) | ✅ᵗ | 代码逻辑验证 |
| 192 | 切换飞控 (switch_vehicle) | ✅ᵗ | 代码逻辑验证 |
| 193 | 串口控制台 (serial_control) | ✅ | 真机"ver"命令已发送 |
| 194 | RTCM 注入 (inject_rtcm) | ⚠️ | 代码存在, 需 RTK 基站 |
| 195 | RTCM分片注入 | ✅ᵗ | 110字节分片, first/last标志(0x04/0x08), GPS_RTCM_DATA msg233 |
| 196 | 云台归中按钮 | ✅ᵗ | pitch/yaw归零(0,0)并发送gimbal_angle, 一键复位 |

---

## 十二、REST API

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 197 | /health | ✅ | 真机 {"ok": true} |
| 198 | /api/version | ✅ | 真机 {"version": "3.4.0"} |
| 199 | /api/session | ✅ | 真机 connected/armed/sysid |
| 200 | /api/ports | ✅ᵗ | 端点测试 |
| 201 | /api/tile_sources | ✅ | 真机 8 种地图源 |
| 202 | /api/tile/{style}/{z}/{x}/{y} | ✅ᵗ | 路由测试 + 缓存逻辑 |
| 203 | /api/tile_cache | ✅ᵗ | 端点测试 |
| 204 | /api/tile_bulk_download | ✅ᵗ | 端点测试 |
| 205 | /api/tile_cache_clear | ✅ | REST 请求验证 |
| 206 | /api/terrain/elevation | ✅ | SRTM 海拔查询测试 |
| 207 | /api/param_meta | ✅ | 真机 5729 key 加载 |
| 208 | /api/firmware/upload | ✅ᵗ | 50MB 限制 + .apj 验证测试 |
| 209 | /api/firmware/list | ✅ᵗ | 端点测试 |
| 210 | /api/firmware/online | ✅ᵗ | 端点测试 |
| 211 | /api/firmware/download | ✅ᵗ | HTTPS 限制测试 |
| 212 | /api/mbtiles/list | ✅ᵗ | 端点测试 |
| 213 | /api/mbtiles/{name}/{z}/{x}/{y} | ✅ᵗ | 路径穿越防护测试 |
| 214 | /api/log | ✅ | CSV 下载端点 |
| 215 | /api/video?url= | ✅ᵗ | URL 验证 + SSRF 防护测试 |
| 216 | /api/video/stop | ✅ᵗ | 端点测试 |
| 217 | /api/video/capabilities | ✅ | ffmpeg 检测 |
| 218 | /api/auth/login | ✅ᵗ | token 验证测试 |
| 219 | /api/auth/status | ✅ᵗ | 端点测试 |
| 220 | /api/auth/generate | ✅ᵗ | token 生成测试 |
| 221 | 在线固件浏览 | ✅ᵗ | /api/firmware/online?board_id=X查询可用版本(版本列表, date/size字段为占位空值) |
| 222 | 在线固件下载 | ✅ᵗ | /api/firmware/download下载到服务器, HTTPS限制 |

---

## 十三、安全

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 223 | 视频 URL SSRF 防护 | ✅ᵗ | file:///etc/passwd + 内网 IP 拦截测试 |
| 224 | 固件上传大小限制 (50MB) | ✅ᵗ | 分块读取超限拒绝测试 |
| 225 | WS 端口验证 | ✅ᵗ | validate_port 纯函数测试 |
| 226 | WS 波特率验证 | ✅ᵗ | sanitize_baud 纯函数测试 |
| 227 | WS 协议验证 | ✅ᵗ | sanitize_protocol 纯函数测试 |
| 228 | WS 语言验证 | ✅ᵗ | VALID_LOCALES 验证 |
| 229 | 命令异常捕获 | ✅ᵗ | execute() try/except 测试 |
| 230 | Token 认证 | ✅ᵗ | auth.py SHA256 token 测试 |
| 231 | MBTiles 路径穿越防护 | ✅ᵗ | ../../../etc/passwd 拒绝测试 |
| 232 | CORS 跨域控制 | ✅ᵗ | ARGUS_CORS_ORIGINS 环境变量配置, 默认 localhost |
| 233 | X-Content-Type-Options: nosniff | ✅ᵗ | app.py 安全响应头中间件 |
| 234 | X-Frame-Options: DENY | ✅ᵗ | 防止 iframe 嵌入 |
| 235 | Referrer-Policy | ✅ᵗ | strict-origin-when-cross-origin |
| 236 | WebSocket Origin 校验 | ✅ᵗ | app.py websocket_endpoint 拒绝非白名单 origin |
| 237 | 环境变量配置覆盖 | ✅ᵗ | ARGUS_HOST/ARGUS_PORT/ARGUS_CORS_ORIGINS |
| 238 | 品牌CSS注入XSS防护 | ✅ᵗ | primaryColor: 长度<100, 正则拒绝expression/url()/javascript/;{} |
| 239 | 视频URL长度限制 | ✅ᵗ | VIDEO_URL_MAX_LEN: 2048字符, 超长URL拒绝 |

---

## 十四、前端面板总览

| # | 面板名称 | 状态 | 验证方式 |
|---|------|------|----------|
| 240 | MapView (地图) | ✅ | Playwright 页面加载可见 |
| 241 | StatusBar (状态栏) | ✅ | Playwright 状态信息可见 |
| 242 | ConnectionForm (连接) | ✅ | Playwright 连接/断开操作 |
| 243 | ControlPanel (控制面板) | ✅ | Playwright 模式按钮可见 |
| 244 | EventLog (事件日志) | ✅ | 真机事件推送验证 |
| 245 | TelemetryOverlay (遥测叠加) | ✅ | Playwright 数据显示 |
| 246 | RcPanel (RC面板) | ✅ᵗ | App.svelte 视图级懒加载 (非 panel registry) + 数据绑定验证 |
| 247 | ServoPanel (舵机面板) | ✅ᵗ | App.svelte 视图级懒加载 (非 panel registry) + 数据绑定验证 |
| 248 | VibrationPanel (振动面板) | ✅ᵗ | App.svelte 视图级懒加载 (非 panel registry) + Canvas 渲染 |
| 249 | EkfPanel (EKF面板) | ✅ᵗ | App.svelte 视图级懒加载 (非 panel registry) + 标志位解析 |
| 250 | MissionPanel (任务面板) | ✅ᵗ | 航点编辑 + 导入导出 |
| 251 | SurveyPanel (测区面板) | ✅ᵗ | App.svelte 视图级懒加载 (非 panel registry) |
| 252 | FencePanel (围栏面板) | ✅ | 真机围栏上传验证 |
| 253 | CalibrationPanel (校准) | ✅ | 真机陀螺仪校准 |
| 254 | FirmwarePanel (固件) | ✅ᵗ | 上传/列表端点测试 |
| 255 | NtripPanel (NTRIP) | ✅ᵗ | 前后端打通: backend/commands/_ntrip.py 实现 ntrip_start/stop, mocked socket 单元测试覆盖 ICY/HTTP/401/stop_event 路径 |
| 256 | PositionSourcePanel (定位源) | ✅ᵗ | 面板注册存在 |
| 257 | ParamPanel (参数面板) | ✅ | Playwright 1317 参数加载, 0 long task |
| 258 | PidPanel (PID调参) | ✅ᵗ | 面板注册存在 |
| 259 | FlightModePanel (飞行模式) | ✅ᵗ | ArduPilot/PX4 模式列表验证 |
| 260 | InspectorPanel (消息检查器) | ✅ | 真机 inspector_toggle 命令发送 |
| 261 | ConsolePanel (控制台) | ✅ | 真机"ver"命令发送 |
| 262 | LogPanel (日志面板) | ✅ | 真机 log_list 发送 |
| 263 | FlightReportPanel (飞行报告) | ✅ᵗ | flightDb 存储逻辑 |
| 264 | Map3DView (3D地图) | ✅ᵗ | App.svelte mapMode='3d' 按需加载 (mission3d PanelId 为独立的 Mission3DPanel), MapLibre GL 集成 |
| 265 | AirspacePanel (空域) | ✅ᵗ | 50 机场数据库验证 |
| 266 | OfflineMapPanel (离线地图) | ✅ᵗ | bulk_download 端点测试 |
| 267 | FleetDashboard (机群) | ✅ᵗ | 面板注册存在 |
| 268 | GimbalPanel (云台) | ✅ᵗ | 仅 gimbal_angle 命令 (前端未使用 gimbal_rate) |
| 269 | VideoOverlay (视频叠加) | ✅ᵗ | video 端点 + SSRF 防护测试 |
| 270 | AiPlannerPanel (AI规划) | ✅ᵗ | 面板注册存在 |
| 271 | SchedulerPanel (调度器) | ✅ᵗ | 面板注册存在 |
| 272 | CommandPalette (命令面板) | ✅ᵗ | Ctrl+K 快捷键验证 |
| 273 | ConfirmDialog (确认对话框) | ✅ᵗ | showConfirm 逻辑验证 |
| 274 | SettingsPanel (设置面板) | ✅ᵗ | 语言/主题 切换验证 (单位切换 UI 不在此面板) |
| 275 | DroneLayer (飞行器图层) | ✅ᵗ | 地图叠加层注册 |
| 276 | WaypointLayer (航点图层) | ✅ᵗ | 地图叠加层注册 |
| 277 | ParamDiffPanel (参数对比) | ✅ᵗ | 面板注册存在 |
| 278 | CorridorPanel (走廊规划) | ✅ᵗ | 代码逻辑验证 |
| 279 | OverlapCalcPanel (重叠计算) | ✅ᵗ | 面板注册存在 |
| 280 | AutoTunePanel (自动调参) | ✅ᵗ | 面板注册存在 |
| 281 | SetupWizard (设置向导) | ✅ᵗ | 面板注册存在 |
| 282 | 懒加载面板重试 | ✅ᵗ | 动态导入失败→内联红色错误卡片(非Toast)+最多3次重试, shortcuts面板排除渲染 |

---

## 十五、国际化与可访问性

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 283 | 中文 (zh) | ✅ | 真机 UI 显示 |
| 284 | 英文 (en) | ✅ᵗ | vitest i18n 完整性测试 |
| 285 | 日语 (ja) beta | ✅ᵗ | 912 key 翻译, vitest 验证 |
| 286 | 韩语 (ko) beta | ✅ᵗ | 912 key 翻译, vitest 验证 |
| 287 | 德语 (de) beta | ✅ᵗ | 912 key 翻译, vitest 验证 |
| 288 | 法语 (fr) beta | ✅ᵗ | 912 key 翻译, vitest 验证 |
| 289 | 西班牙语 (es) beta | ✅ᵗ | 912 key 翻译, vitest 验证 |
| 290 | 葡萄牙语 (pt) beta | ✅ᵗ | 912 key 翻译, vitest 验证 |
| 291 | 俄语 (ru) beta | ✅ᵗ | 912 key 翻译, vitest 验证 |
| 292 | 阿拉伯语 (ar) beta | ✅ᵗ | 912 key 翻译, vitest 验证 |
| 293 | 语言异步加载 | ✅ᵗ | _dictVersion 响应式更新验证 |
| 294 | Beta 标记显示 | ✅ᵗ | LOCALE_BETA Set 验证 |
| 295 | 阿拉伯语RTL布局 | ✅ᵗ | locale='ar' 时 document.dir='rtl' + document.lang='ar' 自动切换 |
| 296 | Skip-to-content链接 | ✅ᵗ | sr-only focus:not-sr-only 跳转到#main-content, 屏幕阅读器可见 |
| 297 | 安全操作确认 | ✅ᵗ | arm/RTL需showConfirm确认对话框, input/select元素跳过全局键盘事件处理 |

---

## 十六、PWA / Service Worker

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 298 | App Shell 缓存 | ✅ᵗ | sw.js 预缓存逻辑 |
| 299 | 地图瓦片缓存 (5000 LRU) | ✅ᵗ | handleTileRequest + eviction |
| 300 | 离线模式 | ✅ᵗ | staleWhileRevalidate 策略 |
| 301 | 推送通知 | ✅ᵗ | push + notificationclick handler |
| 302 | manifest.json | ✅ | REST /manifest.json 可访问 |
| 303 | 动态资源预缓存 | ✅ᵗ | PRECACHE_ASSETS消息: 应用可发送URL列表要求SW预缓存 |
| 304 | 缓存统计查询 | ✅ᵗ | GET_CACHE_STATS/CACHE_STATS消息: 返回app缓存条数+tile缓存条数+tile上限 |
| 305 | 旧缓存自动清理 | ✅ᵗ | activate事件: 删除非当前版本app缓存+非tile缓存, 保留tile数据 |
| 306 | SW自动更新激活 | ✅ᵗ | sw.js install事件内直接调用self.skipWaiting()自动激活 (main.ts的postMessage在activated后为no-op) |

---

## 十七、地图

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 307 | 高德卫星 (Amap) | ✅ᵗ | tile_sources 包含 |
| 308 | Google 卫星/混合 | ✅ᵗ | tile_sources 包含 |
| 309 | OpenStreetMap | ✅ᵗ | tile_sources 包含 |
| 310 | CartoDB 暗/亮 | ✅ᵗ | tile_sources 包含 |
| 311 | Esri 卫星+地形 | ✅ᵗ | tile_sources 包含 |
| 312 | 天地图 (Tianditu) | ✅ᵗ | tile_sources 包含 |
| 313 | MBTiles 离线地图 | ✅ᵗ | mbtiles 端点测试 |
| 314 | 3D 地图 (MapLibre GL) | ✅ᵗ | Map3DView 组件存在 |
| 315 | 中国/全球区域切换 | ✅ᵗ | mapRegion 设置 |
| 316 | SRTM 海拔查询 | ✅ | /api/terrain/elevation 测试 |
| 317 | 点击地图添加航点 | ✅ᵗ | MapView.svelte onMapClick, 点击坐标直接创建航点 |
| 318 | 距离/面积测量工具 | ✅ᵗ | MapView.svelte 测量模式切换, 多边形面积计算 |
| 319 | 航点拖拽移动 | ✅ᵗ | WaypointLayer.svelte L.marker draggable:true + dragend |
| 320 | GCJ02/WGS84 坐标偏移 | ✅ᵗ | gcj02.ts 中国地图坐标纠偏 (toGcj/toWgs) |
| 321 | 坐标复制到剪贴板 | ✅ᵗ | DroneLayer.svelte navigator.clipboard.writeText |
| 322 | KML叠加层显示 | ✅ᵗ | kmlOverlay状态: 导入KML/KMZ形状(类型+坐标+名称)在地图上叠加 |
| 323 | 集结点地图显示 | ✅ᵗ | rallyPoints + showRally 状态控制, 集结点标记在地图上显示 |
| 324 | 回放轨迹图层 (ReplayLayer) | ✅ᵗ | ReplayLayer.svelte: CSV日志回放时显示飞行轨迹+当前位置+航向标记 |
| 325 | 引导模式目标选择 | ✅ᵗ | guidedMode状态切换, 地图点击发送guided_goto, GuidedLayer显示目标+连线 |
| 326 | 右键引导飞行 | ✅ᵗ | MapView右键菜单→确认对话框→guided_goto(lat, lon, alt), 需连接+解锁 (不检查当前模式) |
| 327 | 罗盘玫瑰图 | ✅ᵗ | SVG罗盘+航向针旋转到当前heading, N/S/E/W标签, 地图右上角叠加 (top-12 right-3) |
| 328 | 定位Home按钮 | ✅ᵗ | 地图飞到home_lat/home_lon, 需Home已设置 |
| 329 | 深色模式瓦片滤镜 | ✅ᵗ | darkTheme时CSS filter: brightness(0.75) contrast(1.1) saturate(0.85) 应用到地图瓦片 |
| 330 | 飞行轨迹导出KML | ✅ᵗ | droneTrail坐标序列导出为KML LineString文件, Blob下载 |
| 331 | 电池航程圈 | ✅ᵗ | Home为圆心, 半径=剩余时间×速度×0.5-60s安全余量, 绿/黄/红颜色编码 |
| 332 | 速度矢量线 | ✅ᵗ | 航向方向绿色虚线, 长度按地速缩放(max 200m, 非像素), gs>0.5时显示 |
| 333 | Home返航连线 | ✅ᵗ | Home到无人机橙色虚线, dist_home>5m时显示 |
| 334 | 飞行轨迹缓冲 | ✅ᵗ | 2000点LRU轨迹, 超出时裁剪到1500点 |
| 335 | 航段距离标注 | ✅ᵗ | 连续航点间中段距离标签, m/km自动格式化 |
| 336 | 活跃航点高亮 | ✅ᵗ | 当前wp_seq航点橙色虚线环标记 |
| 337 | 航点类型视觉区分 | ✅ᵗ | loiter紫色虚线/drop橙色徽章/normal蓝色, loiter参数子标签(圈数/秒数) |
| 338 | 围栏半径圈 | ✅ᵗ | geoRadius以Home为圆心红色虚线圆, 区别于围栏多边形 |
| 339 | 无人机点击弹窗 | ✅ᵗ | 模式/解锁/坐标(可复制)/高度MSL+REL/速度/航向/Home距离 |
| 340 | 航点点击弹窗 | ✅ᵗ | WP号/坐标/高度/速度/延迟/航段距离 |
| 341 | 航点聚焦+航线适配 | ✅ᵗ | focusWp→map.setView+2s橙色临时环, fitRouteFlag→fitBounds自适应缩放 |
| 342 | ADSB交通标记渲染 | ✅ᵗ | 黄色箭头图标, 呼号/ICAO标签, tooltip(高度/速度), 过期自动清理 |
| 343 | 多机标记渲染 | ✅ᵗ | 各机SysID标签, 解锁=红/未解锁=灰, 航向旋转, DroneLayer渲染 |
| 344 | 3D任务视图交互 | ✅ᵗ | MapLibre GL 默认交互控制 + 点击空地添加航点 (guidedMode+armed 时改发 guided_goto, 右键带 confirm 对话框) + 可拖拽编号 marker (drag→保存新坐标) + marker 点击弹出气泡含删除按钮 + 围栏/测绘多边形渲染与点击绘制 + 测距/测面工具 + ESC 清当前 measure/guidedMode/绘制态 + 飞行日志回放层 (replayPos 驱动的橙色箭头+轨迹) + ADSB 流量层 (Map<icao, Marker>, 黄色三角+呼号标签); 与 2D WaypointLayer/FenceLayer/SurveyLayer/ReplayLayer/DroneLayer ADSB 行为完全一致, GCJ-02 反向变换避免坐标偏移 |

---

## 十八、任务规划与测区

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 345 | 测区多边形绘制 | ✅ᵗ | 地图点击画多边形, drawingPolygon 状态控制 |
| 346 | 测区面积计算 | ✅ᵗ | survey.ts polygonArea 经纬度面积算法 |
| 347 | 测区网格航线生成 | ✅ᵗ | generateSurveyGrid: 角度/间距/超越距/高度参数 |
| 348 | 航线预览计数 | ✅ᵗ | 生成前显示预计航点数量 |
| 349 | 围栏面积计算 | ✅ᵗ | 多边形面积m²/公顷格式化显示 |
| 350 | 围栏上传状态徽章 | ✅ᵗ | fenceUploaded=true→"已上传"绿色/false→"未上传"灰色 |
| 351 | 围栏JSON导入导出 | ✅ᵗ | JSON文件保存/加载围栏多边形顶点, FileReader+Blob |
| 352 | 4种本地NLP解析器 | ✅ᵗ | 圆形航线(半径/点数/高度)/测区网格(WxH/30m间距/蛇形)/航线反转/方向航点(N/S/E/W距离) |
| 353 | 上下文感知+双语 | ✅ᵗ | 使用当前无人机位置/Home/默认高度速度/机型, 中英文关键词, Chat风格UI+历史 |
| 354 | 离线地图自动框选 | ✅ᵗ | 连接时以无人机位置±0.05°自动填充边界框, 瓦片估算(≤5000), 3样式(卫星/矢量/OSM) |
| 355 | 调度器客户端限制 | ✅ᵗ | 纯前端调度无后端定时器, once/daily/weekly/custom(1-720h), autoArm, argus_mission_*来源 |
| 356 | 空域禁飞检测 | ✅ᵗ | 51中国机场Haversine排序, 3级半径(4.5/6/8.5km), 进入禁飞区红色警告, argus_airspace持久化 |
| 357 | 机群仪表盘颜色 | ✅ᵗ | 红(解锁)/灰(心跳>5s)/绿(已连接未解锁), 活跃机遥测卡片+其他机Switch按钮 |

---

## 十九、视频

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 358 | RTSP 流转 MJPEG | ✅ᵗ | video.py ffmpeg 调用逻辑 |
| 359 | RTMP 流支持 | ✅ᵗ | URL 校验允许 rtmp:// |
| 360 | HTTP/HTTPS 流 | ✅ᵗ | URL 校验允许 |
| 361 | 视频停止 | ✅ᵗ | /api/video/stop 端点 |
| 362 | ffmpeg 能力检测 | ✅ | /api/video/capabilities 测试 |
| 363 | 视频AR航点叠加 | ✅ᵗ | Canvas FOV投射航点/Home到视频画面, arEnabled切换, FOV 30-120°可调, 方位角/仰角计算 |
| 364 | 视频截图 | ✅ᵗ | 当前帧Canvas drawImage→PNG下载, 时间戳文件名 |
| 365 | 视频窗口拖拽+尺寸 | ✅ᵗ | 鼠标拖拽重定位, 3种尺寸预设(sm 320x240/md 480x360/lg 640x480) |

---

## 二十、HUD与飞行界面

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 366 | HUD 仪表盘 (HudOverlay) | ✅ᵗ | SVG 人工地平仪 + 罗盘 + 速度/高度标尺, 纯 SVG 渲染 (非 Canvas) |
| 367 | 任务进度条 (MissionProgress) | ✅ᵗ | 自动模式下显示当前航点/总航点/剩余距离/预计时间 |
| 368 | 地图浮动控制 (MapControls) | ✅ᵗ | 全屏地图时显示返航/悬停/强制上锁按钮+遥测摘要 |
| 369 | 引导目标标记 (GuidedLayer) | ✅ᵗ | GUIDED 模式目标点+连线+距离标签地图叠加 |
| 370 | 围栏编辑图层 (FenceLayer) | ✅ᵗ | 围栏多边形绘制/编辑地图叠加 (静态顶点标记, 无拖拽) |
| 371 | 测区编辑图层 (SurveyLayer) | ✅ᵗ | 测区多边形绘制/编辑地图叠加 |
| 372 | 飞行摘要弹窗 (FlightSummary) | ✅ᵗ | 降落后弹出时长/高度/速度/距离/电量统计 |
| 373 | 人工地平仪 | ✅ᵗ | 俯仰梯(±30°, 5°刻度, 虚线/实线), 天空/地面着色, 滚转旋转 |
| 374 | 滚转指示器 | ✅ᵗ | 0/10/20/30/45/60°固定刻度, 三角指针跟随当前roll |
| 375 | 速度/高度带 | ✅ᵗ | 左侧速度带+右侧高度带, 滚动刻度线, 当前值指针框 |
| 376 | Home方位箭头 | ✅ᵗ | 罗盘环上绿色箭头, bearing(当前→Home)计算, >5m时显示 |
| 377 | 风速风向指示 | ✅ᵗ | 右下角风向箭头(相对航向旋转)+风速数值, wind_speed>0.3时显示 |
| 378 | 遥测叠加趋势箭头 | ✅ᵗ | 8字段+高度/距离1.5s趋势(↑/↓), vz颜色(绿/红), 地形近地(红<10m/黄<30m/绿≥30m) |

---

## 二十一、音频与语音

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 379 | 音频提示音生成 | ✅ᵗ | audio.ts AudioContext 合成, 频率/时长/重复/间隔可配 |
| 380 | 语音播报 (TTS) | ✅ᵗ | SpeechSynthesis 解锁/上锁/返航/连接丢失/EKF 异常语音提示 |
| 381 | 连接状态音效 | ✅ᵗ | 连接/断开/重连 不同音调模式 |
| 382 | 电池低电量警报 | ✅ᵗ | 电池剩余百分比(remaining)低于阈值触发音频+语音 (非电压) |
| 383 | 高度语音播报 | ✅ᵗ | 下降9级(50/40/30/20/10/8/6/4/2m)+上升5级(10/20/30/50/100m), 0.2m滞后防抖 |
| 384 | 航点到达播报 | ✅ᵗ | wp_seq变化时语音"航点N到达", 中英文自动切换 |
| 385 | 3级电池警报 | ✅ᵗ | <30%(2响400Hz)/<20%(3响300Hz)/<10%(5响200Hz), 每级不同语音消息 |
| 386 | RTL模式警报 | ✅ᵗ | 10种RTL相关模式切换时440Hz 2响特殊警报 |
| 387 | 链路延迟警报 | ✅ᵗ | link_age>3时800ms 200Hz+语音"链路延迟高", 5秒去抖 |

---

## 二十二、UI/UX与导航

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 388 | 深色/浅色主题 | ✅ᵗ | darkTheme 切换 + localStorage |
| 389 | 键盘快捷键 (15+) | ✅ᵗ | App.svelte onkeydown 处理 |
| 390 | Toast 通知 (最多5条) | ✅ᵗ | addToast 逻辑验证 |
| 391 | 确认对话框 | ✅ᵗ | showConfirm 逻辑 |
| 392 | 滑动确认 (危险操作) | ✅ᵗ | showSlide/completeSlide 逻辑 |
| 393 | 语音播报 | ✅ᵗ | voiceEnabled + SpeechSynthesis |
| 394 | 音频警报 | ✅ᵗ | audioMuted 控制 |
| 395 | 公/英制切换 | ✅ᵗ | unitSystem 设置 |
| 396 | 面板懒加载 (42面板) | ✅ᵗ | LazyPanelHost 逻辑验证 |
| 397 | 视图懒加载 (4视图) | ✅ᵗ | App.svelte 动态导入 |
| 398 | Toast严重级分类 | ✅ᵗ | ws.ts: armed→warn/5s, disarmed→success, connect→success, disconnect→info, RTL→error/8s, cmd_fail→error/5s |
| 399 | 紧急事件检测 | ✅ᵗ | URGENT_TYPES: rtl/force_disarm/cmd_ack_fail/mission_ack_fail/fence_ack_fail/link_lost/connect_fail (7种) → 事件栏红色闪烁+脉冲徽章 |
| 400 | 命令ACK双语显示 | ✅ᵗ | 7种命令名(起飞/模式/继电器/校准/任务/解锁/引导) + 6种结果(成功/暂拒/拒绝/不支持/进行中/已取消) |
| 401 | PreArm消息收集 | ✅ᵗ | STATUSTEXT中"PreArm:"/"Arm:"前缀截取, ≤20条去重收集, 超出FIFO裁剪到10条 |
| 402 | 动态浏览器标题 | ✅ᵗ | 连接: "Argus — 模式 | 电压V | GPS", [!!]remaining<10或EKF异常, [!]remaining<20或link_age>3s |
| 403 | 4视图切换系统 | ✅ᵗ | Fly/Plan/Monitor/Params 选项卡, Ctrl+1~4快捷键, 各视图独立懒加载 |
| 404 | Monitor标签警告徽章 | ✅ᵗ | 振动>30 或 EKF flags & 0x480 或 EKF方差>0.8 时脉冲红点 |
| 405 | Plan标签航点计数 | ✅ᵗ | waypoints.length > 0 时显示计数徽章 |
| 406 | Params标签加载指示 | ✅ᵗ | param_fetching=true 时脉冲黄点 |
| 407 | 移动端底部导航 | ✅ᵗ | isMobile(window.innerWidth<768) 时固定底部标签栏, safe-area-bottom |
| 408 | 欢迎界面 | ✅ᵗ | 未连接时: 应用LOGO+名称+副标题+快捷键提示(Ctrl+K/?/Ctrl+S), 后端离线红色警告 |
| 409 | 快捷键面板 | ✅ᵗ | ?键打开, 15个快捷键列表(Space/R/A/D/1-9/Ctrl+1-4/M/G/F/L/Ctrl+Z/Ctrl+S/?/Ctrl+K/Esc), ESC关闭 |
| 410 | 链路质量趋势图 | ✅ᵗ | StatusBar: 20点SVG sparkline, linkHistory消息率历史, 120条滚动缓冲 |
| 411 | 消息率(Hz)显示 | ✅ᵗ | 2秒采样间隔, 帧数差值÷时间计算, 实时刷新 |
| 412 | EKF状态徽章 | ✅ᵗ | 绿/黄/红色点: vel/posH/posV/compass方差阈值+EKF_CONST_POS/UNINITIALIZED标志, tooltip详情 |
| 413 | 模式徽章颜色 | ✅ᵗ | 紧急模式(6/9/11/17/20/21)→destructive红, 手动模式→secondary灰, 其他→primary |
| 414 | 电池剩余时间显示 | ✅ᵗ | bat_time 字段格式化: ≥3600→~Xh Ym, <3600→~Xm, 不可用时隐藏 |
| 415 | 解析错误计数显示 | ✅ᵗ | parse_errors>0时StatusBar显示E:<count>红色标记 |
| 416 | 状态栏多机下拉 | ✅ᵗ | vehicles.length>0时+N徽章, 展开显示sysid/armed/alt列表 |
| 417 | 50+命令项8类 | ✅ᵗ | 导航/飞行/任务/参数/校准/工具/设置/连接, 模糊搜索过滤 |
| 418 | 动态模式+参数搜索 | ✅ᵗ | 连接时注入mode_btns飞行模式, 查询≥2字符搜索paramState.list(≤8结果+当前值) |
| 419 | 全屏切换 | ✅ᵗ | 快捷键 F, requestFullscreen API |

---

## 二十三、数据持久化与文件IO

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 420 | 连接配置文件 (profiles) | ✅ᵗ | argus_profiles: 保存/加载/删除连接预设 (端口+波特率+协议) |
| 421 | 端口历史 (port_history) | ✅ᵗ | argus_port_history: 最近 10 个端口 |
| 422 | 航线数据持久化 | ✅ᵗ | argus_waypoints: 航点列表本地保存 |
| 423 | 设置持久化 | ✅ᵗ | argus_settings: 高度/速度/围栏/主题/音频/区域/瓦片源 (语言→argus_locale, 单位→argus_units 独立存储) |
| 424 | 预检检查单自定义 | ✅ᵗ | argus_preflight_config: 自定义检查项 |
| 425 | 地图标注持久化 | ✅ᵗ | argus_annotations: 名称/备注/经纬度 |
| 426 | 手柄映射持久化 | ✅ᵗ | argus_gamepad_map: 通道映射+死区 |
| 427 | 调度任务持久化 | ✅ᵗ | argus_schedules: 定时任务列表 |
| 428 | localStorage品牌迁移 | ✅ᵗ | migrate.ts: 21静态key + 动态前缀key(ai_annotations_*/mission_*) pllink_*→argus_* 非破坏性迁移 |
| 429 | NTRIP 配置持久化 | ✅ᵗ | argus_ntrip: host/port/mountpoint/username, NtripPanel加载时自动恢复 |
| 430 | 飞手姓名持久化 | ✅ᵗ | argus_pilot_name: FlightReportPanel飞行报告飞手标识, 跨会话保持 |
| 431 | 视频URL持久化 | ✅ᵗ | argus_video_url: 上次视频流地址, VideoOverlay打开时自动填充 |
| 432 | 正射影像覆盖持久化 | ✅ᵗ | argus_ortho_overlays: 地理配准影像配置(NW/SE角坐标+透明度), 跨会话保持 |
| 433 | 任务导出 JSON | ✅ᵗ | MissionPanel Blob 下载 |
| 434 | 任务导入 JSON/.waypoints/.plan | ✅ᵗ | FileReader 解析 QGC/JSON 格式 |
| 435 | KML 导入/导出 | ✅ᵗ | parseKmlCoords + exportKml |
| 436 | 参数导出 .param | ✅ᵗ | ParamPanel TSV 格式导出 |
| 437 | 参数导入 .param | ✅ᵗ | FileReader 解析 + 逐项 param_set |
| 438 | 日志导出 CSV | ✅ᵗ | LogViewerPanel 多通道数据导出 |
| 439 | 正射影像上传覆盖 | ✅ᵗ | OrthoOverlayPanel 地理配准 (NW/SE 角坐标), 透明度控制 |

---

## 二十四、飞控适配

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 440 | ArduPilot 旋翼 (25模式) | ✅ᵗ | ardupilot.ts COPTER_MODES 25条目 (最高mode ID=27, 有空位) |
| 441 | ArduPilot 固定翼 (23模式) | ✅ | 真机 vtype=1, 模式切换验证 |
| 442 | PX4 (15+模式) | ✅ᵗ | px4.ts 模式表验证 |
| 443 | 机型自动识别 | ✅ | 真机 HEARTBEAT vtype_raw=1 |
| 444 | 机型手动强制 | ✅ᵗ | set_vtype 命令验证 |
| 445 | Rover 模式 (9种) | ✅ᵗ | Manual/Acro/Steering/Hold/Follow/Auto/RTL/SmartRTL/Guided (constants.py 中英双语, 无Loiter) |
| 446 | Sub 模式 (9种) | ✅ᵗ | Stabilize/Acro/DepthHold/Manual/Guided/Circle/PosHold/Auto/Surface (constants.py 中英双语) |
| 447 | VTOL/QuadPlane 模式 | ✅ᵗ | Q-Stabilize/Q-Hover/Q-Loiter/Q-Land/Q-RTL (constants.py Plane部分, 固定翼VTOL过渡) |
| 448 | GPS定位类型标签 | ✅ᵗ | No Fix/2D/3D/DGPS/RTK Float/RTK Fixed 中英双语 (constants.py FIX_NAMES/FIX_NAMES_EN) |
| 449 | 模式快捷按钮集 | ✅ᵗ | 每种机型预选模式子集: 前端旋翼8/固定翼8 (ardupilot.ts), 后端旋翼6/固定翼8 (constants.py), 键盘1-9快速切换 |
| 450 | ArduPilot固定翼23模式 | ✅ᵗ | 含Thermal(ID 24)+Loiter-to-QLand(ID 25), mode ID有空位故总数为23 |
| 451 | PX4精确着陆模式 | ✅ᵗ | PX4_AUTO_PRECLAND=9, 自动精确着陆 |
| 452 | PX4跟随模式 | ✅ᵗ | PX4_AUTO_FOLLOW=8, 跟随目标飞行 |
| 453 | 模式类别分类 | ✅ᵗ | manual/assisted/auto/emergency四类, 驱动StatusBar模式徽章颜色 |
| 454 | 模式快捷按钮8个 | ✅ᵗ | 前端 COPTER_BTNS=8/PLANE_BTNS=8 (ardupilot.ts), 后端 COPTER_BTNS_EN=6 (constants.py 不一致) |

---

## 二十五、多客户端与角色

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 455 | 观察者/飞手角色 | ✅ᵗ | set_role WS 消息处理 |
| 456 | 飞手控制权移交 | ✅ᵗ | request_handoff/accept WS 处理 |
| 457 | 多客户端状态同步 | ✅ᵗ | push_loop 发送到所有客户端 |

---

## 二十六、扩展系统与品牌

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 458 | 插件系统 (Plugin API v3.4.0) | ✅ᵗ | plugins.ts: getDroneState/sendCommand/subscribe/addPanel 生命周期 |
| 459 | 白标/品牌定制 (branding.ts) | ✅ᵗ | appName/logo/primaryColor/defaultPort, DOM #argus-branding 或 localStorage |
| 460 | 脚本面板 (ScriptPanel) | ✅ᵗ | 面板注册存在, 自动化脚本执行 |
| 461 | 高级命令面板 (AdvCmdPanel) | ✅ᵗ | 面板注册存在, 任意 MAVLink 命令发送 |
| 462 | 远程控制面板 (RemotePanel) | ✅ᵗ | 面板注册存在, SITL 远程连接 |
| 463 | Plugin getWaypoints() | ✅ᵗ | 返回当前航点列表深拷贝, 供插件读取航线数据 |
| 464 | Plugin emit(event, data) | ✅ᵗ | 自定义事件总线+window.dispatchEvent(CustomEvent('argus:<event>')) |
| 465 | Plugin showToast/removePanel | ✅ᵗ | 插件显示Toast通知(msg+level), 注销已添加面板元素 |
| 466 | Plugin生命周期 | ✅ᵗ | init→mount→destroy→unmount 4钩子, unloadPlugin(name)运行时卸载 |
| 467 | 脚本API (5函数) | ✅ᵗ | drone(只读快照)/waypoints(冻结)/send(cmd,data)/wait(ms,≤10s)/log(msg), AsyncFunction沙盒 |
| 468 | 脚本持久化 | ✅ᵗ | argus_scripts localStorage, 保存/加载/删除命名脚本, 侧边栏库列表 |
| 469 | 脚本输出控制台 | ✅ᵗ | 颜色编码: [ERROR]红/[CMD]黄/[OK]绿/普通灰 |
| 470 | 品牌hideArduPilot选项 | ✅ᵗ | 白标时隐藏ArduPilot特定UI元素 |
| 471 | 品牌subtitle+defaultProtocol | ✅ᵗ | 自定义副标题文本+默认连接协议覆盖 |

---

## 二十七、桌面应用与部署

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 472 | Tauri 桌面打包 (Windows MSI/NSIS) | ✅ᵗ | src-tauri/tauri.conf.json 配置验证 |
| 473 | 启动器 run.py (--sim/--host/--port) | ✅ | 真机 python run.py 启动验证 |
| 474 | Windows 打包脚本 | ✅ᵗ | scripts/build_package.py 存在 |
| 475 | 模拟器 (sim_pllink.py) | ✅ | --sim 模式验证, 41 参数模拟 (真机1317为FC参数总数) |
| 476 | 链路丢失超时 (5s) | ✅ᵗ | LINK_LOST_TIMEOUT: 5秒无心跳判定链路丢失, 触发事件+语音 |
| 477 | 参数元数据缓存TTL | ✅ᵗ | PARAM_CACHE_TTL: 7天本地JSON缓存, 无网络时graceful fallback |
| 478 | SRTM 高程缓存 | ✅ᵗ | SRTM_CACHE_MAX: 500条内存缓存, ~11m分辨率 |
| 479 | 自动打开浏览器 | ✅ | server.py: /health轮询(≤30次,0.3s间隔)后webbrowser.open; run.py直接调用webbrowser.open |
| 480 | ARGUS_NO_BROWSER 环境变量 | ✅ᵗ | 设置后抑制自动打开浏览器, headless/服务器部署用 |
| 481 | Tauri运行时检测 | ✅ᵗ | __TAURI_INTERNALS__检测: Tauri时API→127.0.0.1:8100, 浏览器时API→相对路径 |

---

## 二十八、手柄 / 回放 / 预检

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 482 | 手柄/摇杆控制 (Gamepad API) | ✅ᵗ | gamepad.svelte.ts: rAF轮询(~60Hz)+50ms发送节流, 4通道主动映射(roll/pitch/throttle/yaw)+4零值, 死区校准, rc_override |
| 483 | 手柄映射持久化 | ✅ᵗ | localStorage argus_gamepad_map |
| 484 | 日志回放 (ReplayPanel) | ✅ᵗ | CSV 日志播放, 播放/暂停/进度条/倍速, ReplayLayer 地图轨迹 |
| 485 | 起飞前检查单 (PreflightPanel) | ✅ᵗ | 连接且未解锁时自动弹出, 自定义检查项 localStorage |
| 486 | 飞行摘要弹窗 | ✅ᵗ | 降落后自动弹出时长/高度/速度/距离/电量统计 |
| 487 | 多格式日志支持 | ✅ᵗ | .csv(20+列) + .bin/.log(DataFlash二进制, ATT/GPS/BAT合并时间序列) |
| 488 | 5级回放速度 | ✅ᵗ | 0.5x/1x/2x/4x/8x, ±10帧跳转, 进度条拖动, 时间显示 |
| 489 | 回放遥测显示 | ✅ᵗ | 播放时显示alt/speed/voltage/distance/roll/pitch/yaw, onposition回调驱动地图标记 |
| 490 | 15项预检检查 | ✅ᵗ | GPS/卫星≥10/电压>22V/电量>30%/Home/链路<2s/EKF/振动<30/罗盘<0.8/气压/AHRS/RC RSSI/任务/机型/未解锁 |
| 491 | 检查项自定义+PreArm | ✅ᵗ | 每项启用/禁用+critical标志, argus_preflight_config持久化, FC PreArm消息独立显示区 |
| 492 | 手柄轴反转 | ✅ᵗ | 每轴独立反转开关(invertRoll/Pitch/Throttle/Yaw) |
| 493 | 手柄解锁保护 | ✅ᵗ | 仅connected+armed时发送rc_override, rAF+50ms节流(非固定20Hz) |

---

## 二十九、图表与可视化

| # | 功能 | 状态 | 验证方式 |
|---|------|------|----------|
| 494 | 遥测时序图表 (ChartPanel) | ✅ᵗ | 高度/速度/垂直速度/电池/电流/振动 Canvas 渲染 |
| 495 | 航线高度剖面图 | ✅ᵗ | MissionPanel profileCanvas 地形+航线高度可视化 |
| 496 | 链路质量历史图 | ✅ᵗ | StatusBar linkHistory SVG sparkline 仅绘制消息率(rate), 延迟(age)仅tooltip显示 |
| 497 | 日志数据图表查看器 | ✅ᵗ | LogViewerPanel 多通道图表+缩放+表格+统计+CSV 导出 |
| 498 | FFT 频谱分析 | ✅ᵗ | FFTPanel 振动/信号频域分析 |
| 499 | 3D 罗盘可视化 | ✅ᵗ | Compass3DPanel 磁力计样本 3D 显示, 2000 样本, 鼠标旋转 |

---

## 统计汇总

| 类别 | 总数 | ✅ 真机 | ✅ᵗ 测试 | ⚠️ 部分 | 🔒 不可测 | ❌ 缺失 |
|------|------|---------|----------|---------|----------|---------|
| 连接与通信 | 26 | 3 | 20 | 2 | 0 | 1 |
| 遥测数据 | 32 | 20 | 12 | 0 | 0 | 0 |
| 状态推送与WS协议 | 7 | 3 | 4 | 0 | 0 | 0 |
| 飞行状态计算 | 5 | 3 | 2 | 0 | 0 | 0 |
| 参数管理 | 18 | 6 | 12 | 0 | 0 | 0 |
| 任务与航点 | 30 | 5 | 25 | 0 | 0 | 0 |
| 飞行控制 | 18 | 1 | 17 | 0 | 0 | 0 |
| 校准 | 9 | 2 | 4 | 3 | 0 | 0 |
| 设置与配置面板 | 21 | 0 | 21 | 0 | 0 | 0 |
| 日志与数据分析 | 14 | 2 | 12 | 0 | 0 | 0 |
| 硬件控制 | 16 | 2 | 5 | 7 | 2 | 0 |
| REST API | 26 | 9 | 17 | 0 | 0 | 0 |
| 安全 | 17 | 0 | 17 | 0 | 0 | 0 |
| 前端面板总览 | 43 | 12 | 30 | 0 | 0 | 1 |
| 国际化与可访问性 | 15 | 1 | 14 | 0 | 0 | 0 |
| PWA / Service Worker | 9 | 1 | 8 | 0 | 0 | 0 |
| 地图 | 38 | 1 | 37 | 0 | 0 | 0 |
| 任务规划与测区 | 13 | 0 | 13 | 0 | 0 | 0 |
| 视频 | 8 | 1 | 7 | 0 | 0 | 0 |
| HUD与飞行界面 | 13 | 0 | 13 | 0 | 0 | 0 |
| 音频与语音 | 9 | 0 | 9 | 0 | 0 | 0 |
| UI/UX与导航 | 32 | 0 | 32 | 0 | 0 | 0 |
| 数据持久化与文件IO | 20 | 0 | 20 | 0 | 0 | 0 |
| 飞控适配 | 15 | 2 | 13 | 0 | 0 | 0 |
| 多客户端与角色 | 3 | 0 | 3 | 0 | 0 | 0 |
| 扩展系统与品牌 | 14 | 0 | 14 | 0 | 0 | 0 |
| 桌面应用与部署 | 10 | 3 | 7 | 0 | 0 | 0 |
| 手柄 / 回放 / 预检 | 12 | 0 | 12 | 0 | 0 | 0 |
| 图表与可视化 | 6 | 0 | 6 | 0 | 0 | 0 |
| **合计** | **499** | **77** | **406** | **6** | **8** | **2** |

---

## 已知问题

| # | 问题 | 状态 | 说明 |
|---|------|------|------|
| 1 | ~~NtripPanel 缺少后端 handler~~ | ✅ | 已实现 (#1 总表)。`KNOWN_FRONTEND_ORPHANS` 已清空 |
| 2 | WebSerial 未真机验证 | ⚠️ | 需 Chrome/Edge + USB 直连浏览器, Linux 环境未测试 |
| 3 | ~~EKF handler 注册错误消息 ID~~ | ✅ | 已修复: 注册到 msg 335, 新增 VFR_HUD handler (msg 74) |
| 4 | ~~VFR_HUD 数据后端不解析~~ | ✅ | 已修复: 新增 handle_vfr_hud, state 增加 airspeed/throttle/climb |
| 5 | ~~云台遥测无接收 handler~~ | ✅ | 已修复: 新增 handle_mount_status (msg 158) |
| 6 | ~~高级命令后端未实现上传~~ | ✅ | 已修复: _upload_mission() 处理 5 种 cmd_* 字段 |
| 7 | PX4 支持基本未实现 | ❌ | 前端 `src/lib/fc/` PX4 adapter scaffolded 但无 production import; 后端 Phase P commit 已读取 HEARTBEAT.autopilot byte 并推送 `drone.autopilot`，但无任何分支行为。详见 `CLAUDE.md ## PX4 Status` |
| 8 | ~~gimbal_rate 命令无法工作~~ | ✅ᵗ | 已修复 (#184): 新增 `cmd_gimbal_pitchyaw` 走 MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW(1000) via COMMAND_INT, 5 个 pymavlink 字节级契约测试通过; 前端 GimbalPanel 加 Rate 模式 + Retract/Neutral 按钮 |
| 9 | ~~tests/test_integration.py 32 个失败~~ | ✅ | 2026-05-24 全部修复: A=真 bug已修, B=sim协议bug已修, C=过期测试已修, D=xfail装饰器已移除; 新增 test_connect_with_pllink_protocol。53/53 通过。|
| 10 | ~~MAVLink 2 zero-trim 不容忍~~ | ✅ | 2026-05 修复: 所有 handler 新增 `_pad()` helper, 容忍 trailing-zero trimmed payload (FC 发的 trailing-zero 字段不再读到 0)。commit 102a05e |
| 11 | ~~observer 客户端可发危险指令~~ | ✅ | 2026-05 修复: ws_manager.command 分支检查 pilot 角色, 否则拒绝 |
| 12 | ~~firmware download 路径穿越 + SSRF~~ | ✅ | 2026-05 修复: Path.relative_to + DNS 解析后检查私有 IP |
| 13 | ~~mbtiles 路径校验 startswith 可绕过~~ | ✅ | 2026-05 修复: Path.relative_to + basename 检查 |
| 14 | ~~UDP _remote 可被劫持~~ | ✅ | 2026-05 修复: 只在原 peer 静默 >30s 后才接受新源 |
| 15 | ~~.gitignore 误把 src/components/params/ 排除~~ | ✅ | 2026-05 修复: 改为 `/params/` 锚定根目录; 4 个 Svelte 组件入库 |
| 16 | ~~ConnectionForm 串口/WS 双传输冲突~~ | ✅ᵗ | F-39 已修复: `AppState.activeTransport` 互斥锁。toggle()/toggleSerial() 按钮级拒绝另一 transport 已激活; updateState() 防御性丢弃 serial-mode 下的 WS state; 4 个 vitest 单元测试覆盖。disconnect/失败/串口丢失路径都会复位 `activeTransport='none'` |

---

## 2026-05-23 协议层 audit 圆满收尾

- 11 份 audit 报告归档在 `docs/audits/`，README 索引每个区域的 fix 状态
- `docs/protocol_design.md` 记录 10 条 "看起来错但其实对" 的 load-bearing 设计决策（防止未来误改）
- 新增 5 套契约测试 (`tests/test_contract_*.py`) 永久护栏:
  - 命令名 frontend↔backend 一致性
  - 状态字段 _build_state↔DroneState 一致性
  - handler ↔ CRC_EXTRA 一致性
  - byte-level vs pymavlink 真值表
  - locale key 完整性
- CLAUDE.md 新增 `## Protocol Code Discipline` 规则: FC 协议代码必须引上游源码 file:line

## 2026-05-24 audit_remaining 跟进修复

- 修复 L2: `scripts/build_package.py` PIP_DEPS 补 `python-multipart`
- 修复 L4: `run.py` `--host` 默认改为 `127.0.0.1`
- 修复 L5: `backend/app.py` 固件上传拒绝裸 `.apj` 点文件 + 新增测试
- 修复 M4: `scripts/build_desktop.sh` 替换19条 `--hidden-import` 为 `--collect-submodules`
- 修复 M7: `backend/app.py` tile_bulk_download 全异步 + 每块大小限制
- 修复 M8: `backend/app.py` mbtiles 穿越防护改用 `Path.relative_to`
- 修复 M9: `backend/app.py` 固件上传流式写入 + `.tmp` 原子重命名
- 修复 Gap A/B: `tests/test_unit_handlers.py` 补 count=0 和乱序块两个单元测试
- 修复 Gap C: `tests/test_integration.py` 补 `test_connect_with_pllink_protocol`
- 移除 xfail 装饰器 (`test_compass_calibration` 已稳定通过)
- 集成测试: 52/52 → 53/53 全部通过; 后端单元测试: 1043 条

## 2026-05-24 真 SITL 端到端验证

- `docs/audits/sitl_validation_2026-05-24.md` — 在真 ArduCopter SITL v4.6.3 上跑通 7 条关键路径:
  - 后端 TCP 基线遥测、Mission 上传/下载字节对齐、Arm/Mode/Takeoff/RTL 命令链、1398 参数读取+SET 回写、Fence mission_type=1 上传、Phase P WS autopilot 字段 1s 内到达前端、custom-identity FC (autopilot=1, type=0) 渲染
- 个别命令全部在真 AP 上 PASS — 之前只有 mock 测试做断言
- 仍 hardware-blocked: WebSerial 直连真飞控、5 种校准、firmware 上传 (VMware USB passthrough kernel-unstable)

## 2026-05-24 全面审计 (5-agent parallel)

5 维度并行审计 (后端安全/前端质量/测试覆盖/架构/协议正确性), 报告: `docs/audits/audit_full_2026-05-24.md`

已修复 (commit 712682b):
- H4: `App.svelte` 加 `<svelte:boundary>` 错误边界，防渲染崩溃白屏
- M7: `DroneLayer.svelte` ADSB callsign HTML 转义防 XSS
- M9: `sw.js` 缓存版本 v3.3 → v3.4
- T1: CI 加入 `test_contract_*.py` (之前被静默跳过)
- T2: `vite.config.ts` 移除 `onUnhandledErrors:'ignore'`
- M13: `crc.ts` 补 3 个缺失的 CRC_EXTRA (msg 158/191/192)
- M3: `auth.py` token 文件原子创建 (os.open O_CREAT 0o600)
- M4: `_ntrip.py` NTRIP host SSRF 防护 (DNS 解析+内网 IP 拒绝)
- H3: `app.py` `/api/auth/generate` 限制仅 localhost
- M6: `app.py` 固件下载流式写入 .tmp (不再 50MB 全量读入内存)

未修复 (documented): H1 WS token query string (浏览器限制), H2 auth status disclosure (前端需要), M1/M2/M5/M10-M14 见审计报告

## 2026-05-24 SITL 全载具验证 + 补充工作

- SITL 验证 v2: Copter 98/105 + Rover 28/29 = **126/134 PASS**, 0 功能 bug
- 飞行控制 #120-130: 🔒/⚠️ → ✅ᵗ (SITL arm/takeoff/RTL/guided/drop/ROI/RC 全验证)
- 校准 #140-141: ⚠️ → ✅ᵗ (SITL cal_level/cal_baro ACK 验证)
- 集结点 #93: SITL rally_upload 2 点验证通过
- app.py 拆分: 653→211 行 (tiles.py/terrain.py/firmware.py 独立 APIRouter)
- a11y: 24→16 抑制 (App/MapView/InspectorPanel 清零)
- E2E: 新增 connected-flow.spec.ts (12 测试)
- 报告: `docs/audits/sitl_full_verification_2026-05-24.md`

## 测试基础设施

| 测试类型 | 数量 | 工具 |
|----------|------|------|
| 后端单元 + 契约测试 | **1068** | pytest |
| 前端单元测试 | **487** | vitest |
| E2E 测试 | 20 specs | Playwright |
| SITL 端到端验证 | 126/134 项 (Copter+Rover) | Python websockets + httpx |
| 真机 WS 测试 | 25 项 | Python websockets |
| 真机浏览器测试 | 7 秒参数加载 | Playwright headless |
| 代码类型检查 | 4677 文件 0 错误 0 警告 | svelte-check |
| Python lint | 0 错误 | ruff |
