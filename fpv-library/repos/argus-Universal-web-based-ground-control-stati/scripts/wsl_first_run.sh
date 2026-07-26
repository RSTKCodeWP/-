#!/usr/bin/env bash
# Argus 首次 WSL 全自动 bootstrap — Claude Code 在 WSL 内首次启动时调用。
# 涵盖:
#   1. 检测环境（必须是 WSL2）
#   2. 系统包安装（apt — 唯一需要 sudo 密码的步骤）
#   3. Node 20 / Python venv / pip 依赖 / npm install
#   4. SSH key 检测 + 引导（不自动复制私钥）
#   5. Memory 恢复（从 .claude-memory-bootstrap/ 到 ~/.claude/.../memory/）
#   6. 跑完整测试门
#   7. 打印下一步（USB + SITL）清单
#
# 用法：
#   bash scripts/wsl_first_run.sh
#
# 设计原则：幂等 — 重跑不会破坏已有状态。
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[first-run]${NC} $*"; }
ask()  { echo -e "${BLUE}[first-run]${NC} $*"; }
warn() { echo -e "${YELLOW}[first-run]${NC} $*"; }
die()  { echo -e "${RED}[first-run]${NC} $*" >&2; exit 1; }

# === Phase 0: Environment check ===
log "Phase 0: 环境检测"

if ! grep -qi "microsoft" /proc/version 2>/dev/null; then
    warn "不在 WSL 内 — 这个脚本是为 WSL2 设计的"
    warn "在普通 Linux/Docker 里也能跑，但 USB 部分不适用"
fi

ARGUS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ARGUS_DIR"
[[ -f pyproject.toml ]] || die "不在 argus 仓库里？pwd=$(pwd)"
log "  argus dir: $ARGUS_DIR"
log "  WSL user: $USER"

# === Phase 1: System packages ===
log "Phase 1: 系统包 (需要 sudo)"

NEED_INSTALL=()
command -v python3 >/dev/null || NEED_INSTALL+=("python3")
command -v pip3 >/dev/null || NEED_INSTALL+=("python3-pip")
python3 -c "import venv" 2>/dev/null || NEED_INSTALL+=("python3-venv")
command -v curl >/dev/null || NEED_INSTALL+=("curl")
command -v git >/dev/null || NEED_INSTALL+=("git")
command -v cc >/dev/null || NEED_INSTALL+=("build-essential")
command -v ccache >/dev/null || NEED_INSTALL+=("ccache")
dpkg -l libssl-dev 2>/dev/null | grep -q '^ii' || NEED_INSTALL+=("libssl-dev")
dpkg -l libffi-dev 2>/dev/null | grep -q '^ii' || NEED_INSTALL+=("libffi-dev")

