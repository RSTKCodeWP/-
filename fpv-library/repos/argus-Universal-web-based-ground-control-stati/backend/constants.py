"""Vehicle mode tables. Each entry maps ArduPilot's custom_mode integer to a
display name. Verified against `ArduCopter/mode.h`, `ArduPlane/mode.h`,
`Rover/mode.h`, `ArduSub/mode.h` (May 2026 master).

Adding modes here doesn't enable them — it's only how we *display* an
incoming HEARTBEAT.custom_mode value. Missing entries fall back to "MODE%d".
"""

# Copter — ArduCopter/mode.h `enum class Number`
COPTER_MODES = {
    0: "自稳",
    1: "特技",
    2: "定高",
    3: "自动",
    4: "引导",
    5: "悬停",
    6: "返航",
    7: "绕圈",
    9: "降落",
    11: "漂移",
    13: "运动",
    14: "翻转",
    15: "自动调参",
    16: "定点",
    17: "刹停",
    18: "抛飞",
    19: "避障",
    20: "引导无导航",
    21: "智能返航",
    22: "光流定点",
    23: "跟随",
    24: "蛇形",
    25: "系统辨识",
    26: "自旋下降",
    27: "自动返航",
    28: "翻龟",
}
PLANE_MODES = {
    0: "手动",
    1: "绕圈",
    2: "自稳",
    3: "训练",
    4: "特技",
    5: "辅助A",
    6: "辅助B",
    7: "巡航",
    8: "自动调参",
    10: "自动",
    11: "返航",
    12: "盘旋",
    13: "起飞",
    14: "自动避让",
    15: "引导",
    16: "初始化",
    17: "旋翼自稳",
    18: "旋翼悬停",
    19: "旋翼定点",
    20: "旋翼降落",
    21: "旋翼返航",
    22: "旋翼自调",
    23: "旋翼特技",
    24: "热气流",
    25: "盘旋至定点",
    26: "自动着陆",
}
ROVER_MODES = {
    0: "手动",
    1: "特技",
    3: "转向",
    4: "固定",
    5: "悬停",
    6: "跟随",
    7: "简单",
    8: "停靠",
    9: "环线",
    10: "自动",
    11: "返航",
    12: "智能返航",
    15: "引导",
    16: "初始化",
}
SUB_MODES = {
    0: "自稳",
    1: "特技",
    2: "定深",
    3: "自动",
    4: "引导",
    7: "绕圈",
    9: "水面",
    16: "定点",
    19: "手动",
    20: "电机检测",
    21: "地形跟随",
}
COPTER_BTNS = [[0, "自稳"], [2, "定高"], [5, "悬停"], [3, "自动"], [6, "返航"], [9, "降落"]]
PLANE_BTNS = [
    [0, "手动"],
    [10, "自动"],
    [11, "返航"],
    [12, "盘旋"],
    [19, "旋翼定点"],
    [18, "旋翼悬停"],
    [17, "旋翼自稳"],
    [21, "旋翼返航"],
    [20, "旋翼降落"],
]
ROVER_BTNS = [[0, "手动"], [4, "固定"], [10, "自动"], [15, "引导"], [11, "返航"]]
SUB_BTNS = [[0, "自稳"], [2, "定深"], [16, "定点"], [3, "自动"], [4, "引导"]]
FIX_NAMES = {0: "无定位", 1: "无定位", 2: "2D", 3: "3D", 4: "差分", 5: "RTK浮动", 6: "RTK固定"}

