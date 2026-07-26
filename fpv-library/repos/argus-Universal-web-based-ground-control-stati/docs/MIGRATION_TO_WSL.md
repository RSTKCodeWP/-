# Argus 开发环境迁移：VMware → Windows + WSL2 + usbipd-win

迁移目标：解决 VMware USB passthrough 写入死锁，把 hardware-blocked 验证（WebSerial 直连、校准、firmware 上传）解封。

迁移决策见 [docs/audits/sitl_validation_2026-05-24.md](audits/sitl_validation_2026-05-24.md)。

## 总览

```
[Windows 主机]                    [WSL2 Ubuntu]
                                  ├── ~/argus  (代码)
[USB FC] ─────usbipd→ /dev/ttyACM0
                                  ├── ~/ardupilot (ArduPilot fork)
[Chrome] ──→ http://localhost:8100
                                  └── ~/.claude (memory)
```

预估耗时：**首次半天**（含 SITL build），日常用 = 立即生效。

---

## Phase 1 — Windows 主机准备（管理员 PowerShell）

```powershell
# 1. 装 WSL2 + Ubuntu (会自动重启)
wsl --install -d Ubuntu

# 重启后会弹 Ubuntu 终端，设用户名 + 密码

# 2. 装 usbipd-win
winget install --interactive --exact dorssel.usbipd-win
# 或: https://github.com/dorssel/usbipd-win/releases 装最新 MSI

# 3. 验证 WSL 跑起来 + USB-IP 内核模块
wsl --list --verbose
# 应该看到 Ubuntu 是 VERSION 2 (不是 1)
```

---

## Phase 2 — WSL 内一次性 bootstrap

进入 Ubuntu 终端，先把代理设好（不然 apt/git/npm 会卡）：

```bash
# 测一下能不能到 Windows 主机的代理
curl -x http://192.168.100.1:7897 -sI https://www.google.com | head -1

# 持久化代理（写进 ~/.bashrc）
cat >> ~/.bashrc <<'EOF'
alias proxy='export http_proxy=http://192.168.100.1:7897; export https_proxy=http://192.168.100.1:7897; export HTTPS_PROXY=$https_proxy; export HTTP_PROXY=$http_proxy'
alias unproxy='unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY'
EOF
source ~/.bashrc
proxy
```

**装 git + 装 Claude Code + clone + 启 claude — 4 行就够，其余全自动**：

```bash
# 1. 最少装两个工具
sudo apt update && sudo apt install -y git curl
curl -fsSL https://claude.ai/install.sh | bash
exec bash    # 重载 PATH

# 2. SSH key（如果有就拷过来；没有就用 https clone 也行）
# 选项 A — 从 VMware 拷私钥过来（推荐，跟 VMware 时期一致）
#   在 VMware 里: cat ~/.ssh/id_ed25519
#   在 WSL: mkdir -p ~/.ssh && chmod 700 ~/.ssh
#           nano ~/.ssh/id_ed25519  # 粘贴
#           chmod 600 ~/.ssh/id_ed25519
# 选项 B — 用 HTTPS clone（无 SSH 折腾）—— 后续 push 需要 gh auth login

# 3. Clone（SSH 或 HTTPS 二选一）
git clone git@github.com:L-X-Yao/argus.git ~/argus   # SSH
# git clone https://github.com/L-X-Yao/argus.git ~/argus   # HTTPS

# 4. 启 claude，告诉它"开始迁移"
cd ~/argus
claude
```

Claude 一进来读 CLAUDE.md，看到 `.claude-memory-bootstrap/` 存在 + `~/argus-venv/` 不存在 + 在 WSL，会主动问"要跑 `scripts/wsl_first_run.sh` 吗？"。**答 yes**，它就帮你：

| 步骤 | 谁做 | 备注 |
| - | - | - |
| apt 装系统包 | 脚本 | 会问一次 sudo 密码 |
| Node 20 (NodeSource) | 脚本 | |
| `gh` CLI | 脚本 | SSH 兜底用 |
| `~/argus-venv` 创建 + 激活进 `.bashrc` | 脚本 | |
| `pip install -e ".[dev]"` | 脚本 | |
| `npm install` | 脚本 | |
| SSH key 检测 + 引导 | 脚本 | 不会自动复制私钥 |
| 拷 memory 到 `~/.claude/projects/-home-$USER-argus/memory/` | 脚本 | |
| 跑测试门（ruff + pytest 1040 + vitest 487 + svelte-check） | 脚本 | |
| 打印下一步（SITL/usbipd 命令） | 脚本 | |

全程 3-5 min（不含 SITL）。

---

## Phase 3 — ArduPilot SITL（可选，按需）

只在 USB 不通需要回退到仿真验证时才装：

