_LEAK_FILTERS = [
    ("ArduCopter", "FC"),
    ("ArduPlane", "FC"),
    ("ArduPilot", "FC"),
    ("APM", "FC"),
    ("EKF3", "NAV"),
    ("EKF2", "NAV"),
    ("EKF ", "NAV "),
    ("NavEKF", "导航"),
    ("ChibiOS", "RTOS"),
    ("MAVLink", "通信"),
    ("PreArm", "解锁前检查"),
    ("AHRS", "姿态"),
    ("DCM", "姿态"),
    ("Compass", "罗盘"),
    ("Barometer", "气压计"),
    ("Baro ", "气压 "),
    ("Throttle", "油门"),
    ("Mission", "任务"),
    ("Waypoint", "航点"),
    ("Rally", "集结点"),
    ("Fence", "围栏"),
    ("Takeoff", "起飞"),
    ("Landing", "降落中"),
    ("Land ", "降落 "),
    ("Failsafe", "失控保护"),
    ("failsafe", "失控保护"),
    ("Rangefinder", "测距仪"),
    ("Terrain", "地形"),
    ("Parachute", "降落伞"),
    ("AutoTune", "自动调参"),
]

_LEAK_MSGS = {
    "Need 3D Fix": "需要3D定位",
    "RC not calibrated": "遥控未校准",
    "Hardware safety switch": "安全开关未解除",
    "Battery not healthy": "电池异常",
    "Logging not available": "日志不可用",
    "not healthy": "异常",
    "not calibrated": "未校准",
    "Initialising": "初始化中",
    "Ready to FLY": "准备就绪",
    "Ready to fly": "准备就绪",
    "GROUND START": "地面启动",
    "Calibrating barometer": "校准气压计中",
    "Motors Emergency Stopped": "电机紧急停止",
    "GPS Glitch": "GPS异常",
    "Lost GPS": "GPS信号丢失",
    "Regained GPS": "GPS信号恢复",
    "Low Battery": "低电量",
    "Critical Battery": "电量极低",
    "Crash: Disarming": "碰撞: 锁定",
    "Bad Velocity": "速度异常",
    "Bad AHRS": "姿态异常",
    "EKF not started": "导航未启动",
    "Gyros not healthy": "陀螺仪异常",
    "Accels not healthy": "加速计异常",
    "Barometer not healthy": "气压计异常",
    "Compass not calibrated": "罗盘未校准",
    "Gyros not calibrated": "陀螺仪未校准",
    "Accels not calibrated": "加速计未校准",
    "3D Accel Cal needed": "需要三维加速计校准",
    "Waiting for navigation alignment": "等待导航对准",
    "Radio failsafe": "无线电失控保护",
    "Battery failsafe": "电池失控保护",
    "GCS failsafe": "地面站失控保护",
    "Throttle failsafe": "油门失控保护",
    "Fence breach": "围栏越界",
    "Fence disabled": "围栏已禁用",
    "No terrain data": "无地形数据",
    "is using GPS": "正在使用GPS",
    "is not using GPS": "未使用GPS",
    "started relative aiding": "启用相对辅助",
    "stopped relative aiding": "停用相对辅助",
    "IMU0 ": "IMU0 ",
    "IMU1 ": "IMU1 ",
    "IMU2 ": "IMU2 ",
}

_TRAILING_EN = [
    (" cleared", " 已解除"),
    (" triggered", " 已触发"),
    (" enabled", " 已启用"),
    (" disabled", " 已禁用"),
    (" complete", " 完成"),
    (" failed", " 失败"),
    (" on", " 开启"),
    (" off", " 关闭"),
]


_BRAND_ONLY = [
    ("ArduCopter", "FC"),
    ("ArduPlane", "FC"),
    ("ArduPilot", "FC"),
    ("APM", "FC"),
    ("ChibiOS", "RTOS"),
]


def filter_statustext(text: str, locale: str = "zh") -> str:
    if locale == "en":
        for old, new in _BRAND_ONLY:
            text = text.replace(old, new)
        return text
    for old, new in _LEAK_MSGS.items():
        text = text.replace(old, new)
    for old, new in _LEAK_FILTERS:
        text = text.replace(old, new)
    for old, new in _TRAILING_EN:
        if text.endswith(old):
            text = text[: -len(old)] + new
            break
    return text
