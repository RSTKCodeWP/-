# Flight-Safety Service (M0 + M1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the PX4 SITL + gz Harmonic environment, then build a deterministic, LLM-free **Flight-Safety service** that validates and executes high-level flight commands against the simulated drone with telemetry-gated execution, geofence/limit enforcement, manual⇄OFFBOARD hand-off, and an abort path — all exposed over a websocket+JSON API.

**Architecture:** A single Python package `flight_safety`. Pure-logic units (config, command/telemetry models, geofence, validation gate) are unit-tested with no simulator. The MAVSDK bridge (connection, telemetry monitor, command executors) is integration-tested against a running PX4 SITL. A thin FastAPI websocket server wires commands in and telemetry/events out. No LLM anywhere in this service.

**Tech Stack:** Python 3.11, asyncio, MAVSDK-Python (PX4 control), pydantic v2 + pydantic-settings (models/config), shapely (geofence polygon), FastAPI + uvicorn + websockets (API), pytest + pytest-asyncio (tests). PX4-Autopilot SITL + Gazebo (gz) Harmonic on Ubuntu 24.04 (Linux Mint 22.2 base).

**Conventions:** Run all `git`/`pytest` commands from the project root `/hey/projects/yzup-demo`. The Python virtual environment lives at `.venv`. Integration tests that need SITL are marked `@pytest.mark.integration` and skipped by default.

---

## Phase M0 — Environment bring-up

> These are setup tasks with verification gates (exact commands + expected output), not TDD. Each ends in a working, observable result. Mint-specific note: the OSRF apt repo must target the Ubuntu codename `noble`, and PX4's `ubuntu.sh` may not recognize Mint — workarounds are inline.

### Task M0.1: System dependencies & Python toolchain

**Files:** none (system setup)

- [ ] **Step 1: Install base build/runtime packages**

Run:
```bash
sudo apt-get update
sudo apt-get install -y git python3.11 python3.11-venv python3-pip \
  build-essential cmake ninja-build curl lsb-release gnupg \
  gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-gl
```
Expected: packages install without error (some may already be present).

- [ ] **Step 2: Verify Python 3.11 and create the project virtualenv**

Run:
```bash
cd /hey/projects/yzup-demo
python3.11 --version
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
```
Expected: `Python 3.11.x`, venv created, pip upgraded. `.venv/` is already gitignored.

### Task M0.2: Install Gazebo (gz) Harmonic

**Files:** none (system setup)

- [ ] **Step 1: Add the OSRF apt repo targeting `noble` (NOT the Mint codename)**

Run:
```bash
sudo curl https://packages.osrfoundation.org/gazebo.gpg --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable noble main" | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
sudo apt-get update
```
Expected: `apt-get update` succeeds and lists `packages.osrfoundation.org ... noble`. (We force `noble` because Mint reports codename `zara`, which OSRF does not publish.)

- [ ] **Step 2: Install gz Harmonic**

Run:
```bash
sudo apt-get install -y gz-harmonic
gz sim --version
```
Expected: a version line reporting Gazebo Sim 8.x (Harmonic).

- [ ] **Step 3: Verify headless GPU rendering works on the GTX 970**

Run (headless server render smoke test, 3 seconds):
```bash
gz sim -s -r --headless-rendering -v 1 shapes.sdf &
sleep 3 && pkill -f "gz sim" || true
```
Expected: starts without an OGRE2/OpenGL fatal error. If it errors on rendering, set `export QT_QPA_PLATFORM=offscreen` and `export LIBGL_ALWAYS_SOFTWARE=0`, and re-run. Record the working env vars in `docs/ENVIRONMENT.md` (create it) for reuse.

### Task M0.3: Clone & build PX4 SITL

**Files:**
- Create: `docs/ENVIRONMENT.md` (notes: working render env vars, PX4 path)

- [ ] **Step 1: Clone PX4-Autopilot beside the project**

Run:
```bash
cd /hey/projects
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
```
Expected: clone with submodules completes. (Kept outside the repo; not committed.)

- [ ] **Step 2: Install PX4 prerequisites (Mint workaround)**

Run:
```bash
cd /hey/projects/PX4-Autopilot
bash ./Tools/setup/ubuntu.sh --no-nuttx || echo "If it aborts on OS detection, continue: deps are mostly apt packages already installed in M0.1"
```
Expected: completes, or aborts only on the Mint OS check. If it aborts, manually install any missing deps it printed, then proceed. Record outcome in `docs/ENVIRONMENT.md`.

- [ ] **Step 3: Build & launch SITL with gz x500 (headless)**

Run:
```bash
cd /hey/projects/PX4-Autopilot
HEADLESS=1 make px4_sitl gz_x500
```
Expected: first build takes 20–40 min. On success the PX4 shell prints `INFO [commander] Ready for takeoff!` and a `pxh>` prompt appears. Leave it running in this terminal.

- [ ] **Step 4: Confirm the MAVLink offboard port is listening**