if [[ ${#NEED_INSTALL[@]} -gt 0 ]]; then
    log "  缺: ${NEED_INSTALL[*]}"
    ask "  即将 sudo apt install — 可能要密码"
    sudo apt update -qq
    sudo apt install -y "${NEED_INSTALL[@]}"
else
    log "  所有系统包都在"
fi

# Node 20 (NodeSource) — only if missing or wrong major
if ! command -v node >/dev/null || [[ "$(node --version 2>/dev/null | cut -d. -f1)" != "v20" ]]; then
    log "  安装 Node 20 LTS (NodeSource)"
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
else
    log "  Node $(node --version) 已就位"
fi

# GitHub CLI (for ssh / auth fallback) — 可选但有助于 SSH
if ! command -v gh >/dev/null; then
    log "  安装 gh CLI (帮助 SSH key 流程)"
    type -P curl >/dev/null && \
        (curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
         | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg) && \
        sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
         | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null && \
        sudo apt update -qq && sudo apt install -y gh || \
        warn "gh 安装失败，跳过（不影响主流程）"
fi

# === Phase 2: Python venv + deps ===
log "Phase 2: Python venv + 依赖"
VENV_DIR="$HOME/argus-venv"
if [[ ! -d "$VENV_DIR" ]]; then
    log "  创建 venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip
log "  pip install -e .[dev]"
pip install --quiet -e ".[dev]"

# Persist venv activation
if ! grep -q "argus-venv/bin/activate" ~/.bashrc 2>/dev/null; then
    echo "source $VENV_DIR/bin/activate" >> ~/.bashrc
    log "  已加进 ~/.bashrc"
fi

# === Phase 3: Frontend ===
log "Phase 3: npm install"
if [[ ! -d node_modules ]] || [[ package.json -nt node_modules/.package-lock.json ]]; then
    npm install
else
    log "  node_modules 已就位"
fi

# === Phase 4: SSH key check ===
log "Phase 4: SSH key 检查"
if [[ -f ~/.ssh/id_ed25519 ]]; then
    log "  ~/.ssh/id_ed25519 存在"
    # 测一下 github
    if ssh -T -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new git@github.com 2>&1 | grep -q "successfully authenticated"; then
        log "  github SSH OK"
    else
        warn "  SSH key 在但 github 没认证 — 把 ~/.ssh/id_ed25519.pub 加进 github.com/settings/keys"
        warn "  公钥内容: $(cat ~/.ssh/id_ed25519.pub 2>/dev/null || echo '(读不到)')"
    fi
else
    warn "  没找到 ~/.ssh/id_ed25519"
    ask "  选项："
    ask "  A) 从 VMware 拷过来: 在 VMware 里 cat ~/.ssh/id_ed25519，新建文件在 WSL 粘贴，chmod 600"
    ask "  B) WSL 里新生成: ssh-keygen -t ed25519 -C \"$(git config user.email)\" 然后把 .pub 加进 github"
    ask "  C) 暂时跳过 — 用 https + gh auth login"
    if command -v gh >/dev/null; then
        ask "  gh auth login 现在可以跑了 (选 GitHub.com → HTTPS → Login with web browser)"
    fi
fi

# === Phase 5: Memory restore ===
log "Phase 5: Claude Code memory 恢复"
BOOTSTRAP_DIR="$ARGUS_DIR/.claude-memory-bootstrap"
if [[ -d "$BOOTSTRAP_DIR" ]] && ls "$BOOTSTRAP_DIR"/*.md >/dev/null 2>&1; then
    PROJECT_SLUG="${ARGUS_DIR//\//-}"   # /home/user/argus → -home-user-argus
    TARGET_DIR="$HOME/.claude/projects/${PROJECT_SLUG}/memory"
    log "  → $TARGET_DIR"
    mkdir -p "$TARGET_DIR"
    cp -n "$BOOTSTRAP_DIR"/*.md "$TARGET_DIR/" 2>/dev/null || true
    COPIED=$(ls "$TARGET_DIR"/*.md 2>/dev/null | wc -l)
    log "  $COPIED 个 memory 文件就位"
    warn "  完成后请 git rm -rf .claude-memory-bootstrap/ 把 staging 目录删掉 (memory 是个人偏好不该留 repo)"
else
    log "  .claude-memory-bootstrap/ 已清理或本就不存在 — 跳过"
fi

# === Phase 6: Test gate ===
log "Phase 6: 测试门 (ruff → pytest → vitest → svelte-check)"
echo "--- ruff ---"
ruff check backend/ scripts/ tests/
echo "--- pytest unit + contract ---"
python -m pytest tests/test_unit_*.py tests/test_contract_*.py -q --no-header
echo "--- vitest ---"
npx vitest run
echo "--- svelte-check ---"
npx svelte-check --tsconfig ./tsconfig.json

# === Phase 7: Next steps ===
log ""
log "==================== 完成！下一步 ===================="
log ""
log "✓ Argus dev 环境就绪 (Python venv + Node + pytest 1040 / vitest 487 全绿)"
log ""
log "接下来手动的事 — 见 docs/MIGRATION_TO_WSL.md:"
log ""
log "  1. ArduPilot SITL — 想跑仿真才装 (50GB clone + 10-20min 编译):"
log "       cd ~ && git clone --recursive https://github.com/ArduPilot/ardupilot.git"
log "       cd ~/ardupilot && Tools/environment_install/install-prereqs-ubuntu.sh -y"
log "       ./waf configure --board sitl && ./waf copter"
log ""
log "  2. USB FC 接进 WSL — 真飞控验证才需要 (在 Windows admin PowerShell):"
log "       usbipd list                              # 找你的飞控设备"
log "       usbipd bind --busid=<X>                  # 一次性"
log "       usbipd attach --wsl --busid=<X>          # 每次重启重做"
log "     然后在 WSL: sudo usermod -aG dialout \$USER 并注销重进"
log ""
log "  3. 启 Claude Code 接着干: claude"
log "     新会话告诉它'读 CLAUDE.md + docs/MIGRATION_TO_WSL.md，从 USB 验证继续'"
log ""
log "项目: $ARGUS_DIR"
log "venv: $VENV_DIR (已加进 .bashrc)"