COPTER_MODES_EN = {
    0: "Stabilize",
    1: "Acro",
    2: "Alt Hold",
    3: "Auto",
    4: "Guided",
    5: "Loiter",
    6: "RTL",
    7: "Circle",
    9: "Land",
    11: "Drift",
    13: "Sport",
    14: "Flip",
    15: "AutoTune",
    16: "PosHold",
    17: "Brake",
    18: "Throw",
    19: "AvoidADSB",
    20: "GuidedNoGPS",
    21: "Smart RTL",
    22: "FlowHold",
    23: "Follow",
    24: "ZigZag",
    25: "SystemID",
    26: "Autorotate",
    27: "Auto RTL",
    28: "Turtle",
}
PLANE_MODES_EN = {
    0: "Manual",
    1: "Circle",
    2: "Stabilize",
    3: "Training",
    4: "Acro",
    5: "FBW-A",
    6: "FBW-B",
    7: "Cruise",
    8: "AutoTune",
    10: "Auto",
    11: "RTL",
    12: "Loiter",
    13: "Takeoff",
    14: "AvoidADSB",
    15: "Guided",
    16: "Initialising",
    17: "Q-Stabilize",
    18: "Q-Hover",
    19: "Q-Loiter",
    20: "Q-Land",
    21: "Q-RTL",
    22: "QAutoTune",
    23: "QAcro",
    24: "Thermal",
    25: "Loiter2QLand",
    26: "Autoland",
}
ROVER_MODES_EN = {
    0: "Manual",
    1: "Acro",
    3: "Steering",
    4: "Hold",
    5: "Loiter",
    6: "Follow",
    7: "Simple",
    8: "Dock",
    9: "Circle",
    10: "Auto",
    11: "RTL",
    12: "Smart RTL",
    15: "Guided",
    16: "Initialising",
}
SUB_MODES_EN = {
    0: "Stabilize",
    1: "Acro",
    2: "Depth Hold",
    3: "Auto",
    4: "Guided",
    7: "Circle",
    9: "Surface",
    16: "PosHold",
    19: "Manual",
    20: "Motor Detect",
    21: "Surftrak",
}
COPTER_BTNS_EN = [[0, "Stabilize"], [2, "Alt Hold"], [5, "Loiter"], [3, "Auto"], [6, "RTL"], [9, "Land"]]
PLANE_BTNS_EN = [
    [0, "Manual"],
    [10, "Auto"],
    [11, "RTL"],
    [12, "Loiter"],
    [19, "Q-Loiter"],
    [18, "Q-Hover"],
    [17, "Q-Stabilize"],
    [21, "Q-RTL"],
    [20, "Q-Land"],
]
ROVER_BTNS_EN = [[0, "Manual"], [4, "Hold"], [10, "Auto"], [15, "Guided"], [11, "RTL"]]
SUB_BTNS_EN = [[0, "Stabilize"], [2, "Depth Hold"], [16, "PosHold"], [3, "Auto"], [4, "Guided"]]
FIX_NAMES_EN = {0: "No Fix", 1: "No Fix", 2: "2D", 3: "3D", 4: "DGPS", 5: "RTK Float", 6: "RTK Fixed"}

# Category classification for mode quick-switch UI grouping.
# manual=direct stick control, assisted=stabilised, auto=autonomous, emergency=safety
COPTER_CATEGORIES: dict[int, str] = {
    0: "manual", 1: "manual", 2: "assisted", 3: "auto", 4: "auto",
    5: "assisted", 6: "emergency", 7: "auto", 9: "emergency",
    11: "assisted", 13: "manual", 14: "manual", 15: "assisted",
    16: "assisted", 17: "emergency", 18: "auto", 19: "emergency",
    20: "auto", 21: "emergency", 22: "assisted", 23: "assisted",
    24: "assisted", 25: "auto", 26: "emergency", 27: "emergency", 28: "emergency",
}
PLANE_CATEGORIES: dict[int, str] = {
    0: "manual", 1: "auto", 2: "manual", 3: "manual", 4: "manual",
    5: "assisted", 6: "assisted", 7: "assisted", 8: "assisted",
    10: "auto", 11: "emergency", 12: "assisted", 13: "auto",
    14: "emergency", 15: "auto", 16: "auto",
    17: "manual", 18: "assisted", 19: "assisted", 20: "emergency",
    21: "emergency", 22: "assisted", 23: "manual", 24: "assisted",
    25: "emergency", 26: "emergency",
}
ROVER_CATEGORIES: dict[int, str] = {
    0: "manual", 1: "manual", 3: "assisted", 4: "assisted", 5: "assisted",
    6: "auto", 7: "assisted", 8: "auto", 9: "auto",
    10: "auto", 11: "emergency", 12: "emergency", 15: "auto", 16: "auto",
}
SUB_CATEGORIES: dict[int, str] = {
    0: "manual", 1: "manual", 2: "assisted", 3: "auto", 4: "auto",
    7: "auto", 9: "emergency", 16: "assisted", 19: "manual", 20: "auto", 21: "assisted",
}