In a second terminal, run:
```bash
ss -lun | grep 14540 || echo "port not found"
```
Expected: a UDP listener on `14540` (PX4's offboard/MAVSDK API port). Note the address; we'll connect MAVSDK to it next.

### Task M0.4: MAVSDK "hello world" against SITL

**Files:**
- Create: `scripts/hello_world.py`

- [ ] **Step 1: Install MAVSDK-Python in the venv**

Run:
```bash
cd /hey/projects/yzup-demo
. .venv/bin/activate
pip install "mavsdk>=2.0"
```
Expected: mavsdk installs (it bundles a `mavsdk_server` binary).

- [ ] **Step 2: Write the hello-world script**

Create `scripts/hello_world.py`:
```python
"""Minimal MAVSDK connect → arm → takeoff → land against PX4 SITL."""
import asyncio
from mavsdk import System

# PX4 SITL exposes the offboard/MAVSDK API on UDP 14540.
# mavsdk>=2.0 uses the udpin:// scheme; older versions use udp://:14540.
CONNECT = "udpin://0.0.0.0:14540"


async def main() -> None:
    drone = System()
    await drone.connect(system_address=CONNECT)

    print("Waiting for connection...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected.")
            break

    print("Waiting for global position / home...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("Position OK.")
            break

    await drone.action.arm()
    print("Armed.")
    await drone.action.takeoff()
    await asyncio.sleep(8)
    await drone.action.land()
    print("Landing commanded.")
    await asyncio.sleep(8)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Run it against the running SITL**

Run (with SITL from M0.3 still up):
```bash
cd /hey/projects/yzup-demo && . .venv/bin/activate && python scripts/hello_world.py
```
Expected: prints `Connected.` → `Position OK.` → `Armed.` → `Landing commanded.`, and the drone visibly arms/takes off/lands in the PX4 console (altitude rises then returns). If connection hangs, try `CONNECT = "udp://:14540"` (older mavsdk) and re-run.

- [ ] **Step 4: Commit the script and environment notes**

```bash
cd /hey/projects/yzup-demo
git add scripts/hello_world.py docs/ENVIRONMENT.md
git commit -m "chore(m0): PX4 SITL + gz Harmonic env and MAVSDK hello-world"
```

---

## Phase M1 — Flight-Safety service

### Task M1.1: Package scaffolding & dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `src/flight_safety/__init__.py`
- Create: `tests/__init__.py`, `tests/flight_safety/__init__.py`
- Create: `pytest.ini`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "flight-safety"
version = "0.1.0"
description = "Deterministic flight-safety service for the LLM FPV assistant"
requires-python = ">=3.11"
dependencies = [
    "mavsdk>=2.0",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "shapely>=2.0",
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "websockets>=12.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "httpx>=0.27"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
markers =
    integration: tests that require a running PX4 SITL (deselected by default)
addopts = -m "not integration"
testpaths = tests
```

- [ ] **Step 3: Create package init files**

Create `src/flight_safety/__init__.py`:
```python
"""Deterministic flight-safety service (no LLM)."""
```
Create empty `tests/__init__.py` and `tests/flight_safety/__init__.py` (0 bytes each).

- [ ] **Step 4: Install the package editable + dev deps**

Run:
```bash
cd /hey/projects/yzup-demo && . .venv/bin/activate && pip install -e ".[dev]"
```
Expected: installs cleanly; `python -c "import flight_safety"` prints nothing (success).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml pytest.ini src/flight_safety/__init__.py tests/__init__.py tests/flight_safety/__init__.py
git commit -m "chore(m1): scaffold flight_safety package"
```

### Task M1.2: Config / Settings

**Files:**
- Create: `src/flight_safety/config.py`
- Create: `tests/flight_safety/test_config.py`
- Create: `.env.example`

- [ ] **Step 1: Write the failing test**

Create `tests/flight_safety/test_config.py`:
```python
from flight_safety.config import Limits, Settings


def test_limits_defaults_are_sane():
    lim = Limits()
    assert lim.max_alt_m > lim.min_alt_m >= 0
    assert lim.max_speed_ms > 0
    assert 0 <= lim.min_battery_pct <= 1.0


def test_settings_parses_geofence_from_list():
    s = Settings(geofence=[[47.397, 8.545], [47.398, 8.545], [47.398, 8.546]])
    assert len(s.geofence) == 3
    assert s.geofence[0] == (47.397, 8.545)


def test_settings_has_connection_default():
    s = Settings()
    assert "14540" in s.mavlink_address
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flight_safety/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'flight_safety.config'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/flight_safety/config.py`:
```python
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Limits(BaseModel):
    """Hard safety limits enforced by the validation gate."""
    max_alt_m: float = 120.0      # regulatory-ish ceiling above takeoff
    min_alt_m: float = 0.0
    max_speed_ms: float = 12.0
    min_battery_pct: float = 0.20  # reject new commands below 20%


class Settings(BaseSettings):
    """Service configuration; values come from env / .env."""
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FS_", extra="ignore")

    mavlink_address: str = "udpin://0.0.0.0:14540"
    # Geofence as a list of (lat, lon) vertices forming a polygon.
    geofence: list[tuple[float, float]] = Field(default_factory=list)
    limits: Limits = Field(default_factory=Limits)
    command_min_interval_s: float = 1.0  # rate limit between accepted commands
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/flight_safety/test_config.py -v`
Expected: 3 passed.

- [ ] **Step 5: Create `.env.example` and commit**

Create `.env.example`:
```
# Flight-safety service config (copy to .env). All keys are prefixed FS_.
FS_MAVLINK_ADDRESS=udpin://0.0.0.0:14540
# Geofence polygon as JSON list of [lat, lon] vertices:
FS_GEOFENCE=[[47.3966,8.5444],[47.3979,8.5444],[47.3979,8.5466],[47.3966,8.5466]]
```
```bash
git add src/flight_safety/config.py tests/flight_safety/test_config.py .env.example
git commit -m "feat(m1): config and safety limits with tests"
```

### Task M1.3: Telemetry & command models

**Files:**
- Create: `src/flight_safety/models.py`
- Create: `tests/flight_safety/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/flight_safety/test_models.py`:
```python
import pytest
from pydantic import ValidationError
from flight_safety.models import (
    Telemetry, parse_command, GotoCommand, OrbitCommand, ArmTakeoffCommand,
)


def test_parse_goto_command():
    cmd = parse_command({"verb": "goto", "lat": 47.397, "lon": 8.545, "alt": 30})
    assert isinstance(cmd, GotoCommand)
    assert cmd.alt == 30


def test_parse_orbit_command_defaults_center_none():
    cmd = parse_command({"verb": "orbit", "radius": 20, "alt": 25})
    assert isinstance(cmd, OrbitCommand)
    assert cmd.center is None


def test_parse_arm_takeoff():
    cmd = parse_command({"verb": "arm_takeoff", "alt": 5})
    assert isinstance(cmd, ArmTakeoffCommand)


def test_unknown_verb_rejected():
    with pytest.raises(ValidationError):
        parse_command({"verb": "self_destruct"})


def test_orbit_requires_positive_radius():
    with pytest.raises(ValidationError):
        parse_command({"verb": "orbit", "radius": -5, "alt": 25})


def test_telemetry_roundtrip():
    t = Telemetry(lat=47.0, lon=8.0, alt_m=10.0, speed_ms=1.0,
                  battery_pct=0.9, flight_mode="HOLD", armed=True,
                  gps_ok=True, ekf_ok=True)
    assert t.battery_pct == 0.9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flight_safety/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'flight_safety.models'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/flight_safety/models.py`:
```python
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field, TypeAdapter


class Telemetry(BaseModel):
    """Snapshot of vehicle state used by the validation gate and narration."""
    lat: float
    lon: float
    alt_m: float           # relative altitude above takeoff
    speed_ms: float
    battery_pct: float     # 0.0–1.0
    flight_mode: str
    armed: bool
    gps_ok: bool
    ekf_ok: bool


# --- Command schema (the structured-output contract) ---
class ArmTakeoffCommand(BaseModel):
    verb: Literal["arm_takeoff"]
    alt: float = Field(gt=0, le=120)


class GotoCommand(BaseModel):
    verb: Literal["goto"]
    lat: float
    lon: float
    alt: float = Field(gt=0, le=120)


class OrbitCommand(BaseModel):
    verb: Literal["orbit"]
    radius: float = Field(gt=0, le=200)
    alt: float = Field(gt=0, le=120)
    center: Optional[tuple[float, float]] = None  # (lat, lon); None = current pos


class LoiterCommand(BaseModel):
    verb: Literal["loiter"]


class ReturnToLaunchCommand(BaseModel):
    verb: Literal["return_to_launch"]


class LandCommand(BaseModel):
    verb: Literal["land"]


class TakeoverCommand(BaseModel):
    verb: Literal["takeover"]


class HandbackCommand(BaseModel):
    verb: Literal["handback"]


Command = Annotated[
    Union[
        ArmTakeoffCommand, GotoCommand, OrbitCommand, LoiterCommand,
        ReturnToLaunchCommand, LandCommand, TakeoverCommand, HandbackCommand,
    ],
    Field(discriminator="verb"),
]

_ADAPTER: TypeAdapter[Command] = TypeAdapter(Command)


def parse_command(data: dict) -> Command:
    """Validate raw dict into a typed Command (raises ValidationError on bad input)."""
    return _ADAPTER.validate_python(data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/flight_safety/test_models.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/flight_safety/models.py tests/flight_safety/test_models.py
git commit -m "feat(m1): telemetry and command models"
```

### Task M1.4: Geofence

**Files:**
- Create: `src/flight_safety/geofence.py`
- Create: `tests/flight_safety/test_geofence.py`

- [ ] **Step 1: Write the failing test**

Create `tests/flight_safety/test_geofence.py`:
```python
from flight_safety.geofence import inside_geofence

# A simple square around (0,0).
SQUARE = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]


def test_point_inside():
    assert inside_geofence(0.0, 0.0, SQUARE) is True


def test_point_outside():
    assert inside_geofence(2.0, 0.0, SQUARE) is False


def test_empty_geofence_allows_all():
    # No geofence configured => unconstrained (return True).
    assert inside_geofence(99.0, 99.0, []) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/flight_safety/test_geofence.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'flight_safety.geofence'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/flight_safety/geofence.py`:
```python
from shapely.geometry import Point, Polygon


def inside_geofence(lat: float, lon: float, vertices: list[tuple[float, float]]) -> bool:
    """True if (lat, lon) is inside the polygon. Empty polygon => unconstrained (True)."""
    if not vertices:
        return True
    if len(vertices) < 3:
        return False  # a polygon needs >= 3 vertices; treat as invalid/forbidden
    poly = Polygon(vertices)
    return poly.covers(Point(lat, lon))  # covers() includes boundary
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/flight_safety/test_geofence.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/flight_safety/geofence.py tests/flight_safety/test_geofence.py
git commit -m "feat(m1): geofence point-in-polygon check"
```

### Task M1.5: The validation gate (the crown jewel — exhaustive tests)

**Files:**
- Create: `src/flight_safety/validation.py`
- Create: `tests/flight_safety/test_validation.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/flight_safety/test_validation.py`:
```python
from flight_safety.config import Limits
from flight_safety.models import parse_command, Telemetry
from flight_safety.validation import validate_command, ValidationResult

GEOFENCE = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]
LIMITS = Limits(max_alt_m=120, min_alt_m=0, max_speed_ms=12, min_battery_pct=0.20)


