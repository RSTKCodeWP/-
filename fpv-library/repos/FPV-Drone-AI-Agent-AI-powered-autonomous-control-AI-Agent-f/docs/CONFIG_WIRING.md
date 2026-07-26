# Runtime Config Wiring Complete

The nanohawk-agent bootstrap now fully supports runtime config-driven endpoint selection from `config/endpoints.yaml`.

## What was implemented:

### 1. Bootstrap Config Loading (`src/app/Bootstrap.cpp`)
- Added `buildFromConfig(endpointsConfigPath)` method that loads endpoints from YAML
- Minimal regex-based YAML parser (no external dependencies)
- Multi-path search candidates for resilient config discovery:
  - Requested path
  - `config/endpoints.yaml`
  - `../config/endpoints.yaml` 
  - `../../config/endpoints.yaml`

### 2. Endpoint Selection Logic
- **LLM endpoint:** `llm.base_url` ? passed to `LlmClient`
- **MAVLink endpoint (priority order):**
  1. `mavlink.udp_listen` (primary, if set)
  2. `mavlink.serial_port` + `mavlink.serial_baud` (fallback when UDP unset)
  3. Default `udp://0.0.0.0:14550` (when config missing/empty)

### 3. ArduPilotGuidedAdapter Wiring
- Added constructor parameter: `ArduPilotGuidedAdapter(std::string mavlinkEndpoint)`
- Transport now initializes with configured endpoint
- Bootstrap composition injects endpoint into guided adapter

### 4. Runtime Entry Point (`src/main.cpp`)
- Switched from hardcoded endpoints to `bootstrap.buildFromConfig()`
- CLI now respects `config/endpoints.yaml` at startup

### 5. Test Coverage
- **`test_pipeline.cpp`:** Uses explicit endpoint override (unchanged)
- **`test_transports.cpp`:** Validates transport fallback errors
- **`test_config_wiring.cpp`:** NEW test that validates:
  - Default UDP config loading
  - Serial fallback config loading (`endpoints_serial.yaml`)
  - Explicit endpoint override

## Validation Run

```powershell
PS D:\DroneAI\nanohawk-agent> ctest --preset ci
Test project D:/DroneAI/nanohawk-agent/build/ci
    Start 1: nanohawk_unit_pipeline
1/1 Test #1: nanohawk_unit_pipeline ...........   Passed    0.18 sec
    Start 2: nanohawk_transport_checks
2/2 Test #2: nanohawk_transport_checks ........   Passed    0.17 sec
    Start 3: nanohawk_config_wiring
3/3 Test #3: nanohawk_config_wiring ...........   Passed    0.19 sec

100% tests passed, 0 tests failed out of 3

Total Test time (real) =   0.54 sec
```

## Example Configurations

### UDP (default `config/endpoints.yaml`)
```yaml
mavlink:
  udp_listen: udp://0.0.0.0:14550
llm:
  base_url: http://127.0.0.1:8080/v1
```

### Serial (`config/endpoints_serial.yaml`)
```yaml
mavlink:
  # udp_listen: udp://0.0.0.0:14550  # Commented out ? serial fallback activates
  serial_port: COM6
  serial_baud: 115200
llm:
  base_url: http://127.0.0.1:8080/v1
```

## Benefits

- **Zero hardcoded endpoints in runtime path** ? all driven by config
- **Automatic serial fallback** when UDP unavailable/unset
- **Deterministic defaults** when config missing
- **Test-friendly** ? explicit override still available via `build(llm, mavlink)`
- **Safe fallback** ? missing config/keys fall back to hardcoded defaults

The system now cleanly separates compile-time feature flags (MAVSDK/OpenCV/CURL) from runtime endpoint configuration (UDP vs serial, local vs remote LLM).