```bash
cd ~
git clone --recursive https://github.com/ArduPilot/ardupilot.git
cd ~/ardupilot
git checkout master  # 或 checkout 你需要的特定 commit/分支

# 装 ArduPilot 编译依赖
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile

# 编译 SITL Copter (~10-20 分钟 first build, ccache 后秒级)
./waf configure --board sitl
./waf copter

ls build/sitl/bin/arducopter  # 验证产物
```

---

## Phase 3 — Claude Code memory（脚本已处理）

`scripts/wsl_first_run.sh` 会从 `.claude-memory-bootstrap/` 自动拷 13 个 memory 文件到正确的 `~/.claude/projects/-home-<USER>-argus/memory/`。无需手动操作。

完事后清理 staging 目录（个人偏好不该长期在 repo 里）：

```bash
git rm -rf .claude-memory-bootstrap/
git commit -m "chore: remove migration staging"
git push
```

---

## Phase 4 — USB 验证（关键里程碑）

这是迁移的全部意义所在。

### Windows 主机（管理员 PowerShell）

```powershell
# 列出所有 USB 设备
usbipd list

# 找到你的 FC（应该是 BUSID xxx, VID:PID 与你的飞控匹配）

# 第一次绑定（持久化共享给 WSL）
usbipd bind --busid=<BUSID>

# 附给 WSL
usbipd attach --wsl --busid=<BUSID>

# 之后每次插拔后只需要 attach（bind 是一次性的）
```

### WSL 内

```bash
# 看 USB 设备
lsusb  # 应该能看到你的飞控 USB 设备

# 看串口
ls -la /dev/ttyACM*  # 应该有 ttyACM0 (+ ttyACM1)

# 权限：把自己加进 dialout
sudo usermod -aG dialout $USER
# 注销 WSL 重进生效：在 PowerShell 里 wsl --shutdown 然后重新打开

# 跑 A.0 baseline（VMware 里这步会 kernel 死锁，WSL 应该正常）
cd ~/argus
python3 - <<'PY'
import sys; sys.path.insert(0, '.')
import time
from backend.drone_link import DroneLink
link = DroneLink()
ok = link.connect('/dev/ttyACM0', baudrate=115200, protocol='auto')
print(f"connect={ok}")
time.sleep(3)
st = link.get_state()
print(f"frames={st['frames']} autopilot={st['autopilot']} mode={st['mode']}")
link.disconnect()
PY
```

**期望输出**：`connect=True frames>30 autopilot=1 mode=...`。如果 `frames=0` — 同样的死锁症状，那就是 usbipd 也搞不定，要考虑 dual-boot 方案（极少见但可能）。

---

## Phase 5 — 完成验证

USB 通了之后立刻把之前 hardware-blocked 的清单跑掉：

```bash
# 在 WSL 内
cd ~/argus

# A.1: WebSerial 直连 — Windows Chrome 打开 http://localhost:8100，点 USB 按钮
python run.py  # 然后浏览器操作

# A.2: 校准全套 — 在 UI 里依次跑 compass / gyro / level / baro / accel
# (这步是手动操作 + 真传感器扭动)

# Firmware 上传 — 只在你打算给飞控烧自己编译的固件时跑，不要拿通用 ArduPilot APJ 测
```

跑完更新 `docs/audits/sitl_validation_2026-05-24.md` 把 A.1/A.2 状态从 ⚠️ 改成 ✅。

---

## Phase 6 — VMware 退役

**不要立刻删 VM** — 保留至少一周作为 fallback。

```
✓ WSL 跑通 npm install + pytest + vitest + svelte-check + ruff 全绿
✓ WSL 跑通 USB telemetry 不死锁
✓ WSL 跑通 SITL ArduCopter
✓ 一周日常开发无回退
   ↓
关闭 VMware VM（保留磁盘镜像）
   ↓
一个月稳定后才删
```

---

## 回退预案

迁过去如果 WSL 出意外问题（usbipd 不稳、性能不及预期、其他兼容性），原 VMware VM 还在，直接切回继续 SITL 工作。代码已经全部 push 到 GitHub，两边随时 sync。

最坏情况：USB 在 WSL 也死锁 → 这时基本可以确认是飞控的 USB CDC 栈对某些 host write 不健壮（不是 hypervisor 问题），要在 FC 固件侧排查 USB 中断处理。

---

## 关键提醒

- ⚠️ **代码不要放 `/mnt/c/...`** — NTFS 跨边界访问慢 10 倍。一定放 WSL ext4（`~/argus`）。
- ⚠️ **ArduPilot 不要从 samba 拷过来** — 50GB 大部分是 build artifacts，重新 clone 1-2GB + 重编 SITL 才是干净的。
- ⚠️ **proxy 别忘** — npm / pip / git clone 默认不走 FlClash TUN，需要手动 `proxy` 别名（除非你把 FlClash 配成 TUN 模式接管 WSL 流量）。
- ⚠️ **usbipd `bind` 一次性，`attach` 每次重启都要重做** — 写个 PowerShell 启动脚本省事。