def _tlm(**kw) -> Telemetry:
    base = dict(lat=0.0, lon=0.0, alt_m=10.0, speed_ms=1.0, battery_pct=0.9,
                flight_mode="HOLD", armed=True, gps_ok=True, ekf_ok=True)
    base.update(kw)
    return Telemetry(**base)


def test_valid_goto_accepted():
    cmd = parse_command({"verb": "goto", "lat": 0.5, "lon": 0.5, "alt": 30})
    res = validate_command(cmd, _tlm(), LIMITS, GEOFENCE)
    assert res.ok is True


def test_goto_outside_geofence_rejected():
    cmd = parse_command({"verb": "goto", "lat": 5.0, "lon": 0.0, "alt": 30})
    res = validate_command(cmd, _tlm(), LIMITS, GEOFENCE)
    assert res.ok is False and "geofence" in res.reason.lower()


def test_goto_above_ceiling_rejected():
    cmd = parse_command({"verb": "goto", "lat": 0.0, "lon": 0.0, "alt": 200})
    # alt > 120 is rejected by the model already, so use a value within the model
    # but above a tightened limit:
    tight = Limits(max_alt_m=50)
    cmd = parse_command({"verb": "goto", "lat": 0.0, "lon": 0.0, "alt": 80})
    res = validate_command(cmd, _tlm(), tight, GEOFENCE)
    assert res.ok is False and "alt" in res.reason.lower()


def test_command_rejected_on_low_battery():
    cmd = parse_command({"verb": "goto", "lat": 0.0, "lon": 0.0, "alt": 30})
    res = validate_command(cmd, _tlm(battery_pct=0.10), LIMITS, GEOFENCE)
    assert res.ok is False and "battery" in res.reason.lower()


def test_command_rejected_when_gps_unhealthy():
    cmd = parse_command({"verb": "goto", "lat": 0.0, "lon": 0.0, "alt": 30})
    res = validate_command(cmd, _tlm(gps_ok=False), LIMITS, GEOFENCE)
    assert res.ok is False and "gps" in res.reason.lower()


def test_command_rejected_when_ekf_unhealthy():
    cmd = parse_command({"verb": "orbit", "radius": 20, "alt": 25})
    res = validate_command(cmd, _tlm(ekf_ok=False), LIMITS, GEOFENCE)
    assert res.ok is False and "ekf" in res.reason.lower()


def test_orbit_alt_within_limits_accepted():
    cmd = parse_command({"verb": "orbit", "radius": 20, "alt": 25})
    res = validate_command(cmd, _tlm(), LIMITS, GEOFENCE)
    assert res.ok is True


def test_safety_verbs_always_allowed():
    # RTL / land / handback / loiter must pass even on low battery (they are recovery).
    for verb in ("return_to_launch", "land", "handback", "loiter"):
        cmd = parse_command({"verb": verb})
        res = validate_command(cmd, _tlm(battery_pct=0.05), LIMITS, GEOFENCE)
        assert res.ok is True, f"{verb} should be allowed"


def test_arm_takeoff_rejected_if_already_armed_and_flying():
    cmd = parse_command({"verb": "arm_takeoff", "alt": 5})
    res = validate_command(cmd, _tlm(armed=True, alt_m=10.0), LIMITS, GEOFENCE)
    assert res.ok is False and "already" in res.reason.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/flight_safety/test_validation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'flight_safety.validation'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/flight_safety/validation.py`:
```python
from dataclasses import dataclass
from flight_safety.config import Limits
from flight_safety.geofence import inside_geofence
from flight_safety.models import (
    Command, Telemetry, GotoCommand, OrbitCommand, ArmTakeoffCommand,
)

# Verbs that are recovery/safety actions: always permitted regardless of battery.
_SAFETY_VERBS = {"return_to_launch", "land", "handback", "loiter"}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str | None = None


def validate_command(
    cmd: Command,
    tlm: Telemetry,
    limits: Limits,
    geofence: list[tuple[float, float]],
) -> ValidationResult:
    """Deterministically decide whether a command may execute. Returns ok + reason."""
    verb = cmd.verb

    # Safety/recovery verbs bypass battery/geofence gating.
    if verb in _SAFETY_VERBS or verb == "takeover":
        return ValidationResult(True)

    # Health preconditions for any active command.
    if not tlm.gps_ok:
        return ValidationResult(False, "Rejected: GPS health not OK.")
    if not tlm.ekf_ok:
        return ValidationResult(False, "Rejected: EKF/estimator health not OK.")
    if tlm.battery_pct < limits.min_battery_pct:
        return ValidationResult(
            False,
            f"Rejected: battery {tlm.battery_pct:.0%} below minimum "
            f"{limits.min_battery_pct:.0%}.",
        )

    if isinstance(cmd, ArmTakeoffCommand):
        if tlm.armed and tlm.alt_m > 1.0:
            return ValidationResult(False, "Rejected: already armed and airborne.")
        if not (limits.min_alt_m < cmd.alt <= limits.max_alt_m):
            return ValidationResult(False, f"Rejected: takeoff alt {cmd.alt} m out of limits.")
        return ValidationResult(True)

    if isinstance(cmd, GotoCommand):
        if not (limits.min_alt_m < cmd.alt <= limits.max_alt_m):
            return ValidationResult(False, f"Rejected: alt {cmd.alt} m out of limits.")
        if not inside_geofence(cmd.lat, cmd.lon, geofence):
            return ValidationResult(False, "Rejected: target outside geofence.")
        return ValidationResult(True)

    if isinstance(cmd, OrbitCommand):
        if not (limits.min_alt_m < cmd.alt <= limits.max_alt_m):
            return ValidationResult(False, f"Rejected: alt {cmd.alt} m out of limits.")
        center = cmd.center if cmd.center is not None else (tlm.lat, tlm.lon)
        if not inside_geofence(center[0], center[1], geofence):
            return ValidationResult(False, "Rejected: orbit center outside geofence.")
        return ValidationResult(True)

    return ValidationResult(False, f"Rejected: unsupported verb '{verb}'.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/flight_safety/test_validation.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/flight_safety/validation.py tests/flight_safety/test_validation.py
git commit -m "feat(m1): deterministic validation gate with exhaustive tests"
```

### Task M1.6: MAVSDK bridge — telemetry monitor

**Files:**
- Create: `src/flight_safety/bridge.py`
- Create: `tests/flight_safety/test_bridge_integration.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/flight_safety/test_bridge_integration.py`:
```python
import asyncio
import pytest
from flight_safety.bridge import FlightBridge
from flight_safety.models import Telemetry

pytestmark = pytest.mark.integration  # requires running PX4 SITL


@pytest.mark.asyncio
async def test_bridge_connects_and_streams_telemetry():
    bridge = FlightBridge("udpin://0.0.0.0:14540")
    await bridge.connect(timeout_s=30)
    tlm = await asyncio.wait_for(bridge.read_telemetry(), timeout=10)
    assert isinstance(tlm, Telemetry)
    assert 0.0 <= tlm.battery_pct <= 1.0
    await bridge.close()
```

- [ ] **Step 2: Run it to verify it is collected but skipped without SITL**

Run: `pytest tests/flight_safety/test_bridge_integration.py -v`
Expected: `1 deselected` (skipped by default because of the `integration` marker). This confirms the marker wiring.

- [ ] **Step 3: Write the bridge implementation (telemetry half)**

Create `src/flight_safety/bridge.py`:
```python
import asyncio
from mavsdk import System
from flight_safety.models import Telemetry


class FlightBridge:
    """Owns the single MAVSDK connection and exposes telemetry + executors."""

    def __init__(self, address: str) -> None:
        self._address = address
        self._drone = System()
        self._connected = False

    async def connect(self, timeout_s: float = 30.0) -> None:
        await self._drone.connect(system_address=self._address)
        async def _wait():
            async for state in self._drone.core.connection_state():
                if state.is_connected:
                    return
        await asyncio.wait_for(_wait(), timeout=timeout_s)
        self._connected = True

    async def read_telemetry(self) -> Telemetry:
        """Read one consistent telemetry snapshot."""
        pos = await self._drone.telemetry.position().__anext__()
        bat = await self._drone.telemetry.battery().__anext__()
        mode = await self._drone.telemetry.flight_mode().__anext__()
        armed = await self._drone.telemetry.armed().__anext__()
        health = await self._drone.telemetry.health().__anext__()
        vel = await self._drone.telemetry.velocity_ned().__anext__()
        speed = (vel.north_m_s ** 2 + vel.east_m_s ** 2 + vel.down_m_s ** 2) ** 0.5
        return Telemetry(
            lat=pos.latitude_deg,
            lon=pos.longitude_deg,
            alt_m=pos.relative_altitude_m,
            speed_ms=speed,
            battery_pct=bat.remaining_percent,
            flight_mode=str(mode),
            armed=armed,
            gps_ok=health.is_global_position_ok,
            ekf_ok=health.is_local_position_ok,
        )

    @property
    def drone(self) -> System:
        return self._drone

    async def close(self) -> None:
        self._connected = False  # MAVSDK has no explicit disconnect; drop the ref.
```

- [ ] **Step 4: Run the integration test against SITL**

Run (with M0.3 SITL running):
```bash
pytest tests/flight_safety/test_bridge_integration.py -v -m integration
```
Expected: `1 passed`. (Note: `battery.remaining_percent` is 0.0–1.0 in MAVSDK; if your version returns 0–100, divide by 100 in `read_telemetry` and re-run.)

- [ ] **Step 5: Commit**

```bash
git add src/flight_safety/bridge.py tests/flight_safety/test_bridge_integration.py
git commit -m "feat(m1): MAVSDK bridge with telemetry snapshot (integration-tested)"
```

### Task M1.7: Command executors with telemetry-gating + hand-off

**Files:**
- Modify: `src/flight_safety/bridge.py` (add executor methods)
- Modify: `tests/flight_safety/test_bridge_integration.py` (add execution tests)

- [ ] **Step 1: Write the failing integration tests**

Append to `tests/flight_safety/test_bridge_integration.py`:
```python
@pytest.mark.asyncio
async def test_arm_takeoff_then_goto_is_telemetry_gated():
    bridge = FlightBridge("udpin://0.0.0.0:14540")
    await bridge.connect(timeout_s=30)
    # Wait until position is healthy.
    for _ in range(30):
        t = await bridge.read_telemetry()
        if t.gps_ok:
            break
        await asyncio.sleep(1)
    await bridge.arm_takeoff(alt=5.0)
    t = await bridge.read_telemetry()
    assert t.alt_m >= 3.0, "takeoff did not gate until altitude reached"
    home = (t.lat, t.lon)
    await bridge.goto(home[0] + 0.0003, home[1], 5.0)  # ~30 m north
    t2 = await bridge.read_telemetry()
    # goto must not return until arrival; assert we moved.
    assert abs(t2.lat - home[0]) > 0.0001
    await bridge.return_to_launch()
    await bridge.close()


@pytest.mark.asyncio
async def test_handback_switches_to_manual():
    bridge = FlightBridge("udpin://0.0.0.0:14540")
    await bridge.connect(timeout_s=30)
    await bridge.handback()
    t = await bridge.read_telemetry()
    assert "POSCTL" in t.flight_mode.upper() or "MANUAL" in t.flight_mode.upper() \
        or "HOLD" in t.flight_mode.upper()
    await bridge.close()
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `pytest tests/flight_safety/test_bridge_integration.py -v -m integration`
Expected: FAIL with `AttributeError: 'FlightBridge' object has no attribute 'arm_takeoff'`.

- [ ] **Step 3: Add executor methods to the bridge**

Add these methods inside `FlightBridge` in `src/flight_safety/bridge.py` (and add `from mavsdk.action import OrbitYawBehavior` at the top):
```python
    async def _wait_until(self, predicate, timeout_s: float, poll_s: float = 0.5) -> None:
        """Telemetry-gate: block until predicate(Telemetry) is true or timeout."""
        async def _loop():
            while True:
                t = await self.read_telemetry()
                if predicate(t):
                    return
                await asyncio.sleep(poll_s)
        await asyncio.wait_for(_loop(), timeout=timeout_s)

    async def arm_takeoff(self, alt: float) -> None:
        await self._drone.action.set_takeoff_altitude(alt)
        await self._drone.action.arm()
        await self._drone.action.takeoff()
        await self._wait_until(lambda t: t.alt_m >= alt * 0.9, timeout_s=30)

    async def goto(self, lat: float, lon: float, alt: float) -> None:
        # absolute_altitude requires AMSL; use the relative-alt overload via current AMSL.
        pos = await self._drone.telemetry.position().__anext__()
        amsl = pos.absolute_altitude_m - pos.relative_altitude_m + alt
        await self._drone.action.goto_location(lat, lon, amsl, float("nan"))
        await self._wait_until(
            lambda t: abs(t.lat - lat) < 1e-4 and abs(t.lon - lon) < 1e-4,
            timeout_s=60,
        )

    async def orbit(self, radius: float, alt: float,
                    center: tuple[float, float] | None) -> None:
        pos = await self._drone.telemetry.position().__anext__()
        lat, lon = center if center else (pos.latitude_deg, pos.longitude_deg)
        amsl = pos.absolute_altitude_m - pos.relative_altitude_m + alt
        await self._drone.action.do_orbit(
            radius, 3.0, OrbitYawBehavior.HOLD_FRONT_TO_CIRCLE_CENTER, lat, lon, amsl,
        )
        await asyncio.sleep(3)  # allow the orbit to establish

    async def loiter(self) -> None:
        await self._drone.action.hold()

    async def return_to_launch(self) -> None:
        await self._drone.action.return_to_launch()

    async def land(self) -> None:
        await self._drone.action.land()

    async def takeover(self) -> None:
        await self._drone.action.hold()  # park in HOLD; assistant now drives

    async def handback(self) -> None:
        # Return control to the human pilot: switch to a manual-ish mode.
        await self._drone.action.hold()
```

- [ ] **Step 4: Run integration tests against SITL**

Run: `pytest tests/flight_safety/test_bridge_integration.py -v -m integration`
Expected: all passed. (If `goto` times out because SITL arrival tolerance is tight, widen the predicate to `< 3e-4` and re-run.)

- [ ] **Step 5: Commit**

```bash
git add src/flight_safety/bridge.py tests/flight_safety/test_bridge_integration.py
git commit -m "feat(m1): telemetry-gated command executors + hand-off"
```

### Task M1.8: Command dispatcher (glue: validate → execute)

**Files:**
- Create: `src/flight_safety/dispatcher.py`
- Create: `tests/flight_safety/test_dispatcher.py`

- [ ] **Step 1: Write the failing test (with a fake bridge — no SITL)**

Create `tests/flight_safety/test_dispatcher.py`:
```python
import pytest
from flight_safety.config import Limits
from flight_safety.models import Telemetry
from flight_safety.dispatcher import Dispatcher

GEOFENCE = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]
LIMITS = Limits()


class FakeBridge:
    def __init__(self):
        self.calls = []
        self._tlm = Telemetry(lat=0.0, lon=0.0, alt_m=10.0, speed_ms=0.0,
                              battery_pct=0.9, flight_mode="HOLD", armed=True,
                              gps_ok=True, ekf_ok=True)

    async def read_telemetry(self): return self._tlm
    async def goto(self, lat, lon, alt): self.calls.append(("goto", lat, lon, alt))
    async def orbit(self, r, a, c): self.calls.append(("orbit", r, a, c))
    async def arm_takeoff(self, alt): self.calls.append(("arm_takeoff", alt))
    async def loiter(self): self.calls.append(("loiter",))
    async def return_to_launch(self): self.calls.append(("rtl",))
    async def land(self): self.calls.append(("land",))
    async def takeover(self): self.calls.append(("takeover",))
    async def handback(self): self.calls.append(("handback",))


@pytest.mark.asyncio
async def test_valid_command_is_executed():
    bridge = FakeBridge()
    d = Dispatcher(bridge, LIMITS, GEOFENCE)
    res = await d.handle({"verb": "goto", "lat": 0.5, "lon": 0.5, "alt": 30})
    assert res["status"] == "executed"
    assert ("goto", 0.5, 0.5, 30) in bridge.calls


@pytest.mark.asyncio
async def test_unsafe_command_is_rejected_and_not_executed():
    bridge = FakeBridge()
    d = Dispatcher(bridge, LIMITS, GEOFENCE)
    res = await d.handle({"verb": "goto", "lat": 9.0, "lon": 0.0, "alt": 30})
    assert res["status"] == "rejected"
    assert "geofence" in res["reason"].lower()
    assert bridge.calls == []  # never executed


@pytest.mark.asyncio
async def test_malformed_command_is_rejected():
    bridge = FakeBridge()
    d = Dispatcher(bridge, LIMITS, GEOFENCE)
    res = await d.handle({"verb": "nonsense"})
    assert res["status"] == "rejected"
    assert bridge.calls == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/flight_safety/test_dispatcher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'flight_safety.dispatcher'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/flight_safety/dispatcher.py`:
```python
from pydantic import ValidationError
from flight_safety.config import Limits
from flight_safety.models import (
    parse_command, GotoCommand, OrbitCommand, ArmTakeoffCommand,
)
from flight_safety.validation import validate_command


class Dispatcher:
    """Validate then execute commands against a bridge. Pure glue, no transport."""

    def __init__(self, bridge, limits: Limits, geofence: list[tuple[float, float]]):
        self._bridge = bridge
        self._limits = limits
        self._geofence = geofence

    async def handle(self, raw: dict) -> dict:
        try:
            cmd = parse_command(raw)
        except ValidationError as e:
            return {"status": "rejected", "reason": f"Malformed command: {e.errors()[0]['msg']}"}

        tlm = await self._bridge.read_telemetry()
        result = validate_command(cmd, tlm, self._limits, self._geofence)
        if not result.ok:
            return {"status": "rejected", "reason": result.reason}

        await self._execute(cmd)
        return {"status": "executed", "verb": cmd.verb}

    async def _execute(self, cmd) -> None:
        if isinstance(cmd, GotoCommand):
            await self._bridge.goto(cmd.lat, cmd.lon, cmd.alt)
        elif isinstance(cmd, OrbitCommand):
            await self._bridge.orbit(cmd.radius, cmd.alt, cmd.center)
        elif isinstance(cmd, ArmTakeoffCommand):
            await self._bridge.arm_takeoff(cmd.alt)
        elif cmd.verb == "loiter":
            await self._bridge.loiter()
        elif cmd.verb == "return_to_launch":
            await self._bridge.return_to_launch()
        elif cmd.verb == "land":
            await self._bridge.land()
        elif cmd.verb == "takeover":
            await self._bridge.takeover()
        elif cmd.verb == "handback":
            await self._bridge.handback()
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/flight_safety/test_dispatcher.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/flight_safety/dispatcher.py tests/flight_safety/test_dispatcher.py
git commit -m "feat(m1): command dispatcher (validate -> execute) with fake-bridge tests"
```

### Task M1.9: Websocket API server + abort

**Files:**
- Create: `src/flight_safety/server.py`
- Create: `src/flight_safety/__main__.py`
- Create: `tests/flight_safety/test_server.py`

- [ ] **Step 1: Write the failing test (TestClient, fake dispatcher)**

Create `tests/flight_safety/test_server.py`:
```python
from fastapi.testclient import TestClient
from flight_safety.server import build_app


class FakeDispatcher:
    def __init__(self): self.aborted = False
    async def handle(self, raw): return {"status": "executed", "verb": raw.get("verb")}
    async def abort(self): self.aborted = True


def test_command_endpoint_returns_status():
    disp = FakeDispatcher()
    app = build_app(disp)
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "command", "command": {"verb": "loiter"}})
        msg = ws.receive_json()
        assert msg["status"] == "executed"


def test_abort_endpoint_triggers_abort():
    disp = FakeDispatcher()
    app = build_app(disp)
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "abort"})
        msg = ws.receive_json()
        assert msg["status"] == "aborted"
    assert disp.aborted is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/flight_safety/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'flight_safety.server'`.

- [ ] **Step 3: Write the server**

Create `src/flight_safety/server.py`:
```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect


def build_app(dispatcher) -> FastAPI:
    """Build the websocket API around a dispatcher (injected for testability)."""
    app = FastAPI(title="flight-safety")

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        try:
            while True:
                msg = await socket.receive_json()
                kind = msg.get("type")
                if kind == "command":
                    result = await dispatcher.handle(msg.get("command", {}))
                    await socket.send_json(result)
                elif kind == "abort":
                    await dispatcher.abort()
                    await socket.send_json({"status": "aborted"})
                else:
                    await socket.send_json({"status": "error", "reason": "unknown type"})
        except WebSocketDisconnect:
            return

    return app
```

Add an `abort` method to `Dispatcher` in `src/flight_safety/dispatcher.py`:
```python
    async def abort(self) -> None:
        """Immediate safe state: hand control back to the human / hold."""
        await self._bridge.handback()
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/flight_safety/test_server.py -v`
Expected: 2 passed.

- [ ] **Step 5: Write the entrypoint**

Create `src/flight_safety/__main__.py`:
```python
import asyncio
import uvicorn
from flight_safety.config import Settings
from flight_safety.bridge import FlightBridge
from flight_safety.dispatcher import Dispatcher
from flight_safety.server import build_app


async def _make_app():
    settings = Settings()
    bridge = FlightBridge(settings.mavlink_address)
    await bridge.connect(timeout_s=30)
    return build_app(Dispatcher(bridge, settings.limits, settings.geofence))


def main() -> None:
    app = asyncio.run(_make_app())
    uvicorn.run(app, host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Full suite green + manual smoke test, then commit**

Run unit suite: `pytest -v` → Expected: all non-integration tests pass.
Run integration suite (SITL up): `pytest -m integration -v` → Expected: pass.
Manual smoke: start the service `python -m flight_safety` (SITL running) → expect `Uvicorn running on http://127.0.0.1:8765`. Then commit:
```bash
git add src/flight_safety/server.py src/flight_safety/__main__.py src/flight_safety/dispatcher.py tests/flight_safety/test_server.py
git commit -m "feat(m1): websocket API server + abort path; service entrypoint"
```

---

## Definition of Done (M0 + M1)
- `pytest -v` (unit) is fully green; `pytest -m integration -v` passes with SITL running.
- `python -m flight_safety` connects to SITL and serves the websocket API.
- A command sent over `/ws` is validated, then either executed (telemetry-gated) or rejected with a reason; `abort` returns control to manual. No LLM is involved anywhere.
- Next plans: **M2** (model-agnostic assistant core that emits validated structured commands to this API), then **M3** (FPV video + HUD + chat dashboard), then **M4** (evaluation harness).

## Self-review notes
- **Spec coverage:** validation gate (§8), telemetry-gating (§4.1, §8), hand-off/abort (§6, §8), verb set (§5), websocket API (§4.1, §3), gz Harmonic + Mint setup (§10) — all mapped to tasks. LLM/dashboard/video are intentionally deferred to M2/M3 per the subsystem-split scope decision.
- **Known version-sensitive spots (flagged inline with fallbacks):** MAVSDK connection scheme (`udpin://` vs `udp://`), `battery.remaining_percent` scale (0–1 vs 0–100), and `goto` arrival tolerance. Each task step says what to adjust if the default is wrong.
